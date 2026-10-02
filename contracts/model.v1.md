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
| `maps` | One or more maps, each `{id, template, title, intro, ...}`. See below. |
| `gaps` | `{id, title, why, anchors[], impact 1-5, effort 1-5, stories[{as, done_when[]}]}`. |
| `notes` | `{id, role, anchor, title, body, recommend, question, urgency, evidence[]}`. Urgency: must, should, info. `anchor` is any box or gap id. |
| `decisions` | `{id, question, notes[], options[], owner, status, due, decided_by, decision}`. Status: open, decided, deferred. |
| `outcomes` | `{id, measure, baseline, target, result, checked, becomes_evidence}`. |
| `dots`, `freshness_days` | Optional: dots per reviewer (default 5); age in days before a box is flagged (default 60). |

## Map shapes

- **Journeys** (`system-journeys`, `customer-journey`, `service-blueprint`): `lanes[{id, label, sub}]`
  and `journeys[{id, title, summary, creates[], steps[]}]`. A step:
  `{id, lane, text, status, detail, pain, moment, feeling, checked, evidence[]}`.
- **Chain** (`decision-chain`): `stages[{id, label, sub, verb, items[]}]`. An item:
  `{id, title, text, status, when (today|planned|both), detail, checked, evidence[]}`.
- **Tree** (`opportunity-tree`): `levels[]` and `root{id, title, text, status, children[]}`.

Status: works, partial, missing, planned. Feeling: good, ok, bad. `detail` holds technical
names, shown only when a reader asks for them.

Ids are unique across the whole model. `validate` reports every broken link.
