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

Outputs:

```
output/
  job_tracker.xlsx        Jobs + Dashboard (charts)
  shortlist.md            top 40 as a table
  cvs/                    one tailored CV per top job (.docx)
  cover_letters/          one cover letter per top job (.docx)
```

## Settings

[`config/preferences.yaml`](config/preferences.yaml) sets locations, the regions a remote job must mention, role types, the maximum years of experience, internships, languages you speak and the minimum score. To add employers, put their board in [`config/companies.yaml`](config/companies.yaml). The comments explain how to find the board name from any job link.

## Project layout

```
jobhunt/
  sources/          one parser per job board + optional aggregators
  skills.py         skill vocabulary (regular expressions)
  cv.py             read PDF / Word / text CVs and split sections
  match.py          filters and the score
  verify.py         employer and scam checks
  tailor.py         tailored CV and cover letter (Word)
  tracker.py        Excel workbook with dashboard
  pipeline.py, cli.py
docs/               the website (GitHub Pages) and the daily data
tests/              pytest suite with recorded API samples
```

## Data and licences

Job adverts belong to the employers who published them; the site shows them with a link back to the original. The job-board APIs used are the public endpoints each provider offers for listing a customer's open roles. Code is MIT licensed.

## Author

Bhuvann Vinodh Ram · [Portfolio](https://bhuvannv13.github.io/) · [GitHub](https://github.com/bhuvannv13)
