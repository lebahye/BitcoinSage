"""
components/risk_center.py
Merged from: risk_management.py + risk_dashboard.py
RiskCenter combines position-sizing/risk-alerts with quantitative risk metrics (VaR, Monte Carlo, etc.)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from utils.risk_engine import RiskEngine
from utils.unified_data_fetcher import DataFetcher


class RiskCenter:
    """Unified Risk Center — position sizing, alerts, VaR, Monte Carlo, Beta analysis"""

    def __init__(self):
        self.risk_data = {}
        self.risk_engine = RiskEngine()
        self.data_fetcher = DataFetcher()

    def render(self, selected_stocks, stock_names):
        """Render the full Risk Center dashboard"""

        st.header("⚠️ Risk Center")
        st.write("Position sizing, risk alerts, VaR, stress testing, Monte Carlo simulation, and beta analysis.")

        tab1, tab2, tab4, tab5, tab6 = st.tabs([
            "📊 Position Sizing",
            "📈 VaR & CVaR",
            "💥 Stress Testing",
            "🎲 Monte Carlo",
            "📈 Beta Analysis"
        ])
        st.caption("🔗 Correlation between stocks has moved to the **RIOT Correlation Map** tab.")

        with tab1:
            self._render_position_sizing_tab(selected_stocks, stock_names)

        stock_data = self.data_fetcher.get_stock_data(selected_stocks, period='3M')

        with tab2:
            self._render_var_cvar_tab(stock_data)

        with tab4:
            self._render_stress_test_tab(stock_data, selected_stocks)

        with tab5:
            self._render_monte_carlo_tab(stock_data)

        with tab6:
            self._render_beta_analysis_tab(selected_stocks)

    # -----------------------------------------------------------------------
    # Tab 1 — Position Sizing (from RiskManagement)
    # -----------------------------------------------------------------------

    def _render_position_sizing_tab(self, selected_stocks, stock_names):
        portfolio_value = st.sidebar.number_input(
            "Portfolio Value ($)", min_value=1000, max_value=10_000_000,
            value=100_000, step=1000,
            help="Enter your total portfolio value for position sizing calculations"
        )
        risk_per_trade = st.sidebar.slider(
            "Risk Per Trade (%)", min_value=0.5, max_value=5.0,
            value=2.0, step=0.1,
            help="Maximum percentage of portfolio to risk per trade"
        )

        self._render_risk_overview(selected_stocks, portfolio_value, risk_per_trade)
        self._render_individual_risk_analysis(selected_stocks, stock_names, portfolio_value, risk_per_trade)
        self._render_portfolio_optimization(selected_stocks, stock_names, portfolio_value)
        self._render_risk_alerts(selected_stocks)

    def _render_risk_overview(self, selected_stocks, portfolio_value, risk_per_trade):
        st.subheader("📊 Portfolio Risk Overview")
        try:
            risk_metrics = self._calculate_sector_risk_metrics(selected_stocks)
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                sv = risk_metrics.get('avg_volatility', 0)
                st.metric("Sector Volatility", f"{sv:.1f}%")
                if sv > 80: st.error("Very High Risk")
                elif sv > 60: st.warning("High Risk")
                elif sv > 40: st.info("Moderate Risk")
                else: st.success("Lower Risk")
            with col2:
                st.metric("Max Drawdown", f"{risk_metrics.get('max_drawdown', 0):.1f}%")
            with col3:
                st.metric("Sharpe Ratio", f"{risk_metrics.get('sharpe_ratio', 0):.2f}")
            with col4:
                st.metric("Avg Correlation", f"{risk_metrics.get('avg_correlation', 0):.2f}")

            st.subheader("💡 Risk Capacity Recommendations")
            rec = self._calculate_recommended_allocation(
                portfolio_value, risk_per_trade, risk_metrics.get('avg_volatility', 0)
            )
            col1, col2 = st.columns(2)
            with col1:
                st.write("**Conservative Allocation:**")
                st.write(f"• Total Crypto/Mining: {rec['conservative']:.1f}%")
                st.write(f"• Per Stock: {rec['conservative']/len(selected_stocks):.1f}%")
                st.write(f"• Max $ Amount: ${portfolio_value * rec['conservative']/100:,.0f}")
            with col2:
                st.write("**Aggressive Allocation:**")
                st.write(f"• Total Crypto/Mining: {rec['aggressive']:.1f}%")
                st.write(f"• Per Stock: {rec['aggressive']/len(selected_stocks):.1f}%")
                st.write(f"• Max $ Amount: ${portfolio_value * rec['aggressive']/100:,.0f}")
        except Exception as e:
            st.error(f"Error calculating risk overview: {str(e)}")

    def _render_individual_risk_analysis(self, selected_stocks, stock_names, portfolio_value, risk_per_trade):
        st.subheader("🎯 Individual Stock Risk Analysis")
        risk_data = []
        for symbol in selected_stocks:
            try:
                metrics = self._calculate_stock_risk_metrics(symbol)
                pos = self._calculate_position_size(symbol, portfolio_value, risk_per_trade, metrics)
                risk_data.append({
                    'Symbol': symbol,
                    'Company': stock_names.get(symbol, symbol)[:20],
                    'Volatility': f"{metrics.get('volatility', 0):.1f}%",
                    'Max Drawdown': f"{metrics.get('max_drawdown', 0):.1f}%",
                    'Beta': f"{metrics.get('beta', 0):.2f}",
                    'Position Size': f"${pos.get('dollar_amount', 0):,.0f}",
                    'Shares': f"{pos.get('shares', 0):.0f}",
                    'Stop Loss': f"${pos.get('stop_loss', 0):.2f}",
                    'Risk Score': metrics.get('risk_score', 'N/A')
                })
            except Exception:
                continue
        if risk_data:
            st.dataframe(pd.DataFrame(risk_data), use_container_width=True, hide_index=True)
            vols = [float(item['Volatility'].rstrip('%')) for item in risk_data]
            syms = [item['Symbol'] for item in risk_data]
            fig = px.bar(x=syms, y=vols, title="Stock Volatility Comparison",
                         labels={'x': 'Stock', 'y': 'Annualized Volatility (%)'},
                         color=vols, color_continuous_scale='RdYlGn_r')
            fig.update_layout(template='plotly_dark', height=400, margin=dict(l=0, r=0, t=40, b=0))
            st.plotly_chart(fig, use_container_width=True)

    def _render_portfolio_optimization(self, selected_stocks, stock_names, portfolio_value):
        st.subheader("🎯 Portfolio Optimization")
        try:
            optimal_weights = self._calculate_optimal_weights(selected_stocks)
            if optimal_weights:
                col1, col2 = st.columns(2)
                with col1:
                    fig = px.pie(values=list(optimal_weights.values()),
                                 names=list(optimal_weights.keys()),
                                 title="Optimal Portfolio Allocation",
                                 color_discrete_sequence=px.colors.qualitative.Set3)
                    fig.update_layout(template='plotly_dark', height=400, margin=dict(l=0, r=0, t=40, b=0))
                    st.plotly_chart(fig, use_container_width=True)
                with col2:
                    st.write("**Optimal Allocation Table:**")
                    alloc = [{'Stock': s, 'Weight': f"{w:.1%}", 'Amount': f"${portfolio_value*w:,.0f}"}
                             for s, w in optimal_weights.items()]
                    st.dataframe(pd.DataFrame(alloc), use_container_width=True, hide_index=True)
                    stats = self._calculate_portfolio_stats(selected_stocks, optimal_weights)
                    st.write("**Portfolio Statistics:**")
                    st.write(f"• Expected Return: {stats.get('expected_return', 0):.1f}%")
                    st.write(f"• Portfolio Volatility: {stats.get('portfolio_volatility', 0):.1f}%")
                    st.write(f"• Sharpe Ratio: {stats.get('sharpe_ratio', 0):.2f}")
                    st.write(f"• Diversification Ratio: {stats.get('diversification_ratio', 0):.2f}")
        except Exception as e:
            st.error(f"Error in portfolio optimization: {str(e)}")

    def _render_risk_alerts(self, selected_stocks):
        st.subheader("🚨 Risk Alerts")
        alerts = []
        for symbol in selected_stocks:
            try:
                alerts.extend(self._check_stock_risk_alerts(symbol))
            except Exception:
                continue
        if alerts:
            for alert in alerts:
                if alert['severity'] == 'High':
                    st.error(f"🚨 **{alert['symbol']}**: {alert['message']}")
                elif alert['severity'] == 'Medium':
                    st.warning(f"⚠️ **{alert['symbol']}**: {alert['message']}")
                else:
                    st.info(f"ℹ️ **{alert['symbol']}**: {alert['message']}")
        else:
            st.success("✅ No significant risk alerts at this time")
        with st.expander("💡 Risk Management Tips", expanded=False):
            st.write("""
            **Position Sizing:** Never risk more than 2% per trade. Use 10-15% stop losses.
            **Diversification:** Max 20% in crypto/mining. Spread across 4-6 stocks.
            **Monitoring:** Review when stocks move 15%+. Rebalance quarterly.
            """)

    # -----------------------------------------------------------------------
    # Tab 2 — VaR & CVaR (from RiskDashboard)
    # -----------------------------------------------------------------------

    def _render_var_cvar_tab(self, stock_data):
        st.subheader("📊 Value at Risk (VaR) & Conditional VaR")
        if stock_data.empty:
            st.warning("No data available for VaR calculation")
            return
        col1, col2 = st.columns(2)
        with col1:
            confidence_level = st.select_slider("Confidence Level",
                options=[0.90, 0.95, 0.99], value=0.95,
                format_func=lambda x: f"{int(x*100)}%")
        with col2:
            time_horizon = st.select_slider("Time Horizon",
                options=[1, 5, 10, 21], value=1,
                format_func=lambda x: f"{x} day{'s' if x > 1 else ''}")
        var_results = self.risk_engine.calculate_var_cvar(
            stock_data, confidence_level=confidence_level, time_horizon_days=time_horizon)
        if not var_results:
            st.error("Unable to calculate VaR/CVaR")
            return
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(f"VaR ({int(confidence_level*100)}%)",
                      f"{abs(var_results['var_pct']):.2f}%",
                      delta=f"${abs(var_results['var_dollar']):,.0f}")
        with col2:
            st.metric("CVaR", f"{abs(var_results['cvar_pct']):.2f}%",
                      delta=f"${abs(var_results['cvar_dollar']):,.0f}")
        with col3:
            st.metric("Daily Volatility", f"{var_results['daily_volatility']:.2f}%")
        with col4:
            st.metric("Annual Volatility", f"{var_results['annualized_volatility']:.1f}%")
        st.info(f"**Interpretation:** {var_results['interpretation']}")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Worst Day", f"{var_results['worst_day_pct']:.2f}%",
                      delta=f"${var_results['worst_day_dollar']:,.0f}")
        with col2:
            st.metric("Best Day", f"+{var_results['best_day_pct']:.2f}%",
                      delta=f"${var_results['best_day_dollar']:,.0f}")

    # -----------------------------------------------------------------------
    # Tab 3 — Correlation (from RiskDashboard)
    # -----------------------------------------------------------------------

    def _render_correlation_tab(self, selected_stocks):
        st.subheader("🔗 Stock Correlation Matrix")
        corr_data = self.risk_engine.calculate_correlation_matrix(selected_stocks, period='3mo')
        if not corr_data or corr_data.get('correlation_matrix') is None:
            st.warning("Unable to calculate correlation matrix")
            return
        col1, col2 = st.columns(2)
        with col1:
            avg_corr = corr_data['avg_correlation']
            color = "🔴" if avg_corr > 0.8 else "🟡" if avg_corr > 0.6 else "🟢"
            st.metric("Average Correlation", f"{avg_corr:.2f}", delta=color)
        with col2:
            st.metric("Diversification", corr_data['diversification_score'])
        fig = go.Figure(data=go.Heatmap(
            z=corr_data['correlation_matrix'].values,
            x=corr_data['correlation_matrix'].columns,
            y=corr_data['correlation_matrix'].index,
            colorscale='RdBu_r', zmid=0, zmin=-1, zmax=1,
            text=np.round(corr_data['correlation_matrix'].values, 2),
            texttemplate='%{text}', textfont={'size': 12},
            colorbar=dict(title="Correlation")
        ))
        fig.update_layout(title='Stock Correlation Heatmap', template='plotly_dark', height=500)
        st.plotly_chart(fig, use_container_width=True)
        if corr_data['highly_correlated_pairs']:
            st.subheader("⚠️ Highly Correlated Pairs (>0.7)")
            pairs_df = pd.DataFrame(corr_data['highly_correlated_pairs'])
            pairs_df['correlation'] = pairs_df['correlation'].apply(lambda x: f"{x:.2f}")
            st.dataframe(pairs_df, use_container_width=True, hide_index=True)
            st.warning("These stocks move together - limited diversification benefit!")
        else:
            st.success("✅ No highly correlated pairs - good diversification!")

    # -----------------------------------------------------------------------
    # Tab 4 — Stress Testing (from RiskDashboard)
    # -----------------------------------------------------------------------

    def _render_stress_test_tab(self, stock_data, selected_stocks):
        st.subheader("💥 Portfolio Stress Testing")
        if stock_data.empty:
            st.warning("No data available for stress testing")
            return
        stress_results = self.risk_engine.run_stress_test(stock_data, selected_stocks)
        if not stress_results or stress_results.get('error'):
            st.warning(f"⚠️ Insufficient data — stress test not shown. "
                       f"{(stress_results or {}).get('error', '')}")
            return
        st.caption("Assumes an equal-dollar basket of the selected stocks. Dollar figures are per "
                   "**$10,000 invested**. Beta is measured from 1 year of daily prices, with Bitcoin "
                   "lined up on stock trading days (weekend moves count toward Monday).")
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Example Basket", f"${stress_results['current_value']:,.0f}",
                      help="A hypothetical $10,000 split equally across the selected stocks.")
        with col2:
            beta = stress_results['beta_to_bitcoin']
            st.metric("Beta to Bitcoin", f"{beta:.2f}",
                      delta="🔴" if beta > 1.5 else "🟡" if beta > 1.0 else "🟢",
                      help=f"Measured over {stress_results['n_days']} shared trading days. "
                           "Beta 1.5 means: when Bitcoin moves 1%, this basket has typically moved 1.5%.")
        st.info(f"**Risk Assessment:** {stress_results['recommendation']}")
        scenarios_df = pd.DataFrame(stress_results['stress_scenarios'])
        for _, scenario in scenarios_df.iterrows():
            with st.expander(f"{scenario['scenario']} - {scenario['description']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                with col1: st.metric("Bitcoin Drop", f"{scenario['market_drop_pct']:.0f}%")
                with col2: st.metric("Expected Basket Drop", f"{scenario['portfolio_drop_pct']:.1f}%")
                with col3: st.metric("Loss per $10k", f"${abs(scenario['portfolio_loss_dollar']):,.0f}")
                st.metric("Value After (per $10k)", f"${scenario['portfolio_value_after']:,.0f}")
        fig = go.Figure(go.Bar(
            x=[s['scenario'] for s in stress_results['stress_scenarios']],
            y=[s['portfolio_drop_pct'] for s in stress_results['stress_scenarios']],
            marker_color=['red' if abs(x['portfolio_drop_pct']) > 30 else 'orange'
                          if abs(x['portfolio_drop_pct']) > 15 else 'yellow'
                          for x in stress_results['stress_scenarios']],
            text=[f"{x['portfolio_drop_pct']:.1f}%" for x in stress_results['stress_scenarios']],
            textposition='auto'
        ))
        fig.update_layout(title='Stress Test — Portfolio Loss %', template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Tab 5 — Monte Carlo (from RiskDashboard)
    # -----------------------------------------------------------------------

    def _render_monte_carlo_tab(self, stock_data):
        st.subheader("🎲 Monte Carlo Simulation")
        if stock_data.empty:
            st.warning("No data available for Monte Carlo simulation")
            return
        col1, col2 = st.columns(2)
        with col1:
            num_sims = st.select_slider("Simulations", options=[100, 500, 1000, 5000], value=1000)
        with col2:
            days_forward = st.select_slider("Days Forward", options=[7, 14, 30, 60, 90], value=30)
        mc_results = self.risk_engine.run_monte_carlo_simulation(
            stock_data, num_simulations=num_sims, days_forward=days_forward)
        if not mc_results:
            st.error("Unable to run Monte Carlo simulation")
            return
        col1, col2, col3, col4 = st.columns(4)
        with col1: st.metric("Expected Value", f"${mc_results['expected_value']:,.0f}")
        with col2: st.metric("Prob of Profit", f"{mc_results['prob_profit']:.1f}%")
        with col3: st.metric("Prob +10%", f"{mc_results['prob_gain_10_pct']:.1f}%")
        with col4: st.metric("Prob -10%", f"{mc_results['prob_loss_10_pct']:.1f}%")
        st.info(f"**Outlook:** {mc_results['interpretation']}")
        cols = st.columns(5)
        for col, (pct, key) in zip(cols, [
            ('5th', 'percentile_5'), ('25th', 'percentile_25'), ('50th (Median)', 'percentile_50'),
            ('75th', 'percentile_75'), ('95th', 'percentile_95')
        ]):
            col.metric(f"{pct} %ile", f"${mc_results[key]:,.0f}")
        fig = go.Figure()
        simulations = mc_results['simulations']
        for p in [10, 25, 50, 75, 90]:
            path = np.percentile(simulations, p, axis=1)
            fig.add_trace(go.Scatter(x=list(range(days_forward)), y=path, name=f'{p}th %ile',
                                     line=dict(width=2 if p == 50 else 1), opacity=0.8 if p == 50 else 0.4))
        fig.add_hline(y=mc_results['current_value'], line_dash="dash", line_color="white",
                      annotation_text="Current Value")
        fig.update_layout(title=f'Monte Carlo — {num_sims} Paths / {days_forward} Days',
                          xaxis_title='Days Forward', yaxis_title='Portfolio Value ($)',
                          template='plotly_dark', height=500, hovermode='x unified')
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Tab 6 — Beta Analysis (from RiskDashboard)
    # -----------------------------------------------------------------------

    def _render_beta_analysis_tab(self, selected_stocks):
        st.subheader("📈 Beta Analysis vs Bitcoin")
        beta_data = self.risk_engine.calculate_beta_analysis(selected_stocks, benchmark='BTC-USD', period='1y')
        if not beta_data or not beta_data.get('beta_results'):
            beta_data = self.risk_engine.calculate_beta_analysis(selected_stocks, benchmark='BTC-USD', period='3mo')
        if not beta_data or not beta_data.get('beta_results'):
            st.warning("Unable to calculate beta analysis - insufficient data overlap")
            return
        col1, col2 = st.columns(2)
        with col1:
            avg_beta = beta_data['avg_portfolio_beta']
            st.metric("Portfolio Beta", f"{avg_beta:.2f}",
                      delta="🔴" if avg_beta > 1.5 else "🟡" if avg_beta > 1.0 else "🟢")
        with col2:
            st.metric("Risk Assessment", beta_data['portfolio_risk_assessment'])
        beta_df = pd.DataFrame(beta_data['beta_results'])
        display_df = beta_df[['symbol', 'beta', 'correlation', 'annualized_volatility', 'risk_level', 'interpretation']].copy()
        display_df['beta'] = display_df['beta'].apply(lambda x: f"{x:.2f}")
        display_df['correlation'] = display_df['correlation'].apply(lambda x: f"{x:.2f}")
        display_df['annualized_volatility'] = display_df['annualized_volatility'].apply(lambda x: f"{x:.1f}%")
        display_df.columns = ['Symbol', 'Beta', 'Correlation', 'Volatility', 'Risk Level', 'Interpretation']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        fig = go.Figure(go.Bar(
            x=beta_df['symbol'], y=beta_df['beta'],
            marker_color=['red' if x > 1.5 else 'orange' if x > 1.0 else 'green' for x in beta_df['beta']],
            text=[f"{x:.2f}" for x in beta_df['beta']], textposition='auto'
        ))
        fig.add_hline(y=1.0, line_dash="dash", line_color="white", annotation_text="Beta = 1.0")
        fig.update_layout(title='Stock Beta vs Bitcoin', template='plotly_dark', height=400)
        st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Helper calculations (from RiskManagement)
    # -----------------------------------------------------------------------

    def _calculate_sector_risk_metrics(self, selected_stocks):
        try:
            volatilities, drawdowns, returns_data = [], [], []
            for symbol in selected_stocks:
                hist = yf.Ticker(symbol).history(period='1y')
                if not hist.empty and len(hist) > 30:
                    returns = hist['Close'].pct_change().dropna()
                    volatilities.append(returns.std() * np.sqrt(252) * 100)
                    peak = hist['Close'].expanding().max()
                    drawdowns.append(abs(((hist['Close'] - peak) / peak * 100).min()))
                    returns_data.append(returns)
            correlations = []
            if len(returns_data) > 1:
                for i in range(len(returns_data)):
                    for j in range(i + 1, len(returns_data)):
                        common = returns_data[i].index.intersection(returns_data[j].index)
                        if len(common) > 30:
                            c = np.corrcoef(returns_data[i].loc[common], returns_data[j].loc[common])[0, 1]
                            if not np.isnan(c): correlations.append(c)
            avg_returns = [r.mean() * 252 * 100 for r in returns_data if len(r) > 30]
            avg_vol = np.mean(volatilities) if volatilities else 0
            sharpe = (np.mean(avg_returns) / avg_vol) if avg_vol > 0 and avg_returns else 0
            return {'avg_volatility': avg_vol,
                    'max_drawdown': np.mean(drawdowns) if drawdowns else 0,
                    'avg_correlation': np.mean(correlations) if correlations else 0,
                    'sharpe_ratio': sharpe}
        except Exception:
            return {'avg_volatility': 0, 'max_drawdown': 0, 'avg_correlation': 0, 'sharpe_ratio': 0}

    def _calculate_stock_risk_metrics(self, symbol):
        try:
            hist = yf.Ticker(symbol).history(period='1y')
            if hist.empty: return {}
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252) * 100
            peak = hist['Close'].expanding().max()
            max_drawdown = abs(((hist['Close'] - peak) / peak * 100).min())
            beta = 1.0
            spy_hist = yf.Ticker("SPY").history(period='1y')
            if not spy_hist.empty:
                spy_returns = spy_hist['Close'].pct_change().dropna()
                common = returns.index.intersection(spy_returns.index)
                if len(common) > 30:
                    sp = spy_returns.loc[common]
                    if sp.var() > 0:
                        beta = np.cov(returns.loc[common], sp)[0, 1] / sp.var()
            risk_score = min(10, max(1, (volatility / 10) + (max_drawdown / 10)))
            return {'volatility': volatility, 'max_drawdown': max_drawdown,
                    'beta': beta, 'risk_score': f"{risk_score:.1f}/10"}
        except Exception:
            return {}

    def _calculate_position_size(self, symbol, portfolio_value, risk_per_trade, metrics):
        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get('currentPrice', 0)
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty: current_price = hist['Close'].iloc[-1]
            if current_price <= 0:
                return {'dollar_amount': 0, 'shares': 0, 'stop_loss': 0}
            risk_amount = portfolio_value * (risk_per_trade / 100)
            volatility = metrics.get('volatility', 50) / 100
            stop_pct = max(0.10, min(0.20, volatility * 0.5))
            stop_loss = current_price * (1 - stop_pct)
            risk_per_share = current_price - stop_loss
            shares = (risk_amount / risk_per_share) if risk_per_share > 0 else 0
            adj = 0.5 if volatility > 0.8 else 0.7 if volatility > 0.6 else 0.85 if volatility > 0.4 else 1.0
            return {'dollar_amount': shares * current_price * adj,
                    'shares': shares * adj, 'stop_loss': stop_loss}
        except Exception:
            return {'dollar_amount': 0, 'shares': 0, 'stop_loss': 0}

    def _calculate_recommended_allocation(self, portfolio_value, risk_per_trade, sector_volatility):
        base_c, base_a = 15.0, 30.0
        if sector_volatility > 80:   adj_c, adj_a = -5.0, -10.0
        elif sector_volatility > 60: adj_c, adj_a = -2.5, -5.0
        elif sector_volatility < 40: adj_c, adj_a = 2.5, 5.0
        else:                        adj_c, adj_a = 0, 0
        size_adj = 2.5 if portfolio_value > 1_000_000 else -2.5 if portfolio_value < 50_000 else 0
        return {'conservative': max(5.0, base_c + adj_c + size_adj),
                'aggressive':   max(10.0, base_a + adj_a + size_adj)}

    def _calculate_optimal_weights(self, selected_stocks):
        try:
            risk_scores, symbols = [], []
            for symbol in selected_stocks:
                metrics = self._calculate_stock_risk_metrics(symbol)
                vol = metrics.get('volatility', 50)
                if vol > 0:
                    risk_scores.append(1 / vol)
                    symbols.append(symbol)
            if not risk_scores:
                w = 1.0 / len(selected_stocks)
                return {s: w for s in selected_stocks}
            total = sum(risk_scores)
            return {symbols[i]: risk_scores[i] / total for i in range(len(symbols))}
        except Exception:
            w = 1.0 / len(selected_stocks)
            return {s: w for s in selected_stocks}

    def _calculate_portfolio_stats(self, selected_stocks, weights):
        try:
            returns_data, expected_returns = [], []
            for symbol in selected_stocks:
                if symbol in weights:
                    hist = yf.Ticker(symbol).history(period='6mo')
                    if not hist.empty:
                        r = hist['Close'].pct_change().dropna()
                        returns_data.append(r)
                        expected_returns.append(r.mean() * 252 * 100)
            if not returns_data: return {}
            port_return = sum(weights.get(selected_stocks[i], 0) * expected_returns[i]
                              for i in range(len(expected_returns)))
            weighted_vols = [weights[selected_stocks[i]] * returns_data[i].std() * np.sqrt(252) * 100
                             for i in range(len(returns_data)) if selected_stocks[i] in weights]
            port_vol = sum(weighted_vols)
            sharpe = port_return / port_vol if port_vol > 0 else 0
            return {'expected_return': port_return, 'portfolio_volatility': port_vol,
                    'sharpe_ratio': sharpe, 'diversification_ratio': 1 / np.sqrt(0.7)}
        except Exception:
            return {}

    def _check_stock_risk_alerts(self, symbol):
        alerts = []
        try:
            hist = yf.Ticker(symbol).history(period='1mo')
            if hist.empty: return alerts
            current = hist['Close'].iloc[-1]
            returns = hist['Close'].pct_change().dropna()
            if len(returns) > 10:
                recent_vol = returns.tail(5).std() * np.sqrt(252) * 100
                if recent_vol > 100:
                    alerts.append({'symbol': symbol, 'severity': 'High',
                                   'message': f'Extreme volatility: {recent_vol:.1f}% annualized'})
                elif recent_vol > 80:
                    alerts.append({'symbol': symbol, 'severity': 'Medium',
                                   'message': f'High volatility: {recent_vol:.1f}% annualized'})
            peak = hist['Close'].max()
            dd = (current - peak) / peak * 100
            if dd < -30:
                alerts.append({'symbol': symbol, 'severity': 'High',
                                'message': f'Large drawdown: {dd:.1f}% from recent high'})
            elif dd < -20:
                alerts.append({'symbol': symbol, 'severity': 'Medium',
                                'message': f'Moderate drawdown: {dd:.1f}% from recent high'})
            if 'Volume' in hist.columns:
                avg_vol = hist['Volume'].mean()
                cur_vol = hist['Volume'].iloc[-1]
                if cur_vol > avg_vol * 3:
                    alerts.append({'symbol': symbol, 'severity': 'Medium',
                                   'message': f'Unusual volume: {cur_vol/avg_vol:.1f}x average'})
        except Exception:
            pass
        return alerts

    def get_risk_data(self, selected_stocks, portfolio_value=100_000, risk_per_trade=2.0):
        """Get risk data dict for integration with other components"""
        risk_data = {}
        sector = self._calculate_sector_risk_metrics(selected_stocks)
        risk_data['sector'] = {
            'volatility': sector.get('avg_volatility', 0),
            'risk_level': ('High' if sector.get('avg_volatility', 0) > 70
                           else 'Moderate' if sector.get('avg_volatility', 0) > 50 else 'Low'),
            'recommended_allocation': self._calculate_recommended_allocation(
                portfolio_value, risk_per_trade, sector.get('avg_volatility', 0))
        }
        for symbol in selected_stocks:
            try:
                metrics = self._calculate_stock_risk_metrics(symbol)
                pos = self._calculate_position_size(symbol, portfolio_value, risk_per_trade, metrics)
                risk_data[symbol] = {
                    'volatility': metrics.get('volatility', 0),
                    'risk_score': float(str(metrics.get('risk_score', '5.0')).split('/')[0]),
                    'position_size': pos.get('dollar_amount', 0),
                    'stop_loss': pos.get('stop_loss', 0),
                    'risk_adjustment': (-1 if metrics.get('volatility', 0) > 80
                                        else 0 if metrics.get('volatility', 0) > 50 else 1)
                }
            except Exception:
                risk_data[symbol] = {'volatility': 50, 'risk_score': 5.0,
                                     'position_size': 0, 'stop_loss': 0, 'risk_adjustment': 0}
        return risk_data
