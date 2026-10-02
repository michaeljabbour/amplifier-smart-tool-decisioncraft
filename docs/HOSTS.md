# Use Decisioncraft from an agent

Decisioncraft gives an agent two things: an **Agent Skill** that tells it when to reach for the
tool, and an optional **MCP server** that exposes the same capabilities as tools, prompts and
resources. Use the skill on its own (the agent runs the `decisioncraft` command), the MCP
server on its own, or both.

## Install once

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

`decisioncraft --version` should print 0.2.0 or later. If an older copy is first on the PATH,
run the install line again with `--force`.

## Claude Code

```sh
mkdir -p ~/.claude/skills/decisioncraft && curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-smart-tool-decisioncraft/main/skills/decisioncraft/SKILL.md \
  -o ~/.claude/skills/decisioncraft/SKILL.md            # the skill, for every project
claude mcp add decisioncraft -- decisioncraft mcp                            # the MCP server (add --scope user for every project)
```

Use `.claude/skills/` inside a project to install the skill for that project only. From a
checkout, `cp -R skills/decisioncraft ~/.claude/skills/` does the same.

## Codex

```sh
mkdir -p ~/.codex/skills/decisioncraft && curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-smart-tool-decisioncraft/main/skills/decisioncraft/SKILL.md \
  -o ~/.codex/skills/decisioncraft/SKILL.md
codex mcp add decisioncraft -- decisioncraft mcp
```

The Codex CLI and the Codex app read the same `~/.codex` folder, so these lines set up both:
the skill in `~/.codex/skills/` and the MCP server in `~/.codex/config.toml`. Codex has a
terminal, so you can also paste the install prompt from the README and let it do this. Inside
Codex, `map` lets Codex's own model fill in the map (no API key is billed) unless you choose a
provider. Tested with Codex CLI 0.160; see docs/HARNESS-TESTS.md.

Older Codex versions without skills: paste the body of `skills/decisioncraft/SKILL.md` into
your `AGENTS.md`, or point `AGENTS.md` at it.

## Amplifier

Put the skill in `~/.amplifier/skills/decisioncraft/SKILL.md` (everyone) or
`.amplifier/skills/decisioncraft/SKILL.md` (one project), or list the folder in a bundle's
skills:

```sh
mkdir -p ~/.amplifier/skills/decisioncraft && curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-smart-tool-decisioncraft/main/skills/decisioncraft/SKILL.md \
  -o ~/.amplifier/skills/decisioncraft/SKILL.md
```

## Claude Desktop

**One click:** download [decisioncraft.mcpb](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/latest/download/decisioncraft.mcpb),
double-click it and choose Install. The canvas then opens right in the chat when Claude maps,
compares or draws something. Claude Desktop installs Python and the package itself (MCPB
`uv` runtime). API keys in the extension settings are optional: without one, `decisioncraft_map`
writes a starter and Claude fills in the map with its own model. Built from `desktop/`
(`npx -y @anthropic-ai/mcpb pack desktop dist/decisioncraft.mcpb`).

**By hand:** add this to `~/Library/Application Support/Claude/claude_desktop_config.json`
(Windows: `%APPDATA%\Claude\claude_desktop_config.json`), then quit and reopen Claude Desktop.
Claude Desktop does not read your shell's PATH, so give `uvx` its full path (`which uvx`):

```json
{
  "mcpServers": {
    "decisioncraft": {
      "command": "/full/path/to/uvx",
      "args": ["--from", "amplifier-smart-tool-decisioncraft[mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft", "decisioncraft", "mcp"],
      "env": {"DECISIONCRAFT_HOST": "Claude Desktop"}
    }
  }
}
```

**As a Skill (also claude.ai and ChatGPT):** download
[decisioncraft-skill.zip](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/latest/download/decisioncraft-skill.zip). Claude:
Customize > Skills > + and upload it, with Code execution turned on. ChatGPT: Skills > Create,
then upload it. The skill carries the library itself and runs in the host's code sandbox with no
key, pip or network: the host's model writes the map, Decisioncraft checks and draws it, and the
canvas comes back as a file to download. Build it with `python3 scripts/build-skill-zip.py`.

ChatGPT connects only to MCP servers on the internet, not local ones, so the local server does
not reach it; use the Skill, or Codex.

## Any other MCP host

Run `decisioncraft mcp` as a stdio server. In a host that uses an `mcpServers` config:

```json
{
  "mcpServers": {
    "decisioncraft": {
      "command": "/absolute/path/to/decisioncraft",
      "args": ["mcp"]
    }
  }
}
```

Use the installed executable's full path (`command -v decisioncraft`) if the host does not
inherit your shell's PATH. Relative paths given to the tools are read from the folder the host
starts the server in; pass absolute paths when unsure.

## Which model answers over MCP

Claude Desktop (checked with version current on 2 October 2026) offers MCP Apps but not MCP
sampling, so without an API key in the extension settings, `decisioncraft_map` hands Claude a
starter to fill in with its own model, and the finished map is drawn in the chat by
`decisioncraft_render`.

`decisioncraft_map`, `decisioncraft_draft`, `decisioncraft_perspectives` and
`decisioncraft_review_notes` need a language model. The server tries, in order:

1. **The host's own model**, through MCP sampling, when the host offers it.
2. **Your API key**, when the host can't sample: the same choice as the command line
   (`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`, or `DECISIONCRAFT_PROVIDER` and
   `DECISIONCRAFT_MODEL`). The server must see these variables; with `claude mcp add`, pass
   them with `-e NAME=value` if your host does not inherit your shell. Each result says what
   answered in `drafted_with`.
3. **Neither:** the tool fails and says what to do. The agent then writes the model itself:
   `decisioncraft_map` with `dry_run` shows the material, the `decisioncraft://model-format`
   resource and `decisioncraft_templates` give the fields, and `decisioncraft_validate` and
   `decisioncraft_render` check and draw it.

Outside MCP, `--complete-cmd 'your-command'` routes the command line through your own model:
the command reads `{"system", "prompt"}` JSON on stdin and prints the reply.

## What the server offers

**Start here:** `decisioncraft_map` (point it at a repo, folder, file, page text or topic),
`decisioncraft_triage` (how much help a choice needs), `decisioncraft_quick` (a scored table in
the chat), `decisioncraft_interview_next` (one question at a time).

**Model-backed:** `decisioncraft_map`, `decisioncraft_draft`, `decisioncraft_perspectives`,
`decisioncraft_review_notes` (expert replies to reviewers' rough notes).

**No model needed:** `decisioncraft_discover`, `decisioncraft_templates`,
`decisioncraft_validate`, `decisioncraft_render` (writes an HTML canvas and returns its path),
`decisioncraft_words`, `decisioncraft_questions`, `decisioncraft_merge`, `decisioncraft_diff`,
`decisioncraft_example` (by id: map, car, business, technical, engineering, medical).

**Live review:** `decisioncraft_start_review`, `decisioncraft_wait_for_review` (bounded; repeat
while the state is open), `decisioncraft_handoff`, `decisioncraft_close_review`.

**Prompts:** `map_this`, `decide`, `compare_options`, `what_could_go_wrong`, `regret_test`,
`review_canvas`.

**Resources:** `decisioncraft://templates`, `decisioncraft://roles`,
`decisioncraft://model-format`, `decisioncraft://writing-guide`,
`decisioncraft://interview-questions`, `decisioncraft://modes`, `decisioncraft://examples`.

**The canvas in the chat (MCP Apps):** `ui://decisioncraft/canvas.html` (MIME type
`text/html;profile=mcp-app`) is the canvas as an MCP App view. `decisioncraft_render`,
`decisioncraft_map`, `decisioncraft_example` and `decisioncraft_quick` declare it
(`_meta.ui.resourceUri`), so hosts that support MCP Apps draw the result right in the chat:
today and planned, what changes, scores and every role's notes. The view's Save my answers
calls `decisioncraft_save_review` (visible only to the view; it writes the review to
`~/Decisioncraft/reviews/` and returns the path), and Ask the experts calls
`decisioncraft_review_notes` through the host. The view makes no outside requests. Hosts
without MCP Apps get the same tools with a short text result and the canvas file path.

## The canvas right in the chat

In Claude Desktop and claude.ai, VS Code Copilot, Cursor, Goose and other hosts that support
MCP Apps, the canvas opens inside the conversation when one of those tools runs. ChatGPT
supports MCP Apps too, but only for MCP servers on the internet (developer mode connectors), not
local ones like `decisioncraft mcp`. Everywhere else, the tools return the canvas file path to
open in a browser.

## The agent workflow

1. **Showing how something works:** call `decisioncraft_map` (or run `decisioncraft map TARGET
   --open`). Open the canvas it returns.
2. **Weighing a choice:** call `decisioncraft_triage` with the person's words and follow its
   `mode`: just answer, a quick table, a guided interview, or a team review. Offer before
   building anything.
3. **Team review:** draft or write the model, validate it, start a review, wait for the person,
   then read the handoff: show stories, acceptance criteria and the proposed map, name what is
   missing, and help the owner record a reasoned choice.

MCP returns both structured content and a text JSON version. Completion returns through the
waiting tool call; it does not send an unsolicited message to an idle host. The review service
binds only to this computer.
