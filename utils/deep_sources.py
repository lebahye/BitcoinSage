"""utils/deep_sources.py — free, key-less data fetchers for the Verdict's "Deeper evidence".

Each cached function RAISES on failure so an outage/rate-limit is never cached; the public wrappers return
None / {} instead, and the UI shows N/A.  No API keys, no accounts.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

import pandas as pd
import requests
import streamlit as st

UA = {"User-Agent": "BitcoinSage dashboard (educational; contact via GitHub lebahye/BitcoinSage)"}
CM_URL = "https://community-api.coinmetrics.io/v4/timeseries/asset-metrics"
CM_METRICS = "CapMVRVCur,CapMrktCurUSD,IssTotUSD,SplyCur,PriceUSD"
GAMMA = "https://gamma-api.polymarket.com"
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"

SOURCES = {
    "coinmetrics": ("Coin Metrics Community API (free)", "https://docs.coinmetrics.io/api/v4/"),
    "yahoo": ("Yahoo Finance via yfinance (free, delayed)", "https://finance.yahoo.com"),
    "polymarket": ("Polymarket public Gamma API", "https://docs.polymarket.com/"),
    "kalshi": ("Kalshi public market-data API", "https://trading-api.readme.io/reference/getevents"),
}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _coinmetrics_cached() -> pd.DataFrame:
    rows, url = [], CM_URL
    params = {"assets": "btc", "metrics": CM_METRICS, "frequency": "1d", "page_size": 10000,
              "start_time": "2010-07-18"}
    for _ in range(3):
        r = requests.get(url, params=params, headers=UA, timeout=30)
        r.raise_for_status()
        j = r.json()
        rows += j.get("data", [])
        url, params = j.get("next_page_url"), None
        if not url:
            break
    if len(rows) < 1000:
        raise RuntimeError("too little data")
    df = pd.DataFrame(rows)
    df.index = pd.to_datetime(df.pop("time")).dt.tz_localize(None).dt.normalize()
    df = df.drop(columns=["asset"], errors="ignore").apply(pd.to_numeric, errors="coerce")
    return df.sort_index()


def coinmetrics_btc() -> Optional[pd.DataFrame]:
    try:
        return _coinmetrics_cached()
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _info_cached(symbol: str) -> dict:
    import yfinance as yf
    info = yf.Ticker(symbol).info or {}
    keep = ["shortPercentOfFloat", "shortRatio", "sharesShort", "sharesShortPriorMonth", "dateShortInterest",
            "floatShares", "enterpriseValue", "marketCap", "totalDebt", "totalCash", "sharesOutstanding"]
    out = {k: info.get(k) for k in keep}
    if not any(v is not None for v in out.values()):
        raise RuntimeError("empty info")         # likely rate-limited → don't cache
    return out


def yahoo_info(symbol: str) -> dict:
    try:
        return _info_cached(symbol)
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def _chain_cached(symbol: str) -> dict:
    """Nearest expiry 20–75 days out (falls back to the next available)."""
    import yfinance as yf
    t = yf.Ticker(symbol)
    exps = list(t.options or [])
    if not exps:
        raise RuntimeError("no options")
    today = date.today()
    days = [(e, (date.fromisoformat(e) - today).days) for e in exps]
    pick = next((e for e, d in days if 20 <= d <= 75), None) or next((e for e, d in days if d > 7), exps[0])
    ch = t.option_chain(pick)
    if ch.calls.empty and ch.puts.empty:
        raise RuntimeError("empty chain")
    return {"expiry": pick, "days": (date.fromisoformat(pick) - today).days,
            "calls": ch.calls[["strike", "impliedVolatility", "openInterest", "volume", "bid", "ask"]].copy(),
            "puts": ch.puts[["strike", "impliedVolatility", "openInterest", "volume", "bid", "ask"]].copy(),
            "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}


def option_chain(symbol: str) -> Optional[dict]:
    try:
        return _chain_cached(symbol)
    except Exception:
        return None


# Prediction markets: fixed, documented questions (we don't search for "interesting" markets).
POLY_EVENTS = {
    "CLARITY Act (crypto market structure) signed into law in 2026": "clarity-act-signed-into-law-in-2026",
    "House control after the 2026 midterms": "which-party-will-win-the-house-in-2026",
    "Senate control after the 2026 midterms": "which-party-will-win-the-senate-in-2026",
}


@st.cache_data(ttl=1800, show_spinner=False)
def _poly_event_cached(slug: str) -> dict:
    r = requests.get(f"{GAMMA}/events", params={"slug": slug}, headers=UA, timeout=15)
    r.raise_for_status()
    j = r.json()
    if not j:
        raise RuntimeError("not found")
    return j[0]


def polymarket_event(slug: str) -> Optional[dict]:
    try:
        return _poly_event_cached(slug)
    except Exception:
        return None


@st.cache_data(ttl=1800, show_spinner=False)
def _kalshi_fed_cached() -> dict:
    r = requests.get(f"{KALSHI}/events", params={"series_ticker": "KXFEDDECISION", "status": "open",
                                                  "with_nested_markets": "true", "limit": 10}, headers=UA, timeout=15)
    r.raise_for_status()
    ev = [e for e in r.json().get("events", []) if e.get("markets")]
    if not ev:
        raise RuntimeError("no open Fed events")
    def close(e):
        return min(m.get("close_time") or "9999" for m in e["markets"])
    return sorted(ev, key=close)[0]           # the next meeting


def kalshi_next_fed() -> Optional[dict]:
    try:
        return _kalshi_fed_cached()
    except Exception:
        return None
