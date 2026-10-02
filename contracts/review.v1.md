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
  "answers": {"<note id>": {"choice": "agree|change|unsure", "comment": "..."}},
  "dots": {"<note id>": 2},
  "decisions": {"<decision id>": {"owner": "", "status": "", "due": "", "decided_by": "", "decision": ""}}
}
```

## Merged answers

`merge` returns `{"format": "decisioncraft-merged/1", reviewers[], stale_reviews[], questions{}, decisions{}}`.
Per question: `agree`, `change`, `unsure`, `dots`, `comments[{who, text, choice}]`, `split`.
Per decision: each field's values `[{who, value}]` and `conflict[]` naming fields where reviewers differ.
`stale_reviews` names reviewers whose file was made against a different version of the model.
