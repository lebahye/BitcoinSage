"""utils/verdict.py — the ⚖️ Stock Verdict engine (pure, deterministic, unit-tested).

ONE source of truth:
  * For a stock you HOLD, the verdict's action is My Plan's call combined with its Add/Wait call —
    `combine_plan(plan_action, add_action)` — and 🧭 My Plan displays the very same function's output.
    The rest of the evidence can only move the CONFIDENCE, never flip the action.
  * For a stock you DON'T hold, the same market checks are used without any personal rules:
    ADD = qualifies for a small starter position · HOLD = no action, watch · SELL = avoid.

Evidence rows carry a lean (+1 bullish / 0 neutral / −1 bearish / None = N/A), a weight and whether the
source has been tested.  Long-term / backtested evidence and your personal risk rules carry the weight;
short-term, untested tools are shown with weight 0 (context only).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

ACTIONS = ("HOLD", "ADD", "TRIM", "SELL", "ROTATE")
STANCE = {"ADD": 1.0, "HOLD": 0.0, "TRIM": -0.5, "ROTATE": -0.5, "SELL": -1.0}
CONF_LEVELS = ["Low", "Medium", "High"]
STRONG = 0.3          # |weighted lean| needed to count as clear agreement
CLASH = 0.6           # |lean − stance| that counts as the evidence pulling the other way

# Weights (sum of the weighted rows = 100 for a held stock).  Zero = context only.
WEIGHTS = {
    "plan_market": 30,     # My Plan market/trend risk checks (rules with a published 5-yr track record)
    "plan_personal": 25,   # your position size / target / gain rules (personal risk rules, not forecasts)
    "add_rule": 10,        # My Plan ADD/WAIT rule (backtested in 📊 Track record)
    "btc_2030": 10,        # Bitcoin-to-2030 implied value (model; assumptions, not backtested)
    "valuation": 5,        # Riot sum-of-parts (RIOT only; assumption-based)
    "dilution": 5,         # share-count growth (measured)
    "miner_stress": 5,     # BTC vs Riot's reported cost to mine (RIOT only)
    "risk_level": 10,      # volatility / drawdown — only weighted for stocks you DON'T hold
}


@dataclass
class Evidence:
    key: str
    source: str            # which tab / module
    reading: str           # plain-English reading (or 'N/A — reason')
    lean: Optional[float]  # +1 / 0 / -1 / None
    weight: float          # 0 = context only
    tested: str            # 'backtested', 'measured', 'personal rule', 'model (untested)', 'untested'
    help: str = ""


@dataclass
class Verdict:
    symbol: str
    held: bool
    action: str
    confidence: str
    headline: str
    score: Optional[float]                 # weighted lean of the evidence, −1..+1 (None if nothing weighted)
    evidence: List[Evidence] = field(default_factory=list)
    why: List[str] = field(default_factory=list)
    disagreements: List[Evidence] = field(default_factory=list)
    changes: List[str] = field(default_factory=list)
    plan_action: Optional[str] = None
    add_action: Optional[str] = None


def combine_plan(plan_action: Optional[str], add_action: Optional[str]) -> Optional[str]:
    """My Plan (Hold/Trim/Sell/Rotate) + Add/Wait → one action.  HOLD + ADD = ADD; otherwise My Plan's call."""
    if plan_action not in ("HOLD", "TRIM", "SELL", "ROTATE"):
        return None
    if plan_action == "HOLD" and add_action == "ADD":
        return "ADD"
    return plan_action


def lean_word(lean: Optional[float]) -> str:
    if lean is None:
        return "N/A"
    return "bullish" if lean > 0.25 else ("bearish" if lean < -0.25 else "neutral")


def weighted_score(evidence: List[Evidence]) -> Optional[float]:
    w = [(e.weight, e.lean) for e in evidence if e.weight > 0 and e.lean is not None]
    tot = sum(x for x, _ in w)
    return None if tot <= 0 else round(sum(x * l for x, l in w) / tot, 3)


def adjust_confidence(base: str, stance: float, score: Optional[float]) -> tuple:
    """Move confidence one notch at most: up when the weighted evidence clearly agrees with the action's stance,
    down when it clearly pulls the other way.  Returns (confidence, note)."""
    i = CONF_LEVELS.index(base) if base in CONF_LEVELS else 0
    if score is None:
        return CONF_LEVELS[max(0, i - 1)], "most weighted evidence is unavailable (N/A)"
    if abs(score - stance) >= CLASH:
        return CONF_LEVELS[max(0, i - 1)], "the weighted evidence leans the other way"
    if stance != 0 and abs(score) >= STRONG and (score > 0) == (stance > 0):
        return CONF_LEVELS[min(2, i + 1)], "the weighted evidence agrees"
    if stance == 0 and abs(score) >= STRONG:
        return CONF_LEVELS[i], (f"the weighted evidence leans {'bullish' if score > 0 else 'bearish'}, but no Add or "
                                "Trim/Sell rule has fired, so the call stays HOLD")
    return CONF_LEVELS[i], "the weighted evidence is mixed or neutral"


def disagreements(evidence: List[Evidence], action: str) -> List[Evidence]:
    """Rows (weighted or context-only) whose lean points away from the verdict:
    ADD → bearish rows; TRIM/SELL/ROTATE → bullish rows; HOLD → any row that leans either way."""
    st = STANCE.get(action, 0.0)
    out = []
    for e in evidence:
        if e.lean is None:
            continue
        if (st > 0 and e.lean < -0.25) or (st < 0 and e.lean > 0.25) or (st == 0 and abs(e.lean) > 0.25):
            out.append(e)
    return out


def build_verdict(symbol: str, held: bool, plan_action: Optional[str], plan_confidence: Optional[str],
                  add_action: Optional[str], evidence: List[Evidence], changes: Optional[List[str]] = None,
                  plan_headline: str = "", add_headline: str = "", risk_points: Optional[int] = None) -> Verdict:
    """Deterministic: same inputs → same verdict.  plan_action None ⇒ verdict N/A.
    Held: action = combine_plan(My Plan, Add/Wait).  Not held: combine_not_held(…, market risk points)."""
    action = combine_plan(plan_action, add_action) if held else combine_not_held(plan_action, add_action, risk_points)
    score = weighted_score(evidence)
    if action is None:
        return Verdict(symbol, held, "N/A", "Low", f"N/A — not enough data to judge {symbol} right now.", score,
                       evidence, ["My Plan's checks could not run (no price data)."], [], changes or [],
                       plan_action, add_action)
    conf, note = adjust_confidence(plan_confidence or "Low", STANCE[action], score)
    if held:
        headline = {"ADD": f"ADD — {add_headline.split('—', 1)[-1].strip()}" if add_headline else "ADD",
                    }.get(action, plan_headline or action)
    else:
        headline = {"ADD": f"ADD (starter position) — you don't own {symbol}; it passes the oversold-but-healthy entry rule.",
                    "HOLD": f"HOLD = watch only — you don't own {symbol}; nothing says buy now, nothing says avoid.",
                    "SELL": f"SELL = avoid for now — you don't own {symbol}; too many risk flags at once to start a position.",
                    }.get(action, plan_headline or action)
    why = []
    weighted = sorted([e for e in evidence if e.weight > 0 and e.lean is not None],
                      key=lambda e: (-(e.weight * abs(e.lean)), -e.weight, e.key))   # strongest pull first
    for e in weighted[:6]:
        why.append(f"**{e.source}** ({lean_word(e.lean)}, weight {e.weight:g}): {e.reading}")
    why.append(f"Confidence {conf}: started from My Plan's {plan_confidence or 'Low'}; {note}"
               + ("" if score is None else f" (weighted lean {score:+.2f} on a −1…+1 scale)") + ".")
    return Verdict(symbol, held, action, conf, headline, score, evidence, why,
                   disagreements(evidence, action), changes or [], plan_action, add_action)


def shares_to_reach_weight(shares: float, price: float, portfolio_value: float, target_weight: float,
                           proceeds_to_cash: bool = True) -> Optional[float]:
    """Shares to sell so the position is `target_weight` of the TRACKED holdings (as My Plan measures it).
    proceeds_to_cash=True: the money leaves the tracked holdings  → (v − x·p) / (P − x·p) = w.
    proceeds_to_cash=False: the money is reinvested in other holdings → (v − x·p) / P = w."""
    if not (shares and price and portfolio_value) or target_weight <= 0 or target_weight >= 1:
        return None
    v = shares * price
    if v / portfolio_value <= target_weight:
        return 0.0
    x = (v - target_weight * portfolio_value) / price
    return min(shares, x / (1 - target_weight) if proceeds_to_cash else x)


# ── Stocks you don't hold ──────────────────────────────────────────────
PERSONAL_CHECKS = ("Your gain/loss", "Your target price", "Concentration")


def combine_not_held(plan_action: Optional[str], add_action: Optional[str], risk_points: Optional[int]) -> Optional[str]:
    """No personal rules: SELL (= avoid) at 5+ market risk points, ADD (= small starter) if the ADD rule fires,
    otherwise HOLD (= watch only).  TRIM/ROTATE never apply to a stock you don't own."""
    if plan_action is None or risk_points is None:
        return None
    if risk_points >= 5:
        return "SELL"
    return "ADD" if add_action == "ADD" else "HOLD"


def market_confidence(action: str, risk_points: int, n_missing_market: int) -> str:
    """My Plan's confidence rule with the personal checks left out (they're not 'missing' — they don't apply)."""
    if n_missing_market >= 3:
        return "Low"
    if action == "HOLD" and risk_points <= 1:
        return "High"
    if risk_points in (3, 4):
        return "Low" if n_missing_market >= 2 else "Medium"
    return "Medium"


# ── Lean rules (pure; one place, unit-tested) ──────────────────────────
def lean_market_risk(points: Optional[int]) -> Optional[float]:
    if points is None:
        return None
    return 0.5 if points <= 1 else 0.0 if points == 2 else -0.5 if points <= 4 else -1.0


def lean_dilution(growth_1y: Optional[float]) -> Optional[float]:
    if growth_1y is None:
        return None
    return -1.0 if growth_1y >= 0.10 else -0.5 if growth_1y >= 0.04 else 0.0


def lean_miner_stress(btc: Optional[float], cash_cost: float, all_in: float) -> Optional[float]:
    if not btc:
        return None
    if btc < cash_cost:
        return -1.0
    if btc < all_in:
        return -0.5
    return 0.5 if btc >= 1.5 * all_in else 0.0


def lean_sum_of_parts(ratio: Optional[float]) -> Optional[float]:
    """Market value ÷ parts.  <0.7 = market pays well under the parts; >1.5 = well over (build cost not netted)."""
    if ratio is None:
        return None
    return 0.5 if ratio < 0.7 else -0.5 if ratio > 1.5 else 0.0


def lean_implied(implied: List[Optional[float]], price: Optional[float]) -> Optional[float]:
    """Bitcoin-to-2030 Base-path implied price(s) vs today: bullish only if every regime is ≥20% above,
    bearish only if every regime is ≥20% below."""
    vals = [v for v in implied if v is not None]
    if not vals or not price:
        return None
    if all(v >= 1.2 * price for v in vals):
        return 1.0
    if all(v <= 0.8 * price for v in vals):
        return -1.0
    return 0.0


def lean_risk_level(vol_annual: Optional[float]) -> Optional[float]:
    if vol_annual is None:
        return None
    return -1.0 if vol_annual >= 1.0 else -0.5 if vol_annual >= 0.7 else 0.0


def lean_ta(rsi: Optional[float], macd_hist: Optional[float], price: Optional[float], sma50: Optional[float]) -> Optional[float]:
    parts = []
    if rsi is not None:
        parts.append(1.0 if rsi < 30 else -1.0 if rsi > 70 else 0.0)
    if macd_hist is not None:
        parts.append(1.0 if macd_hist > 0 else -1.0)
    if price and sma50:
        parts.append(1.0 if price > sma50 else -1.0)
    return None if not parts else round(sum(parts) / len(parts), 2)


def lean_signal(sig: Optional[str]) -> Optional[float]:
    s = (sig or "").upper()
    if "BUY" in s:
        return 1.0
    if "SELL" in s:
        return -1.0
    if "HOLD" in s or "NEUTRAL" in s:
        return 0.0
    return None


def lean_label(label: Optional[str]) -> Optional[float]:
    s = (label or "").lower()
    if not s or s in ("n/a", "na", "none", "unavailable"):
        return None
    return 1.0 if ("positive" in s or "bullish" in s) else -1.0 if ("negative" in s or "bearish" in s) else 0.0


def lean_analyst(mean: Optional[float], price: Optional[float]) -> Optional[float]:
    if not (mean and price):
        return None
    return 1.0 if mean >= 1.2 * price else -1.0 if mean <= 0.9 * price else 0.0


PHASE_LEAN = {"boom": 1.0, "lead": 0.5, "none": 0.0, "lag": -0.5, "bust": -1.0}
