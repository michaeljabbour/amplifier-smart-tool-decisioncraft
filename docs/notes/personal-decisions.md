# Personal decisions: notes for merging into the manifest, skill and CLI

Written for whoever owns `SMART_TOOL.md`, `skills/decisioncraft/SKILL.md`, the MCP server
and `cli.py`. Everything below is already in the library, model contract and canvas on the
`personal-decisions` branch; these are the doc and CLI pieces left to fold in.

## What is new

- **Template `personal-decision`** (a starting set, not a single map): `decisioncraft new
  --template personal-decision` makes a light chain (source, evidence, decision, outcome), a
  today-and-after journey, a scoring table and a cost map, with personal roles: Money,
  Practical expert, Safety, People affected, Future you, Environment, Market and resale,
  Devil's advocate.
- **Map templates `scoring-table` and `cost-over-time`**, usable in any model. They draw the
  model-level `options`, `criteria`, `scores`, `costs` and `whatifs`.
- **`framing`**: a pre-mortem ("a year later this went badly, why?") and a 10-10-10 regret
  check, shown under Before you decide and in the text version.
- **`display`**: `{notes_on_map, start_view}` decides how the canvas first opens; the
  reviewer's later choice wins and is remembered.
- **Reviews** may carry `weights` and `whatifs`; `merge` adds `weights` and `weight_split`.
- **Example `car`** (folder `examples/personal-car/`), with two reviews that disagree on
  the safety weight.

## CLI change needed (not made here)

`cli.py` hard-codes the example names for `decisioncraft example`:
`choices=["business", "technical", "engineering", "medical"]`. Add `"car"`, or better, take
the choices from `examples.example_names()`. The library already resolves `car` to the
`personal-car` folder, and the wheel includes it (pyproject `force-include`). Until then,
`decisioncraft example car` is refused by argparse. The test
`test_library_functions_match_the_cli` was widened to allow the fifth example.

## Suggested SMART_TOOL.md additions

Under "When to reach for it": a choice between a few clear options where money over time
matters (a car, a home, a job offer, a supplier), even when the person did not say
"decision" ("should I renew my lease or buy?", "is it worth fixing the old one?").

A recipe, "Weigh a personal choice":

```sh
decisioncraft new --template personal-decision --title "Renew, keep or buy" \
  --question "When the lease ends, what should we do?" --dir car-choice
# fill options, criteria (must-haves and weighted), scores 1-5 with notes and evidence,
# costs per option (upfront, yearly items, loan, value by year), what-ifs, framing
decisioncraft validate car-choice/model.json
decisioncraft render car-choice/model.json --open
decisioncraft words car-choice/model.json     # the scoring table and cost summary as text
```

Points worth stating for agents:

- Scores are whole numbers 1-5; weights 0-5 in half steps; must-haves are pass or fail and
  an option failing one is out of the ranking. Totals show one decimal; top totals within
  0.25 are reported as a close call. Do not add decimals the judgments do not have.
- "What would change the winner" is computed, not drafted: the smallest single weight
  change (half steps, within 0-5) or one-point score change that puts another option on top.
- Real cost = money spent + loan still owed − what it is worth + what the cash put down
  could have earned (`cash_return`). Use dated public figures for depreciation, fuel,
  insurance and loan rates, and say where each number came from (evidence).
- What-ifs multiply costs by kind, tag or `value`; tag costs (for example `miles`,
  `older-car`) so a what-if touches only what it should.

## Suggested SKILL.md line

"Personal and household choices (car, home, job offer) — use the `personal-decision`
template: must-haves, weighted scores with a computed 'what would change the winner', cost
over time with break-even points and what-ifs, a pre-mortem and a 10-10-10 check."

## MCP

No new tool is needed: `decisioncraft_render`, `_words` and `_validate` cover it. If the
MCP server lists example names, include `car`.
