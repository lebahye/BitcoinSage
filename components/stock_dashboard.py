import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

class StockDashboard:
    """Main stock dashboard component"""
    
    def render(self, stock_data, selected_stocks, stock_names, chart_builder):
        """Render the main stock dashboard"""
        
        # (BTC / VIX / S&P / sector strip now lives once, in the Command Center at the top)

        # Stock performance grid
        self._render_performance_grid(stock_data, selected_stocks, stock_names)
        
        # Interactive charts
        st.subheader("📈 Price Charts")
        self._render_price_charts(stock_data, selected_stocks, chart_builder)
        
        # Correlation now lives in one place: the 🔗 RIOT Correlation Map tab
        st.caption("🔗 For how these stocks move together (and versus Bitcoin, AI stocks and the VIX), "
                   "see the **RIOT Correlation Map** tab.")
    
    def _render_market_overview(self, stock_data=None):
        """Render market overview section"""
        st.subheader("🌍 Market Overview")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            # Bitcoin price
            try:
                import yfinance as yf
                btc = yf.Ticker("BTC-USD")
                btc_data = btc.history(period='2d')
                
                if not btc_data.empty:
                    current_btc = btc_data['Close'].iloc[-1]
                    prev_btc = btc_data['Close'].iloc[-2] if len(btc_data) > 1 else current_btc
                    btc_change = ((current_btc - prev_btc) / prev_btc) * 100
                    
                    st.metric(
                        "Bitcoin Price",
                        f"${current_btc:,.0f}",
                        f"{btc_change:+.2f}%"
                    )
                else:
                    st.metric("Bitcoin Price", "N/A", "N/A")
            except:
                st.metric("Bitcoin Price", "Error", "N/A")
        
        with col2:
            # VIX Fear & Greed
            try:
                import yfinance as yf
                vix = yf.Ticker("^VIX")
                vix_data = vix.history(period='2d')
                
                if not vix_data.empty:
                    current_vix = vix_data['Close'].iloc[-1]
                    prev_vix = vix_data['Close'].iloc[-2] if len(vix_data) > 1 else current_vix
                    vix_change = current_vix - prev_vix
                    
                    st.metric(
                        "VIX (Fear Index)",
                        f"{current_vix:.2f}",
                        f"{vix_change:+.2f}"
                    )
                else:
                    st.metric("VIX (Fear Index)", "N/A", "N/A")
            except:
                st.metric("VIX (Fear Index)", "Error", "N/A")
        
        with col3:
            # Market sentiment
            try:
                import yfinance as yf
                spy = yf.Ticker("SPY")
                spy_data = spy.history(period='2d')
                
                if not spy_data.empty:
                    current_spy = spy_data['Close'].iloc[-1]
                    prev_spy = spy_data['Close'].iloc[-2] if len(spy_data) > 1 else current_spy
                    spy_change = ((current_spy - prev_spy) / prev_spy) * 100
                    
                    st.metric(
                        "S&P 500",
                        f"${current_spy:.2f}",
                        f"{spy_change:+.2f}%"
                    )
                else:
                    st.metric("S&P 500", "N/A", "N/A")
            except:
                st.metric("S&P 500", "Error", "N/A")
        
        with col4:
            # Mining sector average
            if stock_data is not None and not stock_data.empty:
                latest_prices = stock_data.iloc[-1]
                prev_prices = stock_data.iloc[-2] if len(stock_data) > 1 else latest_prices
                
                sector_change = ((latest_prices.mean() - prev_prices.mean()) / prev_prices.mean()) * 100
                
                st.metric(
                    "Mining Sector Avg",
                    f"{sector_change:+.2f}%",
                    "Daily Change"
                )
            else:
                st.metric("Mining Sector Avg", "N/A", "N/A")
    
    def _render_performance_grid(self, stock_data, selected_stocks, stock_names):
        """Performance table from DAILY closes.

        The old version used the chart data, which is hourly for the default 1M
        range, so 'Daily %' was really the last hour, 'Week %' the last 5 hours
        and volatility was annualised from hourly returns.
        """
        from utils.market_data import fetch_daily_closes
        from utils.explain import HELP
        st.subheader("💰 Stock Performance")
        daily = fetch_daily_closes(tuple(selected_stocks), "1y")
        if daily.empty:
            st.warning("No daily price history available for the performance table.")
            return

        def chg(p, n):
            return (p.iloc[-1] / p.iloc[-1 - n] - 1) * 100 if len(p) > n else None

        rows = []
        for symbol in selected_stocks:
            if symbol not in daily.columns:
                continue
            p = daily[symbol].dropna()
            if len(p) < 2:
                continue
            vol = p.pct_change(fill_method=None).iloc[-63:].std() * np.sqrt(252) * 100
            dd = (p.iloc[-1] / p.max() - 1) * 100
            fmt = lambda v: "n/a" if v is None else f"{v:+.1f}%"
            rows.append({
                'Symbol': symbol, 'Company': stock_names.get(symbol, symbol),
                'Last close': f"${p.iloc[-1]:.2f}",
                '1 day': fmt(chg(p, 1)), '1 week': fmt(chg(p, 5)), '1 month': fmt(chg(p, 21)),
                '3 months': fmt(chg(p, 63)), '1 year': fmt(chg(p, len(p) - 1)) if len(p) > 200 else "n/a",
                'From 1y high': f"{dd:+.0f}%", 'Volatility (3M, yearly)': f"{vol:.0f}%",
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption(f"Daily closes from Yahoo Finance through {daily.index[-1].date()}. "
                       "'From 1y high' = drawdown. " + HELP["volatility"])
        else:
            st.warning("No performance data available.")

    def _render_price_charts(self, stock_data, selected_stocks, chart_builder):
        """Render interactive price charts"""
        
        if stock_data.empty:
            st.warning("No data available for charting.")
            return
        
        # Chart selection
        chart_type = st.selectbox(
            "Chart Type",
            options=["Line Chart", "Candlestick Chart", "Performance Comparison"],
            index=0
        )
        
        if chart_type == "Performance Comparison":
            # Normalize all stocks for comparison
            fig = chart_builder.create_performance_comparison(stock_data, {})
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        else:
            # Individual stock charts
            cols = st.columns(2)
            
            for i, symbol in enumerate(selected_stocks[:4]):  # Limit to 4 charts
                col = cols[i % 2]
                
                with col:
                    if chart_type == "Line Chart":
                        fig = chart_builder.create_price_chart(symbol, stock_data, show_volume=True)
                    else:  # Candlestick
                        fig = chart_builder.create_candlestick_chart(symbol, stock_data)
                    
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning(f"No chart data available for {symbol}")
    
    def _render_correlation_analysis(self, stock_data, chart_builder):
        """Render correlation analysis"""
        
        if stock_data.empty or len(stock_data.columns) < 2:
            st.warning("Need at least 2 stocks for correlation analysis.")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Correlation heatmap
            fig = chart_builder.create_correlation_heatmap(stock_data)
            if fig:
                st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Correlation insights
            st.subheader("Correlation Insights")
            
            try:
                returns = stock_data.pct_change().dropna()
                correlation_matrix = returns.corr()
                
                # Find highest and lowest correlations
                corr_pairs = []
                for i in range(len(correlation_matrix.columns)):
                    for j in range(i+1, len(correlation_matrix.columns)):
                        stock1 = correlation_matrix.columns[i]
                        stock2 = correlation_matrix.columns[j]
                        corr_value = correlation_matrix.iloc[i, j]
                        corr_pairs.append((stock1, stock2, corr_value))
                
                # Sort by correlation value
                corr_pairs.sort(key=lambda x: abs(x[2]), reverse=True)
                
                st.write("**Highest Correlations:**")
                for stock1, stock2, corr in corr_pairs[:3]:
                    if corr > 0.7:
                        st.success(f"{stock1} ↔ {stock2}: {corr:.3f} (Strong)")
                    elif corr > 0.5:
                        st.info(f"{stock1} ↔ {stock2}: {corr:.3f} (Moderate)")
                    else:
                        st.warning(f"{stock1} ↔ {stock2}: {corr:.3f} (Weak)")
                
                # Calculate average correlation
                avg_corr = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, 1)].mean()
                st.metric("Average Correlation", f"{avg_corr:.3f}")
                
                if avg_corr > 0.7:
                    st.info("High sector correlation - stocks move together")
                elif avg_corr > 0.5:
                    st.info("Moderate sector correlation - some diversification benefit")
                else:
                    st.info("Low sector correlation - good diversification")
                    
            except Exception as e:
                st.error(f"Error in correlation analysis: {str(e)}")
