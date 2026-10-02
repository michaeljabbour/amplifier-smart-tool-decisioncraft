"""Modes: triage's rule, quick's table and lean, the interview, and their CLI results."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import decisioncraft as dc
from decisioncraft import interview as iv
from decisioncraft.modes import infer, looks_like_choice

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"), DECISIONCRAFT_NO_BROWSER="1")


def cli(*args, env=None, stdin=""):
    return subprocess.run([sys.executable, "-m", "decisioncraft", *args], capture_output=True, text=True,
                          env=env or ENV, input=stdin, timeout=60)


# ------------------------------------------------------------------ triage


@pytest.mark.parametrize("text,mode", [
    ("My lease is up in March, not sure whether to renew it or just buy the car outright", "guided"),
    ("I got two job offers, one pays more but the other is remote", "guided"),
    ("Our team needs to pick a vendor for payroll", "team"),
    ("Should our ward change how we discharge patients so fewer come back?", "team"),
    ("pizza or tacos tonight?", "none"),
    ("which font for my slides", "none"),
    ("what is the capital of France", "none"),
])
def test_triage_from_words(text, mode):
    assert dc.triage(text=text)["mode"] == mode


def test_triage_rule_from_answers():
    assert dc.triage({"cost": 30000, "reversible": "hard", "people": "family"})["mode"] == "guided"
    assert dc.triage({"cost": 50, "reversible": "easy", "people": "just me"})["mode"] == "none"
    assert dc.triage({"cost": 500, "reversible": "some cost", "people": "just me"})["mode"] == "quick"
    assert dc.triage({"cost": "large", "reversible": "hard", "people": "team"})["mode"] == "team"
    assert dc.triage({"people": "several groups"})["mode"] == "team"


def test_triage_deadline_today_steps_down_with_an_alternative():
    r = dc.triage({"cost": 30000, "reversible": "hard", "people": "just me", "deadline": "today"})
    assert r["mode"] == "quick" and r["alternative"] == "guided"


def test_triage_lists_what_is_unknown_and_counts_it_as_the_middle():
    r = dc.triage({"cost": "large"})
    assert {m["id"] for m in r["missing"]} == {"reversible", "people"}
    assert r["stakes"]["score"] == 4 and r["mode"] == "guided"


def test_triage_answers_win_over_words():
    assert dc.triage({"people": "just me", "reversible": "easy", "cost": 20}, text="our team vendor")["mode"] == "none"


def test_triage_is_deterministic_and_offers_rather_than_takes_over():
    a = dc.triage(text="renew the lease or buy the car?")
    assert a == dc.triage(text="renew the lease or buy the car?")
    assert a["offer"].startswith("Offer:") and "?" in a["offer"]


def test_triage_can_read_text_with_a_model():
    calls = []

    def complete(system, prompt):
        calls.append(prompt)
        return '{"cost": 40000, "reversible": "hard", "people": "family", "deadline": null}'

    r = dc.triage(text="the thing with the house", complete=complete)
    assert calls and r["stakes"]["people"] == 1 and r["mode"] == "guided"


def test_word_rules():
    assert infer("$25k car")["cost"] == 25000
    assert infer("we need a vendor")["people"] == "team"
    assert looks_like_choice("torn between two schools") and not looks_like_choice("what time is it")


# ------------------------------------------------------------------ quick


SCORES = {"Renew lease": {"monthly cost": 3, "reliability": 5, "space": 3},
          "Buy outright": {"monthly cost": 4, "reliability": 3, "space": 4},
          "Do nothing": {"monthly cost": 5, "reliability": 2}}


def test_quick_table_lean_and_check():
    r = dc.quick(["Renew lease", "Buy outright", "Do nothing"], ["must:monthly cost", "reliability", "space"], SCORES)
    assert r["format"] == "decisioncraft-quick/1"
    assert r["table"].splitlines()[0].startswith("| Option | monthly cost (must)")
    assert r["lean"]["option"] == "renew-lease" and r["lean"]["close_call"] is True
    assert "monthly cost" in r["check_first"]["text"]
    assert r["options"][2]["unknown"] == ["space"]
    assert "?" in r["table"]


def test_quick_must_have_failure_ranks_last():
    r = dc.quick(["Cheap", "Safe"], ["must:safety", "price"], {"Cheap": {"safety": 2, "price": 5}, "Safe": {"safety": 5, "price": 2}})
    assert r["options"][-1]["title"] == "Cheap" and r["options"][-1]["fails_must"] == ["safety"]
    assert r["lean"]["option"] == "safe"


def test_quick_without_scores_says_what_to_ask():
    r = dc.quick(["A", "B"], ["cost"])
    assert r["lean"] is None and r["ask"]


def test_quick_rejects_bad_input():
    with pytest.raises(ValueError):
        dc.quick(["only one"], ["cost"])
    with pytest.raises(ValueError):
        dc.quick(["A", "B"], ["cost"], {"A": {"cost": 9}})
    with pytest.raises(ValueError):
        dc.quick(text="renew or buy?")


def test_quick_reads_text_with_a_model():
    def complete(system, prompt):
        return json.dumps({"question": "Renew or buy?", "options": ["Renew", "Buy"],
                           "criteria": [{"label": "cost", "importance": "must"}],
                           "scores": [{"option": "Renew", "criterion": "cost", "score": 4},
                                      {"option": "Buy", "criterion": "cost", "score": 2}]})
    r = dc.quick(text="lease is up, renew or buy?", complete=complete)
    assert r["question"] == "Renew or buy?" and r["lean"]["title"] == "Renew"


# ------------------------------------------------------------------ interview


CAR = {"options": "also buy something used", "must_haves": "under 500 a month",
       "criteria": "monthly cost, reliability, space for the kids", "deadline": "by 15 March",
       "budget": "30k", "people": "2", "known": "repair estimate is 2000", "whatifs": "petrol prices rise"}


def run_interview(folder, first, answers):
    r = dc.interview_step(folder, question=first)
    seen = []
    while not r["done"]:
        q = r["question"]
        seen.append(q["id"])
        r = dc.interview_step(folder, answers.get(q["id"], "not sure"))
    return r, seen


def test_interview_car_one_question_at_a_time(tmp_path):
    r, seen = run_interview(tmp_path / "car", "My lease ends in March, should I renew it or buy the car outright?", CAR)
    assert seen[0] == "options" and "reversible" not in seen  # 'buy' and 'lease' already say hard to undo
    assert r["mode"] == "guided" and Path(r["model_path"]).is_file()
    model = json.loads(Path(r["model_path"]).read_text())
    assert [o["title"] for o in model["comparison"]["options"]] == ["Renew it", "Buy the car outright", "Buy something used"]
    assert model["comparison"]["criteria"][0] == {"id": "under-500-a-month", "label": "Under 500 a month", "importance": "must"}
    assert not [p for p in dc.validate(model) if p["level"] == "error"]
    assert (tmp_path / "car" / "material" / "README.txt").is_file()


def test_interview_state_survives_between_calls(tmp_path):
    folder = tmp_path / "x"
    first = dc.interview_step(folder, question="renew the lease or buy the car?")
    assert first["question"]["id"] == "options" and first["question"]["suggested"] == ["Renew the lease", "Buy the car"]
    state = json.loads((folder / "interview.json").read_text())
    assert state["pending"] == "options"
    again = iv.step(folder, None)
    assert again["question"]["id"] == "options"
    nxt = dc.interview_step(folder, "that's it")
    assert nxt["known"]["options"] == ["Renew the lease", "Buy the car"]


def test_interview_stops_at_once_for_a_trivial_choice(tmp_path):
    r = dc.interview_step(tmp_path / "p", question="pizza or tacos tonight")
    assert r["done"] and r["mode"] == "none" and r["model_path"] is None
    assert not (tmp_path / "p" / "model.json").exists()


def test_interview_low_stakes_asks_only_the_core(tmp_path):
    r, seen = run_interview(tmp_path / "q", "which of two $300 desk chairs should I get",
                            {"options": "the mesh one, the leather one", "criteria": "comfort, looks",
                             "deadline": "this week", "reversible": "easy", "people": "just me"})
    assert "budget" not in seen and "whatifs" not in seen and "known" not in seen
    assert r["mode"] == "quick"


def test_interview_team_set_and_template(tmp_path):
    r, seen = run_interview(tmp_path / "t", "Our team needs to pick a payroll vendor",
                            {"options": "Vendor A, Vendor B, stay as we are", "criteria": "cost, support",
                             "deadline": "next month", "reversible": "hard", "owner": "the finance lead",
                             "groups": "finance, staff, IT", "visual": "3"})
    assert "owner" in seen and "groups" in seen and r["mode"] == "team"
    assert json.loads(Path(r["model_path"]).read_text())["maps"][0]["template"] == "decision-chain"


def test_interview_reset_and_finished(tmp_path):
    folder = tmp_path / "z"
    run_interview(folder, "renew the lease or buy the car?", CAR)
    done = dc.interview_step(folder, "more")
    assert done["done"] and "--reset" in done["message"]
    fresh = dc.interview_step(folder, reset=True)
    assert fresh["question"]["id"] == "decision"


def test_question_bank():
    bank = dc.interview_questions()
    assert {"personal", "team", "system"} == set(bank)
    assert any(q["id"] == "whatifs" for q in bank["personal"])
    assert all(q.get("why") for qs in bank.values() for q in qs)


# ------------------------------------------------------------------ command line


def test_cli_triage_json():
    r = cli("triage", "--text", "my lease is up, renew or buy the car?", "--json")
    env = json.loads(r.stdout)
    assert r.returncode == 0 and env["ok"] and env["result"]["mode"] == "guided" and env["next"]


def test_cli_quick_json_and_errors():
    r = cli("quick", "--option", "Renew", "--option", "Buy", "--criterion", "must:cost", "--score", "Renew=cost=3",
            "--score", "Buy=cost=4", "--json")
    env = json.loads(r.stdout)
    assert env["ok"] and env["result"]["lean"]["title"] == "Buy"
    bad = cli("quick", "--option", "A", "--option", "B", "--score", "A=cost", "--json")
    assert bad.returncode == 2 and json.loads(bad.stdout)["error"]["field"] == "--score"
    none = cli("quick", "--text", "renew or buy?", "--json")
    assert none.returncode == 2 and json.loads(none.stdout)["error"]["code"] == "missing_argument"


def test_cli_interview_json_flow_and_quick_from(tmp_path):
    d = str(tmp_path / "car")
    r = json.loads(cli("interview", "--dir", d, "--question", "renew the lease or buy the car?", "--json").stdout)
    while not r["result"]["done"]:
        qid = r["result"]["question"]["id"]
        r = json.loads(cli("interview", "--dir", d, "--answer", CAR.get(qid, "not sure"), "--json").stdout)
    assert r["ok"] and r["files"] and r["result"]["mode"] == "guided"
    q = json.loads(cli("quick", "--from", f"{d}/model.json", "--score", "Renew the lease=Monthly cost=3",
                       "--score", "Buy the car=Monthly cost=4", "--json").stdout)
    assert q["ok"] and q["result"]["lean"]["title"] == "Buy the car"


def test_cli_interview_never_prompts_without_a_terminal(tmp_path):
    r = cli("interview", "--dir", str(tmp_path / "n"), stdin="")
    assert r.returncode == 0 and "What are you trying to decide?" in r.stdout


def test_no_color_and_non_tty_output_is_plain(tmp_path):
    env = dict(ENV, NO_COLOR="1")
    r = cli("triage", "--text", "renew or buy the car?", env=env)
    assert "\x1b[" not in r.stdout + r.stderr


def test_help_lists_modes():
    r = cli("-h")
    assert "Talk a choice through:" in r.stdout and "triage" in r.stdout
    full = cli("triage", "--help")
    assert full.stdout.startswith('<skill_content name="decisioncraft triage">')
    for line in cli("interview", "-h").stdout.splitlines():
        assert len(line) <= 80


def test_skill_description_triggers_on_natural_talk():
    text = (ROOT / "skills" / "decisioncraft" / "SKILL.md").read_text()
    head = text.split("---")[1]
    for phrase in ("should I", "torn between", "pros and cons", "renew or buy", "keep or replace", "Not for factual"):
        assert phrase in head
    assert dc.manifest()["description"].startswith("Helps someone weigh a choice")
