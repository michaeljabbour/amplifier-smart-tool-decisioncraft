"""The four worked examples, as data. Deterministic; reads only files shipped with the tool.

Installed packages carry the examples under `decisioncraft/examples/`. A checkout run
through `bin/decisioncraft.py` reads the repository's `examples/` folder instead, so the
two never drift.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

EXAMPLES = {
    "business": "A bakery chain deciding whether to add a subscription box.",
    "technical": "A web team deciding how to move file uploads to a new storage provider.",
    "engineering": "A town deciding whether to repair or replace a footbridge.",
    "medical": "A hospital ward changing its discharge process to cut readmissions "
    "(about how the ward works; not medical advice, no patient data).",
    "car": "A family choosing whether to keep, lease, buy new, buy used or go car-free "
    "(scoring table, cost over time, what-ifs).",
    "map": "A bike hire shop's small code repository, mapped as it works today and as it could "
    "work (made with decisioncraft map; a made-up repo).",
}
# An example's folder, where it differs from its name.
FOLDERS = {"car": "personal-car", "map": "bike-hire-map"}


def _root(name: str):
    name = FOLDERS.get(name, name)
    packaged = files("decisioncraft").joinpath("examples", name)
    if packaged.joinpath("model.json").is_file():
        return packaged
    checkout = Path(__file__).resolve().parents[2] / "examples" / name
    if (checkout / "model.json").is_file():
        return checkout
    return None


def example_names() -> list[dict]:
    """The worked examples: id and one line on what each decides."""
    return [{"id": k, "about": v} for k, v in EXAMPLES.items()]


def example(name: str) -> dict:
    """One worked example: its model, the material it cites, and any saved reviews.

    Returns {"id", "about", "model", "material": [{name, text}], "reviews": [review],
    "earlier_model": model or None}. Raises ValueError for an unknown name.
    """
    if name not in EXAMPLES:
        raise ValueError(f"Unknown example: {name}. Choose one of {', '.join(EXAMPLES)}.")
    root = _root(name)
    if root is None:
        raise FileNotFoundError(f"The {name} example is missing from this installation.")
    model = json.loads(root.joinpath("model.json").read_text(encoding="utf-8"))
    material = []
    mat = root.joinpath("material")
    if mat.is_dir():
        for f in sorted(mat.iterdir(), key=lambda p: p.name):
            if f.is_file() and f.name.endswith((".md", ".txt")):
                material.append({"name": f.name, "text": f.read_text(encoding="utf-8")})
    reviews = []
    rev = root.joinpath("reviews")
    if rev.is_dir():
        for f in sorted(rev.iterdir(), key=lambda p: p.name):
            if f.is_file() and f.name.endswith(".json"):
                reviews.append(json.loads(f.read_text(encoding="utf-8")))
    earlier = root.joinpath("model-before.json")
    return {
        "id": name,
        "about": EXAMPLES[name],
        "model": model,
        "material": material,
        "reviews": reviews,
        "earlier_model": json.loads(earlier.read_text(encoding="utf-8")) if earlier.is_file() else None,
    }
