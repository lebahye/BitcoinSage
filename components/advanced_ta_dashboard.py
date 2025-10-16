import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from utils.advanced_ta import AdvancedTA

class AdvancedTADashboard:
    """Dashboard for Advanced Technical Analysis indicators"""
    
    def __init__(self):
        self.ta = AdvancedTA()
    
    def render(self, selected_stocks, stock_names):
        """Render the Advanced TA dashboard"""
        
        st.header("⚡ Advanced Technical Analysis")
        st.write("Professional-grade indicators used by institutional traders")
        
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Volume Profile",
            "📈 Ichimoku Cloud", 
            "🎯 Fibonacci",
            "💰 Money Flow",
            "🏢 Market Breadth"
        ])
        
        with tab1:
            self._render_volume_profile_tab(selected_stocks, stock_names)
        
        with tab2:
            self._render_ichimoku_tab(selected_stocks, stock_names)
        
        with tab3:
            self._render_fibonacci_tab(selected_stocks, stock_names)
        
        with tab4:
            self._render_money_flow_tab(selected_stocks, stock_names)
        
        with tab5:
            self._render_market_breadth_tab(selected_stocks)
    
    def _render_volume_profile_tab(self, selected_stocks, stock_names):
        """Render Volume Profile analysis"""
        
        st.subheader("📊 Volume Profile Analysis")
        st.write("Shows where institutional money is concentrated - critical for support/resistance")
        
        for symbol in selected_stocks[:3]:
            with st.expander(f"📊 {symbol} - {stock_names.get(symbol, symbol)}", expanded=True):
                vp = self.ta.calculate_volume_profile(symbol, period='3mo')
                
                if not vp or not vp.get('poc') or not np.isfinite(vp.get('poc', 0)):
                    st.warning(f"Insufficient data to calculate volume profile for {symbol}")
                    continue
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Current Price", f"${vp['current_price']:.2f}")
                
                with col2:
                    st.metric("POC (Point of Control)", f"${vp['poc']:.2f}",
                             delta=f"{((vp['current_price'] - vp['poc']) / vp['poc'] * 100):.1f}%")
                
                with col3:
                    st.metric("Value Area High", f"${vp['value_area_high']:.2f}")
                
                with col4:
                    st.metric("Value Area Low", f"${vp['value_area_low']:.2f}")
                
                st.info(f"**Position:** {vp['position']}")
                st.write(f"**Signal:** {vp['signal']}")
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    y=vp['price_levels'],
                    x=vp['volume_pct'],
                    orientation='h',
                    marker=dict(
                        color=vp['volume_pct'],
                        colorscale='Viridis',
                        showscale=True
                    ),
                    name='Volume %'
                ))
                
                fig.add_hline(y=vp['poc'], line_dash="dot", line_color="red", 
                             annotation_text="POC", annotation_position="right")
                fig.add_hline(y=vp['value_area_high'], line_dash="dash", line_color="green",
                             annotation_text="VA High", annotation_position="right")
                fig.add_hline(y=vp['value_area_low'], line_dash="dash", line_color="orange",
                             annotation_text="VA Low", annotation_position="right")
                fig.add_hline(y=vp['current_price'], line_color="white",
                             annotation_text="Current", annotation_position="left")
                
                fig.update_layout(
                    title=f'{symbol} Volume Profile (3 Months)',
                    xaxis_title='Volume Distribution (%)',
                    yaxis_title='Price Level ($)',
                    template='plotly_dark',
                    height=500,
                    showlegend=False
                )
                
                st.plotly_chart(fig, use_container_width=True)
    
    def _render_ichimoku_tab(self, selected_stocks, stock_names):
        """Render Ichimoku Cloud analysis"""
        
        st.subheader("📈 Ichimoku Cloud - Complete Trend System")
        st.write("Japanese institutional indicator - shows trend, momentum, and support/resistance")
        
        for symbol in selected_stocks[:3]:
            with st.expander(f"☁️ {symbol} - {stock_names.get(symbol, symbol)}", expanded=True):
                ichimoku = self.ta.calculate_ichimoku_cloud(symbol, period='6mo')
                
                if not ichimoku:
                    st.warning(f"Unable to calculate Ichimoku Cloud for {symbol}")
                    continue
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Current Price", f"${ichimoku['current_price']:.2f}")
                
                with col2:
                    cloud_color = "🟢" if ichimoku['cloud_color'] == 'bullish' else "🔴"
                    st.metric("Trend", ichimoku['trend'], delta=cloud_color)
                
                with col3:
                    st.metric("Cloud Position", 
                             f"Top: ${ichimoku['cloud_top']:.2f} | Bottom: ${ichimoku['cloud_bottom']:.2f}")
                
                if ichimoku.get('tk_cross'):
                    if 'Bullish' in ichimoku['tk_cross']:
                        st.success(f"🟢 {ichimoku['tk_cross']}")
                    else:
                        st.error(f"🔴 {ichimoku['tk_cross']}")
                
                for signal in ichimoku['signals']:
                    if 'STRONG BUY' in signal:
                        st.success(f"✅ {signal}")
                    elif 'STRONG SELL' in signal:
                        st.error(f"❌ {signal}")
                    elif 'HOLD/BUY' in signal:
                        st.info(f"ℹ️ {signal}")
                    elif 'HOLD/SELL' in signal:
                        st.warning(f"⚠️ {signal}")
                    else:
                        st.info(f"⏸️ {signal}")
                
                fig = go.Figure()
                
                valid_indices = [i for i, (a, b) in enumerate(zip(ichimoku['senkou_span_a'], ichimoku['senkou_span_b'])) 
                                if a is not None and b is not None and not (pd.isna(a) or pd.isna(b))]
                
                if valid_indices:
                    dates_filtered = [ichimoku['dates'][i] for i in valid_indices]
                    span_a_filtered = [ichimoku['senkou_span_a'][i] for i in valid_indices]
                    span_b_filtered = [ichimoku['senkou_span_b'][i] for i in valid_indices]
                    
                    fig.add_trace(go.Scatter(
                        x=dates_filtered,
                        y=span_a_filtered,
                        name='Senkou Span A',
                        line=dict(color='rgba(0,255,0,0.3)', width=1),
                        fill=None
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=dates_filtered,
                        y=span_b_filtered,
                        name='Senkou Span B',
                        line=dict(color='rgba(255,0,0,0.3)', width=1),
                        fill='tonexty',
                        fillcolor='rgba(0,255,0,0.2)' if ichimoku['cloud_color'] == 'bullish' else 'rgba(255,0,0,0.2)'
                    ))
                
                fig.add_trace(go.Scatter(
                    x=ichimoku['dates'],
                    y=ichimoku['price'],
                    name='Price',
                    line=dict(color='white', width=2)
                ))
                
                valid_tenkan = [(i, v) for i, v in enumerate(ichimoku['tenkan_sen']) if v is not None and not pd.isna(v)]
                if valid_tenkan:
                    tenkan_indices, tenkan_values = zip(*valid_tenkan)
                    tenkan_dates = [ichimoku['dates'][i] for i in tenkan_indices]
                    
                    fig.add_trace(go.Scatter(
                        x=tenkan_dates,
                        y=tenkan_values,
                        name='Tenkan-sen (Conversion)',
                        line=dict(color='blue', width=1, dash='dot')
                    ))
                
                valid_kijun = [(i, v) for i, v in enumerate(ichimoku['kijun_sen']) if v is not None and not pd.isna(v)]
                if valid_kijun:
                    kijun_indices, kijun_values = zip(*valid_kijun)
                    kijun_dates = [ichimoku['dates'][i] for i in kijun_indices]
                    
                    fig.add_trace(go.Scatter(
                        x=kijun_dates,
                        y=kijun_values,
                        name='Kijun-sen (Base)',
                        line=dict(color='red', width=1, dash='dash')
                    ))
                
                fig.update_layout(
                    title=f'{symbol} Ichimoku Cloud (6 Months)',
                    xaxis_title='Date',
                    yaxis_title='Price ($)',
                    template='plotly_dark',
                    height=500,
                    hovermode='x unified'
                )
                
                st.plotly_chart(fig, use_container_width=True)
    
    def _render_fibonacci_tab(self, selected_stocks, stock_names):
        """Render Fibonacci Extensions analysis"""
        
        st.subheader("🎯 Fibonacci Extensions - Price Targets")
        st.write("Professional price targets based on Fibonacci ratios - where to take profits")
        
        for symbol in selected_stocks[:3]:
            with st.expander(f"📐 {symbol} - {stock_names.get(symbol, symbol)}", expanded=True):
                fib = self.ta.calculate_fibonacci_extensions(symbol, period='1y')
                
                if not fib:
                    st.warning(f"Unable to calculate Fibonacci levels for {symbol}")
                    continue
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Current Price", f"${fib['current_price']:.2f}")
                
                with col2:
                    st.metric("Swing High", f"${fib['swing_high']:.2f}")
                
                with col3:
                    st.metric("Swing Low", f"${fib['swing_low']:.2f}")
                
                st.write(f"**Trend Direction:** {fib['direction'].upper()}")
                
                st.subheader("🎯 Next Price Targets (Extensions)")
                if fib['next_targets']:
                    targets_df = pd.DataFrame(fib['next_targets'])
                    targets_df['price'] = targets_df['price'].apply(lambda x: f"${x:.2f}")
                    targets_df['distance_pct'] = targets_df['distance_pct'].apply(lambda x: f"+{x:.1f}%")
                    st.dataframe(targets_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No upside targets - price at or above major extensions")
                
                st.subheader("🛡️ Support Levels (Retracements)")
                if fib['support_levels']:
                    support_df = pd.DataFrame(fib['support_levels'])
                    support_df['price'] = support_df['price'].apply(lambda x: f"${x:.2f}")
                    support_df['distance_pct'] = support_df['distance_pct'].apply(lambda x: f"-{x:.1f}%")
                    st.dataframe(support_df, use_container_width=True, hide_index=True)
                else:
                    st.info("No support levels - price below major retracements")
    
    def _render_money_flow_tab(self, selected_stocks, stock_names):
        """Render Money Flow Index analysis"""
        
        st.subheader("💰 Money Flow Index - Volume-Weighted RSI")
        st.write("Shows buying/selling pressure with volume - more accurate than regular RSI")
        
        for symbol in selected_stocks[:3]:
            with st.expander(f"💵 {symbol} - {stock_names.get(symbol, symbol)}", expanded=True):
                mfi = self.ta.calculate_money_flow_index(symbol, period='3mo')
                elder = self.ta.calculate_elder_ray(symbol, period='3mo')
                
                if not mfi:
                    st.warning(f"Unable to calculate Money Flow for {symbol}")
                    continue
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    mfi_color = "🔴" if mfi['current_mfi'] > 60 else "🟢" if mfi['current_mfi'] < 40 else "⚪"
                    st.metric("Money Flow Index", f"{mfi['current_mfi']:.1f}", delta=mfi_color)
                
                with col2:
                    ratio = mfi.get('money_flow_ratio', 1)
                    st.metric("Money Flow Ratio", f"{ratio:.2f}", 
                             delta="Buyers" if ratio > 1 else "Sellers")
                
                with col3:
                    if elder:
                        st.metric("Bull vs Bear Power", 
                                 f"Bull: {elder['current_bull_power']:.2f} | Bear: {elder['current_bear_power']:.2f}")
                
                st.write(f"**Signal:** {mfi['signal']}")
                
                if elder:
                    st.write(f"**Elder Ray:** {elder['signal']}")
                
                fig = make_subplots(
                    rows=2, cols=1,
                    shared_xaxes=True,
                    vertical_spacing=0.05,
                    subplot_titles=('Money Flow Index', 'Bull/Bear Power'),
                    row_heights=[0.6, 0.4]
                )
                
                valid_mfi = [(i, v) for i, v in enumerate(mfi['mfi']) if v is not None and not pd.isna(v)]
                if valid_mfi:
                    mfi_indices, mfi_values = zip(*valid_mfi)
                    mfi_dates = [mfi['dates'][i] for i in mfi_indices]
                    
                    fig.add_trace(go.Scatter(
                        x=mfi_dates,
                        y=mfi_values,
                        name='MFI',
                        line=dict(color='cyan', width=2)
                    ), row=1, col=1)
                
                fig.add_hline(y=80, line_dash="dash", line_color="red", 
                             annotation_text="Overbought", row=1, col=1)
                fig.add_hline(y=20, line_dash="dash", line_color="green",
                             annotation_text="Oversold", row=1, col=1)
                
                if elder:
                    valid_bull = [(i, v) for i, v in enumerate(elder['bull_power']) if v is not None and not pd.isna(v)]
                    valid_bear = [(i, v) for i, v in enumerate(elder['bear_power']) if v is not None and not pd.isna(v)]
                    
                    if valid_bull:
                        bull_indices, bull_values = zip(*valid_bull)
                        bull_dates = [elder['dates'][i] for i in bull_indices]
                        
                        fig.add_trace(go.Scatter(
                            x=bull_dates,
                            y=bull_values,
                            name='Bull Power',
                            line=dict(color='green', width=2)
                        ), row=2, col=1)
                    
                    if valid_bear:
                        bear_indices, bear_values = zip(*valid_bear)
                        bear_dates = [elder['dates'][i] for i in bear_indices]
                        
                        fig.add_trace(go.Scatter(
                            x=bear_dates,
                            y=bear_values,
                            name='Bear Power',
                            line=dict(color='red', width=2)
                        ), row=2, col=1)
                    
                    fig.add_hline(y=0, line_dash="dot", line_color="white", row=2, col=1)
                
                fig.update_layout(
                    title=f'{symbol} Money Flow Analysis',
                    template='plotly_dark',
                    height=600,
                    hovermode='x unified',
                    showlegend=True
                )
                
                st.plotly_chart(fig, use_container_width=True)
    
    def _render_market_breadth_tab(self, selected_stocks):
        """Render Market Breadth analysis"""
        
        st.subheader("🏢 Mining Sector Market Breadth")
        st.write("Measures the strength and health of the overall mining sector")
        
        breadth = self.ta.calculate_market_breadth(selected_stocks, period='1mo')
        
        if not breadth:
            st.warning("Unable to calculate market breadth")
            return
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Bullish Stocks", 
                     f"{breadth['bullish_stocks']}/{breadth['total_stocks']}", 
                     delta=f"{breadth['bullish_pct']:.0f}%")
        
        with col2:
            st.metric("Bearish Stocks",
                     f"{breadth['bearish_stocks']}/{breadth['total_stocks']}")
        
        with col3:
            st.metric("High Volume Stocks", breadth['high_volume_stocks'])
        
        with col4:
            strength_emoji = "🟢" if "Bullish" in breadth['sector_strength'] else "🔴" if "Bearish" in breadth['sector_strength'] else "⚪"
            st.metric("Sector Strength", breadth['sector_strength'], delta=strength_emoji)
        
        st.metric("Advance-Decline Line", breadth['advance_decline_line'],
                 help="Positive = More stocks advancing, Negative = More declining")
        
        st.subheader("📊 Individual Stock Analysis")
        
        ad_df = pd.DataFrame(breadth['advance_decline_data'])
        ad_df['ad_ratio'] = ad_df['ad_ratio'].apply(lambda x: f"{x:.2f}")
        st.dataframe(ad_df, use_container_width=True, hide_index=True)
        
        fig = go.Figure()
        
        symbols = [x['symbol'] for x in breadth['advance_decline_data']]
        ad_ratios = [x['ad_ratio'] for x in breadth['advance_decline_data']]
        
        colors = ['green' if float(ratio) > 1 else 'red' for ratio in ad_ratios]
        
        fig.add_trace(go.Bar(
            x=symbols,
            y=[float(x) for x in ad_ratios],
            marker_color=colors,
            name='Advance/Decline Ratio'
        ))
        
        fig.add_hline(y=1.0, line_dash="dash", line_color="white",
                     annotation_text="Neutral Line")
        
        fig.update_layout(
            title='Stock-by-Stock Advance/Decline Ratios',
            xaxis_title='Symbol',
            yaxis_title='A/D Ratio (>1 = Bullish)',
            template='plotly_dark',
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
