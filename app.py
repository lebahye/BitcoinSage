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
from components.sentiment_dashboard import SentimentDashboard
from components.risk_management import RiskManagement
from components.options_evaluator import OptionsEvaluator
from components.riot_protection import RIOTProtection
from components.polymarket_tracker import PolymarketTracker
from components.personal_portfolio import PersonalPortfolio
from components.volatility_hole_chart import VolatilityHoleChart
from components.advanced_ta_dashboard import AdvancedTADashboard
from components.pro_options_dashboard import ProOptionsDashboard
from components.risk_dashboard import RiskDashboard
from components.backtesting_dashboard import BacktestingDashboard
from components.next_mover_dashboard import NextMoverDashboard

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
    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14, tab15, tab16, tab17 = st.tabs([
        "📊 Stock Overview", 
        "🎯 Next Mover Prediction",
        "⚡ Options Flow", 
        "🌊 Dark Pool Activity", 
        "📈 Technical Analysis",
        "🔬 Enhanced Technical",
        "⚡ Advanced TA (Pro)",
        "📊 Pro Options Analytics",
        "📰 Sentiment Analysis", 
        "⚠️ Risk Management",
        "🔮 Market Outlook",
        "🎯 Options Evaluator",
        "🛡️ RIOT Protection",
        "🎲 Mining Prediction Markets",
        "🏆 Your Portfolio",
        "🕳️ Volatility Hole",
        "🔬 Backtesting Lab"
    ])
    
    if not selected_stocks:
        st.warning("Please select at least one mining stock to track.")
        return
    
    try:
        # Fetch stock data
        with st.spinner("Fetching market data..."):
            stock_data = data_fetcher.get_stock_data(selected_stocks, time_range)
        
        stock_data_available = not stock_data.empty
        
        if not stock_data_available:
            st.warning("⚠️ Yahoo Finance rate limit reached. Some tabs require stock data and won't work. Try: Sentiment Analysis, Backtesting Lab, or select fewer stocks and refresh.")
            
        # Tab 1: Stock Overview
        with tab1:
            if not stock_data_available:
                st.error("Stock data unavailable due to Yahoo Finance rate limits. Please select fewer stocks or wait 30 seconds and refresh.")
                st.info("💡 **Working Tabs**: Sentiment Analysis (Tab 9), Backtesting Lab (Tab 17)")
                return
            stock_dashboard = StockDashboard()
            stock_dashboard.render(stock_data, selected_stocks, MINING_STOCKS, chart_builder)
        
        # Tab 2: Next Mover Prediction (AI-powered prediction engine)
        with tab2:
            next_mover = NextMoverDashboard()
            next_mover.render(data_fetcher, options_analyzer)
        
        # Tab 3: Options Flow
        with tab3:
            if not stock_data_available:
                st.error("Options data requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                options_dashboard = OptionsDashboard()
                options_dashboard.render(selected_stocks, options_analyzer, chart_builder)
        
        # Tab 4: Dark Pool Activity
        with tab4:
            if not stock_data_available:
                st.error("Dark pool data requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                dark_pool_tracker = DarkPoolTracker()
                dark_pool_tracker.render(selected_stocks, data_fetcher, chart_builder)
        
        # Tab 5: Technical Analysis
        with tab5:
            if not stock_data_available:
                st.error("Technical analysis requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                render_technical_analysis(stock_data, selected_stocks, chart_builder)
        
        # Tab 6: Enhanced Technical Analysis
        with tab6:
            if not stock_data_available:
                st.error("Enhanced TA requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                enhanced_technical = EnhancedTechnical()
                enhanced_technical.render(selected_stocks, MINING_STOCKS)
        
        # Tab 7: Advanced TA (Professional-grade indicators)
        with tab7:
            if not stock_data_available:
                st.error("Advanced TA requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                advanced_ta = AdvancedTADashboard()
                advanced_ta.render(selected_stocks, MINING_STOCKS)
        
        # Tab 8: Pro Options Analytics
        with tab8:
            if not stock_data_available:
                st.error("Options analytics requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                pro_options = ProOptionsDashboard()
                pro_options.render(selected_stocks, MINING_STOCKS)
        
        # Tab 9: News Sentiment Analysis (Alpha Vantage powered - WORKS WITHOUT YAHOO DATA)
        with tab9:
            sentiment_dashboard = SentimentDashboard()
            sentiment_dashboard.render(list(MINING_STOCKS.keys()))
        
        # Tab 10: Risk Management (Professional)
        with tab10:
            if not stock_data_available:
                st.error("Risk analysis requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                risk_dashboard = RiskDashboard()
                risk_dashboard.render(selected_stocks, MINING_STOCKS)
        
        # Tab 11: Market Outlook (Enhanced Weekly/Monthly)
        with tab11:
            if not stock_data_available:
                st.error("Market outlook requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                weekly_outlook = WeeklyOutlook()
                weekly_outlook.render(selected_stocks, MINING_STOCKS)
        
        # Tab 12: Options Evaluator (Purchase Recommendations)
        with tab12:
            if not stock_data_available:
                st.error("Options evaluator requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                options_evaluator = OptionsEvaluator()
                options_evaluator.render(selected_stocks, options_analyzer, chart_builder)
        
        # Tab 13: RIOT Protection Strategies
        with tab13:
            if not stock_data_available:
                st.error("RIOT protection requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                riot_protection = RIOTProtection()
                riot_protection.render(data_fetcher, options_analyzer)
        
        # Tab 14: Bitcoin Mining Prediction Markets (WORKS WITHOUT YAHOO DATA)
        with tab14:
            polymarket_tracker = PolymarketTracker()
            polymarket_tracker.render()
        
        # Tab 15: Personal Portfolio
        with tab15:
            if not stock_data_available:
                st.error("Portfolio tracking requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                personal_portfolio = PersonalPortfolio()
                personal_portfolio.render(data_fetcher, options_analyzer)
        
        # Tab 16: Volatility Hole Chart (Danny Cheng's Favorite Indicator)
        with tab16:
            if not stock_data_available:
                st.error("Volatility hole analysis requires stock data. Yahoo Finance rate limited - select fewer stocks or wait 30s and refresh.")
            else:
                volatility_hole = VolatilityHoleChart()
                
                st.title("🕳️ Volatility Hole Indicator")
                st.markdown("### Danny Cheng's Favorite - Spots Low Volatility Before Major Moves")
                
                st.info("""
                **What You'll See:**
                - 🟡 **Yellow lines** = Volatility holes (consolidation zones)  
                - 🔥 **Breakout markers** = When the hole releases (up or down)  
                - 📊 **Volatility score** = Below 25 = hole forming, Above 75 = breakout  
                - 📊 **Momentum bars** = Green/red showing price direction
                """)
                
                for symbol in selected_stocks:
                    with st.expander(f"📈 {symbol} - Volatility Hole Analysis", expanded=True if symbol == 'RIOT' else False):
                        volatility_hole.render(symbol, data_fetcher)
        
        # Tab 17: Backtesting Lab (WORKS WITHOUT YAHOO DATA)
        with tab17:
            backtesting_dashboard = BacktestingDashboard()
            backtesting_dashboard.render(selected_stocks, MINING_STOCKS)
            
    except Exception as e:
        st.error(f"An error occurred while fetching data: {str(e)}")
        st.info("Please check your internet connection and try again.")
    
    # Auto-refresh functionality with 30-second gating
    if auto_refresh:
        # Initialize session state for refresh tracking
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = time.time()
        
        # Check if 30 seconds have passed since last refresh
        current_time = time.time()
        if current_time - st.session_state.last_refresh >= 30:
            st.session_state.last_refresh = current_time
            st.rerun()
        else:
            # Display countdown until next refresh
            time_until_refresh = 30 - (current_time - st.session_state.last_refresh)
            st.sidebar.info(f"Next auto-refresh in {time_until_refresh:.0f}s")

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
                        st.plotly_chart(volume_fig, width='stretch')
                
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
