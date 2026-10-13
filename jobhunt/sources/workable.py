"""Workable public jobs widget API (the feed behind each company's apply.workable.com page)."""
from __future__ import annotations

from ..models import Job, html_to_text
from ._util import iso_date, join_locations

API = "https://apply.workable.com/api/v1/widget/accounts/{token}"


def parse(data: dict, company: str) -> list[Job]:
    jobs = []
    name = (data or {}).get("name") or company
    for item in (data or {}).get("jobs", []):
        places = [", ".join(p for p in [loc.get("city"), loc.get("region"), loc.get("country")] if p)
                  for loc in item.get("locations") or []]
        location = join_locations(", ".join(p for p in [item.get("city"), item.get("country")] if p), places)
        jobs.append(Job(
            source="workable", company=name, title=(item.get("title") or "").strip(), location=location,
            url=item.get("url") or item.get("shortlink") or "", apply_url=item.get("application_url") or "",
            description=html_to_text(item.get("description")),
            posted=iso_date(item.get("published_on") or item.get("created_at")),
            remote=bool(item.get("telecommuting")), employment_type=item.get("employment_type") or "",
            department=item.get("department") or "",
        ))
    return [j for j in jobs if j.url and j.title]


def fetch(token: str, name: str | None = None) -> list[Job]:
    from . import get_json
    return parse(get_json(API.format(token=token), params={"details": "true"}), name or token)
