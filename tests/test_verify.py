from jobhunt.models import Job
from jobhunt.verify import assess, career_site_links_board, red_flags


def job(**kw):
    base = dict(source="greenhouse", company="Stripe", title="Graduate Data Analyst", location="Dublin",
                url="https://stripe.com/jobs/listing/x/1", description="A real advert. " * 30)
    base.update(kw)
    return Job(**base)


def test_verified_when_on_company_domain():
    label, evidence = assess(job(), {"website": "stripe.com", "career_site_links_board": False})
    assert label == "Verified employer" and any("own website" in e for e in evidence)


def test_official_board_without_website_confirmation():
    label, _ = assess(job(url="https://boards.greenhouse.io/stripe/jobs/1"), {"website": "stripe.com"})
    assert label == "Official job board"


def test_verified_when_site_links_board():
    label, _ = assess(job(url="https://boards.greenhouse.io/stripe/jobs/1"),
                      {"website": "stripe.com", "career_site_links_board": True})
    assert label == "Verified employer"


def test_aggregator_is_unverified():
    label, _ = assess(job(source="adzuna", url="https://www.adzuna.ie/details/1"), None)
    assert label == "Unverified"


def test_scam_signs():
    text = ("Work from home! Earn €500 per day, no experience needed. Pay a small training fee and contact us on "
            "WhatsApp. Send your bank account details to hr.jobs@gmail.com to get started.")
    flags = red_flags(job(description=text, source="jooble", url="https://jooble.org/x"))
    assert {"asks for a fee", "contact by chat app", "asks for bank or ID details",
            "personal email address for applications", "promises big daily or weekly pay"} <= set(flags)
    assert assess(job(description=text), None)[0] == "Caution"


def test_genuine_advert_has_no_flags():
    text = "You will build dashboards in Tableau. We offer a training budget and private health insurance."
    assert red_flags(job(description=text)) == []


def test_career_site_link_detection():
    assert career_site_links_board('<a href="https://boards.greenhouse.io/stripe">Jobs</a>', "greenhouse", "stripe")
    assert career_site_links_board('<a href="https://jobs.lever.co/palantir/123">', "lever", "palantir")
    assert not career_site_links_board("<p>We are hiring</p>", "lever", "palantir")
