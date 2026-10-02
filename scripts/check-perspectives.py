#!/usr/bin/env python3
"""Check sticky-note perspectives and option comparison with visible controls."""

from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
import decisioncraft as dc
from playwright.sync_api import sync_playwright


def main():
    model = dc.new("opportunity-tree", "Compare review styles", "How should we review?")
    model["roles"] = [
        dict(id="architect", label="Architect", color="#d9b420"),
        dict(id="ux", label="UX", color="#de699b"),
    ]
    model["notes"] = [
        dict(
            id="A1",
            role="architect",
            anchor="root",
            title="Keep a reason",
            question="What would make you change the choice?",
        ),
        dict(
            id="U1",
            role="ux",
            anchor="root",
            title="Make it easy to finish",
            question="What should happen next?",
        ),
    ]
    model["comparison"] = dict(
        criteria=[dict(id="C1", label="Easy to understand", importance="must")],
        options=[
            dict(
                id="O1",
                title="Map first",
                evaluations=[
                    dict(
                        criterion="C1",
                        judgment="unknown",
                        reason="Not tried by a new reader.",
                    )
                ],
            ),
            dict(id="O2", title="Question first", evaluations=[]),
        ],
        method="Observe one real review.",
    )
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        path = Path(tmp) / "perspectives.html"
        path.write_text(dc.render(model))
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 1000})
        page.goto(path.as_uri())
        page.get_by_role("button", name="Got it", exact=True).click()
        page.locator("#top").get_by_role("button", name="View ▾").click()
        page.get_by_role("menuitemcheckbox", name="Notes on the map", exact=True).click()
        assert page.locator(".notecard").count() == 2
        assert (
            page.locator("#role-strip")
            .get_by_role("button", name="Architect", exact=True)
            .is_visible()
        )
        page.locator("#role-strip").get_by_role("button", name="UX", exact=True).click()
        assert (
            page.locator(".notecard").count() == 1
            and "Architect" in page.locator(".notecard").inner_text()
        )
        page.locator("#story").get_by_role(
            "button", name="2. Give your view", exact=True
        ).click()
        assert "Question 1 of 2" in page.inner_text("#panel")
        page.get_by_role("button", name="Compare the options", exact=True).click()
        text = page.inner_text("#panel")
        assert (
            "Must-have" in text
            and "Not yet known" in text
            and "No choice has been recommended" in text
        )
        page.locator("#pclose").click()
        page.locator("#role-strip").get_by_role("button", name="UX", exact=True).click()
        assert page.locator(".notecard").count() == 2
        assert (
            page.locator(".notecard").first.evaluate(
                "el => getComputedStyle(el).transform"
            )
            != "none"
        )
        page.reload()
        assert page.locator(".notecard").count() == 2
        browser.close()
    print(
        "ok custom Architect and UX roles, paper notes, all review questions and explicit uncertainty"
    )


if __name__ == "__main__":
    main()
