"""Command line adapter: reads files, calls the library, prints or writes the result."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import lib
from .help import CAPABILITIES, capability_skill, skill
from .intelligence import ProviderError
from .model import ModelError, require_valid


class SkillHelp(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        print(skill() if self.const is None else
              capability_skill(self.const, argument_reference=parser.format_help()))
        parser.exit()


class SkillParser(argparse.ArgumentParser):
    def __init__(self, *args, capability=None, **kwargs):
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self.add_argument("-h", action="help", help="Show the short argument reference.")
        self.add_argument("--help", action=SkillHelp, nargs=0, const=capability,
                          help="Read the full usage skill.")


def _load(path: str):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(_fail(f"File not found: {path}"))
    except json.JSONDecodeError as e:
        raise SystemExit(_fail(f"{path} is not valid JSON: {e}"))


def _material(paths):
    out = []
    for p in paths or []:
        try:
            out.append({"name": Path(p).name, "text": Path(p).read_text(encoding="utf-8")})
        except (OSError, UnicodeDecodeError) as e:
            raise SystemExit(_fail(f"Could not read {p}: {e}"))
    return out


def _fail(msg: str) -> int:
    print(f"decisioncraft: {msg}", file=sys.stderr)
    return 1


def _emit(value, out: str | None):
    text = value if isinstance(value, str) else json.dumps(value, indent=2, ensure_ascii=False)
    if out:
        Path(out).write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
        print(f"Wrote {out}", file=sys.stderr)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


def build() -> SkillParser:
    p = SkillParser(prog="decisioncraft",
                    description="Map how a problem works, gather every point of view, and "
                                "decide together. --help prints the full skill.")
    sub = p.add_subparsers(dest="command", required=True, parser_class=SkillParser)

    def cap(name):
        return sub.add_parser(name, capability=name, help=f"[{CAPABILITIES[name]['kind']}] "
                              + CAPABILITIES[name]["summary"])

    for name in ("manifest", "templates", "roles"):
        cap(name)
    c = cap("new")
    c.add_argument("--template", required=True)
    c.add_argument("--title", required=True)
    c.add_argument("--question", required=True)
    c.add_argument("--date", default="")
    c.add_argument("--out")
    c = cap("validate")
    c.add_argument("model")
    for name in ("render", "words", "questions"):
        c = cap(name)
        c.add_argument("model")
        c.add_argument("--reviews", nargs="*", default=[])
        if name == "render":
            c.add_argument("--merged")
            c.add_argument("--since")
        if name != "questions":
            c.add_argument("--out")
    c = cap("merge")
    c.add_argument("model")
    c.add_argument("reviews", nargs="+")
    c.add_argument("--out")
    c = cap("diff")
    c.add_argument("old")
    c.add_argument("new")
    c = cap("draft")
    c.add_argument("material", nargs="+")
    c.add_argument("--template", required=True)
    c.add_argument("--question", required=True)
    c.add_argument("--title", default="")
    c.add_argument("--date", default="")
    c.add_argument("--provider", required=True)
    c.add_argument("--model")
    c.add_argument("--out")
    c = cap("perspectives")
    c.add_argument("model")
    c.add_argument("material", nargs="*")
    c.add_argument("--per-role", type=int, default=3)
    c.add_argument("--provider", required=True)
    c.add_argument("--model")
    c.add_argument("--out")
    return p


def main(argv=None) -> int:
    args = build().parse_args(argv)
    try:
        cmd = args.command
        if cmd == "manifest":
            _emit(lib.manifest(), None)
        elif cmd == "templates":
            _emit(lib.templates(), None)
        elif cmd == "roles":
            _emit(lib.roles(), None)
        elif cmd == "new":
            _emit(lib.new(args.template, args.title, args.question, args.date), args.out)
        elif cmd == "validate":
            problems = lib.validate(_load(args.model))
            _emit(problems, None)
            return 1 if any(p["level"] == "error" for p in problems) else 0
        elif cmd in ("render", "words", "questions"):
            model = _load(args.model)
            reviews = [_load(r) for r in args.reviews]
            merged = lib.merge(reviews, model) if reviews else None
            if cmd == "render":
                if args.merged:
                    merged = _load(args.merged)
                since = _load(args.since) if args.since else None
                _emit(lib.render(model, merged=merged, since=since), args.out)
            elif cmd == "words":
                require_valid(model)
                _emit(lib.words(model, merged), args.out)
            else:
                require_valid(model)
                _emit(lib.questions(model, merged), None)
        elif cmd == "merge":
            model = _load(args.model)
            _emit(lib.merge([_load(r) for r in args.reviews], model), args.out)
        elif cmd == "diff":
            _emit(lib.diff(_load(args.old), _load(args.new)), None)
        elif cmd == "draft":
            model = lib.draft(_material(args.material), template=args.template,
                              question=args.question, title=args.title, date=args.date,
                              provider=args.provider, model=args.model)
            _emit(model, args.out)
        elif cmd == "perspectives":
            model = lib.perspectives(_load(args.model), material=_material(args.material),
                                     per_role=args.per_role, provider=args.provider,
                                     model_name=args.model)
            _emit(model, args.out)
    except ModelError as e:
        for p in e.problems:
            print(f"  {p.get('path', '')}: {p['message']}", file=sys.stderr)
        return _fail("the model has problems (listed above).")
    except (ProviderError, ValueError) as e:
        return _fail(str(e))
    return 0
