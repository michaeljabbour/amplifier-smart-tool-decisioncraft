"""Regression tests for bugs found walking the command line as a new user."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from decisioncraft import interview as iv
from decisioncraft.cli import _merge_text

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"), DECISIONCRAFT_NO_BROWSER="1")


def cli(*args, stdin=""):
    return subprocess.run([sys.executable, "-m", "decisioncraft", *args], capture_output=True, text=True,
                          env=ENV, input=stdin, timeout=60)


def jcli(*args):
    r = cli("--json", *args)
    return r, json.loads(r.stdout)


# ----------------------------------------------------------- interview answers


@pytest.mark.parametrize("answer", ["not sure", "idk", "I don't know", "no idea", "?", "dunno", "", "skip"])
def test_unsure_answers_never_become_options_or_must_haves(tmp_path, answer):
    iv.start(tmp_path, question="should I renew my lease or buy a used car")
    iv.step(tmp_path, answer)  # options: keeps the suggested two
    iv.step(tmp_path, answer)  # must-haves: none, still to find out
    state = iv.load(tmp_path)
    assert state["answers"]["options"] == ["Renew my lease", "Buy a used car"]
    assert state["answers"]["must_haves"] == []
    assert "must_haves" in state["unsure"]


def test_still_to_find_out_lands_in_the_starter_model(tmp_path):
    iv.start(tmp_path, question="should I renew my lease or buy a used car")
    for answer in ["", "not sure", "safety", "March", "idk", "me and the kids", "not sure", "fuel prices", "x"]:
        r = iv.step(tmp_path, answer)
        if r["done"]:
            break
    model = json.loads((tmp_path / "model.json").read_text())
    names = [o["name"] for o in model["options"]]
    assert "Not sure" not in names and "Idk" not in names
    assert "Still to find out:" in model["summary"] and "the must-haves" in model["summary"]


@pytest.mark.parametrize("text,choice", [
    ("March", None),                      # 'a' in 'A team' must not match
    ("me and the kids", "Me and my family or household"),
    ("just me", "Just me"),
    ("my team at work", "A team"),
    ("several departments", "Several groups"),
    ("2", "Me and my family or household"),
])
def test_people_choice_matches_whole_words(text, choice):
    assert iv._parse_choice(text, iv.PEOPLE_CHOICES) == choice


def test_interview_next_with_answer_records_it_and_accepts_text(tmp_path):
    r, d = jcli("interview", "--dir", str(tmp_path), "--next", "--text", "should I renew my lease or buy a used car")
    assert d["ok"] and d["result"]["question"]["id"] == "options"
    r, d = jcli("interview", "--dir", str(tmp_path), "--next", "--answer", "those two")
    assert d["result"]["question"]["id"] != "options"


# ----------------------------------------------------------------- quick, triage


@pytest.mark.parametrize("text,options", [
    ("pizza or tacos tonight?", ["Pizza", "Tacos"]),
    ("Postgres vs SQLite", ["Postgres", "SQLite"]),
    ("between the red one and the blue one", ["The red one", "The blue one"]),
    ("keep it, renew the lease, or buy new", ["Keep it", "Renew the lease", "Buy new"]),
    ("laptop: mac or pc", ["Mac", "Pc"]),
    ("what should I eat", []),
])
def test_options_from_plain_words(text, options):
    assert iv.options_from_text(text) == options


def test_quick_reads_options_from_text_without_a_model():
    r, d = jcli("quick", "--text", "pizza or tacos tonight?")
    assert r.returncode == 0 and [o["title"] for o in d["result"]["options"]] == ["Pizza", "Tacos"]


def test_quick_without_options_says_how_to_name_them():
    r, d = jcli("quick", "--text", "what should I eat")
    assert r.returncode == 2 and "--option" in d["error"]["message"]


def test_quick_text_reaches_the_model_when_plain_words_are_not_enough(tmp_path):
    stub = tmp_path / "reply.py"
    stub.write_text("import json,sys;json.load(sys.stdin);print(json.dumps({'options':['Air','ThinkPad','Chromebook'],"
                    "'criteria':[{'label':'Price','importance':'important'}],'scores':[]}))")
    r, d = jcli("quick", "--text", "I can't decide what laptop to get for school, maybe a macbook air or a thinkpad "
                "or a chromebook, budget is tight", "--complete-cmd", f"{sys.executable} {stub}")
    assert r.returncode == 0, r.stdout
    assert [o["title"] for o in d["result"]["options"]] == ["Air", "ThinkPad", "Chromebook"]


def test_triage_with_nothing_to_go_on_is_a_usage_error():
    r, d = jcli("triage")
    assert r.returncode == 2 and d["error"]["field"] == "--text"


# ----------------------------------------------------------------------- handoff


def test_handoff_accepts_a_review_without_a_fingerprint(tmp_path):
    model = json.loads((ROOT / "examples/business/model.json").read_text())
    review = json.loads((ROOT / "examples/business/reviews/review-owner.json").read_text())
    review.pop("model_fingerprint", None)
    (tmp_path / "r.json").write_text(json.dumps(review))
    r, d = jcli("handoff", str(ROOT / "examples/business/model.json"), str(tmp_path / "r.json"))
    assert d["ok"], d
    review["model_fingerprint"] = "000000000000"
    (tmp_path / "r.json").write_text(json.dumps(review))
    r, d = jcli("handoff", str(ROOT / "examples/business/model.json"), str(tmp_path / "r.json"))
    assert not d["ok"] and "earlier version" in d["error"]["message"]
    assert model["title"]


def test_every_example_review_hands_off():
    for review in ROOT.glob("examples/*/reviews/*.json"):
        r, d = jcli("handoff", str(review.parent.parent / "model.json"), str(review))
        assert d["ok"], (review, d.get("error"))


# ------------------------------------------------------------ errors and output


def test_unknown_option_names_the_command_and_suggests_one():
    r = cli("quick", "--options", "A,B")
    assert r.returncode == 2
    assert "decisioncraft quick:" in r.stderr and "--option" in r.stderr and "decisioncraft quick -h" in r.stderr
    r, d = jcli("map", ".", "--out", "x.html")
    assert d["command"] == "map" and "--dir" in d["error"]["message"]


def test_merge_reads_as_words():
    model = json.loads((ROOT / "examples/personal-car/model.json").read_text())
    import decisioncraft as dc
    reviews = [json.loads(p.read_text()) for p in sorted(ROOT.glob("examples/personal-car/reviews/*.json"))]
    text = _merge_text(dc.merge(reviews, model), model)
    assert "2 reviewers" in text and "Safety features: Dana 4, Sam (partner) 5" in text
    assert "1 dots" not in text


def test_broken_pipe_is_quiet():
    p = subprocess.Popen([sys.executable, "-m", "decisioncraft", "render", str(ROOT / "examples/business/model.json")],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
    p.stdout.read(10)
    p.stdout.close()
    err = p.stderr.read().decode()
    p.wait(timeout=60)
    assert "Traceback" not in err


def test_version_as_json():
    r = cli("--version", "--json")
    assert json.loads(r.stdout)["result"]["version"]
