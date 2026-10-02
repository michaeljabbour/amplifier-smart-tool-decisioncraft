"""Three ways to help with a choice, and a rule for picking one.

- Just answer: a small, easy-to-undo choice that only affects the person asking. Give an
  opinion if asked; build nothing.
- Quick: options, what matters, a small scored table, a lean and the one thing to check,
  all in the conversation. No files.
- Guided: a short interview, one question at a time, then a canvas to look at.
- Team: the full canvas, with every role's notes, reviews, a live session and Ask the
  experts, because several groups are affected and each should be heard.

`triage` picks one from four plain answers (cost, how easy it is to undo, who is affected,
the deadline). It is deterministic: the same answers always give the same mode. A host can
pass free text instead; then simple word rules fill in what they can, and a host model
(optional) can read the text more carefully. `quick` scores a handful of options against
what matters. With scores given it is deterministic; with only free text it needs a model
to read the options out of the text, then the scoring is code again.
"""

from __future__ import annotations

import json
import re

MODES = {
    "none": {
        "label": "Just answer",
        "summary": "A small choice that is easy to undo and only affects the person asking.",
        "does": "Answer in a sentence or two. Offer a side-by-side only if they want one. "
        "Build nothing.",
    },
    "quick": {
        "label": "Quick",
        "summary": "A real choice, but small enough to settle in the conversation.",
        "does": "List the options and what matters, score them in a small table, give a lean "
        "and the one thing to check before choosing. No files. "
        "Command: decisioncraft quick.",
    },
    "guided": {
        "label": "Guided",
        "summary": "Costly or hard to undo, or worth seeing laid out.",
        "does": "Ask a few questions one at a time, then draw a canvas the person can open: "
        "the options side by side, what matters, what could change the picture. "
        "Commands: decisioncraft interview, then decisioncraft render.",
    },
    "team": {
        "label": "Team",
        "summary": "Several groups are affected and each should be heard before anyone chooses.",
        "does": "The full canvas: how it works today and the plan, notes from every role, "
        "reviews merged, a live session and Ask the experts. Commands: decisioncraft "
        "interview --kind team, draft, render, session.",
    },
}

ORDER = ["none", "quick", "guided", "team"]

TRIAGE_QUESTIONS = {
    "cost": "Roughly how much money, time or effort is at stake?",
    "reversible": "If it turns out wrong, how easy is it to undo? (easy, some cost, or hard)",
    "people": "Who else is affected or gets a say? (just you, family, a team, or several groups)",
    "deadline": "When do you need to decide by?",
}

_MONEY = re.compile(r"(?<![\w.])\$?\s?(\d[\d,]*(?:\.\d+)?)\s*(k|m|thousand|million)?\b", re.I)


def _amount(text: str) -> float | None:
    """The largest amount of money written in the text, if any ('$25k', '30,000')."""
    best = None
    for m in _MONEY.finditer(text):
        raw = m.group(0)
        unit = (m.group(2) or "").lower()
        if "$" not in raw and not unit:
            continue  # a bare number is more often a count or a year than money
        n = float(m.group(1).replace(",", ""))
        n *= {"k": 1e3, "thousand": 1e3, "m": 1e6, "million": 1e6}.get(unit, 1)
        best = n if best is None else max(best, n)
    return best


def _words(text: str, *patterns: str) -> bool:
    return any(re.search(rf"\b(?:{p})\b", text) for p in patterns)


# Plain word rules for free text. Each returns a level or None when the text says nothing.
SMALL_THINGS = r"pizza|tacos|lunch|dinner|breakfast|coffee|snack|movie|film|show|song|playlist|outfit|shirt|colou?r|font|emoji|game tonight"
BIG_THINGS = (r"house|home|flat|apartment|mortgage|car|van|truck|vehicle|lease|job|offer|salary|"
              r"career|school|university|college|surgery|treatment|wedding|business|company|"
              r"vendor|supplier|contract|platform|migration|bridge|hospital|ward|hire|hiring")
HARD_TO_UNDO = r"offers?|accept|buy|buying|sign|signing|contract|lease|mortgage|quit|resign|move|moving|hire|fire|surgery|replace|rebuild|demolish|years?|permanent|commit"
EASY_TO_UNDO = r"try|trial|test|tonight|this weekend|return|refund|cancel any ?time"
GROUPS = r"customers|patients|public|residents|council|company|organi[sz]ation|departments|several groups|everyone|staff|ward|nurses|doctors|clinic|students"
TEAM = r"we|our|us|team|colleagues|department|board|committee|managers|engineers|vendor|supplier"
FAMILY = r"family|partner|wife|husband|kids|children|parents|household|roommates?|flatmates?"


CHOICE_WORDS = (r"should|or|vs|versus|which|whether|decide|deciding|decision|choose|choosing|torn|"
                r"options?|pick|renew|keep|replace|buy|lease|between|pros and cons|weighing|worth it|"
                r"go with|switch|stay|leave|accept|offers?")


def looks_like_choice(text: str) -> bool:
    """True when the text reads like someone weighing options, not asking a fact."""
    return _words(" " + (text or "").lower() + " ", CHOICE_WORDS)


def infer(text: str) -> dict:
    """Fill in triage answers from free text with plain word rules. Unknowns stay out."""
    t = " " + (text or "").lower() + " "
    out: dict = {}
    amount = _amount(t)
    if amount is not None:
        out["cost"] = amount
    elif _words(t, BIG_THINGS):
        out["cost"] = "large"
    elif _words(t, SMALL_THINGS):
        out["cost"] = "small"
    if _words(t, EASY_TO_UNDO) and not _words(t, HARD_TO_UNDO):
        out["reversible"] = "easy"
    elif _words(t, HARD_TO_UNDO):
        out["reversible"] = "hard"
    elif _words(t, SMALL_THINGS):
        out["reversible"] = "easy"
    if _words(t, GROUPS):
        out["people"] = "several groups"
    elif _words(t, TEAM):
        out["people"] = "team"
    elif _words(t, FAMILY):
        out["people"] = "family"
    elif _words(t, r"i|me|my|myself|i'm|im"):
        out["people"] = "just me"
    if _words(t, r"today|tonight|now|right now|in an hour|this afternoon"):
        out["deadline"] = "today"
    return out


def _cost_level(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        n = float(v)
    else:
        s = str(v).lower().strip()
        n = _amount(s if "$" in s or re.search(r"\d\s*(k|m)\b", s) else "$" + s) if re.search(r"\d", s) else None
        if n is None:
            if _words(" " + s + " ", r"none|nothing|free|tiny|trivial|small|little|a few dollars|cheap|low"):
                return 0
            if _words(" " + s + " ", r"medium|moderate|hundreds|some"):
                return 1
            if _words(" " + s + " ", r"large|big|thousands|expensive|high|a lot"):
                return 2
            if _words(" " + s + " ", r"very large|huge|tens of thousands|life changing|major"):
                return 3
            return None
    if n < 100:
        return 0
    if n < 2000:
        return 1
    if n < 20000:
        return 2
    return 3


def _undo_level(v) -> int | None:
    if v is None or v == "":
        return None
    if v is True:
        return 0
    if v is False:
        return 2
    s = " " + str(v).lower().strip() + " "
    if _words(s, r"hard|no|not|never|permanent|cannot|can't|years|very hard|difficult"):
        return 2
    if _words(s, r"some|partly|costly|fee|penalty|a bit|somewhat|with effort"):
        return 1
    if _words(s, r"easy|easily|yes|undo|return|refund|reversible|anytime|any time|trivial"):
        return 0
    return None


def _people_level(v) -> int | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        n = int(v)
        return 0 if n <= 1 else 1 if n <= 6 else 2 if n <= 50 else 3
    s = " " + str(v).lower().strip() + " "
    if _words(s, GROUPS + r"|groups|many|org"):
        return 3
    if _words(s, TEAM):
        return 2
    if _words(s, FAMILY + r"|couple|two of us|friends?"):
        return 1
    if _words(s, r"me|just me|myself|only me|i|nobody else|no one else|alone"):
        return 0
    m = re.search(r"\d+", s)
    return _people_level(int(m.group(0))) if m else None


def _deadline_days(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = " " + str(v).lower().strip() + " "
    if _words(s, r"now|today|tonight|right now|this afternoon|an hour|hours?"):
        return 0.5
    if _words(s, r"tomorrow"):
        return 1
    m = re.search(r"(\d+)\s*(day|week|month|year)s?", s)
    if m:
        return float(m.group(1)) * {"day": 1, "week": 7, "month": 30, "year": 365}[m.group(2)]
    if _words(s, r"this week|few days"):
        return 5
    if _words(s, r"next week"):
        return 10
    if _words(s, r"this month|few weeks"):
        return 21
    if _words(s, r"next month|month"):
        return 45
    if _words(s, r"no rush|no deadline|whenever|someday|no hurry"):
        return 365
    return None


def _model_answers(text: str, complete) -> dict:
    system = ("You read a person's message and estimate four things about the choice in it. "
              "Reply with JSON only.")
    prompt = (
        f"Message: {text}\n\nReply with {{\"cost\": number in dollars or null, \"reversible\": "
        "\"easy\"|\"some cost\"|\"hard\"|null, \"people\": \"just me\"|\"family\"|\"team\"|"
        "\"several groups\"|null, \"deadline\": text or null}. Use null when the message "
        "does not say."
    )
    reply = complete(system, prompt)
    m = re.search(r"\{.*\}", reply, re.S)
    if not m:
        return {}
    try:
        value = json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}
    return {k: v for k, v in value.items() if k in TRIAGE_QUESTIONS and v not in (None, "")}


def triage(answers: dict | None = None, *, text: str = "", complete=None) -> dict:
    """Recommend how much help a choice needs: none, quick, guided or team.

    `answers` may hold cost (a number of dollars or words like small/large), reversible
    (easy / some cost / hard, or true/false), people (just me / family / team / several
    groups, or a count) and deadline (days, or words like today / this week). Answers given
    win over anything read from `text`. Deterministic unless `complete` is passed, in which
    case a model reads `text` first and the rules run on what it found.
    """
    answers = dict(answers or {})
    if not isinstance(answers, dict):
        raise ValueError("Answers must be an object with cost, reversible, people and deadline.")
    found = infer(text) if text else {}
    if text and complete is not None:
        found.update(_model_answers(text, complete))
    merged = {**found, **{k: v for k, v in answers.items() if v not in (None, "")}}
    cost = _cost_level(merged.get("cost"))
    undo = _undo_level(merged.get("reversible"))
    people = _people_level(merged.get("people"))
    days = _deadline_days(merged.get("deadline"))
    missing = [{"id": k, "question": q} for k, q, level in (
        ("cost", TRIAGE_QUESTIONS["cost"], cost),
        ("reversible", TRIAGE_QUESTIONS["reversible"], undo),
        ("people", TRIAGE_QUESTIONS["people"], people),
    ) if level is None]
    # Unknowns count as the middle, so a missing answer never hides a big choice.
    c = 1 if cost is None else cost
    u = 1 if undo is None else undo
    p = 1 if people is None else people
    score = c + u + p
    why = []
    labels = {
        "cost": ["little at stake", "a moderate amount at stake", "a lot at stake", "a very large amount at stake"],
        "undo": ["easy to undo", "some cost to undo", "hard to undo"],
        "people": ["only affects you", "affects your family or household", "affects a team", "affects several groups"],
    }
    if cost is not None:
        why.append(labels["cost"][cost])
    if undo is not None:
        why.append(labels["undo"][undo])
    if people is not None:
        why.append(labels["people"][people])

    if people is not None and people >= 3 or (p >= 2 and score >= 5):
        mode = "team"
    elif score >= 3 or c >= 2 or u == 2:
        mode = "guided"
    elif cost == 0 and undo == 0 and (people is None or people <= 1):
        mode = "none"  # small and easy to undo: nobody needs a table for this
    elif score <= 1 and not missing:
        mode = "none"
    else:
        mode = "quick"

    if text and not answers and complete is None and not looks_like_choice(text):
        mode = "none"
        why = ["this reads like a question to answer, not a choice to weigh"]

    alternative = None
    if days is not None and days < 1 and mode in ("guided", "team"):
        alternative = mode
        mode = "quick"
        why.append("it has to be decided today, so a quick comparison now; the fuller version "
                   "is worth it if the deadline can move")
    elif days is not None and mode != "none":
        why.append(f"about {days:g} day{'s' if days != 1 else ''} to decide")

    offers = {
        "none": "Just answer. If they seem torn, offer: \"Want me to put the two side by side?\"",
        "quick": "Offer: \"Want me to lay the options side by side with what matters to you?\"",
        "guided": "Offer: \"This one's worth a closer look. Want me to ask a few questions and "
        "lay it out as a map you can open?\"",
        "team": "Offer: \"A few groups are affected. Want me to set up a map everyone can "
        "review, with notes from each point of view?\"",
    }
    nxt = {
        "none": [],
        "quick": ['decisioncraft quick --option "A" --option "B" --criterion "cost" --json'],
        "guided": ["decisioncraft interview --dir DECISION --json"],
        "team": ["decisioncraft interview --dir DECISION --kind team --json"],
    }
    return {
        "format": "decisioncraft-triage/1",
        "mode": mode,
        "is_choice": bool(answers) or looks_like_choice(text) if text else True,
        "label": MODES[mode]["label"],
        "does": MODES[mode]["does"],
        "why": why,
        "alternative": alternative,
        "stakes": {"cost": cost, "reversible": undo, "people": people, "deadline_days": days,
                   "score": score},
        "read_from_text": found,
        "missing": missing,
        "offer": offers[mode],
        "next": nxt[mode],
    }


# ------------------------------------------------------------------ quick comparison

WEIGHTS = {"must": 3, "important": 2, "nice": 1}


def _slug(text: str, used: set) -> str:
    base = "-".join(re.findall(r"[a-z0-9]+", text.lower())[:4]) or "item"
    key, n = base, 2
    while key in used:
        key, n = f"{base}-{n}", n + 1
    used.add(key)
    return key


def _norm_options(options) -> list[dict]:
    out, used = [], set()
    for o in options or []:
        if isinstance(o, str):
            o = {"title": o}
        if not isinstance(o, dict) or not str(o.get("title", "")).strip():
            raise ValueError("Each option needs a name.")
        out.append({"id": o.get("id") or _slug(o["title"], used), "title": o["title"].strip()})
    return out


def _norm_criteria(criteria) -> list[dict]:
    out, used = [], set()
    for i, c in enumerate(criteria or []):
        if isinstance(c, str):
            label, imp = c, None
            m = re.match(r"\s*(must|important|nice)\s*:\s*(.+)", c, re.I)
            if m:
                imp, label = m.group(1).lower(), m.group(2)
            c = {"label": label, "importance": imp}
        if not isinstance(c, dict) or not str(c.get("label", "")).strip():
            raise ValueError("Each thing that matters needs a name.")
        imp = c.get("importance")
        weight = c.get("weight")
        if weight is None:
            # Order is a signal: the first thing named matters most unless told otherwise.
            imp = imp or ("important" if i < 2 else "nice")
            weight = WEIGHTS.get(imp, 2)
        out.append({"id": c.get("id") or _slug(c["label"], used), "label": c["label"].strip(),
                    "importance": imp or ("must" if weight >= 3 else "important" if weight == 2 else "nice"),
                    "weight": int(weight)})
    return out


def _norm_scores(scores, options, criteria) -> dict:
    """{option id: {criterion id: {score 1-5, why}}}. Accepts names or ids."""
    oid = {o["id"]: o["id"] for o in options} | {o["title"].lower(): o["id"] for o in options}
    cid = {c["id"]: c["id"] for c in criteria} | {c["label"].lower(): c["id"] for c in criteria}
    out: dict = {o["id"]: {} for o in options}
    items = []
    if isinstance(scores, dict):
        for o, row in scores.items():
            for c, v in (row or {}).items():
                items.append({"option": o, "criterion": c, **(v if isinstance(v, dict) else {"score": v})})
    elif isinstance(scores, list):
        items = scores
    elif scores is not None:
        raise ValueError("Scores must be an object {option: {criterion: 1-5}} or a list.")
    for s in items:
        o = oid.get(str(s.get("option", "")).lower()) or oid.get(s.get("option"))
        c = cid.get(str(s.get("criterion", "")).lower()) or cid.get(s.get("criterion"))
        if o is None:
            valid = ", ".join(repr(x["title"]) for x in options) or "none yet"
            raise ValueError(f"Score for unknown option {s.get('option')!r}. Options are: {valid}.")
        if c is None:
            valid = ", ".join(repr(x["label"]) for x in criteria) or "none yet (add --criterion)"
            raise ValueError(f"Score for unknown criterion {s.get('criterion')!r}. Criteria are: {valid}.")
        v = s.get("score")
        if v is None:
            continue
        if not isinstance(v, (int, float)) or not 1 <= v <= 5:
            raise ValueError("Scores run from 1 (poor) to 5 (great).")
        out[o][c] = {"score": float(v), "why": str(s.get("why", ""))}
    return out


def _table(options, criteria, grid, ranked) -> str:
    head = "| Option | " + " | ".join(f"{c['label']} ({'must' if c['importance'] == 'must' else 'x' + str(c['weight'])})"
                                       for c in criteria) + " | Overall |"
    sep = "|" + "---|" * (len(criteria) + 2)
    rows = []
    for r in ranked:
        cells = []
        for c in criteria:
            s = grid[r["id"]].get(c["id"])
            cells.append("?" if s is None else f"{s['score']:g}")
        overall = f"{r['percent']}%" + (" (fails a must)" if r["fails_must"] else "")
        rows.append(f"| {r['title']} | " + " | ".join(cells) + f" | {overall} |")
    return "\n".join([head, sep, *rows])


def quick(options=None, criteria=None, scores=None, *, question: str = "", text: str = "",
          complete=None) -> dict:
    """Score a few options against what matters; return a table, a lean and the one check.

    Scores run 1 (poor) to 5 (great). Importance: must (weight 3; a score of 2 or less fails
    it), important (2), nice (1); order sets it when not given. Deterministic when options and
    scores are given. With only `text`, `complete` (a model) reads the options, what matters
    and rough scores out of it; without a model you get the empty table and what to ask.
    """
    if text and not options:
        if complete is None:
            raise ValueError("Give the options (and ideally what matters and scores), or a model "
                             "to read them from the text.")
        system = "You turn a person's message about a choice into a small comparison. Reply with JSON only."
        prompt = (
            f"Message: {text}\n\nReply with {{\"question\": one plain question, \"options\": [names], "
            "\"criteria\": [{\"label\": name, \"importance\": \"must|important|nice\"}], "
            "\"scores\": [{\"option\": name, \"criterion\": name, \"score\": 1-5, \"why\": short}]}. "
            "Include doing nothing if it is a real option. Score only what the message supports; "
            "leave out a score you would have to guess."
        )
        reply = complete(system, prompt)
        m = re.search(r"\{.*\}", reply, re.S)
        if not m:
            raise ValueError("The model's reply had no JSON in it.")
        value = json.loads(m.group(0))
        question = question or value.get("question", "")
        options, criteria, scores = value.get("options"), value.get("criteria"), value.get("scores")
    opts = _norm_options(options)
    crit = _norm_criteria(criteria)
    if len(opts) < 2:
        raise ValueError("A comparison needs at least two options (doing nothing can be one).")
    # Always check scores, so a score for something that isn't listed is an error, not silently dropped.
    grid = _norm_scores(scores, opts, crit) if (crit or scores) else {o["id"]: {} for o in opts}
    # Percent of what was scored for anyone: a criterion nobody has scored yet (say an
    # unchecked must-have) would only drag every option down by the same amount.
    scored = {cid for o in opts for cid in grid[o["id"]]}
    max_total = sum(c["weight"] * 5 for c in crit if c["id"] in scored) or 1
    ranked = []
    for o in opts:
        row = grid[o["id"]]
        known = [c for c in crit if c["id"] in row]
        unknown = [c["label"] for c in crit if c["id"] not in row]
        total = sum(row[c["id"]]["score"] * c["weight"] for c in known)
        fails = [c["label"] for c in crit if c["importance"] == "must" and c["id"] in row and row[c["id"]]["score"] <= 2]
        ranked.append({"id": o["id"], "title": o["title"], "total": total,
                       "percent": round(100 * total / max_total), "fails_must": fails, "unknown": unknown})
    ranked.sort(key=lambda r: (bool(r["fails_must"]), -r["total"]))
    asks = []
    if not crit:
        asks.append("What matters most when you choose? Name two to four things.")
    elif all(not grid[o["id"]] for o in opts):
        asks.append("How does each option do on each thing that matters? A rough 1 to 5 is fine.")
    lean = None
    check = None
    if crit and any(grid[o["id"]] for o in opts):
        top, second = ranked[0], ranked[1]
        close = abs(top["percent"] - second["percent"]) < 8
        reasons = [c["label"] for c in sorted(crit, key=lambda c: -c["weight"])
                   if grid[top["id"]].get(c["id"]) and grid[second["id"]].get(c["id"])
                   and grid[top["id"]][c["id"]]["score"] > grid[second["id"]][c["id"]]["score"]][:2]
        if top["fails_must"]:
            lean = {"option": None, "reason": "Every option fails a must-have. Look for another "
                    "option, or ask whether that must-have is truly a must.", "close_call": False}
        else:
            reason = (f"{top['title']} comes out ahead" + (f", mainly on {' and '.join(reasons)}" if reasons else "")
                      + ("; it is a close call" if close else "") + ".")
            lean = {"option": top["id"], "title": top["title"], "reason": reason, "close_call": close}
        # The one thing to check: an unknown on the two leaders first, else the weightiest
        # thing where the runner-up wins (it could flip the lean), else the weightiest thing.
        unknown = [(c, o) for c in sorted(crit, key=lambda c: -c["weight"]) for o in (top, second)
                   if c["label"] in o["unknown"]]
        # Only a criterion that could flip the lean: the runner-up wins it, and moving its
        # score by one point would close the gap. A nice-to-have rarely qualifies.
        gap = top["total"] - second["total"]
        flips = [c for c in sorted(crit, key=lambda c: -c["weight"])
                 if grid[second["id"]].get(c["id"]) and grid[top["id"]].get(c["id"])
                 and grid[second["id"]][c["id"]]["score"] > grid[top["id"]][c["id"]]["score"]
                 and c["weight"] * 2 >= gap and c["importance"] != "nice"]
        if unknown:
            c, o = unknown[0]
            if c["importance"] == "must":
                check = {"text": f"Check that {o['title']} meets the must-have: {c['label']}.",
                         "why": "If it fails a must-have it drops out, whatever its other scores."}
            else:
                check = {"text": f"Find out how {o['title']} does on {c['label']}.",
                         "why": "It is not scored yet and it matters to the result."}
        elif flips:
            c = flips[0]
            check = {"text": f"Check {c['label']} again for {top['title']} and {second['title']}.",
                     "why": f"{second['title']} wins on it; if the gap is bigger than you think, the lean flips."}
        else:
            c = max(crit, key=lambda c: c["weight"])
            check = {"text": f"Make sure your score for {top['title']} on {c['label']} rests on "
                     "something you have seen, not a guess.", "why": "It carries the most weight."}
    return {
        "format": "decisioncraft-quick/1",
        "question": question,
        "options": ranked,
        "criteria": crit,
        "scores": grid,
        "table": _table(opts, crit, grid, ranked) if crit else "",
        "lean": lean,
        "check_first": check,
        "ask": asks,
        "note": "A lean, not a verdict: scores are the person's own judgment.",
        "offer_next": "If it is bigger than it first looked, offer the Guided mode: "
        "decisioncraft interview --dir DECISION",
    }


def quick_model(result: dict) -> dict:
    """A small model that draws a `quick` result as a scoring table, for hosts that can show
    the canvas (MCP Apps). Must-haves stay must-haves (met when scored 3 or more); the rest are
    scored with the quick weights. Deterministic."""
    from .model import new_model

    question = result.get("question") or "Which option fits best?"
    model = new_model("scoring-table", "Quick comparison", question)
    model["options"] = [{"id": o["id"], "name": o["title"]} for o in result.get("options", [])]
    criteria, kinds = [], {}
    for c in result.get("criteria", []):
        kind = "must" if c.get("importance") == "must" else "scored"
        kinds[c["id"]] = kind
        entry = {"id": c["id"], "name": c["label"], "kind": kind}
        if kind == "scored":
            entry["weight"] = max(0.5, min(5.0, float(c.get("weight") or 1)))
        criteria.append(entry)
    model["criteria"] = criteria
    scores = []
    for option, per in (result.get("scores") or {}).items():
        for criterion, s in per.items():
            if criterion not in kinds or s.get("score") is None:
                continue
            row = {"option": option, "criterion": criterion, "note": s.get("why") or ""}
            if kinds[criterion] == "must":
                row["meets"] = float(s["score"]) >= 3
            else:
                row["value"] = max(1, min(5, round(float(s["score"]))))
            scores.append(row)
    model["scores"] = scores
    return model
