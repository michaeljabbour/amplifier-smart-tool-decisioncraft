---
smart_tool_format: 1
name: decisioncraft
version: 0.1.0
description: >-
  Map how a problem works, gather every point of view, and decide together.
  Builds a zoomable, offline HTML canvas and a plain-text version from a decision model.
  Use when a decision affects several groups and each should be heard, with a record
  of why it was decided, before anyone chooses.
use_cases:
  - Draft a decision map from meeting notes, interviews, documents or data
  - Run a review where designers, analysts, engineers, owners, security, customers and finance each leave notes that end in a question
  - Merge reviewers' answers to see where people agree and disagree, and rank gaps by impact and effort
  - Compare two versions of a decision to see what changed since the last review
platforms:
  - macos
  - linux
requires:
  - name: ANTHROPIC_API_KEY
    purpose: >-
      `draft` and `perspectives` with --provider anthropic. Without it, those two
      capabilities fail with a clear message; every other capability is unaffected.
    install: https://docs.anthropic.com/en/api/getting-started
    optional: true
  - name: OPENAI_API_KEY
    purpose: >-
      `draft` and `perspectives` with --provider openai. Without it, those two
      capabilities fail with a clear message; every other capability is unaffected.
    install: https://platform.openai.com/docs/quickstart
    optional: true
---
# decisioncraft

Decisioncraft helps a mixed group make one decision well. It draws how the problem
works today and what is planned, puts the evidence next to each claim, and adds notes
from every point of view. Each note ends in a question, so the review ends with a short,
ranked list of things to decide.

**The library is the tool.** `decisioncraft` (the Python package) holds every
capability. The command line reads files, calls the library, and prints or writes the
result.

## When to reach for it

- A decision affects several groups and you want each one heard before you choose.
- You need to show how something works (a service, a system, a patient's path, a
  process) and where it falls short.
- You want a record of why something was decided, with the exact words or numbers
  behind it.

Not for: a quick yes/no between two people, project tracking, or anything that needs a
live shared editor. The canvas is a file you send round; answers come back as files.

## How it works

1. **A model** (JSON) holds the decision: sources, quoted evidence, one or more maps,
   gaps, notes by role, decisions and outcome measures. Start with `new` (by hand) or
   `draft` (from your material, using a language model).
2. **`validate`** checks it: broken links between parts, missing evidence, notes with no
   question, and filler words.
3. **`render`** makes one HTML file. It works offline and makes no requests. Reviewers
   pan and zoom, filter by role, answer questions, place dots on what matters most,
   fill in decision owners and dates, and save their answers as a file.
4. **`merge`** combines those files. Render again with `--reviews` to show tallies.
5. **`diff`** or `render --since` shows what changed before a follow-up review.

## Templates

- `system-journeys`: numbered steps across the parts of a system or organisation.
- `customer-journey`: phases of a customer's or patient's path, with feelings, pain
  points and moments that matter.
- `service-blueprint`: what the person does, what staff do in front of them and out
  of sight, and what supports it.
- `decision-chain`: source, evidence, decision, intent, spec, plan, work, outcome;
  today and planned.
- `opportunity-tree`: an outcome, the needs that could move it, ideas, and quick tests.

A model can hold several maps, for example a journey map and a decision chain.

## Roles

Eight default roles, each with the question it always asks: designer, analyst,
engineer, product owner, security and privacy, customer voice, AI agent teammate and
finance. Replace or rename them in the model's `roles` list (for a hospital, "patient
voice" and "clinical lead"). Roles can list jobs to be done.

## Worked invocations

```
decisioncraft new --template customer-journey --title "Missed pickups" \
  --question "How do we cut missed pickups by half?" --out model.json
decisioncraft validate model.json
decisioncraft render model.json --out canvas.html
decisioncraft merge model.json review-a.json review-b.json --out merged.json
decisioncraft render model.json --merged merged.json --since old-model.json --out canvas.html
decisioncraft words model.json --out model.md
decisioncraft draft notes/*.md --template decision-chain \
  --question "Should we open on Sundays?" --provider anthropic --out model.json
```

## Sharp edges

- `draft` and `perspectives` are model-backed. They need one of `--provider` (with the
  matching API key and the `[smart]` extra installed: `pip install
  'amplifier-smart-tool-decisioncraft[smart]'`) or `--complete-cmd` (a command of your
  own that reads `{system, prompt}` JSON on stdin and prints the reply -- use this to
  route the call through a host's own model setup instead of a vendor SDK). They cost
  tokens and differ run to run. Their output is validated and repaired once, but a
  person must still read it.
- Everything else runs with no model and no credentials.
- Answers in the canvas are kept in the browser on that computer until saved as a file.
- The canvas shows the first glossary term in each piece of text with a dotted line;
  hover, focus or tap it for the meaning.
- Examples in the repository are fictional. The medical example is about how a ward
  organises its work; it is not medical advice and holds no patient data.
