import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from coach import core, market, server, tracker

SAMPLES = Path(__file__).parent.parent / "samples"
MKT = market.Market.load()
RESUME = (SAMPLES / "sample_resume.txt").read_text()
GOOD = ("When I was at the logistics firm, dispatches ran late. I had to find why. I mapped the dispatch "
        "workflow, interviewed four staff and built an Excel tracker with pivots covering 400 orders a week. "
        "I then rewrote the SOP so that each hand-off had one owner. As a result, late dispatches reduced "
        "from 30 to 12 a week, which the operations head now reviews every Monday. I learned to check the "
        "data before proposing a fix, and I now map the process first on every problem I am given.")


def plan_for(role):
    p = core.intake(RESUME, role, 8, 8)
    g = core.gap_map(p, MKT)
    return p, g


class MarketTest(unittest.TestCase):
    def test_corpus_learns_a_vocabulary_without_filler(self):
        self.assertGreater(len(MKT.jobs), 100)
        self.assertIn("sql", MKT.vocab)
        self.assertNotIn("development", MKT.vocab)
        self.assertEqual(market.canon("Power Bi"), market.canon("BI Tools"))

    def test_each_role_gets_its_own_profile(self):
        tops = {r: [x["skill"] for x in MKT.role_profile(r)["rows"][:5]]
                for r in ("Business Analyst", "Python Developer", "Digital Marketing Executive")}
        self.assertIn("django", tops["Python Developer"])
        self.assertIn("seo", tops["Digital Marketing Executive"])
        self.assertIn("requirements gathering", tops["Business Analyst"])
        self.assertEqual(len({tuple(t) for t in tops.values()}), 3)

    def test_closest_family_is_labelled_not_silent(self):
        p = MKT.role_profile("Program Analyst")
        self.assertEqual((p["families"], p["exact"]), (["program manager"], False))

    def test_unknown_role_says_no_data(self):
        p = MKT.role_profile("Chartered Accountant")
        self.assertFalse(p["ok"])
        self.assertTrue(p["roles"])

    def test_ui_ux_designer_gets_a_design_profile(self):
        p = MKT.role_profile("UI/UX Designer")
        self.assertTrue(p["exact"])
        top = [r["skill"] for r in p["rows"][:6]]
        self.assertTrue({"ui design", "ux design", "figma"} <= set(top))
        _, g = plan_for("UI/UX Designer")
        self.assertEqual(core.suggest_projects(g)[0]["title"], "End-to-end UX case study for a real app")


class CoachTest(unittest.TestCase):
    # 1
    def test_intake_finds_skills_with_evidence(self):
        p = core.intake(RESUME, "Business Analyst")
        self.assertIn("excel", p["skills"])
        self.assertIn("pivots", p["evidence"]["excel"])

    def test_goal_sentences_are_not_evidence(self):
        p = core.intake("Customer support at a SaaS firm. I built a weekly ticket report in Excel. "
                        "I want to move into a Product Analyst role.", "Product Analyst")
        self.assertNotIn("product analytics", p["skills"])
        self.assertIn("excel", p["skills"])

    def test_experience_before_a_goal_in_the_same_sentence_still_counts(self):
        p = core.intake("I have 2 years as a junior accountant doing Tally entries, GST returns and monthly MIS in "
                        "Excel with pivots, and I helped with one audit, and now I want to become a Financial Analyst.",
                        "Financial Analyst")
        self.assertTrue({"finance / accounting", "excel", "reporting", "audit / compliance"} <= set(p["skills"]))

    def test_plain_star_answer_gets_full_structure(self):
        a = ("At my CA firm, GST returns were filed late every month. I had to fix that. I built a tracker in Excel "
             "and set reminders, so we filed all returns on time with no penalties.")
        self.assertEqual(core.score_answer(a, "finance / accounting")["parts"]["structure"], 5)

    def test_related_tool_counts_as_partly_relevant(self):
        r = core.score_answer("I set up a Jenkins job that ran our tests on every commit.", "ci/cd")
        self.assertEqual(r["parts"]["relevance"], 3)

    def test_number_words_count_as_specific(self):
        r = core.score_answer("I cut handling time by about a fifth using Excel.", "excel")
        self.assertGreaterEqual(r["parts"]["specificity"], 3)

    # 2
    def test_gap_map_ranks_by_share_and_cites_real_postings(self):
        p, g = plan_for("Business Analyst")
        shares = [r["share"] for r in g["rows"]]
        self.assertEqual(shares, sorted(shares, reverse=True))
        sql = next(r for r in g["rows"] if r["skill"] == "sql")
        self.assertFalse(sql["have"])
        self.assertTrue(sql["sources"][0]["url"].startswith("https://www.naukri.com/job-listings-"))
        self.assertTrue(0 < g["coverage"] < 1)

    # 3
    def test_plan_fits_weeks_and_ends_with_capstone(self):
        p, g = plan_for("Python Developer")
        plan = core.build_plan(p, g)
        self.assertEqual(len(plan), 8)
        self.assertEqual(plan[0]["skill"], "python")
        self.assertEqual([plan[0]["mode"], plan[1]["mode"]], ["learn", "apply"])
        self.assertEqual(plan[-1]["skill"], "capstone")

    # 4
    def test_projects_differ_by_role(self):
        dev = core.suggest_projects(plan_for("Python Developer")[1])
        mkt = core.suggest_projects(plan_for("Digital Marketing Executive")[1])
        self.assertEqual(dev[0]["title"], "REST API with tests and a container")
        self.assertEqual(mkt[0]["title"], "Live mini campaign with a results report")
        covered = [s for p in dev for s in p["closes_gaps"]]
        self.assertEqual(len(covered), len(set(covered)))

    # 5
    def test_rubric_scores_strong_above_weak(self):
        strong = core.score_answer(GOOD, "process improvement")
        weak = core.score_answer("We did some process stuff.", "process improvement")
        self.assertGreaterEqual(strong["score"], 80)
        self.assertLess(weak["score"], 50)
        self.assertTrue(weak["feedback"])

    # 6
    def test_slip_repeats_week_and_low_score_adds_review(self):
        p, g = plan_for("Business Analyst")
        plan = core.build_plan(p, g)
        slipped, _ = core.check_in(plan, 1, done=False)
        self.assertEqual((slipped[0]["status"], slipped[1]["skill"]), ("slipped", plan[0]["skill"]))
        self.assertEqual(len(slipped), len(plan) + 1)
        reviewed, _ = core.check_in(plan, 1, done=True, interview_score=40)
        self.assertEqual(reviewed[1]["mode"], "review")
        same, ch = core.check_in(plan, 1, done=True, interview_score=85)
        self.assertEqual((len(same), ch), (len(plan), []))

    # 7
    def test_tracker_learns_tailored_resumes_get_replies(self):
        apps = json.loads((SAMPLES / "sample_applications.json").read_text())
        advice = tracker.recommend(tracker.learn(apps))
        self.assertTrue(any(a.startswith("tailored = yes") for a in advice["do_more"]))
        self.assertTrue(any("naukri" in a for a in advice["do_less"]))

    def test_tracker_ignores_small_groups(self):
        apps = [{"lane": "A", "role_family": "x", "source": "s", "work_model": "w", "tailored": "no", "responded": True}] * 2
        self.assertEqual(tracker.learn(apps)["insights"], [])


class WholeMarketTest(unittest.TestCase):
    def test_every_role_has_a_distinct_cited_profile_and_a_plan(self):
        tops = {}
        for role in MKT.roles:
            p, g = plan_for(role)
            self.assertTrue(g["ok"] and g["exact"], role)
            self.assertGreaterEqual(g["jd_total"], market.MIN_JOBS, role)
            for r in g["rows"]:
                for src in r["sources"]:
                    self.assertTrue(src["url"].startswith("https://www.naukri.com/job-listings-"), (role, src))
            plan = core.build_plan(p, g)
            self.assertEqual(len(plan), 8, role)
            self.assertTrue(core.suggest_projects(g), role)
            tops[role] = tuple(r["skill"] for r in g["rows"][:3])
        self.assertEqual(len(set(tops.values())), len(tops), "two roles share the same top-3 skills")

    def test_planned_skills_mostly_have_a_specific_hint(self):
        # Daily refreshes bring new tags; the app falls back to a generic hint, but 90%+ should be specific
        planned = {w["skill"] for role in MKT.roles for w in core.build_plan(*plan_for(role))} - core.GENERAL
        missing = planned - set(core.HINTS)
        self.assertLessEqual(len(missing), len(planned) // 10, sorted(missing))


class RobustnessTest(unittest.TestCase):
    def call(self, body):
        try:
            return server.act(str(body.get("action", "")) if isinstance(body, dict) else "", body if isinstance(body, dict) else {})
        except server.BadRequest as e:
            return {"bad": str(e)}

    def test_tampered_state_never_crashes(self):
        for state in ([1], "x", {"interviews": "x"}, {"plan": "x"}, {"plan": [1, 2]}, {"apps": {"a": 1}},
                      {"plan": [{"week": 1}], "profile": "x"}):
            for action, extra in (("question", {}), ("answer", {"answer": "a", "skill": "sql"}),
                                  ("checkin", {"week": 1, "done": True}), ("apps", {})):
                self.call({"action": action, "state": state, **extra})  # must not raise anything but BadRequest

    def test_bad_inputs_get_clear_messages(self):
        self.assertIn("Build a plan", self.call({"action": "question", "state": {}})["bad"])
        self.assertIn("application", self.call({"action": "apps", "state": {}, "add": "x"})["bad"])
        r = server.act("intake", {"resume": RESUME, "target_role": "Data Analyst", "hours": 10 ** 30, "weeks": -5})
        self.assertEqual((r["state"]["profile"]["hours_per_week"], r["state"]["profile"]["weeks"]), (40, 3))
        st = r["state"]
        self.assertIn("isn't in your plan", self.call({"action": "checkin", "state": st, "week": 99, "done": True})["bad"])

    def test_string_false_is_not_a_reply(self):
        r = server.act("apps", {"state": {}, "add": {"role": "x", "responded": "false"}})
        self.assertFalse(r["state"]["apps"][0]["responded"])

    def test_weekly_tasks_fit_the_hours_budget(self):
        for h in range(2, 41):
            p = core.intake(RESUME, "Data Analyst", h, 8)
            for w in core.build_plan(p, core.gap_map(p, MKT)):
                self.assertEqual(sum(int(t.split("h")[0]) for t in w["tasks"]), h, (h, w["tasks"]))

    def test_icp_profile_reads_real_experience(self):
        t = ("Led a Zoho One implementation, migrated 980 Tally records and reconciled them, built Power BI reports "
             "and ran a weekly KPI review. Rank 1 in an AI hackathon with PyTorch. Cleaned customer and vendor records.")
        p = core.intake(t, "Business Analyst")
        self.assertTrue({"project management", "reconciliation", "reporting", "kpis", "machine learning"} <= set(p["skills"]))
        self.assertNotIn("procurement", p["skills"])  # "vendor records" is context, not procurement work
        g = core.gap_map(p, MKT)
        self.assertTrue(all(r["have"] for r in g["rows"] if r["skill"] == "data visualization"))  # implied by Power BI

    def test_soft_skills_are_never_learning_weeks(self):
        for role in MKT.roles:
            self.assertFalse({w["skill"] for w in core.build_plan(*plan_for(role))} & core.SOFT, role)

    def test_context_words_are_not_skills(self):
        p = core.intake("I coordinated with sales and finance teams across two warehouses.", "Business Analyst")
        self.assertFalse({"sales", "finance / accounting", "etl / data engineering"} & set(p["skills"]))


class RefreshTest(unittest.TestCase):
    def setUp(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))
        import refresh_corpus
        self.r = refresh_corpus

    def test_rotation_covers_every_role_within_six_days(self):
        import datetime as dt
        start = dt.date(2026, 11, 1)
        seen = {role for i in range(6) for role in self.r.todays_batch(start + dt.timedelta(days=i))}
        self.assertEqual(seen, set(self.r.ROLES))
        self.assertEqual(set(self.r.ROLES), set(MKT.roles))  # every role on the site gets refreshed

    def test_only_real_job_links_with_skills_are_kept(self):
        import datetime as dt
        rows = self.r.to_rows("data analyst", [
            {"title": "A", "url": "https://www.naukri.com/job-listings-a-1", "skills": ["SQL"]},
            {"title": "B", "url": "#", "skills": ["SQL"]},
            {"title": "C", "url": "https://www.naukri.com/job-listings-c-2", "skills": []}], dt.date(2026, 11, 1))
        self.assertEqual([x["t"] for x in rows], ["A"])
        self.assertEqual(rows[0]["d"], "2026-11-01")

    def test_newest_copy_wins_and_old_postings_expire(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            row = lambda u, day, skills: json.dumps({"q": "data analyst", "t": "x", "c": "y", "e": "", "u": u, "s": skills, "d": day})
            NL = chr(10)
            (p / "naukri_2026-09-01_a.jsonl").write_text(row("u-old", "2026-09-01", ["SQL", "Excel"]) + NL, encoding="utf-8")
            (p / "naukri_2026-10-31_a.jsonl").write_text(
                row("u1", "2026-10-31", ["SQL", "Excel"]) + NL + row("u2", "2026-10-31", ["SQL", "Excel"]) + NL, encoding="utf-8")
            (p / "naukri_2026-11-01_a.jsonl").write_text(row("u1", "2026-11-01", ["SQL", "Python"]) + NL, encoding="utf-8")
            m = market.Market.load(folder=p)
            urls = {j["u"]: j for j in m.jobs}
            self.assertNotIn("u-old", urls)                      # 61 days older than the newest refresh
            self.assertEqual(urls["u1"]["d"], "2026-11-01")      # newest copy kept
            self.assertEqual(len(m.jobs), 2)                     # no duplicates
            self.assertEqual(m.updated, "2026-11-01")


class ServerTest(unittest.TestCase):
    def test_end_to_end_api_is_stateless(self):
        srv = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        url = f"http://127.0.0.1:{srv.server_port}/api/coach"

        def post(action, state=None, **body):
            req = urllib.request.Request(url, json.dumps({**body, "action": action, "state": state}).encode(),
                                         {"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req).read())

        try:
            self.assertIn("python developer", post("roles")["result"]["roles"])
            a = post("intake", resume=RESUME, target_role="Python Developer")["state"]
            b = post("intake", resume=RESUME, target_role="HR Recruiter")["state"]
            self.assertEqual(a["plan"][0]["skill"], "python")
            self.assertEqual(b["plan"][0]["skill"], "recruitment")  # visitors don't share state
            q = post("question", a)["result"]
            r = post("answer", a, answer=GOOD, skill=q["skill"])
            self.assertEqual(len(r["state"]["interviews"]), 1)
            a = post("checkin", r["state"], week=1, skill=q["skill"], done=False)["state"]
            self.assertEqual(a["plan"][0]["status"], "slipped")
            apps = post("apps", a, add={"role": "BA", "source": "linkedin", "lane": "A", "work_model": "hybrid",
                                         "tailored": "yes", "responded": True})
            self.assertTrue(apps["result"]["sample"])
            self.assertEqual(len(apps["state"]["apps"]), 1)
            with self.assertRaises(urllib.error.HTTPError) as e:
                post("intake", resume="", target_role="")
            self.assertEqual(e.exception.code, 400)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__ == "__main__":
    unittest.main()
