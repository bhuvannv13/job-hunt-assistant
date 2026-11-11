# Job Hunt Assistant

[![Tests](https://github.com/bhuvannv13/job-hunt-assistant/actions/workflows/tests.yml/badge.svg)](https://github.com/bhuvannv13/job-hunt-assistant/actions/workflows/tests.yml)
[![Refresh jobs](https://github.com/bhuvannv13/job-hunt-assistant/actions/workflows/refresh.yml/badge.svg)](https://github.com/bhuvannv13/job-hunt-assistant/actions/workflows/refresh.yml)

**Live app: https://bhuvannv13.github.io/job-hunt-assistant/**

Upload your CV and see graduate and junior jobs in Ireland (and remote jobs open to Ireland or Europe) ranked by how well they fit you. Each employer is checked for genuineness, every advert comes with tailoring tips and a tailored Word CV, and your applications go into an Excel tracker with a dashboard of charts.

It is free to run: a daily GitHub Actions job collects the jobs, GitHub Pages hosts the site, and everything personal (your CV and tracker) stays in your browser.

## What it does

| Step | How |
|---|---|
| Find jobs | Reads the public job boards that employers publish through Greenhouse, Lever, Ashby, Workable and SmartRecruiters (list in [`config/companies.yaml`](config/companies.yaml)). Optional Adzuna and Jooble API keys add aggregator results. |
| Filter | Keeps Ireland and remote-Europe jobs; drops senior roles, adverts asking for more years than you set, and adverts that require a language you do not speak. |
| Rank | Scores each job 0–100 against your CV (see below) and explains the score. |
| Check the employer | Labels each job *Verified employer*, *Official job board*, *Unverified* or *Caution* (scam warning signs). |
| Tailor | Shows which of the advert's skills your CV already has and which it lacks, and builds a tailored CV and cover letter that only use what you have written. |
| Track | Excel workbook with a Jobs sheet (role, company, dates, description, score, trust, link, status, result, notes) and a Dashboard sheet with charts that update as you edit. |

## Why there is no automatic applying

LinkedIn, Indeed and most job sites forbid bots in their terms of use, and an automated application can send the wrong thing in your name. This tool never logs in, never scrapes and never submits. Each **Apply** button opens the employer's own application page so that you stay in control.

What it does instead is get everything ready: notifications (below) arrive with the match score, the skills you have and lack, and, by email, a tailored CV and cover letter for the best matches. Applying is then a few clicks on the employer's own page.

## Get notified about new jobs

`python -m jobhunt notify` tells you about new jobs that fit your profile, at most once per job.

| Source | How |
|---|---|
| Official job boards | the jobs collected every day by `fetch` |
| Your job-alert emails | Glassdoor, Indeed, LinkedIn, gradireland, Jobs.ie and IrishJobs email you the jobs that match the alerts on your own account. With `--emails` the tool reads those emails over IMAP, **read-only** (nothing is marked read, moved or deleted). The same advert from several sites is notified once. |

Every job is scored with the same rules as `match`, filtered by [`config/notify.yaml`](config/notify.yaml) (minimum score, employer check, how many per run) and sent through:

* **Push to your phone** with the free [ntfy](https://ntfy.sh) app: subscribe to a long, hard-to-guess topic name and set `NTFY_TOPIC`. Each notification opens the advert.
* **Email digest** over SMTP (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `NOTIFY_TO`), with a tailored CV and cover letter attached for the top matches when you use `--profile`.

```bash
python -m jobhunt notify --profile my_profile.yaml --dry-run          # print what would be sent
IMAP_USER=you@gmail.com IMAP_PASSWORD=app-password NTFY_TOPIC=my-long-topic \
  python -m jobhunt notify --profile my_profile.yaml --emails
```

For Gmail, IMAP needs an [app password](https://myaccount.google.com/apppasswords) (2-step verification on); never use your normal password.

**Running it automatically.** The workflow [`.github/workflows/notify.yml`](.github/workflows/notify.yml) runs after the daily refresh and twice more a day. Add these repository secrets (Settings > Secrets and variables > Actions): `PROFILE_YAML` (or `CV_TEXT`), `NTFY_TOPIC` and, if you want them, the SMTP and IMAP settings. Secrets never appear in the public repository; the log prints only counts, and the list of jobs already notified is kept in the Actions cache, not committed.

## Is the employer genuine?

| Label | Meaning |
|---|---|
| Verified employer | The advert lives on the company's own domain, or the company's careers page links to the job board it came from (checked daily by `check-companies`). |
| Official job board | The advert is on the company's applicant-tracking board, but the link from its website could not be confirmed automatically. Many careers pages load jobs with JavaScript. |
| Unverified | Found through an aggregator. Confirm on the employer's website before applying. |
| Caution | The text shows scam signs: fees, chat-app-only contact, requests for bank, PPS or passport details, unrealistic daily pay, personal email addresses, or known scam job types. Hidden by default. |

This is a screening aid, not a guarantee. Never pay to apply and never share bank or ID details before a signed offer.

## Match score

`score = 100 × (0.45 × text similarity + 0.30 × skill coverage + 0.15 × wanted role type + 0.10 × level fit)`

* **Text similarity**: TF-IDF cosine similarity between your CV and the advert (word and two-word phrases), scaled against the best match and an absolute reference.
* **Skill coverage**: share of the tools and skills found in the advert (about 60 recognised, see [`jobhunt/skills.py`](jobhunt/skills.py)) that also appear in your CV.
* **Level fit**: 1 for graduate or entry roles, 0.6 when the level is not stated, 0.5 for internships.

The website and the command-line tool use the same rules. The browser version runs the same Python modules with Pyodide to build the Excel and Word files.

## Use it from the command line

```bash
pip install -r requirements.txt
python -m jobhunt check-companies          # test every board and the employer's website link
python -m jobhunt fetch                    # collect jobs into docs/data/jobs.json
python -m jobhunt match --cv my_cv.pdf     # rank, tailor the top 10 and build output/job_tracker.xlsx
```

For the best tailored CVs, describe yourself once in a profile (copy [`examples/profile.example.yaml`](examples/profile.example.yaml)) and run:

```bash
python -m jobhunt match --profile my_profile.yaml --tailor 15
```

The tool picks the summary written for that type of role, puts your most relevant projects and experience points first, lists the advert's skills that you really have, and writes a short cover letter. It never adds a claim that is not in your profile, and the tests check this.

Running `match` again keeps everything you typed in the tracker (Status, Date applied, Result, Notes) and marks jobs that have been taken down as *Closed*.

Before you apply, more checks:

```bash
python -m jobhunt live https://jobs.lever.co/acme/1234     # still open? asks the board's API, else reads the page
python -m jobhunt workauth --in posting.md --permit "Stamp 1G"
python -m jobhunt patterns                                # where your applications turn into interviews
```

* **`live`** answers *open*, *closed* or *uncertain* with the evidence. Greenhouse, Lever and Ashby links are checked against the board's own API; other pages are read for closure wording ("no longer accepting applications", "has been filled") before looking for an apply button, because closed pages often keep one. `--tracker` checks every open application at once.
* **`workauth`** quotes every right-to-work sentence in an advert and says whether it rules out your permission: "Stamp 4 only", "excludes Stamp 1G", "right to work for an unlimited period", "EU citizens only" and "no sponsorship" (which only matters if you need sponsorship). Set `permit` in [`config/preferences.yaml`](config/preferences.yaml) and `match` drops those adverts before scoring.
* **`factcheck`** lists every number and name in a finished CV or letter that does not appear in your own sources (profile, documents, the posting). A made-up "cut costs by 30%" or an employer you never worked for is caught even when the wording is fluent.
* **`ats-check --max-pages 2`** reads the CV the way an applicant tracking system does: contact details, garbled glyphs, digits or dots lost by a web font, keywords, and the page limit.
* **`app add`** refuses to track the same job twice (same link, or the same company with a near-identical title), so you do not apply twice by accident. Use `--force` if it really is a different job.
* **`patterns`** reads your tracker and shows interview rates by channel, sector and fit score, the median time to a rejection, and applications silent for 30+ days. It only comments on groups of three or more.

Outputs:

```
output/
  job_tracker.xlsx        Jobs + Dashboard (charts)
  shortlist.md            top 40 as a table
  cvs/                    one tailored CV per top job (.docx)
  cover_letters/          one cover letter per top job (.docx)
```

## Use it with Claude Code

Open the folder in [Claude Code](https://claude.com/claude-code) and the workspace in `CLAUDE.md` turns it into a job search assistant with slash commands. Claude does the reading and writing; the Python tools above do the counting, checking and file building, so results are repeatable.

| Command | What happens |
|---|---|
| `/setup` | Builds `private/profile.yaml` from your CV and documents (or by asking you) |
| `/scrape` | Fetches the boards, optionally your job-alert emails, and shows the best matches |
| `/rank` | Fit check of a batch of postings: right-to-work, language, experience and deal-breaker gates, then five weighted scores |
| `/apply <link>` | Evaluation, company research, tailored CV and cover letter, an independent reviewer pass, Word/PDF files and an ATS check |
| `/interview <job>` | Prep pack for the interview stage and an optional mock interview |
| `/outcome <job> <news>` | Updates the tracker and drafts follow-ups, thank-you notes and feedback requests |
| `/gmail-sync` | Reads recent application emails and proposes tracker updates for you to approve |
| `/report` | Offline HTML dashboard of your pipeline |
| `/upskill` | Skill-gap heatmap across your best-fit jobs and a learning plan |

Safeguards built in:

- **You submit.** Claude drafts; it never applies, sends emails, logs in or ticks consent boxes.
- **Nothing invented.** Every claim must trace to your profile; a reviewer agent checks each draft before it is rendered.
- **Postings are untrusted.** `python -m jobhunt guard` strips invisible characters and hidden HTML and flags text aimed at AI tools before Claude reads a posting.
- **Private stays private.** Your profile, tracker and application files live in `private/`, which is git-ignored.

The command layer is inspired by [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search) and several checks by [career-ops](https://github.com/career-ops-hq/career-ops); see [Credits](#credits).

## Settings

[`config/preferences.yaml`](config/preferences.yaml) sets locations, the regions a remote job must mention, role types, the maximum years of experience, internships, languages you speak and the minimum score. To add employers, put their board in [`config/companies.yaml`](config/companies.yaml). The comments explain how to find the board name from any job link.

## Project layout

```
jobhunt/
  sources/          one parser per job board, optional aggregators and job-alert emails
  skills.py         skill vocabulary (regular expressions)
  cv.py             read PDF / Word / text CVs and split sections
  match.py          filters and the score
  verify.py         employer and scam checks
  tailor.py         tailored CV and cover letter (Word)
  tracker.py        Excel workbook with dashboard
  notify.py         push and email notifications about new matches
  guard.py          posting integrity check (hidden text, instructions aimed at AI)
  applications.py   application tracker (CSV + one folder per application)
  report.py         offline HTML dashboard of applications
  upskill.py        skill-gap analysis across top jobs
  ats.py            CV text-layer and keyword check
  liveness.py       is a posting still open?
  workauth.py       right-to-work restrictions (Irish stamps, sponsorship)
  patterns.py       funnel, rejection patterns, ghosted applications, reposts
  factcheck.py      numbers and names in a CV or letter that are not in your sources
  pipeline.py, cli.py
CLAUDE.md           workspace rules for Claude Code
.claude/            slash commands, agents, the job-application skill and permissions
private/            your data (git-ignored, created by /setup)
docs/               the website (GitHub Pages) and the daily data
tests/              pytest suite with recorded API samples
```

## Data and licences

Job adverts belong to the employers who published them; the site shows them with a link back to the original. The job-board APIs used are the public endpoints each provider offers for listing a customer's open roles. Code is MIT licensed.

## How it compares: analysis of the two reference projects

This project learned from two open-source job-search assistants. Both are good; they solve the problem
from different directions. This review (November 2026) looks at what each does well, where each falls
short, and what was changed here as a result.

| | [ai-job-search](https://github.com/ai-job-search-dev/ai-job-search) | [career-ops](https://github.com/career-ops-hq/career-ops) | This project |
|---|---|---|---|
| Built by | Mads Lorentzen; got hired with it | Santiago Fernández de Valderrama; got hired with it, then grew a community | Bhuvann Vinodh Ram, for the Irish market |
| Language and size | Python tools (~20k lines) + Bun CLIs per portal, LaTeX templates | Node.js (~500k lines of .mjs incl. tests, 1,000+ test files) | Python (~3.7k lines), 60+ tests |
| Where it runs | Claude Code (other agent CLIs via AGENTS.md) | Many AI CLIs (Claude, Codex, Gemini, OpenCode...) plus a dashboard | Website (runs in your browser), command line, Claude Code |
| Job sources | Danish portals + LinkedIn, more via `/add-portal` | 100+ preconfigured company boards, many ATS providers | Official Greenhouse, Lever, Ashby, SmartRecruiters, Workable boards of employers in Ireland, plus your alert emails |
| Needs a paid AI subscription | Yes | Yes (free local models possible) | No for search, ranking, tailoring and tracking; only for the Claude Code commands |

### ai-job-search

**Pros**

* Small and readable: a handful of commands carry you from an empty profile to a tracked result.
* Drafter and reviewer are separate agents, so the second one catches what the first missed.
* A real PDF loop: it compiles the CV, reads the pages and fixes overflow and orphaned headings until the CV is exactly two pages.
* Checks the PDF's text layer the way an ATS reads it, and treats postings as untrusted input.
* Honest about limits: it never claims skills you do not have and says what it cannot verify.

**Cons**

* Portal search is built for Denmark; other markets need `/add-portal`.
* Heavy setup: Python, Bun and a full LaTeX distribution.
* Your profile and salary expectations live in tracked files by default, and a GitHub fork is always public, so it is easy to publish personal data by mistake.
* Fit scoring is done by the model, so the same posting can score differently on two runs; there is no deterministic score.
* No daily feed or notifications: you search when you remember to.

### career-ops

**Pros**

* Very broad: posting liveness, evaluation reports, CV and cover letter generation, contact discovery, interview prep, negotiation, follow-up cadence, rejection-pattern analysis, ghost-job (repost) detection.
* Strong principles, enforced in code: it never submits or sends, it warns below a 4.0/5 fit, and a fact check blocks a CV with numbers that are not in your sources.
* Local-first, no telemetry, and works with many AI tools, including free local models.
* Large, active community and a huge test suite.

**Cons**

* Size and complexity: hundreds of scripts and config files make it hard to understand, audit or change.
* Node.js 22+ toolchain and an AI CLI are needed even for simple tasks.
* Immigration checks are built around sponsorship (for example the UK Skilled Worker register) and do not know Irish stamps (Stamp 1G, Stamp 4).
* Much of the value depends on long AI evaluations, which cost tokens and time for every posting.

### What this project does differently

* **Deterministic first, AI second.** Search, filters, the 0-100 score, tailoring, the Excel tracker and notifications are plain Python with tests, so they are repeatable and free. Claude Code is optional, for the writing and judgement steps.
* **Built for Ireland.** Official employer boards in Ireland, Irish job-alert emails, Stamp 1G/Stamp 4 right-to-work screening, Irish employer checks.
* **Private by design.** Everything personal lives in a git-ignored `private/` folder; the public site never sees your CV (it is processed in your browser).
* **Employer and scam labels on every job**, decided by fixed rules (verified employer, official board, unverified, caution). career-ops runs a deeper, AI-led legitimacy review per posting; ai-job-search flags suspicious distribution patterns.

### Cons of this project, and what was done about them

| Weakness found in the review | Status |
|---|---|
| Could not tell whether a posting was still open | **Fixed**: `live` checks the board's API or the page (from career-ops) |
| Right-to-work wording was only read by the AI, so "Stamp 4 only" adverts reached the shortlist | **Fixed**: `workauth` and the `permit` preference drop them before scoring |
| No view of what is working across applications | **Fixed**: `patterns` (interview rate by channel, sector, score; time to rejection; ghosted applications) |
| Fabrication was guarded only by an AI reviewer | **Fixed**: `factcheck` lists unsupported numbers and names deterministically (from career-ops) |
| The same job could be tracked and applied to twice | **Fixed**: `app add` detects duplicates by link or company + similar title |
| CV length and lost characters were not checked | **Fixed**: `ats-check --max-pages`, and it now flags web fonts that drop digits or dots from the text layer (this caught a real problem in the author's own CV) |
| Only employers using the supported ATS boards are searched; LinkedIn and Indeed adverts arrive only through your alert emails | Open: by design, no scraping of sites whose terms forbid it |
| The score is keyword-based (TF-IDF), so it can miss a good match described in different words | Open: the Claude `/rank` command adds a judgement-based score |
| Liveness cannot see pages behind a login, and `workauth` only knows common phrasings | Open: both answer "uncertain"/"none found" rather than guess; read the advert |
| Repost detection needs a history of adverts, which the daily refresh does not keep yet | Open |

## Credits

This project was built with ideas from these open-source projects, both MIT licensed. The code here is
written in Python and adapted to the Irish job market; a few closure phrases in `liveness.py` follow the
wording of career-ops' checker (MIT, © 2026 Santiago Fernández de Valderrama). Thank you to their authors.

| Project | What it inspired here |
|---|---|
| [**career-ops**](https://github.com/career-ops-hq/career-ops) by Santiago Fernández de Valderrama ([@santifer](https://github.com/santifer)) and contributors | Checking that a posting is still live before applying (`liveness.py`), the sponsorship check that became the Irish-stamp right-to-work screen (`workauth.py`), rejection-pattern, funnel and rejection-latency analysis plus repost detection (`patterns.py`), the CV fact verifier (`factcheck.py`), the duplicate-application precheck, and its principles: a human presses Submit, nothing is fabricated, apply better to fewer. |
| [**ai-job-search**](https://github.com/ai-job-search-dev/ai-job-search) | The Claude Code workspace: slash commands (`/setup`, `/scrape`, `/rank`, `/apply`, `/interview`, `/outcome`, `/gmail-sync`, `/report`, `/upskill`), the posting-fetcher, scorer and reviewer agents, the job-application skill (gates, scoring, writing rules), the posting guard, the CSV tracker with an archive per application, and the PDF text-layer (ATS) and page-count checks. |

Built on [scikit-learn](https://scikit-learn.org/) (TF-IDF matching), [openpyxl](https://openpyxl.readthedocs.io/), [python-docx](https://python-docx.readthedocs.io/), [pdfplumber](https://github.com/jsvine/pdfplumber), [Pyodide](https://pyodide.org/) (the website runs the Python in your browser) and [ntfy](https://ntfy.sh) (phone notifications). Job data comes from the public job-board APIs of Greenhouse, Lever, Ashby, SmartRecruiters and Workable.

## Author

Bhuvann Vinodh Ram · [Portfolio](https://bhuvannv13.github.io/) · [GitHub](https://github.com/bhuvannv13)
