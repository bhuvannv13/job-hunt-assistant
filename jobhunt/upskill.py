"""Skill-gap heatmap (python -m jobhunt upskill).

Looks at the jobs that fit you best and counts which skills they ask for that your CV or profile does
not show. A gap that appears in many good-fit adverts is worth learning first; /upskill then turns the
list into a study plan with resources and time estimates.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .match import Preferences, rank
from .models import Job
from .skills import find_skills


@dataclass
class Gap:
    skill: str
    jobs: int            # good-fit jobs asking for it
    share: float         # of all good-fit jobs considered
    avg_score: float     # average match score of those jobs
    examples: list[str]  # "Role at Company"

    @property
    def priority(self) -> float:
        return round(self.share * 100 * (0.5 + self.avg_score / 200), 1)


def gaps(jobs: list[Job], cv_text: str, prefs: Preferences, top: int = 60) -> tuple[list[Gap], list[str], int]:
    """Return (gaps sorted by priority, skills you already have that adverts ask for, number of jobs used)."""
    have = set(find_skills(cv_text))
    ranked, _ = rank(jobs, cv_text, sorted(have), Preferences(**{**prefs.__dict__, "min_score": 0}))
    pool = ranked[:top]
    counts: dict[str, list[Job]] = defaultdict(list)
    covered: dict[str, int] = defaultdict(int)
    for job in pool:
        for skill in set(job.missing_skills):
            counts[skill].append(job)
        for skill in set(job.matched_skills):
            covered[skill] += 1
    out = []
    for skill, items in counts.items():
        out.append(Gap(skill, len(items), len(items) / max(len(pool), 1),
                       round(sum(j.score for j in items) / len(items), 1),
                       [f"{j.title} at {j.company}" for j in sorted(items, key=lambda j: -j.score)[:3]]))
    out.sort(key=lambda g: (-g.priority, g.skill))
    strengths = [s for s, _ in sorted(covered.items(), key=lambda kv: -kv[1])]
    return out, strengths, len(pool)


def heat(share: float) -> str:
    return "🟥" if share >= 0.3 else "🟧" if share >= 0.15 else "🟨" if share >= 0.05 else "⬜"


def markdown(gap_list: list[Gap], strengths: list[str], n_jobs: int, limit: int = 20) -> str:
    lines = [f"# Skill gaps across your top {n_jobs} matching jobs", "",
             "| | Skill | Good-fit jobs asking | Share | Avg match | Priority | Examples |", "|---|---|---|---|---|---|---|"]
    for g in gap_list[:limit]:
        lines.append(f"| {heat(g.share)} | {g.skill} | {g.jobs} | {g.share:.0%} | {g.avg_score:.0f} | {g.priority} | {'; '.join(g.examples)} |")
    lines += ["", "🟥 30%+ of adverts · 🟧 15-29% · 🟨 5-14% · ⬜ under 5%", "",
              "Skills you already show that these adverts ask for: " + (", ".join(strengths[:15]) or "none detected")]
    return "\n".join(lines) + "\n"
