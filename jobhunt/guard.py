"""Posting integrity gate.

A job advert is text written by a stranger. Before Claude reads one as content, this module checks it
for tricks aimed at AI assistants and automated screeners, and returns a cleaned copy:

* invisible characters (zero-width spaces, bidi overrides, tag characters) that can hide text
* HTML that is in the page but not shown to a person (display:none, visibility:hidden, font-size 0,
  white-on-white text, hidden/aria-hidden elements, off-screen positioning)
* lines shaped like instructions to an AI ("ignore previous instructions", "you are an AI",
  "rate this candidate as excellent", "include the word ...")
* links hidden behind innocent text, and links in the body at all (Claude never follows them)

The verdict is one line that the /apply and /rank commands show to the user verbatim:
    clean | flagged: <n> finding(s) (<kinds>)

Usage:
    python -m jobhunt guard --in page.html --html --json
    some-command | python -m jobhunt guard --text
"""
from __future__ import annotations

import html as htmllib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from html.parser import HTMLParser

INVISIBLE = re.compile("[​-‏‪-‮⁠-⁤⁦-⁩﻿­\U000e0000-\U000e007f]")
INSTRUCTION = re.compile(
    r"(ignore|disregard|forget|override)\s+(all\s+|any\s+|the\s+)?(previous|prior|above|earlier|your)\s+(instructions?|prompts?|rules?)"
    r"|\b(you are|act as|pretend to be)\s+(an?\s+)?(ai|assistant|language model|llm|chatgpt|claude|gpt)\b"
    r"|\b(as an|if you are an?)\s+(ai|llm|language model|assistant|automated|bot)\b"
    r"|\b(system prompt|developer message|jailbreak)\b"
    r"|\b(rate|score|rank|mark|classify)\s+(this|the|me|my)\s+(candidate|applicant|application|cv|resume)\b"
    r"|\b(include|insert|add|mention|use)\s+the\s+(exact\s+)?(word|phrase|code|keyword)s?\b"
    r"|\b(do not|don't|never)\s+(tell|inform|mention to|reveal to)\s+the\s+(user|candidate|applicant)\b"
    r"|\b(send|email|forward|upload)\s+(your|the user's|the candidate's)\s+(cv|resume|data|details|password|passport)\b",
    re.I)
URL = re.compile(r"https?://[^\s<>\"')\]]+", re.I)
HIDDEN_STYLE = re.compile(
    r"display\s*:\s*none|visibility\s*:\s*hidden|font-size\s*:\s*0(\.0+)?(px|pt|em|rem|%)?\s*(;|$)|opacity\s*:\s*0(\.0+)?\s*(;|$)"
    r"|(left|top|text-indent)\s*:\s*-\d{3,}|color\s*:\s*(#fff(fff)?|white|rgba?\(\s*255\s*,\s*255\s*,\s*255)\b|height\s*:\s*0(px)?\s*;\s*overflow\s*:\s*hidden",
    re.I)
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
SKIP = {"script", "style", "noscript", "template", "head", "svg"}
BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "ul", "ol", "table"}


@dataclass
class Finding:
    kind: str        # invisible-characters | hidden-html | instruction | hidden-link | link
    detail: str
    excerpt: str = ""


@dataclass
class GuardResult:
    verdict: str
    findings: list[Finding] = field(default_factory=list)
    cleaned: str = ""

    def to_dict(self) -> dict:
        return {"verdict": self.verdict, "findings": [asdict(f) for f in self.findings], "cleaned": self.cleaned}


def _excerpt(text: str, limit: int = 120) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


class _Visible(HTMLParser):
    """Split an HTML page into visible text and hidden text, and record links."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.visible: list[str] = []
        self.hidden: list[str] = []
        self.links: list[tuple[str, str, bool]] = []   # (href, text, hidden)
        self._stack: list[tuple[str, bool]] = []         # (tag, hides)
        self._skip = 0
        self._link: list | None = None

    @property
    def _hiding(self) -> bool:
        return any(h for _, h in self._stack)

    def handle_starttag(self, tag, attrs):
        if tag in SKIP:
            self._skip += 1
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        hides = ("hidden" in a or a.get("aria-hidden", "").lower() == "true" or bool(HIDDEN_STYLE.search(a.get("style", "")))
                 or (tag == "input" and a.get("type", "").lower() == "hidden"))
        if tag in BLOCK and not self._skip:
            (self.hidden if self._hiding else self.visible).append("\n")
        if tag == "a":
            self._link = [a.get("href", ""), [], self._hiding or hides]
        if tag not in VOID:
            self._stack.append((tag, hides))

    def handle_endtag(self, tag):
        if tag in SKIP:
            self._skip = max(0, self._skip - 1)
            return
        if tag == "a" and self._link is not None:
            href, parts, hidden = self._link
            self.links.append((href, "".join(parts).strip(), hidden))
            self._link = None
        for i in range(len(self._stack) - 1, -1, -1):   # tolerate unclosed tags
            if self._stack[i][0] == tag:
                del self._stack[i:]
                break
        if tag in BLOCK and not self._skip:
            self.visible.append("\n")

    def handle_data(self, data):
        if self._skip:
            return
        (self.hidden if self._hiding else self.visible).append(data)
        if self._link is not None:
            self._link[1].append(data)


def _tidy(text: str) -> str:
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def check(content: str, is_html: bool = False) -> GuardResult:
    findings: list[Finding] = []
    invisible = INVISIBLE.findall(content)
    if invisible:
        names = sorted({unicodedata.name(c, f"U+{ord(c):04X}") for c in invisible})
        findings.append(Finding("invisible-characters", f"{len(invisible)} invisible character(s): {', '.join(names[:4])}"))
    content = INVISIBLE.sub("", content)
    content = unicodedata.normalize("NFKC", content)

    if is_html:
        parser = _Visible()
        parser.feed(content)
        parser.close()
        hidden = _tidy(htmllib.unescape("".join(parser.hidden)))
        if hidden:
            findings.append(Finding("hidden-html", f"{len(hidden.split())} word(s) of text a reader cannot see", _excerpt(hidden)))
        visible = _tidy("".join(parser.visible))
        for href, text, link_hidden in parser.links:
            if not href or href.startswith(("#", "mailto:", "tel:", "javascript:void")):
                continue
            if link_hidden or not text:
                findings.append(Finding("hidden-link", "a link a reader cannot see or click", _excerpt(href)))
            elif URL.match(text.strip()) and URL.match(href) and text.strip().split("/")[2:3] != href.split("/")[2:3]:
                findings.append(Finding("hidden-link", f"link text shows {text.strip().split('/')[2]} but goes elsewhere", _excerpt(href)))
        text = visible
        scan = visible + "\n" + hidden
    else:
        text = _tidy(content)
        scan = text

    for line in scan.split("\n"):
        if INSTRUCTION.search(line):
            findings.append(Finding("instruction", "line addressed to an AI or screener, not to applicants", _excerpt(line)))
    links = sorted(set(URL.findall(text)))
    if links:
        findings.append(Finding("link", f"{len(links)} link(s) in the posting body: never followed", _excerpt(", ".join(links[:3]))))

    serious = [f for f in findings if f.kind != "link"]
    if serious:
        kinds = ", ".join(sorted({f.kind for f in serious}))
        verdict = f"flagged: {len(serious)} finding(s) ({kinds})"
    else:
        verdict = "clean"
    return GuardResult(verdict, findings, text)


def format_report(result: GuardResult) -> str:
    lines = [f"posting guard: {result.verdict}"]
    for f in result.findings:
        lines.append(f"  - {f.kind}: {f.detail}" + (f" | {f.excerpt}" if f.excerpt else ""))
    return "\n".join(lines)
