"""⚖️ Stock Verdict — ONE call per stock built from every tab's data.

* Held stock → the action is My Plan's call (Hold/Trim/Sell/Rotate) combined with its Add/Wait call, through
  utils.verdict.combine_plan — the same function 🧭 My Plan displays, so the two can never disagree.
* Not held → the same market checks without personal rules (ADD = small starter, HOLD = watch, SELL = avoid).
* Everything else (Bitcoin-to-2030, Reflexivity, dilution, news, technicals, …) is evidence: weighted when it is
  long-term / measured, weight 0 (context only) when it is short-term or untested.  It can move the confidence,
  never the action.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import streamlit as st

from utils import verdict as V
from utils.verdict import Evidence, WEIGHTS
from utils.tickers import MINING_STOCKS, WATCHLIST, CORRELATION_UNIVERSE, resolve

PLAN_YEAR = 2030
_STYLE = {"ADD": ("#00e676", "➕"), "HOLD": ("#00c853", "🟢"), "TRIM": ("#ffb300", "🟡"),
          "ROTATE": ("#29b6f6", "🔄"), "SELL": ("#ff1744", "🔴"), "N/A": ("#8b8b9b", "❔")}
_NOT_HELD_WORD = {"ADD": "ADD — small starter position", "HOLD": "HOLD — watch only (don't buy yet)",
                  "SELL": "SELL — avoid for now"}
_MACRO = {"^VIX", "BTC-USD", "UUP", "USO", "TLT", "IWM", "QQQ", "ARKK"}

TIP = {
    "verdict": "One answer per stock. For a stock you own it IS My Plan's call (plus My Plan's Add/Wait rule). "
               "The other tabs below can only make us more or less sure — they can't flip the call.",
    "confidence": "How sure the call is: starts from My Plan's own confidence (missing data and how close the risk "
                  "points are to a threshold), then moves at most one notch if the weighted evidence clearly agrees or "
                  "clearly disagrees.",
    "weight": "How much this row counts. 0 = shown for context only (short-term or never tested). The weighted rows "
              "add up to 100 for a stock you own.",
    "tested": "backtested = checked against past prices in this app · measured = a fact from filings/prices · "
              "personal rule = your own risk rule, not a forecast · model/untested = depends on assumptions.",
    "lean": "Which way this piece of evidence points: bullish (good for holding/adding), bearish (argues for "
            "reducing), neutral, or N/A (no data — never guessed).",
    "score": "Weighted average of the leans: +1 = every weighted row bullish, −1 = every weighted row bearish.",
}


def ticker_universe(positions: Dict[str, dict]) -> List[str]:
    """Holdings first (largest share count first, RIOT first if held), then other miners, then the rest."""
    held = sorted([s for s, p in positions.items() if p.get("shares", 0) > 0],
                  key=lambda s: (s != "RIOT", -positions[s].get("shares", 0), s))
    rest = ["RIOT"] + list(MINING_STOCKS) + list(WATCHLIST) + [t for t in CORRELATION_UNIVERSE if t not in _MACRO]
    out = list(dict.fromkeys(held + [resolve(t) for t in rest]))
    return out or ["RIOT"]


def _usd(x, nd=2):
    return "N/A" if x is None or (isinstance(x, float) and math.isnan(x)) else f"${x:,.{nd}f}"


def _big(x):
    return "N/A" if x is None else (f"${x/1e6:,.2f}M" if x >= 1e6 else f"${x/1e3:,.0f}K" if x >= 1e4 else f"${x:,.0f}")


def _safe(fn, *a, **k):
    try:
        return fn(*a, **k)
    except Exception:
        return None


# ── Evidence gathering (each piece fails independently → N/A) ────────────────
def _plan_rows(symbol, adv, add, held, bt) -> List[Evidence]:
    rows = []
    personal = [c for c in adv.checks if c.name in V.PERSONAL_CHECKS]
    market = [c for c in adv.checks if c.name not in V.PERSONAL_CHECKS and c.name != "Analyst 12-month targets"]
    mpts = sum(c.points for c in market)
    flags = [c.name for c in market if c.points > 0]
    rows.append(Evidence("plan_market", "🧭 My Plan — market & trend checks",
                         f"{mpts} market risk point(s)" + (f": {', '.join(flags)}" if flags else " — trend, Bitcoin, VIX all OK")
                         + f" (SELL at 5+).",
                         V.lean_market_risk(mpts), WEIGHTS["plan_market"], "backtested",
                         "200-day trend, death cross, drawdown, Bitcoin's trend, VIX, peers. These rules have a 5-year "
                         "track record in My Plan (📊) — they did not time the market better than holding."))
    if held:
        w, g = adv.facts.get("weight"), adv.facts.get("gain")
        bits = []
        if w is not None and not math.isnan(w):
            bits.append(f"{w:.0%} of your portfolio" + (" (over the 40% cap)" if w > 0.40 else ""))
        if g is not None and not math.isnan(g):
            bits.append(f"{g:+.0%} vs your cost")
        tgt = next((c for c in personal if c.name == "Your target price"), None)
        if tgt is not None:
            bits.append(tgt.detail.rstrip("."))
        reduce = adv.action == "TRIM"
        rows.append(Evidence("plan_personal", "🧭 My Plan — your position rules", "; ".join(bits) or "N/A — no position saved",
                             -1.0 if reduce else 0.0, WEIGHTS["plan_personal"], "personal rule",
                             "Concentration (>40% → trim), your own target price, big-gain-with-risk rule."))
    else:
        rows.append(Evidence("plan_personal", "🧭 My Plan — your position rules", "N/A — you don't own this stock",
                             None, 0, "personal rule"))
    if add is not None:
        why = add.headline.split("—", 1)[-1].strip()
        if symbol not in MINING_STOCKS:
            why += " (note: this rule's backdrop uses Bitcoin and the miner peers — it was built for bitcoin miners)"
        rows.append(Evidence("add_rule", "🧭 My Plan — Add / Wait rule", f"{add.action}: {why[:160]}",
                             1.0 if add.action == "ADD" else 0.0, WEIGHTS["add_rule"], "backtested",
                             "ADD only when the stock is oversold (2 of 3 conditions) AND the backdrop is healthy."))
    else:
        rows.append(Evidence("add_rule", "🧭 My Plan — Add / Wait rule", "N/A", None, 0, "backtested"))
    # Track record (context; it tells you how much to trust the timing rules)
    if bt:
        sm, b = bt["summary"], bt["baseline"]["6M"]
        beat = [n.split(" ")[0] for n, v in sm.items() if v["6M"]["n"] and
                ((v["6M"]["avg"] > b["avg"]) if n.startswith("ADD") else (v["6M"]["avg"] < b["avg"]))]
        stg = bt.get("strategy") or {}
        txt = ("none of the timing signals beat simply holding" if not beat else
               f"{', '.join(beat)} signals beat a random day (small samples)")
        if stg:
            txt += f"; follow-the-rules {stg['strategy_total']:+.0%} vs just-hold {stg['hold_total']:+.0%} over 5 yrs"
        rows.append(Evidence("track", "📊 Track record (My Plan, 5 yrs)", txt + ".", 0.0, 0, "backtested",
                             "Why the timing rules get modest weight and position size matters most."))
    else:
        rows.append(Evidence("track", "📊 Track record (My Plan, 5 yrs)", "N/A — backtest data unavailable right now",
                             None, 0, "backtested"))
    if adv.checks:
        an = next((c for c in adv.checks if c.name == "Analyst 12-month targets"), None)
        if an:
            import re
            m = re.search(r"average \$([\d,\.]+)", an.detail)
            mean = float(m.group(1).replace(",", "")) if m else None
            rows.append(Evidence("analyst", "🎯 Analyst 12-month targets", an.detail.replace(" Context only — not scored.", ""),
                                 V.lean_analyst(mean, adv.facts.get("price")), 0, "untested",
                                 "Wall Street 12-month price targets. Often too optimistic; not scored."))
        else:
            rows.append(Evidence("analyst", "🎯 Analyst 12-month targets", "N/A — none published / unavailable", None, 0, "untested"))
    return rows


def _btc2030_row(symbol, s0, targets, held):
    from components.btc_2030 import _load_fit
    from utils import btc_scenarios as bs, riot_btc_link as link, signal_hub
    from utils.holding_advisor import years_to
    fit, btc_hist, _ = _load_fit(symbol)
    if fit is None or btc_hist is None or btc_hist.dropna().empty:
        return Evidence("btc_2030", f"₿ Bitcoin to {PLAN_YEAR}", "N/A — not enough stock/Bitcoin history to link them",
                        None, 0, "model (untested)"), {}
    b0 = float(btc_hist.dropna().iloc[-1])
    yrs = years_to(PLAN_YEAR)
    sc = bs.build_scenarios(b0, yrs)
    d1 = _safe(link.measured_dilution, signal_hub.get_shares(symbol), 1.0)
    drift = link.drift_from_factors({"dilution": d1 or 0.0})
    sig = link.horizon_sigma(fit, yrs)
    betas = [("full history", fit["beta"])] + ([("last 3 yrs", fit["recent_beta"])] if fit.get("recent_beta") is not None else [])
    base = {lab: link.project_stock(s0, b0, sc["Base"]["price"], yrs, b, drift, sig)["point"] for lab, b in betas}
    txt = (f"Base Bitcoin path {_big(sc['Base']['price'])} by end-{PLAN_YEAR} implies "
           + " / ".join(f"{_usd(v)} ({lab}, β {b:.2f})" for (lab, b), v in zip(betas, base.values()))
           + f" vs {_usd(s0)} today")
    extra = {"b0": b0, "scen": sc, "base": base}
    tgt = targets.get(symbol) if held else None
    if tgt:
        need = link.btc_for_stock(tgt, s0, b0, yrs, fit["beta"], drift, sig)
        if need["point"] is not None and need["reachable"]:
            near = min(sc, key=lambda s: abs(np.log(sc[s]["price"] / need["point"])))
            txt += f". Your ${tgt:,.2f} target needs BTC ≈ {_big(need['point'])} (closest path: {near})"
            extra["need"] = need["point"]
        else:
            txt += f". Your ${tgt:,.2f} target: Bitcoin alone can't plausibly get there (needs AI/HPC gains)"
    return Evidence("btc_2030", f"₿ Bitcoin to {PLAN_YEAR}", txt + ".", V.lean_implied(list(base.values()), s0),
                    WEIGHTS["btc_2030"], "model (untested)",
                    "Default Bitcoin scenarios × the stock's historical sensitivity to Bitcoin, minus measured dilution. "
                    "Assumption-heavy; bullish only if both sensitivity regimes agree."), extra


def _reflexivity_rows(symbol, s0, b0):
    from utils import reflexivity as rx, signal_hub
    from utils.riot_facts import Q2_2026 as F
    rows = []
    try:
        from components.reflexivity_dashboard import live_phase_and_edge
        ph, lab, edge = live_phase_and_edge(symbol)
        rows.append(Evidence("phase", "🔄 Reflexivity — boom/bust phase",
                             (lab or "N/A") + (" — backtest: no phase predicted the next 3–6 months" if not edge else
                                               " — backtest found an edge (small sample)"),
                             V.PHASE_LEAN.get(ph) if ph else None, 0, "backtested",
                             "Context only: tested on history and it did not predict returns."))
    except Exception as e:
        rows.append(Evidence("phase", "🔄 Reflexivity — boom/bust phase", f"N/A ({type(e).__name__})", None, 0, "backtested"))
    sh = _safe(signal_hub.get_shares, symbol)
    g1 = _safe(rx.share_growth, sh, 1) if sh is not None and len(sh) else None
    rows.append(Evidence("dilution", "🧾 Reflexivity — dilution (share count, 12 mo)",
                         "N/A — share history unavailable" if g1 is None else f"share count {g1:+.1%} over 12 months",
                         V.lean_dilution(g1), WEIGHTS["dilution"] if g1 is not None else 0, "measured",
                         "New shares shrink your slice. ≥10%/yr is heavy dilution."))
    if symbol != "RIOT":
        rows.append(Evidence("valuation", "💰 Reflexivity — sum-of-parts value", "RIOT only (filing facts on file for Riot)",
                             None, 0, "model (untested)"))
        rows.append(Evidence("miner_stress", "⛏️ Reflexivity — miner stress vs cost to mine", "RIOT only (Riot's reported costs)",
                             None, 0, "measured"))
        return rows
    try:
        bal = signal_hub.get_balance("RIOT") or {}
        shares = float(sh.iloc[-1]) if sh is not None and len(sh) else bal.get("shares")
        yrs_full = max(0.0, (F["lease_191mw_full"] - date.today()).days / 365.25)
        r = rx.sum_of_parts(s0, shares, b0, F["btc_held"], F["cash_usd"], bal.get("total_debt") or 0.0,
                            (F["lease_191mw_noi_low"] + F["lease_191mw_noi_high"]) / 2, F["lease_191mw_term_years"],
                            round(yrs_full, 1), 0.09, 0.0, 0.0, 0.0, F["btc_pledged"])
        ratio = r.get("ratio") if r else None
        rows.append(Evidence("valuation", "💰 Reflexivity — sum-of-parts value",
                             "N/A — share count/price unavailable" if ratio is None else
                             f"market value {ratio:.2f}× the parts (~{_usd(r['per_share'])}/share: BTC + cash + AI lease − debt; "
                             "build cost & mining business not entered)",
                             V.lean_sum_of_parts(ratio), WEIGHTS["valuation"] if ratio is not None else 0, "model (untested)",
                             "Default inputs from the Reflexivity tab. Undisclosed build cost is 0, so the parts are "
                             "probably overstated."))
    except Exception as e:
        rows.append(Evidence("valuation", "💰 Reflexivity — sum-of-parts value", f"N/A ({type(e).__name__})", None, 0, "model (untested)"))
    rows.append(Evidence("miner_stress", "⛏️ Reflexivity — miner stress vs cost to mine",
                         "N/A — no Bitcoin price" if not b0 else
                         f"Bitcoin {_big(b0)} = {b0/F['cost_to_mine_ex_da']:.2f}× Riot's cash cost, "
                         f"{b0/F['cost_to_mine_incl_da']:.2f}× its all-in cost (Q2 2026)",
                         V.lean_miner_stress(b0, F["cost_to_mine_ex_da"], F["cost_to_mine_incl_da"]),
                         WEIGHTS["miner_stress"] if b0 else 0, "measured",
                         "Below the all-in cost, mining loses money after equipment wear-out."))
    return rows


def _context_rows(symbol, closes, held, include_slow):
    from utils import signal_hub, stat_forecast as sf, riot_btc_link as link
    from utils.news_sentiment import news_sentiment, crypto_fear_greed
    rows = []
    c = closes[symbol].dropna() if symbol in closes else pd.Series(dtype=float)
    # Risk level (weighted only when not held — for a holding, size rules already cover risk)
    fr = sf.forecast_range(c, sf.HORIZONS["3 months"]) if len(c) else None
    vol = fr["annual_vol"] if fr else None
    rows.append(Evidence("risk_level", "🛡️ Risk — how much the price swings",
                         "N/A" if vol is None else f"{vol:.0%} a year (typical yearly swing; the S&P 500 is ~15–20%)",
                         V.lean_risk_level(vol), 0 if held or vol is None else WEIGHTS["risk_level"], "measured",
                         "Volatility from the last year of daily prices. Weighted only for stocks you don't own."))
    if fr:
        cov = _safe(sf.backtest_coverage, c, sf.HORIZONS["3 months"])
        rows.append(Evidence("forecast", "🔮 Forecast Center — 3-month statistical range",
                             f"68%: {_usd(fr['low_68%'])}–{_usd(fr['high_68%'])} · 90%: {_usd(fr['low_90%'])}–{_usd(fr['high_90%'])}. "
                             + sf.coverage_verdict(cov), 0.0, 0, "backtested",
                             "A range, not a direction — it says how far the price may move, not which way."))
    else:
        rows.append(Evidence("forecast", "🔮 Forecast Center — 3-month statistical range", "N/A — not enough history", None, 0, "backtested"))
    ts = signal_hub.short_term_signal(symbol) or {}
    sig = ts.get("signal")
    rows.append(Evidence("trade_signal", "🚦 Trade Signals (short-term)",
                         "N/A" + (f" — {ts.get('error')}" if ts.get("error") else "") if not sig or sig == "N/A" else
                         f"{sig}" + (f" (confidence {ts['confidence']}%)" if ts.get("confidence") is not None else "")
                         + " — days-to-weeks momentum",
                         V.lean_signal(sig), 0, "untested", "Short-term; never backtested. Context only."))
    snap = signal_hub.snapshot(symbol) or {}
    if snap.get("available"):
        rsi, mh, p, s50 = snap.get("rsi14"), snap.get("macd_hist"), snap.get("price"), snap.get("sma50")
        rows.append(Evidence("ta", "📈 Technical Analysis indicators",
                             f"RSI {rsi:.0f}" if rsi is not None else "RSI N/A", V.lean_ta(rsi, mh, p, s50), 0, "untested",
                             "RSI (<30 oversold, >70 overbought), MACD momentum, price vs 50-day average."))
        rows[-1].reading += (f" · MACD {'rising' if (mh or 0) > 0 else 'falling'}" if mh is not None else "") + \
                            (f" · price {'above' if p > s50 else 'below'} 50-day avg {_usd(s50)}" if p and s50 else "")
    else:
        rows.append(Evidence("ta", "📈 Technical Analysis indicators", "N/A — no price data", None, 0, "untested"))
    if include_slow:
        rows.append(_next_mover_row(symbol))
    else:
        rows.append(Evidence("next_mover", "🎯 Next-Mover ranking", "Not loaded (tick 'Load slower extras' above)",
                             None, 0, "untested"))
    ns = news_sentiment(symbol) or {}
    rows.append(Evidence("news", "📰 News tone (last 7 days)",
                         f"{ns.get('label', 'n/a')} ({ns.get('n_headlines', 0)} headlines"
                         + (f", score {ns['score']:+.2f}" if ns.get("score") is not None else "") + ")"
                         if ns.get("available", True) and ns.get("n_headlines") else "N/A — no headlines / news feed unavailable",
                         V.lean_label(ns.get("label")) if ns.get("n_headlines") else None, 0, "untested",
                         "Headline word-counting; not shown to predict prices."))
    fg = crypto_fear_greed()
    rows.append(Evidence("fng", "😨 Crypto Fear & Greed",
                         "N/A — index unavailable" if not fg else f"{fg['value']} — {fg['label']} ({fg['as_of']})",
                         None if not fg else 0.0, 0, "untested",
                         "Crypto-market mood (0 fear … 100 greed). Some buy fear, but that's untested here — neutral."))
    # Correlation context
    try:
        b = closes["BTC-USD"] if "BTC-USD" in closes else None
        cb = link.daily_corr(c, b) if b is not None and len(c) else None
        lr = np.log(c).diff()
        cv = None
        if "^VIX" in closes:
            cv = float(pd.concat([lr, np.log(closes["^VIX"]).diff()], axis=1).dropna().iloc[-252:].corr().iloc[0, 1])
        u = signal_hub.get_ohlcv("UUP")
        cu = None
        if not u.empty:
            cu = float(pd.concat([lr, np.log(u["Close"]).diff()], axis=1).dropna().iloc[-252:].corr().iloc[0, 1])
        f2 = lambda x: "N/A" if x is None or np.isnan(x) else f"{x:+.2f}"
        rows.append(Evidence("corr", "🕸️ Correlation Map (1 yr, daily)",
                             f"with Bitcoin {f2(cb)} · with VIX {f2(cv)} · with US dollar (UUP) {f2(cu)}", 0.0, 0, "measured",
                             "How tightly the stock moves with Bitcoin, market fear and the dollar. Describes risk, not direction."))
    except Exception as e:
        rows.append(Evidence("corr", "🕸️ Correlation Map (1 yr, daily)", f"N/A ({type(e).__name__})", None, 0, "measured"))
    # Events
    try:
        from components.holding_plan import load_events
        from utils.event_calendar import flagged
        today, events, have_earn, _ = load_events(symbol)
        soon = [e for e in flagged(events, today, 14)
                if e.kind != "Earnings" or symbol in e.title]
        rows.append(Evidence("events", "📅 Event calendar (next 14 days)",
                             "; ".join(f"{e.title} {e.when:%b %d}" + (" (est.)" if e.estimated else "") for e in soon)
                             or ("nothing scheduled" + ("" if have_earn else " (earnings dates unavailable)")),
                             0.0, 0, "measured", "Big events add short-term swings; avoid acting the day before."))
    except Exception as e:
        rows.append(Evidence("events", "📅 Event calendar (next 14 days)", f"N/A ({type(e).__name__})", None, 0, "measured"))
    rows.append(Evidence("options", "🎰 Options / 🏦 Institutional flow / 🛡️ Monte Carlo",
                         "Not used — options & flow data are free/delayed proxies (not validated); Monte Carlo repeats "
                         "the statistical range above", None, 0, "untested"))
    return rows


@st.cache_data(ttl=900, show_spinner=False)
def _next_mover_cached() -> pd.DataFrame:
    from utils.next_mover_engine import NextMoverEngine
    r = NextMoverEngine().calculate_composite_score()
    if r is None or r.empty:
        raise RuntimeError("empty")
    return r[["Symbol", "Rank", "Score"]].copy()


def _next_mover_row(symbol):
    if symbol not in WATCHLIST:
        return Evidence("next_mover", "🎯 Next-Mover ranking", "N/A — ranks the 9 watchlist miners only", None, 0, "untested")
    try:
        r = _next_mover_cached()
        row = r[r["Symbol"] == symbol]
        if row.empty:
            raise RuntimeError("not ranked")
        rk, n = int(row["Rank"].iloc[0]), len(r)
        return Evidence("next_mover", "🎯 Next-Mover ranking", f"#{rk} of {n} (score {float(row['Score'].iloc[0]):.0f}/100)",
                        1.0 if rk <= 3 else -1.0 if rk > n - 3 else 0.0, 0, "untested",
                        "Relative short-term ranking among the miners; not backtested.")
    except Exception as e:
        return Evidence("next_mover", "🎯 Next-Mover ranking", f"N/A ({type(e).__name__})", None, 0, "untested")


def _changes(symbol, adv, add, held, positions, closes, extra) -> List[str]:
    out = list(adv.change_my_mind)
    if add is not None and add.action != "ADD":
        lv = list(getattr(add, "levels", None) or [])
        if lv and not (held and "cap" in add.headline):
            out.append("An ADD signal would need the stock oversold (2 of 3) with a healthy backdrop — e.g. "
                       + " or ".join(x.rstrip(".") for x in lv[:2]) + ".")
    if held:
        w = adv.facts.get("weight")
        price = adv.facts.get("price")
        if w is not None and not math.isnan(w) and w > 0.40 and price:
            pv = adv.facts["value"] / w
            sh = positions[symbol]["shares"]
            n_cash = V.shares_to_reach_weight(sh, price, pv, 0.40, proceeds_to_cash=True)
            n_move = V.shares_to_reach_weight(sh, price, pv, 0.40, proceeds_to_cash=False)
            if n_cash:
                out.append(f"Concentration ({w:.0%} now): {symbol} drops to 40% of your tracked holdings after selling "
                           f"≈{n_move:,.0f} shares if the money goes into your other holdings, or ≈{n_cash:,.0f} if it goes "
                           f"to cash. My Plan's step is smaller (trim ~{adv.trim_pct or 10}%, spread over weeks); the "
                           "size-based TRIM stays on until the weight is under 40%.")
    if extra.get("need"):
        out.append(f"Bitcoin heading toward ≈{_big(extra['need'])} by end-{PLAN_YEAR} is what lines up with your target "
                   f"(today {_big(extra.get('b0'))}).")
    return list(dict.fromkeys(out))[:8]


def build_for(symbol: str, include_slow: bool = False):
    """Gather every tab's evidence for one ticker and build the verdict.  Returns (Verdict, adv, add, positions)."""
    from components.holding_plan import get_advice, get_add_advice, load_backtest
    symbol = resolve(symbol)
    adv, closes, positions, targets = get_advice(symbol)
    held = positions.get(symbol, {}).get("shares", 0) > 0
    if adv is None or not adv.facts or adv.facts.get("price") is None or symbol not in closes:
        return V.build_verdict(symbol, held, None, None, None, []), adv, None, positions
    add = _safe(get_add_advice, symbol, closes, positions)
    bt = load_backtest(symbol) if symbol in closes else None
    s0 = adv.facts["price"]
    ev = _plan_rows(symbol, adv, add, held, bt)
    btc_row, extra = _safe(_btc2030_row, symbol, s0, targets, held) or (
        Evidence("btc_2030", f"₿ Bitcoin to {PLAN_YEAR}", "N/A — unavailable right now", None, 0, "model (untested)"), {})
    ev.append(btc_row)
    b0 = extra.get("b0") or (float(closes["BTC-USD"].dropna().iloc[-1]) if "BTC-USD" in closes else None)
    ev += _reflexivity_rows(symbol, s0, b0)
    ev += _context_rows(symbol, closes, held, include_slow)
    if held:
        base_conf = adv.confidence
    else:
        mk = [c for c in adv.checks if c.name not in V.PERSONAL_CHECKS]
        risk = sum(c.points for c in mk)
        base_conf = V.market_confidence("HOLD" if risk < 5 else "SELL", risk, sum(1 for c in mk if c.status == "missing"))
    risk_pts = sum(c.points for c in adv.checks if c.name not in V.PERSONAL_CHECKS)
    vd = V.build_verdict(symbol, held, adv.action, base_conf, add.action if add else None, ev,
                         _changes(symbol, adv, add, held, positions, closes, extra),
                         plan_headline=adv.headline, add_headline=add.headline if add else "", risk_points=risk_pts)
    return vd, adv, add, positions


# ── UI ──────────────────────────────────────────────────────────────────
class StockVerdict:
    def render(self):
        from components.holding_plan import _load_user_data
        st.header("⚖️ Stock Verdict — one clear call per stock")
        st.caption("Pulls together every tab (My Plan, track record, Bitcoin to 2030, Reflexivity, Forecast Center, "
                   "signals, news, correlations, events) into **one** answer. Long-term, tested evidence and your own "
                   "risk rules carry the weight; short-term, untested signals are shown for context with **weight 0**. "
                   "Educational tool — **not financial advice**.")
        positions, _ = _load_user_data()
        uni = ticker_universe(positions)
        # Remember the choice across section switches: Streamlit drops a widget's state when its section isn't
        # rendered, so we keep a copy under a separate key and seed the widget from it.  (No `index=` argument —
        # a changing index would give the widget a new identity and silently undo every other selection.)
        saved = st.session_state.get("verdict_symbol_saved", "RIOT" if "RIOT" in uni else uni[0])
        if st.session_state.get("verdict_symbol") not in uni:
            st.session_state["verdict_symbol"] = saved if saved in uni else uni[0]

        def _fmt(s):
            sh = positions.get(s, {}).get("shares", 0)
            name = MINING_STOCKS.get(s, positions.get(s, {}).get("name", ""))
            return f"{s} — {name}" + (f"  · you own {sh:,.0f}" if sh else "  · not held")

        c1, c2 = st.columns([3, 1])
        sym = c1.selectbox("Stock", uni, format_func=_fmt, key="verdict_symbol",
                           help="Your holdings first (from 🏆 Portfolio), then the other miners and the stocks in the "
                                "Correlation Map. Your choice is remembered while you switch tabs.")
        st.session_state["verdict_symbol_saved"] = sym
        slow = c2.checkbox("Load slower extras", value=False, key="verdict_slow",
                           help="Adds the Next-Mover ranking (scans 9 miners; ~10–30 s the first time). Weight 0 either way.")
        with st.spinner(f"Gathering every tab's data for {sym}…"):
            vd, adv, add, positions = build_for(sym, slow)
        self._card(vd, adv)
        if sym not in MINING_STOCKS:
            st.caption(f"ℹ️ {sym} isn't a bitcoin miner. My Plan's checks (Bitcoin trend, miner peers) and the Bitcoin-to-"
                       f"{PLAN_YEAR} link were built for miners, so read this verdict as a rougher guide.")
        if vd.action == "N/A":
            st.warning("Price data is unavailable from Yahoo Finance right now (often a temporary rate limit) — "
                       "no verdict shown rather than a guess. Try 🔄 Refresh Data in a minute.")
            return
        st.markdown("#### Why")
        for b in vd.why:
            st.markdown("- " + b)
        self._table(vd)
        self._disagree(vd)
        st.markdown("#### What would change the verdict")
        if vd.changes:
            for c in vd.changes:
                st.markdown("- " + c)
        else:
            st.caption("N/A — no specific trigger levels available.")
        with st.expander("ℹ️ How this verdict is made (and its limits)"):
            st.markdown(
                "- **Stocks you own:** the action is exactly 🧭 My Plan's call, upgraded to **ADD** only when My Plan says "
                "HOLD *and* its Add/Wait rule says ADD. My Plan shows the same verdict line, so the tabs can't disagree.\n"
                "- **Stocks you don't own:** no personal rules. ADD = the entry rule fires (start small), HOLD = watch only, "
                "SELL = avoid (5+ market risk points).\n"
                "- **Weights:** My Plan market checks 30 · your position rules 25 · Add/Wait rule 10 · Bitcoin-to-2030 10 · "
                "dilution 5 · sum-of-parts 5 (RIOT) · miner stress 5 (RIOT) · price-swing risk 10 (not-held only). "
                "Everything else is weight 0.\n"
                "- **Evidence moves confidence, not the action** — at most one notch.\n"
                "- **Honest limits:** My Plan's 5-year track record shows its timing rules did not beat holding; the "
                "verdict leans on them for *risk control*, not for predicting prices. Bitcoin-to-2030 and sum-of-parts "
                "depend on assumptions. N/A means the data wasn't available — nothing is filled in.")

    def _card(self, vd, adv):
        color, icon = _STYLE.get(vd.action, _STYLE["N/A"])
        label = vd.action if vd.held or vd.action == "N/A" else _NOT_HELD_WORD.get(vd.action, vd.action)
        sub = (f"{'You own this stock — this is My Plan’s call' if vd.held else 'Not held — judged on the stock alone'}"
               f" · confidence: <b>{vd.confidence}</b>"
               + ("" if vd.score is None else f" · weighted evidence {vd.score:+.2f}"))
        st.markdown(
            f'<div style="background:{color}1a;border:2px solid {color};border-radius:12px;padding:18px 22px;margin:6px 0 12px">'
            f'<div style="font-size:.85rem;color:#bbb">⚖️ Verdict for {vd.symbol} · {sub}</div>'
            f'<div style="font-size:2rem;font-weight:800;color:{color};margin:4px 0">{icon} {label}</div>'
            f'<div style="font-size:1.05rem;color:#eee">{vd.headline}</div></div>', unsafe_allow_html=True)
        c = st.columns(4)
        c[0].metric("Verdict", label.split(" — ")[0], help=TIP["verdict"])
        c[1].metric("Confidence", vd.confidence, help=TIP["confidence"])
        c[2].metric("Weighted evidence", "N/A" if vd.score is None else f"{vd.score:+.2f}", help=TIP["score"])
        c[3].metric("Last close", _usd(adv.facts.get("price")) if adv is not None and adv.facts else "N/A",
                    help="Latest daily close from Yahoo Finance (may be delayed).")

    def _table(self, vd):
        st.markdown("#### Evidence from every tab")
        df = pd.DataFrame([{"Source": e.source, "Reading": e.reading, "Leans": V.lean_word(e.lean),
                            "Weight": e.weight, "Tested?": e.tested, "What it is": e.help} for e in vd.evidence])
        st.dataframe(df, hide_index=True, use_container_width=True,
                     column_config={"Leans": st.column_config.TextColumn("Leans", help=TIP["lean"]),
                                    "Weight": st.column_config.NumberColumn("Weight", help=TIP["weight"], format="%g"),
                                    "Tested?": st.column_config.TextColumn("Tested?", help=TIP["tested"]),
                                    "Reading": st.column_config.TextColumn("Reading", width="large")})
        st.caption("Weight 0 = context only (short-term or untested). N/A = data unavailable or not applicable — never "
                   "estimated. 'RIOT only' = the module only has Riot's filing data.")

    def _disagree(self, vd):
        st.markdown("#### Where the tabs disagree")
        if not vd.disagreements:
            st.caption("No tab points the other way right now.")
            return
        for e in vd.disagreements:
            tag = "counts toward confidence" if e.weight > 0 else "context only — doesn't change the call"
            st.markdown(f"- **{e.source}** leans **{V.lean_word(e.lean)}** ({tag}): {e.reading}")
        st.caption("Disagreement is normal: short-term tools answer 'next few weeks', the verdict answers "
                   f"'what should a risk-averse holder do with a {PLAN_YEAR} plan'.")
