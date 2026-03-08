"""
components/reflexivity_dashboard.py  (v2 — Replit-hardened)

Soros Reflexivity Analysis for Bitcoin Miners.
Works entirely from yfinance price data — no external APIs required.
Blockchain.info hashrate/difficulty used as enhancement only (fails gracefully).
"""

from utils.styles import data_lineage_panel

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
import requests
from datetime import datetime, timedelta
import traceback


# ─── Constants ────────────────────────────────────────────────────────────────
JOULES_PER_TH     = 30.0     # modern ASIC efficiency
KWH_PRICE         = 0.05     # $/kWh industry average
BTC_PER_BLOCK     = 3.125    # post-2024 halving
BLOCKS_PER_DAY    = 144
SECONDS_PER_DAY   = 86_400


# ─── Data fetchers (each independently fault-tolerant) ───────────────────────

def _fetch_prices(symbols: list, period: str = "1y") -> pd.DataFrame:
    """Fetch BTC + miner closing prices via yfinance. Returns empty df on failure."""
    tickers = ["BTC-USD"] + [s for s in symbols if s != "BTC-USD"]
    out = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period=period, timeout=10)
            if not hist.empty:
                out[t] = hist["Close"].copy()
        except Exception:
            pass
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame(out)
    return df.dropna(how="all")


def _fetch_blockchain_chart(chart: str, timespan: str = "1year") -> pd.DataFrame:
    """
    Optional enhancement: fetch hashrate/difficulty from blockchain.info.
    Returns empty DataFrame if request fails (Replit network restrictions common).
    """
    try:
        url = (f"https://api.blockchain.info/charts/{chart}"
               f"?timespan={timespan}&format=json&cors=true")
        resp = requests.get(url, timeout=8)
        if resp.status_code != 200:
            return pd.DataFrame()
        values = resp.json().get("values", [])
        if not values:
            return pd.DataFrame()
        df = pd.DataFrame(values, columns=["timestamp", "value"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("date", inplace=True)
        df.drop(columns=["timestamp"], inplace=True)
        return df
    except Exception:
        return pd.DataFrame()


# ─── Math helpers ─────────────────────────────────────────────────────────────

def _rolling_beta(stock: pd.Series, bench: pd.Series, window: int = 30) -> pd.Series:
    sr = stock.pct_change().dropna()
    br = bench.pct_change().dropna()
    idx = sr.index.intersection(br.index)
    sr, br = sr.loc[idx], br.loc[idx]
    betas, dates = [], []
    for i in range(window, len(sr)):
        s_w, b_w = sr.iloc[i-window:i], br.iloc[i-window:i]
        var = b_w.var()
        betas.append(np.cov(s_w, b_w)[0,1] / var if var > 1e-10 else np.nan)
        dates.append(sr.index[i])
    return pd.Series(betas, index=dates, name="beta")


def _rolling_corr(a: pd.Series, b: pd.Series, window: int = 30) -> pd.Series:
    ra = a.pct_change()
    rb = b.pct_change()
    idx = ra.index.intersection(rb.index)
    return ra.loc[idx].rolling(window).corr(rb.loc[idx])


def _estimate_breakeven(difficulty_series: pd.Series) -> pd.Series:
    """
    Estimate breakeven BTC price from difficulty.
    breakeven = (D × 2^32 / 600) TH/s × J/TH × kWh_price / (BTC/day × 1e12)
    """
    h_ths      = difficulty_series * (2**32) / 600 / 1e12
    kwh_day    = h_ths * JOULES_PER_TH * SECONDS_PER_DAY / 3_600_000
    btc_day    = BLOCKS_PER_DAY * BTC_PER_BLOCK
    return (kwh_day * KWH_PRICE) / btc_day


def _detect_phase(btc30: float, miner30: float, corr: float, margin: float):
    hi = abs(corr) > 0.6
    if btc30 >  0.05 and miner30 >  0.05 and margin > 0.30 and hi:
        return "🚀 Expansionary",  "#00cc66", \
            "Classic boom: rising prices justify expansion, expansion drives prices higher. Bullish loop active."
    if btc30 >  0    and miner30 >  0.10 and margin < 0.20:
        return "⚠️ Mature Boom",   "#ffaa00", \
            "Miners over-expanding on cheap capital. Margins compressing. Loop is overheating."
    if btc30 >  0.02 and miner30 < -0.05:
        return "🔄 Divergence",    "#f7931e", \
            "BTC rising but miners lagging. Loop may be decoupling — watch for convergence."
    if btc30 < -0.05 and miner30 < -0.05 and hi and margin < 0.10:
        return "💀 Capitulation",  "#ff2222", \
            "Margins near zero. Forced BTC selling drives price lower. Self-reinforcing bust loop."
    if btc30 < -0.05 and miner30 < -0.05 and hi:
        return "📉 Contraction",   "#ff6666", \
            "Bust loop: falling prices cut margins, miners scale back, signals weakness."
    if btc30 > -0.03 and miner30 > 0.05 and margin > 0.15:
        return "🌱 Recovery",      "#66ddaa", \
            "Post-capitulation: weak miners gone, survivors benefit from lower difficulty."
    return "➡️ Neutral",           "#8b8b9b", \
        "No dominant reflexive loop. Market digesting — watch for loop re-engagement."


def _reflexivity_index(corr: float, beta: float, margin: float,
                       btc_mom: float, miner_mom: float) -> dict:
    coupling   = min(abs(corr), 1.0) * 100
    amplif     = min(abs(beta) / 3.0, 1.0) * 100
    alignment  = 100.0 if (btc_mom * miner_mom) > 0 else 0.0
    margin_sc  = min(max(margin, 0), 1.0) * 100
    score      = 0.30*coupling + 0.30*amplif + 0.20*alignment + 0.20*margin_sc
    return dict(index=round(score,1), coupling=round(coupling,1),
                amplification=round(amplif,1), alignment=round(alignment,1),
                margin_score=round(margin_sc,1))


# ─── Main component ───────────────────────────────────────────────────────────

class ReflexivityDashboard:
    """Soros Reflexivity Analysis — Bitcoin Miners Edition"""

    def render(self, selected_stocks: list, stock_names: dict):
        st.header("🔄 Reflexivity Analysis")
        data_lineage_panel(["<strong>Direct:</strong> BTC + miner prices from Yahoo Finance", "<strong>Optional direct:</strong> blockchain.info hashrate/difficulty if reachable", "<strong>Estimated:</strong> miner breakeven, margin, and reflexivity composite index", "<strong>Fallback:</strong> when network data fails, charts still run on price-only mode"], title="Reflexivity Data Quality")
        st.markdown(
            "> *\"Markets are always biased in one direction or another. "
            "The trend is your friend until the reflexive process reverses.\"*  \n"
            "> — George Soros"
        )

        # ── Step 1: Fetch price data (required) ──────────────────────────────
        with st.spinner("📡 Fetching BTC + miner prices from Yahoo Finance…"):
            prices_df = _fetch_prices(selected_stocks, period="1y")

        if prices_df.empty:
            st.error("❌ Could not fetch any price data from Yahoo Finance.")
            st.info("Yahoo Finance may be rate-limiting. Wait 30 seconds and refresh.")
            return

        if "BTC-USD" not in prices_df.columns:
            st.error("❌ BTC-USD price data unavailable.")
            st.info("Try refreshing — Yahoo Finance occasionally drops BTC data.")
            return

        miner_cols = [c for c in prices_df.columns if c != "BTC-USD"]
        if not miner_cols:
            st.error("❌ No miner price data loaded. Check selected stocks.")
            return

        st.success(
            f"✅ Loaded {len(prices_df)} days of price data for "
            f"BTC + {len(miner_cols)} miners: {', '.join(miner_cols)}"
        )

        # ── Step 2: Optional hashrate/difficulty from blockchain.info ────────
        with st.spinner("📡 Fetching network data (optional — fallback if unavailable)…"):
            hashrate_df = _fetch_blockchain_chart("hash-rate",  "1year")
            diff_df     = _fetch_blockchain_chart("difficulty", "1year")

        if hashrate_df.empty:
            st.caption("⚠️ Hashrate data unavailable (blockchain.info blocked on this host). "
                       "Using miner stocks as hashrate proxy.")
        if diff_df.empty:
            st.caption("⚠️ Difficulty data unavailable. "
                       "Using fixed-cost breakeven estimate ($30K).")

        # ── Step 3: Core calculations ─────────────────────────────────────────
        btc          = prices_df["BTC-USD"].dropna()
        miners_df    = prices_df[miner_cols].dropna(how="all")
        miners_avg   = miners_df.mean(axis=1)

        corr_series  = _rolling_corr(miners_avg, btc, window=30)
        beta_series  = _rolling_beta(miners_avg, btc, window=30)

        corr_val     = float(corr_series.dropna().iloc[-1]) if not corr_series.dropna().empty else 0.0
        beta_val     = float(beta_series.iloc[-1])          if not beta_series.empty         else 1.0
        btc_mom30    = float(btc.pct_change(30).iloc[-1])   if len(btc) > 30                 else 0.0
        miner_mom30  = float(miners_avg.pct_change(30).iloc[-1]) if len(miners_avg) > 30     else 0.0

        # Margin estimate
        if not diff_df.empty:
            try:
                diff_r   = diff_df["value"].resample("D").last().ffill()
                beven_s  = _estimate_breakeven(diff_r)
                btc_al   = btc.reindex(beven_s.index, method="ffill")
                margin_s = ((btc_al - beven_s) / btc_al).clip(-1, 1)
                cur_margin = float(margin_s.dropna().iloc[-1])
                cur_beven  = float(beven_s.iloc[-1])
            except Exception:
                cur_margin = max(0.0, (btc.iloc[-1] - 30_000) / btc.iloc[-1])
                cur_beven  = 30_000.0
                margin_s   = None
        else:
            cur_margin = max(0.0, (btc.iloc[-1] - 30_000) / btc.iloc[-1])
            cur_beven  = 30_000.0
            margin_s   = None

        ri = _reflexivity_index(corr_val, beta_val, cur_margin, btc_mom30, miner_mom30)
        phase, phase_color, phase_desc = _detect_phase(
            btc_mom30, miner_mom30, corr_val, cur_margin)

        # ── Tabs ──────────────────────────────────────────────────────────────
        t1, t2, t3, t4, t5 = st.tabs([
            "🎯 Reflexivity Index",
            "🔁 Loop Analysis",
            "📡 Miner–BTC Coupling",
            "🗺️ Phase Map",
            "💡 Signals",
        ])

        with t1:
            self._tab_index(ri, phase, phase_color, phase_desc,
                            btc, btc_mom30, miner_mom30,
                            cur_margin, cur_beven, beta_val, corr_val)
        with t2:
            self._tab_loop(btc, miners_avg, hashrate_df, margin_s, corr_series)
        with t3:
            self._tab_coupling(prices_df, miner_cols, stock_names, beta_series, corr_series)
        with t4:
            self._tab_phase_map(btc, miners_avg, corr_series)
        with t5:
            self._tab_signals(ri, phase, phase_color, btc, miners_avg,
                              beta_series, hashrate_df, cur_margin)

    # ────────────────────────────────────────────────────────────────────────
    # Tab 1 — Reflexivity Index
    # ────────────────────────────────────────────────────────────────────────

    def _tab_index(self, ri, phase, phase_color, phase_desc,
                   btc, btc_mom, miner_mom, margin, beven, beta, corr):
        try:
            col_g, col_p = st.columns(2)

            with col_g:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=ri["index"],
                    title={"text": "Reflexivity Index (0–100)", "font": {"size": 16}},
                    gauge={
                        "axis":  {"range": [0, 100]},
                        "bar":   {"color": phase_color},
                        "steps": [
                            {"range": [0,  25], "color": "#1a2a1a"},
                            {"range": [25, 50], "color": "#1a2010"},
                            {"range": [50, 75], "color": "#2a1a00"},
                            {"range": [75,100], "color": "#2a0000"},
                        ],
                    },
                ))
                fig.update_layout(template="plotly_dark", height=260,
                                  margin=dict(l=20, r=20, t=50, b=10))
                st.plotly_chart(fig, use_container_width=True)
                st.caption("0–25 Weak · 25–50 Forming · 50–75 Active · 75–100 Dominant")

            with col_p:
                st.markdown("### Current Phase")
                st.markdown(
                    f'<div style="background:{phase_color}22;border:1px solid {phase_color};'
                    f'border-radius:8px;padding:16px;margin:8px 0">'
                    f'<h3 style="color:{phase_color};margin:0">{phase}</h3>'
                    f'<p style="color:#ccc;margin-top:8px;font-size:.9rem">{phase_desc}</p>'
                    f'</div>', unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("📊 Index Components")
            c1, c2, c3, c4 = st.columns(4)
            for col, label, val, tip in [
                (c1, "🔗 Coupling",       ri["coupling"],      f"30d correlation with BTC: {corr:.2f}"),
                (c2, "📡 Amplification",  ri["amplification"], f"30d beta vs BTC: {beta:.2f}×"),
                (c3, "🎯 Alignment",      ri["alignment"],     "Same direction = loop active"),
                (c4, "💰 Margin Health",  ri["margin_score"],  f"Est. miner margin: {margin*100:.1f}%"),
            ]:
                with col:
                    st.metric(label, f"{val:.0f}/100", help=tip)
                    bar_color = ("#00cc66" if val > 60 else "#ffaa00" if val > 30 else "#ff4444")
                    st.markdown(
                        f'<div style="height:5px;background:{bar_color};'
                        f'border-radius:3px;width:{val}%"></div>',
                        unsafe_allow_html=True)

            st.markdown("---")
            st.subheader("📈 Market State")
            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("BTC Price",      f"${btc.iloc[-1]:,.0f}",  f"{btc_mom*100:+.1f}% (30d)")
            m2.metric("Miner vs BTC",   f"{(miner_mom-btc_mom)*100:+.1f}%", "spread")
            m3.metric("Miner Beta",     f"{beta:.2f}×")
            m4.metric("Coupling",       f"{corr:.2f}")
            m5.metric("Breakeven BTC",  f"${beven:,.0f}", f"{margin*100:.1f}% margin")

        except Exception as e:
            st.error(f"Index tab error: {e}")
            st.code(traceback.format_exc())

    # ────────────────────────────────────────────────────────────────────────
    # Tab 2 — Loop Analysis
    # ────────────────────────────────────────────────────────────────────────

    def _tab_loop(self, btc, miners_avg, hashrate_df, margin_s, corr_series):
        try:
            st.subheader("🔁 The Feedback Loop")
            st.caption("BTC price → miner margins → expansion → hashrate → difficulty → margins")

            rows   = 3 if (margin_s is None or margin_s.dropna().empty) else 4
            titles = ["BTC Price (USD)",
                      "Miner Stocks — Expansion Proxy (indexed to 100)"]
            if rows == 4:
                titles.append("Estimated Miner Margin (%)")
            titles.append("30d Reflexivity Coupling (rolling correlation)")

            row_h = [0.35, 0.25, 0.20] if rows == 3 else [0.30, 0.22, 0.22, 0.16]
            fig = make_subplots(rows=rows, cols=1, shared_xaxes=True,
                                vertical_spacing=0.04,
                                subplot_titles=titles,
                                row_heights=row_h)

            # Row 1 — BTC
            fig.add_trace(go.Scatter(
                x=btc.index, y=btc.values,
                name="BTC", line=dict(color="#f7931e", width=2),
                fill="tozeroy", fillcolor="rgba(247,147,30,.07)"
            ), row=1, col=1)

            # Row 2 — Miner stocks (indexed to 100)
            miners_idx = miners_avg / miners_avg.iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=miners_idx.index, y=miners_idx.values,
                name="Miners (indexed)", line=dict(color="#00aaff", width=2),
                fill="tozeroy", fillcolor="rgba(0,170,255,.07)"
            ), row=2, col=1)

            # Optional: real hashrate overlay
            if not hashrate_df.empty:
                hr_norm = hashrate_df["value"] / hashrate_df["value"].iloc[0] * 100
                fig.add_trace(go.Scatter(
                    x=hr_norm.index, y=hr_norm.values,
                    name="Hashrate (indexed)", line=dict(color="#88ffcc", width=1.5, dash="dot")
                ), row=2, col=1)
                hr_30 = hashrate_df["value"].rolling(30).mean()
                hr_60 = hashrate_df["value"].rolling(60).mean()
                hr_30n = hr_30 / hashrate_df["value"].iloc[0] * 100
                hr_60n = hr_60 / hashrate_df["value"].iloc[0] * 100
                fig.add_trace(go.Scatter(x=hr_30n.index, y=hr_30n.values,
                    name="HR 30d MA", line=dict(color="#44ffaa", width=1, dash="dash")), row=2, col=1)
                fig.add_trace(go.Scatter(x=hr_60n.index, y=hr_60n.values,
                    name="HR 60d MA", line=dict(color="#ffffff", width=1, dash="dot")), row=2, col=1)

            # Optional: margin
            cur_row = 3
            if margin_s is not None and not margin_s.dropna().empty:
                mp = margin_s.dropna() * 100
                bar_colors = ["#00cc66" if v > 30 else "#ffaa00" if v > 10 else "#ff4444"
                              for v in mp.values]
                fig.add_trace(go.Bar(
                    x=mp.index, y=mp.values,
                    name="Margin %", marker_color=bar_colors, opacity=0.7
                ), row=3, col=1)
                fig.add_hline(y=0, line_color="white", line_dash="dash",
                              annotation_text="Breakeven", row=3, col=1)
                cur_row = 4

            # Coupling
            cc = corr_series.dropna()
            if not cc.empty:
                fig.add_trace(go.Scatter(
                    x=cc.index, y=cc.values,
                    name="Coupling", line=dict(color="#cc88ff", width=2),
                    fill="tozeroy", fillcolor="rgba(200,136,255,.10)"
                ), row=cur_row, col=1)
                for lvl, col, lbl in [(0.7,"#00cc66","Strong"),(-0.7,"#ff4444","Strong bear")]:
                    fig.add_hline(y=lvl, line_color=col, line_dash="dot",
                                  annotation_text=lbl, row=cur_row, col=1)

            fig.update_layout(template="plotly_dark", height=680,
                              hovermode="x unified", showlegend=True,
                              legend=dict(orientation="h", y=-0.05),
                              margin=dict(l=0, r=0, t=50, b=40))
            st.plotly_chart(fig, use_container_width=True)

            st.info(
                "🔶 **BTC + Miners rising together** = expansionary loop  \n"
                "🟢 **Green margin bars** = healthy expansion capacity  \n"
                "🔴 **Red margin + flat/falling miners** = bust / capitulation  \n"
                "🟣 **Coupling near ±1** = prices and fundamentals locked in sync"
            )
        except Exception as e:
            st.error(f"Loop tab error: {e}")
            st.code(traceback.format_exc())

    # ────────────────────────────────────────────────────────────────────────
    # Tab 3 — Miner–BTC Coupling
    # ────────────────────────────────────────────────────────────────────────

    def _tab_coupling(self, prices_df, miner_cols, stock_names, beta_series, corr_series):
        try:
            st.subheader("📡 Miner–BTC Coupling")
            st.markdown("**Amplification factor** = how much miners lever up each BTC move.")
            btc = prices_df["BTC-USD"]

            # Per-stock table
            rows = []
            for sym in miner_cols:
                if sym not in prices_df.columns:
                    continue
                try:
                    b_s = _rolling_beta(prices_df[sym], btc, window=30)
                    c_s = _rolling_corr(prices_df[sym], btc, window=30).dropna()
                    r30 = prices_df[sym].pct_change(30).iloc[-1]
                    b30 = btc.pct_change(30).iloc[-1]
                    bv  = float(b_s.iloc[-1]) if not b_s.empty else np.nan
                    cv  = float(c_s.iloc[-1]) if not c_s.empty else np.nan
                    rows.append({
                        "Symbol":       sym,
                        "Name":         stock_names.get(sym, sym)[:22],
                        "Beta (30d)":   f"{bv:.2f}" if not np.isnan(bv) else "N/A",
                        "Correlation":  f"{cv:.2f}" if not np.isnan(cv) else "N/A",
                        "30d Return":   f"{r30*100:+.1f}%",
                        "vs BTC":       f"{(r30-b30)*100:+.1f}%",
                        "Role": ("🔥 High Amplifier"  if not np.isnan(bv) and bv > 2.5 else
                                 "📡 Amplifier"        if not np.isnan(bv) and bv > 1.5 else
                                 "⚖️ Proportional"     if not np.isnan(bv) and bv > 0.8 else
                                 "🛡️ Damper"),
                    })
                except Exception:
                    continue

            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.markdown("---")

            # Rolling beta chart
            if not beta_series.empty:
                st.subheader("📈 Portfolio Amplification Factor — 30d Rolling Beta")
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=beta_series.index, y=beta_series.values,
                    name="Beta", line=dict(color="#f7931e", width=2),
                    fill="tozeroy", fillcolor="rgba(247,147,30,.10)"
                ))
                for lvl, col, lbl in [
                    (3.0,"#ff2222","3× Extreme"),
                    (2.0,"#ff8800","2× High"),
                    (1.5,"#ffcc00","1.5× Moderate"),
                    (1.0,"#ffffff","1× Neutral"),
                ]:
                    fig.add_hline(y=lvl, line_dash="dot", line_color=col,
                                  annotation_text=lbl, annotation_position="right")
                fig.update_layout(template="plotly_dark", height=380,
                                  xaxis_title="Date", yaxis_title="Beta",
                                  hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

            # Scatter: BTC vs miner 30d returns
            st.subheader("🎯 Amplification Scatter")
            sdata = []
            for sym in miner_cols:
                if sym not in prices_df.columns:
                    continue
                try:
                    rb = btc.pct_change(30).dropna() * 100
                    rm = prices_df[sym].pct_change(30).dropna() * 100
                    idx = rb.index.intersection(rm.index)[-120:]
                    for d in idx:
                        sdata.append({"btc": float(rb.loc[d]),
                                      "miner": float(rm.loc[d]),
                                      "symbol": sym})
                except Exception:
                    continue

            if sdata:
                sdf = pd.DataFrame(sdata)
                fig = px.scatter(sdf, x="btc", y="miner", color="symbol",
                                 trendline="ols", template="plotly_dark",
                                 title="BTC 30d Return vs Miner 30d Return",
                                 labels={"btc": "BTC 30d Return (%)",
                                         "miner": "Miner 30d Return (%)"})
                x_r = np.linspace(sdf["btc"].min(), sdf["btc"].max(), 100)
                for mult, col, nm in [(1,"white","1×"),(2,"#ffaa00","2×"),(3,"#ff4444","3×")]:
                    fig.add_trace(go.Scatter(x=x_r, y=x_r*mult, mode="lines",
                                             name=nm, line=dict(color=col, dash="dot", width=1)))
                fig.update_layout(height=480)
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Steeper slope = higher beta = stronger reflexive amplification.")
        except Exception as e:
            st.error(f"Coupling tab error: {e}")
            st.code(traceback.format_exc())

    # ────────────────────────────────────────────────────────────────────────
    # Tab 4 — Phase Map
    # ────────────────────────────────────────────────────────────────────────

    def _tab_phase_map(self, btc, miners_avg, corr_series):
        try:
            st.subheader("🗺️ Reflexivity Phase Map")
            st.caption("Each dot = one 30-day window. ⭐ = now. Arrow shows recent trajectory.")

            bm   = btc.pct_change(30).dropna() * 100
            mm   = miners_avg.pct_change(30).dropna() * 100
            cc   = corr_series.dropna().abs()
            idx  = bm.index.intersection(mm.index).intersection(cc.index)

            if len(idx) < 10:
                st.warning("Not enough history for phase map (need >40 data points).")
                return

            df = pd.DataFrame({
                "btc":  bm.loc[idx],
                "min":  mm.loc[idx],
                "corr": cc.loc[idx],
                "date": idx,
                "age":  range(len(idx)),
            }).dropna().tail(252)

            recent = df.tail(30)

            fig = go.Figure()

            # Quadrant shading
            for x0,x1,y0,y1,clr,lbl in [
                ( 0, 120,  0, 400, "rgba(0,200,100,.05)",    "Boom"),
                (-120, 0, -400, 0, "rgba(255,50,50,.05)",    "Bust"),
                ( 0, 120, -400, 0, "rgba(255,170,0,.05)",    "Diverge"),
                (-120, 0,  0, 400, "rgba(100,200,255,.05)",  "Recovery"),
            ]:
                fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                              fillcolor=clr, line=dict(width=0))
                fig.add_annotation(x=(x0+x1)/2, y=(y0+y1)/2, text=lbl,
                                   showarrow=False,
                                   font=dict(size=16, color="rgba(255,255,255,.12)"))

            # Historical dots
            fig.add_trace(go.Scatter(
                x=df["btc"], y=df["min"], mode="markers",
                marker=dict(size=5, color=df["age"], colorscale="Blues", opacity=.4),
                text=pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d"),
                hovertemplate="<b>%{text}</b><br>BTC: %{x:.1f}%<br>Miners: %{y:.1f}%<extra></extra>",
                name="History"
            ))

            # Recent trajectory
            fig.add_trace(go.Scatter(
                x=recent["btc"], y=recent["min"], mode="lines+markers",
                line=dict(color="#f7931e", width=2.5),
                marker=dict(size=7, color="#f7931e"),
                text=pd.to_datetime(recent["date"]).dt.strftime("%Y-%m-%d"),
                hovertemplate="<b>%{text}</b><br>BTC: %{x:.1f}%<br>Miners: %{y:.1f}%<extra></extra>",
                name="Last 30 days"
            ))

            # Current star
            fig.add_trace(go.Scatter(
                x=[float(df["btc"].iloc[-1])], y=[float(df["min"].iloc[-1])],
                mode="markers+text", name="NOW",
                marker=dict(size=18, color="#ffcc02", symbol="star"),
                text=["NOW"], textposition="top center"
            ))

            fig.add_vline(x=0, line_color="rgba(255,255,255,.25)")
            fig.add_hline(y=0, line_color="rgba(255,255,255,.25)")
            fig.update_layout(
                title="Phase Map: BTC Momentum vs Miner Momentum (30d)",
                xaxis_title="BTC 30d Momentum (%)",
                yaxis_title="Miner Portfolio 30d Momentum (%)",
                template="plotly_dark", height=580, hovermode="closest"
            )
            st.plotly_chart(fig, use_container_width=True)

            st.info(
                "↗️ **Top-right = Boom** · ↙️ **Bottom-left = Bust** · "
                "↘️ **Bottom-right = Divergence** · ↖️ **Top-left = Recovery**"
            )
        except Exception as e:
            st.error(f"Phase map error: {e}")
            st.code(traceback.format_exc())

    # ────────────────────────────────────────────────────────────────────────
    # Tab 5 — Signals
    # ────────────────────────────────────────────────────────────────────────

    def _tab_signals(self, ri, phase, phase_color, btc, miners_avg,
                     beta_series, hashrate_df, margin):
        try:
            st.subheader("💡 Reflexivity Signals")
            signals = []

            btc_mom = btc.pct_change(30).iloc[-1]
            min_mom = miners_avg.pct_change(30).iloc[-1]
            beta    = float(beta_series.iloc[-1]) if not beta_series.empty else 1.0

            # 1 — Loop direction
            if btc_mom > .10 and min_mom > .15 and ri["coupling"] > 60:
                signals.append(("#00cc66", "🚀 BULLISH",  "Strong Boom Loop Active",
                    f"BTC +{btc_mom*100:.1f}% · Miners +{min_mom*100:.1f}% · Coupling {ri['coupling']:.0f}/100. "
                    "Self-reinforcing bull loop. Momentum likely to continue until margins compress."))
            elif btc_mom < -.10 and min_mom < -.15 and ri["coupling"] > 60:
                signals.append(("#ff4444", "📉 BEARISH", "Strong Bust Loop Active",
                    f"BTC {btc_mom*100:.1f}% · Miners {min_mom*100:.1f}% · Coupling {ri['coupling']:.0f}/100. "
                    "Self-reinforcing bear loop. Expect continued pressure until capitulation clears."))

            # 2 — Amplification extreme
            if beta > 2.5:
                signals.append(("#ff8800", "⚠️ WARNING", f"Extreme Amplification ({beta:.1f}× Beta)",
                    "Miners amplifying BTC moves >2.5×. Soros: extreme amplification = late-stage reflexivity. "
                    "When loop reverses miners fall faster than BTC. Consider hedging."))
            elif beta < 0.8 and abs(btc_mom) > .05:
                signals.append(("#8b8b9b", "ℹ️ NEUTRAL", f"Decoupling ({beta:.1f}× Beta)",
                    "Miners not amplifying BTC. Loop is weak — dormant phase or miner-specific stress."))

            # 3 — Margin
            if margin < .05:
                signals.append(("#ff2222", "🚨 CRITICAL", f"Breakeven Territory ({margin*100:.1f}% margin)",
                    "Forced BTC selling imminent. This is the Soros bust accelerant — "
                    "selling BTC drives price lower → more selling. Watch hash ribbon reversal."))
            elif margin > .60:
                signals.append(("#00cc66", "💰 BULLISH", f"Fat Margins ({margin*100:.1f}%) — Expansion Likely",
                    "Healthy margins → aggressive ASIC purchasing → reflexive loop accelerates."))

            # 4 — Hash ribbon (if data)
            if not hashrate_df.empty and len(hashrate_df) > 65:
                hr = hashrate_df["value"]
                hr30_now  = hr.rolling(30).mean().iloc[-1]
                hr60_now  = hr.rolling(60).mean().iloc[-1]
                hr30_prev = hr.rolling(30).mean().iloc[-5]
                hr60_prev = hr.rolling(60).mean().iloc[-5]
                if hr30_now > hr60_now and hr30_prev <= hr60_prev:
                    signals.append(("#00cc66", "🌱 BULLISH", "Hash Ribbon Buy Signal",
                        "30d hashrate MA just crossed above 60d MA. "
                        "Miner capitulation is over; survivors expanding. "
                        "Reflexive recovery loop beginning — historically strong buy signal."))
                elif hr30_now < hr60_now:
                    signals.append(("#ffaa00", "⚠️ WARNING", "Hash Ribbon: Capitulation Phase",
                        "30d hashrate MA below 60d MA. Miners still capitulating. "
                        "Bust loop may not be over. Wait for ribbon reversal before adding exposure."))

            # 5 — Short-term divergence
            btc5 = btc.pct_change(5).iloc[-1]
            min5 = miners_avg.pct_change(5).iloc[-1]
            if btc5 > .03 and min5 < -.02:
                signals.append(("#f7931e", "🔄 WARNING", "Short-term Divergence: BTC Up, Miners Down",
                    f"BTC +{btc5*100:.1f}% in 5d while miners {min5*100:.1f}%. "
                    "Loop losing steam or miners pricing in difficulty adjustment."))

            if not signals:
                st.success("✅ No extreme reflexivity signals. Market in balanced state.")
            else:
                for color, level, title, detail in signals:
                    st.markdown(
                        f'<div style="background:{color}18;border-left:4px solid {color};'
                        f'border-radius:6px;padding:14px 18px;margin:8px 0">'
                        f'<strong style="color:{color}">{level} — {title}</strong>'
                        f'<p style="color:#ccc;margin:6px 0 0;font-size:.88rem">{detail}</p>'
                        f'</div>', unsafe_allow_html=True)

            with st.expander("📚 Soros Reflexivity Cycle for Bitcoin Miners", expanded=False):
                st.markdown("""
**Phase 1 — Boom:**
> BTC rises → revenue up → miners expand (buy ASICs) → hashrate up → market confidence → BTC rises further ↑

**Phase 2 — Mature boom:**
> Fat margins attract capital → miners issue equity at premiums → massive expansion → difficulty surges
> → margins compress → but stock valuations still high → expansion continues on cheap capital
> *(Soros: biased perception sustains the boom past fundamentals)*

**Phase 3 — Break:**
> BTC drops OR margins hit zero → miners sell BTC to cover costs → more supply → BTC drops more ↓

**Phase 4 — Bust:**
> Weak miners shut down → hashrate falls → stocks collapse faster than BTC (high beta = amplified losses)

**Phase 5 — Recovery:**
> Difficulty adjusts down → survivors get better margins → hash ribbon crosses up → new cycle begins

**The Soros edge:** Ride the boom early, exit before the reversal. The RI score tells you where you are.
                """)
        except Exception as e:
            st.error(f"Signals tab error: {e}")
            st.code(traceback.format_exc())
