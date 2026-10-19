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
