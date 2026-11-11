"""Fact check a finished CV or cover letter against your own sources (python -m jobhunt factcheck).

A tailored CV may reword your experience, but every number, percentage, year and named organisation in
it must come from somewhere you wrote: the profile or a document you supplied. This lists the ones that
do not, so a made-up figure ("cut costs by 30%") or employer cannot slip through a fluent draft.

It is deliberately strict and simple: a number counts as supported only if the same number appears in a
source. Rewordings of real facts pass; new facts do not. It cannot judge every claim, so a person still
reads the CV before sending it.

Idea adapted from the CV fact verifier in career-ops (MIT, https://github.com/career-ops-hq/career-ops).
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(\s?%|\s?k\b|\+)?", re.I)
# Two or more capitalised words in a row (an organisation, product or place), e.g. "University College Dublin".
PROPER = re.compile(r"\b([A-Z][a-z][\w&'-]*(?:[ \t]+(?:of|for|and|&|de|the)?[ \t]*[A-Z][a-z][\w&'-]*)+)")
# Capitalised words that are not names: months, salutations, sentence starters.
COMMON = {"jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "sept", "oct", "nov", "dec", "january", "february",
          "march", "april", "june", "july", "august", "september", "october", "november", "december", "dear", "hiring",
          "manager", "team", "yours", "sincerely", "faithfully", "regards", "kind", "best", "thank", "the", "and", "for",
          "of", "my", "in", "at", "as", "this", "with", "re", "present", "live", "demo", "code", "github"}
PHONE = re.compile(r"\+?\d[\d ()-]{7,}\d")
DATE = re.compile(r"\b\d{1,2}(?:st|nd|rd|th)? (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{4}\b")
IGNORE_NUMBERS = {"1", "2", "3", "4", "5", "10", "100"}   # list markers, "top 5", "100%": too common to judge
IGNORE_PHRASES = {"dear hiring", "hiring manager", "yours sincerely", "yours faithfully", "kind regards", "best regards",
                  "cover letter", "curriculum vitae", "technical skills", "work experience", "other projects",
                  "key skills", "awards and activities", "live demo"}


@dataclass
class FactReport:
    file: str
    numbers_checked: int = 0
    names_checked: int = 0
    unsupported_numbers: list[str] = field(default_factory=list)
    unsupported_names: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.unsupported_numbers and not self.unsupported_names

    def to_dict(self) -> dict:
        return {**asdict(self), "ok": self.ok}


def read_any(path: str | Path) -> str:
    path = Path(path)
    if path.suffix.lower() in (".pdf", ".docx"):
        from .ats import extract
        return extract(path)[0]
    return path.read_text(encoding="utf-8", errors="replace")


def _norm_number(raw: str) -> str:
    return raw.replace(",", "").rstrip("0").rstrip(".") if "." in raw else raw.replace(",", "")


def _numbers(text: str) -> set[str]:
    return {_norm_number(m.group(1)) for m in NUMBER.finditer(text)}


def _squash(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def sources_text(paths: list[str | Path]) -> str:
    parts = []
    for p in paths:
        p = Path(p)
        files = [f for f in p.rglob("*") if f.is_file()] if p.is_dir() else [p]
        for f in files:
            if f.suffix.lower() in (".pdf", ".docx", ".md", ".txt", ".yaml", ".yml", ".json", ".csv", ".tex", ".html", ".py"):
                try:
                    parts.append(read_any(f))
                except Exception:   # an unreadable source is skipped, not fatal
                    continue
    return "\n".join(parts)


def check(document: str | Path, sources: list[str | Path], allow: list[str] | None = None) -> FactReport:
    text = read_any(document)
    text = DATE.sub(" ", PHONE.sub(" ", text))     # the letter's date and phone numbers are not claims
    source = sources_text(sources) + "\n" + "\n".join(allow or [])
    have_numbers, have_words = _numbers(source), set(_squash(source.replace("&", " and ")).split())
    report = FactReport(file=str(document))
    seen = set()
    for m in NUMBER.finditer(text):
        value = _norm_number(m.group(1))
        if value in seen or value in IGNORE_NUMBERS:
            continue
        seen.add(value)
        report.numbers_checked += 1
        if value not in have_numbers:
            start, end = max(0, m.start() - 40), min(len(text), m.end() + 40)
            report.unsupported_numbers.append(f"{m.group(0).strip()}  …{' '.join(text[start:end].split())}…")
    # Names are checked word by word, so a PDF layout that runs two columns together ("University College
    # Dublin Dublin") does not raise a false alarm, but an invented organisation ("Globex Corporation") does.
    names = set()
    for m in PROPER.finditer(text):
        name = " ".join(m.group(1).split()).strip(".,'")
        key = _squash(name)
        if key in names or key in IGNORE_PHRASES or len(key) < 5:
            continue
        names.add(key)
        report.names_checked += 1
        unknown = [w for w in _squash(name.replace("&", " and ")).split() if w not in have_words and w not in COMMON and len(w) > 2]
        if unknown:
            report.unsupported_names.append(f"{name}  (not in your sources: {', '.join(unknown)})")
    return report


def format_report(report: FactReport) -> str:
    head = (f"Fact check: {'PASS' if report.ok else 'CHECK THESE'} ({report.file}: {report.numbers_checked} numbers, "
            f"{report.names_checked} names checked against your sources)")
    lines = [head]
    lines += [f"  ✗ number not in your sources: {n}" for n in report.unsupported_numbers]
    lines += [f"  ? name not in your sources: {n}" for n in report.unsupported_names]
    if not report.ok:
        lines.append("  Remove anything you cannot back up, or add the source document. Names may be the employer's own "
                     "(from the posting): pass the posting with --source to allow them.")
    return "\n".join(lines)
