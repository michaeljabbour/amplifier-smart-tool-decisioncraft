"""Use the official SDK client against the real stdio server."""

import asyncio
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import decisioncraft as dc
from decisioncraft.review import blank_review


def test_stdio_host_receives_the_finished_review_and_handoff(tmp_path):
    async def check():
        env = dict(
            os.environ, PYTHONPATH=str(Path(__file__).resolve().parent.parent / "src")
        )
        params = StdioServerParameters(
            command=sys.executable, args=["-m", "decisioncraft", "mcp"], env=env
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                listed = await client.list_tools()
                assert {
                    "decisioncraft_discover",
                    "decisioncraft_wait_for_review",
                    "decisioncraft_handoff",
                } <= {t.name for t in listed.tools}
                discovery = await client.call_tool(
                    "decisioncraft_discover", {"question": "Which trial?"}
                )
                assert len(discovery.structuredContent["questions"]) == 4
                model = dc.new("decision-chain", "Host review", "Which trial?")
                model["maps"][0]["stages"] = [
                    dict(
                        id="stage",
                        label="Trial",
                        items=[dict(id="trial", title="Run one trial", when="planned")],
                    )
                ]
                review = blank_review(model)
                started = await client.call_tool(
                    "decisioncraft_start_review",
                    dict(
                        model=model,
                        directory=str(tmp_path / "review"),
                        open_browser=False,
                    ),
                )
                info = started.structuredContent
                request = Request(
                    info["url"].rstrip("/") + "/finish",
                    data=json.dumps(dict(version=0, review=review)).encode(),
                    headers={
                        "Origin": info["url"].split("/review/")[0],
                        "Content-Type": "application/json",
                    },
                )
                with urlopen(request, timeout=3) as response:
                    assert json.load(response)["handoff"]["proposed_model"]
                completed = await client.call_tool(
                    "decisioncraft_wait_for_review",
                    dict(session_id=info["session_id"], timeout=0),
                )
                result = completed.structuredContent
                assert result["state"] == "finished"
                assert (
                    result["handoff"]["review"]["model_fingerprint"]
                    == review["model_fingerprint"]
                )
                assert (tmp_path / "review" / "proposed-canvas.html").exists()
                assert (tmp_path / "review" / "user-stories.md").exists()
                closed = await client.call_tool(
                    "decisioncraft_close_review", dict(session_id=info["session_id"])
                )
                assert closed.structuredContent["state"] == "closed"

    asyncio.run(check())
