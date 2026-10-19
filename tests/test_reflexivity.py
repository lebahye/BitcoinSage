import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from utils import reflexivity as rx
from utils import edgar


def _walk(n=900, seed=0, beta=1.2, start="2018-01-02"):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(start, periods=n)
    lb = np.cumsum(rng.normal(0.0005, 0.03, n))
    ls = 2 + beta * lb + np.cumsum(rng.normal(0, 0.02, n))
    return pd.Series(np.exp(ls), idx), pd.Series(np.exp(lb + 10), idx)


# ── basket ─────────────────────────────────────────────────────────────
def test_equal_weight_index_uses_returns_not_prices():
    idx = pd.bdate_range("2024-01-01", periods=3)
    df = pd.DataFrame({"CHEAP": [10.0, 11.0, 12.1], "DEAR": [100.0, 100.0, 100.0]}, idx)
    ew = rx.equal_weight_index(df)
    assert ew.iloc[0] == 100 and ew.iloc[1] == pytest.approx(105.0) and ew.iloc[2] == pytest.approx(110.25)
    # a price average would be dominated by the $100 stock (+0.9%), not +5%
    assert (df.mean(axis=1).iloc[1] / df.mean(axis=1).iloc[0] - 1) < 0.01


def test_rolling_beta_is_dated_on_last_included_day():
    s, b = _walk(200)
    beta = rx.rolling_beta(s, b, 30)
    sr, br = s.pct_change(), b.pct_change()
    d = beta.index[-1]
    w_s, w_b = sr.loc[:d].iloc[-30:], br.loc[:d].iloc[-30:]
    assert beta.iloc[-1] == pytest.approx(np.cov(w_s, w_b)[0, 1] / w_b.var())


# ── index & phase ──────────────────────────────────────────────────────
def test_coupling_index_bounds_and_na():
    assert rx.coupling_index(1.0, 3.0, 0.1, 0.1)["index"] == 100
    assert rx.coupling_index(-0.5, -1.0, 0.1, -0.1)["index"] == 0      # negative corr/beta are not "amplification"
    assert rx.coupling_index(0.5, 1.5, 0.001, 0.1)["alignment"] == 50   # tiny move = undecided, not 0/100
    assert rx.coupling_index(float("nan"), 1, 0.1, 0.1) is None
    assert rx.coupling_index(None, 1, 0.1, 0.1) is None


@pytest.mark.parametrize("b,m,c,exp", [(0.1, 0.1, 0.8, "boom"), (-0.1, -0.1, 0.8, "bust"), (0.05, -0.2, 0.3, "lag"),
                                       (-0.05, 0.2, 0.3, "lead"), (0.01, 0.02, 0.9, "none"), (0.1, 0.1, 0.2, "none")])
def test_detect_phase(b, m, c, exp):
    assert rx.detect_phase(b, m, c) == exp
    assert exp in rx.PHASES


def test_detect_phase_missing_is_none():
    assert rx.detect_phase(float("nan"), 0.1, 0.5) is None


# ── backtest: point-in-time & non-overlapping ──────────────────────────
def test_phase_frame_has_no_lookahead():
    s, b = _walk(700)
    cut = s.index[500]
    full = rx.phase_frame(s, b)
    s2, b2 = s.copy(), b.copy()
    s2[s2.index > cut] *= 7
    b2[b2.index > cut] *= 0.2
    alt = rx.phase_frame(s2, b2)
    cols = ["btc_mom", "miner_mom", "corr", "beta", "index"]
    pd.testing.assert_frame_equal(full.loc[:cut, cols], alt.loc[:cut, cols])
    assert full.loc[:cut, "phase"].fillna("-").equals(alt.loc[:cut, "phase"].fillna("-"))


def test_non_overlapping_entries():
    labs = pd.Series(["a"] * 10 + ["b"] * 3 + ["a"] * 10)
    e = rx.non_overlapping_entries(labs, 5)
    assert e["a"] == [0, 5, 13, 18] and e["b"] == [10]
    for pos in e.values():
        assert all(j - i >= 5 for i, j in zip(pos, pos[1:]))


def test_backtest_acts_next_day_and_uses_only_full_windows():
    idx = pd.bdate_range("2020-01-01", periods=12)
    price = pd.Series([100, 100, 200, 200, 200, 200, 200, 200, 200, 200, 200, 200.0], idx)
    labels = pd.Series(["x"] + [None] * 11, idx, dtype=object)
    t = rx.backtest_labels(price, labels, horizon=3, delay=1)
    # label at day 0 is acted on at day 1 (100) and held 3 days -> day 4 (200): +100%
    assert t.loc[t.label == "x", "typical_return"].iloc[0] == pytest.approx(1.0)
    t0 = rx.backtest_labels(price, pd.Series([None] * 10 + ["late", "late"], idx, dtype=object), horizon=3)
    assert "late" not in set(t0.label)          # no forward window -> excluded, never padded


def test_backtest_finds_a_planted_edge_and_not_noise():
    rng = np.random.default_rng(3)
    n = 4000
    idx = pd.bdate_range("2000-01-03", periods=n)
    lab = pd.Series(np.where(rng.random(n) < 0.5, "good", "bad"), idx, dtype=object)
    r = rng.normal(0, 0.01, n) + np.where(lab.shift(1).fillna("bad") == "good", 0.004, -0.004)
    price = pd.Series(100 * np.exp(np.cumsum(r)), idx)
    t = rx.backtest_labels(price, lab, horizon=1, delay=0)
    # planted: returns on the day AFTER a 'good' label are higher
    assert rx.has_edge(t)
    noise = pd.Series(np.where(rng.random(n) < 0.5, "p", "q"), idx, dtype=object)
    t2 = rx.backtest_labels(pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), idx), noise, horizon=20)
    assert not rx.has_edge(t2) or (t2.verdict != "no reliable difference").sum() <= 1


# ── mining economics ───────────────────────────────────────────────────
def test_subsidy_by_height_and_date():
    assert rx.subsidy_at_height(0) == 50
    assert rx.subsidy_at_height(839_999) == 6.25 and rx.subsidy_at_height(840_000) == 3.125
    assert rx.subsidy_at_height(1_050_000) == 1.5625
    assert rx.subsidy_on("2019-01-01") == 12.5 and rx.subsidy_on("2024-04-19") == 6.25 and rx.subsidy_on("2024-04-20") == 3.125
    assert rx.subsidy_on("2028-05-01", next_halving=date(2028, 4, 11)) == 1.5625


def test_power_breakeven_formula_and_halving_doubles_it():
    d = 1.4e14
    be = rx.network_power_breakeven(d, 20, 0.05, 3.125)
    ths = d * 2 ** 32 / 600 / 1e12
    assert be == pytest.approx(ths * 20 * 86400 / 3.6e6 * 0.05 / (144 * 3.125))
    assert rx.network_power_breakeven(d, 20, 0.05, 1.5625) == pytest.approx(2 * be)
    assert rx.network_power_breakeven(0, 20, 0.05, 3.125) is None


def test_hashprice():
    hp = rx.hashprice_usd_per_ph_day(80_000, 1e21, 3.125)
    assert hp == pytest.approx(144 * 3.125 / 1e6 * 80_000)
    assert rx.hashprice_usd_per_ph_day(80_000, 0, 3.125) is None


def test_difficulty_adjusted_cost():
    assert rx.difficulty_adjusted_cost(50_000, 1.0, 1.1) == pytest.approx(55_000)
    assert rx.difficulty_adjusted_cost(50_000, None, 1.1) is None


def test_trailing_percentile_is_point_in_time():
    s = pd.Series(np.arange(300, dtype=float))
    p = rx.percentile_rank_trailing(s, 100)
    s2 = s.copy()
    s2.iloc[200:] = -1
    p2 = rx.percentile_rank_trailing(s2, 100)
    assert p.iloc[:200].equals(p2.iloc[:200])


# ── sum of parts ───────────────────────────────────────────────────────
def test_annuity_pv():
    assert rx.annuity_pv(100, 1, 0.1) == pytest.approx(100 / 1.1)
    assert rx.annuity_pv(100, 2, 0.0) == 200
    assert rx.annuity_pv(100, 1, 0.1, start_in_years=1) == pytest.approx(100 / 1.1 / 1.1)


def test_sum_of_parts_adds_up():
    r = rx.sum_of_parts(price=10, shares=100, btc_price=50_000, btc_held=0.02, cash=200, debt=300,
                        lease_noi_per_year=100, lease_years=2, lease_start_years=0, discount=0.0,
                        build_cost_remaining=50, mining_value=25, other_value=5, btc_pledged=0.01)
    assert r["parts"]["Bitcoin held"] == 1000
    assert r["total"] == pytest.approx(1000 + 200 + 200 - 50 + 25 + 5 - 300)
    assert r["market_cap"] == 1000 and r["ratio"] == pytest.approx(1000 / r["total"])
    assert r["pledged_value"] == 500 and r["btc_only_mnav"] == 1.0
    assert rx.sum_of_parts(0, 100, 1, 1, 0, 0, 0, 1, 0, 0.1) is None


# ── dilution & loops ───────────────────────────────────────────────────
def test_share_growth_and_issuance_link():
    idx = pd.date_range("2020-01-01", "2026-01-01", freq="QS")
    sh = pd.Series(100 * 1.2 ** (np.arange(len(idx)) / 4), idx)
    assert rx.share_growth(sh, 1) == pytest.approx(0.2, abs=0.01)
    px = pd.Series(np.linspace(10, 20, len(idx)), idx)
    q = rx.quarterly_issuance_link(px, sh)
    assert {"ret", "issue_next", "rolling_corr"} <= set(q.columns)
    assert (q.issue_next > 0).all()


def test_edgar_parser_and_graceful_failure():
    sub = {"cik": "1167419", "name": "Riot", "filings": {"recent": {
        "form": ["8-K", "424B5", "10-Q", "S-3ASR"], "filingDate": ["2026-10-01", "2026-09-01", "2026-08-10", "2025-01-01"],
        "accessionNumber": ["0001-26-1", "0001-26-2", "0001-26-3", "0001-25-4"],
        "primaryDocument": ["a.htm", "b.htm", "c.htm", "d.htm"]}}}
    f = edgar.parse_offering_filings(sub)
    assert [x["form"] for x in f] == ["424B5", "S-3ASR"]
    assert f[0]["url"] == "https://www.sec.gov/Archives/edgar/data/1167419/0001262/b.htm"
    assert edgar.offering_filings(None)["available"] is False


def test_riot_facts_are_cited():
    from utils.riot_facts import Q2_2026, FACT_SOURCES
    assert Q2_2026["url"].startswith("https://") and Q2_2026["btc_pledged"] < Q2_2026["btc_held"]
    for v in FACT_SOURCES.values():
        assert v["url"].startswith("https://") and len(v["date"]) == 10
