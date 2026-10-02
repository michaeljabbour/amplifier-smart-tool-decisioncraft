"""Options, a scoring table and cost over time, for decisions between a few clear choices.

All deterministic: the canvas repeats the same arithmetic live, and the words and tests
use these functions. Scores are whole numbers from 1 to 5 and totals are shown to one
decimal place, so the table never looks more precise than the judgments behind it.
"""

from __future__ import annotations

import math

SCORE_MIN, SCORE_MAX = 1, 5
WEIGHT_MAX = 5
CRITERION_KINDS = ("scored", "must")
COST_KINDS = {
    "purchase": "Buying it",
    "lease": "Lease payments",
    "financing": "Loan payments",
    "insurance": "Insurance",
    "energy": "Fuel or charging",
    "maintenance": "Servicing and repairs",
    "tax": "Taxes and fees",
    "membership": "Membership and hire",
    "other": "Other costs",
}
CLOSE_CALL = 0.25  # totals closer than this (on the 1-5 scale) are a close call
MAX_HORIZON_YEARS = 10


def _list(value) -> list:
    return value if isinstance(value, list) else []


def _num(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def has_choice(model: dict) -> bool:
    return any(k in model for k in ("options", "criteria", "scores", "costs", "whatifs", "framing"))


# ---------------------------------------------------------------- checking


def check_choice(model: dict, evidence_ids: set) -> list[dict]:
    """Problems with options, criteria, scores, costs and what-ifs (validate's format)."""
    out: list[dict] = []

    def err(path, msg):
        out.append({"level": "error", "path": path, "message": msg})

    def warn(path, msg):
        out.append({"level": "warning", "path": path, "message": msg})

    options = []
    if "options" in model and not isinstance(model["options"], list):
        err("options", "Options must be a list.")
    for i, o in enumerate(_list(model.get("options"))):
        p = f"options[{i}]"
        if not isinstance(o, dict):
            err(p, "Each option must be a JSON object.")
            continue
        options.append(o)
        if not str(o.get("name", "")).strip():
            err(f"{p}.name", "Give each option a short name.")
    option_ids = {o.get("id") for o in options}
    if options and len(options) < 2:
        warn("options", "A choice needs at least two options. Doing nothing counts if it is real.")

    criteria = []
    if "criteria" in model and not isinstance(model["criteria"], list):
        err("criteria", "Criteria must be a list.")
    for i, c in enumerate(_list(model.get("criteria"))):
        p = f"criteria[{i}]"
        if not isinstance(c, dict):
            err(p, "Each criterion must be a JSON object.")
            continue
        criteria.append(c)
        if not str(c.get("name", "")).strip():
            err(f"{p}.name", "Give each criterion a short name.")
        kind = c.get("kind", "scored")
        if kind not in CRITERION_KINDS:
            err(f"{p}.kind", "A criterion is scored or a must-have (kind: scored or must).")
        if kind == "scored":
            w = c.get("weight")
            if not _num(w) or not 0 <= w <= WEIGHT_MAX:
                err(f"{p}.weight", f"Weight is a number from 0 to {WEIGHT_MAX} (how much it matters).")
            elif w * 2 != int(w * 2):
                warn(f"{p}.weight", "Use whole or half weights; finer weights suggest precision nobody has.")
        elif "weight" in c:
            warn(f"{p}.weight", "A must-have has no weight: an option either meets it or it is out.")
    by_crit = {c.get("id"): c for c in criteria}
    if criteria and not any(c.get("kind", "scored") == "scored" for c in criteria):
        warn("criteria", "Add at least one scored criterion, or the table cannot rank anything.")

    if "scores" in model and not isinstance(model["scores"], list):
        err("scores", "Scores must be a list.")
    seen = set()
    for i, s in enumerate(_list(model.get("scores"))):
        p = f"scores[{i}]"
        if not isinstance(s, dict):
            err(p, "Each score must be a JSON object.")
            continue
        if s.get("option") not in option_ids:
            err(f"{p}.option", f"Score points at unknown option {s.get('option')!r}.")
        c = by_crit.get(s.get("criterion"))
        if c is None:
            err(f"{p}.criterion", f"Score points at unknown criterion {s.get('criterion')!r}.")
            continue
        key = (s.get("option"), s.get("criterion"))
        if key in seen:
            err(p, f"Option {key[0]} is scored on {key[1]} twice.")
        seen.add(key)
        if c.get("kind", "scored") == "must":
            if not isinstance(s.get("meets"), bool):
                err(f"{p}.meets", "For a must-have, say whether the option meets it: meets true or false.")
            elif not s["meets"] and not str(s.get("note", "")).strip():
                warn(f"{p}.note", "Say why the option fails this must-have.")
        else:
            v = s.get("value")
            if not isinstance(v, int) or isinstance(v, bool) or not SCORE_MIN <= v <= SCORE_MAX:
                err(f"{p}.value", f"A score is a whole number from {SCORE_MIN} to {SCORE_MAX}.")
        for r in _list(s.get("evidence")):
            if r not in evidence_ids:
                err(f"{p}.evidence", f"Unknown evidence {r!r}.")
    if options and criteria and "scores" in model:
        gaps = [(o, c) for o in options for c in criteria if (o.get("id"), c.get("id")) not in seen]
        if gaps and len(gaps) == len(options) * len(criteria):
            # A starter model (for example after an interview): one warning, not one per cell.
            warn("scores", f"No scores yet for {len(options)} options and {len(criteria)} criteria. "
                 "Add a score 1-5 with a note and evidence for each, or meets true/false for a must-have.")
        else:
            for o, c in gaps[:10]:
                warn("scores", f"{o.get('name', o.get('id'))} has no score for {c.get('name', c.get('id'))}.")
            if len(gaps) > 10:
                warn("scores", f"... and {len(gaps) - 10} more option and criterion pairs with no score.")

    costs = model.get("costs")
    if costs is not None:
        out.extend(_check_costs(costs, option_ids))
    framing = model.get("framing")
    if framing is not None:
        if not isinstance(framing, dict):
            err("framing", "Framing must be a JSON object with premortem and regret.")
        else:
            pm = framing.get("premortem", [])
            if not isinstance(pm, list) or any(not isinstance(x, str) or not x.strip() for x in pm):
                err("framing.premortem", "List the reasons it went badly, one sentence each.")
            rg = framing.get("regret", {})
            if not isinstance(rg, dict) or any(not isinstance(v, str) for v in rg.values()):
                err("framing.regret", "Regret is text keyed by time, like \"10 months\".")
    if "whatifs" in model and not isinstance(model["whatifs"], list):
        err("whatifs", "What-ifs must be a list.")
    for i, wi in enumerate(_list(model.get("whatifs"))):
        p = f"whatifs[{i}]"
        if not isinstance(wi, dict):
            err(p, "Each what-if must be a JSON object.")
            continue
        if not str(wi.get("label", "")).strip():
            err(f"{p}.label", "Say what the what-if changes, in a few words.")
        mult = wi.get("multiply")
        if not isinstance(mult, dict) or not mult:
            err(f"{p}.multiply", "A what-if multiplies costs: multiply {\"energy\": 1.3}.")
            continue
        for k, f in mult.items():
            if not _num(f) or f < 0:
                err(f"{p}.multiply.{k}", "Each factor is a number, 0 or more (1.3 means 30% more).")
    return out


def _check_costs(costs, option_ids) -> list[dict]:
    out: list[dict] = []

    def err(path, msg):
        out.append({"level": "error", "path": path, "message": msg})

    def warn(path, msg):
        out.append({"level": "warning", "path": path, "message": msg})

    if not isinstance(costs, dict):
        return [{"level": "error", "path": "costs", "message": "Costs must be a JSON object."}]
    h = costs.get("horizon_years", 5)
    if not isinstance(h, int) or isinstance(h, bool) or not 1 <= h <= MAX_HORIZON_YEARS:
        err("costs.horizon_years", f"The horizon is a whole number of years from 1 to {MAX_HORIZON_YEARS}.")
        h = 5
    if "currency" in costs and not isinstance(costs["currency"], str):
        err("costs.currency", "Currency is a short code like USD.")
    r = costs.get("cash_return", 0)
    if not _num(r) or not 0 <= r < 0.5:
        err("costs.cash_return", "What cash would earn elsewhere is a yearly rate, like 0.04 for 4%.")
    per = costs.get("options")
    if not isinstance(per, dict):
        err("costs.options", "List each option's costs under its id.")
        return out
    for oid, c in per.items():
        p = f"costs.options.{oid}"
        if oid not in option_ids:
            err(p, f"Costs for unknown option {oid!r}.")
        if not isinstance(c, dict):
            err(p, "Each option's costs must be a JSON object.")
            continue
        for i, u in enumerate(_list(c.get("upfront"))):
            if not isinstance(u, dict) or not _num(u.get("amount")) or not str(u.get("label", "")).strip():
                err(f"{p}.upfront[{i}]", "Each upfront cost needs a label and an amount.")
            elif u.get("kind", "other") not in COST_KINDS:
                err(f"{p}.upfront[{i}].kind", f"Kind must be one of {', '.join(COST_KINDS)}.")
        for i, it in enumerate(_list(c.get("items"))):
            ip = f"{p}.items[{i}]"
            if not isinstance(it, dict) or not str(it.get("label", "")).strip():
                err(ip, "Each running cost needs a label.")
                continue
            if it.get("kind", "other") not in COST_KINDS:
                err(f"{ip}.kind", f"Kind must be one of {', '.join(COST_KINDS)}.")
            y = it.get("yearly")
            if _num(y):
                continue
            if not isinstance(y, list) or not y or any(not _num(v) for v in y):
                err(f"{ip}.yearly", "Give a yearly amount, or a list of amounts for year 1, year 2 and so on.")
            elif len(y) < h:
                warn(f"{ip}.yearly", f"Only {len(y)} years given for a {h}-year horizon; the last year repeats.")
            if any(_num(v) and v < 0 for v in (y if isinstance(y, list) else [])):
                warn(f"{ip}.yearly", "A negative running cost is unusual; use value for what the thing is worth.")
        loan = c.get("loan")
        if loan is not None:
            if not isinstance(loan, dict) or not _num(loan.get("amount")) or loan["amount"] < 0:
                err(f"{p}.loan", "A loan needs an amount, a yearly rate (apr) and a length in months.")
            else:
                if not _num(loan.get("apr")) or not 0 <= loan["apr"] < 1:
                    err(f"{p}.loan.apr", "The loan rate is yearly, like 0.067 for 6.7%.")
                mo = loan.get("months")
                if not isinstance(mo, int) or isinstance(mo, bool) or not 1 <= mo <= 120:
                    err(f"{p}.loan.months", "The loan length is a whole number of months, 1 to 120.")
        value = c.get("value")
        if value is not None:
            if not isinstance(value, list) or any(not _num(v) or v < 0 for v in value):
                err(f"{p}.value", "Value is what it is worth: today, then at the end of each year.")
            elif len(value) < h + 1:
                warn(f"{p}.value", f"Value is given for {len(value) - 1} years of {h}; the last value is kept.")
            elif any(b > a for a, b in zip(value, value[1:])):
                warn(f"{p}.value", "The value goes up in a later year. Check the numbers.")
    missing = option_ids - set(per)
    if missing and not per:
        warn("costs.options", f"No costs yet for any of the {len(option_ids)} options, so the cost chart is empty. "
             "Add upfront amounts, yearly items, any loan and value by year for each option.")
    else:
        for oid in sorted(x for x in missing if isinstance(x, str)):
            warn("costs.options", f"Option {oid} has no costs, so it is left off the cost chart.")
    return out


# ---------------------------------------------------------------- scoring


def scoring(model: dict, weights: dict | None = None) -> dict:
    """Weighted totals, must-have failures, the leader and what would flip it.

    weights: optional {criterion id: weight} that replaces the model's weights (a
    reviewer's own weights). Returns totals on the 1-5 scale.
    """
    options = [o for o in _list(model.get("options")) if isinstance(o, dict)]
    criteria = [c for c in _list(model.get("criteria")) if isinstance(c, dict)]
    scored = [c for c in criteria if c.get("kind", "scored") == "scored"]
    musts = [c for c in criteria if c.get("kind") == "must"]
    w = {c["id"]: float((weights or {}).get(c["id"], c.get("weight", 0))) for c in scored}
    cell = {(s.get("option"), s.get("criterion")): s for s in _list(model.get("scores")) if isinstance(s, dict)}
    rows = []
    for o in options:
        fails = [c["id"] for c in musts if cell.get((o["id"], c["id"]), {}).get("meets") is False]
        unknown = [c["id"] for c in musts if not isinstance(cell.get((o["id"], c["id"]), {}).get("meets"), bool)]
        A = sum(w[c["id"]] * cell.get((o["id"], c["id"]), {}).get("value", 0) for c in scored)
        missing = [c["id"] for c in scored if (o["id"], c["id"]) not in cell]
        W = sum(w[c["id"]] for c in scored if (o["id"], c["id"]) in cell)
        rows.append({"option": o["id"], "name": o.get("name", o["id"]), "points": A,
                     "total": round(A / W, 2) if W else 0.0, "fails": fails, "unknown_musts": unknown,
                     "missing": missing})
    eligible = sorted((r for r in rows if not r["fails"]), key=lambda r: (-r["total"], _order(options, r["option"])))
    for rank, r in enumerate(eligible, 1):
        r["rank"] = rank
    leader = eligible[0]["option"] if eligible else None
    runner = eligible[1] if len(eligible) > 1 else None
    close = bool(runner and eligible[0]["total"] - runner["total"] < CLOSE_CALL)
    return {"weights": w, "options": rows, "leader": leader,
            "close_call": close, "flips": flips(model, w, cell, scored, eligible, options)}


def _order(options, oid) -> int:
    return next((i for i, o in enumerate(options) if o["id"] == oid), 0)


def flips(model, w, cell, scored, eligible, options, limit: int = 3) -> list[dict]:
    """The smallest changes that would put a different option on top.

    Two kinds: a weight change (within 0 to 5) or a one-point change in a single score.
    Sorted by how small the change is; deterministic ties by table order.
    """
    if len(eligible) < 2:
        return []
    lead = eligible[0]["option"]
    val = lambda o, c: cell.get((o, c), {}).get("value")
    out = []
    W = sum(w.values())
    for r in eligible[1:]:
        o = r["option"]
        A_l = sum(w[c["id"]] * (val(lead, c["id"]) or 0) for c in scored)
        A_o = sum(w[c["id"]] * (val(o, c["id"]) or 0) for c in scored)
        gap = A_l - A_o  # o needs to make this up
        for c in scored:
            vl, vo = val(lead, c["id"]), val(o, c["id"])
            if vl is None or vo is None or vl == vo:
                continue
            delta = gap / (vo - vl)  # weight change that makes them equal
            new = w[c["id"]] + delta
            # strict overtake: nudge by a quarter point in the same direction, then round to halves
            step = 0.5 if delta > 0 else -0.5
            target = math.ceil(new * 2) / 2 if delta > 0 else math.floor(new * 2) / 2
            if target == new:
                target += step
            if 0 <= target <= WEIGHT_MAX and target != w[c["id"]]:
                out.append({"kind": "weight", "option": o, "criterion": c["id"],
                            "from": w[c["id"]], "to": target, "size": abs(target - w[c["id"]])})
        for c in scored:
            vl, vo = val(lead, c["id"]), val(o, c["id"])
            if vl is None or vo is None or not W:
                continue
            if vo < SCORE_MAX and A_o + w[c["id"]] > A_l:
                out.append({"kind": "score", "option": o, "criterion": c["id"], "of": o,
                            "from": vo, "to": vo + 1, "size": 1.0})
            if vl > SCORE_MIN and A_l - w[c["id"]] < A_o:
                out.append({"kind": "score", "option": o, "criterion": c["id"], "of": lead,
                            "from": vl, "to": vl - 1, "size": 1.0})
    order = {o["id"]: i for i, o in enumerate(options)}
    crit_order = {c["id"]: i for i, c in enumerate(scored)}
    # One score point and one weight point count as the same size of change.
    out.sort(key=lambda f: (f["size"], f["kind"] != "score", -w.get(f["criterion"], 0),
                            order.get(f["option"], 0), crit_order.get(f["criterion"], 0)))
    # Check each change against every option, not only the leader: report who ends on top.
    eligible_ids = [r["option"] for r in eligible]
    checked = []
    for f in out:
        ww, cc = dict(w), dict(cell)
        if f["kind"] == "weight":
            ww[f["criterion"]] = f["to"]
        else:
            key = (f["of"], f["criterion"])
            cc[key] = {**cc[key], "value": f["to"]}
        top = _top(eligible_ids, ww, cc, scored, order)
        if top != lead:
            checked.append({**f, "new_leader": top})
    return checked[:limit]


def _top(ids, w, cell, scored, order):
    def total(o):
        W = sum(w[c["id"]] for c in scored if (o, c["id"]) in cell)
        A = sum(w[c["id"]] * cell[(o, c["id"])].get("value", 0) for c in scored if (o, c["id"]) in cell)
        return A / W if W else 0
    return sorted(ids, key=lambda o: (-total(o), order.get(o, 0)))[0]


# ---------------------------------------------------------------- cost over time


def _yearly(item, year: int) -> float:
    y = item.get("yearly", 0)
    if _num(y):
        return float(y)
    y = [v for v in _list(y) if _num(v)]
    return float(y[min(year, len(y) - 1)]) if y else 0.0


def _factor(mult: dict, keys) -> float:
    f = 1.0
    for k in keys:
        if k in mult:
            f *= float(mult[k])
    return f


def loan_schedule(amount: float, apr: float, months: int) -> tuple[float, list[float]]:
    """Monthly payment and the balance left after each month (index 0 = before any payment)."""
    r = apr / 12
    pay = amount / months if r == 0 else amount * r / (1 - (1 + r) ** -months)
    bal = [amount]
    b = amount
    for _ in range(months):
        b = b * (1 + r) - pay
        bal.append(max(b, 0.0))
    return pay, bal


def option_series(costs: dict, oid: str, mult: dict | None = None) -> dict:
    """Month by month for one option: money spent so far, and the real cost so far.

    Real cost = money spent + loan still owed - what the thing is worth + what the cash
    put in up front could have earned elsewhere. Month 0 is the day you start.
    """
    mult = mult or {}
    h = costs.get("horizon_years", 5)
    months = h * 12
    c = costs["options"][oid]
    up = sum(u["amount"] * _factor(mult, [u.get("kind", "other"), *u.get("tags", [])]) for u in _list(c.get("upfront")))
    items = _list(c.get("items"))
    loan = c.get("loan")
    pay, bal = (loan_schedule(loan["amount"], loan["apr"], loan["months"]) if loan else (0.0, [0.0]))
    value = [v for v in _list(c.get("value")) if _num(v)] or [0.0]
    vf = _factor(mult, ["value"])
    rate = costs.get("cash_return", 0) or 0
    spent, real = [], []
    total = up
    for m in range(months + 1):
        if m > 0:
            year = (m - 1) // 12
            total += sum(_yearly(it, year) * _factor(mult, [it.get("kind", "other"), *it.get("tags", [])]) / 12 for it in items)
            if loan and m <= loan["months"]:
                total += pay
        owed = bal[min(m, len(bal) - 1)] if loan else 0.0
        yi, frac = divmod(m, 12)
        a = value[min(yi, len(value) - 1)]
        b = value[min(yi + 1, len(value) - 1)]
        worth = (a + (b - a) * frac / 12) * vf
        forgone = up * ((1 + rate) ** (m / 12) - 1)
        spent.append(round(total, 2))
        real.append(round(total + owed - worth + forgone, 2))
    if not loan:
        pay = sum(_yearly(it, 0) for it in items if it.get("kind") in ("lease",)) / 12
    return {"spent": spent, "real": real, "payment": round(pay, 2), "upfront": round(up, 2)}


def breakdown(costs: dict, oid: str, mult: dict | None = None) -> list[dict]:
    """Where the real cost over the whole horizon comes from, largest first."""
    mult = mult or {}
    h = costs.get("horizon_years", 5)
    c = costs["options"][oid]
    parts: dict[str, float] = {}
    bought = 0.0
    for u in _list(c.get("upfront")):
        amt = u["amount"] * _factor(mult, [u.get("kind", "other"), *u.get("tags", [])])
        if u.get("kind") == "purchase":
            bought += amt
        else:
            parts[u.get("kind", "other")] = parts.get(u.get("kind", "other"), 0) + amt
    for it in _list(c.get("items")):
        f = _factor(mult, [it.get("kind", "other"), *it.get("tags", [])])
        parts[it.get("kind", "other")] = parts.get(it.get("kind", "other"), 0) + sum(_yearly(it, y) * f for y in range(h))
    loan = c.get("loan")
    if loan:
        pay, bal = loan_schedule(loan["amount"], loan["apr"], loan["months"])
        n = min(loan["months"], h * 12)
        interest = pay * n - (loan["amount"] - bal[n])
        parts["interest"] = interest
        bought += loan["amount"]
    value = [v for v in _list(c.get("value")) if _num(v)]
    if value:
        end = value[min(h, len(value) - 1)] * _factor(mult, ["value"])
        parts["value_lost"] = bought - end
    elif bought:
        parts["purchase"] = parts.get("purchase", 0) + bought
    rate = costs.get("cash_return", 0) or 0
    up = sum(u["amount"] * _factor(mult, [u.get("kind", "other"), *u.get("tags", [])]) for u in _list(c.get("upfront")))
    if rate and up:
        parts["cash_tied_up"] = up * ((1 + rate) ** h - 1)
    label = {**COST_KINDS, "interest": "Loan interest", "value_lost": "Value lost (what it is worth less at the end)",
             "cash_tied_up": "What the cash up front could have earned"}
    return sorted(({"kind": k, "label": label.get(k, k), "amount": round(v, 2)} for k, v in parts.items() if abs(v) >= 25),
                  key=lambda p: -p["amount"])


def whatif_multipliers(model: dict, ids) -> dict:
    mult: dict[str, float] = {}
    by_id = {w.get("id"): w for w in _list(model.get("whatifs")) if isinstance(w, dict)}
    for i in ids or []:
        for k, f in (by_id.get(i) or {}).get("multiply", {}).items():
            mult[k] = mult.get(k, 1.0) * float(f)
    return mult


def cost_over_time(model: dict, whatifs=()) -> dict | None:
    """Every option's month-by-month real cost, totals at each year and where lines cross."""
    costs = model.get("costs")
    if not isinstance(costs, dict) or not isinstance(costs.get("options"), dict):
        return None
    names = {o["id"]: o.get("name", o["id"]) for o in _list(model.get("options")) if isinstance(o, dict)}
    order = [o for o in names if o in costs["options"]]
    mult = whatif_multipliers(model, whatifs)
    h = costs.get("horizon_years", 5)
    series = {o: option_series(costs, o, mult) for o in order}
    at_years = {o: {y: series[o]["real"][y * 12] for y in range(1, h + 1)} for o in order}
    crossings = []
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            ra, rb = series[a]["real"], series[b]["real"]
            prev = None
            for m in range(1, h * 12 + 1):
                d = ra[m] - rb[m]
                sign = (d > 0) - (d < 0)
                if prev is not None and sign and prev and sign != prev:
                    cheaper, dearer = (a, b) if sign < 0 else (b, a)
                    crossings.append({"month": m, "cheaper": cheaper, "dearer": dearer})
                if sign:
                    prev = sign
    crossings.sort(key=lambda c: (c["month"], order.index(c["cheaper"])))
    end = sorted(order, key=lambda o: series[o]["real"][-1])
    return {"horizon_years": h, "currency": costs.get("currency", ""), "names": names, "order": order,
            "series": series, "at_years": at_years, "crossings": crossings,
            "cheapest": end[0] if end else None, "ranking": end,
            "breakdown": {o: breakdown(costs, o, mult) for o in order}, "whatifs": list(whatifs)}


def money(v: float, currency: str = "") -> str:
    sign = "-" if v < 0 else ""
    sym = {"USD": "$", "GBP": "£", "EUR": "€"}.get(currency, "")
    text = f"{abs(v):,.0f}"
    return f"{sign}{sym}{text}" if sym else f"{sign}{text}{' ' + currency if currency else ''}"


def describe_crossings(result: dict, focus: str | None = None, limit: int = 4) -> list[str]:
    """Plain sentences about where one option becomes cheaper than another."""
    if not result:
        return []
    names = result["names"]
    lines = []
    for c in result["crossings"]:
        if focus and focus not in (c["cheaper"], c["dearer"]):
            continue
        lines.append(f"{names[c['cheaper']]} costs less than {names[c['dearer']]} from month {c['month']} on"
                     f" ({_years(c['month'])}).")
    return lines[:limit]


def _years(m: int) -> str:
    y, mo = divmod(m, 12)
    if y and mo:
        return f"{y} year{'s' if y > 1 else ''} and {mo} month{'s' if mo > 1 else ''} in"
    if y:
        return f"{y} year{'s' if y > 1 else ''} in"
    return f"{mo} month{'s' if mo > 1 else ''} in"
