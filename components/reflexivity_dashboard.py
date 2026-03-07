"""
components/reflexivity_dashboard.py

Soros Reflexivity Analysis — Bitcoin Miners Edition

Theory: Markets don't reflect reality, they create it.
For Bitcoin miners, price → margins → expansion → hashrate → difficulty → margins
is a measurable, self-reinforcing feedback loop.

This component quantifies:
  1. Loop strength (how tightly coupled are prices ↔ fundamentals right now)
  2. Amplification factor (how much are miners amplifying BTC moves)
  3. Phase (expansionary / mature / bust / recovery)
  4. Reflexivity Index (0-100 composite score)
  5. Actionable signals derived from Soros's framework
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import yfinance as yf
import requests
from datetime import datetime, timedelta


# ─── Constants ────────────────────────────────────────────────────────────────

# Estimated all-in cost per BTC mined (USD) — industry average, updated manually
# Based on: ~30 J/TH modern ASICs, $0.05/kWh electricity, ~620 EH/s network
INDUSTRY_COST_PER_BTC = 30_000   # rough 2024-2025 average

# EH/s per unit for difficulty-to-cost formula
JOULES_PER_TH = 30.0             # modern ASIC efficiency
KWH_PRICE     = 0.05             # $/kWh industry average
SECONDS_PER_DAY = 86_400
BTC_PER_BLOCK   = 3.125          # post-halving 2024
BLOCKS_PER_DAY  = 144

# ─── Data helpers ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600)
def _fetch_blockchain_chart(chart: str, timespan: str = "1year") -> pd.DataFrame:
    """Fetch chart data from blockchain.info (free, no API key)."""
    try:
        url = (f"https://api.blockchain.info/charts/{chart}"
               f"?timespan={timespan}&format=json&cors=true")
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            return pd.DataFrame()
        data = resp.json().get("values", [])
        df = pd.DataFrame(data, columns=["timestamp", "value"])
        df["date"] = pd.to_datetime(df["timestamp"], unit="s")
        df.set_index("date", inplace=True)
        df.drop(columns=["timestamp"], inplace=True)
        return df
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=300)
def _fetch_btc_and_miners(symbols: list, period: str = "1y") -> pd.DataFrame:
    """Fetch BTC + miner closing prices."""
    tickers = ["BTC-USD"] + symbols
    raw = {}
    for t in tickers:
        try:
            hist = yf.Ticker(t).history(period=period)
            if not hist.empty:
                raw[t] = hist["Close"]
        except Exception:
            pass
    return pd.DataFrame(raw).dropna(how="all")


# ─── Core calculations ────────────────────────────────────────────────────────

def _rolling_beta(stock: pd.Series, benchmark: pd.Series, window: int = 30) -> pd.Series:
    """Rolling beta of stock vs benchmark."""
    sr = stock.pct_change().dropna()
    br = benchmark.pct_change().dropna()
    idx = sr.index.intersection(br.index)
    sr, br = sr.loc[idx], br.loc[idx]

    betas = []
    dates = []
    for i in range(window, len(sr)):
        s_w = sr.iloc[i - window:i]
        b_w = br.iloc[i - window:i]
        cov  = np.cov(s_w, b_w)[0, 1]
        var  = np.var(b_w)
        betas.append(cov / var if var > 0 else np.nan)
        dates.append(sr.index[i])
    return pd.Series(betas, index=dates)


def _rolling_correlation(a: pd.Series, b: pd.Series, window: int = 30) -> pd.Series:
    ra, rb = a.pct_change(), b.pct_change()
    idx = ra.index.intersection(rb.index)
    return ra.loc[idx].rolling(window).corr(rb.loc[idx])


def _estimate_miner_breakeven(difficulty_series: pd.Series) -> pd.Series:
    """
    Estimate breakeven BTC price needed to cover electricity costs.
    breakeven = (difficulty * 2^32 / (10*60)) * joules_per_th * kwh_price / (btc_per_day * 1e12)
    Simplified: proportional to difficulty.
    """
    # Network hashrate implied by difficulty:
    # H = difficulty * 2^32 / 600  (hashes/sec)
    hashrate_hs = difficulty_series * (2**32) / 600          # H/s
    hashrate_ths = hashrate_hs / 1e12                        # TH/s

    # Energy cost per day for whole network (kWh)
    energy_kwh_day = hashrate_ths * JOULES_PER_TH * SECONDS_PER_DAY / 3_600_000

    # Total BTC mined per day
    btc_per_day = BLOCKS_PER_DAY * BTC_PER_BLOCK

    # Breakeven BTC price: energy cost / BTC produced
    breakeven = (energy_kwh_day * KWH_PRICE) / btc_per_day
    return breakeven


def _detect_phase(btc_mom_30d: float, avg_miner_mom_30d: float,
                  loop_corr: float, margin_pct: float) -> tuple:
    """
    Returns (phase_name, phase_color, description).
    Phase logic based on Soros's boom-bust cycle:
      - Expansionary: both positive + high coupling + healthy margins
      - Mature Boom:  positive but margins compressing + high beta
      - Transition:   divergence between BTC and miners
      - Contraction:  both negative + high coupling
      - Capitulation: miners falling faster than BTC + ultra-low margins
      - Recovery:     BTC stabilizing + miner stocks rebounding from lows
    """
    high_coupling = abs(loop_corr) > 0.6

    if btc_mom_30d > 0.05 and avg_miner_mom_30d > 0.05 and margin_pct > 0.30:
        if high_coupling:
            return ("🚀 Expansionary", "#00cc66",
                    "Classic Soros boom: rising prices justify expansion, expansion drives prices higher. "
                    "Self-reinforcing BULLISH loop active.")

    if btc_mom_30d > 0 and avg_miner_mom_30d > 0.10 and margin_pct < 0.20:
        return ("⚠️ Mature Boom", "#ffaa00",
                "Miners over-expanding on cheap capital. Margins compressing despite rising BTC. "
                "Loop is heating — watch for reversal when capital dries up.")

    if btc_mom_30d > 0.02 and avg_miner_mom_30d < -0.05:
        return ("🔄 Divergence", "#f7931e",
                "BTC rising but miners lagging — loop may be decoupling. "
                "Could be early warning of miner-specific stress or valuation reset.")

    if btc_mom_30d < -0.05 and avg_miner_mom_30d < -0.05 and high_coupling:
        if margin_pct < 0.10:
            return ("💀 Capitulation", "#ff4444",
                    "Miners in capitulation: BTC falling, margins near zero, forced selling. "
                    "Self-reinforcing BEARISH loop. Historically precedes major bottoms.")
        return ("📉 Contraction", "#ff6666",
                "Bust phase: falling prices reduce margins, miners cut expansion, "
                "which signals weakness, which drives prices lower. Soros bust loop active.")

    if btc_mom_30d > -0.03 and avg_miner_mom_30d > 0.05 and margin_pct > 0.15:
        return ("🌱 Recovery", "#66ddaa",
                "Miners recovering after capitulation. Weak hands gone, survivors benefit "
                "from lower difficulty. Early reflexive BULLISH setup.")

    return ("➡️ Neutral / Transitioning", "#8b8b9b",
            "No dominant reflexive loop detected. Market digesting recent moves. "
            "Watch for loop re-engagement when momentum picks up.")


def _compute_reflexivity_index(loop_corr: float, avg_beta: float,
                                margin_pct: float, btc_mom: float,
                                miner_mom: float) -> dict:
    """
    Composite Reflexivity Index: 0–100.

    Components:
      - Coupling (30%):     |correlation| → how locked-together prices and fundamentals are
      - Amplification (30%):beta/2.5 capped → how much miners amplify BTC moves
      - Momentum alignment (20%): same direction = loop active
      - Margin health (20%): healthy margins = capacity to sustain loop

    Direction (+/-): positive = bullish loop, negative = bearish loop
    """
    coupling   = min(abs(loop_corr), 1.0) * 100          # 0-100
    amplif     = min(abs(avg_beta) / 3.0, 1.0) * 100     # 0-100, capped at beta=3
    alignment  = 100 if (btc_mom * miner_mom) > 0 else 0 # same direction?
    margin_sc  = min(max(margin_pct, 0), 1.0) * 100       # 0-100

    raw = (0.30 * coupling +
           0.30 * amplif   +
           0.20 * alignment +
           0.20 * margin_sc)

    # Direction: positive = bullish reflexivity, negative = bearish
    direction = np.sign(btc_mom) if abs(btc_mom) > 0.01 else 0

    return {
        "index":          round(raw, 1),
        "direction":      direction,
        "coupling":       round(coupling, 1),
        "amplification":  round(amplif, 1),
        "alignment":      round(alignment, 1),
        "margin_score":   round(margin_sc, 1),
    }


# ─── Main component ───────────────────────────────────────────────────────────

class ReflexivityDashboard:
    """Soros Reflexivity Analysis for Bitcoin Miners"""

    def render(self, selected_stocks: list, stock_names: dict):
        st.header("🔄 Reflexivity Analysis")
        st.markdown(
            "> *\"Markets are always biased in one direction or another. "
            "The trend is your friend until the reflexive process reverses.\"*  \n"
            "> — George Soros"
        )

        with st.spinner("Computing reflexivity metrics…"):
            prices_df   = _fetch_btc_and_miners(selected_stocks, period="1y")
            hashrate_df = _fetch_blockchain_chart("hash-rate", "1year")
            diff_df     = _fetch_blockchain_chart("difficulty", "1year")

        if prices_df.empty or "BTC-USD" not in prices_df.columns:
            st.error("Could not fetch BTC/miner price data. Check internet connection.")
            return

        btc = prices_df["BTC-USD"]
        miner_cols = [c for c in prices_df.columns if c != "BTC-USD"]
        if not miner_cols:
            st.warning("No miner price data available for selected stocks.")
            return

        miners_avg = prices_df[miner_cols].mean(axis=1)

        # ── Core metrics ──────────────────────────────────────────────────────
        loop_corr_series = _rolling_correlation(miners_avg, btc, window=30)
        loop_corr        = loop_corr_series.dropna().iloc[-1] if not loop_corr_series.dropna().empty else 0

        avg_beta_series  = _rolling_beta(miners_avg, btc, window=30)
        avg_beta         = avg_beta_series.iloc[-1] if not avg_beta_series.empty else 1.0

        btc_mom_30d      = btc.pct_change(30).iloc[-1]  if len(btc) > 30 else 0
        miner_mom_30d    = miners_avg.pct_change(30).iloc[-1] if len(miners_avg) > 30 else 0

        # Margin estimate
        if not diff_df.empty:
            diff_resampled = diff_df["value"].resample("D").last().ffill()
            breakeven      = _estimate_miner_breakeven(diff_resampled)
            btc_aligned    = btc.reindex(breakeven.index, method="ffill")
            margin_series  = (btc_aligned - breakeven) / btc_aligned
            current_margin = margin_series.dropna().iloc[-1] if not margin_series.dropna().empty else 0.25
            current_beven  = breakeven.iloc[-1] if not breakeven.empty else INDUSTRY_COST_PER_BTC
        else:
            current_margin = max(0, (btc.iloc[-1] - INDUSTRY_COST_PER_BTC) / btc.iloc[-1])
            current_beven  = INDUSTRY_COST_PER_BTC
            margin_series  = None

        ri = _compute_reflexivity_index(
            loop_corr, avg_beta, current_margin, btc_mom_30d, miner_mom_30d)

        phase, phase_color, phase_desc = _detect_phase(
            btc_mom_30d, miner_mom_30d, loop_corr, current_margin)

        # ── Tabs ──────────────────────────────────────────────────────────────
        t1, t2, t3, t4, t5 = st.tabs([
            "🎯 Reflexivity Index",
            "🔁 Loop Analysis",
            "📡 Miner–BTC Coupling",
            "🗺️ Phase Map",
            "💡 Signals",
        ])

        with t1:
            self._render_index_tab(ri, phase, phase_color, phase_desc,
                                   btc, btc_mom_30d, miner_mom_30d,
                                   current_margin, current_beven, avg_beta, loop_corr)

        with t2:
            self._render_loop_tab(btc, miners_avg, hashrate_df, diff_df,
                                  margin_series, loop_corr_series)

        with t3:
            self._render_coupling_tab(prices_df, miner_cols, stock_names,
                                      avg_beta_series, loop_corr_series)

        with t4:
            self._render_phase_map(btc, miners_avg, loop_corr_series, diff_df)

        with t5:
            self._render_signals(ri, phase, phase_color, btc, miners_avg,
                                 avg_beta_series, loop_corr_series, current_margin,
                                 hashrate_df, selected_stocks, stock_names)

    # ─── Tab 1 — Reflexivity Index ───────────────────────────────────────────

    def _render_index_tab(self, ri, phase, phase_color, phase_desc,
                          btc, btc_mom, miner_mom, margin, beven, beta, corr):
        st.subheader("🎯 Reflexivity Index")
        st.markdown(
            "Composite score measuring the strength and direction of the "
            "self-reinforcing feedback loop between BTC prices and miner fundamentals."
        )

        # Big RI gauge
        col_gauge, col_phase = st.columns([1, 1])

        with col_gauge:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=ri["index"],
                title={"text": "Reflexivity Index", "font": {"size": 18}},
                delta={"reference": 50, "valueformat": ".1f"},
                gauge={
                    "axis": {"range": [0, 100], "tickwidth": 1},
                    "bar":  {"color": phase_color},
                    "steps": [
                        {"range": [0,  25], "color": "#1a2a1a"},
                        {"range": [25, 50], "color": "#1a2010"},
                        {"range": [50, 75], "color": "#2a1a00"},
                        {"range": [75, 100],"color": "#2a0000"},
                    ],
                    "threshold": {
                        "line": {"color": "white", "width": 3},
                        "thickness": 0.75,
                        "value": ri["index"],
                    },
                },
            ))
            fig.update_layout(
                template="plotly_dark", height=280,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "**0–25** Weak/No loop  |  "
                "**25–50** Forming  |  "
                "**50–75** Active  |  "
                "**75–100** Dominant"
            )

        with col_phase:
            st.markdown(f"### Current Phase")
            st.markdown(
                f'<div style="background:{phase_color}22; border:1px solid {phase_color}; '
                f'border-radius:8px; padding:16px; margin:8px 0;">'
                f'<h3 style="color:{phase_color}; margin:0">{phase}</h3>'
                f'<p style="color:#ccc; margin-top:8px; font-size:0.9rem">{phase_desc}</p>'
                f'</div>',
                unsafe_allow_html=True
            )

        st.markdown("---")

        # Component breakdown
        st.subheader("📊 Index Components")
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            color = "#00cc66" if ri["coupling"] > 60 else "#ffaa00" if ri["coupling"] > 30 else "#8b8b9b"
            st.metric("🔗 Coupling", f"{ri['coupling']:.0f}/100",
                      help="Rolling 30d correlation between BTC and miner stocks. High = tight feedback loop.")
            st.markdown(f'<div style="height:6px; background:{color}; border-radius:3px; width:{ri["coupling"]}%"></div>',
                        unsafe_allow_html=True)

        with c2:
            color = "#ff6666" if ri["amplification"] > 70 else "#ffaa00" if ri["amplification"] > 40 else "#00cc66"
            st.metric("📡 Amplification", f"{ri['amplification']:.0f}/100",
                      help=f"Miner beta to BTC: {beta:.2f}x. >1.5 = miners amplifying BTC moves (loop heating up)")
            st.markdown(f'<div style="height:6px; background:{color}; border-radius:3px; width:{ri["amplification"]}%"></div>',
                        unsafe_allow_html=True)

        with c3:
            color = "#00cc66" if ri["alignment"] > 50 else "#ff4444"
            st.metric("🎯 Momentum Alignment", f"{ri['alignment']:.0f}/100",
                      help="Are BTC and miners moving in the same direction? 100=yes (loop active), 0=diverging (loop breaking)")
            st.markdown(f'<div style="height:6px; background:{color}; border-radius:3px; width:{ri["alignment"]}%"></div>',
                        unsafe_allow_html=True)

        with c4:
            color = "#00cc66" if ri["margin_score"] > 50 else "#ffaa00" if ri["margin_score"] > 20 else "#ff4444"
            st.metric("💰 Margin Health", f"{ri['margin_score']:.0f}/100",
                      help=f"Estimated miner margin: {margin*100:.1f}%. "
                           f"Healthy margins sustain the expansionary loop.")
            st.markdown(f'<div style="height:6px; background:{color}; border-radius:3px; width:{ri["margin_score"]}%"></div>',
                        unsafe_allow_html=True)

        st.markdown("---")

        # Market stats
        st.subheader("📈 Current Market State")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.metric("BTC Price", f"${btc.iloc[-1]:,.0f}",
                      delta=f"{btc_mom*100:+.1f}% (30d)")
        with c2:
            st.metric("Miner Avg (30d)", f"{miner_mom*100:+.1f}%",
                      delta="vs BTC " + f"{(miner_mom - btc_mom)*100:+.1f}%")
        with c3:
            st.metric("Miner Beta", f"{beta:.2f}x",
                      delta="amplifying" if beta > 1.5 else "moderate" if beta > 1.0 else "low")
        with c4:
            st.metric("Coupling", f"{corr:.2f}",
                      delta="tight" if abs(corr) > 0.7 else "moderate" if abs(corr) > 0.4 else "loose")
        with c5:
            st.metric("Breakeven BTC", f"${beven:,.0f}",
                      delta=f"Margin {margin*100:.1f}%")

    # ─── Tab 2 — Loop Analysis ────────────────────────────────────────────────

    def _render_loop_tab(self, btc, miners_avg, hashrate_df, diff_df, margin_series, corr_series):
        st.subheader("🔁 The Feedback Loop")
        st.markdown(
            "Visualizing the three legs of the miner reflexivity loop: "
            "**price → margins → expansion** and back."
        )

        fig = make_subplots(
            rows=4, cols=1, shared_xaxes=True,
            vertical_spacing=0.04,
            subplot_titles=[
                "BTC Price ($)",
                "Network Hashrate (EH/s) — Miner Expansion Proxy",
                "Estimated Miner Margin (%)",
                "30d Reflexivity Coupling (rolling correlation)"
            ],
            row_heights=[0.30, 0.25, 0.25, 0.20]
        )

        # 1. BTC Price
        fig.add_trace(go.Scatter(
            x=btc.index, y=btc.values,
            name="BTC Price", line=dict(color="#f7931e", width=2),
            fill="tozeroy", fillcolor="rgba(247,147,30,0.07)"
        ), row=1, col=1)

        # 2. Hashrate
        if not hashrate_df.empty:
            fig.add_trace(go.Scatter(
                x=hashrate_df.index, y=hashrate_df["value"],
                name="Hashrate (EH/s)", line=dict(color="#00aaff", width=2),
                fill="tozeroy", fillcolor="rgba(0,170,255,0.07)"
            ), row=2, col=1)

            # Hash ribbon: 30d and 60d MA
            hr_30 = hashrate_df["value"].rolling(30).mean()
            hr_60 = hashrate_df["value"].rolling(60).mean()
            fig.add_trace(go.Scatter(
                x=hr_30.index, y=hr_30.values,
                name="HR 30d MA", line=dict(color="#66ddff", width=1, dash="dot")
            ), row=2, col=1)
            fig.add_trace(go.Scatter(
                x=hr_60.index, y=hr_60.values,
                name="HR 60d MA", line=dict(color="#ffffff", width=1, dash="dash")
            ), row=2, col=1)
        else:
            # Fallback: average miner stocks as expansion proxy
            miners_norm = miners_avg / miners_avg.iloc[0] * 100
            fig.add_trace(go.Scatter(
                x=miners_norm.index, y=miners_norm.values,
                name="Miners (indexed)", line=dict(color="#00aaff", width=2)
            ), row=2, col=1)
            st.caption("⚠️ Hashrate data unavailable — showing miner stock index as proxy")

        # 3. Margin
        if margin_series is not None and not margin_series.dropna().empty:
            margin_pct = margin_series.dropna() * 100
            colors = ["#00cc66" if v > 30 else "#ffaa00" if v > 10 else "#ff4444"
                      for v in margin_pct.values]
            fig.add_trace(go.Bar(
                x=margin_pct.index, y=margin_pct.values,
                name="Margin (%)", marker_color=colors, opacity=0.7
            ), row=3, col=1)
            fig.add_hline(y=0, line_color="white", line_dash="dash",
                          row=3, col=1, annotation_text="Breakeven")
            fig.add_hline(y=20, line_color="#ffaa00", line_dash="dot",
                          row=3, col=1, annotation_text="Caution")
        else:
            st.caption("Margin data unavailable — check difficulty API")

        # 4. Coupling
        corr_clean = corr_series.dropna()
        if not corr_clean.empty:
            fig.add_trace(go.Scatter(
                x=corr_clean.index, y=corr_clean.values,
                name="Coupling", line=dict(color="#cc88ff", width=2),
                fill="tozeroy", fillcolor="rgba(200,136,255,0.1)"
            ), row=4, col=1)
            fig.add_hline(y=0.7,  line_color="#00cc66", line_dash="dot",
                          row=4, col=1, annotation_text="Strong")
            fig.add_hline(y=-0.7, line_color="#ff4444", line_dash="dot",
                          row=4, col=1)

        fig.update_layout(
            template="plotly_dark", height=750,
            hovermode="x unified", showlegend=True,
            legend=dict(orientation="h", y=-0.05),
            margin=dict(l=0, r=0, t=50, b=40)
        )
        fig.update_yaxes(title_text="USD",    row=1, col=1)
        fig.update_yaxes(title_text="EH/s",   row=2, col=1)
        fig.update_yaxes(title_text="%",       row=3, col=1)
        fig.update_yaxes(title_text="Corr",   row=4, col=1, range=[-1, 1])

        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "**Reading the loop:**  \n"
            "🔶 **BTC + Hashrate rising together** = expansionary reflexivity (Soros boom phase)  \n"
            "🟢 **Green margin bars** = healthy feedback; miners can justify expansion  \n"
            "🔴 **Red margin + falling hashrate** = capitulation; bust loop  \n"
            "🟣 **Coupling near ±1** = loop is dominant; prices and fundamentals locked in sync"
        )

    # ─── Tab 3 — Coupling ─────────────────────────────────────────────────────

    def _render_coupling_tab(self, prices_df, miner_cols, stock_names,
                              beta_series, corr_series):
        st.subheader("📡 Miner–BTC Coupling Analysis")
        st.markdown(
            "**Amplification factor** = how much miners lever up each BTC move. "
            "Soros: the higher the amplification, the more explosive (and fragile) the loop."
        )

        btc = prices_df["BTC-USD"]

        # Per-stock beta table
        beta_data = []
        for symbol in miner_cols:
            if symbol not in prices_df.columns:
                continue
            try:
                betas_s = _rolling_beta(prices_df[symbol], btc, window=30)
                corr_s  = _rolling_correlation(prices_df[symbol], btc, window=30).dropna()
                ret_30  = prices_df[symbol].pct_change(30).iloc[-1]
                btc_30  = btc.pct_change(30).iloc[-1]

                beta_val = betas_s.iloc[-1] if not betas_s.empty else np.nan
                corr_val = corr_s.iloc[-1]  if not corr_s.empty  else np.nan

                beta_data.append({
                    "Symbol":        symbol,
                    "Name":          stock_names.get(symbol, symbol)[:22],
                    "Beta (30d)":    round(beta_val, 2) if not np.isnan(beta_val) else "N/A",
                    "Correlation":   round(corr_val, 2) if not np.isnan(corr_val) else "N/A",
                    "30d Return":    f"{ret_30*100:+.1f}%",
                    "vs BTC":        f"{(ret_30-btc_30)*100:+.1f}%",
                    "Loop Role":     (
                        "🔥 High Amplifier"   if not np.isnan(beta_val) and beta_val > 2.5 else
                        "📡 Amplifier"         if not np.isnan(beta_val) and beta_val > 1.5 else
                        "⚖️ Proportional"      if not np.isnan(beta_val) and beta_val > 0.8 else
                        "🛡️ Damper"
                    )
                })
            except Exception:
                continue

        if beta_data:
            st.dataframe(pd.DataFrame(beta_data), use_container_width=True, hide_index=True)

        st.markdown("---")

        # Beta evolution chart
        st.subheader("📈 Average Amplification Factor Over Time (30d Rolling Beta)")
        if not beta_series.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=beta_series.index, y=beta_series.values,
                name="Portfolio Beta", line=dict(color="#f7931e", width=2),
                fill="tozeroy", fillcolor="rgba(247,147,30,0.1)"
            ))
            # Reference lines
            for level, color, label in [
                (3.0, "#ff2222", "3x — Extreme amplification"),
                (2.0, "#ff8800", "2x — High amplification"),
                (1.5, "#ffcc00", "1.5x — Moderate amplification"),
                (1.0, "#ffffff", "1x — Neutral (moves with BTC)"),
            ]:
                fig.add_hline(y=level, line_dash="dot", line_color=color,
                              annotation_text=label, annotation_position="right")

            fig.update_layout(
                title="Miner Portfolio Rolling Beta vs BTC (30-day window)",
                xaxis_title="Date", yaxis_title="Beta",
                template="plotly_dark", height=400, hovermode="x unified"
            )
            st.plotly_chart(fig, use_container_width=True)

        # Scatter: 30d BTC return vs miner return
        st.subheader("🎯 Amplification Scatter — BTC Return vs Miner Return (30d)")
        scatter_data = []
        for symbol in miner_cols:
            if symbol in prices_df.columns:
                try:
                    r_btc   = prices_df["BTC-USD"].pct_change(30).dropna()
                    r_miner = prices_df[symbol].pct_change(30).dropna()
                    idx     = r_btc.index.intersection(r_miner.index)
                    for date in idx[-120:]:   # last 120 data points
                        scatter_data.append({
                            "date": date,
                            "btc_return":   r_btc.loc[date] * 100,
                            "miner_return": r_miner.loc[date] * 100,
                            "symbol": symbol
                        })
                except Exception:
                    continue

        if scatter_data:
            sdf = pd.DataFrame(scatter_data)
            fig = px.scatter(
                sdf, x="btc_return", y="miner_return", color="symbol",
                title="BTC 30d Return vs Miner 30d Return (each dot = one time window)",
                labels={"btc_return": "BTC 30d Return (%)",
                        "miner_return": "Miner 30d Return (%)"},
                trendline="ols",
                template="plotly_dark"
            )
            # Add slope reference lines
            x_range = np.linspace(sdf["btc_return"].min(), sdf["btc_return"].max(), 100)
            for mult, color, name in [(1, "white", "1x (beta=1)"), (2, "#ffaa00", "2x"), (3, "#ff4444", "3x")]:
                fig.add_trace(go.Scatter(
                    x=x_range, y=x_range * mult,
                    mode="lines", name=name,
                    line=dict(color=color, dash="dot", width=1)
                ))
            fig.update_layout(height=500)
            st.plotly_chart(fig, use_container_width=True)
            st.caption(
                "Steeper slope = higher beta = stronger amplification = "
                "more explosive reflexive loop. "
                "Tighter cluster = higher coupling."
            )

    # ─── Tab 4 — Phase Map ────────────────────────────────────────────────────

    def _render_phase_map(self, btc, miners_avg, corr_series, diff_df):
        st.subheader("🗺️ Reflexivity Phase Map")
        st.markdown(
            "Each point = one 30-day window. "
            "Position in the map reveals the current loop phase. "
            "The arrow shows recent trajectory."
        )

        btc_mom    = btc.pct_change(30).dropna() * 100
        miner_mom  = miners_avg.pct_change(30).dropna() * 100
        corr_clean = corr_series.dropna()

        idx = btc_mom.index.intersection(miner_mom.index).intersection(corr_clean.index)
        if len(idx) < 10:
            st.warning("Insufficient data for phase map.")
            return

        df = pd.DataFrame({
            "btc_mom":   btc_mom.loc[idx],
            "miner_mom": miner_mom.loc[idx],
            "coupling":  corr_clean.loc[idx].abs(),
            "date":      idx
        }).dropna().tail(252)   # last year

        df["age"] = range(len(df))
        recent = df.tail(30)

        fig = go.Figure()

        # Background quadrant shading
        for x0, x1, y0, y1, color, label in [
            (0, 100, 0, 300, "rgba(0,200,100,0.05)",  "Boom"),
            (-100, 0, -300, 0, "rgba(255,50,50,0.05)", "Bust"),
            (0, 100, -300, 0, "rgba(255,170,0,0.05)",  "Diverge"),
            (-100, 0, 0, 300, "rgba(100,200,255,0.05)","Recovery"),
        ]:
            fig.add_shape(type="rect", x0=x0, x1=x1, y0=y0, y1=y1,
                          fillcolor=color, line=dict(width=0))
            fig.add_annotation(
                x=(x0+x1)/2, y=(y0+y1)/2, text=label,
                showarrow=False, font=dict(size=14, color="rgba(255,255,255,0.15)")
            )

        # Historical path (faded)
        fig.add_trace(go.Scatter(
            x=df["btc_mom"], y=df["miner_mom"],
            mode="markers",
            marker=dict(
                size=6,
                color=df["age"],
                colorscale="Blues",
                opacity=0.4,
                showscale=False,
            ),
            text=df["date"].dt.strftime("%Y-%m-%d"),
            hovertemplate="<b>%{text}</b><br>BTC: %{x:.1f}%<br>Miners: %{y:.1f}%<extra></extra>",
            name="History"
        ))

        # Recent trajectory (bright + arrow)
        fig.add_trace(go.Scatter(
            x=recent["btc_mom"], y=recent["miner_mom"],
            mode="lines+markers",
            line=dict(color="#f7931e", width=2),
            marker=dict(size=8, color="#f7931e"),
            text=recent["date"].dt.strftime("%Y-%m-%d"),
            hovertemplate="<b>%{text}</b><br>BTC: %{x:.1f}%<br>Miners: %{y:.1f}%<extra></extra>",
            name="Last 30 days"
        ))

        # Current position
        fig.add_trace(go.Scatter(
            x=[df["btc_mom"].iloc[-1]],
            y=[df["miner_mom"].iloc[-1]],
            mode="markers+text",
            marker=dict(size=18, color="#ffcc02", symbol="star"),
            text=["NOW"],
            textposition="top center",
            name="Current"
        ))

        # Axes
        fig.add_vline(x=0, line_color="rgba(255,255,255,0.3)", line_width=1)
        fig.add_hline(y=0, line_color="rgba(255,255,255,0.3)", line_width=1)

        fig.update_layout(
            title="Reflexivity Phase Map: BTC Momentum vs Miner Momentum (30d)",
            xaxis_title="BTC 30d Momentum (%)",
            yaxis_title="Miner 30d Momentum (%)",
            template="plotly_dark",
            height=600,
            hovermode="closest",
        )
        st.plotly_chart(fig, use_container_width=True)

        st.info(
            "**Quadrants:**  \n"
            "↗️ Top-right = Boom (both rising, loop amplifying)  \n"
            "↙️ Bottom-left = Bust (both falling, loop crushing)  \n"
            "↘️ Bottom-right = Divergence (BTC up, miners lagging — loop weakening)  \n"
            "↖️ Top-left = Recovery (miners bouncing from capitulation)"
        )

    # ─── Tab 5 — Signals ──────────────────────────────────────────────────────

    def _render_signals(self, ri, phase, phase_color, btc, miners_avg,
                         beta_series, corr_series, margin,
                         hashrate_df, selected_stocks, stock_names):
        st.subheader("💡 Reflexivity Signals")
        st.markdown("Actionable intelligence derived from the Soros framework.")

        signals = []

        # ── Signal 1: Loop direction ──────────────────────────────────────────
        btc_mom = btc.pct_change(30).iloc[-1]
        miner_mom = miners_avg.pct_change(30).iloc[-1]

        if btc_mom > 0.10 and miner_mom > 0.15 and ri["coupling"] > 60:
            signals.append({
                "icon": "🚀", "level": "BULLISH",
                "color": "#00cc66",
                "signal": "Strong Boom Loop Active",
                "detail": f"BTC +{btc_mom*100:.1f}% and miners +{miner_mom*100:.1f}% in 30d. "
                           f"High coupling ({ri['coupling']:.0f}/100). "
                           "Self-reinforcing bull loop. Momentum likely to continue until margins compress."
            })
        elif btc_mom < -0.10 and miner_mom < -0.15 and ri["coupling"] > 60:
            signals.append({
                "icon": "📉", "level": "BEARISH",
                "color": "#ff4444",
                "signal": "Strong Bust Loop Active",
                "detail": f"BTC {btc_mom*100:.1f}% and miners {miner_mom*100:.1f}% in 30d. "
                           f"High coupling ({ri['coupling']:.0f}/100). "
                           "Self-reinforcing bear loop. Expect continued pressure until capitulation clears."
            })

        # ── Signal 2: Amplification extremes ─────────────────────────────────
        avg_beta = beta_series.iloc[-1] if not beta_series.empty else 1.0
        if avg_beta > 2.5:
            signals.append({
                "icon": "🔥", "level": "WARNING",
                "color": "#ff8800",
                "signal": f"Extreme Amplification ({avg_beta:.1f}x Beta)",
                "detail": "Miners are amplifying BTC moves by >2.5x. "
                           "Soros: extreme amplification signals late-stage reflexivity. "
                           "When the loop reverses, miners will fall faster than BTC. "
                           "Consider hedging or reducing miner exposure."
            })
        elif avg_beta < 0.8 and abs(btc_mom) > 0.05:
            signals.append({
                "icon": "🛡️", "level": "NEUTRAL",
                "color": "#8b8b9b",
                "signal": f"Decoupling Detected ({avg_beta:.1f}x Beta)",
                "detail": "Miners not amplifying BTC moves. Loop is weak. "
                           "Could mean miners are pricing in idiosyncratic risk, "
                           "or the reflexive cycle is in a dormant phase."
            })

        # ── Signal 3: Margin-based signals ────────────────────────────────────
        if margin < 0.05:
            signals.append({
                "icon": "💀", "level": "CRITICAL",
                "color": "#ff2222",
                "signal": f"Breakeven Territory (Margin: {margin*100:.1f}%)",
                "detail": "Estimated miner margins near zero. Forced BTC selling imminent as miners "
                           "cover operating costs. This is the Soros 'bust accelerant' — selling BTC "
                           "drives the price lower, which drives more selling. Watch for hash ribbon reversal."
            })
        elif margin > 0.60:
            signals.append({
                "icon": "💰", "level": "BULLISH",
                "color": "#00cc66",
                "signal": f"Fat Margins ({margin*100:.1f}%) — Expansion Imminent",
                "detail": "Extremely healthy mining margins. Expect aggressive ASIC purchasing, "
                           "capacity expansion, and potential capital raises. "
                           "Reflexive loop will accelerate — more hashrate → market confidence → higher valuations."
            })

        # ── Signal 4: Hash ribbon (if data available) ─────────────────────────
        if not hashrate_df.empty and len(hashrate_df) > 60:
            hr = hashrate_df["value"]
            hr_30 = hr.rolling(30).mean().iloc[-1]
            hr_60 = hr.rolling(60).mean().iloc[-1]
            hr_30_prev = hr.rolling(30).mean().iloc[-5]  # 5 days ago

            if hr_30 > hr_60 and hr_30_prev <= hr.rolling(60).mean().iloc[-5]:
                signals.append({
                    "icon": "🌱", "level": "BULLISH",
                    "color": "#00cc66",
                    "signal": "Hash Ribbon Buy Signal",
                    "detail": "30d hashrate MA just crossed above 60d MA. "
                               "Historically one of the strongest Bitcoin buy signals — "
                               "means miner capitulation is over, survivors are expanding. "
                               "Reflexive recovery loop beginning."
                })
            elif hr_30 < hr_60:
                signals.append({
                    "icon": "⚠️", "level": "WARNING",
                    "color": "#ffaa00",
                    "signal": "Hash Ribbon: Capitulation Phase",
                    "detail": "30d hashrate MA below 60d MA. Miners still capitulating. "
                               "Bust loop may not be over. Wait for ribbon reversal before adding exposure."
                })

        # ── Signal 5: Momentum divergence ─────────────────────────────────────
        btc_5d = btc.pct_change(5).iloc[-1]
        miner_5d = miners_avg.pct_change(5).iloc[-1]
        if btc_5d > 0.03 and miner_5d < -0.02:
            signals.append({
                "icon": "🔄", "level": "WARNING",
                "color": "#f7931e",
                "signal": "Short-term Divergence: BTC Up, Miners Down",
                "detail": f"BTC +{btc_5d*100:.1f}% in 5d while miners {miner_5d*100:.1f}%. "
                           "Loop may be losing steam or miners pricing in upcoming difficulty adjustment. "
                           "Watch for convergence — either miners catch up or BTC gives back gains."
            })

        # Render signals
        if not signals:
            st.success("✅ No extreme reflexivity signals. Market in balanced state.")
        else:
            for s in signals:
                st.markdown(
                    f'<div style="background:{s["color"]}18; border-left:4px solid {s["color"]}; '
                    f'border-radius:6px; padding:14px 18px; margin:8px 0;">'
                    f'<strong style="color:{s["color"]}">{s["icon"]} [{s["level"]}] {s["signal"]}</strong>'
                    f'<p style="color:#ccc; margin:6px 0 0; font-size:0.88rem">{s["detail"]}</p>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # ── Soros Framework Explainer ─────────────────────────────────────────
        with st.expander("📚 How Soros Reflexivity Works for Bitcoin Miners", expanded=False):
            st.markdown("""
**The Classic Mining Reflexivity Cycle:**

**Phase 1 — Boom begins:**
> BTC price rises → Mining revenue increases → Miners profitable → Miners expand (buy ASICs)
> → Hashrate rises → Market confidence grows → BTC price rises further (loop active ↑)

**Phase 2 — Mature boom:**
> Fat margins attract institutional capital → Miners issue equity/debt at premium valuations
> → Massive expansion plans → Difficulty surges → Margins start compressing
> → But stock valuations still high, so expansion continues on cheap capital
> → *This is Soros's "reflexive divergence" — biased perception sustains the boom past fundamentals*

**Phase 3 — Boom breaks:**
> BTC price drops OR margins hit zero → Expansion stops → Miners SELL BTC to cover costs
> → More BTC supply → BTC price falls more → More miners in distress → Loop reverses ↓

**Phase 4 — Bust and capitulation:**
> Weak miners shut down → Hashrate falls → Hash ribbon inverts
> → Stock prices collapse faster than BTC (high beta = amplified losses)
> → Panic selling, distressed assets, bankruptcies

**Phase 5 — Recovery:**
> Difficulty adjusts DOWN (less competition) → Survivors get better margins
> → Buying opportunity for patient capital → Hash ribbon crosses up → New cycle begins

**The Soros edge:** He identified that the *loop itself* — not just the fundamentals — is the asset.
Ride the boom early, exit before the reversal. The RI score helps you know where you are in the cycle.
            """)
