"""Optional aggregator APIs. Each needs a free key from the provider; without a key they are skipped.

* Adzuna: https://developer.adzuna.com/  (env ADZUNA_APP_ID, ADZUNA_APP_KEY, ADZUNA_COUNTRY)
* Jooble: https://jooble.org/api/about   (env JOOBLE_API_KEY)
"""
from __future__ import annotations

import os

from ..models import Job, html_to_text
from ._util import iso_date


def parse_adzuna(data: dict) -> list[Job]:
    jobs = []
    for item in (data or {}).get("results", []):
        jobs.append(Job(
            source="adzuna", company=(item.get("company") or {}).get("display_name") or "",
            title=html_to_text(item.get("title")), location=(item.get("location") or {}).get("display_name") or "",
            url=item.get("redirect_url") or "", description=html_to_text(item.get("description")),
            posted=iso_date(item.get("created")), employment_type=item.get("contract_time") or "",
            department=(item.get("category") or {}).get("label") or "",
        ))
    return [j for j in jobs if j.url and j.title]


def fetch_adzuna(queries: list[str], where: str = "", pages: int = 2) -> list[Job]:
    app_id, app_key = os.environ.get("ADZUNA_APP_ID"), os.environ.get("ADZUNA_APP_KEY")
    if not (app_id and app_key):
        return []
    from . import get_json
    country = os.environ.get("ADZUNA_COUNTRY", "gb")
    jobs = []
    for query in queries:
        for page in range(1, pages + 1):
            data = get_json(f"https://api.adzuna.com/v1/api/jobs/{country}/search/{page}",
                            params={"app_id": app_id, "app_key": app_key, "what": query, "where": where,
                                    "results_per_page": 50, "max_days_old": 30, "content-type": "application/json"})
            batch = parse_adzuna(data)
            jobs.extend(batch)
            if len(batch) < 50:
                break
    return jobs


def parse_jooble(data: dict) -> list[Job]:
    jobs = []
    for item in (data or {}).get("jobs", []):
        jobs.append(Job(
            source="jooble", company=item.get("company") or "", title=html_to_text(item.get("title")),
            location=item.get("location") or "", url=item.get("link") or "",
            description=html_to_text(item.get("snippet")), posted=iso_date(item.get("updated")),
            employment_type=item.get("type") or "",
        ))
    return [j for j in jobs if j.url and j.title]


def fetch_jooble(queries: list[str], where: str = "Ireland") -> list[Job]:
    key = os.environ.get("JOOBLE_API_KEY")
    if not key:
        return []
    from . import get_json
    jobs = []
    for query in queries:
        jobs.extend(parse_jooble(get_json(f"https://jooble.org/api/{key}", method="POST",
                                          json_body={"keywords": query, "location": where})))
    return jobs
