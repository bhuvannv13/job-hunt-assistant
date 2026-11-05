---
description: Stage-specific interview prep pack, and an optional mock interview
argument-hint: "<application id or company> [screening|technical|final]"
---

Load the `job-application` skill and read `interview.md`.

1. Find the application: `python -m jobhunt app list --json` and match `$ARGUMENTS`. Ask if more than one matches.
2. Read its archive folder: `posting.md`, `evaluation.md`, the CV and letter that were sent, `outcome.md`, and `private/research/<company>.md` (refresh it if over 30 days old, from the company's own site and reputable news).
3. Write `private/applications/<id>/interview_prep_<stage>.md` with the eight sections in `interview.md`. Stories come from `star_stories` and experience in `private/profile.yaml`; mark any story without a real result as "result: ask the person".
4. If the stage is new, `python -m jobhunt app update <id> --status interview_1|interview_2|final_interview --note "<date, format>"` after the person confirms the details.
5. Offer a mock interview. If accepted, run it as `interview.md` describes: one question at a time, wait, feedback, next.
