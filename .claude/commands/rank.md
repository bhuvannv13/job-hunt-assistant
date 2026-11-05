---
description: Score a batch of jobs against your profile into a shortlist with strengths and gaps
argument-hint: "[urls | 'top N' from the last match]"
---

Load the `job-application` skill and read `evaluation.md`.

1. Collect the postings: URLs or pasted text in `$ARGUMENTS`, or the top N jobs from the last `python -m jobhunt match` run (default 10).
2. For each URL, use the `posting-fetcher` agent (one per posting; run them in parallel) so raw pages never enter this conversation. Each saves a cleaned `posting.md` under `private/applications/_inbox/<slug>/` and returns the guard verdict.
3. Score them with the `posting-scorer` agent (or directly, for 3 or fewer), following the gates and weights exactly.
4. Show one table ordered by overall score: role, employer, guard, gates, overall, band, the single biggest gap. Then the strengths/gaps blocks for the top 5.
5. Ask which ones to track. For each confirmed one run `python -m jobhunt app add --company ... --role ... --url ... --score N --source ... --status considering` and move its `_inbox` folder contents into the new `private/applications/<id>/`.
