"""Questions to begin a decision, and a clear handoff after a review."""

from __future__ import annotations

import copy

from .model import require_valid, iter_boxes
from .review import check_review, fingerprint
from .comparison import comparison_summary


def discover(question: str = "") -> dict:
    """Give a host four short questions before it builds a decision map."""
    if not isinstance(question, str):
        raise ValueError("The decision must be text.")
    return {
        "format": "decisioncraft-discovery/1",
        "decision": question,
        "instruction": "Ask these in conversation before drawing. Reuse answers the person has already given. Ask a short follow-up when an answer is unclear.",
        "questions": [
            {
                "id": "decision",
                "question": "What choice do you need to make, and which options are you considering?",
            },
            {
                "id": "why",
                "question": "Why does this matter now? What would a good outcome look like?",
            },
            {
                "id": "owner",
                "question": "Who makes the final choice? Whose experience should we understand?",
            },
            {
                "id": "visual",
                "question": "What would a picture help you understand: the person's experience, how the work changes, or how the options compare?",
            },
        ],
        "follow_up_questions": [
            {
                "id": "criteria",
                "question": "What matters most when choosing? Is anything a must-have?",
            },
            {
                "id": "method",
                "question": "What would give you enough confidence to choose: a discussion, research, a small trial, or something else?",
            },
            {
                "id": "stakes",
                "question": "How hard would this choice be to reverse, and when do you need to make it?",
            },
        ],
        "response_format": {
            "format": "decisioncraft-brief/1",
            "answers": {"decision": "", "why": "", "owner": "", "visual": ""},
        },
        "next": "Confirm the choice and the reason in plain words. Use the answers and source material to draft suitable maps. Keep missing information visible.",
    }


def handoff(model: dict, review: dict) -> dict:
    """Return answers, proposed stories and checks, and an explicit proposed-state map.

    This is deterministic. It preserves the supplied requirements, rather than making
    requirements out of an agreement or inventing a task from a written answer.
    """
    require_valid(model)
    problems = check_review(review)
    if problems:
        raise ValueError("; ".join(problems))
    if review.get("model") != model["title"] or review.get(
        "model_fingerprint"
    ) != fingerprint(model):
        raise ValueError("The review must belong to this model.")
    known_notes = {n["id"] for n in model.get("notes", [])}
    known_decisions = {d["id"] for d in model.get("decisions", [])}
    if (
        set(review.get("answers", {})) - known_notes
        or set(review.get("dots", {})) - known_notes
        or set(review.get("decisions", {})) - known_decisions
    ):
        raise ValueError(
            "The review refers to questions or decisions outside this model."
        )
    answers = review.get("answers", {})
    unresolved = []
    for note in model.get("notes", []):
        if not note.get("question"):
            continue
        answer = answers.get(note["id"], {})
        done = (
            bool(answer.get("choice"))
            if note.get("answer_type", "text") == "stance"
            else bool(str(answer.get("answer", "")).strip())
            or answer.get("choice") == "unsure"
        )
        if not done or answer.get("choice") == "unsure":
            unresolved.append(
                {
                    "id": note["id"],
                    "question": note["question"],
                    "reason": "Not sure yet"
                    if answer.get("choice") == "unsure"
                    else "Not answered",
                }
            )
    stories = []
    for gap in model.get("gaps", []):
        for i, story in enumerate(gap.get("stories", []), 1):
            if not isinstance(story, dict):
                continue
            criteria = story.get("done_when", [])
            if isinstance(criteria, str):
                criteria = [criteria]
            stories.append(
                {
                    "id": f"{gap['id']}-{i}",
                    "gap": gap["id"],
                    "story": story.get("as", ""),
                    "acceptance_criteria": list(criteria),
                    "status": "Proposed; owner review required",
                }
            )
    comparison = comparison_summary(model)
    missing = list(comparison["missing"])
    if not stories:
        missing.append(
            "User stories and acceptance criteria have not been written. The agent should draft them from the answers and confirm them with the owner."
        )
    for story in stories:
        if not story["acceptance_criteria"]:
            missing.append(f"{story['id']} needs acceptance criteria.")
    proposed = copy.deepcopy(model)
    maps = []
    for source in model["maps"]:
        m = copy.deepcopy(source)
        if m.get("when") == "today":
            continue
        if m["template"] == "decision-chain":
            has_proposal = any(
                item.get("when") == "planned"
                for stage in m.get("stages", [])
                for item in stage.get("items", [])
            )
            if not has_proposal and m.get("when") != "planned":
                continue
            for stage in m.get("stages", []):
                stage["items"] = [
                    item
                    for item in stage.get("items", [])
                    if item.get("when", "both") != "today"
                ]
        elif m.get("when") != "planned":
            # A current journey or a list of options is not automatically a proposal.
            continue
        m["when"] = "planned"
        m["title"] = "Proposed: " + m.get("title", "Next steps")
        maps.append(m)
    proposed_model = None
    if maps:
        proposed["maps"] = maps
        kept = {b["id"] for _, b in iter_boxes(proposed)}
        proposed["links"] = [
            l
            for l in proposed.get("links", [])
            if l.get("when", "both") != "today"
            and l["from"] in kept
            and l["to"] in kept
        ]
        proposed["gaps"] = [
            g
            for g in proposed.get("gaps", [])
            if all(a in kept for a in g.get("anchors", []))
        ]
        anchors = kept | {g["id"] for g in proposed["gaps"]}
        proposed["notes"] = [
            n for n in proposed.get("notes", []) if n.get("anchor") in anchors
        ]
        note_ids = {n["id"] for n in proposed["notes"]}
        for decision in proposed.get("decisions", []):
            decision["notes"] = [n for n in decision.get("notes", []) if n in note_ids]
        proposed["title"] = "Proposed view: " + model["title"]
        proposed["reading"] = (
            "This shows the proposed work and retained context. It does not mean the owner has approved it."
        )
        require_valid(proposed)
        proposed_model = proposed
    else:
        missing.append(
            "No proposed-state map is marked in this model. The agent should draft one; the current map must not be relabelled as a proposal."
        )
    return {
        "format": "decisioncraft-handoff/1",
        "decision": model["question"],
        "model_fingerprint": fingerprint(model),
        "review": copy.deepcopy(review),
        "unresolved_questions": unresolved,
        "user_stories": stories,
        "proposed_model": proposed_model,
        "comparison": comparison,
        "missing": missing,
        "agent_request": "Read the person's answers. Explain how they affect the choice. Agree what matters, compare realistic options using a suitable method, examine uncertainty and risks, and record the owner’s choice and reason. Keep the effort proportionate to the stakes. Show the proposed user stories, acceptance criteria and proposed-state map. Draft missing parts from the source material and answers, mark assumptions, and ask the owner to resolve open points. Finishing a review is not approval of the proposal.",
    }


def handoff_words(result: dict) -> str:
    """A short, readable list of stories and checks from a handoff."""
    out = [
        "# Review handoff",
        "",
        f"**The decision:** {result['decision']}",
        "",
        "These are proposals for the decision owner to review.",
    ]
    for story in result["user_stories"]:
        out.extend(
            ["", f"## {story['id']}: {story['story']}", "", "Acceptance criteria:"]
        )
        out.extend(f"- {criterion}" for criterion in story["acceptance_criteria"])
        if not story["acceptance_criteria"]:
            out.append("- Not defined yet.")
    if result["unresolved_questions"]:
        out.extend(["", "## Questions still open", ""])
        out.extend(
            f"- {q['question']} — {q['reason']}" for q in result["unresolved_questions"]
        )
    if result["missing"]:
        out.extend(["", "## What the agent should prepare", ""])
        out.extend(f"- {item}" for item in result["missing"])
    return "\n".join(out) + "\n"


def check_brief(brief: dict) -> None:
    """Check discovery answers without judging the person's choice."""
    if not isinstance(brief, dict) or brief.get("format") != "decisioncraft-brief/1":
        raise ValueError("Expected decisioncraft-brief/1 discovery answers.")
    answers = brief.get("answers")
    if not isinstance(answers, dict) or any(
        not isinstance(value, str) for value in answers.values()
    ):
        raise ValueError("Discovery answers must be text, keyed by question id.")
    if set(answers) - {
        "decision",
        "why",
        "owner",
        "visual",
        "criteria",
        "method",
        "stakes",
    }:
        raise ValueError("Unknown discovery question id.")
