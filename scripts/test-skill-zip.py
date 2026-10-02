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


# In the wheel but deliberately left out of the skill: the MCP server needs the optional mcp package.
SKILL_ONLY_OMITS = {"mcp_server.py"}


def wheel_gaps(skill: Path) -> list[str]:
    """Files the installed wheel's decisioncraft package has that the skill's copy lacks.

    Builds the wheel with `uv build` (or `python -m build`) into a temp folder. Skipped, with a
    note, when neither is available."""
    out = Path(tempfile.mkdtemp(prefix="dc-wheel-"))
    for cmd in (["uv", "build", "--wheel", "--out-dir", str(out)],
                [sys.executable, "-m", "build", "--wheel", "--outdir", str(out)]):
        try:
            if subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=300).returncode == 0:
                break
        except (FileNotFoundError, subprocess.TimeoutExpired):
            continue
    wheels = sorted(out.glob("*.whl"))
    if not wheels:
        print("(could not build a wheel to compare against; skipped)")
        return []
    with zipfile.ZipFile(wheels[-1]) as w:
        names = {n.split("/", 1)[1] for n in w.namelist()
                 if n.startswith("decisioncraft/") and not n.endswith("/") and "__pycache__" not in n}
    have = {p.relative_to(skill / "scripts" / "decisioncraft").as_posix()
            for p in (skill / "scripts" / "decisioncraft").rglob("*") if p.is_file()}
    return sorted(n for n in names - have if n.split("/")[-1] not in SKILL_ONLY_OMITS)


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
        # (name, args, expected exit, extra check on (data, skill))
        ("deterministic smoke: manifest", ["manifest", "--json"], 0, None),
        ("guide returns the model format", ["guide", "--json"], 0,
         lambda d, sk: bool(d and (d.get("result") or {}).get("model_format", "").strip())),
        ("example car writes its files", ["example", "car", "--out", "car", "--json"], 0,
         lambda d, sk: (sk / "car" / "model.json").is_file() and (sk / "car" / "canvas.html").is_file()),
        ("triage", ["triage", "--text", "should I keep my old car or buy a used one", "--json"], 0, None),
        ("quick with scores", ["quick", "--option", "Keep", "--option", "Buy used", "--criterion", "Cost",
                               "--criterion", "Safety", "--score", "Keep=Cost=4", "--score", "Keep=Safety=2",
                               "--score", "Buy used=Cost=3", "--score", "Buy used=Safety=4", "--json"], 0, None),
        ("interview --next", ["interview", "--dir", "work", "--text", "keep my car or buy used?", "--next", "--json"],
         0, None),
        ("map --starter on uploaded files", ["map", "uploaded", "--starter", "--dir", "map", "--json"], 0,
         lambda d, sk: (sk / "map" / "model.json").is_file()),
        ("untouched starter fails validate (empty map)", ["validate", "map/model.json", "--json"], 1,
         lambda d, sk: "map is empty" in json.dumps(d or {})),
        ("untouched starter passes with --allow-empty", ["validate", "map/model.json", "--allow-empty", "--json"],
         0, None),
        ("render refuses the empty starter", ["render", "map/model.json", "--out", "map/canvas.html", "--json"], 1,
         lambda d, sk: not (sk / "map" / "canvas.html").exists()),
        ("validate a filled model (car example)", ["validate", "car/model.json", "--json"], 0, None),
        ("render a filled model", ["render", "car/model.json", "--out", "car/again.html", "--json"], 0,
         lambda d, sk: (sk / "car" / "again.html").is_file()),
        ("hand-written empty model is rejected", ["validate", "hand.json", "--json"], 1, None),
        ("doctor reports skill mode", ["doctor", "--json"], 0,
         lambda d, sk: "Skill mode" in json.dumps(d or {}) and "provider_" not in json.dumps(d or {})),
        ("plain map falls back to the starter (no key)", ["map", "uploaded", "--dir", "map2", "--json"], 0, None),
    ]
    failed = 0
    print("| Step | Exit | Result |\n|---|---|---|")
    for name, args, want, check in steps:
        code, data, tail = run(skill, *args)
        ok = code == want and "network used" not in tail
        if ok and check is not None:
            ok = bool(check(data, skill))
        failed += not ok
        last = tail.strip().splitlines()[-1] if tail.strip() else ""
        print(f"| {name} | {code} | {'pass' if ok else 'FAIL: ' + last} |")
    missing = wheel_gaps(skill)
    print(f"| matches the wheel's package files | - | {'pass' if not missing else 'FAIL: missing ' + ', '.join(missing[:8])} |")
    failed += bool(missing)
    imports = [l for f in (skill / "scripts").rglob("*.py") for l in f.read_text(encoding="utf-8").splitlines()
               if l.startswith(("import anthropic", "import openai", "import mcp", "from mcp"))]
    print(f"| no top-level anthropic/openai/mcp imports | - | {'pass' if not imports else 'FAIL'} |")
    failed += bool(imports)
    total = len(steps) + 2
    print(f"\n{total - failed} of {total} passed (unzipped at {skill})")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
