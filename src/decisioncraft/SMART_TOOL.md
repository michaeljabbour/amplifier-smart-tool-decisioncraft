---
smart_tool_format: 1
name: decisioncraft
version: 0.2.1
description: Point it at anything (a codebase, a folder of notes, a page or a topic) and get a map of how it works today, how it could work, the gaps as user stories with 'done when' checks, and a note from every role. It also helps someone weigh a choice at the right depth, from a quick side-by-side in the chat to a full team review. Use for 'map this codebase', 'show me how X works', 'as-is and to-be', 'where are the gaps', 'turn these notes into a process map', 'review this process', and whenever someone is weighing options without saying decision, such as 'should I', 'torn between', 'pros and cons', 'which is better', 'renew or buy', 'keep or replace', 'help me think this through', or comparing offers, quotes or vendors. Not for factual questions or trivial picks.
use_cases:
  - Point it at a codebase, a folder of notes or a topic and see how it works today, how it could work, and the gaps as user stories
  - Talk a personal choice through, like renewing a lease or buying a car, a job offer or a school, and see the options side by side
  - Settle a small choice in the chat with a scored table, a lean and the one thing to check first
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
      The model-backed steps (map, draft, perspectives and Ask the experts) with
      --provider anthropic. Without it those steps fail with a clear message; every other
      capability, and --complete-cmd or --starter, is unaffected.
    install: https://docs.anthropic.com/en/api/getting-started
    optional: true
  - name: OPENAI_API_KEY
    purpose: >-
      The model-backed steps (map, draft, perspectives and Ask the experts) with
      --provider openai. Without it those steps fail with a clear message; every other
      capability, and --complete-cmd or --starter, is unaffected.
    install: https://platform.openai.com/docs/quickstart
    optional: true
---
# decisioncraft

**Point it at anything:** `decisioncraft map ./your-repo --open` reads a codebase, a folder
of notes, a page or a topic and draws how it works today, how it could work, the gaps as
user stories with "done when" checks, and notes from every role.

Decisioncraft helps people make a choice well, at the depth the choice deserves. A small
one gets a scored table in the conversation. A bigger one gets a few questions and a map
to open. One that affects several groups gets the full canvas: how the problem works today
and what is planned, the evidence next to each claim, and notes from every point of view,
each ending in a question, so the review ends with a short, ranked list of things to decide.

**The library is the tool.** `decisioncraft` (the Python package) holds every
capability. The command line reads files, calls the library, and prints or writes the
result. To chain several steps, call the library from Python: results are ordinary
dicts, lists and strings, so there is no output to parse.

## When to reach for it

- Someone wants to see how something works and what is missing: "map this codebase",
  "show me how onboarding works", "as-is and to-be", "where are the gaps", "turn these
  notes into a process map", "review this process". Use `map` (below).
- Someone is weighing options, whether or not they say "decision": should I renew or
  buy, which offer, keep or replace, pros and cons, torn between two things. Start with
  `triage` (below); it may well say "just answer".
- A decision affects several groups and each should be heard before anyone chooses.
- You need to show how something works (a service, a system, a patient's path, a
  process) and where it falls short, with today and the plan side by side.
- You want a record of why something was decided, with the exact words or numbers
  behind it.
- You have meeting notes, interviews or documents and want them turned into a map
  people can review without training.

## When not to

- A factual question ("what is the capital of France?"): answer it.
- A trivial pick ("pizza or tacos?"): give an opinion if asked. `triage` returns `none`
  for these; build nothing.
- Tracking tasks or a project plan: use a tracker. (`questions` can feed one.)
- Live editing by many people at once: the canvas is a file; answers come back as files
  or, with `session`, straight to the agent on the same computer.
- Medical, legal or financial advice: the tool organises a team's reasoning; it gives
  no advice of its own.

## Modes

Decisioncraft helps at four depths. `decisioncraft triage` picks one; you can always go
deeper if the person wants.

| Mode | When | What you do |
|---|---|---|
| `none`, Just answer | Small, easy to undo, only affects the person | Answer. Offer a side-by-side only if they seem torn. No files. |
| `quick` | A real choice that fits in the conversation | Ask what matters, score the options 1 to 5 with them, run `quick`, show the table, the lean and the one thing to check. No files. |
| `guided` | Costly or hard to undo, or worth seeing laid out | Ask permission, then `interview` one question at a time; it writes a starter model; `render --open`. |
| `team` | Several groups affected | `interview --kind team`, then `draft` from their material, `render`, a `session` review, Ask the experts. |

The rule `triage` uses, so you can predict it: it rates cost (0 little to 3 very large),
how hard it is to undo (0 to 2) and who is affected (0 just you, 1 family, 2 a team,
3 several groups). Anything unknown counts as the middle. Team when several groups are
affected, or a team with a total of 5 or more. Guided when the total is 3 or more, a lot
of money is at stake, or it is hard to undo. Just answer when it is small and easy to
undo. Quick otherwise. A deadline today turns guided or team into quick, with the fuller
mode named as the alternative. A message that is not a choice at all comes back as
`none` with `is_choice: false`.

## Recognising a decision

People rarely announce a decision. Listen for: "should I", "should we", "or" between two
real things, "torn between", "pros and cons", "which is better", "is it worth it", "renew
or buy", "keep or replace", "stay or go", "help me think this through", comparing offers,
quotes, plans, schools or vendors, or a team asking how to change the way something works.

**Offer, don't take over.** Never build files unasked. Call `triage` with their words,
then use its `offer` sentence or your own, for example:

- "Want me to lay the options side by side with what matters to you?"
- "This one's worth a closer look. Want me to ask a few questions and draw it as a map
  you can open?"
- "A few groups are affected. Want me to set up a map everyone can review?"

If they say no, help in the conversation as you normally would.

## Interview

`decisioncraft interview --dir FOLDER --question "their words" --json` returns one
question at a time: `{done: false, question: {id, ask, why, kind, choices?, suggested?},
progress: {asked, remaining}}`. Ask it in your own words, then pass their reply back with
`--answer "..."`. Repeat until `done: true`; the folder then holds `model.json` and
`material/README.txt`, and `next` says what to run. State lives in `FOLDER/interview.json`,
so you can stop and come back. `--next` shows the pending question again; `--reset` starts
over.

It skips what the first sentence already says (options in "renew or buy" are suggested,
and the person is asked if there are others), asks only the core questions when the stakes
are low, and stops at once with `mode: none` for a trivial choice. The question set is
chosen from the first answer: personal, team (an owner, the groups affected, the material)
or system (how it works today and what would change); `--kind` forces one. The full bank:
`decisioncraft://interview-questions` over MCP, or `decisioncraft.interview_questions()`.

At a terminal, `decisioncraft interview --dir FOLDER` and plain `decisioncraft new` run
the whole interview with prompts.

## Personal decisions

For one person or a household (a car, a lease, a job offer, a move, a school), even when
nobody says "decision" ("should I renew my lease or buy?", "is it worth fixing the old
one?"). The personal questions are: the decision, the options including doing nothing,
must-haves and deal-breakers, what matters most first, the deadline, how easy it is to
undo, the budget (only for purchases), who else is affected, what is known and unsure, and
what could change the picture.

The interview writes a `personal-decision` model: a light chain, a today-and-after journey,
a scoring table and cost over time, with personal roles (Money, Practical expert, Safety,
People affected, Future you, Environment, Market and resale, Devil's advocate). The answers
land in the model's top-level fields:

- `options`: each with an id, a name and a short summary. Doing nothing is added if missing.
- `criteria`: must-haves (`kind: must`, pass or fail) and weighted ones (`kind: scored`,
  `weight` 0-5 in half steps; the interview uses 4 for important and 2 for nice).
- `scores`: whole numbers 1-5 with a note and evidence, or `meets: true|false` for a
  must-have. Left empty by the interview: scores need facts.
- `costs`: per option, upfront amounts, yearly items, a loan, and value by year, over
  `horizon_years`, with `cash_return` and `assumptions`.
- `whatifs`: named multipliers by cost kind, tag or `value` (for example petrol 30% dearer).
- `framing`: a pre-mortem ("a year later this went badly, why?") and a 10-10-10 check.

Points worth stating:

- An option failing a must-have is out of the ranking. Totals show one decimal; top
  totals within 0.25 are reported as a close call. Do not add decimals the judgments do not
  have.
- "What would change the winner" is computed, not drafted: the smallest single weight
  change (half steps, within 0-5) or one-point score change that puts another option on top.
- Real cost = money spent + loan still owed - what it is worth + what the cash put down
  could have earned. Use dated public figures for depreciation, fuel, insurance and loan
  rates, and cite each one as evidence.
- Tag costs (for example `miles`, `older-car`) so a what-if touches only what it should.
- `quick --from model.json` reads these fields for a lean in the chat; `render` draws the
  scoring table (with live weights) and cost over time (with break-even points); `words`
  gives both as text tables. Reviews may carry their own `weights`; `merge` reports where
  reviewers disagree.

## Install and check

```
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

Python 3.11 or later. `[smart]` brings the Anthropic and OpenAI SDKs, used when a model
step runs on your API key; `[mcp]` is only for `decisioncraft mcp`. `doctor` checks everything, never
calls a model, and prints exactly what to fix.

## First five minutes

```
decisioncraft                                  # start screen
decisioncraft map ./your-repo --open          # read, draw and open it (see Which model answers)
decisioncraft map ./your-repo --dry-run        # what map would read; no model call
decisioncraft example medical --open           # a finished example in the browser
decisioncraft new                              # asks a few questions, makes a folder
decisioncraft render model.json --open         # draw your model
```

Worked examples: `map` (a made-up bike hire repo, mapped as-is and to-be), `car` (keep,
renew, buy new, buy used or car share, with scores and cost over time), `business` (a
bakery's subscription box), `technical` (moving file uploads), `engineering` (repair or
replace a footbridge), `medical` (a ward's discharge process; not medical advice, no
patient data).

## Deterministic and model-backed

Everything runs with no model and no credentials except `map`, `draft` and `perspectives`
(`map --dry-run` needs none).
`triage` and `quick` also accept `--text` (the person's own words); `triage` reads it with
plain word rules, and both use a model only if you name one (`--complete-cmd` or
`--provider`).

- Deterministic: `triage`, `quick` (with scores), `interview`, `example`, `new`, `render`,
  `doctor`, `session`, `questions`, `merge`, `diff`, `words`, `validate`, `handoff`,
  `discover`, `templates`, `roles`, `manifest`, `mcp`.
- Model-backed: `map` (point it at a repo, notes, a page or a topic), `draft` (material to
  a full model) and `perspectives` (add notes from each role). They cost tokens, differ run to run, check the reply and repair it once,
  and still need a person to read the result.

## Which model answers

`map`, `draft` and `perspectives` need a model. **With an API key set, nothing else is
needed:** `decisioncraft map ./repo --open` picks the model itself and says which on stderr.
The order, first that is set wins: `--provider`/`--model`, then `DECISIONCRAFT_PROVIDER` /
`DECISIONCRAFT_MODEL`, then `decisioncraft config set provider|model ...` (a small file in
your config folder), then whichever key is set, Anthropic first. Defaults: Anthropic
`claude-sonnet-5-5`, trying `claude-opus-5-5` once if a draft still has problems after a
repair; OpenAI `gpt-5.5` (and `gpt-5.5-pro` once, if your account has it). `decisioncraft
doctor` names the model that will answer; `doctor --live` makes one tiny real call to each.
A map of a mid-size repository takes a few minutes and costs about a dollar; the command
prints its estimate first and its token use at the end.

If you are an agent, choose the first that fits:

1. **Write the model yourself** when you can't call your own model from a command (for
   example a coding agent with no MCP sampling). Run `decisioncraft new --question "..."
   --dir NAME --yes` (or finish an `interview`), read `decisioncraft guide` (every field
   of the model, with its rules, plus the writing guide; `--json` for both as Markdown) and
   `decisioncraft templates`, fill in `NAME/model.json` from the material, quoting it as
   evidence, then run `decisioncraft validate NAME/model.json` until it reports no errors.
   Don't read the tool's source code; `guide` is the reference. No model call happens inside Decisioncraft.
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
5. **A vendor SDK.** With `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set and the `[smart]`
   extra installed, no flags are needed. Pin one with `--provider anthropic --model
   claude-sonnet-5-5` (`--model-name` for perspectives) or `decisioncraft config set`.

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

**Point it at anything.** Someone asks "can you show me how this repo works and what's
missing?"

```
decisioncraft map ./the-repo --dry-run --json      # what it will read; no model call
decisioncraft map ./the-repo --dir repo-map --open  # drafts with the model from Which model answers
decisioncraft map ./the-repo --complete-cmd 'python3 my_adapter.py' --dir repo-map --open  # or your own model
```

It reads the README, docs, manifests, schemas, routes and entry points first (respecting
`.gitignore`, within `--budget` characters), numbers every line so claims cite
`path:line`, and stamps the commit it read. The model draws today's way, proposes the
planned way (each replacing box marked), turns the differences into gaps with user stories
and "done when" checks, and adds a note from each of eight roles (UX designer, Architect,
Business analyst, Lead engineer, Product manager, Security and privacy, Customer voice,
AI agent teammate; change with `--roles`). The canvas opens on the planned way with the
notes on the map. Other targets: a notes folder or file, `--page FILE` with a web page's text (or
`--allow-network`), or a topic in quotes with `--answers` (how_today, pain, goal; without
answers the map is marked as unchecked). Over MCP: `decisioncraft_map`, and the `map_this`
prompt.

No model to route? `decisioncraft map ./the-repo --starter --dir repo-map --json` reads the same
files with no model call and writes `repo-map/material/digest.md` (numbered lines to cite as
`path:line`), a starter `repo-map/model.json` (the right template, the eight roles, notes on the
map, opening on the plan) and `repo-map/FILL-IN.md` with the steps. Fill the model in using
`decisioncraft guide`, run `decisioncraft validate repo-map/model.json` until it reports no
errors, then `decisioncraft render repo-map/model.json --open`.

**Talk a choice through, at the right depth.** Someone says "my lease is up in March,
renew it or just buy the car?"

```
decisioncraft triage --text "my lease is up in March, renew it or just buy the car?" --json
# mode: guided -> ask "Want me to ask a few questions and lay it out as a map?"
decisioncraft interview --dir car --question "renew the lease or buy the car?" --json
decisioncraft interview --dir car --answer "also a used car, or keep the old one" --json
# ...repeat with each answer until done: true...
decisioncraft quick --from car/model.json --score "Renew the lease=Monthly cost=3" \
  --score "Buy the car=Monthly cost=4" --json      # a lean in the chat, once scored
decisioncraft render car/model.json --open          # the map
```

For a small choice (`mode: quick`) skip the interview: ask what matters, then
`decisioncraft quick --option A --option B --criterion "must:cost" --criterion "comfort"
--score "A=cost=4" ... --json`, and show `table`, `lean.reason` and `check_first.text`.

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

**Weigh a personal choice.** A lease is ending and the person wants it worked out properly.

```
decisioncraft interview --dir car-choice --question "My lease ends in March: renew, keep or buy?" --json
# answer one question at a time with --answer "..." until done
# then fill scores (1-5 with a note and evidence), costs per option and what-ifs
decisioncraft validate car-choice/model.json
decisioncraft render car-choice/model.json --open
decisioncraft words car-choice/model.json            # scoring table and cost summary as text
decisioncraft quick --from car-choice/model.json --json   # a lean for the chat
```

Or start from the worked example: `decisioncraft example car --open`.

## Templates

- `system-journeys`: numbered steps across the parts of a system or organisation.
- `customer-journey`: phases of a customer's or patient's path, with feelings, pain
  points and moments that matter.
- `service-blueprint`: what the person does, what staff do in front of them and out
  of sight, and what supports it.
- `decision-chain`: source, evidence, decision, intent, spec, plan, work, outcome;
  today and planned.
- `opportunity-tree`: an outcome, the needs that could move it, ideas, and quick tests.
- `scoring-table`: options against must-haves and weighted criteria, with "what would
  change the winner". Usable in any model.
- `cost-over-time`: what each option really costs, year by year, with break-even points
  and what-ifs. Usable in any model.
- `personal-decision`: a starting set, not one map: a light chain, today and after the
  change, a scoring table and cost over time, with personal roles.

A model can hold several maps. `draft --template auto` (the default) chooses suitable
maps from the material.

## Roles

Eight default roles, each with the question it always asks: designer, analyst,
engineer, product owner, security and privacy, customer voice, AI agent teammate and
finance. `new --roles owner,finance,voice` keeps a subset; rename or replace them in the
model's `roles` list (for a hospital, "patient voice" and "clinical lead").

## Starting a decision with a person

For one person or a small choice, start with `triage` and the `interview` (see Modes).
For a team review, begin with `discover`: four opening questions about the choice, purpose, owner and
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
