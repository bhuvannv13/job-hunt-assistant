"""Command line interface.

    python -m jobhunt check-companies            # test every job board and the employer's website link
    python -m jobhunt fetch                      # collect jobs and write docs/data/jobs.json
    python -m jobhunt match --cv my_cv.pdf       # rank jobs for a CV, tailor CVs, build the Excel tracker
    python -m jobhunt match --profile me.yaml    # same, using a structured profile for better tailoring
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
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
