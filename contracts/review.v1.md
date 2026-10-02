# Reviews, version 1 (draft)

## A reviewer's answers

Saved from the canvas with "Share my answers", or made with `review.blank_review`.

```json
{
  "format": "decisioncraft-review/1",
  "model": "title of the model",
  "model_fingerprint": "first 12 characters of the model's SHA-256",
  "reviewer": "Name or role",
  "saved_at": "ISO time",
  "answers": {"<note id>": {"answer": "Written answer", "choice": "agree|change|unsure", "comment": "..."}},
  "dots": {"<note id>": 2},
  "decisions": {"<decision id>": {"owner": "", "status": "", "due": "", "decided_by": "", "decision": ""}},
  "notes": [{
    "id": "R1", "anchor": "<box, gap or 'G1#story-0' id; null for the whole map>", "map": "<map id, for a whole-map note>",
    "text": "A reviewer's rough note", "author": "Name or role", "at": "ISO time",
    "ask": {"roles": ["owner", "voice"], "requested_at": "ISO time"},
    "replies": [{"id": "R1-owner", "role": "owner", "view": "Short view in that role's voice",
                 "question": "One question that could change the choice", "urgency": "must|should|info",
                 "author": "AI assistant", "at": "ISO time"}]
  }]
}
```

### A reviewer's own weights and what-ifs (optional)

When the model has a scoring table, `"weights": {"<criterion id>": 0-5}` holds the weights
this reviewer set with Change the weights (only when they differ from the model's). When the
model has a cost map, `"whatifs": ["<what-if id>", ...]` lists the what-ifs they had switched
on. `merge` collects weights as `weights: {"<criterion id>": [{"who", "weight"}]}` and lists
criteria where reviewers differ by a point or more in `weight_split`, widest first; the
canvas marks those rows "Reviewers disagree" and the text version lists them.

### Reviewers' rough notes and the experts' replies (optional)

`notes` holds a reviewer's own sticky notes, added in the canvas on any box, gap, story
or the whole map. **Ask the experts** records an `ask` with the roles to reply. Replies
arrive in the page when the canvas is served by `decisioncraft session` with a model
(`--complete-cmd` or `--provider`); otherwise the reviewer saves the file and runs
`decisioncraft perspectives MODEL --notes ANSWERS --out replies.json`, or pastes the
copied prompt into their AI agent. Each reply is one role's short view and one question.
Reply questions join the questions to decide, marked as coming from a reviewer note, and
can be answered like any other (keyed by the reply id). `merge` keeps every thread as
`notes[]` with `who`; `render --reviews` shows them; the text version lists them.
Files without `notes` work as before.

## Merged answers

`merge` returns `{"format": "decisioncraft-merged/1", reviewers[], stale_reviews[], questions{}, decisions{}}`.
Per question: `agree`, `change`, `unsure`, `dots`, `comments[{who, text, choice}]`, `split`.
Per decision: each field's values `[{who, value}]` and `conflict[]` naming fields where reviewers differ.
`stale_reviews` names reviewers whose file was made against a different version of the model.

`answer` is optional text. `choice` is an optional view or an expression of uncertainty;
it is not a written answer. Old files with choices and comments still work. Merged
questions also carry `answers[{who, text}]`. Written answers stay separate from view
counts and are not automatically treated as agreement or a final decision.
