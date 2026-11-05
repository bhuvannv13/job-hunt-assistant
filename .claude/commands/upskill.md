---
description: Skill-gap heatmap across the jobs that fit you best, and a short learning plan
argument-hint: "[posting url for a single-job gap check]"
---

1. If `$ARGUMENTS` is a posting URL: use the `posting-fetcher` agent, then compare its requirements with `private/profile.yaml` and list each gap as: requirement, how often it appears in your other top jobs (from step 2), closest real experience.
2. Otherwise run `python -m jobhunt upskill --profile private/profile.yaml --top 60` and show the heatmap and the top 10 gaps by priority, plus the strengths the market asks for most.
3. For the top 3-5 gaps write `private/upskill_plan.md`: why it matters (how many jobs ask), a free or low-cost resource found by searching (official docs or course pages, with links), a small portfolio project that would show it, and a realistic time estimate.
4. Never add a skill to the profile until the person has actually learned and used it; offer to update `profile.yaml` when they say they have.
