"""Market model learnt from real job postings (corpus/*.jsonl, Naukri, Oct 2026).

"Training" here is deterministic and inspectable:
1. Normalise every posted skill tag (lower-case, merge synonyms, drop filler tags).
2. Keep tags seen in 2+ postings as the skill vocabulary.
3. For a target role, pick postings whose role/title words match, then rank skills by
   share of those postings, and mark "signature" skills whose share is far above the
   whole-market share (lift), so each role gets its own profile.
"""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = ROOT / "corpus"
MIN_JOBS = 5

ALIASES = {
    "sql": ["sql", "advance sql", "advanced sql", "mysql", "sql server", "postgresql", "queries"],
    "excel": ["excel", "advanced excel", "ms excel", "spreadsheet", "pivot", "vlookup", "vba", "macros"],
    "business intelligence": ["power bi", "bi tools", "bi", "business intelligence", "business intelligence reporting", "tableau", "qlikview", "looker"],
    "dashboards": ["dashboards", "dashboard development", "dashboard", "mis report"],
    "data visualization": ["data visualization", "data visualisation"],
    "data analysis": ["data analysis", "data analytics", "insight generation", "analyse data", "analyzed", "analysed"],
    "python": ["python", "python development", "python framework", "pandas", "numpy"],
    "machine learning": ["machine learning", "ml", "aiml", "scikit-learn", "predictive modeling", "regression", "decision tree", "logistic regression"],
    "ai / llm": ["artificial intelligence", "ai", "llm", "genai", "ai solutions", "chatgpt", "claude"],
    "statistics": ["statistics", "multivariate analysis", "mathematics"],
    "django": ["django", "django framework", "django rest api"],
    "flask": ["flask"],
    "fastapi": ["fast api", "fastapi"],
    "rest api": ["rest", "rest api", "rest api services", "api", "api development"],
    "message queues": ["rabbitmq", "kafka", "message queue", "message queue - rabitmq", "queue"],
    "orm": ["orm", "sqlalchemy"],
    "docker": ["docker"],
    "cloud": ["aws", "cloud", "cloud platform", "azure", "serverless"],
    "ci/cd": ["continuous integration", "ci/cd", "devops", "azure devops"],
    "testing": ["pytest", "unit testing", "debugging", "code quality", "test cases", "uat"],
    "unix / shell": ["unix", "shell scripting", "scripting", "linux"],
    "oops": ["oops", "oops programming"],
    "mongodb": ["mongodb"],
    "etl / data engineering": ["etl", "data engineering", "data warehousing", "data integration", "warehouse"],
    "requirements gathering": ["requirements", "requirement gathering", "requirement analysis", "gap analysis", "scoping"],
    "brd / frd": ["brd", "frd", "srs", "user stories"],
    "business analysis": ["business analysis", "business analyst", "it business analysis", "business analytics"],
    "agile / scrum": ["agile", "scrum", "agile methodology", "csm", "sprint", "jira"],
    "project management": ["project management", "project coordination", "project control", "program and project management", "project delivery", "ms project", "project scheduling", "scheduling", "timelines"],
    "program management": ["program management", "program delivery", "program governance", "delivery management", "program development"],
    "pmo": ["pmo", "pmo management", "project management office", "project governance"],
    "stakeholder management": ["stakeholder management", "stakeholder", "coordination", "client relationship", "cross-functional", "coordinated"],
    "budget / cost management": ["budget management", "cost management", "cost reduction", "cost variance analysis"],
    "risk management": ["risk management", "risk"],
    "product management": ["product management", "product development", "saas product development"],
    "product strategy": ["product strategy", "vision", "product positioning", "positioning"],
    "product roadmap": ["product roadmap", "roadmap"],
    "product lifecycle": ["product life cycle", "life cycle management", "product life cycle management", "life cycle"],
    "product launch": ["product launch", "launch", "rollout"],
    "product marketing": ["product marketing", "branding", "brand strategy", "brand campaigns", "online branding", "digital branding"],
    "market research": ["market research", "market intelligence", "primary research", "trend analysis", "consumer research", "competitor"],
    "seo": ["seo", "search engine optimization", "page seo", "link building", "keyword research", "organic search"],
    "google ads": ["google ads", "adwords", "google adwords", "google marketing", "display advertising", "internet advertising"],
    "social media marketing": ["social media marketing", "social media", "media marketing", "social media optimization", "meta ads", "instagram ads", "facebook", "instagram", "youtube marketing"],
    "content writing": ["content writing", "web content writing", "blog writing", "content creation", "content planning", "writing"],
    "digital marketing": ["digital marketing", "online marketing", "internet marketing", "web promotion", "website promotion", "marketing campaigns", "campaigns"],
    "reporting": ["reporting", "business reporting", "regulatory reporting", "project reports"],
    "reconciliation": ["reconciliation", "settlements"],
    "payments": ["payments", "payment operations", "payment processing", "card operations"],
    "audit / compliance": ["external audit", "auditing", "compliance", "audit", "audits", "internal audit", "statutory audit"],
    "finance / accounting": ["finance", "accounting entries", "financial statements", "cash flow", "taxation",
                             "accounting", "accounts", "accountant", "tally", "tally erp", "tally prime", "gst", "gst returns", "tds",
                             "bookkeeping", "book keeping", "journal entries", "ledger", "ledgers", "trial balance", "bank reconciliation",
                             "accounts payable", "accounts receivable", "general ledger", "general ledger accounting", "payables",
                             "receivable", "invoice processing", "revenue recognition", "ledger scrutiny", "consolidation of accounts"],
    "customer service": ["customer service", "customer support", "customer operations", "customer experience", "customer satisfaction"],
    "process improvement": ["process improvement", "improvement", "operational excellence", "process mapping", "workflow", "sop", "sops", "bottleneck"],
    "supply chain": ["supply chain", "supply chain management", "supply chain planning", "logistics", "distribution", "shipment", "warehouse operations"],
    "inventory management": ["inventory", "inventory management", "inventory planning", "inventory optimization"],
    "procurement": ["procurement", "purchase", "purchase order", "po", "negotiation", "vendor"],
    "order management": ["order management", "order processing", "order fulfillment"],
    "erp / sap": ["sap", "sap hana", "oracle", "erp", "d365"],
    "forecasting": ["forecasting", "forecasts", "predictive"],
    "communication": ["communication skills", "powerpoint", "presentation", "decks"],
    "problem solving": ["problem solving", "analytical", "troubleshooting"],
    "team management": ["team management", "team handling", "team leading", "leadership"],
    "crm / zoho": ["crm", "zoho", "salesforce", "hubspot"],
    "automation": ["automation", "rpa", "apps script", "zapier", "n8n"],
    "ui design": ["ui", "user interface designing", "interface design", "interfaces", "visual design"],
    "ux design": ["ux", "ux design", "ui/ux", "ui and ux", "ui ux", "user experience"],
    "figma": ["figma"],
    "adobe xd": ["adobe xd", "xd"],
    "adobe suite": ["adobe", "adobe creative suite", "photoshop", "illustrator", "indesign"],
    "prototyping": ["prototyping", "prototype", "wireframe", "wireframes", "wireframing", "sketching"],
    "user research": ["user research", "usability testing", "usability", "human computer interaction", "user interviews"],
    "design thinking": ["design thinking"],
    "html / css": ["html", "css", "cs", "front end"],
    "javascript": ["javascript", "typescript"],
    "mobile app design": ["mobile application design", "mobile applications"],
    # Engineering
    "react": ["react.js", "react", "react js", "nextjs", "next.js"],
    "angular": ["angular", "angularjs"],
    "node.js": ["node.js", "node", "nodejs"],
    "full stack": ["full stack", "fullstack development", "java fullstack", "full stack development"],
    ".net / c#": ["c#", ".net", ".net core", "asp.net core", "asp.net mvc", "asp.net", "mvc"],
    "java": ["java", "java development", "core java development", "j2ee", "j2ee development", "jsp", "jsp servlets", "struts", "core java"],
    "spring boot": ["spring boot", "spring", "java spring boot", "springboot java", "spring mvc"],
    "microservices": ["microservices"],
    "hibernate": ["hibernate"],
    "maven": ["maven"],
    "kubernetes": ["kubernetes", "container orchestration", "orchestration", "aks", "azure kubernetes service", "azure kubernetes", "swarm"],
    "jenkins": ["jenkins", "devops jenkins"],
    "infrastructure as code": ["terraform", "ansible"],
    "git": ["git", "gitlab", "github"],
    "test automation": ["automation testing", "selenium", "appium"],
    # Data science
    "deep learning": ["deep learning"],
    "data science": ["data science"],
    "algorithms": ["algorithms"],
    "data modeling": ["data modeling", "data modelling"],
    # Product analytics
    "product analytics": ["product analysis", "product analyst", "mixpanel", "amplitude", "adobe analytics", "google analytics", "heap", "ab testing", "a/b testing", "a/b test"],
    # Finance
    "financial analysis": ["financial analysis", "financial skills"],
    "financial reporting": ["financial reporting", "management reporting", "data reporting", "mis"],
    "fp&a / budgeting": ["fpa", "fp&a", "financial planning", "financial planning and analysis", "budgeting", "financial forecasting", "revenue forecasting", "variance analysis"],
    "financial modelling": ["finance modelling", "financial modelling", "financial modeling", "dcf", "dcf valuation", "valuation", "npv", "unit economics", "cac", "ltv", "break-even"],
    # Sales and customer
    "sales": ["sales", "b2b sales", "b2c sales", "inside sales", "product sales", "field sales", "telesales", "direct selling", "software sales", "it sales", "outbound sales", "telemarketing", "cold calling", "channel sales", "presales", "it services sales"],
    "business development": ["business development", "bd", "bde"],
    "lead generation": ["lead generation", "client acquisition", "customer acquisition"],
    "customer retention": ["retention", "customer retention", "client retention", "churn", "churn management", "retention strategies", "renewals"],
    "customer success": ["client success", "customer focus", "customer success", "customer management", "customer engagement", "client engagement", "client account management", "account management", "relationship building", "customer relationship", "customer relationships", "customer life cycle management"],
    "upsell / cross-sell": ["upsell", "cross selling", "cross-selling"],
    "client onboarding": ["client onboarding", "onboarding"],
    # Content and design
    "creative writing": ["creative writing", "copy writing", "copywriting", "script writing", "creative content"],
    "editing / proofreading": ["editing", "content editing", "proof reading", "proofreading", "publishing"],
    "content strategy": ["content strategy", "content marketing", "content management"],
    "graphic design": ["graphics", "graphic designing", "graphic design", "layout", "print design", "printing", "labels", "brochure design", "posters", "signage", "illustration"],
    "corel draw": ["corel draw", "corel"],
    "motion graphics / video": ["motion graphics", "adobe premiere", "premiere pro", "adobe after effects", "aftereffects", "video", "motion"],
    "canva": ["canva"],
    # HR
    "recruitment": ["recruitment", "end to end recruitment", "it recruitment", "non it recruitment", "bulk hiring", "volume hiring", "lateral hiring", "bpo hiring", "sales hiring", "staffing", "recruitment management"],
    "talent acquisition": ["talent acquisition", "talent sourcing", "sourcing", "sourcing profiles"],
    "screening / interviewing": ["screening", "interviewing", "interview coordination", "selection"],
    "hr operations": ["hrsd", "human resource management", "hr processes", "hris", "hcm"],
}
ALIASES["kpis"] = ["kpi", "kpis", "kpi review", "metrics", "okr", "okrs", "scorecard"]
# Extra synonyms found by running a real target user's profile through the coach (2026-10-31)
ALIASES["machine learning"] += ["pytorch", "tensorflow", "keras", "explainable ai", "grad-cam", "cnn", "neural network"]
ALIASES["reporting"] += ["reports", "report", "weekly report", "mis"]
ALIASES["reconciliation"] += ["reconciled", "reconcile", "reconciling"]
ALIASES["project management"] += ["implementation", "implementations", "go-live", "go live", "led the rollout"]
ALIASES["market research"] += ["survey", "surveys", "respondents", "go-to-market study", "benchmarking"]
ALIASES["financial reporting"].remove("mis")
# Extra synonyms for existing skills found in the wider market sweep
ALIASES["testing"] += ["software testing", "manual testing", "software qa", "test engineering", "writing test cases",
                       "bug reporting", "bug life cycle", "test scenarios", "junit"]
ALIASES["ci/cd"] += ["cd", "ci cd pipeline", "pipeline", "continuous delivery", "gitlab ci", "github actions", "azure pipelines", "code deploy"]
ALIASES["docker"] += ["container"]
ALIASES["cloud"] += ["microsoft azure", "aws services", "aws cloud", "cloud technologies", "amazon ec2", "cloud native"]
ALIASES["rest api"] += ["web api", "rest api development"]
ALIASES["statistics"] += ["statistical analysis", "statistical modeling"]
ALIASES["data analysis"] += ["data mining", "data interpretation", "data wrangling"]
ALIASES["seo"] += ["seo writing"]
ALIASES["content writing"] += ["articles", "blogs", "web content", "content development", "article writing", "english writing", "written communication"]
ALIASES["adobe suite"] += ["image editing", "retouching"]
ALIASES["etl / data engineering"] += ["etl testing", "data warehouse testing", "dwh testing"]
# Tags too vague to teach anything ("Development", "Management", "Data").
FILLER = {
    "development", "program", "project", "management", "data", "analysis", "analytics", "tools", "office",
    "intelligence", "coding", "software", "software development", "programming", "process", "processing", "digital",
    "marketing", "media", "supply", "team", "core", "local", "express", "direct", "functional", "change", "delivery",
    "quality", "page", "engine", "gap", "searching", "console", "awareness", "content", "generation", "industrial",
    "application", "system", "technology", "integration", "machine", "languages", "framework", "microsoft", "operations",
    "analytics tool", "planning", "research", "fresher", "remote", "global", "engineering", "control", "administration",
    "brand", "commercial", "design", "creative", "concepts", "methods", "center", "freelancing", "web application",
    "emerging technologies", "creative designing", "architecture", "scalability", "payroll", "sketchup", "automotive design", "enterprise", "usage", "ownership", "monitoring", "internet", "web technologies", "google",
    "ms office", "it systems", "trade", "cost", "cash", "investment", "allocation", "transit", "excellence", "training",
    "end", "end to end", "stack", "boot", "bootstrap", "client", "science", "acquisition", "hiring", "english", "draw",
    "feedback", "engagement", "advocacy", "modeling", "employee satisfaction", "focus", "key", "case", "pan", "s",
    "automotive", "front", "bulk", "volume", "salary", "resource", "corporate", "consultancy", "incentives", "post",
    "life cycle", "generation", "promotional", "cd/ci", "as", "native", "deployment process", "x", "smart", "mc",
}

_ALIAS_TO_CANON = {a: canon for canon, aliases in ALIASES.items() for a in aliases}
STOP = {"and", "the", "of", "for", "to", "a", "an", "in", "senior", "junior", "associate", "assistant", "lead", "intern",
        "ii", "iii", "executive", "walk", "urgent", "opening", "immediate", "team", "member"}


def canon(tag):
    t = re.sub(r"\s+", " ", tag.strip().lower())
    if t in _ALIAS_TO_CANON:
        return _ALIAS_TO_CANON[t]
    return None if t in FILLER or len(t) < 2 else t


def _words(s):
    return {w for w in re.findall(r"[a-z]+", s.lower()) if w not in STOP}


class Market:
    def __init__(self, jobs):
        self.jobs = []
        for j in jobs:
            skills = sorted({c for c in (canon(s) for s in j.get("s", [])) if c})
            if skills:
                self.jobs.append({**j, "skills": skills})
        counts = Counter(s for j in self.jobs for s in j["skills"])
        self.vocab = {s for s, n in counts.items() if n >= 2}
        self.base_share = {s: counts[s] / len(self.jobs) for s in self.vocab} if self.jobs else {}
        self.roles = Counter(j["q"] for j in self.jobs)

    @classmethod
    def load(cls, folder=CORPUS_DIR, extra_csv=None):
        jobs = []
        for f in sorted(Path(folder).glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    jobs.append(json.loads(line))
        if extra_csv and Path(extra_csv).exists():  # career-OS JDs: free-text key needs, skills read from text
            import csv
            with open(extra_csv, newline="", encoding="utf-8-sig") as fh:
                for r in csv.DictReader(fh):
                    jobs.append({"q": r["role"].lower(), "t": r["role"], "c": r["company"], "e": "",
                                 "l": "", "u": r["source_url"], "s": list(resume_skills(r["jd_key_needs"], prose=False))})
        return cls(jobs)

    @staticmethod
    def _family_score(target_role, family):
        """Domain words ("program", "python") count double; the job noun ("analyst") once."""
        words = [w for w in re.findall(r"[a-z]+", target_role.lower()) if w not in STOP]
        if not words:
            return 0
        fam = _words(family)
        weights = {w: (1 if i == len(words) - 1 and len(words) > 1 else 2) for i, w in enumerate(words)}
        return sum(wt for w, wt in weights.items() if w in fam) / sum(weights.values())

    def match(self, target_role):
        """Postings from the best-matching role families. Returns (jobs, families, exact)."""
        scores = {f: self._family_score(target_role, f) for f in self.roles}
        best = max(scores.values(), default=0)
        if best < 0.5:
            return [], [], False
        families = sorted(f for f, s in scores.items() if s == best)
        return [j for j in self.jobs if j["q"] in families], families, best == 1

    def nearest_roles(self, target_role, k=3):
        return sorted(self.roles, key=lambda r: (-self._family_score(target_role, r), -self.roles[r]))[:k]

    def role_profile(self, target_role):
        jobs, families, exact = self.match(target_role)
        if len(jobs) < MIN_JOBS:
            return {"ok": False, "jd_total": len(jobs), "nearest": self.nearest_roles(target_role),
                    "roles": dict(self.roles)}
        counts = Counter(s for j in jobs for s in j["skills"] if s in self.vocab)
        rows = []
        for skill, n in counts.most_common():
            share = n / len(jobs)
            lift = share / self.base_share[skill]
            rows.append({"skill": skill, "share": round(share, 2), "jd_count": n, "lift": round(lift, 1),
                         "signature": lift >= 2 and n >= 2,
                         "sources": _distinct_sources([j for j in jobs if skill in j["skills"]])})
        entry = sum(1 for j in jobs if min_years(j.get("e", "")) <= 1)
        return {"ok": True, "jd_total": len(jobs), "rows": rows, "entry_share": round(entry / len(jobs), 2),
                "families": families, "exact": exact}


def _distinct_sources(jobs, k=3):
    """Up to k postings from different companies, plus how many companies asked in total."""
    seen, out = set(), []
    for j in jobs:
        if j["c"] not in seen:
            seen.add(j["c"])
            if len(out) < k:
                out.append({"company": j["c"], "title": j["t"], "url": j["u"]})
    if out:
        out[0]["companies"] = len(seen)
    return out


def min_years(exp):
    """'0-3 Yrs' -> 0; '5-8 Yrs' -> 5; unknown -> 99 (not counted as entry level)."""
    m = re.search(r"\d+", exp or "")
    return int(m.group()) if m else 99


# Tags that are fine on a job posting but, in someone's own prose, usually describe the setting, not a skill:
# "coordinated with sales and finance", "two warehouses", "the marketing team".
PROSE_AMBIGUOUS = {"sales", "finance", "warehouse", "marketing", "retail", "risk", "cloud", "operations", "inventory",
                   "purchase", "po", "ai", "bd", "cs", "cd", "x", "case", "writing", "video", "motion", "layout",
                   "printing", "labels", "graphics", "illustration", "vision", "launch", "rollout", "positioning",
                   "accounts", "container", "pipeline", "queue", "api", "rest", "node", "spring", "selection",
                   "screening", "sourcing", "retention", "onboarding", "editing", "publishing", "vendor", "vendors", "prototype", "prototypes"}


def resume_skills(text, prose=True):
    """Canonical skills found in free text, with the phrase that matched.
    prose=True skips aliases that are ambiguous in someone's description of their own work."""
    low = " " + (text or "").lower() + " "
    found = {}
    for alias, skill in sorted(_ALIAS_TO_CANON.items(), key=lambda kv: -len(kv[0])):
        if skill in found or len(alias) < 2 or (prose and alias in PROSE_AMBIGUOUS):
            continue
        if re.search(r"(?<![a-z0-9])" + re.escape(alias) + r"(?:e?s)?(?![a-z0-9])", low):
            found[skill] = alias
    return found
