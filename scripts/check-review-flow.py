#!/usr/bin/env python3
"""Check written answers, old views, offline saving and merge in a real browser.

Needs Playwright and Chromium, like check-canvas.py. Uses temporary files only.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'src'))
import decisioncraft as dc
from decisioncraft.review import check_review
from playwright.sync_api import sync_playwright


def main():
    model = dc.new('opportunity-tree', 'Review flow check', 'Which trial should we run?')
    model['maps'][0]['root'].update(id='goal', title='Choose a trial', children=[])
    model['notes'] = [dict(id='Q1', role='owner', anchor='goal', title='Choose a trial',
        question='Which trial should we run?', recommend='Use one small trial.', urgency='must'),
        dict(id='Q2', role='engineer', anchor='goal', title='Support the plan',
        question='Do you support the proposed trial?', answer_type='stance', urgency='should')]
    answer = 'Try one decision first.\nMeasure time and requests for help.'
    with tempfile.TemporaryDirectory() as tmp, sync_playwright() as pw:
        root = Path(tmp)
        canvas = root / 'canvas.html'
        canvas.write_text(dc.render(model))
        browser = pw.chromium.launch()
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        page.goto(canvas.as_uri())
        page.get_by_role('button', name='Got it', exact=True).click()
        # Seed an old response through storage, then prove it is kept but not completed.
        key = page.evaluate("'decisioncraft:' + JSON.parse(document.querySelector('#dc-meta').textContent).fingerprint")
        page.evaluate("([key]) => localStorage.setItem(key, JSON.stringify({answers:{Q1:{choice:'agree',comment:'Keep this earlier comment.'}}}))", [key])
        page.reload()
        page.locator('#story').get_by_role('button', name='1. Understand the decision').click()
        page.get_by_role('button', name='See all questions', exact=True).click()
        assert '0 of 2 reviewed' in page.inner_text('#review-progress')
        assert page.locator('[data-comment=Q1]').input_value() == 'Keep this earlier comment.'
        assert 'Earlier view: agree' in page.inner_text('#panel')
        page.locator('#story').get_by_role('button', name='1. Understand the decision').click()
        page.get_by_role('button', name='Answer questions', exact=True).click()
        assert 'Question 1 of 2' in page.inner_text('#panel')
        assert page.get_by_text('Use one small trial.', exact=True).is_visible()
        assert not page.locator('#panel details').count()
        assert page.locator('[data-answer]').count() == 1
        page.locator('[data-answer=Q1]').fill(answer)
        page.get_by_role('button', name='Mark as important', exact=True).click()
        assert '4 votes left' in page.inner_text('#panel')
        page.get_by_role('button', name='Next question', exact=True).click()
        page.locator('[data-ans=Q2][data-choice=agree]').click()
        page.get_by_role('button', name='Check my answers', exact=True).click()
        assert answer in page.locator('.review-answer').first.inner_text()
        page.locator('[data-review-at="0"]').click()
        assert page.locator('[data-answer=Q1]').input_value() == answer
        page.get_by_role('button', name='Pause and check my answers', exact=True).click()
        assert '2 of 2 reviewed' in page.inner_text('#review-progress')
        # Views and answers survive a reload of this exact model.
        page.reload()
        page.locator('#story').get_by_role('button', name='1. Understand the decision').click()
        page.get_by_role('button', name='See all questions', exact=True).click()
        assert page.locator('[data-answer=Q1]').input_value() == answer
        page.locator('#reviewer').fill('Product owner')
        # Copy includes the actual answer, not a view labelled as an answer.
        page.evaluate("window.copied = ''; Object.defineProperty(navigator, 'clipboard', {value:{writeText: text => {window.copied=text; return Promise.resolve();}}, configurable:true})")
        page.locator('#top').get_by_role('button', name='Tools ▾', exact=True).click()
        page.get_by_role('menuitem', name='Copy the questions as a list').click()
        copied = page.evaluate('window.copied')
        assert 'my answer: Try one decision first.' in copied
        assert 'my view: agree' in copied
        assert 'my answer: agree' not in copied
        page.evaluate("() => { window.print = () => { window.paper = document.querySelector('#paper-review').innerHTML; }; }")
        page.locator('#top').get_by_role('button', name='Tools ▾', exact=True).click()
        page.get_by_role('menuitem', name='Print the questions', exact=True).click()
        paper = page.evaluate('window.paper')
        assert 'Which trial should we run?' in paper and 'Decision owner:' in paper
        assert paper.count('<article>') == 2
        assert not page.locator('#paper-review').count()
        assert not page.evaluate("document.body.classList.contains('print-review')")
        with page.expect_download() as dl:
            page.locator('#top').get_by_role('button', name='Save my answers', exact=True).click()
        saved = root / 'review.json'
        dl.value.save_as(saved)
        review = json.loads(saved.read_text())
        assert check_review(review) == []
        assert review['answers']['Q1']['answer'] == answer
        assert review['answers']['Q1']['comment'] == 'Keep this earlier comment.'
        assert review['answers']['Q2']['choice'] == 'agree'
        assert review['dots']['Q1'] == 1
        assert 'Send your saved answers' in page.inner_text('#panel')
        merged = dc.merge([review], model)
        assert merged['stale_reviews'] == []
        assert merged['questions']['Q1']['answers'] == [{'who':'Product owner', 'text':answer}]
        rendered = root / 'reviewed.html'
        rendered.write_text(dc.render(model, merged=merged))
        page.goto(rendered.as_uri())
        page.locator('#story').get_by_role('button', name='1. Understand the decision').click()
        page.get_by_role('button', name='See all questions', exact=True).click()
        page.get_by_role('button', name='Compare earlier responses', exact=True).first.click()
        assert answer in page.locator('.review-answer').inner_text()
        page.get_by_role('button', name='Back to the question', exact=True).click()
        # Unavailable browser storage is visible, and file saving still works.
        page.evaluate("() => { Storage.prototype.setItem = () => { throw new Error('Storage unavailable'); }; }")
        page.locator('[data-answer=Q1]').fill('A partial answer is still worth saving.')
        assert 'storage is unavailable' in page.inner_text('#review-progress')
        with page.expect_download() as partial:
            page.locator('#top').get_by_role('button', name='Save my answers', exact=True).click()
        partial.value.save_as(root / 'partial.json')
        assert json.loads((root / 'partial.json').read_text())['answers']['Q1']['answer'].startswith('A partial answer')
        browser.close()
    print('ok written answer → reopen → download → merge → reviewed canvas; old views and storage failure')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
