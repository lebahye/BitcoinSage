"""Remember the last My Plan call per ticker and detect when it changes.

State lives in data/last_calls.json (data/ is gitignored — it's personal state).
A detected change is kept as `pending_change` until the user clicks "Got it", so the
banner survives Streamlit reruns and page reloads.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, Optional

STATE_FILE = os.path.join("data", "last_calls.json")
HISTORY_LIMIT = 50


def _load(path: str) -> dict:
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save(d: dict, path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, path)


def snapshot(adv, add=None) -> dict:
    """Small JSON-able summary of a call (Advice + optional AddAdvice)."""
    checks = {c.name: c.status for c in adv.checks}
    if add is not None:
        checks.update({f"ADD · {c.name}": c.status for c in add.oversold + add.backdrop})
    return {
        "action": adv.action,
        "confidence": adv.confidence,
        "headline": adv.headline,
        "risk_score": adv.risk_score,
        "add_action": getattr(add, "action", None),
        "add_headline": getattr(add, "headline", None),
        "price": adv.facts.get("price"),
        "checks": checks,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _why(old: dict, new: dict) -> list:
    """Checks whose status changed between two snapshots (plain English)."""
    out = []
    oc, nc = old.get("checks", {}), new.get("checks", {})
    rank = {"good": 0, "info": 1, "missing": 1, "warn": 2, "bad": 3}
    for name, ns in nc.items():
        os_ = oc.get(name)
        if os_ is None or os_ == ns:
            continue
        better = rank.get(ns, 1) < rank.get(os_, 1)
        out.append(f"{name}: {os_} → {ns} ({'better' if better else 'worse'})")
    if old.get("risk_score") is not None and old.get("risk_score") != new.get("risk_score"):
        out.append(f"Risk points {old['risk_score']} → {new['risk_score']}")
    return out


def record(symbol: str, snap: dict, path: str = STATE_FILE) -> Optional[dict]:
    """Store the new call. Returns a change dict if the call (main or ADD/WAIT) differs
    from the stored one, else None. The first ever check is stored silently."""
    state = _load(path)
    entry = state.get(symbol, {})
    old = entry.get("last")
    change = None
    if old and (old.get("action") != snap["action"] or old.get("add_action") != snap.get("add_action")):
        change = {"symbol": symbol, "old": {k: old.get(k) for k in ("action", "add_action", "confidence", "price", "ts")},
                  "new": {k: snap.get(k) for k in ("action", "add_action", "confidence", "price", "ts")},
                  "why": _why(old, snap), "headline": snap["headline"], "add_headline": snap.get("add_headline"),
                  "notified": False}
        entry["pending_change"] = change
        hist = entry.get("history", [])
        hist.append(change)
        entry["history"] = hist[-HISTORY_LIMIT:]
    entry["last"] = snap
    state[symbol] = entry
    _save(state, path)
    return change


def pending(symbol: str, path: str = STATE_FILE) -> Optional[dict]:
    return _load(path).get(symbol, {}).get("pending_change")


def last(symbol: str, path: str = STATE_FILE) -> Optional[dict]:
    return _load(path).get(symbol, {}).get("last")


def acknowledge(symbol: str, path: str = STATE_FILE) -> None:
    state = _load(path)
    if symbol in state:
        state[symbol].pop("pending_change", None)
        _save(state, path)


def mark_notified(symbol: str, path: str = STATE_FILE) -> None:
    state = _load(path)
    pc = state.get(symbol, {}).get("pending_change")
    if pc:
        pc["notified"] = True
        _save(state, path)


def history(symbol: str, path: str = STATE_FILE) -> list:
    return _load(path).get(symbol, {}).get("history", [])


def format_change(ch: Dict) -> str:
    o, n = ch["old"], ch["new"]
    lines = [f"BitcoinSage: {ch['symbol']} call changed",
             f"Hold/Sell call: {o['action']} → {n['action']}",
             f"Add more?: {o.get('add_action') or 'n/a'} → {n.get('add_action') or 'n/a'}"]
    if n.get("price"):
        lines.append(f"Price now: ${n['price']:,.2f}")
    lines.append(ch.get("headline", ""))
    if ch.get("why"):
        lines.append("What changed: " + "; ".join(ch["why"][:6]))
    lines.append("Educational tool, not financial advice.")
    return "\n".join(lines)
