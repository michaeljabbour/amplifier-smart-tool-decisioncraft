#!/usr/bin/env python3
"""Fail if the repository holds anything it must not.

Checks every tracked and untracked (non-ignored) file, file paths, and the git history
(author and committer names and emails, commit messages) for:
  - home directories and personal checkout paths
  - real email addresses (example.com / noreply addresses are fine)
  - names and terms listed in the untracked file .check-generic.local (one per line)
  - built-in product names this tool must never mention
  - filler words the project's writing rules ban

A line ending `check-generic:allow` is exempt; use it narrowly. Patterns are assembled
from fragments so this file does not match itself.

    python3 scripts/check-generic.py [repo-root]
Exit 0 when clean, 1 when anything is found.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

J = "".join
LOCAL_TERMS = ".check-generic.local"
ALLOW_LINE = re.compile(r"check-generic:allow\s*(-->)?\s*$")

PATHS = [
    re.compile(J(["/", "Users", "/"])),
    re.compile(J(["/", "home", "/"]) + r"[a-z]"),
    re.compile(J(["~", "/dev", "/"])),
    re.compile(r"[A-Za-z]:\\" + J(["Us", "ers"])),
]
PRODUCT_TERMS = [
    J(["Give ", "Us a ", "Project"]), J(["Team", "Thynk"]), J(["give", "usa", "project"]),
    J(["Harbor ", "& ", "Pine"]), J(["Harbor ", "and ", "Pine"]),
]
# One capitalised product name; the ordinary lower-case verb is fine.
CASED_TERMS = [J(["En", "gage"])]
FILLER = [
    "leverage", "seamless", "robust", "unlock", "empower", "synergy", J(["cutting", "-edge"]),
    J(["game", "-changer"]), J(["game ", "changer"]), "delve",
]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(r"@(example\.(com|org|net))$|^noreply@", re.IGNORECASE)
# The checker's own word lists and the validator's filler list are allowed to name filler.
FILLER_EXEMPT = {"scripts/check-generic.py", "src/decisioncraft/model.py",
                 "src/decisioncraft/resources/writing-guide.md", "AGENTS.md", "tests/test_model.py"}


def local_terms(root: Path) -> list[re.Pattern]:
    f = root / LOCAL_TERMS
    if not f.is_file():
        return []
    terms = [t.strip() for t in f.read_text().splitlines() if t.strip() and not t.lstrip().startswith("#")]
    return [re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in terms]


# The vendored family theme names the family's owner and organisation; that is expected.
# Paths, emails and product names are still checked there.
VENDORED = ("site/theme/",)


def patterns(rel: str, terms):
    vendored = rel.startswith(VENDORED)
    pats = list(PATHS) + ([] if vendored else list(terms))
    pats += [re.compile(re.escape(t), re.IGNORECASE) for t in PRODUCT_TERMS]
    pats += [re.compile(r"\b" + re.escape(t) + r"\b") for t in CASED_TERMS]
    if rel not in FILLER_EXEMPT and not vendored:
        pats += [re.compile(r"\b" + re.escape(t) + r"\b", re.IGNORECASE) for t in FILLER]
    return pats


def files(root: Path) -> list[Path]:
    out = subprocess.run(["git", "ls-files", "-co", "--exclude-standard"], cwd=root,
                         capture_output=True, text=True, check=True).stdout
    return [root / f for f in out.splitlines() if f and (root / f).is_file()]


def scan(text: str, where: str, pats) -> list[str]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if ALLOW_LINE.search(line):
            continue
        for pat in pats:
            m = pat.search(line)
            if m:
                hits.append(f"{where}:{n}: '{m.group(0)}'")
        for m in EMAIL.finditer(line):
            if not ALLOWED_EMAIL.search(m.group(0)):
                hits.append(f"{where}:{n}: email '{m.group(0)}'")
    return hits


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent).resolve()
    terms = local_terms(root)
    hits: list[str] = []
    n = 0
    for f in files(root):
        rel = f.relative_to(root).as_posix()
        if rel == LOCAL_TERMS:
            continue
        pats = patterns(rel, terms)
        hits += scan(rel, f"path {rel}", pats)
        data = f.read_bytes()
        if b"\0" in data[:4096]:
            continue
        hits += scan(data.decode("utf-8", "replace"), rel, pats)
        n += 1
    log = subprocess.run(["git", "log", "--all", "--format=%an <%ae>%n%cn <%ce>%n%B"], cwd=root,
                         capture_output=True, text=True).stdout
    hits += scan(log, "git history", patterns("git history", terms))
    for h in hits:
        print(h)
    print(f"check-generic: {n} files and the git history checked, {len(hits)} problem(s).",
          file=sys.stderr)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
