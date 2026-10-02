"""Options, the scoring table, cost over time, framing and display settings."""

import copy
import json
from pathlib import Path

import pytest

from decisioncraft.choice import (
    breakdown, cost_over_time, describe_crossings, loan_schedule, option_series, scoring,
)
from decisioncraft.model import new_model, templates, validate
from decisioncraft.review import merge
from decisioncraft.words import words

CAR = Path(__file__).resolve().parents[1] / "examples" / "personal-car" / "model.json"


def car():
    return json.loads(CAR.read_text())


def errors(model):
    return [p for p in validate(model) if p["level"] == "error"]


def tiny():
    m = new_model("personal-decision", "Pick a bike", "Which bike?")
    m["options"] = [{"id": "a", "name": "A"}, {"id": "b", "name": "B"}, {"id": "c", "name": "C"}]
    m["criteria"] = [
        {"id": "must", "name": "Fits the shed", "kind": "must"},
        {"id": "price", "name": "Price", "kind": "scored", "weight": 4},
        {"id": "comfort", "name": "Comfort", "kind": "scored", "weight": 2},
    ]
    m["scores"] = [
        {"option": "a", "criterion": "must", "meets": True}, {"option": "a", "criterion": "price", "value": 5},
        {"option": "a", "criterion": "comfort", "value": 2},
        {"option": "b", "criterion": "must", "meets": True}, {"option": "b", "criterion": "price", "value": 3},
        {"option": "b", "criterion": "comfort", "value": 5},
        {"option": "c", "criterion": "must", "meets": False, "note": "Too long"},
        {"option": "c", "criterion": "price", "value": 5}, {"option": "c", "criterion": "comfort", "value": 5},
    ]
    return m


# ---------------------------------------------------------------- templates and validation

def test_personal_decision_is_a_starting_set():
    ids = [t["id"] for t in templates()]
    assert {"scoring-table", "cost-over-time", "personal-decision"} <= set(ids)
    m = new_model("personal-decision", "Car", "Which car?")
    assert [x["template"] for x in m["maps"]] == ["decision-chain", "customer-journey", "scoring-table", "cost-over-time"]
    assert {r["id"] for r in m["roles"]} >= {"money", "safety", "future", "devil"}
    assert errors(m) == []


def test_personal_decision_cannot_be_a_single_map():
    m = tiny()
    m["maps"][0]["template"] = "personal-decision"
    assert any(p["path"] == "maps[0].template" for p in errors(m))


def test_car_example_is_valid():
    assert errors(car()) == []


@pytest.mark.parametrize("change,path", [
    (lambda m: m["criteria"][1].update(weight=7), "criteria[1].weight"),
    (lambda m: m["criteria"][1].update(kind="nice"), "criteria[1].kind"),
    (lambda m: m["scores"][1].update(value=6), "scores[1].value"),
    (lambda m: m["scores"][1].update(value=2.5), "scores[1].value"),
    (lambda m: m["scores"][0].pop("meets"), "scores[0].meets"),
    (lambda m: m["scores"].append({"option": "zz", "criterion": "price", "value": 3}), "scores[9].option"),
    (lambda m: m["scores"].append({"option": "a", "criterion": "price", "value": 3}), "scores[9]"),
])
def test_scoring_validation(change, path):
    m = tiny()
    change(m)
    assert any(p["path"] == path for p in errors(m)), errors(m)


def test_finer_than_half_weights_warn():
    m = tiny()
    m["criteria"][1]["weight"] = 3.3
    assert any(p["path"] == "criteria[1].weight" and p["level"] == "warning" for p in validate(m))


@pytest.mark.parametrize("change,path", [
    (lambda c: c.update(horizon_years=0), "costs.horizon_years"),
    (lambda c: c.update(cash_return=4), "costs.cash_return"),
    (lambda c: c["options"].update(zz={}), "costs.options.zz"),
    (lambda c: c["options"]["keep"]["loan"].update(apr=7.9), "costs.options.keep.loan.apr"),
    (lambda c: c["options"]["keep"]["loan"].update(months=0), "costs.options.keep.loan.months"),
    (lambda c: c["options"]["keep"]["items"][0].update(yearly="lots"), "costs.options.keep.items[0].yearly"),
    (lambda c: c["options"]["keep"]["items"][0].update(kind="snacks"), "costs.options.keep.items[0].kind"),
    (lambda c: c["options"]["keep"].update(value=[1, -2]), "costs.options.keep.value"),
])
def test_cost_validation(change, path):
    m = car()
    change(m["costs"])
    assert any(p["path"] == path for p in errors(m)), errors(m)


def test_whatif_and_framing_validation():
    m = car()
    m["whatifs"][0]["multiply"] = {"energy": -1}
    m["framing"]["premortem"] = ["fine", ""]
    paths = {p["path"] for p in errors(m)}
    assert "whatifs[0].multiply.energy" in paths and "framing.premortem" in paths


def test_display_settings():
    m = tiny()
    m["display"] = {"notes_on_map": True, "start_view": "planned"}
    assert errors(m) == []
    m["display"] = {"notes_on_map": "yes", "start_view": "later"}
    paths = {p["path"] for p in errors(m)}
    assert {"display.notes_on_map", "display.start_view"} <= paths


def test_notes_may_anchor_to_options_criteria_and_whatifs():
    m = car()
    anchors = {n["anchor"] for n in m["notes"]}
    assert {"keep", "flex", "w-miles"} <= anchors
    assert errors(m) == []


# ---------------------------------------------------------------- scoring

def test_must_have_failure_takes_an_option_out():
    r = scoring(tiny())
    c = next(x for x in r["options"] if x["option"] == "c")
    assert c["fails"] == ["must"] and "rank" not in c
    assert r["leader"] == "a"  # C scores highest but fails the must-have


def test_weighted_totals_and_close_call():
    r = scoring(tiny())
    a = next(x for x in r["options"] if x["option"] == "a")
    b = next(x for x in r["options"] if x["option"] == "b")
    assert a["total"] == pytest.approx((4 * 5 + 2 * 2) / 6, abs=0.01)  # 4.0
    assert b["total"] == pytest.approx((4 * 3 + 2 * 5) / 6, abs=0.01)  # 3.67
    assert r["close_call"] is False


def test_flip_the_winner_finds_the_smallest_change():
    r = scoring(tiny())
    assert r["flips"], "a flip should exist"
    for f in r["flips"]:
        assert f["new_leader"] == "b"
    weight = [f for f in r["flips"] if f["kind"] == "weight"]
    # Comfort must matter more (B is better there): 2 -> above 2.67, rounded up to a half step.
    assert any(f["criterion"] == "comfort" and f["from"] == 2 and f["to"] == 3 for f in weight)
    # Applying the flip really changes the winner; half a step less does not.
    m = tiny()
    assert scoring(m, {"comfort": 3})["leader"] == "b"
    assert scoring(m, {"comfort": 2.5})["leader"] == "a"


def test_reviewer_weights_replace_the_models():
    assert scoring(tiny(), {"price": 0})["leader"] == "b"


def test_car_example_scores():
    r = scoring(car())
    assert r["leader"] == "new" and r["close_call"] is True
    share = next(x for x in r["options"] if x["option"] == "share")
    assert share["fails"] == ["m-school"]
    assert all(f["new_leader"] == "used" for f in r["flips"])


# ---------------------------------------------------------------- cost over time

def test_loan_schedule_pays_off():
    pay, bal = loan_schedule(25000, 0.095, 60)
    assert pay == pytest.approx(525.04, abs=0.05)
    assert bal[0] == 25000 and bal[-1] == pytest.approx(0, abs=0.01)
    pay0, bal0 = loan_schedule(1200, 0, 12)
    assert pay0 == 100 and bal0[6] == pytest.approx(600)


def test_real_cost_parts_add_up():
    m = car()
    for oid in m["costs"]["options"]:
        s = option_series(m["costs"], oid)
        parts = breakdown(m["costs"], oid)
        # the breakdown ignores items under $25; the car example has none
        assert sum(p["amount"] for p in parts) == pytest.approx(s["real"][-1], abs=30), oid


def test_buying_month_zero_is_fees_and_instant_drop():
    m = car()
    s = option_series(m["costs"], "new")
    # down 5,230 + loan 33,000 - worth 32,000 on day one
    assert s["real"][0] == pytest.approx(5230 + 33000 - 32000)


def test_depreciation_is_straight_between_year_ends():
    costs = {"horizon_years": 2, "options": {"x": {"upfront": [{"label": "Price", "amount": 1000, "kind": "purchase"}],
                                                  "value": [1000, 800, 700]}}}
    s = option_series(costs, "x")
    assert s["real"][0] == 0 and s["real"][6] == pytest.approx(100) and s["real"][12] == pytest.approx(200)
    assert s["real"][18] == pytest.approx(250) and s["real"][24] == pytest.approx(300)


def test_lease_against_buy_break_even():
    m = car()
    r = cost_over_time(m)
    assert {"month": 15, "cheaper": "used", "dearer": "lease"} in r["crossings"]
    assert {"month": 39, "cheaper": "new", "dearer": "lease"} in r["crossings"]
    assert r["at_years"]["keep"][5] < r["at_years"]["used"][5] < r["at_years"]["new"][5] < r["at_years"]["lease"][5]
    lines = describe_crossings(r)
    assert lines[0].startswith("Buy used costs less than Renew the lease from month 15")


def test_whatifs_move_the_answer():
    m = car()
    base = cost_over_time(m)
    repairs = cost_over_time(m, ["w-repairs"])
    assert repairs["at_years"]["keep"][5] > base["at_years"]["keep"][5]
    assert repairs["at_years"]["used"][5] == base["at_years"]["used"][5]  # only the older car is tagged
    fuel = cost_over_time(m, ["w-fuel"])
    assert fuel["at_years"]["share"][5] == base["at_years"]["share"][5]  # car share includes fuel
    resale = cost_over_time(m, ["w-resale"])
    assert resale["at_years"]["used"][5] - base["at_years"]["used"][5] == pytest.approx(2100, abs=1)


def test_cash_return_counts_what_the_down_payment_could_earn():
    m = car()
    with_rate = option_series(m["costs"], "used")["real"][-1]
    m["costs"]["cash_return"] = 0
    without = option_series(m["costs"], "used")["real"][-1]
    assert with_rate - without == pytest.approx(3914 * (1.04 ** 5 - 1), abs=0.5)


# ---------------------------------------------------------------- reviews and words

def test_merge_shows_weight_disagreements():
    a = {"format": "decisioncraft-review/1", "reviewer": "Dana", "answers": {}, "weights": {"cost": 5, "safety": 2}}
    b = {"format": "decisioncraft-review/1", "reviewer": "Sam", "answers": {}, "weights": {"cost": 4.5, "safety": 5}}
    merged = merge([a, b], car())
    assert merged["weight_split"] == ["safety"]
    assert merged["weights"]["cost"] == [{"who": "Dana", "weight": 5}, {"who": "Sam", "weight": 4.5}]
    text = words(car(), merged)
    assert "Weights reviewers disagree on:" in text and "Safety features: Dana 2, Sam 5." in text


def test_bad_weights_in_a_review_are_refused():
    with pytest.raises(ValueError):
        merge([{"format": "decisioncraft-review/1", "answers": {}, "weights": {"cost": 9}}])


def test_words_has_scores_costs_and_framing():
    text = words(car())
    assert "| **Weighted total** | 3.6 | 3.8 | 4.0 | 3.9 | out: fails a must-have |" in text
    assert "It is a close call" in text
    assert "Buy used costs less than Renew the lease from month 15 on" in text
    assert "## Before you decide" in text and "In 10 years:" in text
    assert "Cheapest over 5 years among options that meet every must-have: **Keep and repair**." in text


def test_words_still_work_without_choice_fields():
    m = tiny()
    m.pop("costs")
    m["maps"] = [x for x in m["maps"] if x["template"] != "cost-over-time"]
    text = words(m)
    assert "Weighted total" in text
