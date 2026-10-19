"""
utils/indicators.py — ONE implementation of every technical indicator used in the app.

Before this module, Trade Signals, Next-Mover ("AI Predictions"), Technical Analysis and
My Plan each had their own RSI/MACD code with different formulas (simple-average RSI vs
Wilder RSI, adjust=True vs adjust=False EMAs) and different look-back windows, so the same
stock could show RSI 27 on one tab and RSI 11 on another.  Every tab now calls these.

Conventions
  * RSI = Wilder's 14-day RSI (exponential smoothing, alpha = 1/14) — the standard definition.
    Implementation is shared with My Plan / the track record (utils.holding_advisor).
  * EMAs use adjust=False (the standard recursive EMA used by charting platforms).
  * Functions return None (scalars) when there is not enough data — callers must show
    "n/a", never a made-up neutral value like RSI 50.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from utils.holding_advisor import rsi_series as _rsi_series, rsi_wilder as _rsi_wilder

RSI_PERIOD = 14


def rsi_series(close: pd.Series, n: int = RSI_PERIOD) -> pd.Series:
    """Wilder RSI for every day (each value uses data up to that day only)."""
    return _rsi_series(close.dropna(), n)


def rsi(close: pd.Series, n: int = RSI_PERIOD) -> Optional[float]:
    """Latest Wilder RSI, or None if fewer than n+1 closes."""
    return _rsi_wilder(close, n)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Optional[dict]:
    """MACD line, signal line and histogram (last 3 histogram values for crossover logic)."""
    close = close.dropna()
    if len(close) < slow + signal:
        return None
    line = close.ewm(span=fast, adjust=False).mean() - close.ewm(span=slow, adjust=False).mean()
    sig = line.ewm(span=signal, adjust=False).mean()
    hist = line - sig
    return {"line": float(line.iloc[-1]), "signal": float(sig.iloc[-1]),
            "hist": float(hist.iloc[-1]), "hist_prev": float(hist.iloc[-2]), "hist_prev2": float(hist.iloc[-3]),
            "line_series": line, "signal_series": sig, "hist_series": hist}


def bollinger(close: pd.Series, n: int = 20, k: float = 2.0) -> Optional[dict]:
    close = close.dropna()
    if len(close) < n:
        return None
    ma = close.rolling(n).mean()
    sd = close.rolling(n).std()
    up, lo = ma + k * sd, ma - k * sd
    width = float(up.iloc[-1] - lo.iloc[-1])
    pct_b = float((close.iloc[-1] - lo.iloc[-1]) / width) if width > 0 else None
    return {"pct_b": pct_b, "upper": float(up.iloc[-1]), "middle": float(ma.iloc[-1]), "lower": float(lo.iloc[-1])}


def stochastic(hist: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> Optional[Tuple[float, float]]:
    if hist is None or len(hist) < k_period + d_period:
        return None
    lo = hist["Low"].rolling(k_period).min()
    hi = hist["High"].rolling(k_period).max()
    k = 100 * (hist["Close"] - lo) / (hi - lo).replace(0, np.nan)
    d = k.rolling(d_period).mean()
    if pd.isna(k.iloc[-1]) or pd.isna(d.iloc[-1]):
        return None
    return float(k.iloc[-1]), float(d.iloc[-1])


def atr(hist: pd.DataFrame, n: int = 14) -> Optional[float]:
    if hist is None or len(hist) < n + 1:
        return None
    h, l, c = hist["High"], hist["Low"], hist["Close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    v = tr.ewm(alpha=1 / n, min_periods=n, adjust=False).mean().iloc[-1]
    return float(v) if pd.notna(v) else None


def sma(close: pd.Series, n: int) -> Optional[float]:
    close = close.dropna()
    return float(close.iloc[-n:].mean()) if len(close) >= n else None


def volume_ratio(volume: pd.Series, window: int = 20) -> Optional[float]:
    """Today's volume ÷ average of the previous `window` days."""
    volume = volume.dropna()
    if len(volume) < window + 1:
        return None
    avg = float(volume.iloc[-(window + 1):-1].mean())
    return float(volume.iloc[-1] / avg) if avg > 0 else None
