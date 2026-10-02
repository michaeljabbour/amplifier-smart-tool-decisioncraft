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
Plus: display options from the View menu, and on maps with a plan: the Today / Planned /
What changes switch is text-labelled, What changes marks boxes with ribbons and counts,
Side by side keeps both panes on one pan and zoom, and nothing overlaps any text at about
30%, 60%, 100% and 150% zoom.

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
  const hit = (a, b) => a.width && b.width && a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1;
  let hits = 0;
  for (const w of ['#world', '#world2']) {
    const boxes = [...document.querySelectorAll(w + ' .box')].map(r);
    const notes = [...document.querySelectorAll(w + ' .notecard, ' + w + ' .morenotes')].map(r);
    const words = [...document.querySelectorAll(w + ' .label, ' + w + ' .lanehead, ' + w + ' .steplabel, ' + w + ' .modebar, ' + w + ' .maptitle, ' + w + ' .mapintro')].map(r);
    for (let i = 0; i < boxes.length; i++) for (let j = i + 1; j < boxes.length; j++) if (hit(boxes[i], boxes[j])) hits++;
    for (const n of notes) for (const b of boxes) if (hit(n, b)) hits++;
    for (const t of words) for (const b of [...boxes, ...notes]) if (hit(t, b)) hits++;
  }
  return hits;
}"""
SCALE = "parseFloat((document.getElementById('world').style.transform.match(/scale\\(([^)]+)\\)/) || [0, 1])[1])"
TRANSFORM = "document.getElementById('world').style.transform"


def view_toggle(page, name):
    """Turn a display option on or off from the View menu; returns its new state."""
    page.locator("#top").get_by_role("button", name="View ▾").click()
    item = page.get_by_role("menuitemcheckbox", name=name, exact=True)
    item.click()
    page.wait_for_timeout(250)
    return item


def zoom_to(page, target):
    """Use the visible zoom buttons until the scale is within a step of the target."""
    for _ in range(14):
        z = page.evaluate(SCALE)
        if z < target / 1.12:
            page.get_by_role("button", name="+ Zoom in").click()
        elif z > target * 1.12:
            page.get_by_role("button", name="− Zoom out").click()
        else:
            break
    return page.evaluate(SCALE)


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

    # extras: details, notes on the map, each view
    try:
        page.locator("#top").get_by_role("button", name="View ▾").click()
        has_tech = page.get_by_role("menuitemcheckbox", name="Technical names on the map", exact=True).count()
        page.keyboard.press("Escape")
        if has_tech:
            item = view_toggle(page, "Technical names on the map")
            assert page.locator("#world .techname").count() > 0, "no technical names on the map"
        view_toggle(page, "Notes on the map")
        views = page.locator("#story ol.maps > li > .view").count()
        for i in range(views):
            page.locator("#story ol.maps > li > .view").nth(i).click()
            page.wait_for_timeout(250)
            hits = page.evaluate(OVERLAP_JS)
            if hits:
                problems.append(f"view {i + 1}: {hits} overlaps with notes on the map")
            shot(f"7-view{i + 1}-notes-on-map")
        view_toggle(page, "Notes on the map")
        done.append("display options, notes on the map and every view")
    except Exception as e:  # noqa: BLE001
        problems.append(f"extras: {e}")

    # a journey's own walk-through, lane panels, and chain extras
    try:
        starts = page.locator("#story [data-startj]")
        views = page.locator("#story ol.maps > li > .view")
        for i in range(views.count()):
            if starts.count():
                break
            views.nth(i).click(); page.wait_for_timeout(200)
        if starts.count():
            starts.first.click(); page.wait_for_timeout(250)
            text = page.inner_text("#walk")
            assert "step 1 of" in text.lower(), text[:80]
            click_text("Next", "#walk")
            assert "step 2 of" in page.inner_text("#walk").lower()
            assert page.is_visible("#panel"), "the step did not open on the right"
            shot("9-journey-walk")
            click_text("End the walk-through", "#walk")
            click_text("Close", "#panel")
            lane = page.locator("#world .lanehead[role=button]")
            if lane.count():
                page.get_by_role("button", name="Fit to screen").click()
                lane.first.click(); page.wait_for_timeout(200)
                assert page.is_visible("#panel"), "a lane header did not open"
                click_text("Close", "#panel")
            done.append("walked a journey step by step and opened a lane")
        for i in range(views.count()):
            views.nth(i).click(); page.wait_for_timeout(200)
            if page.locator("#world .band, #world .beforecell").count():
                extra = page.evaluate("""() => { const r = e => e.getBoundingClientRect(); let hits = 0;
                  const boxes = [...document.querySelectorAll('#world .box:not(.band)')].map(r);
                  for (const e of document.querySelectorAll('#world .band, #world .beforecell')) { const a = r(e);
                    for (const b of boxes) if (a.left < b.right - 1 && a.right > b.left + 1 && a.top < b.bottom - 1 && a.bottom > b.top + 1) hits++; }
                  return hits; }""")
                if extra:
                    problems.append(f"view {i + 1}: bands or before notes overlap {extra} boxes")
                shot(f"9-view{i + 1}-chain-extras")
    except Exception as e:  # noqa: BLE001
        problems.append(f"journey walk and lanes: {e}")

    # maps with a plan: the switch, What changes, Side by side, zoom levels
    try:
        views = page.locator("#story ol.maps > li > .view").count()
        planned = 0
        for i in range(views):
            page.locator("#story ol.maps > li > .view").nth(i).click()
            page.wait_for_timeout(200)
            if not page.locator("#top .mode-seg").count():
                continue
            planned += 1
            top = page.locator("#top")
            for label in ("Today", "Planned", "What changes", "Side by side"):
                b = top.get_by_role("button", name=label, exact=True)
                assert b.count() == 1 and b.inner_text().strip() == label, f"switch button {label!r} is not a labelled button"
            for label in ("Today", "Planned"):
                top.get_by_role("button", name=label, exact=True).click()
                page.wait_for_timeout(200)
                assert not page.locator("#world .box > .ribbon").count(), f"{label} should not mark changes"
                hits = page.evaluate(OVERLAP_JS)
                if hits:
                    problems.append(f"view {i + 1} {label}: {hits} overlaps")
                shot(f"8-view{i + 1}-{label.lower()}")
            top.get_by_role("button", name="What changes", exact=True).click()
            page.wait_for_timeout(250)
            ribbons = page.locator("#world .box > .ribbon").count()
            counts = page.locator("#world .modebar .ribbon").count()
            assert ribbons > 0 and counts > 0, f"What changes shows {ribbons} ribbons and {counts} counts"
            assert page.locator("#story .changes .view").count() == ribbons, "the left list does not list every change"
            shot(f"8-view{i + 1}-what-changes")
            for target in (0.3, 0.6, 1.0, 1.5):
                z = zoom_to(page, target)
                hits = page.evaluate(OVERLAP_JS)
                if hits:
                    problems.append(f"view {i + 1} What changes at {z:.2f}: {hits} overlaps")
            page.get_by_role("button", name="Fit to screen").click()
            top.get_by_role("button", name="Side by side", exact=True).click()
            page.wait_for_timeout(300)
            assert page.evaluate("document.body.classList.contains('sbs')"), "side by side did not open"
            assert page.is_visible("#viewport2"), "the right pane is not visible"
            same = "document.getElementById('world').style.transform === document.getElementById('world2').style.transform"
            assert page.evaluate(same), "panes start out of step"
            if page.is_visible("#sbsbar"):
                # journey maps: one journey, readable, only what changes by default
                z = page.evaluate(SCALE)
                assert z >= 0.54, f"side by side opens at {z:.2f}, too small to read"
                rows_shown = page.evaluate("new Set([...document.querySelectorAll('#world .box')].map(b => b.dataset.row)).size")
                assert rows_shown == 1, f"side by side shows {rows_shown} journeys"
                assert page.locator("#sbs-only").is_checked(), "Only what changes is not on by default"
                few = page.locator("#world .box").count()
                page.locator("#sbs-only").uncheck(); page.wait_for_timeout(250)
                assert page.locator("#world .box").count() >= few, "turning off Only what changes hid steps"
                page.locator("#sbs-only").check(); page.wait_for_timeout(250)
                assert page.locator("#sbs-journey option").count() >= 1
                assert page.locator("#world .ghostlabel").count() == 0 or page.evaluate(
                    "[...document.querySelectorAll('#world .chg-new .ghostlabel')].every(g => g.getBoundingClientRect().height < 40)"), "placeholders are not slim"
            page.get_by_role("button", name="+ Zoom in").click()
            page.mouse.move(700, 600); page.mouse.down(); page.mouse.move(640, 520); page.mouse.up()
            assert page.evaluate(same), "panes fell out of step after zoom and drag"
            left = page.locator("#world .box").count(); right = page.locator("#world2 .box").count()
            assert left == right, f"panes differ: {left} and {right} boxes"
            hits = page.evaluate(OVERLAP_JS)
            if hits:
                problems.append(f"view {i + 1} side by side: {hits} overlaps")
            shot(f"8-view{i + 1}-side-by-side")
            top.get_by_role("button", name="Side by side", exact=True).click()
            page.wait_for_timeout(200)
        if planned:
            done.append(f"Today, Planned, What changes and Side by side on {planned} map(s)")
    except Exception as e:  # noqa: BLE001
        problems.append(f"plan views: {e}")

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
