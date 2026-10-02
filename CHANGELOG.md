# Changelog

## 0.2.2 (2026-10-02)

### Works in Claude Desktop and ChatGPT, not only coding agents

- **Claude Desktop extension:** `decisioncraft.mcpb` (built from `desktop/`, MCPB `uv` runtime).
  Double-click to install; Claude Desktop sets up Python and the package. Keys are optional.
- **Skill ZIP:** `decisioncraft-skill.zip` carries the library itself, for Claude (Customize >
  Skills, with Code execution) and ChatGPT Skills. It runs in the host's sandbox with no key, pip
  or network; the host's model writes the map and Decisioncraft checks and draws it. Built by
  `scripts/build-skill-zip.py`, tested by `scripts/test-skill-zip.py`.
- **Install, three ways:** the page and README now say exactly what to do for a coding agent,
  Claude Desktop, or a Skills host, and that chat-only apps can't run it yet.

### No surprise bills inside an agent

- Inside Claude Code, Codex or Amplifier with no explicit model choice, `map` lets the agent
  draw the map with its own model instead of quietly billing `ANTHROPIC_API_KEY` or
  `OPENAI_API_KEY`. Other model steps there say which key they bill. `doctor` reports which
  applies. Hosts can declare themselves with `DECISIONCRAFT_HOST`, or turn this off with
  `DECISIONCRAFT_HOST=none`.

### Shorter README, tested triggers

- The README keeps install, a first map, which model answers, the three depths and the examples;
  the reference sections moved to `docs/GUIDE.md`.
- `docs/HARNESS-TESTS.md` now logs false positives: coding questions in Claude Code and Codex
  that correctly did not trigger the skill.
- The product page title fits narrow phones.

## 0.2.1 (2026-10-02)

### Small fixes

- `quick` refuses a score for an option or criterion it doesn't know, and names the valid ones,
  instead of quietly leaving it out.
- Every model-backed command takes `--model`, including `perspectives` and `session`
  (`--model-name` still works).
- `--open` inside a sandbox prints one plain line when no browser can open, without the
  browser helper's own errors.
- `map ./something-missing` says the path isn't there instead of mapping it as a topic.

### Works with just an API key

- `map`, `draft` and `perspectives` no longer need `--provider` and `--model`. With
  `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set they pick the model and say which on stderr:
  Anthropic `claude-sonnet-5-5` (trying `claude-opus-5-5` once if a draft still has problems),
  or OpenAI `gpt-5.5`. Override with flags, `DECISIONCRAFT_PROVIDER` / `DECISIONCRAFT_MODEL`,
  or the new `decisioncraft config set provider|model ...`.
- `doctor` names the model that will answer and only says "Ready, including drafting" when
  one does. `doctor --live` makes one tiny real call to each provider.

### Maps that finish with real models

- Before, a real-model `map` could run for minutes and then fail: long replies were cut off
  at 16,000 tokens and the cut-off reply was misread, and common model slips failed the whole
  map. Now replies stream with room for a whole model, a cut-off is reported as such, and the
  slips are fixed before checking: evidence kinds such as "code" or "fact", stories written as
  sentences, decision ids that clash with box ids, planned steps drawn in a separate journey,
  effort written as "Medium" or "not sure", line numbers copied into quotes. Quotes that can't
  be found word for word in the material are marked unverified instead of failing the map.
- `map` draws the boxes first, then asks each role for its notes in a separate small call,
  several at once, at lower effort.
- `map` prints its steps as it works, a time and cost estimate before it starts, and the
  token use at the end. Error hints give a command you can copy.

### Easier first run, and MCP that never dead-ends

- README and the Agent Skill open with **First run: which model?**: what to type, in order
  (your API key, a saved choice, `--provider`, your agent's model, or no model with `--starter`).
- The skill installs without a checkout (one `curl` line per host), and `docs/HOSTS.md` gives
  exact setup for Claude Code, Codex, Amplifier and any MCP host, with every tool, prompt and
  resource.
- Over MCP, model steps use the host's model when it can sample, otherwise the server's API
  key. `decisioncraft_map` writes a starter instead of failing when neither is available.
- A path that doesn't exist is refused instead of being mapped as a topic; an unwritable folder
  says so plainly.
- The MCP server reports Decisioncraft's version and logs only warnings.
- The skill description is a single plain line that every skill loader reads whole.

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
