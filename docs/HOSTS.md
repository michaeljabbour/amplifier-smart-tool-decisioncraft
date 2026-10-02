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
