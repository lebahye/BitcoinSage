"""Every tab must compute the SAME indicator values from the same prices.

Before the shared hub, the same RIOT closes produced RSI 27 on Trade Signals / My Plan
and RSI 11 on 'AI Predictions' / Technical Analysis (simple-average vs Wilder RSI).
"""
import numpy as np
import pandas as pd
import pytest

from utils import indicators as ind
from utils.holding_advisor import compute_facts, rsi_wilder
from utils.signal_hub import snapshot_from_ohlcv, reconcile


def _ohlcv(n=400, seed=7, drift=-0.002):
    rng = np.random.default_rng(seed)
    close = 20 * np.exp(np.cumsum(rng.normal(drift, 0.04, n)))
    idx = pd.bdate_range("2024-01-01", periods=n)
    hi = close * (1 + rng.uniform(0, 0.03, n)); lo = close * (1 - rng.uniform(0, 0.03, n))
    return pd.DataFrame({"Open": close, "High": hi, "Low": lo, "Close": close,
                         "Volume": rng.integers(1_000_000, 5_000_000, n).astype(float)}, index=idx)


def test_rsi_identical_across_engines(monkeypatch):
    h = _ohlcv()
    ref = ind.rsi(h["Close"])
    # My Plan
    assert compute_facts(h["Close"])["rsi14"] == pytest.approx(ref, abs=1e-9)
    assert rsi_wilder(h["Close"]) == pytest.approx(ref, abs=1e-9)
    # Trade Signals
    from utils.trade_signal_engine import TradeSignalEngine
    assert TradeSignalEngine()._calc_rsi(h["Close"]) == pytest.approx(ref, abs=1e-9)
    # Technical Analysis tab
    from components.advanced_ta_dashboard import AdvancedTADashboard
    assert AdvancedTADashboard()._calculate_rsi(h["Close"]) == pytest.approx(ref, abs=1e-9)
    # Next-Mover ranking (reads bars through the hub)
    import utils.signal_hub as hub
    monkeypatch.setattr(hub, "get_ohlcv", lambda s, period=None: h)
    from utils.next_mover_engine import NextMoverEngine
    eng = NextMoverEngine.__new__(NextMoverEngine)
    eng.mining_stocks = ["RIOT"]
    tech = eng.analyze_technical_setup()
    assert tech["RIOT"]["rsi"] == pytest.approx(ref, abs=1e-9)
    # Shared snapshot
    assert snapshot_from_ohlcv(h)["rsi14"] == pytest.approx(ref, abs=1e-9)


def test_rsi_series_last_equals_scalar():
    h = _ohlcv()
    assert ind.rsi_series(h["Close"]).iloc[-1] == pytest.approx(ind.rsi(h["Close"]), abs=1e-9)


def test_macd_identical_trade_signals_vs_shared():
    h = _ohlcv()
    from utils.trade_signal_engine import TradeSignalEngine
    _, _, hist_now, hist_prev = TradeSignalEngine()._calc_macd(h["Close"])
    m = ind.macd(h["Close"])
    assert hist_now == pytest.approx(m["hist"]) and hist_prev == pytest.approx(m["hist_prev"])


def test_trade_signal_price_matches_snapshot(monkeypatch):
    h = _ohlcv()
    import utils.signal_hub as hub
    monkeypatch.setattr(hub, "get_ohlcv", lambda s, period=None: h)
    from utils.trade_signal_engine import TradeSignalEngine
    eng = TradeSignalEngine()
    monkeypatch.setattr(eng, "_get_sentiment_score", lambda s: None)
    r = eng.analyze_stock("RIOT")
    snap = snapshot_from_ohlcv(h)
    assert r["current_price"] == pytest.approx(snap["price"])
    assert r["rsi"] == pytest.approx(round(snap["rsi14"], 1))
    assert r["signal"] in ("BUY", "HOLD", "SELL")


def test_no_data_is_na_not_fake_hold(monkeypatch):
    import utils.signal_hub as hub
    monkeypatch.setattr(hub, "get_ohlcv", lambda s, period=None: pd.DataFrame())
    from utils.trade_signal_engine import TradeSignalEngine
    r = TradeSignalEngine().analyze_stock("RIOT")
    assert r["signal"] == "N/A" and r["rsi"] is None and r["confidence"] is None
    assert snapshot_from_ohlcv(pd.DataFrame()) == {"available": False}


def test_short_indicators_return_none():
    h = _ohlcv(n=10)
    assert ind.rsi(h["Close"]) is None and ind.macd(h["Close"]) is None and ind.sma(h["Close"], 50) is None


@pytest.mark.parametrize("short,long_,must", [
    ("SELL", "HOLD", "Don't sell your 2030 position"),
    ("BUY", "TRIM", "not a reason to add"),
    ("HOLD", "HOLD", "Follow My Plan"),
    ("N/A", "HOLD", "unavailable"),
])
def test_reconcile_points_to_my_plan(short, long_, must):
    assert must in reconcile(short, long_, "RIOT")


def test_forecast_centre_and_my_plan_price_match_snapshot():
    from utils.stat_forecast import forecast_range
    h = _ohlcv()
    snap = snapshot_from_ohlcv(h)
    assert forecast_range(h["Close"], 21)["centre"] == pytest.approx(snap["price"])
    assert compute_facts(h["Close"])["price"] == pytest.approx(snap["price"])
    assert compute_facts(h["Close"])["sma200"] == pytest.approx(snap["sma200"])


def test_monte_carlo_is_stable_and_gives_no_advice():
    from utils.risk_engine import RiskEngine
    h = _ohlcv()
    df = pd.DataFrame({"A": h["Close"], "B": h["Close"] * 1.1})
    eng = RiskEngine()
    a, b = eng.run_monte_carlo_simulation(df, 200, 21), eng.run_monte_carlo_simulation(df, 200, 21)
    assert a["prob_profit"] == b["prob_profit"]
    assert "add" not in a["interpretation"].lower().replace("my plan", "")
