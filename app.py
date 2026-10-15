"""Job Desk app. Double-click "Start Job Desk.bat" (Windows) or run:  python app.py

Serves ui.html on http://localhost:PORT (this computer only), runs Claude Code in the background when you click
"Find & draft", and stops by itself a few minutes after you close the window.
Same file as grant-desk/app.py except the import and settings below.
"""
import contextlib, io, json, mimetypes, os, platform, shutil, subprocess, sys, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

import jobs as data  # the only line that differs between desks, plus the settings below

TITLE = "Job Desk"
PORT = 8765
PROFILE = "profile.md"
COMMAND = ".claude/commands/apply.md"
ORDER = ["drafted", "ready", "interview", "offer", "applied", "new", "rejected", "skip"]

HERE = Path(__file__).resolve().parent
DRAFTS = HERE / "applications"
LOG = HERE / "desk.log"
CLAUDE_TOOLS = ["Bash(python *)", "PowerShell(python *)", "WebFetch", "WebSearch"]
IDLE_EXIT = 240  # seconds without a ping from the window before the server stops itself

lock = threading.Lock()  # one writer of the CSV at a time
state = {"ping": time.time(), "proc": None, "events": [], "usage": None, "started": 0}


# ---------- data ----------
def items():
    rank = {s: i for i, s in enumerate(ORDER)}
    out = []
    for r in data.load():
        folder = DRAFTS / data.slug(r)
        md = folder / "application.md"
        files = sorted(p.name for p in folder.glob("*") if p.is_file()) if folder.exists() else []
        out.append(dict(r, slug=folder.name, application=md.read_text(encoding="utf-8") if md.exists() else "", files=files))
    return sorted(out, key=lambda r: (rank.get(r["status"], 99), -float(r.get("score") or 0)))


def health():
    todos = (HERE / PROFILE).read_text(encoding="utf-8").count("TODO") if (HERE / PROFILE).exists() else 0
    return {
        "python": platform.python_version(),
        "claude": bool(shutil.which("claude")),
        "profile": (HERE / PROFILE).exists() and not todos,
        "todos": todos,
        "csv": data.CSV_PATH.exists(),
    }


# ---------- Claude Code runner ----------
def describe(name, inp):
    """Turn a Claude tool call into one plain-English activity line."""
    if name in ("Bash", "PowerShell"):
        cmd = inp.get("command", "")
        for key, text in data.ACTIVITY:
            if key in cmd:
                return text
        return "Running " + cmd[:90]
    path = inp.get("file_path") or inp.get("path") or ""
    rel = Path(path).name if path else ""
    if path and HERE in Path(path).resolve().parents:
        rel = str(Path(path).resolve().relative_to(HERE)).replace("\\", "/")
    return {
        "Read": f"Reading {rel}", "Write": f"Writing {rel}", "Edit": f"Updating {rel}",
        "WebFetch": f"Reading {urlparse(inp.get('url', '')).netloc}", "WebSearch": f"Searching the web for “{inp.get('query', '')}”",
        "Glob": "Looking through files", "Grep": "Searching files", "TodoWrite": "Planning the next steps",
    }.get(name, name)


def pump(proc):
    events = state["events"]
    for line in proc.stdout:
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except ValueError:
            events.append({"kind": "warn", "text": line[:300]})
            continue
        if e.get("type") == "assistant":
            for c in e["message"].get("content", []):
                if c.get("type") == "tool_use":
                    events.append({"kind": "step", "text": describe(c["name"], c.get("input") or {})})
                elif c.get("type") == "text" and c["text"].strip():
                    events.append({"kind": "say", "text": c["text"].strip()[:400]})
        elif e.get("type") == "rate_limit_event":
            w = (e.get("rate_limit_info") or {}).get("unifiedWindows") or {}
            state["usage"] = {k: round(v.get("utilization", 0) * 100) for k, v in w.items()}
        elif e.get("type") == "result":
            if events and events[-1]["kind"] == "say" and (e.get("result") or "").strip().startswith(events[-1]["text"][:200]):
                events.pop()  # the final message is shown as the summary; don't list it twice
            events.append({"kind": "error" if e.get("is_error") else "done", "text": e.get("result") or "",
                           "cost": e.get("total_cost_usd")})
    code = proc.wait()
    if not any(ev["kind"] in ("done", "error") for ev in events):
        events.append({"kind": "error", "text": f"Claude stopped before finishing (exit code {code}). "
                                                "If it says you're not logged in, open a terminal and run: claude"})
    print(f"{time.strftime('%Y-%m-%d %H:%M')} Claude run ended ({events[-1]['kind']}): {events[-1]['text'][:300]}")
    for ev in events:  # keep warnings in desk.log so a failed run can be diagnosed later
        if ev["kind"] == "warn":
            print("  warning:", ev["text"])


def start_claude(limit):
    if state["proc"] and state["proc"].poll() is None:
        return "Claude is already working."
    exe = shutil.which("claude")
    if not exe:
        return "Claude Code isn't installed. Open the Guide and follow “Set up this computer”."
    prompt = (HERE / COMMAND).read_text(encoding="utf-8").split("---", 2)[-1].replace("$ARGUMENTS", str(limit))
    cmd = [exe, "-p", "--output-format", "stream-json", "--verbose", "--permission-mode", "acceptEdits",
           "--allowedTools", *CLAUDE_TOOLS]
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    proc = subprocess.Popen(cmd, cwd=HERE, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace", creationflags=flags)
    proc.stdin.write(prompt)  # stdin, not argv: Windows .cmd shims mangle long prompts with special characters
    proc.stdin.close()
    state.update(proc=proc, events=[{"kind": "step", "text": "Starting Claude"}], started=time.time())
    print(f"{time.strftime('%Y-%m-%d %H:%M')} Claude run started (up to {limit} drafts)")
    threading.Thread(target=pump, args=(proc,), daemon=True).start()
    return ""


def stop_claude():
    proc = state["proc"]
    if proc and proc.poll() is None:
        if os.name == "nt":  # kill the whole tree: the .cmd shim, node, and anything it started
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        else:
            proc.terminate()
        state["events"].append({"kind": "error", "text": "Stopped. Anything Claude already saved is kept."})


def open_folder(slug):
    folder = (DRAFTS / slug).resolve()
    if DRAFTS.resolve() not in folder.parents or not folder.is_dir():
        return False
    if os.name == "nt":
        os.startfile(folder)
    else:
        subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)])
    return True


# ---------- HTTP ----------
class Handler(BaseHTTPRequestHandler):
    def reply(self, code, body, ctype="application/json"):
        raw = json.dumps(body).encode() if ctype == "application/json" else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        state["ping"] = time.time()
        url = urlparse(self.path)
        path = unquote(url.path)
        if path == "/":
            return self.reply(200, (HERE / "ui.html").read_bytes(), "text/html; charset=utf-8")
        if path in ("/logo-light.png", "/logo-dark.png") and (HERE / path[1:]).exists():
            return self.reply(200, (HERE / path[1:]).read_bytes(), "image/png")
        if path == "/api/items":
            return self.reply(200, {"items": items(), "health": health()})
        if path == "/api/run":
            since = int(parse_qs(url.query).get("since", ["0"])[0])
            proc = state["proc"]
            return self.reply(200, {"running": bool(proc and proc.poll() is None), "events": state["events"][since:],
                                    "total": len(state["events"]), "usage": state["usage"], "started": state["started"]})
        if path == "/api/profile":
            p = HERE / PROFILE
            return self.reply(200, {"text": p.read_text(encoding="utf-8") if p.exists() else ""})
        if path.startswith("/files/"):
            f = (DRAFTS / path[len("/files/"):]).resolve()
            if DRAFTS.resolve() in f.parents and f.is_file():  # never serve anything outside applications/
                return self.reply(200, f.read_bytes(), mimetypes.guess_type(f.name)[0] or "application/octet-stream")
        self.reply(404, {"error": "Not found"})

    def do_POST(self):
        # JSON-only: a web page can't send this to localhost without a CORS preflight, which we never answer.
        if self.headers.get("Content-Type") != "application/json":
            return self.reply(415, {"error": "Send JSON"})
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        state["ping"] = time.time()
        if self.path == "/api/ping":
            return self.reply(200, {"ok": True})
        if self.path == "/api/run":
            err = start_claude(max(1, min(int(body.get("limit") or 10), 30)))
            return self.reply(409 if err else 200, {"error": err} if err else {"ok": True})
        if self.path == "/api/stop":
            stop_claude()
            return self.reply(200, {"ok": True})
        if self.path == "/api/open-folder":
            return self.reply(200 if open_folder(body.get("slug", "")) else 404, {"ok": True})
        log = io.StringIO()
        with lock, contextlib.redirect_stdout(log):
            if self.path == "/api/fetch":
                data.fetch()
            elif self.path == "/api/update" and body.get("url") and body.get("status") in data.STATUSES:
                data.update([{"url": body["url"], "status": body["status"]}])
            elif self.path == "/api/profile" and isinstance(body.get("text"), str):
                p = HERE / PROFILE
                if p.exists():
                    p.with_suffix(".md.bak").write_text(p.read_text(encoding="utf-8"), encoding="utf-8")
                p.write_text(body["text"], encoding="utf-8")
            else:
                return self.reply(400, {"error": "Unknown action"})
        self.reply(200, {"log": log.getvalue()})

    def log_message(self, *args):
        pass


def open_window(url):
    """Open as an app window (no tabs or address bar) with Edge or Chrome; fall back to the default browser."""
    for exe in [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]:
        if Path(exe).exists():
            profile = Path.home() / ".desk-window" / TITLE.replace(" ", "")
            subprocess.Popen([exe, f"--app={url}", f"--user-data-dir={profile}", "--window-size=1320,880",
                              "--no-first-run", "--no-default-browser-check"])
            return
    webbrowser.open(url)


def watchdog():
    while True:
        time.sleep(20)
        busy = state["proc"] and state["proc"].poll() is None
        if not busy and time.time() - state["ping"] > IDLE_EXIT:
            os._exit(0)


if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    try:
        server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    except OSError:  # already running: just bring up a window
        open_window(url)
        sys.exit(0)
    if sys.stdout is None or "pythonw" in Path(sys.executable).name.lower():  # no console: keep errors in desk.log
        sys.stdout = sys.stderr = open(LOG, "a", encoding="utf-8", buffering=1)
    print(f"{TITLE} running at {url}. Close the app window to stop it.")
    threading.Thread(target=watchdog, daemon=True).start()
    if "--no-window" not in sys.argv:  # --no-window: serve only (e.g. open the URL yourself from another device's browser)
        threading.Timer(0.3, open_window, [url]).start()
    server.serve_forever()
