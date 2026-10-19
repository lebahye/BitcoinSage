"""⚖️ Stock Verdict engine: determinism, one-source-of-truth with My Plan, N/A handling."""
import itertools
import inspect

import numpy as np
import pandas as pd
import pytest

from utils import verdict as V
from utils.verdict import Evidence, build_verdict, combine_plan, combine_not_held
from utils.holding_advisor import advise, add_signal, compute_facts


def _series(trend, n=300, start=20.0):
    return pd.Series(start * np.exp(np.linspace(0, trend, n)), index=pd.bdate_range("2025-01-01", periods=n))


def _crash_then(n_up=260, n_down=40):
    up = np.linspace(0, 0.6, n_up); down = np.linspace(0.6, -0.1, n_down)
    return pd.Series(20 * np.exp(np.concatenate([up, down])), index=pd.bdate_range("2024-01-01", periods=n_up + n_down))


def _ev(lean, w=10, key="x"):
    return Evidence(key, key, "r", lean, w, "measured")


# ── combine rules ───────────────────────────────────────────────────────
def test_combine_plan_truth_table():
    for plan, add in itertools.product(["HOLD", "TRIM", "SELL", "ROTATE"], ["ADD", "WAIT", None]):
        out = combine_plan(plan, add)
        assert out == ("ADD" if (plan == "HOLD" and add == "ADD") else plan)
    assert combine_plan(None, "ADD") is None and combine_plan("N/A", None) is None


def test_not_held_never_trims_or_rotates():
    for plan, add, pts in itertools.product(["HOLD", "TRIM", "SELL", "ROTATE"], ["ADD", "WAIT", None], range(0, 9)):
        out = combine_not_held(plan, add, pts)
        assert out in ("ADD", "HOLD", "SELL")
        assert out == ("SELL" if pts >= 5 else "ADD" if add == "ADD" else "HOLD")
    assert combine_not_held(None, "ADD", 0) is None and combine_not_held("HOLD", None, None) is None


# ── consistency with My Plan (the same answer everywhere) ───────────────
def _scenarios():
    b_up, b_dn = compute_facts(_series(0.3, start=80000)), compute_facts(_series(-0.6, start=80000))
    up, dn, crash = compute_facts(_series(0.5)), compute_facts(_series(-1.0)), compute_facts(_crash_then())
    for f, b, vix, w, tgt in itertools.product([up, dn, crash], [b_up, b_dn], [15.0, 27.0, 35.0],
                                               [0.1, 0.3, 0.8], [None, 0.9, 3.0]):
        price = f["price"]
        a = advise("RIOT", f, b, vix, shares=1000, cost_basis=price / 1.5, portfolio_value=price * 1000 / w,
                   target_price=None if tgt is None else price * tgt)
        ad = add_signal(f, b, vix, 0.05, w)
        yield a, ad


def test_held_verdict_never_contradicts_my_plan():
    n = 0
    noisy = [_ev(1.0, 30, "a"), _ev(-1.0, 25, "b"), _ev(None, 10, "c"), _ev(0.5, 0, "d")]
    for a, ad in _scenarios():
        for ev in ([], noisy, [_ev(1.0, 100)], [_ev(-1.0, 100)]):
            vd = build_verdict("RIOT", True, a.action, a.confidence, ad.action, ev, plan_headline=a.headline,
                               add_headline=ad.headline)
            assert vd.action == combine_plan(a.action, ad.action)      # evidence can't flip the action
            if ad.action != "ADD" or a.action != "HOLD":
                assert vd.action == a.action
            # confidence moves at most one notch from My Plan's
            assert abs(V.CONF_LEVELS.index(vd.confidence) - V.CONF_LEVELS.index(a.confidence)) <= 1
            n += 1
    assert n > 100


def test_my_plan_page_uses_the_same_function():
    import components.holding_plan as hp
    src = inspect.getsource(hp.HoldingPlan.render) if hasattr(hp, "HoldingPlan") else inspect.getsource(hp)
    assert "combine_plan(adv.action" in src


def test_build_for_wiring_matches_my_plan(monkeypatch):
    """The page's gatherer must hand My Plan's own adv/add straight to the engine."""
    import components.holding_plan as hp
    import components.stock_verdict as sv
    f = compute_facts(_crash_then()); b = compute_facts(_series(0.3, start=80000))
    closes = pd.DataFrame({"RIOT": _crash_then()})
    cases = [
        (advise("RIOT", f, b, 15.0, shares=100, cost_basis=10, portfolio_value=f["price"] * 100 / 0.2),
         add_signal(f, b, 15.0, 0.05, 0.2), True),
        (advise("RIOT", f, b, 15.0, shares=1000, cost_basis=10, portfolio_value=f["price"] * 1000 / 0.8),
         add_signal(f, b, 15.0, 0.05, 0.8), True),
        (advise("HUT", f, b, 35.0), add_signal(f, b, 35.0, 0.05, None), False),
    ]
    for adv, add, held in cases:
        sym = adv.symbol
        pos = {sym: {"shares": 100 if held else 0, "cost_basis": 10}}
        monkeypatch.setattr(hp, "get_advice", lambda s, _a=adv, _p=pos, _c=closes.rename(columns={"RIOT": sym}): (_a, _c, _p, {}))
        monkeypatch.setattr(hp, "get_add_advice", lambda s, c, p, _d=add: _d)
        monkeypatch.setattr(hp, "load_backtest", lambda s, y=5: None)
        monkeypatch.setattr(sv, "_btc2030_row", lambda *a: (Evidence("btc_2030", "b", "N/A", None, 0, "model"), {}))
        monkeypatch.setattr(sv, "_reflexivity_rows", lambda *a: [])
        monkeypatch.setattr(sv, "_context_rows", lambda *a: [])
        vd, a2, d2, _ = sv.build_for(sym)
        if held:
            assert vd.action == combine_plan(adv.action, add.action)
        else:
            pts = sum(c.points for c in adv.checks if c.name not in V.PERSONAL_CHECKS)
            assert vd.action == combine_not_held(adv.action, add.action, pts)
        assert vd.held == held


# ── determinism ─────────────────────────────────────────────────────────
def test_deterministic():
    ev = [_ev(1.0, 30, "a"), _ev(-0.5, 25, "b"), _ev(None, 10, "c"), _ev(0.0, 0, "d")]
    v1 = build_verdict("MARA", True, "HOLD", "Medium", "WAIT", list(ev), ["x"])
    v2 = build_verdict("MARA", True, "HOLD", "Medium", "WAIT", list(ev), ["x"])
    assert v1 == v2
    v3 = build_verdict("MARA", True, "HOLD", "Medium", "WAIT", list(reversed(ev)), ["x"])
    assert (v3.action, v3.confidence, v3.score, v3.why) == (v1.action, v1.confidence, v1.score, v1.why)


def test_weighted_score_and_confidence_notches():
    assert V.weighted_score([_ev(1.0, 30), _ev(-1.0, 10), _ev(None, 50), _ev(1.0, 0)]) == 0.5
    assert V.adjust_confidence("Medium", -0.5, -0.4)[0] == "High"      # TRIM, evidence agrees
    assert V.adjust_confidence("Medium", -0.5, 0.3)[0] == "Low"        # TRIM, evidence pulls the other way
    assert V.adjust_confidence("High", 0.0, 0.1)[0] == "High"          # HOLD, neutral evidence
    assert V.adjust_confidence("High", 1.0, 1.0)[0] == "High"          # capped
    assert V.adjust_confidence("Low", -1.0, 1.0)[0] == "Low"           # floored


# ── N/A handling ────────────────────────────────────────────────────────
def test_na_rows_are_ignored_not_invented():
    ev = [_ev(None, 30, "a"), _ev(None, 25, "b")]
    assert V.weighted_score(ev) is None
    vd = build_verdict("CLSK", True, "HOLD", "High", "WAIT", ev)
    assert vd.action == "HOLD" and vd.score is None and vd.confidence == "Medium"
    assert all(V.lean_word(e.lean) == "N/A" for e in vd.evidence)


def test_no_price_means_na_verdict():
    vd = build_verdict("CORZ", False, None, None, None, [])
    assert vd.action == "N/A" and vd.confidence == "Low" and "N/A" in vd.headline


def test_lean_rules_return_none_on_missing():
    for fn, args in [(V.lean_market_risk, (None,)), (V.lean_dilution, (None,)), (V.lean_miner_stress, (None, 1, 2)),
                     (V.lean_sum_of_parts, (None,)), (V.lean_implied, ([None], 10.0)), (V.lean_implied, ([20.0], None)),
                     (V.lean_risk_level, (None,)), (V.lean_ta, (None, None, None, None)), (V.lean_signal, ("N/A",)),
                     (V.lean_label, ("n/a",)), (V.lean_analyst, (None, 10.0))]:
        assert fn(*args) is None, fn.__name__


def test_lean_rules_directions():
    assert V.lean_market_risk(0) > 0 > V.lean_market_risk(3) > V.lean_market_risk(6)
    assert V.lean_dilution(0.15) == -1 and V.lean_dilution(0.01) == 0
    assert V.lean_miner_stress(40_000, 50_000, 90_000) == -1 and V.lean_miner_stress(80_000, 50_000, 90_000) == -0.5
    assert V.lean_miner_stress(150_000, 50_000, 90_000) == 0.5
    assert V.lean_implied([30.0, 15.0], 14.0) == 0.0 and V.lean_implied([30.0, 20.0], 14.0) == 1.0
    assert V.lean_signal("STRONG BUY") == 1 and V.lean_signal("SELL") == -1 and V.lean_signal("HOLD") == 0
    assert V.lean_ta(25, 0.1, 10, 9) == 1.0


def test_disagreements():
    ev = [_ev(1.0, 0, "bull"), _ev(-1.0, 5, "bear"), _ev(0.0, 30, "flat"), _ev(None, 0, "na")]
    assert [e.key for e in V.disagreements(ev, "TRIM")] == ["bull"]
    assert [e.key for e in V.disagreements(ev, "ADD")] == ["bear"]
    assert [e.key for e in V.disagreements(ev, "HOLD")] == ["bull", "bear"]


def test_shares_to_reach_weight():
    # 80% of a $100k book at $10/share = 8,000 shares
    n_cash = V.shares_to_reach_weight(8000, 10.0, 100_000, 0.40, proceeds_to_cash=True)
    n_move = V.shares_to_reach_weight(8000, 10.0, 100_000, 0.40, proceeds_to_cash=False)
    assert n_move == pytest.approx(4000)
    assert (80_000 - n_cash * 10) / (100_000 - n_cash * 10) == pytest.approx(0.40)
    assert V.shares_to_reach_weight(100, 10.0, 100_000, 0.40) == 0.0
    assert V.shares_to_reach_weight(0, 10.0, 100_000, 0.40) is None


def test_ticker_universe_holdings_first():
    from components.stock_verdict import ticker_universe
    u = ticker_universe({"KEEL": {"shares": 1700}, "RIOT": {"shares": 10975}, "MSTR": {"shares": 38}, "XYZ": {"shares": 0}})
    assert u[:3] == ["RIOT", "KEEL", "MSTR"] and "XYZ" not in u
    assert "^VIX" not in u and "BTC-USD" not in u and "BITF" not in u and len(u) == len(set(u))
    assert ticker_universe({})[0] == "RIOT"
