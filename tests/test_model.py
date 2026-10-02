import json
from pathlib import Path

import pytest

import decisioncraft as dc
from decisioncraft.model import ModelError, require_valid

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
MODELS = sorted(EXAMPLES.glob("*/model.json"))


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def test_the_examples_exist():
    assert {p.parent.name for p in MODELS} == {
        "business",
        "technical",
        "engineering",
        "medical",
        "personal-car",
        "bike-hire-map",
    }


@pytest.mark.parametrize("path", MODELS, ids=lambda p: p.parent.name)
def test_examples_have_no_errors(path):
    errors = [p for p in dc.validate(load(path)) if p["level"] == "error"]
    assert errors == []


def test_every_template_is_used_by_an_example():
    used = {m["template"] for p in MODELS for m in load(p)["maps"]}
    # personal-decision is a starting set of maps, not a map template of its own
    assert used == {t["id"] for t in dc.templates() if t["kind"] != "set"}


@pytest.mark.parametrize("template", [t["id"] for t in dc.templates()])
def test_new_model_from_each_template_is_valid(template):
    m = dc.new(template, "Title", "What should we do?")
    assert [p for p in dc.validate(m, allow_empty=True) if p["level"] == "error"] == []
    # Untouched, it is a starter, not a map: plain validate says the map is empty.
    assert any("map is empty" in p["message"] for p in dc.validate(m) if p["level"] == "error")


def test_unknown_template_is_refused():
    with pytest.raises(ModelError):
        dc.new("nope", "T", "Q?")


def test_validate_catches_broken_links():
    m = load(EXAMPLES / "business" / "model.json")
    m["notes"][0]["anchor"] = "missing-box"
    m["notes"][1]["role"] = "nobody"
    m["evidence"][0]["source"] = "S99"
    m["gaps"][0]["impact"] = 9
    messages = " ".join(p["message"] for p in dc.validate(m) if p["level"] == "error")
    assert "unknown box" in messages
    assert "unknown role" in messages
    assert "unknown source" in messages
    assert "1 to 5" in messages


def test_validate_catches_duplicate_ids():
    m = load(EXAMPLES / "technical" / "model.json")
    m["notes"][1]["id"] = m["notes"][0]["id"]
    assert any("used twice" in p["message"] for p in dc.validate(m))


def test_validate_warns_about_filler_words_and_missing_evidence():
    m = dc.new("decision-chain", "T", "Q?")
    m["summary"] = "We will leverage a seamless approach."
    probs = dc.validate(m)
    assert any(p["level"] == "warning" and "leverage" in p["message"] for p in probs)


def test_require_valid_raises_with_every_problem():
    with pytest.raises(ModelError) as e:
        require_valid({"format": "decisioncraft/1"})
    assert len(e.value.problems) >= 2


def test_validate_reports_wrong_field_types_instead_of_crashing():
    m = {
        "format": "decisioncraft/1",
        "title": "T",
        "question": "Q?",
        "maps": "oops",
        "roles": "oops",
        "sources": "oops",
        "evidence": "oops",
        "gaps": "oops",
        "notes": "oops",
        "decisions": "oops",
        "outcomes": "oops",
    }
    errors = [p for p in dc.validate(m) if p["level"] == "error"]
    assert any("maps" in p["path"] for p in errors)
    assert any(p["path"] == "roles" for p in errors)


def test_validate_reports_non_object_items_in_lists():
    m = load(EXAMPLES / "business" / "model.json")
    m["sources"] = m["sources"] + ["oops"]
    m["notes"] = m["notes"] + [42]
    errors = [p for p in dc.validate(m) if p["level"] == "error"]
    assert any("sources" in p["path"] and "object" in p["message"] for p in errors)
    assert any("notes" in p["path"] and "object" in p["message"] for p in errors)


def test_default_roles_cover_the_room():
    ids = {r["id"] for r in dc.roles()}
    assert {
        "designer",
        "analyst",
        "engineer",
        "owner",
        "security",
        "voice",
        "agent",
        "finance",
    } <= ids
    assert all(r.get("asks") for r in dc.roles())
