"""Build a clean Vercel deploy folder with only public files.

Run: python tools/build_deploy.py   ->  active/deploy/
Never copies active/, data/ (personal), tests or the lead pipeline.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "active" / "deploy"

API = '''"""Vercel entry point: the same stateless handler the local server uses."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "_lib"))
from coach.server import Handler  # noqa: E402


class handler(Handler):  # Vercel looks for a class named `handler` defined in this file
    pass
'''

VERCEL = {
    "framework": None,  # static page + one Python function, not a Python web app
    "rewrites": [{"source": "/api/coach", "destination": "/api/coach_api"}],
    "functions": {"api/coach_api.py": {"includeFiles": "api/_lib/**"}},
    "headers": [{"source": "/(.*)", "headers": [
        {"key": "X-Content-Type-Options", "value": "nosniff"},
        {"key": "Referrer-Policy", "value": "strict-origin-when-cross-origin"},
        {"key": "X-Frame-Options", "value": "DENY"},
        {"key": "Permissions-Policy", "value": "camera=(), geolocation=()"},
    ]}],
}


def main():
    if OUT.exists():  # keep the Vercel project link (.vercel) between builds; replace everything else
        for p in OUT.iterdir():
            if p.name != ".vercel":
                shutil.rmtree(p) if p.is_dir() else p.unlink()
    (OUT / "api").mkdir(parents=True)
    (OUT / ".vercelignore").write_text(".env*\n.vercel\n__pycache__\n", encoding="utf-8")
    shutil.copy(ROOT / "web" / "index.html", OUT / "index.html")
    lib = OUT / "api" / "_lib"  # bundled into the function only; "_" folders are neither functions nor public files
    shutil.copytree(ROOT / "coach", lib / "coach", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "corpus", lib / "corpus")
    (lib / "samples").mkdir()
    shutil.copy(ROOT / "samples" / "sample_applications.json", lib / "samples")
    (OUT / "api" / "coach_api.py").write_text(API, encoding="utf-8")
    (OUT / "vercel.json").write_text(json.dumps(VERCEL, indent=2), encoding="utf-8")
    (OUT / "requirements.txt").write_text("", encoding="utf-8")  # standard library only
    files = sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file())
    print(f"{len(files)} files -> {OUT}")
    for f in files:
        print("  " + f)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
