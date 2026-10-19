"""
utils/market_data.py — shared daily price loading + calendar alignment.

Why this exists
---------------
Yahoo Finance stamps BTC-USD daily bars at 00:00 UTC and US stocks at 00:00
America/New_York.  Joining those indexes directly gives ZERO shared days, which
silently broke every "stock vs Bitcoin" number in the app (beta, correlation,
stress test, reflexivity).  Bitcoin also trades on weekends while stocks don't.

Rules used everywhere:
  1. Every daily series is converted to a tz-naive calendar date.
  2. Non-stock series (BTC, etc.) are put on the STOCK trading calendar by
     taking the last value at-or-before each trading date.  Because we compare
     closes, Monday's BTC return automatically includes the weekend move
     (Friday close -> Monday close), i.e. weekend moves are folded into Monday.
  3. If there is not enough overlapping history we return None — callers must
     show "insufficient data" instead of inventing a default.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

try:
    import streamlit as st
    _cache = st.cache_data(ttl=900, show_spinner=False)
except Exception:  # pragma: no cover - allows use outside Streamlit
    def _cache(fn):
        return fn

MIN_OVERLAP_DAYS = 20


def to_daily(series: pd.Series) -> pd.Series:
    """Return a series indexed by tz-naive calendar date (last value per day)."""
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)
    s = series.copy()
    idx = pd.to_datetime(s.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_localize(None)  # keep the exchange's wall-clock date
    s.index = idx.normalize()
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s.astype(float)


def to_stock_calendar(other: pd.Series, stock_dates: pd.Index) -> pd.Series:
    """Put a 7-day-a-week series (e.g. BTC) on the stock trading calendar.

    Uses the last available value at or before each stock date, so returns
    computed afterwards fold weekend/holiday moves into the next trading day.
    """
    o = to_daily(other)
    dates = pd.DatetimeIndex(stock_dates)
    if o.empty or len(dates) == 0:
        return pd.Series(index=dates, dtype=float)
    union = o.index.union(dates)
    return o.reindex(union).ffill().reindex(dates)


def aligned_returns(stock: pd.Series, bench: pd.Series) -> pd.DataFrame:
    """Daily simple returns of stock and bench on the stock's trading calendar."""
    s = to_daily(stock).dropna()
    b = to_stock_calendar(bench, s.index)
    df = pd.DataFrame({"stock": s, "bench": b}).dropna()
    rets = df.pct_change(fill_method=None).dropna()
    return rets


def beta_corr(stock: pd.Series, bench: pd.Series,
              min_obs: int = MIN_OVERLAP_DAYS) -> Optional[Dict[str, float]]:
    """Beta / correlation of stock vs bench. None if overlap < min_obs days."""
    r = aligned_returns(stock, bench)
    if len(r) < min_obs or r["bench"].var() <= 0:
        return None
    beta = float(r["stock"].cov(r["bench"]) / r["bench"].var())
    corr = float(r["stock"].corr(r["bench"]))
    return {"beta": beta, "corr": corr, "r_squared": corr ** 2, "n_days": int(len(r))}


def align_frame(closes: pd.DataFrame, calendar_col: Optional[str] = None,
                calendar: Optional[pd.Index] = None) -> pd.DataFrame:
    """Align a dict-like frame of closes onto one trading calendar.

    calendar: explicit dates; else dates where `calendar_col` traded; else the
    union of dates of all columns that do NOT trade on weekends (stocks).
    """
    cols = {c: to_daily(closes[c].dropna()) for c in closes.columns}
    cols = {c: s for c, s in cols.items() if not s.empty}
    if not cols:
        return pd.DataFrame()
    if calendar is None:
        if calendar_col and calendar_col in cols:
            calendar = cols[calendar_col].index
        else:
            stockish = [s.index for s in cols.values() if (s.index.dayofweek >= 5).mean() < 0.02]
            base = stockish if stockish else [s.index for s in cols.values()]
            calendar = base[0]
            for ix in base[1:]:
                calendar = calendar.union(ix)
    calendar = pd.DatetimeIndex(calendar)
    out = {}
    for c, s in cols.items():
        on_cal = to_stock_calendar(s, calendar)
        # don't ffill before a series' own first date
        on_cal[on_cal.index < s.index[0]] = np.nan
        out[c] = on_cal
    return pd.DataFrame(out, index=calendar)


class _FetchIncomplete(Exception):
    """Raised inside the cached function so a failed/rate-limited download is NOT cached."""


@_cache
def _fetch_daily_closes_cached(tickers: tuple, period: str) -> pd.DataFrame:
    import yfinance as yf
    out = {}
    for t in tickers:
        try:
            h = yf.Ticker(t).history(period=period, interval="1d", auto_adjust=True)
            if h is not None and not h.empty:
                out[t] = to_daily(h["Close"])
        except Exception:
            continue
    # If most tickers failed (typically a Yahoo rate limit), don't cache the hole.
    if not out or len(out) < max(1, len(tickers) // 2):
        raise _FetchIncomplete(f"only {len(out)}/{len(tickers)} tickers downloaded")
    return pd.DataFrame(out).sort_index()


def fetch_daily_closes(tickers: tuple, period: str = "1y") -> pd.DataFrame:
    """Daily closes (auto-adjusted) for tickers on a tz-naive date index.

    Returns the raw per-ticker series joined on the union of dates (no fill);
    use `align_frame` before computing cross-asset statistics.  Successful
    downloads are cached for 15 minutes; failures return an empty frame and
    are retried on the next run instead of being cached.
    """
    try:
        return _fetch_daily_closes_cached(tuple(tickers), period)
    except _FetchIncomplete:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()


def fetched_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
