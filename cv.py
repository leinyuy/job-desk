"""Render a CV from JSON to HTML + PDF (ATS-safe: one column, real text, standard headings).

  python cv.py cv/base.json                     -> cv/base.html + cv/base.pdf
  python cv.py applications/<slug>/cv.json      -> tailored CV for one job
  python cv.py lint <file> [...]                -> list AI-sounding words to reword (also runs on every build)

JSON shape (every field except name/sections is optional):
{
  "lang": "en",
  "name": "...", "headline": "...", "contact": ["City, Country (UTC+1)", "email", "linkedin.com/in/...", "site.com"],
  "sections": [
    {"title": "Summary", "items": [{"text": "..."}]},
    {"title": "Skills", "items": [{"title": "AI & automation", "text": "n8n, Claude API"}]},
    {"title": "Experience", "items": [{"title": "Role", "org": "Company", "where": "Remote", "dates": "2024 - Present",
                                       "bullets": ["..."]}]}
  ]
}
"""
import html, json, re, shutil, subprocess, sys, tempfile
from pathlib import Path

# Words hiring managers flag as AI-written (Simplify 2025 resume data). Warn only: the writer decides.
AI_TELLS = re.compile(r"spearhead\w*|leverag\w*|\bhoned\b|streamlin\w*|results-driven|passionate|synerg\w*|cutting-edge"
                      r"|excited to apply|thrilled|delve\w*|—", re.I)

CSS = """
@page { size: A4; margin: 14mm 16mm; }
* { box-sizing: border-box; }
body { margin: 0; color: #1a1d29; font: 10pt/1.38 "Segoe UI", Calibri, "Helvetica Neue", Arial, sans-serif; }
h1 { font-size: 21pt; font-weight: 600; letter-spacing: -0.01em; margin: 0; }
.headline { color: #2b4c7e; font-size: 11pt; font-weight: 600; margin: 2pt 0 4pt; }
.contact { color: #4a5068; font-size: 9pt; }
.contact span + span::before { content: "  |  "; color: #b4b9c9; }
h2 { color: #2b4c7e; font-size: 9.5pt; font-weight: 700; letter-spacing: 0.02em; text-transform: uppercase;  /* wide tracking splits words for ATS parsers */
     border-bottom: 0.6pt solid #c9cedb; padding-bottom: 2pt; margin: 12pt 0 5pt; }
.item { margin: 0 0 6pt; break-inside: avoid; }
.row { display: flex; justify-content: space-between; gap: 12pt; }
.row b { font-weight: 600; }
.dates, .where { color: #4a5068; white-space: nowrap; font-variant-numeric: tabular-nums; }
.where { font-size: 9pt; }
p { margin: 1pt 0 0; }
ul { margin: 2pt 0 0; padding-left: 12pt; }
li { margin: 0 0 1.5pt; }
.inline b { font-weight: 600; }
"""


def e(s):
    return html.escape(str(s or ""))


def render(cv):
    out = [f'<!doctype html><html lang="{e(cv.get("lang", "en"))}"><head><meta charset="utf-8">',
           f"<title>{e(cv['name'])} - CV</title><style>{CSS}</style></head><body>",
           f"<h1>{e(cv['name'])}</h1>"]
    if cv.get("headline"):
        out.append(f'<div class="headline">{e(cv["headline"])}</div>')
    if cv.get("contact"):
        out.append('<div class="contact">' + "".join(f"<span>{e(c)}</span>" for c in cv["contact"]) + "</div>")
    for sec in cv["sections"]:
        out.append(f"<h2>{e(sec['title'])}</h2>")
        for it in sec.get("items", []):
            out.append('<div class="item">')
            if it.get("title") and it.get("text") and not (it.get("org") or it.get("dates") or it.get("bullets")):
                out.append(f'<p class="inline"><b>{e(it["title"])}:</b> {e(it["text"])}</p>')  # skills line
            else:
                if it.get("title") or it.get("dates"):
                    org = f" - {e(it['org'])}" if it.get("org") else ""
                    out.append(f'<div class="row"><span><b>{e(it.get("title"))}</b>{org}</span>'
                               f'<span class="dates">{e(it.get("dates"))}</span></div>')
                if it.get("where"):
                    out.append(f'<div class="where">{e(it["where"])}</div>')
                if it.get("text"):
                    out.append(f"<p>{e(it['text'])}</p>")
                if it.get("bullets"):
                    out.append("<ul>" + "".join(f"<li>{e(b)}</li>" for b in it["bullets"]) + "</ul>")
            out.append("</div>")
    out.append("</body></html>")
    return "\n".join(out)


def browser():
    candidates = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                  "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"]
    found = [c for c in candidates if Path(c).exists()]
    return found[0] if found else next(filter(None, map(shutil.which, ["msedge", "google-chrome", "chromium", "chrome"])), None)


def lint(path):
    hits = sorted({m.group(0).lower() for m in AI_TELLS.finditer(Path(path).read_text(encoding="utf-8"))})
    if hits:
        print(f"{Path(path).name}: reword these AI-sounding words: {', '.join(hits)}")
    return hits


def build(json_path):
    src = Path(json_path).resolve()
    lint(src)
    page = src.with_suffix(".html")
    page.write_text(render(json.loads(src.read_text(encoding="utf-8"))), encoding="utf-8")
    exe = browser()
    if not exe:
        print(f"{page.name} written. No Edge/Chrome found: open it and use Print > Save as PDF.")
        return page
    pdf = src.with_suffix(".pdf")
    with tempfile.TemporaryDirectory() as profile:  # separate profile so an open browser window doesn't block it
        subprocess.run([exe, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--user-data-dir={profile}",
                        f"--print-to-pdf={pdf}", page.as_uri()], check=True, capture_output=True, timeout=120)
    print(f"{pdf} written")
    return pdf


if __name__ == "__main__":
    if sys.argv[1:2] == ["lint"]:
        for p in sys.argv[2:]:
            lint(p)
    else:
        for p in sys.argv[1:] or ["cv/base.json"]:
            build(p)
