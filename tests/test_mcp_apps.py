"""MCP Apps: the canvas as a view in hosts that support it (resources, tool _meta, results)."""

from __future__ import annotations

import asyncio
import json

import pytest

pytest.importorskip("mcp")

from decisioncraft import lib  # noqa: E402
from decisioncraft.mcp_server import build_server  # noqa: E402
from decisioncraft.modes import quick_model  # noqa: E402
from decisioncraft.render import APP_MIME, APP_URI, app_html  # noqa: E402

VISUAL = {"decisioncraft_render", "decisioncraft_map", "decisioncraft_example", "decisioncraft_quick"}


def run(coro):
    return asyncio.run(coro)


@pytest.fixture(scope="module")
def server():
    return build_server()[0]


def test_instructions_say_when_to_use_and_when_not(server):
    text = server._mcp_server.instructions
    for phrase in ("renew or buy", "keep or replace", "job offer", "as-is and to-be", "where are the gaps"):
        assert phrase in text
    assert "Not for factual questions" in text and "code-level choices" in text
    assert text.index("Use Decisioncraft when") == 0


def test_visual_tools_declare_the_view_and_save_is_app_only(server):
    tools = {t.name: t for t in run(server.list_tools())}
    for name in VISUAL:
        assert (tools[name].meta or {}).get("ui", {}).get("resourceUri") == APP_URI, name
    save = tools["decisioncraft_save_review"].meta["ui"]
    assert save["visibility"] == ["app"]
    for name in ("decisioncraft_triage", "decisioncraft_quick", "decisioncraft_map"):
        assert any(p in tools[name].description for p in ("should I", "which is better", "map this codebase"))


def test_view_resource_is_a_self_contained_mcp_app(server):
    contents = list(run(server.read_resource(APP_URI)))
    assert contents[0].mime_type == APP_MIME == "text/html;profile=mcp-app"
    assert contents[0].meta == {"ui": {"csp": {}, "prefersBorder": False}}
    html = contents[0].content
    assert "window.DC_DEFER = true" in html and "ui/initialize" in html and "2026-01-26" in html
    assert html.index("window.DC_DEFER") < html.index("window.__dcBoot = function")
    for outside in ("https://", "http://", "unpkg", "cdn."):
        assert outside not in html.split("<script>", 1)[1].replace("http://www.w3.org", ""), outside
    assert app_html() == html


def test_render_returns_short_text_and_the_model_for_the_view(server, tmp_path):
    model = lib.example("car")["model"]
    out = run(server.call_tool("decisioncraft_render", {"model": model, "directory": str(tmp_path)}))
    text = out.content[0].text
    assert text.startswith("Drew ") and str(tmp_path) in text and len(text) < 600
    assert out.structuredContent["model"]["title"] == model["title"]
    assert (tmp_path / "canvas.html").is_file()


def test_quick_carries_a_scoring_model(server):
    result = run(server.call_tool("decisioncraft_quick", {
        "options": ["Keep", "Buy used"], "criteria": ["must:Five seats", "Cost", "Safety"],
        "scores": [{"option": "Keep", "criterion": "Cost", "score": 4},
                   {"option": "Buy used", "criterion": "Safety", "score": 4},
                   {"option": "Keep", "criterion": "Five seats", "score": 5}]}))
    data = result[1] if isinstance(result, tuple) else result.structuredContent
    m = data["model"]
    assert [x["template"] for x in m["maps"]] == ["scoring-table"]
    assert {c["kind"] for c in m["criteria"]} == {"must", "scored"}
    assert [p for p in lib.validate(m) if p["level"] == "error"] == []


def test_quick_model_maps_must_haves_and_weights():
    r = lib.quick(["A", "B"], ["must:Fits", "Price"],
                  [{"option": "A", "criterion": "Fits", "score": 2}, {"option": "B", "criterion": "Price", "score": 4.6}])
    m = quick_model(r)
    must = [s for s in m["scores"] if s["criterion"] == "fits"][0]
    assert must["meets"] is False
    assert [s for s in m["scores"] if s["criterion"] == "price"][0]["value"] == 5


def test_save_review_writes_the_answers(server, tmp_path):
    model = lib.example("business")["model"]
    review = lib.example("business")["reviews"][0]
    out = run(server.call_tool("decisioncraft_save_review", {"review": review, "directory": str(tmp_path)}))
    data = out[1] if isinstance(out, tuple) else out.structuredContent
    saved = json.loads(open(data["path"], encoding="utf-8").read())
    assert saved == review and data["path"].startswith(str(tmp_path))
    assert model["title"]


def test_canvas_engine_defers_only_when_asked():
    from importlib.resources import files

    js = files("decisioncraft").joinpath("resources/canvas.js").read_text(encoding="utf-8")
    assert js.rstrip().endswith("if (!window.DC_DEFER) window.__dcBoot();")
    assert "HOST.saveReview" in js and "HOST.askExperts" in js


def test_what_would_change_the_winner_lists_each_change_once():
    from decisioncraft.choice import scoring

    r = lib.quick(["Keep and repair", "Buy used", "Lease new"], ["must:Five seats", "Monthly cost", "Safety", "Reliability"],
                  [{"option": o, "criterion": "Five seats", "score": 5} for o in ("Keep and repair", "Buy used", "Lease new")] +
                  [{"option": "Keep and repair", "criterion": "Monthly cost", "score": 5},
                   {"option": "Buy used", "criterion": "Monthly cost", "score": 3},
                   {"option": "Lease new", "criterion": "Monthly cost", "score": 2},
                   {"option": "Keep and repair", "criterion": "Safety", "score": 2},
                   {"option": "Buy used", "criterion": "Safety", "score": 4},
                   {"option": "Lease new", "criterion": "Safety", "score": 5},
                   {"option": "Keep and repair", "criterion": "Reliability", "score": 2},
                   {"option": "Buy used", "criterion": "Reliability", "score": 4},
                   {"option": "Lease new", "criterion": "Reliability", "score": 5}])
    flips = scoring(quick_model(r))["flips"]
    keys = [(f["kind"], f["criterion"], f["to"], f.get("of"), f["new_leader"]) for f in flips]
    assert len(keys) == len(set(keys))
