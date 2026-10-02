---
name: decisioncraft
description: Map how a problem works, gather every point of view, and decide together. Builds a zoomable, offline HTML canvas and a plain-text version from a decision model. Use when a decision affects several groups and each should be heard, with a record of why it was decided, before anyone chooses.
---

# Decisioncraft

Install:

```sh
uv tool install "amplifier-smart-tool-decisioncraft[smart] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"
```

Then run `decisioncraft --help` and follow it. Each capability has its own help:
`decisioncraft <capability> --help`.

When you start a review for the person on this computer, use `decisioncraft session`
instead of opening a standalone HTML file. Pass a fresh `--dir`, `--open`, and
`--until-finished`. The answers return directly when the person presses Finish review.
Read the completed review before acting; an unanswered question or vote is not a decision.
Use `--review` to continue earlier responses. Keep session folders outside tracked content.

For a new draft, let `draft` choose suitable maps (the default `--template auto`).
Choose a template explicitly only when the person wants that view. Customer actions,
staff handoffs, current versus proposed work, and alternative choices need different
visuals. Use named links only for relationships the source material establishes.
Do not invent dependencies or loops to make a diagram look complete.

Start a new decision by calling `discover`. Ask its few opening questions in conversation;
reuse earlier answers. Follow up on what matters, how to compare, and the stakes. Store
answers in a private `decisioncraft-brief/1` file and pass it to `draft --brief` when using
the draft capability. Do not ask a long checklist or draw first and explain later.

Agree criteria before assessing alternatives. Compare realistic options using evidence
and a method proportionate to the stakes. Keep uncertainty explicit. The owner makes
and records the choice and its reason; a vote or completed review is not approval.

When a review finishes, read `handoff` from the returned CLI or MCP result. Follow its
`agent_request`: explain the answers, show proposed user stories, acceptance criteria and
a proposed-state map, and draft missing parts for owner review. Do not leave the person
with a download instruction. For an MCP host, use `decisioncraft mcp`; the same flow is
available through its standard tools. See `docs/HOSTS.md` in the checkout.
