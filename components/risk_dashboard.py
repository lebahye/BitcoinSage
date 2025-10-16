import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.risk_engine import RiskEngine
from utils.data_fetcher import DataFetcher

class RiskDashboard:
    """Professional Risk Management Dashboard"""
    
    def __init__(self):
        self.risk_engine = RiskEngine()
        self.data_fetcher = DataFetcher()
    
    def render(self, selected_stocks, stock_names):
        """Render the Risk Dashboard"""
        
        st.header("⚠️ Portfolio Risk Management")
        st.write("Professional risk metrics - VaR, stress testing, Monte Carlo simulation")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 VaR & CVaR",
            "🔗 Correlation Matrix",
            "💥 Stress Testing",
            "🎲 Monte Carlo",
            "📈 Beta Analysis"
        ])
        
        stock_data = self.data_fetcher.get_stock_data(selected_stocks, period='3M')
        
        with tab1:
            self._render_var_cvar_tab(stock_data)
        
        with tab2:
            self._render_correlation_tab(selected_stocks)
        
        with tab3:
            self._render_stress_test_tab(stock_data, selected_stocks)
        
        with tab4:
            self._render_monte_carlo_tab(stock_data)
        
        with tab5:
            self._render_beta_analysis_tab(selected_stocks)
    
    def _render_var_cvar_tab(self, stock_data):
        """Render VaR and CVaR analysis"""
        
        st.subheader("📊 Value at Risk (VaR) & Conditional VaR")
        st.write("**VaR** = Maximum expected loss at given confidence level")
        st.write("**CVaR** = Average loss in worst-case scenarios (beyond VaR)")
        
        if stock_data.empty:
            st.warning("No data available for VaR calculation")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            confidence_level = st.select_slider(
                "Confidence Level",
                options=[0.90, 0.95, 0.99],
                value=0.95,
                format_func=lambda x: f"{int(x*100)}%"
            )
        
        with col2:
            time_horizon = st.select_slider(
                "Time Horizon",
                options=[1, 5, 10, 21],
                value=1,
                format_func=lambda x: f"{x} day{'s' if x > 1 else ''}"
            )
        
        var_results = self.risk_engine.calculate_var_cvar(
            stock_data, 
            confidence_level=confidence_level,
            time_horizon_days=time_horizon
        )
        
        if not var_results:
            st.error("Unable to calculate VaR/CVaR")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                f"VaR ({int(confidence_level*100)}%)", 
                f"{abs(var_results['var_pct']):.2f}%",
                delta=f"${abs(var_results['var_dollar']):,.0f}"
            )
        
        with col2:
            st.metric(
                "CVaR (Expected Shortfall)",
                f"{abs(var_results['cvar_pct']):.2f}%",
                delta=f"${abs(var_results['cvar_dollar']):,.0f}"
            )
        
        with col3:
            st.metric(
                "Daily Volatility",
                f"{var_results['daily_volatility']:.2f}%"
            )
        
        with col4:
            st.metric(
                "Annual Volatility",
                f"{var_results['annualized_volatility']:.1f}%"
            )
        
        st.info(f"**Interpretation:** {var_results['interpretation']}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric(
                "Worst Day (Historical)",
                f"{var_results['worst_day_pct']:.2f}%",
                delta=f"${var_results['worst_day_dollar']:,.0f}"
            )
        
        with col2:
            st.metric(
                "Best Day (Historical)",
                f"+{var_results['best_day_pct']:.2f}%",
                delta=f"${var_results['best_day_dollar']:,.0f}"
            )
        
        st.markdown("---")
        st.subheader("📚 What This Means")
        st.write(f"""
        **VaR of {abs(var_results['var_pct']):.2f}%** means:
        - {int(confidence_level*100)}% of the time, you won't lose more than {abs(var_results['var_pct']):.2f}% in {time_horizon} day(s)
        - In dollar terms: ${abs(var_results['var_dollar']):,.0f} maximum loss
        
        **CVaR of {abs(var_results['cvar_pct']):.2f}%** means:
        - In the worst {int((1-confidence_level)*100)}% of cases, average loss is {abs(var_results['cvar_pct']):.2f}%
        - This is your "tail risk" - what happens in extreme scenarios
        """)
    
    def _render_correlation_tab(self, selected_stocks):
        """Render correlation matrix"""
        
        st.subheader("🔗 Stock Correlation Matrix")
        st.write("Shows which stocks move together - important for diversification")
        
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
            colorscale='RdBu_r',
            zmid=0,
            zmin=-1,
            zmax=1,
            text=np.round(corr_data['correlation_matrix'].values, 2),
            texttemplate='%{text}',
            textfont={'size': 12},
            colorbar=dict(title="Correlation")
        ))
        
        fig.update_layout(
            title='Stock Correlation Heatmap',
            template='plotly_dark',
            height=500,
            xaxis_title='',
            yaxis_title=''
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        if corr_data['highly_correlated_pairs']:
            st.subheader("⚠️ Highly Correlated Pairs (>0.7)")
            pairs_df = pd.DataFrame(corr_data['highly_correlated_pairs'])
            pairs_df['correlation'] = pairs_df['correlation'].apply(lambda x: f"{x:.2f}")
            st.dataframe(pairs_df, use_container_width=True, hide_index=True)
            st.warning("These stocks move together - limited diversification benefit!")
        else:
            st.success("✅ No highly correlated pairs - good diversification!")
    
    def _render_stress_test_tab(self, stock_data, selected_stocks):
        """Render stress testing"""
        
        st.subheader("💥 Portfolio Stress Testing")
        st.write("See how your portfolio performs in market crashes")
        
        if stock_data.empty:
            st.warning("No data available for stress testing")
            return
        
        stress_results = self.risk_engine.run_stress_test(stock_data, selected_stocks)
        
        if not stress_results:
            st.error("Unable to run stress test")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Current Portfolio Value", f"${stress_results['current_value']:,.0f}")
        
        with col2:
            beta = stress_results['beta_to_bitcoin']
            beta_color = "🔴" if beta > 1.5 else "🟡" if beta > 1.0 else "🟢"
            st.metric("Beta to Bitcoin", f"{beta:.2f}", delta=beta_color)
        
        st.info(f"**Risk Assessment:** {stress_results['recommendation']}")
        
        st.subheader("📊 Scenario Analysis")
        
        scenarios_df = pd.DataFrame(stress_results['stress_scenarios'])
        
        for _, scenario in scenarios_df.iterrows():
            with st.expander(f"{scenario['scenario']} - {scenario['description']}", expanded=False):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Market Drop", f"{scenario['market_drop_pct']:.0f}%")
                
                with col2:
                    loss_color = "🔴" if abs(scenario['portfolio_drop_pct']) > 30 else "🟡" if abs(scenario['portfolio_drop_pct']) > 15 else "🟢"
                    st.metric(
                        "Your Portfolio Drop",
                        f"{scenario['portfolio_drop_pct']:.1f}%",
                        delta=loss_color
                    )
                
                with col3:
                    st.metric(
                        "Dollar Loss",
                        f"${abs(scenario['portfolio_loss_dollar']):,.0f}"
                    )
                
                st.metric("Portfolio Value After", f"${scenario['portfolio_value_after']:,.0f}")
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=[s['scenario'] for s in stress_results['stress_scenarios']],
            y=[s['portfolio_drop_pct'] for s in stress_results['stress_scenarios']],
            marker_color=['red' if abs(x['portfolio_drop_pct']) > 30 else 'orange' if abs(x['portfolio_drop_pct']) > 15 else 'yellow'
                         for x in stress_results['stress_scenarios']],
            text=[f"{x['portfolio_drop_pct']:.1f}%" for x in stress_results['stress_scenarios']],
            textposition='auto'
        ))
        
        fig.update_layout(
            title='Stress Test Results - Portfolio Loss %',
            xaxis_title='Scenario',
            yaxis_title='Portfolio Loss (%)',
            template='plotly_dark',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_monte_carlo_tab(self, stock_data):
        """Render Monte Carlo simulation"""
        
        st.subheader("🎲 Monte Carlo Simulation")
        st.write("Probability distribution of future portfolio values")
        
        if stock_data.empty:
            st.warning("No data available for Monte Carlo simulation")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            num_sims = st.select_slider(
                "Number of Simulations",
                options=[100, 500, 1000, 5000],
                value=1000
            )
        
        with col2:
            days_forward = st.select_slider(
                "Days to Simulate",
                options=[7, 14, 30, 60, 90],
                value=30
            )
        
        mc_results = self.risk_engine.run_monte_carlo_simulation(
            stock_data,
            num_simulations=num_sims,
            days_forward=days_forward
        )
        
        if not mc_results:
            st.error("Unable to run Monte Carlo simulation")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Expected Value", f"${mc_results['expected_value']:,.0f}")
        
        with col2:
            prob_color = "🟢" if mc_results['prob_profit'] > 60 else "🔴"
            st.metric("Prob of Profit", f"{mc_results['prob_profit']:.1f}%", delta=prob_color)
        
        with col3:
            st.metric("Prob of +10% Gain", f"{mc_results['prob_gain_10_pct']:.1f}%")
        
        with col4:
            st.metric("Prob of -10% Loss", f"{mc_results['prob_loss_10_pct']:.1f}%")
        
        st.info(f"**Outlook:** {mc_results['interpretation']}")
        
        st.subheader("📊 Percentile Outcomes")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("5th %ile (Worst)", f"${mc_results['percentile_5']:,.0f}")
        
        with col2:
            st.metric("25th %ile", f"${mc_results['percentile_25']:,.0f}")
        
        with col3:
            st.metric("50th %ile (Median)", f"${mc_results['percentile_50']:,.0f}")
        
        with col4:
            st.metric("75th %ile", f"${mc_results['percentile_75']:,.0f}")
        
        with col5:
            st.metric("95th %ile (Best)", f"${mc_results['percentile_95']:,.0f}")
        
        fig = go.Figure()
        
        simulations = mc_results['simulations']
        percentiles = [10, 25, 50, 75, 90]
        
        for p in percentiles:
            percentile_path = np.percentile(simulations, p, axis=1)
            fig.add_trace(go.Scatter(
                x=list(range(days_forward)),
                y=percentile_path,
                name=f'{p}th Percentile',
                line=dict(width=2 if p == 50 else 1),
                opacity=0.8 if p == 50 else 0.4
            ))
        
        fig.add_hline(
            y=mc_results['current_value'],
            line_dash="dash",
            line_color="white",
            annotation_text="Current Value"
        )
        
        fig.update_layout(
            title=f'Monte Carlo Simulation - {num_sims} Paths over {days_forward} Days',
            xaxis_title='Days Forward',
            yaxis_title='Portfolio Value ($)',
            template='plotly_dark',
            height=500,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_beta_analysis_tab(self, selected_stocks):
        """Render Beta analysis"""
        
        st.subheader("📈 Beta Analysis vs Bitcoin")
        st.write("**Beta > 1** = More volatile than Bitcoin | **Beta < 1** = Less volatile")
        
        beta_data = self.risk_engine.calculate_beta_analysis(selected_stocks, benchmark='BTC-USD')
        
        if not beta_data or not beta_data.get('beta_results'):
            st.warning("Unable to calculate beta analysis")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            avg_beta = beta_data['avg_portfolio_beta']
            beta_color = "🔴" if avg_beta > 1.5 else "🟡" if avg_beta > 1.0 else "🟢"
            st.metric("Portfolio Beta", f"{avg_beta:.2f}", delta=beta_color)
        
        with col2:
            st.metric("Risk Assessment", beta_data['portfolio_risk_assessment'])
        
        beta_df = pd.DataFrame(beta_data['beta_results'])
        
        display_df = beta_df[['symbol', 'beta', 'correlation', 'annualized_volatility', 'risk_level', 'interpretation']]
        display_df['beta'] = display_df['beta'].apply(lambda x: f"{x:.2f}")
        display_df['correlation'] = display_df['correlation'].apply(lambda x: f"{x:.2f}")
        display_df['annualized_volatility'] = display_df['annualized_volatility'].apply(lambda x: f"{x:.1f}%")
        display_df.columns = ['Symbol', 'Beta', 'Correlation', 'Volatility', 'Risk Level', 'Interpretation']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=beta_df['symbol'],
            y=beta_df['beta'],
            marker_color=['red' if x > 1.5 else 'orange' if x > 1.0 else 'green' for x in beta_df['beta']],
            text=[f"{x:.2f}" for x in beta_df['beta']],
            textposition='auto'
        ))
        
        fig.add_hline(y=1.0, line_dash="dash", line_color="white", annotation_text="Beta = 1.0 (Bitcoin)")
        
        fig.update_layout(
            title='Stock Beta vs Bitcoin',
            xaxis_title='Symbol',
            yaxis_title='Beta',
            template='plotly_dark',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
