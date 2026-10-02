"""Regression tests for 0.2.3: empty maps are not finished maps, missing package data fails
loudly, and doctor understands skill mode."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import decisioncraft as dc
import importlib

doctor_mod = importlib.import_module("decisioncraft.doctor")
from decisioncraft import examples as examples_mod
from decisioncraft import lib
from decisioncraft.errors import ToolError
from decisioncraft.model import content_count

ROOT = Path(__file__).resolve().parents[1]
BIN = ROOT / "bin" / "decisioncraft.py"


def cli(*args, env_extra=None):
    import os

    env = {**os.environ, "DECISIONCRAFT_HOST": "none", "NO_COLOR": "1"}
    env.update(env_extra or {})
    return subprocess.run([sys.executable, str(BIN), *args], capture_output=True, text=True, env=env)


def starter(tmp_path) -> Path:
    m = dc.new("system-journeys", "How the shop works", "How does it work today?")
    p = tmp_path / "model.json"
    p.write_text(json.dumps(m))
    return p


def test_content_count_sees_steps_items_ideas_and_options():
    assert content_count(dc.new("system-journeys", "T", "Q?")) == 0
    assert content_count(dc.new("opportunity-tree", "T", "Q?")) == 0
    car = json.loads((ROOT / "examples" / "personal-car" / "model.json").read_text())
    assert content_count(car) > 0
    tree = dc.new("opportunity-tree", "T", "Q?")
    tree["maps"][0]["root"]["children"] = [{"id": "a", "title": "Idea", "text": "", "children": []}]
    assert content_count(tree) == 1
    assert content_count({"options": [{"id": "keep"}], "maps": []}) == 1
    assert content_count("not a model") == 0


def test_validate_flags_an_empty_map_unless_allowed():
    m = dc.new("decision-chain", "T", "Q?")
    errs = [p for p in dc.validate(m) if p["level"] == "error"]
    assert len(errs) == 1 and errs[0]["path"] == "maps" and "map is empty" in errs[0]["message"]
    assert "--allow-empty" in errs[0]["message"]
    assert [p for p in dc.validate(m, allow_empty=True) if p["level"] == "error"] == []


def test_render_refuses_an_empty_map_unless_allowed():
    m = dc.new("decision-chain", "T", "Q?")
    with pytest.raises(dc.model.ModelError, match="map is empty"):
        dc.render(m)
    assert "<html" in dc.render(m, allow_empty=True).lower()


def test_cli_validate_and_render_on_an_untouched_starter(tmp_path):
    p = starter(tmp_path)
    r = cli("validate", str(p), "--json")
    assert r.returncode == 1
    body = json.loads(r.stdout)
    assert body["ok"] is False and body["error"]["code"] == "invalid_model"
    assert "map is empty" in json.dumps(body)
    assert cli("validate", str(p), "--allow-empty", "--json").returncode == 0
    out = tmp_path / "c.html"
    assert cli("render", str(p), "--out", str(out), "--json").returncode == 1 and not out.exists()
    assert cli("render", str(p), "--out", str(out), "--allow-empty", "--json").returncode == 0 and out.exists()


def test_map_starter_instructions_warn_about_the_empty_check(tmp_path):
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "a.md").write_text("The desk books slots in a paper diary.\n")
    r = cli("map", str(folder), "--starter", "--dir", str(tmp_path / "out"), "--json")
    assert r.returncode == 0, r.stderr
    fill = (tmp_path / "out" / "FILL-IN.md").read_text()
    assert "empty" in fill and "never hand over an empty canvas" in fill
    assert cli("validate", str(tmp_path / "out" / "model.json"), "--json").returncode == 1


def test_guide_fails_loudly_when_the_model_format_is_missing(monkeypatch):
    class Missing:
        def joinpath(self, *_a):
            return self

        def is_file(self):
            return False

    import importlib.resources as ir
    from pathlib import Path as P

    monkeypatch.setattr(ir, "files", lambda _pkg: Missing())
    monkeypatch.setattr(P, "is_file", lambda self: False)
    with pytest.raises(ToolError) as e:
        lib.guide()
    assert e.value.code == "missing_resource" and "model-format.md" in e.value.message
    assert "skill" in e.value.hint


def test_guide_returns_the_model_format():
    assert lib.guide()["model_format"].strip()


def test_example_names_the_missing_piece_and_skill_hint(monkeypatch):
    monkeypatch.setattr(examples_mod, "_root", lambda _name: None)
    with pytest.raises(ToolError) as e:
        examples_mod.example("car")
    assert e.value.code == "missing_resource"
    assert "examples/personal-car/model.json" in e.value.message
    assert "skill" in e.value.hint and e.value.exit_code == 3


def test_doctor_in_skill_mode_skips_provider_checks(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISIONCRAFT_HOST", "skill")
    report = doctor_mod.doctor(directory=str(tmp_path))
    ids = {c["id"] for c in report["checks"]}
    assert "skill_mode" in ids
    assert not any(i.startswith(("provider_", "complete_cmd", "model", "mcp")) for i in ids)
    assert report["summary"].startswith("Skill mode")
    assert report["ready"]["host"] == "skill" and report["ready"]["map_uses_host_model"] is True


def test_doctor_outside_skill_mode_still_checks_providers(monkeypatch, tmp_path):
    monkeypatch.setenv("DECISIONCRAFT_HOST", "none")
    ids = {c["id"] for c in doctor_mod.doctor(directory=str(tmp_path))["checks"]}
    assert {"provider_anthropic", "provider_openai"} <= ids
