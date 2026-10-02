"""Check this computer's setup and say exactly what to fix. Deterministic; never calls a model.

Each check is {"id", "status": "ok" | "warn" | "fail", "detail", "fix"}. "fail" means
something every user needs is broken; "warn" means an optional path is not ready.
"""

from __future__ import annotations

import importlib.util
import os
import shlex
import shutil
import sys
import tempfile
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

MIN_PYTHON = (3, 11)
EXTRAS = "amplifier-smart-tool-decisioncraft"


def _pkg(name: str) -> str | None:
    if importlib.util.find_spec(name) is None:
        return None
    try:
        return version(name)
    except PackageNotFoundError:
        return "installed"


def _writable(folder: Path) -> bool:
    try:
        with tempfile.NamedTemporaryFile(dir=folder, prefix=".decisioncraft-check-", delete=True):
            return True
    except OSError:
        return False


def doctor(*, directory: str = ".", complete_cmd: str | None = None) -> dict:
    """Check Python, optional packages, provider keys, host-model routing and write access.

    directory: where you plan to write canvases and models (default: the current folder).
    complete_cmd: a --complete-cmd you plan to use; its program is looked up, not run.
    Returns {"checks": [...], "ready": {path: bool}, "summary": str}.
    """
    checks: list[dict] = []

    def add(id_, status, detail, fix=""):
        checks.append({"id": id_, "status": status, "detail": detail, "fix": fix})

    py = sys.version_info
    py_text = f"Python {py.major}.{py.minor}.{py.micro}"
    if (py.major, py.minor) >= MIN_PYTHON:
        add("python", "ok", py_text)
    else:
        add("python", "fail", f"{py_text} is too old.", "Install Python 3.11 or newer.")

    folder = Path(directory).expanduser()
    if not folder.exists():
        add("write_access", "fail", f"{folder} does not exist.", f"Create it: mkdir -p {shlex.quote(str(folder))}")
    elif _writable(folder):
        add("write_access", "ok", f"Can write to {folder.resolve()}")
    else:
        add("write_access", "fail", f"Can't write to {folder.resolve()}.", "Use --out or --dir with a folder you own.")
    tmp = Path(tempfile.gettempdir())
    if _writable(tmp):
        add("temp_folder", "ok", f"Temporary folder {tmp} is writable")
    else:
        add("temp_folder", "fail", f"Can't write to the temporary folder {tmp}.", "Set TMPDIR to a folder you can write to.")

    sdks = {}
    for pkg, env in (("anthropic", "ANTHROPIC_API_KEY"), ("openai", "OPENAI_API_KEY")):
        have_pkg = _pkg(pkg)
        have_key = bool(os.environ.get(env))
        ready = bool(have_pkg and have_key)
        sdks[pkg] = ready
        if ready:
            add(f"provider_{pkg}", "ok", f"{pkg} {have_pkg} installed and {env} is set")
        else:
            missing = []
            fixes = []
            if not have_pkg:
                missing.append(f"the {pkg} package")
                fixes.append(f"uv tool install --force '{EXTRAS}[smart]' (or pip install '{EXTRAS}[smart]')")
            if not have_key:
                missing.append(env)
                fixes.append(f"export {env}=...")
            add(
                f"provider_{pkg}", "warn",
                f"--provider {pkg} is not ready: missing {' and '.join(missing)}. Only draft and perspectives need it.",
                "; ".join(fixes),
            )

    routing_ready = False
    if complete_cmd:
        try:
            program = shlex.split(complete_cmd)[0]
        except (ValueError, IndexError):
            program = ""
        found = shutil.which(program) if program else None
        if found:
            routing_ready = True
            add("complete_cmd", "ok", f"--complete-cmd program found: {found} (not run; it would cost tokens)")
        else:
            add(
                "complete_cmd", "fail",
                f"--complete-cmd program {program or '(empty)'} was not found on PATH.",
                "Use the full path to the program, or check the command spelling.",
            )
    else:
        add(
            "complete_cmd", "warn",
            "No --complete-cmd given. A host can route draft and perspectives through its own model "
            "with --complete-cmd; the command reads {\"system\", \"prompt\"} JSON on stdin and prints the reply.",
            "Check one with: decisioncraft doctor --complete-cmd 'your-command'",
        )

    mcp = _pkg("mcp")
    if mcp:
        add("mcp", "ok", f"mcp {mcp} installed: decisioncraft mcp can serve MCP hosts")
    else:
        add("mcp", "warn", "The mcp package is not installed, so decisioncraft mcp will not start.",
            f"uv tool install --force '{EXTRAS}[mcp]' (only needed for MCP hosts)")

    failed = any(c["status"] == "fail" for c in checks)
    ready = {
        "deterministic": not any(c["status"] == "fail" for c in checks if c["id"] in ("python", "write_access", "temp_folder")),
        "draft_with_anthropic": sdks["anthropic"],
        "draft_with_openai": sdks["openai"],
        "draft_with_complete_cmd": routing_ready,
        "mcp": bool(mcp),
    }
    if failed:
        text = "Some things need fixing before you start (marked fix)."
    elif not (ready["draft_with_anthropic"] or ready["draft_with_openai"] or routing_ready):
        text = "Ready to draw, review and compare. To draft with a model, set up a provider or --complete-cmd."
    else:
        text = "Ready, including drafting with a model."
    return {"checks": checks, "ready": ready, "summary": text}
