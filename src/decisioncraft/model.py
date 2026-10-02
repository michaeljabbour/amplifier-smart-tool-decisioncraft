"""The decision model: templates, default roles, and validation.

A model is plain JSON. Everything here is deterministic and needs no credentials.
"""

from __future__ import annotations

import copy
import re

FORMAT = "decisioncraft/1"

STATUSES = {
    "works": "Works today",
    "partial": "Partly there",
    "missing": "Missing",
    "planned": "Planned",
}
URGENCY = {"must": "Must decide", "should": "Should decide", "info": "For information"}
URGENCY_ORDER = {"must": 0, "should": 1, "info": 2}
DECISION_STATUS = {"open": "Open", "decided": "Decided", "deferred": "Deferred"}
FEELINGS = {"good": "Good", "ok": "Mixed", "bad": "Bad"}
EVIDENCE_KINDS = {"quote", "data", "file", "observation"}
SOURCE_KINDS = {
    "interview",
    "document",
    "data",
    "code",
    "meeting",
    "observation",
    "survey",
    "other",
}

DEFAULT_ROLES = [
    {
        "id": "designer",
        "label": "Designer",
        "color": "#e86a92",
        "asks": "Will people understand this and find their way without help?",
    },
    {
        "id": "analyst",
        "label": "Analyst",
        "color": "#4f7fd8",
        "asks": "Is it clear what must be true, for whom, and how we will measure it?",
    },
    {
        "id": "engineer",
        "label": "Engineer",
        "color": "#2f9e6a",
        "asks": "What do we build first, what could break, and how do we test it?",
    },
    {
        "id": "owner",
        "label": "Product owner",
        "color": "#8a5cd6",
        "asks": "What is in the first version, what do we cut, and what does success look like?",
    },
    {
        "id": "security",
        "label": "Security and privacy",
        "color": "#d1543f",
        "asks": "Who can see what, what do we keep, and what happens if it leaks?",
    },
    {
        "id": "voice",
        "label": "Customer voice",
        "color": "#d99a1e",
        "asks": "Would the people we serve choose this, and would they need a manual?",
    },
    {
        "id": "agent",
        "label": "AI agent teammate",
        "color": "#1f9aa6",
        "asks": "What can an agent do on its own, and what needs a person's OK?",
    },
    {
        "id": "finance",
        "label": "Finance",
        "color": "#7a7a72",
        "asks": "What does it cost to build and run, and when does it pay back?",
    },
]

TEMPLATES = {
    "system-journeys": {
        "kind": "journeys",
        "title": "How it works",
        "about": "Each journey is a numbered path of steps. Each column is the part of the "
        "system or organisation that does that step.",
        "lanes": [
            {"id": "people", "label": "People", "sub": "Who starts it"},
            {"id": "front", "label": "Front door", "sub": "What they see and touch"},
            {"id": "core", "label": "Core", "sub": "Rules and decisions"},
            {"id": "records", "label": "Records", "sub": "What gets stored"},
            {"id": "background", "label": "Background", "sub": "Work that runs later"},
            {"id": "outside", "label": "Outside", "sub": "Partners and services"},
        ],
    },
    "customer-journey": {
        "kind": "journeys",
        "title": "Their journey",
        "about": "Each column is a phase of the journey. Each step shows what the person does, "
        "how it feels, and the moments that matter most.",
        "lanes": [
            {"id": "notice", "label": "Notice", "sub": "They find out"},
            {"id": "start", "label": "Start", "sub": "First try"},
            {"id": "use", "label": "Use", "sub": "Day to day"},
            {"id": "help", "label": "Get help", "sub": "When stuck"},
            {"id": "stay", "label": "Stay or leave", "sub": "What happens next"},
        ],
    },
    "service-blueprint": {
        "kind": "journeys",
        "title": "Service blueprint",
        "about": "What the person does on top, what staff do in front of them, what happens "
        "out of sight, and what supports it all.",
        "lanes": [
            {"id": "person", "label": "Person", "sub": "What they do"},
            {
                "id": "front",
                "label": "In front of them",
                "sub": "Staff and screens they meet",
            },
            {"id": "back", "label": "Out of sight", "sub": "Staff work they never see"},
            {"id": "support", "label": "Support", "sub": "Systems, suppliers, rules"},
            {
                "id": "proof",
                "label": "What they keep",
                "sub": "Receipts, letters, records",
            },
        ],
    },
    "decision-chain": {
        "kind": "chain",
        "title": "From signal to outcome",
        "about": "Each stage is one step from what we heard to what we shipped and whether it "
        "worked. Today shows what exists; Planned shows what we propose.",
        "stages": [
            {
                "id": "source",
                "label": "Source",
                "verb": "backs up",
                "sub": "Where it was said, shown or measured",
            },
            {
                "id": "evidence",
                "label": "Evidence",
                "verb": "informs",
                "sub": "The exact words or numbers we rely on",
            },
            {
                "id": "decision",
                "label": "Decision",
                "verb": "shapes",
                "sub": "What we chose, and why",
            },
            {
                "id": "intent",
                "label": "Intent",
                "verb": "spells out",
                "sub": "The result we want, in plain words",
            },
            {
                "id": "spec",
                "label": "Spec",
                "verb": "plans",
                "sub": "What it must do, and how we will know",
            },
            {
                "id": "plan",
                "label": "Plan",
                "verb": "produces",
                "sub": "Pieces of work, in order",
            },
            {
                "id": "work",
                "label": "Work",
                "verb": "creates",
                "sub": "What was actually built or changed",
            },
            {
                "id": "outcome",
                "label": "Outcome",
                "verb": "",
                "sub": "Did it work? Measured, not guessed",
            },
        ],
    },
    "opportunity-tree": {
        "kind": "tree",
        "title": "Opportunities",
        "about": "The outcome we want at the top, then the needs and pains that could move it, "
        "then ideas for each, then the quick tests that would prove an idea.",
        "levels": ["Outcome", "Need or pain", "Idea", "Quick test"],
    },
}

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

PLAIN_WORDS = [
    "leverage",
    "seamless",
    "robust",
    "unlock",
    "empower",
    "synergy",
    "cutting-edge",
    "game-changer",
    "game changer",
    "delve",
    "best-in-class",
    "paradigm",
    "holistic",
]


class ModelError(ValueError):
    """A model that cannot be used. `problems` lists every reason."""

    def __init__(self, problems):
        self.problems = problems
        super().__init__("; ".join(p["message"] for p in problems[:5]))


def templates() -> list[dict]:
    """Every template: id, the kind of map it draws, its title and what it is for."""
    return [
        {"id": k, "kind": v["kind"], "title": v["title"], "about": v["about"]}
        for k, v in TEMPLATES.items()
    ]


def default_roles() -> list[dict]:
    """The roles used when a model names none."""
    return copy.deepcopy(DEFAULT_ROLES)


def new_model(template: str, title: str, question: str, *, date: str = "") -> dict:
    """An empty model for one template, ready to fill in by hand or by `draft`."""
    if template not in TEMPLATES:
        raise ModelError(
            [
                {
                    "path": "template",
                    "message": f"Unknown template: {template}. "
                    f"Choose one of {', '.join(TEMPLATES)}.",
                }
            ]
        )
    t = TEMPLATES[template]
    m = {"id": "m1", "template": template, "title": t["title"], "intro": t["about"]}
    if t["kind"] == "journeys":
        m["lanes"] = copy.deepcopy(t["lanes"])
        m["journeys"] = []
    elif t["kind"] == "chain":
        m["stages"] = [dict(s, items=[]) for s in copy.deepcopy(t["stages"])]
    else:
        m["levels"] = list(t["levels"])
        m["root"] = {
            "id": "root",
            "title": question or title,
            "text": "",
            "children": [],
        }
    return {
        "format": FORMAT,
        "title": title,
        "question": question,
        "summary": "",
        "checked": {"date": date, "note": ""},
        "roles": default_roles(),
        "glossary": {},
        "sources": [],
        "evidence": [],
        "maps": [m],
        "gaps": [],
        "notes": [],
        "decisions": [],
        "outcomes": [],
    }


def roles_of(model: dict) -> list[dict]:
    roles = model.get("roles")
    return roles if isinstance(roles, list) and roles else default_roles()


def iter_boxes(model: dict):
    """Yield (map, box) for every box a note can point at: steps, items, tree nodes.

    Tolerates a malformed model (wrong types in place of lists or objects) by skipping
    what it cannot read, rather than raising. `validate` is what reports those problems.
    """
    maps = model.get("maps")
    if not isinstance(maps, list):
        return
    for m in maps:
        if not isinstance(m, dict):
            continue
        journeys = m.get("journeys")
        for j in journeys if isinstance(journeys, list) else []:
            if not isinstance(j, dict):
                continue
            yield m, j
            steps = j.get("steps")
            for s in steps if isinstance(steps, list) else []:
                if isinstance(s, dict):
                    yield m, s
        stages = m.get("stages")
        for st in stages if isinstance(stages, list) else []:
            if not isinstance(st, dict):
                continue
            yield m, st
            items = st.get("items")
            for it in items if isinstance(items, list) else []:
                if isinstance(it, dict):
                    yield m, it
        root = m.get("root")
        stack = [root] if isinstance(root, dict) else []
        while stack:
            n = stack.pop()
            yield m, n
            children = n.get("children")
            if isinstance(children, list):
                stack.extend(c for c in children if isinstance(c, dict))


def _as_list(value) -> list:
    """`value` if it is a list, else an empty list.

    Keeps `validate` from crashing when a field holds the wrong JSON type; the wrong
    type is reported as its own error instead.
    """
    return value if isinstance(value, list) else []


def validate(model: dict) -> list[dict]:
    """Check a model. Returns problems: {level: error|warning, path, message}.

    Errors make a model unusable; warnings are worth fixing (plain words, missing evidence).
    Never raises on a malformed model -- a wrong type in place of a list or object is
    reported as an error at that path instead.
    """
    out: list[dict] = []

    def err(path, msg):
        out.append({"level": "error", "path": path, "message": msg})

    def warn(path, msg):
        out.append({"level": "warning", "path": path, "message": msg})

    if not isinstance(model, dict):
        return [
            {
                "level": "error",
                "path": "",
                "message": "The model must be a JSON object.",
            }
        ]
    if model.get("format") != FORMAT:
        err("format", f'Expected format "{FORMAT}".')
    for key in ("title", "question"):
        if not str(model.get(key, "")).strip():
            err(key, f"Give the model a {key}.")
    raw_maps = model.get("maps")
    if not isinstance(raw_maps, list) or not raw_maps:
        err("maps", "Add at least one map.")
        raw_maps = []
    maps = []
    for mi, m in enumerate(raw_maps):
        if not isinstance(m, dict):
            err(f"maps[{mi}]", "Each map must be a JSON object.")
            continue
        maps.append(m)

    seen: dict[str, str] = {}

    def claim(i, path):
        if not isinstance(i, str) or not ID_RE.match(i):
            err(
                path,
                f"Bad id {i!r}: use letters, numbers, dots, dashes or underscores.",
            )
            return
        if i in seen:
            err(path, f"Id {i!r} is used twice (also at {seen[i]}).")
        else:
            seen[i] = path

    raw_roles = model.get("roles")
    if raw_roles is not None and not isinstance(raw_roles, list):
        err("roles", "Roles must be a list.")
    role_ids = {r.get("id") for r in roles_of(model) if isinstance(r, dict)}
    for i, r in enumerate(_as_list(raw_roles)):
        if not isinstance(r, dict):
            err(f"roles[{i}]", "Each role must be a JSON object.")
            continue
        if not r.get("id") or not r.get("label"):
            err(f"roles[{i}]", "Each role needs an id and a label.")

    raw_sources = model.get("sources")
    if raw_sources is not None and not isinstance(raw_sources, list):
        err("sources", "Sources must be a list.")
    sources = []
    for i, s in enumerate(_as_list(raw_sources)):
        if not isinstance(s, dict):
            err(f"sources[{i}]", "Each source must be a JSON object.")
            continue
        sources.append(s)
        claim(s.get("id"), f"sources[{i}]")
        if s.get("kind") and s["kind"] not in SOURCE_KINDS:
            warn(f"sources[{i}].kind", f"Unusual source kind {s['kind']!r}.")
    source_ids = {s.get("id") for s in sources}

    raw_evidence = model.get("evidence")
    if raw_evidence is not None and not isinstance(raw_evidence, list):
        err("evidence", "Evidence must be a list.")
    evidence = []
    for i, e in enumerate(_as_list(raw_evidence)):
        if not isinstance(e, dict):
            err(f"evidence[{i}]", "Each evidence item must be a JSON object.")
            continue
        evidence.append(e)
        claim(e.get("id"), f"evidence[{i}]")
        if e.get("source") not in source_ids:
            err(
                f"evidence[{i}].source",
                f"Evidence {e.get('id')} points at unknown source {e.get('source')!r}.",
            )
        if e.get("kind") and e["kind"] not in EVIDENCE_KINDS:
            err(
                f"evidence[{i}].kind",
                f"Evidence kind must be one of {sorted(EVIDENCE_KINDS)}.",
            )
        if not str(e.get("text", "")).strip():
            err(f"evidence[{i}].text", "Evidence needs the exact words or numbers.")
    evidence_ids = {e.get("id") for e in evidence}

    def check_evidence(refs, path):
        for r in _as_list(refs):
            if r not in evidence_ids:
                err(path, f"Unknown evidence {r!r}.")

    def check_status(box, path):
        if box.get("status") and box["status"] not in STATUSES:
            err(path, f"Status must be one of {sorted(STATUSES)}.")

    for mi, m in enumerate(maps):
        mp = f"maps[{mi}]"
        claim(m.get("id"), mp)
        t = TEMPLATES.get(m.get("template"))
        if not t:
            err(f"{mp}.template", f"Unknown template {m.get('template')!r}.")
            continue
        if t["kind"] == "journeys":
            lanes = _as_list(m.get("lanes"))
            lane_ids = {ln.get("id") for ln in lanes if isinstance(ln, dict)}
            if not lanes:
                err(f"{mp}.lanes", "A journey map needs lanes.")
            for ji, j in enumerate(_as_list(m.get("journeys"))):
                jp = f"{mp}.journeys[{ji}]"
                if not isinstance(j, dict):
                    err(jp, "Each journey must be a JSON object.")
                    continue
                claim(j.get("id"), jp)
                steps = _as_list(j.get("steps"))
                if not steps:
                    warn(jp, f"Journey {j.get('id')} has no steps.")
                for si, s in enumerate(steps):
                    sp = f"{jp}.steps[{si}]"
                    if not isinstance(s, dict):
                        err(sp, "Each step must be a JSON object.")
                        continue
                    claim(s.get("id"), sp)
                    if s.get("lane") not in lane_ids:
                        err(
                            f"{sp}.lane",
                            f"Step {s.get('id')} uses unknown lane {s.get('lane')!r}.",
                        )
                    if s.get("feeling") and s["feeling"] not in FEELINGS:
                        err(
                            f"{sp}.feeling",
                            f"Feeling must be one of {sorted(FEELINGS)}.",
                        )
                    check_status(s, f"{sp}.status")
                    check_evidence(s.get("evidence"), f"{sp}.evidence")
        elif t["kind"] == "chain":
            stages = _as_list(m.get("stages"))
            if not stages:
                err(f"{mp}.stages", "A chain map needs stages.")
            for gi, st in enumerate(stages):
                gp = f"{mp}.stages[{gi}]"
                if not isinstance(st, dict):
                    err(gp, "Each stage must be a JSON object.")
                    continue
                claim(st.get("id"), gp)
                for ii, it in enumerate(_as_list(st.get("items"))):
                    ip = f"{gp}.items[{ii}]"
                    if not isinstance(it, dict):
                        err(ip, "Each item must be a JSON object.")
                        continue
                    claim(it.get("id"), ip)
                    check_status(it, f"{ip}.status")
                    if it.get("when", "both") not in {"today", "planned", "both"}:
                        err(f"{ip}.when", "When must be today, planned or both.")
                    check_evidence(it.get("evidence"), f"{ip}.evidence")
        else:
            root = m.get("root")
            if not isinstance(root, dict):
                err(f"{mp}.root", "A tree map needs a root.")
            else:
                stack = [(root, f"{mp}.root")]
                while stack:
                    n, np_ = stack.pop()
                    if not isinstance(n, dict):
                        err(np_, "Each node must be a JSON object.")
                        continue
                    claim(n.get("id"), np_)
                    check_status(n, f"{np_}.status")
                    check_evidence(n.get("evidence"), f"{np_}.evidence")
                    for ci, c in enumerate(_as_list(n.get("children"))):
                        stack.append((c, f"{np_}.children[{ci}]"))

    box_ids = {b.get("id") for _, b in iter_boxes(model)}
    raw_gaps = model.get("gaps")
    if raw_gaps is not None and not isinstance(raw_gaps, list):
        err("gaps", "Gaps must be a list.")
    gaps = []
    for gi, g in enumerate(_as_list(raw_gaps)):
        gp = f"gaps[{gi}]"
        if not isinstance(g, dict):
            err(gp, "Each gap must be a JSON object.")
            continue
        gaps.append(g)
        claim(g.get("id"), gp)
        for a in _as_list(g.get("anchors")):
            if a not in box_ids:
                err(f"{gp}.anchors", f"Gap {g.get('id')} points at unknown box {a!r}.")
        for k in ("impact", "effort"):
            v = g.get(k)
            if v is not None and (not isinstance(v, int) or not 1 <= v <= 5):
                err(f"{gp}.{k}", f"{k.title()} is a whole number from 1 to 5.")
        for si, s in enumerate(_as_list(g.get("stories"))):
            if isinstance(s, dict) and not s.get("done_when"):
                warn(f"{gp}.stories[{si}]", "Say how we will know it is done.")
    gap_ids = {g.get("id") for g in gaps}
    anchors = box_ids | gap_ids
    raw_notes = model.get("notes")
    if raw_notes is not None and not isinstance(raw_notes, list):
        err("notes", "Notes must be a list.")
    notes = []
    for ni, n in enumerate(_as_list(raw_notes)):
        np_ = f"notes[{ni}]"
        if not isinstance(n, dict):
            err(np_, "Each note must be a JSON object.")
            continue
        notes.append(n)
        claim(n.get("id"), np_)
        if n.get("role") not in role_ids:
            err(
                f"{np_}.role",
                f"Note {n.get('id')} uses unknown role {n.get('role')!r}.",
            )
        if n.get("anchor") not in anchors:
            err(
                f"{np_}.anchor",
                f"Note {n.get('id')} points at unknown box {n.get('anchor')!r}.",
            )
        if n.get("urgency", "info") not in URGENCY:
            err(f"{np_}.urgency", f"Urgency must be one of {sorted(URGENCY)}.")
        if not str(n.get("question", "")).strip():
            warn(f"{np_}.question", f"Note {n.get('id')} should end in a question.")
        if not n.get("evidence"):
            warn(f"{np_}.evidence", f"Note {n.get('id')} cites no evidence.")
        check_evidence(n.get("evidence"), f"{np_}.evidence")
    note_ids = {n.get("id") for n in notes}
    raw_decisions = model.get("decisions")
    if raw_decisions is not None and not isinstance(raw_decisions, list):
        err("decisions", "Decisions must be a list.")
    for di, d in enumerate(_as_list(raw_decisions)):
        dp = f"decisions[{di}]"
        if not isinstance(d, dict):
            err(dp, "Each decision must be a JSON object.")
            continue
        claim(d.get("id"), dp)
        if d.get("status", "open") not in DECISION_STATUS:
            err(f"{dp}.status", f"Status must be one of {sorted(DECISION_STATUS)}.")
        for r in _as_list(d.get("notes")):
            if r not in note_ids:
                err(
                    f"{dp}.notes",
                    f"Decision {d.get('id')} points at unknown note {r!r}.",
                )
        if d.get("status") == "decided" and not d.get("decided_by"):
            warn(
                f"{dp}.decided_by",
                f"Decision {d.get('id')} is decided but nobody is named.",
            )
    raw_outcomes = model.get("outcomes")
    if raw_outcomes is not None and not isinstance(raw_outcomes, list):
        err("outcomes", "Outcomes must be a list.")
    for oi, o in enumerate(_as_list(raw_outcomes)):
        op = f"outcomes[{oi}]"
        if not isinstance(o, dict):
            err(op, "Each outcome must be a JSON object.")
            continue
        claim(o.get("id"), op)
        if o.get("becomes_evidence") and o["becomes_evidence"] not in evidence_ids:
            err(
                f"{op}.becomes_evidence", f"Unknown evidence {o['becomes_evidence']!r}."
            )

    for path, text in _texts(model):
        low = text.lower()
        for w in PLAIN_WORDS:
            if re.search(r"\b" + re.escape(w) + r"\b", low):
                warn(path, f"Use plainer words than {w!r}.")
    return out


def _texts(value, path=""):
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for k, v in value.items():
            if k not in {"id", "color", "template", "lane", "role", "anchor", "source"}:
                yield from _texts(v, f"{path}.{k}" if path else k)
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from _texts(v, f"{path}[{i}]")


def require_valid(model: dict) -> dict:
    """Raise ModelError when a model has errors; return it unchanged otherwise."""
    errors = [p for p in validate(model) if p["level"] == "error"]
    if errors:
        raise ModelError(errors)
    return model
