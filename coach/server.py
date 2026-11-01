"""Career pivot coach API. Standard library only, stateless.

The browser keeps each visitor's state (profile, plan, interviews, applications) and sends it
with every call, so one deployment serves many people without a database.

Local:  python -m coach.server   then open http://localhost:8765
Cloud:  api/coach.py wraps the same Handler for Vercel.
"""
import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from coach import core, market, tracker

ROOT = Path(__file__).resolve().parent.parent
REAL_JDS = ROOT / "data" / "jds" / "real_jds.csv"
SAMPLE_APPS = ROOT / "samples" / "sample_applications.json"
MARKET = market.Market.load(extra_csv=REAL_JDS)
MAX_BODY = 200_000  # bytes; a résumé plus state fits easily


MAX_PLAN_WEEKS = 40  # slips and review weeks can extend a 16-week plan, but not without bound


class BadRequest(ValueError):
    """An error whose message is safe and useful to show the visitor."""


def _clean_state(s):
    """The browser owns the state, so check its shape before using it."""
    if not isinstance(s, dict):
        return {}
    for key in ("apps", "log", "interviews", "plan", "projects"):
        if key in s and not isinstance(s[key], list):
            s[key] = []
    if "plan" in s and not all(isinstance(w, dict) for w in s["plan"]):
        s["plan"] = []
    return s


def _int(value, default, lo, hi):
    try:
        return max(lo, min(hi, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def act(action, body):
    """Returns {"state": ..., "result": ...}. Never trusts state for anything but the visitor's own data."""
    s = _clean_state(body.get("state"))
    result = None
    if action == "roles":
        result = {"roles": dict(MARKET.roles), "jobs": len(MARKET.jobs), "career_os": REAL_JDS.exists(),
                  "updated": MARKET.updated, "new_today": MARKET.new_today}
    elif action == "intake":
        resume, role = str(body.get("resume", ""))[:20000], str(body.get("target_role", ""))[:100]
        if not resume.strip() or not role.strip():
            raise BadRequest("Add your experience and the role you want.")
        profile = core.intake(resume, role, _int(body.get("hours"), 8, 2, 40), _int(body.get("weeks"), 8, 3, 16))
        gmap = core.gap_map(profile, MARKET)
        s = {"profile": profile, "gap_map": gmap, "apps": s.get("apps", []), "log": [], "interviews": [],
             "plan": core.build_plan(profile, gmap) if gmap["ok"] else [],
             "projects": core.suggest_projects(gmap) if gmap["ok"] else []}
    elif action == "question":
        if not s.get("plan") or not isinstance(s.get("profile"), dict):
            raise BadRequest("Build a plan first.")
        week = next((w for w in s["plan"] if w.get("status") == "todo"), s["plan"][-1])
        result = {"skill": str(week.get("skill", "")), "week": week.get("week"), "rubric": core.RUBRIC,
                  "question": core.question(str(week.get("skill", "")), str(s["profile"].get("target_role", "")))}
    elif action == "answer":
        skill = str(body.get("skill", ""))[:80]
        result = core.score_answer(str(body.get("answer", ""))[:5000], skill)
        s.setdefault("interviews", []).append({"skill": skill, "score": result["score"]})
    elif action == "checkin":
        if not s.get("plan"):
            raise BadRequest("Build a plan first.")
        if len(s["plan"]) >= MAX_PLAN_WEEKS:
            raise BadRequest("This plan is already very long. Start over with a fresh plan.")
        week = _int(body.get("week"), None, 1, MAX_PLAN_WEEKS)
        if week not in {w.get("week") for w in s["plan"]}:
            raise BadRequest("That week isn't in your plan.")
        done = body.get("done") is True
        last = [i.get("score") for i in s.get("interviews", [])
                if isinstance(i, dict) and i.get("skill") == body.get("skill") and isinstance(i.get("score"), int)]
        s["plan"], changes = core.check_in(s["plan"], week, done, last[-1] if last else None)
        s.setdefault("log", []).append({"week": week, "done": done, "changes": changes})
    elif action == "apps":
        add = body.get("add")
        if add is not None and not isinstance(add, dict):
            raise BadRequest("An application must have a role and a source.")
        if add:
            a = {k: str(v)[:80] for k, v in add.items() if k != "responded"}
            a["responded"] = add.get("responded") is True  # "false" (a string) must not count as a reply
            a["role_family"] = tracker.role_family(a.get("role", ""))
            s.setdefault("apps", []).append(a)
        mine = [a for a in s.get("apps", []) if isinstance(a, dict)][-500:]
        s["apps"] = mine
        apps = mine if len(mine) >= 3 else json.loads(SAMPLE_APPS.read_text(encoding="utf-8"))  # never mix example and real
        model = tracker.learn(apps)
        result = {"sample": len(mine) < 3, "mine": len(mine), "model": model, "advice": tracker.recommend(model)}
    else:
        raise BadRequest("Unknown action.")
    return {"state": s, "result": result}


def _reject_constant(name):
    raise ValueError(f"bad number {name}")  # json accepts Infinity/NaN by default; we don't


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json"):
        data = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            return self._send(200, (ROOT / "web" / "index.html").read_bytes(), "text/html; charset=utf-8")
        self._send(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/api/coach"):
            return self._send(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
        except ValueError:
            return self._send(400, {"error": "Invalid request."})
        if n < 0 or n > MAX_BODY:
            return self._send(413, {"error": "Request too large."})
        try:
            body = json.loads(self.rfile.read(n) or b"{}", parse_constant=_reject_constant)
            if not isinstance(body, dict):
                raise BadRequest("Invalid request.")
            self._send(200, act(str(body.get("action", "")), body))
        except BadRequest as e:
            self._send(400, {"error": str(e)})
        except Exception:  # never leak internals; the visitor's state may simply be from an older version
            self._send(400, {"error": "Something in your saved plan looks out of date. Use Start over and build it again."})

    def log_message(self, *args):
        pass


def main(port=8765):
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Career Pivot Coach on http://localhost:{port}  ({len(MARKET.jobs)} postings, {len(MARKET.roles)} roles)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
