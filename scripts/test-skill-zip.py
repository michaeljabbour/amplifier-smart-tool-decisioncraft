#!/usr/bin/env python3
"""Test decisioncraft-skill.zip the way a code sandbox runs it: unzip into a temp folder, run with
an isolated interpreter (python3 -I -S: no site-packages, no user site, no PYTHON* env), and with
networking disabled (any socket use raises). Prints a results table; exits 1 on any failure.

Usage: python3 scripts/test-skill-zip.py [dist/decisioncraft-skill.zip]
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUARD = (
    "import socket,sys,runpy\n"
    "def _no(*a,**k): raise RuntimeError('network used in skill mode')\n"
    "class _NoSocket(socket.socket):\n"
    "    def connect(self,*a,**k): _no()\n"
    "    def connect_ex(self,*a,**k): _no()\n"
    "socket.socket=_NoSocket; socket.create_connection=_no; socket.getaddrinfo=_no\n"
    "sys.argv=['dc.py']+sys.argv[1:]\n"
    "runpy.run_path('scripts/dc.py', run_name='__main__')\n"
)

MODEL = {
    "version": 1, "title": "Hand-written check", "question": "Should the ward change its discharge checklist?",
    "maps": [{"id": "m1", "template": "decision-chain", "title": "The chain", "stages": []}],
}


def run(skill: Path, *args: str) -> tuple[int, dict | None, str]:
    env = {"PATH": "/usr/bin:/bin", "HOME": str(skill.parent), "NO_COLOR": "1", "LANG": "C.UTF-8"}
    p = subprocess.run([sys.executable, "-I", "-S", "-c", GUARD, *args], cwd=skill, env=env,
                       capture_output=True, text=True, timeout=120)
    try:
        data = json.loads(p.stdout) if p.stdout.strip().startswith("{") else None
    except json.JSONDecodeError:
        data = None
    return p.returncode, data, (p.stderr or p.stdout)[-300:]


def main() -> int:
    zpath = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "dist" / "decisioncraft-skill.zip"
    tmp = Path(tempfile.mkdtemp(prefix="dc-skill-"))
    with zipfile.ZipFile(zpath) as z:
        z.extractall(tmp)
    skill = tmp / "decisioncraft"
    notes = skill / "uploaded"
    notes.mkdir()
    (notes / "README.md").write_text("# Clinic booking\n\nPatients phone the desk to book.\nThe desk writes slots in a paper diary.\n")
    (notes / "pain.md").write_text("Double bookings happen weekly.\nNo reminders are sent.\n")
    (skill / "hand.json").write_text(json.dumps(MODEL))
    steps = [
        ("deterministic smoke: manifest", ["manifest", "--json"], 0),
        ("triage", ["triage", "--text", "should I keep my old car or buy a used one", "--json"], 0),
        ("quick with scores", ["quick", "--option", "Keep", "--option", "Buy used", "--criterion", "Cost",
                               "--criterion", "Safety", "--score", "Keep=Cost=4", "--score", "Keep=Safety=2",
                               "--score", "Buy used=Cost=3", "--score", "Buy used=Safety=4", "--json"], 0),
        ("interview --next", ["interview", "--dir", "work", "--text", "keep my car or buy used?", "--next", "--json"], 0),
        ("map --starter on uploaded files", ["map", "uploaded", "--starter", "--dir", "map", "--json"], 0),
        ("guide", ["guide", "--json"], 0),
        ("validate hand-written model", ["validate", "hand.json", "--json"], None),
        ("render canvas", ["render", "map/model.json", "--out", "map/canvas.html", "--json"], 0),
        ("plain map falls back to the starter (no key)", ["map", "uploaded", "--dir", "map2", "--json"], 0),
    ]
    failed = 0
    print("| Step | Exit | Result |\n|---|---|---|")
    for name, args, want in steps:
        code, data, tail = run(skill, *args)
        ok = (code == want) if want is not None else (data is not None and "network used" not in tail)
        if name == "render canvas":
            ok = ok and (skill / "map" / "canvas.html").exists()
        if "network used" in tail:
            ok = False
        failed += not ok
        print(f"| {name} | {code} | {'pass' if ok else 'FAIL: ' + tail.strip().splitlines()[-1] if tail.strip() else 'FAIL'} |")
    imports = [l for f in (skill / "scripts").rglob("*.py") for l in f.read_text(encoding="utf-8").splitlines()
               if l.startswith(("import anthropic", "import openai", "import mcp", "from mcp"))]
    print(f"| no top-level anthropic/openai/mcp imports | - | {'pass' if not imports else 'FAIL'} |")
    failed += bool(imports)
    print(f"\n{len(steps) + 1 - failed} of {len(steps) + 1} passed (unzipped at {skill})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
