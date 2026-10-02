"""A short interview, one question at a time, that ends in a starter model.

State lives in the decision folder as `interview.json`, so a host can ask a question, wait
for the person, and come back later (or from another process) with the answer. Every step
is deterministic: the next question depends only on the answers so far.

Three question sets: personal (one person or a household weighing options), team (several
people or groups, with an owner and evidence) and system (how something works today and what
would change). The set is chosen from the first answer unless the caller names it. Questions
already answered by the first sentence are skipped, and a low-stakes choice stops early.
"""

from __future__ import annotations

import json
import re
from datetime import date as _date
from pathlib import Path

from .modes import infer, quick, triage
from .starter import material_readme, pick_roles, title_from

STATE = "interview.json"
FORMAT = "decisioncraft-interview/1"

UNDO_CHOICES = ["Easy to undo", "Some cost to undo", "Hard to undo"]
PEOPLE_CHOICES = ["Just me", "Me and my family or household", "A team", "Several groups"]
VISUAL_CHOICES = [
    "Someone's experience, step by step",
    "How the work changes, today and planned",
    "How the options compare",
]

# Each question: id, ask, why, kind (text|list|choice|number), sets (which question sets),
# core (asked even for low stakes), min_score (only asked when stakes reach this).
QUESTIONS = [
    {"id": "decision", "ask": "What are you trying to decide? One sentence is fine.",
     "why": "Everything else hangs off this.", "kind": "text", "sets": ["personal", "team", "system"], "core": True},
    {"id": "options", "ask": "What are the options? Include doing nothing or waiting, if that is a real choice.",
     "why": "Choices go wrong most often when an option is missing.", "kind": "list",
     "sets": ["personal", "team"], "core": True},
    {"id": "today", "ask": "How does it work today, roughly step by step?",
     "why": "The plan is easier to judge next to how things work now.", "kind": "list",
     "sets": ["system"], "core": True},
    {"id": "planned", "ask": "What would change? Describe the new way, or the options for it.",
     "why": "This becomes the planned side of the map.", "kind": "list", "sets": ["system"], "core": True},
    {"id": "must_haves", "ask": "Is anything a must-have or a deal-breaker?",
     "why": "An option that fails a must-have drops out, however well it does elsewhere.",
     "kind": "list", "sets": ["personal", "team"], "min_score": 2},
    {"id": "criteria", "ask": "What matters most when you choose? Name a few things, most important first.",
     "why": "This is what the options get compared on.", "kind": "list",
     "sets": ["personal", "team", "system"], "core": True},
    {"id": "deadline", "ask": "When do you need to decide by?",
     "why": "A close deadline changes how much checking is worth doing.", "kind": "text",
     "sets": ["personal", "team", "system"], "core": True},
    {"id": "reversible", "ask": "If it turns out wrong, how easy is it to undo?",
     "why": "Hard-to-undo choices deserve more care before, easy ones can be tried.",
     "kind": "choice", "choices": UNDO_CHOICES, "sets": ["personal", "team", "system"], "core": True},
    {"id": "budget", "ask": "Is there a budget or a cost limit?",
     "why": "Money is usually a must-have in disguise.", "kind": "text", "sets": ["personal"], "min_score": 2,
     "only_if": r"buy|buying|purchase|lease|rent|price|cost|afford|car|van|house|home|flat|apartment|"
                r"laptop|phone|kitchen|renovat|holiday|trip|wedding|tuition|school fees|subscription"},
    {"id": "people", "ask": "Who else is affected, or gets a say?",
     "why": "People who are affected but not asked tend to undo the choice later.",
     "kind": "choice", "choices": PEOPLE_CHOICES, "sets": ["personal"], "core": True},
    {"id": "owner", "ask": "Who makes the final call?",
     "why": "Reviews end with a decision only when someone owns it.", "kind": "text",
     "sets": ["team", "system"], "core": True},
    {"id": "groups", "ask": "Which groups are affected? Each one gets a point of view on the map.",
     "why": "Each group becomes a role with its own notes.", "kind": "list", "sets": ["team", "system"],
     "core": True},
    {"id": "why_now", "ask": "Why does this matter now? What would a good outcome look like?",
     "why": "It becomes the summary at the top of the map.", "kind": "text", "sets": ["team", "system"],
     "min_score": 3},
    {"id": "evidence", "ask": "What material do you have: notes, interviews, numbers, documents?",
     "why": "Every claim on the map should point back to something real.", "kind": "text",
     "sets": ["team", "system"], "min_score": 3},
    {"id": "known", "ask": "What do you already know, and what are you unsure about?",
     "why": "The unsure parts become the things to check first.", "kind": "text",
     "sets": ["personal", "team", "system"], "min_score": 3},
    {"id": "whatifs", "ask": "What could change the picture? For example a price rise, a move or a new job.",
     "why": "A choice that only works if nothing changes is fragile.", "kind": "list",
     "sets": ["personal", "team"], "min_score": 4},
    {"id": "visual", "ask": "What would a picture help with most?",
     "why": "This picks the kind of map to draw.", "kind": "choice", "choices": VISUAL_CHOICES,
     "sets": ["team"], "core": True},
]
BY_ID = {q["id"]: q for q in QUESTIONS}


def question_bank() -> dict:
    """Every question by set, for hosts that want to ask in their own words."""
    return {s: [{k: q[k] for k in ("id", "ask", "why", "kind") if k in q}
                | ({"choices": q["choices"]} if "choices" in q else {})
                for q in QUESTIONS if s in q["sets"]]
            for s in ("personal", "team", "system")}


def parse_list(text: str) -> list[str]:
    """'keep it, renew the lease, or buy new' -> ['keep it', 'renew the lease', 'buy new']."""
    if not text or re.fullmatch(r"\s*(none|nothing|no|n/a|skip|-)\s*\.?", text, re.I):
        return []
    parts = re.split(r"\n|;|,|\bor\b|\bversus\b|\bvs\.?\b|\s/\s", text)
    out = []
    for p in parts:
        p = re.sub(r"^\s*(?:and|or|then|[-*•\d.)]+)\s+", "", p.strip()).strip(" .")
        if p:
            out.append(p[:1].upper() + p[1:])
    return out


def _parse_choice(text: str, choices: list[str]) -> str | None:
    t = text.strip().lower()
    if t.isdigit() and 1 <= int(t) <= len(choices):
        return choices[int(t) - 1]
    for c in choices:
        if t and (t in c.lower() or c.lower().split()[0] in t):
            return c
    return None


def _set_from(text: str) -> str:
    t = " " + text.lower() + " "
    found = infer(text)
    system = re.search(r"\b(process|system|service|workflow|works today|pipeline|upload|handover|discharge|intake|onboarding)\b", t)
    if found.get("people") in ("team", "several groups"):
        return "system" if system else "team"
    return "personal"


def _path(directory) -> Path:
    return Path(directory).expanduser() / STATE


def load(directory) -> dict | None:
    p = _path(directory)
    if not p.exists():
        return None
    value = json.loads(p.read_text(encoding="utf-8"))
    if value.get("format") != FORMAT:
        raise ValueError(f"{p} is not a Decisioncraft interview file.")
    return value


def _save(directory, state: dict) -> None:
    p = _path(directory)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _triage_answers(a: dict) -> dict:
    out = {}
    if "reversible" in a:
        out["reversible"] = a["reversible"]
    if "people" in a:
        out["people"] = a["people"]
    elif a.get("groups"):
        out["people"] = "several groups" if len(a["groups"]) >= 2 else "team"
    if a.get("budget"):
        out["cost"] = a["budget"]
    if a.get("deadline"):
        out["deadline"] = a["deadline"]
    return out


def _stakes(state: dict) -> dict:
    a = state["answers"]
    return triage(_triage_answers(a), text=a.get("decision", ""))


def _record(state: dict, qid: str, text: str) -> None:
    q = BY_ID[qid]
    text = (text or "").strip()
    suggested = (state.get("suggested") or {}).get(qid)
    if q["kind"] == "list" and suggested:
        adding = re.match(r"\s*(yes|yeah|also|and|plus|add)\b", text, re.I)
        extra = [] if re.fullmatch(r"\s*(|no|none|nope|that'?s (it|all)|those|both|yes|correct)\s*\.?", text, re.I) \
            else parse_list(re.sub(r"^\s*(yes|yeah|also|and|plus|add)[,:]?\s*", "", text, flags=re.I))
        # A full list of two or more replaces the suggestion; "also ..." or a single item adds to it.
        value = extra if len(extra) >= 2 and not adding else list(dict.fromkeys(suggested + extra))
    elif q["kind"] == "list":
        value = parse_list(text)
    elif q["kind"] == "choice":
        value = _parse_choice(text, q["choices"]) or text
    else:
        value = text
    state["answers"][qid] = value
    state["asked"].append(qid)
    if qid == "decision":
        found = infer(text)
        if not state.get("set_given"):
            state["set"] = _set_from(text)
        # Skip what the first sentence already says.
        if found.get("reversible") == "hard" and "reversible" not in state["answers"]:
            state["answers"]["reversible"] = "Hard to undo"
            state["inferred"].append("reversible")
        if re.search(r"\b(just me|only me|only affects me)\b", text, re.I) and state["set"] == "personal":
            state["answers"]["people"] = "Just me"
            state["inferred"].append("people")
        opts = re.findall(r"\b(?:whether to|whether|should i|should we|i should|we should)\s+(?:just\s+)?(.+?)\s+or\s+(.+?)[?.!]?$", text.strip(), re.I)
        if not opts and len(text) <= 90 and len(re.findall(r"\bor\b", text, re.I)) == 1:
            m = re.match(r"\s*(.+?)\s+or\s+(.+?)\s*[?.!]?\s*$", text, re.I)
            opts = [m.groups()] if m else []
        if opts and "options" not in state["answers"]:
            # Suggested, not settled: the options question is still asked, with these filled in.
            a, b = opts[0]
            state["suggested"] = {"options": [a[:1].upper() + a[1:], b[:1].upper() + b[1:].rstrip("?")]}


def _next_q(state: dict) -> dict | None:
    stakes = _stakes(state)
    score = stakes["stakes"]["score"]
    low = stakes["mode"] in ("none", "quick")
    for q in QUESTIONS:
        if state["set"] not in q["sets"] or q["id"] in state["answers"]:
            continue
        if q.get("only_if") and not re.search(rf"\b(?:{q['only_if']})", state["answers"].get("decision", ""), re.I):
            continue
        if q["id"] == "decision" or q.get("core"):
            # Low stakes: once options and what matters are known, stop.
            if low and q["id"] not in ("decision", "options", "criteria", "today", "planned") \
                    and all(k in state["answers"] for k in ("decision", "criteria")):
                continue
            return q
        if not low and score >= q.get("min_score", 0):
            return q
    return None


def _progress(state: dict) -> dict:
    remaining = 0
    probe = {**state, "answers": dict(state["answers"])}
    while (q := _next_q(probe)) is not None and remaining < 30:
        probe["answers"][q["id"]] = "…"
        remaining += 1
    asked = len([k for k in state["answers"] if k not in state["inferred"]])
    return {"asked": asked, "remaining": remaining, "of": asked + remaining}


def start(directory, *, question: str = "", kind: str | None = None) -> dict:
    """Begin (or restart) an interview in a folder. Returns the first step.

    A first answer that is plainly small and easy to undo ends it at once with mode "none"
    and writes nothing (unless `kind` was given, which means the caller wants the interview).
    """
    if kind and kind not in ("personal", "team", "system"):
        raise ValueError("Kind must be personal, team or system.")
    state = {"format": FORMAT, "set": kind or "personal", "set_given": bool(kind), "answers": {},
             "asked": [], "inferred": [], "suggested": {}, "pending": "decision", "done": False}
    if question:
        _record(state, "decision", question)
        state["pending"] = None
    _save(directory, state)
    return step(directory)


def step(directory, answer: str | None = None, *, question: str = "", kind: str | None = None) -> dict:
    """Record an answer to the pending question (if any) and return the next step.

    The result is either {"done": false, "question": {...}, "progress": {...}} or, when there
    is nothing more worth asking, {"done": true, "model_path", "mode", ...} after writing
    model.json and material/README.txt into the folder.
    """
    state = load(directory)
    if state is None:
        if answer and not question:
            question = answer
            answer = None
        return start(directory, question=question, kind=kind)
    if state.get("done"):
        return {"format": FORMAT, "done": True, "model_path": str(Path(directory).expanduser() / "model.json"),
                "mode": state.get("mode"), "message": "This interview is finished. Use --reset to start again."}
    if answer is not None and state.get("pending"):
        _record(state, state["pending"], answer)
        state["pending"] = None
    if not state.get("set_given") and "decision" in state["answers"] and len(state["asked"]) == 1:
        first = triage(text=state["answers"]["decision"])
        if first["mode"] == "none":
            state.update(done=True, pending=None, mode="none")
            _save(directory, state)
            return {"format": FORMAT, "done": True, "set": state["set"], "mode": "none", "why": first["why"],
                    "model_path": None, "files": [], "next": [],
                    "message": "This is small and easy to undo, so an interview is more than it needs. "
                    "Just answer, or offer a quick side-by-side if they want one. No model was written."}
    q = _next_q(state)
    if q is None:
        result = finish(directory, state)
        return result
    state["pending"] = q["id"]
    _save(directory, state)
    stakes = _stakes(state)
    out = {k: q[k] for k in ("id", "ask", "why", "kind")}
    if "choices" in q:
        out["choices"] = q["choices"]
    suggested = (state.get("suggested") or {}).get(q["id"])
    if suggested:
        out["suggested"] = suggested
        out["ask"] = (f"So far I have: {', '.join(suggested)}. Any others? Doing nothing or waiting "
                      "counts if it is a real choice.")
    if q["kind"] == "list":
        out["hint"] = "Separate items with commas, or one per line."
    return {"format": FORMAT, "done": False, "set": state["set"], "question": out,
            "progress": _progress(state), "mode_so_far": stakes["mode"],
            "known": {k: v for k, v in state["answers"].items()}}


def _criteria(answers: dict) -> list[dict]:
    musts = answers.get("must_haves") or []
    crit = [{"label": m, "importance": "must"} for m in musts]
    for i, c in enumerate(answers.get("criteria") or []):
        if c.lower() not in {m.lower() for m in musts}:
            crit.append({"label": c, "importance": "important" if i < 2 else "nice"})
    return crit


def _template(state: dict) -> str:
    if state["set"] == "system":
        return "system-journeys"
    if state["set"] == "team":
        v = state["answers"].get("visual", "")
        if v.startswith("Someone"):
            return "customer-journey"
        if v.startswith("How the work"):
            return "service-blueprint"
    return "decision-chain"


def build_model(state: dict, *, date: str = "") -> dict:
    """The starter model from an interview's answers."""
    from .model import new_model

    a = state["answers"]
    question = a.get("decision", "").strip()
    if question and not question.endswith("?") and re.match(
            r"(should|which|what|how|whether|do|does|is|are|can|will|where|when|who)\b", question, re.I):
        question = question.rstrip(".") + "?"
    title = title_from(question)
    template = _template(state)
    model = new_model(template, title, question, date=date or _date.today().isoformat())
    if state["set"] == "personal":
        # TODO(merge with the personal-decision template): the personal roles and template
        # land in a parallel branch; until then personal decisions use the default roles.
        model["roles"] = pick_roles(None)
    else:
        model["roles"] = pick_roles(None)
    summary = a.get("why_now") or ""
    if a.get("known"):
        summary = (summary + " " if summary else "") + f"What we know so far: {a['known']}"
    model["summary"] = summary.strip()
    crit = _criteria(a)
    options = a.get("options") or []
    if options or crit:
        q = quick(options if len(options) >= 2 else options + ["Keep things as they are"],
                  crit or None, question=question) if (len(options) >= 1) else None
        model["comparison"] = {
            "why": "Options and what matters, from the interview.",
            "criteria": [{"id": c["id"], "label": c["label"], "importance": c["importance"]}
                         for c in (q["criteria"] if q else [])],
            "options": [{"id": o["id"], "title": o["title"], "summary": "", "evaluations": []}
                        for o in (q["options"] if q else [])],
            "method": "",
            "review_when": a.get("deadline", ""),
        }
    model["interview"] = {"set": state["set"], "answers": a, "inferred": state["inferred"]}
    # TODO(merge with the personal-decision template): field names from the parallel plan.
    model["personal"] = {
        "options": options,
        "criteria": crit,
        "scores": [],
        "costs": {"budget": a.get("budget", "")} if a.get("budget") else {},
        "whatifs": a.get("whatifs") or [],
    }
    return model


def finish(directory, state: dict | None = None) -> dict:
    """Write model.json and material/README.txt from the interview and mark it done."""
    from .model import validate

    state = state or load(directory)
    if state is None:
        raise ValueError("No interview in this folder. Start one with: decisioncraft interview --dir FOLDER")
    folder = Path(directory).expanduser().resolve()
    model = build_model(state)
    problems = [p for p in validate(model) if p.get("level") == "error"]
    if problems:
        raise ValueError("The starter model has problems: " + "; ".join(p["message"] for p in problems[:5]))
    stakes = _stakes(state)
    (folder / "material").mkdir(parents=True, exist_ok=True)
    (folder / "model.json").write_text(json.dumps(model, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    readme = folder / "material" / "README.txt"
    if not readme.exists():
        readme.write_text(material_readme(model, state["answers"].get("evidence", "")), encoding="utf-8")
    state.update(done=True, pending=None, mode=stakes["mode"])
    _save(directory, state)
    mode = stakes["mode"]
    rel = str(folder)
    nxt = {
        "none": [],
        "quick": [f"decisioncraft quick --from {rel}/model.json --json"],
        "guided": [f"decisioncraft render {rel}/model.json --open"],
        "team": [f"add notes and documents to {rel}/material/",
                 f"decisioncraft draft {rel}/material/*.md --question \"{model['question']}\" --complete-cmd 'YOUR-COMMAND' --out {rel}/model.json",
                 f"decisioncraft render {rel}/model.json --open"],
    }[mode]
    return {"format": FORMAT, "done": True, "set": state["set"], "mode": mode,
            "why": stakes["why"], "model_path": str(folder / "model.json"),
            "files": [str(folder / "model.json"), str(readme)],
            "answers": state["answers"], "next": nxt}


def run_interactive(directory, ask, say, *, question: str = "", kind: str | None = None) -> dict:
    """Run the whole interview at a terminal. `ask(prompt, default) -> str`, `say(text)`."""
    r = start(directory, question=question, kind=kind) if load(directory) is None or question \
        else step(directory)
    while not r["done"]:
        q = r["question"]
        say("")
        say(f"{q['ask']}")
        say(f"  ({q['why']})")
        if q.get("choices"):
            for i, c in enumerate(q["choices"], 1):
                say(f"  {i}. {c}")
        answer = ask("Your answer" + (" (a number or words)" if q.get("choices") else ""), "")
        r = step(directory, answer)
    return r
