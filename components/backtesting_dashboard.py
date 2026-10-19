import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from utils.backtesting_engine import BacktestingEngine
from utils.options_backtester import OptionsBacktester

class BacktestingDashboard:
    """Professional Backtesting Dashboard - Validate strategies on historical data"""
    
    def __init__(self):
        self.engine = BacktestingEngine()
        self.options_bt = OptionsBacktester()
    
    def render(self, selected_stocks, stock_names):
        """Render the Backtesting Dashboard"""
        
        st.header("🔬 Strategy Backtesting Lab")
        st.write("Test and validate trading strategies on historical data before using them live")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Single Strategy Test",
            "🏆 Strategy Comparison",
            "📈 Options Strategies",
            "🛠️ Custom Strategy Builder"
        ])
        
        with tab1:
            self._render_single_strategy_tab(selected_stocks)
        
        with tab2:
            self._render_comparison_tab(selected_stocks)

        with tab3:
            self._render_options_backtest_tab()
        
        with tab4:
            self._render_custom_strategy_tab(selected_stocks)
    
    def _render_single_strategy_tab(self, selected_stocks):
        """Test a single strategy in detail"""
        
        st.subheader("📊 Single Strategy Backtest")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            symbol = st.selectbox("Select Stock", selected_stocks, key='single_symbol')
        
        with col2:
            strategy_type = st.selectbox(
                "Strategy Type",
                ['MA Crossover', 'RSI Mean Reversion', 'Volume Breakout', 'Momentum'],
                key='single_strategy'
            )
        
        with col3:
            lookback_months = st.selectbox(
                "Backtest Period",
                [3, 6, 12, 24],
                format_func=lambda x: f"{x} months",
                key='single_period'
            )
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_months*30)
        
        col1, col2 = st.columns(2)
        
        with col1:
            initial_capital = st.number_input(
                "Initial Capital ($)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000,
                key='single_capital'
            )
        
        st.markdown("---")
        st.subheader("⚙️ Strategy Parameters")
        
        if strategy_type == 'MA Crossover':
            col1, col2 = st.columns(2)
            with col1:
                short_window = st.slider("Short MA Window", 5, 50, 20, key='ma_short')
            with col2:
                long_window = st.slider("Long MA Window", 20, 200, 50, key='ma_long')
        
        elif strategy_type == 'RSI Mean Reversion':
            col1, col2, col3 = st.columns(3)
            with col1:
                rsi_period = st.slider("RSI Period", 5, 30, 14, key='rsi_period')
            with col2:
                oversold = st.slider("Oversold Level", 20, 40, 30, key='rsi_oversold')
            with col3:
                overbought = st.slider("Overbought Level", 60, 80, 70, key='rsi_overbought')
        
        elif strategy_type == 'Volume Breakout':
            volume_threshold = st.slider("Volume Threshold (x avg)", 1.0, 3.0, 1.5, 0.1, key='vol_threshold')
        
        else:
            lookback = st.slider("Momentum Lookback (days)", 5, 60, 20, key='mom_lookback')
        
        run_backtest = st.button("🚀 Run Backtest", key='single_run', type='primary')
        
        if run_backtest:
            with st.spinner(f"Running {strategy_type} backtest on {symbol}..."):
                
                if strategy_type == 'MA Crossover':
                    result = self.engine.test_ma_crossover_strategy(
                        symbol, start_date, end_date, short_window, long_window, initial_capital
                    )
                
                elif strategy_type == 'RSI Mean Reversion':
                    result = self.engine.test_rsi_strategy(
                        symbol, start_date, end_date, rsi_period, oversold, overbought, initial_capital
                    )
                
                elif strategy_type == 'Volume Breakout':
                    result = self.engine.test_volume_breakout_strategy(
                        symbol, start_date, end_date, volume_threshold, initial_capital
                    )
                
                else:
                    result = self.engine.test_momentum_strategy(
                        symbol, start_date, end_date, lookback, 5, initial_capital
                    )
                
                if result:
                    self._display_backtest_results(result)
                else:
                    st.error("Backtest failed. Please try different parameters.")
    
    def _display_backtest_results(self, result):
        """Display detailed backtest results"""
        
        st.markdown("---")
        st.subheader(f"📊 Results: {result['strategy_name']}")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            return_color = "🟢" if result['total_return_pct'] > 0 else "🔴"
            st.metric(
                "Total Return",
                f"{result['total_return_pct']:.2f}%",
                delta=return_color
            )
        
        with col2:
            st.metric(
                "Buy & Hold",
                f"{result['buy_hold_return_pct']:.2f}%"
            )
        
        with col3:
            outperf_color = "🟢" if result['outperformance'] > 0 else "🔴"
            st.metric(
                "Outperformance",
                f"{result['outperformance']:.2f}%",
                delta=outperf_color
            )
        
        with col4:
            st.metric(
                "Final Capital",
                f"${result['final_capital']:,.0f}"
            )
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric(
                "CAGR",
                f"{result['cagr_pct']:.2f}%"
            )
        
        with col2:
            sharpe_color = "🟢" if result['sharpe_ratio'] > 1 else "🟡" if result['sharpe_ratio'] > 0 else "🔴"
            st.metric(
                "Sharpe Ratio",
                f"{result['sharpe_ratio']:.2f}",
                delta=sharpe_color
            )
        
        with col3:
            st.metric(
                "Max Drawdown",
                f"{result['max_drawdown_pct']:.2f}%"
            )
        
        with col4:
            st.metric(
                "Win Rate",
                f"{result['win_rate_pct']:.1f}%"
            )
        
        with col5:
            st.metric(
                "Total Trades",
                result['num_trades']
            )
        
        if result['total_return_pct'] > result['buy_hold_return_pct']:
            st.success(f"✅ **Strategy OUTPERFORMED** buy-and-hold by {result['outperformance']:.2f}%!")
        else:
            st.warning(f"⚠️ **Strategy UNDERPERFORMED** buy-and-hold by {abs(result['outperformance']):.2f}%")
        
        equity_curve = result['equity_curve']
        
        fig = make_subplots(
            rows=2, cols=1,
            row_heights=[0.7, 0.3],
            subplot_titles=('Portfolio Equity Curve', 'Drawdown %'),
            vertical_spacing=0.1
        )
        
        fig.add_trace(
            go.Scatter(
                x=equity_curve['date'],
                y=equity_curve['equity'],
                name='Strategy Equity',
                line=dict(color='cyan', width=2)
            ),
            row=1, col=1
        )
        
        buy_hold_equity = (equity_curve['price'] / equity_curve['price'].iloc[0]) * result['initial_capital']
        fig.add_trace(
            go.Scatter(
                x=equity_curve['date'],
                y=buy_hold_equity,
                name='Buy & Hold',
                line=dict(color='orange', width=2, dash='dash')
            ),
            row=1, col=1
        )
        
        fig.add_trace(
            go.Scatter(
                x=equity_curve['date'],
                y=equity_curve['drawdown'],
                name='Drawdown',
                fill='tozeroy',
                line=dict(color='red', width=1)
            ),
            row=2, col=1
        )
        
        fig.update_layout(
            template='plotly_dark',
            height=600,
            showlegend=True,
            hovermode='x unified'
        )
        
        fig.update_xaxes(title_text="Date", row=2, col=1)
        fig.update_yaxes(title_text="Portfolio Value ($)", row=1, col=1)
        fig.update_yaxes(title_text="Drawdown (%)", row=2, col=1)
        
        st.plotly_chart(fig, use_container_width=True)
        
        if not result['trades'].empty:
            st.subheader("📝 Trade History")
            trades_display = result['trades'].copy()
            trades_display['price'] = trades_display['price'].apply(lambda x: f"${x:.2f}")
            trades_display['shares'] = trades_display['shares'].apply(lambda x: f"{x:.2f}")
            trades_display['capital'] = trades_display['capital'].apply(lambda x: f"${x:,.2f}")
            st.dataframe(trades_display, use_container_width=True, hide_index=True)
    
    def _render_comparison_tab(self, selected_stocks):
        """Compare multiple strategies"""
        
        st.subheader("🏆 Strategy Comparison")
        st.write("Compare all strategies on the same stock to find the best performer")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            symbol = st.selectbox("Select Stock", selected_stocks, key='comp_symbol')
        
        with col2:
            lookback_months = st.selectbox(
                "Backtest Period",
                [3, 6, 12, 24],
                format_func=lambda x: f"{x} months",
                key='comp_period'
            )
        
        with col3:
            initial_capital = st.number_input(
                "Initial Capital ($)",
                min_value=1000,
                max_value=1000000,
                value=10000,
                step=1000,
                key='comp_capital'
            )
        
        if st.button("🚀 Run All Strategies", key='comp_run', type='primary'):
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_months*30)
            
            with st.spinner("Running all strategies..."):
                results = []
                
                with st.expander("Running MA Crossover...", expanded=False):
                    result1 = self.engine.test_ma_crossover_strategy(symbol, start_date, end_date, 20, 50, initial_capital)
                    if result1: results.append(result1)
                
                with st.expander("Running RSI Mean Reversion...", expanded=False):
                    result2 = self.engine.test_rsi_strategy(symbol, start_date, end_date, 14, 30, 70, initial_capital)
                    if result2: results.append(result2)
                
                with st.expander("Running Volume Breakout...", expanded=False):
                    result3 = self.engine.test_volume_breakout_strategy(symbol, start_date, end_date, 1.5, initial_capital)
                    if result3: results.append(result3)
                
                with st.expander("Running Momentum...", expanded=False):
                    result4 = self.engine.test_momentum_strategy(symbol, start_date, end_date, 20, 5, initial_capital)
                    if result4: results.append(result4)
                
                if results:
                    comparison_df = self.engine.compare_strategies(results)
                    
                    st.subheader("📊 Strategy Performance Comparison")
                    st.dataframe(comparison_df, use_container_width=True, hide_index=True)
                    
                    best_strategy = max(results, key=lambda x: x['total_return_pct'])
                    st.success(f"🏆 **Best Strategy: {best_strategy['strategy_name']}** with {best_strategy['total_return_pct']:.2f}% return!")
                    
                    fig = go.Figure()
                    
                    for result in results:
                        fig.add_trace(go.Scatter(
                            x=result['equity_curve']['date'],
                            y=result['equity_curve']['equity'],
                            name=result['strategy_name'],
                            line=dict(width=2)
                        ))
                    
                    fig.update_layout(
                        title='All Strategies - Equity Curves',
                        xaxis_title='Date',
                        yaxis_title='Portfolio Value ($)',
                        template='plotly_dark',
                        height=500,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.error("No results available. Please try different parameters.")
    
    def _render_options_backtest_tab(self):
        """Backtest options income/protection strategies on a held stock position"""
        st.subheader("📈 Options Strategy Backtest")
        st.markdown(
            "*Simulates what you would have earned (or paid) using options on your actual position. "
            "Premiums are estimated using Black-Scholes with real historical volatility — "
            "not actual historical options prices, which aren't freely available.*"
        )

        # ── Load portfolio positions ──────────────────────────────────────────
        try:
            from components.personal_portfolio import PersonalPortfolio, DEFAULT_POSITIONS
            saved = PersonalPortfolio._load_positions()
        except Exception:
            from components.personal_portfolio import DEFAULT_POSITIONS
            saved = DEFAULT_POSITIONS

        # ── Controls ─────────────────────────────────────────────────────────
        c1, c2, c3 = st.columns(3)

        with c1:
            all_syms = list(saved.keys())
            default_idx = all_syms.index('RIOT') if 'RIOT' in all_syms else 0
            symbol = st.selectbox("Stock", all_syms, index=default_idx, key='opt_bt_sym')

        pos = saved.get(symbol, {})
        default_shares = int(pos.get('shares', 100))
        default_cb     = float(pos.get('cost_basis', 10.0))

        with c2:
            strategy = st.selectbox(
                "Strategy",
                ['Covered Call', 'Protective Put', 'Collar'],
                key='opt_bt_strat',
                help=(
                    "**Covered Call** – Sell monthly calls to collect income, capping your upside.\n\n"
                    "**Protective Put** – Buy monthly puts to floor your downside. Costs premium.\n\n"
                    "**Collar** – Sell a call + buy a put. Usually near-zero net cost."
                )
            )

        with c3:
            months = st.selectbox(
                "Backtest Period",
                [3, 6, 12, 24],
                index=2,
                format_func=lambda x: f"{x} months",
                key='opt_bt_months'
            )

        c4, c5, c6, c7 = st.columns(4)

        with c4:
            shares = st.number_input(
                "Shares", min_value=1, value=default_shares, step=100, key='opt_bt_shares'
            )
            contracts = shares // 100
            st.caption(f"= {contracts} option contracts")

        with c5:
            cost_basis = st.number_input(
                "Your Cost Basis ($)", min_value=0.01,
                value=default_cb, step=0.01, format="%.2f", key='opt_bt_cb'
            )

        with c6:
            call_otm = st.slider(
                "Call OTM %", 5, 30, 10, key='opt_bt_call_otm',
                help="How far above current price the call strike is. Higher = more upside room, lower premium."
            ) / 100

        with c7:
            put_otm = st.slider(
                "Put OTM %", 5, 20, 10, key='opt_bt_put_otm',
                help="How far below current price the put strike is (floor). Only used for Put/Collar."
            ) / 100

        run_btn = st.button("▶ Run Options Backtest", type="primary", key='opt_bt_run')
        if not run_btn:
            st.info("Configure your position above and click **Run Options Backtest** to start.")
            return

        # ── Run backtest ──────────────────────────────────────────────────────
        strat_key = {
            'Covered Call':   'covered_call',
            'Protective Put': 'protective_put',
            'Collar':         'collar',
        }[strategy]

        with st.spinner(f"Running {strategy} backtest on {months} months of {symbol} history…"):
            result = self.options_bt.run(
                symbol=symbol, shares=shares, cost_basis=cost_basis,
                strategy=strat_key, months=months,
                call_otm_pct=call_otm, put_otm_pct=put_otm, dte=30,
            )

        if result is None:
            st.error(f"Could not fetch price data for {symbol}. Please try again.")
            return

        self._display_options_results(result, strategy, symbol, shares, cost_basis)

    def _display_options_results(self, r, strategy, symbol, shares, cost_basis):
        """Render the full options backtest result"""
        st.divider()

        # ── Headline metrics ──────────────────────────────────────────────────
        is_income  = strategy in ('Covered Call', 'Collar')
        net_income   = r['net_income']    # true edge: premiums minus missed upside
        gross_income = r['gross_income']  # raw premiums collected/paid

        st.subheader(f"📊 {symbol} — {strategy} Results ({r['num_cycles']} monthly cycles)")

        m1, m2, m3, m4, m5 = st.columns(5)

        if is_income:
            m1.metric(
                "💰 Gross Premiums Collected",
                f"${gross_income:,.0f}",
                help="Total option premiums received from selling calls (Black-Scholes estimate). "
                     "Does NOT yet account for upside capped on assignment cycles."
            )
            m2.metric(
                "📅 Annual Yield",
                f"{r['annual_yield_pct']:.1f}%",
                help="Gross premiums as % of starting position value, annualized"
            )
        else:
            m1.metric(
                "💸 Total Put Cost",
                f"${abs(gross_income):,.0f}",
                help="Total premiums paid for protective puts (Black-Scholes estimate)"
            )
            payoff = r['extra'].get('Total Put Payoff', 0)
            m2.metric(
                "🛡️ Total Protection Payoff",
                f"${payoff:,.0f}",
                help="Actual cash received when puts triggered"
            )

        m3.metric(
            "🔄 Cycles Run",
            r['num_cycles'],
            help="Number of monthly option cycles completed"
        )

        event_label = {
            'Covered Call':   f"Assignments",
            'Protective Put': f"Puts Triggered",
            'Collar':         f"Assignments",
        }[strategy]
        m4.metric(event_label, r['event_count'])

        m5.metric(
            "📊 Stock Move",
            f"{r['start_price']:.2f} → {r['final_price']:.2f}",
            delta=f"{((r['final_price']/r['start_price'])-1)*100:+.1f}%"
        )

        # ── P&L comparison ────────────────────────────────────────────────────
        st.markdown("### 📈 Strategy vs Buy & Hold")
        p1, p2, p3 = st.columns(3)

        p1.metric(
            "Buy & Hold P&L",
            f"${r['bah_pnl']:,.0f}",
            delta=f"{r['bah_return_pct']:+.1f}%"
        )
        p2.metric(
            f"{strategy} Total P&L",
            f"${r['strategy_pnl']:,.0f}",
            delta=f"{r['strategy_return_pct']:+.1f}%"
        )
        edge = r['strategy_edge']
        p3.metric(
            "Options Edge vs B&H",
            f"${edge:+,.0f}",
            delta="More than B&H" if edge > 0 else "Less than B&H",
            delta_color="normal" if edge > 0 else "inverse"
        )

        # ── Extra strategy metrics ────────────────────────────────────────────
        if r['extra']:
            ex_cols = st.columns(len(r['extra']))
            for i, (k, v) in enumerate(r['extra'].items()):
                ex_cols[i].metric(k, f"${v:,.0f}" if isinstance(v, (int, float)) and abs(v) > 10 else str(v))

        st.divider()

        # ── Charts ────────────────────────────────────────────────────────────
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            # Dual cumulative chart: gross premiums vs net cycle impact
            fig_inc = go.Figure()
            date_strs = [str(d) for d in r['cum_dates']]

            if is_income:
                # Show gross premiums (what you collected) and net (after assignment cap)
                fig_inc.add_trace(go.Scatter(
                    x=date_strs, y=r['cum_gross'],
                    mode='lines+markers', name='Gross Premiums Collected',
                    line=dict(color='#00cc88', width=2, dash='dot'),
                    marker=dict(size=5),
                ))
                fig_inc.add_trace(go.Scatter(
                    x=date_strs, y=r['cum_income'],
                    mode='lines+markers', name='Net Impact (after assignments)',
                    line=dict(color='#3399ff', width=2.5),
                    marker=dict(size=6),
                    fill='tozeroy',
                    fillcolor='rgba(51,153,255,0.10)',
                ))
                chart_title = "Gross Premiums vs Net Impact"
            else:
                fig_inc.add_trace(go.Scatter(
                    x=date_strs, y=r['cum_income'],
                    mode='lines+markers', name='Cumulative Net Protection Value',
                    line=dict(color='#ff9944', width=2.5),
                    marker=dict(size=6),
                    fill='tozeroy',
                    fillcolor='rgba(255,153,68,0.12)',
                ))
                chart_title = "Cumulative Net Protection Value"

            fig_inc.add_hline(y=0, line_color='white', line_dash='dash', opacity=0.25)
            fig_inc.update_layout(
                title=chart_title,
                xaxis_title="Cycle Date", yaxis_title="$ Amount",
                template='plotly_dark', height=320, hovermode='x unified',
                margin=dict(l=0, r=0, t=40, b=0),
                legend=dict(orientation='h', yanchor='bottom', y=1.02),
            )
            st.plotly_chart(fig_inc, use_container_width=True)

        with chart_col2:
            # P&L comparison chart
            price_dates = [str(d)[:10] for d in r['price_dates']]
            prices      = r['prices']
            bah_values  = [(p - cost_basis) * shares for p in prices]

            # Build options cumulative at each date
            # Map cycle dates → cumulative income at that point
            cum_map = dict(zip(r['cum_dates'], r['cum_income']))
            opts_values = []
            last_cum = 0.0
            for d, p in zip(r['price_dates'], prices):
                day = d.date() if hasattr(d, 'date') else d
                if day in cum_map:
                    last_cum = cum_map[day]
                stock_pnl = (p - cost_basis) * shares
                opts_values.append(stock_pnl + last_cum)

            fig_pnl = go.Figure()
            fig_pnl.add_trace(go.Scatter(
                x=price_dates, y=bah_values,
                mode='lines', name='Buy & Hold P&L',
                line=dict(color='#888888', width=2, dash='dot'),
            ))
            fig_pnl.add_trace(go.Scatter(
                x=price_dates, y=opts_values,
                mode='lines', name=f'{strategy} P&L',
                line=dict(color='#3399ff', width=2.5),
            ))
            fig_pnl.add_hline(y=0, line_color='white', line_dash='dash', opacity=0.3)
            fig_pnl.update_layout(
                title="Total P&L: Options Strategy vs Buy & Hold",
                xaxis_title="Date", yaxis_title="Total P&L ($)",
                template='plotly_dark', height=320, hovermode='x unified',
                margin=dict(l=0, r=0, t=40, b=0),
            )
            st.plotly_chart(fig_pnl, use_container_width=True)

        # ── Monthly bar chart ─────────────────────────────────────────────────
        trades_df = r['trades_df']
        cycle_col = 'Total Premium' if 'Total Premium' in trades_df.columns else \
                    'Net Position ($)' if 'Net Position ($)' in trades_df.columns else \
                    'Cycle Net ($)'

        fig_bar = go.Figure()
        bar_vals  = trades_df['Cycle Net ($)'].tolist()
        bar_dates = [str(d) for d in trades_df['Entry Date'].tolist()]
        bar_colors = ['#00cc88' if v >= 0 else '#ff4444' for v in bar_vals]

        fig_bar.add_trace(go.Bar(
            x=bar_dates, y=bar_vals,
            marker_color=bar_colors,
            name='Cycle Net P&L',
        ))
        fig_bar.add_hline(y=0, line_color='white', opacity=0.3)
        fig_bar.update_layout(
            title="Per-Cycle Net P&L",
            xaxis_title="Entry Date", yaxis_title="$ Net",
            template='plotly_dark', height=280,
            margin=dict(l=0, r=0, t=40, b=0),
        )
        st.plotly_chart(fig_bar, use_container_width=True)

        # ── Trade log ─────────────────────────────────────────────────────────
        st.markdown("### 📋 Trade-by-Trade Log")
        st.caption(
            "Premiums estimated using Black-Scholes with 30-day realized volatility. "
            "'Cycle Net' = premium income minus any capped upside or net of put payoff."
        )
        st.dataframe(trades_df, use_container_width=True, hide_index=True)

        # ── Key takeaway ──────────────────────────────────────────────────────
        n_cyc   = r['num_cycles']
        n_ev    = r['event_count']
        ann_y   = r['annual_yield_pct']
        assign_rate = round(n_ev / n_cyc * 100) if n_cyc > 0 else 0

        edge      = r['strategy_edge']
        edge_word = "outperformed" if edge > 0 else "underperformed"

        if strategy == 'Covered Call':
            st.info(
                f"**Over {n_cyc} monthly cycles:** collected **${gross_income:,.0f}** in gross premiums "
                f"(**{ann_y:.1f}%/yr yield**). Shares were called away {n_ev} times "
                f"({assign_rate}% assignment rate). After accounting for capped upside on assignment "
                f"cycles, the strategy **{edge_word}** buy-and-hold by **${abs(edge):,.0f}** "
                f"({'more' if edge > 0 else 'less'} total profit). "
                f"⚠️ *Covered calls shine in flat/slightly rising markets — in strong bull runs like "
                f"this one, they cap your gains.*"
            )
        elif strategy == 'Protective Put':
            net_prot = r['extra'].get('Net Protection Value', 0)
            st.info(
                f"**Over {n_cyc} monthly cycles:** paid **${abs(gross_income):,.0f}** in put premiums. "
                f"Puts triggered {n_ev} times ({assign_rate}% of cycles), "
                f"paying out **${r['extra'].get('Total Put Payoff',0):,.0f}**. "
                f"Net protection value: **${net_prot:,.0f}** "
                f"({'insurance paid off' if net_prot > 0 else 'net cost — insurance that was not fully needed'}). "
                f"Strategy vs buy-and-hold: **${edge:+,.0f}**."
            )
        elif strategy == 'Collar':
            net_prem_word = 'credit' if gross_income >= 0 else 'debit'
            st.info(
                f"**Over {n_cyc} monthly cycles:** net option premium **${gross_income:+,.0f}** ({net_prem_word}). "
                f"Call assigned {n_ev} times, put triggered {r['extra'].get('Put Triggers',0)} times. "
                f"After all outcomes, strategy **{edge_word}** buy-and-hold by **${abs(edge):,.0f}**."
            )

    def _render_custom_strategy_tab(self, selected_stocks):
        """Custom strategy builder (placeholder for future)"""
        
        st.subheader("📈 Custom Strategy Builder")
        st.info("🚧 **Coming Soon!** Build your own custom strategies using multiple indicators")
        
        st.write("""
        **Future Features:**
        - Combine multiple technical indicators
        - Set custom entry/exit rules
        - Add position sizing rules
        - Risk management integration
        - Walk-forward optimization
        """)
        
        st.write("For now, use the pre-built strategies in the other tabs!")
