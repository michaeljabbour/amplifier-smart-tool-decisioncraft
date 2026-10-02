# Harness tests

How Decisioncraft behaves when a real coding agent uses it from its skill. Each conversation
was run in a fresh, empty git folder with the skill installed and nothing else. The prompts
were written the way people actually type: vague, partial, sometimes "not sure", with a change
of mind partway through. Agents were driven turn by turn from a terminal multiplexer.

Run for version 0.2.0 on 2026-10-02.

| # | Agent | What the person said | Expected | Result |
|---|---|---|---|---|
| 1 | Claude Code | "my lease is up soon and idk what to do, car's got some issues" | spot a choice; offer; a guided interview one question at a time; cope with "not sure"; a personal-decision map | Pass. Offered first, ran `triage` and `interview`, asked 9 single questions, accepted a change of mind ("drop extending, add used car"), followed up a vague "not too expensive" with "a rough number?", and drew the map without inventing scores it had no facts for. It ended with the three things to find out first. |
| 2 | Codex | "we keep arguing about which payroll vendor, can you help" | team mode; ask who is affected; a canvas | Pass. `triage` chose team, it offered a shared map, ran the team interview, recorded provisional answers as provisional, and drew a map with Finance, HR and the COO as roles. |
| 3 | Amplifier | "pros and cons of taking the new job?", then "just quick pls" | offer; quick table without files | Pass. A scored table, a lean ("stay"), the one thing to check first ("is losing remote days negotiable?"), and an offer to go deeper. No files. |
| 4 | Claude Code | "pizza or tacos tonight?" | a brief answer; nothing built | Pass. One line of opinion and an offer to compare if torn. No files. |
| 5 | Codex | "what year did the first iPhone come out?" | not triggered | Pass. A plain answer; the tool was not called. |
| 6a | Claude Code | "can you show me how this repo works and what's missing?" (a small made-up repo) | `map`; as-is and to-be with stories and notes | Pass after a fix. It ran `map --starter`, filled the model in from the files with `path:line` evidence, validated it and opened the canvas: 10 steps, 5 gaps, a note from each of 8 roles. |
| 6b | Codex | the same | the same | Pass. `--version`, `map --dry-run`, `map --starter`, `guide`, fill in, validate, render: 14 steps (7 planned, each replacing a today step), 6 gaps, 8 roles, 0 validation problems. |

## What the runs changed

The first runs found real problems. Each was fixed and the conversation run again.

- **No way to draw a map without a model.** An agent that could not route its own model
  stopped at a text summary. `map --starter` now writes the reading digest with numbered lines,
  a starter model and plain fill-in steps, and the skill says not to stop at a summary.
- **Agents read the source code to learn the model format.** `decisioncraft guide` now prints
  every field with its rules, plus the writing guide; MCP serves it as a resource.
- **An older copy on the PATH.** One agent's shell found an older install without `triage`.
  The skill now says to check `decisioncraft --version` and how to upgrade.
- **Interview starter models.** A "keep things as they are" option was added even when a lease
  was ending; a money must-have had no measure although a budget was given; "what could
  change" answers were dropped; and an unscored starter produced dozens of warnings. All fixed.
- **Canvas.** A cost map with no costs yet crashed the page; very wide or tall journey maps
  fitted at an unreadable size. Both fixed.

## Not covered

- Real-model quality of `map` with `--complete-cmd` or `--provider` was not scored here;
  the agents wrote the models themselves from the digest.
- Phones were not tested.
