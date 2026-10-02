#!/usr/bin/env python3
"""Check timeline order, comparisons, named connections and panel space in a browser."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
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
        page.get_by_role("button", name="All connections", exact=True).click()
        assert page.locator(".connection.feedback").is_visible()
        page.get_by_role("button", name="Explore the map", exact=True).click()
        page.locator("[data-map='1']").click()
        current = page.get_by_role("button", name="Current: Download a file", exact=True)
        proposed = page.get_by_role("button", name="Proposed: Answers reach the agent", exact=True)
        assert current.bounding_box()["x"] < proposed.bounding_box()["x"]
        page.locator("#view-version").select_option("today")
        assert page.get_by_role("button", name="Download a file", exact=True).is_visible()
        assert not page.get_by_role("button", name="Answers reach the agent", exact=True).count()
        page.locator("#view-version").select_option("planned")
        assert page.get_by_role("button", name="Answers reach the agent", exact=True).is_visible()
        assert not page.get_by_role("button", name="Download a file", exact=True).count()
        page.set_viewport_size({"width":1024,"height":768})
        page.get_by_role("button", name="Answers reach the agent", exact=True).click()
        assert not page.locator("#story").is_visible()
        navigation = page.get_by_role("button", name="Left navigation", exact=True)
        assert navigation.get_attribute("aria-pressed") == "false"
        navigation.click()
        assert page.locator("#story").is_visible()
        navigation.click()
        assert not page.locator("#story").is_visible()
        rect = page.get_by_role("button", name="Answers reach the agent", exact=True).bounding_box()
        assert rect["x"] + rect["width"] <= page.locator("#panel").bounding_box()["x"] + 1
        assert not errors, errors
        browser.close()
    print("ok distinct timeline and comparison, named feedback, focus and panel space")


if __name__ == "__main__":
    main()
