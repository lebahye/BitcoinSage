"""Tests for the 🧪 Edge Lab: math on synthetic data, no look-ahead, determinism, honest verdicts."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from utils import edge_lab as el
from utils import edge_stats as es


def _rw(n=1500, seed=0, mu=0.0005, sig=0.03, start="2016-01-04"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(100 * np.exp(np.cumsum(rng.normal(mu, sig, n))), idx)


# ── backtest engine ───────────────────────────────────────────────────
def test_forward_outcomes_are_stamped_at_entry_and_use_only_later_bars():
    p = pd.Series([10.0, 8.0, 12.0, 6.0, 9.0], pd.bdate_range("2024-01-01", periods=5))
    fr = es.forward_log_return(p, 2)
    assert fr.iloc[0] == pytest.approx(np.log(12 / 10)) and np.isnan(fr.iloc[-1])
    dd = es.forward_drawdown(p, 2)
    assert dd.iloc[0] == pytest.approx(-0.2)          # min(8,12)/10 − 1
    assert dd.iloc[1] == pytest.approx(-0.25)         # min(12,6)/8 − 1
    assert dd.iloc[2] == pytest.approx(-0.5)
    assert np.isnan(dd.iloc[3]) and np.isnan(dd.iloc[4])


def test_random_signal_is_not_an_edge_and_planted_signal_is():
    p = _rw(3000, seed=1)
    H = 21
    y = es.forward_log_return(p, H)
    rng = np.random.default_rng(7)
    blocks = np.repeat(rng.random(3000 // 60 + 1) < 0.3, 60)[:3000]
    rand_sig = pd.Series(blocks, p.index)
    r = es.evaluate_signal(rand_sig, y, H, direction=-1, hypothesis="random")
    assert r.verdict in (es.NO_EDGE, es.INSUFFICIENT)
    # planted: the signal is ON exactly when the next 21 days fall (uses the future → must look like an edge)
    planted = (y < 0).astype(float).where(y.notna())
    r2 = es.evaluate_signal(planted, y, H, direction=-1, hypothesis="cheat")
    assert r2.verdict == es.EDGE and r2.effect < 0 and r2.p_full < 0.01


def test_evaluate_signal_is_deterministic():
    p = _rw(2000, seed=3)
    y = es.forward_drawdown(p, 30)
    s = pd.Series(np.sin(np.arange(2000) / 40) > 0.5, p.index)
    a = es.evaluate_signal(s, y, 30, direction=-1, hypothesis="x").as_dict()
    b = es.evaluate_signal(s, y, 30, direction=-1, hypothesis="x").as_dict()
    assert a == b


def test_insufficient_when_signal_rarely_on():
    p = _rw(800, seed=4)
    y = es.forward_log_return(p, 63)
    s = pd.Series(False, p.index)
    s.iloc[100:110] = True
    assert es.evaluate_signal(s, y, 63, direction=-1, hypothesis="x").verdict == es.INSUFFICIENT


def test_expanding_rank_is_point_in_time():
    x = pd.Series([3.0, 1.0, 2.0, 5.0, 4.0])
    r = es.expanding_pct_rank(x, min_periods=1)
    assert list(r) == pytest.approx([1.0, 0.5, 2 / 3, 1.0, 0.8])


# ── 1 LPPLS ──────────────────────────────────────────────────────────
def _lppls_path(n=300, tc_extra=20, m=0.5, w=7.5, B=-0.6, C=0.04, noise=0.002, seed=0):
    rng = np.random.default_rng(seed)
    tc = n - 1 + tc_extra
    tau = tc - np.arange(n)
    lp = 3 + B * tau ** m / (tc ** m) * 3 + C * tau ** m / (tc ** m) * 3 * np.cos(w * np.log(tau))
    return lp + rng.normal(0, noise, n)


def test_lppls_detects_a_synthetic_bubble_but_not_noise():
    lp = _lppls_path()
    fit = el.lppls_fit_window(lp)
    assert fit["B"] < 0 and fit["positive"]
    rng = np.random.default_rng(5)
    noise = np.cumsum(rng.normal(0, 0.03, 300))
    conf = el.lppls_confidence_at(noise, 299)
    conf_b = el.lppls_confidence_at(lp, 299, windows=(120, 160, 200, 240, 280))
    assert conf_b["pos"] > conf["pos"]


def test_lppls_series_has_no_look_ahead():
    p = _rw(700, seed=2)
    full = el.lppls_series(p, step=20, windows=(60, 90, 125))
    cut = p.index[500]
    part = el.lppls_series(p[p.index <= cut], step=20, windows=(60, 90, 125))
    common = part.dropna().index.intersection(full.dropna().index)
    common = common[common < part.dropna().index[-1]]  # the last partial point is computed at the cut
    assert len(common) > 5
    pd.testing.assert_frame_equal(full.loc[common], part.loc[common])


# ── 2 Fragility ──────────────────────────────────────────────────────
def test_permutation_entropy_extremes_and_rolling_matches_direct():
    assert el.permutation_entropy(np.arange(200.0)) == pytest.approx(0.0)
    rng = np.random.default_rng(0)
    x = rng.normal(size=20000)
    assert el.permutation_entropy(x) > 0.99
    s = pd.Series(rng.normal(size=400))
    roll = el.rolling_permutation_entropy(s, window=126)
    assert roll.iloc[300] == pytest.approx(el.permutation_entropy(s.values[175:301]))
    assert roll.iloc[:124].isna().all()


def test_kendall_trend():
    up = pd.Series(np.arange(50.0))
    assert el.kendall_trend(up, 20).iloc[-1] == pytest.approx(1.0)
    assert el.kendall_trend(-up, 20).iloc[-1] == pytest.approx(-1.0)


def test_fragility_is_point_in_time():
    p = _rw(1200, seed=8)
    full = el.fragility_frame(p)
    part = el.fragility_frame(p.iloc[:900])
    i = part.dropna().index
    assert len(i) > 50
    pd.testing.assert_frame_equal(full.loc[i], part.loc[i])


# ── 3 Hurst / DFA ────────────────────────────────────────────────────
def test_dfa_white_noise_vs_persistent():
    rng = np.random.default_rng(1)
    assert el.dfa_alpha(rng.normal(size=4000)) == pytest.approx(0.5, abs=0.07)
    e = rng.normal(size=4000)
    ar = np.zeros(4000)
    for i in range(1, 4000):
        ar[i] = 0.6 * ar[i - 1] + e[i]
    assert el.dfa_alpha(ar) > 0.6
    assert np.isnan(el.dfa_alpha(rng.normal(size=20)))


def test_rolling_dfa_point_in_time_and_momentum_outcome():
    p = _rw(900, seed=9)
    a = el.rolling_dfa(p).dropna()
    b = el.rolling_dfa(p.iloc[:700]).dropna()
    i = b.index[:-1]
    pd.testing.assert_series_equal(a.loc[i], b.loc[i])
    q = pd.Series(np.exp(np.arange(200) * 0.01), pd.bdate_range("2024-01-01", periods=200))
    mo = el.momentum_outcome(q, 63, 21)
    assert mo.iloc[100] == pytest.approx(0.21)  # uptrend → long → earns the next 21 days


# ── 4 Tails ──────────────────────────────────────────────────────────
def test_gpd_recovers_pareto_tail_and_var_consistency():
    rng = np.random.default_rng(0)
    from scipy.stats import genpareto
    x = genpareto.rvs(0.3, scale=1.0, size=20000, random_state=rng)
    fit = el.gpd_fit(x, q=0.9)
    assert fit["xi"] == pytest.approx(0.3, abs=0.08)
    v = el.gpd_var(fit, 0.99)
    assert el.gpd_tail_prob(fit, v) == pytest.approx(0.01, rel=1e-6)
    assert (x > v).mean() == pytest.approx(0.01, abs=0.003)


def test_kupiec():
    assert el.kupiec_pof(1000, 10, 0.01) == pytest.approx(1.0)
    assert el.kupiec_pof(1000, 40, 0.01) < 0.001


def test_tail_dependence_bounds():
    rng = np.random.default_rng(2)
    x = rng.normal(size=5000)
    td = el.tail_dependence(x, x)
    assert td["lower"] == pytest.approx(1.0) and td["upper"] == pytest.approx(1.0)
    ind = el.tail_dependence(x, rng.normal(size=5000), q=0.1)
    assert ind["lower"] == pytest.approx(0.1, abs=0.04) and ind["upper"] == pytest.approx(0.1, abs=0.04)
    # crash-together-only: y follows x on bad days only
    y = np.where(x < -1.2, x, rng.normal(size=5000))
    asym = el.tail_asym_bootstrap(x, y, n_boot=100)
    assert asym["asym"] > 0.4 and asym["ci"][0] > 0


def test_var_backtest_calibrated_on_t_noise():
    rng = np.random.default_rng(3)
    r = rng.standard_t(3, size=3000) * 0.02
    p = pd.Series(100 * np.exp(np.cumsum(r)), pd.bdate_range("2012-01-02", periods=3000))
    bt = el.var_backtest(p)
    assert bt["gpd_p"] > 0.01 and bt["normal_breaches"] > bt["gpd_breaches"]


# ── 5 Halving clock ──────────────────────────────────────────────────
def test_halving_phase():
    ph = el.halving_phase(date(2026, 10, 19))
    assert ph["halving"] == date(2024, 4, 20) and ph["days"] == 912
    assert el.halving_phase(date(2010, 1, 1)) is None


def test_halving_fold_uses_only_past_data():
    idx = pd.date_range("2012-01-01", "2026-10-19", freq="D")
    p = pd.Series(np.exp(np.linspace(0, 8, len(idx))), idx)
    fold = el.halving_fold(p, "2021-01-01")
    assert [r["halving"] for r in fold] == [date(2012, 11, 28), date(2016, 7, 9)]
    p2 = p.copy()
    p2[p2.index > "2021-01-01"] = 1.0                   # changing the future must not change the fold
    assert fold == el.halving_fold(p2, "2021-01-01")


# ── 6 Kelly ──────────────────────────────────────────────────────────
def test_kelly_fraction_known_answer_and_bounds():
    # Two-outcome bet: win +b with prob p, lose −a with prob q → f* = p/a − q/b
    r = np.array([1.0] * 60 + [-0.5] * 40)             # 0.6/0.5 − 0.4/1 = 0.8
    assert el.kelly_fraction(r) == pytest.approx(0.8)
    coin = np.array([0.2] * 60 + [-0.2] * 40)           # 0.6/0.2 − 0.4/0.2 = 1.0 (no leverage allowed)
    assert el.kelly_fraction(coin) == 1.0
    loser = np.array([0.1] * 40 + [-0.1] * 60)          # negative edge → hold none
    assert el.kelly_fraction(loser) == 0.0
    mild = np.array([0.5] * 52 + [-0.5] * 48)           # 0.52/0.5 − 0.48/0.5 = 0.08 → grid 0.05 or 0.10
    assert el.kelly_fraction(mild) in (0.05, 0.1)
    assert np.isnan(el.kelly_fraction(np.array([0.1, 0.2])))


def test_kelly_walkforward_uses_trailing_data_only():
    p = _rw(2500, seed=11)
    wf = el.kelly_walkforward(p)
    wf2 = el.kelly_walkforward(p.iloc[:2000])
    i = wf2["weights"].index
    pd.testing.assert_series_equal(wf["weights"].loc[i], wf2["weights"], check_freq=False)
    v = el.kelly_verdict(wf)
    assert v["verdict"] in (es.EDGE, es.NO_EDGE) and el.kelly_verdict(None)["verdict"] == es.INSUFFICIENT


def test_clean_drops_pre_miner_history():
    p = _rw(800, start="2016-06-01")
    assert el.clean(p, "RIOT").index[0] >= pd.Timestamp("2017-10-04")
    assert el.clean(p, "HUT").index[0] == p.index[0]
