"""Model-backed capabilities: draft a model from material, and add role notes.

Nothing here runs on import. Provider SDKs load only when a model-backed capability is
called with an explicit provider, or the caller passes its own `complete` function
(for example, a host agent). Every reply is checked by `validate` before it is returned.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from importlib.resources import files

from .model import FORMAT, TEMPLATES, ModelError, default_roles, new_model, validate

Complete = Callable[[str, str], str]   # (system, prompt) -> text

PROVIDERS = {
    "anthropic": ("ANTHROPIC_API_KEY", "claude-sonnet-5-5"),
    "openai": ("OPENAI_API_KEY", None),   # no default: name the model you have access to
}


class ProviderError(RuntimeError):
    """No usable model provider. The message says what to set or install."""


def provider_complete(provider: str, model: str | None = None, max_tokens: int = 16000) -> Complete:
    """A `complete` function for a named provider, using its official SDK."""
    if provider not in PROVIDERS:
        raise ProviderError(f"Unknown provider {provider!r}. Choose one of: {', '.join(PROVIDERS)}.")
    env, default_model = PROVIDERS[provider]
    if not os.environ.get(env):
        raise ProviderError(f"Set {env} to use the {provider} provider.")
    model = model or default_model
    if not model:
        raise ProviderError(f"Name a model for the {provider} provider (--model).")
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError as e:
            raise ProviderError("Install the smart extra: pip install "
                                "'amplifier-smart-tool-decisioncraft[smart]'.") from e
        client = anthropic.Anthropic()

        def complete(system: str, prompt: str) -> str:
            msg = client.messages.create(model=model, max_tokens=max_tokens, system=system,
                                         messages=[{"role": "user", "content": prompt}])
            return "".join(getattr(b, "text", "") for b in msg.content)
        return complete
    try:
        import openai
    except ImportError as e:
        raise ProviderError("Install the smart extra: pip install "
                            "'amplifier-smart-tool-decisioncraft[smart]'.") from e
    client = openai.OpenAI()

    def complete(system: str, prompt: str) -> str:
        r = client.responses.create(model=model, instructions=system, input=prompt,
                                    max_output_tokens=max_tokens)
        return r.output_text
    return complete


def _guide() -> str:
    return files("decisioncraft").joinpath("resources/writing-guide.md").read_text(encoding="utf-8")


def _json_from(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise ModelError([{"level": "error", "path": "", "message": "The model reply held no JSON."}])
    return json.loads(m.group(0))


def _material_block(material: list[dict], limit: int) -> str:
    out, used = [], 0
    for i, item in enumerate(material):
        name = item.get("name") or f"material-{i + 1}"
        text = str(item.get("text", ""))
        room = max(0, limit - used)
        if not room:
            out.append(f"[{name}: left out, over the size limit]")
            continue
        piece = text[:room]
        used += len(piece)
        out.append(f"<material name=\"{name}\">\n{piece}\n</material>")
    return "\n\n".join(out)


def _ask(complete: Complete, system: str, prompt: str, check) -> dict:
    """Ask once; if the reply fails validation, ask once more with the problems listed."""
    reply = complete(system, prompt)
    try:
        value = _json_from(reply)
        problems = check(value)
    except (json.JSONDecodeError, ModelError) as e:
        value, problems = None, [str(e)]
    if not problems:
        return value
    retry = (prompt + "\n\nYour last reply had these problems. Fix them and reply with the "
             "whole JSON again:\n- " + "\n- ".join(problems[:30]))
    value = _json_from(complete(system, retry))
    problems = check(value)
    if problems:
        raise ModelError([{"level": "error", "path": "", "message": p} for p in problems[:20]])
    return value


def draft(material: list[dict], *, template: str, question: str, title: str = "",
          roles: list[dict] | None = None, date: str = "", provider: str | None = None,
          model: str | None = None, complete: Complete | None = None,
          max_material_chars: int = 120_000) -> dict:
    """Model-backed. Read the material and draft a full decision model.

    material: [{name, text}] — the actual content (notes, transcripts, documents, data).
    template: one of the template ids; question: the decision being made.
    Returns a validated model with sources, quoted evidence, maps, gaps, notes from each
    role, decisions and outcome measures. Every claim should cite the material.
    """
    if template not in TEMPLATES:
        raise ModelError([{"level": "error", "path": "template",
                           "message": f"Unknown template {template!r}."}])
    complete = complete or provider_complete(provider or "", model)
    skeleton = new_model(template, title or question, question, date=date)
    skeleton["roles"] = roles or default_roles()
    system = ("You build decision models as JSON. " + _guide())
    prompt = (
        f"Build a complete model in format {FORMAT!r} for this decision:\n{question}\n\n"
        f"Start from this skeleton and fill every part. Keep its lanes or stages unless the "
        f"material clearly needs different ones.\n{json.dumps(skeleton, indent=1)}\n\n"
        "Rules: every source in the material becomes a source; quote exact words or numbers "
        "as evidence and cite evidence ids from boxes and notes; add 2 to 5 notes per role, "
        "each ending in a question, with urgency must/should/info; turn differences between "
        "today and planned into gaps with impact and effort 1-5, user stories and 'done when' "
        "checks; add open decisions that collect related notes; add outcome measures. "
        "Say 'not sure' rather than invent facts. Reply with the JSON only.\n\n"
        + _material_block(material, max_material_chars))

    def check(v):
        return [p["message"] for p in validate(v) if p["level"] == "error"]

    return _ask(complete, system, prompt, check)


def perspectives(model: dict, *, material: list[dict] | None = None,
                 roles: list[dict] | None = None, per_role: int = 3,
                 provider: str | None = None, model_name: str | None = None,
                 complete: Complete | None = None, max_material_chars: int = 60_000) -> dict:
    """Model-backed. Add notes from each role to an existing model; returns the new model.

    Existing notes are kept. New notes get fresh ids, point at existing boxes or gaps,
    cite existing evidence where they can, and end in a question.
    """
    complete = complete or provider_complete(provider or "", model_name)
    roles = roles or model.get("roles") or default_roles()
    system = "You review decision models from several points of view. " + _guide()
    prompt = (
        f"Here is a decision model:\n{json.dumps(model, indent=1)}\n\n"
        f"Write up to {per_role} new notes for each of these roles:\n{json.dumps(roles, indent=1)}\n"
        "Each note: {id, role, anchor (an existing box or gap id), title, body, recommend, "
        "question, urgency (must|should|info), evidence (existing evidence ids)}. Use ids that "
        "start with 'P'. Do not repeat points the model already makes. Reply with "
        "{\"notes\": [...]} only.\n\n" + (_material_block(material or [], max_material_chars)))
    merged_roles = {r["id"]: r for r in (model.get("roles") or default_roles())}
    for r in roles:
        merged_roles.setdefault(r["id"], r)

    def combine(v):
        out = dict(model)
        out["roles"] = list(merged_roles.values())
        out["notes"] = list(model.get("notes", [])) + list(v.get("notes", []))
        return out

    def check(v):
        if not isinstance(v, dict) or not isinstance(v.get("notes"), list):
            return ["Reply must be {\"notes\": [...]}."]
        return [p["message"] for p in validate(combine(v)) if p["level"] == "error"]

    return combine(_ask(complete, system, prompt, check))
