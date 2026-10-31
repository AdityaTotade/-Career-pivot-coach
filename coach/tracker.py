"""7. Application tracker that learns which kinds of roles get responses.

Each application has features (lane, source, work_model, role_family, tailored) and an
outcome. learn() gives a smoothed response rate per feature value and its lift over the
overall rate, so the coach can say "apply more to X, less to Y" with the sample size shown.
"""
import csv
import re

FEATURES = ("lane", "role_family", "source", "work_model", "tailored")
RESPONSE = {"replied", "interview", "rejected", "offer"}  # any human answer counts
ROLE_FAMILIES = [
    ("founder's office", ["founder"]),
    ("business analyst", ["business analyst", " ba "]),
    ("operations", ["operations", "ops"]),
    ("zoho/crm", ["zoho", "crm"]),
    ("supply chain", ["supply", "logistics", "procurement"]),
    ("policy/research", ["policy", "research", "governance"]),
    ("strategy/consulting", ["strategy", "consult"]),
]


def role_family(role):
    low = f" {role.lower()} "
    return next((fam for fam, cues in ROLE_FAMILIES if any(c in low for c in cues)), "other")


def learn(apps, min_n=3):
    """apps: dicts with FEATURES + 'responded' (bool). Returns overall rate and ranked insights."""
    n = len(apps)
    if not n:
        return {"n": 0, "overall": 0, "insights": []}
    overall = sum(a["responded"] for a in apps) / n
    insights = []
    for feat in FEATURES:
        groups = {}
        for a in apps:
            groups.setdefault(str(a.get(feat, "unknown")), []).append(a["responded"])
        for value, outs in groups.items():
            if len(outs) < min_n:
                continue
            # Laplace-style smoothing toward the overall rate so tiny groups don't dominate
            rate = (sum(outs) + 2 * overall) / (len(outs) + 2)
            insights.append({"feature": feat, "value": value, "n": len(outs), "responses": sum(outs),
                             "rate": round(rate, 2), "lift": round(rate / overall, 2) if overall else 0})
    insights.sort(key=lambda i: -i["lift"])
    return {"n": n, "overall": round(overall, 2), "insights": insights}


def recommend(model, top=3):
    good = [i for i in model["insights"] if i["lift"] > 1.1][:top]
    weak = [i for i in reversed(model["insights"]) if i["lift"] < 0.9][:top]
    say = lambda i: f"{i['feature']} = {i['value']} ({i['responses']}/{i['n']} responded)"
    return {"do_more": [say(i) for i in good], "do_less": [say(i) for i in weak]}


# Importer for a personal job-search tracker (read-only; output stays in active/, never in git)
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def _source(s):
    low = s.lower()
    for key in ("indeed", "naukri", "linkedin", "cold email", "jobdatalake", "job-hunt-cycle"):
        if key in low:
            return "job cycle (mixed)" if key == "job-hunt-cycle" else key
    return "other"


def _work(s):
    low = s.lower()
    return "remote" if "remote" in low else "hybrid" if "hybrid" in low else "on-site" if "on-site" in low else "unknown"


def import_career_os(tracker_csv, contact_status_csv):
    with open(contact_status_csv, newline="", encoding="utf-8-sig") as f:
        status = {_norm(r["company"]): r["status"] for r in csv.DictReader(f)}
    apps = []
    with open(tracker_csv, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            st = r["Status"].lower()
            if "applied" not in st or "not applied" in st:
                continue  # bounced / never sent are not applications
            reply = status.get(_norm(r["Company"]), "")
            responded = reply in RESPONSE or "rejected" in r["Outcome"].lower()
            apps.append({
                "id": r["Opportunity ID"], "company": r["Company"], "role": r["Role"],
                "lane": (re.match(r"[A-E]", r["Lane"].strip()) or [None])[0] or "unknown",
                "role_family": role_family(r["Role"]),
                "source": _source(r["Source"]),
                "work_model": _work(r["Work Model"]),
                "tailored": "yes" if "tailor" in r["Resume Version"].lower() or "_20261" in r["Resume Version"] else "no",
                "responded": responded,
            })
    return apps
