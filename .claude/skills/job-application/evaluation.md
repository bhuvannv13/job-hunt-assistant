# Evaluating a job

Run the four gates in order. A failed gate stops the evaluation: report it with the posting's exact
words quoted, and do not score or draft. Only then score the five dimensions.

## Gate 1 - Right to work

Read the profile's `work_authorisation` (e.g. `Stamp 1G, valid to 2027-12-31; needs an employment
permit after that`) and the posting's eligibility wording.

| Posting says | Verdict |
|---|---|
| Citizenship, permanent residency or a security clearance required | **FAIL** |
| "No sponsorship" / "must already have the right to work" and the candidate's current permission covers the role's start and a reasonable term | **PASS, note** the end date of the permission |
| "No sponsorship" and the permission ends before or soon after the start | **FLAG**: the person decides |
| Names the candidate's permission, or says visas/sponsorship considered | **PASS** (a positive worth noting) |
| Silent | **PASS, unverified**: check the employer's careers or FAQ page before drafting |

Answer the application form's sponsorship question truthfully from the profile; never adjust it to look better.

## Gate 2 - Language

Compare languages the **role** requires (not the language of the advert) with the profile's `languages`.
A required language not on the list is **FAIL**. A listed language at a plausibly lower level than asked
("fluent", "C1") is **FLAG**: score and draft, and tell the person. Otherwise PASS.

## Gate 3 - Experience bar

`required_years` in the posting vs the profile's `max_years` preference (default 2 for graduate searches).
More than 2 years above the candidate's real experience is **FAIL** unless the posting says the bar is
flexible. Senior / lead / principal titles are FAIL for graduate searches.

## Gate 4 - Deal-breakers

Anything in the profile's `deal_breakers` (location, contract type, sector, salary floor, on-site days).
Also stop on scam signs: fees, chat-app-only contact, requests for bank, PPS or passport details before
an offer (`python -m jobhunt.verify` labels "Caution").

## Scoring (each 0-100, then a weighted overall)

| Dimension | Weight | 80-100 | 50-79 | under 50 |
|---|---|---|---|---|
| Technical skills | 35% | Core requirements are things the profile shows clearly | Most match; 1-2 learnable gaps | Several core gaps |
| Experience fit | 20% | Level and domain match the role | Adjacent domain or slightly junior | Clear mismatch |
| Domain / sector interest | 15% | In the profile's target sectors | Neutral | Outside stated interests |
| Growth & learning | 15% | Builds toward the profile's goals | Some | Little |
| Practical fit | 15% | Location, hours, salary, start date all work | One compromise | Several |

Overall = weighted sum, rounded. Bands: **75+ strong fit, apply**; **60-74 worth applying with a clear
gap story**; **45-59 stretch, apply only if keen**; **under 45 skip**.

## Report format (show before drafting)

```
Posting guard: <verdict line>
Gates: right to work PASS (Stamp 1G to Dec 2027; ad silent) | language PASS | experience PASS (asks 1-2 yrs) | deal-breakers PASS
Scores: technical 78 · experience 65 · domain 80 · growth 85 · practical 90 -> overall 79 (strong fit)
Strengths: 3 bullets tied to specific requirements and specific profile evidence
Gaps: each requirement the profile does not show, and the honest bridge (adjacent experience) if any
Questions for the person: anything only they can answer (salary, start date, willingness to relocate)
```

Strengths and gaps quote the requirement and point to the profile entry that supports it. Never count a
skill as present because it "would be easy to learn".
