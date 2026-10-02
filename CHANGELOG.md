# Changelog

## 0.2.3 (2026-10-02)

### The canvas opens in the chat, the skill ZIP is the whole tool, and an empty map no longer passes

- **The host is the model.** In Claude Desktop, Claude does the thinking. In Codex, Codex does.
  In a plain terminal, Decisioncraft uses your API key. The Claude Desktop extension no longer
  has API-key fields: its install asks for nothing, and it reads no key. Over MCP,
  `decisioncraft_map`, `decisioncraft_draft`, `decisioncraft_perspectives` and
  `decisioncraft_review_notes` no longer call a provider: each returns a task for the calling
  assistant (the material or digest with path:line evidence, a starter, the model format and the
  writing rules), and the assistant writes the model and calls `decisioncraft_render`, which
  validates it and shows the canvas. The server samples only with `DECISIONCRAFT_ALLOW_SAMPLING=1`
  and reads keys only with `DECISIONCRAFT_ALLOW_KEYS=1`. On the command line inside Codex (CLI
  or app), Claude Code or Amplifier, `draft`, `perspectives` and review notes stop with
  `host_model` and point at `decisioncraft guide` instead of billing a key; `map` hands the agent
  a starter, as before. Codex is now detected first, from the markers both the CLI and the
  Codex app set (`CODEX_THREAD_ID`, `CODEX_SANDBOX`, `CODEX_CI`), and `doctor` there says
  "Codex's own model does the thinking; no keys needed."
- **The canvas right in the chat (MCP Apps).** `decisioncraft mcp` now serves the canvas as an
  MCP App view (`ui://decisioncraft/canvas.html`, `text/html;profile=mcp-app`). `render`,
  `map`, `example` and `quick` declare it, so Claude Desktop and claude.ai, VS Code Copilot,
  Cursor, Goose and other hosts that support MCP Apps draw today and planned, what changes,
  scores and every role's notes inside the conversation, instead of a Markdown table. `quick`
  results come with a scoring-table model for the view. The view makes no outside requests; its
  Save my answers goes to a new view-only tool, `decisioncraft_save_review` (written to
  `~/Decisioncraft/reviews/` or `DECISIONCRAFT_REVIEWS_DIR`), and Ask the experts calls
  `decisioncraft_review_notes` through the host. Hosts without MCP Apps get a short text result
  and the canvas file path. ChatGPT supports MCP Apps only for servers on the internet.
- **Hosts know when to reach for it.** The MCP server's instructions now open with when to use
  Decisioncraft (renew or buy, keep or replace, job offers, vendors; how something works,
  as-is and to-be, gaps) and when not to (factual questions, trivial picks, code-level choices),
  and the main tools' descriptions lead with the same plain phrases. Found by Claude Desktop
  answering "my lease ends in March, help me think it through" on its own.
- **"What would change the winner" says each change once.** Two challengers suggesting the same
  change no longer list it twice, in the canvas and in the library.

Found by Claude Desktop reviewing the 0.2.2 downloads.

- **The skill ZIP was missing files the library reads.** `guide` returned an empty model format
  and `example car` failed with "Can't find the file". The build now copies everything the
  wheel adds to the package (the model format and the six worked examples, as models, material
  and reviews; canvases are drawn on demand), and ends with a smoke test that unzips the ZIP,
  runs `guide`, `example car` and the key commands offline with a bare interpreter, and compares
  its files with a freshly built wheel. A ZIP missing anything fails the build.
- **`guide` and `example` fail loudly.** A missing model format or example is now an error
  (`missing_resource`, exit 3) that names the file and says how to fix it, instead of an empty
  result or a bare "Can't find the file".
- **An untouched starter is not a finished map.** `validate` and `render` now fail on a model
  with no steps, items, ideas or options ("The map is empty"), so an agent can't hand someone a
  blank canvas while the tool reports success. `--allow-empty` checks or draws an unfinished
  starter on purpose. FILL-IN.md and the skill say so. Drafts from a model that come back empty
  get a repair turn.
- **`doctor` in skill mode** reports "Skill mode: your host's model does the thinking; no keys
  or installs needed" instead of suggesting provider installs the skill never needs.
- **Codex, documented and tested:** the Codex CLI and the Codex app read the same `~/.codex`
  skills folder and `config.toml`. Install the skill with one `curl` line and the MCP server
  with `codex mcp add decisioncraft -- decisioncraft mcp`; the terminal install prompt also
  works, because Codex has a terminal.

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
