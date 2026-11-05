---
description: Offline HTML dashboard of your application pipeline
---

1. Run `python -m jobhunt report` (writes `private/report.html`; it never leaves your machine).
2. Summarise in 4-6 lines from `python -m jobhunt app list --json`: totals by status, response rate, interview rate, applications in the last 7 and 30 days, follow-ups due (`python -m jobhunt app followups`).
3. Point out one pattern worth acting on if the data shows it (e.g. a sector or channel with no responses), stated as an observation, not a rule.
4. Tell the person where the file is so they can open it in a browser.
