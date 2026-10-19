"""utils/btc_scenarios.py — transparent Bitcoin price scenarios to a plan year (default 2030).

How it works (deliberately simple so a beginner can audit it):
  * Start from the LIVE Bitcoin price.
  * Each scenario's yearly growth rate = the SUM of driver contributions (percentage points per year).
    Every driver has a plain-English assumption and the dated public facts behind it (SOURCES).
  * BTC in year T = BTC today x (1 + yearly growth) ^ years.

The driver numbers are ASSUMPTIONS (editable in the UI), not data or forecasts.  They were calibrated so that
  Bear ~ a crypto winter at the wrong time, Base ~ well below published bullish forecasts,
  Bull ~ the Bernstein / Standard Chartered range, Super-bull ~ ARK's base case,
and the published forecasts themselves are shown next to them as reference points (with links and dates).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional

import math

SCENARIOS = ["Bear", "Base", "Bull", "Super-bull"]
SCENARIO_COLORS = {"Bear": "#ff1744", "Base": "#ffd600", "Bull": "#00c853", "Super-bull": "#ab47bc"}
LAST_VERIFIED = date(2026, 10, 19)

# ── Dated public facts used to document the drivers. Never shown without url + date. ────────────────
SOURCES: Dict[str, dict] = {
    "fed_sep26": {"label": "FOMC raised the fed funds target to 3.75–4.00% (12–0 vote); 'inflation remains elevated'",
                  "url": "https://www.federalreserve.gov/newsevents/pressreleases/monetary20260916a.htm",
                  "date": "2026-09-16"},
    "cpi_sep26": {"label": "US CPI +3.7% year-on-year in Sep 2026 (core +2.6%)",
                  "url": "https://www.bls.gov/news.release/cpi.nr0.htm", "date": "2026-10-14"},
    "m2_aug26": {"label": "US M2 money supply $23.34 trillion in Aug 2026, +5.7% year-on-year",
                 "url": "https://www.federalreserve.gov/releases/h6/current/default.htm", "date": "2026-09-22"},
    "clarity_cloture": {"label": "Senate cloture vote on the CLARITY Act (crypto market-structure bill) failed 49–50",
                        "url": "https://www.senate.gov/legislative/cloture/119.htm", "date": "2026-09-15"},
    "dgi_agenda": {"label": "If CLARITY does not pass this Congress it must be reintroduced when the new Congress "
                             "convenes in Jan 2027; House committee advanced the American Reserve Modernization Act "
                             "(reserve study, 20-yr hold) 28–21; White House crypto director left Oct 14",
                   "url": "https://www.dgi.io/2026-10-15-us-crypto-agenda-delays/", "date": "2026-10-15"},
    "sbr_eo": {"label": "Strategic Bitcoin Reserve executive order: funded with forfeited BTC; only budget-neutral ways to acquire more — no funded purchase program",
               "url": "https://www.whitehouse.gov/presidential-actions/2025/03/establishment-of-the-strategic-bitcoin-reserve-and-united-states-digital-asset-stockpile/",
               "date": "2025-03-06"},
    "ark_2025": {"label": "ARK Invest 2030 BTC cases: bear ~$300K, base ~$710K, bull ~$1.5M",
                 "url": "https://www.ark-invest.com/articles/valuation-models/arks-bitcoin-price-target-2030",
                 "date": "2025-04-24"},
    "ark_2026": {"label": "ARK Big Ideas 2026 review: keeps ~$1M-by-2030 view; base implies ~$762K",
                 "url": "https://cryptobriefing.com/ark-invest-big-ideas-2026-crypto-review/", "date": "2026-10-13"},
    "stanchart": {"label": "Standard Chartered: $500K by end-2030 (target pushed back from 2028; end-2026 cut to $100K)",
                  "url": "https://www.coindesk.com/markets/2026/02/12/standard-chartered-sees-bitcoin-sliding-to-usd50-000-ether-to-usd1-400-before-recovery",
                  "date": "2026-02-12"},
    "bernstein": {"label": "Bernstein: base $150K mid-2027 → ~$300K at a 2029 cycle peak (bull $200K → $500K); "
                           "method: price vs. miners' production cost, 4-year cycle",
                  "url": "https://www.cnbc.com/2026/08/26/debasement-trade-to-take-bitcoin-to-300000-in-2029-bernstein-says-.html",
                  "date": "2026-08-26"},
    "halving_history": {"label": "Post-halving cycle peaks (computed from Yahoo BTC-USD daily closes): "
                                 "Jul-2016 halving → Dec-2017 peak, May-2020 → Nov-2021, Apr-2024 → Oct-2025",
                        "url": "https://finance.yahoo.com/quote/BTC-USD/history/", "date": "2026-10-19"},
}

# Published forecasts shown as reference markers (all are from optimistic / crypto-friendly research shops).
PUBLISHED_TARGETS: List[dict] = [
    {"who": "ARK bear", "year": 2030, "price": 300_000, "src": "ark_2025"},
    {"who": "ARK base", "year": 2030, "price": 710_000, "src": "ark_2025"},
    {"who": "ARK bull", "year": 2030, "price": 1_500_000, "src": "ark_2025"},
    {"who": "Standard Chartered", "year": 2030, "price": 500_000, "src": "stanchart"},
    {"who": "Bernstein base (2029 peak)", "year": 2029, "price": 300_000, "src": "bernstein"},
    {"who": "Bernstein bull (2029 peak)", "year": 2029, "price": 500_000, "src": "bernstein"},
]


@dataclass
class Driver:
    key: str
    label: str
    help: str                      # beginner tooltip
    assumption: Dict[str, float]   # percentage points per year, by scenario
    why: Dict[str, str]            # what each scenario assumes, in words
    sources: List[str] = field(default_factory=list)


DRIVERS: List[Driver] = [
    Driver("trend", "Organic adoption trend",
           "Steady growth from more people and apps using Bitcoin, before any of the special drivers below. "
           "BTC grew ~37%/yr over the last 8 years and ~44%/yr over 4, but growth slows as it gets bigger.",
           {"Bear": 4, "Base": 8, "Bull": 12, "Super-bull": 18},
           {"Bear": "adoption stalls", "Base": "about a quarter of the past 8-yr pace",
            "Bull": "a third of the past pace", "Super-bull": "half of the past pace"}),
    Driver("halving", "2028 halving (new supply cut in half)",
           "Around April 2028 the number of new bitcoins created per block drops from 3.125 to 1.5625. "
           "Less new supply has historically come before big rallies — but each halving matters less, "
           "because new supply is already tiny versus the ~20M coins that exist.",
           {"Bear": 1, "Base": 2, "Bull": 3, "Super-bull": 5},
           {"Bear": "almost no effect", "Base": "small effect", "Bull": "classic post-halving rally",
            "Super-bull": "strong cycle"}, ["halving_history"]),
    Driver("etf", "ETF & institutional flows",
           "Money arriving through spot Bitcoin ETFs, pension funds, wealth managers and banks.",
           {"Bear": -2, "Base": 4, "Bull": 8, "Super-bull": 15},
           {"Bear": "net outflows", "Base": "slow steady inflows", "Bull": "advisers allocate 1–2%",
            "Super-bull": "large institutional allocations"}),
    Driver("policy", "US policy & politics",
           "Laws and politics: the CLARITY market-structure bill (failed a Senate vote 49–50 on Sep 15 2026), "
           "the Strategic Bitcoin Reserve (today it holds seized coins; any buying must be 'budget-neutral' — no funded purchases), the Nov 3 2026 "
           "midterms and the Nov 2028 presidential election.",
           {"Bear": -3, "Base": 1, "Bull": 4, "Super-bull": 10},
           {"Bear": "bill dies, hostile Congress after elections", "Base": "a bill passes eventually, no reserve buying",
            "Bull": "clear rules by 2027–28", "Super-bull": "Congress funds reserve purchases"},
           ["clarity_cloture", "dgi_agenda", "sbr_eo"]),
    Driver("monetary", "Money printing, inflation & interest rates",
           "Bitcoin tends to do well when money supply grows and 'real' interest rates (rates minus inflation) fall, "
           "and badly when the Fed tightens. Today: inflation 3.7%, M2 money supply +5.7%/yr, and the Fed "
           "RAISED rates to 3.75–4.00% in Sep 2026 — a headwind for now.",
           {"Bear": -3, "Base": 2, "Bull": 5, "Super-bull": 8},
           {"Bear": "Fed keeps hiking, real rates rise", "Base": "rates plateau, M2 grows ~5%/yr",
            "Bull": "cuts + 'debasement trade'", "Super-bull": "fiscal stress, heavy money printing"},
           ["fed_sep26", "cpi_sep26", "m2_aug26"]),
    Driver("treasuries", "Corporate treasury buyers",
           "Companies holding BTC on their balance sheet (e.g. Strategy/MicroStrategy). They can buy a lot — "
           "or be forced to sell if their own shares fall.",
           {"Bear": -2, "Base": 1, "Bull": 3, "Super-bull": 6},
           {"Bear": "forced selling by over-leveraged holders", "Base": "flat", "Bull": "steady buying",
            "Super-bull": "many large companies adopt"}),
    Driver("global", "Global adoption (other countries, sovereign funds)",
           "Countries, sovereign wealth funds and people in high-inflation economies buying Bitcoin.",
           {"Bear": 0, "Base": 2, "Bull": 5, "Super-bull": 8},
           {"Bear": "none", "Base": "slow", "Bull": "a few sovereign funds buy", "Super-bull": "a G20 central bank buys"}),
    Driver("risks", "Risks (crackdown, recession, quantum, miner stress)",
           "Things that could hurt: a regulatory crackdown, a recession, quantum computers threatening old wallets "
           "before an upgrade, a major exchange failure, or miners selling coins when profits shrink after the halving.",
           {"Bear": -3, "Base": 0, "Bull": 0, "Super-bull": 0},
           {"Bear": "recession + a crackdown", "Base": "the usual scares, no lasting damage",
            "Bull": "none materialise", "Super-bull": "none materialise"}),
]

DRIVER_KEYS = [d.key for d in DRIVERS]


def default_assumptions() -> Dict[str, Dict[str, float]]:
    """{scenario: {driver_key: pp_per_year}} — a fresh copy of the documented defaults."""
    return {s: {d.key: float(d.assumption[s]) for d in DRIVERS} for s in SCENARIOS}


def scenario_growth(assumptions: Dict[str, float]) -> float:
    """Yearly growth (fraction) = sum of driver contributions (percentage points). Floored at −95%/yr."""
    return max(-0.95, sum(float(v) for v in assumptions.values()) / 100.0)


def project(btc_now: float, growth: float, years: float) -> float:
    return float(btc_now) * (1.0 + growth) ** float(years)


def build_scenarios(btc_now: Optional[float], years: float,
                    assumptions: Optional[Dict[str, Dict[str, float]]] = None,
                    inflation: float = 0.035) -> Dict[str, dict]:
    """Per scenario: yearly growth, BTC at the horizon (nominal and in today's dollars), and each driver's
    share.  Returns {} if there is no live price (we never invent a starting point)."""
    if btc_now is None or not (btc_now > 0) or math.isnan(btc_now):
        return {}
    assumptions = assumptions or default_assumptions()
    out = {}
    for s in SCENARIOS:
        a = assumptions[s]
        g = scenario_growth(a)
        p = project(btc_now, g, years)
        out[s] = {"growth": g, "price": p, "real_price": p / (1 + inflation) ** years,
                  "multiple": p / btc_now, "drivers": dict(a)}
    return out


def path(btc_now: float, growth: float, t_years) -> list:
    """Price path at the given year-fractions (list/array) for charting."""
    return [float(btc_now) * (1.0 + growth) ** float(t) for t in t_years]


def growth_needed(btc_now: float, target: float, years: float) -> Optional[float]:
    """Yearly growth needed to go from today's BTC to `target` in `years`."""
    if not (btc_now and target and btc_now > 0 and target > 0 and years > 0):
        return None
    return (target / btc_now) ** (1.0 / years) - 1.0


def source_line(key: str) -> str:
    s = SOURCES[key]
    return f"[{s['label']}]({s['url']}) ({s['date']})"
