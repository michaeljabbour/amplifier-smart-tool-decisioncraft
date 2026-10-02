#!/usr/bin/env python3
"""Record short, silent demo videos of each example canvas for the product page.

Drives every example the way a first-time reviewer would (walk-through; on a map with a
plan, Today, What changes, two changes walked through and Side by side; then open a box,
answer a question, open Questions to decide), records it in headless Chromium, and
converts the recording to H.264 MP4 with ffmpeg. Writes, per example:
  docs/images/<example>-demo.mp4 and docs/images/<example>-poster.png
Needs Playwright with Chromium, and ffmpeg on PATH. Development only.

    python3 scripts/record-demos.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
W, H = 1440, 900
HOLD = 4800   # each view stays on screen long enough to read (about 4-6 s)
STEP = 2600   # a shorter pause between clicks within one view


def hold(page, ms=HOLD):
    page.wait_for_timeout(ms)


def extras(page, name):
    """Scenes only some examples have: scoring and costs, notes on the map."""
    story, top = page.locator("#story"), page.locator("#top")
    if name == "personal-car":
        story.locator('[data-map="0"]').first.click(); page.get_by_role("button", name="Fit to screen").click(); hold(page)
        w = page.locator('[data-open="weights"]').first
        if w.count():
            w.click(); hold(page, STEP)
            sl = page.locator('#panel input[type=range]').first
            if sl.count():
                sl.focus(); [page.keyboard.press("ArrowRight") for _ in range(4)]; hold(page)
            close = page.locator("#panel").get_by_role("button", name="Close")
            if close.count():
                close.first.click()
        story.locator('[data-map="1"]').first.click(); page.get_by_role("button", name="Fit to screen").click(); hold(page)
        wi = page.locator('#world [data-choice^="whatif:"]').last
        if wi.count():
            wi.click(); hold(page)
    if name == "bike-hire-map":
        top.get_by_role("button", name="Planned", exact=True).click(); hold(page, STEP)
        top.get_by_role("button", name="View").click()
        page.locator("#menu").get_by_text("Notes on the map").first.click(); hold(page)
        top.get_by_role("button", name="View").click()
        page.locator("#menu").get_by_text("Notes on the map").first.click(); hold(page, STEP)


def drive(page, name=""):
    page.wait_for_timeout(STEP)
    if page.is_visible("#hint"):
        page.get_by_role("button", name="Got it").click()
    page.wait_for_timeout(500)
    page.locator("#top").get_by_role("button", name="Tools").click()
    page.get_by_role("menuitem", name="Walk me through it").click()
    for _ in range(3):
        page.wait_for_timeout(HOLD)
        page.locator("#walk").get_by_role("button", name="Next").click()
    page.wait_for_timeout(HOLD)
    page.locator("#walk").get_by_role("button", name="End the walk-through").click()
    # A map that holds a plan: What changes, two changes walked through, then side by side.
    planned = page.locator("#story ol.maps > li > .view:has(.viewtag)")
    if planned.count():
        planned.first.click()
        page.wait_for_timeout(STEP)
        top = page.locator("#top")
        top.get_by_role("button", name="Today", exact=True).click()
        page.wait_for_timeout(STEP)
        top.get_by_role("button", name="What changes", exact=True).click()
        page.wait_for_timeout(HOLD)
        page.locator("#story").get_by_role("button", name="▶ Walk through the changes").click()
        page.wait_for_timeout(HOLD)
        for _ in range(2):
            page.locator("#walk").get_by_role("button", name="Next").click()
            page.wait_for_timeout(HOLD)
        page.locator("#walk").get_by_role("button", name="End the walk-through").click()
        page.locator("#panel").get_by_role("button", name="Close").click()
        top.get_by_role("button", name="Side by side", exact=True).click()
        page.wait_for_timeout(HOLD)
        top.get_by_role("button", name="Side by side", exact=True).click()
        page.locator("#story ol.maps > li > .view").first.click()
        page.wait_for_timeout(600)
    extras(page, name)
    page.get_by_role("button", name="Fit to screen").click()
    page.wait_for_timeout(600)
    boxes = page.locator("#world .box[role=button]:has(.notebadge.must), #world .box[role=button]:has(.notebadge)")
    for i in range(boxes.count()):
        bb = boxes.nth(i).bounding_box()
        if bb and bb["y"] > 80 and bb["y"] + 40 < H - 20 and 340 < bb["x"] < 1250:
            boxes.nth(i).click()
            break
    page.wait_for_timeout(HOLD)
    agree = page.locator("#panel [data-choice=agree]").first
    if agree.count():
        agree.click()
    page.wait_for_timeout(STEP)
    page.locator("#story").get_by_role("button", name="1. Understand the decision").click()
    page.wait_for_timeout(HOLD)


def main() -> int:
    from playwright.sync_api import sync_playwright

    if not shutil.which("ffmpeg"):
        print("ffmpeg is needed on PATH", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    examples = sorted(p for p in (ROOT / "examples").iterdir() if (p / "canvas.html").is_file())
    with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
        browser = p.chromium.launch()
        for ex in examples:
            ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=tmp,
                                      record_video_size={"width": W, "height": H})
            page = ctx.new_page()
            page.goto((ex / "canvas.html").resolve().as_uri())
            page.wait_for_timeout(700)
            if page.is_visible("#hint"):
                page.get_by_role("button", name="Got it").click()
                page.wait_for_timeout(200)
            page.screenshot(path=str(OUT / f"{ex.name}-poster.png"))
            page.reload()
            drive(page, ex.name)
            raw = page.video.path()
            ctx.close()
            mp4 = OUT / f"{ex.name}-demo.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-an", "-c:v", "libx264",
                            "-pix_fmt", "yuv420p", "-crf", "36", "-preset", "slow", "-movflags", "+faststart",
                            "-vf", f"scale={W}:{H}", str(mp4)], check=True)
            print(f"wrote {mp4.relative_to(ROOT)} ({mp4.stat().st_size // 1024} KB)")
        # Ask the experts: a reviewer's rough note and the roles' replies (bakery, reviewed copy).
        ctx = browser.new_context(viewport={"width": W, "height": H}, record_video_dir=tmp,
                                  record_video_size={"width": W, "height": H})
        page = ctx.new_page()
        page.goto((ROOT / "examples/business/canvas-reviewed.html").resolve().as_uri())
        page.wait_for_timeout(900)
        if page.is_visible("#hint"):
            page.get_by_role("button", name="Got it").click()
        page.locator('#story [data-map="2"]').first.click(); hold(page, STEP)
        page.locator("#top").get_by_role("button", name="Planned", exact=True).click(); hold(page, STEP)
        box = page.locator('#world .box:has-text("Start with collection only")').first
        box.scroll_into_view_if_needed(); box.click(); hold(page, STEP)
        rn = page.locator("#panel").get_by_text("Reviewer notes").first
        if rn.count():
            rn.scroll_into_view_if_needed()
        hold(page); hold(page, STEP)
        page.screenshot(path=str(OUT / "ask-experts-poster.png"))
        raw = page.video.path()
        ctx.close()
        mp4 = OUT / "ask-experts-demo.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-an", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-crf", "36", "-preset", "slow", "-movflags", "+faststart",
                        "-vf", f"scale={W}:{H}", str(mp4)], check=True)
        print(f"wrote {mp4.relative_to(ROOT)} ({mp4.stat().st_size // 1024} KB)")
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
