# Harness tests

How Decisioncraft behaves when a real coding agent uses it from its skill. Each conversation
was run in a fresh, empty git folder with the skill installed and nothing else. The prompts
were written the way people actually type: vague, partial, sometimes "not sure", with a change
of mind partway through. Agents were driven turn by turn from a terminal multiplexer.

Run for version 0.2.0 on 2026-10-02.

| # | Agent | What the person said | Expected | Result |
|---|---|---|---|---|
| 1 | Claude Code | "my lease is up soon and idk what to do, car's got some issues" | spot a choice; offer; a guided interview one question at a time; cope with "not sure"; a personal-decision map | Pass. Offered first, ran `triage` and `interview`, asked 9 single questions, accepted a change of mind ("drop extending, add used car"), followed up a vague "not too expensive" with "a rough number?", and drew the map without inventing scores it had no facts for. It ended with the three things to find out first. |
| 2 | Codex | "we keep arguing about which payroll vendor, can you help" | team mode; ask who is affected; a canvas | Pass. `triage` chose team, it offered a shared map, ran the team interview, recorded provisional answers as provisional, and drew a map with Finance, HR and the COO as roles. |
| 3 | Amplifier | "pros and cons of taking the new job?", then "just quick pls" | offer; quick table without files | Pass. A scored table, a lean ("stay"), the one thing to check first ("is losing remote days negotiable?"), and an offer to go deeper. No files. |
| 4 | Claude Code | "pizza or tacos tonight?" | a brief answer; nothing built | Pass. One line of opinion and an offer to compare if torn. No files. |
| 5 | Codex | "what year did the first iPhone come out?" | not triggered | Pass. A plain answer; the tool was not called. |
| 6a | Claude Code | "can you show me how this repo works and what's missing?" (a small made-up repo) | `map`; as-is and to-be with stories and notes | Pass after a fix. It ran `map --starter`, filled the model in from the files with `path:line` evidence, validated it and opened the canvas: 10 steps, 5 gaps, a note from each of 8 roles. |
| 6b | Codex | the same | the same | Pass. `--version`, `map --dry-run`, `map --starter`, `guide`, fill in, validate, render: 14 steps (7 planned, each replacing a today step), 6 gaps, 8 roles, 0 validation problems. |

## What the runs changed

The first runs found real problems. Each was fixed and the conversation run again.

- **No way to draw a map without a model.** An agent that could not route its own model
  stopped at a text summary. `map --starter` now writes the reading digest with numbered lines,
  a starter model and plain fill-in steps, and the skill says not to stop at a summary.
- **Agents read the source code to learn the model format.** `decisioncraft guide` now prints
  every field with its rules, plus the writing guide; MCP serves it as a resource.
- **An older copy on the PATH.** One agent's shell found an older install without `triage`.
  The skill now says to check `decisioncraft --version` and how to upgrade.
- **Interview starter models.** A "keep things as they are" option was added even when a lease
  was ending; a money must-have had no measure although a budget was given; "what could
  change" answers were dropped; and an unscored starter produced dozens of warnings. All fixed.
- **Canvas.** A cost map with no costs yet crashed the page; very wide or tall journey maps
  fitted at an unreadable size. Both fixed.

## MCP in a real host (after 0.2.0)

Run on 2026-10-02 with the MCP server registered in the project (`.mcp.json`) beside the skill,
in Claude Code (sonnet) and Codex, from the same small made-up repo.

| # | Agent | What the person said | Expected | Result |
|---|---|---|---|---|
| 7 | Claude Code + MCP | "map this repo and tell me what's missing" | a canvas, even with no model for the server | First run: fail. Claude Code does not offer MCP sampling and this test session had no API key in its environment, so `decisioncraft_map` returned an error and the agent stopped at a text summary. After the fix: `decisioncraft_map` wrote a starter, the agent filled it in from the digest, validated it and rendered `map/canvas.html`. Pass. |
| 8 | Claude Code + MCP | "help me decide whether to keep my car", then vague answers ("idk", "not sure honestly") and a change of mind ("maybe lease something?") | triage, an offer, one question at a time | Pass. It offered a map or a quick comparison, asked one question per turn, suggested options when the person was unsure, and recorded the lease when it came up later. |
| 9 | Codex + skill + MCP | "can you show me how this repo works and what's missing?" | a canvas | Pass. 12 steps, 6 gaps with checks, a note from each of 8 roles, validated and rendered. Opening a browser failed inside the Codex sandbox; the command printed the path instead. |

What this changed:

- **No dead end over MCP.** When the host can't sample and the server has no usable API key,
  `decisioncraft_map` writes a starter (digest, starter model, fill-in steps) instead of failing.
  `starter: true` asks for this directly.
- **Your API key over MCP.** When the host can't sample, model steps use the server's API key
  if it has one. A host started outside your shell (from a dock icon or a terminal multiplexer) may not see your shell's keys; give them explicitly (for
  example `claude mcp add decisioncraft -e ANTHROPIC_API_KEY=... -- decisioncraft mcp`).
- **A missing path is refused,** not mapped as a topic.
- **The server reports its own version** (0.2.0), not the MCP library's, and no longer logs
  every request to stderr.
- **The skill description is one plain line,** so strict and simple frontmatter readers both
  read it whole. (Headless Claude Code lists skill names without descriptions for every skill;
  that is not specific to Decisioncraft.)

## Not covered

- Real-model quality of `map` with `--complete-cmd` or `--provider` was not scored here;
  the agents wrote the models themselves from the digest.
- Phones were not tested.

## False positives: coding questions that must not trigger it (0.2.2)

In a scratch Python repo with the skill installed, each harness got a code-level choice inside a
coding task. The right behaviour is a normal coding answer with no Decisioncraft. Run through Forge
(`delegate claude --model sonnet` and `codex-exec --sandbox read-only`), 2026-10-02.

| Prompt | Claude Code | Codex |
|---|---|---|
| "should I use a map or a list here?" | coding answer, not triggered | coding answer, not triggered |
| "torn between pytest and unittest for this file" | coding answer, not triggered | coding answer, not triggered |
| "keep or replace this regex?" | coding answer, not triggered | coding answer, not triggered |
| "which is better here, async or threads?" | coding answer, not triggered | coding answer, not triggered |
| Control: "my car lease is up in March… keep it or replace it? help me think it through" | offered the guided interview and a map (triggered, as it should) | ran Decisioncraft and asked the first question (triggered, as it should) |

No change to the skill description was needed.

## Skill ZIP in a code sandbox (0.2.3)

From 0.2.3 the build runs this test itself. It adds: `guide` must return the model format,
`example car` must write its files, the untouched starter must fail `validate` (the map is
empty) and `render`, `--allow-empty` must accept it, a filled example must validate and render,
`doctor` must report skill mode, and the ZIP's package files must match a freshly built wheel
(only `mcp_server.py` is left out on purpose). A ZIP with the model format and examples removed
fails 5 of the 17 checks, which is the gap Claude Desktop found in 0.2.2.

| Step | Result |
|---|---|
| deterministic smoke (`manifest`) | pass |
| `guide` returns the model format | pass |
| `example car` writes its files | pass |
| `triage` | pass |
| `quick` with scores | pass |
| `interview --next` | pass |
| `map --starter` on uploaded files | pass |
| untouched starter fails `validate` (empty map) | pass |
| untouched starter passes with `--allow-empty` | pass |
| `render` refuses the empty starter | pass |
| `validate` a filled model (car example) | pass |
| `render` a filled model | pass |
| hand-written empty model is rejected | pass |
| `doctor` reports skill mode | pass |
| plain `map` with no key falls back to the starter | pass |
| matches the wheel's package files | pass |
| no top-level `anthropic` / `openai` / `mcp` imports | pass |

## Skill ZIP in a code sandbox (0.2.2)

`python3 scripts/test-skill-zip.py` unzips `decisioncraft-skill.zip` into a temp folder and runs it
the way a Skills sandbox would: `python3 -I -S` (no site-packages, no user site, no PYTHON*
environment) with networking disabled (any socket connect raises).

| Step | Result |
|---|---|
| deterministic smoke (`manifest`) | pass |
| `triage` | pass |
| `quick` with scores | pass |
| `interview --next` | pass |
| `map --starter` on uploaded files | pass |
| `guide` | pass |
| `validate` a hand-written model | pass (reports its problems) |
| `render` → `canvas.html` | pass |
| plain `map` with no key falls back to the starter | pass |
| no top-level `anthropic` / `openai` / `mcp` imports | pass |

## Claude Desktop extension (0.2.2)

The extension's server (`desktop/src/server.py`, MCPB `uv` runtime) was added to Claude Desktop
through `claude_desktop_config.json` and Claude Desktop was restarted. Its log
(`~/Library/Logs/Claude/mcp-server-decisioncraft.log`) showed: "Server started and connected
successfully", then `initialize`, `tools/list`, `prompts/list` and `resources/list` each answered.
The config was restored afterwards. Installing the `.mcpb` by double-click needs a person and was
not automated.

## Codex (0.2.3)

Codex CLI 0.160, `codex exec --sandbox workspace-write`, in a temporary `CODEX_HOME` holding only
the sign-in, the user's settings without their MCP servers, the skill in `skills/decisioncraft/`,
and `decisioncraft mcp` added with `codex mcp add`. The user's own `~/.codex` was not touched.

| Prompt | What Codex did | Result |
|---|---|---|
| "help me figure out whether to keep or replace my car" (scratch repo) | Read the skill, ran `decisioncraft triage` (guided: a lot at stake, hard to undo), offered to work through it, and asked one question about the car and why replace it. Built no files. | pass |
| "map this repo and tell me what's missing" (a copy of the sample bike-hire repo) | Ran `doctor`, `map . --dry-run`, `map . --starter --dir repo-map`, read `guide`, filled in the model from the digest, validated and rendered `repo-map/canvas.html`, and summarised seven gaps in a table with the key open question. The model validates with 0 problems. | pass |

It used the command line, not the MCP tools: inside Codex the skill's terminal route came first,
which is fine, since both reach the same library. The Codex app shares `~/.codex` with the CLI,
so the same skill and MCP setup apply; the app itself was not driven in this test.

## The canvas in the chat: MCP Apps (0.2.3)

**Reference host.** The MCP Apps reference host (`examples/basic-host` from
modelcontextprotocol/ext-apps, which loads views through a separate-origin sandbox iframe) was
driven headlessly with Playwright against `decisioncraft mcp` served over HTTP. Each tool call
drew the canvas inside the host's iframe, with no console errors:

| Tool call | Result in the host |
|---|---|
| `decisioncraft_render` with the car example | the full canvas: scoring table, cost over time, journeys, 14 questions |
| `decisioncraft_quick` (3 options, a must-have, 3 weighted criteria) | the scoring table with weights, totals and "What would change the winner?" |
| `decisioncraft_render` with Codex's map of the sample bike-hire repo | How it works, Today / Planned / What changes, 7 changes, 8 roles |
| Save my answers in the car canvas | the view called `decisioncraft_save_review` through the host; the review file was written and the canvas said where |

**Claude Desktop.** With a temporary entry in `claude_desktop_config.json` (backed up and
restored byte for byte afterwards), Claude Desktop started the server, sent `initialize`,
`tools/list`, `prompts/list` and `resources/list`, and advertised MCP Apps support in its
`initialize` capabilities: `extensions: {"io.modelcontextprotocol/ui": {"mimeTypes":
["text/html;profile=mcp-app"]}}`. It did not advertise MCP sampling, so in Claude Desktop the
model-backed steps use an API key if one is set, otherwise `decisioncraft_map` hands Claude a
starter to fill in and Claude then calls `decisioncraft_render`, which draws the canvas in the
chat. The view itself is fetched (`resources/read`) only when a visual tool runs in a
conversation; that needs a person and was not automated.
