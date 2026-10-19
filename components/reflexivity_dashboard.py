"""
components/reflexivity_dashboard.py  (v3)

🔄 Reflexivity for bitcoin miners — honest edition.
  * Equal-weight RETURNS basket (not averaged share prices) + a focus-stock view (default: your largest holding).
  * Descriptive phases only; their 2018–2026 track record (point-in-time, non-overlapping) is shown, and
    🧭 My Plan stays the final word.
  * Two loops explained: the stabilising network (difficulty) loop vs the reflexive capital-markets loop.
  * Mining economics from live block height, difficulty and fees, with your machine/power assumptions and
    Riot's reported cost to mine; Riot sum-of-parts value check; dilution tracker; loop strength over time.
Maths: utils/reflexivity.py · network data: utils/network_data.py · filing facts: utils/riot_facts.py.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from utils import network_data as nd
from utils import reflexivity as rx
from utils import signal_hub
from utils.explain import HELP, explain
from utils.market_data import to_stock_calendar
from utils.riot_facts import FACT_SOURCES, Q2_2026, RIOT_CIK
from utils.styles import data_lineage_panel

HORIZONS = {63: "next ~3 months", 126: "next ~6 months"}
BT_START = "2018-01-01"
DEFAULT_J_TH = 20.0
DEFAULT_KWH = 0.05
_INPUT_PARTS = {"Less: remaining build cost", "Bitcoin-mining business", "Other (land/power, other leases)"}


def _pct(x, nd_=1, sign=True):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"{x*100:+.{nd_}f}%" if sign else f"{x*100:.{nd_}f}%"


def _usd(x, nd_=0):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"${x:,.{nd_}f}"


def _m(x):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "N/A"
    return f"${x/1e9:,.2f}B" if abs(x) >= 1e9 else f"${x/1e6:,.0f}M"


def _close(sym: str) -> pd.Series:
    h = signal_hub.get_ohlcv(sym, "max")
    return h["Close"].dropna() if not h.empty else pd.Series(dtype=float)


def _block_height():
    try:
        from components.holding_plan import _block_height_cached
        return _block_height_cached()
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _track_record(symbols: tuple) -> dict:
    """Point-in-time backtest of phases / index buckets for one stock or an equal-weight basket."""
    btc = _close("BTC-USD")
    closes = pd.DataFrame({s: _close(s) for s in symbols})
    if btc.empty or closes.dropna(how="all").empty:
        raise RuntimeError("no data")
    price = closes.iloc[:, 0].dropna() if len(symbols) == 1 else rx.equal_weight_index(closes)
    pf = rx.phase_frame(price, btc)
    pf = pf[pf.index >= BT_START]
    out = {"frame": pf, "tables": {}}
    for h in HORIZONS:
        out["tables"][("phase", h)] = rx.backtest_labels(pf.stock, pf.phase, h)
        out["tables"][("bucket", h)] = rx.backtest_labels(pf.stock, pf.bucket, h)
    out["edge"] = any(rx.has_edge(t) for t in out["tables"].values())
    return out


def live_phase_and_edge(symbol: str):
    """(phase key, label, edge?) for My Plan's context line."""
    tr = _track_record((symbol,))
    pf = tr["frame"]
    ph = pf["phase"].dropna().iloc[-1] if len(pf) else None
    return ph, (rx.PHASES[ph][0] if ph else None), tr["edge"]


class ReflexivityDashboard:
    """Soros-style reflexivity for bitcoin miners — descriptive, backtested, reconciled with My Plan."""

    def render(self, selected_stocks: list, stock_names: dict):
        st.header("🔄 Reflexivity — are miners in a boom or bust loop?")
        st.caption("Describes which feedback loop looks active for bitcoin miners today, what it has meant historically, "
                   "and what Riot's parts are worth. Educational — **not financial advice**; 🧭 My Plan is the final word.")
        explain("reflexivity")

        try:
            from components.personal_portfolio import PersonalPortfolio
            pos = PersonalPortfolio._load_positions()
        except Exception:
            pos = {}
        held = sorted([s for s, p in pos.items() if p.get("shares", 0) > 0 and s in stock_names],
                      key=lambda s: -pos[s]["shares"])
        c1, c2 = st.columns([1, 2])
        opts = list(stock_names.keys())
        focus_default = held[0] if held else ("RIOT" if "RIOT" in opts else opts[0])
        focus = c1.selectbox("Focus stock", opts, index=opts.index(focus_default), key="rfx_focus",
                             help="Defaults to your largest miner holding (from the 🏆 Portfolio tab).")
        basket_default = held or [s for s in selected_stocks if s in stock_names] or ["MARA", "RIOT", "CLSK"]
        basket = c2.multiselect("Miner basket (equal-weight)", opts, default=basket_default, key="rfx_basket",
                                help="Defaults to the miners you hold. Each stock counts equally (daily returns "
                                     "averaged), so a high-priced stock can't dominate.")
        basket = basket or [focus]

        with st.spinner("Loading prices and network data…"):
            btc = _close("BTC-USD")
            closes = pd.DataFrame({s: _close(s) for s in dict.fromkeys([focus] + basket)})
            net = nd.network_history()
            rewards = nd.recent_rewards()
            fees = nd.fees_history()
        if btc.empty or closes.dropna(how="all").empty:
            st.warning("⚠️ No price data from Yahoo Finance right now — Reflexivity is N/A. Try 🔄 Refresh in a minute.")
            return
        data_lineage_panel([
            "<strong>Prices:</strong> Yahoo Finance daily closes via the shared signal hub (same as My Plan), "
            f"last close {closes[focus].dropna().index[-1]:%Y-%m-%d}",
            f"<strong>Network:</strong> {net.get('source', 'unavailable')} hashrate/difficulty, data as of "
            f"<b>{net.get('as_of', 'N/A')}</b>; fees: blockchain.info to "
            f"<b>{fees.index[-1].date() if len(fees) else 'N/A'}</b> + mempool.space last ~1,008 blocks (cached 1 h)",
            "<strong>Company facts:</strong> Riot filings (dated, cited) · <strong>Estimates:</strong> power breakeven, "
            "sum-of-parts — from inputs you can edit"], title="Reflexivity data")

        f_px = closes[focus].dropna()
        b_px = rx.equal_weight_index(closes[basket])
        pf_f = rx.phase_frame(f_px, btc)
        pf_b = rx.phase_frame(b_px, btc)
        if pf_f.empty or pf_b.empty:
            st.warning("⚠️ Fewer than 60 shared trading days with Bitcoin — Reflexivity is N/A for this selection.")
            return
        try:
            tr_f = _track_record((focus,))
        except Exception:
            tr_f = None
        try:
            tr_b = _track_record(tuple(sorted(basket)))
        except Exception:
            tr_b = None
        edge = bool((tr_f and tr_f["edge"]) or (tr_b and tr_b["edge"]))
        ph_now = pf_f["phase"].dropna().iloc[-1] if pf_f["phase"].notna().any() else None
        from components.signal_reconcile import render_reflexivity_banner
        render_reflexivity_banner(focus, rx.PHASES[ph_now][0] if ph_now else None, edge)

        tabs = st.tabs(["🎯 Now", "🔁 How the loops work", "📡 Coupling", "🧪 Track record", "💰 Riot value check",
                        "🧾 Dilution", "⛏️ Hashprice & miner stress", "📈 Loop strength", "🗺️ Phase map"])
        sections = [
            lambda: self._tab_now(focus, basket, pf_f, pf_b, tr_f, tr_b, btc),
            lambda: self._tab_loops(focus, f_px, b_px, btc, net, fees),
            lambda: self._tab_coupling(focus, basket, closes, btc, stock_names, pf_f, pf_b),
            lambda: self._tab_track(focus, basket, tr_f, tr_b, btc, net, fees),
            lambda: self._tab_value(focus, f_px, btc),
            lambda: self._tab_dilution(focus),
            lambda: self._tab_hashprice(btc, net, rewards, fees),
            lambda: self._tab_loop_strength(focus, f_px, btc, net),
            lambda: self._tab_phase_map(focus, pf_f, pf_b),
        ]
        for t, fn in zip(tabs, sections):
            with t:
                try:
                    fn()
                except Exception as e:  # never show a raw traceback to the user
                    st.warning(f"⚠️ This section is unavailable right now ({type(e).__name__}) — N/A.")

    # ── 🎯 Now ───────────────────────────────────────────────────────────
    def _tab_now(self, focus, basket, pf_f, pf_b, tr_f, tr_b, btc):
        cols = st.columns(2)
        for col, name, pf, tr in [(cols[0], focus, pf_f, tr_f), (cols[1], f"Basket ({', '.join(basket)})", pf_b, tr_b)]:
            with col:
                last = pf.dropna(subset=["corr", "beta", "btc_mom", "miner_mom"]).iloc[-1]
                ci = rx.coupling_index(last["corr"], last["beta"], last["btc_mom"], last["miner_mom"])
                ph = rx.detect_phase(last["btc_mom"], last["miner_mom"], last["corr"])
                label, colr = rx.PHASES[ph] if ph else ("N/A", "#888")
                st.markdown(f"**{name}**")
                st.markdown(f'<div style="background:{colr}22;border:1px solid {colr};border-radius:8px;padding:12px 14px">'
                            f'<div style="color:{colr};font-weight:800;font-size:1.1rem">{label}</div>'
                            f'<div style="color:#ccc;font-size:.88rem;margin-top:4px">{rx.PHASE_PLAIN.get(ph, "")}</div></div>',
                            unsafe_allow_html=True)
                st.metric("Bitcoin co-movement index", "N/A" if ci is None else f"{ci['index']:.0f}/100",
                          help=HELP["coupling_index"])
                if ci:
                    st.caption(f"Parts: correlation {last['corr']:.2f} → {ci['coupling']:.0f} · beta {last['beta']:.2f}× → "
                               f"{ci['amplification']:.0f} · same direction → {ci['alignment']:.0f}")
                if tr and ph:
                    t = tr["tables"][("phase", 63)]
                    row = t[t.label == ph]
                    if len(row):
                        r = row.iloc[0]
                        st.caption(f"🧪 After this phase ({tr['frame'].index[0]:%Y}–now, {int(r.n)} separate cases), the "
                                   f"next ~3 months: typical {_pct(r.typical_return, 0)}, up {r.hit_rate:.0%} of the time "
                                   f"vs {_pct(t.attrs['baseline_typical'], 0)} / {t.attrs['baseline_hit']:.0%} for all periods "
                                   f"→ **{r.verdict}**.")
        st.markdown("---")
        last_f = pf_f.dropna(subset=["miner_mom"]).iloc[-1]
        last_b = pf_b.dropna(subset=["miner_mom"]).iloc[-1]
        m = st.columns(4)
        m[0].metric("Bitcoin", _usd(btc.iloc[-1]), f"{_pct(last_f['btc_mom'])} (30 trading days)", delta_color="off",
                    help="Yahoo BTC-USD, aligned to stock trading days.")
        m[1].metric(f"{focus} 30-day", _pct(last_f["miner_mom"]), f"{_pct(last_f['miner_mom'] - last_f['btc_mom'])} vs BTC",
                    delta_color="off")
        m[2].metric("Basket 30-day", _pct(last_b["miner_mom"]), f"{_pct(last_b['miner_mom'] - last_b['btc_mom'])} vs BTC",
                    delta_color="off", help="Equal-weight basket of the miners selected above.")
        m[3].metric(f"{focus} beta / correlation (30d)", f"{last_f['beta']:.2f}× / {last_f['corr']:.2f}",
                    help="Daily moves over the last 30 trading days: beta = how many % the stock moved per 1% in BTC; "
                         "correlation = how closely (1 = lockstep).")
        self._horizon_note(focus, last_f["beta"])

    def _horizon_note(self, focus, beta30):
        try:
            from components.btc_2030 import _load_fit
            fit, _, _ = _load_fit(focus)
        except Exception:
            fit = None
        if not fit:
            st.caption("Long-run sensitivity: N/A.")
            return
        st.info(f"⏱️ **Two different 'betas' — both right.** Here, {focus}'s **day-to-day** beta over the last 30 trading "
                f"days is **{beta30:.2f}×**. In 🧭 My Plan → ₿ Bitcoin to 2030, the **long-run** (quarter-to-quarter) "
                f"sensitivity is **{fit['beta']:.2f}** over {fit['start']:%Y}–now but only **{fit['recent_beta']:.2f}** "
                f"(R² {fit['recent_r2']:.2f}) over the last 3 years. Day to day, {focus} still jumps with Bitcoin; over "
                "quarters and years its own story (AI data-centre leases, dilution) has mattered more. For a 2030 plan the "
                "long-run number is the relevant one.")

    # ── 🔁 Loops ─────────────────────────────────────────────────────────
    def _tab_loops(self, focus, f_px, b_px, btc, net, fees):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**1 · Network loop — stabilising** (pulls margins back)")
            st.graphviz_chart("""digraph{rankdir=LR;node[shape=box,style="rounded,filled",fillcolor="#1e2a38",fontcolor=white,color="#5b7a99",fontsize=11];edge[color="#aaa",fontcolor="#ccc",fontsize=9];
"Bitcoin price ↑"->"Mining pays more"->"More machines\\nplugged in"->"Network difficulty ↑"->"Each machine\\nearns less"->"Margins squeezed\\nback down";
"Margins squeezed\\nback down"->"More machines\\nplugged in"[label="fewer new\\nmachines",style=dashed];}""")
            st.caption("Difficulty resets about every 2 weeks so blocks keep coming every ~10 minutes. "
                       "This loop **dampens** booms — it is not the boom/bust amplifier.")
        with c2:
            st.markdown("**2 · Capital-markets loop — reflexive** (amplifies, both ways)")
            st.graphviz_chart("""digraph{rankdir=LR;node[shape=box,style="rounded,filled",fillcolor="#2a1f12",fontcolor=white,color="#f7931e",fontsize=11];edge[color="#f7931e",fontcolor="#ccc",fontsize=9];
"Share price ↑"->"Sell new shares\\nat high prices"->"Buy machines /\\nBTC / data centres"->"Per-share growth\\n& better story"->"Share price ↑"[label="boom"];
"Share price ↓"->"Shares sold cheaply\\nor BTC sold"->"Value per share ↓"->"Share price ↓"[label="bust",color="#ff4444"];}""")
            st.caption("This is Soros's reflexivity: the price itself changes the fundamentals (how many shares exist, "
                       "how much BTC is owned). Track it in 🧾 Dilution and 📈 Loop strength.")
        st.markdown("---")
        rows = 4 if net else 2
        titles = ["Bitcoin price (USD)", f"Miner share prices — {focus} and basket (indexed to 100)"]
        if net:
            titles += ["Network hashrate (EH/s) — machines plugged in", "Hashprice ($ per PH/s per day) — what mining pays"]
        fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.05, subplot_titles=titles)
        start = btc.index[-1] - pd.Timedelta(days=730)
        b2 = btc[btc.index >= start]
        fig.add_trace(go.Scatter(x=b2.index, y=b2.values, name="BTC", line=dict(color="#f7931e")), 1, 1)
        for s, nm, colr in [(f_px, focus, "#00aaff"), (b_px, "Basket", "#cc88ff")]:
            s2 = s[s.index >= start].dropna()
            if len(s2):
                fig.add_trace(go.Scatter(x=s2.index, y=s2 / s2.iloc[0] * 100, name=nm, line=dict(color=colr)), 2, 1)
        if net:
            hr = net["hashrate_hs"]
            hr = hr[hr.index >= start]
            fig.add_trace(go.Scatter(x=hr.index, y=hr / 1e18, name="Hashrate (EH/s)", line=dict(color="#88ffcc", width=1)), 3, 1)
            hp = rx.hashprice_history(btc, net["hashrate_hs"], fees)
            hp = hp[hp.index >= start]
            fig.add_trace(go.Scatter(x=hp.index, y=hp.rolling(7).mean(), name="Hashprice (7d avg)",
                                     line=dict(color="#ffd600")), 4, 1)
        fig.update_layout(template="plotly_dark", height=200 * rows + 80, hovermode="x unified",
                          legend=dict(orientation="h", y=-0.05), margin=dict(l=0, r=0, t=40, b=30))
        st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Network data as of {net.get('as_of', 'N/A')} ({net.get('source', 'unavailable')}). "
                   "Hashprice uses the block reward in force on each day (halvings included) plus daily fees.")

    # ── 📡 Coupling ──────────────────────────────────────────────────────
    def _tab_coupling(self, focus, basket, closes, btc, stock_names, pf_f, pf_b):
        rows = []
        for sym in dict.fromkeys([focus] + basket):
            pf = rx.phase_frame(closes[sym].dropna(), btc)
            if pf.empty:
                continue
            last = pf.dropna(subset=["beta", "corr"]).iloc[-1]
            bv = last["beta"]
            rows.append({"Symbol": sym, "Name": stock_names.get(sym, sym)[:24], "Beta (30d)": f"{bv:.2f}",
                         "Correlation (30d)": f"{last['corr']:.2f}", "30-day return": _pct(last["miner_mom"]),
                         "vs BTC": _pct(last["miner_mom"] - last["btc_mom"]),
                         "Behaviour (last 30 days)": ("amplifies Bitcoin (>1.5×)" if bv > 1.5 else
                                                      "moves about with Bitcoin" if bv > 0.8 else "moves less than Bitcoin")})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        st.caption("Daily returns, last 30 trading days, Bitcoin aligned to stock trading days. Beta and correlation "
                   "are dated on the last day included.")
        fig = go.Figure()
        for pf, nm, colr in [(pf_f, focus, "#00aaff"), (pf_b, "Basket", "#cc88ff")]:
            s = pf["beta"].dropna().iloc[-504:]
            fig.add_trace(go.Scatter(x=s.index, y=s.values, name=f"{nm} 30d beta", line=dict(color=colr)))
        fig.add_hline(y=1, line_dash="dot", line_color="#fff", annotation_text="moves 1:1 with BTC")
        fig.update_layout(template="plotly_dark", height=340, title="30-day beta to Bitcoin (2 years)",
                          hovermode="x unified", margin=dict(l=0, r=0, t=40, b=0))
        st.plotly_chart(fig, use_container_width=True)
        d = pf_f.dropna(subset=["btc_mom", "miner_mom"]).iloc[-504::21]
        if len(d) >= 6:
            sdf = pd.DataFrame({"BTC 30d %": d.btc_mom * 100, f"{focus} 30d %": d.miner_mom * 100,
                                "date": d.index.strftime("%Y-%m-%d")})
            fig2 = px.scatter(sdf, x="BTC 30d %", y=f"{focus} 30d %", hover_name="date", template="plotly_dark",
                              title=f"BTC vs {focus} — one dot per ~month (2 years, non-overlapping)")
            if sdf["BTC 30d %"].var() > 0:
                k, c = np.polyfit(sdf["BTC 30d %"], sdf[f"{focus} 30d %"], 1)
                xr = np.linspace(sdf["BTC 30d %"].min(), sdf["BTC 30d %"].max(), 50)
                fig2.add_trace(go.Scatter(x=xr, y=k * xr + c, name=f"fit ({k:.1f}×)", mode="lines"))
            fig2.update_layout(height=420)
            st.plotly_chart(fig2, use_container_width=True)

    # ── 🧪 Track record ──────────────────────────────────────────────────
    def _tab_track(self, focus, basket, tr_f, tr_b, btc, net, fees):
        st.markdown("**Did these phases or index levels tell you anything about what came next?** "
                    "Tested point-in-time: each day's phase uses only data up to that day, is acted on at the *next* "
                    "close, and each phase's cases are spaced so their forward windows never overlap.")
        any_edge = False
        for name, tr in [(focus, tr_f), (f"Basket ({', '.join(sorted(basket))})", tr_b)]:
            if not tr:
                st.caption(f"{name}: N/A (not enough history).")
                continue
            st.markdown(f"#### {name} — {tr['frame'].index[0]:%b %Y} to {tr['frame'].index[-1]:%b %Y}")
            for h, hl in HORIZONS.items():
                for kind, title in [("phase", "Phase"), ("bucket", "Co-movement index")]:
                    t = tr["tables"][(kind, h)]
                    if not len(t):
                        continue
                    lab = (lambda k: rx.PHASES[k][0]) if kind == "phase" else (lambda k: k)
                    view = pd.DataFrame({title: [lab(k) for k in t.label], "Separate cases": t.n,
                                         f"Typical {hl}": [_pct(v, 0) for v in t.typical_return],
                                         "Median": [_pct(v, 0) for v in t.median_return],
                                         "Up how often": [f"{v:.0%}" for v in t.hit_rate],
                                         "Verdict": t.verdict})
                    view.loc[len(view)] = [f"(all periods, every {h} days)", t.attrs["baseline_n"],
                                           _pct(t.attrs["baseline_typical"], 0), _pct(t.attrs["baseline_median"], 0),
                                           f"{t.attrs['baseline_hit']:.0%}", "baseline"]
                    st.markdown(f"*{title} → {hl}*")
                    st.dataframe(view, hide_index=True, use_container_width=True)
                    any_edge |= rx.has_edge(t)
        self._stress_backtest(focus, btc, net, fees)
        st.success("**Verdict:** " + (
            "at least one reading shows a statistically noticeable difference — still kept as context only, because "
            "samples are small and it was found by looking at many tables." if any_edge else
            "**no phase, index level or hashprice-stress reading reliably predicted the next 3 or 6 months** "
            "(none beat the all-periods baseline by 2 standard errors). That is why the phases are labelled as "
            "descriptions, why the old wording ('momentum likely to continue', 'buy signal', 'consider hedging') was "
            "removed, and why the regime is **not** fed into 🧭 My Plan's call — it appears there only as context."))
        st.caption(f"Method: 'typical' = average of log returns converted back to %, so one huge spike can't dominate; "
                   f"verdict needs ≥{rx.EDGE_MIN_N} separate cases and |t| ≥ {rx.EDGE_T:g} vs the baseline. "
                   "Only one market history exists (2018–2026, ~2 crypto cycles), so even a 'difference' would be fragile.")

    def _stress_backtest(self, focus, btc, net, fees):
        if not net:
            return
        hp = rx.hashprice_history(btc, net["hashrate_hs"], fees)
        pct = rx.percentile_rank_trailing(hp, 730)
        pct.index = pct.index + pd.Timedelta(days=1)   # day-D network data is complete only after D
        f = _close(focus)
        f = f[f.index >= BT_START]
        on = to_stock_calendar(pct, f.index)
        lab = pd.Series(np.where(on.isna(), None, np.where(on <= 0.2, "hashprice in bottom 20% of 2 yrs",
                                                           "hashprice not low")), f.index)
        t = rx.backtest_labels(f, lab, 126)
        if len(t):
            st.markdown(f"*Miner-stress reading (hashprice percentile) → {focus}, next ~6 months*")
            st.dataframe(pd.DataFrame({"Reading": t.label, "Separate cases": t.n,
                                       "Typical": [_pct(v, 0) for v in t.typical_return],
                                       "Up how often": [f"{v:.0%}" for v in t.hit_rate], "Verdict": t.verdict}),
                         hide_index=True, use_container_width=True)

    # ── 💰 Riot value check ─────────────────────────────────────────────
    def _tab_value(self, focus, f_px, btc):
        explain("sum_of_parts")
        if focus != "RIOT":
            st.info(f"Filing facts are on file for RIOT only — set the focus stock to RIOT. ({focus}: N/A)")
            return
        F = Q2_2026
        bal = signal_hub.get_balance("RIOT")
        shares_s = signal_hub.get_shares("RIOT")
        shares = float(shares_s.iloc[-1]) if len(shares_s) else bal.get("shares")
        price, b0 = float(f_px.iloc[-1]), float(btc.iloc[-1])
        st.caption(f"Facts from [{F['label']}]({F['url']}) (quarter ended {F['period_end']:%b %d %Y}, published "
                   f"{F['published']:%b %d %Y}). Debt from Yahoo's balance sheet ({bal.get('date', 'N/A')}). "
                   "Undisclosed items are inputs — defaults are 0 so nothing is invented.")
        with st.expander("⚙️ Inputs (edit to your own view)", expanded=False):
            a = st.columns(3)
            btc_held = a[0].number_input("Bitcoin held", 0, 100_000, int(F["btc_held"]), 100, key="sop_btc",
                                         help=f"{F['btc_held']:,} at {F['period_end']:%b %d %Y}, of which {F['btc_pledged']:,} "
                                              "pledged as loan collateral (still Riot's, but tied to a loan).")
            cash = a[1].number_input("Cash ($M)", 0.0, 10_000.0, F["cash_usd"] / 1e6, 10.0, key="sop_cash",
                                     help=f"Incl. ${F['cash_restricted_usd']/1e6:.1f}M restricted.") * 1e6
            dflt_debt = (bal.get("total_debt") or 0) / 1e6
            debt = a[2].number_input("Debt ($M)", 0.0, 20_000.0, float(round(dflt_debt, 1)), 10.0, key="sop_debt",
                                     help=f"Yahoo total debt at {bal.get('date', 'N/A')}. 0 if unavailable — check the 10-Q.") * 1e6
            b = st.columns(4)
            noi = b[0].slider("AI lease operating income ($M/yr)", F["lease_191mw_noi_low"] / 1e6,
                              F["lease_191mw_noi_high"] / 1e6, (F["lease_191mw_noi_low"] + F["lease_191mw_noi_high"]) / 2e6,
                              1.0, key="sop_noi", help="Riot's own estimate: $365–411M average per year, 191 MW AI-lab lease.") * 1e6
            yrs_to_full = max(0.0, (F["lease_191mw_full"] - date.today()).days / 365.25)
            start = b[1].number_input("Income starts in (years)", 0.0, 10.0, round(yrs_to_full, 1), 0.1, key="sop_start",
                                      help=f"{F['lease_191mw_first_mw']}; full 191 MW by {F['lease_191mw_full']:%b %Y}.")
            term = b[2].number_input("Lease years", 1, 40, int(F["lease_191mw_term_years"]), 1, key="sop_term",
                                     help="Initial term through June 2048 (two optional 5-year extensions not counted).")
            rate = b[3].number_input("Discount rate %/yr", 0.0, 30.0, 9.0, 0.5, key="sop_rate",
                                     help="Your required return. Assumption — higher = more cautious.") / 100
            c = st.columns(3)
            build = c[0].number_input("Remaining build cost ($M) — NOT disclosed", 0.0, 50_000.0, 0.0, 100.0, key="sop_build",
                                      help=f"Riot hasn't published it. A ${F['interim_facility_usd']/1e6:.0f}M Morgan Stanley "
                                           "interim facility funds the start. Enter your estimate.") * 1e6
            mining = c[1].number_input("Mining business value ($M)", 0.0, 50_000.0, 0.0, 100.0, key="sop_mining",
                                       help="Your estimate. Riot's all-in cost to mine (incl. depreciation) was above the "
                                            "BTC price in Q2 2026.") * 1e6
            other = c[2].number_input("Other: land/power, other leases ($M)", 0.0, 50_000.0, 0.0, 100.0, key="sop_other",
                                      help="e.g. AMD lease (NOI not disclosed) or the Corsicana site (non-binding LOI only).") * 1e6
        r = rx.sum_of_parts(price, shares, b0, btc_held, cash, debt, noi, term, start, rate, build, mining, other,
                            F["btc_pledged"])
        if r is None:
            st.warning("N/A — share count or price unavailable.")
            return
        st.dataframe(pd.DataFrame([{"Part": k, "Value": _m(v) if v else "0 (not entered)" if k in _INPUT_PARTS else _m(v),
                                    "Per share": _usd(v / shares, 2) if v else "—"} for k, v in r["parts"].items()]
                                  + [{"Part": "= Sum of the parts", "Value": _m(r["total"]), "Per share": _usd(r["per_share"], 2)},
                                     {"Part": "Stock-market value (market cap)", "Value": _m(r["market_cap"]),
                                      "Per share": _usd(price, 2)}]), hide_index=True, use_container_width=True)
        k = st.columns(3)
        k[0].metric("Market cap ÷ sum of parts", "N/A" if r["ratio"] is None else f"{r['ratio']:.2f}×",
                    help="Above 1 = the market pays more than these parts add up to (e.g. for future growth or parts you "
                         "left at 0); below 1 = less.")
        k[1].metric("Market cap ÷ bitcoin held ('mNAV')", "N/A" if r["btc_only_mnav"] is None else f"{r['btc_only_mnav']:.1f}×",
                    help="Common treasury-company yardstick. Less meaningful for Riot, which is mostly an operating business.")
        rest = r["market_cap"] - (r["parts"]["Bitcoin held"] + r["parts"]["Cash"] + r["parts"]["Less: debt"])
        k[2].metric("Market's price for everything except BTC & net cash", _m(rest),
                    help="Market cap − (bitcoin + cash − debt). No assumptions: what investors pay for the mining "
                         "business, AI leases and land/power together.")
        st.caption(f"Bitcoin valued at today's {_usd(b0)} (of which {_m(r['pledged_value'])} is pledged collateral). "
                   f"Shares: {shares/1e6:,.1f}M (Yahoo). The lease value is shown **before** the undisclosed build cost "
                   "unless you enter one — that cost could be large.")

    # ── 🧾 Dilution ──────────────────────────────────────────────────────
    def _tab_dilution(self, focus):
        explain("dilution")
        sh = signal_hub.get_shares(focus)
        if len(sh) < 2:
            st.warning(f"Share-count history N/A for {focus} (Yahoo).")
        else:
            g1, g3 = rx.share_growth(sh, 1), rx.share_growth(sh, 3)
            c = st.columns(3)
            c[0].metric("Shares outstanding", f"{sh.iloc[-1]/1e6:,.1f}M", help=f"Yahoo, latest {sh.index[-1]:%Y-%m-%d}.")
            c[1].metric("Growth, last 12 months", _pct(g1), help="Your slice of the company shrinks by about this much a year.")
            c[2].metric("Growth, last 3 years (per yr)", _pct(g3))
            yr = sh.resample("YE").last()
            fig = go.Figure(go.Scatter(x=sh.index, y=sh / 1e6, line=dict(color="#f7931e"), name="Shares (M)"))
            fig.update_layout(template="plotly_dark", height=300, yaxis_title="Shares (millions)",
                              margin=dict(l=0, r=0, t=20, b=0))
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(pd.DataFrame({"Year": yr.index.year, "Shares (M)": (yr / 1e6).round(1),
                                       "Growth": [_pct(v) for v in yr.pct_change(fill_method=None)]}),
                         hide_index=True, use_container_width=True)
        self._converts_map(focus, sh)
        st.markdown("**Recent SEC filings that can come with share sales**")
        if focus != "RIOT":
            st.caption("SEC check set up for RIOT only (N/A).")
            return
        from utils import edgar
        r = edgar.offering_filings(RIOT_CIK)
        browse = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={RIOT_CIK}&type=424&owner=include&count=40"
        if not r["available"]:
            st.caption(f"Couldn't check automatically — {r['reason']}. [Open Riot's filings on SEC EDGAR]({browse}).")
            return
        if not r["filings"]:
            st.caption(f"No 424B/S-3/S-8 filings among the most recent filings. [EDGAR]({browse})")
            return
        st.dataframe(pd.DataFrame([{"Filed": f["date"], "Form": f["form"], "What it usually means": f["what"],
                                    "Link": f["url"]} for f in r["filings"]]),
                     hide_index=True, use_container_width=True,
                     column_config={"Link": st.column_config.LinkColumn("Link")})

    def _converts_map(self, focus, sh):
        """Convertible notes / warrants / ATM → potential new shares (cited facts; same numbers as the Verdict)."""
        from utils.deep_facts import CONVERTS
        from utils import deep_evidence as de
        st.markdown("**Potential new shares: convertible notes, warrants, share-sale programme**")
        f = CONVERTS.get(focus)
        if not f:
            st.caption(f"No cited convertible/warrant facts on file for {focus} (N/A).")
            return
        px = _close(focus)
        price = float(px.iloc[-1]) if len(px) else None
        d = de.convert_dilution(f, price)
        rows = [{"Instrument": n["name"], "Principal": _m(n["principal"]), "Conversion price": _usd(n["conversion_price"], 2),
                 "Price ÷ conversion": "N/A" if n["moneyness"] is None else f"{n['moneyness']:.2f}",
                 "New shares if converted": f"{n['shares']/1e6:,.1f}M", "vs shares today": f"{n['pct']:.1%}",
                 "Maturity": f"{n['maturity']:%b %d %Y}"} for n in d["notes"]]
        rows += [{"Instrument": o["name"], "Principal": "—", "Conversion price": "—", "Price ÷ conversion": "—",
                  "New shares if converted": f"{o['shares']/1e6:,.2f}M", "vs shares today": f"{o['shares']/d['shares_outstanding']:.1%}",
                  "Maturity": "—"} for o in f.get("other", [])]
        if f.get("atm_capacity_usd"):
            rows.append({"Instrument": f"At-the-market share programme (unused, {f['atm_as_of']:%b %Y})",
                         "Principal": _m(f["atm_capacity_usd"]), "Conversion price": "market", "Price ÷ conversion": "—",
                         "New shares if converted": "N/A" if d["atm_shares"] is None else f"≈{d['atm_shares']/1e6:,.1f}M at today's price",
                         "vs shares today": "N/A" if d["atm_pct"] is None else f"{d['atm_pct']:.1%}", "Maturity": "—"})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        n = f["notes"][0] if f.get("notes") else {}
        st.caption(f"Shares outstanding {d['shares_outstanding']/1e6:,.1f}M ({f['shares_as_of']:%b %d %Y}). "
                   + n.get("status_note", "") + " " + n.get("settlement", "").capitalize() + ". Sources: "
                   + " · ".join(f"[filing]({u})" for u in n.get("sources", [])))

    # ── ⛏️ Hashprice & miner stress ──────────────────────────────────────
    def _tab_hashprice(self, btc, net, rewards, fees):
        explain("hashprice")
        if not net:
            st.warning("Network data unavailable (mempool.space and blockchain.info) — hashprice and breakeven N/A.")
            return
        height = _block_height() or rewards.get("end_height")
        subsidy = rx.subsidy_at_height(height) if height else None
        fee_blk = rewards.get("fee_btc_per_block")
        reward = (subsidy + fee_blk) if (subsidy and fee_blk is not None) else subsidy
        b0 = float(btc.iloc[-1])
        a = st.columns(2)
        jth = a[0].number_input("Machine efficiency (J/TH)", 5.0, 100.0, DEFAULT_J_TH, 1.0, key="hp_jth",
                                help="Joules per terahash — lower is more efficient. Assumption: newer fleets ~15–25, older 30+.")
        kwh = a[1].number_input("Power price ($/kWh)", 0.0, 0.30, DEFAULT_KWH, 0.005, format="%.3f", key="hp_kwh",
                                help="All-in electricity price. Assumption — Texas miners with fixed contracts can be lower.")
        diff = net["current_difficulty"]
        be = rx.network_power_breakeven(diff, jth, kwh, reward) if reward else None
        hp = rx.hashprice_usd_per_ph_day(b0, net["current_hashrate_hs"], reward) if reward else None
        hist = rx.hashprice_history(btc, net["hashrate_hs"], fees)
        pctl = float((hist.iloc[-730:] < hp).mean()) if hp and len(hist) > 100 else None
        m = st.columns(4)
        m[0].metric("Hashprice now", "N/A" if hp is None else f"${hp:,.1f}/PH/day",
                    None if pctl is None else f"{pctl:.0%} percentile of 2 yrs", delta_color="off",
                    help="Dollars earned per PH/s per day (new coins + fees).")
        m[1].metric("Block reward", "N/A" if reward is None else f"{reward:.4f} BTC",
                    None if subsidy is None else f"{subsidy:g} new + {fee_blk or 0:.4f} fees", delta_color="off",
                    help=f"New-coin subsidy from the live block height ({height:,}) plus average fees over the last "
                         f"{rewards.get('blocks', 'N/A')} blocks (mempool.space)." if height else "N/A")
        m[2].metric("Power-only breakeven (your machine)", _usd(be),
                    None if be is None else f"BTC is {b0/be:.2f}× this", delta_color="off",
                    help="Electricity cost to mine 1 BTC at today's difficulty with your inputs. Excludes staff, repairs, "
                         "depreciation and interest.")
        F = Q2_2026
        try:
            adj = net["adjustments"]
            q = adj[(adj.date >= "2026-03-15") & (adj.date <= "2026-06-30")]
            d_q2 = float(q.difficulty.mean()) if len(q) else None
        except Exception:
            d_q2 = None
        adj_cost = rx.difficulty_adjusted_cost(F["cost_to_mine_ex_da"], d_q2, diff)
        m[3].metric("Riot cost to mine (Q2 2026)", f"${F['cost_to_mine_ex_da']:,} / ${F['cost_to_mine_incl_da']:,}",
                    "cash / incl. depreciation", delta_color="off",
                    help="Riot's reported cost per BTC mined, Q2 2026 (excl. / incl. miner depreciation).")
        stress = ("🔴 **below** Riot's all-in cost" if b0 < F["cost_to_mine_incl_da"] else "🟢 above Riot's all-in cost")
        st.markdown(f"**Miner stress:** Bitcoin {_usd(b0)} is **{b0/F['cost_to_mine_ex_da']:.2f}×** Riot's Q2 cash cost and "
                    f"**{b0/F['cost_to_mine_incl_da']:.2f}×** its all-in cost — {stress}. "
                    + (f"Adjusted for the difficulty rise since Q2 (×{diff/d_q2:.2f}), the cash cost is roughly "
                       f"**{_usd(adj_cost)}** today (estimate, same fleet & power price)." if adj_cost else ""))
        st.caption(f"Riot's power cost alone (computed from its Q2 table): ${73.499e6/F['btc_mined_q']:,.0f}/BTC gross, "
                   f"${(73.499e6-10.054e6)/F['btc_mined_q']:,.0f}/BTC after power-curtailment credits. "
                   f"Source: [{F['label']}]({F['url']}) ({F['published']:%b %d %Y}).")
        try:
            from utils.event_calendar import halving_estimate
            h = halving_estimate(height) if height else None
        except Exception:
            h = None
        if h and be:
            st.caption(f"⏳ Next halving ~{h['eta']:%b %Y} (block {h['halving_height']:,}): the new-coin reward drops to "
                       f"{h['reward_after']:g} BTC, so at today's difficulty this machine's breakeven would roughly double to "
                       f"{_usd(rx.network_power_breakeven(diff, jth, kwh, h['reward_after'] + (fee_blk or 0)))}.")
        if len(hist):
            h3 = hist.iloc[-1095:]
            fig = go.Figure(go.Scatter(x=h3.index, y=h3.rolling(7).mean(), line=dict(color="#ffd600"), name="Hashprice 7d"))
            fig.update_layout(template="plotly_dark", height=300, yaxis_title="$ per PH/s per day",
                              title="Hashprice, 3 years (falls at halvings and as machines join)", margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)
        st.caption(f"Network data as of {net['as_of']} ({net['source']}); fees as of "
                   f"{fees.index[-1].date() if len(fees) else 'N/A'}.")

    # ── 📈 Loop strength ─────────────────────────────────────────────────
    def _tab_loop_strength(self, focus, f_px, btc, net):
        st.markdown("How strongly each loop has worked over time (rolling correlations; small samples — read the "
                    "direction, not the decimals).")
        sh = signal_hub.get_shares(focus)
        c = st.columns(2)
        with c[0]:
            st.markdown(f"**Capital-markets loop:** did {focus}'s price rising in a quarter come with more new shares the "
                        "next quarter?")
            if len(sh) > 8:
                q = rx.quarterly_issuance_link(f_px, sh)
                fig = go.Figure(go.Bar(x=q.index, y=q.issue_next * 100, name="New shares next quarter (%)",
                                       marker_color="#f7931e"))
                fig.add_trace(go.Scatter(x=q.index, y=q.rolling_corr, name="Rolling 2-yr correlation", yaxis="y2",
                                         line=dict(color="#00aaff")))
                fig.update_layout(template="plotly_dark", height=320, margin=dict(l=0, r=0, t=20, b=0),
                                  yaxis=dict(title="% new shares"), yaxis2=dict(overlaying="y", side="right", range=[-1, 1]),
                                  legend=dict(orientation="h"))
                st.plotly_chart(fig, use_container_width=True)
                lc = q.rolling_corr.dropna()
                st.caption(f"Latest rolling correlation: {'N/A' if lc.empty else f'{lc.iloc[-1]:+.2f}'} "
                           f"({len(q)} quarters since {q.index[0]:%Y}). Positive = the reflexive loop was active "
                           "(shares sold into strength).")
            else:
                st.caption("N/A — share history too short.")
        with c[1]:
            st.markdown("**Network loop:** did a Bitcoin rally over 3 months bring more machines (hashrate) over the next 3?")
            if net:
                r = rx.hashrate_response(btc, net["hashrate_hs"])
                r = r[r.index >= "2018-01-01"]
                fig = go.Figure(go.Scatter(x=r.index, y=r.rolling_corr, line=dict(color="#88ffcc"), name="Rolling 2-yr corr"))
                fig.add_hline(y=0, line_color="#666")
                fig.update_layout(template="plotly_dark", height=320, yaxis=dict(range=[-1, 1]),
                                  margin=dict(l=0, r=0, t=20, b=0))
                st.plotly_chart(fig, use_container_width=True)
                lc = r.rolling_corr.dropna()
                st.caption(f"Latest: {'N/A' if lc.empty else f'{lc.iloc[-1]:+.2f}'} (monthly samples, overlapping 3-month windows).")
            else:
                st.caption("N/A — network data unavailable.")
        try:
            from components.btc_2030 import _load_fit
            fit, _, _ = _load_fit(focus)
        except Exception:
            fit = None
        if fit and len(fit["rolling"]):
            st.markdown(f"**Bitcoin → {focus} link (quarterly, rolling 3 years)** — same numbers as ₿ Bitcoin to 2030")
            ro = fit["rolling"]
            fig = go.Figure(go.Scatter(x=ro.index, y=ro.beta, name="beta", line=dict(color="#ffb300")))
            fig.add_trace(go.Scatter(x=ro.index, y=ro.r2, name="R²", line=dict(color="#29b6f6")))
            fig.update_layout(template="plotly_dark", height=280, margin=dict(l=0, r=0, t=20, b=0), legend=dict(orientation="h"))
            st.plotly_chart(fig, use_container_width=True)

    # ── 🗺️ Phase map ─────────────────────────────────────────────────────
    def _tab_phase_map(self, focus, pf_f, pf_b):
        which = st.radio("Show", [focus, "Basket"], horizontal=True, key="rfx_map_which")
        pf = (pf_f if which == focus else pf_b).dropna(subset=["btc_mom", "miner_mom"])
        df = pf.iloc[-252:]
        if len(df) < 10:
            st.warning("Not enough history for the phase map (needs at least 10 days with 30-day moves).")
            return
        x, y = df.btc_mom * 100, df.miner_mom * 100
        fig = go.Figure()
        lim = max(40, float(np.nanmax(np.abs(np.r_[x, y]))) * 1.1)
        xr = np.array([-lim, lim])
        fig.add_trace(go.Scatter(x=xr, y=xr - 15, mode="lines", line=dict(color="#f7931e", dash="dot"),
                                 name="lagging BTC by 15 pts"))
        fig.add_trace(go.Scatter(x=xr, y=xr + 15, mode="lines", line=dict(color="#66ddaa", dash="dot"),
                                 name="leading BTC by 15 pts"))
        fig.add_trace(go.Scatter(x=x, y=y, mode="markers", marker=dict(size=5, color=list(range(len(df))), colorscale="Blues",
                                 opacity=.5), text=df.index.strftime("%Y-%m-%d"), name="last year",
                                 hovertemplate="<b>%{text}</b><br>BTC %{x:.1f}%<br>Miners %{y:.1f}%<extra></extra>"))
        fig.add_trace(go.Scatter(x=x.iloc[-30:], y=y.iloc[-30:], mode="lines+markers", line=dict(color="#f7931e"),
                                 name="last 30 days"))
        fig.add_trace(go.Scatter(x=[x.iloc[-1]], y=[y.iloc[-1]], mode="markers+text", text=["NOW"], textposition="top center",
                                 marker=dict(size=16, color="#ffcc02", symbol="star"), name="now"))
        for tx, ty, t in [(lim * .6, lim * .8, "both up"), (-lim * .6, -lim * .8, "both down"),
                          (lim * .6, -lim * .8, "BTC up, miners down"), (-lim * .6, lim * .8, "BTC down, miners up")]:
            fig.add_annotation(x=tx, y=ty, text=t, showarrow=False, font=dict(color="rgba(255,255,255,.3)", size=14))
        fig.add_vline(x=0, line_color="rgba(255,255,255,.25)")
        fig.add_hline(y=0, line_color="rgba(255,255,255,.25)")
        fig.update_layout(template="plotly_dark", height=560, xaxis_title="Bitcoin 30-day move (%)",
                          yaxis_title=f"{which} 30-day move (%)", xaxis=dict(range=[-lim, lim]), yaxis=dict(range=[-lim, lim]))
        st.plotly_chart(fig, use_container_width=True)
        st.caption("Each dot is a day (overlapping 30-day windows). Boom/Bust also need correlation ≥ 0.5 and moves > 5%; "
                   "below the orange line = 'miners lagging', above the green line = 'miners leading'. Descriptive only.")
