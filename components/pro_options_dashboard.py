import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.options_analytics import OptionsAnalytics

class ProOptionsDashboard:
    """Professional Options Analytics Dashboard"""
    
    def __init__(self):
        self.analytics = OptionsAnalytics()
    
    def render(self, selected_stocks, stock_names):
        """Render the Professional Options dashboard"""
        
        st.header("📊 Professional Options Analytics")
        st.write("Institutional-grade options analysis - IV Percentile, Chain Scanner, Greeks Surface")
        
        tab1, tab2, tab3, tab4 = st.tabs([
            "📈 IV Percentile/Rank",
            "🔍 Options Chain Scanner",
            "🎨 Greeks Surface",
            "📊 IV Term Structure"
        ])
        
        with tab1:
            self._render_iv_percentile_tab(selected_stocks, stock_names)
        
        with tab2:
            self._render_chain_scanner_tab(selected_stocks, stock_names)
        
        with tab3:
            self._render_greeks_surface_tab(selected_stocks, stock_names)
        
        with tab4:
            self._render_iv_term_structure_tab(selected_stocks, stock_names)
    
    def _render_iv_percentile_tab(self, selected_stocks, stock_names):
        """Render IV Percentile/Rank analysis"""
        
        st.subheader("📈 IV Percentile & Rank - Know if Options are Cheap or Expensive")
        st.write("**IV Percentile > 75% = Options EXPENSIVE (great for selling)**")
        st.write("**IV Percentile < 25% = Options CHEAP (great for buying)**")
        
        for symbol in selected_stocks[:3]:
            with st.expander(f"📊 {symbol} - IV Analysis", expanded=True):
                iv_data = self.analytics.calculate_iv_percentile(symbol, 0, period_days=252)
                
                if not iv_data or 'error' in iv_data:
                    st.warning(f"Unable to calculate IV percentile for {symbol} - {iv_data.get('error', 'No data')}")
                    continue
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    iv_pct = iv_data['iv_percentile']
                    color = "🔴" if iv_pct > 75 else "🟢" if iv_pct < 25 else "🟡"
                    st.metric("IV Percentile", f"{iv_pct:.1f}%", delta=color)
                
                with col2:
                    st.metric("IV Rank", f"{iv_data['iv_rank']:.1f}%")
                
                with col3:
                    st.metric("Current IV", f"{iv_data['current_iv']*100:.1f}%")
                
                with col4:
                    st.metric("Median IV (1Y)", f"{iv_data['median_iv']*100:.1f}%")
                
                st.info(f"**Signal:** {iv_data['signal']}")
                
                if iv_data.get('iv_history'):
                    fig = go.Figure()
                    
                    dates = [x['date'] for x in iv_data['iv_history']]
                    ivs = [x['iv'] * 100 for x in iv_data['iv_history']]
                    
                    fig.add_trace(go.Scatter(
                        x=dates,
                        y=ivs,
                        name='IV History',
                        line=dict(color='cyan', width=2),
                        fill='tozeroy',
                        fillcolor='rgba(0,255,255,0.1)'
                    ))
                    
                    fig.add_hline(y=iv_data['current_iv']*100, line_dash="solid", line_color="white",
                                 annotation_text="Current IV", annotation_position="right")
                    fig.add_hline(y=iv_data['median_iv']*100, line_dash="dash", line_color="yellow",
                                 annotation_text="Median IV", annotation_position="right")
                    
                    percentile_25 = np.percentile(ivs, 25)
                    percentile_75 = np.percentile(ivs, 75)
                    
                    fig.add_hrect(y0=percentile_75, y1=max(ivs), fillcolor="red", opacity=0.1,
                                 annotation_text="Expensive Zone", annotation_position="top right")
                    fig.add_hrect(y0=0, y1=percentile_25, fillcolor="green", opacity=0.1,
                                 annotation_text="Cheap Zone", annotation_position="bottom right")
                    
                    fig.update_layout(
                        title=f'{symbol} IV History (1 Year)',
                        xaxis_title='Date',
                        yaxis_title='Implied Volatility (%)',
                        template='plotly_dark',
                        height=400,
                        hovermode='x unified'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
    
    def _render_chain_scanner_tab(self, selected_stocks, stock_names):
        """Render Options Chain Scanner"""
        
        st.subheader("🔍 Options Chain Scanner - Best Opportunities")
        
        strategy = st.selectbox(
            "Select Strategy",
            ['covered_calls', 'protective_puts', 'long_calls'],
            format_func=lambda x: {
                'covered_calls': '💰 Covered Calls (Income)',
                'protective_puts': '🛡️ Protective Puts (Insurance)',
                'long_calls': '🚀 Long Calls (Speculation)'
            }[x]
        )
        
        for symbol in selected_stocks[:2]:
            with st.expander(f"🎯 {symbol} - {stock_names.get(symbol, symbol)}", expanded=True):
                scan_results = self.analytics.scan_options_chain(symbol, strategy=strategy)
                
                if not scan_results or not scan_results.get('recommendations'):
                    st.warning(f"No options recommendations found for {symbol}")
                    continue
                
                st.metric("Current Stock Price", f"${scan_results['current_price']:.2f}")
                st.metric("Total Opportunities Found", scan_results['total_opportunities'])
                
                recs_df = pd.DataFrame(scan_results['recommendations'])
                
                if strategy == 'covered_calls':
                    st.subheader("📊 Best Covered Call Opportunities")
                    display_df = recs_df[['expiration', 'days_to_exp', 'strike', 'premium', 'annual_return', 'max_gain', 'delta']].head(10)
                    display_df['strike'] = display_df['strike'].apply(lambda x: f"${x:.2f}")
                    display_df['premium'] = display_df['premium'].apply(lambda x: f"${x:.2f}")
                    display_df['annual_return'] = display_df['annual_return'].apply(lambda x: f"{x:.1f}%")
                    display_df['max_gain'] = display_df['max_gain'].apply(lambda x: f"{x:.1f}%")
                    display_df['delta'] = display_df['delta'].apply(lambda x: f"{x:.2f}")
                    display_df.columns = ['Expiration', 'Days', 'Strike', 'Premium', 'Annual Return', 'Max Gain', 'Delta']
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.info("**Strategy:** Sell calls above current price to generate income. Higher annual return = better income potential.")
                
                elif strategy == 'protective_puts':
                    st.subheader("🛡️ Best Protective Put Opportunities")
                    display_df = recs_df[['expiration', 'days_to_exp', 'strike', 'premium', 'cost_pct', 'protection_pct']].head(10)
                    display_df['strike'] = display_df['strike'].apply(lambda x: f"${x:.2f}")
                    display_df['premium'] = display_df['premium'].apply(lambda x: f"${x:.2f}")
                    display_df['cost_pct'] = display_df['cost_pct'].apply(lambda x: f"{x:.2f}%")
                    display_df['protection_pct'] = display_df['protection_pct'].apply(lambda x: f"{x:.2f}%")
                    display_df.columns = ['Expiration', 'Days', 'Strike', 'Premium', 'Cost %', 'Protection %']
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.info("**Strategy:** Buy puts below current price for downside protection. Lower cost % with higher protection % = better insurance.")
                
                elif strategy == 'long_calls':
                    st.subheader("🚀 Best Long Call Opportunities")
                    display_df = recs_df[['expiration', 'days_to_exp', 'strike', 'premium', 'breakeven', 'delta', 'leverage', 'moneyness']].head(10)
                    display_df['strike'] = display_df['strike'].apply(lambda x: f"${x:.2f}")
                    display_df['premium'] = display_df['premium'].apply(lambda x: f"${x:.2f}")
                    display_df['breakeven'] = display_df['breakeven'].apply(lambda x: f"${x:.2f}")
                    display_df['delta'] = display_df['delta'].apply(lambda x: f"{x:.2f}")
                    display_df['leverage'] = display_df['leverage'].apply(lambda x: f"{x:.1f}x")
                    display_df.columns = ['Expiration', 'Days', 'Strike', 'Premium', 'Breakeven', 'Delta', 'Leverage', 'Moneyness']
                    st.dataframe(display_df, use_container_width=True, hide_index=True)
                    
                    st.info("**Strategy:** Buy calls for leveraged upside. Higher delta & leverage with lower premium = better value.")
    
    def _render_greeks_surface_tab(self, selected_stocks, stock_names):
        """Render Greeks Surface visualization"""
        
        st.subheader("🎨 Greeks Surface - Visualize Risk Across All Options")
        st.write("See how Delta, Gamma, Theta, and Vega change across strikes and time")
        
        for symbol in selected_stocks[:2]:
            with st.expander(f"📊 {symbol} Greeks Surface", expanded=True):
                greeks_surface = self.analytics.calculate_greeks_surface(symbol)
                
                if not greeks_surface or greeks_surface.get('greeks_data') is None or greeks_surface['greeks_data'].empty:
                    st.warning(f"Unable to calculate Greeks surface for {symbol}")
                    continue
                
                st.metric("Current Price", f"${greeks_surface['current_price']:.2f}")
                
                greek_type = st.selectbox(
                    f"Select Greek to Visualize ({symbol})",
                    ['delta', 'gamma', 'theta', 'vega'],
                    key=f"greek_{symbol}",
                    format_func=lambda x: x.upper()
                )
                
                df = greeks_surface['greeks_data']
                call_data = df[df['type'] == 'call']
                
                fig = go.Figure()
                
                for exp in call_data['expiration'].unique()[:4]:
                    exp_data = call_data[call_data['expiration'] == exp]
                    days = exp_data['days_to_exp'].iloc[0] if not exp_data.empty else 0
                    
                    fig.add_trace(go.Scatter(
                        x=exp_data['strike'],
                        y=exp_data[greek_type],
                        name=f"{exp} ({days}d)",
                        mode='lines+markers',
                        line=dict(width=2)
                    ))
                
                fig.add_vline(x=greeks_surface['current_price'], line_dash="dash", line_color="white",
                             annotation_text="Current Price")
                
                fig.update_layout(
                    title=f'{symbol} {greek_type.upper()} Surface (Calls)',
                    xaxis_title='Strike Price',
                    yaxis_title=greek_type.upper(),
                    template='plotly_dark',
                    height=500,
                    hovermode='x unified',
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if greek_type == 'delta':
                    st.info("**Delta:** Rate of change - how much option price changes per $1 stock move. ATM options ~0.5 delta.")
                elif greek_type == 'gamma':
                    st.info("**Gamma:** Delta acceleration - how fast delta changes. Highest near ATM, especially close to expiration.")
                elif greek_type == 'theta':
                    st.info("**Theta:** Time decay - how much option loses per day. Negative for long options, accelerates near expiration.")
                elif greek_type == 'vega':
                    st.info("**Vega:** IV sensitivity - how much option price changes per 1% IV move. Higher for ATM and longer-dated options.")
    
    def _render_iv_term_structure_tab(self, selected_stocks, stock_names):
        """Render IV Term Structure"""
        
        st.subheader("📊 IV Term Structure - Volatility Across Time")
        st.write("Shows if near-term or far-term options are more expensive")
        
        for symbol in selected_stocks[:3]:
            with st.expander(f"📈 {symbol} IV Term Structure", expanded=True):
                term_structure = self.analytics.calculate_iv_term_structure(symbol)
                
                if not term_structure or not term_structure.get('term_structure'):
                    st.warning(f"Unable to calculate IV term structure for {symbol}")
                    continue
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Near-Term IV", f"{term_structure['near_term_iv']:.1f}%")
                
                with col2:
                    st.metric("Far-Term IV", f"{term_structure['far_term_iv']:.1f}%")
                
                with col3:
                    spread_color = "🔴" if term_structure['term_spread'] < 0 else "🟢"
                    st.metric("Term Spread", f"{term_structure['term_spread']:.1f}%", delta=spread_color)
                
                st.info(f"**Shape:** {term_structure['shape']}")
                
                fig = go.Figure()
                
                ts_data = term_structure['term_structure']
                
                fig.add_trace(go.Scatter(
                    x=[x['days_to_exp'] for x in ts_data],
                    y=[x['iv'] * 100 for x in ts_data],
                    name='ATM IV',
                    mode='lines+markers',
                    line=dict(color='cyan', width=3),
                    marker=dict(size=10)
                ))
                
                fig.add_trace(go.Scatter(
                    x=[x['days_to_exp'] for x in ts_data],
                    y=[x['call_iv'] * 100 for x in ts_data],
                    name='Call IV',
                    mode='lines',
                    line=dict(color='green', width=2, dash='dot'),
                    opacity=0.6
                ))
                
                fig.add_trace(go.Scatter(
                    x=[x['days_to_exp'] for x in ts_data],
                    y=[x['put_iv'] * 100 for x in ts_data],
                    name='Put IV',
                    mode='lines',
                    line=dict(color='red', width=2, dash='dot'),
                    opacity=0.6
                ))
                
                fig.update_layout(
                    title=f'{symbol} IV Term Structure',
                    xaxis_title='Days to Expiration',
                    yaxis_title='Implied Volatility (%)',
                    template='plotly_dark',
                    height=400,
                    hovermode='x unified',
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                if "Inverted" in term_structure['shape']:
                    st.warning("⚠️ **Inverted Term Structure** - Near-term event or volatility spike expected. Good time to sell short-dated options.")
                elif "Normal" in term_structure['shape']:
                    st.success("✅ **Normal Term Structure** - Standard volatility curve. Sell longer-dated options for more premium.")
                else:
                    st.info("ℹ️ **Flat Term Structure** - Volatility expectations stable across time.")
