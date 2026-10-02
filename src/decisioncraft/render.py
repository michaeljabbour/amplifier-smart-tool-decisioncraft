"""Turn a model into one self-contained HTML canvas. Deterministic, no network."""

from __future__ import annotations

import html
import json
import re
from importlib.resources import files

from .model import require_valid
from .review import diff as diff_models
from .review import fingerprint, merge


def _embed(value) -> str:
    """JSON safe to place inside a <script type="application/json"> element."""
    if value is None:
        return ""
    raw = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return raw.replace("</", "<\\/").replace("<!--", "<\\!--")


def render(model: dict, *, reviews: list[dict] | None = None, merged: dict | None = None,
           since: dict | None = None) -> str:
    """Render a model as a single HTML file that works offline.

    reviews: saved review files to show as agree/disagree tallies (merged here).
    merged: an already merged review set (from `merge`), used instead of `reviews`.
    since: an earlier version of the same model; boxes added or changed since then
    are marked "New" or "Changed".
    """
    require_valid(model)
    if reviews and merged is None:
        merged = merge(reviews, model)
    changes = diff_models(since, model) if since else None
    res = files("decisioncraft").joinpath("resources")
    page = res.joinpath("canvas.html").read_text(encoding="utf-8")
    meta = {"fingerprint": fingerprint(model), "generator": "decisioncraft"}
    slots = {
        "TITLE": html.escape(model.get("title", "Decision map")),
        "MODEL": _embed(model), "MERGED": _embed(merged), "SINCE": _embed(changes),
        "META": _embed(meta),
        "CSS": res.joinpath("canvas.css").read_text(encoding="utf-8"),
        "JS": res.joinpath("canvas.js").read_text(encoding="utf-8"),
    }
    # one pass over the template only, so text inside the model is never rescanned
    return re.sub(r"__(TITLE|MODEL|MERGED|SINCE|META|CSS|JS)__", lambda m: slots[m.group(1)], page)
