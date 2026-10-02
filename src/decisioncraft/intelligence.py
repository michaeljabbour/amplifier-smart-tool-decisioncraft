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

# Everyday models, and the one a failed draft escalates to once. Override with --model,
# DECISIONCRAFT_MODEL or `decisioncraft config set model NAME`.
DEFAULT_MODELS = {"anthropic": "claude-sonnet-5-5", "openai": "gpt-5.5"}
ESCALATE_MODELS = {"anthropic": "claude-opus-5-5", "openai": "gpt-5.5-pro"}
PROVIDERS = {
    "anthropic": ("ANTHROPIC_API_KEY", DEFAULT_MODELS["anthropic"]),
    "openai": ("OPENAI_API_KEY", DEFAULT_MODELS["openai"]),
}
# Room for a whole model in one reply. Long replies stream, so there is no HTTP timeout.
MAX_TOKENS = 64_000


class ProviderError(RuntimeError):
    """No usable model provider. The message says what to set or install."""


class TruncatedReply(RuntimeError):
    """The model stopped before its reply was finished (it hit the length limit)."""


# --- which model answers -------------------------------------------------------------

def config_path() -> "os.PathLike[str]":
    """The small user config file: $DECISIONCRAFT_CONFIG, else <config dir>/decisioncraft/config.json."""
    from pathlib import Path

    if os.environ.get("DECISIONCRAFT_CONFIG"):
        return Path(os.environ["DECISIONCRAFT_CONFIG"]).expanduser()
    base = os.environ.get("XDG_CONFIG_HOME") or (
        os.path.join(os.environ.get("APPDATA", ""), "") if os.name == "nt" and os.environ.get("APPDATA")
        else os.path.join(os.path.expanduser("~"), ".config"))
    return Path(base) / "decisioncraft" / "config.json"


CONFIG_KEYS = ("provider", "model")


def load_config() -> dict:
    p = config_path()
    try:
        data = json.loads(open(p, encoding="utf-8").read())
    except (OSError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if k in CONFIG_KEYS and isinstance(v, str) and v.strip()} \
        if isinstance(data, dict) else {}


def save_config(values: dict) -> str:
    """Write config keys (None or "" removes a key). Returns the file path."""
    p = config_path()
    data = load_config()
    for k, v in values.items():
        if k not in CONFIG_KEYS:
            raise ValueError(f"Unknown setting {k!r}. Settings: {', '.join(CONFIG_KEYS)}.")
        if k == "provider" and v and v not in PROVIDERS:
            raise ValueError(f"Unknown provider {v!r}. Choose {' or '.join(PROVIDERS)}.")
        if v:
            data[k] = v
        else:
            data.pop(k, None)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, indent=2) + "\n")
    return str(p)


def resolve(provider: str | None = None, model: str | None = None) -> dict:
    """Which provider and model will answer, and why. Precedence, first that is set wins:
    --provider/--model, DECISIONCRAFT_PROVIDER/DECISIONCRAFT_MODEL, the user config file, then
    the first provider whose API key is set (Anthropic, then OpenAI) with its default model.

    Returns {provider, model, why, escalate}. Raises ProviderError with copy-paste fixes when
    nothing is usable.
    """
    cfg = load_config()
    why = []
    if provider:
        why.append("--provider")
    elif os.environ.get("DECISIONCRAFT_PROVIDER"):
        provider = os.environ["DECISIONCRAFT_PROVIDER"].strip()
        why.append("DECISIONCRAFT_PROVIDER")
    elif cfg.get("provider"):
        provider = cfg["provider"]
        why.append(f"config {config_path()}")
    if provider and provider not in PROVIDERS:
        raise ProviderError(f"Unknown provider {provider!r}. Choose {' or '.join(PROVIDERS)}, for example: "
                            "decisioncraft config set provider anthropic")
    if not provider:
        for name, (env, _m) in PROVIDERS.items():
            if os.environ.get(env):
                provider = name
                why.append(f"{env} is set")
                break
    if not provider:
        raise ProviderError(
            "No model is set up. Set ANTHROPIC_API_KEY or OPENAI_API_KEY, then run the command again "
            "(it picks the provider for you). Or route through your own model: "
            "--complete-cmd 'your-command'. Check with: decisioncraft doctor")
    env = PROVIDERS[provider][0]
    if not os.environ.get(env):
        raise ProviderError(f"The {provider} provider needs {env}. Set it, for example: "
                            f"export {env}=...  then check with: decisioncraft doctor")
    if model:
        why.append("--model")
    elif os.environ.get("DECISIONCRAFT_MODEL"):
        model = os.environ["DECISIONCRAFT_MODEL"].strip()
        why.append("DECISIONCRAFT_MODEL")
    elif cfg.get("model") and (not cfg.get("provider") or cfg.get("provider") == provider):
        model = cfg["model"]
        why.append("config model")
    else:
        model = DEFAULT_MODELS[provider]
        why.append("default model")
    escalate = ESCALATE_MODELS.get(provider) if model == DEFAULT_MODELS.get(provider) else None
    return {"provider": provider, "model": model, "why": ", ".join(why), "escalate": escalate}


def _openai_has(model: str) -> bool:
    try:
        import openai

        return any(m.id == model for m in openai.OpenAI().models.list())
    except Exception:  # noqa: BLE001 - escalation is optional; fail soft
        return False


def provider_complete(
    provider: str, model: str | None = None, max_tokens: int = MAX_TOKENS, effort: str | None = None,
    _usage: dict | None = None,
) -> Complete:
    """A `complete` function for a named provider, using its official SDK.

    Replies stream (Anthropic) so long models do not time out. A reply cut off by the length
    limit raises TruncatedReply instead of returning half a JSON object. The function keeps a
    running `usage` dict ({calls, input_tokens, output_tokens}) and its `provider`/`model`.
    """
    if provider not in PROVIDERS:
        raise ProviderError(
            f"Unknown provider {provider!r}. Choose one of: {', '.join(PROVIDERS)}."
        )
    env, default_model = PROVIDERS[provider]
    if not os.environ.get(env):
        raise ProviderError(f"Set {env} to use the {provider} provider.")
    model = model or default_model
    usage = _usage if _usage is not None else {"calls": 0, "input_tokens": 0, "output_tokens": 0}
    if provider == "anthropic":
        try:
            import anthropic
        except ImportError as e:
            raise ProviderError(
                "Install the smart extra: uv tool install --force "
                "'amplifier-smart-tool-decisioncraft[smart]' (or pip install 'amplifier-smart-tool-decisioncraft[smart]')."
            ) from e
        client = anthropic.Anthropic()

        def complete(system: str, prompt: str) -> str:
            extra = {"extra_body": {"output_config": {"effort": effort}}} if effort else {}
            with client.messages.stream(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                **extra,
            ) as stream:
                msg = stream.get_final_message()
            usage["calls"] += 1
            u = getattr(msg, "usage", None)
            usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
            usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
            if msg.stop_reason == "max_tokens":
                raise TruncatedReply(f"{model} stopped at its length limit ({max_tokens} tokens).")
            if msg.stop_reason == "refusal":
                raise ProviderError(f"{model} declined this request. Try --provider openai or other material.")
            return "".join(getattr(b, "text", "") for b in msg.content if getattr(b, "type", "") == "text")

    else:
        try:
            import openai
        except ImportError as e:
            raise ProviderError(
                "Install the smart extra: uv tool install --force "
                "'amplifier-smart-tool-decisioncraft[smart]' (or pip install 'amplifier-smart-tool-decisioncraft[smart]')."
            ) from e
        client = openai.OpenAI()

        def complete(system: str, prompt: str) -> str:
            extra = {"reasoning": {"effort": effort}} if effort else {}
            r = client.responses.create(
                model=model, instructions=system, input=prompt, max_output_tokens=max_tokens, **extra
            )
            usage["calls"] += 1
            u = getattr(r, "usage", None)
            usage["input_tokens"] += getattr(u, "input_tokens", 0) or 0
            usage["output_tokens"] += getattr(u, "output_tokens", 0) or 0
            if getattr(r, "status", "") == "incomplete":
                reason = getattr(getattr(r, "incomplete_details", None), "reason", "") or "length limit"
                raise TruncatedReply(f"{model} stopped early ({reason}).")
            return r.output_text

    complete.usage = usage  # type: ignore[attr-defined]
    complete.provider = provider  # type: ignore[attr-defined]
    complete.model = model  # type: ignore[attr-defined]
    complete.with_effort = (  # type: ignore[attr-defined]
        lambda level: provider_complete(provider, model, max_tokens, level, usage))
    return complete


def escalation_complete(provider: str, model: str | None) -> "Complete | None":
    """The stronger model a failed draft may try once, or None."""
    if not model:
        return None
    if provider == "openai" and not _openai_has(model):
        return None
    try:
        return provider_complete(provider, model)
    except ProviderError:
        return None


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
    """The JSON object in a model reply.

    Tries the whole reply first (code fences removed), then every `{` in turn and keeps the
    largest object that parses -- so prose or a small example before the real answer cannot
    win over the answer itself.
    """
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else ""
        if t.rstrip().endswith("```"):
            t = t.rstrip()[:-3]
    try:
        value = json.loads(t)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass
    dec = json.JSONDecoder()
    best, best_len = None, 0
    i = t.find("{")
    while i != -1:
        try:
            value, end = dec.raw_decode(t, i)
        except json.JSONDecodeError:
            value, end = None, i
        if isinstance(value, dict) and end - i > best_len:
            best, best_len = value, end - i
            i = t.find("{", end)
        else:
            i = t.find("{", i + 1)
    if best is not None:
        return best
    raise ModelError(
        [{"level": "error", "path": "", "message": "The model reply held no JSON."}]
    )


_LINE_PREFIX = __import__("re").compile(r"^\s*\d+\|\s?", __import__("re").M)
_SPACES = __import__("re").compile(r"\s+")


_KIND_ALIASES = {"code": "quote", "snippet": "quote", "excerpt": "quote", "text": "quote", "doc": "quote",
                 "document": "quote", "readme": "quote", "comment": "quote", "fact": "data", "number": "data",
                 "metric": "data", "figure": "data", "statistic": "data", "config": "file", "path": "file",
                 "note": "observation", "inference": "observation", "assumption": "observation"}


def _text(value) -> str | None:
    """Text from a list or number a model wrote where text was wanted."""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "; ".join(str(v) for v in value if str(v).strip())
    if isinstance(value, (int, float)):
        return str(value)
    return None


_JUDGMENTS = {"fit": "fits", "good": "fits", "yes": "fits", "meets": "fits", "strong": "fits",
              "partial": "mixed", "partly": "mixed", "some": "mixed", "medium": "mixed", "ok": "mixed",
              "no": "does_not_fit", "poor": "does_not_fit", "fails": "does_not_fit", "weak": "does_not_fit",
              "does not fit": "does_not_fit", "not sure": "unknown", "unclear": "unknown"}
_IMPORTANCE = {"critical": "must", "required": "must", "high": "must", "essential": "must",
               "medium": "important", "should": "important", "low": "nice", "optional": "nice", "could": "nice"}


def _tidy_comparison(model: dict, warnings: list[str]) -> None:
    c = model.get("comparison")
    if not isinstance(c, dict):
        return
    for crit in c.get("criteria") or []:
        if isinstance(crit, dict) and crit.get("importance") not in (None, "must", "important", "nice"):
            crit["importance"] = _IMPORTANCE.get(str(crit["importance"]).lower(), "important")
    for opt in c.get("options") or []:
        for ev in (opt.get("evaluations") or []) if isinstance(opt, dict) else []:
            if not isinstance(ev, dict):
                continue
            if ev.get("judgment") not in (None, "fits", "mixed", "does_not_fit", "unknown"):
                ev["judgment"] = _JUDGMENTS.get(str(ev["judgment"]).lower().replace("_", " "), "unknown")
            if "reason" in ev and not isinstance(ev["reason"], str):
                ev["reason"] = _text(ev["reason"]) or ""
    rec = c.get("recommendation")
    if rec is not None:
        if not isinstance(rec, dict) or not str(rec.get("reason") or "").strip():
            c.pop("recommendation")
            warnings.append("Dropped a recommendation that had no reason.")
        elif "risks" in rec and not isinstance(rec["risks"], str):
            rec["risks"] = _text(rec["risks"]) or ""


_WORD_SCALE = {"very low": 1, "low": 2, "small": 2, "s": 2, "medium": 3, "moderate": 3, "m": 3,
               "high": 4, "large": 4, "l": 4, "very high": 5, "xl": 5}


def _scale(value) -> int | None:
    """A 1-5 score from what models write instead: '3', 3.5, 'Medium', 'M', '4/5'."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return max(1, min(5, round(value)))
    text = str(value).strip().lower()
    if text in _WORD_SCALE:
        return _WORD_SCALE[text]
    head = text.split("/")[0].split()[0] if text else ""
    try:
        return max(1, min(5, round(float(head))))
    except ValueError:
        return None


def _squash(text: str) -> str:
    return _SPACES.sub(" ", _LINE_PREFIX.sub("", text)).strip().lower()


def tidy(model: dict, material: list[dict] | None = None) -> list[str]:
    """Fix the slips models make most often, in place, before validation. Returns warnings.

    - evidence written under quote/excerpt/content instead of text; line-number prefixes
      ("  42| ") copied into quotes; evidence with no words is dropped (and its references);
    - references to unknown evidence ids are removed;
    - evidence pointing at an unknown source gets that source added;
    - quotes are checked against the material: ones that cannot be found are kept but
      marked `unverified` and listed as warnings, instead of failing the whole map.
    """
    warnings: list[str] = []
    if not isinstance(model, dict):
        return warnings
    ev = model.get("evidence")
    if isinstance(ev, list):
        haystack = _squash("\n".join(str(m.get("text", "")) for m in (material or [])))
        kept = []
        for e in ev:
            if not isinstance(e, dict):
                continue
            if not str(e.get("text", "")).strip():
                for alt in ("quote", "excerpt", "content", "value", "words"):
                    if str(e.get(alt, "")).strip():
                        e["text"] = e.pop(alt)
                        break
            if isinstance(e.get("text"), str):
                e["text"] = _LINE_PREFIX.sub("", e["text"]).strip()
            kind = e.get("kind")
            if kind and kind not in ("quote", "data", "file", "observation"):
                e["kind"] = _KIND_ALIASES.get(str(kind).lower(), "quote")
            if not str(e.get("text", "")).strip():
                warnings.append(f"Dropped evidence {e.get('id')!r}: it had no words.")
                continue
            if haystack and e.get("kind", "quote") == "quote":
                q = _squash(e["text"])
                if q and q not in haystack and q.strip('"\'') not in haystack:
                    e["unverified"] = True
                    warnings.append(f"Evidence {e.get('id')!r} could not be found word for word in the material.")
            kept.append(e)
        model["evidence"] = kept
        known_src = {s.get("id") for s in model.get("sources", []) if isinstance(s, dict)}
        for e in kept:
            src = e.get("source")
            if isinstance(src, str) and src and src not in known_src:
                model.setdefault("sources", []).append({"id": src, "title": src, "kind": "document"})
                known_src.add(src)
                warnings.append(f"Added source {src!r}, which evidence cited but the reply left out.")
        ids = {e.get("id") for e in kept}

        def clean(obj, top=False):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if k == "evidence" and not top and isinstance(v, list):
                        obj[k] = [r for r in v if r in ids]
                    elif not (top and k == "evidence"):
                        clean(v)
            elif isinstance(obj, list):
                for v in obj:
                    clean(v)

        clean(model, top=True)
    # Decisions and outcomes often reuse short ids (d1, o1) that boxes already use.
    taken: set = set()

    def collect(obj, top=False):
        if isinstance(obj, dict):
            if not top and isinstance(obj.get("id"), str):
                taken.add(obj["id"])
            for k, v in obj.items():
                if not (top and k in ("decisions", "outcomes")):
                    collect(v)
        elif isinstance(obj, list):
            for v in obj:
                collect(v)

    collect(model, top=True)
    renamed = {}
    for key, prefix in (("decisions", "decision"), ("outcomes", "outcome")):
        for item in model.get(key) or []:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                if item["id"] in taken:
                    new = f"{prefix}-{item['id']}"
                    while new in taken:
                        new += "x"
                    renamed[item["id"]] = new
                    item["id"] = new
                taken.add(item["id"])
    if renamed:
        warnings.append(f"Renamed {len(renamed)} decision or outcome id(s) that boxes already used.")
        for n in model.get("notes") or []:
            if isinstance(n, dict) and n.get("decision") in renamed:
                n["decision"] = renamed[n["decision"]]
    # A planned box that replaces one in another journey or stage (models often draw "today"
    # and "planned" as two journeys): move it next to the box it replaces.
    for m in model.get("maps") or []:
        if not isinstance(m, dict):
            continue
        for group_key, box_key in (("journeys", "steps"), ("stages", "items")):
            groups = [g for g in (m.get(group_key) or []) if isinstance(g, dict)]
            home = {}
            for g in groups:
                for b in g.get(box_key) or []:
                    if isinstance(b, dict) and b.get("id"):
                        home[b["id"]] = g
            moved = 0
            for g in groups:
                for b in list(g.get(box_key) or []):
                    if not isinstance(b, dict) or not b.get("replaces"):
                        continue
                    target_group = home.get(b["replaces"])
                    if target_group is None:
                        b.pop("replaces")
                        warnings.append(f"Dropped replaces on {b.get('id')!r}: no box {b['replaces'] if 'replaces' in b else ''} to replace.")
                        continue
                    target = next(x for x in target_group[box_key] if isinstance(x, dict) and x.get("id") == b["replaces"])
                    target.setdefault("when", "today")
                    b["when"] = "planned"
                    if target_group is not g:
                        g[box_key].remove(b)
                        lst = target_group[box_key]
                        lst.insert(lst.index(target) + 1, b)
                        if b.get("lane") is None and target.get("lane"):
                            b["lane"] = target["lane"]
                        moved += 1
            if moved:
                m[group_key] = [g for g in m.get(group_key) or [] if not isinstance(g, dict) or g.get(box_key)]
                warnings.append(f"Moved {moved} planned box(es) next to the ones they replace.")
    _tidy_comparison(model, warnings)

    def text_fields(obj):
        if isinstance(obj, dict):
            for k in ("status_reason", "kind", "summary", "body", "recommend", "question", "why"):
                if k in obj and isinstance(obj[k], list):
                    obj[k] = _text(obj[k]) or ""
            for v in obj.values():
                text_fields(v)
        elif isinstance(obj, list):
            for v in obj:
                text_fields(v)

    for key in ("maps", "notes", "gaps"):
        text_fields(model.get(key))
    for g in model.get("gaps") or []:
        if isinstance(g, dict):
            for k in ("impact", "effort"):
                if k in g and not (isinstance(g[k], int) and 1 <= g[k] <= 5):
                    n = _scale(g[k])
                    if n is None:
                        g.pop(k)
                    else:
                        g[k] = n
    for gi, g in enumerate(model.get("gaps") or []):
        if not isinstance(g, dict) or not isinstance(g.get("stories"), list):
            continue
        shared = g.get("done_when") if isinstance(g.get("done_when"), list) else []
        fixed = []
        for si, st in enumerate(g["stories"]):
            if isinstance(st, str) and st.strip():
                st = {"id": f"{g.get('id', f'g{gi + 1}')}-s{si + 1}", "as": st.strip(),
                      "done_when": [str(c) for c in shared]}
            elif isinstance(st, dict):
                if not st.get("as"):
                    for alt in ("story", "text", "user_story", "title"):
                        if isinstance(st.get(alt), str) and st[alt].strip():
                            st["as"] = st.pop(alt)
                            break
                if isinstance(st.get("done_when"), str):
                    st["done_when"] = [st["done_when"]]
                if not st.get("done_when") and shared:
                    st["done_when"] = [str(c) for c in shared]
                st.setdefault("id", f"{g.get('id', f'g{gi + 1}')}-s{si + 1}")
            else:
                continue
            fixed.append(st)
        g["stories"] = fixed
    return warnings


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


def _note(progress, text: str) -> None:
    if progress:
        progress(text)


def _ask(complete: Complete, system: str, prompt: str, check, *, escalate: "Complete | None" = None,
         fix=None, progress=None, label: str = "") -> dict:
    """Ask once; if the reply fails validation, ask once more with the problems listed; if it
    still fails and a stronger model is given, try that model once. `fix(value)` tidies a
    parsed reply in place before it is checked. A reply cut off at the length limit counts as
    a failed attempt with a clear message."""

    def attempt(fn, p):
        try:
            reply = fn(system, p)
            if os.environ.get("DECISIONCRAFT_DEBUG_DIR"):
                import time as _t

                d = os.environ["DECISIONCRAFT_DEBUG_DIR"]
                os.makedirs(d, exist_ok=True)
                safe = "".join(c if c.isalnum() else "-" for c in label)[:40]
                with open(os.path.join(d, f"{_t.time():.3f}-{safe}.txt"), "w", encoding="utf-8") as f:
                    f.write(reply)
        except TruncatedReply as e:
            _note(progress, f"{label}: the reply was cut off at the length limit.")
            return None, [f"{e} Reply with less: shorter boxes and fewer notes."]
        value, problems = _parse(reply, lambda v: ((fix(v) if fix else None), check(v))[1])
        return value, problems

    value, problems = attempt(complete, prompt)
    if not problems:
        assert value is not None
        return value
    _note(progress, f"{label}: fixing {len(problems)} problem(s) and asking again ...")
    retry = (
        prompt + "\n\nYour last reply had these problems. Fix them and reply with the "
        "whole JSON again:\n- " + "\n- ".join(problems[:30])
    )
    value, problems = attempt(complete, retry)
    if problems and escalate is not None:
        _note(progress, f"{label}: still {len(problems)} problem(s); trying the stronger model "
                        f"{getattr(escalate, 'model', '')} once ...")
        value, problems = attempt(escalate, retry)
    if problems:
        raise ModelError(
            [{"level": "error", "path": "", "message": p} for p in problems[:20]]
        )
    assert value is not None
    return value


def _resolve_complete(provider, model, complete):
    """(complete, escalate) for a call: the caller's own function, or the resolved provider
    and model plus the stronger model it may escalate to once."""
    if complete is not None:
        return complete, None
    r = resolve(provider, model)
    fn = provider_complete(r["provider"], r["model"])
    esc = escalation_complete(r["provider"], r["escalate"]) if r["escalate"] else None
    return fn, esc


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
    escalate: Complete | None = None,
    progress=None,
    defer_notes: bool = False,
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
    if complete is None:
        complete, auto_escalate = _resolve_complete(provider, model, None)
        escalate = escalate or auto_escalate
    if hasattr(complete, "with_effort"):
        complete = complete.with_effort("medium")  # thinking shares the reply's token budget
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
        "Say 'not sure' rather than invent facts. "
        + ("Leave notes as an empty list: notes from each role are added in a separate step. "
           if defer_notes else "")
        + "Evidence items are {id, source, kind, text}, kind one of quote, data, file, observation: "
        "put the exact words in text, without the line numbers shown in the material. Each gap's "
        "stories are objects {id, as, done_when: [checks in text]}. Reply with the JSON only.\n\n"
        + _material_block(material, max_material_chars)
    )

    def check(v):
        return [p["message"] for p in validate(v) if p["level"] == "error"]

    result = _ask(complete, system, prompt, check, escalate=escalate,
                  fix=lambda v: tidy(v, material), progress=progress, label="Draft")
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
    escalate: Complete | None = None,
    progress=None,
    parallel: bool | None = None,
) -> dict:
    """Model-backed. Add notes from each role to an existing model; returns the new model.

    Existing notes are kept. New notes get fresh ids, point at existing boxes or gaps,
    cite existing evidence where they can, and end in a question. Each role is asked in its
    own small call, several at once, so a slow or failed role does not sink the others.
    parallel: None (default) asks roles separately only for a vendor provider; a caller's own
    `complete` (a host model) gets one call for all roles unless parallel=True.
    """
    if parallel is None:
        parallel = complete is None or hasattr(complete, "with_effort")
    if complete is None:
        complete, auto_escalate = _resolve_complete(provider, model_name, None)
        escalate = escalate or auto_escalate
    if hasattr(complete, "with_effort"):
        complete = complete.with_effort("low")
    roles = roles or model.get("roles") or default_roles()
    merged_roles = {r["id"]: r for r in (model.get("roles") or default_roles())}
    for r in roles:
        merged_roles.setdefault(r["id"], r)
    system = "You review decision models from several points of view. " + _guide()
    base_json = json.dumps(model, indent=1)
    mat = _material_block(material or [], max_material_chars)

    def combine(notes):
        out = dict(model)
        out["roles"] = list(merged_roles.values())
        out["notes"] = list(model.get("notes", [])) + list(notes)
        return out

    def ask_for(group: list[dict], prefix: str) -> list[dict]:
        prompt = (
            f"Here is a decision model:\n{base_json}\n\n"
            f"Write up to {per_role} new notes for each of these roles:\n{json.dumps(group, indent=1)}\n"
            "Ask only questions that could change the choice or resolve an important unknown. "
            "Do not repeat a standard checklist for every role or fill a quota. "
            "Explain why each question matters in everyday words. "
            "Each note: {id, role, anchor (an existing box or gap id), title, body, recommend, "
            "question, urgency (must|should|info), evidence (existing evidence ids)}. Use ids that "
            f"start with '{prefix}'. Do not repeat points the model already makes. Reply with "
            '{"notes": [...]} only.\n\n' + mat
        )

        def check(v):
            if not isinstance(v, dict) or not isinstance(v.get("notes"), list):
                return ['Reply must be {"notes": [...]}.']
            return [p["message"] for p in validate(combine(v["notes"])) if p["level"] == "error"]

        def fix(v):
            if isinstance(v, dict) and isinstance(v.get("notes"), list):
                known = {e.get("id") for e in model.get("evidence", []) if isinstance(e, dict)}
                for n in v["notes"]:
                    if isinstance(n, dict) and isinstance(n.get("evidence"), list):
                        n["evidence"] = [r for r in n["evidence"] if r in known]
            return []

        label = "Notes from " + ", ".join(r.get("label", r["id"]) for r in group)
        got = _ask(complete, system, prompt, check, escalate=escalate, fix=fix,
                   progress=progress, label=label)
        notes = got.get("notes", [])
        for n in notes:
            n.setdefault("author", "AI assistant")
        return notes

    if parallel and len(roles) > 1:
        from concurrent.futures import ThreadPoolExecutor

        def one(i_role):
            i, role = i_role
            notes = ask_for([role], f"P{i + 1}-")
            _note(progress, f"Notes from {role.get('label', role['id'])}: {len(notes)} added.")
            return notes

        new: list[dict] = []
        with ThreadPoolExecutor(max_workers=min(4, len(roles))) as pool:
            for notes in pool.map(one, list(enumerate(roles))):
                new.extend(notes)
        seen = {n.get("id") for n in model.get("notes", [])}
        for n in new:
            while n.get("id") in seen:
                n["id"] = f"{n.get('id')}x"
            seen.add(n.get("id"))
        result = combine(new)
        problems = [p["message"] for p in validate(result) if p["level"] == "error"]
        if problems:
            raise ModelError([{"level": "error", "path": "", "message": p} for p in problems[:20]])
        return result
    return combine(ask_for(roles, "P"))


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
    if complete is None:
        complete, _esc = _resolve_complete(provider, model_name, None)
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
