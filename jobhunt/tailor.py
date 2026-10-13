"""Make a CV and cover letter tailored to one job.

Tailoring never invents anything. It only chooses and orders material that is already in the
candidate's profile or CV:

* picks the profile summary written for that type of role
* puts the most relevant projects and experience points first and drops the least relevant
* lists the advert's skills that the candidate really has at the front of the skills section
* writes a short cover letter from the same facts

Two inputs are supported:

* a structured profile (YAML, see examples/profile.example.yaml): best results
* a plain CV file: the original text is kept, a "Key skills for this role" line is added and a
  report lists which advert keywords are missing so the candidate can decide what to add.
"""
from __future__ import annotations

import re
from pathlib import Path

from .models import Job
from .skills import find_skills, skill_pattern

TEAL, INK, GREY = "0B6E75", "1D2733", "566273"


def load_profile(path: str | Path) -> dict:
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def profile_text(profile: dict) -> str:
    """Flatten a profile into plain text (used for matching)."""
    parts = [profile.get("person", {}).get("title", "")]
    parts += list((profile.get("summaries") or {}).values())
    for group in profile.get("skills", []):
        parts.append(f"{group.get('group', '')}: {', '.join(group.get('items', []))}")
    for item in profile.get("experience", []) + profile.get("projects", []):
        parts.append(" ".join([item.get("role", item.get("name", "")), item.get("tags", "")] + item.get("bullets", [])))
    for edu in profile.get("education", []):
        parts.append(f"{edu.get('degree', '')} {edu.get('school', '')}")
    return "\n".join(p for p in parts if p)


def _relevance(job_text: str, candidates: list[str]) -> list[float]:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    if not candidates:
        return []
    matrix = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True).fit_transform([job_text] + candidates)
    scores = cosine_similarity(matrix[0], matrix[1:]).ravel()
    advert_skills = set(find_skills(job_text))
    return [float(s) + 0.05 * len(advert_skills & set(find_skills(c))) for s, c in zip(scores, candidates)]


def tailor_profile(profile: dict, job: Job, max_projects: int = 4, max_bullets: int = 2) -> dict:
    """Return a new profile dict ordered and trimmed for this job."""
    job_text = f"{job.title}\n{job.title}\n{job.description}"
    advert_skills = find_skills(job_text)
    summaries = profile.get("summaries") or {}
    summary = summaries.get(job.category) or summaries.get("default") or next(iter(summaries.values()), "")

    experience = []
    for item in profile.get("experience", []):
        bullets = item.get("bullets", [])
        scores = _relevance(job_text, bullets)
        keep = sorted(range(len(bullets)), key=lambda i: -scores[i])[:max_bullets]
        experience.append({**item, "bullets": [bullets[i] for i in sorted(keep)]})

    projects = profile.get("projects", [])
    proj_texts = [" ".join([p.get("name", ""), p.get("tags", "")] + p.get("bullets", [])) for p in projects]
    proj_scores = _relevance(job_text, proj_texts)
    order = sorted(range(len(projects)), key=lambda i: -proj_scores[i])
    chosen = []
    for i in order[:max_projects]:
        p = projects[i]
        b_scores = _relevance(job_text, p.get("bullets", []))
        keep = sorted(range(len(p.get("bullets", []))), key=lambda k: -b_scores[k])[:max_bullets]
        chosen.append({**p, "bullets": [p["bullets"][k] for k in sorted(keep)]})
    others = [projects[i] for i in order[max_projects:max_projects + 4]]

    have = [s for s in advert_skills if s in find_skills(profile_text(profile))]
    skills = []
    for group in profile.get("skills", []):
        items = group.get("items", [])
        def hit(item):
            return any(skill_pattern(s) and skill_pattern(s).search(item) for s in advert_skills)
        ordered = [i for i in items if hit(i)] + [i for i in items if not hit(i)]
        skills.append({"group": group.get("group"), "items": ordered, "hits": sum(hit(i) for i in items)})
    skills.sort(key=lambda g: -g["hits"])

    return {**profile, "summary": summary, "experience": experience, "projects": chosen, "other_projects": others,
            "skills": skills, "key_skills": have, "target_category": job.category,
            "target": {"title": job.title, "company": job.company}}


def cover_letter(profile: dict, job: Job, tailored: dict | None = None) -> str:
    tailored = tailored or tailor_profile(profile, job)
    person = profile.get("person", {})
    projects = tailored.get("projects", [])[:2]
    skills = tailored.get("key_skills", [])[:5]
    lines = ["Dear Hiring Team,", "",
             f"I am applying for the {job.title} role at {job.company}. {profile.get('cover_letter', {}).get('intro', tailored.get('summary', ''))}".strip(),
             ""]
    if projects:
        lines.append("Two pieces of my work are particularly relevant:")
        for p in projects:
            lines.append(f"• {p['name']}: {p['bullets'][0] if p.get('bullets') else p.get('tags', '')}")
        lines.append("")
    if skills:
        listed = ", ".join(skills[:-1]) + (f" and {skills[-1]}" if len(skills) > 1 else skills[0])
        lines.append(f"The advert mentions {listed}; you will find each of these in my CV.")
        lines.append("")
    closing = profile.get("cover_letter", {}).get("closing", "")
    if closing:
        lines += [closing, ""]
    links = "  ".join(l.get("url", "") for l in person.get("links", [])[:2])
    lines += ["Thank you for your time and consideration.", "", "Kind regards,", person.get("name", ""),
              " · ".join(x for x in [person.get("phone"), person.get("email")] if x), links]
    return "\n".join(lines).strip() + "\n"


# ---------------------------------------------------------------- Word output

def _docx_helpers(doc):
    from docx.enum.text import WD_TAB_ALIGNMENT
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Pt, RGBColor

    sec = doc.sections[0]
    width = sec.page_width - sec.left_margin - sec.right_margin
    rgb = {k: RGBColor.from_string(v) for k, v in (("teal", TEAL), ("ink", INK), ("grey", GREY))}

    def para(before=0, after=0):
        p = doc.add_paragraph()
        p.paragraph_format.space_before, p.paragraph_format.space_after = Pt(before), Pt(after)
        return p

    def run(p, text, bold=False, italic=False, size=None, color=None):
        r = p.add_run(text)
        r.bold, r.italic = bold, italic
        if size:
            r.font.size = Pt(size)
        if color:
            r.font.color.rgb = rgb[color]
        return r

    def link(p, text, url, size=None, bold=False):
        rel = p.part.relate_to(url, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink", is_external=True)
        h = OxmlElement("w:hyperlink"); h.set(qn("r:id"), rel)
        r = OxmlElement("w:r"); pr = OxmlElement("w:rPr")
        c = OxmlElement("w:color"); c.set(qn("w:val"), TEAL); pr.append(c)
        if bold:
            pr.append(OxmlElement("w:b"))
        if size:
            sz = OxmlElement("w:sz"); sz.set(qn("w:val"), str(int(size * 2))); pr.append(sz)
        r.append(pr); t = OxmlElement("w:t"); t.text = text; t.set(qn("xml:space"), "preserve"); r.append(t)
        h.append(r); p._p.append(h)

    def rule(p, color=TEAL, size=6):
        pPr = p._p.get_or_add_pPr(); border = OxmlElement("w:pBdr"); bottom = OxmlElement("w:bottom")
        for k, v in (("val", "single"), ("sz", str(size)), ("space", "1"), ("color", color)):
            bottom.set(qn("w:" + k), v)
        border.append(bottom); pPr.append(border)

    def heading(text):
        p = para(9, 3); run(p, text.upper(), bold=True, size=10, color="teal"); rule(p, "C9D3DA", 4)
        p.paragraph_format.keep_with_next = True

    def bullet(text, before=None):
        p = doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_after = Pt(1)
        if before:
            before(p)
        run(p, text)
        return p

    def row(left, right, sub_left="", sub_right="", links=None):
        p = para(4); p.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
        p.paragraph_format.keep_with_next = True
        run(p, left, bold=True); run(p, "\t" + (right or ""), bold=True, size=9, color="grey")
        if sub_left or sub_right or links:
            q = para(); q.paragraph_format.tab_stops.add_tab_stop(width, WD_TAB_ALIGNMENT.RIGHT)
            q.paragraph_format.keep_with_next = True
            run(q, sub_left or "", italic=True, size=9.5, color="grey"); run(q, "\t")
            for i, item in enumerate(links or []):
                if i:
                    run(q, "  ·  ", size=9, color="grey")
                link(q, item.get("label", "Link"), item.get("url", ""), size=9, bold=True)
            if not links:
                run(q, sub_right or "", size=9, color="grey")

    return para, run, link, rule, heading, bullet, row


def _new_doc():
    from docx import Document
    from docx.oxml.ns import qn
    from docx.shared import Mm, Pt, RGBColor
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Mm(210), Mm(297)
    sec.left_margin = sec.right_margin = Mm(16)
    sec.top_margin, sec.bottom_margin = Mm(14), Mm(13)
    normal = doc.styles["Normal"]
    normal.font.name, normal.font.size, normal.font.color.rgb = "Calibri", Pt(10), RGBColor.from_string(INK)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    normal.paragraph_format.space_after, normal.paragraph_format.line_spacing = Pt(0), 1.08
    return doc


def _header(doc, person, title, para, run, link, rule):
    p = para(); run(p, person.get("name", ""), bold=True, size=22)
    if title:
        p = para(0, 2); run(p, title, bold=True, size=11.5, color="teal")
    p = para(0, 1)
    bits = [person.get("location"), person.get("phone")]
    run(p, "  ·  ".join(b for b in bits if b) + ("  ·  " if any(bits) else ""), size=9.5, color="grey")
    if person.get("email"):
        link(p, person["email"], "mailto:" + person["email"], size=9.5)
    for item in person.get("links", []):
        run(p, "  ·  ", size=9.5, color="grey")
        link(p, item.get("label") or item.get("url", ""), item.get("url", ""), size=9.5)
    p = para(0, 2)
    if person.get("status"):
        run(p, person["status"], size=9, color="grey")
    rule(p, TEAL, 12)


def write_tailored_docx(tailored: dict, path: str | Path) -> Path:
    doc = _new_doc()
    para, run, link, rule, heading, bullet, row = _docx_helpers(doc)
    person = tailored.get("person", {})
    title = tailored.get("titles", {}).get(tailored.get("target_category", ""), "") or person.get("title", "")
    _header(doc, person, title, para, run, link, rule)

    heading("Profile"); run(para(), tailored.get("summary", ""))
    if tailored.get("key_skills"):
        p = para(3); run(p, "Key skills for this role: ", bold=True); run(p, ", ".join(tailored["key_skills"]))
    heading("Education")
    for e in tailored.get("education", []):
        row(e.get("degree", ""), e.get("when", ""), e.get("school", ""), e.get("grade", ""))
    heading("Technical skills")
    for g in tailored.get("skills", []):
        p = para(0, 1); run(p, f"{g['group']}: ", bold=True); run(p, ", ".join(g["items"]))
    heading("Experience")
    for e in tailored.get("experience", []):
        row(e.get("role", ""), e.get("when", ""), e.get("org", ""), e.get("where", ""))
        for b in e.get("bullets", []):
            bullet(b)
    heading("Projects")
    for p_ in tailored.get("projects", []):
        row(p_.get("name", ""), str(p_.get("year", "")), p_.get("tags", ""), links=p_.get("links"))
        for b in p_.get("bullets", []):
            bullet(b)
    if tailored.get("other_projects"):
        heading("Other projects")
        for p_ in tailored["other_projects"]:
            url = (p_.get("links") or [{}])[0].get("url")
            def name_part(par, p_=p_, url=url):
                if url:
                    link(par, p_["name"], url, bold=True)
                else:
                    run(par, p_["name"], bold=True)
            bullet(f" ({p_.get('tags', '')}): {(p_.get('bullets') or [''])[0]}", before=name_part)
    if tailored.get("awards"):
        heading("Awards and activities")
        for a in tailored["awards"]:
            bullet(a)
    doc.core_properties.author = person.get("name", "")
    target = tailored.get("target", {})
    doc.core_properties.title = f"{person.get('name', '')} – CV for {target.get('title', '')} at {target.get('company', '')}"
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


def write_text_docx(text: str, path: str | Path, title: str = "") -> Path:
    doc = _new_doc()
    para, run, *_ = _docx_helpers(doc)
    if title:
        run(para(0, 6), title, bold=True, size=13, color="teal")
    for line in text.split("\n"):
        run(para(0, 3), line)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


def tailor_plain_cv(cv, job: Job) -> tuple[str, dict]:
    """For an uploaded CV without a profile: add a key-skills line and report the gaps."""
    advert = find_skills(f"{job.title}\n{job.description}")
    have = [s for s in advert if s in cv.skills]
    missing = [s for s in advert if s not in cv.skills]
    lines = cv.text.split("\n")
    insert_at = next((i for i, l in enumerate(lines) if re.match(r"(?i)\s*(education|experience|skills)\b", l)), min(6, len(lines)))
    if have:
        lines[insert_at:insert_at] = ["", "Key skills for this role: " + ", ".join(have), ""]
    report = {"matched": have, "missing": missing,
              "advice": [f"The advert mentions {s}. If you have used it, add a concrete example." for s in missing[:6]]}
    return "\n".join(lines), report


def to_pdf(docx_path: str | Path) -> Path | None:
    """Convert with LibreOffice when it is installed; returns None otherwise."""
    import shutil
    import subprocess
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        return None
    docx_path = Path(docx_path)
    subprocess.run([soffice, "--headless", "--convert-to", "pdf", "--outdir", str(docx_path.parent), str(docx_path)],
                   check=False, capture_output=True, timeout=120)
    pdf = docx_path.with_suffix(".pdf")
    return pdf if pdf.exists() else None
