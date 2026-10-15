# Job Desk

Finds remote jobs that fit your profile. Claude ranks them and writes a tailored CV and cover letter for each of the best ones. You review the drafts and click submit.

It doesn't apply for you. Auto-apply bots get LinkedIn accounts banned, and tailored applications get about 2× more interviews than generic ones.

**To open it, double-click `Start Job Desk.bat`.**

## Every day (about 30 minutes)

1. **Rank & draft.** Click **Rank & draft with Claude**. Claude:
   - pulls new jobs from 8 boards
   - drops ones you can't take (country-restricted, under $1,500/month, wrong stack)
   - scores the rest and drafts the best ones, each with a one-page tailored CV (PDF)

   The panel at the bottom right shows each step. A run takes 5-15 minutes.
2. **Apply.** Open **Jobs → To apply**. Click a ticket. The big number on the stub is the fit score. Then:
   - Click **Open posting**.
   - Upload **Open tailored CV**.
   - Use the **Copy** buttons to paste the cover letter and each answer into the company's form.
   - Submit it there, then click **Mark applied**.
3. **Track.** When a company replies, set the job to **Interview**, **Offer** or **Rejected**. It's all under **Applied**.

**Find new jobs** pulls new jobs without using Claude. It's free, but it doesn't rank them; they stay "Unranked" until you click **Rank & draft with Claude**. Use the **5 drafts** option when your Claude plan is near its weekly limit; the meter at the top shows how much you've used.

## First-time setup

| Need | Check | Get it |
|---|---|---|
| Python 3.10+ | `python --version` | https://www.python.org/downloads/ (tick "Add to PATH") |
| Claude Code | `claude --version` | PowerShell: `irm https://claude.ai/install.ps1 \| iex`, then run `claude` once to log in |
| Edge or Chrome | already on Windows | opens the app window and turns CVs into PDFs |

Nothing to `pip install`. Everything uses Python's standard library.

Then:
- Copy `profile.example.md` to `profile.md` and fill it in (or do it in the app under **My profile**). Every CV and letter is written only from it.
- Write your general CV as `cv/base.json` (the format is at the top of `cv.py`), then run `python cv.py` to build `cv/base.pdf`. Use it for profile sites like Arc.dev, Turing, Andela and Braintrust.

## Files

| File | What it is |
|---|---|
| `Start Job Desk.bat` | Double-click to open the app. It stops by itself a few minutes after you close the window. |
| `profile.md` | Your facts, preferences and tone. Edit it in the app (My profile). |
| `cv/base.json` → `cv/base.pdf` | Your general one-page CV |
| `jobs.csv` | Every job found, with status, score and Claude's note. Close Excel before using the app. |
| `applications/<job>/` | One folder per drafted job: `application.md`, `cv.json`, `cv.html`, `cv.pdf` |
| `jobs.py` | Fetches and filters jobs from 8 free feeds |
| `cv.py` | Turns a CV `.json` into `.html` + `.pdf`, and flags AI-sounding words |
| `app.py`, `ui.html` | The app |
| `.claude/commands/apply.md` | What Claude does when you click Rank & draft with Claude (or type `/apply` in Claude Code) |

## Commands (optional)

```
python app.py                      open the app (same as the .bat)
python jobs.py                     fetch new jobs only
python jobs.py list ready          show ranked jobs, best first
python jobs.py mark applied - URL  set a job's status
python cv.py                       rebuild cv/base.pdf
python test_jobs.py                check the job filters still work
claude, then /apply                rank and draft inside Claude Code instead of the app
```

## Job sources
Remotive, RemoteOK, We Work Remotely, Himalayas (jobs open to Cameroon), Jobicy, Working Nomads, the Hacker News monthly "Who is hiring" thread, and the n8n community jobs board. Each feed asks you to credit it and link back, and that's why every job shows its source.

## If something goes wrong

| Problem | Fix |
|---|---|
| The window doesn't open | Go to http://localhost:8765 in any browser. Errors are in `desk.log`. |
| "Claude not set up" | Install Claude Code (see setup), run `claude` once to log in, restart the app. |
| Claude stopped with a usage limit | Wait for the weekly reset, or use 5 drafts per run. |
| `PermissionError` on jobs.csv | Close jobs.csv in Excel. |
| One source says `failed` | That site is down or changed; the others still run. |
| No CV PDF, only cv.html | Open cv.html, press Ctrl+P, choose "Save as PDF". |
| Too many irrelevant jobs | Edit `ROLE` / `NOT_ROLE` at the top of `jobs.py`, then run `python test_jobs.py`. |
