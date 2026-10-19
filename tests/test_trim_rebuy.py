"""Trim & Rebuy backtester: wash sales, holding periods, no look-ahead, determinism, timeouts."""
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from utils import tax_ny as tx
from utils import trim_rebuy as tr

P = tx.TaxProfile(other_income=100_000)


def _led(basis=10.0, shares=100, acquired=date(2024, 1, 2)):
    led = tr.Ledger(P)
    led._seq = 1
    led.lots.append(tr.Lot(1, shares, shares * basis, acquired, acquired))
    return led


def _ohlc(close, idx=None):
    idx = idx if idx is not None else pd.bdate_range("2018-01-01", periods=len(close))
    c = pd.Series(np.asarray(close, float), index=idx)
    return pd.DataFrame({"Open": c, "High": c * 1.01, "Low": c * 0.99, "Close": c, "Volume": 1e6})


# ── wash sales ─────────────────────────────────────────────────────────
def test_wash_sale_rebuy_within_30_days_disallows_and_moves_loss():
    led = _led(acquired=date(2026, 1, 2))
    led.sell(date(2026, 3, 2), 8.0, 100, cost=0)              # $200 short-term loss
    led.buy(date(2026, 3, 20), 7.0, shares=100, cost=0)       # 18 days later → wash sale
    assert led.disallowed == pytest.approx(200)
    assert led.realized[2026] == [pytest.approx(0), 0.0]       # loss not deductible now
    lot = led.lots[0]
    assert lot.basis == pytest.approx(900)                      # $700 + $200 disallowed
    assert lot.acquired == date(2026, 3, 20) - timedelta(days=(date(2026, 3, 2) - date(2026, 1, 2)).days)
    led.sell(date(2026, 5, 1), 9.0, 100, cost=0)               # proceeds 900 = adjusted basis → no gain
    assert led.realized[2026][0] == pytest.approx(0)


def test_partial_replacement_disallows_proportionally():
    led = _led()
    led.sell(date(2026, 3, 2), 8.0, 100, cost=0)
    led.buy(date(2026, 3, 10), 8.0, shares=40, cost=0)
    assert led.disallowed == pytest.approx(80)                 # 40 of 100 shares replaced
    assert led.realized[2026][1] == pytest.approx(-120)        # long-term (held > 1 year)


def test_replacement_bought_before_the_sale_also_counts():
    led = _led()
    led.buy(date(2026, 2, 20), 8.0, shares=50, cost=0)         # bought 10 days BEFORE the loss sale
    led.sell(date(2026, 3, 2), 8.0, 100, cost=0)               # FIFO sells the old $10 lot
    assert led.disallowed == pytest.approx(100)
    assert led.lots[0].basis == pytest.approx(500)


def test_no_wash_sale_after_31_days_or_in_ira():
    led = _led()
    led.sell(date(2026, 3, 2), 8.0, 100, cost=0)
    led.buy(date(2026, 4, 2), 7.0, shares=100, cost=0)         # 31 days
    assert led.disallowed == 0
    ira = tr.Ledger(tx.TaxProfile(account="ira"))
    ira.lots.append(tr.Lot(1, 100, 1000, date(2026, 1, 2), date(2026, 1, 2)))
    ira.sell(date(2026, 3, 2), 8.0, 100, cost=0)
    ira.buy(date(2026, 3, 5), 7.0, shares=100, cost=0)
    assert ira.disallowed == 0


def test_holding_period_resets_on_rebuy_and_fifo_vs_specific():
    led = _led(basis=5.0, acquired=date(2020, 1, 2))
    led.sell(date(2026, 3, 2), 10.0, 50, cost=0)
    assert led.realized[2026][1] == pytest.approx(250)         # old lot: long-term
    led.buy(date(2026, 3, 10), 9.0, shares=50, cost=0)
    led.sell(date(2026, 6, 1), 10.0, 75, cost=0)               # FIFO: 50 old (LT) then 25 new (ST)
    assert led.realized[2026][0] == pytest.approx(25)
    spec = _led(basis=5.0, acquired=date(2020, 1, 2))
    spec.method = "specific"
    spec.buy(date(2026, 3, 10), 9.0, shares=50, cost=0)
    spec.sell(date(2026, 6, 1), 10.0, 50, cost=0)              # highest cost first → the $9 lot, short-term
    assert spec.realized[2026] == [pytest.approx(50), 0.0]


def test_ledger_settles_3000_limit_and_carryforward():
    led = _led(basis=100.0, acquired=date(2020, 1, 2))
    led.sell(date(2026, 3, 2), 50.0, 100, cost=0)              # $5,000 long-term loss
    led.settle_year(2026, date(2026, 12, 31), 50.0)
    assert led.carry.lt == pytest.approx(2_000)
    assert led.taxes[2026] < 0 and led.tax_shares < 0          # a refund buys shares


# ── rules and simulation ──────────────────────────────────────────────
def _random_walk(n=1500, seed=3):
    rng = np.random.default_rng(seed)
    return 10 * np.exp(np.cumsum(rng.normal(0.0004, 0.04, n)))


def test_no_look_ahead_future_prices_do_not_change_past_trips():
    px = _random_walk()
    df = _ohlc(px)
    k = 1000
    alt = px.copy()
    alt[k:] *= np.linspace(1, 3, len(alt) - k)                 # rewrite the future
    for r in tr.RULES:
        if r.family == "earnings":
            continue
        a = [t for t in tr.generate_trips(r, df) if t[1] < k]
        b = [t for t in tr.generate_trips(r, _ohlc(alt, df.index)) if t[1] < k]
        assert a == b, r.key


def test_signal_executes_on_the_next_close():
    px = np.r_[np.full(60, 10.0), 14.0, 14.0, np.full(40, 10.0)]
    df = _ohlc(px)
    trips = tr.generate_trips(tr.RULE_BY_KEY["A1"], df)
    assert trips and trips[0][0] == 61                         # stretch seen at bar 60, sold at bar 61


def test_rebuy_timeout_is_enforced():
    px = 10 * np.exp(np.linspace(0, 3, 600))                   # never reverts
    df = _ohlc(px)
    for r in tr.RULES:
        if r.family == "earnings":
            continue
        for s, b in tr.generate_trips(r, df):
            assert b - s <= r.timeout, r.key


def test_flat_price_costs_only_and_good_trim_gains_shares():
    df = _ohlc(np.full(300, 10.0))
    ira = tx.TaxProfile(account="ira")
    res = tr.simulate(df["Close"], [(50, 60), (100, 120)], 0.25, ira)
    assert -0.001 < res["share_gain_pct"] < 0                  # only the 0.05%/side cost
    px = np.r_[np.full(50, 10.0), np.full(20, 12.0), np.full(50, 9.0)]
    res = tr.simulate(pd.Series(px, index=pd.bdate_range("2020-01-01", periods=len(px))), [(55, 80)], 0.25, ira)
    assert res["share_gain"] > 0
    assert res["share_gain"] == pytest.approx(250 * 12 * (1 - tr.COST) / (9 * (1 + tr.COST)) - 250)


def test_evaluate_is_deterministic_and_verdict_vocabulary():
    df = _ohlc(_random_walk(1200, 5))
    r1 = tr.evaluate_rule(tr.RULE_BY_KEY["B1"], df, P, n_random=30)
    r2 = tr.evaluate_rule(tr.RULE_BY_KEY["B1"], df, P, n_random=30)
    assert r1["full"]["p_random"] == r2["full"]["p_random"]
    assert r1["full"]["post"]["share_eq"] == r2["full"]["post"]["share_eq"]
    assert r1["verdict"] in (tr.EDGE, tr.NO_EDGE, tr.INSUFFICIENT)


def test_earnings_rule_without_dates_is_insufficient():
    df = _ohlc(_random_walk(800))
    res = tr.evaluate_rule(tr.RULE_BY_KEY["E1"], df, P, earnings=[], n_random=10)
    assert res["full"]["n_trips"] == 0 and res["verdict"] == tr.INSUFFICIENT


def test_reaction_day_after_close_is_next_session():
    idx = pd.bdate_range("2025-01-06", periods=10)
    after = pd.Timestamp("2025-01-07 16:05", tz="America/New_York")
    before = pd.Timestamp("2025-01-07 08:00", tz="America/New_York")
    assert tr.reaction_days(idx, [after]) == [2]
    assert tr.reaction_days(idx, [before]) == [1]


def test_random_baseline_keeps_count_and_lengths():
    rng = np.random.default_rng(0)
    trips = [(100, 110), (300, 330), (600, 605)]
    rt = tr.random_trips(trips, 0, 1000, rng)
    assert sorted(b - s for s, b in rt) == sorted(b - s for s, b in trips)


def test_black_scholes_and_delta_strike():
    from math import log, sqrt
    from statistics import NormalDist
    K = tr.strike_for_delta(100, 35 / 365, 0.8, 0.25)
    d1 = (log(100 / K) + (0.04 + 0.32) * 35 / 365) / (0.8 * sqrt(35 / 365))
    assert NormalDist().cdf(d1) == pytest.approx(0.25, abs=1e-9)
    assert tr.bs_call(100, 100, 1.0, 0.2, r=0.04) == pytest.approx(9.925, abs=0.01)   # textbook value
    assert 0 < tr.bs_call(100, K, 35 / 365, 0.8) < 10


def test_harvest_now_uses_users_basis():
    h = tr.harvest_now(1_000, 14.0, 18.22, P, long_term=True)
    assert h["loss"] == pytest.approx(4_220)
    assert h["saving_now"] == pytest.approx(3_000 * (0.22 + 0.059 + 0.03876))
    assert h["carry"] == pytest.approx(1_220)
    assert tr.harvest_now(1_000, 20.0, 18.22, P)["saving_now"] == 0


def test_tlh_waits_31_days_and_avoids_wash_sale():
    idx = pd.bdate_range("2020-01-01", periods=400)
    c = pd.Series(np.r_[np.linspace(10, 7, 200), np.full(200, 7.0)], index=idx)
    peer = pd.DataFrame({"PEER": c * 2 + np.sin(np.arange(400))}, index=idx)
    r = tr.simulate_tlh(c, peer, P)
    assert r["swaps"] >= 1 and r["harvested"] > 0
    assert r["after_tax_liq"] is not None
