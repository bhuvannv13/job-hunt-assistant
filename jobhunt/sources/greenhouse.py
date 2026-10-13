"""Greenhouse job boards: https://developers.greenhouse.io/job-board.html"""
from __future__ import annotations

from ..models import Job, html_to_text
from ._util import iso_date, join_locations

API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def parse(data: dict, company: str) -> list[Job]:
    jobs = []
    for item in (data or {}).get("jobs", []):
        offices = [o.get("location") or o.get("name") for o in item.get("offices") or []]
        location = join_locations((item.get("location") or {}).get("name"), offices)
        departments = ", ".join(d.get("name", "") for d in item.get("departments") or [] if d.get("name"))
        jobs.append(Job(
            source="greenhouse", company=company, title=(item.get("title") or "").strip(),
            location=location, url=item.get("absolute_url") or "",
            description=html_to_text(item.get("content")),
            posted=iso_date(item.get("first_published") or item.get("updated_at")),
            remote="remote" in location.lower(), department=departments,
        ))
    return [j for j in jobs if j.url and j.title]


def fetch(token: str, name: str | None = None) -> list[Job]:
    from . import get_json
    return parse(get_json(API.format(token=token), params={"content": "true"}), name or token)
