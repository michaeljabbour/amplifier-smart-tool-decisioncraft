"""Discovery, reasoned comparisons and completion handoffs stay provider-free."""

import copy
import json

import pytest
import decisioncraft as dc
from decisioncraft.review import blank_review


def proposed_model():
    model = dc.new(
        "decision-chain", "Choose a review", "How should we review a choice?"
    )
    model["maps"][0]["stages"] = [
        dict(
            id="review-stage",
            label="Review",
            items=[
                dict(id="current", title="Download answers", when="today"),
                dict(
                    id="proposed", title="Return answers to the agent", when="planned"
                ),
            ],
        )
    ]
    model["notes"] = [
        dict(
            id="Q1",
            anchor="review-stage",
            role="owner",
            title="Choose",
            question="What matters most?",
        )
    ]
    model["gaps"] = [
        dict(
            id="G1",
            title="Return to the agent",
            anchors=["proposed"],
            stories=[
                {
                    "as": "As a reviewer, I want my answers to reach the agent so I can continue the decision.",
                    "done_when": [
                        "Finishing returns the recorded answers and next steps."
                    ],
                }
            ],
        )
    ]
    model["comparison"] = dict(
        why="Avoid losing the person's answers.",
        criteria=[dict(id="C1", label="Easy to continue", importance="must")],
        options=[
            dict(id="O1", title="File handoff", evaluations=[]),
            dict(
                id="O2",
                title="Direct handoff",
                evaluations=[
                    dict(
                        criterion="C1",
                        judgment="unknown",
                        reason="A real review is still needed.",
                    )
                ],
            ),
        ],
        method="Observe one review.",
        review_when="After the first trial.",
    )
    return model


def test_discovery_is_short_and_has_useful_followups():
    result = dc.discover("How should we review?")
    assert len(result["questions"]) == 4
    assert {q["id"] for q in result["follow_up_questions"]} == {
        "criteria",
        "method",
        "stakes",
    }
    assert result["response_format"]["format"] == "decisioncraft-brief/1"


def test_completion_preserves_answers_requirements_and_uncertainty():
    model = proposed_model()
    review = blank_review(model)
    review["answers"] = {
        "Q1": {"choice": "unsure", "answer": "I need to see a real trial."}
    }
    result = dc.handoff(model, review)
    assert result["review"] == review
    assert result["unresolved_questions"][0]["reason"] == "Not sure yet"
    assert (
        result["user_stories"][0]["acceptance_criteria"]
        == model["gaps"][0]["stories"][0]["done_when"]
    )
    proposal = result["proposed_model"]
    assert [item["id"] for item in proposal["maps"][0]["stages"][0]["items"]] == [
        "proposed"
    ]
    assert not [p for p in dc.validate(proposal) if p["level"] == "error"]
    assert len(result["comparison"]["missing"]) == 2
    assert model["maps"][0]["stages"][0]["items"][0]["id"] == "current"
    assert "not approval" in result["agent_request"]


def test_current_map_and_blank_answers_do_not_become_a_proposal():
    model = dc.new("customer-journey", "A journey", "What should we change?")
    result = dc.handoff(model, blank_review(model))
    assert result["proposed_model"] is None and result["user_stories"] == []
    assert any("No proposed-state map" in item for item in result["missing"])


def test_invalid_comparisons_and_wrong_reviews_are_rejected():
    model = proposed_model()
    for field, value in [
        ("criterion", "missing"),
        ("evidence", ["missing"]),
        ("judgment", "winner"),
    ]:
        broken = copy.deepcopy(model)
        broken["comparison"]["options"][1]["evaluations"][0][field] = value
        assert any(
            p["level"] == "error" and p["path"].endswith(field)
            for p in dc.validate(broken)
        )
    review = blank_review(model)
    review["model_fingerprint"] = "wrong"
    with pytest.raises(ValueError, match="belong"):
        dc.handoff(model, review)


def test_discovery_answers_shape_the_host_draft():
    model = proposed_model()
    brief = {
        "format": "decisioncraft-brief/1",
        "answers": {
            "decision": "Keep a direct handoff",
            "criteria": "No lost answers",
            "visual": "Show how the work changes",
        },
    }
    prompts = []

    def complete(system, prompt):
        prompts.append(prompt)
        return json.dumps(model)

    result = dc.draft([], question=model["question"], brief=brief, complete=complete)
    assert result["brief"] == brief
    assert "No lost answers" in prompts[0] and "Establish criteria" in prompts[0]
