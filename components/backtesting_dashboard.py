import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from utils.backtesting_engine import BacktestingEngine

class BacktestingDashboard:
    """Professional Backtesting Dashboard - Validate strategies on historical data"""
    
    def __init__(self):
        self.engine = BacktestingEngine()
    
    def render(self, selected_stocks, stock_names):
        """Render the Backtesting Dashboard"""
        
        st.header("🔬 Strategy Backtesting Lab")
        st.write("Test and validate trading strategies on historical data before using them live")
        
        tab1, tab2, tab3 = st.tabs([
            "📊 Single Strategy Test",
            "🏆 Strategy Comparison",
            "📈 Custom Strategy Builder"
        ])
        
        with tab1:
            self._render_single_strategy_tab(selected_stocks)
        
        with tab2:
            self._render_comparison_tab(selected_stocks)
        
        with tab3:
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
