"""The public library. Every capability lives here; the CLI only reads files and prints.

Deterministic: manifest, templates, roles, new, starter, example, example_names, doctor,
summary, validate, render, words, questions, merge, diff, session, discover, handoff.
Model-backed: draft, perspectives.

To chain capabilities, call these functions from Python rather than piping CLI output:
results are ordinary return values (dicts, lists and strings).
"""

from __future__ import annotations

from . import intelligence
from .model import default_roles, new_model, templates, validate
from .render import render
from .review import diff, merge, questions
from .words import words
from .session import session
from .workflow import discover, handoff
from .doctor import doctor
from .examples import example, example_names
from .starter import starter
from .stats import summary

__all__ = [
    "manifest", "templates", "roles", "new", "validate", "render", "words", "questions",
    "merge", "diff", "draft", "perspectives", "session", "discover", "handoff",
    "starter", "example", "example_names", "doctor", "summary",
]


def manifest() -> dict:
    """The tool's manifest fields and which capabilities are model-backed."""
    from .help import manifest as _m
    return _m()


def roles() -> list[dict]:
    """The default roles: id, label, colour and the question each role always asks."""
    return default_roles()


def new(template: str, title: str, question: str, date: str = "") -> dict:
    """An empty model for a template, to fill in by hand or with `draft`."""
    return new_model(template, title, question, date=date)


draft = intelligence.draft
perspectives = intelligence.perspectives

# re-exported deterministic capabilities
templates = templates
validate = validate
render = render
words = words
questions = questions
merge = merge
diff = diff
