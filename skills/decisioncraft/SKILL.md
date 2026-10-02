---
name: decisioncraft
description: Map how a problem works, gather every point of view, and decide together. Builds a zoomable, offline HTML canvas and a plain-text version from a decision model. Use when a decision affects several groups and each should be heard, with a record of why it was decided, before anyone chooses.
---

# Decisioncraft

Install, then check the setup (it never calls a model):

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

Then run `decisioncraft --help` and follow it. It is the full guide and stays correct
when the tool changes. Each command has its own: `decisioncraft <command> --help`.

**Use it when** a decision affects several groups, you need to show how something works
today against a plan, or you want meeting notes and documents turned into a map people
can review. **Don't use it for** a quick yes or no, task tracking, or live co-editing.

Four things worth knowing before you start:

- Add `--json` to any command: one JSON result on stdout, errors included, and `ok` is
  true exactly when the exit code is 0 (1 input, 2 command line, 3 set up first, 4 model
  call failed). It never prompts when stdin is not a terminal.
- Only `draft` and `perspectives` use a model. If you can't call your own model from a
  command, write the model yourself: `decisioncraft new --question "..." --dir NAME --yes`,
  fill in `NAME/model.json` from the material, and run `decisioncraft validate` until it is
  clean. Otherwise route through your model with `--complete-cmd 'your-command'` (it reads
  `{"system", "prompt"}` JSON on stdin and prints the reply), or use `decisioncraft mcp`,
  whose draft tools ask your model through MCP sampling. Never invent evidence.
- To review with the person on this computer, use `decisioncraft session MODEL --dir
  NEW_FOLDER --open --until-finished --json` and read their answers and the `handoff`
  when it finishes. A vote or a finished review is not a decision; the owner decides.
- To chain steps, import the library (`import decisioncraft as dc`) instead of parsing
  command output.

The recipes in `--help` cover: meeting notes to a canvas, a live review, comparing two
versions, merging reviews, and exporting questions to a task list. See `docs/HOSTS.md`
in the repository for MCP setup.
