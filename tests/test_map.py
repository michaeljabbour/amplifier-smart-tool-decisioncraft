"""map: point it at a repo, notes, a page or a topic; a stand-in model draws the as-is / to-be."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import decisioncraft as dc
from decisioncraft.mapper import detect, gather, map_roles

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import stub_map  # noqa: E402

REPO = HERE / "fixtures" / "sample-repo"
# No API keys: a host without sampling must not fall back to a paid provider in tests.
ENV = dict({k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "DECISIONCRAFT_MODEL")}, PYTHONPATH=str(HERE.parent / "src"), DECISIONCRAFT_NO_BROWSER="1")


def cli(*args, cwd=None):
    return subprocess.run([sys.executable, "-m", "decisioncraft", *args], capture_output=True, text=True,
                          env=ENV, cwd=cwd, timeout=120)


def test_detect_targets(tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.md").write_text("# Notes")
    assert detect(str(REPO)) == "repo"
    assert detect(str(tmp_path / "notes")) == "folder"
    assert detect(str(REPO / "README.md")) == "file"
    assert detect("https://example.com/how-it-works") == "url"
    assert detect("how our customer onboarding works") == "topic"


def test_gather_numbers_lines_and_reads_readme_first():
    g = gather(str(REPO))
    assert g["read"][0]["path"] == "README.md"
    app = next(m for m in g["material"] if m["name"] == "src/booking/app.py")
    assert "   4| HOLD_MINUTES = 15" in app["text"]
    assert g["material"][0]["name"] == "(overview of the folder)"


def test_gather_respects_gitignore_and_budget(tmp_path):
    (tmp_path / ".gitignore").write_text("secrets/\n*.log\n")
    (tmp_path / "secrets").mkdir()
    (tmp_path / "secrets" / "keys.md").write_text("do not read")
    (tmp_path / "run.log").write_text("noise")
    (tmp_path / "README.md").write_text("# App\n" + "line\n" * 5000)
    (tmp_path / "main.py").write_text("print('hi')\n")
    g = gather(str(tmp_path), budget=3000, per_file=2000)
    paths = [r["path"] for r in g["read"]]
    assert "secrets/keys.md" not in paths and "run.log" not in paths
    assert g["read"][0]["cut"] is True and sum(r["chars"] for r in g["read"]) <= 3000


def test_plan_for_a_topic_and_a_url():
    t = dc.plan_map("how our customer onboarding works")
    assert t["kind"] == "topic" and t["needs"]["kind"] == "answers" and t["model_calls"] == 0
    assert t["question"].startswith("How does our customer onboarding work today")
    u = dc.plan_map("https://example.com")
    assert u["needs"]["kind"] == "page_text"


def test_map_roles():
    assert [r["label"] for r in map_roles()][:3] == ["UX designer", "Architect", "Business analyst"]
    assert map_roles(["architect", "finance"])[1]["id"] == "finance"
    with pytest.raises(ValueError):
        map_roles(["nobody"])


def test_map_target_draws_as_is_to_be_with_stories_and_notes():
    r = dc.map_target(str(REPO), complete=stub_map.complete)
    m = r["model"]
    steps = m["maps"][0]["journeys"][0]["steps"]
    assert {s.get("when") for s in steps} >= {"today", "planned"}
    assert any(s.get("replaces") for s in steps)
    assert all(g["stories"] and g["stories"][0]["done_when"] for g in m["gaps"])
    assert {n["role"] for n in m["notes"]} >= {r["id"] for r in map_roles()}
    assert all(n["question"].strip() for n in m["notes"])
    assert m["display"]["notes_on_map"] is True and m["display"]["start_view"] == "planned"
    assert m["checked"]["note"].startswith("Checked against")
    assert not [p for p in dc.validate(m) if p["level"] == "error"]


def test_map_topic_without_answers_is_marked_unchecked():
    seen = {}

    def complete(system, prompt):
        seen.setdefault("prompt", prompt)
        return stub_map.complete(system, prompt)

    dc.map_target("how bike hire works", complete=complete)
    assert "nothing here has been checked" in seen["prompt"]


def test_map_url_needs_text_or_permission():
    with pytest.raises(ValueError, match="does not fetch"):
        dc.map_target("https://example.com", complete=stub_map.complete)
    r = dc.map_target("https://example.com", page_text="Bike hire: book online, pay at the counter.",
                      complete=stub_map.complete)
    assert r["model"]["map_source"]["kind"] == "url"


def test_cli_map_dry_run_and_draw(tmp_path):
    plan = json.loads(cli("map", str(REPO), "--dry-run", "--json").stdout)
    assert plan["ok"] and plan["result"]["kind"] == "repo" and plan["result"]["model_calls"] == 2
    r = cli("map", str(REPO), "--complete-cmd", stub_map.COMMAND, "--dir", str(tmp_path / "m"), "--json")
    env = json.loads(r.stdout)
    assert env["ok"], r.stderr
    assert Path(env["result"]["canvas_path"]).is_file() and Path(env["result"]["model_path"]).is_file()
    assert env["result"]["summary"]["gaps"] == 2


def test_cli_map_errors():
    none = cli("map", str(REPO), "--json")
    assert none.returncode == 3 and json.loads(none.stdout)["error"]["code"] == "provider_not_configured"
    url = cli("map", "https://example.com", "--complete-cmd", "true", "--json")
    assert url.returncode == 1 and json.loads(url.stdout)["error"]["field"] == "--page"
    roles = cli("map", str(REPO), "--roles", "nobody", "--dry-run", "--json")
    assert roles.returncode == 2


def test_start_screen_leads_with_map():
    out = cli().stdout
    assert out.splitlines()[4].strip().startswith("decisioncraft map ./your-repo --open")


def test_mcp_map():
    pytest.importorskip("mcp")
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    params = StdioServerParameters(command=sys.executable, args=["-m", "decisioncraft", "mcp"], env=ENV)

    async def run():
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                plan = await client.call_tool("decisioncraft_map", {"target": str(REPO), "dry_run": True})
                assert plan.structuredContent["plan"]["kind"] == "repo"
                nosample = await client.call_tool("decisioncraft_map", {"target": str(REPO)})
                # No sampling and no key: a starter to fill in, not a dead end.
                assert not nosample.isError and nosample.structuredContent["starter"] is True
                assert Path(nosample.structuredContent["digest_path"]).is_file()
                p = await client.get_prompt("map_this", {"target": "./the-repo"})
                assert "decisioncraft_map" in p.messages[0].content.text

    asyncio.run(run())


def test_map_starter_writes_digest_model_and_instructions_without_a_model(tmp_path):
    import json as _json
    import subprocess as _sp
    import sys as _sys
    from pathlib import Path as _P

    repo = _P(__file__).parent / "fixtures" / "sample-repo"
    out = tmp_path / "m"
    r = _sp.run([_sys.executable, str(_P(__file__).parents[1] / "bin" / "decisioncraft.py"), "map", str(repo),
                 "--starter", "--dir", str(out), "--json"], capture_output=True, text=True, stdin=_sp.DEVNULL)
    assert r.returncode == 0, r.stdout + r.stderr
    d = _json.loads(r.stdout)
    assert d["ok"] and d["next"][0] == "decisioncraft guide"
    model = _json.loads((out / "model.json").read_text())
    assert model["display"] == {"notes_on_map": True, "start_view": "planned"}
    assert len(model["roles"]) == 8 and model["checked"]["note"]
    assert "   1| " in (out / "material" / "digest.md").read_text()
    assert "decisioncraft guide" in (out / "FILL-IN.md").read_text()
