"""Which model answers, and how a real model's reply is made reliable. No network: every
model here is a stand-in function."""

import json

import pytest

from decisioncraft import intelligence as I
from decisioncraft.model import ModelError, validate

from stub_map import bike_model


@pytest.fixture(autouse=True)
def clean_env(monkeypatch, tmp_path):
    for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "DECISIONCRAFT_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DECISIONCRAFT_CONFIG", str(tmp_path / "config.json"))


# --- which model answers -------------------------------------------------------------

def test_no_key_says_what_to_set():
    with pytest.raises(I.ProviderError, match="ANTHROPIC_API_KEY or OPENAI_API_KEY"):
        I.resolve()


def test_picks_anthropic_first_with_its_default_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    r = I.resolve()
    assert (r["provider"], r["model"]) == ("anthropic", "claude-sonnet-5-5")
    assert r["escalate"] == "claude-opus-5-5"
    assert "ANTHROPIC_API_KEY is set" in r["why"]


def test_falls_back_to_openai(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    r = I.resolve()
    assert (r["provider"], r["model"]) == ("openai", "gpt-5.5")


def test_precedence_flag_then_env_then_config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    monkeypatch.setenv("OPENAI_API_KEY", "y")
    I.save_config({"provider": "openai", "model": "gpt-5.5"})
    assert I.resolve()["provider"] == "openai"
    monkeypatch.setenv("DECISIONCRAFT_PROVIDER", "anthropic")
    monkeypatch.setenv("DECISIONCRAFT_MODEL", "claude-opus-5-5")
    r = I.resolve()
    assert (r["provider"], r["model"]) == ("anthropic", "claude-opus-5-5")
    assert r["escalate"] is None  # already not the everyday model
    r = I.resolve("openai", "gpt-5.5")
    assert (r["provider"], r["model"]) == ("openai", "gpt-5.5")


def test_config_model_for_another_provider_is_ignored(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    I.save_config({"provider": "openai", "model": "gpt-5.5"})
    r = I.resolve("anthropic")
    assert r["model"] == "claude-sonnet-5-5"


def test_named_provider_without_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
    with pytest.raises(I.ProviderError, match="export OPENAI_API_KEY"):
        I.resolve("openai")


def test_config_rejects_unknown_keys_and_providers():
    with pytest.raises(ValueError):
        I.save_config({"colour": "blue"})
    with pytest.raises(ValueError):
        I.save_config({"provider": "acme"})
    I.save_config({"model": "m"})
    assert I.load_config() == {"model": "m"}
    I.save_config({"model": None})
    assert I.load_config() == {}


# --- reading replies -----------------------------------------------------------------

def test_json_from_prefers_the_real_answer_over_an_example():
    reply = 'For example {"a": 1}. Here it is:\n```json\n{"format": "x", "maps": [1, 2, 3]}\n```'
    assert I._json_from(reply) == {"format": "x", "maps": [1, 2, 3]}


def test_json_from_whole_reply_with_fences():
    assert I._json_from('```json\n{"x": {"y": 1}}\n```') == {"x": {"y": 1}}


# --- tidy: the slips real models make ------------------------------------------------

def _slipped() -> dict:
    m = bike_model()
    m["evidence"][0]["kind"] = "code"
    m["evidence"][1]["kind"] = "fact"
    m["evidence"][2] = {"id": "E3", "source": "S9", "quote": "  21| TODO: no way to record damage here"}
    m["evidence"].append({"id": "E9", "source": "S1", "kind": "quote", "text": ""})
    m["maps"][0]["journeys"][0]["steps"][0]["evidence"].append("E9")
    g = m["gaps"][0]
    g["done_when"] = ["A test booking works"]
    g["stories"] = ["As a visitor, I want X, so that Y."]
    m.setdefault("decisions", []).append({"id": "s1", "title": "Choose", "question": "Which?"})
    return m


def test_tidy_fixes_kinds_quotes_sources_stories_and_ids():
    m = _slipped()
    warnings = I.tidy(m, [{"name": "app.py", "text": "  21| TODO: no way to record damage here"}])
    kinds = {e["id"]: e.get("kind") for e in m["evidence"]}
    assert kinds["E1"] == "quote" and kinds["E2"] == "data"
    e3 = next(e for e in m["evidence"] if e["id"] == "E3")
    assert e3["text"] == "TODO: no way to record damage here"
    assert any(s["id"] == "S9" for s in m["sources"])
    assert all(e["id"] != "E9" for e in m["evidence"])
    assert "E9" not in m["maps"][0]["journeys"][0]["steps"][0]["evidence"]
    story = m["gaps"][0]["stories"][0]
    assert story["as"].startswith("As a visitor") and story["done_when"] == ["A test booking works"]
    assert m["decisions"][-1]["id"] == "decision-s1"
    assert warnings
    assert [p for p in validate(m) if p["level"] == "error"] == []


def test_tidy_marks_quotes_not_in_the_material():
    m = bike_model()
    I.tidy(m, [{"name": "README.md", "text": "nothing that matches"}])
    assert all(e.get("unverified") for e in m["evidence"] if e.get("kind", "quote") == "quote")


# --- asking, repairing, escalating ---------------------------------------------------

def test_repair_then_escalate_once():
    calls = []
    good = json.dumps(bike_model())

    def weak(system, prompt):
        calls.append("weak")
        return '{"format": "nope"}'

    def strong(system, prompt):
        calls.append("strong")
        return good

    check = lambda v: [p["message"] for p in validate(v) if p["level"] == "error"]  # noqa: E731
    v = I._ask(weak, "s", "p", check, escalate=strong)
    assert calls == ["weak", "weak", "strong"]
    assert v["title"]


def test_truncated_reply_becomes_a_repair_then_an_error():
    def cut(system, prompt):
        raise I.TruncatedReply("stopped at its length limit")

    with pytest.raises(ModelError) as e:
        I._ask(cut, "s", "p", lambda v: [])
    assert "length limit" in str(e.value.problems[0]["message"])


def test_perspectives_asks_each_role_in_parallel():
    m = bike_model()
    before = len(m.get("notes", []))
    seen = []

    def stub(system, prompt):
        role = json.loads(prompt.split("each of these roles:\n", 1)[1].split("\nAsk only", 1)[0])[0]["id"]
        seen.append(role)
        prefix = prompt.split("Use ids that start with '", 1)[1].split("'", 1)[0]
        return json.dumps({"notes": [{"id": f"{prefix}1", "role": role, "anchor": "s1", "title": "T",
                                      "body": "Why it matters.", "question": "Will it?", "urgency": "info"}]})

    out = I.perspectives(m, complete=stub, per_role=1, parallel=True)
    assert sorted(seen) == sorted(r["id"] for r in m["roles"])
    assert len(out["notes"]) - before == len(m["roles"])
    assert len({n["id"] for n in out["notes"]}) == len(out["notes"])


def test_tidy_moves_planned_steps_next_to_what_they_replace():
    m = bike_model()
    j = m["maps"][0]["journeys"][0]
    planned = [s for s in j["steps"] if s.get("replaces")]
    for s in planned:
        j["steps"].remove(s)
    m["maps"][0]["journeys"].append({"id": "j-plan", "title": "Planned", "steps": planned})
    I.tidy(m)
    ids = [s["id"] for s in m["maps"][0]["journeys"][0]["steps"]]
    assert ids.index("s3p") == ids.index("s3") + 1
    assert all(jj["id"] != "j-plan" for jj in m["maps"][0]["journeys"])
    assert [p for p in validate(m) if p["level"] == "error"] == []


@pytest.mark.parametrize("raw,want", [("3", 3), (3.6, 4), ("Medium", 3), ("M", 3), ("4/5", 4), (9, 5),
                                      ("not sure", None)])
def test_scale(raw, want):
    assert I._scale(raw) == want


def test_tidy_comparison_slips():
    m = bike_model()
    m["comparison"] = {
        "criteria": [{"id": "c1", "label": "Cost", "importance": "High"}],
        "options": [{"id": "o1", "title": "A", "evaluations": [
            {"criterion": "c1", "judgment": "partial", "reason": ["cheap", "but slow"]}]},
                    {"id": "o2", "title": "B", "evaluations": []}],
        "recommendation": {"option": "o1", "reason": "Cheaper.", "risks": ["slow", "untested"]},
    }
    I.tidy(m)
    c = m["comparison"]
    assert c["criteria"][0]["importance"] == "must"
    ev = c["options"][0]["evaluations"][0]
    assert ev["judgment"] == "mixed" and ev["reason"] == "cheap; but slow"
    assert c["recommendation"]["risks"] == "slow; untested"
    assert [p for p in validate(m) if p["level"] == "error"] == []


def test_tidy_keeps_today_boxes_that_nothing_replaces():
    m = bike_model()
    steps = m["maps"][0]["journeys"][0]["steps"]
    for s in steps:
        if not s.get("when"):
            s["when"] = "today"
    steps.append({"id": "gone", "lane": "people", "text": "Paper sign-up sheet", "when": "today", "goes_away": True})
    I.tidy(m)
    whens = {s["id"]: s.get("when") for s in steps}
    assert whens["s1"] is None and whens["s3"] == "today" and whens["gone"] == "today"
