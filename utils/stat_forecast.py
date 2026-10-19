"""
utils/stat_forecast.py — a modest, transparent statistical price-range forecast with a
backtested accuracy check.  Replaces the Forecast Center's old "targets", which were
invented by a formula (price × (1 ± |score| × 5% × horizon)) and produced e.g. a −88% one-month
"target" for RIOT at "86% probability", outside its own "expected range".

Model (deliberately simple and stated plainly in the UI):
  * Centre = today's price (no directional guess — there's no reliable evidence we can call a
    miner's direction week to week; the rules-based leans elsewhere are untested).
  * Width = the stock's own daily volatility over the last year, scaled by √(trading days):
        68% band: price × exp(±1.0 σ √h),   90% band: price × exp(±1.645 σ √h)
  * Accuracy: replay the same recipe on past data (volatility measured only from data available
    on that day) and count how often the actual price h days later landed inside each band.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

Z = {"68%": 1.0, "90%": 1.645}
HORIZONS = {"1 week": 5, "1 month": 21, "3 months": 63}
VOL_WINDOW = 252


def daily_vol(close: pd.Series, window: int = VOL_WINDOW) -> Optional[float]:
    r = np.log(close.dropna()).diff().dropna().iloc[-window:]
    return float(r.std()) if len(r) >= 60 else None


def forecast_range(close: pd.Series, h: int, window: int = VOL_WINDOW) -> Optional[Dict[str, float]]:
    """Zero-drift lognormal range h trading days ahead. None if <60 days of history."""
    close = close.dropna()
    sig = daily_vol(close, window)
    if sig is None:
        return None
    p = float(close.iloc[-1])
    out = {"price": p, "centre": p, "daily_vol": sig, "annual_vol": sig * np.sqrt(252), "h": h}
    for k, z in Z.items():
        out[f"low_{k}"] = p * float(np.exp(-z * sig * np.sqrt(h)))
        out[f"high_{k}"] = p * float(np.exp(z * sig * np.sqrt(h)))
    return out


def backtest_coverage(close: pd.Series, h: int, window: int = VOL_WINDOW, years: float = 3.0,
                      step: int = 5) -> Optional[Dict[str, float]]:
    """How often the real price h days later fell inside each band (point-in-time volatility)."""
    close = close.dropna()
    lr = np.log(close).diff()
    vol = lr.rolling(window, min_periods=120).std()
    fwd = np.log(close.shift(-h) / close)
    df = pd.DataFrame({"vol": vol, "fwd": fwd}).dropna()
    if years:
        df = df[df.index >= df.index.max() - pd.DateOffset(years=years)] if len(df) else df
    df = df.iloc[::step]
    if len(df) < 20:
        return None
    out = {"n": int(len(df)), "start": df.index[0], "end": df.index[-1]}
    for k, z in Z.items():
        out[f"hit_{k}"] = float((df["fwd"].abs() <= z * df["vol"] * np.sqrt(h)).mean())
    out["up_share"] = float((df["fwd"] > 0).mean())
    return out


def coverage_verdict(cov: Optional[dict]) -> str:
    if not cov:
        return "Not enough history to check accuracy."
    h68, h90 = cov["hit_68%"], cov["hit_90%"]
    if h68 >= 0.78 and h90 >= 0.97:
        return (f"Conservative: the 68% range actually held {h68:.0%} of the time and the 90% range {h90:.0%} "
                f"({cov['n']} past checks) — the real range has tended to be a bit narrower.")
    if h68 >= 0.60 and h90 >= 0.84:
        return (f"Well calibrated: the 68% range held {h68:.0%} of the time and the 90% range {h90:.0%} "
                f"({cov['n']} past checks).")
    return (f"Ranges were too narrow in the past: the 68% range held only {h68:.0%} and the 90% range {h90:.0%} "
            f"of the time ({cov['n']} checks) — expect bigger surprises than the bands suggest.")
