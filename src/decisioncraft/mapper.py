"""Point it at anything: a code repository, a folder or file of notes, a web page, or a topic.

`map` works out what the target is, gathers material from it (deterministic), then asks a
model to draw how it works today, propose how it could work, turn the differences into gaps
with user stories and "done when" checks, and add notes from each role, each ending in a
question. The canvas opens with notes on the map and the What changes view.

Gathering is code: it reads files within a size budget, numbers their lines so every claim
can cite `path:line`, and records what it read. `plan_map` (and `--dry-run`) shows exactly
what would be read and asked, with no model call. Drafting uses the same model routes as
`draft`: a host's own model, a command, or a vendor SDK.
"""

from __future__ import annotations

import fnmatch
import html as _html
import os
import re
import subprocess
from datetime import date as _date, datetime
from pathlib import Path

from .model import default_roles

TEXT_EXT = {".md", ".markdown", ".txt", ".rst", ".adoc", ".html", ".htm", ".csv", ".json", ".yaml",
            ".yml", ".toml", ".pdf"}
CODE_EXT = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".java", ".kt", ".rb", ".php", ".cs",
            ".swift", ".scala", ".sql", ".prisma", ".graphql", ".proto", ".sh", ".vue", ".svelte", ".ex",
            ".exs", ".c", ".h", ".cpp", ".hpp"}
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".next", "out", "target", "vendor", ".venv", "venv",
             "__pycache__", ".pytest_cache", ".mypy_cache", "coverage", ".turbo", ".cache", ".idea", ".vscode",
             ".work", "_site"}
# What to read first in a repository, best first. Each: (label, glob patterns).
PRIORITY = [
    ("readme", ["README*", "readme*", "*/README*"]),
    ("docs", ["docs/**/*.md", "doc/**/*.md", "*.md", "ARCHITECTURE*", "CONTRIBUTING*"]),
    ("manifest", ["package.json", "pyproject.toml", "go.mod", "Cargo.toml", "pom.xml", "build.gradle*",
                  "Gemfile", "composer.json", "requirements*.txt", "docker-compose*.y*ml", "Dockerfile"]),
    ("schema", ["**/schema*.*", "**/models.py", "**/models/*.*", "**/*.prisma", "**/migrations/*.sql",
                "**/*.sql", "**/openapi*.y*ml", "**/openapi*.json", "**/*.graphql", "**/*.proto"]),
    ("routes", ["**/routes/**/*.*", "**/routes.*", "**/urls.py", "**/api/**/*.*", "**/controllers/**/*.*",
                "**/handlers/**/*.*", "**/app/**/route.*", "**/pages/api/**/*.*"]),
    ("entry", ["main.*", "app.*", "server.*", "index.*", "cli.*", "**/main.*", "**/app.*", "**/server.*",
               "**/cli.*", "src/**/__init__.py"]),
    ("code", ["src/**/*.*", "lib/**/*.*", "app/**/*.*", "**/*.*"]),
]

MAP_ROLES = [
    ("designer", "UX designer", "#e86a92", "Will people understand this and find their way without help?"),
    ("architect", "Architect", "#d9a400", "Do the parts fit together, and what breaks if one changes?"),
    ("analyst", "Business analyst", "#4f7fd8", "Is it clear what must be true, for whom, and how we will measure it?"),
    ("engineer", "Lead engineer", "#2e9e5b", "What is the smallest safe order to build this in, and how do we test it?"),
    ("owner", "Product manager", "#8a6fd1", "Is this the right thing to do next, and what would we cut?"),
    ("security", "Security and privacy", "#d0453b", "Who can see or change this, and what happens to the data?"),
    ("voice", "Customer voice", "#d68a00", "Would the people who use it notice, and would they care?"),
    ("agent", "AI agent teammate", "#0f8f8a", "Which steps could an agent do safely, and which need a person's OK?"),
]


def map_roles(ids: list[str] | None = None) -> list[dict]:
    """The roles `map` uses by default (or a chosen subset). Ids not in the list come from the
    general default roles, so `finance` still works."""
    base = {r[0]: {"id": r[0], "label": r[1], "color": r[2], "asks": r[3]} for r in MAP_ROLES}
    for r in default_roles():
        base.setdefault(r["id"], r)
    if not ids:
        return [base[r[0]] for r in MAP_ROLES]
    unknown = [i for i in ids if i not in base]
    if unknown:
        raise ValueError(f"Unknown role{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}. "
                         f"Choose from {', '.join(base)}.")
    return [base[i] for i in ids]


_PATH_PREFIXES = ("/", "./", "../", "~", ".\\", "..\\")


def looks_like_path(target: str) -> bool:
    """True when `target` reads as a file or folder rather than a topic in plain words."""
    t = (target or "").strip()
    if not t or "://" in t:
        return False
    if t.startswith(_PATH_PREFIXES) or t in (".", ".."):
        return True
    if " " in t:
        return False
    return "/" in t or "\\" in t or Path(t).suffix.lower() in TEXT_EXT | CODE_EXT | {".pdf", ".docx"}


def check_target(target: str) -> str:
    """Refuse a path that doesn't exist instead of quietly mapping it as a topic."""
    t = (target or "").strip()
    if looks_like_path(t) and not Path(t).expanduser().exists():
        raise ValueError(f"{t} looks like a path, but nothing is there (looked from {Path.cwd()}).")
    return t


def detect(target: str) -> str:
    """repo, folder, file, url or topic."""
    t = (target or "").strip()
    if re.match(r"https?://", t, re.I):
        return "url"
    p = Path(t).expanduser()
    if t and p.exists():
        if p.is_file():
            return "file"
        if (p / ".git").exists() or any(f.suffix in CODE_EXT for f in _walk(p, limit=400)):
            return "repo"
        return "folder"
    return "topic"


def _gitignore(root: Path) -> list[str]:
    f = root / ".gitignore"
    if not f.exists():
        return []
    return [line.strip().rstrip("/") for line in f.read_text(encoding="utf-8", errors="replace").splitlines()
            if line.strip() and not line.startswith("#") and not line.startswith("!")]


def _ignored(rel: str, patterns: list[str]) -> bool:
    parts = rel.split("/")
    for pat in patterns:
        pat = pat.lstrip("/")
        if fnmatch.fnmatch(rel, pat) or fnmatch.fnmatch(parts[-1], pat) or any(fnmatch.fnmatch(x, pat) for x in parts[:-1]):
            return True
    return False


def _git_files(root: Path) -> list[Path] | None:
    try:
        r = subprocess.run(["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard"],
                           capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return [root / line for line in r.stdout.splitlines() if line and (root / line).is_file()]


def _walk(root: Path, limit: int = 5000) -> list[Path]:
    pats = _gitignore(root)
    out = []
    for dirpath, dirs, files in os.walk(root):
        rel_dir = os.path.relpath(dirpath, root)
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")
                         and not _ignored(os.path.normpath(os.path.join(rel_dir, d)).replace(os.sep, "/"), pats))
        for f in sorted(files):
            rel = os.path.normpath(os.path.join(rel_dir, f)).replace(os.sep, "/")
            if not _ignored(rel, pats):
                out.append(Path(dirpath) / f)
            if len(out) >= limit:
                return out
    return out


def _numbered(text: str, max_chars: int) -> tuple[str, bool]:
    lines = text.splitlines()
    out, size, cut = [], 0, False
    for i, line in enumerate(lines, 1):
        row = f"{i:>4}| {line}"
        if size + len(row) > max_chars:
            cut = True
            break
        out.append(row)
        size += len(row) + 1
    return "\n".join(out), cut


def read_text(path: Path) -> str | None:
    """Plain text from a file: markdown, text, HTML (tags removed), PDF if pypdf is present."""
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        try:
            from pypdf import PdfReader  # optional
        except ImportError:
            return None
        try:
            return "\n".join((page.extract_text() or "") for page in PdfReader(str(path)).pages)
        except Exception:
            return None
    try:
        raw = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    if suffix in (".html", ".htm"):
        raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", " ", raw)
        raw = _html.unescape(re.sub(r"[ \t]+", " ", raw))
        raw = re.sub(r"\n\s*\n+", "\n\n", raw)
    return raw


def _rank(root: Path, files: list[Path]) -> list[tuple[str, Path]]:
    seen, ranked = set(), []
    rels = {f: f.relative_to(root).as_posix() for f in files}
    for label, globs in PRIORITY:
        for f in files:
            rel = rels[f]
            if f in seen:
                continue
            if f.suffix.lower() not in TEXT_EXT | CODE_EXT and f.name not in ("Dockerfile", "Gemfile"):
                continue
            if any(fnmatch.fnmatch(rel, g) for g in globs):
                seen.add(f)
                ranked.append((label, f))
    return ranked


def _checked(root: Path, kind: str) -> dict:
    if kind == "repo" and (root / ".git").exists():  # only the repository's own root, not a folder inside one
        try:
            r = subprocess.run(["git", "-C", str(root), "log", "-1", "--format=%h %cs"], capture_output=True,
                               text=True, timeout=10, check=False)
            if r.returncode == 0 and r.stdout.strip():
                sha, day = r.stdout.split()
                return {"date": day, "note": f"Checked against commit {sha} of {root.name}."}
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    try:
        newest = max((p.stat().st_mtime for p in ([root] if root.is_file() else _walk(root, 2000)) if p.is_file()), default=None)
    except OSError:
        newest = None
    day = datetime.fromtimestamp(newest).date().isoformat() if newest else _date.today().isoformat()
    return {"date": day, "note": f"Checked against the files as they were on {day}."}


def gather(target: str, *, budget: int = 120_000, per_file: int = 12_000, kind: str | None = None) -> dict:
    """Read the material for a target, deterministically. No network unless `fetch` is given.

    Returns {kind, target, material: [{name, text}], read: [{path, label, chars, cut}],
    skipped, digest, checked, needs}. `needs` says what the host must supply (a web page's
    text, or answers about a topic) when the tool cannot gather it itself.
    """
    kind = kind or detect(target)
    out = {"kind": kind, "target": target, "material": [], "read": [], "skipped": [], "digest": "",
           "checked": {"date": _date.today().isoformat(), "note": ""}, "needs": None}
    if kind == "topic":
        out["checked"]["note"] = "Not checked against any source: drawn from a description of the topic."
        out["needs"] = {"kind": "answers", "questions": TOPIC_QUESTIONS}
        return out
    if kind == "url":
        out["checked"]["note"] = f"Checked against {target} as fetched on {out['checked']['date']}."
        out["needs"] = {"kind": "page_text", "message": "Decisioncraft does not fetch web pages itself. "
                        "Fetch the page (and any pages it links to that matter), save the text as files, "
                        "and run map on that folder; or pass --allow-network to let it fetch this one page."}
        return out
    root = Path(target).expanduser()
    out["checked"] = _checked(root, kind)
    if kind == "file":
        files = [(("doc" if root.suffix.lower() in TEXT_EXT else "code"), root)]
        base = root.parent
    else:
        listed = _git_files(root) if kind == "repo" and (root / ".git").exists() else None
        files_all = [f for f in (listed if listed is not None else _walk(root)) if not any(
            part in SKIP_DIRS for part in f.relative_to(root).parts)]
        files = _rank(root, files_all) if kind == "repo" else \
            [("doc", f) for f in files_all if f.suffix.lower() in TEXT_EXT]
        base = root
        langs: dict[str, int] = {}
        for f in files_all:
            if f.suffix.lower() in CODE_EXT:
                langs[f.suffix.lower()] = langs.get(f.suffix.lower(), 0) + 1
        top = sorted({f.relative_to(root).parts[0] for f in files_all if len(f.relative_to(root).parts) > 1})
        out["digest"] = (f"{len(files_all)} files. Top-level folders: {', '.join(top[:20]) or 'none'}. "
                         + ("Code by kind: " + ", ".join(f"{k} {v}" for k, v in sorted(langs.items(), key=lambda x: -x[1])[:8]) + "."
                            if langs else ""))
    used = 0
    for label, f in files:
        rel = f.relative_to(base).as_posix() if f != base else f.name
        text = read_text(f)
        if text is None or not text.strip():
            out["skipped"].append({"path": rel, "why": "not readable as text" if text is None else "empty"})
            continue
        room = min(per_file, budget - used)
        if room < 400:
            out["skipped"].append({"path": rel, "why": "over the reading budget"})
            continue
        body, cut = _numbered(text, room)
        used += len(body)
        out["material"].append({"name": rel, "text": body})
        out["read"].append({"path": rel, "label": label, "chars": len(body), "cut": cut})
    if out["digest"]:
        out["material"].insert(0, {"name": "(overview of the folder)", "text": out["digest"]})
    return out


def fetch(url: str, *, max_chars: int = 200_000) -> str:
    """Fetch one web page and return its text. Only called with --allow-network."""
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "decisioncraft"})
    with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 -- explicit opt-in
        raw = r.read(max_chars * 2).decode("utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
    raw = _html.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    return re.sub(r"\s+\n", "\n", re.sub(r"[ \t]+", " ", raw))[:max_chars]


TOPIC_QUESTIONS = [
    {"id": "how_today", "ask": "Roughly how does it work today, step by step, and who is involved?",
     "why": "This becomes the as-is map."},
    {"id": "pain", "ask": "Where does it go wrong or feel slow?", "why": "Problems become gaps to close."},
    {"id": "goal", "ask": "What would better look like, and how would you know?",
     "why": "This shapes the to-be map and the 'done when' checks."},
]

BRIEF_INTENT = (
    "Map how this works today and how it could work better. Draw today's way first, with "
    "every box marked when: today and citing the material by path and line (for example "
    "'src/app.py:42') as evidence. Then propose the planned way: planned boxes marked when: "
    "planned, using replaces for each one that replaces a today box. Turn every difference "
    "into a gap with impact and effort, user stories and 'done when' checks. Add notes from "
    "each role, each ending in one question. Say 'not sure' where the material does not show "
    "something; never invent features, numbers or names."
)


def plan_map(target: str, *, roles: list[str] | None = None, budget: int = 120_000,
             answers: dict | None = None) -> dict:
    """What `map` would read and ask, with no model call."""
    g = gather(target, budget=budget)
    question = _question_for(target, g["kind"])
    calls = 0 if g["needs"] and not (answers and g["kind"] == "topic") else 2
    return {
        "format": "decisioncraft-map-plan/1",
        "kind": g["kind"], "target": target, "question": question,
        "read": g["read"], "skipped": g["skipped"], "digest": g["digest"],
        "chars": sum(r["chars"] for r in g["read"]), "checked": g["checked"],
        "roles": [r["label"] for r in map_roles(roles)],
        "needs": None if (answers and g["kind"] == "topic") else g["needs"],
        "model_calls": calls,
        "template": _template_for(g["kind"]),
    }


def _display_name(target: str, kind: str) -> str:
    """A repo or folder's own name: the README's first heading if it has one, else the folder name."""
    root = Path(target).expanduser().resolve()
    if kind in ("repo", "folder") and root.is_dir():
        for name in ("README.md", "readme.md", "README.markdown", "README.txt", "README"):
            f = root / name
            if f.is_file():
                try:
                    for line in f.read_text(encoding="utf-8", errors="replace").splitlines()[:40]:
                        m = re.match(r"#\s+(.{2,80})$", line.strip())
                        if m:
                            return m.group(1).strip().strip("#").strip()
                except OSError:
                    pass
                break
    return root.name


def _question_for(target: str, kind: str) -> str:
    if kind == "topic":
        t = re.sub(r"^(show me |tell me |explain |map )?(how )?", "", target.strip().rstrip("?."), flags=re.I)
        t = re.sub(r"\s+(works?|is done|happens)$", "", t, flags=re.I).strip() or "this"
        return f"How does {t[0].lower() + t[1:]} work today, and how could it work better?"
    name = _display_name(target, kind) if kind != "url" else target
    return f"How does {name} work today, and what is missing?"


def _template_for(kind: str) -> str:
    return "system-journeys" if kind == "repo" else "auto"


def map_starter(target: str, *, roles: list[str] | None = None, question: str = "", answers: dict | None = None,
                page_text: str = "", budget: int = 120_000) -> dict:
    """Deterministic. Everything `map` needs, for an agent that writes the map itself.

    Returns {model, digest, instructions, plan}: a starter model (the right template, the
    eight map roles, display notes_on_map and start_view planned, a checked stamp) with no
    boxes yet; the material digest with numbered lines to cite as evidence; and plain
    instructions for filling it in. No model call happens.
    """
    from .model import new_model

    g = gather(target, budget=budget)
    kind = g["kind"]
    material = list(g["material"])
    if kind == "url":
        if not page_text:
            raise ValueError(g["needs"]["message"])
        material = [{"name": target, "text": _numbered(page_text, budget)[0]}]
    if kind == "topic":
        lines = [f"Topic: {target}"]
        for tq in TOPIC_QUESTIONS:
            a = (answers or {}).get(tq["id"])
            lines.append(f"{tq['ask']}\nAnswer from the person: {a or '(not given: mark boxes not sure)'}")
        material = [{"name": "description from the person", "text": "\n\n".join(lines)}]
    q = question or _question_for(target, kind)
    template = _template_for(kind)
    template = "system-journeys" if template == "auto" and kind in ("repo", "folder") else (
        "decision-chain" if template == "auto" else template)
    name = _display_name(target, kind) if kind not in ("url", "topic") else target
    model = new_model(template, f"How {name} works, and what is missing", q, date=g["checked"]["date"])
    model["roles"] = map_roles(roles)
    model["checked"] = g["checked"]
    model["display"] = {"notes_on_map": True, "start_view": "planned"}
    model["map_source"] = {"kind": kind, "target": target if kind in ("url", "topic") else name,
                           "read": [r["path"] for r in g["read"]]}
    digest = "\n\n".join(f"## {m['name']}\n\n{m['text']}" for m in material)
    instructions = (
        "# Fill in this map\n\n"
        f"Question: {q}\n\n"
        "1. Read `decisioncraft guide` for every field and its rules.\n"
        "2. " + BRIEF_INTENT + "\n"
        "3. Cite evidence from material/digest.md by path and line (the numbers at the start of "
        "each line), for example 'src/app.py:42'. Add each cited file to `sources` and each quote to "
        "`evidence`.\n"
        "4. Add one note per role in `roles` (" + ", ".join(r["label"] for r in model["roles"]) + "), "
        "each pointing at a box and ending in one question.\n"
        "5. Run `decisioncraft validate model.json` until it reports no errors, then "
        "`decisioncraft render model.json --open`.\n"
    )
    return {"model": model, "digest": digest, "instructions": instructions,
            "plan": plan_map(target, roles=roles, budget=budget, answers=answers)}


def map_target(target: str, *, roles: list[str] | None = None, question: str = "", answers: dict | None = None,
               page_text: str = "", budget: int = 120_000, per_role: int = 2, provider: str | None = None,
               model: str | None = None, complete=None, allow_network: bool = False, progress=None,
               escalate=None) -> dict:
    """Model-backed. Gather material from a target and draft an as-is / to-be map with notes.

    Returns {model, plan, notes_added}. The model has display.notes_on_map set and a checked
    stamp from the repository commit or file dates. For a topic, pass `answers` to the
    TOPIC_QUESTIONS (or the model draws from general knowledge, clearly marked unverified).
    For a URL, pass `page_text`, or allow_network=True to fetch the one page.
    """
    from . import intelligence
    from .model import validate

    g = gather(target, budget=budget)
    kind = g["kind"]
    material = list(g["material"])
    if kind == "url":
        text = page_text or (fetch(target) if allow_network else "")
        if not text:
            raise ValueError(g["needs"]["message"])
        material = [{"name": target, "text": _numbered(text, budget)[0]}]
    if kind == "topic":
        lines = [f"Topic: {target}"]
        for q in TOPIC_QUESTIONS:
            a = (answers or {}).get(q["id"])
            if a:
                lines.append(f"{q['ask']}\nAnswer from the person: {a}")
        if len(lines) == 1:
            lines.append("No answers were given. Draw from general knowledge, mark every box status "
                         "'not sure', and say in the summary that nothing here has been checked.")
        material = [{"name": "description from the person", "text": "\n\n".join(lines)}]
    q = question or _question_for(target, kind)
    chosen = map_roles(roles)
    brief = {"format": "decisioncraft-brief/1",
             "answers": {"decision": q, "why": BRIEF_INTENT, "visual": "How the work changes, today and planned"}}
    say = progress or (lambda _t: None)
    if complete is None:
        complete, auto = intelligence._resolve_complete(provider, model, None)
        escalate = escalate or auto
    say(f"Read {len(g['read'])} file(s), {sum(len(m['text']) for m in material):,} characters.")
    say("Step 1 of 2: drawing today's way, the planned way, and the gaps with user stories ...")
    drafted = intelligence.draft(material, template=_template_for(kind), question=q, roles=chosen,
                                 brief=brief, complete=complete, escalate=escalate, progress=say,
                                 date=g["checked"]["date"], max_material_chars=budget + 4000,
                                 defer_notes=True)
    say(f"Step 1 done: {len(drafted.get('maps', []))} map(s), {len(drafted.get('gaps', []))} gap(s).")
    before = len(drafted.get("notes", []))
    say(f"Step 2 of 2: a note from each of {len(chosen)} roles, a few at a time ...")
    drafted = intelligence.perspectives(drafted, material=material, roles=chosen, per_role=per_role,
                                        complete=complete, escalate=escalate, progress=say)
    drafted["checked"] = g["checked"]
    drafted.setdefault("display", {})
    drafted["display"]["notes_on_map"] = True
    drafted["display"].setdefault("start_view", "planned")
    drafted["map_source"] = {"kind": kind, "target": target if kind in ("url", "topic") else Path(target).name,
                             "read": [r["path"] for r in g["read"]]}
    problems = [p for p in validate(drafted) if p["level"] == "error"]
    if problems:
        from .model import ModelError

        raise ModelError(problems)
    plan = plan_map(target, roles=roles, budget=budget, answers=answers)
    return {"model": drafted, "plan": plan, "notes_added": len(drafted.get("notes", [])) - before}
