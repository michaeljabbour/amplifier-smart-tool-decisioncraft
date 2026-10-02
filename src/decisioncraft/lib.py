"""The public library. Every capability lives here; the CLI only reads files and prints.

Deterministic: manifest, templates, roles, new, starter, example, example_names, doctor,
summary, validate, render, words, questions, merge, diff, session, discover, handoff,
modes, triage, quick (with scores), interview_step, interview_questions.
Model-backed: map (point it at a repo, notes, a page or a topic), draft, perspectives, review_notes; quick and triage read free text with a
model only when one is passed.

To chain capabilities, call these functions from Python rather than piping CLI output:
results are ordinary return values (dicts, lists and strings).
"""

from __future__ import annotations

from . import intelligence
from .model import default_roles, new_model, templates, validate
from .render import render
from .review import diff, merge, notes_to_ask, questions
from .words import words
from .session import session
from .workflow import discover, handoff
from .doctor import doctor
from .examples import example, example_names
from .starter import starter
from .stats import summary
from .modes import MODES, quick, triage
from . import interview as _interview
from .mapper import gather, map_target, plan_map

__all__ = [
    "manifest", "templates", "roles", "new", "validate", "render", "words", "questions",
    "merge", "diff", "draft", "perspectives", "review_notes", "notes_to_ask", "session", "discover", "handoff",
    "starter", "example", "example_names", "doctor", "summary",
    "modes", "triage", "quick", "interview_step", "interview_questions",
    "map_target", "plan_map", "gather",
]


def modes() -> dict:
    """The ways Decisioncraft can help: none (just answer), quick, guided and team."""
    return MODES


def interview_step(directory, answer=None, *, question: str = "", kind=None, reset: bool = False) -> dict:
    """One interview step in a folder: record `answer`, return the next question or finish.

    Finishing writes model.json and material/README.txt into the folder.
    """
    if reset:
        return _interview.start(directory, question=question, kind=kind)
    return _interview.step(directory, answer, question=question, kind=kind)


def interview_questions() -> dict:
    """The interview's question bank, by set (personal, team, system)."""
    return _interview.question_bank()


def manifest() -> dict:
    """The tool's manifest fields and which capabilities are model-backed."""
    from .help import manifest as _m
    return _m()


def guide() -> dict:
    """The model format (every field, with its rules) and the writing guide, as Markdown."""
    from importlib import resources
    from pathlib import Path

    from .intelligence import _guide

    fmt = ""
    packaged = resources.files("decisioncraft").joinpath("resources/model-format.md")
    if packaged.is_file():
        fmt = packaged.read_text(encoding="utf-8")
    else:  # a checkout: read the contract from the repository
        repo = Path(__file__).resolve().parents[2] / "contracts" / "model.v1.md"
        if repo.is_file():
            fmt = repo.read_text(encoding="utf-8")
    return {"model_format": fmt, "writing_guide": _guide()}


def roles() -> list[dict]:
    """The default roles: id, label, colour and the question each role always asks."""
    return default_roles()


def new(template: str, title: str, question: str, date: str = "") -> dict:
    """An empty model for a template, to fill in by hand or with `draft`."""
    return new_model(template, title, question, date=date)


draft = intelligence.draft
perspectives = intelligence.perspectives
review_notes = intelligence.review_notes

# re-exported deterministic capabilities
templates = templates
validate = validate
render = render
words = words
questions = questions
merge = merge
diff = diff
