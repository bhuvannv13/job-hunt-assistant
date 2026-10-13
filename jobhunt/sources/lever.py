"""Lever postings API: https://github.com/lever/postings-api"""
from __future__ import annotations

from ..models import Job, html_to_text
from ._util import iso_date, join_locations

API = "https://api.lever.co/v0/postings/{token}"


def parse(data, company: str) -> list[Job]:
    jobs = []
    for item in data or []:
        cats = item.get("categories") or {}
        lists = "\n\n".join(f"{block.get('text', '')}\n{html_to_text(block.get('content'))}" for block in item.get("lists") or [])
        description = "\n\n".join(p for p in [item.get("descriptionPlain") or html_to_text(item.get("description")),
                                               lists, item.get("additionalPlain") or ""] if p).strip()
        location = join_locations(cats.get("location"), cats.get("allLocations"))
        workplace = (item.get("workplaceType") or "").lower()
        jobs.append(Job(
            source="lever", company=company, title=(item.get("text") or "").strip(), location=location,
            url=item.get("hostedUrl") or "", apply_url=item.get("applyUrl") or "", description=description,
            posted=iso_date(item.get("createdAt")), remote=workplace == "remote" or "remote" in location.lower(),
            employment_type=cats.get("commitment") or "", department=cats.get("team") or cats.get("department") or "",
        ))
    return [j for j in jobs if j.url and j.title]


def fetch(token: str, name: str | None = None) -> list[Job]:
    from . import get_json
    return parse(get_json(API.format(token=token), params={"mode": "json"}), name or token)
