#!/usr/bin/env python3
"""Rebuild every example's outputs from its committed model, with no model calls.

    python3 scripts/build-examples.py
For each examples/<name>/model.json: canvas.html and in-words.md. Extras where present:
reviews/*.json -> merged.json and canvas-reviewed.html; model-before.json -> canvas-since.html.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import decisioncraft as dc  # noqa: E402


def write(path: Path, text: str):
    path.write_text(text if text.endswith("\n") else text + "\n", encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")


for ex in sorted((ROOT / "examples").iterdir()):
    mp = ex / "model.json"
    if not mp.is_file():
        continue
    model = json.loads(mp.read_text(encoding="utf-8"))
    write(ex / "canvas.html", dc.render(model))
    write(ex / "in-words.md", dc.words(model))
    reviews = sorted((ex / "reviews").glob("*.json")) if (ex / "reviews").is_dir() else []
    if reviews:
        merged = dc.merge([json.loads(r.read_text(encoding="utf-8")) for r in reviews], model)
        write(ex / "merged.json", json.dumps(merged, indent=2, ensure_ascii=False))
        write(ex / "canvas-reviewed.html", dc.render(model, merged=merged))
    before = ex / "model-before.json"
    if before.is_file():
        write(ex / "canvas-since.html", dc.render(model, since=json.loads(before.read_text(encoding="utf-8"))))
