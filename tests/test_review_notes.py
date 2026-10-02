"""Reviewers' rough notes and the experts' replies, with a stand-in model (no network)."""

import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import decisioncraft as dc
from decisioncraft.review import blank_review, check_review, fingerprint, notes_to_ask

BIN = Path(__file__).resolve().parent.parent / "bin" / "decisioncraft.py"
EX = Path(__file__).resolve().parent.parent / "examples"


@pytest.fixture
def model():
    return json.loads((EX / "business" / "model.json").read_text())


def answers(model, **note):
    r = blank_review(model, "Sam")
    r["notes"] = [dict(id="R1", anchor="ci5", text="Collection only might lose the villages.", author="Sam", **note)]
    return r


def stand_in(system, prompt):
    """Reply for every (note, role) pair the prompt lists."""
    asked = json.loads(prompt.split("who should reply:\n", 1)[1].split("\n\nFor every note", 1)[0])
    return json.dumps({"replies": [
        {"note": a["note"], "role": role, "view": f"{role} thinks about it.", "question": f"What would {role} check first?",
         "urgency": "should"} for a in asked for role in a["roles"]]})


def test_notes_are_checked_and_planned(model):
    r = answers(model, ask={"roles": ["owner", "voice"]})
    assert check_review(r) == []
    plan = notes_to_ask(model, r)
    assert [(p["note"]["id"], p["roles"]) for p in plan] == [("R1", ["owner", "voice"])]
    assert plan[0]["target"]["title"] == "Start with collection only"
    assert notes_to_ask(model, r, roles=["finance"])[0]["roles"] == ["finance"]
    bad = answers(model)
    bad["notes"][0]["replies"] = [{"id": "x", "role": "owner"}]
    assert any("view" in p for p in check_review(bad))


def test_replies_per_role_roles_filter_and_no_second_ask(model):
    out = dc.review_notes(model, answers(model, ask={"roles": ["owner", "voice"]}), complete=stand_in)
    replies = out["notes"][0]["replies"]
    assert [(r["id"], r["role"]) for r in replies] == [("R1-owner", "owner"), ("R1-voice", "voice")]
    assert all(r["view"] and r["question"] and r["author"] == "AI assistant" for r in replies)
    assert notes_to_ask(model, out) == []  # everyone asked has replied
    only = dc.review_notes(model, answers(model), roles=["finance"], complete=stand_in)
    assert [r["role"] for r in only["notes"][0]["replies"]] == ["finance"]


def test_merge_render_words_questions_and_handoff_keep_the_threads(model):
    r = dc.review_notes(model, answers(model, ask={"roles": ["owner"]}), complete=stand_in)
    r["model_fingerprint"] = fingerprint(model)
    merged = dc.merge([r], model)
    assert merged["notes"][0]["who"] == "Sam" and merged["notes"][0]["replies"][0]["id"] == "R1-owner"
    html = dc.render(model, merged=merged)
    assert "R1-owner" in html and "Collection only might lose the villages." in html
    text = dc.words(model, merged)
    assert "## Reviewer notes and expert replies" in text and "Question: What would owner check first?" in text
    q = next(q for q in dc.questions(model, merged) if q["id"] == "R1-owner")
    assert q["from_note"] == "R1" and q["where"] == "Start with collection only"
    r["answers"]["R1-owner"] = {"answer": "Check the village orders."}
    assert dc.handoff(model, r)["format"]


def test_session_asks_the_experts_without_saving(tmp_path, model):
    active = dc.session(model, tmp_path / "review", complete=stand_in)
    try:
        note = answers(model)["notes"][0]
        request = Request(active.origin + active.base + "/experts",
                          data=json.dumps({"note": note, "roles": ["owner", "analyst"]}).encode(),
                          headers={"Content-Type": "application/json", "Origin": active.origin})
        replies = json.load(urlopen(request, timeout=10))["replies"]
        assert [r["role"] for r in replies] == ["owner", "analyst"]
        assert not (tmp_path / "review" / "review.json").read_text().count("R1-owner")
    finally:
        active.close()
    plain = dc.session(model, tmp_path / "plain")
    try:
        request = Request(plain.origin + plain.base + "/experts", data=b'{"note": {}, "roles": ["owner"]}',
                          headers={"Content-Type": "application/json", "Origin": plain.origin})
        with pytest.raises(HTTPError) as e:
            urlopen(request, timeout=5)
        assert e.value.code == 501
    finally:
        plain.close()


def run(*args, cwd):
    env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")}
    env["DECISIONCRAFT_NO_BROWSER"] = "1"
    return subprocess.run([sys.executable, str(BIN), *args], cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


def test_cli_notes_dry_run_and_json_contract(tmp_path, model):
    (tmp_path / "model.json").write_text(json.dumps(model))
    (tmp_path / "answers.json").write_text(json.dumps(answers(model, ask={"roles": ["owner", "voice"]})))
    adapter = tmp_path / "adapter.py"
    adapter.write_text(
        "import json, sys\n"
        "req = json.load(sys.stdin)\n"
        "p = req['prompt']\n"
        "asked = json.loads(p.split('who should reply:\\n', 1)[1].split('\\n\\nFor every note', 1)[0])\n"
        "print(json.dumps({'replies': [{'note': a['note'], 'role': r, 'view': 'A view.', 'question': 'A question?', 'urgency': 'info'}"
        " for a in asked for r in a['roles']]}))\n")
    dry = run("perspectives", "model.json", "--notes", "answers.json", "--dry-run", "--json", cwd=tmp_path)
    doc = json.loads(dry.stdout)
    assert doc["ok"] and doc["result"]["dry_run"] and doc["result"]["asked"][0]["roles"] == ["owner", "voice"]
    real = run("perspectives", "model.json", "--notes", "answers.json", "--complete-cmd", f"{sys.executable} {adapter}",
               "--out", "replies.json", "--json", cwd=tmp_path)
    doc = json.loads(real.stdout)
    assert doc["ok"], real.stdout + real.stderr
    assert doc["result"]["replies_added"] == 2 and doc["files"]
    saved = json.loads((tmp_path / "replies.json").read_text())
    assert [r["role"] for r in saved["notes"][0]["replies"]] == ["owner", "voice"]
    no_model = run("perspectives", "--notes", "answers.json", "--json", cwd=tmp_path)
    assert json.loads(no_model.stdout)["ok"] is False and no_model.returncode == 2
