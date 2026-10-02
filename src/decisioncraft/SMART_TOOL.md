---
smart_tool_format: 1
name: decisioncraft
version: 0.1.0
description: >-
  Map how a problem works, gather every point of view, and decide together.
  Builds a zoomable, offline HTML canvas and a plain-text version from a decision model.
  Use when a decision affects several groups and each should be heard, with a record
  of why it was decided, before anyone chooses.
use_cases:
  - Draft a decision map from meeting notes, interviews, documents or data
  - Run a review where designers, analysts, engineers, owners, security, customers and finance each leave notes that end in a question
  - Merge reviewers' answers to see where people agree and disagree, and rank gaps by impact and effort
  - Compare two versions of a decision to see what changed since the last review
  - Show how something works today against a plan, read as Today, Planned, What changes (each box marked New, Changed or Goes away) or Side by side
platforms:
  - macos
  - linux
requires:
  - name: ANTHROPIC_API_KEY
    purpose: >-
      `draft` and `perspectives` with --provider anthropic. Without it, those two
      capabilities fail with a clear message; every other capability is unaffected.
    install: https://docs.anthropic.com/en/api/getting-started
    optional: true
  - name: OPENAI_API_KEY
    purpose: >-
      `draft` and `perspectives` with --provider openai. Without it, those two
      capabilities fail with a clear message; every other capability is unaffected.
    install: https://platform.openai.com/docs/quickstart
    optional: true
---
# decisioncraft

Decisioncraft helps a mixed group make one decision well. It draws how the problem
works today and what is planned, puts the evidence next to each claim, and adds notes
from every point of view. Each note ends in a question, so the review ends with a short,
ranked list of things to decide.

**The library is the tool.** `decisioncraft` (the Python package) holds every
capability. The command line reads files, calls the library, and prints or writes the
result. To chain several steps, call the library from Python: results are ordinary
dicts, lists and strings, so there is no output to parse.

## When to reach for it

- A decision affects several groups and each should be heard before anyone chooses.
- You need to show how something works (a service, a system, a patient's path, a
  process) and where it falls short, with today and the plan side by side.
- You want a record of why something was decided, with the exact words or numbers
  behind it.
- You have meeting notes, interviews or documents and want them turned into a map
  people can review without training.

## When not to

- A quick yes or no between two people: just ask.
- Tracking tasks or a project plan: use a tracker. (`questions` can feed one.)
- Live editing by many people at once: the canvas is a file; answers come back as files
  or, with `session`, straight to the agent on the same computer.
- Medical, legal or financial advice: the tool organises a team's reasoning; it gives
  no advice of its own.

## Install and check

```
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

Python 3.11 or later. `[smart]` is only for `--provider` on the two model-backed
commands; `[mcp]` is only for `decisioncraft mcp`. `doctor` checks everything, never
calls a model, and prints exactly what to fix.

## First five minutes

```
decisioncraft                                  # start screen
decisioncraft example medical --open           # a finished example in the browser
decisioncraft new                              # asks a few questions, makes a folder
decisioncraft render model.json --open         # draw your model
```

Worked examples: `business` (a bakery's subscription box), `technical` (moving file
uploads), `engineering` (repair or replace a footbridge), `medical` (a ward's discharge
process; not medical advice, no patient data).

## Deterministic and model-backed

Everything runs with no model and no credentials except `draft` and `perspectives`.

- Deterministic: `example`, `new`, `render`, `doctor`, `session`, `questions`, `merge`,
  `diff`, `words`, `validate`, `handoff`, `discover`, `templates`, `roles`, `manifest`,
  `mcp`.
- Model-backed: `draft` (material to a full model) and `perspectives` (add notes from
  each role). They cost tokens, differ run to run, check the reply and repair it once,
  and still need a person to read the result.

## Which model answers

`draft` and `perspectives` need a model. Decisioncraft never picks one for you and never
falls back to a lesser answer. If you are an agent, choose the first that fits:

1. **Write the model yourself** when you can't call your own model from a command (for
   example a coding agent with no MCP sampling). Run `decisioncraft new --question "..."
   --dir NAME --yes`, read `decisioncraft templates` and the writing guide
   (`resources/writing-guide.md` in the skill directory), fill in `NAME/model.json` from
   the material, quoting it as evidence, then run `decisioncraft validate NAME/model.json`
   until it reports no errors. No model call happens inside Decisioncraft.
2. **Your host's own model, by command** (`--complete-cmd`). Decisioncraft runs the
   command once per model call: once for the draft, and once more only if the reply needs
   a repair. Each run gets `{"system": "...", "prompt": "..."}` as JSON on stdin. Print
   the model's reply as it is; Decisioncraft finds the JSON in it and checks it. Exit
   non-zero to fail; your stderr is shown and the exit code is 4. No vendor SDK or key is
   needed. A draft can take a few minutes; allow for that in any timeout.

   ```python
   #!/usr/bin/env python3
   import json, sys
   request = json.load(sys.stdin)            # {"system": ..., "prompt": ...}
   reply = my_host_complete(request["system"], request["prompt"])  # your model call
   sys.stdout.write(reply)
   ```

   `decisioncraft doctor --complete-cmd 'python3 my_adapter.py'` checks the program can
   be found without running it.
3. **Your host's own model, in code.** Pass a function to the library:
   `dc.draft(material, question="...", complete=lambda system, prompt: host.ask(system, prompt))`.
4. **Your host's own model, over MCP.** `decisioncraft mcp` serves `decisioncraft_draft`
   and `decisioncraft_perspectives`, which ask the host's model through MCP sampling. A
   host without sampling gets a clear error and goes back to option 1, using
   `decisioncraft_templates` and `decisioncraft_validate`.
5. **A vendor SDK** (`--provider anthropic` or `--provider openai`, with `--model NAME`
   for draft or `--model-name NAME` for perspectives, the matching API key, and the
   `[smart]` extra).

## For agents and scripts

- `--json` on any command prints one JSON document on stdout: `{ok, command, result,
  files, next}`, or `{ok: false, error: {code, message, hint, file, field, problems},
  exit_code}`. `ok` is true exactly when the exit code is 0.
- Exit codes: 0 finished, 1 input problem, 2 wrong command line, 3 set something up
  first, 4 model call failed, 130 interrupted.
- It never prompts when stdin is not a terminal, or with `--yes` or `--json`.
- Progress goes to stderr (`-q` silences it); results go to stdout.
- `render` returns the written path; `example` and `new` list every file written.
- The full contract, with every error code: `contracts/cli.v1.md` in the repository.

## Recipes

**Turn meeting notes into a canvas.**

```
decisioncraft new --question "Should we open on Sundays?" --dir sundays --yes
cp notes/*.md sundays/material/
decisioncraft draft sundays/material/*.md --question "Should we open on Sundays?" \
  --complete-cmd 'python3 my_adapter.py' --out sundays/model.json
decisioncraft validate sundays/model.json
decisioncraft render sundays/model.json --open
```

Read the draft before sharing it. To add more notes from each role later:
`decisioncraft perspectives sundays/model.json sundays/material/*.md --complete-cmd 'python3 my_adapter.py' --out sundays/model.json`.

**Get expert replies on reviewers' rough notes.**

Reviewers add sticky notes in the canvas and press Ask the experts. In a live session
started with a model, replies appear in the page:

```
decisioncraft session model.json --dir .work/review-2 --complete-cmd 'python3 my_adapter.py' --open
```

From a saved answers file instead:

```
decisioncraft perspectives model.json --notes review-sam.json --dry-run
decisioncraft perspectives model.json --notes review-sam.json --complete-cmd 'python3 my_adapter.py' --out replies.json
decisioncraft render model.json --reviews replies.json --open
```

Each chosen role replies with a short view and one question; the questions join the
questions to decide. Over MCP, use `decisioncraft_review_notes` (host sampling).

**Run the review with the person on this computer.**

```
decisioncraft session sundays/model.json --dir .work/review-1 --open --until-finished --json
```

It prints `started` (with the local URL), then `finished` with the completed review and
a `handoff` once the person presses Finish review. Read their actual words; a vote or a
finished review is not a decision.

**Compare two versions.**

```
decisioncraft diff model-june.json model-july.json
decisioncraft render model-july.json --since model-june.json --open
```

**Merge reviews.**

```
decisioncraft merge model.json review-*.json --out merged.json
decisioncraft render model.json --merged merged.json --open
decisioncraft questions model.json --reviews review-*.json
```

**Export the questions to a task list.**

```python
import json, decisioncraft as dc
model = json.load(open("model.json"))
for q in dc.questions(model):
    print(f"- [ ] {q['question']} ({q['urgency']}, {q['role']})")
```

Or from a shell: `decisioncraft questions model.json --json`, then read `result`.

## Templates

- `system-journeys`: numbered steps across the parts of a system or organisation.
- `customer-journey`: phases of a customer's or patient's path, with feelings, pain
  points and moments that matter.
- `service-blueprint`: what the person does, what staff do in front of them and out
  of sight, and what supports it.
- `decision-chain`: source, evidence, decision, intent, spec, plan, work, outcome;
  today and planned.
- `opportunity-tree`: an outcome, the needs that could move it, ideas, and quick tests.

A model can hold several maps. `draft --template auto` (the default) chooses suitable
maps from the material.

## Roles

Eight default roles, each with the question it always asks: designer, analyst,
engineer, product owner, security and privacy, customer voice, AI agent teammate and
finance. `new --roles owner,finance,voice` keeps a subset; rename or replace them in the
model's `roles` list (for a hospital, "patient voice" and "clinical lead").

## Starting a decision with a person

Begin with `discover`: four opening questions about the choice, purpose, owner and
visual, then follow-ups about criteria, comparison and stakes. Ask them in conversation
and reuse what you already know; pass the answers to `draft --brief`. Agree criteria
before assessing options. The owner makes and records the choice and its reason.

## Sharp edges

- `draft` reads text only. Turn PDFs, slides or spreadsheets into text first.
- Answers in a standalone canvas stay in that browser until saved as a file.
- `render` prints HTML to stdout when piped without `--out`; in a terminal it writes
  `canvas.html` beside the model.
- `session` binds only to this computer; a remote host cannot open it. Use `--json` so
  each event is one line on stdout; without it the two results are printed as indented
  JSON one after the other.
- Examples are fictional. The medical example is about how a ward organises its work.
