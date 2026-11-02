"""Tell you about new jobs that fit your profile.

Sources: the jobs collected from official job boards (docs/data/jobs.json) and, optionally, the
job-alert emails your own Glassdoor / Indeed / LinkedIn / gradireland / Jobs.ie / IrishJobs accounts
send you (see jobhunt/sources/email_alerts.py).

Each run ranks every job against your CV or profile with the same rules as `match`, drops jobs you
were already told about, and sends the rest through the channels you set:

* ntfy  - free push notifications to the ntfy phone app (env NTFY_TOPIC, optional NTFY_SERVER)
* email - one digest email over SMTP (env SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, NOTIFY_TO),
          optionally with a tailored CV and cover letter attached for the best matches

The tool never applies for you. Every notification links to the employer's or job site's own page so
that you read the advert and submit the application yourself.
"""
from __future__ import annotations

import json
import os
import smtplib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from pathlib import Path

import requests
import yaml

from .match import Preferences, rank
from .models import Job
from .sources.email_alerts import dedupe_key


@dataclass
class NotifySettings:
    min_score: float = 50.0          # only tell me about jobs at or above this score
    max_per_run: int = 10            # cap per notification run
    include_trust: list[str] = field(default_factory=lambda: ["Verified employer", "Official job board", "Unverified"])
    attach_cvs: int = 3              # tailored CV + cover letter for the top N (needs a profile and email)
    remember_days: int = 60          # forget notified jobs after this many days
    channels: list[str] = field(default_factory=lambda: ["ntfy", "email"])

    @classmethod
    def load(cls, path: str | Path | None) -> "NotifySettings":
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) if path and Path(path).exists() else {}
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in (data or {}).items() if k in known})


# ---------------------------------------------------------------- state (what you were already told about)

def load_state(path: str | Path) -> dict[str, str]:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_state(path: str | Path, state: dict[str, str], remember_days: int) -> None:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=remember_days)).date().isoformat()
    kept = {k: v for k, v in state.items() if v >= cutoff}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(kept, indent=0, sort_keys=True), encoding="utf-8")


# ---------------------------------------------------------------- selection

def select_new(jobs: list[Job], cv_text: str, cv_skills: list[str], prefs: Preferences, settings: NotifySettings,
               state: dict[str, str]) -> list[Job]:
    """Rank all jobs, keep good matches that have not been notified before."""
    for job in jobs:   # alert emails rarely carry a location: the alert itself was set up for your area
        if not job.location and job.source in {"glassdoor", "indeed", "linkedin", "gradireland", "irishjobs", "jobs.ie"}:
            job.location = "Ireland (from your job alert)"
    ranked, _ = rank(jobs, cv_text, cv_skills, prefs)
    fresh = []
    for job in ranked:
        if job.score < settings.min_score:
            continue
        if job.trust and job.trust not in settings.include_trust:
            continue
        if dedupe_key(job) in state:
            continue
        fresh.append(job)
    return fresh[: settings.max_per_run]


# ---------------------------------------------------------------- messages

def job_line(job: Job) -> str:
    where = f" ({job.location})" if job.location else ""
    company = f" at {job.company}" if job.company else ""
    trust = f" [{job.trust}]" if job.trust else ""
    return f"{job.score:.0f} | {job.title}{company}{where}{trust}"


def digest_text(jobs: list[Job]) -> str:
    lines = [f"{len(jobs)} new job{'s' if len(jobs) != 1 else ''} that fit your profile:", ""]
    for i, job in enumerate(jobs, 1):
        lines.append(f"{i}. {job_line(job)}")
        lines.append(f"   Source: {job.source}")
        if job.matched_skills:
            lines.append(f"   You have: {', '.join(job.matched_skills[:8])}")
        if job.missing_skills:
            lines.append(f"   Not on your CV: {', '.join(job.missing_skills[:6])}")
        lines.append(f"   Read and apply: {job.url}")
        lines.append("")
    lines.append("Applications are never sent for you: open each link, check the advert and apply yourself.")
    return "\n".join(lines)


def send_ntfy(jobs: list[Job], topic: str, server: str = "https://ntfy.sh") -> int:
    """One push per job, so each notification opens its own advert."""
    sent = 0
    for job in jobs:
        body = job_line(job)
        if job.matched_skills:
            body += "\nYou have: " + ", ".join(job.matched_skills[:6])
        response = requests.post(f"{server.rstrip('/')}/{topic}", data=body.encode("utf-8"), timeout=15, headers={
            "Title": f"New job match: {job.title}"[:120].encode("utf-8"),
            "Click": job.url, "Tags": "briefcase", "Priority": "high" if job.score >= 70 else "default"})
        if response.ok:
            sent += 1
    return sent


def build_email(jobs: list[Job], to: str, sender: str, attachments: list[Path] | None = None) -> EmailMessage:
    message = EmailMessage()
    message["Subject"] = f"{len(jobs)} new job match{'es' if len(jobs) != 1 else ''}: {jobs[0].title}" + \
                         (f" and {len(jobs) - 1} more" if len(jobs) > 1 else "")
    message["From"], message["To"] = sender, to
    message.set_content(digest_text(jobs))
    for path in attachments or []:
        message.add_attachment(Path(path).read_bytes(), maintype="application",
                               subtype="vnd.openxmlformats-officedocument.wordprocessingml.document", filename=Path(path).name)
    return message


def send_email(message: EmailMessage) -> None:
    host, port = os.environ["SMTP_HOST"], int(os.environ.get("SMTP_PORT", "465"))
    user, password = os.environ["SMTP_USER"], os.environ["SMTP_PASSWORD"]
    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
            smtp.login(user, password)
            smtp.send_message(message)
    else:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(message)


def tailored_attachments(jobs: list[Job], profile: dict | None, out_dir: Path, top: int) -> list[Path]:
    """Tailored CV and cover letter (Word) for the best matches, built only from your profile."""
    if not profile or top <= 0:
        return []
    from . import tailor
    from .pipeline import slug
    files = []
    for job in jobs[:top]:
        name = f"{slug(job.company, 25)}_{slug(job.title, 40)}"
        tailored = tailor.tailor_profile(profile, job)
        files.append(tailor.write_tailored_docx(tailored, out_dir / f"CV_{name}.docx"))
        files.append(tailor.write_text_docx(tailor.cover_letter(profile, job, tailored),
                                            out_dir / f"Cover_letter_{name}.docx", title=f"{job.title} - {job.company}"))
    return files


def deliver(jobs: list[Job], settings: NotifySettings, profile: dict | None, out_dir: Path) -> dict[str, int]:
    """Send through every configured channel that has its settings in the environment."""
    report = {"ntfy": 0, "email": 0}
    if not jobs:
        return report
    if "ntfy" in settings.channels and os.environ.get("NTFY_TOPIC"):
        report["ntfy"] = send_ntfy(jobs, os.environ["NTFY_TOPIC"], os.environ.get("NTFY_SERVER", "https://ntfy.sh"))
    if "email" in settings.channels and all(os.environ.get(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_TO")):
        files = tailored_attachments(jobs, profile, out_dir / "notify_attachments", settings.attach_cvs)
        send_email(build_email(jobs, os.environ["NOTIFY_TO"], os.environ["SMTP_USER"], files))
        report["email"] = 1
    return report
