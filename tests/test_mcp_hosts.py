"""MCP behaviour a real host depends on: version, paths, folders, and the API-key fallback."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

pytest.importorskip("mcp")
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402

HERE = Path(__file__).resolve().parent
REPO = HERE / "fixtures" / "sample-repo"
BASE = {k: v for k, v in os.environ.items()
        if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "DECISIONCRAFT_MODEL")}
BASE["PYTHONPATH"] = str(HERE.parent / "src")


def run(fn, env=None, cwd=None):
    params = StdioServerParameters(command=sys.executable, args=["-m", "decisioncraft", "mcp"],
                                   env=env or BASE, cwd=cwd)

    async def go():
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                info = await client.initialize()
                return await fn(client, info)

    return asyncio.run(go())


def test_server_reports_the_tool_version_not_the_sdk_version():
    from decisioncraft.help import VERSION

    async def check(client, info):
        return info.serverInfo.version

    assert run(check) == VERSION


def test_a_missing_path_is_refused_not_mapped_as_a_topic(tmp_path):
    async def check(client, info):
        missing = await client.call_tool("decisioncraft_map", {"target": "./not-here", "dry_run": True})
        absent = await client.call_tool("decisioncraft_map", {"target": str(tmp_path / "nope"), "dry_run": True})
        relative = await client.call_tool("decisioncraft_map", {"target": "sample-repo", "dry_run": True})
        topic = await client.call_tool("decisioncraft_map", {"target": "how our onboarding works", "dry_run": True})
        return missing, absent, relative, topic

    import shutil

    shutil.copytree(REPO, tmp_path / "sample-repo")
    missing, absent, relative, topic = run(check, cwd=str(tmp_path))
    assert missing.isError and "looks like a path" in missing.content[0].text
    assert absent.isError and "nothing is there" in absent.content[0].text
    assert relative.structuredContent["plan"]["kind"] == "repo"  # resolved against the server's folder
    assert topic.structuredContent["plan"]["kind"] == "topic"


def test_unwritable_folder_says_so_plainly():
    async def check(client, info):
        return await client.call_tool("decisioncraft_interview_next", {"directory": "/nonexistent-root/x", "question": "Q?"})

    r = run(check)
    assert r.isError and "Can't write to" in r.content[0].text and "Errno" not in r.content[0].text


def test_map_hands_the_host_a_task_and_saves_files_only_when_asked(tmp_path):
    async def check(client, info):
        inline = await client.call_tool("decisioncraft_map", {"target": str(REPO)})
        saved = await client.call_tool("decisioncraft_map", {"target": str(REPO), "directory": str(tmp_path / "b"),
                                                             "starter": True})
        return inline, saved

    inline, saved = run(check)
    for r in (inline, saved):
        sc = r.structuredContent
        assert not r.isError and sc["starter"] is True and sc["you_write"] is True and sc["next"]
        assert "## Material digest" in r.content[0].text and "## Model format" in r.content[0].text
    assert "model_path" not in inline.structuredContent
    assert Path(saved.structuredContent["model_path"]).is_file() and Path(saved.structuredContent["digest_path"]).is_file()


def test_draft_hands_the_host_a_task_and_never_reads_keys():
    async def check(client, info):
        return await client.call_tool("decisioncraft_draft", {"material": [{"name": "n", "text": "x"}], "question": "Q?"})

    env = {**BASE, "ANTHROPIC_API_KEY": "sk-should-not-be-used", "OPENAI_API_KEY": "sk-should-not-be-used"}
    r = run(check, env=env)
    assert not r.isError and r.structuredContent["you_write"] is True
    assert "No API key is used" in r.content[0].text and "decisioncraft_render" in r.content[0].text


def test_example_description_lists_every_id():
    async def check(client, info):
        tools = await client.list_tools()
        return next(t for t in tools.tools if t.name == "decisioncraft_example").description

    desc = run(check)
    from decisioncraft.examples import example_names

    for e in example_names():
        assert e["id"] in desc


def test_key_fallback_is_used_when_the_host_cannot_sample(monkeypatch):
    """No sampling, but a key: the server's own provider answers (stubbed here)."""
    from decisioncraft import intelligence, mcp_server

    calls = []

    def fake_provider(provider, model=None, max_tokens=16000):
        calls.append((provider, model))
        return lambda system, prompt: "{}"

    monkeypatch.setattr(intelligence, "provider_complete", fake_provider)
    for name in ("default_complete", "resolve_complete"):
        monkeypatch.delattr(intelligence, name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("DECISIONCRAFT_MODEL", "gpt-5.5")
    monkeypatch.delenv("DECISIONCRAFT_PROVIDER", raising=False)
    complete, how = mcp_server._key_complete()
    assert complete is not None and calls == [("openai", "gpt-5.5")] and how == "openai gpt-5.5"
