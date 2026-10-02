import copy
import json
from pathlib import Path

import pytest

import decisioncraft as dc
from decisioncraft.review import blank_review, fingerprint

EX = Path(__file__).resolve().parent.parent / "examples"


def load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


@pytest.fixture
def model():
    return load(EX / "business" / "model.json")


def test_questions_are_ordered_by_urgency(model):
    qs = dc.questions(model)
    order = {"must": 0, "should": 1, "info": 2}
    assert [order[q["urgency"]] for q in qs] == sorted(order[q["urgency"]] for q in qs)
    assert len(qs) == sum(1 for n in model["notes"] if n.get("question"))


def test_dots_lift_a_question_within_its_urgency(model):
    must = [q for q in dc.questions(model) if q["urgency"] == "must"]
    last = must[-1]["id"]
    review = blank_review(model, "A")
    review["dots"] = {last: 3}
    merged = dc.merge([review], model)
    assert dc.questions(model, merged)[0]["id"] == last


def test_merge_counts_answers_dots_and_splits(model):
    reviews = [load(p) for p in sorted((EX / "business" / "reviews").glob("*.json"))]
    m = dc.merge(reviews, model)
    assert m["reviewers"] == ["Mill Lane manager", "Owner"]
    n1 = m["questions"]["N1"]
    assert (n1["agree"], n1["change"]) == (1, 1)
    assert n1["split"] is True
    assert n1["dots"] == 3
    assert {c["who"] for c in n1["comments"]} == {"Owner", "Mill Lane manager"}
    assert m["questions"]["N3"]["split"] is False
    assert m["decisions"]["D1"]["conflict"] == ["owner"]


def test_merge_flags_reviews_of_another_version(model):
    r = blank_review(model, "A")
    r["model_fingerprint"] = "000000000000"
    assert dc.merge([r], model)["stale_reviews"] == ["A"]
    r["model_fingerprint"] = fingerprint(model)
    assert dc.merge([r], model)["stale_reviews"] == []


def test_merge_refuses_files_that_are_not_reviews(model):
    with pytest.raises(ValueError):
        dc.merge([{"format": "something-else"}], model)
    bad = blank_review(model)
    bad["answers"] = {"N1": {"choice": "maybe"}}
    with pytest.raises(ValueError):
        dc.merge([bad], model)


def test_merge_refuses_a_model_file_passed_in_as_a_review(model):
    """A model has its own top-level `dots` field; merge must report the wrong format
    instead of crashing when it tries to read that field as a review's."""
    with pytest.raises(ValueError, match="Not a review file"):
        dc.merge([model], model)


def test_diff_finds_added_changed_and_removed():
    old = load(EX / "technical" / "model-before.json")
    new = load(EX / "technical" / "model.json")
    d = dc.diff(old, new)
    assert {"t3", "N1"} <= {c["id"] for c in d["changed"]}
    assert "j-direct" in {a["id"] for a in d["added"]}
    assert d["removed"] == []
    back = dc.diff(new, old)
    assert "j-direct" in {r["id"] for r in back["removed"]}


def test_diff_of_identical_models_is_empty(model):
    d = dc.diff(model, copy.deepcopy(model))
    assert d["added"] == d["removed"] == d["changed"] == []
