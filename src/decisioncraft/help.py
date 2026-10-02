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
    "mcp": {
        "kind": "deterministic", "summary": "Serve the same decision workflow to an MCP host over stdio.",
        "when": "For any host that supports a local MCP server.", "args": [],
        "example": "decisioncraft mcp", "result": "Standard tools for discovery, map shapes, validation, review, waiting for completion and agent handoff.",
        "fails": "The optional mcp extra is not installed.",
    },
    "discover": {
        "kind": "deterministic", "summary": "Start with four short questions about the choice and the useful visual.",
        "when": "At the start of a decision, before drawing or drafting.",
        "args": [("--question", "Optional choice already described by the person.")],
        "example": "decisioncraft discover --question 'Which trial should we run?'",
        "result": "Four questions for the host to ask in conversation; no model call.",
        "fails": "The supplied choice is not text.",
    },
    "handoff": {
        "kind": "deterministic", "summary": "Return a review to the agent with stories, acceptance criteria and a proposed map.",
        "when": "After the person finishes a review, or to read a completed review file.",
        "args": [("model", "Decision model file."), ("review", "Completed review file."), ("--out", "Optional output JSON file.")],
        "example": "decisioncraft handoff model.json review.json --out handoff.json",
        "result": "Answers, proposed stories and checks, an explicit proposed-state model, missing parts and an agent request. It does not invent requirements or treat finishing as approval.",
        "fails": "Invalid model or review, or a review for a different model.",
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
        "fails": "Invalid model or review, an existing session folder, or a local server that cannot start.",
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
        "summary": "Start an empty model from a template.",
        "when": "To write a model by hand, or to see the exact shape `draft` fills in.",
        "args": [
            ("--template", "Template id (see `templates`)."),
            ("--title", "Short title for the canvas."),
            ("--question", "The decision being made, as one question."),
            ("--date", "Optional date the model is checked against its sources."),
            ("--out", "Write the model here instead of printing it."),
        ],
        "example": 'decisioncraft new --template decision-chain --title "Delivery van" '
        '--question "Should we lease or buy our next van?" --out model.json',
        "result": "A model JSON with the template's lanes or stages and default roles.",
        "fails": "Unknown template (exit 1, message names the valid ones).",
    },
    "validate": {
        "kind": "deterministic",
        "summary": "Check a model for mistakes and unclear writing.",
        "when": "After editing a model by hand, before rendering or sharing it.",
        "args": [("model", "Path to the model JSON.")],
        "example": "decisioncraft validate model.json",
        "result": "JSON list of problems (level error or warning, path, message). "
        "Exit 0 when there are no errors, 1 when there are.",
        "fails": "Unreadable or non-JSON file (exit 1).",
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
            ("--out", "Output HTML path (default: print to stdout)."),
        ],
        "example": "decisioncraft render model.json --reviews a.json b.json --out canvas.html",
        "result": "HTML. Pan and zoom, role filter, Questions to decide, Decisions, Gaps "
        "ranked by impact and effort, Evidence, and Save my answers.",
        "fails": "A model with errors (exit 1, the problems are listed).",
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
        "summary": "Read your material and draft a full model with a language model.",
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
        '--question "How do we cut missed pickups?" --provider anthropic --out model.json',
        "result": "A validated model citing your material. It is checked and, if needed, "
        "repaired once; it still needs a person's review.",
        "fails": "Neither --provider nor --complete-cmd, or a provider with no key or SDK "
        "installed (exit 1, says what to set); a reply that stays invalid after one "
        "repair (exit 1, problems listed).",
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
        ],
        "example": "decisioncraft perspectives model.json --provider anthropic --out model.json",
        "result": "The model with new notes added; existing notes are kept.",
        "fails": "Neither --provider nor --complete-cmd, or a provider with no key or SDK "
        "installed; an invalid reply after one repair (exit 1).",
    },
}

DESCRIPTION = (
    "Map how a problem works, gather every point of view, and decide together. "
    "Builds a zoomable, offline HTML canvas and a plain-text version from a "
    "decision model. Use when a decision affects several groups and each should "
    "be heard, with a record of why it was decided, before anyone chooses."
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
