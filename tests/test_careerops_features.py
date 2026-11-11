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
