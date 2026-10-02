"""A stand-in model for `map` tests: answers the draft and perspectives prompts for the
fictional bike hire repository in tests/fixtures/sample-repo. No network, same reply each run."""

import json

from decisioncraft.mapper import map_roles
from decisioncraft.model import new_model

Q = "How does sample-repo work today, and what is missing?"


def bike_model() -> dict:
    m = new_model("system-journeys", "How bike hire works", Q, date="2026-10-02")
    m["summary"] = "Visitors book a bike online and pay at the counter; held bikes often go unused."
    m["roles"] = map_roles()
    m["sources"] = [
        {"id": "S1", "title": "What the app does (README)", "kind": "document", "ref": "README.md"},
        {"id": "S2", "title": "Staff meeting notes", "kind": "meeting", "ref": "docs/staff-notes.md"},
        {"id": "S3", "title": "Booking code", "kind": "code", "ref": "src/booking/app.py"},
    ]
    m["evidence"] = [
        {"id": "E1", "source": "S1", "kind": "quote", "where": "README.md:9",
         "text": "The visitor pays at the counter when they arrive; there is no online payment yet."},
        {"id": "E2", "source": "S2", "kind": "quote", "where": "docs/staff-notes.md:3", "voice": True,
         "text": "About one booking in five never shows up on a sunny Saturday."},
        {"id": "E3", "source": "S3", "kind": "file", "where": "src/booking/app.py:21",
         "text": "TODO: no way to record damage here; staff use a paper list."},
        {"id": "E4", "source": "S3", "kind": "file", "where": "src/booking/app.py:4", "text": "HOLD_MINUTES = 15"},
    ]
    j = {"id": "j1", "title": "Booking a bike", "summary": "From picking a date to bringing the bike back.",
         "creates": ["A held bike", "An out or in status"], "steps": [
        {"id": "s1", "lane": "people", "text": "Visitor picks a date and a bike size", "status": "works", "evidence": ["E4"]},
        {"id": "s2", "lane": "core", "text": "App holds a free bike for 15 minutes", "status": "works", "evidence": ["E4"]},
        {"id": "s3", "lane": "front", "text": "Visitor pays at the counter on arrival", "status": "partial",
         "when": "today", "evidence": ["E1"]},
        {"id": "s3p", "lane": "outside", "text": "Visitor pays a deposit online when booking", "status": "planned",
         "when": "planned", "replaces": "s3"},
        {"id": "s4", "lane": "background", "text": "Reminder message the evening before", "status": "planned",
         "when": "planned", "evidence": ["E2"]},
        {"id": "s5", "lane": "records", "text": "Staff note damage on a paper list", "status": "partial",
         "when": "today", "evidence": ["E3"]},
        {"id": "s5p", "lane": "records", "text": "Staff report damage on a phone at check-in", "status": "planned",
         "when": "planned", "replaces": "s5"},
    ]}
    m["maps"][0]["journeys"] = [j]
    m["maps"][0]["intro"] = "How a booking moves through the app today, and the proposed changes."
    m["gaps"] = [
        {"id": "G1", "title": "No-shows leave bikes idle", "why": "One booking in five never shows up.",
         "anchors": ["s3", "s4"], "impact": 4, "effort": 2,
         "stories": [{"as": "As a visitor, I want a reminder the evening before, so I don't forget my booking.",
                      "done_when": ["A reminder goes out by 6pm the day before", "No-shows drop below one in ten"]}]},
        {"id": "G2", "title": "Damage is found too late", "why": "The next customer finds the damage.",
         "anchors": ["s5"], "impact": 3, "effort": 2,
         "stories": [{"as": "As a mechanic, I want staff to report damage at check-in, so the bike is fixed before it goes out again.",
                      "done_when": ["Damage can be reported in under a minute on a phone", "The paper list is retired"]}]},
    ]
    m["notes"] = [
        {"id": "N1", "role": "voice", "anchor": "s3p", "title": "Deposits may put people off",
         "body": "Some visitors decide on the day.", "question": "Would a deposit stop walk-up visitors from booking?",
         "urgency": "should", "evidence": ["E1"], "author": "AI assistant"},
        {"id": "N2", "role": "security", "anchor": "s4", "title": "Phone numbers are personal data",
         "body": "Reminders need a phone number we don't store today.", "question": "How long do we keep visitors' phone numbers?",
         "urgency": "must", "evidence": [], "author": "AI assistant"},
    ]
    m["decisions"] = [{"id": "D1", "question": "Take a deposit online, or keep paying at the counter?", "notes": ["N1"],
                       "options": ["Deposit online", "Pay at the counter"], "owner": "the shop owner", "status": "open"}]
    m["outcomes"] = [{"id": "O1", "measure": "Share of bookings that never show up", "baseline": "about one in five",
                      "target": "under one in ten"}]
    return m


def perspective_notes() -> dict:
    notes = []
    anchors = ["s1", "s2", "s3p", "s4", "s5p", "G1", "G2", "s2"]
    for i, r in enumerate(map_roles()):
        notes.append({"id": f"P{i + 1}", "role": r["id"], "anchor": anchors[i], "title": f"{r['label']} view",
                      "body": "Worth checking before building.", "recommend": "",
                      "question": f"{r['asks']}", "urgency": "should", "evidence": []})
    return {"notes": notes}


def complete(system: str, prompt: str) -> str:
    if "Write up to" in prompt:
        return json.dumps(perspective_notes())
    return json.dumps(bike_model())


COMMAND = f"{__import__('sys').executable} {__import__('pathlib').Path(__file__).with_name('stub_complete.py')}"
