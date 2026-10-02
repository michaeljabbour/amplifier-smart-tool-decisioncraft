# Changelog

## 0.2.0 (2026-10-02)

### Point it at anything

- `decisioncraft map TARGET` reads a code repository, a folder or file of notes, a web page
  (only when allowed) or a plain topic, and draws today's way with evidence by file and line,
  the planned way, gaps as user stories with "done when" checks, and a note from each of eight
  roles. The map opens on the plan with the notes on the map.
- `map --dry-run` shows what it would read. `map --starter` writes the reading digest, a
  starter model and fill-in steps, for an agent that can't route a model.
- A repo's map is named after its README heading.

### The right depth of help

- Four modes: just answer, quick, guided and team. `triage` picks one from what is at stake,
  how easy it is to undo, who is affected and the deadline, and always suggests an offer
  rather than taking over.
- `interview` asks one question at a time, keeps its place in the decision folder, suggests
  options it can read from the first sentence, and stops early for small choices.
- `quick` gives a small scored table, a lean and the one thing to check first, with no files.
- The Agent Skill now triggers on natural talk ("should I…", "torn between", "renew or buy",
  "map this codebase", "as-is and to-be") and not on factual questions or trivial picks.

### Personal decisions

- New `personal-decision` template: a light chain, today and after the change, a scoring table
  and cost over time, with personal roles.
- Scoring table: must-haves first, weighted scores, live weights, and "what would change the
  winner" computed rather than guessed. Reviewers' weights merge, and splits are shown.
- Cost over time: real cost per option over 1, 3 or 5 years, break-even points in words, and
  what-ifs. Pre-mortem and 10-10-10 framing.
- A car example built on real published figures for a fictional family.

### The canvas

- Today, Planned, What changes and Side by side as plain buttons. What changes marks every box
  New, Changed or Goes away, with a walk through the changes and before and after.
- Side by side shows one journey at a time, only the steps that change by default.
- Role-coloured sticky notes beside the boxes, a purple-and-yellow chain with verbs, swimlane
  journeys, a walk-through for each journey, lane descriptions, gap design notes, "not sure"
  and add-on tags, kind labels, chain bands and a "before" column.
- Rough notes on any box, and Ask the experts: each chosen role replies with a view and a
  question, live in a session or later with `perspectives --notes`.
- Whole maps fit at a readable size; a cost map with no costs yet explains what to add.

### For agents and scripts

- `--json` on every command, stable error codes and exit codes, no prompts without a terminal.
- `decisioncraft guide` prints the model format and writing guide.
- MCP: tools for map, triage, quick, interview and review notes; prompts `map_this`, `decide`,
  `compare_options`, `what_could_go_wrong`, `regret_test`, `review_canvas`; resources for
  templates, roles, the model format, the writing guide, the question bank and examples.
- `example NAME` now includes `car` and `map`; `doctor` checks setup; start screen and short
  help screens fit a narrow terminal.
- Tested in Claude Code, Codex and Amplifier with vague prompts; see
  [docs/HARNESS-TESTS.md](docs/HARNESS-TESTS.md).

## 0.1.0 (2026-10-01)

First release: decision models, the canvas, reviews, merge and diff, four worked examples.
