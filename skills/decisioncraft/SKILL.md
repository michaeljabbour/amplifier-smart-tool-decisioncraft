---
name: decisioncraft
description: Point it at anything (a codebase, a folder of notes, a page or a topic) and get a map of how it works today, how it could work, the gaps as user stories with 'done when' checks, and a note from every role. It also helps someone weigh a choice at the right depth, from a quick side-by-side in the chat to a full team review. Use for 'map this codebase', 'show me how X works', 'as-is and to-be', 'where are the gaps', 'turn these notes into a process map', 'review this process', and whenever someone is weighing options without saying decision, such as 'should I', 'torn between', 'pros and cons', 'which is better', 'renew or buy', 'keep or replace', 'help me think this through', or comparing offers, quotes or vendors. Not for factual questions or trivial picks.
---

# Decisioncraft

Install, then check the setup (it never calls a model):

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

`decisioncraft --version` should print 0.2.0 or later. If a command below is "not a valid
choice" or `--version` is not recognised, an older copy is first on the PATH: upgrade it with
the install line above (add `--force`), then check again.

**First run: which model?** `map`, `draft`, `perspectives` and Ask the experts need a model.
`decisioncraft doctor` says which one applies. In order: an explicit choice wins
(`--provider`/`--model`, `DECISIONCRAFT_PROVIDER`/`DECISIONCRAFT_MODEL`, or `decisioncraft config set`);
otherwise, **inside you (an agent harness), `map` hands the drawing to you**: it writes a digest and a
starter map, you fill it in with your own model, so the user's API key is not billed; outside an agent,
an `ANTHROPIC_API_KEY` (`claude-sonnet-5-5`) or `OPENAI_API_KEY` (`gpt-5.5`) answers and is billed;
`--complete-cmd 'cmd'` routes through any model you name; `map --starter` always works with no model.

Then run `decisioncraft --help` and follow it. It is the full guide and stays correct
when the tool changes. Each command has its own: `decisioncraft <command> --help`.

**To show how something works:** `decisioncraft map <repo, folder, file or "topic"> --dry-run
--json` shows what it will read. Then either:

- run `decisioncraft map TARGET --open` (it uses the model from First run above, or add
  `--complete-cmd 'your-command'`) to draw today's way, the planned way, gaps with user stories
  and "done when" checks, and a note from each role. It takes a few minutes; or
- if you can't route a model, run `decisioncraft map TARGET --starter --dir NAME --json`. It
  writes `NAME/material/digest.md` (numbered lines to cite), a starter `NAME/model.json` and
  `NAME/FILL-IN.md`. Fill the model in yourself using `decisioncraft guide`, then validate and
  render with `--open`. Don't stop at a text summary when someone asked to see the map.

**To help with a choice, start with triage.** When someone seems to be weighing options, run
`decisioncraft triage --text "<their words>" --json` and follow its `mode`:

- `none`: just answer. Build nothing.
- `quick`: ask what matters, score the options with them, run `decisioncraft quick ... --json`
  and show its `table`, `lean` and `check_first` in the chat. No files.
- `guided`: offer first, then `decisioncraft interview --dir NAME --question "..." --json`,
  one question at a time (`--answer "..."` each turn) until `done`, then
  `decisioncraft render NAME/model.json --open`.
- `team`: the same with `--kind team`, then draft, render and review (see `--help`).

**Filling in a model yourself** (no model routing, or after an interview): read
`decisioncraft guide`, which lists every field with its rules, edit `model.json`, and run
`decisioncraft validate` until it reports no errors. You don't need the tool's source.

**Personal and household choices** (a car, a home, a job offer): the interview writes a
`personal-decision` model with must-haves, weighted scores and a computed "what would change
the winner", cost over time with break-even points and what-ifs, a pre-mortem and a
10-10-10 check. Fill scores and costs from evidence; see `decisioncraft example car`.

**Offer, don't take over.** Never build files unasked. Use the `offer` sentence triage
returns, or your own: "Want me to lay the options side by side?" If they say no, help in
the conversation as usual.

Add `--json` to any command for one JSON result (errors included). It never prompts when
stdin is not a terminal. Over MCP (`decisioncraft mcp`) the same steps are
`decisioncraft_map`, `decisioncraft_triage`, `decisioncraft_quick` and
`decisioncraft_interview_next`, plus the prompts `map_this`, `decide`, `compare_options`, `what_could_go_wrong`, `regret_test` and
`review_canvas`. See `docs/HOSTS.md` in the repository for MCP setup.
