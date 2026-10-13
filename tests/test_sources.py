import json
from pathlib import Path

from jobhunt.models import html_to_text
from jobhunt.sources import ashby, greenhouse, lever, smartrecruiters, workable

F = Path(__file__).parent / "fixtures"


def load(name):
    return json.loads((F / f"{name}.json").read_text())


def test_greenhouse_parses_and_unescapes():
    jobs = greenhouse.parse(load("greenhouse"), "Stripe")
    assert len(jobs) == 3
    first = jobs[0]
    assert first.title == "Graduate Data Analyst" and first.company == "Stripe"
    assert "Dublin, Ireland" in first.location
    assert "<" not in first.description and "SQL and Python" in first.description
    assert first.posted == "2026-09-30"


def test_lever_combines_lists_and_dates():
    jobs = lever.parse(load("lever"), "Palantir")
    assert jobs[0].title == "Junior Machine Learning Engineer"
    assert "PyTorch" in jobs[0].description and "Graduates welcome" in jobs[0].description
    assert jobs[0].posted.startswith("2025-") or jobs[0].posted.startswith("2026-")
    assert jobs[0].apply_url.endswith("/apply")


def test_ashby_skips_unlisted_and_reads_remote():
    jobs = ashby.parse(load("ashby"), "Ramp")
    titles = [j.title for j in jobs]
    assert "Hidden role" not in titles
    assert jobs[0].remote is True and jobs[0].posted == "2026-09-29"


def test_workable_uses_account_name():
    jobs = workable.parse(load("workable"), "phorest")
    assert jobs[0].company == "Phorest" and jobs[0].location.startswith("Dublin")


def test_smartrecruiters_listing_with_detail():
    item = load("smartrecruiters_list")["content"][0]
    job = smartrecruiters.parse_listing(item, "Visa", "Visa", load("smartrecruiters_detail"))
    assert job.url == "https://jobs.smartrecruiters.com/Visa/744"
    assert "fraud" in job.description and "IE" in job.location


def test_html_to_text_handles_double_escaping():
    assert html_to_text("&amp;lt;b&amp;gt;Hi&amp;lt;/b&amp;gt; there") == "Hi there"
