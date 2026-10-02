import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

import decisioncraft as dc
from decisioncraft.help import CAPABILITIES, capability_skill, skill

ROOT = Path(__file__).resolve().parent.parent
EX = ROOT / "examples"
CLI = [sys.executable, str(ROOT / "bin" / "decisioncraft.py")]
NO_KEYS = {
    k: v
    for k, v in os.environ.items()
    if not re.search(r"API_KEY|TOKEN|SECRET|PROVIDER|MODEL", k)
}


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def run(*args, ok=True):
    r = subprocess.run(
        [*CLI, *args], capture_output=True, text=True, env=NO_KEYS, timeout=60
    )
    if ok:
        assert r.returncode == 0, r.stderr
    return r


@pytest.mark.parametrize("name", ["business", "technical", "engineering", "medical"])
def test_render_is_self_contained(name):
    page = dc.render(load(EX / name / "model.json"))
    assert page.startswith("<!doctype html>")
    assert "__MODEL__" not in page and "__JS__" not in page
    # no outside requests: no remote scripts, styles, fonts or images
    assert not re.search(r"""(src|href)=["']https?://""", page)
    assert "@import" not in page and "url(http" not in page
    assert "default-src 'none'" in page


def test_render_escapes_script_endings_inside_the_model():
    m = dc.new("decision-chain", "A </script><script>alert(1)</script> title", "Q?")
    page = dc.render(m)
    assert "</script><script>alert(1)" not in page


def test_render_refuses_an_invalid_model():
    with pytest.raises(dc.model.ModelError):
        dc.render(
            {"format": "decisioncraft/1", "title": "", "question": "", "maps": []}
        )


def test_render_marks_changes_and_embeds_reviews():
    tech = load(EX / "technical" / "model.json")
    page = dc.render(tech, since=load(EX / "technical" / "model-before.json"))
    assert '"changed"' in page
    biz = load(EX / "business" / "model.json")
    reviews = [load(p) for p in sorted((EX / "business" / "reviews").glob("*.json"))]
    assert '"reviewers"' in dc.render(biz, reviews=reviews)


def test_words_covers_every_part():
    text = dc.words(load(EX / "medical" / "model.json"))
    for heading in (
        "## Questions to decide",
        "## Gaps between today and planned",
        "## Decisions",
        "## Did it work?",
        "## Sources",
        "## Words we use",
        "## Who is speaking",
    ):
        assert heading in text
    assert "not medical advice" in text


def test_committed_example_outputs_are_current():
    for mp in sorted(EX.glob("*/model.json")):
        m = load(mp)
        assert (mp.parent / "canvas.html").read_text(encoding="utf-8").rstrip(
            "\n"
        ) == dc.render(m).rstrip("\n"), mp
        assert (mp.parent / "in-words.md").read_text(encoding="utf-8").rstrip(
            "\n"
        ) == dc.words(m).rstrip("\n"), mp


def test_help_is_a_skill_and_every_capability_has_one():
    s = skill()
    assert s.startswith('<skill_content name="decisioncraft">') and s.endswith(
        "</skill_content>"
    )
    assert "Skill directory:" in s
    for name, c in CAPABILITIES.items():
        assert f"`{name}` [{c['kind']}]" in s
        cs = capability_skill(name)
        assert cs.startswith(f'<skill_content name="decisioncraft {name}">')
        assert c["example"] in cs


def test_manifest_matches_packaged_frontmatter():
    text = (ROOT / "src" / "decisioncraft" / "SMART_TOOL.md").read_text(
        encoding="utf-8"
    )
    front = text.split("---", 2)[1]
    assert re.search(r"^name: decisioncraft$", front, re.M)
    assert re.search(rf"^version: {dc.manifest()['version']}$", front, re.M)
    py = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert f'version = "{dc.manifest()["version"]}"' in py


def test_cli_deterministic_paths_run_without_credentials(tmp_path):
    run("--help")
    run("-h")
    assert json.loads(run("manifest").stdout)["capabilities"]["draft"] == "model-backed"
    run("templates")
    run("roles")
    run("render", "--help")
    model = tmp_path / "m.json"
    run(
        "new",
        "--template",
        "service-blueprint",
        "--title",
        "T",
        "--question",
        "Q?",
        "--out",
        str(model),
    )
    run("validate", str(model))
    run(
        "render", str(EX / "business" / "model.json"), "--out", str(tmp_path / "c.html")
    )
    run(
        "words", str(EX / "engineering" / "model.json"), "--out", str(tmp_path / "w.md")
    )
    qs = json.loads(run("questions", str(EX / "business" / "model.json")).stdout)
    assert qs[0]["urgency"] == "must"
    reviews = [str(p) for p in sorted((EX / "business" / "reviews").glob("*.json"))]
    merged = json.loads(
        run("merge", str(EX / "business" / "model.json"), *reviews).stdout
    )
    assert len(merged["reviewers"]) == 2
    d = json.loads(
        run(
            "diff",
            str(EX / "technical" / "model-before.json"),
            str(EX / "technical" / "model.json"),
        ).stdout
    )
    assert d["changed"]


def test_cli_errors_exit_nonzero(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text('{"format": "decisioncraft/1"}')
    assert run("validate", str(bad), ok=False).returncode == 1
    assert run("render", str(bad), ok=False).returncode == 1
    assert run("render", str(tmp_path / "missing.json"), ok=False).returncode == 1
    assert run("no-such-command", ok=False).returncode != 0


def test_model_backed_paths_need_an_explicit_provider(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("Some notes.")
    r = run(
        "draft",
        str(note),
        "--template",
        "decision-chain",
        "--question",
        "Q?",
        "--provider",
        "anthropic",
        ok=False,
    )
    # exit 3: something must be set up first (contracts/cli.v1.md)
    assert r.returncode == 3 and "ANTHROPIC_API_KEY" in r.stderr
    r = run(
        "draft", str(note), "--template", "decision-chain", "--question", "Q?", ok=False
    )
    assert r.returncode != 0


def test_complete_cmd_runs_the_model_backed_path_with_no_sdk_and_no_key(tmp_path):
    """--complete-cmd routes draft through an external command instead of a vendor SDK."""
    note = tmp_path / "n.md"
    note.write_text("Some notes.")
    script = tmp_path / "fake_complete.py"
    script.write_text(
        "import json, sys\n"
        "json.load(sys.stdin)\n"
        "print(json.dumps({\n"
        "    'format': 'decisioncraft/1', 'title': 'T', 'question': 'Q?', 'summary': '',\n"
        "    'checked': {'date': '', 'note': ''}, 'roles': [], 'glossary': {}, 'sources': [],\n"
        "    'evidence': [], 'gaps': [], 'notes': [], 'decisions': [], 'outcomes': [],\n"
        "    'maps': [{'id': 'm1', 'template': 'opportunity-tree', 'title': 'x', 'intro': 'x',\n"
        "              'levels': ['Outcome', 'Need or pain', 'Idea', 'Quick test'],\n"
        "              'root': {'id': 'root', 'title': 'x', 'text': '', 'children': []}}],\n"
        "}))\n"
    )
    r = run(
        "draft",
        str(note),
        "--template",
        "opportunity-tree",
        "--question",
        "Q?",
        "--complete-cmd",
        f"{sys.executable} {script}",
    )
    assert json.loads(r.stdout)["title"] == "T"


def test_complete_cmd_failure_is_a_clean_error(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("Some notes.")
    r = run(
        "draft",
        str(note),
        "--template",
        "decision-chain",
        "--question",
        "Q?",
        "--complete-cmd",
        f'{sys.executable} -c "import sys; sys.exit(1)"',
        ok=False,
    )
    # exit 4: the model call failed
    assert r.returncode == 4 and "--complete-cmd failed" in r.stderr


def test_neither_provider_nor_complete_cmd_is_a_clean_error(tmp_path):
    note = tmp_path / "n.md"
    note.write_text("Some notes.")
    r = run(
        "draft", str(note), "--template", "decision-chain", "--question", "Q?", ok=False
    )
    # exit 3: nothing is set up to answer; the message says how to fix it
    assert (
        r.returncode == 3 and "ANTHROPIC_API_KEY" in r.stderr and "--complete-cmd" in r.stderr
    )


def test_draft_and_perspectives_with_a_supplied_completion():
    """A host can pass its own model function; the reply is validated and repaired once."""
    target = load(EX / "engineering" / "model.json")
    calls = []

    def fake(system, prompt):
        calls.append(prompt)
        if len(calls) == 1:
            return 'here you go: {"format": "decisioncraft/1"}'  # invalid on purpose
        return json.dumps(target)

    out = dc.draft(
        [{"name": "notes.md", "text": "notes"}],
        template="decision-chain",
        question=target["question"],
        complete=fake,
    )
    assert out["title"] == target["title"] and len(calls) == 2
    assert "problems" in calls[1]

    def fake_notes(system, prompt):
        return json.dumps(
            {
                "notes": [
                    {
                        "id": "P1",
                        "role": "finance",
                        "anchor": "G1",
                        "title": "t",
                        "body": "b",
                        "question": "q?",
                        "urgency": "info",
                        "evidence": ["E4"],
                    }
                ]
            }
        )

    more = dc.perspectives(target, complete=fake_notes)
    assert len(more["notes"]) == len(target["notes"]) + 1
