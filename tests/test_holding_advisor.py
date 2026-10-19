import numpy as np
import pandas as pd

from utils.holding_advisor import advise, compute_facts, scenario_paths


def _series(trend, n=300, start=20.0):
    return pd.Series(start * np.exp(np.linspace(0, trend, n)), index=pd.bdate_range("2025-01-01", periods=n))


def test_uptrend_calm_is_hold_high_conf():
    f = compute_facts(_series(0.5)); b = compute_facts(_series(0.3, start=80000))
    a = advise("RIOT", f, b, 15.0, shares=100, cost_basis=10, portfolio_value=10000)
    assert a.action == "HOLD" and a.confidence == "High"


def test_target_hit_trims():
    f = compute_facts(_series(0.5)); b = compute_facts(_series(0.3, start=80000))
    a = advise("RIOT", f, b, 15.0, shares=100, cost_basis=10, portfolio_value=10000, target_price=f["price"] * 0.9)
    assert a.action == "TRIM" and a.trim_pct == 25


def test_many_warnings_sell():
    f = compute_facts(_series(-1.0)); b = compute_facts(_series(-0.6, start=80000))
    a = advise("RIOT", f, b, 35.0, shares=100, cost_basis=10, portfolio_value=1000)
    assert a.risk_score >= 5 and a.action == "SELL"


def test_concentration_trims():
    f = compute_facts(_series(0.5)); b = compute_facts(_series(0.3, start=80000))
    a = advise("RIOT", f, b, 15.0, shares=1000, cost_basis=10, portfolio_value=f["price"] * 1000 / 0.7)
    assert a.action == "TRIM"


def test_missing_data_never_invents():
    a = advise("RIOT", {}, {}, None)
    assert a.confidence == "Low" and a.checks[0].status == "missing"


def test_scenarios_ordered():
    s = scenario_paths(10.0, 4.0, {"bear": -0.15, "base": 0.05, "bull": 0.25}, 0.9)
    assert s["bear"] < s["base"] < s["bull"] and s["band_low"] < 10 < s["band_high"]


# ── ADD signal & shared risk score ──────────────────────────────────────────
from utils.holding_advisor import add_signal, add_rule, market_risk_score, rsi_wilder, rsi_series


def _crash_then(n_up=260, n_down=40):
    up = np.linspace(0, 0.6, n_up); down = np.linspace(0.6, -0.1, n_down)
    return pd.Series(20 * np.exp(np.concatenate([up, down])), index=pd.bdate_range("2024-01-01", periods=n_up + n_down))


def test_add_fires_when_oversold_and_backdrop_healthy():
    f = compute_facts(_crash_then()); b = compute_facts(_series(0.3, start=80000))
    a = add_signal(f, b, 15.0, peer_vs_200=0.0, weight=0.10)
    assert a.action == "ADD" and a.n_oversold >= 2


def test_add_blocked_by_size_cap():
    f = compute_facts(_crash_then()); b = compute_facts(_series(0.3, start=80000))
    a = add_signal(f, b, 15.0, peer_vs_200=0.0, weight=0.80)
    assert a.action == "WAIT" and "80%" in a.headline


def test_add_waits_when_vix_spikes_or_btc_weak():
    f = compute_facts(_crash_then()); b = compute_facts(_series(0.3, start=80000))
    assert add_signal(f, b, 32.0, 0.0, 0.1).action == "WAIT"
    bw = compute_facts(_series(-0.6, start=80000))
    assert add_signal(f, bw, 15.0, 0.0, 0.1).action == "WAIT"


def test_add_waits_in_uptrend():
    f = compute_facts(_series(0.5)); b = compute_facts(_series(0.3, start=80000))
    assert add_signal(f, b, 15.0, 0.0, 0.1).action == "WAIT"


def test_rsi_matches_series():
    px = _crash_then()
    assert abs(rsi_wilder(px) - rsi_series(px).iloc[-1]) < 1e-9


def test_market_risk_score_matches_advise():
    f = compute_facts(_series(-1.0)); b = compute_facts(_series(-0.6, start=80000))
    a = advise("RIOT", f, b, 27.0)  # no position -> only market points
    assert a.risk_score == market_risk_score(f["price"], f["sma50"], f["sma200"], f["drawdown"],
                                             b["price"], b["sma200"], 27.0)
