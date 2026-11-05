"""ATS readability check for a finished CV (python -m jobhunt ats-check).

Applicant tracking systems read the text layer of your PDF or Word file, not the page you see. This
extracts that text the way a parser would and checks:

* the text layer is there and clean (no (cid:..) glyph codes, no replacement characters)
* your email and phone appear as literal text, not only as an icon or a link
* which skills from the posting are present in the CV text, and which are missing

It never edits the CV. Missing keywords are a prompt to add them only where they are true.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .skills import find_skills

EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE = re.compile(r"(\+?\d[\d ()-]{7,}\d)")


@dataclass
class AtsReport:
    file: str
    characters: int
    problems: list[str] = field(default_factory=list)
    email_found: bool = False
    phone_found: bool = False
    keywords_present: list[str] = field(default_factory=list)
    keywords_missing: list[str] = field(default_factory=list)
    pages: int | None = None

    @property
    def ok(self) -> bool:
        return not self.problems and self.email_found and self.phone_found

    def to_dict(self) -> dict:
        return {**asdict(self), "ok": self.ok}


def extract(path: str | Path) -> tuple[str, int | None]:
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        import pdfplumber
        with pdfplumber.open(str(path)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages), len(pdf.pages)
    if path.suffix.lower() == ".docx":
        from docx import Document
        doc = Document(str(path))
        parts = [p.text for p in doc.paragraphs]
        for table in doc.tables:
            for row in table.rows:
                parts.append(" | ".join(cell.text for cell in row.cells))
        return "\n".join(parts), None
    return path.read_text(encoding="utf-8", errors="replace"), None


def check(path: str | Path, posting_text: str = "", extra_keywords: list[str] | None = None,
          expect_email: str = "", expect_phone: str = "") -> AtsReport:
    text, pages = extract(path)
    report = AtsReport(file=str(path), characters=len(text.strip()), pages=pages)
    if report.characters < 300:
        report.problems.append("Very little text could be extracted: the CV may be an image or use unreadable fonts.")
    cid = len(re.findall(r"\(cid:\d+\)", text))
    if cid:
        report.problems.append(f"{cid} unreadable glyph code(s) like (cid:123): change the font or how it is embedded.")
    if "�" in text:
        report.problems.append("Replacement characters (�) in the text: some characters do not survive extraction.")
    flat = re.sub(r"\s+", "", text)
    report.email_found = bool(expect_email and expect_email.lower() in text.lower()) or (not expect_email and bool(EMAIL.search(text)))
    if expect_phone:
        digits = re.sub(r"\D", "", expect_phone)[-8:]
        report.phone_found = digits in re.sub(r"\D", "", flat)
    else:
        report.phone_found = bool(PHONE.search(text))
    if not report.email_found:
        report.problems.append("Email address is not in the text layer.")
    if not report.phone_found:
        report.problems.append("Phone number is not in the text layer.")
    wanted = list(dict.fromkeys(find_skills(posting_text) + list(extra_keywords or [])))
    have = set(find_skills(text))
    for kw in wanted:
        present = kw in have or re.search(rf"(?<!\w){re.escape(kw)}(?!\w)", text, re.I) is not None
        (report.keywords_present if present else report.keywords_missing).append(kw)
    return report


def format_report(report: AtsReport) -> str:
    lines = [f"ATS check: {'PASS' if report.ok else 'NEEDS ATTENTION'} ({report.file}, {report.characters} characters"
             + (f", {report.pages} page(s))" if report.pages else ")")]
    lines += [f"  ✗ {p}" for p in report.problems]
    lines.append(f"  {'✓' if report.email_found else '✗'} email in text   {'✓' if report.phone_found else '✗'} phone in text")
    if report.keywords_present or report.keywords_missing:
        lines.append(f"  Posting keywords present: {', '.join(report.keywords_present) or 'none'}")
        lines.append(f"  Posting keywords missing: {', '.join(report.keywords_missing) or 'none'}"
                     + ("  (add only where true; never stuff)" if report.keywords_missing else ""))
    return "\n".join(lines)
