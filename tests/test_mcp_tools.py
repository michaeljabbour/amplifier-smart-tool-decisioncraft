"""The MCP server's deterministic tools, and draft through the host's own model (sampling)."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

import decisioncraft as dc

# No API keys: a host without sampling must not fall back to a paid provider in tests.
ENV = dict({k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "DECISIONCRAFT_MODEL")}, PYTHONPATH=str(Path(__file__).resolve().parent.parent / "src"))
PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "decisioncraft", "mcp"], env=ENV)

TINY = {
    "format": "decisioncraft/1", "title": "T", "question": "Q?", "summary": "",
    "checked": {"date": "", "note": ""}, "roles": [], "glossary": {}, "sources": [],
    "evidence": [], "gaps": [], "notes": [], "decisions": [], "outcomes": [],
    "maps": [{"id": "m1", "template": "opportunity-tree", "title": "x", "intro": "x",
              "levels": ["Outcome", "Need or pain", "Idea", "Quick test"],
              "root": {"id": "root", "title": "x", "text": "", "children": []}}],
}


async def _with_client(fn, sampling_callback=None):
    async with stdio_client(PARAMS) as (reader, writer):
        async with ClientSession(reader, writer, sampling_callback=sampling_callback) as client:
            await client.initialize()
            return await fn(client)


def test_deterministic_tools(tmp_path):
    model = dc.example("business")["model"]
    reviews = dc.example("business")["reviews"]

    async def check(client):
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"decisioncraft_render", "decisioncraft_words", "decisioncraft_questions",
                "decisioncraft_merge", "decisioncraft_diff", "decisioncraft_example",
                "decisioncraft_draft", "decisioncraft_perspectives"} <= names
        r = await client.call_tool("decisioncraft_render", {"model": model, "directory": str(tmp_path)})
        assert not r.isError and Path(r.structuredContent["path"]).is_file()
        w = await client.call_tool("decisioncraft_words", {"model": model})
        assert w.structuredContent["markdown"].startswith("#")
        q = await client.call_tool("decisioncraft_questions", {"model": model, "reviews": reviews})
        assert len(q.structuredContent["questions"]) > 0
        m = await client.call_tool("decisioncraft_merge", {"model": model, "reviews": reviews})
        assert not m.isError
        d = await client.call_tool("decisioncraft_diff", {"old": model, "new": model})
        assert not d.isError
        e = await client.call_tool("decisioncraft_example", {"name": "medical"})
        assert e.structuredContent["material"]
        bad = await client.call_tool("decisioncraft_render", {"model": model, "filename": "../x.html"})
        assert bad.isError

    asyncio.run(_with_client(check))


def test_draft_without_sampling_says_what_to_do():
    async def check(client):
        r = await client.call_tool("decisioncraft_draft", {
            "material": [{"name": "n.md", "text": "Notes."}], "question": "Q?",
            "template": "opportunity-tree"})
        assert r.isError and "sampling" in r.content[0].text
        assert "decisioncraft_templates" in r.content[0].text

    asyncio.run(_with_client(check))


def test_draft_through_the_hosts_model():
    seen = {}

    async def sampling(context, params: types.CreateMessageRequestParams):
        seen["system"] = params.systemPrompt
        return types.CreateMessageResult(
            role="assistant", model="host-model",
            content=types.TextContent(type="text", text=json.dumps(TINY)))

    async def check(client):
        r = await client.call_tool("decisioncraft_draft", {
            "material": [{"name": "n.md", "text": "Notes."}], "question": "Q?",
            "template": "opportunity-tree"})
        assert not r.isError, r.content
        assert r.structuredContent["model"]["title"] == "T"
        assert r.structuredContent["summary"]["maps"] == 1

    asyncio.run(_with_client(check, sampling_callback=sampling))
    assert seen["system"]


def test_review_notes_tool_dry_run_and_sampling():
    model = dc.example("business")["model"]
    review = dc.example("business")["reviews"][0]
    review = {**review, "notes": [{"id": "R9", "anchor": "ci5", "text": "What about the villages?", "ask": {"roles": ["owner"]}}]}

    async def sample(context, params):
        return types.CreateMessageResult(role="assistant", model="stand-in", content=types.TextContent(type="text", text=json.dumps(
            {"replies": [{"note": "R9", "role": "owner", "view": "Keep the pilot small.", "question": "Villages later?", "urgency": "must"}]})))

    async def go(client):
        dry = await client.call_tool("decisioncraft_review_notes", {"model": model, "review": review, "dry_run": True})
        real = await client.call_tool("decisioncraft_review_notes", {"model": model, "review": review})
        return dry.structuredContent, real.structuredContent

    dry, real = asyncio.run(_with_client(go, sampling_callback=sample))
    assert dry["asked"][0]["roles"] == ["owner"] and dry["replies_added"] == 0
    assert real["replies_added"] == 1 and real["review"]["notes"][0]["replies"][0]["id"] == "R9-owner"
