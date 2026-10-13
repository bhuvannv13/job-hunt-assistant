"""Is this a genuine job from a real employer?

Each job gets a trust label and the evidence behind it:

* Verified employer   - the advert is on the company's own applicant-tracking board and the company's
                        own website links to that board (or the advert lives on the company's domain).
* Official job board  - the advert is on a real applicant-tracking board for that company name, but the
                        link from the company's website could not be confirmed automatically.
* Unverified          - found through an aggregator; check the employer yourself before applying.
* Caution             - the advert contains scam warning signs (fees, chat-app-only contact, requests for
                        bank or ID details up front, and so on). These jobs are hidden by default.

This is a screening aid, not a guarantee. Never pay to apply, and never send bank, PPS or passport
details before a signed offer.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

from .models import Job

ATS_HOSTS = ("greenhouse.io", "lever.co", "ashbyhq.com", "workable.com", "smartrecruiters.com",
             "myworkdayjobs.com", "icims.com", "successfactors", "taleo.net", "teamtailor.com", "personio")

RED_FLAGS = [
    (r"\b(?:you|candidates?|applicants?|trainees?)\b[^.\n]{0,60}\b(?:registration|application|training|onboarding|starter[- ]kit|equipment|placement)\s+fee",
     "asks for a fee"),
    (r"\b(?:registration|application|training|onboarding|starter[- ]kit|placement)\s+fee\s+(?:of|is|costs?)\s*(?:€|\$|£)", "asks for a fee"),
    (r"\byou\s+(?:will\s+)?(?:need|have|are required)\s+to\s+(?:pay|purchase|buy)\b", "asks you to pay"),
    (r"\bpay\s+(?:a|an|the)\s+(?:small\s+|one-off\s+|refundable\s+)?(?:registration|application|training|onboarding|placement|processing)\s+(?:fee|deposit)",
     "asks for a fee"),
    (r"\b(?:pay|paid|send|transfer|deposit|purchase|buy)\b[^.\n]{0,40}\b(?:via|by|through|using|in|with)\s+"
     r"(?:western union|moneygram|gift cards?|bitcoin|crypto(?:currency)?|usdt)\b", "unusual payment method"),
    (r"\b(?:contact|message|text|reach|apply|send (?:your )?(?:cv|resume))\b[^.\n]{0,40}\b(?:on|via|through|by|using)\s+(?:whatsapp|telegram|signal)\b",
     "contact by chat app"),
    (r"\b(?:bank (?:account|details)|iban|sort code|pps(?:n| number)?|passport (?:number|copy)|credit card)\b"
     r"[^.\n]{0,60}\b(?:send|provide|share|submit|required|needed)", "asks for bank or ID details"),
    (r"\b(?:send|provide|share|submit)\b[^.\n]{0,60}\b(?:bank (?:account|details)|iban|pps(?:n| number)?|passport (?:number|copy)|credit card)\b",
     "asks for bank or ID details"),
    (r"\b(?:earn|make)\s+(?:€|\$|£)?\s?\d{3,}[\d,]*\s*(?:per|a|/)\s*(?:day|week)\b", "promises big daily or weekly pay"),
    (r"\bno (?:experience|interview|qualifications?) (?:needed|required|necessary)\b.*\b(?:earn|income|cash)\b", "too good to be true"),
    (r"\b(?:reshipping|re-shipping|package forwarding|parcel forwarding|money transfer agent|payment processing agent)\b",
     "known scam job type"),
    (r"\b(?:apply|send|email|contact|cv|resume)\b[^.\n]{0,60}[\w.+-]+@(?:gmail|yahoo|hotmail|outlook|live|aol|proton(?:mail)?|icloud)\.\w+",
     "personal email address for applications"),
]
_FLAGS = [
    (r"(?:registration|application|training|onboarding|starter[- ]kit|equipment)\s+fee", "asks for a fee"),
    (r"pay (?:a|the|for)\s+(?:fee|deposit|training|equipment)", "asks you to pay"),
    (r"\b(?:western union|moneygram|gift cards?|bitcoin|crypto(?:currency)? payment|usdt)\b", "unusual payment method"),
    (r"\b(?:whatsapp|telegram|signal app|google hangouts)\b", "contact by chat app"),
    (r"\b(?:bank (?:account|details)|iban|sort code|pps(?:n| number)?|passport (?:number|copy)|credit card)\b"
     r"[^.\n]{0,60}\b(?:send|provide|share|submit|required|needed)", "asks for bank or ID details"),
    (r"\b(?:send|provide|share|submit)\b[^.\n]{0,60}\b(?:bank (?:account|details)|iban|pps(?:n| number)?|passport (?:number|copy)|credit card)\b",
     "asks for bank or ID details"),
    (r"\b(?:earn|make)\s+(?:€|\$|£)?\s?\d{3,}[\d,]*\s*(?:per|a|/)\s*(?:day|week)\b", "promises big daily or weekly pay"),
    (r"\bno (?:experience|interview|qualifications?) (?:needed|required|necessary)\b.*\b(?:earn|income|cash)\b", "too good to be true"),
    (r"\b(?:reshipping|re-shipping|package forwarding|parcel forwarding|money transfer agent|payment processing agent)\b",
     "known scam job type"),
    (r"[\w.+-]+@(?:gmail|yahoo|hotmail|outlook|live|aol|proton(?:mail)?|icloud)\.\w+", "personal email address for applications"),
]
_FLAGS = [(re.compile(p, re.I | re.S), label) for p, label in RED_FLAGS]


def domain(url: str) -> str:
    host = (urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def red_flags(job: Job) -> list[str]:
    text = f"{job.title}\n{job.description}"
    found = []
    for pattern, label in _FLAGS:
        if pattern.search(text) and label not in found:
            found.append(label)
    return found


def assess(job: Job, company_info: dict | None = None) -> tuple[str, list[str]]:
    """Return (label, evidence) for one job. company_info comes from config/companies.yaml and the
    verification step: {"website": "stripe.com", "career_site_links_board": True}."""
    evidence = []
    flags = red_flags(job)
    host = domain(job.url)
    website = domain("https://" + (company_info or {}).get("website", "").replace("https://", "").replace("http://", ""))
    on_ats = any(h in host for h in ATS_HOSTS) or job.source in ("greenhouse", "lever", "ashby", "workable", "smartrecruiters")
    # An advert on a known employer's own hiring board needs two independent warning signs before it is
    # treated as suspicious (a payments company may legitimately mention crypto); anything else needs one.
    if flags and (len(flags) >= 2 or not (on_ats and company_info)):
        return "Caution", [f"Warning sign: {f}" for f in flags]
    evidence += [f"Mentions something that can be a warning sign ({f}); read the advert" for f in flags]
    on_company_domain = bool(website) and (host == website or host.endswith("." + website))
    if on_company_domain:
        evidence.append(f"Advert is hosted on the company's own website ({host})")
    if on_ats:
        evidence.append(f"Published on the company's {job.source.title()} job board")
    if company_info and company_info.get("career_site_links_board"):
        evidence.append(f"{website or 'The company website'} links to this job board")
    if job.description and len(job.description) < 200:
        evidence.append("Very short advert: check details on the company site")
    if on_company_domain or (on_ats and company_info and company_info.get("career_site_links_board")):
        return "Verified employer", evidence
    if on_ats:
        return "Official job board", evidence
    evidence.append(f"Found through {job.source.title()}; confirm the employer on its own website before applying")
    return "Unverified", evidence


def career_site_links_board(page_html: str, ats: str, token: str) -> bool:
    """True if a company careers page references its job board (link, embed or API call)."""
    page = (page_html or "").lower()
    token = token.lower()
    hints = {
        "greenhouse": [f"greenhouse.io/{token}", f"boards/{token}", f"for={token}", "greenhouse.io/embed"],
        "lever": [f"jobs.lever.co/{token}", f"postings/{token}"],
        "ashby": [f"jobs.ashbyhq.com/{token}", f"job-board/{token}", "ashbyhq.com"],
        "workable": [f"apply.workable.com/{token}", f"{token}.workable.com", "workable.com/api"],
        "smartrecruiters": [f"smartrecruiters.com/{token}", f"careers.smartrecruiters.com/{token}"],
    }.get(ats, [])
    return any(h in page for h in hints)
