"""Map choice and explicit relationships preserve their meaning through the library."""
import copy
import json

import decisioncraft as dc
from decisioncraft.cli import build


def model_with_links():
    model = dc.new("opportunity-tree", "Choose a trial", "What should we try?")
    model["maps"][0]["root"]["children"] = [
        dict(id="trial", title="Run a small trial", children=[])
    ]
    model["links"] = [dict(id="L1", **{"from": "trial", "to": "root"},
                           label="Changes the choice after the trial", kind="feedback", when="planned")]
    return model


def test_auto_draft_can_choose_multiple_valid_views():
    target = model_with_links()
    timeline = dc.new("customer-journey", "", "Q?")["maps"][0]
    timeline["id"] = "timeline"
    target["maps"].append(timeline)
    calls = []

    def complete(system, prompt):
        calls.append(prompt)
        return json.dumps(target)

    result = dc.draft([dict(name="notes", text="A trial with a customer.")],
                      question=target["question"], complete=complete)
    assert len(result["maps"]) == 2
    assert len(calls) == 1
    assert "Choose the map or maps" in calls[0]
    assert "customer-journey" in calls[0] and "feedback" in calls[0]
    assert build().parse_args(["draft", "notes.md", "--question", "Q?"]).template == "auto"


def test_links_survive_text_export_and_change_tracking():
    model = model_with_links()
    assert not [p for p in dc.validate(model) if p["level"] == "error"]
    text = dc.words(model)
    assert "Run a small trial → What should we try?" in text
    assert "Changes the choice after the trial (feedback; proposed)" in text
    changed = copy.deepcopy(model)
    changed["links"][0]["label"] = "Review the outcome"
    assert dc.diff(model, changed)["changed"] == [dict(id="L1", kind="links", fields=["label"])]


def test_invalid_relationships_are_rejected():
    model = model_with_links()
    for field, value in [("from", "missing"), ("to", []), ("label", ""),
                         ("kind", "guess"), ("when", "maybe")]:
        broken = copy.deepcopy(model)
        broken["links"][0][field] = value
        assert any(p["path"] == f"links[0].{field}" and p["level"] == "error"
                   for p in dc.validate(broken))
    model["links"][0]["to"] = "trial"
    assert any(p["path"] == "links[0]" and p["level"] == "error" for p in dc.validate(model))
