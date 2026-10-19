"""
Trade Signals Dashboard  v2
"Tell me what to do and when to do it."

Layout:
  1. ⚡ ACTION REQUIRED NOW   — high-conviction BUY/SELL cards with exact levels
  2. 📡 BTC Context banner    — market tailwind / headwind
  3. 📋 Full signal table     — all 9 stocks at a glance
  4. 🔍 Stock-by-stock detail — expandable deep-dives
  5. 📊 Signal strength chart
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from utils.trade_signal_engine import TradeSignalEngine

_SIGNAL_COLORS = {
    'BUY':  ('#00c853', '🟢'),
    'HOLD': ('#ffd600', '🟡'),
    'SELL': ('#d50000', '🔴'),
    'N/A':  ('#90a4ae', '⚪'),
}

from utils.tickers import MINING_STOCKS as _ALL_NAMES, WATCHLIST as _WATCHLIST
_COMPANY_NAMES = {s: _ALL_NAMES.get(s, s) for s in _WATCHLIST}


class TradeSignalsDashboard:
    def __init__(self):
        self.engine = TradeSignalEngine()

    def render(self, data_fetcher=None, options_analyzer=None):
        st.title("🚦 Trade Signal Dashboard")
        st.markdown(
            "Real-time BUY / HOLD / SELL verdicts for all 9 mining stocks — "
            "with exact entry, stop-loss, and take-profit levels."
        )

        with st.spinner("Analyzing all 9 stocks across 8 factors…"):
            results = self.engine.analyze_all()

        if not results:
            st.error("Could not fetch market data. Please try again.")
            return

        # ── Data freshness banner ─────────────────────────────────────────────
        as_of = max((r['as_of'] for r in results if r.get('as_of')), default=None)
        n_na = sum(1 for r in results if r['signal'] == 'N/A')
        if as_of:
            st.caption(f"📅 Based on daily closes up to **{as_of}** (Yahoo Finance, shared with every tab; "
                       f"refreshed every 15 min). Analyzed at {results[0].get('data_timestamp', '')}.")
        if n_na:
            st.warning(f"⚪ {n_na} stock(s) have no signal right now (price data unavailable) — shown as N/A, not HOLD.")

        # ── BTC context banner ────────────────────────────────────────────────
        btc = results[0].get('btc_factors', {})
        self._render_btc_banner(btc)

        st.divider()

        # ── 1. ACTION REQUIRED NOW ────────────────────────────────────────────
        high_conviction = [
            r for r in results
            if r['signal'] in ('BUY', 'SELL') and (r.get('confidence') or 0) >= 60
        ]

        if high_conviction:
            st.subheader("⚡ Action Required Now")
            st.caption("High-conviction signals with exact entry, stop, and target levels.")
            cols = st.columns(min(len(high_conviction), 3))
            for i, r in enumerate(high_conviction[:3]):
                with cols[i]:
                    self._render_action_card(r)
            if len(high_conviction) > 3:
                for r in high_conviction[3:]:
                    self._render_action_card(r, compact=True)
        else:
            st.info(
                "**No high-conviction signals right now.** "
                "All stocks are either in HOLD territory or confidence is below 60%. "
                "Review the full table below and wait for a clearer setup."
            )

        st.divider()

        # ── 2. Summary counts ─────────────────────────────────────────────────
        buys  = [r for r in results if r['signal'] == 'BUY']
        holds = [r for r in results if r['signal'] == 'HOLD']
        sells = [r for r in results if r['signal'] == 'SELL']

        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("🟢 BUY", len(buys),  help="Bullish setup with edge")
        with c2:
            st.metric("🟡 HOLD", len(holds), help="Wait — no clear edge yet")
        with c3:
            st.metric("🔴 SELL / Short", len(sells), help="Overbought or momentum reversing")
        with c4:
            top = results[0] if results and results[0]['signal'] != 'N/A' else None
            if top:
                st.metric(
                    "🏆 Best Setup",
                    top['symbol'],
                    f"{top['signal']} {top.get('confidence', 0)}%",
                    help="Highest-scoring stock right now"
                )

        st.divider()

        # ── 3. Full signal table ──────────────────────────────────────────────
        st.subheader("📋 Signal Snapshot — All 9 Stocks")
        st.caption(
            "8 factors scored: RSI (Wilder) · Stochastic · MACD · Volume (direction-aware) · "
            "Bollinger %B · OBV slope · Sentiment · BTC momentum"
        )
        self._render_signal_table(results)

        st.divider()

        # ── 4. Deep-dive panels ───────────────────────────────────────────────
        st.subheader("🔍 Full Analysis — Expand Any Stock")
        st.caption("BUY signals are expanded by default. Click any row to see exact reasoning.")
        for r in results:
            self._render_stock_detail(r)

        st.divider()

        # ── 5. Signal strength chart ──────────────────────────────────────────
        st.subheader("📊 Signal Strength Comparison")
        self._render_signal_strength_chart(results)

        # ── How signals work ──────────────────────────────────────────────────
        with st.expander("ℹ️ How are signals calculated?"):
            st.markdown("""
**8 factors, scored and summed:**

| Factor | Max Points | Notes |
|--------|-----------|-------|
| RSI (Wilder, 14) | ±30 | Proper EWM formula; regime-gated in downtrends |
| Stochastic %K/D (14,3) | ±15 | Second momentum confirmation |
| MACD histogram | ±25 | Crossovers weighted highest |
| Volume (direction-aware) | ±20 | Surge on UP day = buy; surge on DOWN day = sell |
| Bollinger %B | ±14 | Price position within the band |
| OBV slope | ±10 | Smart-money accumulation / distribution |
| News tone | ±14 | Headline tone from 📰 Sentiment & News (not scored if unavailable) |
| BTC momentum | ±20 | BTC 1-day change is the key miner catalyst |

**Thresholds:** Score ≥ 28 → **BUY** · Score ≤ -20 → **SELL** · Between → **HOLD**  
In strong downtrends (50-MA falling > 2.5% in 10 days), BUY threshold rises to 40.

**Stops:** 2× ATR below entry (not a flat percentage).  
**Targets:** the next two Fibonacci levels above entry from the 60-day swing (retracements below the high, 127.2%/161.8% extensions above it).

**Data:** Yahoo Finance daily bars from the shared data hub (the same prices and RSI as 🧭 My Plan and 📈 Technical Analysis), refreshed every 15 minutes.  
**Confidence %** is how far the score is past the BUY/SELL threshold, rescaled to 50–95. It is **not** a probability and these short-term rules have **not** been backtested — only My Plan's rules have a track record.  
⚠️ Signals are analytical tools, not financial advice. Verify before trading.
""")

    # ──────────────────────────────────────────────────────────────────────────
    # BTC context banner
    # ──────────────────────────────────────────────────────────────────────────

    def _render_btc_banner(self, btc: dict):
        if not btc:
            return
        pct_1d = btc.get('btc_1d', 0)
        pct_5d = btc.get('btc_5d', 0)
        label  = btc.get('btc_label', '')
        score  = btc.get('btc_score', 0)

        if score >= 12:
            st.success(
                f"📡 **BTC Tailwind** — {label}  |  5-day: {pct_5d:+.1f}%  |  "
                f"Mining stocks typically follow BTC up with leverage. "
                f"Signals are boosted +{score} pts."
            )
        elif score >= 5:
            st.info(
                f"📡 **BTC Mild Tailwind** — {label}  |  5-day: {pct_5d:+.1f}%  |  "
                f"Modest BTC upside. Modest boost to signals."
            )
        elif score <= -12:
            st.error(
                f"📡 **BTC Headwind** — {label}  |  5-day: {pct_5d:+.1f}%  |  "
                f"BTC selling is a direct headwind for miners. "
                f"Signals reduced by {abs(score)} pts. Be cautious."
            )
        elif score <= -5:
            st.warning(
                f"📡 **BTC Mild Headwind** — {label}  |  5-day: {pct_5d:+.1f}%  |  "
                f"BTC softness weighing on mining sector."
            )
        else:
            st.info(f"📡 **BTC Neutral** — {label}  |  5-day: {pct_5d:+.1f}%  |  No strong catalyst.")

    # ──────────────────────────────────────────────────────────────────────────
    # Action card
    # ──────────────────────────────────────────────────────────────────────────

    def _render_action_card(self, r: dict, compact: bool = False):
        symbol = r['symbol']
        signal = r['signal']
        color, emoji = _SIGNAL_COLORS[signal]
        conf   = r.get('confidence', 50)
        pt     = r.get('price_targets')
        cur    = r.get('current_price', 0)
        regime_note = ""
        if r.get('in_downtrend'):
            regime_note = " ⚠️ downtrend — size small"
        elif r.get('in_uptrend'):
            regime_note = " ✅ uptrend"

        border_color = '#00c853' if signal == 'BUY' else '#d50000'
        bg_rgb = '0,200,83' if signal == 'BUY' else '213,0,0'

        if compact:
            # Inline compact version
            if pt:
                st.markdown(
                    f"**{emoji} {symbol}** ({conf}% confidence{regime_note})  "
                    f"Entry **${pt['entry']:.2f}** · Stop **${pt['stop_loss']:.2f}** "
                    f"(−{pt['risk_pct']:.1f}%) · TP1 **${pt['take_profit_1']:.2f}** "
                    f"(+{pt['reward_pct_tp1']:.1f}%) · R/R **{pt['risk_reward']:.1f}:1**"
                )
            return

        # Full card
        st.markdown(
            f"<div style='border-left: 4px solid {border_color}; "
            f"background: rgba({bg_rgb},0.08); "
            f"padding: 12px 16px; border-radius: 6px; margin-bottom: 8px;'>"
            f"<h3 style='margin:0; color:{border_color};'>{emoji} {signal}: {symbol} — "
            f"{_COMPANY_NAMES.get(symbol, symbol)}</h3>"
            f"<p style='margin:4px 0 0; color:#aaa; font-size:0.85em;'>"
            f"Confidence: {conf}%{regime_note}</p></div>",
            unsafe_allow_html=True,
        )

        if pt:
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                delta_to_entry = (pt['entry'] - cur) / cur * 100 if cur > 0 else 0
                st.metric(
                    "Entry" if signal == 'BUY' else "Short Entry",
                    f"${pt['entry']:.2f}",
                    f"{delta_to_entry:+.1f}% from now",
                )
            with m2:
                st.metric(
                    "🛑 Stop Loss",
                    f"${pt['stop_loss']:.2f}",
                    f"−{pt['risk_pct']:.1f}% risk  (2× ATR={pt.get('atr', 0):.2f})",
                    delta_color="inverse",
                )
            with m3:
                st.metric(
                    "🎯 Target 1",
                    f"${pt['take_profit_1']:.2f}",
                    f"+{pt['reward_pct_tp1']:.1f}%",
                )
            with m4:
                rr = pt.get('risk_reward', 0)
                rr_label = "Excellent ✅" if rr >= 3 else ("Good" if rr >= 2 else ("Fair" if rr >= 1 else "Poor ⚠️"))
                st.metric("R/R Ratio", f"{rr:.1f}:1", rr_label)

            # Top reasons, condensed
            reasons = r.get('reasons', [])
            key_reasons = [x for x in reasons if '⚠️' not in x and 'Downtrend' not in x and 'Uptrend' not in x][:3]
            if key_reasons:
                st.caption("**Why:** " + "  ·  ".join(key_reasons))
        else:
            st.info("Price targets unavailable — insufficient price history.")

    # ──────────────────────────────────────────────────────────────────────────
    # Signal table
    # ──────────────────────────────────────────────────────────────────────────

    def _render_signal_table(self, results: list):
        rows = []
        for r in results:
            color, emoji = _SIGNAL_COLORS[r['signal']]
            sig_display = f"{emoji} {r['signal']}"
            if r['signal'] == 'N/A':
                rows.append({'Ticker': r['symbol'], 'Price': 'n/a', 'Today': 'n/a', 'Signal': sig_display,
                             'Conf': 'n/a', 'RSI': 'n/a', 'Stoch': 'n/a', 'BB%B': 'n/a', 'Vol': 'n/a',
                             'OBV': 'n/a', 'R/R': 'n/a', 'Top Reason': r.get('error', 'No data')})
                continue
            conf = r.get('confidence', 50)

            rsi = r.get('rsi', 50)
            rsi_display = f"{'🔥' if rsi < 30 else ('⚠️' if rsi > 70 else '')} {rsi:.0f}"

            stoch_k = r.get('stoch_k', 50)
            stoch_display = f"{'🔥' if stoch_k < 25 else ('⚠️' if stoch_k > 75 else '')} {stoch_k:.0f}"

            pct_b = r.get('pct_b', 0.5)
            bb_display = f"{'🔥' if pct_b < 0.1 else ('⚠️' if pct_b > 0.9 else '')} {pct_b:.2f}"

            vol = r.get('volume_ratio', 1.0)
            daily = r.get('daily_return_pct', 0)
            vol_icon = '🔺' if (vol > 1.5 and daily > 0) else ('🔻' if (vol > 1.5 and daily < 0) else '↔️')
            vol_display = f"{vol_icon} {vol:.1f}x"

            obv = r.get('obv_slope', 0)
            obv_display = f"{'📈' if obv > 0.15 else ('📉' if obv < -0.15 else '—')} {obv:+.2f}"

            pt = r.get('price_targets', {}) or {}
            rr_display = f"{pt.get('risk_reward', 0):.1f}:1" if pt else "N/A"

            reasons = r.get('reasons', [])
            top_reason = next((x for x in reasons if '⚠️ Downtrend' not in x and '✅ Uptrend' not in x), reasons[0] if reasons else "—")

            rows.append({
                'Ticker': r['symbol'],
                'Price': f"${r.get('current_price', 0):.2f}",
                'Today': f"{daily:+.1f}%",
                'Signal': sig_display,
                'Conf': f"{conf}%",
                'RSI': rsi_display,
                'Stoch': stoch_display,
                'BB%B': bb_display,
                'Vol': vol_display,
                'OBV': obv_display,
                'R/R': rr_display,
                'Top Reason': top_reason,
            })

        df = pd.DataFrame(rows)

        def _row_style(row):
            sig = row['Signal']
            if 'BUY' in sig:
                return ['background-color: rgba(0,200,83,0.15)'] * len(row)
            elif 'SELL' in sig:
                return ['background-color: rgba(213,0,0,0.15)'] * len(row)
            return ['background-color: rgba(255,214,0,0.06)'] * len(row)

        styled = df.style.apply(_row_style, axis=1)
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # ──────────────────────────────────────────────────────────────────────────
    # Stock detail panel
    # ──────────────────────────────────────────────────────────────────────────

    def _render_stock_detail(self, r: dict):
        symbol  = r['symbol']
        signal  = r['signal']
        color, emoji = _SIGNAL_COLORS[signal]
        if signal == 'N/A':
            with st.expander(f"⚪ **{symbol}** — no signal ({r.get('error', 'no data')})"):
                st.info("No price data right now, so no signal is shown. Try 🔄 Refresh Data in a minute.")
            return
        conf    = r.get('confidence', 50)
        cur     = r.get('current_price', 0)
        daily   = r.get('daily_return_pct', 0)

        regime_tag = ""
        if r.get('in_downtrend'):
            regime_tag = " | ⚠️ Downtrend"
        elif r.get('in_uptrend'):
            regime_tag = " | ✅ Uptrend"

        label = (
            f"{emoji} **{symbol}** — {_COMPANY_NAMES.get(symbol, symbol)}  |  "
            f"Signal: **{signal}** ({conf}%)  |  "
            f"${cur:.2f} ({daily:+.1f}% today){regime_tag}"
        )

        with st.expander(label, expanded=(signal == 'BUY')):

            # ── Indicator grid ─────────────────────────────────────────────
            c1, c2, c3, c4 = st.columns(4)

            rsi = r.get('rsi', 50)
            with c1:
                rsi_delta = "🔥 Oversold" if rsi < 35 else ("⚠️ Overbought" if rsi > 68 else "Neutral")
                st.metric("RSI-14 (Wilder)", f"{rsi:.1f}", rsi_delta,
                          delta_color="normal" if rsi < 50 else "inverse")
                stoch_k = r.get('stoch_k', 50)
                stoch_d = r.get('stoch_d', 50)
                stoch_delta = "🔥 Oversold" if stoch_k < 25 else ("⚠️ Overbought" if stoch_k > 75 else "Neutral")
                st.metric("Stochastic %K/%D", f"{stoch_k:.0f}/{stoch_d:.0f}", stoch_delta,
                          delta_color="normal" if stoch_k < 50 else "inverse")

            with c2:
                st.metric("MACD", r.get('macd_direction', 'N/A'))
                vol = r.get('volume_ratio', 1.0)
                vol_delta = "High vol UP 🔥" if (vol > 1.5 and daily > 0) else \
                            ("High vol DOWN 🚨" if (vol > 1.5 and daily < 0) else \
                            ("Low volume ⚠️" if vol < 0.6 else "Normal"))
                st.metric("Volume vs 20-day avg", f"{vol:.1f}x", vol_delta,
                          delta_color="normal" if (vol > 1.5 and daily > 0) else
                                     ("inverse" if (vol > 1.5 and daily < 0) else "off"))

            with c3:
                pct_b = r.get('pct_b', 0.5)
                bb_delta = "At lower band 🔥" if pct_b < 0.1 else ("At upper band ⚠️" if pct_b > 0.9 else "Mid range")
                st.metric("Bollinger %B", f"{pct_b:.2f}", bb_delta,
                          delta_color="normal" if pct_b < 0.3 else ("inverse" if pct_b > 0.7 else "off"))
                obv = r.get('obv_slope', 0)
                obv_delta = "Accumulating 📈" if obv > 0.2 else ("Distributing 📉" if obv < -0.2 else "Flat")
                st.metric("OBV Slope", f"{obv:+.3f}", obv_delta,
                          delta_color="normal" if obv > 0 else ("inverse" if obv < 0 else "off"))

            with c4:
                st.metric("Signal Strength", f"{r.get('raw_score', 0):+.0f}")
                st.metric("Confidence", f"{conf}%")
                btc = r.get('btc_factors', {})
                if btc:
                    st.metric("BTC Today", f"{btc.get('btc_1d', 0):+.1f}%",
                              f"Signal impact: {btc.get('btc_score', 0):+d} pts")

            # ── MA / trend context ──────────────────────────────────────────
            ma_col1, ma_col2, ma_col3 = st.columns(3)
            with ma_col1:
                st.metric("vs 20-day MA", f"{r.get('pct_vs_20ma', 0):+.1f}%")
            with ma_col2:
                st.metric("vs 50-day MA", f"{r.get('pct_vs_50ma', 0):+.1f}%")
            with ma_col3:
                slope = r.get('ma50_slope', 0)
                slope_label = "Rising ✅" if slope > 1 else ("Falling ⚠️" if slope < -1 else "Flat")
                st.metric("50-MA Slope (10d)", f"{slope:+.1f}%", slope_label,
                          delta_color="normal" if slope > 0 else ("inverse" if slope < -1 else "off"))

            # ── Reasoning ──────────────────────────────────────────────────
            reasons = r.get('reasons', [])
            if reasons:
                st.markdown("**📋 Why this signal?**")
                for reason in reasons:
                    if '⚠️ Downtrend' in reason or '✅ Uptrend' in reason:
                        st.markdown(f"  {reason}")
                    elif any(w in reason for w in ['bullish', 'oversold', 'surge', 'UP day', 'rising', 'accumulating', 'cross from oversold', 'confirmed']):
                        st.markdown(f"  ✅ {reason}")
                    elif any(w in reason for w in ['bearish', 'overbought', 'DOWN day', 'distributing', 'reversal', 'extended', 'falling']):
                        st.markdown(f"  ⚠️ {reason}")
                    else:
                        st.markdown(f"  ℹ️ {reason}")

            # ── Price targets ───────────────────────────────────────────────
            pt = r.get('price_targets')
            if pt:
                st.markdown("**🎯 Price Targets (ATR-based stops)**")
                t1, t2, t3, t4 = st.columns(4)
                with t1:
                    delta_entry = (pt['entry'] - pt['current_price']) / pt['current_price'] * 100
                    st.metric("Entry Zone", f"${pt['entry']:.2f}",
                              f"{delta_entry:+.1f}% from now")
                with t2:
                    st.metric(
                        f"🛑 Stop (ATR {pt.get('atr', 0):.2f})",
                        f"${pt['stop_loss']:.2f}",
                        f"−{pt['risk_pct']:.1f}% risk",
                        delta_color="inverse",
                    )
                with t3:
                    st.metric(f"🎯 Target 1 ({pt.get('tp1_label', 'Fib')})",
                              f"${pt['take_profit_1']:.2f}",
                              f"+{pt['reward_pct_tp1']:.1f}%")
                with t4:
                    rr = pt.get('risk_reward', 0)
                    rr_label = "Excellent ✅" if rr >= 3 else ("Good" if rr >= 2 else ("Fair" if rr >= 1 else "Poor ⚠️"))
                    st.metric("Risk/Reward", f"{rr:.1f}:1", rr_label)

                t5, _, _ = st.columns(3)
                with t5:
                    st.metric(f"🎯 Target 2 ({pt.get('tp2_label', 'Fib')})",
                              f"${pt['take_profit_2']:.2f}",
                              f"+{pt['reward_pct_tp2']:.1f}%")

                if pt.get('risk_reward', 0) < 1.5:
                    st.warning("⚠️ Risk/reward below 1.5:1 — consider waiting for a better entry or skipping this trade.")
                elif pt.get('risk_pct', 0) > 12:
                    st.warning("⚠️ Stop is more than 12% away — this is a wide stop. Size your position accordingly.")
            else:
                st.info("Price targets unavailable — insufficient price history.")

    # ──────────────────────────────────────────────────────────────────────────
    # Signal strength chart
    # ──────────────────────────────────────────────────────────────────────────

    def _render_signal_strength_chart(self, results: list):
        results = [r for r in results if r.get('raw_score') is not None]
        symbols = [r['symbol'] for r in results]
        scores  = [r.get('raw_score', 0) for r in results]
        confs   = [r.get('confidence', 50) for r in results]
        colors  = [
            '#00c853' if s >= 28 else ('#d50000' if s <= -20 else '#ffd600')
            for s in scores
        ]

        hover = [
            f"<b>{sym}</b><br>Score: {s:+.0f}<br>Confidence: {c}%"
            for sym, s, c in zip(symbols, scores, confs)
        ]

        fig = go.Figure(go.Bar(
            x=symbols, y=scores,
            marker_color=colors,
            marker_line_color='rgba(255,255,255,0.3)',
            marker_line_width=1,
            text=[f"{s:+.0f}" for s in scores],
            textposition='outside',
            customdata=confs,
            hovertemplate="%{hovertext}<extra></extra>",
            hovertext=hover,
        ))

        fig.add_hline(y=28, line_dash='dot', line_color='#00c853',
                      annotation_text="BUY ≥ 28", annotation_position="right")
        fig.add_hline(y=40, line_dash='dash', line_color='#00c853', line_width=1,
                      annotation_text="BUY (downtrend) ≥ 40", annotation_position="right")
        fig.add_hline(y=-20, line_dash='dot', line_color='#d50000',
                      annotation_text="SELL ≤ -20", annotation_position="right")
        fig.add_hrect(y0=28, y1=40, fillcolor='rgba(0,200,83,0.05)', line_width=0)

        fig.update_layout(
            title="Signal Strength — 8-Factor Score  (Green=BUY · Yellow=HOLD · Red=SELL)",
            xaxis_title="Stock",
            yaxis_title="Composite Score",
            template='plotly_dark',
            height=440,
            showlegend=False,
            yaxis=dict(zeroline=True, zerolinecolor='rgba(255,255,255,0.3)'),
            margin=dict(r=160),
        )
        st.plotly_chart(fig, use_container_width=True)
