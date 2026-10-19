"""
utils/riot_correlation.py — which stocks/markets move most like RIOT?

Ported from the standalone RIOT correlation study (riot_corr/corr.py):
  * daily log returns, everything aligned on RIOT's trading calendar
    (Bitcoin's weekend moves roll into Monday)
  * 1-year and 3-month correlation for every ticker in the universe
  * stability: correlation in each of the last 4 quarters -> "steady" if the
    sign never changed, "flips" if it did
  * group averages (Miners vs AI data centers vs Bitcoin vs Macro)
  * divergence check: is RIOT currently moving apart from its closest peers?
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from utils.market_data import fetch_daily_closes, align_frame, fetched_at
from utils.tickers import CORRELATION_UNIVERSE, INVERSE_PANEL

ANCHOR = "RIOT"


def _quarter_corrs(r: pd.DataFrame, a: str, b: str, n_quarters: int = 4) -> list:
    d = r[[a, b]].dropna()
    if len(d) < 40:
        return []
    size = len(d) // n_quarters
    out = []
    for i in range(n_quarters):
        chunk = d.iloc[i * size:(i + 1) * size] if i < n_quarters - 1 else d.iloc[i * size:]
        if len(chunk) >= 20:
            out.append(float(chunk[a].corr(chunk[b])))
    return out


def compute_correlations(closes: pd.DataFrame, anchor: str = ANCHOR,
                         universe: Optional[Dict[str, tuple]] = None) -> pd.DataFrame:
    """Pure computation (testable without network). `closes` = raw daily closes."""
    universe = universe or CORRELATION_UNIVERSE
    if closes.empty or anchor not in closes.columns:
        return pd.DataFrame()
    px = align_frame(closes, calendar=closes[anchor].dropna().index)
    r = np.log(px / px.shift(1))
    end = r.index[-1]
    w1 = r.loc[end - pd.DateOffset(years=1):]
    w3 = r.loc[end - pd.DateOffset(months=3):]
    rows = []
    for t, (group, desc) in universe.items():
        if t == anchor or t not in r.columns:
            continue
        d1 = w1[[anchor, t]].dropna()
        if len(d1) < 40:
            continue
        d3 = w3[[anchor, t]].dropna()
        c1 = float(d1[anchor].corr(d1[t]))
        c3 = float(d3[anchor].corr(d3[t])) if len(d3) >= 20 else np.nan
        q = _quarter_corrs(w1, anchor, t)
        signs = {np.sign(x) for x in q if abs(x) >= 0.05}
        stable = len(q) >= 3 and len(signs) <= 1
        var_t = d1[t].var()
        rows.append({
            "ticker": t, "group": group, "description": desc,
            "corr_1y": c1, "corr_3m": c3,
            "change": (c3 - c1) if not np.isnan(c3) else np.nan,
            "riot_beta_to_it": float(d1[anchor].cov(d1[t]) / var_t) if var_t > 0 else np.nan,
            "quarterly": q,
            "q_min": min(q) if q else np.nan, "q_max": max(q) if q else np.nan,
            "stability": "steady" if stable else "flips",
            "n_days": int(len(d1)),
        })
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.sort_values("corr_1y", ascending=False).reset_index(drop=True)


def group_summary(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    g = df.groupby("group").agg(avg_corr_1y=("corr_1y", "mean"),
                                avg_corr_3m=("corr_3m", "mean"),
                                n=("ticker", "count"))
    return g.sort_values("avg_corr_1y", ascending=False)


def divergence_check(closes: pd.DataFrame, peers: list, anchor: str = ANCHOR,
                     lookback: int = 20) -> Optional[dict]:
    """Compare RIOT's last-`lookback`-day return and correlation with its top peers."""
    cols = [anchor] + [p for p in peers if p in closes.columns]
    if anchor not in closes.columns or len(cols) < 2:
        return None
    px = align_frame(closes[cols], calendar=closes[anchor].dropna().index).dropna()
    if len(px) < max(lookback * 3, 60):
        return None
    r = np.log(px / px.shift(1)).dropna()
    peer_ret = r[cols[1:]].mean(axis=1)
    recent = r.iloc[-lookback:]
    riot_move = float(np.exp(recent[anchor].sum()) - 1)
    peer_move = float(np.exp(peer_ret.iloc[-lookback:].sum()) - 1)
    corr_recent = float(recent[anchor].corr(peer_ret.iloc[-lookback:]))
    corr_year = float(r[anchor].iloc[-252:].corr(peer_ret.iloc[-252:]))
    gap = riot_move - peer_move
    diverging = (corr_recent < corr_year - 0.25) or abs(gap) > 0.15
    return {"riot_move": riot_move, "peer_move": peer_move, "gap": gap,
            "corr_recent": corr_recent, "corr_year": corr_year,
            "diverging": bool(diverging), "lookback": lookback, "peers": cols[1:]}


def load_riot_correlations(anchor: str = ANCHOR) -> dict:
    """Fetch data and compute everything the UI needs (cached by fetch layer)."""
    tickers = tuple([anchor] + [t for t in CORRELATION_UNIVERSE if t != anchor])
    closes = fetch_daily_closes(tickers, "1y")
    table = compute_correlations(closes, anchor)
    if table.empty:
        return {"ok": False, "error": "Price history unavailable from Yahoo Finance.", "fetched_at": fetched_at()}
    groups = group_summary(table)
    miners = table[table["group"] == "Miners"].head(5)["ticker"].tolist()
    div = divergence_check(closes, miners, anchor)
    btc_row = table[table["ticker"] == "BTC-USD"]
    last_date = closes[anchor].dropna().index[-1].date() if anchor in closes else None
    missing = [t for t in tickers if t != anchor and t not in set(table["ticker"])]
    return {"ok": True, "table": table, "groups": groups, "divergence": div,
            "btc_corr_1y": float(btc_row["corr_1y"].iloc[0]) if not btc_row.empty else None,
            "btc_corr_3m": float(btc_row["corr_3m"].iloc[0]) if not btc_row.empty else None,
            "inverse": table[table["ticker"].isin(INVERSE_PANEL)].copy(),
            "missing": missing, "last_date": last_date, "fetched_at": fetched_at()}
