#!/usr/bin/env python3
"""Check the shipped local links, source fidelity and complete offline archive."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import zipfile
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, text: str) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: set[str] = set()
        self.references: list[str] = []
        self.feed(text)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        for key in ("href", "src", "poster", "data-motion-src", "data-still-src"):
            if values.get(key):
                self.references.append(str(values[key]))


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def archive_errors(path: Path) -> list[str]:
    """Compare every expected file's bytes, not a hard-coded payload count."""
    spec = importlib.util.spec_from_file_location("decisioncraft_skill_builder", ROOT / "scripts/build-skill-zip.py")
    assert spec and spec.loader
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    expected = {
        "decisioncraft/SKILL.md": (builder.frontmatter() + builder.BODY.lstrip("\n")).encode(),
        "decisioncraft/scripts/dc.py": builder.RUNNER.encode(),
        "decisioncraft/LICENSE.md": (ROOT / "LICENSE").read_bytes(),
    }
    for source in sorted(builder.SRC.rglob("*")):
        relative = source.relative_to(builder.SRC)
        if source.is_file() and not any(p in builder.SKIP for p in relative.parts) and not source.name.endswith(".pyc"):
            expected["decisioncraft/scripts/decisioncraft/" + relative.as_posix()] = source.read_bytes()
    for source_name, destination in builder.wheel_extras().items():
        source = ROOT / source_name
        entries = source.rglob("*") if source.is_dir() else [source]
        for entry in entries:
            if entry.is_file():
                relative = entry.relative_to(source) if source.is_dir() else Path()
                if any(p in builder.SKIP for p in relative.parts) or entry.name.endswith(".pyc"):
                    continue
                target = PurePosixPath("decisioncraft/scripts/decisioncraft") / destination
                if source.is_dir():
                    target /= relative.as_posix()
                expected[str(target)] = entry.read_bytes()
    expected.update({"decisioncraft/references/" + name: text.encode()
                     for name, text in builder.references().items()})
    errors = []
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            if len(names) != len(set(names)):
                errors.append("Archive has duplicate paths")
            unsafe = [name for name in names if PurePosixPath(name).is_absolute()
                      or ".." in PurePosixPath(name).parts or not name.startswith("decisioncraft/")]
            if unsafe:
                errors.append("Archive paths escape the single skill folder")
            actual = set(names)
            if actual != set(expected):
                errors.append(f"Archive file set differs: missing={sorted(set(expected)-actual)}, extra={sorted(actual-set(expected))}")
            for name in set(expected) & actual:
                if archive.read(name) != expected[name]:
                    errors.append("Archive bytes differ from source: " + name)
            if archive.testzip() is not None:
                errors.append("Archive CRC failure")
    except (OSError, zipfile.BadZipFile) as exc:
        errors.append("Unreadable archive: " + str(exc))
    return errors


def check(output: Path) -> dict[str, int]:
    output = output.resolve()
    errors = []
    pages = {path: Page(path.read_text()) for path in output.rglob("*.html")}
    family = json.loads((ROOT / "site/theme/family.json").read_text())
    sibling_roots = tuple("/" + page["repository"] + "/" for page in family["pages"].values()
                          if page["repository"] != "amplifier-smart-tool-decisioncraft")
    references = 0
    for path, page in pages.items():
        for reference in page.references:
            parsed = urlsplit(reference)
            if parsed.scheme or parsed.netloc:
                continue
            if parsed.path.startswith(sibling_roots):
                continue  # --local links to separately hosted sibling sites.
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path
            if not target.is_relative_to(output):
                errors.append(f"Local link escapes output: {path.name}: {reference}")
                continue
            if target.is_dir():
                target /= "index.html"
            if not target.is_file():
                errors.append(f"Missing local link: {path.relative_to(output)}: {reference}")
            elif parsed.fragment and target in pages and unquote(parsed.fragment) not in pages[target].ids:
                errors.append(f"Missing fragment: {path.relative_to(output)}: {reference}")
            references += 1
    config = json.loads((ROOT / "site/site.json").read_text())
    receipt_path = output / "site-release.json"
    if not receipt_path.is_file():
        errors.append("Missing complete-build receipt; use scripts/build-site.py")
        receipt = {}
    else:
        receipt = json.loads(receipt_path.read_text())
    examples = receipt.get("examples", [])
    published = {record["destination"] for record in examples}
    for demo in config.get("capability_demos", []):
        reference = demo.get("link", "")
        if reference and not urlsplit(reference).scheme and reference not in published:
            errors.append("Configured example is not shipped: " + reference)
    for record in [*examples, *receipt.get("media", [])]:
        source, target = ROOT / record["source"], output / record["destination"]
        if not target.is_file() or digest(target) != record["sha256"] or digest(source) != record["sha256"]:
            errors.append("Source/build bytes differ: " + record["destination"])
    archive = output / "downloads/decisioncraft-skill.zip"
    errors.extend(archive_errors(archive))
    packed = receipt.get("archive", {})
    if archive.is_file() and digest(archive) != packed.get("sha256"):
        errors.append("Archive differs from build receipt")
    if not (output / "assets/THEME-LICENSE.txt").is_file() or (output / "assets/THEME-LICENSE.txt").read_bytes() != (ROOT / "site/theme/LICENSE").read_bytes():
        errors.append("Theme MIT notice missing or changed")
    index = (output / "index.html").read_text() if (output / "index.html").is_file() else ""
    if "Microsoft Office of the CTO" in index or "<strong>MADE</strong>" in index:
        errors.append("Product page retains institutional attribution")
    if "downloads/decisioncraft-skill.zip" not in index:
        errors.append("Product page does not link the local skill archive")
    if errors:
        raise ValueError("\n".join(errors))
    return {"html_pages": len(pages), "local_references": references, "examples": len(examples),
            "media_files": len(receipt.get("media", [])), "archive_files": packed.get("file_count", 0)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    args = parser.parse_args()
    try:
        result = check(args.output)
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

