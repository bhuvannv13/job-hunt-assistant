"""Glue: collect jobs, check employers, rank, tailor and track."""
from __future__ import annotations

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path

import yaml

from . import sources, verify
from .match import Preferences, location_ok, rank
from .models import Job

log = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parent.parent


def load_companies(path: str | Path = ROOT / "config" / "companies.yaml") -> list[dict]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["companies"]


def load_preferences(path: str | Path | None) -> Preferences:
    if path and Path(path).exists():
        return Preferences.from_dict(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
    return Preferences()


def collect(companies: list[dict], workers: int = 8) -> tuple[list[Job], dict[str, int]]:
    """Fetch every company's board in parallel. Returns jobs and a per-company count (-1 = failed)."""
    counts: dict[str, int] = {}

    def one(company):
        try:
            jobs = sources.fetch_company(company["ats"], company["token"], company["name"])
        except Exception as error:  # a broken board must not stop the run
            log.warning("%s failed: %s", company["name"], error)
            return company["name"], None
        return company["name"], jobs

    out: list[Job] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for name, jobs in pool.map(one, companies):
            counts[name] = -1 if jobs is None else len(jobs)
            out.extend(jobs or [])
    return out, counts


def check_trust(jobs: list[Job], company_status: dict[str, dict]) -> list[Job]:
    for job in jobs:
        job.trust, job.trust_evidence = verify.assess(job, company_status.get(job.company))
    return jobs


def publish_jobs(jobs: list[Job], prefs: Preferences, path: str | Path, counts: dict[str, int]) -> int:
    """Write the public job list used by the website: only jobs in the chosen locations."""
    from .match import category_of, language_barrier, level_of, required_years
    from .skills import find_skills

    local = [j for j in jobs if location_ok(j, prefs)]
    everyone = Preferences(languages=["English"])
    records = []
    for job in local:
        job.category, job.level = category_of(job), level_of(job)
        if job.level in ("Senior", "Mid / senior"):   # the site is for graduate and junior roles
            continue
        record = job.to_dict()
        record["skills"] = find_skills(f"{job.title}\n{job.description}")   # before truncating
        record["years"] = required_years(job.description)
        record["language"] = language_barrier(job, everyone)
        record["description"] = job.description[:2500]
        for key in ("score", "matched_skills", "missing_skills", "reasons"):
            record.pop(key, None)
        records.append(record)
    payload = {"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"),
               "companies_checked": len(counts), "companies_failed": sorted(k for k, v in counts.items() if v < 0),
               "jobs": records}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    write_skills(Path(path).parent / "skills.json")
    return len(records)


def write_skills(path: Path) -> None:
    """Export the skill patterns so the website detects skills exactly like the Python tool."""
    from .skills import _COMPILED
    data = {name: {"source": p.pattern, "flags": "" if name == "R" else "i"} for name, p in _COMPILED.items()}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def load_jobs(path: str | Path) -> list[Job]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Job.from_dict(d) for d in data["jobs"]]


def slug(text: str, limit: int = 50) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")[:limit]


def run_match(jobs: list[Job], cv_text: str, cv_skills: list[str], prefs: Preferences, out_dir: str | Path,
              profile: dict | None = None, cv=None, tailor_top: int = 10, include_caution: bool = False,
              tracker_name: str = "job_tracker.xlsx") -> dict:
    from . import tailor
    from .tracker import write_tracker

    out_dir = Path(out_dir)
    ranked, dropped = rank(jobs, cv_text, cv_skills, prefs)
    if not include_caution:
        caution = [j for j in ranked if j.trust == "Caution"]
        ranked = [j for j in ranked if j.trust != "Caution"]
        if caution:
            dropped["scam warning signs"] = len(caution)
    cv_files = {}
    for job in ranked[:tailor_top]:
        name = f"{slug(job.company, 25)}_{slug(job.title, 40)}"
        if profile:
            tailored = tailor.tailor_profile(profile, job)
            docx_path = tailor.write_tailored_docx(tailored, out_dir / "cvs" / f"CV_{name}.docx")
            letter = tailor.cover_letter(profile, job, tailored)
        else:
            text, report = tailor.tailor_plain_cv(cv, job)
            docx_path = tailor.write_text_docx(text, out_dir / "cvs" / f"CV_{name}.docx")
            letter = ("Skills from the advert that your CV shows: " + ", ".join(report["matched"]) + "\n\n" +
                      "\n".join(report["advice"]))
        tailor.write_text_docx(letter, out_dir / "cover_letters" / f"Cover_letter_{name}.docx",
                               title=f"{job.title} – {job.company}")
        cv_files[job.id] = docx_path.name
    tracker = write_tracker(ranked, out_dir / tracker_name, cv_files)
    summary = {"ranked": len(ranked), "dropped": dropped, "tailored": len(cv_files), "tracker": str(tracker),
               "date": date.today().isoformat()}
    (out_dir / "shortlist.md").write_text(shortlist_markdown(ranked[:40]), encoding="utf-8")
    return summary


def shortlist_markdown(jobs: list[Job]) -> str:
    lines = ["| # | Score | Role | Company | Location | Trust | Link |", "|---|---|---|---|---|---|---|"]
    for i, j in enumerate(jobs, 1):
        lines.append(f"| {i} | {j.score:.0f} | {j.title} | {j.company} | {j.location[:40]} | {j.trust} | {j.url} |")
    return "\n".join(lines) + "\n"
