#!/usr/bin/env python3
"""Build Decisioncraft's complete static page, examples and offline skill ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*arguments: str) -> None:
    subprocess.run([sys.executable, *arguments], cwd=ROOT, check=True)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def example_outputs() -> dict[str, Path]:
    """Publish each actual self-contained canvas under its stable page name."""
    outputs = {}
    for source in sorted((ROOT / "examples").glob("*/canvas*.html")):
        suffix = source.stem.removeprefix("canvas")
        outputs[f"examples/{source.parent.name}{suffix}.html"] = source
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "_site")
    parser.add_argument("--local", action="store_true")
    parser.add_argument("--family-owner")
    args = parser.parse_args()
    output = args.output.resolve()
    if output == ROOT or ROOT.is_relative_to(output) or any(
        output == ROOT / name or (ROOT / name) in output.parents
        for name in ("site", "src", "examples", "skills", "scripts", ".git")
    ):
        parser.error("Output must be a separate generated-site directory")

    run("scripts/build-examples.py")
    theme_args = ["site/theme/build.py", "--output", str(output)]
    if args.local:
        theme_args.append("--local")
    if args.family_owner:
        theme_args += ["--family-owner", args.family_owner]
    run(*theme_args)

    examples = example_outputs()
    for destination, source in examples.items():
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    shutil.copy2(ROOT / "site/theme/LICENSE", output / "assets/THEME-LICENSE.txt")
    archive = output / "downloads/decisioncraft-skill.zip"
    # The native builder runs all 17 isolated offline checks, including wheel parity.
    run("scripts/build-skill-zip.py", "--out", str(archive))
    with zipfile.ZipFile(archive) as packed:
        archive_files = sorted(packed.namelist())
    config = json.loads((ROOT / "site/site.json").read_text())
    media = [config[key] for key in ("image", "video") if config.get(key)]
    media += [demo[key] for demo in config.get("capability_demos", [])
              for key in ("image", "video") if demo.get(key)]
    receipt = {
        "schema": "decisioncraft-site-release/v1",
        "examples": [{"source": str(source.relative_to(ROOT)), "destination": destination,
                      "sha256": digest(source)} for destination, source in examples.items()],
        "media": [{"source": source, "destination": "assets/" + Path(source).name,
                   "sha256": digest(ROOT / source)} for source in sorted(set(media))],
        "archive": {"destination": "downloads/decisioncraft-skill.zip",
                    "files": archive_files, "file_count": len(archive_files),
                    "sha256": digest(archive)},
        "theme_license_sha256": digest(ROOT / "site/theme/LICENSE"),
    }
    (output / "site-release.json").write_text(json.dumps(receipt, indent=2) + "\n")
    run("scripts/check-site.py", "--output", str(output))
    print(f"Complete static build: {len(examples)} example canvases; {len(archive_files)} archive files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

