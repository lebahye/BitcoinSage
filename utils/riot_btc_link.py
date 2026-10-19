"""utils/riot_btc_link.py — how much does Bitcoin move a miner's stock over the long run?

Model (quarterly, log scale — explained in plain English in the UI):
    change in ln(stock) over a quarter = alpha + beta * change in ln(BTC) + noise

  * beta  ("BTC sensitivity"): +1% in BTC has historically meant about +beta% in the stock.
  * alpha (the stock's own drift apart from BTC): for RIOT this was strongly negative — mostly share dilution.
  * We also fit the LEVEL relationship  ln(stock) = a + b ln(BTC)  only to measure how far the stock usually
    strays from its BTC-implied level (residual σ) and how quickly that gap closes (autocorrelation ρ).
    Over a multi-year horizon that "stray" band — not the raw quarterly noise — sets the range, because the
    gap has historically mean-reverted (ρ < 1).
  * Instability is reported with rolling 12-quarter (3-year) betas.  RIOT's beta fell from ~1.1–1.7 to ~0.2 after
    its AI/HPC data-centre pivot, so we show both a "full history" and a "recent 3 years" regime.

Projection to year T (non-BTC factors replace the historical alpha, as yearly % you can edit):
    ln(S_T / S_0) = beta * ln(B_T / B_0) + years * sum(ln(1 + factor_i))       ± sigma_h
Inverse (the BTC price that "lines up" with a stock target X):
    B_T = B_0 * exp( (ln(X / S_0) - years * sum(...) -/+ sigma_h) / beta )

Every function only uses data up to `as_of` — see tests/test_btc_2030.py (no future-data leakage).
"""
from __future__ import annotations

import math
from typing import Dict, Optional

import numpy as np
import pandas as pd

from utils.market_data import to_daily, to_stock_calendar

FIT_START = "2018-01-01"      # RIOT became a bitcoin miner (renamed from Bioptix) in late 2017
FREQ = "QE"
ROLL_Q = 12                   # 3-year rolling windows
MIN_Q = 12
NOT_REACHABLE_MULT = 100.0    # inverse BTC > 100x today => "BTC alone can't plausibly do it"

AI_SOURCES = {
    "riot_anthropic": {"label": "Riot: 20-year, 191 MW Rockdale data-centre lease (~$9.1B) with a frontier AI lab "
                                "(reported: Anthropic); 96 MW due Dec 2027, full by Jun 2028; ~$9.8B contracted incl. AMD",
                       "url": "https://www.datacenterdynamics.com/en/news/riot-platforms-agrees-191mw-20-year-lease-agreement-with-anthropic-worth-91bn-report/",
                       "date": "2026-08-11"},
    "riot_corsicana": {"label": "Riot 8-K: entire Corsicana site (1 GW power, up to 756 MW IT) under a NON-BINDING letter "
                                "of intent with one tenant — terms not disclosed",
                       "url": "https://www.sec.gov/Archives/edgar/data/1167419/000110465926093406/riot-20260810x8k.htm",
                       "date": "2026-08-10"},
}

# Non-BTC factors (yearly %, positive helps the stock).  Defaults are neutral except dilution (measured).
FACTORS = [
    ("dilution", "Share dilution (new shares issued) %/yr",
     "Each year the company issues new shares, your slice of the company shrinks. Default = the measured share-count "
     "growth over the last 12 months. RIOT's share count grew ~45%/yr in 2019–2024 but only a few % in the last year.",
     -1),
    ("hashprice", "Hashprice headwind %/yr (network hashrate outgrowing Riot's fleet)",
     "Miners split a fixed reward pool. If the whole network's computing power grows faster than Riot's own fleet, "
     "Riot's share of the bitcoin mined each day shrinks. The 2028 halving also cuts the reward in half. 0 = Riot keeps pace.",
     -1),
    ("energy", "Energy-cost drag %/yr",
     "Electricity is a miner's biggest cost. Rising Texas power prices squeeze profit; Riot also earns power credits. 0 = neutral.",
     -1),
    ("ai_hpc", "AI / data-centre uplift %/yr",
     "Extra value from leasing data-centre space to AI companies (not tied to BTC). Riot has ~$9.8B of contracted long-term "
     "leases (AMD + a frontier AI lab, starting 2026–2028); the Corsicana deal is a non-binding letter of intent. 0 = adds no "
     "value beyond what the share price already reflects.",
     +1),
]


def _quarterly_logs(stock: pd.Series, btc: pd.Series, as_of=None, start: str = FIT_START) -> pd.DataFrame:
    s = to_daily(stock).dropna()
    s = s[s > 0]
    b = to_daily(btc).dropna()
    if as_of is not None:
        cut = pd.Timestamp(as_of).normalize()
        s, b = s[s.index <= cut], b[b.index <= cut]
    s = s[s.index >= pd.Timestamp(start)]
    if s.empty or b.empty:
        return pd.DataFrame(columns=["s", "b"])
    bb = to_stock_calendar(b, s.index)
    df = pd.DataFrame({"s": s, "b": bb}).dropna()
    df = df[df.b > 0]
    if df.empty:
        return pd.DataFrame(columns=["s", "b"])
    q = np.log(df.resample(FREQ).last().dropna())
    q.attrs["last_date"] = df.index[-1].date()
    return q


def _ols(x: np.ndarray, y: np.ndarray):
    xm, ym = x.mean(), y.mean()
    sxx = ((x - xm) ** 2).sum()
    beta = ((x - xm) * (y - ym)).sum() / sxx
    alpha = ym - beta * xm
    res = y - (alpha + beta * x)
    r2 = 1 - (res ** 2).sum() / ((y - ym) ** 2).sum()
    se = math.sqrt((res ** 2).sum() / max(1, len(x) - 2) / sxx)
    return float(alpha), float(beta), float(r2), res, float(se)


def fit_link(stock: pd.Series, btc: pd.Series, as_of=None, start: str = FIT_START) -> Optional[dict]:
    """Fit the long-horizon stock↔BTC link using only data up to `as_of`. None if < 3 years of quarters."""
    q = _quarterly_logs(stock, btc, as_of, start)
    if len(q) < MIN_Q + 1:
        return None
    d = q.diff().dropna()
    a, beta, r2, res_q, se = _ols(d.b.values, d.s.values)
    la, lb, lr2, res_l, _ = _ols(q.b.values, q.s.values)
    res_l = pd.Series(res_l, index=q.index)
    rho = float(np.clip(res_l.autocorr(), 0.0, 0.98)) if len(res_l) > 3 else 0.9
    rolling = []
    for i in range(ROLL_Q, len(d) + 1):
        w = d.iloc[i - ROLL_Q:i]
        _, rb, rr2, _, _ = _ols(w.b.values, w.s.values)
        rolling.append({"end": w.index[-1], "beta": rb, "r2": rr2})
    roll = pd.DataFrame(rolling).set_index("end") if rolling else pd.DataFrame(columns=["beta", "r2"])
    recent = rolling[-1] if rolling else None
    return {
        "start": q.index[0].date(), "end": q.attrs.get("last_date", q.index[-1].date()), "n_quarters": int(len(d)),
        "beta": beta, "beta_se": se, "alpha_q": a, "alpha_yr": math.expm1(4 * a), "r2": r2,
        "resid_sd_q": float(np.std(res_q, ddof=1)),
        "level_beta": lb, "level_r2": lr2, "level_sd": float(res_l.std(ddof=1)), "rho_q": rho,
        "rolling": roll, "recent_beta": recent["beta"] if recent else None,
        "recent_r2": recent["r2"] if recent else None,
        "beta_min": float(roll.beta.min()) if len(roll) else None,
        "beta_max": float(roll.beta.max()) if len(roll) else None,
    }


def horizon_sigma(fit: dict, years: float) -> float:
    """Log-scale ±1σ for how far the stock may sit from its BTC-implied value after `years`
    (AR(1) gap: σ_level * sqrt(1 - ρ^(2h)), h in quarters)."""
    h = max(1.0, 4.0 * years)
    rho = fit["rho_q"]
    return float(fit["level_sd"] * math.sqrt(max(0.0, 1.0 - rho ** (2 * h))))


def drift_from_factors(factors: Dict[str, float]) -> float:
    """Yearly log drift from the non-BTC factors (each a yearly %; dilution/hashprice/energy hurt, AI/HPC helps)."""
    sign = {k: s for k, _, _, s in FACTORS}
    tot = 0.0
    for k, v in factors.items():
        if k in sign and v is not None:
            tot += sign[k] * math.log1p(float(v) / 100.0)
    return tot


def project_stock(s0: float, b0: float, b_t: float, years: float, beta: float,
                  drift_log_yr: float = 0.0, sigma: float = 0.0) -> dict:
    """Stock price implied by BTC reaching b_t, with a ±1σ range."""
    core = beta * math.log(b_t / b0) + years * drift_log_yr
    return {"point": s0 * math.exp(core), "low": s0 * math.exp(core - sigma), "high": s0 * math.exp(core + sigma)}


def btc_for_stock(target: float, s0: float, b0: float, years: float, beta: float,
                  drift_log_yr: float = 0.0, sigma: float = 0.0) -> dict:
    """BTC price at the horizon that lines up with the stock at `target`.
    low  = BTC needed if the stock runs 1σ ABOVE its BTC-implied value (lucky),
    high = BTC needed if it runs 1σ BELOW (unlucky).  'reachable' False when BTC alone would need > 100x."""
    if not (target > 0 and s0 > 0 and b0 > 0) or beta is None or beta <= 0.05:
        return {"point": None, "low": None, "high": None, "reachable": False}
    need = math.log(target / s0) - years * drift_log_yr

    def _b(z):
        return b0 * math.exp((need + z) / beta)
    out = {"point": _b(0.0), "low": _b(-sigma), "high": _b(sigma)}
    out["reachable"] = out["point"] <= NOT_REACHABLE_MULT * b0
    return out


def measured_dilution(shares: Optional[pd.Series], years: float = 1.0, as_of=None) -> Optional[float]:
    """Share-count growth %/yr over the last `years` (None if not enough data)."""
    if shares is None or len(shares) < 2:
        return None
    s = to_daily(shares).dropna()
    if as_of is not None:
        s = s[s.index <= pd.Timestamp(as_of)]
    if s.empty:
        return None
    end = s.index[-1]
    past = s[s.index <= end - pd.Timedelta(days=int(365.25 * years))]
    if past.empty or past.iloc[-1] <= 0:
        return None
    return float(((s.iloc[-1] / past.iloc[-1]) ** (1 / years) - 1) * 100)


def daily_corr(stock: pd.Series, btc: pd.Series, days: int = 252) -> Optional[float]:
    s = to_daily(stock).dropna()
    if len(s) < 60:
        return None
    b = to_stock_calendar(btc, s.index)
    r = pd.DataFrame({"s": np.log(s).diff(), "b": np.log(b).diff()}).dropna().iloc[-days:]
    return float(r.s.corr(r.b)) if len(r) > 30 else None


def halving_cycles(btc: pd.Series) -> list:
    """For each halving in the data: months from halving to the cycle peak (within 30 months) and
    the fall from that peak to the following low (within 15 months after the peak)."""
    b = to_daily(btc).dropna()
    out = []
    for h in ["2016-07-09", "2020-05-11", "2024-04-20"]:
        hd = pd.Timestamp(h)
        w = b[(b.index >= hd) & (b.index < hd + pd.Timedelta(days=915))]
        if len(w) < 200:
            continue
        pk = w.idxmax()
        after = b[(b.index > pk) & (b.index <= pk + pd.Timedelta(days=460))]
        out.append({"halving": hd.date(), "peak_date": pk.date(), "peak": float(w.max()),
                    "months": (pk - hd).days / 30.44,
                    "drawdown": float(after.min() / w.max() - 1) if len(after) else None,
                    "complete": len(after) >= 400})
    return out
