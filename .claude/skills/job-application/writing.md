# Writing the CV, cover letter and follow-ups

## The tailored CV (`tailored.yaml` -> `python -m jobhunt render`)

Write `private/applications/<id>/tailored.yaml` using the profile schema (`person`, `titles`,
`education`, `skills`, `experience`, `projects`, `awards`) plus:

- `summary`: 2-3 sentences written for this role, using the posting's own terms where the profile truly supports them.
- `key_skills`: up to 8 skills the posting asks for **and** the profile shows.
- `target`: `{title, company}`; `target_category`: one of the categories in `config/preferences.yaml`.

Rules:
- Start from the profile. You may **select, reorder, trim and rephrase**; you may not add facts. A rephrased bullet keeps its numbers, tools and scope exactly.
- Most relevant experience and projects first; 2-3 bullets each; keep it to two pages.
- Use the posting's exact term when it is a true synonym of what the profile says ("A/B testing" for "experimentation analysis").
- No photos, tables for layout, text boxes or icons-only contact details (ATS cannot read them).

## The cover letter (`cover_letter.md`)

One page, about 250-350 words, plain paragraphs:
1. **Why this role at this company**: one specific, verified fact about the company (from its own site, cached in `private/research/`), linked to what the person wants to do.
2. **Proof**: two short examples from the profile that match the top requirements, each with what was done and the result.
3. **Honest gap + bridge** (only if a core requirement is missing): name it briefly and show the closest real experience.
4. **Close**: availability, work authorisation in one plain sentence if relevant, thanks.

Match the person's `writing_style` in the profile (or their past letters in `private/documents/`): no
clichés ("I am writing to express my keen interest", "passionate", "synergy"), no exaggeration, British or
Irish spelling if the profile says so. Address a named person only if their name was verified.

## Verification checklist (report pass/fail before presenting)

- [ ] Every claim traces to `private/profile.yaml` or a supplied document; nothing invented
- [ ] Names, dates, titles, contact details correct; company facts verified from the company's own site
- [ ] Summary and letter opening are specific to this role, not generic
- [ ] Each must-have requirement is addressed or honestly acknowledged
- [ ] CV and letter agree with each other; tone consistent; spelling clean
- [ ] `python -m jobhunt ats-check` passes: text extracts, email + phone present as text, missing keywords reviewed (added only where true)
- [ ] Letter fits one page; CV at most two

## Follow-ups and thank-you notes (`/outcome`)

- Follow-up after 10+ quiet days, at most two per application, 60-110 words, polite, adds one relevant new fact if there is one; never pushy, never claims anything not already in the application.
- Thank-you after an interview: within 24 hours, references one specific thing discussed (from the person's notes), restates interest.
- Always drafts. The person sends.

## Form answers

Draft answers to application-form questions in the archive folder (`form_answers.md`). Factual
questions (right to work, notice period, salary expectations, referees) come only from the profile;
if the profile lacks the answer, ask the person.
