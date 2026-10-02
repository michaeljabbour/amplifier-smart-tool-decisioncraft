"""Keep the reasons for comparing options visible, without invented scores."""

from __future__ import annotations


def check_comparison(value, evidence_ids):
    problems = []

    def error(path, message):
        problems.append(
            {"level": "error", "path": "comparison" + path, "message": message}
        )

    if not isinstance(value, dict):
        error("", "Comparison must be a JSON object.")
        return problems
    for field in ("why", "method", "review_when"):
        if field in value and not isinstance(value[field], str):
            error("." + field, "Use text.")
    groups = {}
    for field in ("criteria", "options"):
        items = value.get(field, [])
        if not isinstance(items, list):
            error("." + field, "Use a list.")
            items = []
        ids = set()
        clean = []
        for i, item in enumerate(items):
            path = f".{field}[{i}]"
            if not isinstance(item, dict):
                error(path, "Use a JSON object.")
                continue
            key = item.get("id")
            if not isinstance(key, str) or not key.strip() or key in ids:
                error(path + ".id", "Use a unique non-empty id.")
            else:
                ids.add(key)
            label = "label" if field == "criteria" else "title"
            if not isinstance(item.get(label), str) or not item[label].strip():
                error(path + "." + label, "Give this a clear name.")
            if field == "criteria" and item.get("importance", "important") not in (
                "must",
                "important",
                "nice",
            ):
                error(
                    path + ".importance", "Importance must be must, important or nice."
                )
            clean.append(item)
        groups[field] = (ids, clean)
    for i, option in enumerate(groups["options"][1]):
        evaluations = option.get("evaluations", [])
        if not isinstance(evaluations, list):
            error(f".options[{i}].evaluations", "Use a list.")
            continue
        seen = set()
        for j, evaluation in enumerate(evaluations):
            path = f".options[{i}].evaluations[{j}]"
            if not isinstance(evaluation, dict):
                error(path, "Use a JSON object.")
                continue
            criterion = evaluation.get("criterion")
            if (
                not isinstance(criterion, str)
                or criterion not in groups["criteria"][0]
                or criterion in seen
            ):
                error(path + ".criterion", "Use a known criterion once per option.")
            else:
                seen.add(criterion)
            if evaluation.get("judgment", "unknown") not in (
                "fits",
                "mixed",
                "does_not_fit",
                "unknown",
            ):
                error(path + ".judgment", "Use fits, mixed, does_not_fit or unknown.")
            if not isinstance(evaluation.get("reason", ""), str):
                error(path + ".reason", "Explain this in text.")
            refs = evaluation.get("evidence", [])
            if not isinstance(refs, list) or any(
                not isinstance(r, str) or r not in evidence_ids for r in refs
            ):
                error(path + ".evidence", "Use known evidence ids.")
    recommendation = value.get("recommendation")
    if recommendation is not None:
        if not isinstance(recommendation, dict):
            error(".recommendation", "Use an option id, reason and remaining risks.")
        else:
            option = recommendation.get("option")
            if not isinstance(option, str) or option not in groups["options"][0]:
                error(".recommendation.option", "Use a known option id.")
            if (
                not isinstance(recommendation.get("reason"), str)
                or not recommendation["reason"].strip()
            ):
                error(".recommendation.reason", "Explain why this option is suggested.")
            if not isinstance(recommendation.get("risks", ""), str):
                error(".recommendation.risks", "Explain remaining risks in text.")
    return problems


def comparison_summary(model):
    """Return the supplied comparison and the points still needing a human answer."""
    value = model.get("comparison", {})
    missing = []
    if not value.get("criteria"):
        missing.append("Agree what matters when choosing.")
    if len(value.get("options", [])) < 2:
        missing.append(
            "Identify realistic alternatives to compare, including keeping things as they are when that is a real option."
        )
    if not value.get("method"):
        missing.append(
            "Agree how to compare: a conversation, a small trial, research, or another suitable check."
        )
    for option in value.get("options", []):
        evaluated = {e["criterion"]: e for e in option.get("evaluations", [])}
        for criterion in value.get("criteria", []):
            evaluation = evaluated.get(criterion["id"], {})
            if evaluation.get("judgment", "unknown") == "unknown":
                missing.append(f"Check {option['title']} against {criterion['label']}.")
            elif not evaluation.get("reason"):
                missing.append(
                    f"Explain the assessment of {option['title']} against {criterion['label']}."
                )
    return {**value, "missing": missing}
