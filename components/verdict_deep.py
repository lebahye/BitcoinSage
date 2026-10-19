"""⚖️ Stock Verdict — "Deeper evidence" (8 extra analyses), grouped Long-cycle / Company / Market mood.

Each row: one-line takeaway, tooltip, source + date, tested/untested, weight.  Only rows that are backtested
WITH an edge, or structurally sound (convertible dilution, peer valuation), carry weight — and weight only moves
confidence (utils.verdict), never the action.  Slow, weight-0 market-mood pulls are lazy (checkbox).
"""
from __future__ import annotations

import math
from datetime import date
from typing import List

import pandas as pd
import streamlit as st

from utils import deep_evidence as de
from utils.deep_facts import CONVERTS, TREASURY, AI_PEERS, AI_PEER_SET
from utils.verdict import Evidence, lean_word

GROUPS = ("Long-cycle", "Company", "Market mood")
W_STRUCT = 5          # weight for structurally sound rows (converts, peer valuation)
W_EDGE = 5            # weight for backtested rows ONLY when the current reading has a significant edge


def _src(key):
    from utils.deep_sources import SOURCES
    name, url = SOURCES[key]
    return f"[{name}]({url})"


def _pct(x, nd=0):
    return "N/A" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x*100:+.{nd}f}%"


def _m(x):
    return "N/A" if x is None else (f"${x/1e9:,.1f}B" if abs(x) >= 1e9 else f"${x/1e6:,.0f}M")


def _ev(key, title, group, takeaway, lean, weight, tested, help_, source_ref, as_of, reading=None):
    return Evidence(key, title, reading or takeaway, lean, weight, tested, help_, group, takeaway, source_ref,
                    str(as_of) if as_of else "N/A")


def _na(key, title, group, why, tested, help_="", source_ref="—"):
    return _ev(key, title, group, f"N/A — {why}", None, 0, tested, help_, source_ref, None)


# ── backtests (cached; point-in-time) ───────────────────────────────────
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _cycle_bt_cached(symbol: str) -> dict:
    from utils import signal_hub
    from utils.deep_sources import coinmetrics_btc
    cm = coinmetrics_btc()
    if cm is None:
        raise RuntimeError("no on-chain data")
    m = de.cycle_metrics(cm)
    st_ = signal_hub.get_ohlcv(symbol, "max")
    if st_.empty:
        raise RuntimeError("no stock data")
    px = st_["Close"].dropna()
    px = px[px.index >= "2018-01-01"]
    return {"metrics": m, "z": de.zone_backtest(px, m["mvrv_z"], de.mvrv_zone),
            "puell": de.zone_backtest(px, m["puell"], de.puell_zone) if "puell" in m else {},
            "start": px.index[0].date() if len(px) else None}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _regime_bt_cached(symbol: str) -> dict:
    from utils import signal_hub
    from utils import reflexivity as rx
    h = signal_hub.get_ohlcv(symbol, "max")
    if h.empty or len(h) < 800:
        raise RuntimeError("not enough history")
    px = h["Close"].dropna()
    labels = de.vol_regime_labels(px)
    keep = labels.index >= "2018-01-01"
    px, labels = px[keep], labels[keep]
    return {"labels": labels, "tables": {hz: rx.backtest_labels(px, labels, hz, delay=1) for hz in de.HORIZONS}}


def _edge_text(edge):
    if not edge:
        return "backtest: N/A"
    t = "N/A" if edge["t"] is None else f"{edge['t']:+.1f}"
    return (f"backtest ({edge['n']} past cases, {edge['h']} trading days later): typical {_pct(edge['typical'])} vs "
            f"{_pct(edge['baseline'])} for any day, t {t} → {edge['verdict']}")


# ── rows ────────────────────────────────────────────────────────────────
def long_cycle_rows(symbol: str) -> List[Evidence]:
    rows = []
    try:
        bt = _cycle_bt_cached(symbol)
    except Exception as e:
        bt = None
        why = f"on-chain data unavailable ({type(e).__name__})"
    if bt is None:
        rows.append(_na("mvrv", "MVRV-Z (Bitcoin long-cycle valuation)", "Long-cycle", why, "backtested", source_ref=_src("coinmetrics")))
        rows.append(_na("puell", "Puell Multiple (miner revenue vs its 1-yr average)", "Long-cycle", why, "backtested", source_ref=_src("coinmetrics")))
        return rows
    m = bt["metrics"].dropna(subset=["mvrv_z"])
    last = m.iloc[-1]
    asof = m.index[-1].date()
    zone = de.mvrv_zone(last["mvrv_z"])
    edge = de.edge_for_label(bt["z"], zone)
    w, lean_bt = de.edge_weight_and_lean(edge, W_EDGE)
    rows.append(_ev("mvrv", "MVRV-Z (Bitcoin long-cycle valuation)", "Long-cycle",
                    f"Bitcoin is in the **{zone}** zone — MVRV {last['mvrv']:.2f}, Z {last['mvrv_z']:.2f}; the average "
                    f"coin last moved at ≈${last.get('realized_price', float('nan')):,.0f} (realized price).",
                    lean_bt if w else de.zone_lean(zone), w, "backtested" + ("" if w else " (no edge → weight 0)"),
                    "MVRV = Bitcoin's market value ÷ 'realized' value (each coin priced when it last moved). High = holders "
                    "sit on big gains (past tops); low = near cost (past bottoms). Z scales it by history. Rule of thumb, "
                    f"tested here against {symbol}'s later returns since {bt['start']}.",
                    _src("coinmetrics") + " (realized cap = market cap ÷ MVRV)", asof,
                    reading=f"Z {last['mvrv_z']:.2f} ({zone}); {_edge_text(edge)}"))
    p = last.get("puell")
    if p is not None and p == p:
        pz = de.puell_zone(p)
        pe = de.edge_for_label(bt["puell"], pz)
        pw, pl = de.edge_weight_and_lean(pe, W_EDGE)
        rows.append(_ev("puell", "Puell Multiple (miner revenue vs its 1-yr average)", "Long-cycle",
                        f"Miners' daily issuance is {p:.2f}× its 1-year average — **{pz}**.",
                        pl if pw else de.zone_lean(pz), pw, "backtested" + ("" if pw else " (no edge → weight 0)"),
                        "Daily value of new coins ÷ its 365-day average. Below ~0.6 miners are squeezed (historically near "
                        "cycle lows); above ~2 they're flush (near highs). Issuance only (no fees).",
                        _src("coinmetrics") + " (IssTotUSD)", asof, reading=f"{p:.2f} ({pz}); {_edge_text(pe)}"))
    else:
        rows.append(_na("puell", "Puell Multiple", "Long-cycle", "issuance data missing", "backtested", source_ref=_src("coinmetrics")))
    return rows


def company_rows(symbol: str, price) -> List[Evidence]:
    rows = []
    # 3. Converts
    d = de.convert_dilution(CONVERTS.get(symbol), price)
    if d is None:
        rows.append(_na("converts", "Convertible debt & warrants → potential new shares", "Company",
                        f"no cited convertible facts on file for {symbol} yet", "measured"))
    else:
        f = CONVERTS[symbol]
        n0 = d["notes"][0] if d["notes"] else None
        nf = f["notes"][0] if f.get("notes") else {}
        tk = (f"{_m(n0['principal'])} of convertible notes could become **{n0['shares']/1e6:,.1f}M new shares "
              f"({n0['pct']:.1%} more)** at ${n0['conversion_price']:.2f}; the stock is at {n0['moneyness']:.0%} of that "
              f"price. Matures {n0['maturity']:%b %Y}." if n0 else "No convertible notes outstanding.")
        if d["atm_shares"]:
            tk += f" Plus an unused {_m(f['atm_capacity_usd'])} at-the-market share program (≈{d['atm_pct']:.0%} more shares at today's price, if used)."
        rows.append(_ev("converts", "Convertible debt & warrants → potential new shares", "Company", tk,
                        de.lean_converts(d), W_STRUCT, "measured (filings)",
                        "If converted into shares, convertible bonds dilute today's holders. Near or above the conversion "
                        "price, conversion becomes likely. Settlement can be cash or shares at the company's choice. "
                        + nf.get("status_note", ""),
                        " · ".join(f"[filing]({u})" for u in nf.get("sources", [])) or "—",
                        nf.get("as_of"),
                        reading=(f"{n0['shares']/1e6:,.1f}M shares ({n0['pct']:.1%}) at ${n0['conversion_price']:.2f}; "
                                 f"price/conversion {n0['moneyness']:.2f}" if n0 else "none")))
    # 2. Treasury flows
    t = de.treasury_summary(TREASURY.get(symbol))
    if t is None:
        rows.append(_na("treasury", "Miner treasury: BTC produced vs sold vs held", "Company",
                        f"no cited production report on file for {symbol}", "measured"))
    else:
        r = TREASURY[symbol][-1]
        verb = "sold more than it mined" if (t["sold_ratio"] or 0) > 1 else "kept part of what it mined"
        tk = (f"{t['period']}: mined {t['produced']:,} BTC, sold {t['sold']:,}, holds {t['held']:,} — {verb}"
              + (f" (holdings {_pct(t['held_change'])} vs prior period)." if t["held_change"] is not None else "."))
        rows.append(_ev("treasury", "Miner treasury: BTC produced vs sold vs held", "Company", tk,
                        -0.5 if (t["sold_ratio"] or 0) > 1 else 0.0, 0, "measured (untested as a signal)",
                        "Selling more bitcoin than you mine means the treasury funds spending (e.g. AI data-centre builds). "
                        "Descriptive only. " + r.get("note", ""), f"[report]({r['source']})", t["end"]))
    # 4. AI/HPC peer valuation
    if symbol not in AI_PEER_SET:
        rows.append(_na("peers", "AI/HPC peer valuation (EV per contracted MW)", "Company",
                        "covers the AI-hosting miners only (RIOT, CORZ, IREN, APLD, WULF, CIFR, HUT, CLSK)", "measured"))
    else:
        tab = peer_table()
        rel = de.peer_relative(tab, symbol, "ev_per_mw")
        if rel is None:
            rows.append(_na("peers", "AI/HPC peer valuation (EV per contracted MW)", "Company",
                            "enterprise values unavailable from Yahoo right now", "measured"))
        else:
            f = AI_PEERS[symbol]
            word = "cheaper than" if rel["ratio"] <= 0.7 else "more expensive than" if rel["ratio"] >= 1.5 else "in line with"
            rows.append(_ev("peers", "AI/HPC peer valuation (EV per contracted MW)", "Company",
                            f"{symbol}'s whole company value is **${rel['value']/1e6:,.0f}M per contracted AI megawatt** vs a "
                            f"peer median ${rel['median']/1e6:,.0f}M ({rel['ratio']:.1f}×) — {word} peers on this yardstick.",
                            de.lean_peer(rel), W_STRUCT, "measured (filings + live EV)",
                            "EV = market value + debt − cash (Yahoo, live). Contracted MW = signed AI/HPC capacity (critical IT). "
                            "Crude: EV also pays for mining businesses and bitcoin held, and contract definitions differ.",
                            f"[peer MW compilation]({f['source']}) · Yahoo EV", f["as_of"],
                            reading=f"${rel['value']/1e6:,.0f}M/MW vs median ${rel['median']/1e6:,.0f}M ({rel['ratio']:.1f}×, {rel['n_peers']} peers)"))
    return rows


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _peer_table_cached(overrides: tuple = ()) -> pd.DataFrame:
    from utils.deep_sources import yahoo_info
    ev = {}
    for s in AI_PEER_SET:
        i = yahoo_info(s)
        ev[s] = i.get("enterpriseValue") or ((i.get("marketCap") or 0) + (i.get("totalDebt") or 0)
                                            - (i.get("totalCash") or 0)) or None
    facts = {s: dict(AI_PEERS[s]) for s in AI_PEER_SET}
    for s, k, v in overrides:
        facts[s][k] = v
    tab = de.peer_valuation(ev, facts)
    if tab["ev"].notna().sum() < 4:
        raise RuntimeError("too few EVs")
    return tab


def peer_table(overrides: tuple = ()):
    try:
        return _peer_table_cached(overrides)
    except Exception:
        return None


def mood_rows(symbol: str, price, load_live: bool) -> List[Evidence]:
    from utils.deep_sources import yahoo_info, option_chain, POLY_EVENTS, polymarket_event, kalshi_next_fed
    rows = []
    # 7. Regime
    try:
        r = _regime_bt_cached(symbol)
        cur = r["labels"].dropna()
        lab, asof = cur.iloc[-1], cur.index[-1].date()
        edge = de.edge_for_label(r["tables"], lab)
        w, l = de.edge_weight_and_lean(edge, W_EDGE)
        rows.append(_ev("regime", "Volatility regime (calm / normal / stormy)", "Market mood",
                        f"{symbol} is in a **{lab}** stretch: its last-month swings rank in the "
                        f"{'bottom' if lab == 'calm' else 'top' if lab == 'stormy' else 'middle'} third of the past 2 years "
                        "(this measures the size of day-to-day moves, not direction — a steady slide can be 'calm').",
                        l if w else 0.0, w, "backtested" + ("" if w else " (no edge → weight 0)"),
                        "21-day realised volatility ranked against its own previous 2 years (point-in-time). Tested: does "
                        "the regime say anything about the next 6–12 months?", "Yahoo prices (computed here)", asof,
                        reading=f"{lab}; {_edge_text(edge)}"))
    except Exception as e:
        rows.append(_na("regime", "Volatility regime", "Market mood", f"not enough price history ({type(e).__name__})", "backtested"))
    # 8. Short interest
    si = de.short_interest(yahoo_info(symbol))
    if si is None:
        rows.append(_na("short", "Short interest & days to cover", "Market mood", "not reported by Yahoo right now", "untested",
                        source_ref=_src("yahoo")))
    else:
        rows.append(_ev("short", "Short interest & days to cover", "Market mood",
                        f"{_pct(si['pct_float'], 1).lstrip('+')} of tradable shares are sold short — {de.short_label(si)}; "
                        f"{si['days_to_cover'] or 'N/A'} days of normal volume to buy them back"
                        + (f" (short position {_pct(si['change'])} vs prior month)." if si["change"] is not None else "."),
                        0.0, 0, "untested", "High short interest = many bet on a fall; it can also fuel sharp 'squeeze' "
                        "rallies. Borrow cost isn't available free (N/A). Reported twice a month, with a lag.",
                        _src("yahoo"), si["as_of"]))
    if not load_live:
        rows.append(_ev("options", "Options fear (25-delta skew, max pain)", "Market mood",
                        "Not loaded — tick 'Load live options & prediction markets'.", None, 0, "untested", "", _src("yahoo"), None))
        rows.append(_ev("odds", "Prediction-market odds (CLARITY Act, midterms, Fed)", "Market mood",
                        "Not loaded — tick 'Load live options & prediction markets'.", None, 0, "untested", "",
                        _src("polymarket") + " · " + _src("kalshi"), None))
        return rows
    # 5. Options
    ch = option_chain(symbol)
    if ch is None or not price:
        rows.append(_na("options", "Options fear (25-delta skew, max pain)", "Market mood", "no option chain from Yahoo",
                        "untested", source_ref=_src("yahoo")))
    else:
        sk = de.skew_25d(ch["calls"], ch["puts"], price, ch["days"] / 365)
        mp = de.max_pain(ch["calls"], ch["puts"])
        pc = de.put_call_oi(ch["calls"], ch["puts"])
        parts = []
        if sk:
            parts.append(f"downside protection costs {sk['skew']*100:+.0f} vol pts vs upside bets "
                         f"({'fearful' if sk['skew'] > 0.10 else 'calm' if sk['skew'] < 0.02 else 'mildly cautious'})")
        else:
            parts.append("25-delta skew N/A (no liquid strikes near 25-delta)")
        parts.append(f"max pain ${mp:,.2f}" if mp else "max pain N/A")
        parts.append(f"put/call open interest {pc:.2f}" if pc else "put/call N/A")
        rows.append(_ev("options", "Options fear (25-delta skew, max pain)", "Market mood",
                        f"Options expiring {ch['expiry']} ({ch['days']} days): " + "; ".join(parts) + ".",
                        0.0, 0, "untested",
                        "Skew = implied volatility of a ~25-delta put minus a ~25-delta call (Black-Scholes deltas from "
                        "Yahoo IVs). Max pain = the expiry price where option buyers collectively get least. Free data is "
                        "delayed and thin — context only.", _src("yahoo"), ch["fetched"][:10]))
    # 6. Prediction markets
    bits, n_ok = [], 0
    for lab, slug in POLY_EVENTS.items():
        y = de.polymarket_yes(polymarket_event(slug))
        if y:
            n_ok += 1
            bits.append(f"{lab}: {de.short_question(y[0]['question'])} {y[0]['yes']:.0%}")
    k = kalshi_next_fed()
    ky = de.kalshi_yes(k)
    if ky:
        n_ok += 1
        bits.append(f"Next Fed meeting (Kalshi): {ky[0]['question']} {ky[0]['yes']:.0%}")
    if not n_ok:
        rows.append(_na("odds", "Prediction-market odds (CLARITY Act, midterms, Fed)", "Market mood",
                        "Polymarket and Kalshi unavailable right now", "untested", source_ref=_src("polymarket") + " · " + _src("kalshi")))
    else:
        rows.append(_ev("odds", "Prediction-market odds (CLARITY Act, midterms, Fed)", "Market mood",
                        " · ".join(bits) + ".", 0.0, 0, "untested",
                        "Crowd-priced probabilities from real-money markets. Useful for 'what's priced in' around events; "
                        "not a forecast of the stock.", _src("polymarket") + " · " + _src("kalshi"), date.today()))
    return rows


def deep_rows(symbol: str, price, load_live: bool = False) -> List[Evidence]:
    out = []
    for fn, args in ((long_cycle_rows, (symbol,)), (company_rows, (symbol, price)), (mood_rows, (symbol, price, load_live))):
        try:
            out += fn(*args)
        except Exception as e:      # one broken analysis never breaks the page
            out.append(_na(fn.__name__, fn.__name__.replace("_rows", "").replace("_", " ").title(), "Market mood",
                           f"error ({type(e).__name__})", "untested"))
    return out


def render(rows: List[Evidence]):
    """The collapsed 'Deeper evidence' section."""
    w = [r for r in rows if r.weight > 0]
    with st.expander(f"🔎 Deeper evidence — 8 extra analyses ({len(w)} currently count toward confidence)", expanded=False):
        st.caption("Grouped by question. Only analyses that are **backtested with a real edge** or **structurally sound** "
                   "(convertible dilution, peer valuation) carry weight — and weight can only make the verdict more or "
                   "less sure, **never change the action**. Everything else is weight 0: context.")
        st.checkbox("Load live options & prediction markets", value=False, key="verdict_deep_live",
                    help="Fetches option chains (Yahoo) and Polymarket/Kalshi odds — a few seconds. Weight 0 either way.")
        for g in GROUPS:
            gr = [r for r in rows if r.group == g]
            if not gr:
                continue
            st.markdown(f"**{ {'Long-cycle': '🕰️', 'Company': '🏢', 'Market mood': '🌡️'}[g] } {g}**")
            for r in gr:
                st.markdown(f"- **{r.source}** — {r.takeaway}", help=r.help or None)
            st.dataframe(pd.DataFrame([{"Analysis": r.source, "Leans": lean_word(r.lean), "Weight": r.weight,
                                        "Tested?": r.tested, "As of": r.as_of, "Source": r.source_ref}
                                       for r in gr]), hide_index=True, use_container_width=True)
