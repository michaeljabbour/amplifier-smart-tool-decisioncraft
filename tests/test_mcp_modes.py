"""The modes over MCP: tools, prompts and resources, through the official client."""

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ENV = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parent.parent / "src"))
PARAMS = StdioServerParameters(command=sys.executable, args=["-m", "decisioncraft", "mcp"], env=ENV)


async def _with_client(fn):
    async with stdio_client(PARAMS) as (reader, writer):
        async with ClientSession(reader, writer) as client:
            await client.initialize()
            return await fn(client)


def test_mode_tools(tmp_path):
    async def check(client):
        names = {t.name for t in (await client.list_tools()).tools}
        assert {"decisioncraft_triage", "decisioncraft_quick", "decisioncraft_interview_next"} <= names
        t = await client.call_tool("decisioncraft_triage", {"text": "my lease is up, renew or buy the car?"})
        assert t.structuredContent["mode"] == "guided"
        q = await client.call_tool("decisioncraft_quick", {
            "options": ["Renew", "Buy"], "criteria": ["must:cost", "reliability"],
            "scores": [{"option": "Renew", "criterion": "cost", "score": 3},
                       {"option": "Buy", "criterion": "cost", "score": 4}]})
        assert q.structuredContent["table"].startswith("| Option")
        d = str(tmp_path / "car")
        r = await client.call_tool("decisioncraft_interview_next", {"directory": d, "question": "renew the lease or buy the car?"})
        assert r.structuredContent["question"]["id"] == "options"
        r = await client.call_tool("decisioncraft_interview_next", {"directory": d, "answer": "keep the old car too"})
        assert r.structuredContent["known"]["options"][-1] == "Keep the old car too"

    asyncio.run(_with_client(check))


def test_prompts_and_resources():
    async def check(client):
        prompts = {p.name for p in (await client.list_prompts()).prompts}
        assert prompts == {"map_this", "decide", "compare_options", "what_could_go_wrong", "regret_test", "review_canvas"}
        p = await client.get_prompt("decide", {"situation": "renew or buy my car"})
        text = p.messages[0].content.text
        assert "decisioncraft_triage" in text and "renew or buy my car" in text
        uris = {str(r.uri) for r in (await client.list_resources()).resources}
        assert {"decisioncraft://templates", "decisioncraft://roles", "decisioncraft://writing-guide",
                "decisioncraft://interview-questions", "decisioncraft://modes", "decisioncraft://examples"} <= uris
        bank = await client.read_resource("decisioncraft://interview-questions")
        assert "personal" in json.loads(bank.contents[0].text)
        ex = await client.read_resource("decisioncraft://examples")
        assert {e["name"] for e in json.loads(ex.contents[0].text)} >= {"business", "medical"}

    asyncio.run(_with_client(check))
