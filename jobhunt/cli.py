"""Command line interface.

    python -m jobhunt check-companies            # test every job board and the employer's website link
    python -m jobhunt fetch                      # collect jobs and write docs/data/jobs.json
    python -m jobhunt match --cv my_cv.pdf       # rank jobs for a CV, tailor CVs, build the Excel tracker
    python -m jobhunt match --profile me.yaml    # same, using a structured profile for better tailoring
    python -m jobhunt notify --profile me.yaml   # push / email new jobs that fit you (add --emails for alert emails)
    python -m jobhunt live URL [--tracker]       # is the posting still open?
    python -m jobhunt workauth --in posting.md --permit "Stamp 1G"   # right-to-work blockers
    python -m jobhunt patterns                   # funnel and rejection patterns from your tracker
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import pipeline, sources, verify
from .pipeline import ROOT

DATA = ROOT / "docs" / "data"
CAREER_PATHS = ["/careers", "/jobs", "/careers/", "/company/careers", "/about/careers", "/en/careers", "/join-us", "/work-with-us"]


def check_company(company: dict) -> dict:
    result = {**company, "board_ok": False, "jobs_total": 0, "jobs_ireland": 0, "links_board": None,
              "careers_page": "", "checked": datetime.now(timezone.utc).date().isoformat()}
    try:
        jobs = sources.fetch_company(company["ats"], company["token"], company["name"])
    except Exception:
        jobs = []
    result["board_ok"] = bool(jobs)
    result["jobs_total"] = len(jobs)
    prefs = pipeline.Preferences()
    result["jobs_ireland"] = sum(1 for j in jobs if pipeline.location_ok(j, prefs))
    website = company.get("website")
    if website and result["board_ok"]:
        urls = [f"https://{website}{p}" for p in CAREER_PATHS] + [f"https://careers.{website}", f"https://jobs.{website}"]
        for url in urls:
            try:
                page = requests.get(url, timeout=12, headers={"User-Agent": sources.USER_AGENT}, allow_redirects=True)
            except requests.RequestException:
                continue
            if page.status_code != 200:
                continue
            result["careers_page"] = page.url
            if verify.career_site_links_board(page.text, company["ats"], company["token"]):
                result["links_board"] = True
                break
            result["links_board"] = False
        # Adverts hosted on the company's own domain also prove the link.
        if not result["links_board"] and any(verify.domain(j.url).endswith(website) for j in jobs[:20]):
            result["links_board"] = True
    return result


def cmd_check(args):
    companies = pipeline.load_companies(args.companies)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check_company, companies))
    DATA.mkdir(parents=True, exist_ok=True)
    out = Path(args.out)
    out.write_text(json.dumps({"checked": datetime.now(timezone.utc).isoformat(timespec="minutes"), "companies": results},
                              indent=1, ensure_ascii=False), encoding="utf-8")
    ok = [r for r in results if r["board_ok"]]
    print(f"{len(ok)}/{len(results)} boards respond; {sum(1 for r in ok if r['links_board'])} confirmed from the company website; "
          f"{sum(r['jobs_ireland'] for r in ok)} jobs in Ireland or remote-Europe.")
    for r in results:
        if not r["board_ok"]:
            print(f"  not responding: {r['name']} ({r['ats']}:{r['token']})")


def company_status(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {c["name"]: {"website": c.get("website", ""), "career_site_links_board": bool(c.get("links_board"))}
            for c in data["companies"]}


def cmd_fetch(args):
    companies = [c for c in pipeline.load_companies(args.companies)]
    status_path = Path(args.status)
    if status_path.exists():   # skip boards that the last check found dead
        status = json.loads(status_path.read_text(encoding="utf-8"))["companies"]
        dead = {c["name"] for c in status if not c["board_ok"]}
        companies = [c for c in companies if c["name"] not in dead]
    jobs, counts = pipeline.collect(companies)
    from .sources import aggregators
    queries = ["graduate data analyst", "graduate data engineer", "junior data scientist", "graduate machine learning", "trust and safety"]
    jobs += aggregators.fetch_adzuna(queries) + aggregators.fetch_jooble(queries)
    pipeline.check_trust(jobs, company_status(status_path))
    prefs = pipeline.load_preferences(args.prefs)
    n = pipeline.publish_jobs(jobs, prefs, args.out, counts)
    print(f"Fetched {len(jobs)} jobs from {sum(1 for v in counts.values() if v >= 0)} boards; {n} in Ireland or remote-Europe written to {args.out}")


def cmd_match(args):
    from . import cv as cvmod
    from .tailor import load_profile, profile_text
    from .skills import find_skills

    if not (args.cv or args.profile):
        sys.exit("Give --cv (PDF/DOCX/TXT) or --profile (YAML)")
    profile = load_profile(args.profile) if args.profile else None
    cv = cvmod.load(args.cv) if args.cv else None
    text = "\n".join(t for t in [profile_text(profile) if profile else "", cv.text if cv else ""] if t)
    skills = find_skills(text)
    jobs = pipeline.load_jobs(args.jobs)
    status = company_status(Path(args.status))
    if status or not any(j.trust for j in jobs):   # keep the labels from fetch when no status file is available
        pipeline.check_trust(jobs, status)
    prefs = pipeline.load_preferences(args.prefs)
    summary = pipeline.run_match(jobs, text, skills, prefs, args.out, profile=profile, cv=cv, tailor_top=args.tailor,
                                 include_caution=args.include_caution)
    print(json.dumps(summary, indent=1))


def cmd_notify(args):
    from . import cv as cvmod
    from . import notify
    from .skills import find_skills
    from .sources import email_alerts
    from .tailor import load_profile, profile_text

    if not (args.cv or args.profile):
        sys.exit("Give --cv (PDF/DOCX/TXT) or --profile (YAML)")
    profile = load_profile(args.profile) if args.profile else None
    cv = cvmod.load(args.cv) if args.cv else None
    text = "\n".join(t for t in [profile_text(profile) if profile else "", cv.text if cv else ""] if t)
    jobs = pipeline.load_jobs(args.jobs) if Path(args.jobs).exists() else []
    alerts = email_alerts.from_eml_dir(args.eml_dir) if args.eml_dir else []
    if args.emails:
        alerts += email_alerts.fetch_imap(days=args.days)
    pipeline.check_trust(alerts, {})
    settings = notify.NotifySettings.load(args.config)
    state = notify.load_state(args.state)
    new = notify.select_new(jobs + alerts, text, find_skills(text), pipeline.load_preferences(args.prefs), settings, state)
    if args.dry_run:
        print(notify.digest_text(new) if new else "No new matching jobs.")
        return
    report = notify.deliver(new, settings, profile, Path(args.out))
    today = datetime.now(timezone.utc).date().isoformat()
    from .sources.email_alerts import dedupe_key
    state.update({dedupe_key(j): today for j in new})
    notify.save_state(args.state, state, settings.remember_days)
    # Counts only: workflow logs of a public repository must not show which jobs you are applying for.
    print(f"Checked {len(jobs)} board jobs and {len(alerts)} alert-email jobs; {len(new)} new matches; "
          f"push notifications sent: {report['ntfy']}; digest emails sent: {report['email']}.")


def _profile_text(args) -> str:
    from . import cv as cvmod
    from .tailor import load_profile, profile_text
    profile = load_profile(args.profile) if getattr(args, "profile", None) else None
    cv = cvmod.load(args.cv) if getattr(args, "cv", None) else None
    return "\n".join(t for t in [profile_text(profile) if profile else "", cv.text if cv else ""] if t)


def cmd_guard(args):
    from . import guard
    content = Path(args.input).read_text(encoding="utf-8", errors="replace") if args.input else sys.stdin.read()
    result = guard.check(content, is_html=args.html)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=1))
    else:
        print(guard.format_report(result))
        if args.cleaned:
            print("\n--- cleaned posting ---\n" + result.cleaned)
    if args.out:
        Path(args.out).write_text(result.cleaned, encoding="utf-8")


def cmd_render(args):
    import yaml
    from . import tailor
    outputs = []
    if args.tailored:
        data = yaml.safe_load(Path(args.tailored).read_text(encoding="utf-8"))
        outputs.append(tailor.write_tailored_docx(data, args.cv_out))
    if args.letter:
        text = Path(args.letter).read_text(encoding="utf-8")
        outputs.append(tailor.write_text_docx(text, args.letter_out, title=args.letter_title or ""))
    for path in outputs:
        pdf = tailor.to_pdf(path) if args.pdf else None
        print(f"wrote {path}" + (f" and {pdf}" if pdf else " (PDF needs LibreOffice)" if args.pdf else ""))


def cmd_ats(args):
    from . import ats
    posting = Path(args.posting).read_text(encoding="utf-8") if args.posting else ""
    report = ats.check(args.file, posting, args.keyword or [], args.email or "", args.phone or "")
    print(json.dumps(report.to_dict(), indent=1) if args.json else ats.format_report(report))


def cmd_app(args):
    from . import applications as A
    csv_path, archive = Path(args.csv), Path(args.archive)
    if args.action == "add":
        app = A.add(args.company, args.role, csv_path, archive, status=args.status or "considering",
                    **{k: v for k, v in dict(url=args.url, location=args.location, source=args.source, score=args.score,
                                            channel=args.channel, sector=args.sector, notes=args.notes,
                                            next_step=args.next_step).items() if v})
        print(f"added {app.id} -> {archive / app.folder}")
    elif args.action == "update":
        values = {k: v for k, v in dict(status=args.status, url=args.url, score=args.score, channel=args.channel,
                                        sector=args.sector, notes=args.notes, next_step=args.next_step).items() if v}
        app = A.update(args.key, csv_path, archive, note=args.note or "", **values)
        print(f"updated {app.id}: {app.status}")
    elif args.action == "followup-sent":
        app = A.record_followup(args.key, csv_path, archive)
        print(f"{app.id}: follow-ups sent {app.followups_sent}")
    elif args.action == "followups":
        due = A.followups_due(A.load(csv_path), args.days)
        print(json.dumps([{**{k: getattr(a, k) for k in ("id", "company", "role", "status", "followups_sent", "folder")},
                           "days_quiet": d} for a, d in due], indent=1))
    elif args.action == "import":
        import csv as csvmod
        with open(args.file, newline="", encoding="utf-8") as fh:
            print(f"imported {A.import_rows(list(csvmod.DictReader(fh)), csv_path)} application(s)")
    else:   # list
        apps = A.load(csv_path)
        if args.json:
            print(json.dumps([vars(a) for a in apps], indent=1))
        else:
            for a in apps:
                print(f"{a.status:16} {a.date_applied or a.status_date:10}  {a.company} – {a.role}  [{a.id}]")
            print(json.dumps(A.summary(apps, archive)))


def cmd_report(args):
    from . import report
    print(f"wrote {report.write(args.out, args.csv, args.archive, args.days)}")


def cmd_upskill(args):
    from . import upskill
    if not (args.cv or args.profile):
        sys.exit("Give --cv or --profile")
    jobs = pipeline.load_jobs(args.jobs)
    if args.extra_jobs:
        jobs += pipeline.load_jobs(args.extra_jobs)
    gap_list, strengths, n = upskill.gaps(jobs, _profile_text(args), pipeline.load_preferences(args.prefs), args.top)
    if args.json:
        print(json.dumps({"jobs": n, "strengths": strengths, "gaps": [{**vars(g), "priority": g.priority} for g in gap_list]}, indent=1))
    else:
        print(upskill.markdown(gap_list, strengths, n, args.limit))


def cmd_live(args):
    from . import applications as A, liveness
    urls = list(args.urls)
    if args.tracker:
        urls += [a.url for a in A.load(args.csv) if a.url.startswith("http") and a.status in ({"considering"} | A.OPEN)]
    if not urls:
        sys.exit("Give one or more URLs, or --tracker")
    session = requests.Session()
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda u: liveness.check(u, session), dict.fromkeys(urls)))
    if args.json:
        print(json.dumps([r.to_dict() for r in results], indent=1))
    else:
        for r in results:
            print(f"{r.status:9}  {r.url}\n           {r.evidence}")


def cmd_workauth(args):
    from . import workauth
    text = Path(args.input).read_text(encoding="utf-8") if args.input else sys.stdin.read()
    found = workauth.restrictions(text)
    blocked = workauth.blocker(text, args.permit) if args.permit else None
    if args.json:
        print(json.dumps({"restrictions": [{"kind": r.kind, "label": r.label, "evidence": r.evidence} for r in found],
                          "blocked": blocked.label if blocked else None}, indent=1))
        return
    if not found:
        print("No right-to-work restrictions found in the advert.")
    for r in found:
        print(f"- {r.label}: \"{r.evidence}\"")
    if args.permit:
        print(f"\nVerdict for {args.permit}: " + (f"DO NOT APPLY ({blocked.label})" if blocked else "no blocker found"))


def cmd_patterns(args):
    from . import applications as A, patterns
    result = patterns.analyse(A.load(args.csv), args.archive)
    print(json.dumps(result, indent=1) if args.json else patterns.format_text(result))


def main(argv=None):
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(prog="jobhunt", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("check-companies", help="test each job board and the link from the employer's website")
    c.add_argument("--companies", default=ROOT / "config" / "companies.yaml")
    c.add_argument("--out", default=DATA / "companies.json")
    c.set_defaults(func=cmd_check)
    f = sub.add_parser("fetch", help="collect jobs from every board")
    f.add_argument("--companies", default=ROOT / "config" / "companies.yaml")
    f.add_argument("--status", default=DATA / "companies.json")
    f.add_argument("--prefs", default=ROOT / "config" / "preferences.yaml")
    f.add_argument("--out", default=DATA / "jobs.json")
    f.set_defaults(func=cmd_fetch)
    m = sub.add_parser("match", help="rank jobs for your CV, tailor CVs and build the Excel tracker")
    m.add_argument("--cv")
    m.add_argument("--profile")
    m.add_argument("--jobs", default=DATA / "jobs.json")
    m.add_argument("--status", default=DATA / "companies.json")
    m.add_argument("--prefs", default=ROOT / "config" / "preferences.yaml")
    m.add_argument("--out", default="output")
    m.add_argument("--tailor", type=int, default=10, help="how many top jobs get a tailored CV and cover letter")
    m.add_argument("--include-caution", action="store_true", help="keep jobs with scam warning signs")
    m.set_defaults(func=cmd_match)
    n = sub.add_parser("notify", help="send push / email notifications about new jobs that fit you")
    n.add_argument("--cv")
    n.add_argument("--profile")
    n.add_argument("--jobs", default=DATA / "jobs.json")
    n.add_argument("--prefs", default=ROOT / "config" / "preferences.yaml")
    n.add_argument("--config", default=ROOT / "config" / "notify.yaml")
    n.add_argument("--state", default="output/notified.json", help="remembers which jobs you were already told about")
    n.add_argument("--out", default="output")
    n.add_argument("--emails", action="store_true", help="also read job-alert emails over IMAP (IMAP_USER, IMAP_PASSWORD)")
    n.add_argument("--days", type=int, default=2, help="how many days of alert emails to read")
    n.add_argument("--eml-dir", help="folder of saved job-alert .eml files to read")
    n.add_argument("--dry-run", action="store_true", help="print the digest instead of sending it")
    n.set_defaults(func=cmd_notify)

    g = sub.add_parser("guard", help="check a job posting for hidden text and instructions aimed at AI tools")
    g.add_argument("--in", dest="input", help="file to check (default: read stdin)")
    g.add_argument("--html", action="store_true", help="the input is an HTML page")
    g.add_argument("--json", action="store_true")
    g.add_argument("--cleaned", action="store_true", help="also print the cleaned posting text")
    g.add_argument("--out", help="write the cleaned posting text to this file")
    g.set_defaults(func=cmd_guard)

    r = sub.add_parser("render", help="build Word (and PDF) files from a tailored CV YAML and a cover letter text")
    r.add_argument("--tailored", help="tailored profile YAML written by /apply")
    r.add_argument("--cv-out", default="output/CV.docx")
    r.add_argument("--letter", help="cover letter as plain text / markdown")
    r.add_argument("--letter-out", default="output/Cover_letter.docx")
    r.add_argument("--letter-title", default="")
    r.add_argument("--pdf", action="store_true", help="also convert to PDF with LibreOffice")
    r.set_defaults(func=cmd_render)

    a = sub.add_parser("ats-check", help="check that a CV's text layer is readable by applicant tracking systems")
    a.add_argument("file", help="CV as .pdf, .docx or .txt")
    a.add_argument("--posting", help="posting text file, to check keyword coverage")
    a.add_argument("--keyword", action="append", help="extra keyword to look for (repeatable)")
    a.add_argument("--email")
    a.add_argument("--phone")
    a.add_argument("--json", action="store_true")
    a.set_defaults(func=cmd_ats)

    t = sub.add_parser("app", help="application tracker: add, update, list, followups, followup-sent, import")
    t.add_argument("action", choices=["add", "update", "list", "followups", "followup-sent", "import"])
    t.add_argument("key", nargs="?", help="application id or a unique part of 'company role' (update / followup-sent)")
    t.add_argument("--company"); t.add_argument("--role"); t.add_argument("--url"); t.add_argument("--location")
    t.add_argument("--source"); t.add_argument("--score"); t.add_argument("--status"); t.add_argument("--channel")
    t.add_argument("--sector"); t.add_argument("--notes"); t.add_argument("--next-step", dest="next_step")
    t.add_argument("--note", help="line for the outcome log (update)")
    t.add_argument("--days", type=int, default=10, help="quiet days before a follow-up is due")
    t.add_argument("--file", help="CSV to import (columns: company, role, status, date_applied, url, notes, channel)")
    t.add_argument("--json", action="store_true")
    t.add_argument("--csv", default="private/applications.csv")
    t.add_argument("--archive", default="private/applications")
    t.set_defaults(func=cmd_app)

    h = sub.add_parser("report", help="offline HTML dashboard of your applications")
    h.add_argument("--out", default="private/report.html")
    h.add_argument("--csv", default="private/applications.csv")
    h.add_argument("--archive", default="private/applications")
    h.add_argument("--days", type=int, default=10)
    h.set_defaults(func=cmd_report)

    u = sub.add_parser("upskill", help="skill gaps across the jobs that fit you best")
    u.add_argument("--cv"); u.add_argument("--profile")
    u.add_argument("--jobs", default=DATA / "jobs.json")
    u.add_argument("--extra-jobs", help="another jobs.json, e.g. postings saved by /rank")
    u.add_argument("--prefs", default=ROOT / "config" / "preferences.yaml")
    u.add_argument("--top", type=int, default=60)
    u.add_argument("--limit", type=int, default=20)
    u.add_argument("--json", action="store_true")
    u.set_defaults(func=cmd_upskill)

    lv = sub.add_parser("live", help="check whether postings are still open before you apply")
    lv.add_argument("urls", nargs="*")
    lv.add_argument("--tracker", action="store_true", help="also check open and considering applications in the tracker")
    lv.add_argument("--csv", default="private/applications.csv")
    lv.add_argument("--json", action="store_true")
    lv.set_defaults(func=cmd_live)

    w = sub.add_parser("workauth", help="find right-to-work restrictions (Stamp 4 only, excludes Stamp 1G, no sponsorship...)")
    w.add_argument("--in", dest="input", help="posting text file (default: read stdin)")
    w.add_argument("--permit", help="your permission, e.g. 'Stamp 1G', 'Stamp 4', 'EU', 'needs sponsorship'")
    w.add_argument("--json", action="store_true")
    w.set_defaults(func=cmd_workauth)

    pt = sub.add_parser("patterns", help="funnel and rejection patterns from the application tracker")
    pt.add_argument("--csv", default="private/applications.csv")
    pt.add_argument("--archive", default="private/applications")
    pt.add_argument("--json", action="store_true")
    pt.set_defaults(func=cmd_patterns)
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
