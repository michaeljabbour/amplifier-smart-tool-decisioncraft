# Working on Decisioncraft

Read [the vision](docs/VISION.md) and [the contracts](contracts/README.md) before changing
product behaviour. The contracts are drafts. The packaged `SMART_TOOL.md` documents what
is built.

## Architecture

- The library is the product. Every capability lives in `src/decisioncraft/`; the CLI
  reads files, calls the library and prints. Help text comes from the library.
- Deterministic capabilities (manifest, templates, roles, new, validate, render, words,
  questions, merge, diff) must import, run and print help with no credentials and no
  provider SDK installed.
- Model-backed capabilities (draft, perspectives) live in `intelligence.py`. Provider
  SDKs load only when called. Every reply goes through `validate`; one repair, then fail.
- The canvas is one self-contained HTML file: no outside requests, a strict content
  security policy, the model embedded as JSON.

## Writing

- Plain everyday words and short sentences, in code comments, help, examples and UI text.
- No filler words: leverage, seamless, robust, unlock, empower, synergy, cutting-edge,
  game-changer, delve. `scripts/check-generic.py` fails on them.
- Name people by role. Examples are fictional; say so.
- Never add personal details (names, usernames, emails, home paths) or the names of
  products this tool was first built alongside. The check fails on them; keep a local
  list in `.check-generic.local` (gitignored).

## The canvas must need no manual

- One quiet top bar; the list of views on the left; detail on the right.
- Every control has a text label. Shortcuts are optional, behind "? Keys".
- Notes never cover a box's text.
- `scripts/check-canvas.py` runs five first-time-user tasks with visible controls only.
  Keep it passing when changing the canvas.

## Before committing

```sh
uv run pytest
python3 scripts/build-examples.py
python3 scripts/check-generic.py
python3 scripts/check-canvas.py examples/*/canvas*.html   # when the canvas changed
```

Commit in small steps. Do not add a remote or push unless asked.
