"""Shared data structures."""
from __future__ import annotations

import hashlib
import html
import re
from dataclasses import asdict, dataclass, field

_TAG = re.compile(r"<[^>]+>")
_SPACE = re.compile(r"[ \t\r\f\v]+")
_BLANK_LINES = re.compile(r"\n\s*\n+")


def html_to_text(raw: str | None) -> str:
    """Turn job-board HTML (sometimes HTML-escaped twice) into readable plain text."""
    if not raw:
        return ""
    text = html.unescape(html.unescape(raw))
    text = re.sub(r"(?i)<\s*br\s*/?>|</\s*(p|div|li|h[1-6]|tr)\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*li[^>]*>", "\n• ", text)
    text = _TAG.sub(" ", text)
    text = _SPACE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return _BLANK_LINES.sub("\n\n", text).strip()


@dataclass
class Job:
    source: str            # e.g. "greenhouse"
    company: str
    title: str
    location: str
    url: str               # page where a person can read and apply
    description: str = ""  # plain text
    posted: str = ""       # ISO date (YYYY-MM-DD) when known
    remote: bool = False
    employment_type: str = ""
    department: str = ""
    apply_url: str = ""
    # Filled in by matching
    score: float = 0.0
    category: str = ""
    level: str = ""
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    trust: str = ""
    trust_evidence: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return hashlib.sha1(self.url.encode("utf-8")).hexdigest()[:12]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["id"] = self.id
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
