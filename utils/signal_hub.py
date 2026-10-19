"""
utils/signal_hub.py — the shared, cached source of truth for prices, indicators,
the short-term trade signal, the long-term My Plan call, and news sentiment.

Every tab that shows a price, an RSI, a BUY/HOLD/SELL, or a sentiment number reads it
from here, so two tabs can no longer disagree because they downloaded different windows,
used different formulas, or silently fell back to a different default.

Hierarchy (shown to the user wherever signals appear):
  1. 🧭 My Plan (Hold / Trim / Sell / Rotate + Add / Wait) is the FINAL WORD for a
     long-term holder.  It is rule-based and has a published track record.
  2. 🚦 Trade Signals (BUY / HOLD / SELL) is a short-term (days-to-weeks) momentum read.
     It never overrides My Plan; where they differ we say so and explain why.
  3. Everything else (Next-Mover ranking, Forecast Center lean, news tone) is context.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

try:
    import streamlit as st
    _cache15 = st.cache_data(ttl=900, show_spinner=False)
    _cache5 = st.cache_data(ttl=300, show_spinner=False)
except Exception:  # pragma: no cover
    def _cache15(fn):
        return fn
    _cache5 = _cache15

from utils import indicators as ind
from utils.market_data import to_daily

OHLCV_PERIOD = "2y"     # one window for every tab (long enough for 200-day averages)


class _NoData(Exception):
    """Raised inside cached functions so empty / rate-limited downloads are never cached."""


@_cache15
def _ohlcv_cached(symbol: str, period: str) -> pd.DataFrame:
    import yfinance as yf
    h = yf.Ticker(symbol).history(period=period, interval="1d", auto_adjust=True)
    if h is None or h.empty:
        raise _NoData(symbol)
    h = h[["Open", "High", "Low", "Close", "Volume"]].copy()
    idx = pd.to_datetime(h.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)
    h.index = idx.normalize()
    return h[~h.index.duplicated(keep="last")].sort_index()


def get_ohlcv(symbol: str, period: str = OHLCV_PERIOD) -> pd.DataFrame:
    """Daily OHLCV (auto-adjusted, tz-naive dates). Empty frame on failure (not cached)."""
    try:
        return _ohlcv_cached(symbol, period)
    except Exception:
        return pd.DataFrame()


def snapshot_from_ohlcv(hist: pd.DataFrame) -> dict:
    """Indicator snapshot from an OHLCV frame — pure function (unit-tested)."""
    if hist is None or hist.empty:
        return {"available": False}
    c = hist["Close"].dropna()
    m = ind.macd(c)
    bb = ind.bollinger(c)
    sto = ind.stochastic(hist)
    prev = float(c.iloc[-2]) if len(c) > 1 else None
    return {
        "available": True,
        "price": float(c.iloc[-1]),
        "as_of": c.index[-1].date(),
        "change_1d_pct": (float(c.iloc[-1]) / prev - 1) * 100 if prev else None,
        "rsi14": ind.rsi(c),
        "macd_hist": m["hist"] if m else None,
        "macd_hist_prev": m["hist_prev"] if m else None,
        "sma20": ind.sma(c, 20), "sma50": ind.sma(c, 50), "sma200": ind.sma(c, 200),
        "pct_b": bb["pct_b"] if bb else None,
        "stoch_k": sto[0] if sto else None, "stoch_d": sto[1] if sto else None,
        "atr14": ind.atr(hist),
        "volume_ratio": ind.volume_ratio(hist["Volume"]) if "Volume" in hist else None,
    }


def snapshot(symbol: str) -> dict:
    """Shared price + indicator snapshot for one ticker."""
    snap = snapshot_from_ohlcv(get_ohlcv(symbol))
    snap["symbol"] = symbol
    snap["source"] = "Yahoo Finance daily bars (auto-adjusted), 2-year window, cached 15 min"
    return snap


# ── Short-term signal (Trade Signals engine) ─────────────────────────────────

_ENGINE = None


def _engine():
    global _ENGINE
    if _ENGINE is None:
        from utils.trade_signal_engine import TradeSignalEngine
        _ENGINE = TradeSignalEngine()
    return _ENGINE


def short_term_signal(symbol: str) -> dict:
    """The ONE short-term BUY/HOLD/SELL for a ticker (same result the Trade Signals tab shows)."""
    try:
        return _engine().analyze_stock(symbol)
    except Exception as e:
        return {"symbol": symbol, "signal": "N/A", "error": str(e)}


# ── Long-term call (My Plan) ─────────────────────────────────────────────────

def long_term_call(symbol: str) -> Optional[dict]:
    """My Plan's Hold/Trim/Sell/Rotate + Add/Wait for a ticker, or None if unavailable."""
    try:
        from components.holding_plan import get_advice, get_add_advice
        adv, closes, positions, _ = get_advice(symbol)
        if adv is None:
            return None
        add = get_add_advice(adv.symbol, closes, positions)
        return {"symbol": adv.symbol, "action": adv.action, "confidence": adv.confidence,
                "risk_score": adv.risk_score, "max_score": adv.max_score,
                "add_action": add.action if add else None, "price": adv.facts.get("price"),
                "held": positions.get(adv.symbol, {}).get("shares", 0) > 0}
    except Exception:
        return None


def reconcile(short_signal: Optional[str], long_action: Optional[str], symbol: str = "") -> str:
    """Plain-English explanation of how the short-term signal relates to the My Plan call."""
    s = (short_signal or "N/A").upper()
    l = (long_action or "").upper()
    name = symbol or "this stock"
    if not l:
        return (f"Short-term signal for {name}: {s}. My Plan has no long-term call for it right now "
                "(no price data or not a holding).")
    if s == "N/A":
        return f"My Plan says **{l}** for {name}. The short-term signal is unavailable right now."
    if (s == "SELL" and l in ("SELL", "TRIM")) or (s == "BUY" and l == "HOLD") or (s == "HOLD" and l == "HOLD"):
        return (f"Both agree in direction: short-term **{s}**, long-term plan **{l}** for {name}. "
                "Follow My Plan for what to actually do.")
    if s == "SELL" and l in ("HOLD", "ROTATE"):
        return (f"**No conflict to act on:** short-term momentum for {name} is weak (**{s}** = expect more chop or "
                f"downside over days–weeks), but your long-term plan is **{l}**. Short-term dips are normal for miners; "
                "the long-term checks decide. Don't sell your 2030 position on a short-term signal alone.")
    if s == "BUY" and l in ("TRIM", "SELL"):
        return (f"**Different time frames:** short-term momentum for {name} looks positive (**{s}**), but your "
                f"long-term plan says **{l}** because of position size / risk. A short-term bounce can be a better "
                "moment to carry out a trim — it is not a reason to add.")
    return (f"Short-term signal **{s}**, long-term plan **{l}** for {name}. They measure different things "
            "(days–weeks momentum vs. multi-year risk). My Plan is the one to act on.")


@_cache15
def _shares_cached(symbol: str) -> pd.Series:
    import yfinance as yf
    sh = yf.Ticker(symbol).get_shares_full(start="2019-01-01")
    if sh is None or len(sh) == 0:
        raise _NoData(symbol)
    sh = sh[~sh.index.duplicated(keep="last")].sort_index()
    return to_daily(sh)


def get_shares(symbol: str) -> pd.Series:
    """Shares-outstanding history (Yahoo). Empty series on failure (not cached)."""
    try:
        return _shares_cached(symbol)
    except Exception:
        return pd.Series(dtype=float)
