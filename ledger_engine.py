"""
ledger_engine.py — Banshee 5 Portfolio Transaction Ledger

Pure functions. No I/O, no network (adapter pattern — the caller fetches data
and current prices; this engine only computes). Average-cost basis. The single
source of truth for derived positions, cash, and realized P&L.

See docs/superpowers/specs/2026-06-08-portfolio-history-design.md.
"""

_EPS = 1e-9

_QUARTER_ENDS = {1: "03-31", 2: "06-30", 3: "09-30", 4: "12-31"}

_INTERNAL_LINE = ("Evolution couldn't be computed right now — the rest of your "
                  "analysis is unaffected.")
_STEADY_LINE = "Your mix held steady this quarter — no major shifts."
_INSUFFICIENT_LINE = ("Evolution tracking begins once you've held positions "
                      "across a full quarter.")


def prev_quarter_end(today_iso):
    """ISO date (YYYY-MM-DD) of the last day of the calendar quarter BEFORE
    the quarter that `today_iso` falls in."""
    parts = str(today_iso).split("-")
    y, m = int(parts[0]), int(parts[1])
    q = (m - 1) // 3 + 1            # 1..4
    if q == 1:
        return f"{y - 1}-12-31"
    return f"{y}-{_QUARTER_ENDS[q - 1]}"


def has_two_quarters(earliest_iso, today_iso):
    """True when the earliest transaction falls in a STRICTLY earlier calendar
    quarter than today (the minimum history the evolution line needs)."""
    if not earliest_iso or not today_iso:
        return False
    ep = str(earliest_iso).split("-")
    tp = str(today_iso).split("-")
    e = (int(ep[0]), (int(ep[1]) - 1) // 3)   # (year, quarter_index 0..3)
    t = (int(tp[0]), (int(tp[1]) - 1) // 3)
    return e < t


def _sorted_txns(transactions):
    """Stable sort by ISO date; same-day ties keep original array order."""
    return sorted(enumerate(transactions or []),
                  key=lambda it: (str(it[1].get("date", "")), it[0]))


def replay(transactions, as_of=None):
    """Replay the ledger in date order; return derived state as of `as_of`
    (default: all transactions). See spec for the exact shape."""
    positions = {}          # sym -> {"shares", "cost_basis", "first_date"}
    cash = 0.0
    realized = 0.0
    total_deposited = 0.0
    opening_cost_basis = 0.0   # capital deployed in pre-existing (opening) holdings
    warnings = []
    cash_negative = False

    for _i, tx in _sorted_txns(transactions):
        date = str(tx.get("date", ""))
        if as_of is not None and date > str(as_of):
            continue
        ttype = str(tx.get("type", "")).upper()

        if ttype == "BUY":
            sym = tx.get("sym")
            qty = float(tx.get("shares") or 0)
            price = tx.get("price")
            opening = bool(tx.get("opening"))
            if qty <= 0 or not sym:
                continue
            pos = positions.get(sym)
            if pos is None or pos["shares"] <= _EPS:
                pos = {"shares": 0.0, "cost_basis": 0.0, "first_date": date}
                positions[sym] = pos
            pos["shares"] += qty
            if price is not None:
                pos["cost_basis"] += qty * float(price)
            if opening and price is not None:
                # opening lots are money the user already had deployed before
                # tracking began — counted toward "money in", but they don't
                # flow through cash (no deposit was logged for them).
                opening_cost_basis += qty * float(price)
            elif price is not None:
                cash -= qty * float(price)

        elif ttype == "SELL":
            sym = tx.get("sym")
            qty = float(tx.get("shares") or 0)
            if tx.get("price") is None:
                warnings.append(f"sold {sym} on {date} with no price — ignored")
                continue
            price = float(tx.get("price") or 0)
            pos = positions.get(sym)
            if pos is None or pos["shares"] <= _EPS:
                warnings.append(f"sold {sym} on {date} but no shares held — ignored")
                continue
            if qty > pos["shares"] + _EPS:
                warnings.append(
                    f"sold {qty:g} {sym} on {date} but only {pos['shares']:g} held — clamped")
                qty = pos["shares"]
            avg_cost = pos["cost_basis"] / pos["shares"] if pos["shares"] > _EPS else 0.0
            realized += qty * (price - avg_cost)
            pos["shares"] -= qty
            pos["cost_basis"] -= qty * avg_cost
            cash += qty * price
            if pos["shares"] <= _EPS:
                del positions[sym]

        elif ttype == "DEPOSIT":
            amt = float(tx.get("amount") or 0)
            cash += amt
            total_deposited += amt

        elif ttype == "WITHDRAW":
            cash -= float(tx.get("amount") or 0)

        if cash < -_EPS and not cash_negative:
            warnings.append(f"cash went negative on {date} — missing a deposit?")
            cash_negative = True
        elif cash >= -_EPS:
            cash_negative = False

    pos_out = []
    for sym, pos in positions.items():
        if pos["shares"] <= _EPS:
            continue
        avg_cost = pos["cost_basis"] / pos["shares"] if pos["shares"] > _EPS else 0.0
        pos_out.append({
            "sym": sym,
            "shares": round(pos["shares"], 8),
            "avg_cost": round(avg_cost, 4),
            "cost_basis": round(pos["cost_basis"], 4),
            "first_date": pos["first_date"],
        })

    return {
        "positions": pos_out,
        "cash": round(cash, 2),
        "realized_pnl": round(realized, 2),
        "total_deposited": round(total_deposited, 2),
        "opening_cost_basis": round(opening_cost_basis, 2),
        "warnings": warnings,
    }


def holdings_to_transactions(holdings, today):
    """Migrate legacy static holdings to opening BUY transactions (spec §Migration).

    Pure: `today` (ISO 'YYYY-MM-DD' str) is supplied by the caller so this stays
    deterministic and testable. Each holding -> an opening BUY (sets shares +
    basis, debits no cash). Missing entry_price -> price=None (basis unknown).
    Missing entry_date -> earliest known entry_date, else `today`.
    The 'never re-migrate' guard lives in the caller (presence of transactions)."""
    holdings = holdings or []
    dates = [h.get("entry_date") for h in holdings if h.get("entry_date")]
    earliest = min(dates) if dates else today
    out = []
    for i, h in enumerate(holdings):
        ep = h.get("entry_price")
        out.append({
            "id": f"tx_open_{i}",
            "type": "BUY",
            "sym": h.get("sym"),
            "shares": h.get("shares", 0) or 0,
            "price": ep if (ep is not None and ep != "") else None,
            "date": h.get("entry_date") or earliest,
            "opening": True,
        })
    return out


def composition_at(transactions, date, price_lookup, cls_of):
    """Asset-class weights as of `date` (spec §composition_at). Caller supplies:
      price_lookup(sym, date) -> float|None (historical close; None => skip the position)
      cls_of(sym)             -> str        (static asset class per symbol)
    Cash is its own bucket so a move to cash reads as defensive."""
    state = replay(transactions, as_of=date)
    buckets = {}
    total = 0.0
    for p in state["positions"]:
        price = price_lookup(p["sym"], date)
        if price is None:
            continue
        val = p["shares"] * float(price)
        cls = cls_of(p["sym"]) or "EQUITY"
        buckets[cls] = buckets.get(cls, 0.0) + val
        total += val
    cash = state["cash"]
    if cash > _EPS:  # negative cash (margin / missing-deposit state) is intentionally omitted — no negative weight
        buckets["CASH"] = buckets.get("CASH", 0.0) + cash
        total += cash
    weights = {k: round(v / total, 4) for k, v in buckets.items()} if total > _EPS else {}
    return {"as_of": date, "total_value": round(total, 2), "weights": weights}


def _pp(move):
    """Absolute percentage-point label, e.g. '30pp'."""
    return f"{abs(round(move['delta_pp']))}pp"


def _build_sentence(qualifying):
    """Compose the shift sentence from the top-2 movers (by |delta|)."""
    top = qualifying[:2]
    ups = [m for m in top if m["delta_pp"] > 0]
    downs = [m for m in top if m["delta_pp"] < 0]
    if len(top) == 1:
        m = top[0]
        if m["delta_pp"] > 0:
            return f"This quarter your {m['cls']} weight rose +{_pp(m)}."
        return f"This quarter your {m['cls']} weight fell {_pp(m)}."
    if ups and downs:
        u, d = ups[0], downs[0]
        return (f"This quarter you rotated more into {u['cls']} (+{_pp(u)}) "
                f"and out of {d['cls']} ({_pp(d)}).")
    if len(ups) == 2:
        a, b = ups
        return (f"This quarter you shifted more into {a['cls']} (+{_pp(a)}) "
                f"and {b['cls']} (+{_pp(b)}).")
    a, b = downs
    return f"This quarter you trimmed {a['cls']} ({_pp(a)}) and {b['cls']} ({_pp(b)})."


def _price_gap_line(transactions, date, price_lookup):
    state = replay(transactions, as_of=date)
    missing = [p["sym"] for p in state["positions"]
               if price_lookup(p["sym"], date) is None]
    if missing:
        names = ", ".join(missing[:3])
        return (f"Couldn't chart your evolution — {names} have no price history "
                f"that far back.")
    return ("Couldn't chart your evolution — price history was unavailable for "
            "this period.")


def evolution_line(transactions, q_prev_date, q_curr_date,
                   price_lookup, cls_of, enough_history, threshold=0.10):
    """Compare asset-class composition at two quarter boundaries and describe
    the shift in one sentence. Pure (adapter pattern): the caller supplies
    price_lookup(sym, date)->float|None, cls_of(sym)->str, and enough_history.
    The engine owns every sentence string. See the Phase 3 spec for the shape."""
    if not enough_history:
        return {"status": "insufficient", "line": _INSUFFICIENT_LINE, "reason": None}
    try:
        prev = composition_at(transactions, q_prev_date, price_lookup, cls_of)
        curr = composition_at(transactions, q_curr_date, price_lookup, cls_of)
        wf, wt = prev["weights"], curr["weights"]
        if not wf or not wt:
            return {"status": "unavailable", "reason": "price_gap",
                    "line": _price_gap_line(transactions, q_curr_date, price_lookup)}
        classes = set(wf) | set(wt)
        moves = []
        for c in classes:
            dpp = round((wt.get(c, 0.0) - wf.get(c, 0.0)) * 100, 1)
            if abs(dpp) >= 1:
                moves.append({"cls": c, "delta_pp": dpp})
        moves.sort(key=lambda m: abs(m["delta_pp"]), reverse=True)
        thr_pp = threshold * 100
        qualifying = [m for m in moves if abs(m["delta_pp"]) >= thr_pp - _EPS]
        if not qualifying:
            return {"status": "steady", "line": _STEADY_LINE, "reason": None,
                    "from": wf, "to": wt, "moves": moves}
        return {"status": "shift", "line": _build_sentence(qualifying),
                "reason": None, "from": wf, "to": wt, "moves": moves}
    except Exception:
        return {"status": "unavailable", "reason": "internal", "line": _INTERNAL_LINE}


def total_return(realized_pnl, total_deposited, holdings_rows, opening_cost_basis=0.0):
    """Net return = (realized + unrealized P&L) / money actually put in (spec §3).

    "Money in" is cash you deposited PLUS the cost basis of pre-existing
    (opening) holdings — capital deployed before tracking began that never
    flowed through the cash ledger as a deposit. Counting only deposits is wrong
    when a large opening book sits behind a token deposit (a $10 deposit must not
    become the whole denominator). When neither deposits nor opening basis exist
    (e.g. all non-opening buys), it falls back to the current cost basis.

    Rows need entry_price>0 and current_price>0 to contribute unrealized/basis;
    rows without a usable basis are ignored. Returns None when nothing qualifies."""
    unrealized = 0.0
    cost_basis = 0.0
    for r in holdings_rows:
        ep, cp, sh = r.get("entry_price"), r.get("current_price"), r.get("shares") or 0
        if ep and ep > 0 and cp and cp > 0:
            unrealized += (cp - ep) * sh
            cost_basis += ep * sh
    money_in = (total_deposited or 0.0) + (opening_cost_basis or 0.0)
    denom = money_in if money_in > 0 else cost_basis
    if denom <= 0:
        return None
    return round((realized_pnl + unrealized) / denom, 4)
