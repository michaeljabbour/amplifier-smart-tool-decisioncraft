"""Command line adapter: reads files, calls the library, prints or writes the result.

Results go to stdout; progress, notes and errors go to stderr. `--json` prints exactly one
JSON document per result (JSON Lines for the long-running `session` and `render --watch`),
errors included, and the exit code always matches. See contracts/cli.v1.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from . import errors as E
from . import lib
from .errors import ToolError, classify
from .examples import example_names
from .help import CAPABILITIES, VERSION, capability_skill, skill
from .stats import describe, summary
from .term import Term, interactive

WIDTH = 80
MODEL_BACKED = {"draft", "perspectives", "map"}  # quick and triage call a model only when one is named
GROUPS = [
    ("Start here", ["map", "example", "new", "render", "doctor"]),
    ("Talk a choice through", ["triage", "quick", "interview"]),
    ("Review and compare", ["session", "questions", "merge", "diff", "words", "validate", "handoff"]),
    ("Draft with a model (costs tokens)", ["draft", "perspectives"]),
    ("For agents and hosts", ["discover", "guide", "templates", "roles", "manifest", "mcp"]),
]

# Set from argv before parsing, so even a usage error can answer in JSON.
_JSON_MODE = False


# ---------------------------------------------------------------- help and parsing


class Formatter(argparse.RawDescriptionHelpFormatter):
    def __init__(self, prog):
        super().__init__(prog, width=WIDTH, max_help_position=26)


class SkillHelp(argparse.Action):
    """`--help` prints the skill (the full guide an agent reads); `-h` is the short summary."""

    def __call__(self, parser, namespace, values, option_string=None):
        print(
            skill()
            if self.const is None
            else capability_skill(self.const, argument_reference=parser.format_help())
        )
        parser.exit()


class SkillParser(argparse.ArgumentParser):
    def __init__(self, *args, capability=None, root=False, **kwargs):
        kwargs["add_help"] = False
        kwargs.setdefault("formatter_class", Formatter)
        super().__init__(*args, **kwargs)
        self._root = root
        self._capability = capability

    def add_help_group(self):
        """Added last so it prints after the command's own options."""
        g = self.add_argument_group("Help")
        g.add_argument("-h", action="help", help="Show this short summary.")
        g.add_argument("--help", action=SkillHelp, nargs=0, const=self._capability,
                       help="Show the full guide (written for agents).")

    def format_help(self):
        return root_help() if self._root else super().format_help()

    def error(self, message):
        where = self.prog
        hint = f"Run: {where} -h" if where != "decisioncraft" else "Run: decisioncraft -h"
        if _JSON_MODE:
            err = ToolError("usage", f"{where}: {message}", hint=hint, exit_code=E.USAGE)
            sys.stdout.write(json.dumps(_envelope(_command_from(where), err=err), ensure_ascii=False) + "\n")
            sys.exit(E.USAGE)
        sys.stderr.write(f"{where}: {message}\n{hint}\n")
        sys.exit(E.USAGE)


def _command_from(prog: str) -> str | None:
    parts = prog.split()
    return parts[1] if len(parts) > 1 else None


def _wrap(name: str, text: str, indent: int = 17) -> str:
    return textwrap.fill(
        text, width=WIDTH, initial_indent=f"  {name:<{indent - 2}}",
        subsequent_indent=" " * indent,
    )


def root_help() -> str:
    lines = [
        "usage: decisioncraft <command> [options]",
        "",
        "Map how a problem works, hear every point of view, and decide together.",
    ]
    for title, names in GROUPS:
        lines += ["", f"{title}:"]
        lines += [_wrap(n, CAPABILITIES[n]["summary"]) for n in names]
    lines += [
        "",
        "Options for every command:",
        _wrap("--json", "One JSON result on stdout, errors included (for agents)."),
        _wrap("-q, --quiet", "No progress lines on stderr."),
        _wrap("-y, --yes", "Never ask questions; use defaults for anything not given."),
        _wrap("--no-color", "Plain output (setting NO_COLOR does the same)."),
        _wrap("--debug", "Show the full trace when something fails."),
        _wrap("-h, --help", "-h: this summary. --help: the full guide, written for agents."),
        _wrap("--version", "Print the version."),
        "",
        "Each command has its own: decisioncraft <command> -h (or --help).",
        "To chain commands in your own code, import the library: import decisioncraft",
        "",
        "Try: decisioncraft example medical --open",
        "",
    ]
    return "\n".join(lines)


def start_screen() -> str:
    rows = [
        ("decisioncraft map ./your-repo --open", "point it at anything: as-is, to-be, gaps"),
        ("decisioncraft example medical --open", "open a worked example"),
        ("decisioncraft new", "start your own decision, step by step"),
        ('decisioncraft triage --text "..."', "how much help does this choice need?"),
        ("decisioncraft render model.json --open", "draw a model you can share"),
        ("decisioncraft doctor", "check your setup"),
    ]
    out = [
        f"Decisioncraft {VERSION}: map how a problem works, hear every point of view,",
        "and decide together.",
        "",
        "Start here:",
    ]
    out += [f"  {cmd:<41}{what}" for cmd, what in rows]
    out += ["", "  (map also takes a notes folder, a file, a web address or a topic in quotes)"]
    out += [
        "",
        "Try: decisioncraft example medical --open",
        "",
        "Every command: decisioncraft -h    The full guide: decisioncraft --help",
        "",
    ]
    return "\n".join(out)


def _globals(parser: argparse.ArgumentParser, *, root: bool) -> None:
    """The options every command takes. Sub-level copies use SUPPRESS so a value given
    before the command name is not overwritten by the sub-parser's default."""
    d = (lambda v: v) if root else (lambda v: argparse.SUPPRESS)
    g = parser.add_argument_group("Options for every command")
    g.add_argument("--json", action="store_true", default=d(False),
                   help="One JSON result on stdout, errors included.")
    g.add_argument("-q", "--quiet", action="store_true", default=d(False),
                   help="No progress lines on stderr.")
    g.add_argument("-y", "--yes", action="store_true", default=d(False),
                   help="Never ask; use defaults.")
    g.add_argument("--no-color", action="store_true", default=d(False),
                   help="Plain output (NO_COLOR works too).")
    g.add_argument("--debug", action="store_true", default=d(False),
                   help="Show the full trace on failure.")


def build() -> SkillParser:
    p = SkillParser(prog="decisioncraft", root=True,
                    description="Map how a problem works, gather every point of view, and decide together.")
    p.add_argument("--version", action="version", version=f"decisioncraft {VERSION}")
    _globals(p, root=True)
    sub = p.add_subparsers(dest="command", parser_class=SkillParser, metavar="<command>")

    def cmd(name: str, extra_examples: tuple[str, ...] = ()):
        c = CAPABILITIES[name]
        kind = "Uses a language model and costs tokens." if c["kind"] == "model-backed" \
            else "Runs with no model and no credentials."
        examples = (c["example"], *extra_examples)
        epilog = "Examples:\n" + "\n".join(
            textwrap.fill(e, width=WIDTH, initial_indent="  ", subsequent_indent="      ")
            for e in examples
        ) + f"\n\nThe full guide: decisioncraft {name} --help"
        sp = sub.add_parser(
            name, capability=name, help=c["summary"],
            description=textwrap.fill(f"{c['summary']} {kind}", width=WIDTH)
            + "\n\n" + textwrap.fill(f"When: {c['when']}", width=WIDTH),
            epilog=epilog,
        )
        return sp

    # Start here
    c = cmd("map", ("decisioncraft map ./notes --dry-run",
                    'decisioncraft map "how our customer onboarding works" --answers answers.json --complete-cmd "my-host complete"'))
    g = c.add_argument_group("What to map")
    g.add_argument("target", help="A repo or folder, a notes file, a web address, or a topic in quotes.")
    g.add_argument("--question", default="", help="The question the map answers.")
    g.add_argument("--roles", help="Comma-separated role ids (default: the eight map roles).")
    g.add_argument("--answers", metavar="FILE", help="For a topic: JSON answering how_today, pain, goal.")
    g.add_argument("--page", metavar="FILE", help="For a web address: the page's text, fetched by your host.")
    g.add_argument("--allow-network", action="store_true", help="For a web address: fetch that one page.")
    g.add_argument("--budget", type=int, default=120_000, help="Most characters to read (default 120000).")
    g.add_argument("--dry-run", action="store_true", help="Show what would be read; no model call.")
    g.add_argument("--starter", action="store_true",
                   help="Write the reading digest and a starter model to fill in yourself; no model call.")
    g = c.add_argument_group("Where it goes")
    g.add_argument("--dir", help="Folder for model.json and canvas.html (default: ./decisioncraft-map-NAME).")
    g.add_argument("--open", action="store_true", help="Open the canvas in your browser.")
    _model_flags(c, name_flag="--model")

    c = cmd("example", ("decisioncraft example business --out ~/bakery --json",))
    g = c.add_argument_group("What to copy")
    _names = [e["id"] for e in example_names()]
    g.add_argument("name", choices=_names,
                   help=", ".join(_names[:-1]) + " or " + _names[-1] + ".")
    g = c.add_argument_group("Where it goes")
    g.add_argument("--out", metavar="DIR", help="Folder to create (default: ./decisioncraft-example-NAME).")
    g.add_argument("--open", action="store_true", help="Open the canvas in your browser.")
    g.add_argument("--force", action="store_true", help="Write even if the folder has files.")

    c = cmd("new", ("decisioncraft new",
                    'decisioncraft new --question "Which supplier?" --roles owner,finance,engineer --yes'))
    g = c.add_argument_group("The decision")
    g.add_argument("--question", help="The decision being made, as one question.")
    g.add_argument("--title", help="Short title (default: taken from the question).")
    g.add_argument("--template", help="Template id (see templates; default decision-chain).")
    g.add_argument("--roles", help="Comma-separated role ids to keep (default: all).")
    g.add_argument("--material", help="Where your notes and documents are.")
    g.add_argument("--date", default="", help="Date the model is checked against its sources.")
    g = c.add_argument_group("Where it goes")
    g.add_argument("--dir", help="Create a starter folder: model.json and material/README.txt.")
    g.add_argument("--out", help="Without --dir: write just the model JSON here.")

    c = cmd("render", ("decisioncraft render model.json --watch",
                       "decisioncraft render model.json --since old.json --out canvas.html"))
    g = c.add_argument_group("Input")
    g.add_argument("model", help="The model JSON file.")
    g.add_argument("--reviews", nargs="*", default=[], metavar="FILE", help="Saved review files to tally.")
    g.add_argument("--merged", metavar="FILE", help="An already merged review file.")
    g.add_argument("--since", metavar="FILE", help="An earlier model; new and changed boxes are marked.")
    g = c.add_argument_group("Output")
    g.add_argument("--out", metavar="FILE", help="Where to write the HTML.")
    g.add_argument("--open", action="store_true", help="Open it in your browser.")
    g.add_argument("--watch", action="store_true", help="Draw again whenever an input file changes.")

    c = cmd("doctor")
    g = c.add_argument_group("What to check")
    g.add_argument("--dir", default=".", help="Folder you plan to write into (default: here).")
    g.add_argument("--complete-cmd", metavar="CMD", help="A host command to look up (not run).")
    g.add_argument("--live", action="store_true", help="Make one tiny real call to each provider with a key.")

    c = cmd("config", ("decisioncraft config set model claude-opus-5-5", "decisioncraft config show"))
    g = c.add_argument_group("What to change")
    g.add_argument("action", nargs="?", default="show", choices=["show", "set", "unset"], help="show, set or unset.")
    g.add_argument("key", nargs="?", choices=["provider", "model"], help="provider or model.")
    g.add_argument("value", nargs="?", help="For set: the value.")


    # Talk a choice through
    def _ask_model(c):
        g = c.add_argument_group("A model to read --text (optional)")
        g.add_argument("--provider", choices=["anthropic", "openai"], help="Use this vendor's SDK and API key.")
        g.add_argument("--model", metavar="NAME", help="Model name for --provider.")
        g.add_argument("--complete-cmd", metavar="CMD",
                       help="Route the call through your own command ({system, prompt} JSON on stdin).")

    c = cmd("triage", ('decisioncraft triage --cost 30000 --reversible hard --people family --json',))
    g = c.add_argument_group("What you know (all optional)")
    g.add_argument("--text", default="", help="The person's own words.")
    g.add_argument("--cost", help="Money, time or effort at stake (dollars, or small/large).")
    g.add_argument("--reversible", help="easy, some cost or hard.")
    g.add_argument("--people", help="just me, family, team, several groups, or a count.")
    g.add_argument("--deadline", help="Days, or words like today, this week, next month.")
    _ask_model(c)

    c = cmd("quick", ('decisioncraft quick --from car/model.json --scores scores.json',
                      'decisioncraft quick --text "renew the lease or buy?" --complete-cmd "my-host complete"'))
    g = c.add_argument_group("The choice")
    g.add_argument("--option", action="append", default=[], metavar="NAME", help="An option (repeat).")
    g.add_argument("--criterion", action="append", default=[], metavar="NAME",
                   help="Something that matters (repeat), most important first; must: or nice: prefix.")
    g.add_argument("--score", action="append", default=[], metavar="O=C=N", help="OPTION=CRITERION=1..5 (repeat).")
    g.add_argument("--scores", metavar="FILE", help="JSON file: {option: {criterion: score}}.")
    g.add_argument("--from", dest="from_model", metavar="FILE",
                   help="Take options and what matters from a model's comparison (for example after interview).")
    g.add_argument("--question", default="", help="The choice, for the heading.")
    g.add_argument("--text", default="", help="The person's words, read by a model when no options are given.")
    _ask_model(c)

    c = cmd("interview", ('decisioncraft interview --dir car --answer "renew, buy, or wait" --json',
                          "decisioncraft interview --dir car"))
    g = c.add_argument_group("The interview")
    g.add_argument("--dir", required=True, help="The decision folder (keeps interview.json).")
    g.add_argument("--answer", help="The answer to the question last returned.")
    g.add_argument("--question", default="", help="The choice in the person's words, to start.")
    g.add_argument("--kind", choices=["personal", "team", "system"], help="Which question set (default: chosen for you).")
    g.add_argument("--next", action="store_true", help="Show the pending question again.")
    g.add_argument("--reset", action="store_true", help="Start again in this folder.")

    # Review and compare
    c = cmd("session")
    g = c.add_argument_group("Input")
    g.add_argument("model", help="The model JSON file.")
    g.add_argument("--review", metavar="FILE", help="A saved review to continue.")
    g.add_argument("--source-root", default=".", metavar="DIR", help="Folder holding sources reviewers may open.")
    g.add_argument("--prepared-by", default="", help="Who prepared notes with no author.")
    g = c.add_argument_group("Session")
    g.add_argument("--dir", required=True, help="New, empty folder for answers.")
    g.add_argument("--open", action="store_true", help="Open the review in your browser.")
    g.add_argument("--until-finished", action="store_true", help="Return when the person presses Finish review.")
    _model_flags(c, name_flag="--model-name", optional=True)

    for name in ("questions", "words"):
        c = cmd(name)
        g = c.add_argument_group("Input")
        g.add_argument("model", help="The model JSON file.")
        g.add_argument("--reviews", nargs="*", default=[], metavar="FILE", help="Saved review files.")
        if name == "words":
            g = c.add_argument_group("Output")
            g.add_argument("--out", metavar="FILE", help="Write the Markdown here (default: print).")

    c = cmd("merge")
    g = c.add_argument_group("Input")
    g.add_argument("model", help="The model JSON the reviews answered.")
    g.add_argument("reviews", nargs="+", help="One or more saved review files.")
    g = c.add_argument_group("Output")
    g.add_argument("--out", metavar="FILE", help="Write the merged JSON here (default: print).")

    c = cmd("diff")
    g = c.add_argument_group("Input")
    g.add_argument("old", help="The earlier model JSON.")
    g.add_argument("new", help="The later model JSON.")

    c = cmd("validate")
    c.add_argument_group("Input").add_argument("model", help="The model JSON file.")

    c = cmd("handoff")
    g = c.add_argument_group("Input")
    g.add_argument("model", help="The model JSON file.")
    g.add_argument("review", help="The completed review file.")
    c.add_argument_group("Output").add_argument("--out", metavar="FILE", help="Write the handoff JSON here.")

    # Draft with a model
    c = cmd("draft", (
        'decisioncraft draft notes/*.md --question "Open on Sundays?" '
        "--complete-cmd 'my-host complete' --out model.json",
    ))
    g = c.add_argument_group("Input")
    g.add_argument("material", nargs="+", help="Files to read (Markdown or plain text).")
    g.add_argument("--question", required=True, help="The decision being made.")
    g.add_argument("--template", default="auto", help="Template id, or auto (default).")
    g.add_argument("--title", default="", help="Optional title.")
    g.add_argument("--date", default="", help="Optional checked-on date.")
    g.add_argument("--brief", metavar="FILE", help="Discovery answers JSON from the conversation.")
    _model_flags(c, name_flag="--model")
    c.add_argument_group("Output").add_argument("--out", metavar="FILE", help="Write the model here (default: print).")

    c = cmd("perspectives", (
        "decisioncraft perspectives model.json --notes answers.json --complete-cmd 'my-host complete' --out replies.json",
        "decisioncraft perspectives model.json --notes answers.json --dry-run",
    ))
    g = c.add_argument_group("Input")
    g.add_argument("model", nargs="?", help="The model JSON file (needed with --notes for context).")
    g.add_argument("material", nargs="*", help="Optional files the roles may read.")
    g.add_argument("--per-role", type=int, default=3, help="Most notes to add per role (default 3).")
    g = c.add_argument_group("Reply to reviewers' rough notes instead")
    g.add_argument("--notes", metavar="FILE", help="A saved answers file whose notes should get expert replies.")
    g.add_argument("--roles", help="Comma-separated role ids to ask (default: what each note asked, else all).")
    g.add_argument("--dry-run", action="store_true", help="Show what would be asked; no model call.")
    _model_flags(c, name_flag="--model-name")
    c.add_argument_group("Output").add_argument("--out", metavar="FILE", help="Write the model here (default: print).")

    # For agents and hosts
    c = cmd("discover")
    c.add_argument_group("Input").add_argument("--question", default="", help="The choice, if already described.")
    for name in ("guide", "templates", "roles", "manifest", "mcp"):
        cmd(name)
    for name, sp in sub.choices.items():
        _globals(sp, root=False)
        sp.add_help_group()
        pos = []
        for act in sp._actions:
            if not act.option_strings and act.dest != argparse.SUPPRESS:
                label = act.dest.upper()
                pos.append(f"{label} ..." if act.nargs in ("+", "*") else label)
        sp.usage = " ".join(["decisioncraft", name, *pos, "[options]"])
    p.add_help_group()
    return p


def _model_flags(c, *, name_flag: str, optional: bool = False) -> None:
    g = c.add_argument_group("Which model answers Ask the experts (optional)" if optional else "Which model answers (pick one)")
    g.add_argument("--provider", choices=["anthropic", "openai"], help="Use this vendor's SDK and API key.")
    if name_flag == "--model":
        g.add_argument("--model", metavar="NAME", help="Model name for --provider.")
    else:
        g.add_argument("--model-name", dest="model_name", metavar="NAME",
                       help="Model name for --provider (the positional is the model file).")
    g.add_argument("--complete-cmd", metavar="CMD",
                   help="Route calls through your own command: it reads {system, prompt} "
                   "JSON on stdin and prints the reply.")


# ---------------------------------------------------------------- results


@dataclass
class Out:
    """What a command produced. `text` is for people; `data` is the JSON result."""

    data: object = None
    text: str | None = None
    files: list[dict] = field(default_factory=list)
    next: list[str] = field(default_factory=list)
    error: ToolError | None = None
    explained: bool = False  # the text already explains the failure; only the exit code is left


def _envelope(command, *, data=None, files=None, next_steps=None, err: ToolError | None = None, event=None) -> dict:
    env = {"ok": err is None, "command": command}
    if event:
        env["event"] = event
    if data is not None or err is None:
        env["result"] = data
    env["files"] = files or []
    if next_steps:
        env["next"] = next_steps
    if err is not None:
        env["error"] = err.as_dict()
        env["exit_code"] = err.exit_code
    return env


class Run:
    """Per-invocation state: parsed args, output settings and helpers."""

    def __init__(self, args):
        self.args = args
        self.json = bool(getattr(args, "json", False))
        self.term = Term(quiet=bool(getattr(args, "quiet", False)), no_color=bool(getattr(args, "no_color", False)))
        self.file: str | None = None  # the file being read, for error messages

    @property
    def can_ask(self) -> bool:
        return interactive() and not self.json and not getattr(self.args, "yes", False)

    @property
    def pretty(self) -> bool:
        """Readable text instead of JSON: only for a person at a terminal."""
        return not self.json and sys.stdout.isatty()

    def load(self, path: str):
        self.file = path
        p = Path(path).expanduser()
        try:
            text = p.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ToolError("file_not_found", f"Can't find {path}.",
                            hint="Check the path. To start a new model, run: decisioncraft new",
                            file=path) from None
        except IsADirectoryError:
            raise ToolError("not_a_file", f"{path} is a folder, not a file.",
                            hint="Point to the JSON file inside it, for example model.json.", file=path) from None
        except UnicodeDecodeError:
            raise ToolError("bad_json", f"{path} is not text (expected JSON).", file=path,
                            hint="Point to a .json file saved by decisioncraft or your editor.") from None
        try:
            value = json.loads(text)
        except json.JSONDecodeError as e:
            raise ToolError("bad_json", f"{path} is not valid JSON (line {e.lineno}, column {e.colno}: {e.msg}).",
                            hint="Fix the JSON, or start again with: decisioncraft new", file=path) from None
        return value

    def material(self, paths) -> list[dict]:
        out = []
        for path in paths or []:
            p = Path(path).expanduser()
            self.file = path
            if p.is_dir():
                raise ToolError("not_a_file", f"{path} is a folder.", file=path,
                                hint=f"Pass the files inside it, for example {path.rstrip('/')}/*.md")
            try:
                out.append({"name": p.name, "text": p.read_text(encoding="utf-8")})
            except FileNotFoundError:
                raise ToolError("file_not_found", f"Can't find {path}.", file=path,
                                hint="Check the path or the shell pattern (for example notes/*.md).") from None
            except UnicodeDecodeError:
                raise ToolError("not_text", f"{path} is not plain text.", file=path,
                                hint="Save it as Markdown or plain text first.") from None
        return out

    def write(self, path: Path, text: str, kind: str) -> dict:
        path = path.expanduser()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        except PermissionError:
            raise ToolError("no_write_access", f"Can't write {path}.", file=str(path), exit_code=E.SETUP,
                            hint="Choose a folder you can write to with --out or --dir.") from None
        return {"path": str(path), "kind": kind}

    def open(self, path: Path) -> None:
        if os.environ.get("DECISIONCRAFT_NO_BROWSER"):
            self.term.say(f"Not opening a browser (DECISIONCRAFT_NO_BROWSER is set): {path}")
            return
        import webbrowser

        if webbrowser.open(path.resolve().as_uri()):
            self.term.say("Opened it in your browser.")
        else:
            self.term.warn(f"Couldn't open a browser here. Open this file yourself: {path.resolve()}")

    def ask(self, prompt: str, default: str = "") -> str:
        shown = f"{prompt} [{default}]: " if default else f"{prompt}: "
        sys.stderr.write(self.term.paint(shown, "bold"))
        sys.stderr.flush()
        line = sys.stdin.readline()
        if not line:
            raise KeyboardInterrupt
        return line.strip() or default


def _size(n: int) -> str:
    return f"{n / 1024:.0f} KB" if n >= 1024 else f"{n} bytes"


def _default_canvas(model_path: str) -> Path:
    p = Path(model_path).expanduser()
    return p.with_name("canvas.html" if p.name == "model.json" else f"{p.stem}.html")


def _q(path) -> str:
    """A path as people would type it: relative to here when inside it, quoted if needed."""
    p = Path(path).expanduser()
    try:
        text = str(p.resolve().relative_to(Path.cwd().resolve())) if p.is_absolute() else str(path)
    except ValueError:
        home = str(Path.home())
        text = "~" + str(p)[len(home):] if str(p).startswith(home + os.sep) else str(p)
    return f'"{text}"' if " " in text else text


# ---------------------------------------------------------------- commands


def do_example(run: Run) -> Out:
    a = run.args
    data = lib.example(a.name)
    out_dir = Path(a.out).expanduser() if a.out else Path.cwd() / f"decisioncraft-example-{a.name}"
    if out_dir.exists() and any(out_dir.iterdir()) and not a.force:
        raise ToolError("folder_not_empty", f"{_q(out_dir)} already has files.", file=str(out_dir),
                        hint="Choose another folder with --out, or add --force to write into it.")
    run.term.say(f"Copying the {a.name} example into {_q(out_dir)} ...")
    files = [run.write(out_dir / "model.json", json.dumps(data["model"], indent=2, ensure_ascii=False), "model")]
    for m in data["material"]:
        files.append(run.write(out_dir / "material" / m["name"], m["text"], "material"))
    for i, r in enumerate(data["reviews"], 1):
        files.append(run.write(out_dir / "reviews" / f"review-{i}.json", json.dumps(r, indent=2, ensure_ascii=False), "review"))
    if data["earlier_model"]:
        files.append(run.write(out_dir / "model-before.json",
                               json.dumps(data["earlier_model"], indent=2, ensure_ascii=False), "model"))
    run.term.say("Drawing it ...")
    html = lib.render(data["model"])
    canvas = out_dir / "canvas.html"
    files.append(run.write(canvas, html, "canvas"))
    files.append(run.write(out_dir / "in-words.md", lib.words(data["model"]), "words"))
    run.term.say(f"Wrote {_q(canvas)} ({describe(data['model'])}) and in-words.md")
    rel = _q(out_dir)
    nxt = [f"decisioncraft render {rel}/model.json --open", f"decisioncraft questions {rel}/model.json"]
    if data["reviews"]:
        nxt.append(f"decisioncraft render {rel}/model.json --reviews {rel}/reviews/*.json --open")
    if data["earlier_model"]:
        nxt.append(f"decisioncraft render {rel}/model.json --since {rel}/model-before.json --open")
    if a.open:
        run.open(canvas)
    else:
        nxt.insert(0, f"open {_q(canvas)}")
    if not run.json:
        run.term.say("")
        run.term.say(run.term.paint("Try next:", "bold"))
        for n in nxt:
            run.term.say(f"  {n}")
    return Out(data={"directory": str(out_dir), "example": a.name, "about": data["about"],
                     "summary": summary(data["model"])},
               files=files, next=nxt, text="")


def do_new(run: Run) -> Out:
    a = run.args
    question, title, template, roles, material, folder = a.question, a.title, a.template, a.roles, a.material, a.dir
    if not question:
        if not run.can_ask:
            raise ToolError(
                "missing_argument",
                "--question is needed when decisioncraft can't ask (stdin is not a terminal, "
                "or --yes or --json was given).",
                hint='For example: decisioncraft new --question "Should we lease or buy our next van?" --dir van',
                exit_code=E.USAGE, field="--question",
            )
        from .starter import slug, title_from

        if not template and not roles:
            # The guided interview: one question at a time, then the starter folder.
            from . import interview as iv

            run.term.say(run.term.paint("Start a new decision", "bold") + ". A few questions, one at a time; "
                         "press Enter to skip one.")
            run.term.say("")
            while not question:
                question = run.ask("What are you trying to decide? One sentence is fine")
            folder = folder or run.ask("Folder to create", slug(question))
            r = iv.run_interactive(Path(folder).expanduser(), run.ask, run.term.say, question=question)
            if r.get("mode") == "none":
                run.term.say(r["message"])
                return Out(data=r, text="")
            run.term.say("")
            run.term.say(f"Created {_q(folder)}: model.json and material/README.txt. "
                         f"Suggested mode: {lib.modes()[r['mode']]['label']}.")
            for n in r.get("next", []):
                run.term.say(f"  next: {n}")
            files = [{"path": f, "kind": "model" if f.endswith(".json") else "readme"} for f in r["files"]]
            return Out(data=r, files=files, next=r.get("next", []), text="")

        run.term.say(run.term.paint("Start a new decision", "bold") + " (press Enter to accept the [default]).")
        run.term.say("")
        while not question:
            question = run.ask("What decision are you making? Write it as one question")
        title = title or run.ask("A short title", title_from(question))
        temps = lib.templates()
        run.term.say("")
        run.term.say("How should it be drawn?")
        for i, t in enumerate(temps, 1):
            run.term.say(textwrap.fill(f"{t['about']}", width=WIDTH, initial_indent=f"  {i}. {t['id']}: ",
                                       subsequent_indent="     "))
        default_t = next(i for i, t in enumerate(temps, 1) if t["id"] == "decision-chain")
        while True:
            pick = template or run.ask("Pick a number or name", str(default_t))
            template = temps[int(pick) - 1]["id"] if pick.isdigit() and 1 <= int(pick) <= len(temps) else pick
            if template in {t["id"] for t in temps}:
                break
            run.term.warn(f"{pick} is not one of the choices.")
            template = None
        run.term.say("")
        run.term.say(textwrap.fill("Whose points of view? " + ", ".join(f"{r['id']} ({r['label']})" for r in lib.roles()),
                                   width=WIDTH, subsequent_indent="  "))
        roles = roles or run.ask("Keep all, or list the ids to keep (comma-separated)", "all")
        material = material or run.ask("Where are your notes and documents? (a folder; Enter to make one)", "")
        folder = folder or run.ask("Folder to create", slug(title or question))
    template = template or "decision-chain"
    known = [t["id"] for t in lib.templates()]
    if template not in known:
        raise ToolError("invalid_input", f"Unknown template: {template}. Choose one of {', '.join(known)}.",
                        hint="See them all with: decisioncraft templates", field="--template")
    role_ids = None if not roles or roles == "all" else [r.strip() for r in roles.split(",") if r.strip()]

    if folder:
        from .starter import starter

        target = Path(folder).expanduser()
        if (target / "model.json").exists():
            raise ToolError("already_exists", f"{target}/model.json already exists.", file=str(target / "model.json"),
                            hint="Choose another folder with --dir, or edit the existing model.")
        files_text = lib.starter(template, title or "", question, roles=role_ids, date=a.date, material_hint=material or "")
        files = [run.write(target / rel, text, "model" if rel.endswith(".json") else "readme")
                 for rel, text in files_text.items()]
        model = json.loads(files_text["model.json"])
        rel = _q(target)
        nxt = [
            f"add your notes to {rel}/material/ (see README.txt there)",
            f'decisioncraft draft {rel}/material/*.md --question "{question}" '
            f"--complete-cmd 'YOUR-COMMAND' --out {rel}/model.json",
            f"decisioncraft render {rel}/model.json --open",
        ]
        run.term.say(f"Created {_q(target)}: model.json ({model['maps'][0]['template']}, {len(model['roles'])} roles) "
                     "and material/README.txt")
        if not run.json:
            run.term.say("")
            run.term.say(run.term.paint("Next:", "bold"))
            for n in nxt:
                run.term.say(textwrap.fill(n, width=WIDTH, initial_indent="  ", subsequent_indent="      ",
                                           break_on_hyphens=False, break_long_words=False))
            run.term.say("  (use --provider anthropic --model NAME instead of --complete-cmd to call a vendor directly)")
        return Out(data={"directory": str(target), "model": model}, files=files, next=nxt, text="")

    from .starter import pick_roles, title_from

    model = lib.new(template, title or title_from(question), question, a.date)
    model["roles"] = pick_roles(role_ids)
    if a.out:
        f = run.write(Path(a.out), json.dumps(model, indent=2, ensure_ascii=False), "model")
        run.term.say(f"Wrote {a.out}")
        return Out(data=model, files=[f], text="")
    return Out(data=model)


def _render_once(run: Run, out_path: Path | None) -> Out:
    a = run.args
    run.term.say(f"Reading {a.model} ...")
    model = run.load(a.model)
    reviews = [run.load(r) for r in a.reviews]
    merged = run.load(a.merged) if a.merged else (lib.merge(reviews, model) if reviews else None)
    since = run.load(a.since) if a.since else None
    run.file = a.model
    run.term.say("Checking it and drawing the canvas ...")
    html = lib.render(model, merged=merged, since=since)
    info = {"summary": summary(model), "bytes": len(html.encode("utf-8"))}
    if out_path is None:
        return Out(data={**info, "path": None}, text=html)
    f = run.write(out_path, html, "canvas")
    run.term.say(f"Wrote {_q(out_path)} ({describe(model)}; {_size(info['bytes'])})")
    nxt = [] if a.open else [
        f"decisioncraft render {_q(a.model)}" + (f" --out {_q(out_path)}" if a.out else "") + " --open"
    ]
    return Out(data={**info, "path": str(out_path)}, files=[f], next=nxt, text="")


def do_render(run: Run) -> Out | None:
    a = run.args
    need_file = a.out or a.open or a.watch or run.json or sys.stdout.isatty()
    out_path = Path(a.out).expanduser() if a.out else (_default_canvas(a.model) if need_file else None)
    if not a.watch:
        out = _render_once(run, out_path)
        if a.open and out_path is not None:
            run.open(out_path)
        elif out.next and not run.json:
            run.term.say(f"Open it: {out.next[0]}")
        return out

    watched = [a.model, *a.reviews, *([a.merged] if a.merged else []), *([a.since] if a.since else [])]

    def stamp():
        return tuple(Path(p).expanduser().stat().st_mtime if Path(p).expanduser().exists() else 0 for p in watched)

    def attempt(first: bool):
        try:
            out = _render_once(run, out_path)
            if run.json:
                _print_json(_envelope("render", data=out.data, files=out.files, event="rendered"))
            if first and a.open:
                run.open(out_path)
        except ToolError as e:
            _report(run, "render", e, event="error")
        except Exception as e:  # keep watching whatever happened
            _report(run, "render", classify(e, file=run.file), event="error")

    attempt(True)
    run.term.say(f"Watching {', '.join(watched)} for changes. Press Ctrl-C to stop.")
    last = stamp()
    interval = float(os.environ.get("DECISIONCRAFT_WATCH_INTERVAL", "1"))
    limit = int(os.environ.get("DECISIONCRAFT_WATCH_ROUNDS", "0"))  # for tests; 0 = forever
    rounds = 0
    try:
        while not limit or rounds < limit:
            time.sleep(interval)
            rounds += 1
            now = stamp()
            if now != last:
                last = now
                run.term.say(time.strftime("%H:%M:%S") + " change seen, drawing again ...")
                attempt(False)
    except KeyboardInterrupt:
        pass
    run.term.say("Stopped watching.")
    return None


def do_doctor(run: Run) -> Out:
    a = run.args
    result = lib.doctor(directory=a.dir, complete_cmd=a.complete_cmd, live=getattr(a, "live", False))
    failed = any(c["status"] == "fail" for c in result["checks"])
    err = ToolError("setup_incomplete", result["summary"], hint="Fix the items marked fix, then run doctor again.",
                    exit_code=E.SETUP) if failed else None
    lines = [run.term.paint(f"Decisioncraft {VERSION} setup check", "bold", sys.stdout), ""]
    for c in result["checks"]:
        lines.append(textwrap.fill(c["detail"], width=WIDTH, initial_indent=f"  {run.term.mark(c['status'])}  ",
                                   subsequent_indent=" " * 8))
        if c["fix"] and c["status"] != "ok":
            lines.append(textwrap.fill(f"fix: {c['fix']}", width=WIDTH, initial_indent=" " * 8,
                                       subsequent_indent=" " * 13))
    lines += ["", result["summary"], ""]
    return Out(data=result, text="\n".join(lines), error=err, explained=True)


def do_session(run: Run) -> None:
    a = run.args
    folder = Path(a.dir).expanduser()
    if folder.exists() and (not folder.is_dir() or any(folder.iterdir())):
        raise ToolError(
            "folder_not_empty", f"{_q(folder)} is not a new, empty folder.", file=str(folder), field="--dir",
            hint="Pick a new folder with --dir. To continue earlier answers, add "
            f"--review {_q(folder)}/review.json with a new --dir.",
        )
    model = run.load(a.model)
    review = run.load(a.review) if a.review else None
    run.file = a.model
    complete = None
    if a.complete_cmd or a.provider:
        kwargs, _who = _complete_kwargs(run, name_attr="model_name")
        if "complete" in kwargs:
            complete = kwargs["complete"]
        else:
            from .intelligence import provider_complete
            complete = provider_complete(kwargs["provider"], kwargs.get("model_name"))
    active = lib.session(model, a.dir, review=review, source_root=a.source_root, prepared_by=a.prepared_by,
                         complete=complete)
    active.close_on_finish = a.until_finished

    def emit(event, value):
        if run.json:
            _print_json(_envelope("session", data=value, event=event))
        else:
            sys.stdout.write(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
            sys.stdout.flush()

    try:
        emit("started", active.info())
        run.term.say(f"Review is open at {active.url}")
        if a.open:
            import webbrowser

            webbrowser.open(active.url)
        if a.until_finished:
            run.term.say("Waiting for the person to press Finish review (Ctrl-C to stop) ...")
            active.wait()
            emit("finished", active.status())
        else:
            run.term.say("Answers save as the person works. Press Ctrl-C to stop the review.")
            while True:
                active.wait(1)
                if active.wait(0):
                    time.sleep(1)
    except KeyboardInterrupt:
        run.term.say("Stopped the review. Saved answers stay in the folder.")
    finally:
        active.close()


def _pretty_problems(problems: list[dict], term: Term) -> str:
    if not problems:
        return "No problems found.\n"
    lines = []
    for p in problems:
        level = term.paint(f"{p['level']:<7}", "red" if p["level"] == "error" else "yellow", sys.stdout)
        lines.append(textwrap.fill(f"{p.get('path', '')}: {p['message']}", width=WIDTH,
                                   initial_indent=f"  {level} ", subsequent_indent=" " * 11))
    n_err = sum(1 for p in problems if p["level"] == "error")
    lines += ["", f"{n_err} error(s), {len(problems) - n_err} warning(s)."]
    return "\n".join(lines) + "\n"


def do_validate(run: Run) -> Out:
    model = run.load(run.args.model)
    problems = lib.validate(model)
    errs = [p for p in problems if p["level"] == "error"]
    err = None
    if errs:
        from .model import ModelError

        err = classify(ModelError(errs), file=run.args.model)
        err.problems = problems
    return Out(data=problems, text=_pretty_problems(problems, run.term) if run.pretty else None, error=err,
               explained=run.pretty)


def do_questions(run: Run) -> Out:
    model = run.load(run.args.model)
    reviews = [run.load(r) for r in run.args.reviews]
    run.file = run.args.model
    qs = lib.questions(model, lib.merge(reviews, model) if reviews else None)
    text = None
    if run.pretty:
        lines = [f"{len(qs)} questions to decide, most urgent first:", ""]
        for i, q in enumerate(qs, 1):
            urgency = {"must": "must decide", "should": "should decide", "info": "for information"}.get(
                q.get("urgency"), q.get("urgency"))
            meta = ", ".join(x for x in (urgency, q.get("role")) if x)
            lines.append(textwrap.fill(f"{q.get('question')}", width=WIDTH, initial_indent=f"{i:>3}. ",
                                       subsequent_indent="     "))
            if meta:
                lines.append(f"     ({meta})")
        text = "\n".join(lines) + "\n"
    return Out(data=qs, text=text)


def do_words(run: Run) -> Out:
    a = run.args
    model = run.load(a.model)
    reviews = [run.load(r) for r in a.reviews]
    run.file = a.model
    md = lib.words(model, lib.merge(reviews, model) if reviews else None)
    if a.out:
        f = run.write(Path(a.out), md, "words")
        run.term.say(f"Wrote {a.out} ({len(md.splitlines())} lines)")
        return Out(data={"path": a.out}, files=[f], text="")
    return Out(data={"markdown": md, "path": None}, text=md)


def do_merge(run: Run) -> Out:
    a = run.args
    model = run.load(a.model)
    reviews = [run.load(r) for r in a.reviews]
    run.file = None
    merged = lib.merge(reviews, model)
    if a.out:
        f = run.write(Path(a.out), json.dumps(merged, indent=2, ensure_ascii=False), "merged")
        run.term.say(f"Wrote {a.out} ({len(reviews)} review(s) merged)")
        return Out(data=merged, files=[f], text="")
    return Out(data=merged)


def do_diff(run: Run) -> Out:
    old, new = run.load(run.args.old), run.load(run.args.new)
    run.file = None
    d = lib.diff(old, new)
    text = None
    if run.pretty:
        lines = []
        for key in ("added", "changed", "removed"):
            items = d.get(key) or []
            lines.append(f"{key.capitalize()}: {len(items)}")
            for it in items[:20]:
                label = it.get("id") if isinstance(it, dict) else it
                extra = f" ({', '.join(it.get('fields', []))})" if isinstance(it, dict) and it.get("fields") else ""
                lines.append(f"  {label}{extra}")
        text = "\n".join(lines) + "\n"
    return Out(data=d, text=text)


def do_handoff(run: Run) -> Out:
    a = run.args
    result = lib.handoff(run.load(a.model), run.load(a.review))
    if a.out:
        f = run.write(Path(a.out), json.dumps(result, indent=2, ensure_ascii=False), "handoff")
        run.term.say(f"Wrote {a.out}")
        return Out(data=result, files=[f], text="")
    return Out(data=result)


def _complete_kwargs(run: Run, *, name_attr: str) -> tuple[dict, str]:
    """The model that answers: --complete-cmd, or a provider and model resolved from flags,
    DECISIONCRAFT_PROVIDER/DECISIONCRAFT_MODEL, the user config, or whichever API key is set.
    Says on stderr which one and why. Sets run.escalate to the stronger model (or None)."""
    a = run.args
    run.escalate = None
    if a.complete_cmd:
        from .intelligence import command_complete

        return {"complete": command_complete(a.complete_cmd)}, f"your command ({a.complete_cmd.split()[0]})"
    from .intelligence import ProviderError, escalation_complete, provider_complete, resolve

    name = getattr(a, "model" if name_attr == "model" else "model_name", None)
    try:
        r = resolve(a.provider, name)
    except ProviderError as e:
        raise ToolError(
            "provider_not_configured", str(e),
            hint="Set ANTHROPIC_API_KEY or OPENAI_API_KEY (it then picks for you), or name one: "
            "--provider anthropic --model claude-sonnet-5-5   Check with: decisioncraft doctor",
            exit_code=E.SETUP, field="--provider",
        ) from None
    fn = provider_complete(r["provider"], r["model"])
    if r["escalate"]:
        run.escalate = escalation_complete(r["provider"], r["escalate"])
    more = f"; tries {r['escalate']} once if the draft still has problems" if run.escalate else ""
    run.term.say(f"Using {r['provider']} {r['model']} ({r['why']}{more}).")
    return {"complete": fn}, f"{r['provider']} {r['model']}"


# Prices per million tokens (input, output) for the estimate printed before a long run.
_PRICES = {"claude-sonnet-5-5": (2.0, 10.0), "claude-opus-5-5": (4.0, 20.0), "claude-haiku-4-5": (1.0, 5.0)}


def _estimate(model_name: str, chars: int, roles: int) -> str:
    """A rough time and cost for map: one draft (sometimes a repair), then a small call per role
    that rereads the drafted model."""
    material = min(chars, 60000) // 4  # each role rereads up to 60,000 characters of material
    tokens_in = (chars // 4 + 15000) * 2 + roles * (material + 16000) * 1.4
    tokens_out = 18000 + roles * 2500
    low, high = max(2, round(tokens_out / 12000)), max(4, round(tokens_out / 6000))
    price = _PRICES.get(model_name)
    cost = f", about ${(tokens_in * price[0] + tokens_out * price[1]) / 1e6:.2f}" if price else ""
    return f"roughly {low}-{high} minutes{cost}"


def do_draft(run: Run) -> Out:
    a = run.args
    material = run.material(a.material)
    brief = run.load(a.brief) if a.brief else None
    run.file = None
    kwargs, who = _complete_kwargs(run, name_attr="model")
    chars = sum(len(m["text"]) for m in material)
    run.term.say(f"Reading {len(material)} file(s) ({chars:,} characters) ...")
    run.term.say(f"Asking {who} to draft the model. This can take a minute or two ...")
    model = lib.draft(material, template=a.template, question=a.question, title=a.title, date=a.date,
                      brief=brief, escalate=getattr(run, "escalate", None), progress=run.term.say, **kwargs)
    run.term.say(f"Checked the draft: {describe(model)}.")
    return _model_result(run, model, verb="Drafted")


def do_review_notes(run: Run) -> Out:
    a = run.args
    if not a.model:
        raise ToolError("missing_argument", "Give the model the answers were made on, before --notes.",
                        hint="decisioncraft perspectives model.json --notes answers.json --dry-run",
                        exit_code=E.USAGE, field="model")
    model = run.load(a.model)
    review = run.load(a.notes)
    run.file = a.notes
    from .review import check_review, notes_to_ask
    problems = check_review(review)
    if problems:
        raise ToolError("invalid_review", " ".join(problems), file=a.notes, exit_code=E.INPUT)
    roles = [r.strip() for r in a.roles.split(",") if r.strip()] if a.roles else None
    plan = notes_to_ask(model, review, roles)
    asked = [{"note": p["note"]["id"], "text": p["note"]["text"], "on": p["target"]["title"], "roles": p["roles"]} for p in plan]
    if a.dry_run:
        lines = [f"Would ask about {len(plan)} note(s):"] + [
            f"  {x['note']} on {x['on']}: {', '.join(x['roles'])}" for x in asked]
        return Out(data={"dry_run": True, "asked": asked, "replies_added": 0}, text="\n".join(lines) + "\n")
    if not plan:
        run.term.say("No notes are waiting for experts.")
        return Out(data={"dry_run": False, "asked": [], "replies_added": 0, "review": review})
    run.file = None
    kwargs, who = _complete_kwargs(run, name_attr="model_name")
    before = sum(len(n.get("replies", [])) for n in review.get("notes", []))
    run.term.say(f"Asking {who} for expert replies on {len(plan)} note(s) ...")
    out = lib.review_notes(model, review, roles=roles, **kwargs)
    added = sum(len(n.get("replies", [])) for n in out.get("notes", [])) - before
    run.term.say(f"Added {added} repl{'y' if added == 1 else 'ies'}.")
    data = {"dry_run": False, "asked": asked, "replies_added": added, "review": out}
    if a.out:
        f = run.write(Path(a.out), json.dumps(out, indent=2, ensure_ascii=False), "review")
        nxt = f"decisioncraft render {_q(a.model)} --reviews {_q(a.out)} --open"
        run.term.say(f"Wrote {a.out}. See the threads: {nxt}")
        return Out(data=data, files=[f], next=[nxt], text="")
    return Out(data=data)


def do_perspectives(run: Run) -> Out:
    a = run.args
    if a.notes:
        return do_review_notes(run)
    if not a.model:
        raise ToolError("missing_argument", "Give the model JSON file.", exit_code=E.USAGE, field="model",
                        hint="decisioncraft perspectives model.json --complete-cmd 'my-host complete'")
    model = run.load(a.model)
    material = run.material(a.material)
    run.file = None
    kwargs, who = _complete_kwargs(run, name_attr="model_name")
    before = summary(model)["notes"]
    run.term.say(f"Asking {who} for up to {a.per_role} notes per role ...")
    out = lib.perspectives(model, material=material, per_role=a.per_role,
                           escalate=getattr(run, "escalate", None), progress=run.term.say, **kwargs)
    run.term.say(f"Added {summary(out)['notes'] - before} note(s); {describe(out)}.")
    return _model_result(run, out, verb="Updated")


def _model_result(run: Run, model: dict, *, verb: str) -> Out:
    a = run.args
    if a.out:
        f = run.write(Path(a.out), json.dumps(model, indent=2, ensure_ascii=False), "model")
        run.term.say(f"{verb} {a.out}. Read it before you share it: decisioncraft render {_q(a.out)} --open")
        return Out(data=model, files=[f], next=[f"decisioncraft render {_q(a.out)} --open"], text="")
    return Out(data=model)


def do_simple(run: Run) -> Out:
    cmd = run.args.command
    if cmd == "manifest":
        return Out(data=lib.manifest())
    if cmd == "roles":
        roles = lib.roles()
        text = None
        if run.pretty:
            text = "\n".join(_wrap(r["id"], f"{r['label']}: {r.get('asks', '')}", 13) for r in roles) + "\n"
        return Out(data=roles, text=text)
    if cmd == "guide":
        g = lib.guide()
        text = None
        if run.pretty or not run.args.json:
            text = "# The model format\n\n" + g["model_format"].strip() + "\n\n# Writing guide\n\n" + g["writing_guide"].strip() + "\n"
        return Out(data=g, text=text)
    if cmd == "templates":
        temps = lib.templates()
        text = None
        if run.pretty:
            text = "\n".join(_wrap(t["id"], f"{t['title']}. {t['about']}", 20) for t in temps) + "\n"
        return Out(data=temps, text=text)
    if cmd == "discover":
        return Out(data=lib.discover(run.args.question))
    raise AssertionError(cmd)


def _text_complete(run: Run):
    """A model for reading free text, only when the caller named one."""
    a = run.args
    if getattr(a, "complete_cmd", None) or getattr(a, "provider", None):
        kwargs, _ = _complete_kwargs(run, name_attr="model")
        if "complete" in kwargs:
            return kwargs["complete"]
        from .intelligence import provider_complete

        return provider_complete(kwargs["provider"], kwargs.get("model"))
    return None


def do_triage(run: Run) -> Out:
    a = run.args
    answers = {k: getattr(a, k) for k in ("cost", "reversible", "people", "deadline") if getattr(a, k)}
    r = lib.triage(answers, text=a.text, complete=_text_complete(run) if a.text else None)
    text = None
    if run.pretty:
        t = run.term
        lines = [t.paint(f"{r['label']}", "bold") + f": {r['does']}"]
        if r["why"]:
            lines.append("Why: " + "; ".join(r["why"]) + ".")
        if r["alternative"]:
            lines.append(f"If the deadline can move: {lib.modes()[r['alternative']]['label']}.")
        for m in r["missing"]:
            lines.append(f"Worth asking: {m['question']}")
        lines.append(r["offer"])
        text = "\n".join(textwrap.fill(x, width=WIDTH, subsequent_indent="  ") for x in lines) + "\n"
    return Out(data=r, text=text, next=r["next"])


def _parse_scores(items: list[str]) -> list[dict]:
    out = []
    for item in items:
        parts = item.rsplit("=", 2)
        if len(parts) != 3:
            raise ToolError("invalid_input", f"--score {item!r} should look like OPTION=CRITERION=4.",
                            field="--score", exit_code=E.USAGE, hint='For example: --score "Buy it=reliability=4"')
        try:
            n = float(parts[2])
        except ValueError:
            raise ToolError("invalid_input", f"--score {item!r}: the score must be a number from 1 to 5.",
                            field="--score", exit_code=E.USAGE) from None
        out.append({"option": parts[0].strip(), "criterion": parts[1].strip(), "score": n})
    return out


def do_quick(run: Run) -> Out:
    a = run.args
    options, criteria, scores = list(a.option), list(a.criterion), _parse_scores(a.score)
    question = a.question
    if a.from_model:
        model = run.load(a.from_model)
        comp = model.get("comparison") or {}
        question = question or model.get("question", "")
        # A personal-decision model keeps options and criteria at the top level.
        top_opts = {o.get("id"): o.get("name") for o in model.get("options") or [] if isinstance(o, dict)}
        top_crit = {c.get("id"): c for c in model.get("criteria") or [] if isinstance(c, dict)}
        options = options or [n for n in top_opts.values() if n] \
            or [o.get("title") for o in comp.get("options", []) if o.get("title")]
        def _crit(c):
            if c.get("kind") == "must":
                return {"label": c.get("name"), "importance": "must"}
            w = c.get("weight") if isinstance(c.get("weight"), (int, float)) else 2
            # Engine weights run 0-5; keep them, but never let a weight read as a must-have.
            return {"label": c.get("name"), "importance": "important" if w >= 3 else "nice",
                    "weight": max(1, round(float(w)))}
        criteria = criteria or [_crit(c) for c in top_crit.values() if c.get("name")] \
            or [{"label": c["label"], "importance": c.get("importance")}
                for c in comp.get("criteria", []) if c.get("label")]
        if not scores and top_opts and top_crit:
            scores = []
            for s in model.get("scores") or []:
                if not (isinstance(s, dict) and s.get("criterion") in top_crit and top_opts.get(s.get("option"))):
                    continue
                if isinstance(s.get("meets"), bool):  # a must-have: meets is 5, fails is 1
                    n = 5 if s["meets"] else 1
                elif isinstance(s.get("value"), (int, float)):
                    n = int(s["value"])
                else:
                    continue
                scores.append({"option": top_opts[s["option"]], "criterion": top_crit[s["criterion"]].get("name"),
                               "score": n})
    if a.scores:
        loaded = run.load(a.scores)
        if isinstance(loaded, dict):
            loaded = [{"option": o, "criterion": c, "score": v} for o, row in loaded.items() for c, v in (row or {}).items()]
        scores = scores + list(loaded)
    complete = _text_complete(run) if a.text and not options else None
    if a.text and not options and complete is None:
        raise ToolError("missing_argument", "Give the options with --option, or a model to read them from --text.",
                        field="--option", exit_code=E.USAGE,
                        hint='For example: --option "Renew" --option "Buy", or add --complete-cmd "my-host complete".')
    if not options:
        raise ToolError("missing_argument", "A quick comparison needs at least two options.", field="--option",
                        exit_code=E.USAGE, hint='Add --option "A" --option "B" (doing nothing can be one).')
    r = lib.quick(options, criteria, scores or None, question=question, text=a.text, complete=complete)
    text = None
    if run.pretty:
        lines = [run.term.paint(r["question"], "bold")] if r["question"] else []
        if r["table"]:
            lines += [r["table"], ""]
        if r["lean"]:
            lines.append("Lean: " + r["lean"]["reason"])
        if r["check_first"]:
            lines.append("Check first: " + r["check_first"]["text"] + " " + r["check_first"]["why"])
        lines += ["Ask: " + q for q in r["ask"]]
        lines.append(r["note"])
        text = "\n".join(lines) + "\n"
    return Out(data=r, text=text)


def do_interview(run: Run) -> Out:
    a = run.args
    folder = Path(a.dir).expanduser()
    if a.answer is None and not a.next and not a.reset and run.can_ask:
        from . import interview as iv

        run.term.say(run.term.paint("A few questions, one at a time.", "bold") + " Press Enter to skip one.")
        r = iv.run_interactive(folder, run.ask, run.term.say, question=a.question, kind=a.kind)
    else:
        try:
            if a.next and not a.reset:
                from . import interview as iv

                state = iv.load(folder)
                r = lib.interview_step(folder, None, question=a.question, kind=a.kind) if state is None \
                    else iv.step(folder, None)
            else:
                r = lib.interview_step(folder, a.answer, question=a.question, kind=a.kind, reset=a.reset)
        except PermissionError:
            raise ToolError("no_write_access", f"Can't write to {folder}.", file=str(folder), exit_code=E.SETUP,
                            hint="Choose a folder you can write to with --dir.") from None
    files = [{"path": f, "kind": "model" if f.endswith(".json") else "readme"} for f in r.get("files", [])]
    text = None
    if run.pretty:
        if r["done"]:
            text = (f"Done. Wrote {_q(r['model_path'])}. Suggested mode: {lib.modes()[r['mode']]['label']}.\n"
                    + "".join(f"  next: {n}\n" for n in r.get("next", [])))
        else:
            q = r["question"]
            text = f"{q['ask']}\n  ({q['why']})\n" + "".join(f"  {i}. {c}\n" for i, c in enumerate(q.get("choices", []), 1)) \
                + f"Answer with: decisioncraft interview --dir {_q(folder)} --answer \"...\"\n"
    return Out(data=r, text=text, files=files, next=r.get("next", []))


def do_map(run: Run) -> Out:
    a = run.args
    from .mapper import detect, map_roles
    from .starter import slug

    roles = [r.strip() for r in a.roles.split(",") if r.strip()] if a.roles else None
    try:
        map_roles(roles)
    except ValueError as e:
        raise ToolError("invalid_input", str(e), field="--roles", exit_code=E.USAGE,
                        hint="See the role ids with: decisioncraft roles") from None
    answers = run.load(a.answers) if a.answers else None
    if a.dry_run:
        plan = lib.plan_map(a.target, roles=roles, budget=a.budget, answers=answers)
        text = None
        if run.pretty:
            lines = [run.term.paint(f"map {a.target}", "bold") + f"  ({plan['kind']})", f"Question: {plan['question']}"]
            if plan["read"]:
                lines.append(f"Would read {len(plan['read'])} files, {_size(plan['chars'])}:")
                lines += [f"  {r['path']}" + (" (first part)" if r["cut"] else "") for r in plan["read"][:40]]
                if len(plan["read"]) > 40:
                    lines.append(f"  ... and {len(plan['read']) - 40} more")
            if plan["needs"]:
                n = plan["needs"]
                lines.append(n.get("message") or "Would ask: " + " / ".join(q["ask"] for q in n["questions"]))
            lines.append(f"Roles: {', '.join(plan['roles'])}.")
            lines.append(f"Model calls: {plan['model_calls']} (none now: this was a dry run).")
            text = "\n".join(lines) + "\n"
        return Out(data=plan, text=text)
    if a.starter:
        kind = detect(a.target)
        page = Path(a.page).expanduser().read_text(encoding="utf-8") if a.page else ""
        try:
            st = lib.map_starter(a.target, roles=roles, question=a.question, answers=answers,
                                 page_text=page, budget=a.budget)
        except ValueError as e:
            raise ToolError("invalid_input", str(e), field="--page", exit_code=E.INPUT,
                            hint="Save the page's text to a file and pass --page FILE.") from None
        if kind in ("repo", "folder") and not st["plan"]["read"]:
            raise ToolError("invalid_input", f"Found nothing readable in {a.target}.", file=a.target,
                            hint="Point it at a folder with Markdown, text or code files.")
        name = Path(a.target).expanduser().resolve().name if kind not in ("topic", "url") else slug(a.target)
        folder = Path(a.dir).expanduser() if a.dir else Path(f"decisioncraft-map-{slug(name)}")
        files = [run.write(folder / "model.json", json.dumps(st["model"], indent=2, ensure_ascii=False), "model"),
                 run.write(folder / "material" / "digest.md", st["digest"], "material"),
                 run.write(folder / "FILL-IN.md", st["instructions"], "instructions")]
        mp = _q(folder / "model.json")
        run.term.say(f"Wrote a starter map in {_q(folder)}: read FILL-IN.md, fill in model.json from "
                     f"material/digest.md, then validate and render.")
        nxt = ["decisioncraft guide", f"decisioncraft validate {mp}", f"decisioncraft render {mp} --open"]
        return Out(data={"directory": str(folder.resolve()), "model_path": str((folder / "model.json").resolve()),
                         "digest_path": str((folder / "material" / "digest.md").resolve()),
                         "instructions_path": str((folder / "FILL-IN.md").resolve()),
                         "instructions": st["instructions"], "plan": st["plan"]},
                   files=files, next=nxt, text="")
    kind = detect(a.target)
    if kind == "url" and not a.page and not a.allow_network:
        raise ToolError("invalid_input", "Decisioncraft does not fetch web pages unless you allow it.",
                        hint="Save the page's text to a file and pass --page FILE, or add --allow-network.",
                        field="--page", exit_code=E.INPUT)
    if kind in ("repo", "folder"):
        plan = lib.plan_map(a.target, roles=roles, budget=a.budget)
        if not plan["read"]:
            raise ToolError("invalid_input", f"Found nothing readable in {a.target}.", file=a.target,
                            hint="Point it at a folder with Markdown, text or code files.")
    kwargs, who = _complete_kwargs(run, name_attr="model")
    page = Path(a.page).expanduser().read_text(encoding="utf-8") if a.page else ""
    chars = plan["chars"] if kind in ("repo", "folder") else len(page) or 4000
    est = _estimate(getattr(kwargs["complete"], "model", ""), chars, len(roles or []) or 8)
    run.term.say(f"Mapping {a.target} ({kind}) with {who}: {est}.")
    if chars > 200_000 and run.can_ask:
        if run.ask("That is a lot to read. Go ahead? (y/n)", "y").lower() not in ("y", "yes"):
            raise ToolError("cancelled", "Stopped before calling the model.", exit_code=E.USAGE,
                            hint="Read less with --budget 60000, or add --yes to skip this question.")
    result = lib.map_target(a.target, roles=roles, question=a.question, answers=answers, page_text=page,
                            budget=a.budget, allow_network=a.allow_network, progress=run.term.say,
                            escalate=getattr(run, "escalate", None), **kwargs)
    usage = getattr(kwargs["complete"], "usage", None)
    if usage and usage.get("calls"):
        run.term.say(f"Model use: {usage['calls']} call(s), {usage['input_tokens']:,} tokens in, "
                     f"{usage['output_tokens']:,} out.")
    model = result["model"]
    name = Path(a.target).expanduser().resolve().name if kind not in ("topic", "url") else slug(a.target)
    folder = Path(a.dir).expanduser() if a.dir else Path(f"decisioncraft-map-{slug(name)}")
    files = [run.write(folder / "model.json", json.dumps(model, indent=2, ensure_ascii=False), "model")]
    html = lib.render(model)
    canvas = folder / "canvas.html"
    files.append(run.write(canvas, html, "canvas"))
    s = summary(model)
    run.term.say(f"Wrote {_q(canvas)} ({describe(model)}; {_size(len(html.encode('utf-8')))}).")
    nxt = [f"decisioncraft render {_q(folder / 'model.json')} --open"]
    if a.open:
        run.open(canvas)
    elif not run.json:
        run.term.say(f"Open it with --open, or: open {_q(canvas)}")
    return Out(data={"directory": str(folder.resolve()), "model_path": str((folder / "model.json").resolve()),
                     "canvas_path": str(canvas.resolve()), "summary": s, "plan": result["plan"]},
               files=files, next=nxt, text="")


def do_mcp(run: Run) -> None:
    import importlib.util

    if importlib.util.find_spec("mcp") is None:
        raise ToolError("missing_prerequisite", "The mcp package is not installed, so the MCP server can't start.",
                        exit_code=E.SETUP,
                        hint="uv tool install --force 'amplifier-smart-tool-decisioncraft[mcp]' "
                        "(or pip install 'amplifier-smart-tool-decisioncraft[mcp]')")
    from .mcp_server import serve

    serve()


def do_config(run: Run) -> Out:
    a = run.args
    from .intelligence import ProviderError, config_path, load_config, resolve, save_config

    if a.action in ("set", "unset"):
        if not a.key or (a.action == "set" and not a.value):
            raise ToolError("missing_argument", f"Say what to {a.action}.", exit_code=E.USAGE,
                            hint="decisioncraft config set provider anthropic   or   decisioncraft config unset model")
        try:
            save_config({a.key: a.value if a.action == "set" else None})
        except ValueError as e:
            raise ToolError("invalid_input", str(e), exit_code=E.USAGE, field=a.key,
                            hint="decisioncraft config set provider anthropic") from None
    settings = load_config()
    try:
        r = resolve()
        resolved = {"provider": r["provider"], "model": r["model"], "why": r["why"]}
    except ProviderError as e:
        resolved = {"error": str(e)}
    lines = [f"Settings file: {config_path()}"]
    lines += [f"  {k} = {v}" for k, v in settings.items()] or ["  (nothing set)"]
    lines.append(f"Answers with: {resolved['provider']} {resolved['model']} ({resolved['why']})"
                 if "provider" in resolved else f"Answers with: nothing yet. {resolved['error']}")
    return Out(data={"path": str(config_path()), "settings": settings, "resolved": resolved},
               text="\n".join(lines) + "\n")


HANDLERS = {
    "config": do_config,
    "example": do_example, "new": do_new, "render": do_render, "doctor": do_doctor,
    "session": do_session, "questions": do_questions, "words": do_words, "merge": do_merge,
    "diff": do_diff, "validate": do_validate, "handoff": do_handoff, "draft": do_draft,
    "perspectives": do_perspectives, "discover": do_simple, "templates": do_simple, "guide": do_simple,
    "roles": do_simple, "manifest": do_simple, "mcp": do_mcp,
    "triage": do_triage, "quick": do_quick, "interview": do_interview, "map": do_map,
}


# ---------------------------------------------------------------- output


def _print_json(value) -> None:
    sys.stdout.write(json.dumps(value, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _report(run: Run, command: str, err: ToolError, *, event=None) -> None:
    if run.json:
        _print_json(_envelope(command, err=err, event=event))
        return
    t = run.term
    print(t.paint("decisioncraft: ", "red") + err.message, file=sys.stderr)
    for p in err.problems[:12]:
        level = p.get("level", "error")
        print(f"  {level}: {p.get('path', '')}: {p.get('message', '')}", file=sys.stderr)
    if len(err.problems) > 12:
        print(f"  ... and {len(err.problems) - 12} more (decisioncraft validate shows them all)", file=sys.stderr)
    if err.file and err.code not in ("invalid_model",):
        print(f"  file: {err.file}", file=sys.stderr)
    if err.hint:
        print(t.paint("  What to do: ", "bold") + err.hint, file=sys.stderr)


def main(argv=None) -> int:
    global _JSON_MODE
    argv = list(sys.argv[1:] if argv is None else argv)
    _JSON_MODE = "--json" in argv[: argv.index("--")] if "--" in argv else "--json" in argv
    parser = build()
    if not argv:
        sys.stdout.write(start_screen())
        return E.OK
    args = parser.parse_args(argv)
    if args.command is None:
        if args.json:
            _print_json(_envelope(None, data={"version": VERSION, "commands": list(CAPABILITIES),
                                              "next": ["decisioncraft example medical --open"]}))
        else:
            sys.stdout.write(start_screen())
        return E.OK
    run = Run(args)
    cmd = args.command
    try:
        out = HANDLERS[cmd](run)
    except KeyboardInterrupt:
        err = ToolError("interrupted", "Stopped before finishing.", exit_code=E.INTERRUPTED)
        _report(run, cmd, err)
        return E.INTERRUPTED
    except Exception as exc:  # every failure is reported once, with a code and a hint
        if getattr(args, "debug", False):
            traceback.print_exc()
        err = classify(exc, file=run.file, model_backed=cmd in MODEL_BACKED)
        _report(run, cmd, err)
        return err.exit_code
    if out is None:  # long-running commands print as they go
        return E.OK
    if run.json:
        _print_json(_envelope(cmd, data=out.data, files=out.files, next_steps=out.next, err=out.error))
    else:
        if out.text is not None:
            if out.text:
                sys.stdout.write(out.text if out.text.endswith("\n") else out.text + "\n")
        elif out.data is not None:
            sys.stdout.write(json.dumps(out.data, indent=2, ensure_ascii=False) + "\n")
        sys.stdout.flush()
        if out.error is not None and not out.explained:
            _report(run, cmd, out.error)
    return out.error.exit_code if out.error else E.OK
