"""
utils/holding_advisor.py — Hold / Trim / Sell / Rotate guidance for a
RISK-AVERSE, LONG-TERM holder planning to sell or rotate around 2030.

Design principles
  * Every input is live (Yahoo Finance) or the user's own saved data
    (positions, cost basis, target prices).  Missing inputs are reported as
    missing and lower the confidence — they are never filled with a default.
  * A long-term plan should not be whipsawed by short-term noise, so the
    default is HOLD.  It takes several warning signs at once to say SELL,
    and the preferred risk-reducing action is TRIM (sell a slice), not
    all-or-nothing.
  * Each call comes with: the reasons, a confidence level, and concrete
    "what would change my mind" price/indicator levels.
Educational tool — not financial advice.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd


@dataclass
class Check:
    name: str
    status: str          # "good" | "warn" | "bad" | "info" | "missing"
    detail: str
    points: int = 0      # +risk points (positive = more risk)
    help_key: str = ""


@dataclass
class Advice:
    symbol: str
    action: str                      # HOLD | TRIM | SELL | ROTATE
    confidence: str                  # High | Medium | Low
    headline: str
    risk_score: int
    max_score: int
    checks: List[Check] = field(default_factory=list)
    change_my_mind: List[str] = field(default_factory=list)
    trim_pct: Optional[int] = None
    rotate_to: Optional[str] = None
    facts: Dict[str, float] = field(default_factory=dict)


def _sma(s: pd.Series, n: int) -> Optional[float]:
    s = s.dropna()
    return float(s.iloc[-n:].mean()) if len(s) >= n else None


def compute_facts(px: pd.Series) -> Dict[str, Optional[float]]:
    """Price facts from a daily close series (>= ~1 year preferred)."""
    px = px.dropna()
    if px.empty:
        return {}
    last = float(px.iloc[-1])
    yr = px.iloc[-252:]
    r = np.log(px / px.shift(1)).dropna()
    f = {
        "price": last,
        "sma50": _sma(px, 50),
        "sma200": _sma(px, 200),
        "high_52w": float(yr.max()),
        "low_52w": float(yr.min()),
        "drawdown": last / float(yr.max()) - 1.0,
        "ret_3m": (last / float(px.iloc[-63]) - 1.0) if len(px) > 63 else None,
        "ret_1y": (last / float(px.iloc[-252]) - 1.0) if len(px) > 252 else None,
        "vol_1y": float(r.iloc[-252:].std() * np.sqrt(252)) if len(r) > 60 else None,
    }
    return f


def advise(symbol: str,
           facts: Dict[str, Optional[float]],
           btc_facts: Dict[str, Optional[float]],
           vix_level: Optional[float],
           shares: float = 0.0,
           cost_basis: float = 0.0,
           portfolio_value: Optional[float] = None,
           target_price: Optional[float] = None,
           analyst: Optional[Dict[str, float]] = None,
           divergence: Optional[dict] = None,
           best_peer: Optional[dict] = None) -> Advice:
    checks: List[Check] = []
    change: List[str] = []
    price = facts.get("price")
    if price is None:
        return Advice(symbol, "HOLD", "Low", f"No price data for {symbol} — can't assess. Default is to hold and re-check.",
                      0, 0, [Check("Price data", "missing", "Yahoo Finance returned no prices.")])

    # 1. Long-term trend: price vs 200-day average
    sma200, sma50 = facts.get("sma200"), facts.get("sma50")
    if sma200:
        if price >= sma200:
            checks.append(Check("Long-term trend", "good",
                                f"Price ${price:,.2f} is above its 200-day average ${sma200:,.2f} (uptrend).", 0, "sma200"))
            change.append(f"A close below the 200-day average (~${sma200:,.2f}) would weaken the case for holding.")
        else:
            checks.append(Check("Long-term trend", "warn",
                                f"Price ${price:,.2f} is {price/sma200-1:+.0%} below its 200-day average ${sma200:,.2f} (downtrend).",
                                1, "sma200"))
            change.append(f"A sustained move back above the 200-day average (~${sma200:,.2f}) would turn the trend positive.")
        if sma50 and sma50 < sma200 and price < sma200:
            checks.append(Check("Trend confirmation", "warn",
                                f"50-day average ${sma50:,.2f} is below the 200-day — a 'death cross', typical of extended declines.",
                                1, "sma200"))
    else:
        checks.append(Check("Long-term trend", "missing", "Less than 200 days of history — trend check skipped."))

    # 2. Drawdown
    dd = facts.get("drawdown")
    if dd is not None:
        st_ = "bad" if dd <= -0.5 else "warn" if dd <= -0.3 else "good"
        pts = 1 if dd <= -0.4 else 0
        checks.append(Check("Drawdown from 52-week high", st_,
                            f"{dd:.0%} below the 52-week high of ${facts['high_52w']:,.2f}. "
                            + ("Deep drawdowns are common for miners; selling here locks in the loss, but it also shows how much risk you carry."
                               if dd <= -0.3 else "Near the highs."), pts, "drawdown"))
        change.append(f"A close below the 52-week low (${facts['low_52w']:,.2f}) would add a risk point.")

    # 3. Bitcoin regime
    bp, b200 = btc_facts.get("price"), btc_facts.get("sma200")
    if bp and b200:
        if bp >= b200:
            checks.append(Check("Bitcoin trend", "good", f"Bitcoin ${bp:,.0f} is above its 200-day average ${b200:,.0f}.", 0))
        else:
            checks.append(Check("Bitcoin trend", "warn",
                                f"Bitcoin ${bp:,.0f} is {bp/b200-1:+.0%} below its 200-day average ${b200:,.0f} — a crypto down-cycle hurts miners.", 1))
            change.append(f"Bitcoin reclaiming its 200-day average (~${b200:,.0f}) would remove a risk point.")
    else:
        checks.append(Check("Bitcoin trend", "missing", "Bitcoin price history unavailable."))

    # 4. Fear gauge
    if vix_level is not None:
        if vix_level >= 30:
            checks.append(Check("Market fear (VIX)", "bad", f"VIX {vix_level:.1f} — fear. Miners usually fall when fear spikes.", 2, "vix"))
        elif vix_level >= 25:
            checks.append(Check("Market fear (VIX)", "warn", f"VIX {vix_level:.1f} — nervous market.", 1, "vix"))
        else:
            checks.append(Check("Market fear (VIX)", "good", f"VIX {vix_level:.1f} — calm (under 25).", 0, "vix"))
            change.append("VIX rising above 25 (nervous) or 30 (fear) would add risk points.")
    else:
        checks.append(Check("Market fear (VIX)", "missing", "VIX unavailable."))

    # 5. Decoupling from peers (RIOT-specific divergence check)
    if divergence:
        gap = divergence["gap"]
        if divergence["diverging"] and gap < 0:
            checks.append(Check("Moving with peers?", "warn",
                                f"Lagging its closest peers by {gap:+.0%} over {divergence['lookback']} trading days — "
                                "may signal company-specific trouble.", 1, "decoupling"))
        elif divergence["diverging"]:
            checks.append(Check("Moving with peers?", "info",
                                f"Outperforming its closest peers by {gap:+.0%} over {divergence['lookback']} trading days.", 0, "decoupling"))
        else:
            checks.append(Check("Moving with peers?", "good",
                                f"Moving in line with peers (corr {divergence['corr_recent']:.2f}); no company-specific red flag.", 0, "decoupling"))

    # 6. Position: gain vs cost basis, concentration
    value = shares * price if shares else 0.0
    gain = (price / cost_basis - 1.0) if cost_basis else None
    weight = (value / portfolio_value) if (portfolio_value and value) else None
    if shares and cost_basis:
        checks.append(Check("Your gain/loss", "info",
                            f"{shares:,.0f} shares, cost ${cost_basis:,.2f} → {gain:+.0%} (${value - shares*cost_basis:+,.0f}).",
                            0, "cost_basis"))
    else:
        checks.append(Check("Your gain/loss", "missing", "No position/cost basis saved for this stock (Portfolio tab)."))
    if weight is not None:
        if weight > 0.40:
            checks.append(Check("Concentration", "bad",
                                f"{weight:.0%} of your tracked portfolio is in {symbol}. For a risk-averse plan, >40% in one volatile stock is a lot.",
                                1))
        elif weight > 0.25:
            checks.append(Check("Concentration", "warn", f"{weight:.0%} of your tracked portfolio.", 0))
        else:
            checks.append(Check("Concentration", "good", f"{weight:.0%} of your tracked portfolio.", 0))

    # 7. User's own target
    target_hit = False
    if target_price and target_price > 0:
        if price >= target_price:
            target_hit = True
            checks.append(Check("Your target price", "good", f"Reached your target ${target_price:,.2f}.", 0, "target_price"))
        else:
            checks.append(Check("Your target price", "info",
                                f"Target ${target_price:,.2f} is {target_price/price-1:+.0%} above today's price.", 0, "target_price"))
            change.append(f"Reaching your own target (${target_price:,.2f}) → plan says trim a slice.")
    else:
        checks.append(Check("Your target price", "missing", "No target saved for this stock (set one in the Portfolio tab)."))

    # 8. Analyst targets (context only — no points)
    if analyst and analyst.get("mean"):
        n = analyst.get("n")
        checks.append(Check("Analyst 12-month targets", "info",
                            f"Low ${analyst.get('low', float('nan')):,.2f} · average ${analyst['mean']:,.2f} "
                            f"({analyst['mean']/price-1:+.0%}) · high ${analyst.get('high', float('nan')):,.2f}"
                            + (f" from {int(n)} analysts" if n else "") + ". Context only — not scored.", 0, "analyst_targets"))

    risk = sum(c.points for c in checks)
    max_score = 8
    missing = sum(1 for c in checks if c.status == "missing")

    # ── Decision ─────────────────────────────────────────────────────────
    action, trim_pct, rotate_to = "HOLD", None, None
    reasons = []
    if target_hit:
        action, trim_pct = "TRIM", 25
        reasons.append("your own target price has been reached")
    if weight is not None and weight > 0.40:
        action, trim_pct = "TRIM", max(trim_pct or 0, 10)
        reasons.append(f"{symbol} is {weight:.0%} of your portfolio")
    if gain is not None and gain > 1.0 and risk >= 3:
        action, trim_pct = "TRIM", max(trim_pct or 0, 20)
        reasons.append("you have a large gain and several risk flags")
    if risk >= 5:
        action, trim_pct = "SELL", None
        reasons = [f"{risk} of {max_score} risk points are flashing at once"]
    elif action == "HOLD" and best_peer and divergence and divergence.get("diverging") and divergence["gap"] < -0.15:
        action, rotate_to = "ROTATE", best_peer.get("ticker")
        reasons.append(f"{symbol} is lagging peers and {rotate_to} is in a stronger trend")

    if action == "HOLD":
        if risk >= 3:
            headline = (f"HOLD, but on watch — {risk}/{max_score} risk points. Long-term plan intact; don't add new money "
                        "until the trend improves.")
        else:
            headline = f"HOLD — {risk}/{max_score} risk points. Nothing in the data calls for action on a 2030 plan."
    elif action == "TRIM":
        headline = f"TRIM about {trim_pct}% — " + "; ".join(reasons) + ". Keep the rest for the 2030 plan."
        if gain is not None and gain < 0:
            headline += (" You're below your cost basis, so a trim would realise a loss (which can offset taxes on gains). "
                         "If you'd rather not sell at a loss, the minimum step is: don't add more and send new money elsewhere. "
                         "If you do trim, spread it over a few weeks or sell into rebounds rather than on a sharp down day.")
    elif action == "SELL":
        headline = (f"SELL / reduce heavily — {reasons[0]}. For a risk-averse holder this is the point to protect "
                    "capital; consider selling in stages over a few weeks.")
    else:
        headline = (f"ROTATE a slice (10–20%) — {reasons[-1]}. Same sector exposure, better momentum.")

    # Confidence: distance from thresholds and missing data
    if missing >= 3:
        confidence = "Low"
    elif action == "HOLD" and risk <= 1:
        confidence = "High"
    elif action in ("TRIM",) and target_hit:
        confidence = "High"
    elif risk in (3, 4) or action == "ROTATE":
        confidence = "Low" if missing >= 2 else "Medium"
    else:
        confidence = "Medium"

    return Advice(symbol, action, confidence, headline, risk, max_score, checks, change[:6],
                  trim_pct, rotate_to,
                  {"price": price, "value": value, "gain": gain if gain is not None else float("nan"),
                   "weight": weight if weight is not None else float("nan")})


def years_to(target_year: int, today: Optional[date] = None) -> float:
    today = today or date.today()
    return max(0.25, (date(target_year, 12, 31) - today).days / 365.25)


def scenario_paths(price: float, years: float, cagr: Dict[str, float], vol: Optional[float]) -> dict:
    """Projected prices at horizon for labelled CAGR assumptions, plus a
    volatility band (zero-drift lognormal ±1σ) from historical volatility."""
    out = {k: price * (1 + g) ** years for k, g in cagr.items()}
    if vol:
        out["band_low"] = price * float(np.exp(-vol * np.sqrt(years)))
        out["band_high"] = price * float(np.exp(vol * np.sqrt(years)))
    return out
