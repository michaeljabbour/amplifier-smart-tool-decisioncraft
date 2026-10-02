# Next steps for Decisioncraft

**The decision:** Which next step should we take to learn whether Decisioncraft helps people make a decision?

Proposed order: run a small real decision trial, fix the failures it reveals, then firm up the contracts and release checks. All scores and role notes are agent analysis, not user feedback. No option has been chosen.

**How to read this:** Open the options map, then Gaps and Questions to decide. Compare the four small trials. Scores are tentative: impact means learning value, and effort means relative work, not days. Save your answers to record your preferences. This is an internal planning model; the repository examples it cites are fictional.

_Checked against the sources on 2026-10-01. Checked against local repository revision 3f8aa2e. No user interviews, live provider trials, or release verification were performed for this model._

## Four ways to learn what to do next

These can form a sequence. Choose one primary trial before widening the work.

- Outcome: **A useful decision with reasons attached** (Planned): Choose the smallest trial that reduces the most uncertainty.
  - Need or pain: **The examples show the format; they do not show whether a real group can reach a useful decision.** (Partly there): Evidence and uncertainty
  > “Most decisions that matter affect several groups at once” — docs/VISION.md, Line 3 [E-vision]
  > “The models were written by hand to show the format” — README.md, Line 90 [E-readme]
  > “decisioncraft-review/1” — contracts/review.v1.md, Line 9 [E-review]
    - Idea: **Try one real decision** (Planned): Invite three reviewers from different roles to review one non-sensitive decision. Watch them find evidence, answer questions, vote, save, and merge.
  > “Most decisions that matter affect several groups at once” — docs/VISION.md, Line 3 [E-vision]
  > “The models were written by hand to show the format” — README.md, Line 90 [E-readme]
  > “decisioncraft-review/1” — contracts/review.v1.md, Line 9 [E-review]
    - **Designer note (Must decide): Watch where readers get stuck.** The vision says people should read the file without being shown how. This needs an observed trial.
      We suggest: Record task completion and requests for help.
      Question: Which visible task should each reviewer complete without help?
      > “Most decisions that matter affect several groups at once” — docs/VISION.md, Line 3 [E-vision]
    - **Product owner note (Must decide): Choose one decision.** A narrow trial can reveal what prevents the review from ending in a decision.
      We suggest: Use one decision with an owner and a clear deadline.
      Question: Which real decision and owner should we use for the first trial?
      > “Most decisions that matter affect several groups at once” — docs/VISION.md, Line 3 [E-vision]
    - **Customer voice note (Must decide): Hear from people doing the review.** The examples are handwritten. No user feedback was collected for this planning model.
      We suggest: Ask reviewers what helped them decide and what remained unclear.
      Question: Would reviewers use the file for another decision?
      > “The models were written by hand to show the format” — README.md, Line 90 [E-readme]
      - Quick test: **What would count as success?** (Planned): Three reviewers finish without coaching; the owner records a decision and reason. Record every point where help was needed.
  - Need or pain: **The contracts remain drafts until real callers use them.** (Partly there): Evidence and uncertainty
  > “They are drafts until the shapes have
been used by real callers.” — contracts/README.md, Line 3 [E-contracts]
  > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
    - Idea: **Test the file contracts** (Planned): Have two independent callers create and consume models and review files. Agree on required fields, error messages, and a version-change policy.
  > “They are drafts until the shapes have
been used by real callers.” — contracts/README.md, Line 3 [E-contracts]
  > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
    - **Analyst note (Should decide): Define what success means.** A passing check and a useful decision measure different things. The contract needs real callers.
      We suggest: Keep file validity and decision usefulness as separate measures.
      Question: What failure would make us change the file shape?
      > “They are drafts until the shapes have
been used by real callers.” — contracts/README.md, Line 3 [E-contracts]
      - Quick test: **What would count as success?** (Planned): Both callers exchange files successfully; malformed files fail with useful errors; compatibility rules are written down.
  - Need or pain: **Handwritten examples and supplied-completion tests do not establish the quality of live drafting.** (Partly there): Evidence and uncertainty
  > “The models were written by hand to show the format” — README.md, Line 90 [E-readme]
  > “Every reply is checked by `validate` before it is returned.” — src/decisioncraft/intelligence.py, Line 5 [E-intelligence]
  > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
    - Idea: **Try drafting from real notes** (Planned): Use a redacted notes pack and an explicitly chosen provider and model. Compare the draft with a human reference; check claims, missing roles, questions, repairs, cost, and elapsed time.
  > “The models were written by hand to show the format” — README.md, Line 90 [E-readme]
  > “Every reply is checked by `validate` before it is returned.” — src/decisioncraft/intelligence.py, Line 5 [E-intelligence]
  > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
    - **Security and privacy note (Must decide): Keep trial material suitable to share.** Real notes may contain information that should not be included in a saved canvas or sent to a provider. This is a trial design concern, not evidence of a current leak.
      We suggest: Use redacted material and agree who can receive the output.
      Question: What material is approved for this trial and who may see it?
      > “Every reply is checked by `validate` before it is returned.” — src/decisioncraft/intelligence.py, Line 5 [E-intelligence]
    - **AI agent teammate note (Should decide): Keep a person in charge of claims.** Validation checks the reply shape; it does not establish that a claim is true.
      We suggest: Compare each draft claim with the notes and keep corrections.
      Question: What must a person check before sharing a draft?
      > “Every reply is checked by `validate` before it is returned.” — src/decisioncraft/intelligence.py, Line 5 [E-intelligence]
    - **Finance note (Should decide): Measure work saved.** The draft trial should measure editing time and provider cost; no savings have been measured here.
      We suggest: Set a budget before the trial and compare total work with the manual path.
      Question: What correction time and cost would make drafting worth continuing?
      > “The models were written by hand to show the format” — README.md, Line 90 [E-readme]
      > “Every reply is checked by `validate` before it is returned.” — src/decisioncraft/intelligence.py, Line 5 [E-intelligence]
      - Quick test: **What would count as success?** (Planned): No invented quotes or broken evidence links; a person records correction time and cost and decides whether another trial is worthwhile.
  - Need or pain: **Local deterministic tests cover key commands; that alone does not prove a new user can install and complete a review.** (Partly there): Evidence and uncertainty
  > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
  > “decisioncraft-review/1” — contracts/review.v1.md, Line 9 [E-review]
    - Idea: **Check a fresh installation** (Planned): On a clean supported environment, install a pinned revision, create a model, render, save a review, merge it, and render again. Test the base package without provider SDKs.
  > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
  > “decisioncraft-review/1” — contracts/review.v1.md, Line 9 [E-review]
    - **Engineer note (Should decide): Prove the full path.** The command tests cover many deterministic paths. A fresh install and saved browser review still need their own proof.
      We suggest: Start with the documented install and one complete review.
      Question: Which supported environment should we check first?
      > “def test_cli_deterministic_paths_run_without_credentials(tmp_path):” — tests/test_render_and_cli.py, Line 119 [E-tests]
      > “decisioncraft-review/1” — contracts/review.v1.md, Line 9 [E-review]
      - Quick test: **What would count as success?** (Planned): A first-time user completes the documented path; supported versions and reproducible install instructions are recorded.

## Gaps between today and planned

### gap-trial: Try one real decision (impact 5/5, effort 2/5)
The examples show the format; they do not show whether a real group can reach a useful decision.

- As a product owner, I want a small trial so I can choose the next change from evidence.
  - Done when: Three reviewers finish without coaching; the owner records a decision and reason. Record every point where help was needed.

### gap-contracts-check: Test the file contracts (impact 4/5, effort 3/5)
The contracts remain drafts until real callers use them.

- As a product owner, I want a small trial so I can choose the next change from evidence.
  - Done when: Both callers exchange files successfully; malformed files fail with useful errors; compatibility rules are written down.

### gap-draft-trial: Try drafting from real notes (impact 4/5, effort 3/5)
Handwritten examples and supplied-completion tests do not establish the quality of live drafting.

- As a product owner, I want a small trial so I can choose the next change from evidence.
  - Done when: No invented quotes or broken evidence links; a person records correction time and cost and decides whether another trial is worthwhile.

### gap-release-check: Check a fresh installation (impact 3/5, effort 2/5)
Local deterministic tests cover key commands; that alone does not prove a new user can install and complete a review.

- As a product owner, I want a small trial so I can choose the next change from evidence.
  - Done when: A first-time user completes the documented path; supported versions and reproducible install instructions are recorded.

## Questions to decide

### Must decide
- Which visible task should each reviewer complete without help? (Designer, on Try one real decision)
- Which real decision and owner should we use for the first trial? (Product owner, on Try one real decision)
- What material is approved for this trial and who may see it? (Security and privacy, on Try drafting from real notes)
- Would reviewers use the file for another decision? (Customer voice, on Try one real decision)

### Should decide
- What failure would make us change the file shape? (Analyst, on Test the file contracts)
- Which supported environment should we check first? (Engineer, on Check a fresh installation)
- What must a person check before sharing a draft? (AI agent teammate, on Try drafting from real notes)
- What correction time and cost would make drafting worth continuing? (Finance, on Try drafting from real notes)

## Decisions

### D-next: Which next step should we take to learn whether Decisioncraft helps people make a decision?
Status: Open. Owner: Product owner.
Options: Try one real decision; Test the file contracts; Try drafting from real notes; Check a fresh installation.

## Did it work?

- **Reviewers who complete the first review without coaching** Before: Not measured. Target: 3 of 3 in the first trial; proposed target. Not measured yet.

- **Decision recorded with owner and evidence-backed reason** Before: Not measured. Target: One real decision; proposed target. Not measured yet.

- **Time to prepare, review, and merge the decision file** Before: Not measured. Target: Measure first; agree a target after the trial. Not measured yet.

## Sources

- [vision] docs/VISION.md (document, 2026-10-01)
- [contracts] contracts/README.md (document, 2026-10-01)
- [readme] README.md (document, 2026-10-01)
- [tests] tests/test_render_and_cli.py (code, 2026-10-01)
- [intelligence] src/decisioncraft/intelligence.py (code, 2026-10-01)
- [review] contracts/review.v1.md (document, 2026-10-01)

## Who is speaking

- **Designer**: Will people understand this and find their way without help?
- **Analyst**: Is it clear what must be true, for whom, and how we will measure it?
- **Engineer**: What do we build first, what could break, and how do we test it?
- **Product owner**: What is in the first version, what do we cut, and what does success look like?
- **Security and privacy**: Who can see what, what do we keep, and what happens if it leaks?
- **Customer voice**: Would the people we serve choose this, and would they need a manual?
- **AI agent teammate**: What can an agent do on its own, and what needs a person's OK?
- **Finance**: What does it cost to build and run, and when does it pay back?
