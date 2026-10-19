"""
components/holding_plan.py — "🧭 My Plan": the ONE place the dashboard says
Hold / Trim / Sell / Rotate, written for a risk-averse long-term holder with a
2030 sell-or-rotate plan who is new to investing.
"""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.explain import explain, HELP, GLOSSARY
from utils.holding_advisor import advise, compute_facts, scenario_paths, years_to, add_signal, peer_vs_200
from utils.market_data import fetch_daily_closes, fetched_at
from utils.tickers import WATCHLIST, MINING_STOCKS, resolve

_ACTION_STYLE = {
    "HOLD":   ("#00c853", "🟢"),
    "TRIM":   ("#ffb300", "🟡"),
    "ROTATE": ("#29b6f6", "🔄"),
    "SELL":   ("#ff1744", "🔴"),
}
_STATUS_ICON = {"good": "✅", "warn": "⚠️", "bad": "🚨", "info": "ℹ️", "missing": "❔"}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _analyst_targets_cached(symbol: str) -> dict:
    import yfinance as yf
    info = yf.Ticker(symbol).info or {}   # raises on rate limit -> not cached
    out = {"low": info.get("targetLowPrice"), "mean": info.get("targetMeanPrice"),
           "high": info.get("targetHighPrice"), "n": info.get("numberOfAnalystOpinions"),
           "rating": info.get("recommendationKey")}
    return out if out["mean"] else {}


def _analyst_targets(symbol: str) -> dict:
    try:
        return _analyst_targets_cached(symbol)
    except Exception:
        return {}


def _load_user_data():
    from components.personal_portfolio import PersonalPortfolio
    positions = PersonalPortfolio._load_positions()
    targets = PersonalPortfolio._load_targets()
    return positions, targets


def _market_bundle(symbols):
    tickers = tuple(sorted(set(list(symbols) + list(WATCHLIST) + ["BTC-USD", "^VIX"])))
    return fetch_daily_closes(tickers, "2y")


def _best_peer(closes, exclude):
    best = None
    for t in WATCHLIST:
        if t == exclude or t not in closes.columns:
            continue
        f = compute_facts(closes[t])
        if not f or f.get("sma200") is None or f.get("ret_3m") is None:
            continue
        if f["price"] > f["sma200"] and (best is None or f["ret_3m"] > best["ret_3m"]):
            best = {"ticker": t, "ret_3m": f["ret_3m"]}
    return best


def get_advice(symbol: str = "RIOT"):
    """Compute advice for one holding (used by the tab and the Command Center line)."""
    symbol = resolve(symbol)
    positions, targets = _load_user_data()
    closes = _market_bundle(list(positions.keys()) + [symbol])
    if closes.empty or symbol not in closes.columns:
        return None, closes, positions, targets
    last = {s: float(closes[s].dropna().iloc[-1]) for s in positions if s in closes.columns and closes[s].notna().any()}
    port_value = sum(positions[s]["shares"] * last[s] for s in last) or None
    btc = compute_facts(closes["BTC-USD"]) if "BTC-USD" in closes.columns else {}
    vix = float(closes["^VIX"].dropna().iloc[-1]) if "^VIX" in closes.columns and closes["^VIX"].notna().any() else None
    div = None
    if symbol == "RIOT":
        try:
            from utils.riot_correlation import load_riot_correlations
            div = load_riot_correlations().get("divergence")
        except Exception:
            div = None
    pos = positions.get(symbol, {})
    adv = advise(symbol, compute_facts(closes[symbol]), btc, vix,
                 shares=pos.get("shares", 0), cost_basis=pos.get("cost_basis", 0.0),
                 portfolio_value=port_value, target_price=targets.get(symbol),
                 analyst=_analyst_targets(symbol), divergence=div,
                 best_peer=_best_peer(closes, symbol))
    return adv, closes, positions, targets


def get_add_advice(symbol, closes, positions):
    """ADD / WAIT for one holding, from the same price bundle."""
    last = {s: float(closes[s].dropna().iloc[-1]) for s in positions if s in closes.columns and closes[s].notna().any()}
    port_value = sum(positions[s]["shares"] * last[s] for s in last) or None
    pos = positions.get(symbol, {})
    weight = (pos.get("shares", 0) * last[symbol] / port_value) if (port_value and symbol in last) else None
    btc = compute_facts(closes["BTC-USD"]) if "BTC-USD" in closes.columns else {}
    vix = float(closes["^VIX"].dropna().iloc[-1]) if "^VIX" in closes.columns and closes["^VIX"].notna().any() else None
    peers = [t for t in WATCHLIST if t != symbol]
    return add_signal(compute_facts(closes[symbol]), btc, vix, peer_vs_200(closes, peers), weight)


class HoldingPlan:
    def render(self):
        st.header("🧭 My Plan — Hold, Trim, Sell or Rotate?")
        st.caption("Built for a **risk-averse, long-term holder** planning to sell or rotate around **2030**. "
                   "Uses live prices plus your own positions, cost basis and target prices from the 🏆 Portfolio tab. "
                   "Educational tool — **not financial advice**.")

        positions, _ = _load_user_data()
        held = [s for s, p in positions.items() if p.get("shares", 0) > 0] or ["RIOT"]
        default = held.index("RIOT") if "RIOT" in held else 0
        symbol = st.selectbox("Which holding?", held, index=default,
                              format_func=lambda s: f"{s} — {MINING_STOCKS.get(s, positions.get(s, {}).get('name', s))}",
                              help="Your holdings from the Portfolio tab. RIOT is your largest position.")

        with st.spinner("Checking prices, Bitcoin, the VIX and your position…"):
            adv, closes, positions, targets = get_advice(symbol)
        if adv is None:
            st.error(f"⚠️ No price data for {symbol} from Yahoo Finance right now — no recommendation shown. "
                     "Try 🔄 Refresh Data in a minute.")
            return

        # ── Verdict card ─────────────────────────────────────────────────
        color, icon = _ACTION_STYLE[adv.action]
        st.markdown(
            f'<div style="background:{color}1a;border:2px solid {color};border-radius:12px;padding:18px 22px;margin:6px 0 12px">'
            f'<div style="font-size:.85rem;color:#bbb">Recommendation for {symbol} · confidence: <b>{adv.confidence}</b> · '
            f'risk points {adv.risk_score}/{adv.max_score}</div>'
            f'<div style="font-size:2rem;font-weight:800;color:{color};margin:4px 0">{icon} {adv.action}</div>'
            f'<div style="font-size:1.05rem;color:#eee">{adv.headline}</div></div>',
            unsafe_allow_html=True)
        explain("recommendation")

        f = adv.facts
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Last close", f"${f['price']:,.2f}", help="Latest daily close from Yahoo Finance (may be delayed).")
        c2.metric("Your position value", f"${f['value']:,.0f}" if f["value"] else "n/a",
                  help=HELP["cost_basis"])
        c3.metric("Gain vs cost basis", "n/a" if np.isnan(f["gain"]) else f"{f['gain']:+.0%}", help=HELP["cost_basis"])
        c4.metric("Share of your portfolio", "n/a" if np.isnan(f["weight"]) else f"{f['weight']:.0%}",
                  help="This position's value ÷ the value of all positions saved in the Portfolio tab.")

        # ── The checks ───────────────────────────────────────────────────
        st.subheader("Why — the checks behind the call")
        for chk in adv.checks:
            pts = f" · **+{chk.points} risk**" if chk.points else ""
            st.markdown(f"{_STATUS_ICON.get(chk.status, '•')} **{chk.name}** — {chk.detail}{pts}")
        keys = [c.help_key for c in adv.checks if c.help_key]
        with st.expander("ℹ️ What do these checks mean? (plain English)"):
            for k in dict.fromkeys(keys):
                title, body = GLOSSARY[k]
                st.markdown(f"**{title}**  \n{body}")
                st.markdown("---")

        self._render_add(symbol, closes, positions)

        st.subheader("🔁 What would change my mind")
        for line in adv.change_my_mind:
            st.markdown(f"- {line}")
        st.caption("Re-check after each quarterly earnings report and whenever one of these levels is crossed.")

        # ── Path to 2030 ─────────────────────────────────────────────────
        self._render_path(symbol, closes, positions, targets, adv)

        # ── All holdings at a glance ─────────────────────────────────────
        self._render_all_holdings(closes, positions, targets)

        last_date = closes[symbol].dropna().index[-1].date()
        st.caption(f"Sources: Yahoo Finance daily closes to {last_date} (2 years, cached 15 min), Yahoo analyst targets "
                   f"(cached 6 h), your saved positions/targets. Computed {fetched_at()}. "
                   "This is an educational tool, not financial advice — markets can do anything.")

    # ------------------------------------------------------------------
    def _render_path(self, symbol, closes, positions, targets, adv):
        st.subheader(f"🗺️ Path to 2030 — what {symbol} could be worth")
        explain("projection")
        f = compute_facts(closes[symbol])
        price, vol = f["price"], f.get("vol_1y")
        c1, c2 = st.columns([1, 2])
        with c1:
            year = st.slider("Plan year", 2027, 2032, 2030, help="The year you plan to sell or rotate.")
        with c2:
            with st.expander("⚙️ Scenario assumptions (yearly return) — edit to your own view"):
                a1, a2, a3 = st.columns(3)
                bear = a1.number_input("Bear %/yr", -60.0, 0.0, -20.0, 5.0,
                                       help="Crypto winter / dilution / AI-hosting story fails.") / 100
                base = a2.number_input("Base %/yr", -20.0, 40.0, 5.0, 5.0,
                                       help="Muddle-through: Bitcoin and AI hosting grow modestly, dilution continues.") / 100
                bull = a3.number_input("Bull %/yr", 0.0, 100.0, 25.0, 5.0,
                                       help="Strong Bitcoin cycle plus successful AI data-center conversion.") / 100
        yrs = years_to(year)
        sc = scenario_paths(price, yrs, {"Bear": bear, "Base": base, "Bull": bull}, vol)
        shares = positions.get(symbol, {}).get("shares", 0)

        months = pd.date_range(date.today(), periods=max(2, int(yrs * 12) + 1), freq="MS")
        t = np.array([(d.date() - date.today()).days / 365.25 for d in months]).clip(min=0)
        fig = go.Figure()
        hist = closes[symbol].dropna().iloc[-504:]
        fig.add_trace(go.Scatter(x=hist.index, y=hist.values, name="History", line=dict(color="#bbb", width=1.5)))
        if vol:
            fig.add_trace(go.Scatter(x=list(months) + list(months[::-1]),
                                     y=list(price * np.exp(vol * np.sqrt(t))) + list((price * np.exp(-vol * np.sqrt(t)))[::-1]),
                                     fill="toself", fillcolor="rgba(255,255,255,.07)", line=dict(width=0),
                                     name=f"Typical range (±1σ, {vol:.0%} vol)", hoverinfo="skip"))
        for name, g, colr in [("Bull", bull, "#00c853"), ("Base", base, "#ffd600"), ("Bear", bear, "#ff1744")]:
            fig.add_trace(go.Scatter(x=months, y=price * (1 + g) ** t, name=f"{name} ({g:+.0%}/yr)",
                                     line=dict(color=colr, width=2, dash="dash")))
        an = _analyst_targets(symbol)
        if an:
            one_year = pd.Timestamp(date.today()) + pd.DateOffset(years=1)
            fig.add_trace(go.Scatter(x=[one_year] * 3, y=[an.get("low"), an.get("mean"), an.get("high")],
                                     mode="markers+text", text=["analyst low", "analyst avg", "analyst high"],
                                     textposition="middle right", marker=dict(size=9, color="#29b6f6"),
                                     name="Analyst 12-mo targets"))
        tgt = targets.get(symbol)
        if tgt:
            fig.add_hline(y=tgt, line_dash="dot", line_color="#ffb300", annotation_text=f"Your target ${tgt:,.2f}")
        fig.update_layout(template="plotly_dark", height=460, yaxis_title="Price ($)", hovermode="x unified",
                          legend=dict(orientation="h"), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        rows = []
        for name in ["Bear", "Base", "Bull"]:
            p = sc[name]
            rows.append({"Scenario": name, f"Price end of {year}": f"${p:,.2f}", "Change": f"{p/price-1:+.0%}",
                         "Your position value": f"${p*shares:,.0f}" if shares else "n/a"})
        if vol:
            rows.append({"Scenario": "Typical range (data-driven)",
                         f"Price end of {year}": f"${sc['band_low']:,.2f} – ${sc['band_high']:,.2f}",
                         "Change": f"{sc['band_low']/price-1:+.0%} to {sc['band_high']/price-1:+.0%}",
                         "Your position value": (f"${sc['band_low']*shares:,.0f} – ${sc['band_high']*shares:,.0f}" if shares else "n/a")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Bear/Base/Bull are **assumptions you can edit**, not predictions. The 'typical range' uses only "
                   f"{symbol}'s own last-year volatility (about 2 in 3 outcomes historically fall inside it) — "
                   "it shows how wide the possibilities are, not which way the price will go.")

        with st.expander("📅 A simple, low-stress 2030 exit framework (education, not advice)"):
            st.markdown(f"""
- **Don't plan to sell everything on one day.** Miners can move 10% in a day. Selling in stages
  (for example a third in late {year-1}, a third in early {year}, the rest later in {year}) averages out your exit price.
- **Trim on strength, not on panic.** If your own target or the bull case arrives early, selling 10–25% locks in gains
  and lowers risk while keeping you in for the rest of the plan.
- **Keep any single stock to a size you can sleep with.** If one position is more than ~40% of your portfolio,
  gradually rotating some into less volatile holdings reduces the chance one bad year wrecks the plan.
- **Know your re-check triggers** (listed above under "What would change my mind") and look again after each earnings report.
- **Taxes:** shares held over a year usually qualify for lower long-term capital-gains rates in the US. Check with a tax adviser before large sales.
""")

    # ------------------------------------------------------------------
    def _render_add(self, symbol, closes, positions):
        st.subheader("➕ Good time to add more?")
        a = get_add_advice(symbol, closes, positions)
        color = "#00c853" if a.action == "ADD" else "#90a4ae"
        st.markdown(
            f'<div style="background:{color}1a;border-left:5px solid {color};border-radius:8px;padding:12px 16px;margin:4px 0 8px">'
            f'<b style="color:{color};font-size:1.3rem">{"➕ ADD" if a.action == "ADD" else "⏸️ WAIT"}</b>'
            f' <span style="color:#bbb">· confidence {a.confidence}</span><br>'
            f'<span style="color:#eee">{a.headline}</span></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Is it on sale?** (need 2 of 3)")
            for chk in a.oversold:
                st.markdown(f"{'✅' if chk.status == 'good' else '❔' if chk.status == 'missing' else '▫️'} "
                            f"**{chk.name}** — {chk.detail}")
        with c2:
            st.markdown("**Is the backdrop healthy?** (need all 3)")
            for chk in a.backdrop:
                st.markdown(f"{_STATUS_ICON.get(chk.status, '•')} **{chk.name}** — {chk.detail}")
        with st.expander("📍 Price / condition levels that would trigger ADD"):
            for lv in a.levels:
                st.markdown(f"- {lv}")
        explain("add_signal")
        explain("rsi")

    # ------------------------------------------------------------------
    def _render_all_holdings(self, closes, positions, targets):
        st.subheader("📋 All your holdings at a glance")
        rows = []
        last = {s: float(closes[s].dropna().iloc[-1]) for s in positions if s in closes.columns and closes[s].notna().any()}
        port_value = sum(positions[s]["shares"] * last[s] for s in last) or None
        btc = compute_facts(closes["BTC-USD"]) if "BTC-USD" in closes.columns else {}
        vix = float(closes["^VIX"].dropna().iloc[-1]) if "^VIX" in closes.columns and closes["^VIX"].notna().any() else None
        for s, p in positions.items():
            if p.get("shares", 0) <= 0:
                continue
            if s not in closes.columns:
                rows.append({"Stock": s, "Call": "n/a (no data)"})
                continue
            a = advise(s, compute_facts(closes[s]), btc, vix, shares=p["shares"], cost_basis=p["cost_basis"],
                       portfolio_value=port_value, target_price=targets.get(s))
            rows.append({"Stock": s, "Call": f"{_ACTION_STYLE[a.action][1]} {a.action}", "Confidence": a.confidence,
                         "Risk pts": a.risk_score, "Last": f"${a.facts['price']:,.2f}",
                         "Gain": "n/a" if np.isnan(a.facts["gain"]) else f"{a.facts['gain']:+.0%}",
                         "Weight": "n/a" if np.isnan(a.facts["weight"]) else f"{a.facts['weight']:.0%}",
                         "Your target": f"${targets[s]:,.2f}" if targets.get(s) else "—"})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption("Same rules as above (the RIOT-only peer-divergence check is applied to RIOT only). "
                       "Edit shares, cost basis and targets in 🏆 Portfolio.")
