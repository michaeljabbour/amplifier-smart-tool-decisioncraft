---
name: decisioncraft
description: Helps someone weigh a choice at the right depth, from a quick side-by-side in the chat to a short interview and a map to open, or a full map a team reviews with notes from every point of view. Use when a person is weighing options, even without saying "decision" - "should I...", "torn between", "pros and cons", "which is better", "renew or buy", "keep or replace", "help me think this through", comparing job offers, quotes, plans or vendors, or a team changing how something works. Not for factual questions or trivial picks.
---

# Decisioncraft

Install, then check the setup (it never calls a model):

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
decisioncraft doctor
```

Then run `decisioncraft --help` and follow it. It is the full guide and stays correct
when the tool changes. Each command has its own: `decisioncraft <command> --help`.

**Start with triage.** When someone seems to be weighing options, run
`decisioncraft triage --text "<their words>" --json` and follow its `mode`:

- `none`: just answer. Build nothing.
- `quick`: ask what matters, score the options with them, run `decisioncraft quick ... --json`
  and show its `table`, `lean` and `check_first` in the chat. No files.
- `guided`: offer first, then `decisioncraft interview --dir NAME --question "..." --json`,
  one question at a time (`--answer "..."` each turn) until `done`, then
  `decisioncraft render NAME/model.json --open`.
- `team`: the same with `--kind team`, then draft, render and review (see `--help`).

**Offer, don't take over.** Never build files unasked. Use the `offer` sentence triage
returns, or your own: "Want me to lay the options side by side?" If they say no, help in
the conversation as usual.

Add `--json` to any command for one JSON result (errors included). It never prompts when
stdin is not a terminal. Over MCP (`decisioncraft mcp`) the same steps are
`decisioncraft_triage`, `decisioncraft_quick` and `decisioncraft_interview_next`, plus the
prompts `decide`, `compare_options`, `what_could_go_wrong`, `regret_test` and
`review_canvas`. See `docs/HOSTS.md` in the repository for MCP setup.
