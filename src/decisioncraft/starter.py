"""A starter folder for a new decision: the model and a README saying what material to add."""

from __future__ import annotations

import json
import re

from .model import default_roles, new_model


def slug(text: str, fallback: str = "decision") -> str:
    """A short folder name from a title or question."""
    words = re.findall(r"[a-z0-9]+", text.lower())[:6]
    return "-".join(words) or fallback


def title_from(question: str) -> str:
    """A short title from the decision question when none is given."""
    text = question.strip().rstrip("?").strip()
    for lead in ("should we ", "should i ", "how do we ", "how can we ", "how should we ", "what ", "which "):
        if text.lower().startswith(lead):
            text = text[len(lead):]
            break
    text = text[:60].rsplit(" ", 1)[0] if len(text) > 60 else text
    return text[:1].upper() + text[1:] if text else "New decision"


def pick_roles(ids: list[str] | None) -> list[dict]:
    """The default roles, kept to `ids` when given. Raises ValueError naming the valid ids."""
    roles = default_roles()
    if not ids:
        return roles
    known = {r["id"]: r for r in roles}
    unknown = [i for i in ids if i not in known]
    if unknown:
        raise ValueError(
            f"Unknown role{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}. "
            f"Choose from {', '.join(known)}."
        )
    return [known[i] for i in ids]


def material_readme(model: dict, material_hint: str = "") -> str:
    roles = ", ".join(r["label"] for r in model.get("roles") or [])
    where = f"\nYou said your material is in: {material_hint}\nCopy or link the files here.\n" if material_hint else ""
    return f"""# Material for: {model.get('title') or model.get('question')}

The decision: {model.get('question')}

Put the things this decision should rest on in this folder, as Markdown or plain
text files. Every claim on the canvas should point back to something here.
{where}
Good things to add:

- Notes from meetings and calls, and transcripts.
- What people told you: interviews, surveys, support messages, complaints.
- Numbers: costs, counts, times, results of trials. A short table is fine.
- Documents that set limits: rules, contracts, standards, budgets.
- How things work today, step by step, even if rough.

One topic per file works best. Name files plainly, for example
`customer-calls.md` or `costs-2026.md`.

Roles who will leave notes: {roles}.

Next steps:

- Fill in model.json by hand (see `decisioncraft new --help` and `decisioncraft validate`), or
- Draft it from this folder with a model:
  decisioncraft draft material/*.md --question "{model.get('question')}" \\
    --provider anthropic --model <model-name> --out model.json
  (or route through your own model with --complete-cmd instead of --provider)
- Then draw it: decisioncraft render model.json --open
"""


def starter(
    template: str,
    title: str,
    question: str,
    *,
    roles: list[str] | None = None,
    date: str = "",
    material_hint: str = "",
) -> dict:
    """The files for a new decision folder: {relative path: text}.

    Contains `model.json` (an empty model for the template, with the chosen roles) and
    `material/README.txt` (what to put in the folder and what to run next). The README is
    plain text so `draft material/*.md` does not read it as evidence.
    """
    model = new_model(template, title or title_from(question), question, date=date)
    model["roles"] = pick_roles(roles)
    return {
        "model.json": json.dumps(model, indent=2, ensure_ascii=False) + "\n",
        "material/README.txt": material_readme(model, material_hint),
    }
