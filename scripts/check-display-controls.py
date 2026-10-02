#!/usr/bin/env python3
"""Check display switches and word meanings with real browser interactions."""
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import decisioncraft as dc
from playwright.sync_api import sync_playwright


def main():
    model = dc.new("opportunity-tree", "Display check", "What should we try?")
    model["maps"][0]["root"].update(
        title="API and API", detail="More context for this choice.", children=[]
    )
    model["glossary"] = {"API": "A way for programs to exchange information."}
    model["notes"] = [dict(id="Q1", anchor=model["maps"][0]["root"]["id"],
                           role="owner", title="Choose a trial", question="What should we try?")]
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        path = Path(tmp) / "display.html"
        path.write_text(dc.render(model))
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(path.as_uri())
        page.get_by_role("button", name="Got it", exact=True).click()

        def item(name):
            page.locator("#top").get_by_role("button", name="View ▾").click()
            return page.get_by_role("menuitemcheckbox", name=name, exact=True)

        def state(name):
            it = item(name)
            value = it.get_attribute("aria-checked")
            page.keyboard.press("Escape")
            return value

        assert state("Technical names on the map") == "false"
        assert not page.locator("#world .techname").count()
        page.locator("#world .box").click()
        assert "More context for this choice." in page.inner_text("#panel")
        page.locator("#pclose").click()
        item("Technical names on the map").click()
        assert state("Technical names on the map") == "true"
        assert page.locator("#world .techname").inner_text() == "More context for this choice."
        assert page.locator("#world .term").count() == 2
        page.locator("#world .term").nth(1).hover()
        assert page.locator("#gloss").is_visible()
        assert model["glossary"]["API"] in page.inner_text("#gloss")
        page.locator("#world .term").nth(1).click()
        assert not page.locator("#panel").is_visible()
        page.locator("#world .term").nth(1).focus()
        page.keyboard.press("Enter")
        assert page.locator("#gloss").is_visible()
        assert not page.locator("#panel").is_visible()
        page.locator("#top").get_by_role("button", name="View ▾").click()
        page.get_by_role("menuitem", name="Word meanings", exact=True).click()
        assert model["glossary"]["API"] in page.inner_text("#panel")
        item("Background dots").click()
        assert "dots" not in page.locator("body").get_attribute("class").split()
        item("List on the left").click()
        assert state("List on the left") == "false"
        page.reload()
        assert state("Technical names on the map") == "true"
        assert state("Background dots") == "false"
        item("List on the left").click()
        assert page.locator("#story [data-give]").is_visible()
        page.set_viewport_size({"width": 390, "height": 844})
        # The resize handler rebuilds the toolbar before fitting the map.
        page.wait_for_timeout(150)
        for button in page.locator("#top button").all():
            if not button.is_visible():
                continue
            rect = button.bounding_box()
            assert rect and rect["x"] >= 0 and rect["x"] + rect["width"] <= 390, (button.get_attribute("aria-label") or button.inner_text(), rect)
            assert button.get_attribute("aria-label") or button.inner_text().strip()
        model["maps"][0]["root"].pop("detail")
        model.pop("glossary")
        plain = Path(tmp) / "plain.html"
        plain.write_text(dc.render(model))
        page.goto(plain.as_uri())
        page.locator("#top").get_by_role("button", name="View ▾").click()
        assert not page.get_by_role("menuitemcheckbox", name="Technical names on the map", exact=True).count()
        assert not page.get_by_role("menuitem", name="Word meanings", exact=True).count()
        browser.close()
    print("ok View menu states, technical names, repeated word meanings, reload and mobile controls")


if __name__ == "__main__":
    main()
