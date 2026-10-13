import json
from pathlib import Path

from jobhunt.cv import parse
from jobhunt.match import Preferences, category_of, language_barrier, level_of, location_ok, rank, required_years
from jobhunt.models import Job
from jobhunt.skills import find_skills
from jobhunt.sources import ashby, greenhouse, lever, workable

F = Path(__file__).parent / "fixtures"


def all_jobs():
    load = lambda n: json.loads((F / f"{n}.json").read_text())  # noqa: E731
    return (greenhouse.parse(load("greenhouse"), "Stripe") + lever.parse(load("lever"), "Palantir")
            + ashby.parse(load("ashby"), "Ramp") + workable.parse(load("workable"), "Phorest"))


def job(title, description="", location="Dublin, Ireland", **kw):
    return Job(source="greenhouse", company="Acme", title=title, location=location, url=f"https://x/{title}", description=description, **kw)


def test_skill_matching_respects_word_boundaries():
    found = find_skills("We use Python, SQL and Tableau. Experience with R or MATLAB. Javascript is a plus.")
    assert {"Python", "SQL", "Tableau", "R", "MATLAB", "JavaScript"} <= set(found)
    assert "Java" not in found
    assert "R" not in find_skills("Our Recruiting team reads every Resume")


def test_levels_and_years():
    assert level_of(job("Senior Data Engineer")) == "Senior"
    assert level_of(job("Graduate Data Analyst")) == "Graduate / entry"
    assert level_of(job("Data Analyst", "You have 5+ years of experience in SQL.")) == "Mid / senior"
    assert level_of(job("Summer Internship - Data")) == "Internship"
    assert required_years("at least 3 years of relevant experience") == 3
    assert required_years("0-2 years experience") == 0


def test_categories():
    assert category_of(job("Junior Machine Learning Engineer")) == "AI / ML engineer"
    assert category_of(job("Analytics Engineer (Graduate)")) == "Data engineer"
    assert category_of(job("Trust & Safety Analyst")) == "Trust and safety"


def test_location_rules():
    prefs = Preferences()
    assert location_ok(job("x", location="Dublin, Ireland"), prefs)
    assert not location_ok(job("x", location="San Francisco, CA"), prefs)
    assert location_ok(job("x", "Remote across EMEA", location="Remote", remote=True), prefs)
    assert not location_ok(job("x", "Must live in the United States", location="Remote - US", remote=True), prefs)


def test_language_requirement_detected():
    prefs = Preferences(languages=["English"])
    assert language_barrier(job("German Speaking Content Moderator"), prefs) == "German"
    assert language_barrier(job("Analyst", "Fluent French is essential."), prefs) == "French"
    assert language_barrier(job("Analyst", "We work in English."), prefs) is None


def test_rank_filters_and_orders():
    cv = parse((F / "cv.txt").read_text())
    ranked, dropped = rank(all_jobs(), cv.text, cv.skills, Preferences(min_score=0))
    titles = [j.title for j in ranked]
    assert "Senior Data Engineer" not in titles
    assert "German Speaking Content Moderator" not in titles
    assert "Data Scientist, Machine Learning" not in titles      # San Francisco
    assert "Remote Data Analyst" not in titles                   # US only
    assert titles[0] in ("Graduate Data Analyst", "Junior Machine Learning Engineer")
    assert all(0 <= j.score <= 100 for j in ranked)
    assert ranked == sorted(ranked, key=lambda j: -j.score)
    assert dropped["seniority"] >= 1 and dropped["language"] == 1 and dropped["location"] >= 2
    top = ranked[0]
    assert top.matched_skills and top.reasons


def test_cv_sections_and_contact():
    cv = parse((F / "cv.txt").read_text())
    assert cv.name == "Alex Example" and cv.email == "alex@example.com"
    assert "experience" in cv.sections and "projects" in cv.sections
    assert len(cv.bullets("experience")) == 2
