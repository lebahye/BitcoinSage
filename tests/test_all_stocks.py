"""Every page that used to be RIOT-only now works for any ticker (facts per company; N/A when not on file)."""
from datetime import date

import numpy as np
import pandas as pd
import pytest

from utils import company_facts as cf

TICKERS = ["RIOT", "MARA", "CLSK", "HUT", "CIFR", "KEEL", "BITF", "WULF", "IREN", "CORZ", "BTDR", "BTBT", "MSTR", "NVDA"]


def test_every_fact_is_cited_dated_and_plausible():
    for t, c in cf.COMPANIES.items():
        for k, (v, as_of, src, note) in c["fields"].items():
            assert k in cf.FIELDS, (t, k)
            assert v is not None and v >= 0, (t, k)
            assert isinstance(as_of, date) and date(2026, 1, 1) <= as_of <= cf.LAST_VERIFIED, (t, k)
            lab, url = cf.SOURCES[src]
            assert url and url.startswith("https://"), (t, k)
        if c["fields"].get("btc_pledged"):
            assert c["fields"]["btc_pledged"][0] <= c["fields"]["btc_held"][0], t


def test_facts_table_and_na_for_every_ticker():
    for t in TICKERS:
        rows = cf.facts_table(t)
        assert len(rows) == len(cf.FIELDS)
        for r in rows:
            assert (r["Value"] == "N/A") == (r["As of"] == "—"), (t, r)
    assert all(r["Value"] == "N/A" for r in cf.facts_table("NVDA"))
    assert cf.coverage("NVDA") == "none" and cf.coverage("RIOT") == "partial"
    assert cf.get("BITF", "btc_held") == cf.get("KEEL", "btc_held")       # Bitfarms → Keel alias


def test_cash_debt_falls_back_to_yahoo_and_labels_it():
    yb = {"cash": 1e8, "total_debt": 2e8, "date": date(2026, 6, 30)}
    d = cf.cash_debt("MARA", yb)                                         # MARA: not on file → Yahoo
    assert d["cash_usd"] == (1e8, "Yahoo balance sheet 2026-06-30") and d["debt_usd"][0] == 2e8
    d = cf.cash_debt("CLSK", yb)                                         # CLSK: filing wins
    assert d["cash_usd"][0] == pytest.approx(202.601e6) and d["cash_usd"][1].startswith("filing")
    assert cf.cash_debt("NVDA", {})["cash_usd"] == (None, "N/A")


@pytest.mark.parametrize("t", TICKERS)
def test_sop_inputs_never_invent(t):
    d = cf.sop_inputs(t, {})
    assert d["btc_held"] == cf.value(t, "btc_held")
    assert d["lease_disclosed"] == (cf.alias(t) == "RIOT")
    if not d["lease_disclosed"]:
        assert d["lease_noi"] == 0
    for k in ("btc_held", "cash", "debt"):
        if d[k] is None:
            assert any(k.replace("btc_held", "bitcoin held") in m for m in d["missing"]), (t, k)


def test_miner_cost_only_where_cited():
    assert cf.miner_cost("RIOT")["incl_da"] == 90_631
    for t in ("MARA", "CLSK", "HUT", "NVDA", "MSTR"):
        assert cf.miner_cost(t) is None


def test_ciks_for_us_filers():
    for t in ("RIOT", "MARA", "CLSK", "HUT", "CIFR", "WULF", "IREN", "CORZ", "KEEL", "BTBT", "MSTR"):
        assert cf.cik(t) and len(cf.cik(t)) == 10 and cf.cik(t).isdigit(), t
    assert cf.cik("BTDR") is None and cf.cik("NVDA") is None


def _closes():
    rng = np.random.default_rng(3)
    days = pd.bdate_range("2025-09-01", periods=300)
    common = rng.normal(0, 0.03, len(days))
    cols = {t: 10 * np.exp(np.cumsum(common + rng.normal(0, 0.012, len(days))))
            for t in ["RIOT", "MARA", "CLSK", "HUT", "CIFR", "WULF", "IREN", "CORZ"]}
    cols["BTC-USD"] = 60000 * np.exp(np.cumsum(0.6 * common + rng.normal(0, 0.01, len(days))))
    return pd.DataFrame(cols, index=days)


@pytest.mark.parametrize("anchor", ["RIOT", "MARA", "CLSK", "IREN"])
def test_correlation_map_any_anchor(monkeypatch, anchor):
    from utils import riot_correlation as rc
    seen = []
    monkeypatch.setattr(rc, "fetch_daily_closes", lambda tickers, period: (seen.append(tickers), _closes())[1])
    d = rc.load_riot_correlations(anchor)
    assert d["ok"] and anchor not in set(d["table"]["ticker"])
    if anchor != "RIOT":
        assert "RIOT" in set(d["table"]["ticker"])                      # other stocks are compared with RIOT too
    assert d["divergence"] is not None and set(d["divergence"]["peers"]) <= set(d["table"]["ticker"])
    assert seen[0] == tuple(sorted(seen[0]))                             # one shared, cache-friendly download


@pytest.mark.parametrize("sym", ["RIOT", "MARA", "CLSK", "WULF", "NVDA"])
def test_verdict_valuation_rows_any_ticker(monkeypatch, sym):
    import components.stock_verdict as sv
    from utils import signal_hub
    import components.reflexivity_dashboard as rd
    sh = pd.Series([3.0e8, 3.3e8], index=pd.to_datetime(["2025-06-30", "2026-06-30"]))
    monkeypatch.setattr(signal_hub, "get_shares", lambda s: sh)
    monkeypatch.setattr(signal_hub, "get_balance", lambda s: {"cash": 5e8, "total_debt": 1e9, "date": date(2026, 6, 30)})
    monkeypatch.setattr(rd, "live_phase_and_edge", lambda s: (None, None, False))
    rows = {r.key: r for r in sv._reflexivity_rows(sym, 10.0, 100_000.0)}
    val, ms = rows["valuation"], rows["miner_stress"]
    if sym == "NVDA":
        assert val.lean is None and val.weight == 0 and "N/A" in val.reading
    if sym == "WULF":                                                    # AI host, lease income not disclosed
        assert val.weight == 0 and "context only" in val.reading
    if sym == "RIOT":
        assert val.weight > 0 and ms.weight > 0 and ms.lean is not None
    else:
        assert ms.lean is None and ms.weight == 0 and "N/A" in ms.reading


def test_pick_following_verdict(monkeypatch):
    import components.stock_verdict as sv

    class SS(dict):
        __getattr__ = dict.get
    ss = SS()
    monkeypatch.setattr(sv.st, "session_state", ss)

    class C:
        def selectbox(self, label, opts, key, **kw):
            return ss[key]
    opts = ["RIOT", "MARA", "CLSK"]
    assert sv.pick_following_verdict(C(), "x", opts, "k", "RIOT") == "RIOT"
    ss["verdict_symbol_saved"] = "MARA"
    assert sv.pick_following_verdict(C(), "x", opts, "k", "RIOT") == "MARA"     # follows the Verdict
    ss["k"] = "CLSK"                                                            # user picks on the page
    assert sv.pick_following_verdict(C(), "x", opts, "k", "RIOT") == "CLSK"     # …and it sticks
    del ss["k"]                                                                 # section switch drops widget state
    assert sv.pick_following_verdict(C(), "x", opts, "k", "RIOT") == "CLSK"
    ss["verdict_symbol_saved"] = "NVDA"                                         # not in this page's list
    assert sv.pick_following_verdict(C(), "x", opts, "k", "RIOT") == "CLSK"


def test_edge_lab_dropdown_has_all_miners_and_holdings():
    from components.edge_lab import stock_choices
    from components.personal_portfolio import DEFAULT_POSITIONS
    from utils.tickers import MINING_STOCKS, resolve
    ch = stock_choices()
    assert ch[0] == "RIOT" and len(ch) == len(set(ch))
    for t in list(MINING_STOCKS) + ["MARA", "CLSK", "HUT", "WULF", "IREN", "CORZ", "BTDR", "CIFR"]:
        assert resolve(t) in ch, t
    for t in DEFAULT_POSITIONS:
        assert resolve(t) in ch, t
