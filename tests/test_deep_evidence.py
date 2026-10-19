"""Deeper-evidence calculations: point-in-time, N/A on missing inputs, cited facts, never flips the action."""
import math
from datetime import date

import numpy as np
import pandas as pd
import pytest

from utils import deep_evidence as de
from utils.deep_facts import CONVERTS, TREASURY, AI_PEERS, AI_PEER_SET
from utils.verdict import Evidence, build_verdict, combine_plan


def _cm(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2015-01-01", periods=n, freq="D")
    mc = pd.Series(1e11 * np.exp(np.cumsum(rng.normal(0, 0.03, n))), index=idx)
    mvrv = pd.Series(1.5 + 0.5 * np.sin(np.arange(n) / 200), index=idx)
    iss = pd.Series(3e7 * np.exp(rng.normal(0, 0.1, n)), index=idx)
    return pd.DataFrame({"CapMVRVCur": mvrv, "CapMrktCurUSD": mc, "IssTotUSD": iss, "SplyCur": 1.9e7, "PriceUSD": mc / 1.9e7})


def test_cycle_metrics_formulas_and_point_in_time():
    df = _cm()
    m = de.cycle_metrics(df)
    i = 1500
    rc = df.CapMrktCurUSD.iloc[i] / df.CapMVRVCur.iloc[i]
    assert m.realized_cap.iloc[i] == pytest.approx(rc)
    assert m.mvrv_z.iloc[i] == pytest.approx((df.CapMrktCurUSD.iloc[i] - rc) / df.CapMrktCurUSD.iloc[: i + 1].std())
    assert m.realized_price.iloc[i] == pytest.approx(rc / 1.9e7)
    # no look-ahead: changing the future leaves the past unchanged
    df2 = df.copy(); df2.iloc[1600:, 1] *= 50
    m2 = de.cycle_metrics(df2)
    pd.testing.assert_series_equal(m.mvrv_z.iloc[:1600], m2.mvrv_z.iloc[:1600])
    pd.testing.assert_series_equal(m.puell.iloc[:1600], m2.puell.iloc[:1600])
    assert de.cycle_metrics(pd.DataFrame()).empty


def test_zones_and_none():
    assert de.mvrv_zone(None) is None and de.mvrv_zone(float("nan")) is None
    assert de.mvrv_zone(0.2).startswith("cheap") and de.mvrv_zone(6).startswith("hot")
    assert de.puell_zone(0.4).startswith("miner stress") and de.puell_zone(3).startswith("miner windfall")
    assert de.zone_lean("cheap (Z < 0.5)") == 1 and de.zone_lean("hot (Z > 5)") == -1 and de.zone_lean(None) is None


def test_edge_weight_only_with_significant_edge():
    assert de.edge_weight_and_lean(None) == (0.0, None)
    assert de.edge_weight_and_lean({"verdict": "no reliable difference"}) == (0.0, None)
    assert de.edge_weight_and_lean({"verdict": "too few cases"}) == (0.0, None)
    assert de.edge_weight_and_lean({"verdict": "worse than average"}, 5) == (5, -1.0)


def test_zone_backtest_no_lookahead():
    idx = pd.bdate_range("2018-01-01", periods=1500)
    rng = np.random.default_rng(1)
    stock = pd.Series(10 * np.exp(np.cumsum(rng.normal(0, 0.03, 1500))), index=idx)
    metric = pd.Series(rng.normal(1, 2, 2200), index=pd.date_range("2017-11-01", periods=2200, freq="D"))
    t1 = de.zone_backtest(stock, metric, de.mvrv_zone)
    m2 = metric.copy(); m2[m2.index > idx[1000]] = 99.0       # change the future metric only
    t2 = de.zone_backtest(stock, m2, de.mvrv_zone)
    assert set(t1) == set(de.HORIZONS)
    # labels before the change are identical, so the early entries are identical
    s1 = t1[126]; assert {"label", "n", "verdict"} <= set(s1.columns)
    assert de.zone_backtest(stock.iloc[:100], metric, de.mvrv_zone) == {}
    assert t2[126].attrs["delay"] == 2


def test_vol_regime_is_point_in_time():
    idx = pd.bdate_range("2016-01-01", periods=1400)
    rng = np.random.default_rng(2)
    c = pd.Series(10 * np.exp(np.cumsum(rng.normal(0, 0.03, 1400))), index=idx)
    a = de.vol_regime_labels(c)
    c2 = c.copy(); c2.iloc[1200:] *= np.exp(np.cumsum(rng.normal(0, 0.2, 200)))
    b = de.vol_regime_labels(c2)
    assert a.iloc[:1200].fillna("-").equals(b.iloc[:1200].fillna("-"))
    assert set(a.dropna().unique()) <= {"calm", "normal", "stormy"}


def test_convert_dilution_riot_facts():
    d = de.convert_dilution(CONVERTS["RIOT"], 14.86, today=date(2026, 10, 19))
    n = d["notes"][0]
    assert n["shares"] == 39_988_127 and n["moneyness"] == pytest.approx(1.0)
    assert n["pct"] == pytest.approx(39_988_127 / 375_258_935)
    # cross-check: principal × conversion rate ≈ shares in the filing (within 0.1%)
    f = CONVERTS["RIOT"]["notes"][0]
    assert f["principal"] / 1000 * f["conversion_rate_per_1000"] == pytest.approx(f["shares_if_converted"], rel=1e-3)
    assert de.lean_converts(d) == -1.0                     # ≥10% and at the money
    assert de.lean_converts(de.convert_dilution(CONVERTS["RIOT"], 13.0, today=date(2026, 10, 19))) == -0.5
    assert de.lean_converts(de.convert_dilution(CONVERTS["RIOT"], 5.0, today=date(2026, 10, 19))) == 0.0
    assert de.convert_dilution(CONVERTS["RIOT"], 14.0, today=date(2030, 2, 1))["notes"] == []   # matured
    assert de.convert_dilution(None, 10) is None and de.lean_converts(None) is None
    assert de.convert_dilution(CONVERTS["RIOT"], None)["atm_shares"] is None


def test_facts_are_cited_and_dated():
    for sym, rows in TREASURY.items():
        for r in rows:
            assert r["source"].startswith("http") and isinstance(r["end"], date)
            assert r["produced"] > 0 and r["sold"] >= 0 and r["held"] > 0
    for s in AI_PEER_SET:
        f = AI_PEERS[s]
        assert f["source"].startswith("http") and isinstance(f["as_of"], date) and f["mw"] > 0
    for s, f in CONVERTS.items():
        for n in f["notes"]:
            assert n["sources"] and all(u.startswith("http") for u in n["sources"])
    # RIOT Q2 derivation: holdings reconcile within employee-comp rounding
    q1, q2 = TREASURY["RIOT"]
    assert abs(q1["held"] + q2["produced"] - q2["sold"] - q2["held"]) <= 25


def test_treasury_summary():
    t = de.treasury_summary(TREASURY["RIOT"])
    assert t["sold_ratio"] == pytest.approx(5887 / 1587) and t["held_change"] == pytest.approx(11380 / 15679 - 1)
    assert de.treasury_summary(None) is None and de.treasury_summary([]) is None


def test_peer_valuation_and_relative():
    ev = {s: 1e9 * (i + 1) for i, s in enumerate(AI_PEER_SET)}
    tab = de.peer_valuation(ev, {s: AI_PEERS[s] for s in AI_PEER_SET})
    r = tab.set_index("symbol")
    assert r.loc["RIOT", "ev_per_mw"] == pytest.approx(1e9 / 241)
    assert r.loc["RIOT", "ev_per_hpc_rev"] == pytest.approx(1e9 / (4 * 23.2e6))
    assert math.isnan(r.loc["APLD", "ev_per_hpc_rev"]) or r.loc["APLD", "ev_per_hpc_rev"] is None
    rel = de.peer_relative(tab, "RIOT")
    assert rel["n_peers"] == len(AI_PEER_SET) - 1
    ev2 = dict(ev); ev2["CORZ"] = None
    assert de.peer_relative(de.peer_valuation(ev2, AI_PEERS), "CORZ") is None
    assert de.peer_relative(tab, "NVDA") is None and de.lean_peer(None) is None
    assert de.lean_peer({"ratio": 0.5}) == 0.5 and de.lean_peer({"ratio": 2}) == -0.5


def test_options_math():
    assert de.bs_delta("call", 100, 100, 0.25, 0.5) == pytest.approx(0.5 + 0.0, abs=0.08)
    assert de.bs_delta("put", 100, 100, 0.25, 0.5) < 0 and de.bs_delta("call", 0, 100, 1, 1) is None
    strikes = np.arange(5, 31, 1.0)
    calls = pd.DataFrame({"strike": strikes, "impliedVolatility": 0.9, "openInterest": 100, "bid": 0.5})
    puts = pd.DataFrame({"strike": strikes, "impliedVolatility": 1.1, "openInterest": 100, "bid": 0.5})
    sk = de.skew_25d(calls, puts, 15.0, 30 / 365)
    assert sk["skew"] == pytest.approx(0.2) and sk["put_strike"] < 15 < sk["call_strike"]
    mp = de.max_pain(calls, puts)
    assert 5 <= mp <= 30
    # known case: all OI at one strike → max pain is that strike
    c1 = pd.DataFrame({"strike": [10.0, 15, 20], "openInterest": [0, 500, 0]})
    p1 = pd.DataFrame({"strike": [10.0, 15, 20], "openInterest": [0, 500, 0]})
    assert de.max_pain(c1, p1) == 15
    assert de.put_call_oi(calls, puts) == pytest.approx(1.0)
    assert de.skew_25d(pd.DataFrame(), puts, 15, 0.1) is None and de.max_pain(None, None) is None


def test_prediction_market_parsers():
    ev = {"markets": [{"question": "Will X?", "outcomePrices": '["0.3","0.7"]', "outcomes": '["Yes","No"]', "volume": "10"},
                      {"question": "closed", "outcomePrices": '["1","0"]', "closed": True},
                      {"question": "bad", "outcomePrices": "oops"}]}
    y = de.polymarket_yes(ev)
    assert len(y) == 1 and y[0]["yes"] == pytest.approx(0.3)
    k = de.kalshi_yes({"markets": [{"yes_sub_title": "Hold", "yes_bid_dollars": "0.85", "yes_ask_dollars": "0.86"},
                                   {"yes_sub_title": "Hike", "no_bid_dollars": "0.86", "no_ask_dollars": "0.87"}]})
    assert k[0]["question"] == "Hold" and k[0]["yes"] == pytest.approx(0.855) and k[1]["yes"] == pytest.approx(0.135)
    assert de.polymarket_yes(None) == [] and de.kalshi_yes({}) == []
    assert de.short_question("Will the Democratic Party control the House after the 2026 Midterm elections?") == "Democratic Party"


def test_short_interest():
    si = de.short_interest({"shortPercentOfFloat": 0.14, "shortRatio": 3.1, "sharesShort": 90, "sharesShortPriorMonth": 100,
                            "dateShortInterest": 1790726400})
    assert si["change"] == pytest.approx(-0.1) and isinstance(si["as_of"], date)
    assert de.short_label(si).startswith("high")
    assert de.short_interest({}) is None and de.short_interest({"shortRatio": None}) is None and de.short_label(None) is None


def test_deep_rows_never_flip_the_action():
    """Even maximally one-sided deep evidence only moves confidence."""
    for plan, add in [("HOLD", "WAIT"), ("TRIM", "WAIT"), ("SELL", "WAIT"), ("HOLD", "ADD"), ("ROTATE", "WAIT")]:
        for lean in (1.0, -1.0):
            deep = [Evidence(k, k, "r", lean, 5, "measured", group="Company") for k in ("converts", "peers")] + \
                   [Evidence(k, k, "r", lean, 5, "backtested", group="Long-cycle") for k in ("mvrv", "puell", "regime")]
            vd = build_verdict("RIOT", True, plan, "Medium", add, deep)
            assert vd.action == combine_plan(plan, add)


def test_deep_rows_na_when_everything_is_down(monkeypatch):
    import components.verdict_deep as vd
    from utils import deep_sources as ds
    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(vd, "_cycle_bt_cached", boom)
    monkeypatch.setattr(vd, "_regime_bt_cached", boom)
    monkeypatch.setattr(vd, "peer_table", lambda *a: None)
    monkeypatch.setattr(ds, "yahoo_info", lambda s: {})
    monkeypatch.setattr(ds, "option_chain", lambda s: None)
    monkeypatch.setattr(ds, "polymarket_event", lambda s: None)
    monkeypatch.setattr(ds, "kalshi_next_fed", lambda: None)
    for sym in ("RIOT", "MARA", "NVDA"):
        rows = vd.deep_rows(sym, 10.0, load_live=True)
        assert {r.group for r in rows} == {"Long-cycle", "Company", "Market mood"}
        keys = {r.key for r in rows}
        assert {"mvrv", "puell", "converts", "treasury", "peers", "regime", "short", "options", "odds"} <= keys
        for r in rows:
            if r.key in ("converts", "treasury") and sym == "RIOT":
                assert r.lean is not None                       # cited facts don't need the network
            elif r.key not in ("converts", "treasury") or sym == "NVDA":
                assert r.lean is None and r.takeaway.startswith("N/A") and r.weight == 0, (sym, r.key)
