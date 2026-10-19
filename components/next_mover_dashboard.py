"""
Next Mover Prediction Dashboard
Identifies which mining stock will run next based on multi-factor analysis
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from utils.next_mover_engine import NextMoverEngine


class NextMoverDashboard:
    """Dashboard for predicting which mining stock will move next"""
    
    def __init__(self):
        self.engine = NextMoverEngine()
    
    def render(self, data_fetcher, options_analyzer):
        """Render the Next Mover Prediction dashboard"""
        st.title("🎯 Next Mover Prediction Engine")
        st.markdown("*Which mining stock has the best setup to move next?*")

        # Get predictions
        with st.spinner("Fetching live market data for all 9 stocks…"):
            rankings = self.engine.calculate_composite_score()
            top_pick = self.engine.get_top_pick()

        if rankings.empty:
            st.error("Unable to fetch market data. Please try again.")
            return

        # ── Data quality banner ───────────────────────────────────────────────
        any_sent_live = rankings['Sentiment Live'].any() if 'Sentiment Live' in rankings.columns else False
        if any_sent_live:
            st.success("✅ All data sources live — Technical, Relative Strength, BTC Correlation, and News Sentiment are from real-time data.")
        else:
            st.warning(
                "⚠️ **News Sentiment is unavailable** (Alpha Vantage free-tier limit reached for today). "
                "Sentiment is shown as Neutral (50) for all stocks — it does not affect the relative ranking "
                "since every stock gets the same default. The other 3 factors (Relative Strength, Technical, BTC) "
                "are fully live."
            )

        # ── How scores work ───────────────────────────────────────────────────
        with st.expander("📖 How the score is calculated"):
            st.markdown("""
            Each stock is scored 0–100 across four factors, then blended into a **composite score**:

            | Factor | Weight | What it measures |
            |--------|--------|-----------------|
            | 🎯 Relative Strength | **30%** | How far behind the sector average the stock is — laggards tend to catch up |
            | 📈 Technical Setup | **40%** | RSI position, MACD direction & momentum, price vs 20/50-day moving averages, volume |
            | ₿ BTC Correlation | **15%** | Whether the stock's beta to Bitcoin is an advantage given where BTC is trending |
            | 📰 News Sentiment | **15%** | Average sentiment score of recent news articles (Alpha Vantage) |

            **Score guide:**
            - **70+** — Strong setup, multiple signals aligned
            - **60–69** — Decent setup, worth watching
            - **50–59** — Neutral / mixed signals
            - **Below 50** — Overbought or lagging on most factors

            > Scores are *relative to each other* — the point is to rank the 9 stocks, not predict an absolute outcome.
            """)

        st.divider()

        # ── Top pick highlight ────────────────────────────────────────────────
        st.subheader("🏆 Best Setup Right Now")

        if top_pick:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Stock", top_pick['symbol'])
                if top_pick.get('current_price'):
                    st.metric("Price", f"${top_pick['current_price']:.2f}")
            with col2:
                st.metric("Composite Score", f"{top_pick['score']:.1f} / 100")
                score = top_pick['score']
                conf = ("🔥 Strong" if score >= 70 else
                        "✅ Decent"  if score >= 60 else
                        "⚠️ Neutral" if score >= 50 else
                        "❌ Weak")
                st.metric("Signal Strength", conf)
            with col3:
                st.metric("RSI", f"{top_pick['rsi']:.0f}")
                gap = top_pick.get('performance_gap', 0)
                st.metric("Behind Sector Avg", f"{gap:+.1f}%",
                          delta="catch-up candidate" if gap > 3 else "near average",
                          delta_color="normal")
            with col4:
                top_row = rankings[rankings['Symbol'] == top_pick['symbol']]
                if not top_row.empty:
                    rs  = top_row['RS Score'].iloc[0]
                    tec = top_row['Tech Score'].iloc[0]
                    btc = top_row['BTC Score'].iloc[0]
                    st.metric("Rel. Strength", f"{rs:.0f}/100")
                    st.metric("Technical", f"{tec:.0f}/100")

            st.info(f"**Why {top_pick['symbol']}?** {top_pick['signals']}")

        st.divider()

        # Create tabs for different views
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Full Rankings",
            "📅 Earnings Calendar",
            "📈 Performance Chart",
            "🔬 Factor Analysis",
            "📚 How Rotation Works"
        ])

        with tab1:
            self._render_rankings(rankings)

        with tab2:
            self._render_earnings_calendar()

        with tab3:
            self._render_performance_chart()

        with tab4:
            self._render_factor_analysis(rankings)

        with tab5:
            self._render_historical_analysis()
    
    def _render_rankings(self, rankings):
        """Display full stock rankings with clear per-stock score breakdown"""
        st.subheader("📊 All 9 Stocks — Score Breakdown")

        any_sent_live = rankings['Sentiment Live'].any() if 'Sentiment Live' in rankings.columns else False

        for _, row in rankings.iterrows():
            rank    = int(row['Rank'])
            symbol  = row['Symbol']
            score   = float(row['Score'])
            rs      = float(row['RS Score'])
            tec     = float(row['Tech Score'])
            btc     = float(row['BTC Score'])
            sent    = float(row['Sentiment Score']) if 'Sentiment Score' in row else 50.0
            sent_live = bool(row.get('Sentiment Live', False))
            rsi_val  = float(row['RSI'])
            gap      = float(row['Performance Gap'])
            tech_sigs = row.get('Tech Signals', [])
            btc_sig   = row.get('BTC Signal', '')
            sent_lbl  = row.get('Sent Label', 'Neutral')

            # Rank medal
            medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(rank, f"#{rank}")

            # Score colour
            if score >= 70:
                bar_colour = "🟢"
            elif score >= 55:
                bar_colour = "🟡"
            else:
                bar_colour = "🔴"

            with st.expander(f"{medal} **{symbol}** — Composite Score: **{score:.1f}/100** {bar_colour}", expanded=(rank <= 3)):

                col1, col2, col3, col4 = st.columns(4)

                with col1:
                    st.metric(
                        "🎯 Relative Strength",
                        f"{rs:.0f}/100",
                        help="High = stock is lagging sector and likely to catch up"
                    )
                    catchup = f"Behind avg by {gap:.1f}%" if gap > 0 else f"Ahead of avg by {abs(gap):.1f}%"
                    st.caption(catchup)

                with col2:
                    st.metric(
                        "📈 Technical Setup",
                        f"{tec:.0f}/100",
                        help="RSI position, MACD momentum, price vs moving averages, volume"
                    )
                    st.caption(f"RSI {rsi_val:.0f}")
                    if tech_sigs:
                        for sig in tech_sigs[:2]:
                            st.caption(f"• {sig}")

                with col3:
                    st.metric(
                        "₿ BTC Correlation",
                        "n/a" if pd.isna(btc) else f"{btc:.0f}/100",
                        help="Score based on this stock's 3-month beta to Bitcoin relative to the current BTC trend. "
                             "'n/a' = not enough overlapping trading days; the composite then re-weights the other factors."
                    )
                    if btc_sig:
                        st.caption(f"• {btc_sig}")

                with col4:
                    sent_label_display = (
                        f"{sent_lbl} ({sent:.0f}/100)"
                        if sent_live
                        else "Neutral — no data today"
                    )
                    st.metric(
                        "📰 Sentiment",
                        sent_label_display,
                        help="Alpha Vantage news sentiment. Shows 'Neutral' when daily API limit is reached."
                    )
                    if not sent_live:
                        st.caption("⚠️ API limit — defaulted to 50")

                # Composite bar
                bar_pct = int(score)
                filled  = "█" * (bar_pct // 5)
                empty   = "░" * (20 - bar_pct // 5)
                st.caption(f"Composite  {filled}{empty}  {score:.1f}/100  (RS×30% + Tech×40% + BTC×15% + Sent×15%)")
    
    def _render_earnings_calendar(self):
        """Earnings dates, EPS history, and price reaction for all 9 stocks"""
        st.subheader("📅 Earnings Calendar & Price Reaction")
        st.markdown("*Next report dates, analyst estimates vs actual EPS, and how the stock moved after each report*")

        with st.spinner("Loading earnings data for all 9 stocks…"):
            earnings_data = self.engine.get_earnings_data()

        if not earnings_data:
            st.error("Could not load earnings data.")
            return

        # ── Summary table ────────────────────────────────────────────────────
        today = pd.Timestamp.now().date()
        summary_rows = []
        for e in earnings_data:
            sym = e['symbol']
            nd  = e['next_date']
            du  = e['days_until']
            hist = e['history']

            # Urgency flag
            if du is not None and du <= 14:
                urgency = "🔴 <2 weeks"
            elif du is not None and du <= 30:
                urgency = "🟡 <30 days"
            elif du is not None:
                urgency = "🟢 30+ days"
            else:
                urgency = "❓ Unknown"

            last = hist[0] if hist else {}
            prev = hist[1] if len(hist) > 1 else {}

            def fmt_react(h):
                r = h.get('reaction_pct')
                if r is None:
                    return "—"
                arrow = "▲" if r >= 0 else "▼"
                return f"{arrow}{abs(r):.1f}%"

            def fmt_surp(h):
                s = h.get('surprise_pct')
                if s is None:
                    return "—"
                arrow = "✅" if s > 0 else "❌"
                return f"{arrow} {s:+.0f}%"

            summary_rows.append({
                'Stock':            sym,
                'Next Earnings':    str(nd) if nd else "—",
                'Days Away':        du if du is not None else "—",
                'Timing':           urgency,
                'Last EPS Surprise': fmt_surp(last),
                'Last Price React':  fmt_react(last),
                'Prev EPS Surprise': fmt_surp(prev),
                'Prev Price React':  fmt_react(prev),
            })

        summary_df = pd.DataFrame(summary_rows)

        # Sort by days_until so soonest is first
        def sort_key(x):
            return x if isinstance(x, int) else 9999
        summary_df['_sort'] = summary_df['Days Away'].apply(sort_key)
        summary_df = summary_df.sort_values('_sort').drop(columns='_sort').reset_index(drop=True)

        st.dataframe(summary_df, use_container_width=True, hide_index=True)

        st.caption("**Price Reaction** = next trading day's close vs close before the report  ·  **EPS Surprise** = actual vs analyst estimate")
        st.divider()

        # ── Per-stock detail cards ────────────────────────────────────────────
        st.markdown("### 🔍 Detailed Earnings History per Stock")

        # Sort same as table — soonest first
        sorted_data = sorted(
            earnings_data,
            key=lambda x: x['days_until'] if x['days_until'] is not None else 9999
        )

        for e in sorted_data:
            sym    = e['symbol']
            nd     = e['next_date']
            du     = e['days_until']
            hist   = e['history']

            du_str = f"{du} days" if du is not None else "date unknown"
            next_str = f"{nd}  ({du_str})" if nd else "Not scheduled"

            with st.expander(f"**{sym}** — Next report: {next_str}", expanded=False):

                if not hist:
                    st.info("No historical earnings data available.")
                    continue

                # ── Analyst consensus for next report ───────────────────────
                try:
                    ticker = yf.Ticker(sym)
                    cal    = ticker.calendar or {}
                    eps_hi  = cal.get('Earnings High')
                    eps_lo  = cal.get('Earnings Low')
                    eps_avg = cal.get('Earnings Average')
                    rev_avg = cal.get('Revenue Average')

                    if any(v is not None for v in [eps_avg, eps_hi, eps_lo]):
                        st.markdown("**📊 Analyst Estimates for Next Report:**")
                        c1, c2, c3, c4 = st.columns(4)
                        if eps_avg is not None:
                            c1.metric("EPS (consensus)", f"${eps_avg:.3f}")
                        if eps_lo is not None:
                            c2.metric("EPS (low)",       f"${eps_lo:.3f}")
                        if eps_hi is not None:
                            c3.metric("EPS (high)",      f"${eps_hi:.3f}")
                        if rev_avg is not None:
                            c4.metric("Revenue (est.)",  f"${rev_avg/1e6:.1f}M")
                        st.divider()
                except Exception:
                    pass

                # ── Past earnings cards ──────────────────────────────────────
                st.markdown("**📜 Recent Earnings Reports:**")
                cols = st.columns(min(len(hist), 3))

                for i, h in enumerate(hist[:3]):
                    with cols[i]:
                        date_str = str(h['date'])
                        beat = h.get('beat')
                        beat_icon = "✅ Beat" if beat else ("❌ Miss" if beat is False else "—")

                        st.markdown(f"**{date_str}**")
                        st.markdown(f"{beat_icon}")

                        eps_est = h.get('eps_est')
                        eps_act = h.get('eps_act')
                        surp    = h.get('surprise_pct')

                        if eps_est is not None:
                            st.metric("EPS Est.", f"${eps_est:.2f}")
                        if eps_act is not None:
                            color_delta = (eps_act - eps_est) if eps_est is not None else 0
                            st.metric("Actual EPS", f"${eps_act:.2f}",
                                      delta=f"{color_delta:+.2f}" if eps_est is not None else None)
                        if surp is not None:
                            st.metric("Surprise", f"{surp:+.1f}%")

                        react = h.get('reaction_pct')
                        p_bef  = h.get('price_before')
                        p_aft  = h.get('price_after')
                        if react is not None:
                            st.metric(
                                "Price Reaction",
                                f"{react:+.1f}%",
                                delta=f"${p_bef:.2f} → ${p_aft:.2f}" if p_bef and p_aft else None,
                                delta_color="normal"
                            )

                # ── Mini price-reaction chart for past 3 earnings ────────────
                if len(hist) >= 2:
                    try:
                        ticker_hist = yf.Ticker(sym).history(period='2y')
                        if not ticker_hist.empty:
                            ticker_hist.index = pd.to_datetime(ticker_hist.index).tz_localize(None).normalize()
                            ticker_hist = ticker_hist[~ticker_hist.index.duplicated(keep='last')]

                            fig = go.Figure()

                            # Full price line
                            fig.add_trace(go.Scatter(
                                x=ticker_hist.index,
                                y=ticker_hist['Close'],
                                mode='lines',
                                name=sym,
                                line=dict(color='#888', width=1.5),
                                showlegend=False,
                            ))

                            # Mark each earnings date
                            for h in hist[:3]:
                                earn_ts = pd.Timestamp(str(h['date']))
                                # Find nearest close
                                idx = ticker_hist.index.searchsorted(earn_ts)
                                if idx >= len(ticker_hist):
                                    idx = len(ticker_hist) - 1
                                price_at = ticker_hist['Close'].iloc[idx]
                                react    = h.get('reaction_pct')
                                colour   = '#00cc88' if (react or 0) >= 0 else '#ff4444'
                                label    = (f"Earnings {h['date']}<br>"
                                            f"EPS: {h.get('eps_act','?'):.2f} vs est {h.get('eps_est','?'):.2f}<br>"
                                            f"Reaction: {react:+.1f}%" if react is not None else f"Earnings {h['date']}")

                                fig.add_trace(go.Scatter(
                                    x=[earn_ts],
                                    y=[price_at],
                                    mode='markers',
                                    marker=dict(size=12, color=colour,
                                                symbol='triangle-up' if (react or 0) >= 0 else 'triangle-down'),
                                    name='Earnings',
                                    hovertext=label,
                                    hoverinfo='text',
                                    showlegend=False,
                                ))

                                # Vertical dashed line at earnings
                                fig.add_vline(
                                    x=earn_ts,
                                    line_dash='dot',
                                    line_color=colour,
                                    opacity=0.5,
                                )

                            # Mark next earnings if within 90 days
                            if nd and du is not None and du <= 90:
                                fig.add_vline(
                                    x=pd.Timestamp(str(nd)),
                                    line_dash='dash',
                                    line_color='#ffaa00',
                                    opacity=0.8,
                                    annotation_text=f"Next: {nd}",
                                    annotation_position="top right",
                                )

                            fig.update_layout(
                                title=f"{sym} — Price with Earnings Events",
                                xaxis_title="Date",
                                yaxis_title="Price ($)",
                                template='plotly_dark',
                                height=320,
                                margin=dict(l=0, r=0, t=40, b=0),
                            )
                            st.plotly_chart(fig, use_container_width=True)
                    except Exception:
                        pass

    def _render_performance_chart(self):
        """Render comparative performance chart (like screenshot)"""
        st.subheader("📈 Comparative Performance Chart - All Mining Stocks")
        st.markdown("*Normalized to 100 at start - shows which stocks are leading/lagging*")
        
        # Get performance data
        period = st.selectbox("Time Period", ['1M', '3M', '6M', '1Y'], index=1, key='perf_period')
        
        with st.spinner("Loading performance data..."):
            perf_data = self.engine.get_comparative_performance(period=period)
        
        if perf_data.empty:
            st.warning("Unable to fetch performance data")
            return
        
        # Create the chart (like the screenshot)
        fig = go.Figure()
        
        # Color mapping for stocks
        colors = {
            'RIOT': '#3366FF',   # Blue
            'MARA': '#FF6633',   # Orange  
            'CLSK': '#33CC33',   # Green
            'HUT': '#FF3366',    # Pink/Red
            'IREN': '#FFCC00',   # Yellow/Gold
            'KEEL': '#9933FF',   # Purple
            'BTBT': '#00CCCC',   # Cyan
            'WULF': '#FF9933',   # Light Orange
            'CIFR': '#66CCFF'    # Light Blue
        }
        
        for symbol in perf_data.columns:
            fig.add_trace(go.Scatter(
                x=perf_data.index,
                y=perf_data[symbol],
                mode='lines',
                name=symbol,
                line=dict(color=colors.get(symbol, '#888888'), width=2.5),
                hovertemplate=f'{symbol}: %{{y:.1f}}<extra></extra>'
            ))
        
        # Update layout to match screenshot style
        fig.update_layout(
            title=f"Mining Stock Performance Comparison ({period})",
            xaxis_title="Date",
            yaxis_title="Normalized Performance (Start = 100)",
            hovermode='x unified',
            template='plotly_dark',
            height=600,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="right",
                x=1.15
            ),
            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)')
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Performance summary
        st.markdown("### 🏆 Performance Summary")
        col1, col2 = st.columns(2)
        
        with col1:
            # Leaders
            latest_values = perf_data.iloc[-1].sort_values(ascending=False)
            st.markdown("**Top Performers:**")
            for i, (symbol, value) in enumerate(latest_values.head(3).items(), 1):
                change = value - 100
                st.write(f"{i}. **{symbol}**: {change:+.1f}% 🚀")
        
        with col2:
            # Laggards
            st.markdown("**Laggards (Catch-up Potential):**")
            for i, (symbol, value) in enumerate(latest_values.tail(3).items(), 1):
                change = value - 100
                st.write(f"{i}. **{symbol}**: {change:+.1f}% 🎯")
    
    def _render_factor_analysis(self, rankings):
        """Detailed breakdown of each factor"""
        st.subheader("🔬 Multi-Factor Analysis Breakdown")
        
        # Create factor comparison chart
        fig = go.Figure()
        
        symbols = rankings['Symbol'].tolist()
        
        fig.add_trace(go.Bar(
            name='Relative Strength',
            x=symbols,
            y=rankings['RS Score'],
            marker_color='#3366FF'
        ))
        
        fig.add_trace(go.Bar(
            name='Technical Setup',
            x=symbols,
            y=rankings['Tech Score'],
            marker_color='#FF6633'
        ))
        
        fig.add_trace(go.Bar(
            name='Bitcoin Correlation',
            x=symbols,
            y=rankings['BTC Score'],
            marker_color='#33CC33'
        ))

        if 'Sentiment Score' in rankings.columns:
            fig.add_trace(go.Bar(
                name='Sentiment',
                x=symbols,
                y=rankings['Sentiment Score'],
                marker_color='#FF33CC'
            ))

        fig.update_layout(
            title="Factor Scores by Stock (RS 30% · Technical 40% · BTC 15% · Sentiment 15%)",
            xaxis_title="Stock",
            yaxis_title="Score (0-100)",
            barmode='group',
            template='plotly_dark',
            height=500
        )

        st.plotly_chart(fig, use_container_width=True)

        # Factor explanations
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.markdown("""
            **🎯 Relative Strength (30%)**
            - Identifies underperformers
            - Mean reversion play
            - Laggards tend to catch up
            """)

        with col2:
            st.markdown("""
            **📈 Technical Setup (40%)**
            - RSI oversold signals
            - MACD crossovers
            - Real volume breakouts
            """)

        with col3:
            st.markdown("""
            **₿ Bitcoin Beta (15%)**
            - Correlation to BTC
            - High beta in rallies
            - Defensive in drops
            """)

        with col4:
            st.markdown("""
            **📰 Sentiment (15%)**
            - Alpha Vantage news score
            - Bullish/Bearish/Neutral
            - Contrarian signal at extremes
            """)
    
    def _render_historical_analysis(self):
        """Show real sector rotation data computed from live price history"""
        st.subheader("📚 Sector Rotation — Live Historical Analysis")
        st.markdown("*All figures computed from real price data, not estimates*")

        period_choice = st.selectbox(
            "Look-back window", ["1M", "3M", "6M", "1Y"], index=2,
            key="rotation_period"
        )

        with st.spinner("Computing rotation data from live prices…"):
            try:
                perf = self.engine.get_comparative_performance(period=period_choice)
            except Exception:
                perf = pd.DataFrame()

        if perf.empty:
            st.error("Could not load price data. Please refresh.")
            return

        # ── Current leaders vs laggards ───────────────────────────────────────
        latest = perf.iloc[-1]
        pct_changes = (latest - 100).sort_values(ascending=False)

        st.markdown("### 📊 Actual Performance This Period")
        cols = st.columns(len(pct_changes))
        for i, (sym, chg) in enumerate(pct_changes.items()):
            icon = "🚀" if i < 3 else ("🐢" if i >= len(pct_changes) - 3 else "➡️")
            cols[i].metric(f"{icon} {sym}", f"{chg:+.1f}%")

        st.divider()

        # ── Leader / Laggard table (real data) ───────────────────────────────
        st.markdown("### 🔄 Real Rotation Rankings")

        rotation_rows = []
        avg_perf = float(pct_changes.mean())
        for rank, (sym, chg) in enumerate(pct_changes.items(), 1):
            gap = chg - avg_perf
            if rank <= 3:
                role = "🏆 Leader"
            elif rank >= len(pct_changes) - 2:
                role = "🎯 Laggard (catch-up candidate)"
            else:
                role = "➡️ Middle of pack"
            rotation_rows.append({
                "Rank":       rank,
                "Stock":      sym,
                f"Return ({period_choice})": f"{chg:+.1f}%",
                "vs Sector Avg": f"{gap:+.1f}%",
                "Role":       role,
            })

        rotation_df = pd.DataFrame(rotation_rows)
        st.dataframe(rotation_df, use_container_width=True, hide_index=True)

        # ── Rolling 20-day spread (leaders vs laggards) ───────────────────────
        st.markdown("### 📈 Rolling Gap: Top 3 Leaders vs Bottom 3 Laggards")
        st.caption("When the gap is wide, laggards have the most catch-up potential")

        if len(perf) >= 20:
            rolling_leaders  = perf[pct_changes.index[:3]].mean(axis=1)
            rolling_laggards = perf[pct_changes.index[-3:]].mean(axis=1)
            spread = rolling_leaders - rolling_laggards

            fig_spread = go.Figure()
            fig_spread.add_trace(go.Scatter(
                x=spread.index, y=spread.values,
                mode='lines', name='Leader–Laggard Spread',
                fill='tozeroy',
                line=dict(color='#ffaa00', width=2),
                fillcolor='rgba(255,170,0,0.15)',
            ))
            fig_spread.add_hline(y=float(spread.mean()), line_dash="dot",
                                 line_color="white", opacity=0.4,
                                 annotation_text="Average spread")
            fig_spread.update_layout(
                xaxis_title="Date",
                yaxis_title="Performance gap (pp)",
                template='plotly_dark', height=300,
                margin=dict(l=0, r=0, t=10, b=0),
            )
            st.plotly_chart(fig_spread, use_container_width=True)

        # ── What the data says now ────────────────────────────────────────────
        top3    = ", ".join(pct_changes.index[:3].tolist())
        bottom3 = ", ".join(pct_changes.index[-3:].tolist())
        top_avg    = pct_changes.iloc[:3].mean()
        bottom_avg = pct_changes.iloc[-3:].mean()
        current_spread = top_avg - bottom_avg

        st.info(
            f"**Right now ({period_choice}):** {top3} are the leaders (+{top_avg:.1f}% avg).  "
            f"{bottom3} are the laggards ({bottom_avg:+.1f}% avg).  "
            f"The spread is **{current_spread:.1f} percentage points** — "
            + ("a wide gap means laggards have strong catch-up potential." if current_spread > 20
               else "a moderate gap — rotation may already be underway.")
        )
