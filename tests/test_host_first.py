"""Inside an agent harness, map uses the agent's own model unless a model was chosen explicitly."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from decisioncraft import intelligence as ig

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT / "tests" / "fixtures" / "sample-repo"


@pytest.fixture
def clean(monkeypatch, tmp_path):
    for _n, keys in ig.HOST_MARKERS:
        for k in keys:
            monkeypatch.delenv(k, raising=False)
    for k in ("DECISIONCRAFT_HOST", "DECISIONCRAFT_PROVIDER", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("DECISIONCRAFT_CONFIG", str(tmp_path / "config.json"))
    return monkeypatch


@pytest.mark.parametrize("var,host", [("CLAUDECODE", "Claude Code"), ("CLAUDE_CODE_ENTRYPOINT", "Claude Code"),
                                      ("CODEX_SANDBOX", "Codex"), ("CODEX_THREAD_ID", "Codex"),
                                      ("AMPLIFIER_SESSION_ID", "Amplifier")])
def test_detects_hosts(clean, var, host):
    clean.setenv(var, "1")
    assert ig.detect_host() == host


def test_no_host_outside_agents(clean):
    assert ig.detect_host() is None
    assert ig.host_first() is None


def test_declared_host_and_opt_out(clean):
    clean.setenv("DECISIONCRAFT_HOST", "My Agent")
    assert ig.detect_host() == "My Agent"
    clean.setenv("CLAUDECODE", "1")
    clean.setenv("DECISIONCRAFT_HOST", "none")
    assert ig.detect_host() is None


def test_explicit_choice_wins_over_host(clean):
    clean.setenv("CLAUDECODE", "1")
    assert ig.host_first() == "Claude Code"
    assert ig.host_first(provider="anthropic") is None
    assert ig.host_first(complete_cmd="my-model") is None
    clean.setenv("DECISIONCRAFT_PROVIDER", "openai")
    assert ig.host_first() is None
    clean.delenv("DECISIONCRAFT_PROVIDER")
    ig.save_config({"provider": "anthropic"})
    assert ig.host_first() is None


def test_api_key_alone_is_not_an_explicit_choice(clean):
    clean.setenv("CLAUDECODE", "1")
    clean.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert ig.explicit_choice() is None
    assert ig.host_first() == "Claude Code"


def _cli(*args, env, cwd):
    return subprocess.run([sys.executable, str(ROOT / "bin" / "decisioncraft.py"), *args], capture_output=True,
                          text=True, env=env, cwd=cwd)


def test_map_inside_agent_takes_the_starter_route(clean, tmp_path):
    env = {k: v for k, v in os.environ.items()}
    env.update({"CLAUDECODE": "1", "ANTHROPIC_API_KEY": "sk-not-used", "NO_COLOR": "1"})
    r = _cli("map", str(REPO), "--dir", str(tmp_path / "out"), "--json", env=env, cwd=tmp_path)
    out = json.loads(r.stdout)
    assert r.returncode == 0, r.stdout + r.stderr
    assert out["result"]["route"] == "host" and out["result"]["host"] == "Claude Code"
    assert (tmp_path / "out" / "FILL-IN.md").exists()
    assert "Running inside Claude Code" in r.stderr


def test_doctor_reports_host_routing(clean, tmp_path):
    env = {k: v for k, v in os.environ.items()}
    env.update({"CODEX_SANDBOX": "seatbelt", "NO_COLOR": "1"})
    r = _cli("doctor", "--json", env=env, cwd=tmp_path)
    data = json.loads(r.stdout)["result"]
    assert data["ready"]["host"] == "Codex" and data["ready"]["map_uses_host_model"] is True
