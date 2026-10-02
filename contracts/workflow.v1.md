# Starting and finishing a decision (draft)

`discover` returns `decisioncraft-discovery/1`: four opening questions, a few follow-up
questions, and a response shape. The host asks them in conversation and reuses known
answers. It does not force a questionnaire before every small choice.

Discovery answers use `decisioncraft-brief/1` with an `answers` object. Keys are
`decision`, `why`, `owner`, `visual`, and optional `criteria`, `method`, `stakes`.
Values are text. Pass these to `draft` with `--brief`; they guide the map and comparison.

`handoff` returns `decisioncraft-handoff/1`: the review, open questions, the supplied
comparison, proposed user stories with acceptance criteria, an explicit proposed-state
model when available, missing parts, and an `agent_request`.

A local session builds this handoff on Finish review. It writes `handoff.json`,
`user-stories.md`, and, when a proposal exists, `proposed-model.json` and
`proposed-canvas.html`. The waiting CLI or MCP call returns the handoff to its host.
Answers arriving later reopen the review; the host must use the latest completion.
Old handoff files remain a record of that earlier completion, rather than current approval.

Stories come from gap stories. Checks come from `done_when`. Missing requirements are
reported for the host to draft and confirm. Written answers, votes and finishing do not
approve a proposal. Only maps marked `when: planned`, or chains with proposed items,
become the proposed-state view. Current-only items and links are removed.
