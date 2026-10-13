"""Filter and rank jobs against a CV.

The score (0-100) combines four signals, each explained in Job.reasons:

* text similarity between the CV and the job (TF-IDF cosine, 45%)
* share of the job's recognised skills that the CV also shows (30%)
* whether the role is in a category the user wants (15%)
* whether the level suits a graduate or junior candidate (10%)

Jobs outside the user's locations, above the experience limit, or needing a language the
user does not speak are filtered out before scoring, and the reason is recorded.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import Job
from .skills import find_skills

CATEGORIES = {
    "Data analyst": [r"data analyst", r"business intelligence", r"\bbi\b", r"analytics", r"insights? analyst", r"reporting analyst",
                     r"data analytics", r"product analyst", r"marketing analyst", r"commercial analyst", r"financial analyst"],
    "Data engineer": [r"data engineer", r"analytics engineer", r"etl", r"data platform", r"data integration", r"big data"],
    "AI / ML engineer": [r"machine learning", r"\bml\b", r"\bai\b", r"artificial intelligence", r"data scientist", r"data science",
                         r"applied scientist", r"computer vision", r"nlp", r"deep learning", r"research engineer", r"llm"],
    "Software engineer": [r"software engineer", r"software developer", r"developer", r"backend", r"back-end", r"python engineer",
                          r"full[- ]stack"],
    "Trust and safety": [r"trust (?:and|&) safety", r"content moderat", r"policy (?:analyst|specialist|associate)", r"integrity",
                         r"risk analyst", r"fraud", r"investigat", r"abuse", r"compliance (?:operations|analyst|specialist)"],
    "Business / operations analyst": [r"business analyst", r"operations analyst", r"process analyst", r"systems analyst",
                                      r"research analyst", r"quantitative analyst"],
}
ENTRY = re.compile(r"\b(graduate|grad|entry[- ]level|junior|jr\.?|associate|trainee|new grad|early careers?|apprentice|"
                   r"level 1|l1|i)\b(?!\s*\+)", re.I)
INTERN = re.compile(r"\b(intern|internship|placement|co-?op|summer)\b", re.I)
SENIOR = re.compile(r"\b(senior|sr\.?|staff|principal|lead|manager|director|head|vp|vice president|architect|chief|"
                    r"expert|iii|iv|level 3|l3|l4|l5)\b", re.I)
YEARS = re.compile(r"(\d{1,2})\s*(?:\+|plus)?\s*(?:-|to|–)?\s*(?:\d{1,2})?\s*\+?\s*years?(?:['’]s)?\s*(?:of\s+)?"
                   r"(?:relevant\s+|professional\s+|proven\s+|hands-on\s+|industry\s+|work\s+)*(?:experience|exp)", re.I)
LANGUAGES = ["German", "French", "Spanish", "Italian", "Dutch", "Portuguese", "Polish", "Swedish", "Danish", "Norwegian",
             "Finnish", "Japanese", "Korean", "Mandarin", "Chinese", "Cantonese", "Arabic", "Hebrew", "Turkish", "Russian",
             "Czech", "Hungarian", "Romanian", "Greek", "Thai", "Vietnamese", "Indonesian", "Hindi", "Tamil", "Irish"]
LANG_REQ = re.compile(r"(?:fluen\w*|native|proficien\w*|business[- ]level|written and spoken|c1|c2)[^.\n]{0,40}?\b(" +
                      "|".join(LANGUAGES) + r")\b|\b(" + "|".join(LANGUAGES) + r")\b[^.\n]{0,25}?(?:speaker|fluency|is required|required|essential)",
                      re.I)


@dataclass
class Preferences:
    locations: list[str] = field(default_factory=lambda: ["Ireland", "Dublin", "Cork", "Galway", "Limerick", "Waterford",
                                                          "Athlone", "Shannon", "Kildare", "Remote"])
    remote_regions: list[str] = field(default_factory=lambda: ["Ireland", "EMEA", "Europe", "EU", "Worldwide", "Anywhere", "Global"])
    categories: list[str] = field(default_factory=lambda: list(CATEGORIES))
    max_years: int = 2
    include_internships: bool = False
    languages: list[str] = field(default_factory=lambda: ["English"])
    min_score: float = 35.0
    exclude_title_words: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict | None) -> "Preferences":
        data = data or {}
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})


NON_TECH = re.compile(r"\b(account executive|account manager|sales|marketing|recruit\w*|talent|business development|customer success|"
                      r"customer support|support specialist|candidate experience|legal|counsel|paralegal|finance|financial planning|accountant|accounting|payroll|tax|"
                      r"designer|design|product manager|program manager|project manager|people partner|human resources|hr\b|office|"
                      r"facilities|executive assistant|communications|partnerships?|solutions? engineer|sales engineer|customer engineer)\b", re.I)
TECH_TITLE = re.compile(r"\b(engineer|analyst|scientist|developer|associate|specialist|graduate|intern|researcher|consultant|"
                        r"programmer|technician|moderator|reviewer|investigator)\b", re.I)


def category_of(job: Job) -> str:
    title = job.title.lower()
    if NON_TECH.search(title) and not re.search(r"\b(data|analytics|machine learning|ml|ai|software|trust)\b.*\b(engineer|analyst|scientist)", title):
        return "Other"
    best_title, longest = "", 0      # the most specific phrase wins: "analytics engineer" beats "analytics"
    for name, patterns in CATEGORIES.items():
        for p in patterns:
            m = re.search(p, title)
            if m and len(m.group(0)) > longest:
                best_title, longest = name, len(m.group(0))
    if best_title:
        return best_title
    if not TECH_TITLE.search(title):
        return "Other"
    head = job.description[:1500].lower()
    best, hits = "", 0
    for name, patterns in CATEGORIES.items():
        count = sum(len(re.findall(p, head)) for p in patterns)
        if count > hits:
            best, hits = name, count
    if hits >= 4:
        return best
    if re.search(r"\b(engineer|developer|programmer)\b", title):
        return "Software engineer"
    if re.search(r"\banalyst\b", title):
        return "Business / operations analyst"
    return "Other"


def required_years(text: str) -> int | None:
    values = [int(m.group(1)) for m in YEARS.finditer(text or "") if int(m.group(1)) <= 20]
    return min(values) if values else None


def level_of(job: Job) -> str:
    title = job.title
    if INTERN.search(title):
        return "Internship"
    if SENIOR.search(title):
        return "Senior"
    if ENTRY.search(title) or re.search(r"graduate|entry level|early career", job.description[:600], re.I):
        return "Graduate / entry"
    years = required_years(job.description)
    if years is not None and years >= 3:
        return "Mid / senior"
    return "Not stated"


ELSEWHERE = re.compile(r"\b(us|usa|u\.s\.|united states|canada|mexico|brazil|latam|americas|apac|india|australia|japan|singapore|"
                       r"united kingdom only|uk only|mid west|midwest|northeast|southeast|east coast|west coast|"
                       r"new york|california|texas|chicago|seattle|san francisco|toronto)\b", re.I)


def location_ok(job: Job, prefs: Preferences) -> bool:
    text = f"{job.location} {job.title}".lower()
    places = [p.lower() for p in prefs.locations if p.lower() != "remote"]
    if any(re.search(rf"\b{re.escape(p)}\b", text) for p in places) or re.search(r"\b(ie|irl)\b", job.location.lower()):
        return True
    if "remote" in [p.lower() for p in prefs.locations] and (job.remote or "remote" in text):
        if ELSEWHERE.search(f"{job.location} {job.title}"):
            return False
        regions = "|".join(re.escape(r.lower()) for r in prefs.remote_regions)
        if re.search(rf"\b({regions})\b", job.location.lower()):
            return True
        # the advert itself must say the remote role covers one of the regions
        return bool(re.search(rf"remote[^.\n]{{0,40}}\b({regions})\b|\b({regions})\b[^.\n]{{0,40}}remote",
                              job.description[:4000].lower()))
    return False


def language_barrier(job: Job, prefs: Preferences) -> str | None:
    spoken = {l.lower() for l in prefs.languages}
    for match in LANG_REQ.finditer(job.description):
        language = (match.group(1) or match.group(2) or "").title()
        if language and language.lower() not in spoken:
            return language
    for language in LANGUAGES:   # e.g. "German Speaking Content Moderator"
        if language.lower() not in spoken and re.search(rf"\b{language}\b[- ](?:speaking|speaker)", job.title, re.I):
            return language
    return None


def screen(job: Job, prefs: Preferences) -> str | None:
    """Return a reason to drop the job, or None if it passes."""
    if not location_ok(job, prefs):
        return "location"
    job.category, job.level = category_of(job), level_of(job)
    if job.category not in prefs.categories:
        return "category"
    if job.level in ("Senior", "Mid / senior"):
        return "seniority"
    if job.level == "Internship" and not prefs.include_internships:
        return "internship"
    years = required_years(job.description)
    if years is not None and years > prefs.max_years:
        return "experience"
    if any(w.lower() in job.title.lower() for w in prefs.exclude_title_words):
        return "excluded word"
    language = language_barrier(job, prefs)
    if language:
        return f"needs {language}"
    return None


def score_jobs(jobs: list[Job], cv_text: str, cv_skills: list[str], prefs: Preferences) -> list[Job]:
    if not jobs:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    docs = [f"{j.title} {j.title} {j.description}" for j in jobs]
    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, max_df=0.9, sublinear_tf=True)
    matrix = vectorizer.fit_transform(docs + [cv_text])
    sims = cosine_similarity(matrix[-1], matrix[:-1]).ravel()
    top = max(sims.max(), 1e-9)
    have = set(cv_skills)
    for job, sim in zip(jobs, sims):
        wanted = find_skills(f"{job.title}\n{job.description}")
        job.matched_skills = [s for s in wanted if s in have]
        job.missing_skills = [s for s in wanted if s not in have]
        coverage = len(job.matched_skills) / len(wanted) if wanted else 0.5
        text_part = min(sim / top, 1.0) * 0.6 + min(sim / 0.25, 1.0) * 0.4   # relative and absolute similarity
        level_part = {"Graduate / entry": 1.0, "Not stated": 0.6, "Internship": 0.5}.get(job.level, 0.0)
        job.score = round(100 * (0.45 * text_part + 0.30 * coverage + 0.15 * 1.0 + 0.10 * level_part), 1)
        job.reasons = [f"{len(job.matched_skills)} of {len(wanted)} skills in the advert appear in your CV" if wanted
                       else "No specific tools listed in the advert",
                       f"Role type: {job.category}", f"Level: {job.level}"]
    return sorted(jobs, key=lambda j: j.score, reverse=True)


def rank(jobs: list[Job], cv_text: str, cv_skills: list[str], prefs: Preferences) -> tuple[list[Job], dict[str, int]]:
    kept, dropped = [], {}
    seen = set()
    for job in jobs:
        key = (job.company.lower(), re.sub(r"\W+", " ", job.title.lower()).strip(), job.location.lower()[:30])
        if key in seen:
            continue
        seen.add(key)
        reason = screen(job, prefs)
        if reason:
            bucket = reason if not reason.startswith("needs ") else "language"
            dropped[bucket] = dropped.get(bucket, 0) + 1
        else:
            kept.append(job)
    ranked = [j for j in score_jobs(kept, cv_text, cv_skills, prefs) if j.score >= prefs.min_score]
    dropped["below minimum score"] = len(kept) - len(ranked)
    return ranked, dropped
