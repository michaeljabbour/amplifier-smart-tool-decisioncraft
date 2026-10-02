#!/usr/bin/env python3
"""Open rendered canvases in headless Chromium and check them like a first-time user.

For each HTML file it checks: no console or page errors, no network requests, a single
top bar, and no overlapping boxes or notes. Then it runs five tasks a
first-time user should manage using only what is visible on screen (clicks on labelled
buttons, no keyboard shortcuts):

  1. Take the walk-through to step 3.
  2. Open a journey or stage from the list on the left.
  3. Open a box, read its notes and answer a question there.
  4. Review the questions, copy them, and save with the visible button.
  5. Zoom in, zoom out and fit with the zoom buttons.
Plus: show extra box details from the bar, and switch Today/Planned where offered.

Needs Playwright (`pip install playwright && playwright install chromium`); a development
check, not a runtime dependency.

    python3 scripts/check-canvas.py examples/*/canvas.html [--shots DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

OVERLAP_JS = """
() => {
  const r = el => el.getBoundingClientRect();
  const boxes = [...document.querySelectorAll('#world .box')].map(r);
  const notes = [...document.querySelectorAll('#world .notecard, #world .morenotes')].map(r);
  let hits = 0;
  const cards = boxes;
  for (let i = 0; i < cards.length; i++) for (let j = i + 1; j < cards.length; j++) {
    const a = cards[i], b = cards[j];
    if (a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1) hits++;
  }
  for (const n of notes) for (const b of boxes)
    if (n.left < b.right - 1 && n.right > b.left + 1 && n.top < b.bottom - 1 && n.bottom > b.top + 1) hits++;
  return hits;
}"""
TRANSFORM = "document.getElementById('world').style.transform"


def check(page, path: Path, shots: Path | None) -> tuple[list[str], list[str]]:
    problems: list[str] = []
    done: list[str] = []
    errors: list[str] = []
    requests: list[str] = []
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("request", lambda r: requests.append(r.url) if not r.url.startswith(("file:", "data:", "blob:")) else None)
    page.goto(path.resolve().as_uri())
    page.wait_for_timeout(400)
    name = path.parent.name + ("" if path.name == "canvas.html" else "-" + path.stem)

    def shot(tag):
        if shots:
            page.screenshot(path=str(shots / f"{name}-{tag}.png"))

    def click_text(text, within="body"):
        loc = page.locator(within).get_by_role("button", name=text).first
        loc.click()
        page.wait_for_timeout(200)

    shot("0-first-visit")
    if page.is_visible("#hint"):
        click_text("Got it")
    top_h = page.evaluate("document.getElementById('top').getBoundingClientRect().height")
    if top_h > 56:
        problems.append(f"top bar is {top_h:.0f}px tall")
    shot("1-start")
    hits = page.evaluate(OVERLAP_JS)
    if hits:
        problems.append(f"initial view: {hits} box or note overlaps")

    # 1. walk-through
    try:
        click_text("Tools", "#top")
        page.get_by_role("menuitem", name="Walk me through it").click()
        click_text("Next", "#walk")
        click_text("Next", "#walk")
        text = page.inner_text("#walk")
        if "step 3 of" not in text.lower():
            raise AssertionError(text[:60])
        shot("2-walk-step3")
        click_text("End the walk-through", "#walk")
        done.append("walk-through to step 3")
    except Exception as e:  # noqa: BLE001
        problems.append(f"task 1 (walk-through): {e}")

    # 2. open a journey or stage from the list
    try:
        click_text("Explore the map", "#story")
        item = page.locator("#story .sub .view").nth(1)
        label = item.inner_text().split("\n")[0]
        before = page.evaluate(TRANSFORM)
        item.click()
        page.wait_for_timeout(250)
        if page.evaluate(TRANSFORM) == before:
            raise AssertionError("the map did not move")
        shot("3-from-list")
        done.append(f"opened '{label}' from the list")
    except Exception as e:  # noqa: BLE001
        problems.append(f"task 2 (list): {e}")

    # 3. open a box with notes and answer a question in the panel
    try:
        page.get_by_role("button", name="Fit to screen").click()
        boxes = page.locator("#world .box[role=button]:has(.notebadge)")
        box = None
        for i in range(boxes.count()):
            bb = boxes.nth(i).bounding_box()
            if bb and bb["y"] > 70 and bb["y"] + 20 < 880 and 330 < bb["x"] < 1300:
                box = boxes.nth(i)
                break
        if box is None:
            raise AssertionError("no box with notes is on screen after Fit to screen")
        box.click()
        page.wait_for_timeout(200)
        if not page.is_visible("#panel"):
            raise AssertionError("panel did not open")
        answer = page.locator("#panel [data-answer]").first
        answer.fill("Try one small change and check the result.")
        if answer.input_value() != "Try one small change and check the result.":
            raise AssertionError("answer not recorded")
        shot("4-box-detail")
        click_text("Close", "#panel")
        done.append("answered a question from a box's notes")
    except Exception as e:  # noqa: BLE001
        problems.append(f"task 3 (box and answer): {e}")

    # 4. questions, then copy through Share my answers
    try:
        page.locator("#story").get_by_role("button", name="1. Understand the decision").click()
        page.get_by_role("button", name="See all questions", exact=True).click()
        page.wait_for_timeout(200)
        shot("5-questions")
        page.locator("#top").get_by_role("button", name="Tools").click()
        page.get_by_role("menuitem", name="Copy the questions as a list").click()
        page.wait_for_timeout(300)
        if "Copied" not in page.inner_text("#toast"):
            raise AssertionError("no confirmation")
        with page.expect_download(timeout=3000) as dl:
            page.locator("#top").get_by_role("button", name="Save my answers", exact=True).click()
        if not dl.value.suggested_filename.endswith(".json"):
            raise AssertionError("download is not a review file")
        if "Send your saved answers" not in page.inner_text("#panel"):
            raise AssertionError("no next step after saving")
        click_text("Close", "#panel")
        done.append("copied the questions and saved answers with the visible button")
    except Exception as e:  # noqa: BLE001
        problems.append(f"task 4 (questions and share): {e}")

    # 5. zoom buttons
    try:
        t0 = page.evaluate(TRANSFORM)
        page.get_by_role("button", name="+ Zoom in").click()
        t1 = page.evaluate(TRANSFORM)
        page.get_by_role("button", name="− Zoom out").click()
        page.get_by_role("button", name="− Zoom out").click()
        t2 = page.evaluate(TRANSFORM)
        page.get_by_role("button", name="Fit to screen").click()
        if len({t0, t1, t2}) < 3:
            raise AssertionError("zoom did not change")
        for _ in range(10):
            page.get_by_role("button", name="− Zoom out").click()
        shot("6-most-zoomed-out")
        hits = page.evaluate(OVERLAP_JS)
        if hits:
            problems.append(f"zoomed out: {hits} box or note overlaps")
        page.get_by_role("button", name="Fit to screen").click()
        done.append("zoomed in, out and fitted with the buttons")
    except Exception as e:  # noqa: BLE001
        problems.append(f"task 5 (zoom): {e}")

    # extras: details, notes on the map, today/planned, each view
    try:
        detail_toggle = page.get_by_role("button", name="Extra details on the map", exact=True)
        if detail_toggle.count():
            detail_toggle.click()
            assert detail_toggle.get_attribute("aria-pressed") == "true"
            assert page.locator("#world .techname").count() > 0
        page.get_by_role("button", name="Notes beside boxes", exact=True).click()
        page.wait_for_timeout(250)
        views = page.locator("#story > ol > li > .view").count()
        for i in range(views):
            page.locator("#story > ol > li > .view").nth(i).click()
            page.wait_for_timeout(250)
            hits = page.evaluate(OVERLAP_JS)
            if hits:
                problems.append(f"view {i + 1}: {hits} box or note overlaps with notes on the map")
            shot(f"7-view{i + 1}-notes-on-map")
            if page.locator("#story [data-mode=today]").count():
                page.locator("#story [data-mode=today]").click()
                page.wait_for_timeout(200)
                shot(f"7-view{i + 1}-today")
                page.locator("#story [data-mode=planned]").click()
        page.get_by_role("button", name="Notes beside boxes", exact=True).click()
        done.append("extra details, notes on the map and every view")
    except Exception as e:  # noqa: BLE001
        problems.append(f"extras: {e}")

    if errors:
        problems += [f"console: {e}" for e in errors[:5]]
    if requests:
        problems += [f"network request: {u}" for u in requests[:5]]
    return problems, done


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--shots")
    args = ap.parse_args()
    from playwright.sync_api import sync_playwright

    shots = Path(args.shots) if args.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    failed = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for f in args.files:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True)
            page = ctx.new_page()
            problems, done = check(page, Path(f), shots)
            ctx.close()
            print(f"{'FAIL' if problems else 'ok  '} {f}  ({len(done)} tasks done)")
            for pr in problems:
                print(f"     {pr}")
            failed += bool(problems)
        browser.close()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
