"""Right-to-work screen, posting liveness and tracker patterns."""
from datetime import date

from jobhunt import liveness, patterns, workauth
from jobhunt.applications import Application
from jobhunt.match import Preferences, screen
from jobhunt.models import Job

TALENTSPOT = ("The successful applicant must be an EU citizen or have the right to work full-time in Ireland for an "
              "unlimited period without sponsorship (i.e. Stamp 4 or Spousal visa). As Stamp 1G/2 visas are time-limited, "
              "this EXCLUDES STAMP 1G Student Visas. Please don't apply if you possess a Stamp 1G Visa.")


def test_workauth_finds_stamp_restrictions():
    kinds = {r.kind for r in workauth.restrictions(TALENTSPOT)}
    assert {"excludes_stamp1g", "unlimited_right_to_work"} <= kinds
    assert workauth.blocker(TALENTSPOT, "Stamp 1G").kind in {"excludes_stamp1g", "unlimited_right_to_work", "eu_only"}
    assert workauth.blocker(TALENTSPOT, "EU") is None


def test_workauth_sponsorship_only_blocks_those_who_need_it():
    text = "Please note we are unable to offer visa sponsorship for this role."
    assert [r.kind for r in workauth.restrictions(text)] == ["no_sponsorship"]
    assert workauth.blocker(text, "Stamp 1G") is None
    assert workauth.blocker(text, "needs sponsorship").kind == "no_sponsorship"


def test_workauth_ignores_neutral_text():
    text = "We welcome applications from graduates. Stamp 1G holders are welcome to apply. Hybrid working in Dublin."
    assert workauth.restrictions(text) == []


def test_screen_drops_jobs_that_exclude_the_permit():
    job = Job(source="t", company="X", title="Graduate Data Analyst", location="Dublin, Ireland", url="https://x/1",
              description="Graduate data analyst using SQL and Python. " + TALENTSPOT)
    assert screen(job, Preferences(permit="Stamp 1G")).startswith("right to work")
    assert screen(job, Preferences()) is None


def test_liveness_page_judgement():
    assert liveness.judge_page("<h1>Sorry, this job is no longer available</h1><button>Apply</button>")[0] == "closed"
    assert liveness.judge_page("Applications for this role have closed.")[0] == "closed"
    assert liveness.judge_page("<p>Great role</p><a href='#'>Apply now</a>")[0] == "open"
    assert liveness.judge_page("Once the application form has been filled out, apply now")[0] == "open"
    assert liveness.judge_page("", 404)[0] == "closed"
    assert liveness.judge_page("Please sign in to view this job")[0] == "uncertain"


def test_liveness_recognises_ats_links():
    assert liveness._ats_api("https://job-boards.greenhouse.io/stripe/jobs/7123456")[1] == "greenhouse"
    assert liveness._ats_api("https://jobs.lever.co/acme/1b2c-3d4e")[0] == "https://api.lever.co/v0/postings/acme/1b2c-3d4e"
    assert liveness._ats_api("https://example.com/careers/1") is None


def _app(i, status, channel, applied, status_date, sector="tech", score="60"):
    return Application(id=f"a{i}", company=f"C{i}", role="Analyst", status=status, channel=channel, sector=sector,
                       date_applied=applied, status_date=status_date, score=score, folder=f"a{i}")


def test_patterns_funnel_and_ghosting(tmp_path):
    apps = [_app(1, "rejected", "linkedin", "2026-10-01", "2026-10-11"),
            _app(2, "rejected", "linkedin", "2026-10-01", "2026-10-21"),
            _app(3, "interview_1", "referral", "2026-10-01", "2026-10-15"),
            _app(4, "applied", "referral", "2026-09-01", "2026-09-01"),
            _app(5, "applied", "linkedin", "2026-11-01", "2026-11-01"),
            _app(6, "considering", "", "", "")]
    r = patterns.analyse(apps, tmp_path, today=date(2026, 11, 11))
    assert r["applied"] == 5 and r["interviews"] == 1 and r["rejected"] == 2
    assert r["median_days_to_rejection"] == 15
    assert [g["company"] for g in r["probably_ghosted"]] == ["C4"]
    channel = {g["group"]: g for g in r["by_channel"]}
    assert channel["referral"]["interviews"] == 1 and channel["linkedin"]["rejected"] == 2
    assert any("silent" in n for n in r["insights"])


def test_reposts():
    hist = [{"company": "Acme", "title": "Data Analyst (m/f/d)", "url": "u1", "posted": "2026-09-01"},
            {"company": "Acme", "title": "Data Analyst", "url": "u2", "posted": "2026-10-15"},
            {"company": "Beta", "title": "Data Analyst", "url": "u3", "posted": "2026-10-15"}]
    assert [f["company"] for f in patterns.reposts(hist)] == ["Acme"]


def test_duplicate_application_detection():
    from jobhunt.applications import find_duplicate
    apps = [Application(id="a", company="Accenture", role="Trust & Safety Associate - CL12", url="https://x.com/job/1?src=li")]
    assert find_duplicate(apps, "Accenture Ireland", "Trust & Safety Associate CL12") is apps[0]
    assert find_duplicate(apps, "Other", "Analyst", url="https://x.com/job/1") is apps[0]
    assert find_duplicate(apps, "Accenture", "Data Engineer") is None


def test_factcheck_flags_invented_numbers_and_names(tmp_path):
    from jobhunt import factcheck
    profile = tmp_path / "profile.yaml"
    profile.write_text("experience: Research Intern at University College Dublin, 2025. ECG CNN 96.01% accuracy on 21,892 beats.")
    cv = tmp_path / "cv.md"
    cv.write_text("Research Intern, University College Dublin (2025). ECG CNN reached 96.01% on 21892 beats. "
                  "Cut processing costs by 37% at Globex Corporation.")
    r = factcheck.check(cv, [profile])
    assert not r.ok
    assert [n.split()[0] for n in r.unsupported_numbers] == ["37%"]
    assert any(n.startswith("Globex Corporation") for n in r.unsupported_names)
    assert not any("University College" in n for n in r.unsupported_names)
    assert factcheck.check(cv, [profile], allow=["37", "Globex Corporation"]).ok


def test_ats_page_limit(tmp_path):
    from jobhunt import ats
    f = tmp_path / "cv.txt"
    f.write_text("x " * 400 + " me@example.com +353 89 000 0000")
    assert ats.check(f, expect_email="me@example.com", max_pages=2).ok   # text files have no pages: no false alarm


def test_ats_flags_lost_digits_and_dots(tmp_path):
    from jobhunt import ats
    f = tmp_path / "cv.txt"
    f.write_text("Experienced analyst. " * 30 + " me@gmailcom")
    problems = " ".join(ats.check(f).problems)
    assert "No digits" in problems


# --- fetch must not wipe the job list when the network is down ---------------------------------

def test_fetch_failed_when_all_boards_error():
    from jobhunt.pipeline import fetch_failed
    assert fetch_failed([], {"a": -1, "b": -1})
    assert fetch_failed([], {"a": -1, "b": 0})          # half failed, nothing returned
    assert fetch_failed([], {})                         # nothing was even tried


def test_fetch_not_failed_when_boards_are_just_empty_or_jobs_returned():
    from jobhunt.models import Job
    from jobhunt.pipeline import fetch_failed
    assert not fetch_failed([], {"a": 0, "b": 0, "c": -1})
    job = Job(source="test", title="Graduate Data Analyst", company="X", location="Dublin", url="https://x", description="")
    assert not fetch_failed([job], {"a": -1, "b": -1})


def test_cli_fetch_keeps_existing_file_when_offline(tmp_path, monkeypatch):
    import argparse
    from jobhunt import cli, pipeline
    from jobhunt.sources import aggregators
    out = tmp_path / "jobs.json"
    out.write_text('{"jobs":[{"title":"keep me"}]}', encoding="utf-8")
    monkeypatch.setattr(pipeline, "collect", lambda companies: ([], {"a": -1, "b": -1}))
    monkeypatch.setattr(aggregators, "fetch_adzuna", lambda q: [])
    monkeypatch.setattr(aggregators, "fetch_jooble", lambda q: [])
    args = argparse.Namespace(companies=str(pipeline.ROOT / "config" / "companies.yaml"),
                              status=str(tmp_path / "none.json"), prefs=None, out=str(out))
    import pytest
    with pytest.raises(SystemExit):
        cli.cmd_fetch(args)
    assert "keep me" in out.read_text(encoding="utf-8")


# --- real advert wording found while testing on live postings (Nov 2026) -----------------------

import pytest as _pytest


@_pytest.mark.parametrize("text,country,expected", [
    ("Applicants must have an existing right to work in Ireland without the requirement for employment "
     "permit sponsorship to be considered for this role.", "Ireland", None),
    ("A legal right to work in the UK.", "UK", "foreign_right_to_work"),
    ("Relocation is welcome, however you must be based in the UK and be a British Citizen.", "UK", "nationality_required"),
    ("UK nationals only, no visa sponsorship", "UK", "no_sponsorship"),
    ("French nationality required (legal obligations).", "France", "nationality_required"),
    ("Candidates must be eligible to work in Ireland/EU.", "Ireland", None),
    ("We offer visa sponsorship for the right candidate.", "UK", None),
])
def test_workauth_real_adverts(text, country, expected):
    from jobhunt.workauth import blocker
    found = blocker(text, "Stamp 1G", country)
    assert (found.kind if found else None) == expected


def test_irish_stamp_needs_sponsorship_abroad():
    from jobhunt.workauth import blocker, effective_permit
    assert effective_permit("Stamp 1G", "United Kingdom") == "needs_sponsorship"
    assert effective_permit("Stamp 1G", "Dublin, Ireland") == "stamp1g"
    assert effective_permit("Stamp 1G") == "stamp1g"
    advert = "Unfortunately we cannot offer visa sponsorship."
    assert blocker(advert, "Stamp 1G") is None                     # fine in Ireland
    assert blocker(advert, "Stamp 1G", "Netherlands").kind == "no_sponsorship"


@_pytest.mark.parametrize("text,years", [
    ("A minimum of two years' relevant experience in data analysis", 2),
    ("1 - 2 years' Data Analysis experience", 1),
    ("Three (3) years of experience with SQL", 3),
    ("3 years’ experience as a data engineer", 3),
    ("We are two years old and growing", None),
    ("Ten years ago we started", None),
])
def test_required_years_words_and_apostrophes(text, years):
    from jobhunt.match import required_years
    assert required_years(text) == years


def test_workauth_cli_country_note(tmp_path, capsys):
    from jobhunt import cli
    posting = tmp_path / "p.md"
    posting.write_text("Junior data analyst in London. Python and SQL.", encoding="utf-8")
    cli.main(["workauth", "--in", str(posting), "--permit", "Stamp 1G", "--country", "UK"])
    out = capsys.readouterr().out
    assert "no blocker found" in out and "needs visa sponsorship" in out
