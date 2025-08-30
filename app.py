import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# Import custom modules
from utils.data_fetcher import DataFetcher
from utils.options_analyzer import OptionsAnalyzer
from utils.chart_builder import ChartBuilder
from components.stock_dashboard import StockDashboard
from components.options_dashboard import OptionsDashboard
from components.dark_pool_tracker import DarkPoolTracker
from components.weekly_outlook import WeeklyOutlook
from components.enhanced_technical import EnhancedTechnical
from components.sentiment_analysis import SentimentAnalysis
from components.risk_management import RiskManagement

# Page configuration
st.set_page_config(
    page_title="Bitcoin Mining Stock Tracker",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for professional styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #ff6b35, #f7931e, #ffcc02);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    .metric-card {
        background-color: #262730;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #00ff88;
    }
    
    .alert-box {
        background-color: #ff4444;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
    
    .success-box {
        background-color: #00ff88;
        color: #000;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

def main():
    # Header
    st.markdown('<h1 class="main-header">₿ Bitcoin Mining Stock Tracker</h1>', unsafe_allow_html=True)
    
    # Initialize components
    data_fetcher = DataFetcher()
    options_analyzer = OptionsAnalyzer()
    chart_builder = ChartBuilder()
    
    # Sidebar configuration
    st.sidebar.title("🔧 Dashboard Controls")
    
    # Bitcoin mining stocks
    MINING_STOCKS = {
        'MARA': 'Marathon Digital Holdings',
        'RIOT': 'Riot Platforms Inc',
        'CLSK': 'CleanSpark Inc',
        'HUT': 'Hut 8 Mining Corp',
        'BITF': 'Bitfarms Ltd',
        'BTBT': 'Bit Digital Inc',
        'CIFR': 'Cipher Mining Inc',
        'CORZ': 'Core Scientific Inc',
        'IREN': 'Iris Energy Ltd',
        'WULF': 'TeraWulf Inc'
    }
    
    # Stock selection
    selected_stocks = st.sidebar.multiselect(
        "Select Mining Stocks",
        options=list(MINING_STOCKS.keys()),
        default=['MARA', 'RIOT', 'CLSK', 'HUT'],
        help="Choose bitcoin mining stocks to track"
    )
    
    # Time range selection
    time_range = st.sidebar.selectbox(
        "Time Range",
        options=['1D', '5D', '1M', '3M', '6M', '1Y'],
        index=2,
        help="Select data time range"
    )
    
    # Auto-refresh toggle
    auto_refresh = st.sidebar.checkbox("Auto Refresh (30s)", value=False)
    
    # Refresh button
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()
    
    # Main dashboard tabs - Enhanced with new analytical components
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
        "📊 Stock Overview", 
        "⚡ Options Flow", 
        "🌊 Dark Pool Activity", 
        "📈 Technical Analysis",
        "🔬 Enhanced Technical", 
        "📰 Sentiment Analysis", 
        "⚠️ Risk Management",
        "🔮 Market Outlook"
    ])
    
    if not selected_stocks:
        st.warning("Please select at least one mining stock to track.")
        return
    
    try:
        # Fetch stock data
        with st.spinner("Fetching market data..."):
            stock_data = data_fetcher.get_stock_data(selected_stocks, time_range)
            
        if stock_data.empty:
            st.error("No stock data available. Please check your selection and try again.")
            return
            
        # Tab 1: Stock Overview
        with tab1:
            stock_dashboard = StockDashboard()
            stock_dashboard.render(stock_data, selected_stocks, MINING_STOCKS, chart_builder)
        
        # Tab 2: Options Flow
        with tab2:
            options_dashboard = OptionsDashboard()
            options_dashboard.render(selected_stocks, options_analyzer, chart_builder)
        
        # Tab 3: Dark Pool Activity
        with tab3:
            dark_pool_tracker = DarkPoolTracker()
            dark_pool_tracker.render(selected_stocks, data_fetcher, chart_builder)
        
        # Tab 4: Technical Analysis
        with tab4:
            render_technical_analysis(stock_data, selected_stocks, chart_builder)
        
        # Tab 5: Enhanced Technical Analysis
        with tab5:
            enhanced_technical = EnhancedTechnical()
            enhanced_technical.render(selected_stocks, MINING_STOCKS)
        
        # Tab 6: Sentiment Analysis
        with tab6:
            sentiment_analysis = SentimentAnalysis()
            sentiment_analysis.render(selected_stocks, MINING_STOCKS)
        
        # Tab 7: Risk Management
        with tab7:
            risk_management = RiskManagement()
            risk_management.render(selected_stocks, MINING_STOCKS)
        
        # Tab 8: Market Outlook (Enhanced Weekly/Monthly)
        with tab8:
            weekly_outlook = WeeklyOutlook()
            weekly_outlook.render(selected_stocks, MINING_STOCKS)
            
    except Exception as e:
        st.error(f"An error occurred while fetching data: {str(e)}")
        st.info("Please check your internet connection and try again.")
    
    # Auto-refresh functionality
    if auto_refresh:
        time.sleep(30)
        st.rerun()

def render_technical_analysis(stock_data, selected_stocks, chart_builder):
    """Render technical analysis section"""
    st.subheader("📈 Technical Analysis")
    
    if stock_data.empty:
        st.warning("No data available for technical analysis.")
        return
    
    for symbol in selected_stocks:
        if symbol in stock_data.columns:
            with st.expander(f"{symbol} Technical Indicators", expanded=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    # Price chart with moving averages
                    fig = chart_builder.create_candlestick_chart(symbol, stock_data)
                    if fig:
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    # Volume analysis
                    volume_fig = chart_builder.create_volume_chart(symbol, stock_data)
                    if volume_fig:
                        st.plotly_chart(volume_fig, use_container_width=True)
                
                # Technical indicators
                st.subheader("Key Indicators")
                
                try:
                    prices = stock_data[symbol].dropna()
                    if len(prices) > 20:
                        # Calculate basic indicators
                        sma_20 = prices.rolling(20).mean().iloc[-1]
                        sma_50 = prices.rolling(50).mean().iloc[-1] if len(prices) > 50 else None
                        current_price = prices.iloc[-1]
                        
                        # RSI calculation
                        rsi = calculate_rsi(prices)
                        
                        col1, col2, col3, col4 = st.columns(4)
                        
                        with col1:
                            st.metric("Current Price", f"${current_price:.2f}")
                        
                        with col2:
                            st.metric("SMA 20", f"${sma_20:.2f}")
                        
                        with col3:
                            if sma_50:
                                st.metric("SMA 50", f"${sma_50:.2f}")
                        
                        with col4:
                            st.metric("RSI", f"{rsi:.1f}")
                            
                except Exception as e:
                    st.error(f"Error calculating technical indicators for {symbol}: {str(e)}")

def calculate_rsi(prices, window=14):
    """Calculate Relative Strength Index"""
    if len(prices) < window + 1:
        return 50.0
        
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0

if __name__ == "__main__":
    main()
