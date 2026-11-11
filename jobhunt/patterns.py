"""What is working? Funnel and rejection patterns from the application tracker.

After a run of rejections the useful question is not "how many" but "where": which channel, sector or
score band turns into interviews, how quickly rejections arrive, and which applications have gone
silent long enough to count as no response.

    python -m jobhunt patterns            # text summary
    python -m jobhunt patterns --json     # for the report or another tool

Idea adapted from the rejection-pattern, funnel and rejection-latency analyses in career-ops
(MIT, https://github.com/career-ops-hq/career-ops).
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import date
from pathlib import Path
from statistics import median

from .applications import ARCHIVE, CLOSED, OPEN, Application, reached_interview

GHOST_DAYS = 30          # open applications silent this long are probably "no response"
MIN_GROUP = 3            # do not draw conclusions from smaller groups


def _days(start: str, end: str) -> int | None:
    try:
        return (date.fromisoformat(end) - date.fromisoformat(start)).days
    except (TypeError, ValueError):
        return None


def score_band(score: str) -> str:
    try:
        value = float(score)
    except (TypeError, ValueError):
        return "no score"
    if value <= 5:            # scores kept on a 1-5 scale
        value *= 20
    return "70+" if value >= 70 else "50-69" if value >= 50 else "under 50"


def _group(apps: list[Application], key, archive) -> list[dict]:
    groups: dict[str, list[Application]] = defaultdict(list)
    for app in apps:
        groups[key(app) or "unknown"].append(app)
    rows = []
    for name, members in groups.items():
        interviews = sum(1 for a in members if reached_interview(a, archive))
        rejected = sum(1 for a in members if a.status == "rejected")
        waiting = sum(1 for a in members if a.status in OPEN)
        rows.append({"group": name, "applied": len(members), "interviews": interviews, "rejected": rejected,
                     "waiting": waiting, "interview_rate": round(interviews / len(members), 2)})
    return sorted(rows, key=lambda r: (-r["applied"], r["group"]))


def analyse(apps: list[Application], archive: str | Path = ARCHIVE, today: date | None = None) -> dict:
    today = today or date.today()
    applied = [a for a in apps if a.status != "considering"]
    interviews = [a for a in applied if reached_interview(a, archive)]
    rejected = [a for a in applied if a.status == "rejected"]
    latencies = [d for a in rejected if (d := _days(a.date_applied, a.status_date)) is not None and d >= 0]
    ghosted = []
    for a in applied:
        if a.status == "applied":
            last = max((x for x in (a.status_date, a.last_followup, a.date_applied) if x), default="")
            silent = _days(last, today.isoformat()) if last else None
            if silent is not None and silent >= GHOST_DAYS:
                ghosted.append({"id": a.id, "company": a.company, "role": a.role, "silent_days": silent})
    result = {
        "applied": len(applied),
        "interviews": len(interviews),
        "rejected": len(rejected),
        "waiting": sum(1 for a in applied if a.status in OPEN),
        "closed": sum(1 for a in applied if a.status in CLOSED),
        "interview_rate": round(len(interviews) / len(applied), 2) if applied else 0.0,
        "median_days_to_rejection": median(latencies) if latencies else None,
        "by_channel": _group(applied, lambda a: a.channel.strip().lower(), archive),
        "by_sector": _group(applied, lambda a: a.sector.strip().lower(), archive),
        "by_score": _group(applied, lambda a: score_band(a.score), archive),
        "probably_ghosted": sorted(ghosted, key=lambda g: -g["silent_days"]),
    }
    result["insights"] = insights(result)
    return result


def insights(result: dict) -> list[str]:
    """Plain-language observations, only from groups big enough to mean something."""
    notes = []
    if result["applied"] < 5:
        return ["Fewer than 5 applications recorded: too early for patterns."]
    if result["interviews"] == 0 and result["applied"] >= 15:
        notes.append(f"No interviews from {result['applied']} applications: tighten targeting (fewer, better-fit roles) "
                     "and get the CV reviewed before sending more.")
    for dim, label in (("by_channel", "channel"), ("by_sector", "sector"), ("by_score", "score band")):
        groups = [g for g in result[dim] if g["applied"] >= MIN_GROUP and g["group"] != "unknown"]
        if len(groups) < 2:
            continue
        best = max(groups, key=lambda g: g["interview_rate"])
        worst = min(groups, key=lambda g: g["interview_rate"])
        if best["interview_rate"] > worst["interview_rate"]:
            notes.append(f"By {label}: '{best['group']}' turns {best['interview_rate']:.0%} of applications into interviews, "
                         f"'{worst['group']}' {worst['interview_rate']:.0%}.")
    if result["median_days_to_rejection"] is not None:
        notes.append(f"Rejections arrive a median of {result['median_days_to_rejection']:g} days after applying.")
    if result["probably_ghosted"]:
        notes.append(f"{len(result['probably_ghosted'])} application(s) silent for {GHOST_DAYS}+ days: consider one "
                     "follow-up, then mark them no_response.")
    return notes or ["No clear pattern yet."]


def format_text(result: dict) -> str:
    lines = [f"Applied {result['applied']} · interviews {result['interviews']} ({result['interview_rate']:.0%}) · "
             f"rejected {result['rejected']} · waiting {result['waiting']}"]
    for dim, title in (("by_channel", "Channel"), ("by_sector", "Sector"), ("by_score", "Fit score")):
        if result[dim]:
            lines.append(f"\n{title}:")
            for g in result[dim]:
                lines.append(f"  {g['group'][:28]:<28} applied {g['applied']:>3}  interviews {g['interviews']:>2}  "
                             f"rejected {g['rejected']:>2}  waiting {g['waiting']:>2}")
    if result["probably_ghosted"]:
        lines.append("\nProbably ghosted:")
        lines += [f"  {g['company']} – {g['role']} ({g['silent_days']} days)" for g in result["probably_ghosted"]]
    lines.append("\nWhat it suggests:")
    lines += [f"  - {n}" for n in result["insights"]]
    return "\n".join(lines)


_TITLE_NOISE = re.compile(r"\b(?:m/f/d|f/m/d|h/f|remote|hybrid|dublin|ireland|\d{4})\b|[^a-z0-9 ]", re.I)


def reposts(history: list[dict], min_gap_days: int = 21) -> list[dict]:
    """Same company and title re-advertised under a new link weeks later: possibly a ghost or hard-to-fill job.

    `history` is a list of {"company", "title", "url", "posted"} records collected over time.
    """
    seen: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in history:
        key = (row.get("company", "").strip().lower(), " ".join(_TITLE_NOISE.sub(" ", row.get("title", "").lower()).split()))
        seen[key].append(row)
    flagged = []
    for (company, title), rows in seen.items():
        urls = {r.get("url") for r in rows}
        dates = sorted(r.get("posted") for r in rows if r.get("posted"))
        if len(urls) > 1 and len(dates) >= 2 and (_days(dates[0], dates[-1]) or 0) >= min_gap_days:
            flagged.append({"company": rows[0].get("company"), "title": rows[0].get("title"),
                            "times_posted": len(urls), "first": dates[0], "last": dates[-1]})
    return sorted(flagged, key=lambda f: -f["times_posted"])
