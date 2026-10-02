"""The whole model as readable Markdown, for people who prefer text and for AI readers."""

from __future__ import annotations

from .model import DECISION_STATUS, FEELINGS, STATUSES, TEMPLATES, URGENCY, iter_boxes, plan_changes, roles_of
from .review import _note_target, note_threads, questions


def words(model: dict, merged: dict | None = None) -> str:
    """Render a model (and optionally merged reviews) as Markdown prose and lists."""
    roles = {r["id"]: r for r in roles_of(model)}
    evidence = {e["id"]: e for e in model.get("evidence", [])}
    sources = {s["id"]: s for s in model.get("sources", [])}
    notes_by_anchor: dict[str, list] = {}
    for n in model.get("notes", []):
        notes_by_anchor.setdefault(n.get("anchor"), []).append(n)
    out: list[str] = []
    w = out.append

    def cite(refs):
        parts = []
        for r in refs or []:
            e = evidence.get(r)
            if not e:
                continue
            s = sources.get(e.get("source"), {})
            where = f", {e['where']}" if e.get("where") else ""
            parts.append(f"  > “{e['text']}” — {s.get('title', e.get('source'))}{where} [{r}]")
        return parts

    def notes_for(anchor, indent=""):
        for n in notes_by_anchor.get(anchor, []):
            role = roles.get(n.get("role"), {}).get("label", n.get("role"))
            w(f"{indent}- **{role} note ({URGENCY[n.get('urgency', 'info')]}): {n['title']}.** "
              f"{n.get('body', '')}")
            if n.get("recommend"):
                w(f"{indent}  We suggest: {n['recommend']}")
            if n.get("question"):
                w(f"{indent}  Question: {n['question']}")
            for c in cite(n.get("evidence")):
                w(indent + c)

    def box_line(b, indent="- "):
        status = f" ({STATUSES[b['status']]}{': ' + b['status_reason'] if b.get('status_reason') else ''})" if b.get("status") else ""
        if b.get("when") == "today":
            status += " (today only)"
        elif b.get("when") == "planned":
            status += " (planned)"
        title = (f"{b['kind']}: " if b.get("kind") else "") + (b.get("title") or b.get("text", ""))
        text = b.get("text", "") if b.get("title") else ""
        w(f"{indent}**{title}**{status}{': ' + text if text else ''}")
        extra = []
        if b.get("pain"):
            extra.append(f"Pain: {b['pain']}")
        if b.get("moment"):
            extra.append("A moment that matters.")
        if b.get("feeling"):
            extra.append(f"How it feels: {FEELINGS[b['feeling']]}.")
        if b.get("checked"):
            extra.append(f"Checked {b['checked']}.")
        if extra:
            w("  " + " ".join(extra))
        for c in cite(b.get("evidence")):
            w(c)

    w(f"# {model['title']}")
    w("")
    w(f"**The decision:** {model['question']}")
    if model.get("summary"):
        w("")
        w(model["summary"])
    if model.get("reading"):
        w("")
        w(f"**How to read this:** {model['reading']}")
    checked = model.get("checked") or {}
    if checked.get("date"):
        w("")
        w(f"_Checked against the sources on {checked['date']}."
          f"{' ' + checked['note'] if checked.get('note') else ''}_")

    for m in model.get("maps", []):
        kind = TEMPLATES[m["template"]]["kind"]
        w("")
        w(f"## {m.get('title') or TEMPLATES[m['template']]['title']}")
        if m.get("intro"):
            w("")
            w(m["intro"])
        changes = plan_changes(m)
        if changes:
            label = {"new": "New", "changed": "Changed", "gone": "Goes away"}
            counts = {k: sum(c["change"] == k for c in changes) for k in label}
            w("")
            w("### What changes")
            w("")
            w(" · ".join(f"{n} {word}" for word, n in (("new", counts["new"]), ("changed", counts["changed"]),
                                                     ("goes away" if counts["gone"] == 1 else "go away", counts["gone"])) if n) + ".")
            w("")
            for c in changes:
                name = lambda b: b.get("title") or b.get("text", "")
                if c["change"] == "changed":
                    w(f"- **{label['changed']}:** {name(c['before'])} → {name(c['box'])}")
                else:
                    w(f"- **{label[c['change']]}:** {name(c['box'])}")
        if kind == "journeys":
            lanes = {ln["id"]: ln["label"] for ln in m.get("lanes", [])}
            described = [ln for ln in m.get("lanes", []) if ln.get("summary") or ln.get("detail")]
            if described:
                w("")
                w("Parts of the system:")
                for ln in described:
                    w(f"- **{ln['label']}**{': ' + ln['summary'] if ln.get('summary') else ''}"
                      f"{' (Technical: ' + ln['detail'] + ')' if ln.get('detail') else ''}")
            for j in m.get("journeys", []):
                w("")
                w(f"### {j['title']}")
                if j.get("summary"):
                    w(j["summary"])
                w("")
                for k, s in enumerate(j.get("steps", []), 1):
                    box_line(s, f"{k}. [{lanes.get(s.get('lane'), s.get('lane'))}] ")
                notes_for(j["id"])
                for s in j.get("steps", []):
                    notes_for(s["id"])
        elif kind == "chain":
            for st in m.get("stages", []):
                w("")
                w(f"### {st['label']}{' (' + STATUSES[st['status']] + ')' if st.get('status') in STATUSES else ''}")
                if st.get("sub"):
                    w(st["sub"])
                if st.get("before"):
                    w(f"{m.get('before_label') or 'Before'}: {st['before']}")
                for when, label in (("today", "Today"), ("planned", "Planned")):
                    items = [i for i in st.get("items", []) if i.get("when", "both") in (when, "both")]
                    if items:
                        w("")
                        w(f"{label}:")
                        for it in items:
                            box_line(it)
                notes_for(st["id"])
                for it in st.get("items", []):
                    notes_for(it["id"])
            stage_names = {st["id"]: st["label"] for st in m.get("stages", [])}
            for band in m.get("bands", []):
                w("")
                w(f"### Across the chain: {band.get('title', band['id'])}")
                box_line({k: v for k, v in band.items() if k != "title"} | {"title": band.get("title", band["id"])})
                if band.get("stages"):
                    w("  Touches: " + ", ".join(stage_names.get(s, s) for s in band["stages"]) + ".")
                notes_for(band["id"])
        else:
            levels = m.get("levels") or TEMPLATES[m["template"]]["levels"]

            def walk(n, depth):
                label = levels[min(depth, len(levels) - 1)]
                box_line(n, "  " * depth + f"- {label}: ")
                notes_for(n["id"], "  " * depth)
                for c in n.get("children", []):
                    walk(c, depth + 1)

            w("")
            walk(m["root"], 0)

    if model.get("gaps"):
        w("")
        w("## Gaps between today and planned")
        for g in sorted(model["gaps"], key=lambda g: -((g.get("impact") or 0) * 2 - (g.get("effort") or 0))):
            w("")
            score = []
            if g.get("impact"):
                score.append(f"impact {g['impact']}/5")
            if g.get("effort"):
                score.append(f"effort {g['effort']}/5")
            w(f"### {g['id']}: {g['title']}{' (' + ', '.join(score) + ')' if score else ''}")
            if g.get("why"):
                w(g["why"])
            if g.get("design"):
                w("")
                w("Design principles:")
                for d in g["design"]:
                    w(f"- {d}")
            if g.get("detail"):
                w("")
                w(f"Technical design: {g['detail']}")
            for s in g.get("stories", []):
                w("")
                w(f"- {s['as']}")
                for d in s.get("done_when", []):
                    w(f"  - Done when: {d}")
                sd = s.get("detail")
                for d in ([sd] if isinstance(sd, str) else sd or []):
                    w(f"  - Technical check: {d}")
            notes_for(g["id"])

    threads = note_threads(merged)
    if threads:
        w("")
        w("## Reviewer notes and expert replies")
        for n in threads:
            on = _note_target(model, n.get("anchor"))["title"]
            who = n.get("who") or n.get("author") or "A reviewer"
            w("")
            w(f"- **{who} on {on}:** {n.get('text', '')}")
            if n.get("ask") and not n.get("replies"):
                w("  Waiting for experts: " + ", ".join(roles.get(r, {}).get("label", r) for r in n["ask"].get("roles", [])) + ".")
            for r in n.get("replies", []):
                label = roles.get(r.get("role"), {}).get("label", r.get("role"))
                w(f"  - {label} ({URGENCY[r.get('urgency', 'info')]}): {r.get('view', '')}")
                if r.get("question"):
                    w(f"    Question: {r['question']}")

    qs = questions(model, merged)
    if qs:
        w("")
        w("## Questions to decide")
        current = None
        for q in qs:
            if q["urgency"] != current:
                current = q["urgency"]
                w("")
                w(f"### {URGENCY[current]}")
            tally = ""
            if merged:
                tally = (f" — agree {q['agree']}, change {q['change']}, unsure {q['unsure']},"
                         f" dots {q['dots']}")
            w(f"- {q['question']} ({q['role_label']}, on {q['where']}){tally}")
            for a in q.get("answers", []):
                w(f"  - {a['who']} answered: {a['text']}")
            for c in (merged or {}).get("questions", {}).get(q["id"], {}).get("comments", []):
                w(f"  - {c['who']}: {c['text']}")

    if model.get("comparison"):
        comparison = model["comparison"]
        w(""); w("## Compare the options")
        if comparison.get("why"):
            w(comparison["why"])
        w("What matters:")
        for criterion in comparison.get("criteria", []):
            w(f"- {criterion['label']} ({criterion.get('importance', 'important')}).")
        w("How we will compare: " + (comparison.get("method") or "Not agreed yet."))
        for option in comparison.get("options", []):
            w(""); w(f"### {option['title']}")
            for evaluation in option.get("evaluations", []):
                criterion = next(c for c in comparison["criteria"] if c["id"] == evaluation["criterion"])
                w(f"- {criterion['label']}: {evaluation.get('judgment', 'unknown')}. {evaluation.get('reason', 'Not checked yet.')}")
                out.extend(cite(evaluation.get("evidence")))
        recommendation = comparison.get("recommendation")
        if recommendation:
            option = next(o for o in comparison["options"] if o["id"] == recommendation["option"])
            w(f"Suggested choice: {option['title']}. {recommendation['reason']}")
            w("Remaining risks: " + (recommendation.get("risks") or "Not recorded yet."))
        w("Check again when: " + (comparison.get("review_when") or "Not agreed yet."))

    if model.get("links"):
        boxes = {b["id"]: b for _, b in iter_boxes(model)}
        w("")
        w("## Connections")
        for connection in model["links"]:
            a, b = boxes[connection["from"]], boxes[connection["to"]]
            name = lambda box: box.get("title") or box.get("label") or box.get("text") or box["id"]
            when = {"today": "current", "planned": "proposed", "both": "current and proposed"}[connection.get("when", "both")]
            w(f"- {name(a)} → {name(b)}: {connection['label']} ({connection.get('kind', 'flow')}; {when}).")

    if model.get("decisions"):
        w("")
        w("## Decisions")
        for d in model["decisions"]:
            w("")
            w(f"### {d['id']}: {d['question']}")
            bits = [f"Status: {DECISION_STATUS[d.get('status', 'open')]}"]
            for k, label in (("owner", "Owner"), ("due", "Due"), ("decided_by", "Decided by")):
                if d.get(k):
                    bits.append(f"{label}: {d[k]}")
            w(". ".join(bits) + ".")
            if d.get("options"):
                w("Options: " + "; ".join(d["options"]) + ".")
            if d.get("decision"):
                w(f"What we decided: {d['decision']}")

    if model.get("outcomes"):
        w("")
        w("## Did it work?")
        for o in model["outcomes"]:
            w("")
            line = f"- **{o['measure']}**"
            if o.get("baseline"):
                line += f" Before: {o['baseline']}."
            if o.get("target"):
                line += f" Target: {o['target']}."
            line += f" Result: {o['result']}." if o.get("result") else " Not measured yet."
            w(line)
            if o.get("becomes_evidence"):
                w(f"  This result feeds back as evidence {o['becomes_evidence']}.")

    if model.get("sources"):
        w("")
        w("## Sources")
        w("")
        for s in model["sources"]:
            w(f"- [{s['id']}] {s['title']} ({s.get('kind', 'other')}"
              f"{', ' + s['date'] if s.get('date') else ''})")

    if model.get("glossary"):
        w("")
        w("## Words we use")
        w("")
        for term, meaning in model["glossary"].items():
            w(f"- **{term}**: {meaning}")

    w("")
    w("## Who is speaking")
    w("")
    for r in roles_of(model):
        w(f"- **{r['label']}**: {r.get('asks', '')}")
        for job in r.get("jobs", []):
            w(f"  - Job to be done: {job}")
    return "\n".join(out).rstrip() + "\n"
