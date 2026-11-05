---
description: Record what happened with an application, and draft follow-ups or thank-you notes
argument-hint: "<application id or company> <what happened> | followups"
---

Load the `job-application` skill (`writing.md`, follow-ups section).

- **`/outcome followups`**: run `python -m jobhunt app followups --days 10`. For each, draft a follow-up (60-110 words) in `private/applications/<id>/followup_<n>.md` and show it. When the person says they sent it, run `python -m jobhunt app followup-sent <id>`.
- **An event** (`$ARGUMENTS` like "Stripe rejected", "Intercom interview Thursday 2pm", "offer from X"):
  1. Find the application (`python -m jobhunt app list --json`); ask if ambiguous.
  2. Map the event to a status: assessment, interview_1, interview_2, final_interview, offer, hired, offer_declined, rejected, withdrawn, no_response. Confirm the mapping with the person if it is not explicit.
  3. `python -m jobhunt app update <id> --status <status> --note "<short fact>" [--next-step "..."]`.
  4. After an interview: offer a thank-you note draft (within 24 hours; built from the person's notes). After a rejection: offer a short reply asking for feedback, and note any feedback given in `outcome.md`. After an offer: list what to check (salary vs profile `salary`, start date, contract type, permit implications) without giving financial or legal advice.
  5. Make sure the folder has what was actually sent (CV, letter, form answers); ask for anything missing.
- Drafts only. The person sends every email.
