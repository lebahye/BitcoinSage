"""utils/network_data.py — free Bitcoin-network data (no keys), cached for 1 hour.

Primary: mempool.space (current difficulty/hashrate, full daily hashrate history, every difficulty
adjustment with its block height, recent block rewards incl. fees).  Fallback / fees history: blockchain.info.
Every fetcher raises inside the cached function so failures are never cached, and the public wrappers return
empty results (-> the UI shows N/A).  Each result carries an `as_of` date so the UI can show data age.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import pandas as pd

try:
    import streamlit as st
    _cache1h = st.cache_data(ttl=3600, show_spinner=False)
except Exception:  # pragma: no cover
    def _cache1h(fn):
        return fn

MEMPOOL = "https://mempool.space/api"
BCI = "https://api.blockchain.info/charts"
TIMEOUT = 10
SOURCES = {
    "mempool": "https://mempool.space/docs/api/rest",
    "blockchain.info": "https://www.blockchain.com/explorer/charts",
}


class _NoData(Exception):
    pass


def _get_json(url: str):
    import requests
    r = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": "BitcoinSage/1.0"})
    if r.status_code != 200:
        raise _NoData(f"{url} -> {r.status_code}")
    return r.json()


@_cache1h
def _mempool_history_cached() -> dict:
    d = _get_json(f"{MEMPOOL}/v1/mining/hashrate/all")
    hr = pd.Series({pd.Timestamp(x["timestamp"], unit="s").normalize(): float(x["avgHashrate"]) for x in d["hashrates"]})
    adj = pd.DataFrame([{"date": pd.Timestamp(x["time"], unit="s"), "height": int(x["height"]),
                         "difficulty": float(x["difficulty"])} for x in d["difficulty"]])
    if hr.empty or adj.empty:
        raise _NoData("empty mempool history")
    return {"hashrate_hs": hr.sort_index(), "adjustments": adj.sort_values("date").reset_index(drop=True),
            "current_hashrate_hs": float(d.get("currentHashrate") or hr.iloc[-1]),
            "current_difficulty": float(d.get("currentDifficulty") or adj.difficulty.iloc[-1]),
            "as_of": hr.index[-1].date(), "source": "mempool.space"}


@_cache1h
def _bci_chart_cached(chart: str, timespan: str) -> pd.Series:
    d = _get_json(f"{BCI}/{chart}?timespan={timespan}&format=json&sampled=false")
    vals = d.get("values") or []
    s = pd.Series({pd.Timestamp(v["x"], unit="s").normalize(): float(v["y"]) for v in vals if v.get("y") is not None})
    if s.empty:
        raise _NoData(chart)
    return s.sort_index()


@_cache1h
def _reward_stats_cached(blocks: int) -> dict:
    d = _get_json(f"{MEMPOOL}/v1/mining/reward-stats/{blocks}")
    n = int(d["endBlock"]) - int(d["startBlock"]) + 1
    return {"blocks": n, "fee_btc_per_block": int(d["totalFee"]) / 1e8 / n,
            "reward_btc_per_block": int(d["totalReward"]) / 1e8 / n, "end_height": int(d["endBlock"])}


def network_history() -> dict:
    """{'hashrate_hs', 'adjustments', 'current_*', 'as_of', 'source'} or {} if unavailable.
    Falls back to blockchain.info hashrate (TH/s -> H/s) + difficulty charts."""
    try:
        return _mempool_history_cached()
    except Exception:
        pass
    try:
        hr = _bci_chart_cached("hash-rate", "all") * 1e12
        df = _bci_chart_cached("difficulty", "all")
        adj = pd.DataFrame({"date": df.index, "height": [None] * len(df), "difficulty": df.values})
        return {"hashrate_hs": hr, "adjustments": adj, "current_hashrate_hs": float(hr.iloc[-1]),
                "current_difficulty": float(df.iloc[-1]), "as_of": hr.index[-1].date(), "source": "blockchain.info"}
    except Exception:
        return {}


def fees_history() -> pd.Series:
    """Total transaction fees paid to miners per day (BTC), blockchain.info. Empty on failure."""
    try:
        return _bci_chart_cached("transaction-fees", "all")
    except Exception:
        return pd.Series(dtype=float)


def recent_rewards(blocks: int = 1008) -> dict:
    """Average subsidy+fees per block over the last ~week of blocks (mempool.space). {} on failure."""
    try:
        return _reward_stats_cached(blocks)
    except Exception:
        return {}


def fetched_at() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
