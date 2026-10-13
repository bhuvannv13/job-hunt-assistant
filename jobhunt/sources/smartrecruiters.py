"""SmartRecruiters public Posting API: https://developers.smartrecruiters.com/docs/posting-api"""
from __future__ import annotations

from ..models import Job, html_to_text
from ._util import iso_date, join_locations

API = "https://api.smartrecruiters.com/v1/companies/{token}/postings"


def parse_listing(item: dict, company: str, token: str, detail: dict | None = None) -> Job:
    loc = item.get("location") or {}
    location = join_locations(", ".join(p for p in [loc.get("city"), loc.get("region"), (loc.get("country") or "").upper()] if p),
                              "Remote" if loc.get("remote") else None)
    sections = ((detail or {}).get("jobAd") or {}).get("sections") or {}
    description = "\n\n".join(html_to_text((sections.get(key) or {}).get("text"))
                              for key in ("companyDescription", "jobDescription", "qualifications", "additionalInformation")
                              if (sections.get(key) or {}).get("text"))
    return Job(
        source="smartrecruiters", company=(item.get("company") or {}).get("name") or company,
        title=(item.get("name") or "").strip(), location=location,
        url=(detail or {}).get("postingUrl") or f"https://jobs.smartrecruiters.com/{token}/{item.get('id')}",
        apply_url=(detail or {}).get("applyUrl") or "", description=description,
        posted=iso_date(item.get("releasedDate")), remote=bool(loc.get("remote")),
        employment_type=(item.get("typeOfEmployment") or {}).get("label") or "",
        department=(item.get("function") or {}).get("label") or (item.get("department") or {}).get("label") or "",
        level=(item.get("experienceLevel") or {}).get("label") or "",
    )


def fetch(token: str, name: str | None = None, country: str = "ie", max_details: int = 60) -> list[Job]:
    from . import get_json
    jobs, offset = [], 0
    while True:
        page = get_json(API.format(token=token), params={"limit": 100, "offset": offset, "country": country})
        content = (page or {}).get("content") or []
        for item in content:
            detail = get_json(f"{API.format(token=token)}/{item.get('id')}") if len(jobs) < max_details else None
            jobs.append(parse_listing(item, name or token, token, detail))
        offset += len(content)
        if not content or offset >= (page or {}).get("totalFound", 0):
            break
    return [j for j in jobs if j.title]
