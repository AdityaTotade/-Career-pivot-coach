"""Career pivot coach engine. Brief items 1-6:
intake -> skill-gap map (real postings, via market.py) -> weekly plan -> portfolio projects
-> mock interview -> progress replan. Item 7 (application tracker) is in tracker.py.
"""
import re

from coach import market

# How to learn each skill in a week (free resources, one artefact). Unknown skills get a generic line.
HINTS = {
    "sql": "SQLBolt, then 20 queries on a public dataset (Kaggle) saved to GitHub",
    "excel": "Rebuild one real report with pivots, XLOOKUP and a chart",
    "business intelligence": "Power BI free desktop: one dashboard on a public dataset, published",
    "dashboards": "Design one dashboard that answers three named business questions",
    "data visualization": "Recreate two charts from a news story; write what each one shows",
    "data analysis": "One end-to-end write-up: question, data, method, finding, limits",
    "python": "Python for Everybody (free), then automate one manual task",
    "machine learning": "Kaggle Learn intro to ML; one model with a baseline and an honest score",
    "ai / llm": "Build one small LLM workflow with a human approval step",
    "django": "Django official tutorial (polls app), then add one feature of your own",
    "flask": "Flask quickstart; ship a two-endpoint API",
    "fastapi": "FastAPI tutorial; one API with validation and auto docs",
    "rest api": "Design and document 4 REST endpoints (OpenAPI), then build them",
    "orm": "Model three related tables with SQLAlchemy; write two joins through the ORM",
    "docker": "Docker's getting-started guide; containerise a small app (yours, or their sample) and run it with docker compose",
    "cloud": "Deploy one small app on a free cloud tier and note the cost",
    "testing": "Write pytest tests for your project until coverage passes 70%",
    "requirements gathering": "Interview one real user; write 10 requirements with acceptance criteria",
    "brd / frd": "Write a BRD and 10 user stories for an app you use daily",
    "business analysis": "IIBA BABOK overview; do one as-is / to-be analysis",
    "agile / scrum": "Scrum Guide (free); run two one-week sprints on your project",
    "project management": "Plan one real initiative: scope, schedule, RAID log",
    "program management": "Map 3 related projects into one programme plan with dependencies",
    "pmo": "Build a PMO status template: RAG, risks, decisions, next steps",
    "stakeholder management": "Make a stakeholder map and a weekly update for a real project",
    "budget / cost management": "Build a project budget with a variance tracker",
    "product management": "Write a one-page product brief for a feature you'd ship",
    "product strategy": "Write a strategy memo: user, problem, bet, metric",
    "product roadmap": "Turn the strategy into a now / next / later roadmap",
    "product lifecycle": "Trace one product from launch to sunset; write the decisions at each stage",
    "product launch": "Plan a launch: audience, message, channel, success metric",
    "market research": "Run a 10-person survey and a 3-competitor scan; summarise in 2 pages",
    "seo": "Google SEO starter guide; audit one live site and fix 5 issues",
    "google ads": "Google Skillshop Search Ads certificate (free)",
    "social media marketing": "Run a 2-week content calendar on one channel and report reach",
    "content writing": "Publish 3 posts or blogs for a real audience; track engagement",
    "digital marketing": "Google Digital Garage fundamentals (free)",
    "supply chain": "Map one product's supply chain end to end with lead times",
    "inventory management": "Build a reorder-point model in Excel with safety stock",
    "reconciliation": "Reconcile two exported statements in Excel; document the breaks",
    "process improvement": "Map one process as-is / to-be and measure the time saved",
    "erp / sap": "Learn one ERP's order-to-cash flow; document it with screenshots",
    "ui design": "Redesign three screens of an app you use; explain each change",
    "ux design": "Google UX Design course (audit free); write one case study: problem, research, design, test",
    "figma": "Figma's free beginner course; rebuild one real screen pixel-perfect with auto layout",
    "adobe xd": "Recreate one Figma screen in Adobe XD to learn its prototyping panel",
    "adobe suite": "Make one set of icons and a banner in Illustrator / Photoshop",
    "prototyping": "Turn a wireframe into a clickable Figma prototype with 5 linked screens",
    "user research": "Interview 5 users and run one 5-task usability test; write the findings",
    "design thinking": "Run a one-day design sprint on a real problem (IDEO / GV method)",
    "html / css": "freeCodeCamp Responsive Web Design; build one of your designs in HTML/CSS",
    "javascript": "javascript.info basics; add one interaction to your HTML prototype",
    "react": "React official tutorial (react.dev); build a 3-page app with routing",
    "angular": "Angular Tour of Heroes tutorial; extend it with one API call",
    "node.js": "Node.js + Express: build and document a small REST API",
    "full stack": "Ship one app end to end: React front, Node or Python API, a database, deployed",
    ".net / c#": "Microsoft Learn C# path (free); build a Web API with ASP.NET Core",
    "java": "Java MOOC (University of Helsinki, free) parts 1–7",
    "spring boot": "Spring Boot guides: build a REST service with JPA and tests",
    "microservices": "Split one app into two services that talk over REST; draw the diagram",
    "hibernate": "Map three related entities with JPA/Hibernate; write two queries",
    "kubernetes": "Kubernetes basics tutorial; deploy a containerised app (last week's, or a sample image) on minikube",
    "jenkins": "Set up a Jenkins (or GitHub Actions) pipeline that builds and tests on every push",
    "infrastructure as code": "Terraform tutorial: create and destroy one cloud resource from code",
    "git": "Learn Git Branching (interactive); use pull requests on your own repo",
    "test automation": "Selenium WebDriver: automate 10 test cases for a public demo site",
    "deep learning": "fast.ai Practical Deep Learning lesson 1–3; train one image or text model",
    "data science": "Kaggle Learn track; one notebook from question to honest conclusion",
    "algorithms": "NeetCode / LeetCode easy set: 20 problems with written reasoning",
    "statistics": "Khan Academy statistics; redo one analysis with confidence intervals",
    "product analytics": "Mixpanel or GA4 demo data: build a funnel and a retention chart, write 3 insights",
    "financial analysis": "Analyse one listed company's annual report: ratios, trends, a one-page view",
    "financial reporting": "Build a monthly MIS pack in Excel from a trial balance",
    "fp&a / budgeting": "Build a 12-month budget vs actual with variance commentary",
    "financial modelling": "Build a three-statement model and a DCF for one listed company",
    "finance / accounting": "Record a month of sample transactions to a trial balance (Tally or Zoho Books trial)",
    "sales": "Write a call script and run 20 practice calls or messages; log objections",
    "business development": "Pick one industry; list 30 target accounts with a reason each",
    "lead generation": "Build a 50-lead list from public sources with a qualification score",
    "customer retention": "Design a churn early-warning list for a SaaS product from usage signals",
    "customer success": "Write a customer success playbook: onboarding, health score, QBR template",
    "upsell / cross-sell": "Map upgrade triggers for one product and draft the outreach for each",
    "client onboarding": "Design a 30-day onboarding checklist with success milestones",
    "creative writing": "Write 5 short pieces for different formats (ad, script, story post)",
    "editing / proofreading": "Edit 5 published articles; show tracked changes and why",
    "content strategy": "Plan a 4-week content calendar tied to one business goal",
    "graphic design": "Make a brand kit: logo usage, colours, type, 3 social posts and 1 print piece",
    "corel draw": "CorelDRAW basics: recreate one print label or brochure",
    "motion graphics / video": "Make a 15-second animated post in Premiere or After Effects",
    "canva": "Build 5 templates in Canva for one brand",
    "recruitment": "Run a mock hiring funnel for one role: JD, sourcing plan, screening sheet",
    "talent acquisition": "Source 30 profiles on LinkedIn for one JD with Boolean search; log the strings",
    "screening / interviewing": "Write a 10-question structured interview with a scoring rubric",
    "hr operations": "Map hire-to-onboard steps and the HRIS fields each one needs",
    "audit / compliance": "Pick one process; write its controls, test 10 samples, log exceptions",
    "automation": "Automate one repeated task with Apps Script, Power Automate or n8n; time the saving",
    "ci/cd": "GitHub Actions quickstart: build, test and deploy one repo on every push",
    "crm / zoho": "Zoho CRM or HubSpot free tier: set up a pipeline, fields and two automations",
    "forecasting": "Forecast 12 months of public sales data three ways; compare errors",
    "payments": "Map a card or UPI payment end to end: parties, messages, settlement, failure points",
    "problem solving": "Solve 5 case questions (Case in Point style) and write the structure for each",
    "procurement": "Run a mock RFQ: 3 suppliers, comparison sheet, negotiation notes",
    "product marketing": "Write positioning, a launch message and a one-page battlecard for one product",
    "reporting": "Rebuild one weekly report so it answers three named questions in one page",
    "software engineering": "Read 'The Missing Semester' (MIT, free); apply version control, testing and debugging to a project",
    "feature writing": "Write two 800-word features with interviews or sources; get one published on a blog or Medium",
    "banking operation":"Map one banking process (account opening, KYC or payments) end to end: steps, checks, failure points",
    "service delivery": "Write an SLA and a weekly service report (volumes, breaches, causes, fixes) for a process you know",
    "data management": "Clean and document one messy public dataset: data dictionary, checks, and a before / after",
    "account opening": "Walk through a bank's account-opening + KYC flow and list the checks at each step",
    "communication":"Turn one piece of your work into a 5-slide deck and a one-page memo; present it to a friend for 5 minutes",
    "team management":"Write a 1:1 template, a RACI and a weekly team update for a real project",
}


GENERAL = {"capstone", "portfolio project"}  # weeks that are about the whole role, not one skill


def hint(skill):
    return HINTS.get(skill, f"One free course on {skill}, then use it in your portfolio project")


# 1. Intake
def _evidence(text, phrase):
    for sent in re.split(r"(?<=[.!?\n])\s+", text):
        if re.search(r"(?<![a-z0-9])" + re.escape(phrase) + r"(?![a-z0-9])", sent.lower()):
            return sent.strip()[:180]
    return ""


_GOAL = re.compile(r"\b(want|wants|wanting|hope|aim|aiming|target|goal|looking for|move into|moving into|switch|transition|pivot|aspire|interested in)\b", re.I)


def experience_only(resume_text, target_role):
    """Cut the goal part of each sentence ("...and I want to move into a Product Analyst role") so wishes
    don't count as evidence, but keep the experience written before it in the same sentence."""
    kept = []
    for sent in re.split(r"(?<=[.!?\n])\s+", resume_text):
        m = _GOAL.search(sent)
        if m:
            sent = sent[:m.start()]
        if target_role.strip():
            sent = re.sub(re.escape(target_role.strip()), " ", sent, flags=re.I)
        kept.append(sent)
    return " ".join(kept)


def intake(resume_text, target_role, hours_per_week=8, weeks=8):
    resume_text = experience_only(resume_text, target_role)
    found = market.resume_skills(resume_text)
    return {
        "target_role": target_role.strip(),
        "hours_per_week": max(2, int(hours_per_week)),
        "weeks": max(3, int(weeks)),
        "skills": sorted(found),
        "evidence": {s: _evidence(resume_text, p) for s, p in found.items()},
    }


# 2. Skill-gap map from real postings
def gap_map(profile, mkt, min_share=0.1):
    prof = mkt.role_profile(profile["target_role"])
    if not prof["ok"]:
        return {**prof, "rows": []}
    implied = {s: src for src in profile["skills"] for s in IMPLIES.get(src, ())}
    rows = []
    for r in prof["rows"]:
        if r["share"] < min_share:
            continue
        direct = r["skill"] in profile["skills"]
        rows.append({**r, "have": direct or r["skill"] in implied, "soft": r["skill"] in SOFT,
                     "evidence": profile["evidence"].get(r["skill"], "") if direct
                     else (f"Implied by your {implied[r['skill']]} work" if r["skill"] in implied else "")})
    have = [r for r in rows if r["have"]]
    coverage = sum(r["share"] for r in have) / max(1e-9, sum(r["share"] for r in rows))
    return {**prof, "rows": rows, "coverage": round(coverage, 2)}


# Doing one skill is evidence of another (building Power BI dashboards is data visualisation).
IMPLIES = {
    "business intelligence": ("data visualization", "dashboards", "reporting"),
    "dashboards": ("data visualization", "reporting"),
    "financial reporting": ("reporting",),
    "machine learning": ("statistics", "data analysis"),
    "deep learning": ("machine learning",),
    "financial modelling": ("financial analysis", "excel"),
    "full stack": ("javascript", "html / css"),
    "spring boot": ("java",),
    "django": ("python",), "flask": ("python",), "fastapi": ("python",),
    "kubernetes": ("docker",),
    "test automation": ("testing",),
}
# Real asks, but you show them in interviews rather than spend a learning week on them
SOFT = {"problem solving", "communication", "stakeholder management", "team management", "customer service"}


def gaps(gmap):
    """Skills to learn: signature ones first (they define the role), then by share. Soft skills are not weeks."""
    return sorted((r for r in gmap["rows"] if not r["have"] and r["skill"] not in SOFT),
                  key=lambda r: (-r["signature"], -r["share"]))


# 3. Week-by-week plan: one main gap per week, biggest first
def build_plan(profile, gmap):
    missing = gaps(gmap)
    if not missing:
        return []
    h, slots = profile["hours_per_week"], profile["weeks"] - 1  # last week is the capstone
    queue = []
    for i, g in enumerate(missing):
        queue.append((g, "learn"))
        if i < 2:
            queue.append((g, "apply"))  # top two gaps get a second week to use what was learnt
    queue = queue[:slots]
    # Split the weekly hours roughly 40 / 40 / 20 and never exceed the budget (2h -> 1+0+1, 3h -> 1+1+1)
    learn_h = max(1, round(h * 0.4))
    practise_h = max(0, h - learn_h - max(1, round(h * 0.2)))
    interview_h = h - learn_h - practise_h
    weeks = []
    for n, (g, mode) in enumerate(queue, start=1):
        apply = mode == "apply"
        weeks.append({
            "week": n, "skill": g["skill"], "mode": mode, "hours": h, "status": "todo",
            "goal": (f"Use {g['skill']} in project 1 (see Projects below)" if apply
                     else f"Learn {g['skill']}: asked in {round(g['share'] * 100)}% of {profile['target_role']} postings"),
            "tasks": [t for t in [
                f"{learn_h}h · " + (f"add {g['skill']} work to project 1 (see Projects)" if apply else hint(g["skill"])),
                f"{practise_h}h · " + ("write it up: what you built, one before / after, one number" if apply
                                       else f"use {g['skill']} on one real task from your current or last job; keep the output as proof")
                if practise_h else "",
                f"{interview_h}h · answer this week's interview question on {g['skill']} below and aim for 60+"] if t],
        })
    while len(weeks) < slots:  # few gaps: spend the spare weeks building proof
        weeks.append({"week": len(weeks) + 1, "skill": "portfolio project", "mode": "build", "hours": h, "status": "todo",
                      "goal": "Build the top portfolio project below, using what you learnt",
                      "tasks": [f"{h - 1}h · build the next part of the project", "1h · write down what you'd show an interviewer"]})
    weeks.append({"week": len(weeks) + 1, "skill": "capstone", "mode": "ship", "hours": h, "status": "todo",
                  "goal": "Publish the top project and run a full mock interview",
                  "tasks": [f"{h}h · ship it, write it up, link it on your CV and LinkedIn"]})
    return weeks


# 4. Portfolio projects matched to gaps (greedy cover weighted by share)
PROJECTS = [
    {"title": "End-to-end UX case study for a real app", "covers": {"ux design", "ui design", "user research", "prototyping", "figma", "design thinking", "adobe xd", "mobile app design"},
     "deliverable": "Case study: research notes, wireframes, Figma prototype, usability-test results"},
    {"title": "Design-to-code: one screen shipped in HTML / CSS", "covers": {"html / css", "javascript", "ui design", "adobe suite", "figma"},
     "deliverable": "Live page built from your own design, linked from the case study"},
    {"title": "Ops KPI dashboard for a small business", "covers": {"business intelligence", "dashboards", "excel", "sql", "data analysis", "data visualization", "reporting"},
     "deliverable": "Published dashboard + a one-page memo on three decisions it supports"},
    {"title": "As-is / to-be process redesign with a BRD", "covers": {"business analysis", "requirements gathering", "brd / frd", "process improvement", "stakeholder management", "testing"},
     "deliverable": "Process maps, BRD, 10 user stories, a UAT test plan"},
    {"title": "REST API with tests and a container", "covers": {"python", "django", "flask", "fastapi", "rest api", "orm", "sql", "testing", "docker", "ci/cd"},
     "deliverable": "GitHub repo: API, tests, Dockerfile, README with run steps"},
    {"title": "Small data pipeline into a dashboard", "covers": {"python", "etl / data engineering", "sql", "business intelligence", "data analysis", "cloud"},
     "deliverable": "Scheduled script that loads public data into a database and a dashboard on top"},
    {"title": "Honest ML baseline on a public dataset", "covers": {"machine learning", "python", "statistics", "data analysis", "forecasting"},
     "deliverable": "Notebook with a baseline, one model, and what it can't do"},
    {"title": "Bounded AI workflow: AI drafts, rules check, human approves", "covers": {"ai / llm", "automation", "python", "process improvement", "rest api"},
     "deliverable": "Working script with an approval step and a test log"},
    {"title": "Product teardown with a strategy memo and roadmap", "covers": {"product management", "product strategy", "product roadmap", "product lifecycle", "product launch", "market research", "brd / frd"},
     "deliverable": "Teardown, one-page strategy memo, now / next / later roadmap"},
    {"title": "Project plan and PMO pack for a real initiative", "covers": {"project management", "program management", "pmo", "stakeholder management", "agile / scrum", "risk management", "budget / cost management"},
     "deliverable": "Charter, schedule, RAID log, weekly status report"},
    {"title": "Live mini campaign with a results report", "covers": {"digital marketing", "seo", "google ads", "social media marketing", "content writing", "product marketing", "market research"},
     "deliverable": "Two-week campaign for a real page, with a reach and conversion report"},
    {"title": "Inventory reorder and supplier model", "covers": {"supply chain", "inventory management", "procurement", "excel", "forecasting", "erp / sap", "order management"},
     "deliverable": "Reorder-point model with safety stock and a supplier scorecard"},
    {"title": "Spring Boot microservice with tests", "covers": {"java", "spring boot", "microservices", "hibernate", "rest api", "maven", "testing", "sql"},
     "deliverable": "Two services, JPA persistence, JUnit tests, README with an architecture diagram"},
    {"title": "Full-stack app, deployed", "covers": {"full stack", "react", "angular", "node.js", ".net / c#", "javascript", "html / css", "sql", "cloud"},
     "deliverable": "Live URL, repo, and a short write-up of one hard bug you fixed"},
    {"title": "CI/CD pipeline from commit to cloud", "covers": {"ci/cd", "docker", "kubernetes", "jenkins", "infrastructure as code", "git", "cloud", "unix / shell"},
     "deliverable": "Repo where every push builds, tests and deploys; Terraform for the infra"},
    {"title": "Automated test suite for a public web app", "covers": {"testing", "test automation", "agile / scrum", "git", "ci/cd"},
     "deliverable": "Selenium suite with 20+ cases, a bug report, and a CI run log"},
    {"title": "Product funnel and A/B test readout", "covers": {"product analytics", "business intelligence", "sql", "data analysis", "statistics", "dashboards", "business analysis"},
     "deliverable": "Funnel, retention cohort and one experiment design in a 5-slide readout"},
    {"title": "Company financial model and FP&A pack", "covers": {"financial modelling", "financial analysis", "fp&a / budgeting", "financial reporting", "excel", "finance / accounting"},
     "deliverable": "Three-statement model, DCF, budget-vs-actual with commentary"},
    {"title": "30-day sales pipeline sprint", "covers": {"sales", "business development", "lead generation", "crm / zoho", "communication"},
     "deliverable": "50 qualified leads, scripts, a CRM pipeline and a conversion report"},
    {"title": "Customer success playbook", "covers": {"customer success", "customer retention", "upsell / cross-sell", "client onboarding", "customer service", "crm / zoho"},
     "deliverable": "Onboarding plan, health score model, QBR template, churn-save script"},
    {"title": "Writing portfolio with results", "covers": {"content writing", "creative writing", "editing / proofreading", "content strategy", "seo"},
     "deliverable": "6 published pieces across formats, one SEO article with ranking notes"},
    {"title": "Brand kit and campaign creatives", "covers": {"graphic design", "adobe suite", "corel draw", "motion graphics / video", "canva", "social media marketing"},
     "deliverable": "Brand guide, 6 social posts, 1 print piece, 1 short animation"},
    {"title": "Hiring funnel for one real role", "covers": {"recruitment", "talent acquisition", "screening / interviewing", "hr operations", "stakeholder management"},
     "deliverable": "JD, sourcing strings, screening rubric, funnel metrics sheet"},
    {"title": "Reconciliation and ops-reporting automation", "covers": {"reconciliation", "excel", "reporting", "payments", "audit / compliance", "automation", "sql"},
     "deliverable": "Script or workbook that reconciles two files and reports the breaks"},
]


def related(skill):
    """Skills that sit in the same portfolio project as this one (Jenkins is related to CI/CD)."""
    return {s for p in PROJECTS if skill in p["covers"] for s in p["covers"]} - {skill}


def suggest_projects(gmap, k=3):
    left = {g["skill"]: g["share"] * (1.5 if g["signature"] else 1) for g in gaps(gmap)}
    picks = []
    for _ in range(k):
        best = max(PROJECTS, key=lambda p: sum(left.get(s, 0) for s in p["covers"]))
        if sum(left.get(s, 0) for s in best["covers"]) == 0:
            break
        picks.append({"title": best["title"], "deliverable": best["deliverable"],
                      "closes_gaps": sorted(s for s in best["covers"] if s in left)})
        for s in best["covers"]:
            left.pop(s, None)
    return picks


# 5. Mock interview scored against a rubric
RUBRIC = {
    "structure": "Situation, task, action and result are all there (STAR)",
    "specificity": "Names a tool, a number or a concrete output",
    "relevance": "Shows the skill the question is about",
    "ownership": "Says what you did, not only 'we'",
    "length": "80 to 300 words: complete but tight",
}
_STAR = {
    "situation": ["when", " at ", "while", "during", "context", "situation", "the client", "the team", "last year",
                  " i was ", " in my ", " at my ", " our ", "every month", "each month", "every week"],
    "task": ["needed to", "need to", "had to", "goal", "task", "asked to", "responsible", "wanted to", "the problem",
             "the issue", "my job", "deadline", "challenge", "were late", "was late", "piled up"],
    "action": [],  # matched by _ACTION: "I" followed by a past-tense verb
    "result": ["result", "so that", "reduced", "improved", "saved", "led to", "outcome", "increased", "cut ", "%",
               "helped", "fewer", "faster", "on time", "no penalties", "which meant", " so we ", " so the "],
}
_ACTION = re.compile(r"\bi (?:also |then )?(?:\w+ed|built|wrote|ran|made|led|set|took|did|found|gave|got|kept|met|"
                     r"sent|taught|drew|chose|began|brought|caught|fixed|cut|put|sold|spoke|won|ran)\b")


_NUMBER = re.compile(r"\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|twelve|twenty|thirty|fifty|hundred|"
                     r"thousand|lakh|crore|dozen|half|third|quarter|fifth|tenth|double|doubled|tripled|percent|per cent)\b")


def question(skill, target_role):
    if skill in GENERAL:
        return f"Walk me through one project that shows you're ready for a {target_role} role. What would you do differently?"
    return f"Tell me about a time you used {skill}. What was the problem, what did you do, and what changed?"


def score_answer(answer, skill):
    low = " " + re.sub(r"[.,;!?()]", " ", (answer or "").lower()) + " "
    words = len(low.split())
    parts = [p for p, cues in _STAR.items() if any(c in low for c in cues) or (p == "action" and _ACTION.search(low))]
    i_count, we_count = low.count(" i "), low.count(" we ")
    mentioned = market.resume_skills(low)
    scores = {
        "structure": round(5 * len(parts) / 4),
        "specificity": min(5, (2 if _NUMBER.search(low) else 0) + len(mentioned)),
        "relevance": 5 if skill in GENERAL or skill in mentioned else (3 if related(skill) & set(mentioned) else 1),
        "ownership": min(5, 2 + i_count) if i_count >= we_count else 2,
        "length": 5 if 80 <= words <= 300 else (3 if 40 <= words < 80 or 300 < words <= 400 else 1),
    }
    tips = {
        "structure": "Add the missing parts: " + ", ".join(p for p in _STAR if p not in parts) + ".",
        "specificity": "Name the tool and give one real number (time, volume, %, records).",
        "relevance": f"Say plainly where you used {skill}.",
        "ownership": "Say 'I' for your part; keep 'we' for the team.",
        "length": f"Aim for 80–300 words (this was {words}).",
    }
    total = round(sum(scores.values()) / (5 * len(scores)) * 100)
    return {"score": total, "parts": scores, "feedback": [tips[k] for k, v in scores.items() if v < 4]}


# 6. Progress tracking that adjusts the plan
def check_in(plan, week, done, interview_score=None, pass_mark=60):
    """Mark a week; a slipped week repeats and a weak interview adds a review week."""
    plan = [dict(w) for w in plan]
    cur = next(w for w in plan if w["week"] == week)
    changes = []
    cur["status"] = "done" if done else "slipped"
    if not done:
        changes.append(f"Week {week} ({cur['skill']}) slipped, so it repeats next week.")
    elif interview_score is not None and interview_score < pass_mark and cur["skill"] not in GENERAL:
        changes.append(f"Interview scored {interview_score} on {cur['skill']} (under {pass_mark}), so a review week was added.")
    if changes:
        redo = {**cur, "status": "todo"}
        if done:
            redo.update(mode="review", goal=f"Review {cur['skill']}: redo the mock answer until it scores {pass_mark}+")
        plan.insert(plan.index(cur) + 1, redo)
        for n, w in enumerate(plan, start=1):
            w["week"] = n
    return plan, changes
