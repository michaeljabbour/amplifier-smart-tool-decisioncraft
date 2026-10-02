#!/usr/bin/env python3
"""Check that a local session gives an agent responses without a downloaded file."""

from __future__ import annotations
import json
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import decisioncraft as dc
from playwright.sync_api import sync_playwright


def main():
    model = dc.new(
        "opportunity-tree", "Local review check", "Which trial should we run?"
    )
    model["maps"][0]["root"].update(id="goal", title="Choose a trial", children=[dict(id="trial", title="Try a two-week trial", text="", children=[])])
    model["notes"] = [
        dict(
            id="Q1",
            role="owner",
            anchor="goal",
            title="Choose a trial",
            question="Which trial should we run?",
            urgency="must",
            evidence=["E1"],
        ),
        dict(
            id="Q2",
            role="engineer",
            anchor="goal",
            title="Choose an owner",
            question="Who should make the final call?",
            urgency="should",
        ),
    ]
    model["sources"] = [
        dict(id="note", title="Supporting note", kind="document", ref="note.md")
    ]
    model["evidence"] = [
        dict(id="E1", source="note", kind="quote", text="Try one small decision first.")
    ]
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
        root = Path(folder)
        (root / "note.md").write_text("Try one small decision first.")
        active = dc.session(
            model, root / "session", source_root=root, prepared_by="AI assistant"
        )
        browser = pw.chromium.launch()
        try:
            page = browser.new_page()
            errors, downloads, requests = [], [], []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.on("download", lambda item: downloads.append(item))
            page.on("request", lambda request: requests.append(request.url))
            page.goto(active.url)
            page.get_by_role("button", name="Answer questions", exact=True).click()
            assert "From: AI assistant" in page.inner_text("#panel")
            page.get_by_role("button", name="See supporting sources", exact=True).click()
            with page.expect_popup() as source:
                page.get_by_role("link", name="Open source", exact=True).click()
            source.value.wait_for_load_state()
            assert "Try one small decision first." in source.value.inner_text("body")
            source.value.close()
            page.get_by_role("button", name="Back to the question", exact=True).click()
            assert not page.locator("#panel details").count()
            answer = "Try one decision and ask for clear reasons."
            original_check = active._check

            def slow_check(review):
                time.sleep(0.15)
                return original_check(review)

            active._check = slow_check
            with page.expect_request(lambda request: request.url.endswith("/answers")):
                page.locator("[data-answer=Q1]").fill("An unfinished first answer.")
            page.locator("[data-answer=Q1]").fill(answer)
            # No pause before moving on: the latest answer must arrive before navigation.
            page.get_by_role("button", name="Save and continue", exact=True).click()
            page.get_by_role(
                "heading", name="Who should make the final call?", exact=True
            ).wait_for()
            assert active.status()["review"]["answers"]["Q1"]["answer"] == answer
            page.locator("[data-answer=Q2]").fill("Human operator")
            page.get_by_role("button", name="Check my answers", exact=True).click()
            page.reload()
            page.get_by_role("button", name="Check my answers", exact=True).click()
            assert answer in page.inner_text("#panel")
            page.locator("#top").get_by_role(
                "button", name="Finish review", exact=True
            ).click()
            page.get_by_role(
                "heading", name="Your answers are ready for your agent"
            ).wait_for()
            assert active.wait(1)
            review = json.loads(active.review_file.read_text())
            assert review["answers"]["Q1"]["answer"] == answer
            assert review["answers"]["Q2"]["answer"] == "Human operator"
            assert active.status()["state"] == "finished"
            assert active.status()["handoff"]["review"]["answers"]["Q1"]["answer"] == answer
            assert (active.directory / "handoff.json").exists()
            page.get_by_role("button", name="See next steps", exact=True).click()
            assert "What still needs defining" in page.inner_text("#panel")
            page.locator("#tsave").click()
            assert not downloads and not errors
            assert all(url.startswith(active.origin) for url in requests)
            # A later edit reopens the review; an earlier completion is not reused.
            page.locator('[data-review-at="0"]').click()
            page.locator("[data-answer=Q1]").fill("A different trial.")
            page.get_by_role("button", name="Save and continue", exact=True).click()
            page.get_by_role(
                "heading", name="Who should make the final call?", exact=True
            ).wait_for()
            assert active.status()["state"] == "open"
            assert not active.status()["finished_at"]
            assert not active.wait(0)
            active.close_on_finish = True
            page.goto(active.url)
            page.get_by_role("button", name="Check my answers", exact=True).click()
            page.locator("#top").get_by_role(
                "button", name="Finish review", exact=True
            ).click()
            page.locator("#tsave").click()
            assert not page.locator("[data-review-at]").count()
            assert page.locator("#tsave").is_enabled()
        finally:
            browser.close()
            active.close()
    print(
        "ok automatic saving, source link, reopen, finish and agent receipt; no download or outside request"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
