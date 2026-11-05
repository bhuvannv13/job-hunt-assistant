---
description: Build or update private/profile.yaml from your CV, documents or a short interview
argument-hint: "[path to CV or folder]"
---

Build the candidate profile that every other command relies on.

1. Make sure `private/` exists and is git-ignored (`git check-ignore private/` must print `private/`). If not, stop and tell the person.
2. Read the sources: `$ARGUMENTS` if given, otherwise everything in `private/documents/` (CVs, transcripts, past cover letters). If there is nothing, interview the person instead, one topic at a time.
3. Write `private/profile.yaml` following `examples/profile.example.yaml`: `person`, `titles`, `education`, `skills`, `experience`, `projects`, `awards`, and the optional search sections (`work_authorisation`, `languages`, `deal_breakers`, `target_sectors`, `salary`, `max_years`, `star_stories`, `writing_style`).
   - Copy facts exactly. Do not round up numbers, merge roles or add skills that are not in a source.
   - Anything the sources do not answer (work permission end date, notice period, salary floor, deal-breakers) goes into a list of questions; ask them and record only the answers given.
4. If `private/profile.yaml` already exists, show a diff of what would change and ask before overwriting.
5. Check it loads: `python -m jobhunt match --profile private/profile.yaml --out private/out` (skip if there is no jobs data yet).
6. Finish with: what was filled, what is still missing, and the suggestion to run `/scrape` then `/rank`.
