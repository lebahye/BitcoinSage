"""
app.py — BitcoinSage Dashboard
Phase 4: Clean 10-tab rebuild
"""

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time

# Utils
from utils.unified_data_fetcher import DataFetcher
from utils.options_analytics import OptionsAnalytics as OptionsAnalyzer
from utils.chart_builder import ChartBuilder

# Components
from components.stock_dashboard import StockDashboard
from components.next_mover_dashboard import NextMoverDashboard
from components.unified_options import UnifiedOptions
from components.dark_pool_tracker import DarkPoolTracker
from components.advanced_ta_dashboard import AdvancedTADashboard
from components.polymarket_tracker import PolymarketTracker
from components.sentiment_analysis import SentimentAnalysis
from components.risk_center import RiskCenter
from components.personal_portfolio import PersonalPortfolio
from components.riot_protection import RIOTProtection
from components.backtesting_dashboard import BacktestingDashboard
from components.weekly_outlook import WeeklyOutlook
from components.volatility_hole_chart import VolatilityHoleChart

# ─── Page config ────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="BitcoinSage",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ─── Mining stocks ───────────────────────────────────────────────────────────

MINING_STOCKS = {
    'MARA': 'Marathon Digital Holdings',
    'RIOT': 'Riot Platforms Inc',
    'CLSK': 'CleanSpark Inc',
    'HUT':  'Hut 8 Mining Corp',
    'BITF': 'Bitfarms Ltd',
    'BTBT': 'Bit Digital Inc',
    'CIFR': 'Cipher Mining Inc',
    'CORZ': 'Core Scientific Inc',
    'IREN': 'Iris Energy Ltd',
    'WULF': 'TeraWulf Inc',
}


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    st.markdown('<h1 class="main-header">₿ BitcoinSage</h1>', unsafe_allow_html=True)

    # ── Sidebar ──────────────────────────────────────────────────────────────
    st.sidebar.title("🔧 Dashboard Controls")

    selected_stocks = st.sidebar.multiselect(
        "Select Mining Stocks",
        options=list(MINING_STOCKS.keys()),
        default=['MARA', 'RIOT', 'CLSK', 'HUT'],
        help="Choose bitcoin mining stocks to track"
    )

    time_range = st.sidebar.selectbox(
        "Time Range",
        options=['1D', '5D', '1M', '3M', '6M', '1Y'],
        index=2,
        help="Select data time range"
    )

    auto_refresh = st.sidebar.checkbox("Auto Refresh (30s)", value=False)

    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()

    if not selected_stocks:
        st.warning("Please select at least one mining stock.")
        return

    # ── Shared instances ─────────────────────────────────────────────────────
    data_fetcher     = DataFetcher()
    options_analyzer = OptionsAnalyzer()
    chart_builder    = ChartBuilder()

    # ── Tabs ─────────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📊 Market Overview",
        "🎯 AI Predictions",
        "⚡ Options Center",
        "🌊 Institutional Flow",
        "📈 Technical Analysis",
        "📡 Live Polymarket",
        "📰 Sentiment & News",
        "⚠️ Risk Center",
        "🏆 Portfolio",
        "🔬 Strategy Lab",
    ])

    tab_market, tab_ai, tab_options, tab_flow, tab_ta, \
    tab_poly, tab_sentiment, tab_risk, tab_portfolio, tab_lab = tabs

    # ── Fetch shared stock data once ─────────────────────────────────────────
    with st.spinner("Fetching market data..."):
        try:
            stock_data = data_fetcher.get_stock_data(selected_stocks, time_range)
            stock_data_available = not stock_data.empty
        except Exception as e:
            stock_data = pd.DataFrame()
            stock_data_available = False
            st.warning(f"⚠️ Data fetch error: {e}")

    if not stock_data_available:
        st.warning(
            "⚠️ Yahoo Finance rate limit reached. Tabs requiring price data are disabled. "
            "Try selecting fewer stocks or refreshing in 30 seconds. "
            "**Working tabs:** 📡 Live Polymarket · 📰 Sentiment & News · 🔬 Strategy Lab (Backtesting)"
        )

    # ── Tab 1 — Market Overview ───────────────────────────────────────────────
    with tab_market:
        if not stock_data_available:
            st.error("Stock data unavailable. Select fewer stocks or refresh.")
        else:
            StockDashboard().render(stock_data, selected_stocks, MINING_STOCKS, chart_builder)

    # ── Tab 2 — AI Predictions ────────────────────────────────────────────────
    with tab_ai:
        try:
            NextMoverDashboard().render(data_fetcher, options_analyzer)
        except Exception as e:
            st.error(f"AI Predictions error: {e}")

    # ── Tab 3 — Options Center ────────────────────────────────────────────────
    with tab_options:
        if not stock_data_available:
            st.error("Options data requires stock data. Refresh when rate limit clears.")
        else:
            try:
                UnifiedOptions().render(
                    selected_stocks, options_analyzer, chart_builder, MINING_STOCKS
                )
            except Exception as e:
                st.error(f"Options Center error: {e}")

    # ── Tab 4 — Institutional Flow ────────────────────────────────────────────
    with tab_flow:
        if not stock_data_available:
            st.error("Dark pool analysis requires stock data.")
        else:
            try:
                DarkPoolTracker().render(selected_stocks, data_fetcher, chart_builder)
            except Exception as e:
                st.error(f"Institutional Flow error: {e}")

    # ── Tab 5 — Technical Analysis ─────────────────────────────────────────────
    with tab_ta:
        if not stock_data_available:
            st.error("Technical analysis requires stock data.")
        else:
            try:
                ta = AdvancedTADashboard()
                sub_standard, sub_advanced = st.tabs([
                    "📊 Standard Indicators",
                    "⚡ Advanced TA (Pro)"
                ])
                with sub_standard:
                    ta.render_enhanced(selected_stocks, MINING_STOCKS)
                with sub_advanced:
                    ta.render(selected_stocks, MINING_STOCKS)
            except Exception as e:
                st.error(f"Technical Analysis error: {e}")

    # ── Tab 6 — Live Polymarket ────────────────────────────────────────────────
    with tab_poly:
        try:
            PolymarketTracker().render()
        except Exception as e:
            st.error(f"Polymarket error: {e}")

    # ── Tab 7 — Sentiment & News ───────────────────────────────────────────────
    with tab_sentiment:
        try:
            SentimentAnalysis().render(list(MINING_STOCKS.keys()))
        except Exception as e:
            st.error(f"Sentiment error: {e}")

    # ── Tab 8 — Risk Center ────────────────────────────────────────────────────
    with tab_risk:
        if not stock_data_available:
            st.error("Risk analysis requires stock data.")
        else:
            try:
                RiskCenter().render(selected_stocks, MINING_STOCKS)
            except Exception as e:
                st.error(f"Risk Center error: {e}")

    # ── Tab 9 — Portfolio ──────────────────────────────────────────────────────
    with tab_portfolio:
        if not stock_data_available:
            st.error("Portfolio tracking requires stock data.")
        else:
            try:
                sub_portfolio, sub_riot = st.tabs([
                    "🏆 Your Portfolio",
                    "🛡️ RIOT Protection"
                ])
                with sub_portfolio:
                    PersonalPortfolio().render(data_fetcher, options_analyzer)
                with sub_riot:
                    RIOTProtection().render(data_fetcher, options_analyzer)
            except Exception as e:
                st.error(f"Portfolio error: {e}")

    # ── Tab 10 — Strategy Lab ──────────────────────────────────────────────────
    with tab_lab:
        try:
            sub_backtest, sub_outlook, sub_volhole = st.tabs([
                "🔬 Backtesting",
                "🔮 Market Outlook",
                "🕳️ Volatility Hole"
            ])

            with sub_backtest:
                BacktestingDashboard().render(selected_stocks, MINING_STOCKS)

            with sub_outlook:
                if not stock_data_available:
                    st.error("Market outlook requires stock data.")
                else:
                    WeeklyOutlook().render(selected_stocks, MINING_STOCKS)

            with sub_volhole:
                if not stock_data_available:
                    st.error("Volatility hole analysis requires stock data.")
                else:
                    st.title("🕳️ Volatility Hole Indicator")
                    st.markdown("### Danny Cheng's Favorite — Spots Low Volatility Before Major Moves")
                    st.info("""
                    **What You'll See:**
                    - 🟡 **Yellow lines** = Volatility holes (consolidation zones)
                    - 🔥 **Breakout markers** = When the hole releases (up or down)
                    - 📊 **Score below 25** = hole forming | **above 75** = breakout
                    """)
                    vol_hole = VolatilityHoleChart()
                    for symbol in selected_stocks:
                        with st.expander(
                            f"📈 {symbol} - Volatility Hole Analysis",
                            expanded=(symbol == selected_stocks[0])
                        ):
                            vol_hole.render(symbol, data_fetcher)

        except Exception as e:
            st.error(f"Strategy Lab error: {e}")

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if auto_refresh:
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = time.time()
        current_time = time.time()
        elapsed = current_time - st.session_state.last_refresh
        if elapsed >= 30:
            st.session_state.last_refresh = current_time
            st.rerun()
        else:
            st.sidebar.info(f"Next refresh in {30 - elapsed:.0f}s")


if __name__ == "__main__":
    main()
