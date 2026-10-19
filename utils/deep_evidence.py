"""utils/deep_evidence.py — pure, unit-tested calculations behind the Verdict's "Deeper evidence" section.

Nothing here touches the network.  Fetchers live in utils/deep_sources.py; cited facts in utils/deep_facts.py.
Every function returns None (→ N/A in the UI) rather than guessing when its inputs are missing.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from utils import reflexivity as rx
from utils.market_data import to_daily, to_stock_calendar

HORIZONS = (126, 252)          # ~6 and ~12 months — long-cycle questions


# ── 1. Long-cycle Bitcoin valuation (MVRV, MVRV-Z, Puell, realized price) ──
def cycle_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """From CoinMetrics community columns (CapMVRVCur, CapMrktCurUSD, IssTotUSD, SplyCur, PriceUSD) build:
    realized cap = market cap ÷ MVRV; MVRV-Z = (market cap − realized cap) ÷ std of market cap **to date**
    (expanding, so every value is point-in-time); Puell = daily issuance $ ÷ its 365-day average;
    realized price = realized cap ÷ supply."""
    need = {"CapMVRVCur", "CapMrktCurUSD"}
    if df is None or df.empty or not need.issubset(df.columns):
        return pd.DataFrame()
    d = df.astype(float).sort_index()
    out = pd.DataFrame(index=d.index)
    out["mvrv"] = d["CapMVRVCur"]
    mc = d["CapMrktCurUSD"]
    rc = mc / d["CapMVRVCur"]
    out["realized_cap"] = rc
    sd = mc.expanding(min_periods=365).std()
    out["mvrv_z"] = (mc - rc) / sd
    if "IssTotUSD" in d:
        out["puell"] = d["IssTotUSD"] / d["IssTotUSD"].rolling(365, min_periods=300).mean()
    if "SplyCur" in d:
        out["realized_price"] = rc / d["SplyCur"]
    if "PriceUSD" in d:
        out["price"] = d["PriceUSD"]
    return out


def mvrv_zone(z: Optional[float]) -> Optional[str]:
    """Conventional MVRV-Z bands (widely used rule of thumb, not a law)."""
    if z is None or (isinstance(z, float) and math.isnan(z)):
        return None
    return "cheap (Z < 0.5)" if z < 0.5 else "hot (Z > 5)" if z > 5 else "middle (0.5–5)"


def puell_zone(p: Optional[float]) -> Optional[str]:
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return None
    return "miner stress (< 0.6)" if p < 0.6 else "miner windfall (> 2)" if p > 2 else "normal (0.6–2)"


def zone_lean(zone: Optional[str]) -> Optional[float]:
    if zone is None:
        return None
    return 1.0 if zone.startswith(("cheap", "miner stress")) else -1.0 if zone.startswith(("hot", "miner windfall")) else 0.0


def zone_backtest(stock: pd.Series, metric: pd.Series, zone_fn, delay: int = 2) -> Dict[int, pd.DataFrame]:
    """Point-in-time: the on-chain value for day d (published ~1 day later) labels stock date d; we act `delay`
    stock closes later.  Returns {horizon: rx.backtest_labels table}."""
    s = to_daily(stock).dropna()
    if len(s) < 300 or metric is None or metric.dropna().empty:
        return {}
    m = to_stock_calendar(metric, s.index)
    labels = pd.Series([zone_fn(v) if v == v else None for v in m.values], index=s.index, dtype=object)
    return {h: rx.backtest_labels(s, labels, h, delay=delay) for h in HORIZONS}


def edge_for_label(tables: Dict[int, pd.DataFrame], label: Optional[str]) -> Optional[dict]:
    """The strongest backtested result for the CURRENT label: {'h','verdict','typical','n','t'} or None."""
    best = None
    for h, t in tables.items():
        if label is None or t is None or not len(t):
            continue
        row = t[t["label"] == label]
        if row.empty:
            continue
        r = row.iloc[0]
        cand = {"h": h, "verdict": r["verdict"], "typical": r["typical_return"], "n": int(r["n"]),
                "t": None if r["t_vs_all"] != r["t_vs_all"] else float(r["t_vs_all"]),
                "baseline": t.attrs.get("baseline_typical")}
        if best is None or abs(cand["t"] or 0) > abs(best["t"] or 0):
            best = cand
    return best


def edge_weight_and_lean(edge: Optional[dict], weight_if_edge: float = 5.0):
    """Weight only if the current label's backtest is significant (n ≥ 8, |t| ≥ 2); lean = the sign it found."""
    if not edge or edge["verdict"] not in ("better than average", "worse than average"):
        return 0.0, None
    return weight_if_edge, (1.0 if edge["verdict"] == "better than average" else -1.0)


# ── 7. Volatility regime (transparent, point-in-time) ──────────────────
VOL_WIN, PCT_WIN = 21, 504


def vol_regime_labels(close: pd.Series, vol_win: int = VOL_WIN, pct_win: int = PCT_WIN) -> pd.Series:
    """Each day: 21-day realised volatility, ranked against the previous ~2 years of its own values (only past
    data).  Bottom third = 'calm', top third = 'stormy', else 'normal'."""
    c = to_daily(close).dropna()
    lr = np.log(c).diff()
    vol = lr.rolling(vol_win).std()
    pct = rx.percentile_rank_trailing(vol, pct_win)
    def lab(p):
        if p is None or p != p:
            return None
        return "calm" if p < 1 / 3 else "stormy" if p > 2 / 3 else "normal"
    return pd.Series([lab(p) for p in pct.values], index=c.index, dtype=object)


# ── 3. Convertibles → potential dilution ───────────────────────────────
def convert_dilution(facts: Optional[dict], price: Optional[float], today: Optional[date] = None) -> Optional[dict]:
    if not facts or not facts.get("shares_outstanding"):
        return None
    today = today or date.today()
    so = float(facts["shares_outstanding"])
    rows = []
    for n in facts.get("notes", []):
        if n["maturity"] < today:
            continue
        sh = n.get("shares_if_converted") or n["principal"] / 1000 * n["conversion_rate_per_1000"]
        m = (price / n["conversion_price"]) if price else None
        rows.append({"name": n["name"], "shares": float(sh), "pct": sh / so, "conversion_price": n["conversion_price"],
                     "moneyness": m, "maturity": n["maturity"], "principal": n["principal"]})
    other = sum(o["shares"] for o in facts.get("other", []) if "reserved" not in o["name"])
    atm = facts.get("atm_capacity_usd")
    atm_sh = atm / price if (atm and price) else None
    notes_sh = sum(r["shares"] for r in rows)
    return {"notes": rows, "notes_shares": notes_sh, "notes_pct": notes_sh / so, "other_shares": other,
            "other_pct": other / so, "atm_shares": atm_sh, "atm_pct": (atm_sh / so) if atm_sh else None,
            "shares_outstanding": so}


def lean_converts(d: Optional[dict]) -> Optional[float]:
    """Structural: big convertible overhang that is at/near the money is a dilution risk for holders."""
    if not d:
        return None
    if not d["notes"]:
        return 0.0
    near = [r for r in d["notes"] if r["moneyness"] is not None and r["moneyness"] >= 0.8]
    pct = sum(r["pct"] for r in near)
    if pct >= 0.10 and any(r["moneyness"] >= 1.0 for r in near):
        return -1.0
    if pct >= 0.05:
        return -0.5
    return 0.0


# ── 2. Treasury flows ──────────────────────────────────────────────────
def treasury_summary(rows: Optional[List[dict]]) -> Optional[dict]:
    if not rows:
        return None
    last = rows[-1]
    sold_ratio = last["sold"] / last["produced"] if last.get("produced") else None
    held_change = None
    if len(rows) >= 2 and rows[-2].get("held"):
        held_change = last["held"] / rows[-2]["held"] - 1
    return {"period": last["period"], "produced": last["produced"], "sold": last["sold"], "held": last["held"],
            "sold_ratio": sold_ratio, "held_change": held_change, "end": last["end"]}


# ── 4. AI/HPC peer valuation ───────────────────────────────────────────
def peer_valuation(ev: Dict[str, Optional[float]], facts: Dict[str, dict]) -> pd.DataFrame:
    rows = []
    for s, f in facts.items():
        e = ev.get(s)
        rows.append({"symbol": s, "ev": e, "mw": f.get("mw"), "contract_usd": f.get("contract_usd"),
                     "hpc_rev_q": f.get("hpc_rev_q"),
                     "ev_per_mw": (e / f["mw"]) if (e and f.get("mw")) else None,
                     "ev_per_contract": (e / f["contract_usd"]) if (e and f.get("contract_usd")) else None,
                     "ev_per_hpc_rev": (e / (4 * f["hpc_rev_q"])) if (e and f.get("hpc_rev_q")) else None,
                     "as_of": f.get("as_of"), "kind": f.get("kind", "")})
    return pd.DataFrame(rows)


def peer_relative(table: pd.DataFrame, symbol: str, col: str = "ev_per_mw") -> Optional[dict]:
    if table is None or table.empty or symbol not in set(table["symbol"]):
        return None
    v = table.loc[table["symbol"] == symbol, col].iloc[0]
    others = table.loc[(table["symbol"] != symbol) & table[col].notna(), col]
    if v is None or v != v or len(others) < 3:
        return None
    med = float(others.median())
    return {"value": float(v), "median": med, "ratio": float(v) / med, "n_peers": int(len(others))}


def lean_peer(rel: Optional[dict]) -> Optional[float]:
    if not rel:
        return None
    return 0.5 if rel["ratio"] <= 0.7 else -0.5 if rel["ratio"] >= 1.5 else 0.0


# ── 5. Options fear: 25-delta skew and max pain ────────────────────────
def bs_delta(kind: str, spot: float, strike: float, t_years: float, iv: float, r: float = 0.04) -> Optional[float]:
    if not (spot > 0 and strike > 0 and t_years > 0 and iv and iv > 0):
        return None
    d1 = (math.log(spot / strike) + (r + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    n = 0.5 * (1 + math.erf(d1 / math.sqrt(2)))
    return n if kind == "call" else n - 1


def _clean(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    d = df.copy()
    d = d[(d.get("bid", 0) > 0) & (d.get("openInterest", 0).fillna(0) > 0) & (d["impliedVolatility"] > 0.05)
          & (d["impliedVolatility"] < 5)]
    return d


def skew_25d(calls: pd.DataFrame, puts: pd.DataFrame, spot: float, t_years: float) -> Optional[dict]:
    """IV of the ~25-delta put minus IV of the ~25-delta call (positive = paying up for downside protection)."""
    c, p = _clean(calls), _clean(puts)
    if c.empty or p.empty or not spot or t_years <= 0:
        return None
    c = c.assign(delta=[bs_delta("call", spot, k, t_years, iv) for k, iv in zip(c.strike, c.impliedVolatility)])
    p = p.assign(delta=[bs_delta("put", spot, k, t_years, iv) for k, iv in zip(p.strike, p.impliedVolatility)])
    c, p = c.dropna(subset=["delta"]), p.dropna(subset=["delta"])
    if c.empty or p.empty:
        return None
    ci = (c.delta - 0.25).abs().idxmin()
    pi = (p.delta + 0.25).abs().idxmin()
    if abs(c.delta[ci] - 0.25) > 0.12 or abs(p.delta[pi] + 0.25) > 0.12:
        return None                          # no strike near 25-delta → don't pretend
    return {"skew": float(p.impliedVolatility[pi] - c.impliedVolatility[ci]),
            "put_iv": float(p.impliedVolatility[pi]), "call_iv": float(c.impliedVolatility[ci]),
            "put_strike": float(p.strike[pi]), "call_strike": float(c.strike[ci])}


def max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> Optional[float]:
    """Strike at which option holders would collectively get the least at expiry (by open interest)."""
    if calls is None or puts is None or calls.empty or puts.empty:
        return None
    co = calls[["strike", "openInterest"]].fillna(0)
    po = puts[["strike", "openInterest"]].fillna(0)
    if co.openInterest.sum() + po.openInterest.sum() <= 0:
        return None
    strikes = sorted(set(co.strike) | set(po.strike))
    def pay(k):
        return float(((k - co.strike).clip(lower=0) * co.openInterest).sum()
                     + ((po.strike - k).clip(lower=0) * po.openInterest).sum())
    return float(min(strikes, key=pay))


def put_call_oi(calls: pd.DataFrame, puts: pd.DataFrame) -> Optional[float]:
    if calls is None or puts is None or calls.empty or puts.empty:
        return None
    c = float(calls["openInterest"].fillna(0).sum())
    return float(puts["openInterest"].fillna(0).sum()) / c if c > 0 else None


# ── 6. Prediction markets ──────────────────────────────────────────────
def polymarket_yes(event: dict) -> List[dict]:
    """[{question, yes, volume}] for the open markets of a Polymarket gamma event."""
    import json
    out = []
    for m in (event or {}).get("markets", []) or []:
        if m.get("closed") or not m.get("outcomePrices"):
            continue
        try:
            px = m["outcomePrices"]
            px = json.loads(px) if isinstance(px, str) else px
            outcomes = m.get("outcomes")
            outcomes = json.loads(outcomes) if isinstance(outcomes, str) else (outcomes or ["Yes", "No"])
            yes = float(px[outcomes.index("Yes")]) if "Yes" in outcomes else float(px[0])
        except Exception:
            continue
        out.append({"question": m.get("question") or event.get("title"), "yes": yes,
                    "volume": float(m.get("volume") or 0)})
    return sorted(out, key=lambda r: -r["yes"])


def kalshi_yes(event: dict) -> List[dict]:
    out = []
    for m in (event or {}).get("markets", []) or []:
        try:
            yb, ya = m.get("yes_bid_dollars"), m.get("yes_ask_dollars")
            nb, na = m.get("no_bid_dollars"), m.get("no_ask_dollars")
            if yb is not None and ya is not None and float(ya) > 0:
                yes = (float(yb) + float(ya)) / 2                       # mid of the yes quote
            elif nb is not None and na is not None and float(na) > 0:
                yes = 1 - (float(nb) + float(na)) / 2                   # implied from the no quote
            else:
                yes = float(m.get("last_price_dollars"))
        except Exception:
            continue
        out.append({"question": m.get("yes_sub_title") or m.get("subtitle") or m.get("title"), "yes": yes,
                    "close": m.get("close_time")})
    return sorted(out, key=lambda r: -r["yes"])


def short_question(q: str) -> str:
    """'Will the Democratic Party control the House after the 2026 Midterm elections?' → 'Democratic Party'."""
    import re
    q = (q or "").strip().rstrip("?")
    m = re.match(r"Will the (.+?) control the", q)
    if m:
        return m.group(1)
    return re.sub(r"\s*\(H\.R\.\d+\)", "", q.replace("Will ", "")) + " — yes"


# ── 8. Short interest ──────────────────────────────────────────────────
def short_interest(info: Optional[dict]) -> Optional[dict]:
    if not info:
        return None
    spf, sr = info.get("shortPercentOfFloat"), info.get("shortRatio")
    if spf is None and sr is None:
        return None
    ts = info.get("dateShortInterest")
    cur, prev = info.get("sharesShort"), info.get("sharesShortPriorMonth")
    return {"pct_float": spf, "days_to_cover": sr,
            "as_of": date.fromtimestamp(int(ts)) if ts else None,
            "change": (cur / prev - 1) if (cur and prev) else None}


def short_label(si: Optional[dict]) -> Optional[str]:
    if not si or si.get("pct_float") is None:
        return None
    p = si["pct_float"]
    return "very high (>20% of float)" if p > 0.20 else "high (10–20%)" if p > 0.10 else "moderate (5–10%)" if p > 0.05 else "low (<5%)"
