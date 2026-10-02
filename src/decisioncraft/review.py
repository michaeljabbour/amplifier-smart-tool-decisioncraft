"""Questions to decide, reviewers' answers, and what changed between two runs.

All deterministic. A review is the file a reviewer saves from the canvas
("Save my answers"); `merge` combines several into one agree/disagree view.
"""

from __future__ import annotations

import hashlib
import json

from .model import URGENCY, URGENCY_ORDER, iter_boxes, roles_of

REVIEW_FORMAT = "decisioncraft-review/1"
MERGED_FORMAT = "decisioncraft-merged/1"
CHOICES = ("agree", "change", "unsure")


def fingerprint(model: dict) -> str:
    """A short, stable hash of a model, so a review can say which version it answered."""
    raw = json.dumps(model, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()[:12]


def questions(model: dict, merged: dict | None = None) -> list[dict]:
    """Every question to decide, most urgent first.

    Order: urgency (must, should, info), then dots from reviewers, then the impact of
    the gap the note sits on. Each entry carries its role, where it sits and its evidence.
    """
    roles = {r["id"]: r["label"] for r in roles_of(model)}
    gaps = {g["id"]: g for g in model.get("gaps", [])}
    boxes = {b.get("id"): b for _, b in iter_boxes(model)}
    votes = (merged or {}).get("questions", {})
    out = []
    for n in model.get("notes", []):
        q = str(n.get("question", "")).strip()
        if not q:
            continue
        anchor = n.get("anchor")
        target = boxes.get(anchor) or gaps.get(anchor) or {}
        impact = gaps.get(anchor, {}).get("impact") or 0
        v = votes.get(n["id"], {})
        out.append(
            {
                "id": n["id"],
                "question": q,
                "answer_type": n.get("answer_type", "text"),
                "role": n.get("role"),
                "role_label": roles.get(n.get("role"), n.get("role")),
                "urgency": n.get("urgency", "info"),
                "urgency_label": URGENCY[n.get("urgency", "info")],
                "where": target.get("title")
                or target.get("label")
                or target.get("text")
                or anchor,
                "anchor": anchor,
                "evidence": list(n.get("evidence", [])),
                "dots": v.get("dots", 0),
                "impact": impact,
                "agree": v.get("agree", 0),
                "change": v.get("change", 0),
                "unsure": v.get("unsure", 0),
                "answers": list(v.get("answers", [])),
            }
        )
    for n in note_threads(merged):
        target = _note_target(model, n.get("anchor"))
        for r in n.get("replies", []):
            q = str(r.get("question", "")).strip()
            if not q:
                continue
            v = votes.get(r["id"], {})
            out.append({
                "id": r["id"], "question": q, "answer_type": "text", "role": r.get("role"),
                "role_label": roles.get(r.get("role"), r.get("role")),
                "urgency": r.get("urgency", "info"), "urgency_label": URGENCY[r.get("urgency", "info")],
                "where": target["title"], "anchor": n.get("anchor"), "evidence": [],
                "dots": v.get("dots", 0), "impact": 0, "agree": v.get("agree", 0),
                "change": v.get("change", 0), "unsure": v.get("unsure", 0), "answers": list(v.get("answers", [])),
                "from_note": n.get("id"), "note_text": n.get("text", ""), "note_by": n.get("who") or n.get("author", ""),
            })
    out.sort(
        key=lambda q: (URGENCY_ORDER[q["urgency"]], -q["dots"], -q["impact"], q["id"])
    )
    return out


def _note_target(model: dict, anchor) -> dict:
    """What a reviewer's note sits on: a box, a gap, a gap's story ("G1#story-0"), or the map."""
    if not anchor:
        return {"kind": "map", "title": "The whole map", "text": ""}
    boxes = {b.get("id"): b for _, b in iter_boxes(model)}
    gaps = {g.get("id"): g for g in model.get("gaps", [])}
    if "#story-" in str(anchor):
        gid, _, k = str(anchor).partition("#story-")
        stories = (gaps.get(gid) or {}).get("stories", [])
        if k.isdigit() and int(k) < len(stories):
            return {"kind": "story", "title": stories[int(k)].get("as", ""), "text": "; ".join(stories[int(k)].get("done_when", []))}
    target = boxes.get(anchor) or gaps.get(anchor)
    if target is None:
        return {"kind": "unknown", "title": str(anchor), "text": ""}
    return {"kind": "gap" if anchor in gaps else "box",
            "title": target.get("title") or target.get("name") or target.get("label") or target.get("text") or str(anchor),
            "text": target.get("text", "") if target.get("title") else target.get("summary", "") or target.get("why", "")}


def note_threads(merged_or_review: dict | None) -> list[dict]:
    """Reviewer notes with their expert replies, from one review or a merged set."""
    notes = (merged_or_review or {}).get("notes") or []
    return [n for n in notes if isinstance(n, dict)]


def notes_to_ask(model: dict, review: dict, roles: list[str] | None = None) -> list[dict]:
    """Deterministic: which reviewer notes would be sent to the experts, and to whom.

    A note is asked when it carries an `ask` and some of its roles have not replied yet.
    If no note carries an `ask`, every note without replies is asked. `roles` replaces the
    roles each note asked for. Returns [{note, target, roles}] in the review's order.
    """
    known = [r["id"] for r in roles_of(model)]
    notes = note_threads(review)
    any_ask = any(n.get("ask") for n in notes)
    plan = []
    for n in notes:
        if any_ask and not n.get("ask"):
            continue
        wanted = roles or (n.get("ask") or {}).get("roles") or known
        wanted = [r for r in wanted if r in known]
        done = {r.get("role") for r in n.get("replies", []) if isinstance(r, dict)}
        todo = [r for r in wanted if r not in done]
        if not todo or (not any_ask and done):
            continue
        plan.append({"note": n, "target": _note_target(model, n.get("anchor")), "roles": todo})
    return plan


def blank_review(model: dict, reviewer: str = "") -> dict:
    """An empty review for one model, in the same shape the canvas saves."""
    return {
        "format": REVIEW_FORMAT,
        "model": model.get("title", ""),
        "model_fingerprint": fingerprint(model),
        "reviewer": reviewer,
        "saved_at": "",
        "answers": {},
        "dots": {},
        "decisions": {},
    }


def check_review(review: dict) -> list[str]:
    """Problems with a review file; empty when it is usable.

    Tolerant of a file that is not a review at all: a wrong type in place of
    `answers` or `dots` (for example, a model file passed in by mistake) is treated as
    empty rather than raised, so the real problem -- the wrong format -- is reported.
    """
    if not isinstance(review, dict):
        return [f'Not a review file (expected format "{REVIEW_FORMAT}").']
    problems = []
    if review.get("format") != REVIEW_FORMAT:
        problems.append(f'Not a review file (expected format "{REVIEW_FORMAT}").')
    for field in ("model", "model_fingerprint", "reviewer", "saved_at"):
        if field in review and not isinstance(review[field], str):
            problems.append(f"{field} must be text.")
    answers = review.get("answers")
    if answers is not None and not isinstance(answers, dict):
        problems.append("Answers must be an object keyed by question id.")
    for qid, a in (answers if isinstance(answers, dict) else {}).items():
        if not isinstance(a, dict):
            problems.append(f"Answer to {qid} must be an object.")
            continue
        for field in ("answer", "comment", "choice"):
            if field in a and not isinstance(a[field], str):
                problems.append(f"{field.capitalize()} for {qid} must be text.")
        if isinstance(a, dict) and a.get("choice") and a["choice"] not in CHOICES:
            problems.append(f"Answer to {qid} must be one of {', '.join(CHOICES)}.")
    dots = review.get("dots")
    if dots is not None and not isinstance(dots, dict):
        problems.append("Dots must be an object keyed by question id.")
    for k, v in (dots if isinstance(dots, dict) else {}).items():
        if type(v) is not int or v < 0:
            problems.append(f"Dots on {k} must be a whole number, 0 or more.")
    weights = review.get("weights")
    if weights is not None and not isinstance(weights, dict):
        problems.append("Weights must be an object keyed by criterion id.")
    for k, v in (weights if isinstance(weights, dict) else {}).items():
        if isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= v <= 5:
            problems.append(f"Weight for {k} must be a number from 0 to 5.")
    whatifs = review.get("whatifs")
    if whatifs is not None and (not isinstance(whatifs, list) or any(not isinstance(x, str) for x in whatifs)):
        problems.append("What-ifs must be a list of what-if ids.")
    decisions = review.get("decisions")
    if decisions is not None and not isinstance(decisions, dict):
        problems.append("Decisions must be an object keyed by decision id.")
    for did, fields in (decisions if isinstance(decisions, dict) else {}).items():
        if not isinstance(fields, dict):
            problems.append(f"Decision {did} must be an object.")
        elif any(not isinstance(value, str) for value in fields.values()):
            problems.append(f"Fields for decision {did} must be text.")
    notes = review.get("notes")
    if notes is not None and not isinstance(notes, list):
        problems.append("Notes must be a list.")
    seen = set()
    for i, n in enumerate(notes if isinstance(notes, list) else []):
        where = f"Note {i + 1}"
        if not isinstance(n, dict):
            problems.append(f"{where} must be an object.")
            continue
        if not isinstance(n.get("id"), str) or not n["id"]:
            problems.append(f"{where} needs an id.")
        elif n["id"] in seen:
            problems.append(f"{where} repeats id {n['id']}.")
        seen.add(n.get("id"))
        if not isinstance(n.get("text", ""), str) or not str(n.get("text", "")).strip():
            problems.append(f"{where} needs some text.")
        for field in ("anchor", "author", "at", "map"):
            if n.get(field) is not None and not isinstance(n[field], str):
                problems.append(f"{where}: {field} must be text.")
        ask = n.get("ask")
        if ask is not None and (not isinstance(ask, dict) or not isinstance(ask.get("roles", []), list)):
            problems.append(f"{where}: ask must be {{roles: [...]}}.")
        replies = n.get("replies", [])
        if not isinstance(replies, list):
            problems.append(f"{where}: replies must be a list.")
            continue
        for j, r in enumerate(replies):
            if not isinstance(r, dict) or not all(isinstance(r.get(k), str) and r.get(k) for k in ("id", "role", "view")):
                problems.append(f"{where}, reply {j + 1}: needs an id, a role and a view.")
            elif r.get("urgency", "info") not in URGENCY:
                problems.append(f"{where}, reply {j + 1}: urgency must be must, should or info.")
            else:
                if r["id"] in seen:
                    problems.append(f"{where}, reply {j + 1} repeats id {r['id']}.")
                seen.add(r["id"])
    return problems


def merge(reviews: list[dict], model: dict | None = None) -> dict:
    """Combine several reviews into one view of where people agree and disagree.

    For each question: how many agree, want a change or are unsure, every comment with
    who wrote it, written answers, total dots, and `split` for differing views. For each
    decision: the fields reviewers filled in, and `conflict` where they differ.
    Reviews for a different model version are kept but flagged in `stale_reviews`.
    """
    for i, r in enumerate(reviews):
        problems = check_review(r)
        if problems:
            raise ValueError(f"Review {i + 1}: " + " ".join(problems))
    fp = fingerprint(model) if model else None
    merged = {
        "format": MERGED_FORMAT,
        "reviewers": [],
        "stale_reviews": [],
        "questions": {},
        "decisions": {},
        "notes": [],
        "weights": {},
    }
    for i, r in enumerate(reviews):
        who = (r.get("reviewer") or "").strip() or f"Reviewer {i + 1}"
        merged["reviewers"].append(who)
        if fp and r.get("model_fingerprint") not in (None, "", fp):
            merged["stale_reviews"].append(who)
        for qid, a in (r.get("answers") or {}).items():
            q = merged["questions"].setdefault(
                qid, {"agree": 0, "change": 0, "unsure": 0, "dots": 0, "comments": [], "answers": []}
            )
            if a.get("answer", "").strip():
                q["answers"].append({"who": who, "text": a["answer"].strip()})
            if a.get("choice") in CHOICES:
                q[a["choice"]] += 1
            if str(a.get("comment", "")).strip():
                q["comments"].append(
                    {
                        "who": who,
                        "text": a["comment"].strip(),
                        "choice": a.get("choice", ""),
                    }
                )
        for qid, d in (r.get("dots") or {}).items():
            q = merged["questions"].setdefault(
                qid, {"agree": 0, "change": 0, "unsure": 0, "dots": 0, "comments": [], "answers": []}
            )
            q["dots"] += d
        for n in note_threads(r):
            merged["notes"].append({**n, "who": who})
        for cid, wt in (r.get("weights") or {}).items():
            merged["weights"].setdefault(cid, []).append({"who": who, "weight": wt})
        for did, fields in (r.get("decisions") or {}).items():
            d = merged["decisions"].setdefault(did, {})
            for k, v in fields.items():
                if str(v).strip():
                    d.setdefault(k, []).append({"who": who, "value": v})
    for q in merged["questions"].values():
        q["split"] = sum(1 for c in CHOICES if q[c]) > 1
    # Weights people disagree on by a point or more (on the 0-5 scale), widest first.
    merged["weight_split"] = sorted(
        (cid for cid, vals in merged["weights"].items()
         if len(vals) > 1 and max(v["weight"] for v in vals) - min(v["weight"] for v in vals) >= 1),
        key=lambda cid: -(max(v["weight"] for v in merged["weights"][cid]) - min(v["weight"] for v in merged["weights"][cid])),
    )
    if not merged["weights"]:
        del merged["weights"], merged["weight_split"]
    for did, d in merged["decisions"].items():
        d["conflict"] = sorted(
            k
            for k, vals in d.items()
            if isinstance(vals, list) and len({str(v["value"]) for v in vals}) > 1
        )
    return merged


def _index(model: dict) -> dict[str, dict]:
    out = {}

    def walk(value, kind):
        if isinstance(value, dict):
            if isinstance(value.get("id"), str):
                out[value["id"]] = {"kind": kind, "value": value}
            for k, v in value.items():
                walk(v, k)
        elif isinstance(value, list):
            for v in value:
                walk(v, kind)

    walk(model, "model")
    return out


def _shallow(value: dict) -> dict:
    return {
        k: v
        for k, v in value.items()
        if not (
            isinstance(v, list)
            and v
            and all(isinstance(x, dict) and "id" in x for x in v)
        )
        and k not in {"children"}
    }


def diff(old: dict, new: dict) -> dict:
    """What changed between two runs of the same model, by id.

    Returns added, removed and changed items (with the fields that changed). The canvas
    marks changed and new boxes when rendered with `since`.
    """
    a, b = _index(old), _index(new)
    added = [{"id": i, "kind": b[i]["kind"]} for i in b if i not in a]
    removed = [{"id": i, "kind": a[i]["kind"]} for i in a if i not in b]
    changed = []
    for i in b:
        if i in a:
            x, y = _shallow(a[i]["value"]), _shallow(b[i]["value"])
            fields = sorted(k for k in set(x) | set(y) if x.get(k) != y.get(k))
            if fields:
                changed.append({"id": i, "kind": b[i]["kind"], "fields": fields})
    return {
        "added": added,
        "removed": removed,
        "changed": changed,
        "summary": f"{len(added)} new, {len(changed)} changed, {len(removed)} removed",
    }
