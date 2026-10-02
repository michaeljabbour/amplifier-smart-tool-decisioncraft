"""The command line as people and agents meet it: start screen, example, new, doctor,
render progress, --json envelopes, errors with hints, exit codes, NO_COLOR and non-TTY."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BIN = ROOT / "bin" / "decisioncraft.py"
SCRUB = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


def run(*args, cwd=None, env=None, stdin=subprocess.DEVNULL):
    e = {k: v for k, v in os.environ.items() if k not in SCRUB}
    e["DECISIONCRAFT_NO_BROWSER"] = "1"
    e.update(env or {})
    return subprocess.run([sys.executable, str(BIN), *args], cwd=cwd, env=e, stdin=stdin,
                          capture_output=True, text=True, timeout=120)


def envelope(r):
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    assert len(lines) == 1, r.stdout
    doc = json.loads(lines[0])
    assert set(doc) >= {"ok", "command", "files"}
    assert doc["ok"] == (r.returncode == 0)
    return doc


def test_no_arguments_shows_a_start_screen():
    r = run()
    assert r.returncode == 0
    assert "decisioncraft example medical --open" in r.stdout
    for c in ("example", "new", "render", "doctor"):
        assert f"decisioncraft {c}" in r.stdout


def test_short_help_fits_80_columns_for_every_command():
    from decisioncraft.help import CAPABILITIES

    for name in [None, *CAPABILITIES]:
        r = run(*(["-h"] if name is None else [name, "-h"]))
        assert r.returncode == 0, (name, r.stderr)
        assert all(len(line) <= 80 for line in r.stdout.splitlines()), name
        if name:
            assert "Examples:" in r.stdout and "Options for every command" in r.stdout


def test_full_help_is_still_the_skill():
    r = run("--help")
    assert r.stdout.startswith('<skill_content name="decisioncraft">')
    r = run("example", "--help")
    assert r.stdout.startswith('<skill_content name="decisioncraft example">')


def test_example_copies_and_draws(tmp_path):
    r = run("example", "medical", "--open", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    d = tmp_path / "decisioncraft-example-medical"
    assert (d / "model.json").is_file() and (d / "canvas.html").is_file() and (d / "in-words.md").is_file()
    assert any((d / "material").iterdir())
    assert "Wrote" in r.stderr and "Try next" not in r.stdout
    # a second run refuses to overwrite
    again = run("example", "medical", cwd=tmp_path)
    assert again.returncode == 1 and "--force" in again.stderr


def test_example_json_reports_files(tmp_path):
    doc = envelope(run("example", "technical", "--out", str(tmp_path / "t"), "--json"))
    kinds = {f["kind"] for f in doc["files"]}
    assert {"model", "material", "canvas", "words"} <= kinds
    assert doc["result"]["summary"]["maps"] >= 1 and doc["next"]


def test_unknown_example_is_a_usage_error():
    r = run("example", "cooking")
    assert r.returncode == 2 and "invalid choice" in r.stderr


def test_new_never_prompts_without_a_terminal(tmp_path):
    r = run("new", cwd=tmp_path)
    assert r.returncode == 2 and "--question" in r.stderr
    doc = envelope(run("new", "--json", cwd=tmp_path))
    assert doc["error"]["code"] == "missing_argument" and doc["exit_code"] == 2


def test_new_writes_a_starter_folder(tmp_path):
    r = run("new", "--question", "Should we lease or buy our next van?", "--roles", "owner,finance",
            "--dir", "van", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    model = json.loads((tmp_path / "van" / "model.json").read_text())
    assert [x["id"] for x in model["roles"]] == ["owner", "finance"]
    assert model["maps"][0]["template"] == "decision-chain"
    assert "material/README.txt" not in r.stdout
    readme = (tmp_path / "van" / "material" / "README.txt").read_text()
    assert "lease or buy" in readme and "decisioncraft render" in readme
    assert run("new", "--question", "Q?", "--dir", "van", cwd=tmp_path).returncode == 1
    bad = run("new", "--question", "Q?", "--roles", "chef", "--yes", cwd=tmp_path)
    assert bad.returncode == 1 and "Choose from" in bad.stderr


def test_new_keeps_the_old_flag_form(tmp_path):
    r = run("new", "--template", "decision-chain", "--title", "T", "--question", "Q?")
    assert r.returncode == 0 and json.loads(r.stdout)["title"] == "T"


def test_render_progress_goes_to_stderr_and_html_to_stdout_when_piped(tmp_path):
    run("example", "business", "--out", str(tmp_path / "b"), "-q")
    r = run("render", str(tmp_path / "b" / "model.json"))
    assert r.returncode == 0 and r.stdout.lstrip().startswith("<!")
    assert "Reading" in r.stderr
    q = run("render", str(tmp_path / "b" / "model.json"), "--out", str(tmp_path / "c.html"), "-q")
    assert q.returncode == 0 and q.stderr == "" and (tmp_path / "c.html").is_file()


def test_render_json_writes_beside_the_model(tmp_path):
    run("example", "engineering", "--out", str(tmp_path / "e"), "-q")
    doc = envelope(run("render", str(tmp_path / "e" / "model.json"), "--json"))
    assert doc["result"]["path"].endswith("canvas.html") and doc["files"][0]["kind"] == "canvas"


def test_render_watch_redraws(tmp_path):
    run("example", "engineering", "--out", str(tmp_path / "e"), "-q")
    model = tmp_path / "e" / "model.json"
    p = subprocess.Popen(
        [sys.executable, str(BIN), "render", str(model), "--watch", "--json"],
        env=dict(os.environ, DECISIONCRAFT_WATCH_ROUNDS="6", DECISIONCRAFT_WATCH_INTERVAL="0.3",
                 DECISIONCRAFT_NO_BROWSER="1"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    import time

    time.sleep(0.8)
    os.utime(model, None)
    out, _ = p.communicate(timeout=30)
    events = [json.loads(l)["event"] for l in out.splitlines() if l.strip()]
    assert p.returncode == 0 and events.count("rendered") >= 2


@pytest.mark.parametrize("args,code,error", [
    (["render", "missing.json"], 1, "file_not_found"),
    (["validate", "BAD"], 1, "bad_json"),
    (["validate", "INVALID"], 1, "invalid_model"),
    (["no-such-command"], 2, "usage"),
    (["render"], 2, "usage"),
    (["draft", "NOTE", "--question", "Q?"], 2, "missing_argument"),
    (["draft", "NOTE", "--question", "Q?", "--provider", "anthropic"], 3, "provider_not_configured"),
    (["draft", "NOTE", "--question", "Q?", "--complete-cmd", "FAIL"], 4, "model_call_failed"),
])
def test_errors_have_codes_hints_and_exit_codes(tmp_path, args, code, error):
    (tmp_path / "bad.json").write_text('{"a": ')
    (tmp_path / "invalid.json").write_text('{"format": "decisioncraft/1", "title": "x"}')
    (tmp_path / "n.md").write_text("Notes.")
    fail = f'{sys.executable} -c "import sys; sys.exit(1)"'
    swap = {"BAD": str(tmp_path / "bad.json"), "INVALID": str(tmp_path / "invalid.json"),
            "NOTE": str(tmp_path / "n.md"), "FAIL": fail}
    args = [swap.get(a, a) for a in args]
    human = run(*args, cwd=tmp_path)
    assert human.returncode == code, human.stderr
    assert "Traceback" not in human.stderr
    doc = envelope(run(*args, "--json", cwd=tmp_path))
    assert doc["exit_code"] == code and doc["error"]["code"] == error
    assert doc["error"]["message"] and "hint" in doc["error"]


def test_invalid_model_names_the_field(tmp_path):
    (tmp_path / "invalid.json").write_text('{"format": "decisioncraft/1", "title": "x"}')
    doc = envelope(run("render", str(tmp_path / "invalid.json"), "--json"))
    assert doc["error"]["field"] == "question" and doc["error"]["file"].endswith("invalid.json")
    assert any(p["path"] == "maps" for p in doc["error"]["problems"])


def test_debug_shows_the_trace(tmp_path):
    r = run("render", str(tmp_path / "missing.json"), "--debug")
    assert r.returncode == 1 and "Traceback" in r.stderr


def test_doctor_reports_and_never_calls_a_model(tmp_path):
    doc = envelope(run("doctor", "--json"))
    ids = {c["id"] for c in doc["result"]["checks"]}
    assert {"python", "write_access", "provider_anthropic", "complete_cmd", "mcp"} <= ids
    assert doc["result"]["ready"]["deterministic"] is True
    assert doc["result"]["ready"]["draft_with_anthropic"] is False  # keys scrubbed
    ok = envelope(run("doctor", "--complete-cmd", f"{sys.executable} -c pass", "--json"))
    assert ok["result"]["ready"]["draft_with_complete_cmd"] is True
    bad = run("doctor", "--complete-cmd", "no-such-program-here x")
    assert bad.returncode == 3 and "not found on PATH" in bad.stdout


def test_json_mode_keeps_data_commands_stable():
    for cmd in ("manifest", "templates", "roles", "discover"):
        doc = envelope(run(cmd, "--json"))
        assert doc["ok"] and doc["result"]
    # without --json, piped output stays plain JSON for older scripts
    assert json.loads(run("templates").stdout)[0]["id"]


def test_json_flag_works_before_or_after_the_command():
    a = envelope(run("--json", "roles"))
    b = envelope(run("roles", "--json"))
    assert a["result"] == b["result"]


def test_no_color_and_non_tty_output_is_plain(tmp_path):
    r = run("doctor", env={"NO_COLOR": "1"})
    assert "\x1b[" not in r.stdout + r.stderr
    r = run("render", str(tmp_path / "missing.json"))
    assert "\x1b[" not in r.stderr  # stderr is a pipe here: no colour


def test_version():
    from decisioncraft.help import VERSION

    r = run("--version")
    assert r.returncode == 0 and VERSION in r.stdout


def test_library_functions_match_the_cli(tmp_path):
    import decisioncraft as dc

    names = [e["id"] for e in dc.example_names()]
    assert names == ["business", "technical", "engineering", "medical"]
    ex = dc.example("business")
    assert ex["material"] and ex["reviews"] and dc.summary(ex["model"])["notes"] > 0
    files = dc.starter("customer-journey", "", "How do we cut missed pickups?", roles=["voice"])
    assert set(files) == {"model.json", "material/README.txt"}
    with pytest.raises(ValueError):
        dc.example("cooking")
    assert "checks" in dc.doctor(directory=str(tmp_path))
