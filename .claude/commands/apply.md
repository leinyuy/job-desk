---
description: Fetch new remote jobs, rank them against profile.md, and draft tailored applications and CVs for the best ones
argument-hint: "[max applications to draft, default 10]"
---

You are my job-application assistant. Max drafts this run: $ARGUMENTS (default 10 if empty).

## 1. Fetch
Run `python jobs.py` to pull fresh jobs into jobs.csv.

## 2. Rank
Read `profile.md`. It is the only source of facts about me: never invent experience, numbers, employers, degrees or skills. Then run `python jobs.py list new` and read those rows in jobs.csv.

Give each job a fit score from 1 to 10. Mark it `skip` if any of these is true:
- It requires living in, or work authorization for, a country other than Cameroon. The exception is a posting that also says worldwide, anywhere, Africa or EMEA, or hires contractors globally. A list of countries without Cameroon or Africa counts as restricted.
- Pay is clearly below USD 1,500/month full-time equivalent.
- It mainly needs a stack I don't have (Java, .NET, Go, Rust, PHP, native iOS/Android, data or ML research), or it requires 8+ years.
- It looks like a scam, is unpaid or commission-only, or charges to apply.

Score higher for:
- AI automation, n8n or LLM work
- forward-deployed or solutions roles
- Next.js, React or React Native
- early-stage startups, event or ticketing products
- contract or part-time roles
- French or bilingual roles

Write every decision to `triage.json` as a list, then run `python jobs.py triage triage.json`. Use one line of notes saying why it fits or why it was skipped:
`[{"url": "...", "status": "ready", "score": 8, "notes": "n8n + Next.js, contractors worldwide"}, {"url": "...", "status": "skip", "score": 2, "notes": "US residents only"}]`

## 3. Draft
Run `python jobs.py list ready`. For the best jobs that score 7 or higher, up to the max:

a. If the CSV description is cut off or unclear, fetch the posting URL and read all of it.

b. Create the folder `applications/<folder>/`, using the folder name printed by `jobs.py list`.

c. Write `applications/<folder>/cv.json` using the same schema as `cv/base.json`. Start from cv/base.json and tailor it to this posting:
   - Rewrite the headline and the 3-4 line summary for this role. Use the posting's own words for skills I really have.
   - Reorder the skills so the ones the posting asks for come first. Drop skills that don't matter for this role.
   - For each job in my history, keep its 3-4 most relevant bullets and put the strongest first. You may rephrase a bullet. Never add facts.
   - Showwupp stays under **Projects** as a product I designed and built. Recruiters at established companies see founders as likely to leave (Yale field study). The exception is startups, 0→1 or founding-engineer roles, and event or ticketing companies: there, move it into Experience as "Founder & Lead Product Engineer", because being a founder helps.
   - Keep it to one page. Go to two pages only for senior roles with a lot of relevant history. Never pad.
   - Make it sound like me, not AI. Don't use "spearheaded", "leveraged", "streamlined", "honed", "passionate", "results-driven", "cutting-edge", em dashes, or bullets that all have the same shape. Use concrete numbers, product names and stack details instead. Never copy the posting word for word.
   - For a French posting, write the whole CV in French and set `"lang": "fr"`. Keep it to one page. Use these section titles: Profil, Compétences, Expériences professionnelles, Projets, Formation, Langues. Give languages with CEFR levels (e.g. "Anglais : courant (C1)") only if profile.md states them; otherwise write "courant".
   - Never add a photo, date of birth, age, marital status or nationality.

d. Run `python cv.py applications/<folder>/cv.json`. It writes cv.html and cv.pdf next to the JSON.

e. Write `applications/<folder>/application.md` in exactly this structure. The dashboard adds a Copy button to every `##` and `###` heading.

```
# <Company>: <Role>

**Score:** <n>/10 · **Pay:** <pay or "not listed"> · **Apply:** <url>

## Why it fits
- <requirement from the posting> → <matching fact from profile.md>
- <requirement> → <fact>

## Cover letter
<under 180 words, in the posting's language, following the tone rules in profile.md. Plain sentences, no buzzwords, no "I am excited to apply". Name one specific thing about the company.>

## Form answers
### Why do you want to work here?
<2-3 sentences specific to this company>
### Years of experience
<honest number for the main stack, from profile.md>
### Salary expectation
<a fair figure in the posted range, never below the floor; monthly or annual to match the posting>
### Notice period
2 weeks
### Work authorization and location
Based in Buea, Cameroon (UTC+1). I work as an independent contractor and can be paid through Deel, Remote.com or a similar platform.
### Links
LinkedIn: https://www.linkedin.com/in/drepart · Product I built: https://showwupp.com
```

f. Run `python cv.py lint applications/<folder>/application.md`. If it lists any words, reword them and rebuild. (cv.py checks cv.json automatically when it builds.)

g. Run `python jobs.py mark drafted - <urls>` for the jobs you drafted.

## 4. Report
Finish with one table with these columns: score | company | role | pay | folder, best first. Then add one line with how many jobs you skipped and the most common reason, and remind me that `python app.py` opens the dashboard.

Never submit anything yourself. I review each draft, submit it on the company's site, and mark it applied in the dashboard.
