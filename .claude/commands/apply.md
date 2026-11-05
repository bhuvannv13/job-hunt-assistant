---
description: Fit check, then a tailored CV and cover letter, a reviewer pass and an ATS check. You submit.
argument-hint: "<posting url | pasted posting | application id>"
---

Load the `job-application` skill. You draft; the person submits. Never open the application form, log in, or tick a declaration.

1. **Posting.** If `$ARGUMENTS` is an existing application id, use its `posting.md`. Otherwise use the `posting-fetcher` agent and show its guard verdict. If the guard is flagged, show the findings and ask whether to continue.
2. **Evaluate** with `evaluation.md` and show the report. Stop on a failed gate. If overall < 45, say so and ask before going on.
3. **Track.** `python -m jobhunt app add --company ... --role ... --url ... --score N --source ... --status considering` (skip if it exists). Save `posting.md` and `evaluation.md` into `private/applications/<id>/`.
4. **Research.** Reuse `private/research/<company>.md` if under 30 days old; else search the company name, read its own site, and write 5-8 dated facts with source links.
5. **Draft** following `writing.md`: `private/applications/<id>/tailored.yaml` and `cover_letter.md`. Only facts from `private/profile.yaml` and `private/documents/`. Draft `form_answers.md` if the posting lists screening questions.
6. **Review.** Run the `application-reviewer` agent. Fix every item it reports and re-run until PASS.
7. **Render.** `python -m jobhunt render --tailored private/applications/<id>/tailored.yaml --cv-out private/applications/<id>/CV.docx --letter private/applications/<id>/cover_letter.md --letter-out private/applications/<id>/Cover_Letter.docx --pdf`
8. **ATS check.** `python -m jobhunt ats-check private/applications/<id>/CV.pdf --posting private/applications/<id>/posting.md --email <profile email> --phone <profile phone>`. Missing keywords: add only those the profile truly supports, then re-render.
9. **Hand over:** the checklist from `writing.md` with pass/fail, the file paths, the application link, and the form answers. Ask the person to tell you once they have submitted; then run `python -m jobhunt app update <id> --status applied --note "submitted by <channel>"`.
