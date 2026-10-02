"""Today, the plan and what changes: validation, the change list and the text version."""

import decisioncraft as dc
from decisioncraft.model import plan_changes


def chain_model():
    m = dc.new("decision-chain", "Change check", "Should we change it?")
    m["maps"][0]["stages"] = [dict(id="s1", label="Work", items=[
        dict(id="old", title="Download a file", when="today"),
        dict(id="new", title="Answers reach the agent", when="planned", replaces="old"),
        dict(id="add", title="A reminder the day before", when="planned"),
        dict(id="drop", title="Print the form", when="today"),
        dict(id="keep", title="The owner decides"),
    ])]
    return m


def test_plan_changes_reads_each_box_once_in_plan_order():
    changes = plan_changes(chain_model()["maps"][0])
    assert [(c["change"], c["box"]["id"]) for c in changes] == [
        ("changed", "new"), ("new", "add"), ("gone", "drop")]
    assert changes[0]["before"]["id"] == "old"


def test_replaces_must_point_at_a_today_only_box_beside_it():
    m = chain_model()
    assert [e for e in dc.validate(m) if e["level"] == "error"] == []
    m["maps"][0]["stages"][0]["items"][1]["replaces"] = "keep"
    assert any(e["path"].endswith("replaces") for e in dc.validate(m))
    m["maps"][0]["stages"][0]["items"][1]["replaces"] = "old"
    m["maps"][0]["stages"][0]["items"][1]["when"] = "both"
    assert any("Only a planned" in e["message"] for e in dc.validate(m))


def test_journey_steps_take_when_and_replaces():
    m = dc.new("system-journeys", "Steps", "Q?")
    lane = m["maps"][0]["lanes"][0]["id"]
    m["maps"][0]["journeys"] = [dict(id="j", title="J", steps=[
        dict(id="a", lane=lane, text="Send the whole file", when="today"),
        dict(id="b", lane=lane, text="Upload in pieces", when="planned", replaces="a"),
        dict(id="c", lane=lane, text="Show the result")])]
    assert [e for e in dc.validate(m) if e["level"] == "error"] == []
    assert [c["change"] for c in plan_changes(m["maps"][0])] == ["changed"]
    m["maps"][0]["journeys"][0]["steps"][2]["when"] = "later"
    assert any(e["path"].endswith("steps[2].when") for e in dc.validate(m))


def test_words_list_what_changes():
    text = dc.words(chain_model())
    assert "### What changes" in text
    assert "1 new · 1 changed · 1 goes away." in text
    assert "**Changed:** Download a file → Answers reach the agent" in text
