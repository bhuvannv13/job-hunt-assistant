from email.message import EmailMessage

from jobhunt import notify
from jobhunt.match import Preferences
from jobhunt.models import Job
from jobhunt.skills import find_skills
from jobhunt.sources import email_alerts

GLASSDOOR_HTML = """
<html><body><table>
<tr><td><a href="https://www.glassdoor.ie/partner/jobListing.htm?pos=101&jobListingId=1010305347808&utm_source=jobalert">
  <div>Aon</div><div>3.9 ★</div><div>Data &amp; Analytics - Graduate</div><div>Dublin, Co. Dublin</div>
  <div>€46K - €47K (Glassdoor Est.)</div><div>5d</div></a></td></tr>
<tr><td><a href="https://www.glassdoor.ie/partner/jobListing.htm?pos=102&jobListingId=1010304764824">
  <div>Ryanair</div><div>3.2 ★</div><div>Supply Chain Analyst</div><div>Swords, Co. Dublin</div><div>Easy Apply</div></a></td></tr>
<tr><td><a href="https://www.glassdoor.ie/member/profile/emailSettings">Edit</a></td></tr>
</table></body></html>"""

LINKEDIN_HTML = """
<a href="https://www.linkedin.com/comm/jobs/view/4485457624/?trackingId=abc&refId=x">
  <span>Junior Data Scientist</span><br><span>Fintech Startup</span><br><span>Dublin, County Dublin, Ireland</span></a>
<a href="https://www.linkedin.com/comm/jobs/view/4485457624/?trackingId=def">View job</a>
<a href="https://www.linkedin.com/feed/">Home</a>"""

PROFILE_TEXT = ("Graduate Data Analyst. MSc AI. Python, SQL, pandas, Tableau, statistics, A/B testing, dashboards, "
                "machine learning, scikit-learn. Built SQL reports and dashboards; analysed data.")


def eml(sender, html):
    message = EmailMessage()
    message["From"], message["Subject"] = sender, "Job alert"
    message["Date"] = "Mon, 02 Nov 2026 09:00:00 +0000"
    message.set_content("plain version")
    message.add_alternative(html, subtype="html")
    return message.as_bytes()


def test_glassdoor_alert_parsing():
    jobs = email_alerts.parse_message(eml("Glassdoor Jobs <noreply@glassdoor.com>", GLASSDOOR_HTML))
    assert [(j.company, j.title, j.location) for j in jobs] == [
        ("Aon", "Data & Analytics - Graduate", "Dublin, Co. Dublin"),
        ("Ryanair", "Supply Chain Analyst", "Swords, Co. Dublin")]
    assert jobs[0].url == "https://www.glassdoor.ie/job-listing/?jl=1010305347808"
    assert jobs[0].source == "glassdoor" and jobs[0].posted == "2026-11-02"


def test_linkedin_alert_parsing_dedupes_and_drops_tracking():
    jobs = email_alerts.parse_alert(LINKEDIN_HTML, "LinkedIn Job Alerts <jobalerts-noreply@linkedin.com>")
    assert len(jobs) == 1
    assert jobs[0].title == "Junior Data Scientist" and jobs[0].company == "Fintech Startup"
    assert jobs[0].url == "https://www.linkedin.com/jobs/view/4485457624/"


def test_unknown_sender_is_ignored():
    assert email_alerts.parse_alert(GLASSDOOR_HTML, "someone@example.com") == []


def test_eml_dir(tmp_path):
    (tmp_path / "a.eml").write_bytes(eml("noreply@glassdoor.com", GLASSDOOR_HTML))
    assert len(email_alerts.from_eml_dir(tmp_path)) == 2


def board_job(title, company="Acme", description=""):
    return Job(source="greenhouse", company=company, title=title, location="Dublin, Ireland",
               url=f"https://boards.greenhouse.io/acme/{title.replace(' ', '-')}", description=description,
               trust="Official job board")


def test_select_new_ranks_filters_and_remembers():
    jobs = [board_job("Graduate Data Analyst", description="SQL, Python, Tableau dashboards and statistics for reporting."),
            board_job("Senior Staff Platform Engineer", description="10+ years of Kubernetes and Go."),
            board_job("Graduate Data Analyst", company="Beta", description="Python, SQL, A/B testing and dashboards."),
            Job(source="glassdoor", company="Aon", title="Data & Analytics - Graduate", location="",
                url="https://www.glassdoor.ie/job-listing/?jl=1", description="Found in your Glassdoor job alert. data analytics SQL Python")]
    settings = notify.NotifySettings(min_score=30, max_per_run=10)
    new = notify.select_new(jobs, PROFILE_TEXT, find_skills(PROFILE_TEXT), Preferences(min_score=0), settings, {})
    titles = [(j.company, j.title) for j in new]
    assert ("Acme", "Senior Staff Platform Engineer") not in titles
    assert ("Acme", "Graduate Data Analyst") in titles and ("Aon", "Data & Analytics - Graduate") in titles
    state = {email_alerts.dedupe_key(j): "2026-11-02" for j in new}
    again = notify.select_new(jobs, PROFILE_TEXT, find_skills(PROFILE_TEXT), Preferences(min_score=0), settings, state)
    assert again == []


def test_caution_jobs_are_never_notified():
    job = board_job("Graduate Data Analyst", description="Python SQL dashboards")
    job.trust = "Caution"
    settings = notify.NotifySettings(min_score=0)
    assert notify.select_new([job], PROFILE_TEXT, find_skills(PROFILE_TEXT), Preferences(min_score=0), settings, {}) == []


def test_state_forgets_old_entries(tmp_path):
    path = tmp_path / "state.json"
    notify.save_state(path, {"old": "2000-01-01", "new": "2999-01-01"}, remember_days=60)
    assert notify.load_state(path) == {"new": "2999-01-01"}


def test_digest_and_email_never_claim_to_apply():
    job = board_job("Graduate Data Analyst")
    job.score, job.matched_skills, job.missing_skills = 72, ["Python", "SQL"], ["dbt"]
    text = notify.digest_text([job])
    assert "72 | Graduate Data Analyst at Acme" in text and job.url in text
    assert "never sent for you" in text
    message = notify.build_email([job], "me@example.com", "me@example.com")
    assert message["Subject"] == "1 new job match: Graduate Data Analyst"


def test_ntfy_sends_one_push_per_job(monkeypatch):
    calls = []

    class Ok:
        ok = True

    monkeypatch.setattr(notify.requests, "post", lambda url, data, timeout, headers: calls.append((url, headers)) or Ok())
    a, b = board_job("Graduate Data Analyst"), board_job("Junior Data Scientist")
    a.score, b.score = 75, 55
    assert notify.send_ntfy([a, b], "my-topic") == 2
    assert calls[0][0] == "https://ntfy.sh/my-topic"
    assert calls[0][1]["Click"] == a.url and calls[0][1]["Priority"] == "high" and calls[1][1]["Priority"] == "default"


def test_deliver_without_settings_sends_nothing(monkeypatch, tmp_path):
    for key in ("NTFY_TOPIC", "SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "NOTIFY_TO"):
        monkeypatch.delenv(key, raising=False)
    job = board_job("Graduate Data Analyst")
    assert notify.deliver([job], notify.NotifySettings(), None, tmp_path) == {"ntfy": 0, "email": 0}
