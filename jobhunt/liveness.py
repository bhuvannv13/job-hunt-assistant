"""Is a job posting still open? Check before spending an evening on a tailored application.

Three answers, each with the evidence behind it:

* ``closed``    the board's API no longer lists the job, the page is gone (404/410), or the page says
                the posting has closed, expired or been filled
* ``open``      the board's API lists it, or the page loads and shows an apply control
* ``uncertain`` anything else (login walls, blocked requests, pages without an apply button)

For Greenhouse, Lever and Ashby the public job-board API is asked directly, which is reliable. Other
links fall back to reading the page. Only the posting URL itself is fetched; links inside a posting are
never followed.

Approach adapted from the liveness checker in career-ops (MIT, https://github.com/career-ops-hq/career-ops):
API first, closure phrases before apply buttons, and "uncertain" rather than a guess.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

USER_AGENT = "job-hunt-assistant/1.0 (+https://github.com/bhuvannv13/job-hunt-assistant)"

CLOSED_PATTERNS = [re.compile(p, re.I) for p in (
    r"job (?:is )?no longer available",
    r"(?:job|position|role|posting|vacancy)[^.\n]{0,40}no longer (?:open|available|active)",
    r"\b(?:job|position|role|posting|opening|vacancy|requisition)\b[^.\n]{0,60}?(?<!application )(?<!form )has been filled\b(?!\s+out)",
    r"this (?:job|posting|vacancy|advert) has expired",
    r"no longer accepting applications",
    r"this (?:job|role|position|vacancy)(?: listing)? is (?:now )?closed\b(?!-)",
    r"applications? (?:for this (?:role|position|job) )?(?:have|has|are|is) (?:now )?closed",
    r"(?:the )?closing date (?:for this (?:role|vacancy) )?has passed",
    r"job (?:listing )?not found",
    r"the job you(?:'re| are) (?:looking|searching) for (?:is no longer|may have|has) (?:available|closed|been removed)",
    r"(?:sorry|unfortunately),? this (?:job|position|vacancy) (?:was|has been) removed",
)]
APPLY_PATTERNS = [re.compile(p, re.I) for p in (
    r"\bapply (?:now|for this (?:job|role|position)|here|online|today)\b",
    r"\bsubmit (?:your )?application\b",
    r"\beasy apply\b",
    r"<(?:button|a|input)[^>]*>\s*apply\s*<",
    r"<(?:button|input)[^>]*(?:value|aria-label)=\"apply",
)]
LOGIN_WALL = re.compile(r"\b(?:sign in|log in|login) to (?:view|see|apply|continue)\b", re.I)


@dataclass
class Liveness:
    url: str
    status: str            # open | closed | uncertain
    evidence: str

    def to_dict(self) -> dict:
        return {"url": self.url, "status": self.status, "evidence": self.evidence}


def _normalise(text: str) -> str:
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text)


def judge_page(html: str, http_status: int = 200) -> tuple[str, str]:
    """Classify a fetched page. Closure wording wins over an apply button (closed pages often keep one)."""
    if http_status in (404, 410):
        return "closed", f"page returns HTTP {http_status}"
    if http_status >= 400:
        return "uncertain", f"page returns HTTP {http_status}"
    text = _normalise(html or "")
    for pattern in CLOSED_PATTERNS:
        match = pattern.search(text)
        if match:
            return "closed", f'page says "{match.group(0).strip()}"'
    if any(p.search(text) for p in APPLY_PATTERNS):
        return "open", "page loads and shows an apply control"
    if LOGIN_WALL.search(text):
        return "uncertain", "page asks you to sign in"
    return "uncertain", "page loads but shows no apply control"


def _ats_api(url: str) -> tuple[str, str] | None:
    """Return (api_url, kind) for boards with a public per-job endpoint."""
    parsed = urlparse(url)
    host, parts = parsed.netloc.lower(), [p for p in parsed.path.split("/") if p]
    if host.endswith("greenhouse.io") and "jobs" in parts:
        board = parts[0] if parts[0] not in ("embed", "jobs") else None
        job_id = parts[parts.index("jobs") + 1] if parts.index("jobs") + 1 < len(parts) else None
        if board and job_id and job_id.isdigit():
            return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}", "greenhouse"
    if host == "jobs.lever.co" and len(parts) >= 2:
        return f"https://api.lever.co/v0/postings/{parts[0]}/{parts[1]}", "lever"
    if host == "jobs.ashbyhq.com" and len(parts) >= 2:
        return f"https://api.ashbyhq.com/posting-api/job-board/{parts[0]}", "ashby"
    return None


def check(url: str, session: requests.Session | None = None, timeout: int = 15) -> Liveness:
    session = session or requests.Session()
    headers = {"User-Agent": USER_AGENT}
    api = _ats_api(url)
    if api:
        api_url, kind = api
        try:
            resp = session.get(api_url, timeout=timeout, headers=headers)
        except requests.RequestException as exc:
            return Liveness(url, "uncertain", f"{kind} API unreachable ({exc.__class__.__name__})")
        if kind == "ashby" and resp.ok:
            job_id = [p for p in urlparse(url).path.split("/") if p][1]
            ids = {str(j.get("id")) for j in resp.json().get("jobs", [])}
            return (Liveness(url, "open", "listed on the Ashby job board") if job_id in ids
                    else Liveness(url, "closed", "no longer listed on the Ashby job board"))
        if resp.status_code in (404, 410):
            return Liveness(url, "closed", f"{kind} API no longer lists this job")
        if resp.ok:
            return Liveness(url, "open", f"{kind} API lists this job")
        return Liveness(url, "uncertain", f"{kind} API returned HTTP {resp.status_code}")
    try:
        resp = session.get(url, timeout=timeout, headers=headers, allow_redirects=True)
    except requests.RequestException as exc:
        return Liveness(url, "uncertain", f"page unreachable ({exc.__class__.__name__})")
    status, evidence = judge_page(resp.text, resp.status_code)
    return Liveness(url, status, evidence)
