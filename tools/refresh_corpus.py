"""Daily corpus refresh: fetch today's batch of roles from Naukri via the Firecrawl API.

Rotates through ROLES, BATCH per day, so every role is refreshed about every
len(ROLES)/BATCH days at ~5 Firecrawl credits per role. Writes
corpus/naukri_<date>_<slug>.jsonl (one posting per line, with "d" = date seen) and
corpus/manifest.json ({"updated", "new_today", "roles_refreshed"}).

Run:  FIRECRAWL_API_KEY=... python tools/refresh_corpus.py            (today's batch)
      python tools/refresh_corpus.py --plan                            (print today's batch, no calls)
      python tools/refresh_corpus.py --roles "data analyst,hr recruiter"
"""
import argparse
import datetime as dt
import json
import os
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
BATCH = 4
API = "https://api.firecrawl.dev/v1/scrape"

ROLES = {  # role family (q) -> Naukri search slug
    "business analyst": "business-analyst", "business development executive": "business-development-executive",
    "content writer": "content-writer", "customer success manager": "customer-success-manager",
    "data analyst": "data-analyst", "data scientist": "data-scientist", "devops engineer": "devops-engineer",
    "digital marketing": "digital-marketing-executive", "financial analyst": "financial-analyst",
    "full stack developer": "full-stack-developer", "graphic designer": "graphic-designer",
    "hr recruiter": "hr-recruiter", "java developer": "java-developer", "operations analyst": "operations-analyst",
    "product analyst": "product-analyst", "product manager": "product-manager", "program manager": "program-manager",
    "project manager": "project-manager", "python developer": "python-developer",
    "software test engineer": "software-test-engineer", "supply chain analyst": "supply-chain-analyst",
    "ui ux designer": "ui-ux-designer",
}

PROMPT = ("List every job card on this search results page. Copy the title, company, experience, the job-listing URL, "
          "and the skill tags exactly as listed under the card. Do not infer or add skills that are not printed.")
SCHEMA = {"type": "object", "properties": {"jobs": {"type": "array", "items": {"type": "object", "properties": {
    "title": {"type": "string"}, "company": {"type": "string"}, "experience": {"type": "string"},
    "url": {"type": "string"}, "skills": {"type": "array", "items": {"type": "string"}}},
    "required": ["title", "url", "skills"]}}}}


def todays_batch(day=None, n=BATCH):
    """Same date -> same roles; consecutive days walk through the whole list."""
    day = day or dt.date.today()
    roles = sorted(ROLES)
    start = (day.toordinal() * n) % len(roles)
    return [roles[(start + i) % len(roles)] for i in range(n)]


def to_rows(role, jobs, day):
    """Keep only real job links with skill tags; same line format as the rest of the corpus."""
    rows = []
    for j in jobs or []:
        url, skills = str(j.get("url", "")), [str(s) for s in j.get("skills") or [] if str(s).strip()]
        if url.startswith("https://www.naukri.com/job-listings-") and skills:
            rows.append({"q": role, "t": str(j.get("title", ""))[:160], "c": str(j.get("company", ""))[:120],
                         "e": str(j.get("experience", ""))[:40], "u": url, "s": skills[:12], "d": day.isoformat()})
    return rows


def fetch(role, key):
    body = json.dumps({"url": f"https://www.naukri.com/{ROLES[role]}-jobs", "formats": ["json"],
                       "jsonOptions": {"prompt": PROMPT, "schema": SCHEMA}, "onlyMainContent": True}).encode()
    req = urllib.request.Request(API, body, {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read())
    return ((data.get("data") or {}).get("json") or {}).get("jobs", [])


def known_urls():
    urls = set()
    for f in CORPUS.glob("*.jsonl"):
        for line in f.read_text(encoding="utf-8").splitlines():
            if line.strip():
                urls.add(json.loads(line)["u"])
    return urls


def save(role, rows, day, seen):
    """Write one role's file and return how many postings are new to the corpus."""
    path = CORPUS / f"naukri_{day.isoformat()}_{ROLES[role]}.jsonl"
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return sum(1 for r in rows if r["u"] not in seen)


def write_manifest(day, new_today, refreshed):
    path = CORPUS / "manifest.json"
    old = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    same_day = old.get("updated") == day.isoformat()
    path.write_text(json.dumps({
        "updated": day.isoformat(),
        "new_today": new_today + (old.get("new_today", 0) if same_day else 0),
        "roles_refreshed": sorted(set(refreshed) | (set(old.get("roles_refreshed", [])) if same_day else set())),
    }, indent=1), encoding="utf-8")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--plan", action="store_true", help="print today's batch and exit")
    p.add_argument("--roles", help="comma-separated role families instead of today's batch")
    a = p.parse_args(argv)
    day = dt.date.today()
    roles = [r.strip() for r in a.roles.split(",")] if a.roles else todays_batch(day)
    unknown = [r for r in roles if r not in ROLES]
    if unknown:
        sys.exit(f"unknown roles: {unknown}")
    print(f"{day}: {roles}")
    if a.plan:
        return 0
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        sys.exit("FIRECRAWL_API_KEY is not set")
    seen, new_total, done = known_urls(), 0, []
    for role in roles:
        try:
            rows = to_rows(role, fetch(role, key), day)
        except Exception as e:  # one role failing must not stop the others
            print(f"  {role}: FAILED ({type(e).__name__})")
            continue
        if len(rows) < 5:  # keep the previous snapshot rather than shrink a role to a handful
            print(f"  {role}: only {len(rows)} usable postings, kept previous data")
            continue
        new = save(role, rows, day, seen)
        new_total += new
        done.append(role)
        print(f"  {role}: {len(rows)} postings, {new} new")
    if done:
        write_manifest(day, new_total, done)
    return 0 if done else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.exit(main())
