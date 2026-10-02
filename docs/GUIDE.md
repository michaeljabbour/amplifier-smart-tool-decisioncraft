# Decisioncraft guide

The reference sections behind the [README](../README.md). Start there for install and a first map.

## Install

The install line and model choice are under [Install](../README.md#install).

Python 3.11 or later. `[smart]` lets `map`, `draft` and `perspectives` call Anthropic or
OpenAI: set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` and it picks the model for you (pin one
with `decisioncraft config set provider openai`). `[mcp]` is only for `decisioncraft mcp`.
`doctor` says which model will answer and exactly what to fix; `doctor --live` also makes one
tiny real call. You can also run straight from a checkout:
`python3 bin/decisioncraft.py`.

## Use it from your agent

```sh
# the skill (no checkout needed): Claude Code, Codex and Amplifier read the same file
for d in ~/.claude/skills ~/.codex/skills ~/.amplifier/skills; do
  mkdir -p "$d/decisioncraft" && curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-smart-tool-decisioncraft/main/skills/decisioncraft/SKILL.md -o "$d/decisioncraft/SKILL.md"
done
claude mcp add decisioncraft -- decisioncraft mcp   # optional: the MCP server in Claude Code
codex mcp add decisioncraft -- decisioncraft mcp    # optional: the MCP server in Codex
```

From a checkout, `cp -R skills/decisioncraft ~/.claude/skills/` does the same (use
`.claude/skills/` inside a project to install it for that project only).

The skill tells the agent when to reach for Decisioncraft; the MCP server gives it the tools
(map, triage, quick, interview, render, review notes and more), the prompts `map_this`,
`decide`, `compare_options`, `what_could_go_wrong`, `regret_test` and `review_canvas`, and
resources for templates, roles, the model format and the writing guide. Over MCP, model steps
use the host's own model when it offers sampling, otherwise your API key. See
[docs/HOSTS.md](HOSTS.md) for every host and the full list.

An agent that can't route a model to Decisioncraft writes the model itself: `decisioncraft
guide` prints every field with its rules, and `validate` checks the result.

## Quick start

```sh
decisioncraft                               # a short start screen
decisioncraft example medical --open        # copy a worked example and open it
decisioncraft new                           # a few questions, then a starter folder
decisioncraft render model.json --open      # draw your model
decisioncraft render model.json --watch     # draw again every time you save
```

`new` asks questions only in a terminal. Scripts and agents pass flags instead:

```sh
decisioncraft new --question "How do we cut missed pickups by half?" \
  --template customer-journey --roles owner,voice,finance --dir pickups
decisioncraft validate pickups/model.json
decisioncraft render pickups/model.json --out pickups/canvas.html

# or draft it from your material with a model (costs tokens; read the result)
cp notes/*.md pickups/material/
decisioncraft draft pickups/material/*.md --question "How do we cut missed pickups by half?" \
  --complete-cmd 'python3 my_adapter.py' --out pickups/model.json
#   ...or leave both flags off to use your API key (see First run above),
#   or --provider anthropic --model claude-sonnet-5-5 for this one run

# after the review
decisioncraft merge pickups/model.json review-*.json --out merged.json
decisioncraft render pickups/model.json --merged merged.json --open
decisioncraft words pickups/model.json --out pickups/model.md
```

Every command has a short summary (`-h`) and a full guide written for agents (`--help`).
Add `--json` to any command for one machine-readable result on stdout, errors included;
the exit code always matches (0 finished, 1 input problem, 2 wrong command line, 3 set
something up first, 4 model call failed). See [contracts/cli.v1.md](../contracts/cli.v1.md).

From Python, every capability takes and returns plain data:

```python
import json, decisioncraft as dc
model = json.load(open("model.json"))
problems = dc.validate(model)
html = dc.render(model)
merged = dc.merge([json.load(open(p)) for p in ["a.json", "b.json"]], model)
```

## Review with an agent

When the agent starts the review on your computer, use a local session:

```sh
decisioncraft session model.json --dir .work/review --open --until-finished
```

Answers save automatically. **Save and continue** keeps your answer before moving to the
next question. **Finish review** tells the waiting agent the review is ready. The agent
gets the answers directly; you do not need to download or attach a file. You still make
the final decision. Starting a session does not by itself mean the review is finished.

The command prints the local address and where it keeps the answers. Leave it running
while reviewing. Use a new folder for each session; pass `--review review.json` to continue
an earlier review. `--prepared-by` can identify the actual author when the notes omit one.
The session accepts requests only from this computer. Source links show only the files
inside `--source-root` (the current folder by default), or open a source website when asked.
No provider credentials are needed.

## Finish an offline review

1. Open **Questions to decide**, then **Answer questions**. You see one question at a time.
   Write an answer, or choose **Not sure yet**. The suggested next step is visible; supporting sources have a clear link. Use **Check my answers** to see what you have said and what remains open.
2. Press **Save my answers** in the top bar. This downloads a review file; it does not send it.
   You can save a partial review. Browser storage keeps your work when available.
3. Send the file to the review owner, or attach it to the agent chat that started the review.
4. The owner runs `merge` and `render --merged`, reads the answers, and records the decision.
   A review response does not by itself decide anything.

For a meeting on paper, choose **More → Print the questions**. The handout leaves room
for individual answers and the owner's final choice and reason.

Box positions are automatic. Drag empty space to move the view; click a box to read it.

## Personal decisions

For a car, a home, a job offer or a supplier, the `personal-decision` template gives a light
chain, today and after the change, a **scoring table** (must-haves first; weighted scores 1-5;
"what would change the winner" computed, never guessed) and **cost over time** (money spent,
plus loan still owed, minus what it is worth, plus what the cash could have earned; break-even
points in words; what-ifs). See the car example and `decisioncraft guide`.

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
| `map --dry-run`, `map --starter`, `triage`, `quick` (with options given), `interview`, `example`, `new`, `render`, `doctor`, `session`, `questions`, `merge`, `diff`, `words`, `validate`, `handoff`, `discover`, `guide`, `templates`, `roles`, `manifest`, `mcp` | deterministic; no model, no credentials |
| `map`, `draft`, `perspectives` (and `quick --text`, `triage` reading free text with a model) | model-backed; one of `--complete-cmd` (your host's own model), `--provider` with an API key, a `complete` function from code, or MCP sampling |

Model replies are validated; one repair is attempted; the result still needs a person.

## Limits

- Reviews travel as files, or through a local session. There is no live shared editing.
- Answers in the canvas stay in that browser until saved as a file.
- `map` and `draft` read text. Turn slides or spreadsheets into text first; PDFs need a parser.
- A map is only as good as what it read. Boxes the material does not show are marked not sure.
- Layout is automatic. Very large maps (dozens of journeys) are long; split them into several maps.
- The examples are fictional and simplified. The medical example is not clinical guidance.

