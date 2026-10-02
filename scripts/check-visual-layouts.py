#!/usr/bin/env python3
"""Check timeline order, comparisons, named connections and panel space in a browser."""
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
import decisioncraft as dc
from playwright.sync_api import sync_playwright


def main():
    model = dc.new("customer-journey", "Review a choice", "What should we try?")
    model["maps"][0]["journeys"] = [dict(id="person", title="A person reviews a choice",
        summary="A fictional example.", steps=[dict(id="read", lane="notice", text="Read the choice"),
        dict(id="answer", lane="use", text="Give a view"), dict(id="finish", lane="stay", text="Finish the review")])]
    chain = dc.new("decision-chain", "", "Q?")["maps"][0]
    chain.update(id="comparison", stages=[dict(id="review-stage", label="Review", verb="leads to",
        items=[dict(id="old", title="Download a file", when="today"),
               dict(id="new", title="Answers reach the agent", when="planned")])])
    model["maps"].append(chain)
    model["links"] = [dict(id="L1", **{"from": "finish", "to": "answer"},
                           label="Return to change a view", kind="feedback")]
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        path = Path(tmp) / "visuals.html"
        path.write_text(dc.render(model))
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width":1440, "height":1000})
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(path.as_uri())
        page.get_by_role("button", name="Got it", exact=True).click()
        cards = page.locator(".customer-step").all()
        assert len(cards) == 3
        xs = [card.bounding_box()["x"] for card in cards]
        assert xs == sorted(xs) and len(set(xs)) == 3
        assert page.locator("path.customer-flow").count() == 4  # two paths and two arrows
        assert not page.locator(".connection").is_visible()
        cards[1].click()
        assert page.locator(".connection.feedback").is_visible()
        assert "Return to change a view" in page.inner_text("#panel")
        box, panel, nav = cards[1].bounding_box(), page.locator("#panel").bounding_box(), page.locator("#story").bounding_box()
        assert box["x"] >= nav["x"] + nav["width"] - 1
        assert box["x"] + box["width"] <= panel["x"] + 1
        page.locator("[data-connection-to=finish]").click()
        assert "Finish the review" in page.inner_text("#ptitle")
        page.locator("#pclose").click()
        page.locator("#top").get_by_role("button", name="View ▾").click()
        page.get_by_role("menuitemcheckbox", name="All connections", exact=True).click()
        assert page.locator(".connection.feedback").is_visible()
        page.locator("[data-map='1']").click()
        top = page.locator("#top")
        # What changes: one map, each box says what the plan does to it.
        gone = page.get_by_role("button", name="Goes away: Download a file", exact=True)
        new = page.get_by_role("button", name="New: Answers reach the agent", exact=True)
        assert gone.is_visible() and new.is_visible()
        bar = page.inner_text(".modebar").lower()
        assert "1 new" in bar and "1 goes away" in bar, bar
        top.get_by_role("button", name="Today", exact=True).click()
        assert page.get_by_role("button", name="Download a file", exact=True).is_visible()
        assert not page.get_by_role("button", name="Answers reach the agent", exact=True).count()
        top.get_by_role("button", name="Planned", exact=True).click()
        assert page.get_by_role("button", name="Answers reach the agent", exact=True).is_visible()
        assert not page.get_by_role("button", name="Download a file", exact=True).count()
        top.get_by_role("button", name="Side by side", exact=True).click()
        assert page.locator("#viewport2").is_visible()
        top.get_by_role("button", name="Side by side", exact=True).click()
        top.get_by_role("button", name="Planned", exact=True).click()
        page.set_viewport_size({"width":1024,"height":768})
        page.get_by_role("button", name="Answers reach the agent", exact=True).click()
        assert not page.locator("#story").is_visible()

        def nav_state():
            top.get_by_role("button", name="View ▾").click()
            it = page.get_by_role("menuitemcheckbox", name="List on the left", exact=True)
            v = it.get_attribute("aria-checked")
            return it, v

        it, v = nav_state()
        assert v == "false"
        it.click()
        assert page.locator("#story").is_visible()
        it, v = nav_state()
        it.click()
        assert not page.locator("#story").is_visible()
        rect = page.get_by_role("button", name="Answers reach the agent", exact=True).bounding_box()
        assert rect["x"] + rect["width"] <= page.locator("#panel").bounding_box()["x"] + 1
        assert not errors, errors

        # Phones: the top bar fits, the list starts hidden, and the walk-through stays reachable.
        phone = browser.new_page(viewport={"width":375, "height":812})
        for example in ("business", "personal-car", "engineering"):
            phone.goto((ROOT / "examples" / example / "canvas.html").as_uri())
            phone.evaluate("localStorage.clear()")
            phone.reload()
            phone.wait_for_timeout(400)
            for b in phone.locator("#top button").all():
                if b.is_visible():
                    r = b.bounding_box()
                    assert r["x"] >= 0 and r["x"] + r["width"] <= 376, (example, b.inner_text(), r)
            assert not phone.locator("#story").is_visible(), example
            phone.locator("#top").get_by_role("button", name="Tools ▾").click()
            phone.get_by_role("menuitem", name="Walk me through it").first.click()
            nxt = phone.locator("#walk").get_by_role("button", name="Next", exact=True)
            r = nxt.bounding_box()
            assert r and r["x"] + r["width"] <= 376, (example, r)
            nxt.click()
        phone.close()
        browser.close()
    print("ok distinct timeline, What changes with Today, Planned and Side by side, named feedback, focus and panel space, phone layout")


if __name__ == "__main__":
    main()
