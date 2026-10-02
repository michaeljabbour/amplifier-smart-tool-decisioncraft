"""Model-backed capabilities: draft a model from material, and add role notes.

Nothing here runs on import. Provider SDKs load only when a model-backed capability is
called with an explicit provider, or the caller passes its own `complete` function
(for example, a host agent). Every reply is checked by `validate` before it is returned.
"""

from __future__ import annotations

import json
import os
import subprocess
from collections.abc import Callable
from importlib.resources import files

from .model import FORMAT, TEMPLATES, ModelError, default_roles, new_model, validate

Complete = Callable[[str, str], str]  # (system, prompt) -> text

# Neither provider has a built-in default model: name the one you have access to with
# --model. A hard-coded default goes stale the moment a vendor retires it.
PROVIDERS = {
    "anthropic": ("ANTHROPIC_API_KEY", None),
    "openai": ("OPENAI_API_KEY", None),
}


class ProviderError(RuntimeError):
    """No usable model provider. The message says what to set or install."""


def provider_complete(
    provider: str, model: str | None = None, max_tokens: int = 16000
) -> Complete:
    """A `complete` function for a named provider, using its official SDK."""
    if provider not in PROVIDERS:
        raise ProviderError(
            f"Unknown provider {provider!r}. Choose one of: {', '.join(PROVIDERS)}."
        )
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
            raise ProviderError(
                "Install the smart extra: pip install "
                "'amplifier-smart-tool-decisioncraft[smart]'."
            ) from e
        client = anthropic.Anthropic()

        def complete(system: str, prompt: str) -> str:
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(getattr(b, "text", "") for b in msg.content)

        return complete
    try:
        import openai
    except ImportError as e:
        raise ProviderError(
            "Install the smart extra: pip install "
            "'amplifier-smart-tool-decisioncraft[smart]'."
        ) from e
    client = openai.OpenAI()

    def complete(system: str, prompt: str) -> str:
        r = client.responses.create(
            model=model, instructions=system, input=prompt, max_output_tokens=max_tokens
        )
        return r.output_text

    return complete


def command_complete(cmd: str) -> Complete:
    """A `complete` function that runs an external command instead of a vendor SDK.

    The command receives `{"system", "prompt"}` as JSON on stdin and must print the
    completion text to stdout. Use this to route `draft` and `perspectives` through a
    host's own model setup -- for example Amplifier's configured provider -- instead
    of installing the anthropic or openai SDK directly.
    """

    def complete(system: str, prompt: str) -> str:
        result = subprocess.run(
            cmd,
            shell=True,
            input=json.dumps({"system": system, "prompt": prompt}),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        if result.returncode != 0:
            raise ProviderError(
                f"--complete-cmd failed (exit {result.returncode}): "
                f"{result.stderr.strip() or 'no output'}"
            )
        return result.stdout

    return complete


def _guide() -> str:
    return (
        files("decisioncraft")
        .joinpath("resources/writing-guide.md")
        .read_text(encoding="utf-8")
    )


def _json_from(text: str) -> dict:
    """The first balanced `{...}` object in `text`.

    A greedy match to the last `}` in the reply breaks on trailing prose or examples;
    this instead finds the first object whose braces actually balance.
    """
    start = text.find("{")
    while start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break
        start = text.find("{", start + 1)
    raise ModelError(
        [{"level": "error", "path": "", "message": "The model reply held no JSON."}]
    )


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
        out.append(f'<material name="{name}">\n{piece}\n</material>')
    return "\n\n".join(out)


def _parse(reply: str, check) -> tuple[dict | None, list[str]]:
    """Parse a reply as JSON and run `check` on it. Never raises: problems come back
    as messages, so a malformed reply becomes a repair prompt instead of a crash."""
    try:
        value = _json_from(reply)
    except (json.JSONDecodeError, ModelError) as e:
        return None, [str(e)]
    try:
        problems = check(value)
    except (AttributeError, TypeError, KeyError) as e:
        return None, [f"Reply did not match the expected shape: {e}"]
    return value, problems


def _ask(complete: Complete, system: str, prompt: str, check) -> dict:
    """Ask once; if the reply fails validation, ask once more with the problems listed."""
    value, problems = _parse(complete(system, prompt), check)
    if not problems:
        assert value is not None
        return value
    retry = (
        prompt + "\n\nYour last reply had these problems. Fix them and reply with the "
        "whole JSON again:\n- " + "\n- ".join(problems[:30])
    )
    value, problems = _parse(complete(system, retry), check)
    if problems:
        raise ModelError(
            [{"level": "error", "path": "", "message": p} for p in problems[:20]]
        )
    assert value is not None
    return value


def draft(
    material: list[dict],
    *,
    template: str,
    question: str,
    title: str = "",
    roles: list[dict] | None = None,
    date: str = "",
    provider: str | None = None,
    model: str | None = None,
    complete: Complete | None = None,
    max_material_chars: int = 120_000,
) -> dict:
    """Model-backed. Read the material and draft a full decision model.

    material: [{name, text}] — the actual content (notes, transcripts, documents, data).
    template: one of the template ids; question: the decision being made.
    Returns a validated model with sources, quoted evidence, maps, gaps, notes from each
    role, decisions and outcome measures. Every claim should cite the material.
    """
    if template not in TEMPLATES:
        raise ModelError(
            [
                {
                    "level": "error",
                    "path": "template",
                    "message": f"Unknown template {template!r}.",
                }
            ]
        )
    complete = complete or provider_complete(provider or "", model)
    skeleton = new_model(template, title or question, question, date=date)
    skeleton["roles"] = roles or default_roles()
    system = "You build decision models as JSON. " + _guide()
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
        + _material_block(material, max_material_chars)
    )

    def check(v):
        return [p["message"] for p in validate(v) if p["level"] == "error"]

    return _ask(complete, system, prompt, check)


def perspectives(
    model: dict,
    *,
    material: list[dict] | None = None,
    roles: list[dict] | None = None,
    per_role: int = 3,
    provider: str | None = None,
    model_name: str | None = None,
    complete: Complete | None = None,
    max_material_chars: int = 60_000,
) -> dict:
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
        '{"notes": [...]} only.\n\n'
        + (_material_block(material or [], max_material_chars))
    )
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
            return ['Reply must be {"notes": [...]}.']
        return [p["message"] for p in validate(combine(v)) if p["level"] == "error"]

    return combine(_ask(complete, system, prompt, check))
