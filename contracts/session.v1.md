# Local reviews, version 1 (draft)

`session(model, directory, review=None, source_root=None, prepared_by="")` starts a
review server on this computer. It returns a `ReviewSession` with `url`, `info()`,
`status()`, `wait(timeout=None)` and `close()`. No provider SDK or credentials are needed.

The directory contains `review.json` in the existing review format and `session.json`:

```json
{
  "format": "decisioncraft-session/1",
  "url": "local review address",
  "state": "open|finished|closed",
  "version": 0,
  "review_file": "path to review.json",
  "session_file": "path to session.json",
  "status_url": "local status address",
  "finished_at": "ISO time, or empty"
}
```

The URL contains a random access key. Treat the session folder and URL as private.
The server binds only to `127.0.0.1`, checks the host and origin, accepts bounded JSON
requests, and rejects reviews for another model or unknown question. A stale version
returns a conflict instead of replacing newer answers. Review files are replaced
atomically. Source access is restricted to referenced files inside the chosen root.

`GET status_url` includes the current `review`. Browser saves send a review and its
current version to the session's `answers` route. The `finish` route saves the latest
answers and records completion. Completion means the person is ready to return to the
agent; it does not mark any decision as decided. A later edit reopens a running session
and clears its completion time. Closed sessions keep their last review and receipt.

The CLI prints the session details immediately. `--until-finished` waits for completion,
prints the final review, then closes the server. Without it, the session runs until stopped.
The host reads the review directly rather than asking the person to upload it.

This is a local file handoff to the host, not shared live editing or an automatic message
to a remote agent service. Standalone canvases remain offline and retain file export.
