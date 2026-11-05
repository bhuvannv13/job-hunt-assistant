"""Application tracker and archive (private, never committed).

private/applications.csv      one row per application, the system of record
private/applications/<slug>/  what you actually sent: posting.md, evaluation.md, CV, cover letter,
                              outcome.md (stage log), interview_prep.md

The Claude commands (/apply, /outcome, /gmail-sync, /interview, /report) read and write through this
module so the format stays consistent. Cells are written CSV-injection-safe (a value starting with
= + - @ is prefixed with an apostrophe) because the file is often opened in Excel.
"""
from __future__ import annotations

import csv
import re
from dataclasses import asdict, dataclass, fields
from datetime import date, timedelta
from pathlib import Path

PRIVATE = Path("private")
CSV_PATH = PRIVATE / "applications.csv"
ARCHIVE = PRIVATE / "applications"

STATUSES = ["considering", "applied", "assessment", "interview_1", "interview_2", "final_interview",
            "offer", "hired", "offer_declined", "rejected", "withdrawn", "no_response"]
OPEN = {"applied", "assessment", "interview_1", "interview_2", "final_interview"}
CLOSED = {"hired", "offer_declined", "rejected", "withdrawn", "no_response"}
MAX_FOLLOWUPS = 2


@dataclass
class Application:
    id: str
    company: str
    role: str
    url: str = ""
    location: str = ""
    source: str = ""
    score: str = ""
    status: str = "considering"
    status_date: str = ""
    date_applied: str = ""
    next_step: str = ""
    channel: str = ""          # employer site, LinkedIn, referral, agency ...
    sector: str = ""
    notes: str = ""
    folder: str = ""
    followups_sent: str = "0"
    last_followup: str = ""


FIELDS = [f.name for f in fields(Application)]


def slug(company: str, role: str) -> str:
    raw = f"{company}_{role}"
    return re.sub(r"[^A-Za-z0-9]+", "_", raw).strip("_")[:70] or "application"


def _safe(value: str) -> str:
    value = "" if value is None else str(value)
    return "'" + value if value[:1] in ("=", "+", "-", "@") else value


def _unsafe(value: str) -> str:
    return value[1:] if value[:2] in ("'=", "'+", "'-", "'@") else value


def load(path: str | Path = CSV_PATH) -> list[Application]:
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return [Application(**{k: _unsafe(row.get(k, "") or "") for k in FIELDS}) for row in csv.DictReader(fh)]


def save(apps: list[Application], path: str | Path = CSV_PATH) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for app in apps:
            writer.writerow({k: _safe(v) for k, v in asdict(app).items()})


def find(apps: list[Application], key: str) -> Application | None:
    key_l = key.lower()
    exact = [a for a in apps if a.id == key or a.folder == key]
    if exact:
        return exact[0]
    loose = [a for a in apps if key_l in f"{a.company} {a.role}".lower()]
    return loose[0] if len(loose) == 1 else None


def add(company: str, role: str, path: str | Path = CSV_PATH, archive: str | Path = ARCHIVE, **values) -> Application:
    apps = load(path)
    base = slug(company, role)
    folder, n = base, 2
    while any(a.folder == folder for a in apps):
        folder, n = f"{base}_{n}", n + 1
    today = date.today().isoformat()
    status = values.pop("status", "considering")
    _check_status(status)
    app = Application(id=folder, company=company, role=role, folder=folder, status=status, status_date=today, **values)
    if status == "applied" and not app.date_applied:
        app.date_applied = today
    apps.append(app)
    save(apps, path)
    folder_path = Path(archive) / folder
    folder_path.mkdir(parents=True, exist_ok=True)
    log = folder_path / "outcome.md"
    if not log.exists():
        log.write_text(f"# {role} - {company}\n\n| Date | Stage | Note |\n|---|---|---|\n| {today} | {status} | added |\n", encoding="utf-8")
    return app


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"Unknown status {status!r}. Use one of: {', '.join(STATUSES)}")


def update(key: str, path: str | Path = CSV_PATH, archive: str | Path = ARCHIVE, note: str = "", **values) -> Application:
    apps = load(path)
    app = find(apps, key)
    if app is None:
        raise KeyError(f"No single application matches {key!r}")
    today = date.today().isoformat()
    if "status" in values and values["status"]:
        _check_status(values["status"])
        if values["status"] != app.status:
            app.status_date = today
        if values["status"] == "applied" and not app.date_applied:
            app.date_applied = today
    for k, v in values.items():
        if v is not None and k in FIELDS:
            setattr(app, k, str(v))
    save(apps, path)
    log = Path(archive) / app.folder / "outcome.md"
    log.parent.mkdir(parents=True, exist_ok=True)
    if not log.exists():
        log.write_text(f"# {app.role} - {app.company}\n\n| Date | Stage | Note |\n|---|---|---|\n", encoding="utf-8")
    with log.open("a", encoding="utf-8") as fh:
        fh.write(f"| {today} | {app.status} | {note.replace('|', '/').replace(chr(10), ' ')} |\n")
    return app


def record_followup(key: str, path: str | Path = CSV_PATH, archive: str | Path = ARCHIVE) -> Application:
    apps = load(path)
    app = find(apps, key)
    if app is None:
        raise KeyError(key)
    sent = int(app.followups_sent or 0) + 1
    return update(app.id, path, archive, note=f"follow-up {sent} sent", followups_sent=str(sent),
                  last_followup=date.today().isoformat())


def followups_due(apps: list[Application], quiet_days: int = 10, today: date | None = None) -> list[tuple[Application, int]]:
    """Open applications with no news for `quiet_days`, that have not had the maximum follow-ups."""
    today = today or date.today()
    due = []
    for app in apps:
        if app.status not in OPEN or int(app.followups_sent or 0) >= MAX_FOLLOWUPS:
            continue
        last = max(d for d in (app.status_date, app.last_followup, app.date_applied) if d) if any(
            (app.status_date, app.last_followup, app.date_applied)) else ""
        if not last:
            continue
        days = (today - date.fromisoformat(last)).days
        if days >= quiet_days:
            due.append((app, days))
    return sorted(due, key=lambda x: -x[1])


def import_rows(rows: list[dict], path: str | Path = CSV_PATH) -> int:
    """Bring in applications tracked elsewhere (e.g. an Excel sheet): rows of company, role, status, date_applied, url."""
    apps = load(path)
    known = {(a.company.lower(), a.role.lower()) for a in apps}
    added = 0
    for row in rows:
        company, role = (row.get("company") or "").strip(), (row.get("role") or "").strip()
        if not company or not role or (company.lower(), role.lower()) in known:
            continue
        status = row.get("status") or "applied"
        if status not in STATUSES:
            status = "applied"
        folder = slug(company, role)
        apps.append(Application(id=folder, company=company, role=role, folder=folder, status=status,
                                status_date=row.get("date_applied") or date.today().isoformat(),
                                date_applied=row.get("date_applied") or "", url=row.get("url") or "",
                                notes=row.get("notes") or "", channel=row.get("channel") or ""))
        known.add((company.lower(), role.lower()))
        added += 1
    save(apps, path)
    return added


INTERVIEW_OR_LATER = {"interview_1", "interview_2", "final_interview", "offer", "hired", "offer_declined"}


def reached_interview(app: Application, archive: str | Path = ARCHIVE) -> bool:
    if app.status in INTERVIEW_OR_LATER:
        return True
    log = Path(archive) / app.folder / "outcome.md"
    return log.exists() and re.search(r"\|\s*(interview_\d|final_interview)\s*\|", log.read_text(encoding="utf-8")) is not None


def summary(apps: list[Application], archive: str | Path = ARCHIVE) -> dict:
    counts = {s: 0 for s in STATUSES}
    for app in apps:
        counts[app.status] = counts.get(app.status, 0) + 1
    applied = [a for a in apps if a.status != "considering"]
    interviews = [a for a in applied if reached_interview(a, archive)]
    return {"total": len(apps), "applied": len(applied), "interviews": len(interviews),
            "offers": counts["offer"] + counts["hired"] + counts["offer_declined"], "by_status": counts}


def last_n_days(apps: list[Application], days: int) -> list[Application]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return [a for a in apps if (a.date_applied or a.status_date) >= cutoff]
