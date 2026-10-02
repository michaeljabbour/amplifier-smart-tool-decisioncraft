"""Regression tests for the four leftovers fixed in 0.2.1."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import importlib

modes = importlib.import_module("decisioncraft.modes")
from decisioncraft.mapper import check_target, looks_like_path
from decisioncraft.term import open_in_browser

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(os.environ, PYTHONPATH=str(ROOT / "src"), DECISIONCRAFT_NO_BROWSER="1")
for k in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "DECISIONCRAFT_PROVIDER", "DECISIONCRAFT_MODEL"):
    ENV.pop(k, None)


def jcli(*args, cwd=None):
    r = subprocess.run([sys.executable, "-m", "decisioncraft", "--json", *args], capture_output=True,
                       text=True, env=ENV, timeout=60, cwd=cwd)
    return r, json.loads(r.stdout)


# a. quick: scores for unknown options or criteria are refused, not dropped


def test_quick_scores_without_criteria_are_refused():
    r, d = jcli("quick", "--option", "A", "--option", "B", "--score", "A=speed=4")
    assert r.returncode == 1 and not d["ok"]
    assert d["error"]["code"] == "invalid_input"
    assert "'speed'" in d["error"]["message"] and "--criterion" in d["error"]["message"]
    assert d["error"]["field"] == "--score"


def test_quick_unknown_option_lists_the_valid_ones():
    r, d = jcli("quick", "--option", "A", "--option", "B", "--criterion", "speed", "--score", "Z=speed=4")
    assert r.returncode == 1 and d["error"]["code"] == "invalid_input"
    assert "'Z'" in d["error"]["message"] and "'A', 'B'" in d["error"]["message"]


def test_quick_library_refuses_unknown_criterion():
    with pytest.raises(ValueError, match="unknown criterion 'sped'.*'speed'"):
        modes.quick(["A", "B"], ["speed"], [{"option": "A", "criterion": "sped", "score": 4}])


def test_quick_valid_scores_still_total():
    r, d = jcli("quick", "--option", "A", "--option", "B", "--criterion", "speed",
                "--score", "A=speed=4", "--score", "B=speed=2")
    assert d["ok"] and d["result"]["lean"]["title"] == "A"


# b. --model works on every model-backed command


@pytest.mark.parametrize("cmd", ["perspectives", "session", "draft", "map"])
def test_every_model_command_takes_model(cmd):
    r = subprocess.run([sys.executable, "-m", "decisioncraft", cmd, "-h"], capture_output=True, text=True,
                       env=ENV, timeout=60)
    assert "--model NAME" in r.stdout
    assert "--model-name" not in r.stdout  # the older spelling still works but isn't shown


def test_model_name_alias_still_parses(tmp_path):
    model = ROOT / "examples" / "business" / "model.json"
    r, d = jcli("perspectives", str(model), "--provider", "anthropic", "--model-name", "x", "--dry-run")
    assert "unrecognized" not in r.stderr and "usage" != (d.get("error") or {}).get("code")


# c. opening a browser never lets helper programs write to the terminal


def test_open_in_browser_silences_helper_stderr(monkeypatch, capfd):
    import webbrowser

    def noisy(url):
        os.write(2, b"osascript: execution error\n")
        return False

    monkeypatch.setattr(webbrowser, "open", noisy)
    assert open_in_browser("file:///tmp/x.html") is False
    assert "osascript" not in capfd.readouterr().err


# d. a missing path is an error, not a topic


@pytest.mark.parametrize("target", ["./nothere", "../nothere", "~/nothere-xyz", "notes.md", "src/nowhere"])
def test_missing_paths_are_paths(target):
    assert looks_like_path(target)
    with pytest.raises(ValueError, match="looks like a path"):
        check_target(target)


@pytest.mark.parametrize("target", ["how our onboarding works", "renew or buy", "https://example.com/a"])
def test_plain_words_and_urls_are_not_paths(target):
    assert not looks_like_path(target)
    assert check_target(target) == target


def test_map_dry_run_refuses_missing_path(tmp_path):
    r, d = jcli("map", "./nothere", "--dry-run", cwd=tmp_path)
    assert r.returncode == 1 and d["error"]["code"] == "file_not_found"
    assert "plain words" in d["error"]["hint"]
