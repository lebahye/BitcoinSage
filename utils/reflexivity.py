"""utils/reflexivity.py — pure, testable maths behind the 🔄 Reflexivity tab.

Two different feedback loops matter for a bitcoin miner (see the tab's diagram):
  * the BALANCING loop of the network: BTC price ↑ → miners add machines → hashrate ↑ → difficulty ↑ → each
    machine earns less → margins squeezed back.  Difficulty adjustment pulls margins back toward the cost of power.
  * the REFLEXIVE (Soros) loop in the capital markets: share price ↑ → company sells new shares at high prices
    (ATM programmes) → buys machines/BTC/data centres → story & per-share numbers look better → share price ↑.
    In reverse: price ↓ → shares sold cheaply (dilution) or BTC sold → per-share value ↓ → price ↓.

Everything here is point-in-time: a value dated t only uses data up to t (tests/test_reflexivity.py).
"""
from __future__ import annotations

import math
from datetime import date
from typing import Dict, Iterable, Optional

import numpy as np
import pandas as pd

from utils.market_data import to_daily, to_stock_calendar

HALVING_INTERVAL = 210_000
TH = 1e12
# Halving dates (UTC, block timestamp) — fixed history, used to give each past day its correct block subsidy.
HALVING_DATES = [date(2012, 11, 28), date(2016, 7, 9), date(2020, 5, 11), date(2024, 4, 20)]
MOM_DAYS = 30            # trading days for "30-day" momentum
CORR_DAYS = 30
EDGE_MIN_N = 8           # minimum non-overlapping cases before we judge a phase
EDGE_T = 2.0             # |t| needed to call a difference "real"

PHASES = {
    "boom": ("🚀 Boom (miners and Bitcoin rising together)", "#00cc66"),
    "bust": ("📉 Bust (miners and Bitcoin falling together)", "#ff4444"),
    "lag": ("🔄 Miners lagging Bitcoin", "#f7931e"),
    "lead": ("🌱 Miners leading Bitcoin", "#66ddaa"),
    "none": ("➡️ No clear loop", "#8b8b9b"),
}
PHASE_PLAIN = {
    "boom": "Over the last 30 trading days Bitcoin and the miners both rose more than 5% and moved closely together.",
    "bust": "Over the last 30 trading days Bitcoin and the miners both fell more than 5% and moved closely together.",
    "lag": "The miners did at least 15 percentage points worse than Bitcoin over the last 30 trading days.",
    "lead": "The miners did at least 15 percentage points better than Bitcoin over the last 30 trading days.",
    "none": "None of the patterns above — prices are not in a clear joint boom or bust.",
}


# ── Prices ─────────────────────────────────────────────────────────────
def equal_weight_index(closes: pd.DataFrame) -> pd.Series:
    """Equal-weight basket from DAILY RETURNS (rebalanced daily), starting at 100.
    (Averaging share PRICES would let the highest-priced stock dominate.)  Days with no stock data are NaN."""
    if closes is None or closes.empty:
        return pd.Series(dtype=float)
    r = closes.pct_change(fill_method=None)
    avg = r.mean(axis=1, skipna=True)
    has = closes.notna().any(axis=1)
    avg[~has] = np.nan
    first = has.idxmax() if has.any() else None
    if first is None:
        return pd.Series(dtype=float)
    avg = avg[avg.index >= first]
    avg.iloc[0] = 0.0
    return 100 * (1 + avg.fillna(0)).cumprod()


def rolling_beta(stock: pd.Series, bench: pd.Series, window: int = CORR_DAYS) -> pd.Series:
    """Beta over the `window` daily returns ENDING on each date (inclusive)."""
    sr = stock.pct_change(fill_method=None)
    br = bench.pct_change(fill_method=None)
    df = pd.DataFrame({"s": sr, "b": br}).dropna()
    cov = df.s.rolling(window).cov(df.b)
    var = df.b.rolling(window).var()
    return (cov / var.where(var > 1e-12)).rename("beta")


def rolling_corr(a: pd.Series, b: pd.Series, window: int = CORR_DAYS) -> pd.Series:
    df = pd.DataFrame({"a": a.pct_change(fill_method=None), "b": b.pct_change(fill_method=None)}).dropna()
    return df.a.rolling(window).corr(df.b).rename("corr")


def momentum(s: pd.Series, days: int = MOM_DAYS) -> pd.Series:
    return s.pct_change(days, fill_method=None)


# ── Index & phase ──────────────────────────────────────────────────────
def coupling_index(corr: float, beta: float, btc_mom: float, miner_mom: float) -> Optional[dict]:
    """0–100 'Bitcoin co-movement' score (formerly 'Reflexivity Index').  It measures how tightly the miners
    are tracking and amplifying Bitcoin right now — NOT the strength of the capital-markets loop.
      coupling      = correlation (negative counts as 0)                    weight 3/8
      amplification = beta clipped to 0–3, scaled                           weight 3/8
      alignment     = 100 same direction, 0 opposite, 50 if either move < 2% weight 2/8
    Returns None if any input is missing (never a fake neutral value)."""
    vals = [corr, beta, btc_mom, miner_mom]
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in vals):
        return None
    coupling = max(0.0, min(corr, 1.0)) * 100
    amplif = max(0.0, min(beta, 3.0)) / 3.0 * 100
    if abs(btc_mom) < 0.02 or abs(miner_mom) < 0.02:
        align = 50.0
    else:
        align = 100.0 if btc_mom * miner_mom > 0 else 0.0
    idx = (3 * coupling + 3 * amplif + 2 * align) / 8
    return {"index": round(idx, 1), "coupling": round(coupling, 1), "amplification": round(amplif, 1),
            "alignment": align}


def detect_phase(btc_mom: float, miner_mom: float, corr: float) -> Optional[str]:
    """Descriptive phase key (see PHASES).  None if inputs missing."""
    if any(v is None or (isinstance(v, float) and math.isnan(v)) for v in (btc_mom, miner_mom, corr)):
        return None
    if btc_mom > 0.05 and miner_mom > 0.05 and corr >= 0.5:
        return "boom"
    if btc_mom < -0.05 and miner_mom < -0.05 and corr >= 0.5:
        return "bust"
    gap = miner_mom - btc_mom
    if gap <= -0.15:
        return "lag"
    if gap >= 0.15:
        return "lead"
    return "none"


def index_bucket(ix: Optional[float]) -> Optional[str]:
    if ix is None or (isinstance(ix, float) and math.isnan(ix)):
        return None
    return "low (<40)" if ix < 40 else ("high (≥65)" if ix >= 65 else "middle (40–65)")


def phase_frame(stock: pd.Series, btc: pd.Series) -> pd.DataFrame:
    """Daily frame on the STOCK calendar: momentum, corr, beta, index, bucket, phase.
    Row t uses only prices up to t.  BTC is put on the stock calendar with its same-day value (so daily returns
    line up for correlation); because Yahoo's BTC bar for day t closes ~4 h after the New York close, the BACKTEST
    acts on a phase only from the NEXT trading day (`backtest_labels(delay=1)`)."""
    s = to_daily(stock).dropna()
    b = to_stock_calendar(btc, s.index)
    df = pd.DataFrame({"stock": s, "btc": b}).dropna()
    if len(df) < MOM_DAYS + CORR_DAYS:
        return pd.DataFrame()
    df["btc_mom"] = momentum(df.btc)
    df["miner_mom"] = momentum(df.stock)
    df["corr"] = rolling_corr(df.stock, df.btc)
    df["beta"] = rolling_beta(df.stock, df.btc)
    ix, ph = [], []
    for r in df.itertuples():
        ci = coupling_index(r.corr, r.beta, r.btc_mom, r.miner_mom)
        ix.append(ci["index"] if ci else np.nan)
        ph.append(detect_phase(r.btc_mom, r.miner_mom, r.corr))
    df["index"] = ix
    df["phase"] = ph
    df["bucket"] = [index_bucket(v) for v in df["index"]]
    return df


# ── Backtest (point-in-time, non-overlapping) ──────────────────────────
def non_overlapping_entries(labels: pd.Series, horizon: int) -> Dict[str, list]:
    """For each label, the positions where it holds, keeping only entries at least `horizon` rows after the
    previous kept entry of the same label — so forward windows of one label never overlap."""
    out: Dict[str, list] = {}
    last: Dict[str, int] = {}
    for i, lab in enumerate(labels.values):
        if lab is None or (isinstance(lab, float) and math.isnan(lab)):
            continue
        if lab not in last or i - last[lab] >= horizon:
            out.setdefault(lab, []).append(i)
            last[lab] = i
    return out


def backtest_labels(price: pd.Series, labels: pd.Series, horizon: int, delay: int = 1) -> pd.DataFrame:
    """What happened next after each label.  A label seen at the close of day t is acted on at the close of
    t+`delay` (no look-ahead); the forward return runs from there for `horizon` trading days.  Entries are
    non-overlapping per label, and compared with a non-overlapping every-`horizon`-days baseline.
    Averages/t-stats use LOG returns (one +300% spike can't dominate); median and hit rate use simple returns."""
    price = price.reindex(labels.index)
    entry = price.shift(-delay)
    fwd = price.shift(-(delay + horizon)) / entry - 1
    valid = fwd.notna()
    labs = labels.where(valid)
    vpos = np.flatnonzero(valid.values)
    base = fwd.iloc[vpos[::horizon]] if len(vpos) else fwd.iloc[:0]
    lbase = np.log1p(base)
    rows = []
    for lab, pos in non_overlapping_entries(labs, horizon).items():
        r = fwd.iloc[pos].dropna()
        lr = np.log1p(r)
        n = len(r)
        sd = float(lr.std(ddof=1)) if n > 1 else np.nan
        t = (float(lr.mean()) - float(lbase.mean())) / (sd / math.sqrt(n)) if n > 1 and sd > 0 else np.nan
        if n < EDGE_MIN_N:
            verdict = "too few cases"
        elif not np.isnan(t) and abs(t) >= EDGE_T:
            verdict = "better than average" if t > 0 else "worse than average"
        else:
            verdict = "no reliable difference"
        rows.append({"label": lab, "n": n, "typical_return": float(np.expm1(lr.mean())) if n else np.nan,
                     "median_return": float(r.median()) if n else np.nan,
                     "hit_rate": float((r > 0).mean()) if n else np.nan, "t_vs_all": t, "verdict": verdict})
    out = pd.DataFrame(rows, columns=["label", "n", "typical_return", "median_return", "hit_rate", "t_vs_all", "verdict"])
    if len(out):
        out = out.sort_values("label").reset_index(drop=True)
    out.attrs.update({"baseline_typical": float(np.expm1(lbase.mean())) if len(base) else np.nan,
                      "baseline_median": float(base.median()) if len(base) else np.nan,
                      "baseline_hit": float((base > 0).mean()) if len(base) else np.nan,
                      "baseline_n": int(len(base)), "horizon": horizon, "delay": delay,
                      "start": labels.index[0].date() if len(labels) else None,
                      "end": labels.index[-1].date() if len(labels) else None})
    return out


def has_edge(table: pd.DataFrame) -> bool:
    return bool(len(table)) and table["verdict"].isin(["better than average", "worse than average"]).any()


# ── Mining economics ───────────────────────────────────────────────────
def subsidy_at_height(height: int) -> float:
    return 50.0 / 2 ** (int(height) // HALVING_INTERVAL)


def subsidy_on(day, next_halving: Optional[date] = None) -> float:
    """Block subsidy in force on a calendar day (history from HALVING_DATES; optional future halving)."""
    d = pd.Timestamp(day).date()
    dates = HALVING_DATES + ([next_halving] if next_halving else [])
    n = sum(1 for h in dates if d >= h)
    return 50.0 / 2 ** n


def network_power_breakeven(difficulty: float, j_per_th: float, usd_per_kwh: float,
                            reward_btc_per_block: float) -> Optional[float]:
    """Electricity cost to mine 1 BTC for a machine of `j_per_th`, at network difficulty.
    hashrate (TH/s) = D·2^32/600/1e12;  kWh/day = TH/s · J/TH · 86 400 / 3.6e6;  BTC/day = 144 · reward.
    POWER ONLY — excludes staff, repairs, hosting, depreciation, interest."""
    if not (difficulty and j_per_th and reward_btc_per_block) or difficulty <= 0 or reward_btc_per_block <= 0:
        return None
    ths = difficulty * 2 ** 32 / 600 / TH
    kwh_day = ths * j_per_th * 86_400 / 3_600_000
    return kwh_day * usd_per_kwh / (144 * reward_btc_per_block)


def hashprice_usd_per_ph_day(btc_price: float, hashrate_hs: float, reward_btc_per_block: float) -> Optional[float]:
    """What 1 PH/s of mining earns per day in USD (subsidy + fees)."""
    if not (btc_price and hashrate_hs and reward_btc_per_block) or hashrate_hs <= 0:
        return None
    btc_per_day_per_ph = 144 * reward_btc_per_block / (hashrate_hs / 1e15)
    return btc_per_day_per_ph * btc_price


def hashprice_history(btc: pd.Series, hashrate_hs: pd.Series, fees_btc_day: Optional[pd.Series] = None,
                      next_halving: Optional[date] = None) -> pd.Series:
    """Daily USD hashprice ($/PH/day) with the subsidy correct for each day and fees where available."""
    hr = to_daily(hashrate_hs).dropna()
    b = to_daily(btc).reindex(hr.index).ffill()
    sub = pd.Series([subsidy_on(d, next_halving) for d in hr.index], hr.index)
    fee_blk = (to_daily(fees_btc_day).reindex(hr.index).fillna(0) / 144) if fees_btc_day is not None and len(fees_btc_day) \
        else pd.Series(0.0, hr.index)
    return (144 * (sub + fee_blk) / (hr / 1e15) * b).dropna().rename("hashprice")


def difficulty_adjusted_cost(reported_cost: float, diff_then: float, diff_now: float) -> Optional[float]:
    """Rough update of a reported $/BTC mining cost for the change in difficulty since that quarter
    (same fleet & power price ⇒ cost per BTC scales with difficulty).  An estimate."""
    if not (reported_cost and diff_then and diff_now) or diff_then <= 0:
        return None
    return reported_cost * diff_now / diff_then


def percentile_rank_trailing(s: pd.Series, window: int = 730) -> pd.Series:
    """Point-in-time percentile (0–1) of each value within its own trailing window."""
    return s.rolling(window, min_periods=max(60, window // 4)).apply(lambda w: (w[:-1] < w[-1]).mean(), raw=True)


# ── Riot value check (sum of parts) ────────────────────────────────────
def annuity_pv(per_year: float, years: float, rate: float, start_in_years: float = 0.0) -> float:
    """Present value of `per_year` for `years`, starting `start_in_years` from now, discounted at `rate`."""
    if per_year is None or years <= 0:
        return 0.0
    if rate <= 0:
        pv = per_year * years
    else:
        pv = per_year * (1 - (1 + rate) ** -years) / rate
    return pv / (1 + max(rate, 0)) ** max(start_in_years, 0)


def sum_of_parts(price: float, shares: float, btc_price: float, btc_held: float, cash: float, debt: float,
                 lease_noi_per_year: float, lease_years: float, lease_start_years: float, discount: float,
                 build_cost_remaining: float = 0.0, mining_value: float = 0.0, other_value: float = 0.0,
                 btc_pledged: float = 0.0) -> Optional[dict]:
    """Rough 'what the parts are worth' vs the stock-market value.  None if price/shares missing."""
    if not (price and shares) or price <= 0 or shares <= 0:
        return None
    btc_val = (btc_held or 0) * (btc_price or 0)
    lease_pv = annuity_pv(lease_noi_per_year or 0, lease_years, discount, lease_start_years)
    parts = {"Bitcoin held": btc_val, "Cash": cash or 0.0, "AI data-centre lease (PV of NOI)": lease_pv,
             "Less: remaining build cost": -(build_cost_remaining or 0.0), "Bitcoin-mining business": mining_value or 0.0,
             "Other (land/power, other leases)": other_value or 0.0, "Less: debt": -(debt or 0.0)}
    total = sum(parts.values())
    mcap = price * shares
    return {"parts": parts, "total": total, "per_share": total / shares, "market_cap": mcap,
            "price": price, "ratio": mcap / total if total > 0 else None,
            "pledged_value": (btc_pledged or 0) * (btc_price or 0),
            "btc_only_mnav": mcap / btc_val if btc_val > 0 else None}


# ── Dilution & loop strength ───────────────────────────────────────────
def share_growth(shares: pd.Series, years: float, as_of=None) -> Optional[float]:
    s = to_daily(shares).dropna()
    if as_of is not None:
        s = s[s.index <= pd.Timestamp(as_of)]
    if len(s) < 2:
        return None
    end = s.index[-1]
    past = s[s.index <= end - pd.Timedelta(days=int(365.25 * years))]
    if past.empty or past.iloc[-1] <= 0:
        return None
    return float((s.iloc[-1] / past.iloc[-1]) ** (1 / years) - 1)


def quarterly_issuance_link(price: pd.Series, shares: pd.Series, window_q: int = 8) -> pd.DataFrame:
    """Capital-markets loop: stock return in quarter q vs share-count growth in quarter q+1.
    Returns quarterly frame with the pair and a rolling `window_q` correlation (dated at the END of q+1)."""
    p = to_daily(price).dropna().resample("QE").last()
    sh = to_daily(shares).dropna().resample("QE").last()
    df = pd.DataFrame({"ret": p.pct_change(fill_method=None), "issue_next": sh.pct_change(fill_method=None).shift(-1)}).dropna()
    df.index = df.index + pd.offsets.QuarterEnd(1)     # dated when the issuance became known
    df["rolling_corr"] = df.ret.rolling(window_q).corr(df.issue_next)
    return df


def hashrate_response(btc: pd.Series, hashrate_hs: pd.Series, lag_days: int = 90, window: int = 24) -> pd.DataFrame:
    """Network loop: BTC return over 90 days vs hashrate growth over the NEXT 90 days, sampled monthly, with a
    rolling `window`-month correlation dated when the hashrate growth is complete."""
    hr = to_daily(hashrate_hs).dropna().rolling(7).mean()
    b = to_daily(btc).reindex(hr.index).ffill()
    m = pd.DataFrame({"b": b, "h": hr}).dropna().resample("ME").last()
    step = max(1, round(lag_days / 30))
    df = pd.DataFrame({"btc_ret": m.b.pct_change(step, fill_method=None),
                       "hr_next": m.h.pct_change(step, fill_method=None).shift(-step)}).dropna()
    df.index = df.index + pd.DateOffset(months=step)
    df["rolling_corr"] = df.btc_ret.rolling(window).corr(df.hr_next)
    return df
