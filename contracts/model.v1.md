# Decision model, version 1 (draft)

A JSON object with `"format": "decisioncraft/1"`.

| Field | Meaning |
|---|---|
| `title`, `question`, `summary` | What the decision is, in plain words. `question` is required. |
| `reading` | Optional: one paragraph on how to read this particular canvas. |
| `checked` | `{date, note}`: when the model was last checked against its sources. |
| `roles` | Who speaks: `{id, label, color, asks, jobs[]}`. Defaults apply when empty. |
| `glossary` | `{term: meaning}`. The canvas explains each term where it appears. |
| `sources` | `{id, title, kind, date, ref}`. Kind: interview, document, data, code, meeting, observation, survey, other. |
| `evidence` | `{id, source, kind, text, where, voice}`. The exact words or numbers. `voice: true` marks people's own words. |
| `comparison` | Optional: `{why, criteria[{id,label,importance (must/important/nice)}], options[{id,title,summary,evaluations[{criterion,judgment (fits/mixed/does_not_fit/unknown),reason,evidence[]}]}], method, recommendation{option,reason,risks}, review_when}`. Unknown assessments stay unknown; no automatic ranking. |
| `brief` | Optional: discovery answers in `decisioncraft-brief/1`. |
| `maps` | One or more maps, each `{id, template, title, intro, when (today/planned/both), ...}`. See below. |
| `links` | Optional: `{id, from, to, label, kind (flow/evidence/feedback), when (today/planned/both)}`. Endpoints are box ids. Name only relationships established by the material. |
| `gaps` | `{id, title, why, anchors[], impact 1-5, effort 1-5, stories[{as, done_when[]}]}`. |
| `notes` | `{id, role, anchor, title, body, recommend, question, urgency, evidence[], answer_type, author}`. Urgency: must, should, info. `anchor` is any box or gap id. |
| `decisions` | `{id, question, notes[], options[], owner, status, due, decided_by, decision}`. Status: open, decided, deferred. |
| `outcomes` | `{id, measure, baseline, target, result, checked, becomes_evidence}`. |
| `dots`, `freshness_days` | Optional: dots per reviewer (default 5); age in days before a box is flagged (default 60). |

An optional note `author` records who wrote it. Do not infer a person from a role.
Model-backed notes identify the AI assistant; missing authors are shown as missing.

Notes use `answer_type: text` by default: reviewers write an answer. Use `stance` only
when agree/change/unsure directly answers the question. A view on a suggestion is
separate from a written answer. Old views are preserved, not treated as written answers.

Connections highlight when a linked box is selected. The All connections switch shows
them together. Their names also appear in the detail panel and the text version.
Flow, supporting evidence and feedback use different line styles. Cross-map connections
remain available in the detail panel even when both endpoints cannot be drawn together.

## Map shapes

- **Journeys** (`system-journeys`, `customer-journey`, `service-blueprint`): `lanes[{id, label, sub}]`
  and `journeys[{id, title, summary, creates[], steps[]}]`. A step:
  `{id, lane, text, status, when (today|planned|both), replaces, detail, pain, moment, feeling, checked, evidence[]}`.
- **Chain** (`decision-chain`): `stages[{id, label, sub, verb, items[]}]`. An item:
  `{id, title, text, status, when (today|planned|both), replaces, detail, checked, evidence[]}`.
- **Tree** (`opportunity-tree`): `levels[]` and `root{id, title, text, status, children[]}`.

### Today, the plan, and what changes

`when` says whether a step or item exists today only, only in the plan, or in both (the
default). A planned box may name the today-only box it `replaces` in the same journey or
stage; the pair reads as one change with a before and an after. Other planned-only boxes
are new, and today-only boxes nothing replaces go away. Steps without `when` count as both,
whatever their status. Maps with any `when` offer Today, Planned, What changes (one map,
each box marked New, Changed or Goes away, with counts) and Side by side (today and the
plan in two panes with one pan and zoom, rows lined up). The text version lists the same
changes, and the proposed-state model keeps the planned boxes only.

Status: works, partial, missing, planned. Feeling: good, ok, bad. `detail` holds technical
descriptions. Opening a box always shows them; a display switch also shows them on the map when available.

Ids are unique across the whole model. `validate` reports every broken link.
