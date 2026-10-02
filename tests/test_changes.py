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


def test_lane_colours_need_contrast_with_white():
    from decisioncraft.model import lane_colour_problem
    assert lane_colour_problem("#2f6fb3") is None
    assert "too pale" in lane_colour_problem("#f7e9a0")
    assert lane_colour_problem("blue").startswith("Use")
    m = dc.new("system-journeys", "Lanes", "Q?")
    m["maps"][0]["lanes"][0]["color"] = "#fff8c0"
    assert any(e["level"] == "warning" and e["path"].endswith("lanes[0].color") for e in dc.validate(m))
    m["maps"][0]["lanes"][0]["color"] = "pale"
    assert any(e["level"] == "error" and e["path"].endswith("lanes[0].color") for e in dc.validate(m))


def test_bands_stage_extras_new_statuses_and_gap_design():
    m = chain_model()
    st = m["maps"][0]["stages"][0]
    st.update(status="planned", before="Done on paper.")
    st["items"][4].update(status="unsure", status_reason="Nobody has asked the owner yet.", kind="Behind the scenes")
    st["items"][1].update(status="addon")
    m["maps"][0]["bands"] = [dict(id="b1", title="Budget year", stages=["s1"])]
    m["gaps"] = [dict(id="G1", title="Faster answers", anchors=["new"], design=["Answers arrive without a file."],
                      detail="Write answers through the session API.",
                      stories=[dict(**{"as": "As an owner I see answers at once"}, done_when=["Answers show within a minute"],
                                    detail=["The session file updates on every change."])])]
    m["notes"] = [dict(id="N1", anchor="b1", role="owner", title="Check the dates", question="When does the budget close?")]
    assert [e for e in dc.validate(m) if e["level"] == "error"] == []
    text = dc.words(m)
    for expected in ("Before: Done on paper.", "Across the chain: Budget year", "Not sure: Nobody has asked the owner yet.",
                     "Behind the scenes: The owner decides", "Design principles:", "Technical design: Write answers",
                     "Technical check: The session file updates"):
        assert expected in text, expected
    assert "dc-model" in dc.render(m)
    m["maps"][0]["bands"][0]["stages"] = ["nowhere"]
    assert any(e["path"].endswith("bands[0].stages") for e in dc.validate(m))
