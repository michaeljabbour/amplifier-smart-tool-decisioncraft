"""Self-description: the manifest, the tool's skill, and one skill per capability.

Available without credentials and without loading any provider.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata as _metadata
from importlib.resources import files

from .model import templates

NAME = "decisioncraft"
VERSION = "0.1.0"

CAPABILITIES: dict[str, dict] = {
    "map": {
        "kind": "model-backed",
        "summary": "Point it at anything: a repo, notes, a page or a topic. Get an as-is / to-be map.",
        "when": "When someone wants to see how something works and what is missing: 'map this "
        "codebase', 'show me how X works', 'as-is and to-be', 'where are the gaps', 'turn these notes "
        "into a process map'. It reads the target (deterministic), then a model draws today's way with "
        "evidence by file and line, proposes the planned way, turns differences into gaps with user "
        "stories and 'done when' checks, and adds a note from each role. --dry-run shows what it would "
        "read, with no model call.",
        "args": [
            ("target", "A code repository or folder, a notes folder or file (md, txt, html, pdf if pypdf "
             "is installed), a web address, or a topic in quotes."),
            ("--dry-run", "Show what would be read and asked; no model call."),
            ("--question", "The question the map answers (default: how it works today and what is missing)."),
            ("--roles", "Comma-separated role ids (default: designer, architect, analyst, engineer, owner, "
             "security, voice, agent)."),
            ("--answers", "For a topic: a JSON file answering how_today, pain and goal."),
            ("--page", "For a web address: a text file with the page's text, fetched by your host."),
            ("--allow-network", "For a web address: let Decisioncraft fetch that one page itself."),
            ("--budget", "Most characters to read (default 120000)."),
            ("--dir", "Folder for model.json and canvas.html (default: ./decisioncraft-map-NAME)."),
            ("--open", "Open the canvas when it is ready."),
            ("--provider / --model / --complete-cmd", "Which model draws (one is required unless --dry-run)."),
        ],
        "example": "decisioncraft map ./your-repo --complete-cmd 'my-host complete' --open",
        "result": "A folder with model.json and canvas.html (notes on the map, What changes view). "
        "With --json: {directory, model_path, canvas_path, summary, plan}; with --dry-run: the plan "
        "{kind, read[], skipped[], chars, roles[], needs, model_calls}.",
        "fails": "No model named (exit 2); a web address with no --page and no --allow-network, or a "
        "folder with nothing readable (exit 1); a provider with no key (exit 3); a model reply that "
        "stays invalid after one repair (exit 4).",
    },
    "example": {
        "kind": "deterministic",
        "summary": "Copy a worked example into a folder and draw it.",
        "when": "To see what a finished decision map looks like before starting your own, "
        "or to try the commands on real-looking material.",
        "args": [
            ("name", "business, technical, engineering or medical."),
            ("--out", "Folder to create (default: ./decisioncraft-example-<name>)."),
            ("--open", "Open the canvas in your browser when it is ready."),
            ("--force", "Write into the folder even if it already has files."),
        ],
        "example": "decisioncraft example medical --open",
        "result": "A folder with model.json, the material it cites, canvas.html and in-words.md. "
        "With --json: {directory, files, summary}.",
        "fails": "Unknown example name (exit 2); the folder already has files and --force was "
        "not given (exit 1); the folder can't be written (exit 3).",
    },
    "doctor": {
        "kind": "deterministic",
        "summary": "Check your setup and say exactly what to fix.",
        "when": "After installing, before drafting with a model, or when something fails and "
        "you are not sure why. It never calls a model.",
        "args": [
            ("--dir", "Folder you plan to write into (default: the current folder)."),
            ("--complete-cmd", "A host command you plan to route model calls through; "
             "its program is looked up, not run."),
        ],
        "example": "decisioncraft doctor --complete-cmd 'my-host complete'",
        "result": "One line per check (Python, write access, provider packages and keys, "
        "--complete-cmd, MCP) with what to fix. With --json: {checks, ready, summary}.",
        "fails": "Exit 3 when something every user needs is broken (old Python, no write "
        "access, or a --complete-cmd program that can't be found). Optional parts only warn.",
    },
    "mcp": {
        "kind": "deterministic", "summary": "Serve the same decision workflow to an MCP host over stdio.",
        "when": "For any host that supports a local MCP server.", "args": [],
        "example": "decisioncraft mcp", "result": "Standard tools for discovery, map shapes, validation, review, waiting for completion and agent handoff.",
        "fails": "The optional mcp extra is not installed (exit 3, says what to install).",
    },
    "triage": {
        "kind": "deterministic",
        "summary": "Say how much help a choice needs: just answer, quick, guided or team.",
        "when": "First, whenever someone seems to be weighing options, even if they never say "
        "'decision'. It never builds files. Pass what you know (cost, how easy to undo, who is "
        "affected, deadline) and/or their own words with --text.",
        "args": [
            ("--text", "The person's own words; plain word rules fill in what they can."),
            ("--cost", "Money, time or effort at stake: a number of dollars or words (small, large)."),
            ("--reversible", "easy, some cost or hard."),
            ("--people", "just me, family, team, several groups, or a count."),
            ("--deadline", "Days, or words like today, this week, next month."),
            ("--provider / --model / --complete-cmd", "Optional: a model reads --text more carefully first."),
        ],
        "example": 'decisioncraft triage --text "my lease is up, renew or buy?" --json',
        "result": "{mode: none|quick|guided|team, label, does, why[], alternative, stakes, missing[] "
        "(questions worth asking), offer (a sentence to offer help without taking over), next[]}. "
        "A message that is not a choice (a factual question) comes back as none.",
        "fails": "Answers that are not an object (exit 1).",
    },
    "quick": {
        "kind": "deterministic",
        "summary": "Score a few options against what matters: a table, a lean and one thing to check.",
        "when": "Quick mode: a real choice that can be settled in the conversation. No files. "
        "Deterministic when you pass options and scores; with only --text it needs a model to read "
        "the options out of the person's words.",
        "args": [
            ("--option", "An option (repeat). Include doing nothing if it is real."),
            ("--criterion", "Something that matters (repeat), most important first; prefix "
             "'must:' for a must-have or 'nice:' for a nice-to-have."),
            ("--score", "OPTION=CRITERION=1..5 (repeat), or --scores FILE with "
             "{option: {criterion: score}}."),
            ("--scores", "A JSON file of scores."),
            ("--question", "The choice, for the heading."),
            ("--text", "The person's words, read by a model when no options are given."),
            ("--provider / --model / --complete-cmd", "The model for --text."),
        ],
        "example": 'decisioncraft quick --option "Renew the lease" --option "Buy it" '
        '--criterion "must:monthly cost" --criterion "reliability" '
        '--score "Renew the lease=monthly cost=3" --score "Buy it=monthly cost=4" --json',
        "result": "{options ranked with percent and any failed must-haves, table (Markdown), lean "
        "{option, reason, close_call}, check_first {text, why}, ask[] (what to ask when scores are "
        "missing)}. A lean, not a verdict.",
        "fails": "Fewer than two options, a score outside 1 to 5 or for an unknown option (exit 1); "
        "--text with no options and no model (exit 1).",
    },
    "interview": {
        "kind": "deterministic",
        "summary": "Guided mode: one question at a time, then a starter model in the folder.",
        "when": "When triage says guided or team. Ask the person each question in your own words, "
        "pass their answer back with --answer, and repeat until done. At a terminal with no "
        "--answer it runs the whole interview.",
        "args": [
            ("--dir", "The decision folder (state is kept in interview.json there)."),
            ("--answer", "The person's answer to the question last returned."),
            ("--question", "The choice in their words, to start (skips the first question)."),
            ("--kind", "personal, team or system (default: chosen from the first answer)."),
            ("--next", "Just show the pending question again."),
            ("--reset", "Start the interview again in this folder."),
        ],
        "example": 'decisioncraft interview --dir car --question "renew my lease or buy?" --json',
        "result": "{done: false, question {id, ask, why, kind, choices?, suggested?}, progress "
        "{asked, remaining}, mode_so_far} or, when finished, {done: true, mode, why, model_path, "
        "files, next[]} after writing model.json and material/README.txt.",
        "fails": "A folder that can't be written (exit 3); an interview file from something else (exit 1).",
    },
    "discover": {
        "kind": "deterministic", "summary": "Four opening questions about the choice, for a host to ask.",
        "when": "At the start of a decision, before drawing or drafting.",
        "args": [("--question", "Optional choice already described by the person.")],
        "example": "decisioncraft discover --question 'Which trial should we run?'",
        "result": "Four questions for the host to ask in conversation; no model call.",
        "fails": "The supplied choice is not text.",
    },
    "handoff": {
        "kind": "deterministic", "summary": "Turn a finished review into stories, checks and a proposed map.",
        "when": "After the person finishes a review, or to read a completed review file.",
        "args": [("model", "Decision model file."), ("review", "Completed review file."), ("--out", "Optional output JSON file.")],
        "example": "decisioncraft handoff model.json review.json --out handoff.json",
        "result": "Answers, proposed stories and checks, an explicit proposed-state model, missing parts and an agent request. It does not invent requirements or treat finishing as approval.",
        "fails": "Invalid model or review, or a review for a different model (exit 1).",
    },
    "session": {
        "kind": "deterministic",
        "summary": "Open a local review that saves answers for the agent.",
        "when": "When an agent starts a review on this computer and should read the answers directly.",
        "args": [("model", "Path to the decision model."), ("--dir", "New folder for answers and session details."),
                 ("--review", "Optional saved review to continue."), ("--source-root", "Folder containing sources the reviewer may open."),
                 ("--prepared-by", "Who prepared notes when no author is recorded."), ("--open", "Open the review in the browser."), ("--until-finished", "Return after the person presses Finish review.")],
        "example": "decisioncraft session model.json --dir .work/review --open --until-finished",
        "result": "JSON with a local URL and review file path. Answers save automatically. Finish review records completion; the human still decides.",
        "fails": "Invalid model or review, or an existing session folder (exit 1); a local server that cannot start (exit 3).",
    },
    "manifest": {
        "kind": "deterministic",
        "summary": "Print the tool's manifest as JSON.",
        "when": "To check the version and which capabilities need a model.",
        "args": [],
        "example": "decisioncraft manifest",
        "result": "JSON: name, version, description, capabilities and their kind.",
        "fails": "Never, unless the installation is damaged.",
    },
    "guide": {
        "kind": "deterministic",
        "summary": "Print the model format and the writing guide, for writing a model by hand.",
        "when": "When you (or an agent with no model routing) fill in model.json yourself: read this, "
        "then `validate` until it reports no errors.",
        "args": [],
        "example": "decisioncraft guide",
        "result": "Text, or with --json: {model_format, writing_guide} as Markdown.",
        "fails": "Never, unless the installation is damaged.",
    },
    "templates": {
        "kind": "deterministic",
        "summary": "List the map templates.",
        "when": "To choose how a decision should be drawn before `new` or `draft`.",
        "args": [],
        "example": "decisioncraft templates",
        "result": "JSON list: id, kind (journeys, chain or tree), title, what it is for.",
        "fails": "Never.",
    },
    "roles": {
        "kind": "deterministic",
        "summary": "List the default roles and the question each asks.",
        "when": "To see whose points of view a model gets when it names no roles.",
        "args": [],
        "example": "decisioncraft roles",
        "result": "JSON list: id, label, colour, asks.",
        "fails": "Never.",
    },
    "new": {
        "kind": "deterministic",
        "summary": "Start a new decision: a starter folder, or just an empty model.",
        "when": "At the start of your own decision. In a terminal with no flags it asks a "
        "few questions; agents and scripts pass flags (it never prompts when stdin is not a "
        "terminal or --yes is given).",
        "args": [
            ("--question", "The decision being made, as one question."),
            ("--template", "Template id (see `templates`; default decision-chain)."),
            ("--title", "Short title for the canvas (default: taken from the question)."),
            ("--roles", "Comma-separated role ids to keep (see `roles`; default all)."),
            ("--material", "Where your notes and documents are, noted in the README."),
            ("--dir", "Create a starter folder here: model.json and material/README.txt."),
            ("--date", "Optional date the model is checked against its sources."),
            ("--out", "Without --dir: write just the model here instead of printing it."),
            ("--yes", "Never ask; use defaults for anything not given."),
        ],
        "example": 'decisioncraft new --question "Should we lease or buy our next van?" '
        "--template decision-chain --dir van-decision",
        "result": "With --dir: a folder with model.json and material/README.txt, and the next "
        "commands to run. Without --dir: the model JSON (printed, or written to --out).",
        "fails": "Unknown template or role (exit 1, the message names the valid ones); "
        "--question missing when it can't ask (exit 2); the folder already has a model.json "
        "(exit 1).",
    },
    "validate": {
        "kind": "deterministic",
        "summary": "Check a model for mistakes and unclear writing.",
        "when": "After editing a model by hand, before rendering or sharing it.",
        "args": [("model", "Path to the model JSON.")],
        "example": "decisioncraft validate model.json",
        "result": "JSON list of problems (level error or warning, path, message). "
        "Exit 0 when there are no errors, 1 when there are.",
        "fails": "Exit 1 when the model has errors (the list is still printed), or the file is missing or not JSON.",
    },
    "render": {
        "kind": "deterministic",
        "summary": "Draw a model as one self-contained HTML canvas.",
        "when": "To share a model for review. The file works offline and makes no requests.",
        "args": [
            ("model", "Path to the model JSON."),
            ("--reviews", "Saved review files to show as agree/disagree tallies."),
            ("--merged", "An already merged review file, instead of --reviews."),
            (
                "--since",
                "An earlier version of the model; new and changed boxes are marked.",
            ),
            ("--out", "Output HTML path. Default: print to stdout when piped; in a terminal, "
             "or with --open, --watch or --json, write canvas.html next to the model."),
            ("--open", "Open the canvas in your browser when it is written."),
            ("--watch", "Keep running and draw again whenever the model or a review file changes."),
        ],
        "example": "decisioncraft render model.json --reviews a.json b.json --out canvas.html --open",
        "result": "HTML. Pan and zoom, role filter, Questions to decide, Decisions, Gaps "
        "ranked by impact and effort, Evidence, and Save my answers. Progress and the "
        "written path go to stderr. With --json: {path, summary, bytes}.",
        "fails": "A model with errors (exit 1, the problems are listed); a missing or "
        "non-JSON file (exit 1). With --watch, errors are shown and it keeps watching.",
    },
    "words": {
        "kind": "deterministic",
        "summary": "Write the whole model as readable Markdown.",
        "when": "For people who prefer text, for printing, or for an AI reader.",
        "args": [
            ("model", "Path to the model JSON."),
            ("--reviews", "Saved review files to include tallies and comments."),
            ("--out", "Output path (default: print)."),
        ],
        "example": "decisioncraft words model.json --out model.md",
        "result": "Markdown: the decision, every map, gaps, ranked questions, decisions, "
        "outcomes, sources, glossary and roles.",
        "fails": "A model with errors (exit 1).",
    },
    "questions": {
        "kind": "deterministic",
        "summary": "List every question to decide, most urgent first.",
        "when": "To build an agenda, or to see which questions reviewers dotted most.",
        "args": [
            ("model", "Path to the model JSON."),
            (
                "--reviews",
                "Saved review files; their dots and answers change the order.",
            ),
        ],
        "example": "decisioncraft questions model.json --reviews a.json b.json",
        "result": "JSON list: id, question, role, urgency, where it sits, evidence, dots, tallies.",
        "fails": "A model with errors (exit 1).",
    },
    "merge": {
        "kind": "deterministic",
        "summary": "Combine reviewers' answer files into one view.",
        "when": "After a review, to see where people agree, disagree, and what they dotted.",
        "args": [
            ("model", "Path to the model JSON the reviews answered."),
            ("reviews", "One or more saved review files."),
            ("--out", "Output path (default: print)."),
        ],
        "example": "decisioncraft merge model.json a.json b.json --out merged.json",
        "result": "JSON: reviewers, per question agree/change/unsure counts, written answers, dots, comments and "
        "`split`; per decision the values given and any `conflict`; `stale_reviews` "
        "names reviews made against another version of the model.",
        "fails": "A file that is not a review (exit 1).",
    },
    "diff": {
        "kind": "deterministic",
        "summary": "Show what changed between two versions of a model.",
        "when": "Before a follow-up review, to see what is new since last time.",
        "args": [("old", "Earlier model JSON."), ("new", "Later model JSON.")],
        "example": "decisioncraft diff model-june.json model-july.json",
        "result": "JSON: added, removed and changed items by id, with the changed fields.",
        "fails": "Unreadable files (exit 1).",
    },
    "draft": {
        "kind": "model-backed",
        "summary": "Draft a full model from your notes with a language model.",
        "when": "Use when you have real notes, transcripts, documents or data and want a "
        "first draft instead of starting from a blank model. Costs tokens; results "
        "differ run to run; always review the draft.",
        "args": [
            ("material", "Files to read (Markdown or plain text)."),
            ("--brief", "Optional discovery answers JSON from the conversation."),
            ("--template", "Optional template id; auto chooses suitable maps from the material (default)."),
            ("--question", "The decision being made."),
            ("--title", "Optional title."),
            ("--date", "Optional checked-on date."),
            ("--provider", "anthropic or openai. Needs the matching API key."),
            (
                "--model",
                "Model name (required for openai; optional default for anthropic).",
            ),
            (
                "--complete-cmd",
                (
                    "Run this command instead of a provider SDK; it reads "
                    "{system, prompt} JSON on stdin and prints the reply. Use this to route the "
                    "call through a host's own model setup. One of --provider or --complete-cmd "
                    "is required."
                ),
            ),
            ("--out", "Output path (default: print)."),
        ],
        "example": "decisioncraft draft notes/*.md --template customer-journey "
        '--question "How do we cut missed pickups?" --provider anthropic '
        "--model <model-name> --out model.json",
        "result": "A validated model citing your material. It is checked and, if needed, "
        "repaired once; it still needs a person's review. Progress goes to stderr.",
        "fails": "Neither --provider nor --complete-cmd (exit 2); a provider with no key, "
        "no --model, or no SDK installed (exit 3, says what to set); a failed call, or a "
        "reply that stays invalid after one repair (exit 4, problems listed).",
    },
    "perspectives": {
        "kind": "model-backed",
        "summary": "Add notes from each role to an existing model.",
        "when": "Use when a model has few notes, or a new role should weigh in. Costs tokens.",
        "args": [
            ("model", "Path to the model JSON."),
            ("material", "Optional files the roles may read."),
            ("--per-role", "Most notes to add per role (default 3)."),
            ("--provider", "anthropic or openai. Needs the matching API key."),
            (
                "--model-name",
                "Model name (required for openai; optional default for anthropic).",
            ),
            (
                "--complete-cmd",
                (
                    "Run this command instead of a provider SDK; see `draft "
                    "--help`. One of --provider or --complete-cmd is required."
                ),
            ),
            ("--out", "Output path (default: print)."),
            ("--notes", "Instead: a saved answers file; each reviewer note gets replies from the roles asked."),
            ("--roles", "With --notes: comma-separated role ids to ask (default: what each note asked)."),
            ("--dry-run", "With --notes: show what would be asked, with no model call."),
        ],
        "example": "decisioncraft perspectives model.json --provider anthropic "
        "--model-name <model-name> --out model.json",
        "result": "The model with new notes added; existing notes are kept. With --notes: the answers "
        "file with each role's reply (a short view and one question) under each reviewer note.",
        "fails": "Neither --provider nor --complete-cmd (exit 2); a provider with no key, "
        "model name or SDK (exit 3); a failed call or an invalid reply after one repair (exit 4).",
    },
}

DESCRIPTION = (
    'Point it at anything (a codebase, a folder of notes, a page or a topic) and get '
    "a map of how it works today, how it could work, the gaps as user stories with 'd"
    "one when' checks, and notes from every role. It also helps someone weigh a choic"
    'e at the right depth, from a quick side-by-side in the chat to a full team revie'
    'w. Use for "map this codebase", "show me how X works", "as-is and to-be", "where'
    ' are the gaps", "turn these notes into a process map", "review this process", an'
    'd whenever someone is weighing options, even without saying \'decision\': "should '
    'I...", "torn between", "pros and cons", "which is better", "renew or buy", "keep'
    ' or replace", "help me think this through", comparing offers, quotes or vendors.'
    ' Not for factual questions or trivial picks.'
)

REQUIRES = [
    {
        "name": "ANTHROPIC_API_KEY",
        "purpose": "`draft` and `perspectives` with --provider "
        "anthropic. Without it, those two capabilities fail with a clear message; every other "
        "capability is unaffected.",
        "install": "https://docs.anthropic.com/en/api/getting-started",
        "optional": True,
    },
    {
        "name": "OPENAI_API_KEY",
        "purpose": "`draft` and `perspectives` with --provider "
        "openai. Without it, those two capabilities fail with a clear message; every other "
        "capability is unaffected.",
        "install": "https://platform.openai.com/docs/quickstart",
        "optional": True,
    },
]


def manifest() -> dict:
    return {
        "smart_tool_format": 1,
        "name": NAME,
        "version": VERSION,
        "description": DESCRIPTION,
        "library": "decisioncraft",
        "capabilities": {k: v["kind"] for k, v in CAPABILITIES.items()},
        "templates": [t["id"] for t in templates()],
        "requires": REQUIRES,
    }


def _body() -> str:
    text = files(NAME).joinpath("SMART_TOOL.md").read_text(encoding="utf-8")
    if text.startswith("---"):
        text = text.split("---", 2)[2]
    return text.strip()


def _repository() -> str | None:
    try:
        meta = _metadata("amplifier-smart-tool-decisioncraft")
    except PackageNotFoundError:
        return None
    for line in meta.get_all("Project-URL") or []:
        if line.lower().startswith("repository"):
            return line.split(",", 1)[1].strip()
    return None


def _head(name: str) -> str:
    out = [f'<skill_content name="{name}">', f"Skill directory: {files(NAME)}"]
    repo = _repository()
    if repo:
        out.append(f"Repository: {repo}")
    out.append("Relative paths in this skill are relative to the skill directory.")
    return "\n".join(out) + "\n\n"


def skill() -> str:
    caps = "\n".join(
        f"- `{k}` [{v['kind']}] -- {v['summary']}" for k, v in CAPABILITIES.items()
    )
    return (
        _head(NAME) + _body() + "\n\n## Capabilities\n\n"
        f"Each has its own skill: `{NAME} <capability> --help`.\n\n" + caps + "\n\n"
        "<skill_resources>\n  <file>SMART_TOOL.md</file>\n  <file>lib.py</file>\n"
        "  <file>model.py</file>\n  <file>resources/writing-guide.md</file>\n"
        "</skill_resources>\n</skill_content>"
    )


def capability_skill(name: str, argument_reference: str = "") -> str:
    c = CAPABILITIES[name]
    args = "\n".join(f"- `{a}` -- {d}" for a, d in c["args"]) or "None."
    return (
        _head(f"{NAME} {name}") + f"# {NAME} {name}\n\n{c['summary']}\n\n"
        f"**Kind:** {c['kind']}."
        + (
            " Needs a provider and costs tokens."
            if c["kind"] == "model-backed"
            else " Runs with no model and no credentials."
        )
        + f"\n\n## When to use it\n\n{c['when']}\n\n## Arguments\n\n{args}\n\n"
        f"## Example\n\n```\n{c['example']}\n```\n\n## Result\n\n{c['result']}\n\n"
        f"## When it fails\n\n{c['fails']}\n"
        + (
            f"\n## Argument reference\n\n```\n{argument_reference.strip()}\n```\n"
            if argument_reference
            else ""
        )
        + "</skill_content>"
    )
