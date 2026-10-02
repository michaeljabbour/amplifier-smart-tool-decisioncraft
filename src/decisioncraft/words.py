"""The whole model as readable Markdown, for people who prefer text and for AI readers."""

from __future__ import annotations

from .model import DECISION_STATUS, FEELINGS, STATUSES, TEMPLATES, URGENCY, roles_of
from .review import questions


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
        status = f" ({STATUSES[b['status']]})" if b.get("status") else ""
        title = b.get("title") or b.get("text", "")
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
        if kind == "journeys":
            lanes = {ln["id"]: ln["label"] for ln in m.get("lanes", [])}
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
                w(f"### {st['label']}")
                if st.get("sub"):
                    w(st["sub"])
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
            for s in g.get("stories", []):
                w("")
                w(f"- {s['as']}")
                for d in s.get("done_when", []):
                    w(f"  - Done when: {d}")
            notes_for(g["id"])

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
            for c in (merged or {}).get("questions", {}).get(q["id"], {}).get("comments", []):
                w(f"  - {c['who']}: {c['text']}")

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
