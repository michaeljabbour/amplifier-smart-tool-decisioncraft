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
            }
        )
    out.sort(
        key=lambda q: (URGENCY_ORDER[q["urgency"]], -q["dots"], -q["impact"], q["id"])
    )
    return out


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
    answers = review.get("answers")
    for qid, a in (answers if isinstance(answers, dict) else {}).items():
        if isinstance(a, dict) and a.get("choice") and a["choice"] not in CHOICES:
            problems.append(f"Answer to {qid} must be one of {', '.join(CHOICES)}.")
    dots = review.get("dots")
    for k, v in (dots if isinstance(dots, dict) else {}).items():
        if not isinstance(v, int) or v < 0:
            problems.append(f"Dots on {k} must be a whole number, 0 or more.")
    return problems


def merge(reviews: list[dict], model: dict | None = None) -> dict:
    """Combine several reviews into one view of where people agree and disagree.

    For each question: how many agree, want a change or are unsure, every comment with
    who wrote it, total dots, and `split` when people answered differently. For each
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
    }
    for i, r in enumerate(reviews):
        who = (r.get("reviewer") or "").strip() or f"Reviewer {i + 1}"
        merged["reviewers"].append(who)
        if fp and r.get("model_fingerprint") not in (None, "", fp):
            merged["stale_reviews"].append(who)
        for qid, a in (r.get("answers") or {}).items():
            q = merged["questions"].setdefault(
                qid, {"agree": 0, "change": 0, "unsure": 0, "dots": 0, "comments": []}
            )
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
                qid, {"agree": 0, "change": 0, "unsure": 0, "dots": 0, "comments": []}
            )
            q["dots"] += d
        for did, fields in (r.get("decisions") or {}).items():
            d = merged["decisions"].setdefault(did, {})
            for k, v in fields.items():
                if str(v).strip():
                    d.setdefault(k, []).append({"who": who, "value": v})
    for q in merged["questions"].values():
        q["split"] = sum(1 for c in CHOICES if q[c]) > 1
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
