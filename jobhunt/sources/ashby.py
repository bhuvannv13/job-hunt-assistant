"""Ashby public job postings API: https://developers.ashbyhq.com/docs/public-job-posting-api"""
from __future__ import annotations

from ..models import Job, html_to_text
from ._util import iso_date, join_locations

API = "https://api.ashbyhq.com/posting-api/job-board/{token}"


def parse(data: dict, company: str) -> list[Job]:
    jobs = []
    for item in (data or {}).get("jobs", []):
        if item.get("isListed") is False:
            continue
        secondary = [s.get("location") for s in item.get("secondaryLocations") or []]
        country = (((item.get("address") or {}).get("postalAddress") or {}).get("addressCountry"))
        location = join_locations(item.get("location"), secondary, country)
        jobs.append(Job(
            source="ashby", company=company, title=(item.get("title") or "").strip(), location=location,
            url=item.get("jobUrl") or "", apply_url=item.get("applyUrl") or "",
            description=item.get("descriptionPlain") or html_to_text(item.get("descriptionHtml")),
            posted=iso_date(item.get("publishedAt")),
            remote=bool(item.get("isRemote")) or (item.get("workplaceType") or "").lower() == "remote",
            employment_type=item.get("employmentType") or "", department=item.get("department") or item.get("team") or "",
        ))
    return [j for j in jobs if j.url and j.title]


def fetch(token: str, name: str | None = None) -> list[Job]:
    from . import get_json
    return parse(get_json(API.format(token=token)), name or token)
