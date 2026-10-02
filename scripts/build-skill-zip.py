#!/usr/bin/env python3
"""Build decisioncraft-skill.zip: a self-contained Agent Skill for hosts with a code sandbox but
no local shell (Claude Desktop / claude.ai Skills, ChatGPT Skills, any Agent Skills host).

The zip holds one folder, decisioncraft/, with SKILL.md, the zero-dependency library vendored
under scripts/decisioncraft/, a runner (scripts/dc.py) and references/ (model format, writing
guide, modes, interview questions, templates, roles). It needs no API key, pip or network: the
host's own model writes the map; Decisioncraft checks and draws it.

Usage: python3 scripts/build-skill-zip.py [--out dist/decisioncraft-skill.zip] [--no-test]

The build ends with scripts/test-skill-zip.py, so a zip missing a file the library reads
never gets released.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "decisioncraft"
REPO_SKILL = ROOT / "skills" / "decisioncraft" / "SKILL.md"
# Not useful in a sandbox, and they would pull optional packages: the MCP server and the vendored
# copy's compiled caches.
SKIP = {"__pycache__", "mcp_server.py"}

BODY = """
# Decisioncraft (skill mode)

You are the model. Decisioncraft is a plain Python library bundled in `scripts/` that checks and
draws what you write. It needs no API key, no pip install and no network. Run it from this
skill's folder:

```sh
python3 scripts/dc.py <command> [options] --json
```

Every command prints one JSON result (`ok`, `result`, `error`). Never call `draft`,
`perspectives` or a plain `map` (they need an API key): you do that thinking yourself.

## Pick the depth first

```sh
python3 scripts/dc.py triage --text "<what the person said>" --json
```

It returns a mode and an `offer` sentence. Offer, don't take over.

- **none**: just answer in a sentence or two. Build nothing.
- **quick**: a small scored table in the chat, no files:
  `python3 scripts/dc.py quick --option "Keep" --option "Buy used" --criterion "Cost" --criterion "Safety" --score "Keep=Cost=4" ... --json`
  Show the returned Markdown table, the lean and the one thing to check first.
- **guided**: ask one question at a time with the interview, then build a canvas:
  `python3 scripts/dc.py interview --dir work --text "<first message>" --next --json`, then
  `python3 scripts/dc.py interview --dir work --answer "<their reply>" --next --json` until it
  says done. Ask each question in your own words; "not sure" is a fine answer.
- **team**: the same as guided, then the full canvas with every role's notes.

## Map something (as-is, to-be, gaps, notes)

When someone uploads files or a folder and asks how it works or what is missing:

1. `python3 scripts/dc.py map <uploaded folder or file> --starter --dir map --json` writes
   `map/material/digest.md` (numbered lines), a starter `map/model.json` and `map/FILL-IN.md`.
2. Read `references/model-format.md` and `references/writing-guide.md`, then fill in
   `map/model.json` from the digest: how it works today (each step with evidence quoted exactly,
   with its file and line), the planned way, the gaps as user stories with "done when" checks,
   and a short note from each role that ends in a question.
3. `python3 scripts/dc.py validate map/model.json --json`. Fix every error it lists. The
   untouched starter fails on purpose ("The map is empty"): never hand over an empty canvas.
4. `python3 scripts/dc.py render map/model.json --out map/canvas.html --json`.
5. Give the person `map/canvas.html` as a downloadable file. It opens offline in any browser.
   Summarise in a few plain sentences what it shows and the most urgent questions
   (`python3 scripts/dc.py questions map/model.json --json`).

For a topic with no files, write the model from what the person tells you and mark claims you
could not check.

## Other useful commands

- `guide`: the model format and writing guide (same as `references/`).
- `example car --out car --json` (or business, technical, engineering, medical, map): a finished
  example to show what a map looks like; render it with `render car/model.json`.
- `words model.json`: the whole model as readable text.
- `merge model.json review1.json review2.json`: where reviewers agree and split.
- `diff old.json new.json`: what changed between versions.

## Writing

Plain words, short sentences, no jargon. Every note from a role ends in a question. Never invent
evidence: quote the material exactly or say it is unchecked.

## Not for

Factual questions, trivial picks, or code-level choices inside a coding task ("map or list?"),
unless the person asks to lay options out or review a process.
"""


def frontmatter() -> str:
    text = REPO_SKILL.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        raise SystemExit(f"{REPO_SKILL} has no frontmatter")
    keep = [ln for ln in m.group(1).splitlines() if ln.startswith(("name:", "description:"))]
    return "---\n" + "\n".join(keep) + "\n---\n"


def references() -> dict[str, str]:
    sys.path.insert(0, str(ROOT / "src"))
    from decisioncraft import lib
    from decisioncraft.intelligence import _guide

    def as_json(value) -> str:
        return json.dumps(value, indent=2, ensure_ascii=False) + "\n"

    return {
        "model-format.md": lib.guide()["model_format"],
        "writing-guide.md": _guide(),
        "modes.json": as_json(lib.modes()),
        "interview-questions.json": as_json(lib.interview_questions()),
        "templates.json": as_json(lib.templates()),
        "roles.json": as_json(lib.roles()),
    }


RUNNER = '''#!/usr/bin/env python3
"""Run the bundled Decisioncraft library: python3 scripts/dc.py <command> [options]."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DECISIONCRAFT_HOST", "skill")

from decisioncraft.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
'''


def wheel_extras() -> dict[str, str]:
    """The files the wheel adds to the package (pyproject force-include): repository path ->
    path inside the installed package. The skill copies exactly the same set, so `guide`,
    `example` and anything else that reads package data work the same in skill mode."""
    cfg = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extra = cfg["tool"]["hatch"]["build"]["targets"]["wheel"].get("force-include", {})
    return {src: dst.split("/", 1)[1] for src, dst in extra.items() if dst.startswith("decisioncraft/")}


def build(out: Path) -> Path:
    stage = out.parent / "skill-build"
    if stage.exists():
        shutil.rmtree(stage)
    root = stage / "decisioncraft"
    (root / "scripts").mkdir(parents=True)
    (root / "references").mkdir()
    (root / "SKILL.md").write_text(frontmatter() + BODY.lstrip("\n"), encoding="utf-8")
    shutil.copytree(SRC, root / "scripts" / "decisioncraft",
                    ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith(".pyc")])
    pkg = root / "scripts" / "decisioncraft"
    for src, dst in wheel_extras().items():
        source, target = ROOT / src, pkg / dst
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target, dirs_exist_ok=True,
                            ignore=lambda d, names: [n for n in names if n in SKIP or n.endswith(".pyc")])
        elif source.is_file():
            shutil.copy2(source, target)
        else:
            raise SystemExit(f"pyproject force-include names {src}, which does not exist")
    (root / "scripts" / "dc.py").write_text(RUNNER, encoding="utf-8")
    for name, text in references().items():
        (root / "references" / name).write_text(text, encoding="utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for f in sorted(root.rglob("*")):
            if f.is_file():
                z.write(f, f.relative_to(stage).as_posix())
    shutil.rmtree(stage)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default=str(ROOT / "dist" / "decisioncraft-skill.zip"))
    ap.add_argument("--no-test", action="store_true",
                    help="Skip the smoke test (unzip, run every key command offline, compare with the wheel).")
    args = ap.parse_args()
    out = build(Path(args.out))
    with zipfile.ZipFile(out) as z:
        skill = z.read("decisioncraft/SKILL.md").decode("utf-8")
        print(f"Wrote {out} ({len(z.namelist())} files; SKILL.md ~{len(skill) // 4} tokens)")
    if args.no_test:
        return 0
    test = subprocess.run([sys.executable, str(ROOT / "scripts" / "test-skill-zip.py"), str(out)])
    if test.returncode:
        print("The skill zip failed its smoke test; not fit to release.", file=sys.stderr)
    return test.returncode


if __name__ == "__main__":
    raise SystemExit(main())
