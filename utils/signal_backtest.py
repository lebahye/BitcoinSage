"""Track record of the My Plan rules, replayed day by day on history.

Honesty rules
- Point-in-time only: every indicator on day t uses data up to and including t (rolling windows,
  Wilder RSI via EWM). Bitcoin is lagged one day because Yahoo's BTC daily bar closes at 00:00 UTC,
  i.e. ~4 hours *after* the US stock close.
- Entry is the NEXT trading day's close after a signal (you can't trade at the close that produced it).
- Overlapping days are collapsed into episodes: a signal counts once when it first switches on, and
  again only after it has been off for COOLDOWN trading days.
- Only market rules are replayed (trend, drawdown, Bitcoin trend, VIX, peer divergence; ADD rule).
  Personal rules (concentration, your target, cost basis) and analyst targets can't be replayed.
- Peer list is today's WATCHLIST → mild survivorship/hindsight bias in the peer checks.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from utils.holding_advisor import add_rule, market_risk_score, rsi_series
from utils.market_data import to_daily

HORIZONS = {"1M": 21, "3M": 63, "6M": 126, "12M": 252}
COOLDOWN = 20
SELL_PTS = 5      # same as advise(): risk >= 5 → SELL
CAUTION_PTS = 3   # several flags at once
REENTRY_PTS = 2   # strategy re-enters when risk falls back to <= 2 (or an ADD fires)


def build_features(closes: pd.DataFrame, symbol: str, peers: List[str]) -> pd.DataFrame:
    px = to_daily(closes[symbol].dropna())
    cal = px.index
    f = pd.DataFrame(index=cal)
    f["price"] = px
    f["sma50"] = px.rolling(50).mean()
    f["sma200"] = px.rolling(200).mean()
    hi = px.rolling(252, min_periods=200).max()
    f["drawdown"] = px / hi - 1
    f["rsi"] = rsi_series(px)
    # Bitcoin on its own 7-day calendar, then lagged one day and carried onto stock dates
    if "BTC-USD" in closes.columns:
        btc = to_daily(closes["BTC-USD"].dropna())
        b = pd.DataFrame({"btc": btc, "btc200": btc.rolling(200).mean()}).shift(1)
        b = b.reindex(b.index.union(cal)).ffill().reindex(cal)
        f["btc"], f["btc200"] = b["btc"], b["btc200"]
    else:
        f["btc"] = f["btc200"] = np.nan
    f["vix"] = to_daily(closes["^VIX"].dropna()).reindex(cal) if "^VIX" in closes.columns else np.nan
    # Peer basket (equal-weight of whatever peers traded that day)
    pc = [p for p in peers if p in closes.columns and p != symbol]
    if pc:
        pp = pd.DataFrame({p: to_daily(closes[p].dropna()) for p in pc}).reindex(cal)
        rets = pp.pct_change(fill_method=None)
        basket = (1 + rets.mean(axis=1).fillna(0)).cumprod()
        f["peer_vs_200"] = basket / basket.rolling(200).mean() - 1
        f.loc[rets.notna().sum(axis=1).rolling(200).min() < 2, "peer_vs_200"] = np.nan
        lr = np.log(px).diff()
        plr = np.log(pp).diff().mean(axis=1)
        gap = (np.exp(lr.rolling(20).sum()) - 1) - (np.exp(plr.rolling(20).sum()) - 1)
        c20 = lr.rolling(20).corr(plr)
        c252 = lr.rolling(252).corr(plr)
        f["peer_gap"] = gap
        f["diverging"] = ((c20 < c252 - 0.25) | (gap.abs() > 0.15)) & c252.notna()
    else:
        f["peer_vs_200"] = f["peer_gap"] = np.nan
        f["diverging"] = False
    return f


def _nz(v):
    return None if v is None or (isinstance(v, float) and np.isnan(v)) else float(v)


def score_days(f: pd.DataFrame) -> pd.DataFrame:
    risk, add, nov = [], [], []
    for row in f.itertuples():
        risk.append(market_risk_score(row.price, _nz(row.sma50), _nz(row.sma200), _nz(row.drawdown),
                                      _nz(row.btc), _nz(row.btc200), _nz(row.vix),
                                      _nz(row.peer_gap), bool(row.diverging)))
        r = add_rule(_nz(row.rsi), row.price, _nz(row.sma200), _nz(row.drawdown), _nz(row.btc),
                     _nz(row.btc200), _nz(row.vix), _nz(row.peer_vs_200))
        add.append(r["signal"]); nov.append(r["n_oversold"])
    out = f.copy()
    out["risk"] = risk
    out["add"] = add
    out["n_oversold"] = nov
    out["warm"] = f[["sma200", "drawdown", "btc200", "vix"]].notna().all(axis=1)
    return out


def episodes(flag: pd.Series, cooldown: int = COOLDOWN) -> pd.DatetimeIndex:
    """First day of each run of True, ignoring re-triggers within `cooldown` days of the last True."""
    days, last_true = [], -10**9
    for i, v in enumerate(flag.values):
        if v:
            if i - last_true > cooldown:
                days.append(flag.index[i])
            last_true = i
    return pd.DatetimeIndex(days)


def forward_returns(px: pd.Series, dates: pd.DatetimeIndex) -> pd.DataFrame:
    """Return from the close AFTER each date to `h` trading days later. NaN if not enough future yet."""
    pos = px.index.get_indexer(dates)
    rows = []
    for d, i in zip(dates, pos):
        e = i + 1
        row = {"date": d, "entry": float(px.iloc[e]) if e < len(px) else np.nan}
        for k, h in HORIZONS.items():
            row[k] = float(px.iloc[e + h] / px.iloc[e] - 1) if e + h < len(px) else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def baseline(px: pd.Series, start) -> Dict[str, dict]:
    """'Any day' benchmark: forward returns from every day in the window (what just holding gave)."""
    out = {}
    for k, h in HORIZONS.items():
        r = (px.shift(-(h + 1)) / px.shift(-1) - 1)[px.index >= start].dropna()
        out[k] = {"n": int(len(r)), "avg": float(r.mean()) if len(r) else np.nan,
                  "median": float(r.median()) if len(r) else np.nan, "up": float((r > 0).mean()) if len(r) else np.nan}
    return out


def summarize(fr: pd.DataFrame, good_if_up: bool) -> Dict[str, dict]:
    out = {}
    for k in HORIZONS:
        r = fr[k].dropna() if k in fr else pd.Series(dtype=float)
        hit = (r > 0) if good_if_up else (r < 0)
        out[k] = {"n": int(len(r)), "avg": float(r.mean()) if len(r) else np.nan,
                  "median": float(r.median()) if len(r) else np.nan, "hit": float(hit.mean()) if len(r) else np.nan}
    return out


def strategy_vs_hold(s: pd.DataFrame, start) -> dict:
    """Follow the rules: exit the day after a SELL, re-enter the day after an ADD or once risk <= REENTRY_PTS.
    Positions change at the next close (no lookahead). No costs/taxes included."""
    d = s[s.index >= start]
    if len(d) < 30:
        return {}
    ret = d["price"].pct_change().fillna(0)
    invested, state = [], True
    for _, row in d.iterrows():
        invested.append(state)                       # position held INTO the next day
        if state and row.risk >= SELL_PTS:
            state = False
        elif not state and (row.add or row.risk <= REENTRY_PTS):
            state = True
    pos = pd.Series(invested, index=d.index, dtype=bool).shift(1, fill_value=True)
    strat = (1 + ret * pos.astype(float)).cumprod()
    hold = (1 + ret).cumprod()
    mdd = lambda eq: float((eq / eq.cummax() - 1).min())
    return {"strategy_total": float(strat.iloc[-1] - 1), "hold_total": float(hold.iloc[-1] - 1),
            "strategy_mdd": mdd(strat), "hold_mdd": mdd(hold), "time_invested": float(pos.mean()),
            "switches": int((pos.astype(int).diff().abs() > 0).sum()),
            "equity": pd.DataFrame({"Follow the rules": strat, "Just hold": hold})}


def run_backtest(closes: pd.DataFrame, symbol: str, peers: List[str], years: int = 5) -> dict:
    f = build_features(closes, symbol, peers)
    s = score_days(f)
    s = s[s["warm"]]
    if s.empty:
        return {}
    start = s.index[-1] - pd.DateOffset(years=years)
    w = s[s.index >= start]
    px = s["price"]
    # episodes are found on the full (warm) history so a state already "on" at the window start
    # isn't counted as a new signal
    inwin = lambda ix: ix[ix > w.index[0]]
    sigs = {
        "ADD": (inwin(episodes(s["add"])), True),
        "SELL (5+ risk pts)": (inwin(episodes(s["risk"] >= SELL_PTS)), False),
        "Caution (3+ risk pts)": (inwin(episodes(s["risk"] >= CAUTION_PTS)), False),
    }
    table, summary = [], {}
    for name, (days, up) in sigs.items():
        fr = forward_returns(px, days)
        summary[name] = summarize(fr, up)
        for _, r in fr.iterrows():
            table.append({"Signal": name, "Date": r["date"].date(), "Price next close": r["entry"],
                          **{k: r[k] for k in HORIZONS},
                          "Risk pts": int(w.loc[r["date"], "risk"]), "RSI": w.loc[r["date"], "rsi"]})
    return {"symbol": symbol, "start": w.index[0].date(), "end": w.index[-1].date(), "days": int(len(w)),
            "summary": summary, "baseline": baseline(px, w.index[0]), "signals": pd.DataFrame(table),
            "strategy": strategy_vs_hold(s, w.index[0]),
            "days_in_state": {"ADD": int(w["add"].sum()), "SELL": int((w["risk"] >= SELL_PTS).sum()),
                              "Caution": int((w["risk"] >= CAUTION_PTS).sum())}}


def verdict(name: str, summ: dict, base: dict, horizon: str = "6M") -> str:
    """Plain-English 'did this signal help?' using the given horizon vs the any-day baseline."""
    sm, b = summ.get(horizon, {}), base.get(horizon, {})
    n = sm.get("n", 0)
    if not n or np.isnan(sm.get("avg", np.nan)):
        return f"{name}: no completed signals in this window — no evidence either way."
    edge = sm["avg"] - b["avg"]
    good = edge > 0 if name.startswith("ADD") else edge < 0
    what = ("bought better than a random day" if good else "bought worse than a random day") if name.startswith("ADD") \
        else ("came before weaker-than-normal returns (helped)" if good else "came before normal-or-better returns (selling would have hurt)")
    return (f"{name}: {n} signals; {horizon} later RIOT averaged {sm['avg']:+.0%} vs {b['avg']:+.0%} for any day "
            f"→ {what}. Trust: {trust_label(n)}.")


def trust_label(n: int) -> str:
    if n < 5:
        return "very low — too few signals to judge"
    if n < 15:
        return "low — small sample, treat as anecdotes"
    if n < 30:
        return "moderate"
    return "reasonable sample"
