"""Right-to-work check: find adverts that exclude the candidate's immigration permission.

Many Irish adverts are open to graduates but quietly rule out time-limited permissions, for example
"must have the right to work for an unlimited period (Stamp 4)" or "this excludes Stamp 1G". Reading
that only after writing a tailored CV wastes an evening, so the check runs before scoring.

`restrictions(text)` lists what the advert says about the right to work, with the sentence it came from.
`blocker(text, permit)` returns the first restriction that rules out someone holding `permit`
(for example "stamp1g", "stamp4", "eu", "needs_sponsorship"), or None.

Idea adapted from the sponsorship check in career-ops (MIT, https://github.com/career-ops-hq/career-ops),
rewritten for Irish immigration stamps.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_S = r"[^.\n]{0,90}?"   # stay inside one sentence

RULES: list[tuple[str, re.Pattern]] = [
    ("excludes_stamp1g", re.compile(
        rf"(?:exclud\w*|not (?:eligible|accepted|suitable|consider\w*)|ineligible|cannot (?:accept|consider)|unable to (?:accept|consider)|"
        rf"don'?t apply|do not apply|no){_S}stamp\s*1\s*g|stamp\s*1\s*g{_S}(?:not (?:eligible|accepted|suitable)|ineligible|excluded|will not be considered)",
        re.I)),
    ("stamp4_only", re.compile(
        rf"stamp\s*4\s*(?:only|holders? only)|(?:must|need to|required to|should) (?:hold|have|possess){_S}stamp\s*4\b|"
        rf"(?:only|exclusively) (?:open|available) to{_S}stamp\s*4", re.I)),
    ("eu_only", re.compile(
        rf"\b(?:eu|eea|european union)(?:/eea)? (?:citizens?|nationals?|passport holders?) only|"
        rf"(?:must|need to|required to) (?:be|hold){_S}\b(?:an? )?(?:eu|eea|irish)(?:/eea)? (?:citizen|national|passport)", re.I)),
    ("unlimited_right_to_work", re.compile(
        rf"right to (?:live and )?work{_S}(?:unlimited|indefinite|permanent(?:ly)?|without (?:any )?(?:time )?(?:limit|restriction))", re.I)),
    ("no_sponsorship", re.compile(
        rf"(?:unable|not able|cannot|can'?t|do not|don'?t|does not|doesn'?t|will not|won'?t|not in a position|are not)"
        rf"{_S}(?:offer|provide|support|sponsor)\w*{_S}(?:visa|sponsor\w*|work permit|employment permit)|"
        rf"\bno (?:visa |employment permit )?sponsorship\b|sponsorship (?:is )?not (?:available|offered|provided)", re.I)),
    ("security_clearance", re.compile(r"\b(?:security|government|sc|dv) clearance\b", re.I)),
]

# Which restrictions rule out which permission. "needs_sponsorship" is anyone who needs the employer to
# apply for a work permit. Security clearance is only flagged: eligibility depends on the scheme.
BLOCKS = {
    "stamp1g": {"excludes_stamp1g", "stamp4_only", "eu_only", "unlimited_right_to_work"},
    "stamp2": {"excludes_stamp1g", "stamp4_only", "eu_only", "unlimited_right_to_work"},
    "needs_sponsorship": {"excludes_stamp1g", "stamp4_only", "eu_only", "unlimited_right_to_work", "no_sponsorship"},
    "stamp4": {"eu_only"},
    "eu": set(),
}

LABELS = {
    "excludes_stamp1g": "excludes Stamp 1G",
    "stamp4_only": "Stamp 4 holders only",
    "eu_only": "EU/EEA citizens only",
    "unlimited_right_to_work": "needs an unlimited right to work",
    "no_sponsorship": "no visa sponsorship",
    "security_clearance": "security clearance required",
}


@dataclass
class Restriction:
    kind: str
    evidence: str

    @property
    def label(self) -> str:
        return LABELS.get(self.kind, self.kind)


def _sentence(text: str, start: int, end: int) -> str:
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right_dot, right_nl = text.find(".", end), text.find("\n", end)
    right = min(x for x in (right_dot, right_nl, len(text)) if x != -1)
    return " ".join(text[left:right + 1].split())[:220]


def restrictions(text: str) -> list[Restriction]:
    found, seen = [], set()
    for kind, pattern in RULES:
        match = pattern.search(text or "")
        if match and kind not in seen:
            seen.add(kind)
            found.append(Restriction(kind, _sentence(text, match.start(), match.end())))
    return found


def normalise_permit(permit: str | None) -> str:
    p = re.sub(r"[^a-z0-9]", "", (permit or "").lower())
    if p.startswith("stamp1g") or p == "1g":
        return "stamp1g"
    if p.startswith("stamp4"):
        return "stamp4"
    if p.startswith("stamp2"):
        return "stamp2"
    if p in {"eu", "eea", "irish", "eucitizen", "eeacitizen", "citizen"}:
        return "eu"
    if "sponsor" in p or "permit" in p:
        return "needs_sponsorship"
    return p


def blocker(text: str, permit: str | None) -> Restriction | None:
    blocked = BLOCKS.get(normalise_permit(permit), set())
    return next((r for r in restrictions(text) if r.kind in blocked), None)
