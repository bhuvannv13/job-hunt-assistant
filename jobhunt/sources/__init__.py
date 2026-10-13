"""Job sources.

Only official, public job feeds are used:

* Applicant tracking systems that publish public job-board APIs for their customers'
  career sites: Greenhouse, Lever, Ashby, Workable and SmartRecruiters.
* Optional aggregator APIs that need a free key (Adzuna, Jooble). They are skipped
  when no key is set.

No site is scraped and no login is used. Each fetcher returns a list of Job objects.
"""
from __future__ import annotations

import logging
import time

import requests

from ..models import Job

log = logging.getLogger(__name__)
USER_AGENT = "job-hunt-assistant/0.1 (+https://github.com/bhuvannv13/job-hunt-assistant)"


def get_json(url: str, *, params=None, method="GET", json_body=None, timeout=25, retries=2):
    """GET or POST JSON with a polite user agent and small retry budget. Returns None on failure."""
    for attempt in range(retries + 1):
        try:
            response = requests.request(method, url, params=params, json=json_body, timeout=timeout,
                                        headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
            if response.status_code == 404:
                return None
            if response.status_code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except (requests.RequestException, ValueError) as error:
            if attempt >= retries:
                log.warning("Failed %s: %s", url, error)
                return None
            time.sleep(1 + attempt)
    return None


from . import ashby, greenhouse, lever, smartrecruiters, workable, aggregators  # noqa: E402

ATS_FETCHERS = {
    "greenhouse": greenhouse.fetch,
    "lever": lever.fetch,
    "ashby": ashby.fetch,
    "workable": workable.fetch,
    "smartrecruiters": smartrecruiters.fetch,
}


def fetch_company(ats: str, token: str, name: str | None = None) -> list[Job]:
    fetcher = ATS_FETCHERS.get(ats)
    if fetcher is None:
        raise ValueError(f"Unknown ATS {ats!r}")
    return fetcher(token, name)
