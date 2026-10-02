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
    template: str = "auto",
    question: str,
    title: str = "",
    roles: list[dict] | None = None,
    date: str = "",
    brief: dict | None = None,
    provider: str | None = None,
    model: str | None = None,
    complete: Complete | None = None,
    max_material_chars: int = 120_000,
) -> dict:
    """Model-backed. Read the material and draft a full decision model.

    material: [{name, text}] — the actual content (notes, transcripts, documents, data).
    template: auto selects maps from the material, or use a template id; question: the decision being made.
    Returns a validated model with sources, quoted evidence, maps, gaps, notes from each
    role, decisions and outcome measures. Every claim should cite the material.
    """
    if template != "auto" and template not in TEMPLATES:
        raise ModelError(
            [
                {
                    "level": "error",
                    "path": "template",
                    "message": f"Unknown template {template!r}.",
                }
            ]
        )
    if brief is not None:
        from .workflow import check_brief
        check_brief(brief)
    complete = complete or provider_complete(provider or "", model)
    skeleton = new_model("opportunity-tree" if template == "auto" else template,
                         title or question, question, date=date)
    skeleton["roles"] = roles or default_roles()
    skeleton["comparison"] = {"why": "", "criteria": [], "options": [], "method": "", "review_when": ""}
    if template == "auto":
        skeleton["maps"] = []
        map_start = (
            "Choose the map or maps that best explain this material. Do not default to a tree. "
            "Use customer-journey for a person's ordered actions, service-blueprint for visible "
            "and behind-the-scenes work, system-journeys for handoffs between people and systems, "
            "decision-chain for current and proposed work through stages, and opportunity-tree "
            "for alternative ways to reach an outcome. Use more than one map only when each answers "
            "a different useful question. Explain the choice in each map's intro. Keep actions "
            "in the supplied order. Choose meaningful lanes, stages and labels from the material. "
            "Here are the supported map shapes; replace the empty maps list with your choices:\n"
            + json.dumps([new_model(t, "", question)["maps"][0] for t in TEMPLATES], indent=1)
        )
    else:
        map_start = "Start from this skeleton. Keep its lanes or stages unless the material needs different ones."
    system = "You build decision models as JSON. " + _guide()
    prompt = (
        f"Build a complete model in format {FORMAT!r} for this decision:\n{question}\n\n"
        f"Discovery answers from the person: {json.dumps(brief) if brief else 'Not supplied. Keep missing context explicit.'}\n\n"
        f"{map_start}\n{json.dumps(skeleton, indent=1)}\n\n"
        "Compare realistic alternatives against what the person says matters. Establish criteria "
        "before assessing options. Include keeping things as they are only when it is realistic. "
        "Choose the amount of checking and the method to match the stakes. Preserve uncertainty; "
        "do not invent scores, agreed criteria or a final choice. comparison uses criteria "
        "[{id,label,importance:must|important|nice}], options [{id,title,summary,evaluations "
        "[{criterion,judgment:fits|mixed|does_not_fit|unknown,reason,evidence:[]}]}], method, why, "
        "review_when, and an optional recommendation {option,reason,risks}. Use supplied evidence "
        "and say which claims still need checking. Mark a map when planned if it explicitly "
        "shows the proposed state. Questions should help the owner resolve the choice. "
        "Rules: every source in the material becomes a source; quote exact words or numbers "
        "as evidence and cite evidence ids from boxes and notes; consider every role, "
        "but add only questions whose answers could change the choice, reveal an important "
        "unknown, or establish who will act. Do not invent concerns to fill a quota. "
        "Use a note's body to explain why the question matters in everyday words. "
        "Each note must end in one question, with urgency must/should/info. Use answer_type text "
        "for open questions and stance only when agree/change/unsure answers the question; "
        "turn differences between "
        "today and planned into gaps with impact and effort 1-5, user stories and 'done when' "
        "checks; add open decisions that collect related notes; add outcome measures. "
        "Use optional links [{id, from, to, label, kind, when}] for explicit relationships "
        "between boxes: kind flow/evidence/feedback, when today/planned/both. Cite their basis "
        "in the linked boxes. Do not turn shared evidence or visual proximity into a dependency. "
        "Say 'not sure' rather than invent facts. Reply with the JSON only.\n\n"
        + _material_block(material, max_material_chars)
    )

    def check(v):
        return [p["message"] for p in validate(v) if p["level"] == "error"]

    result = _ask(complete, system, prompt, check)
    if brief is not None:
        result["brief"] = brief
    for note in result.get("notes", []):
        note.setdefault("author", "AI assistant")
    return result


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
        "Ask only questions that could change the choice or resolve an important unknown. "
        "Do not repeat a standard checklist for every role or fill a quota. "
        "Explain why each question matters in everyday words. "
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

    result = _ask(complete, system, prompt, check)
    for note in result.get("notes", []):
        note.setdefault("author", "AI assistant")
    return combine(result)


def review_notes(
    model: dict,
    review: dict,
    *,
    roles: list[str] | None = None,
    provider: str | None = None,
    model_name: str | None = None,
    complete: Complete | None = None,
) -> dict:
    """Model-backed. Ask the experts about reviewers' rough notes; returns the review with replies.

    Each chosen role answers each note it was asked about with a short view and one question
    that could change the choice. Notes and earlier replies are kept; nothing else changes.
    Which notes and roles are asked is `review.notes_to_ask` (deterministic, used by --dry-run).
    """
    import copy
    from datetime import datetime, timezone

    from .review import check_review, notes_to_ask

    problems = check_review(review)
    if problems:
        raise ValueError(" ".join(problems))
    plan = notes_to_ask(model, review, roles)
    out = copy.deepcopy(review)
    if not plan:
        return out
    complete = complete or provider_complete(provider or "", model_name)
    role_info = {r["id"]: r for r in (model.get("roles") or default_roles())}
    asked = [{"note": p["note"]["id"], "text": p["note"]["text"], "on": p["target"]["title"],
              "context": p["target"]["text"], "roles": p["roles"]} for p in plan]
    system = ("You are a panel of experts, each speaking for one role, replying to a reviewer's "
              "rough notes on a decision. " + _guide())
    prompt = (
        f"The decision: {model.get('question', '')}\n"
        f"Summary: {model.get('summary', '')}\n\n"
        f"The roles:\n{json.dumps([role_info[r] for p in plan for r in p['roles'] if r in role_info], indent=1)}\n\n"
        f"The reviewer notes, what each sits on, and who should reply:\n{json.dumps(asked, indent=1)}\n\n"
        "For every note and every role listed for it, write one reply: a short view in that role's "
        "voice (one or two plain sentences that react to the note) and one question whose answer "
        "could change the choice. Do not repeat the note back. Reply with "
        '{"replies": [{"note": note id, "role": role id, "view": "...", "question": "...", '
        '"urgency": "must|should|info"}]} only.'
    )
    wanted = {(p["note"]["id"], r) for p in plan for r in p["roles"]}

    def check(v):
        if not isinstance(v, dict) or not isinstance(v.get("replies"), list):
            return ['Reply must be {"replies": [...]}.']
        errs = []
        for k, r in enumerate(v["replies"]):
            if not isinstance(r, dict) or (r.get("note"), r.get("role")) not in wanted:
                errs.append(f"Reply {k + 1} is not for a note and role that was asked.")
            elif not str(r.get("view", "")).strip() or not str(r.get("question", "")).strip():
                errs.append(f"Reply {k + 1} needs a view and a question.")
            elif r.get("urgency", "info") not in ("must", "should", "info"):
                errs.append(f"Reply {k + 1}: urgency must be must, should or info.")
        return errs

    result = _ask(complete, system, prompt, check)
    by_id = {n["id"]: n for n in out.get("notes", [])}
    used = {r["id"] for n in out.get("notes", []) for r in n.get("replies", [])}
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for r in result["replies"]:
        n = by_id[r["note"]]
        rid, k = f"{n['id']}-{r['role']}", 2
        while rid in used:
            rid, k = f"{n['id']}-{r['role']}-{k}", k + 1
        used.add(rid)
        n.setdefault("replies", []).append({"id": rid, "role": r["role"], "view": r["view"].strip(),
                                            "question": r["question"].strip(), "urgency": r.get("urgency", "info"),
                                            "author": "AI assistant", "at": stamp})
    return out
