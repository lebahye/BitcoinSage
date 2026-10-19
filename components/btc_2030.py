"""components/btc_2030.py — '₿ Bitcoin to 2030' panel inside 🧭 My Plan.

Shows (1) editable, sourced Bitcoin scenarios to the plan year, (2) the stock price each implies via the long-horizon
stock↔BTC fit, (3) the Bitcoin price that lines up with a stock target (default $40), reconciled with My Plan's
own Bear/Base/Bull yearly-return paths, (4) halving-cycle timing, (5) a dated policy watchlist and
(6) a sell/rotate milestone checklist.  Scenarios, not promises.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils import btc_scenarios as bs
from utils import riot_btc_link as link
from utils import signal_hub
from utils.explain import HELP, explain


def _money(x, nd=0):
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return "N/A"
    return f"${x:,.{nd}f}"


def _big(x):
    if x is None:
        return "N/A"
    if x >= 1e6:
        return f"${x/1e6:,.2f}M"
    return f"${x/1e3:,.0f}K" if x >= 1e4 else f"${x:,.0f}"


@st.cache_data(ttl=900, show_spinner=False)
def _fit_cached(symbol: str):
    stock = signal_hub.get_ohlcv(symbol, "max")
    btc = signal_hub.get_ohlcv("BTC-USD", "max")
    if stock.empty or btc.empty:
        raise RuntimeError("no data")
    fit = link.fit_link(stock["Close"], btc["Close"])
    return fit, btc["Close"], stock["Close"]


def _load_fit(symbol):
    try:
        return _fit_cached(symbol)
    except Exception:
        return None, None, None


def render(symbol: str, closes: pd.DataFrame, targets: dict, plan_year: int, years: float,
           plan_cagr: dict, block_height=None):
    st.subheader(f"₿ Bitcoin to {plan_year} — what Bitcoin price lines up with your {symbol} plan")
    explain("btc_2030")
    s0 = float(closes[symbol].dropna().iloc[-1])
    b_ser = closes["BTC-USD"].dropna() if "BTC-USD" in closes else pd.Series(dtype=float)
    fit, btc_hist, _ = _load_fit(symbol)
    if b_ser.empty and btc_hist is not None:
        b_ser = btc_hist.dropna()
    if b_ser.empty:
        st.warning("⚠️ No live Bitcoin price from Yahoo Finance right now — Bitcoin scenarios are not shown (N/A).")
        return
    b0 = float(b_ser.iloc[-1])
    corr = link.daily_corr(closes[symbol], closes["BTC-USD"]) if "BTC-USD" in closes else None

    c = st.columns(4)
    c[0].metric("Bitcoin today", _money(b0), help="Latest Yahoo Finance BTC-USD daily close (same data as the rest of My Plan).")
    c[1].metric(f"Daily correlation {symbol}↔BTC (1 yr)", "N/A" if corr is None else f"{corr:.2f}",
                help="Day-to-day co-movement. Says little about where the stock ends up years from now.")
    if fit:
        c[2].metric("BTC sensitivity, full history", f"{fit['beta']:.2f}  (R² {fit['r2']:.2f})", help=HELP["btc_link"])
        c[3].metric("BTC sensitivity, last 3 yrs", "N/A" if fit["recent_beta"] is None else
                    f"{fit['recent_beta']:.2f}  (R² {fit['recent_r2']:.2f})", help=HELP["btc_link"])
    else:
        c[2].metric("BTC sensitivity", "N/A", help="Not enough shared history to fit (needs 3+ years).")

    # ── 1. Bitcoin scenarios ────────────────────────────────────────────
    st.markdown(f"#### 1 · Four Bitcoin paths to end of {plan_year}")
    defaults = bs.default_assumptions()
    with st.expander("⚙️ The 8 drivers behind each Bitcoin path (percentage points per year) — edit to your own view"):
        st.caption("Each scenario's yearly growth = the **sum of its column**. Hover a driver's name in the table below "
                   "for what it means; the facts behind them (with dates) are listed at the bottom of this section.")
        df = pd.DataFrame({s: [defaults[s][d.key] for d in bs.DRIVERS] for s in bs.SCENARIOS},
                          index=[d.label for d in bs.DRIVERS])
        edited = st.data_editor(df, key=f"btc_drivers_{symbol}", use_container_width=True,
                                column_config={s: st.column_config.NumberColumn(s, min_value=-50.0, max_value=50.0,
                                                                                 step=1.0, format="%+.0f")
                                               for s in bs.SCENARIOS})
        for d in bs.DRIVERS:
            st.markdown(f"- **{d.label}** — {d.help}  \n  *Bear:* {d.why['Bear']} · *Base:* {d.why['Base']} · "
                        f"*Bull:* {d.why['Bull']} · *Super-bull:* {d.why['Super-bull']}")
        infl = st.number_input("Inflation to convert to today's dollars (%/yr)", 0.0, 15.0, 3.5, 0.5,
                               key=f"btc_infl_{symbol}",
                               help="US CPI inflation was 3.7% (Sep 2026, BLS). Used only for the 'in today's dollars' column.")
    assumptions = {s: {d.key: float(edited.loc[d.label, s]) for d in bs.DRIVERS} for s in bs.SCENARIOS}
    sc = bs.build_scenarios(b0, years, assumptions, infl / 100)
    rows = [{"Scenario": s, "Growth/yr": f"{v['growth']:+.0%}", f"BTC end of {plan_year}": _big(v["price"]),
             "In today's dollars": _big(v["real_price"]), "× today": f"{v['multiple']:.1f}×"} for s, v in sc.items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("How the drivers combine: growth/yr = sum of the 8 driver numbers; BTC in "
               f"{plan_year} = today's {_money(b0)} × (1 + growth)^{years:.1f} yrs. "
               "Published forecasts for comparison (bullish sources; Standard Chartered already pushed its target back once): "
               + " · ".join(f"{p['who']} {_big(p['price'])} ({p['year']})" for p in bs.PUBLISHED_TARGETS) + ".")

    if not fit:
        st.info(f"N/A — not enough {symbol}/BTC history to link the stock to these Bitcoin paths.")
        return

    # ── 2. Stock implied by each Bitcoin path ───────────────────────────
    st.markdown(f"#### 2 · What each Bitcoin path implies for {symbol}")
    opts = [f"Full history {fit['start']:%Y}–now (beta {fit['beta']:.2f})"]
    if fit["recent_beta"] is not None:
        opts.append(f"Last 3 years only (beta {fit['recent_beta']:.2f})")
    regime = st.radio("Which BTC sensitivity should we assume to 2030?", opts,
                      key=f"btc_regime_{symbol}", horizontal=True, help=HELP["btc_link"])
    beta = fit["beta"] if regime.startswith("Full") else fit["recent_beta"]
    if beta is not None and beta < 0.5:
        st.warning(f"With beta {beta:.2f}, Bitcoin barely moves {symbol}: Bitcoin alone can't get it to much higher prices — "
                   "the result depends mostly on the non-BTC factors below (AI/data-centre leases, dilution).")
    shares = signal_hub.get_shares(symbol)
    d1 = link.measured_dilution(shares, 1.0)
    d3 = link.measured_dilution(shares, 3.0)
    with st.expander(f"⚙️ Things besides Bitcoin that move {symbol} (yearly %) — edit to your own view"):
        st.caption(f"These replace {symbol}'s historical drift apart from Bitcoin, which was **{fit['alpha_yr']:+.0%}/yr** "
                   f"over {fit['start']:%Y}–{fit['end']:%Y} (mostly from issuing new shares). "
                   f"Measured share-count growth: last 12 months **{'N/A' if d1 is None else f'{d1:+.1f}%'}**, "
                   f"last 3 years **{'N/A' if d3 is None else f'{d3:+.1f}%/yr'}** (Yahoo Finance).")
        fc = st.columns(4)
        vals = {}
        for col, (k, lab, hlp, _) in zip(fc, link.FACTORS):
            dv = round(d1, 1) if (k == "dilution" and d1 is not None) else 0.0
            vals[k] = col.number_input(lab, -50.0, 100.0, float(dv), 1.0, key=f"btc_f_{k}_{symbol}", help=hlp)
        st.markdown("AI/data-centre facts: " + " · ".join(
            f"[{v['label']}]({v['url']}) ({v['date']})" for v in link.AI_SOURCES.values()))
    drift = link.drift_from_factors(vals)
    sig = link.horizon_sigma(fit, years)
    imp = {s: link.project_stock(s0, b0, v["price"], years, beta, drift, sig) for s, v in sc.items()}
    hist_rep = {s: link.project_stock(s0, b0, v["price"], years, beta, np.log1p(fit["alpha_yr"]), sig)
                for s, v in sc.items()}
    plan_px = {k: s0 * (1 + g) ** years for k, g in plan_cagr.items()}
    rows = []
    for s in bs.SCENARIOS:
        r = imp[s]
        rows.append({"Bitcoin path": f"{s} ({_big(sc[s]['price'])})",
                     f"{symbol} end of {plan_year}": _money(r["point"], 2),
                     "Likely range (≈2 in 3)": f"{_money(r['low'], 2)} – {_money(r['high'], 2)}",
                     "If past drift repeats": _money(hist_rep[s]["point"], 2)})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption(f"{symbol} = today's {_money(s0, 2)} × (BTC change)^{beta:.2f} × your non-BTC factors "
               f"({np.expm1(drift):+.1%}/yr). Range = how far {symbol} has typically strayed from its Bitcoin-implied "
               f"level (from {-(1-np.exp(-sig)):.0%} to {np.expm1(sig):+.0%} around the middle value). 'If past drift repeats' uses the historical "
               f"{fit['alpha_yr']:+.0%}/yr instead of your factors.")

    # ── 3. Reverse: BTC that lines up with a stock target ───────────────
    st.markdown(f"#### 3 · What Bitcoin price lines up with {symbol} at your target?")
    explain("btc_for_target")
    cx = st.columns(2)
    x = cx[0].number_input(f"{symbol} price to check ($)", 1.0, 1000.0, 40.0, 1.0, key=f"btc_x_{symbol}",
                           help="Default $40 (your bull-case example). Try your own target.")
    checks = [(f"{symbol} at ${x:,.2f}", x)]
    tgt = targets.get(symbol)
    if tgt and abs(tgt - x) > 0.01:
        checks.append((f"Your saved target ${tgt:,.2f}", tgt))
    for k in ["Bear", "Base", "Bull"]:
        if k in plan_px:
            checks.append((f"My Plan {k} ({plan_cagr[k]:+.0%}/yr) → ${plan_px[k]:,.2f}", plan_px[k]))
    rows = []
    for lab, px in checks:
        r = link.btc_for_stock(px, s0, b0, years, beta, drift, sig)
        if r["point"] is None or not r["reachable"]:
            rows.append({"Stock level": lab, f"BTC needed end of {plan_year}": "N/A — Bitcoin alone can't plausibly do it",
                         "Range": "needs AI/HPC or other non-BTC gains", "BTC growth/yr needed": "N/A",
                         "Closest Bitcoin path": "—"})
            continue
        if r["point"] < b0 / link.NOT_REACHABLE_MULT:
            rows.append({"Stock level": lab, f"BTC needed end of {plan_year}": f"under {_big(b0 / link.NOT_REACHABLE_MULT)} "
                         "(a 99%+ Bitcoin crash)", "Range": "Bitcoin barely moves the stock in this setting", "BTC growth/yr needed": "N/A", "Closest Bitcoin path": "—"})
            continue
        cap = link.NOT_REACHABLE_MULT * b0
        hi_txt = _big(r["high"]) if r["high"] <= cap else f"over {_big(cap)}"
        g = bs.growth_needed(b0, r["point"], years)
        near = min(sc, key=lambda s: abs(np.log(sc[s]["price"] / r["point"])))
        rows.append({"Stock level": lab, f"BTC needed end of {plan_year}": _big(r["point"]),
                     "Range": f"{_big(r['low'])} – {hi_txt}",
                     "BTC growth/yr needed": f"{g:+.0%}" if g is not None else "N/A",
                     "Closest Bitcoin path": near})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    st.caption("How My Plan and this section fit together: the My Plan Bear/Base/Bull lines above are **yearly returns for "
               f"{symbol} itself** that you set directly. This section starts from **Bitcoin** and works out {symbol} from "
               f"history. They are different routes, so the numbers differ — the rows above show the Bitcoin price each "
               "My Plan case quietly assumes. If that Bitcoin price looks unrealistic to you, adjust the My Plan case.")

    # ── Chart ───────────────────────────────────────────────────────────
    months = pd.date_range(date.today(), periods=max(2, int(years * 12) + 1), freq="MS")
    t = np.array([(m.date() - date.today()).days / 365.25 for m in months]).clip(min=0)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Bitcoin scenarios (log scale)", f"{symbol}: implied by Bitcoin (solid) vs My Plan (dashed)"))
    bh = b_ser.iloc[-730:]
    fig.add_trace(go.Scatter(x=bh.index, y=bh.values, name="BTC history", line=dict(color="#bbb", width=1.3)), 1, 1)
    sh = closes[symbol].dropna().iloc[-504:]
    fig.add_trace(go.Scatter(x=sh.index, y=sh.values, name=f"{symbol} history", line=dict(color="#bbb", width=1.3),
                             showlegend=False), 2, 1)
    for s, v in sc.items():
        colr = bs.SCENARIO_COLORS[s]
        bp = np.array(bs.path(b0, v["growth"], t))
        fig.add_trace(go.Scatter(x=months, y=bp, name=f"BTC {s}", line=dict(color=colr, width=2)), 1, 1)
        sp = s0 * np.exp(beta * np.log(bp / b0) + t * drift)
        fig.add_trace(go.Scatter(x=months, y=sp, name=f"{symbol} if BTC {s}", line=dict(color=colr, width=2)), 2, 1)
    for p in bs.PUBLISHED_TARGETS:
        if p["year"] <= plan_year:
            fig.add_trace(go.Scatter(x=[pd.Timestamp(p["year"], 12, 31)], y=[p["price"]], mode="markers",
                                     marker=dict(symbol="diamond", size=8, color="#29b6f6"), name=p["who"],
                                     showlegend=False, hovertext=p["who"]), 1, 1)
    for k, colr in [("Bear", "#ff1744"), ("Base", "#ffd600"), ("Bull", "#00c853")]:
        if k in plan_cagr:
            fig.add_trace(go.Scatter(x=months, y=s0 * (1 + plan_cagr[k]) ** t, name=f"My Plan {k}",
                                     line=dict(color=colr, width=1.5, dash="dash")), 2, 1)
    fig.add_hline(y=x, line_dash="dot", line_color="#ffb300", row=2, col=1, annotation_text=f"${x:,.0f}")
    fig.update_yaxes(type="log", row=1, col=1)
    fig.update_yaxes(type="log", row=2, col=1)
    fig.update_layout(template="plotly_dark", height=720, hovermode="x unified", legend=dict(orientation="h"),
                      margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("🔬 How stable is the Bitcoin link? (rolling 3-year windows)"):
        roll = fit["rolling"]
        if len(roll):
            rf = go.Figure(go.Scatter(x=roll.index, y=roll["beta"], name="beta", line=dict(color="#ffb300")))
            rf.add_trace(go.Scatter(x=roll.index, y=roll["r2"], name="R²", line=dict(color="#29b6f6")))
            rf.update_layout(template="plotly_dark", height=300, margin=dict(l=10, r=10, t=20, b=10))
            st.plotly_chart(rf, use_container_width=True)
        st.caption(f"Fit: quarterly closes {fit['start']} → {fit['end']} ({fit['n_quarters']} quarters, Yahoo Finance). "
                   f"Full-history beta {fit['beta']:.2f} ± {fit['beta_se']:.2f}, R² {fit['r2']:.2f}; rolling 3-yr beta ranged "
                   f"{fit['beta_min']:.2f}–{fit['beta_max']:.2f}. Level fit R² {fit['level_r2']:.2f}; typical stray "
                   f"±{fit['level_sd']:.2f} (log), quarter-to-quarter persistence {fit['rho_q']:.2f}. "
                   "The big drop in the last 3 years coincides with Riot's AI/data-centre pivot and slower dilution.")

    _render_cycle(b_ser if btc_hist is None else btc_hist, block_height, plan_year)
    _render_watchlist(block_height)
    _render_milestones(symbol, s0, b0, b_ser, sc, x, beta, drift, sig, years, block_height)
    with st.expander("📚 Sources (with dates)"):
        for k in bs.SOURCES:
            st.markdown("- " + bs.source_line(k))
        for v in link.AI_SOURCES.values():
            st.markdown(f"- [{v['label']}]({v['url']}) ({v['date']})")
        st.caption(f"Facts last checked {bs.LAST_VERIFIED:%b %d %Y}. Driver numbers are assumptions, not data.")


def _halving(block_height):
    if not block_height:
        return None
    from utils.event_calendar import halving_estimate
    return halving_estimate(block_height)


def _render_cycle(btc, block_height, plan_year):
    st.markdown("#### 4 · Halving-cycle timing")
    explain("halving_cycle")
    cyc = link.halving_cycles(btc)
    h = _halving(block_height)
    if cyc:
        st.dataframe(pd.DataFrame([{
            "Halving": c["halving"], "Cycle peak": c["peak_date"], "Months after halving": f"{c['months']:.1f}",
            "Peak price": _money(c["peak"]),
            "Fall over the next ~15 months": ("N/A" if c["drawdown"] is None else f"{c['drawdown']:.0%}")
            + ("" if c["complete"] else " (so far)")} for c in cyc]), hide_index=True, use_container_width=True)
    if h:
        eta = h["eta"]
        w0, w1 = eta + timedelta(days=365), eta + timedelta(days=548)
        st.markdown(f"Next halving estimated **{eta:%b %Y}** (block {h['halving_height']:,}, from the live block height). "
                    f"If the pattern repeated, a peak window of **{w0:%b %Y} – {w1:%b %Y}** (12–18 months later) — "
                    + (f"which is **before {plan_year}**: in past cycles the year after the peak was a down year. "
                       "Consider starting staged sales inside that window rather than waiting for "
                       f"{plan_year}." if w1.year < plan_year else "inside your plan year."))
    else:
        st.caption("Next-halving date N/A (live block height unavailable).")
    st.caption("Only 3 cycles of data (2012's is before Yahoo's history; its peak came ~12 months after). "
               "Bernstein also expects a 2029 peak; others argue ETFs are lengthening or ending the cycle.")


def _render_watchlist(block_height):
    st.markdown("#### 5 · Policy & macro watchlist")
    from utils.event_calendar import FOMC_MEETINGS, CPI_RELEASES
    today = date.today()
    rows = []
    nf = [m for m in FOMC_MEETINGS if date.fromisoformat(m[1]) >= today][:2]
    for m in nf:
        rows.append((date.fromisoformat(m[1]), "Fed rate decision (FOMC)",
                     "Hikes/real-rate rises are a headwind; cuts a tailwind. Last move: a hike to 3.75–4.00% (Sep 16 2026)."))
    nc = [c for c in CPI_RELEASES if date.fromisoformat(c[1]) >= today][:1]
    for c in nc:
        rows.append((date.fromisoformat(c[1]), f"CPI inflation ({c[0]})", "Sep 2026 was 3.7%. Hot prints → more hikes."))
    rows += [
        (date(2026, 11, 3), "US midterm elections", "Decides who controls Congress for crypto bills in 2027–28."),
        (date(2027, 1, 3), "New Congress convenes (Jan 3 unless moved by law)", "If CLARITY hasn't passed by then, it must be reintroduced and start over "
                                                    "(Senate cloture failed 49–50 on Sep 15 2026)."),
        (None, "Strategic Bitcoin Reserve law (no date)", "House committee advanced a reserve study bill 28–21 (Sep 16 2026). "
                                                          "Funded government BTC buying would be a big bull driver — none exists today."),
    ]
    h = _halving(block_height)
    if h:
        rows.append((h["eta"], "Bitcoin halving (estimate)", "Mining reward halves → miners' BTC revenue per hash halves overnight; "
                                                             "historically followed by a rally 12–18 months later."))
    rows.append((date(2028, 11, 7), "US presidential election", "Sets crypto policy for 2029–2032 — i.e. your exit years."))
    rows.sort(key=lambda r: r[0] or date.max)
    st.dataframe(pd.DataFrame([{"When": (r[0].strftime("%a %b %d %Y") if r[0] else "TBD"),
                                "In": (f"{(r[0]-today).days} days" if r[0] else "—"), "What": r[1],
                                "Why it matters": r[2]} for r in rows]), hide_index=True, use_container_width=True)


def _render_milestones(symbol, s0, b0, b_ser, sc, x, beta, drift, sig, years, block_height):
    st.markdown("#### 6 · Bitcoin milestones to watch as sell / rotate triggers (education, not advice)")
    sma200 = float(b_ser.iloc[-200:].mean()) if len(b_ser) >= 200 else None
    ath = float(b_ser.max())
    need = link.btc_for_stock(x, s0, b0, years, beta, drift, sig)
    h = _halving(block_height)
    today = date.today()
    items = [
        ("BTC above its 200-day average (trend healthy)", None if sma200 is None else b0 > sma200,
         f"BTC {_money(b0)} vs 200-day {_money(sma200)}", "If it breaks below and stays there, don't add; review the plan."),
        (f"BTC reaches the Base path's end level ({_big(sc['Base']['price'])})", b0 >= sc["Base"]["price"],
         f"now {_money(b0)}", f"Arriving early = good time to trim 10–25% of {symbol}."),
        (f"BTC reaches the level that lines up with {symbol} ${x:,.0f} ({_big(need['point']) if need['reachable'] else 'N/A'})",
         (b0 >= need["point"]) if need["reachable"] else None, f"now {_money(b0)}",
         f"Check whether {symbol} actually followed; trim in stages if it did."),
        (f"{symbol} reaches ${x:,.2f}", s0 >= x, f"now {_money(s0, 2)}", "Sell in stages (e.g. thirds) rather than all at once."),
        ("Post-halving peak window opens (halving + 12 months)",
         None if not h else today >= h["eta"] + timedelta(days=365),
         "N/A" if not h else f"from ~{(h['eta'] + timedelta(days=365)):%b %Y}",
         "Historically the best part of the cycle to be selling; start staged exits."),
        ("BTC falls 30%+ from its high after the window opens", None, f"today {b0/ath-1:+.0%} vs its high {_money(ath)}",
         "In past cycles that marked the start of a 50–85% bear market — don't wait for the old high."),
        ("CLARITY Act signed into law", False, "failed Senate cloture 49–50 (Sep 15 2026)", "Bull driver — reduces regulatory risk."),
        ("Congress funds Strategic Bitcoin Reserve purchases", False, "no funded buying today", "Big bull driver if it happens."),
    ]
    icon = {True: "✅", False: "⬜", None: "➖"}
    for name, ok, status, action in items:
        st.markdown(f"{icon[ok]} **{name}** — {status}. *{action}*")
    st.caption("✅ reached · ⬜ not yet · ➖ not applicable yet / no data. These are prompts to re-check the plan, not orders.")
