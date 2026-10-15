"""Pull remote jobs from free public feeds, keep the ones that fit, append new ones to jobs.csv.

  python jobs.py                          fetch new jobs
  python jobs.py list [status]            show jobs with that status (default ready), best first, with folder names
  python jobs.py triage triage.json       save Claude's ranking: a JSON list of {url, status, score, notes}
  python jobs.py mark <status> <score> <url> [<url> ...]   set status (new/skip/ready/drafted/applied/interview/offer/rejected); score "-" keeps it

Double-click "Start Job Desk.bat" for the app, or run /apply in Claude Code.
"""
import csv, html, json, re, sys, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

CSV_PATH = Path(__file__).with_name("jobs.csv")
FIELDS = ["found", "status", "score", "source", "title", "company", "location", "salary", "url", "notes", "description"]
STATUSES = ["new", "skip", "ready", "drafted", "applied", "interview", "offer", "rejected"]
EDITABLE = {"status", "score", "notes"}
# How the app describes Claude's commands in its activity panel (first match wins).
ACTIVITY = [("jobs.py triage", "Saving the ranking"), ("jobs.py list", "Listing ranked jobs"), ("jobs.py mark", "Updating statuses"),
            ("cv.py lint", "Checking the wording"), ("cv.py", "Building the tailored CV (PDF)"), ("jobs.py", "Searching 8 job boards for new jobs")]

# Title must look like one of the target roles (EN + FR).
ROLE = re.compile(r"automat|n8n|\bai\b|\bllm|agent|forward[- ]deployed|solutions? (engineer|architect)|implementation|integration"
                  r"|full[- ]?stack|front[- ]?end|react|next\.?js|web developer|software (engineer|developer)|product engineer"
                  r"|founding engineer|design engineer|ui ?/? ?ux|mobile|développeur|ingénieur", re.I)
NOT_ROLE = re.compile(r"sales|account exec|recruit|marketing|support|annotat|trainer|tutor|writer|\b(staff|principal|director|vp|head of)\b"
                      r"|java\b|\.net|golang|rust|c\+\+|php|ruby|android|ios|embedded|data engineer|machine learning|ml engineer"
                      r"|unpaid|volunteer|manager|\bavp\b|teaching|editor|call cent|\bqa\b|test automation|\bsap\b|salesforce", re.I)
# Location must be open to someone in Cameroon. Blank or plain "Remote" passes; Claude checks the description later.
OPEN = re.compile(r"worldwide|anywhere|global|emea|(?<!south )africa|cameroon|europe|\bcet\b|\butc|\bgmt|international|world", re.I)
# Labels lie (e.g. "Anywhere" posts that require US residence), so also scan the description.
RESTRICTED = re.compile(r"\bus[- ]only|must (reside|live|be located|be based) in (the )?(us|u\.s|united states|uk|canada)"
                        r"|authori[sz]ed to work in the (us|u\.s|united states|uk)|\bus citizen|security clearance|\bw-?2\b", re.I)

UA = {"User-Agent": "Mozilla/5.0 (personal job search script)"}


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def text(s, limit=2500):
    s = re.sub(r"<[^>]+>", " ", html.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()[:limit]


def job(source, title, company, location, salary, url, description):
    return dict(source=source, title=text(title, 200), company=text(company, 100), location=text(location, 150),
                salary=text(str(salary or ""), 80), url=url, description=text(description))


def remotive():  # ToS: max ~4 calls/day, credit Remotive
    for j in json.loads(get("https://remotive.com/api/remote-jobs?category=software-dev"))["jobs"]:
        yield job("remotive", j["title"], j["company_name"], j["candidate_required_location"], j["salary"], j["url"], j["description"])


def remoteok():  # first element is a legal notice
    for j in json.loads(get("https://remoteok.com/api"))[1:]:
        sal = f"${j['salary_min']}-{j['salary_max']}/yr" if j.get("salary_max") else ""
        yield job("remoteok", j["position"], j["company"], j.get("location"), sal, j["url"], j.get("description"))


def jobicy():
    for j in json.loads(get("https://jobicy.com/api/v2/remote-jobs?count=100&industry=engineering"))["jobs"]:
        sal = f"{j.get('salaryCurrency', '')} {j.get('annualSalaryMin', '')}-{j.get('annualSalaryMax', '')}/yr" if j.get("annualSalaryMax") else ""
        yield job("jobicy", j["jobTitle"], j["companyName"], j["jobGeo"], sal, j["url"], j["jobDescription"])


def weworkremotely():
    for cat in ["remote-full-stack-programming-jobs", "remote-front-end-programming-jobs", "remote-back-end-programming-jobs"]:
        for it in ET.fromstring(get(f"https://weworkremotely.com/categories/{cat}.rss")).iter("item"):
            company, _, title = it.findtext("title", "").partition(": ")
            yield job("wwr", title, company, it.findtext("region"), "", it.findtext("link"), it.findtext("description"))


def himalayas():  # country=CM returns worldwide jobs plus jobs that list Cameroon; 20 newest per query
    for q in ["react", "full stack", "frontend", "automation", "n8n", "ai engineer", "solutions engineer", "developpeur"]:
        url = f"https://himalayas.app/jobs/api/search?q={urllib.parse.quote(q)}&country=CM&sort=recent"
        for j in json.loads(get(url))["jobs"]:
            loc = ", ".join(j.get("locationRestrictions") or []) or "Worldwide"
            sal = f"{j.get('currency', '')} {j.get('minSalary', '')}-{j.get('maxSalary', '')}/yr" if j.get("maxSalary") else ""
            yield job("himalayas", j["title"], j["companyName"], loc, sal, j["applicationLink"], j["description"])


def workingnomads():
    for j in json.loads(get("https://www.workingnomads.com/api/exposed_jobs/")):
        yield job("workingnomads", j["title"], j["company_name"], j.get("location"), "", j["url"], j.get("description"))


def hackernews():  # latest monthly "Who is hiring?" thread; first line of a comment is "Company | Role | Location | ..."
    stories = json.loads(get("https://hn.algolia.com/api/v1/search_by_date?tags=story,author_whoishiring"))["hits"]
    sid = next(s["objectID"] for s in stories if "who is hiring" in s["title"].lower())
    url = f"https://hn.algolia.com/api/v1/search?tags=comment,story_{sid}&query=remote&hitsPerPage=500"
    for c in json.loads(get(url))["hits"]:
        first = text(re.split(r"<p>|\n", c.get("comment_text") or "")[0], 200)
        yield job("hn", first, first.split("|")[0], first, "", f"https://news.ycombinator.com/item?id={c['objectID']}", c.get("comment_text"))


def n8n_forum():  # paid n8n gigs posted on the n8n community forum
    for it in ET.fromstring(get("https://community.n8n.io/c/jobs/13.rss")).iter("item"):
        title = it.findtext("title", "")
        if not re.search(r"for hire|available for|offering|my services", title, re.I):
            yield job("n8n-forum", "n8n gig: " + title, "n8n community", "", "", it.findtext("link"), it.findtext("description"))


SOURCES = [remotive, remoteok, jobicy, weworkremotely, himalayas, workingnomads, hackernews, n8n_forum]


def load():
    if not CSV_PATH.exists():
        return []
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def save(rows):
    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:  # BOM so Excel shows accents correctly
        w = csv.DictWriter(f, FIELDS, extrasaction="ignore", restval="")
        w.writeheader()
        w.writerows(rows)


def fits(j):
    loc = j["location"]
    loc_ok = not re.sub(r"remote|[\W_]", "", loc, flags=re.I) or OPEN.search(loc)
    return ROLE.search(j["title"]) and not NOT_ROLE.search(j["title"]) and loc_ok and not RESTRICTED.search(j["description"])


def fetch():
    rows = load()
    seen = {r["url"] for r in rows} | {(r["company"].lower(), r["title"].lower()) for r in rows}
    added = 0
    for src in SOURCES:
        try:
            jobs = list(src())
        except Exception as e:  # one dead feed must not stop the others
            print(f"{src.__name__}: failed ({e})")
            continue
        kept = 0
        for j in jobs:
            key = (j["company"].lower(), j["title"].lower())
            if fits(j) and j["url"] not in seen and key not in seen:
                seen |= {j["url"], key}
                rows.append(dict(j, found=date.today().isoformat(), status="new", score=""))
                kept += 1
        print(f"{src.__name__}: {len(jobs)} jobs, {kept} new matches")
        added += kept
    save(rows)
    print(f"\n{added} new jobs added to {CSV_PATH.name} ({sum(r['status'] == 'new' for r in rows)} waiting for /apply)")


def slug(r):
    """Folder name under applications/ for this job (shared by /apply and the dashboard)."""
    return re.sub(r"[^a-z0-9]+", "-", f"{r['company']}-{r['title']}".lower()).strip("-")[:70]


def show(status):
    rows = sorted((r for r in load() if r["status"] == status), key=lambda r: -float(r["score"] or 0))
    for r in rows:
        print(f"{r['score'] or '-':>2} | {slug(r)} | {r['company']} | {r['title']} | {r['url']}")
    print(f"{len(rows)} jobs with status {status}")


def update(changes):
    """Apply a list of {url, field: value} changes. Only known fields and statuses are accepted."""
    by_url = {c["url"]: c for c in changes if c.get("url")}
    rows, hit = load(), 0
    for r in rows:
        c = by_url.get(r["url"])
        if not c:
            continue
        if c.get("status") and c["status"] not in STATUSES:
            raise ValueError(f"unknown status {c['status']!r}; use one of {STATUSES}")
        r.update({k: str(v) for k, v in c.items() if k in EDITABLE and v not in (None, "", "-")})
        hit += 1
    save(rows)
    print(f"updated {hit} of {len(by_url)}")


def mark(status, score, urls):
    update([{"url": u, "status": status, "score": score} for u in urls])


if __name__ == "__main__":
    if sys.argv[1:2] == ["mark"]:
        mark(sys.argv[2], sys.argv[3], set(sys.argv[4:]))
    elif sys.argv[1:2] == ["list"]:
        show(sys.argv[2] if len(sys.argv) > 2 else "ready")
    elif sys.argv[1:2] == ["triage"]:
        update(json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")))
    else:
        fetch()
