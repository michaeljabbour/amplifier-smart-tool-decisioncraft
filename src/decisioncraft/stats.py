"""Counts that describe a model in one line, for progress messages and results."""

from __future__ import annotations


def _n(value) -> int:
    return len(value) if isinstance(value, list) else 0


def summary(model: dict) -> dict:
    """How big a model is: maps, journeys, steps, stages, notes, questions, gaps and more."""
    maps = model.get("maps") if isinstance(model.get("maps"), list) else []
    journeys = steps = stages = items = 0
    for m in maps:
        if not isinstance(m, dict):
            continue
        for j in m.get("journeys") or []:
            if isinstance(j, dict):
                journeys += 1
                steps += _n(j.get("steps"))
        for st in m.get("stages") or []:
            if isinstance(st, dict):
                stages += 1
                items += _n(st.get("items"))
    notes = [n for n in model.get("notes") or [] if isinstance(n, dict)]
    return {
        "maps": len(maps),
        "journeys": journeys,
        "steps": steps,
        "stages": stages,
        "items": items,
        "notes": len(notes),
        "questions": sum(1 for n in notes if n.get("question")),
        "gaps": _n(model.get("gaps")),
        "sources": _n(model.get("sources")),
        "evidence": _n(model.get("evidence")),
        "decisions": _n(model.get("decisions")),
        "outcomes": _n(model.get("outcomes")),
    }


def describe(model: dict) -> str:
    """The counts that matter, plainly: for example "2 maps, 6 journeys, 31 notes"."""
    s = summary(model)
    parts = []
    for key, one, many in (
        ("maps", "map", "maps"),
        ("journeys", "journey", "journeys"),
        ("notes", "note", "notes"),
        ("questions", "question to decide", "questions to decide"),
        ("gaps", "gap", "gaps"),
    ):
        if s[key]:
            parts.append(f"{s[key]} {one if s[key] == 1 else many}")
    return ", ".join(parts) or "empty so far"
