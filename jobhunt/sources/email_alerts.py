"""Jobs from the job-alert emails that job sites send you.

Sites such as Glassdoor, Indeed, LinkedIn, gradireland, Jobs.ie and IrishJobs do not offer a public API,
and their terms forbid scraping. They do email you the jobs that match the alerts you set up on your own
account. This module reads those emails (read-only, over IMAP) and turns each job link into a Job.

Nothing is sent, deleted or marked as read: the mailbox is opened read-only and messages are fetched
with BODY.PEEK.

Environment (only needed for IMAP; parsing .eml files needs nothing):
    IMAP_USER       your email address
    IMAP_PASSWORD   an app password (for Gmail: Google Account > Security > App passwords)
    IMAP_HOST       default imap.gmail.com
"""
from __future__ import annotations

import email
import email.policy
import hashlib
import imaplib
import os
import re
from datetime import date, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from ..models import Job

# sender domain -> (site name, regex a job link must match, order of the text parts inside the link)
SITES = {
    "glassdoor": ("Glassdoor", re.compile(r"glassdoor\.[a-z.]+/(partner/jobListing\.htm|job-listing/|Job/.*_IL\.)", re.I),
                  ("company", "title", "location")),
    "indeed": ("Indeed", re.compile(r"indeed\.[a-z.]+/(rc/clk|viewjob|pagead/clk|m/viewjob)", re.I),
               ("title", "company", "location")),
    "linkedin": ("LinkedIn", re.compile(r"linkedin\.com/(comm/)?jobs/view/", re.I), ("title", "company", "location")),
    "gradireland": ("gradireland", re.compile(r"gradireland\.com/.*(graduate-jobs|/jobs/|internships)/", re.I),
                    ("title", "company", "location")),
    "irishjobs": ("IrishJobs", re.compile(r"irishjobs\.ie/(job|Jobs)/", re.I), ("title", "company", "location")),
    "jobs.ie": ("Jobs.ie", re.compile(r"jobs\.ie/(job|Jobs)/", re.I), ("title", "company", "location")),
}
SENDER_KEYS = {"glassdoor.com": "glassdoor", "indeed.com": "indeed", "linkedin.com": "linkedin",
               "gradireland.com": "gradireland", "irishjobs.ie": "irishjobs", "irishjobsmail.ie": "irishjobs",
               "jobs.ie": "jobs.ie"}

# Text fragments inside a job link that are not title / company / location
_NOISE = re.compile(r"^(\d(\.\d)?\s*★?|★|easy apply|just posted|new|promoted|actively recruiting|be an early applicant|"
                    r"\d+\s*(d|h|days?|hours?|w|weeks?)( ago)?|[€£$].*|.*\b\d+k\b.*|.*\(glassdoor est\.\)|"
                    r".*\(employer est\.\)|apply now|view job|see more jobs?)$", re.I)


class _Links(HTMLParser):
    """Collect (href, [text parts]) for every link in an HTML email."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, list[str]]] = []
        self._href: str | None = None
        self._parts: list[str] = []
        self._depth = 0

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            if self._href is not None:       # unclosed <a>: finish the previous one
                self.handle_endtag("a")
            self._href = dict(attrs).get("href") or ""
            self._parts = []
        elif self._href is not None and tag in ("br", "div", "p", "td", "tr", "span", "li"):
            self._parts.append("\n")

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            parts = [p.strip() for p in re.split(r"\n|\|", "".join(self._parts))]
            self.links.append((self._href, [p for p in parts if p]))
            self._href = None

    def handle_data(self, data):
        if self._href is not None:
            self._parts.append(data)


def site_key(sender: str) -> str | None:
    sender = (sender or "").lower()
    for host, key in SENDER_KEYS.items():
        if host in sender:
            return key
    return None


def canonical_url(url: str) -> str:
    """A stable, clickable URL without tracking parameters where the site allows it."""
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    if "linkedin.com" in parsed.netloc:
        found = re.search(r"/jobs/view/(\d+)", parsed.path)
        if found:
            return f"https://www.linkedin.com/jobs/view/{found.group(1)}/"
    if "indeed." in parsed.netloc and "jk" in query:
        return f"https://{parsed.netloc}/viewjob?jk={query['jk'][0]}"
    if "glassdoor." in parsed.netloc and "jobListingId" in query:
        return f"https://{parsed.netloc}/job-listing/?jl={query['jobListingId'][0]}"
    return url


def parse_alert(html: str, sender: str, received: str = "") -> list[Job]:
    """Turn one job-alert email (HTML body) into Jobs. Unknown senders give an empty list."""
    key = site_key(sender)
    if key is None:
        return []
    site, pattern, order = SITES[key]
    collector = _Links()
    collector.feed(html or "")
    jobs, seen = [], set()
    for href, parts in collector.links:
        if not pattern.search(href or ""):
            continue
        parts = [p for p in parts if not _NOISE.match(p)]
        if not parts:
            continue
        fields = dict(zip(order, parts))
        title = fields.get("title", "").strip()
        if not title or len(title) > 150:
            continue
        url = canonical_url(href)
        if url in seen:
            continue
        seen.add(url)
        jobs.append(Job(source=site.lower(), company=fields.get("company", "").strip(), title=title,
                        location=fields.get("location", "").strip(), url=url, posted=received,
                        description=f"Found in your {site} job alert."))
    return jobs


def _html_part(message) -> str:
    part = message.get_body(preferencelist=("html", "plain"))
    return part.get_content() if part is not None else ""


def parse_message(raw: bytes) -> list[Job]:
    message = email.message_from_bytes(raw, policy=email.policy.default)
    received = ""
    if message["date"]:
        try:
            received = email.utils.parsedate_to_datetime(message["date"]).date().isoformat()
        except (TypeError, ValueError):
            received = ""
    return parse_alert(_html_part(message), str(message["from"] or ""), received)


def from_eml_dir(folder: str | Path) -> list[Job]:
    """Parse saved .eml files (handy for testing, or for mail clients without IMAP)."""
    jobs = []
    for path in sorted(Path(folder).glob("*.eml")):
        jobs += parse_message(path.read_bytes())
    return jobs


def fetch_imap(days: int = 2, max_messages: int = 200) -> list[Job]:
    """Read job alerts from the last `days` days. Returns [] when IMAP_USER / IMAP_PASSWORD are not set."""
    user, password = os.environ.get("IMAP_USER"), os.environ.get("IMAP_PASSWORD")
    if not (user and password):
        return []
    host = os.environ.get("IMAP_HOST", "imap.gmail.com")
    since = (date.today() - timedelta(days=days)).strftime("%d-%b-%Y")
    jobs: list[Job] = []
    with imaplib.IMAP4_SSL(host) as mail:
        mail.login(user, password)
        mail.select("INBOX", readonly=True)
        ids: list[bytes] = []
        for sender in SENDER_KEYS:
            status, data = mail.search(None, "SINCE", since, "FROM", sender)
            if status == "OK" and data and data[0]:
                ids += data[0].split()
        for msg_id in sorted(set(ids))[-max_messages:]:
            status, data = mail.fetch(msg_id, "(BODY.PEEK[])")
            if status == "OK" and data and isinstance(data[0], tuple):
                jobs += parse_message(data[0][1])
    return jobs


def dedupe_key(job: Job) -> str:
    """The same advert often arrives from several sites: key on company + title, not URL."""
    norm = lambda s: re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()  # noqa: E731
    return hashlib.sha1(f"{norm(job.company)}|{norm(job.title)}".encode()).hexdigest()[:16]
