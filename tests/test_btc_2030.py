import math

import numpy as np
import pandas as pd
import pytest

from utils import btc_scenarios as bs
from utils import riot_btc_link as link


# ── Scenario math ────────────────────────────────────────────────────
def test_growth_is_sum_of_drivers_and_projection_compounds():
    a = bs.default_assumptions()
    for s in bs.SCENARIOS:
        assert bs.scenario_growth(a[s]) == pytest.approx(sum(a[s].values()) / 100)
    out = bs.build_scenarios(80_000, 4.0, a, inflation=0.03)
    g = out["Base"]["growth"]
    assert out["Base"]["price"] == pytest.approx(80_000 * (1 + g) ** 4)
    assert out["Base"]["real_price"] == pytest.approx(out["Base"]["price"] / 1.03 ** 4)
    prices = [out[s]["price"] for s in bs.SCENARIOS]
    assert prices == sorted(prices)            # bear < base < bull < super-bull
    assert out["Bear"]["growth"] < 0           # a genuine bear case exists


def test_editing_a_driver_moves_only_that_scenario():
    a = bs.default_assumptions()
    base0 = bs.build_scenarios(80_000, 4.0, a)["Base"]["price"]
    a["Bull"]["policy"] += 10
    out = bs.build_scenarios(80_000, 4.0, a)
    assert out["Base"]["price"] == pytest.approx(base0)
    assert out["Bull"]["growth"] == pytest.approx(bs.scenario_growth(bs.default_assumptions()["Bull"]) + 0.10)


def test_no_live_price_means_no_scenarios():
    assert bs.build_scenarios(None, 4.0) == {}
    assert bs.build_scenarios(float("nan"), 4.0) == {}
    assert bs.build_scenarios(0, 4.0) == {}


def test_every_driver_and_target_is_documented():
    for d in bs.DRIVERS:
        assert set(d.assumption) == set(bs.SCENARIOS) and set(d.why) == set(bs.SCENARIOS) and d.help
        for k in d.sources:
            assert k in bs.SOURCES
    for k, v in {**bs.SOURCES, **link.AI_SOURCES}.items():
        assert v["url"].startswith("https://") and len(v["date"]) == 10, k
    for p in bs.PUBLISHED_TARGETS:
        assert p["src"] in bs.SOURCES


def test_growth_needed_roundtrip():
    g = bs.growth_needed(80_000, 160_000, 4.0)
    assert bs.project(80_000, g, 4.0) == pytest.approx(160_000)


# ── Forward / inverse mapping ────────────────────────────────────────
@pytest.mark.parametrize("beta,drift,sigma", [(1.12, 0.0, 0.0), (0.74, -0.05, 0.6), (1.6, 0.03, 0.3)])
def test_inverse_is_exact_inverse_of_forward(beta, drift, sigma):
    s0, b0, yrs = 14.0, 82_000.0, 4.2
    for bt in [50_000, 176_000, 760_000]:
        fwd = link.project_stock(s0, b0, bt, yrs, beta, drift, sigma)
        inv = link.btc_for_stock(fwd["point"], s0, b0, yrs, beta, drift, sigma)
        assert inv["point"] == pytest.approx(bt, rel=1e-9)
        # range: the stock's HIGH band hits X at a LOWER BTC, and vice versa
        assert link.btc_for_stock(fwd["high"], s0, b0, yrs, beta, drift, sigma)["low"] == pytest.approx(bt, rel=1e-9)
        assert inv["low"] <= inv["point"] <= inv["high"]


def test_inverse_flags_unreachable_and_tiny_beta():
    assert link.btc_for_stock(40, 14, 82_000, 4.2, 0.0, 0, 0)["point"] is None
    r = link.btc_for_stock(400, 14, 82_000, 4.2, 0.17, 0, 0)
    assert r["reachable"] is False


def test_factor_signs():
    assert link.drift_from_factors({"dilution": 10}) == pytest.approx(-math.log(1.1))
    assert link.drift_from_factors({"ai_hpc": 10}) == pytest.approx(math.log(1.1))
    assert link.drift_from_factors({"hashprice": 0, "energy": 0, "dilution": 0, "ai_hpc": 0}) == 0


# ── Fit: recovers a known beta and never uses future data ─────────────
def _synthetic(beta=1.2, n_days=3000, seed=1):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2018-01-02", periods=n_days)
    lb = np.cumsum(rng.normal(0.0005, 0.03, n_days))
    noise = np.zeros(n_days)
    for i in range(1, n_days):          # mean-reverting idiosyncratic gap
        noise[i] = 0.99 * noise[i - 1] + rng.normal(0, 0.02)
    ls = 2 + beta * lb + noise
    return pd.Series(np.exp(ls), idx), pd.Series(np.exp(lb + 10), idx)


def test_fit_recovers_beta():
    s, b = _synthetic(1.2)
    f = link.fit_link(s, b)
    assert f["beta"] == pytest.approx(1.2, abs=0.25)
    assert 0 < f["r2"] <= 1 and 0 <= f["rho_q"] < 1
    assert f["recent_beta"] is not None and len(f["rolling"]) > 0


def test_fit_has_no_future_leakage():
    s, b = _synthetic(1.2)
    cut = s.index[1800]
    f_cut = link.fit_link(s, b, as_of=cut)
    f_trunc = link.fit_link(s[s.index <= cut], b[b.index <= cut])
    # appending wildly different future data must not change a point-in-time fit
    s2 = s.copy()
    s2[s2.index > cut] *= 50
    f_cut2 = link.fit_link(s2, b, as_of=cut)
    for k in ["beta", "r2", "alpha_q", "level_sd", "rho_q", "recent_beta", "n_quarters"]:
        assert f_cut[k] == pytest.approx(f_trunc[k]) == pytest.approx(f_cut2[k])
    assert f_cut["end"] <= cut.date()


def test_fit_needs_enough_history():
    s, b = _synthetic(1.0, n_days=400)
    assert link.fit_link(s, b) is None


def test_horizon_sigma_bounded_by_level_sd():
    f = {"level_sd": 0.6, "rho_q": 0.7}
    assert link.horizon_sigma(f, 0.25) < link.horizon_sigma(f, 4) <= 0.6


def test_measured_dilution():
    idx = pd.date_range("2022-01-01", "2026-01-01", freq="QS")
    sh = pd.Series(100 * 1.1 ** (np.arange(len(idx)) / 4), idx)
    assert link.measured_dilution(sh, 1.0) == pytest.approx(10, abs=0.5)
    assert link.measured_dilution(pd.Series(dtype=float)) is None


def test_halving_cycles_on_synthetic_peak():
    idx = pd.date_range("2020-01-01", "2023-12-31", freq="D")
    px = pd.Series(10_000.0, idx)
    px[pd.Timestamp("2021-11-08")] = 60_000
    px[idx > pd.Timestamp("2022-06-01")] = 5_000
    c = [x for x in link.halving_cycles(px) if str(x["halving"]) == "2020-05-11"][0]
    assert str(c["peak_date"]) == "2021-11-08" and 17 < c["months"] < 19
    assert c["drawdown"] == pytest.approx(5_000 / 60_000 - 1)
