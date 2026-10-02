# Decisioncraft

Decisioncraft helps a mixed group make one decision well. It maps how a problem works
today and what is planned, puts the evidence beside every claim, and gathers notes from
every point of view, each ending in a question. The result is one offline file people can
review without training, and a short, ranked list of what to decide.

![The bakery example: the list of views on the left, a subscriber's journey on the map, notes counted on each step](docs/images/business-poster.png)

*Screenshot of the bakery example. All examples are fictional.*

## What you get

- **A map** of the problem. Five templates: system journeys, a customer or patient
  journey, a service blueprint, a decision chain (source, evidence, decision, intent,
  spec, plan, work, outcome), and an opportunity tree.
- **Evidence beside every claim.** Boxes and notes link to the exact words or numbers,
  with source and date. Quotes from customers or patients are marked as their own words.
- **Notes from every point of view.** Default roles: designer, analyst, engineer, product
  owner, security and privacy, customer voice, AI agent teammate, and finance. Rename or
  replace them per decision.
- **Gaps you can rank.** Differences between today and the plan become gaps with user
  stories, "done when" checks, and impact and effort scores.
- **Decisions with owners.** Each has an owner, a status, a due date and who decided.
- **A review loop.** Reviewers answer questions, place dots on what matters most and save
  their answers as a file. `merge` shows where people agree and disagree.
- **What changed.** `diff`, or `render --since`, marks new and changed boxes before a
  follow-up review. Boxes not checked for a while say so.
- **Did it work?** Outcome measures, and results that feed back as evidence.

The canvas is one HTML file. It works offline, makes no requests, and opens with a
numbered list of views, a "Walk me through it" tour, labelled zoom buttons, and a panel
where people read notes and answer.

## Install

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart] @ git+https://github.com/decisioncraft/amplifier-smart-tool-decisioncraft"
decisioncraft --help
```

Python 3.11 or later. The `[smart]` extra is only needed for the two model-backed
capabilities. You can also run straight from a checkout: `python3 bin/decisioncraft.py --help`.

## Quick start

```sh
# start from a template and fill it in by hand
decisioncraft new --template customer-journey --title "Missed pickups" \
  --question "How do we cut missed pickups by half?" --out model.json
decisioncraft validate model.json
decisioncraft render model.json --out canvas.html

# or draft it from your material with a language model (costs tokens; review the result)
export ANTHROPIC_API_KEY=...
decisioncraft draft notes/*.md --template decision-chain \
  --question "Should we open on Sundays?" --provider anthropic --out model.json

# after the review
decisioncraft merge model.json review-*.json --out merged.json
decisioncraft render model.json --merged merged.json --out canvas.html
decisioncraft words model.json --out model.md
```

From Python, every capability takes and returns plain data:

```python
import json, decisioncraft as dc
model = json.load(open("model.json"))
problems = dc.validate(model)
html = dc.render(model)
merged = dc.merge([json.load(open(p)) for p in ["a.json", "b.json"]], model)
```

## The four examples

Each folder in `examples/` holds the input material, the model, the rendered canvas and a
plain-text version. All names, quotes and figures are invented.

| Example | The decision | Templates |
|---|---|---|
| [business](examples/business/) | Should a three-shop bakery offer a monthly box? Includes two reviewers' answers and the merged canvas. | customer journey, decision chain |
| [technical](examples/technical/) | Move file uploads to a new storage provider, change how uploads reach storage, or both? Includes an earlier version to show what changed. | system journeys, opportunity tree |
| [engineering](examples/engineering/) | Repair, replace, or replace a footbridge with a wider one? | decision chain, service blueprint |
| [medical](examples/medical/) | How should a ward change the way it sends patients home, so fewer come back? About how a team organises its work. **Not medical advice; no patient data.** | customer journey, service blueprint |

The models were written by hand to show the format; `draft` produces the same shape from
your own material. Rebuild every output with `python3 scripts/build-examples.py`.

## Roles and templates

A model's `roles` list sets who speaks. Each role has an id, a label, a colour, the
question it always asks, and optional jobs to be done. Notes point at a role by id.

A model holds one or more `maps`, each using one template. Journey templates draw lanes
(columns) and numbered steps; steps can carry a pain point, a feeling, and a "moment that
matters" mark. The decision chain draws stages with items for today and planned. The
opportunity tree draws an outcome, needs, ideas and quick tests. Run
`decisioncraft templates` for the list and `decisioncraft new` to see each shape.

## What is model-backed

| Capability | Kind |
|---|---|
| `manifest`, `templates`, `roles`, `new`, `validate`, `render`, `words`, `questions`, `merge`, `diff` | deterministic; no model, no credentials |
| `draft`, `perspectives` | model-backed; need `--provider` and an API key, or a `complete` function passed by a host |

Model replies are validated; one repair is attempted; the result still needs a person.

## Limits

- Reviews travel as files. There is no live shared editing.
- Answers in the canvas stay in that browser until saved as a file.
- `draft` reads text. Turn PDFs, slides or spreadsheets into text first.
- Layout is automatic. Very large maps (dozens of journeys) are usable but long; split them
  into several maps.
- The examples are fictional and simplified. The medical example is not clinical guidance.

## Development

```sh
uv run pytest                                   # tests
python3 scripts/check-generic.py                # no personal details, product names or filler words
python3 scripts/build-examples.py               # rebuild example outputs
python3 scripts/check-canvas.py examples/*/canvas*.html   # first-time-user checks (needs Playwright)
```

See [AGENTS.md](AGENTS.md), [the vision](docs/VISION.md) and [the contracts](contracts/README.md).
The product page lives in [site/](site/README.md).

## License

MIT. See [LICENSE](LICENSE).
