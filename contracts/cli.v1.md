# Command line results, errors and exit codes (draft, v1)

What a script or agent can rely on when it runs `decisioncraft`. The Python library returns
the same data as ordinary values; to chain several steps, call the library instead of
parsing command output.

## Streams

- **stdout** carries the result: JSON, Markdown or HTML, depending on the command.
- **stderr** carries progress lines, notes and errors for people. `-q` silences progress;
  errors are always printed.
- Colour is used only on a terminal, and never when `NO_COLOR` is set, `TERM=dumb`, or
  `--no-color` is given. There are no spinners or redrawn lines.

## Never waiting for input

Only `new` asks questions, and only when stdin and stderr are both terminals and neither
`--yes` nor `--json` was given. Otherwise a missing `--question` fails with exit 2.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Finished. |
| 1 | The input has problems: a missing file, bad JSON, an invalid model or review, a folder that already has files. |
| 2 | The command line is wrong: unknown command or flag, a missing argument, no `--provider` or `--complete-cmd` for a model-backed command. |
| 3 | Something must be set up first: a provider key, a model name, an optional package, write access, a `--complete-cmd` program `doctor` can't find. |
| 4 | A model was asked and the call failed, or its reply was still invalid after one repair. |
| 130 | Stopped with Ctrl-C before finishing. Stopping `render --watch` or `session` with Ctrl-C is a normal end (0). |

## `--json`

`--json` works before or after the command name. It prints exactly one JSON document on
stdout (one per line for the long-running commands below), and `ok` is true exactly when
the exit code is 0.

```json
{
  "ok": true,
  "command": "render",
  "result": {"path": "model/canvas.html", "bytes": 153472, "summary": {"maps": 2, "notes": 33}},
  "files": [{"path": "model/canvas.html", "kind": "canvas"}],
  "next": ["decisioncraft render model/model.json --open"]
}
```

- `command`: the command name (null for a usage error before one was chosen).
- `result`: the command's own result, below. Present on success, and for `validate` and
  `doctor` also on failure (the problem list and the checks).
- `files`: every file written, with `kind` one of `model`, `material`, `review`, `canvas`,
  `words`, `merged`, `handoff`, `readme`. Always a list.
- `next`: suggested follow-up commands, when there are any.

On failure:

```json
{
  "ok": false,
  "command": "render",
  "files": [],
  "error": {
    "code": "invalid_model",
    "message": "The model has 2 problems to fix first.",
    "hint": "Run: decisioncraft validate model.json",
    "file": "model.json",
    "field": "question",
    "problems": [{"level": "error", "path": "question", "message": "Give the model a question."}]
  },
  "exit_code": 1
}
```

`file`, `field` and `problems` appear when they apply.

### Error codes

| Code | Exit | When |
|---|---|---|
| `usage` | 2 | Unknown command or flag, or a required argument is missing. |
| `missing_argument` | 2 | `new` can't ask for `--question`; a model-backed command (`draft`, `perspectives`, `map`) has neither `--provider` nor `--complete-cmd`; `quick` has no options. |
| `file_not_found` | 1 | A file named on the command line does not exist. |
| `not_a_file` | 1 | A folder was given where a file was expected. |
| `bad_json`, `not_text` | 1 | The file is not valid JSON, or not text. |
| `invalid_model` | 1 | The model has errors; `problems` lists them, `field` is the first path. A model with no steps, items, ideas or options (an untouched starter) is an error, "The map is empty", unless `validate` or `render` gets `--allow-empty`. |
| `invalid_input` | 1 | Another input problem: an unknown template or role, a review for another model, a bad `--score`, a web address for `map` with no `--page` or `--allow-network`, a folder with nothing readable. |
| `folder_not_empty`, `already_exists` | 1 | `example` or `new` would overwrite files. |
| `file_error` | 1 | The file could not be read for another reason. |
| `provider_not_configured` | 3 | A provider key, model name or SDK is missing. |
| `host_model` | 3 | Running inside an agent (Codex, Claude Code, Amplifier) with no provider chosen: the agent's own model does this step, so no API key is billed. The hint says how to write the model yourself, or how to choose a provider on purpose. |
| `no_write_access` | 3 | The output folder can't be written. |
| `missing_prerequisite` | 3 | An optional package is needed, for example `mcp`. |
| `missing_resource` | 3 | A file the tool ships with (the model format, an example) is missing from this installation, for example a skill folder built without it. The hint says how to rebuild or where to read it instead. |
| `setup_incomplete` | 3 | `doctor` found something every user needs that is broken. |
| `model_call_failed` | 4 | The provider or `--complete-cmd` failed. |
| `reply_invalid` | 4 | The model's reply was still invalid after one repair. |
| `interrupted` | 130 | Ctrl-C. |
| `unexpected` | 1 | A bug. Run again with `--debug` and report it. |

## Results by command

| Command | `result` |
|---|---|
| `example` | `{directory, example, about, summary}` |
| `new` with `--dir` | `{directory, model}` |
| `new` without `--dir` | the model |
| `render` | `{path, bytes, summary}`; `path` is null only when HTML went to stdout (without `--json`) |
| `doctor` | `{checks: [{id, status: ok/warn/fail, detail, fix}], ready: {deterministic, draft_with_anthropic, draft_with_openai, draft_with_complete_cmd, mcp}, summary}` |
| `validate` | `[{level, path, message}]` |
| `questions` | `[{id, question, role, urgency, ...}]` (see review.v1.md) |
| `words` | `{markdown, path: null}`, or `{path}` with `--out` |
| `merge` | the merged reviews (`decisioncraft-merged/1`) |
| `diff` | `{added, removed, changed}` |
| `handoff` | the handoff (see workflow.v1.md) |
| `draft`, `perspectives` | the model |
| `map` | `{directory, model_path, canvas_path, summary, plan}`; with `--dry-run`, the plan: `{format: "decisioncraft-map-plan/1", kind: repo/folder/file/url/topic, target, question, read: [{path, label, chars, cut}], skipped: [{path, why}], digest, chars, checked: {date, note}, roles: [label], needs: null or {kind: answers/page_text, ...}, model_calls, template}` |
| `triage` | `{format: "decisioncraft-triage/1", mode: none/quick/guided/team, is_choice, label, does, why: [text], alternative: mode or null, stakes: {cost 0-3, reversible 0-2, people 0-3, deadline_days, score}, read_from_text, missing: [{id, question}], offer, next: [command]}` |
| `quick` | `{format: "decisioncraft-quick/1", question, options: [{id, title, total, percent, fails_must: [label], unknown: [label]}] (ranked; options failing a must-have last), criteria: [{id, label, importance: must/important/nice, weight}], scores: {option: {criterion: {score, why}}}, table (Markdown), lean: {option, title, reason, close_call} or null, check_first: {text, why} or null, ask: [text], note, offer_next}` |
| `interview` | Not finished: `{format: "decisioncraft-interview/1", done: false, set: personal/team/system, question: {id, ask, why, kind: text/list/choice, choices?, suggested?, hint?}, progress: {asked, remaining, of}, mode_so_far, known}`. Finished: `{done: true, set, mode, why, model_path (null when mode is none), files, answers, next}`. `files` in the envelope lists model.json and material/README.txt when written. |
| `perspectives --notes` | `{dry_run, asked: [{note, text, on, roles}], replies_added, review}`; `review` is the answers file with replies added (absent with `--dry-run`) |
| `manifest`, `templates`, `roles`, `discover` | the same data the library returns |

`summary` is `{maps, journeys, steps, stages, items, notes, questions, gaps, sources,
evidence, decisions, outcomes}`.

### Long-running commands (JSON Lines)

- `render --watch --json` prints one envelope per drawing with `"event": "rendered"`, or
  `"event": "error"` with `ok: false`, and keeps watching.
- `session --json` prints `"event": "started"` with the local URL, then
  `"event": "finished"` with the completed review when `--until-finished` is given.

Without `--json`, these commands print the same JSON objects unwrapped, as before.

## Output without `--json`

- On a terminal, `validate`, `questions`, `templates`, `roles`, `diff` and `doctor` print
  readable text. When piped, they print plain JSON, so older scripts keep working.
- `render` prints HTML to stdout when piped and no `--out` is given. On a terminal, or with
  `--open`, `--watch` or `--json`, it writes `canvas.html` beside `model.json` (or
  `NAME.html` beside `NAME.json`) and says where.

## Environment

| Variable | Effect |
|---|---|
| `NO_COLOR` | No colour. |
| `DECISIONCRAFT_NO_BROWSER` | `--open` says where the file is instead of opening a browser (for tests and servers). |
| `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` | Used only by `--provider` on `draft` and `perspectives`, and on `triage` and `quick` when they read `--text` with a model. |
