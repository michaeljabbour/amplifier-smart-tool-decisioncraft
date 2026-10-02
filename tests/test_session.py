"""Local review receipts, validation and source access, with no model calls."""

import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest
import decisioncraft as dc
from decisioncraft.review import blank_review


@pytest.fixture
def model():
    m = dc.new("opportunity-tree", "Local review", "Which trial should we run?")
    m["maps"][0]["root"].update(id="goal", title="Choose a trial",
                                children=[dict(id="pilot", title="Run a two-week pilot", text="", children=[])])
    m["notes"] = [
        dict(
            id="Q1",
            role="owner",
            anchor="goal",
            title="Choose a trial",
            question="Which trial should we run?",
            urgency="must",
        )
    ]
    return m


def post(active, review, version=0, path="answers", origin=None):
    request = Request(
        active.origin + active.base + "/" + path,
        data=json.dumps(dict(review=review, version=version)).encode(),
        headers={"Content-Type": "application/json", "Origin": origin or active.origin},
    )
    return json.load(urlopen(request, timeout=3))


def test_autosave_and_finish_leave_an_agent_readable_receipt(tmp_path, model):
    active = dc.session(model, tmp_path / "review")
    try:
        review = blank_review(model)
        review["answers"] = {"Q1": {"answer": "Try one small decision first."}}
        assert post(active, review)["version"] == 1
        assert (
            json.loads(active.review_file.read_text())["answers"] == review["answers"]
        )
        assert active.status()["state"] == "open"
        assert not active.wait(0)
        post(active, review, 1, "finish")
        assert active.wait(1)
        receipt = json.loads(active.session_file.read_text())
        assert receipt["state"] == "finished" and receipt["finished_at"]
        assert dc.merge([active.status()["review"]], model)["stale_reviews"] == []
    finally:
        active.close()
    assert json.loads(active.session_file.read_text())["state"] == "closed"


def test_other_origins_bad_reviews_and_conflicts_do_not_overwrite_answers(
    tmp_path, model
):
    active = dc.session(model, tmp_path / "review")
    try:
        review = blank_review(model)
        for invalid, origin, code in [
            (review, "http://example.com", 403),
            ({**review, "model_fingerprint": "wrong"}, None, 400),
            ({**review, "answers": {"unknown": {"answer": "No"}}}, None, 400),
        ]:
            with pytest.raises(HTTPError) as error:
                post(active, invalid, origin=origin)
            assert error.value.code == code
        review["answers"] = {"Q1": {"answer": "Keep this answer."}}
        post(active, review)
        with pytest.raises(HTTPError) as error:
            post(active, blank_review(model))
        assert error.value.code == 409
        assert active.status()["review"]["answers"] == review["answers"]
    finally:
        active.close()


def test_sources_are_limited_to_the_requested_folder(tmp_path, model):
    root = tmp_path / "sources"
    root.mkdir()
    (root / "note.md").write_text("This is the supporting note.")
    (tmp_path / "private.md").write_text("Outside the allowed folder.")
    model["sources"] = [
        dict(id="note", title="Supporting note", ref="note.md"),
        dict(id="outside", title="Outside", ref="../private.md"),
    ]
    active = dc.session(model, tmp_path / "review", source_root=root)
    try:
        data = urlopen(active.origin + active.base + "/source/note").read().decode()
        assert data == "This is the supporting note."
        with pytest.raises(HTTPError) as error:
            urlopen(active.origin + active.base + "/source/outside")
        assert error.value.code == 404
        request = Request(active.url, headers={"Host": "example.com"})
        with pytest.raises(HTTPError) as error:
            urlopen(request)
        assert error.value.code == 403
        (root / "note.md").unlink()
        (root / "note.md").symlink_to(tmp_path / "private.md")
        with pytest.raises(HTTPError) as error:
            urlopen(active.origin + active.base + "/source/note")
        assert error.value.code == 403
    finally:
        active.close()


def test_existing_session_is_not_overwritten(tmp_path, model):
    active = dc.session(model, tmp_path / "review")
    try:
        with pytest.raises(ValueError, match="already exists"):
            dc.session(model, tmp_path / "review")
    finally:
        active.close()


def test_waiting_cli_returns_the_review_to_its_host(tmp_path, model):
    model_file = tmp_path / "model.json"
    model_file.write_text(json.dumps(model))
    directory = tmp_path / "session"
    cli = Path(__file__).resolve().parent.parent / "bin" / "decisioncraft.py"
    process = subprocess.Popen(
        [
            sys.executable,
            str(cli),
            "session",
            str(model_file),
            "--dir",
            str(directory),
            "--until-finished",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        for _ in range(60):
            if (directory / "session.json").exists():
                break
            if process.poll() is not None:
                raise AssertionError(process.communicate()[1])
            time.sleep(0.05)
        receipt = json.loads((directory / "session.json").read_text())
        assert process.poll() is None
        review = blank_review(model)
        review["answers"] = {"Q1": {"answer": "Let the human operator decide."}}
        origin = receipt["url"].split("/review/")[0]
        request = Request(
            receipt["url"].rstrip("/") + "/finish",
            data=json.dumps(dict(version=0, review=review)).encode(),
            headers={"Content-Type": "application/json", "Origin": origin},
        )
        with urlopen(request, timeout=3) as response:
            assert response.status == 200
        stdout, stderr = process.communicate(timeout=5)
        assert process.returncode == 0, stderr
        decoder = json.JSONDecoder()
        first, end = decoder.raw_decode(stdout)
        final, _ = decoder.raw_decode(stdout[end:].lstrip())
        assert first["state"] == "open" and final["state"] == "finished"
        assert final["review"]["answers"] == review["answers"]
        assert json.loads((directory / "session.json").read_text())["finished_at"]
    finally:
        if process.poll() is None:
            process.terminate()
            process.communicate(timeout=5)
