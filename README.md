# Decisioncraft

Point Decisioncraft at anything (a codebase, meeting notes, a process or a personal choice) and you get a map of as-is against to-be, the gaps written as user stories, and a sticky note from every role. It's rigorous decision analysis in plain language, from a quick side-by-side to a full team review.

## Install

Pick the line for where you work. Each one sets up the tool and its skill.

| Where you work | What to do |
|---|---|
| **A coding agent with a terminal** (Claude Code, Codex, Amplifier) | Paste: `Install the Decisioncraft tool from https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft by following its README, then run decisioncraft doctor` |
| **Codex** (CLI or app) | Paste the prompt above, or run: `mkdir -p ~/.codex/skills/decisioncraft && curl -fsSL https://raw.githubusercontent.com/michaeljabbour/amplifier-smart-tool-decisioncraft/main/skills/decisioncraft/SKILL.md -o ~/.codex/skills/decisioncraft/SKILL.md`, then `codex mcp add decisioncraft -- decisioncraft mcp` (after the terminal install below). |
| **Claude Desktop** | Download [decisioncraft.mcpb](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/latest/download/decisioncraft.mcpb), double-click it, then choose Install. No key needed: Claude does the drawing, and the canvas opens right in the chat. |
| **Claude or ChatGPT, as a Skill** | Download [decisioncraft-skill.zip](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/latest/download/decisioncraft-skill.zip). Claude: Customize > Skills > + and upload it (turn on Code execution). ChatGPT: Skills > Create, then upload it. |
| **Your own terminal** | `uv tool install "amplifier-smart-tool-decisioncraft[smart,mcp] @ git+https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft"`, then `decisioncraft doctor` |

In Claude Desktop, VS Code Copilot, Cursor and other hosts with MCP Apps, the canvas opens right
in the chat. ChatGPT supports this only for MCP servers on the internet, not local ones. Chat apps
without Skills or local tools can't run Decisioncraft yet; use Codex or Claude Code.
Agents installing from a terminal: install with the `uv tool install` line above, copy
`skills/decisioncraft/SKILL.md` into your skills folder (see [docs/HOSTS.md](docs/HOSTS.md)), then
run `decisioncraft doctor`.

Then point it at something:

```sh
decisioncraft map ./your-repo --open
```

Decisioncraft reads a codebase, a folder of notes, a page or a plain topic. It draws how things
work today and how they could work, turns the differences into user stories with "done when"
checks, and puts a sticky note from each role beside the boxes it is about: designer, architect,
analyst, engineer, product, security, the customer, an AI agent teammate. Every note ends in a
question. For a choice, big or small, it helps at the right depth: a quick table in the chat, a
few questions and a map, or a full team review. The result is one offline file that people can
read without training.

[![A footbridge decision in Planned view: the chain from source to outcome, each box marked, and tilted role-coloured sticky notes beside the boxes they question](docs/images/hero-notes.png)](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/engineering.html)

[![Watch the 90-second trailer: a repo becomes a map, every role leaves a note, what changes, scores and costs, ask the experts](docs/images/trailer-poster.jpg)](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/download/v0.2.0/decisioncraft-trailer-16x9.mp4)

*Above, the footbridge example in Planned view with notes on the map; below it, the trailer.
All examples are fictional. Watch the [90-second trailer](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/download/v0.2.0/decisioncraft-trailer-16x9.mp4) (no sound needed;
[vertical](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/download/v0.2.0/decisioncraft-trailer-9x16.mp4), [square](https://github.com/michaeljabbour/amplifier-smart-tool-decisioncraft/releases/download/v0.2.0/decisioncraft-trailer-1x1.mp4)).*

## Which model answers

**In Claude Desktop, Claude does the thinking. In Codex, Codex does. In a plain terminal, Decisioncraft uses your API key.**

`map` (and `draft`, `perspectives`, Ask the experts) needs a language model. Decisioncraft uses
the first of these that applies, and says which on screen:

1. **Your explicit choice.** `--provider` / `--model` for one run, `DECISIONCRAFT_PROVIDER` /
   `DECISIONCRAFT_MODEL`, or `decisioncraft config set provider openai` once.
   `--complete-cmd 'your-command'` sends each request through any model you name.
2. **The assistant you are working in.** In Claude Desktop (the extension), over MCP, in
   Codex (CLI or app), Claude Code, Amplifier and Skills, the assistant writes the model with its
   own model: Decisioncraft hands it the material, a starter and the format, then checks and
   draws the result. No API key is asked for or billed, even if one is set. (A terminal user who
   wants the server to use a key over MCP sets `DECISIONCRAFT_ALLOW_KEYS=1`.)
3. **An API key you already have**, when run in your own terminal: `ANTHROPIC_API_KEY` gives
   `claude-sonnet-5-5` (trying `claude-opus-5-5` once if a draft still has problems), otherwise
   `OPENAI_API_KEY` gives `gpt-5.5`. This is billed to that key.
4. **No model at all.** `decisioncraft map ./your-repo --starter --dir repo-map` writes what it
   read and a starter map to fill in (`decisioncraft guide` explains each field), then
   `decisioncraft render repo-map/model.json --open`.

`decisioncraft doctor` tells you which one applies. A first map of a small repo takes a few
minutes and about $1 on your own key; `--dry-run` shows what it will read without calling a model.

## Point it at anything

| Point it at | It reads | You get |
|---|---|---|
| a code repository | README, docs, manifests, schemas, routes and entry points, respecting `.gitignore` | today's way with `path:line` evidence, the planned way, gaps as user stories |
| a folder or file of notes, interviews or transcripts | the text, line by line | the same map, quoting the notes |
| a web page | the page's text (only when you allow it, or pass `--page FILE`) | the same map, quoting the page |
| a topic in quotes | two or three answers from you | a first map, clearly marked as not yet checked |

```sh
decisioncraft map ./your-repo --open             # read it, draw it, open it
decisioncraft map ./your-repo --dry-run          # what it will read; no model call
decisioncraft map ./your-repo --complete-cmd 'your-command' --open   # your host's model drafts it
decisioncraft map ./your-repo --starter --dir repo-map   # no model: a digest and a starter to fill in
```

The map opens on the plan with the notes on the map. Switch to **What changes** to see each box
marked New, Changed or Goes away, or **Side by side** to see today and the plan in two panes.
Open any gap for its user stories and "done when" checks.

## Three depths of help

Most choices don't need a map. `triage` says how much help one needs, from four plain things:
how much is at stake, how easy it is to undo, who is affected, and the deadline.

| Mode | For | What happens |
|---|---|---|
| Just answer | small, easy to undo, only you | nothing to build |
| Quick | a real choice that fits in a chat | a scored table, a lean, the one thing to check first; no files |
| Guided | costly or hard to undo | a short interview, one question at a time, then a map to open |
| Team | several groups affected | the full map, every role's notes, reviews and a live session |

```sh
decisioncraft triage --text "my lease is up in March, renew it or just buy the car?"
decisioncraft interview --dir car --question "Renew the lease or buy?"   # one question at a time
decisioncraft quick --option "Renew" --option "Buy" --criterion "must:monthly cost" \
  --criterion "reliability" --score "Renew=monthly cost=3" --score "Buy=monthly cost=4"
```

**How agents recognise it.** The Agent Skill in `skills/decisioncraft/` triggers on "map this
codebase", "show me how X works", "as-is and to-be", "where are the gaps", and on choices that
never use the word decision: "should I…", "torn between", "renew or buy", "keep or replace",
comparing quotes or vendors. It is told to offer, not take over, and to skip factual questions
and trivial picks. We tested this in Claude Code, Codex and Amplifier with vague, real-sounding
prompts; see [docs/HARNESS-TESTS.md](docs/HARNESS-TESTS.md).

## A closer look

| | |
|---|---|
| [![What changes: one map with each box marked New, Changed or Goes away, and a walk through the changes](docs/images/gallery-what-changes.png)](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/engineering.html) **What changes.** One map, every box marked, with a walk through each change and before and after side by side. | [![Side by side: today and the plan for one journey in two panes, only the steps that change](docs/images/gallery-side-by-side.png)](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/medical.html) **Side by side.** One journey at a time, today and the plan in two panes that pan and zoom together. |
| [![Scoring table: must-haves first, a calm heat map with each score written in, weighted totals](docs/images/gallery-scoring.png)](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/personal-car.html) **Scoring table.** Must-haves first, weights you can change live, and "what would change the winner". | [![Cost over time: a line per option over five years with numbered break-even points](docs/images/gallery-costs.png)](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/personal-car.html) **Cost over time.** Real cost per option over 1, 3 or 5 years, break-even points in words, and what-ifs. |
| [![Ask the experts: a reviewer's rough note on a box with replies from each role](docs/images/gallery-ask-experts.png)](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/business.html) **Ask the experts.** Stick a rough note on any box; each role replies with a short view and a question. | **Also:** evidence beside every claim, gaps ranked by impact and effort, decisions with owners and due dates, dot-voting, merged reviews that show agreement and splits, "what changed since last time", and outcomes that feed back as evidence. |

## The examples

All names, quotes and figures are invented, except the cited public figures in the car example.

| Example | The question | Shows | Open it |
|---|---|---|---|
| [map](examples/bike-hire-map/) | How does a small bike hire app work today, and what is missing? Made by pointing `map --starter` at a made-up repo. | as-is / to-be journeys, gaps with stories, a note from every role | [canvas](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/bike-hire-map.html) |
| [car](examples/personal-car/) | When the lease ends: keep, renew, buy new, buy used, or go car-free? | scoring table, cost over time with what-ifs, today and after, pre-mortem | [canvas](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/personal-car.html) |
| [business](examples/business/) | Should a three-shop bakery offer a monthly box? Includes two reviews, rough notes and expert replies. | customer journey, service blueprint, decision chain | [canvas](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/business.html) |
| [technical](examples/technical/) | Move file uploads to a new storage provider, change how uploads reach storage, or both? Includes an earlier version. | system journeys, opportunity tree, what changed | [canvas](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/technical.html) |
| [engineering](examples/engineering/) | Repair, replace, or replace a footbridge with a wider one? | decision chain, system journeys, service blueprint | [canvas](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/engineering.html) |
| [medical](examples/medical/) | How should a ward change the way it sends patients home, so fewer come back? **Not medical advice; no patient data.** | customer journey, service blueprint | [canvas](https://michaeljabbour.github.io/amplifier-smart-tool-decisioncraft/examples/medical.html) |

`decisioncraft example NAME --open` copies any of them (`map`, `car`, `business`, `technical`,
`engineering`, `medical`). Rebuild every output with `python3 scripts/build-examples.py`.

## More

- [The guide](docs/GUIDE.md): install details, using it from your agent, a longer quick start,
  reviews (live and offline), personal decisions, roles and templates, what needs a model, limits.
- [Hosts](docs/HOSTS.md): exact setup for Claude Code, Codex, Amplifier, Claude Desktop and any
  MCP host. [Harness tests](docs/HARNESS-TESTS.md): how agents behaved with real, vague prompts.
- [Changelog](CHANGELOG.md).

## Development

```sh
uv run pytest                                   # tests
python3 scripts/check-generic.py                # no personal details, product names or filler words
python3 scripts/build-examples.py               # rebuild example outputs
python3 scripts/check-canvas.py examples/*/canvas*.html   # first-time-user checks (needs Playwright)
python3 scripts/check-review-flow.py                     # save and merge a written answer
python3 scripts/check-session-flow.py                    # local answers reach the agent
```

See [AGENTS.md](AGENTS.md), [the vision](docs/VISION.md) and [the contracts](contracts/README.md).
The product page lives in [site/](site/README.md).

## License

MIT. See [LICENSE](LICENSE).
