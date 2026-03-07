"""
app.py — BitcoinSage Dashboard
Phase 5: Polished — shared styles, cached components, loading states
"""

import streamlit as st
import pandas as pd
import time

# Utils
from utils.unified_data_fetcher import DataFetcher
from utils.options_analytics import OptionsAnalytics as OptionsAnalyzer
from utils.chart_builder import ChartBuilder
from utils.styles import inject_styles, main_header, data_badge

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
from components.reflexivity_dashboard import ReflexivityDashboard

# ─── Page config (must be first Streamlit call) ──────────────────────────────

st.set_page_config(
    page_title="BitcoinSage",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

# ─── Cached component instances (survive reruns, init once per session) ──────

@st.cache_resource
def get_data_fetcher():
    return DataFetcher()

@st.cache_resource
def get_options_analyzer():
    return OptionsAnalyzer()

@st.cache_resource
def get_chart_builder():
    return ChartBuilder()

@st.cache_resource
def get_stock_dashboard():
    return StockDashboard()

@st.cache_resource
def get_next_mover():
    return NextMoverDashboard()

@st.cache_resource
def get_unified_options():
    return UnifiedOptions()

@st.cache_resource
def get_dark_pool():
    return DarkPoolTracker()

@st.cache_resource
def get_advanced_ta():
    return AdvancedTADashboard()

@st.cache_resource
def get_polymarket():
    return PolymarketTracker()

@st.cache_resource
def get_sentiment():
    return SentimentAnalysis()

@st.cache_resource
def get_risk_center():
    return RiskCenter()

@st.cache_resource
def get_portfolio():
    return PersonalPortfolio()

@st.cache_resource
def get_riot():
    return RIOTProtection()

@st.cache_resource
def get_backtesting():
    return BacktestingDashboard()

@st.cache_resource
def get_weekly_outlook():
    return WeeklyOutlook()

@st.cache_resource
def get_vol_hole():
    return VolatilityHoleChart()

@st.cache_resource
def get_reflexivity():
    return ReflexivityDashboard()


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _no_data_error(tab_name: str):
    st.error(
        f"**{tab_name}** requires live price data. "
        "Yahoo Finance rate limit reached — select fewer stocks or refresh in 30 s."
    )
    st.info("✅ Tabs that work offline: 📡 Live Polymarket · 📰 Sentiment & News · 🔬 Backtesting")


def _tab_error(tab_name: str, exc: Exception):
    st.error(f"**{tab_name}** encountered an error: `{exc}`")
    st.caption("Check the terminal for a full traceback.")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    inject_styles()
    main_header("₿ BitcoinSage")

    # ── Sidebar ──────────────────────────────────────────────────────────────
    st.sidebar.title("🔧 Controls")

    selected_stocks = st.sidebar.multiselect(
        "Mining Stocks",
        options=list(MINING_STOCKS.keys()),
        default=['MARA', 'RIOT', 'CLSK', 'HUT'],
        help="Select up to 10 Bitcoin mining stocks"
    )

    time_range = st.sidebar.selectbox(
        "Time Range",
        options=['1D', '5D', '1M', '3M', '6M', '1Y'],
        index=2,
    )

    auto_refresh = st.sidebar.checkbox("Auto Refresh (30 s)", value=False)

    if st.sidebar.button("🔄 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.sidebar.markdown("---")

    if not selected_stocks:
        st.warning("👈 Select at least one mining stock from the sidebar.")
        return

    # ── Shared instances ─────────────────────────────────────────────────────
    data_fetcher     = get_data_fetcher()
    options_analyzer = get_options_analyzer()
    chart_builder    = get_chart_builder()

    # ── Fetch stock data ─────────────────────────────────────────────────────
    stock_data_available = False
    stock_data = pd.DataFrame()

    with st.spinner("📡 Fetching market data…"):
        try:
            stock_data = data_fetcher.get_stock_data(selected_stocks, time_range)
            stock_data_available = not stock_data.empty
        except Exception as e:
            st.warning(f"⚠️ Data fetch error: {e}")

    # Data source badge in sidebar
    with st.sidebar:
        if stock_data_available:
            source = "live" if getattr(data_fetcher, 'using_schwab', False) else "delayed"
        else:
            source = "offline"
        data_badge(source)
        if source == "delayed":
            st.caption("Yahoo Finance (15-min delay)")
        elif source == "live":
            st.caption("Schwab API (real-time)")
        else:
            st.caption("Rate limited — refresh soon")

    if not stock_data_available:
        st.warning(
            "⚠️ Price data unavailable (Yahoo Finance rate limit). "
            "**Live Polymarket**, **Sentiment & News**, and **Backtesting** still work."
        )

    # ── 10 Tabs ──────────────────────────────────────────────────────────────
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
        "🔄 Reflexivity",
    ])

    (tab_market, tab_ai, tab_options, tab_flow, tab_ta,
     tab_poly, tab_sentiment, tab_risk, tab_portfolio, tab_lab,
     tab_reflex) = tabs

    # ── 1 · Market Overview ───────────────────────────────────────────────────
    with tab_market:
        if not stock_data_available:
            _no_data_error("Market Overview")
        else:
            with st.spinner("Loading market overview…"):
                try:
                    get_stock_dashboard().render(
                        stock_data, selected_stocks, MINING_STOCKS, chart_builder)
                except Exception as e:
                    _tab_error("Market Overview", e)

    # ── 2 · AI Predictions ────────────────────────────────────────────────────
    with tab_ai:
        with st.spinner("Running AI prediction engine…"):
            try:
                get_next_mover().render(data_fetcher, options_analyzer)
            except Exception as e:
                _tab_error("AI Predictions", e)

    # ── 3 · Options Center ────────────────────────────────────────────────────
    with tab_options:
        if not stock_data_available:
            _no_data_error("Options Center")
        else:
            with st.spinner("Loading options data…"):
                try:
                    get_unified_options().render(
                        selected_stocks, options_analyzer, chart_builder, MINING_STOCKS)
                except Exception as e:
                    _tab_error("Options Center", e)

    # ── 4 · Institutional Flow ────────────────────────────────────────────────
    with tab_flow:
        if not stock_data_available:
            _no_data_error("Institutional Flow")
        else:
            with st.spinner("Analyzing dark pool activity…"):
                try:
                    get_dark_pool().render(selected_stocks, data_fetcher, chart_builder)
                except Exception as e:
                    _tab_error("Institutional Flow", e)

    # ── 5 · Technical Analysis ────────────────────────────────────────────────
    with tab_ta:
        if not stock_data_available:
            _no_data_error("Technical Analysis")
        else:
            sub_std, sub_adv = st.tabs(["📊 Standard Indicators", "⚡ Advanced TA (Pro)"])
            ta = get_advanced_ta()
            with sub_std:
                with st.spinner("Computing technical indicators…"):
                    try:
                        ta.render_enhanced(selected_stocks, MINING_STOCKS)
                    except Exception as e:
                        _tab_error("Standard Indicators", e)
            with sub_adv:
                with st.spinner("Computing advanced indicators…"):
                    try:
                        ta.render(selected_stocks, MINING_STOCKS)
                    except Exception as e:
                        _tab_error("Advanced TA", e)

    # ── 6 · Live Polymarket ────────────────────────────────────────────────────
    with tab_poly:
        with st.spinner("Connecting to Polymarket feed…"):
            try:
                get_polymarket().render()
            except Exception as e:
                _tab_error("Live Polymarket", e)

    # ── 7 · Sentiment & News ──────────────────────────────────────────────────
    with tab_sentiment:
        with st.spinner("Fetching news sentiment…"):
            try:
                get_sentiment().render(list(MINING_STOCKS.keys()))
            except Exception as e:
                _tab_error("Sentiment & News", e)

    # ── 8 · Risk Center ───────────────────────────────────────────────────────
    with tab_risk:
        if not stock_data_available:
            _no_data_error("Risk Center")
        else:
            with st.spinner("Calculating risk metrics…"):
                try:
                    get_risk_center().render(selected_stocks, MINING_STOCKS)
                except Exception as e:
                    _tab_error("Risk Center", e)

    # ── 9 · Portfolio ─────────────────────────────────────────────────────────
    with tab_portfolio:
        if not stock_data_available:
            _no_data_error("Portfolio")
        else:
            sub_port, sub_riot = st.tabs(["🏆 Your Portfolio", "🛡️ RIOT Protection"])
            with sub_port:
                with st.spinner("Loading portfolio…"):
                    try:
                        get_portfolio().render(data_fetcher, options_analyzer)
                    except Exception as e:
                        _tab_error("Portfolio", e)
            with sub_riot:
                with st.spinner("Loading RIOT protection strategies…"):
                    try:
                        get_riot().render(data_fetcher, options_analyzer)
                    except Exception as e:
                        _tab_error("RIOT Protection", e)

    # ── 10 · Strategy Lab ─────────────────────────────────────────────────────
    with tab_lab:
        sub_bt, sub_out, sub_vol = st.tabs([
            "🔬 Backtesting",
            "🔮 Market Outlook",
            "🕳️ Volatility Hole",
        ])

        with sub_bt:
            with st.spinner("Loading backtesting engine…"):
                try:
                    get_backtesting().render(selected_stocks, MINING_STOCKS)
                except Exception as e:
                    _tab_error("Backtesting", e)

        with sub_out:
            if not stock_data_available:
                _no_data_error("Market Outlook")
            else:
                with st.spinner("Generating market outlook…"):
                    try:
                        get_weekly_outlook().render(selected_stocks, MINING_STOCKS)
                    except Exception as e:
                        _tab_error("Market Outlook", e)

        with sub_vol:
            if not stock_data_available:
                _no_data_error("Volatility Hole")
            else:
                st.subheader("🕳️ Volatility Hole Indicator")
                st.caption("Danny Cheng's favorite — identifies low-volatility consolidation before major moves.")
                st.info(
                    "🟡 **Yellow lines** = consolidation zone  |  "
                    "🔥 **Breakout markers** = hole releases  |  "
                    "Score **< 25** = hole forming  |  Score **> 75** = breakout"
                )
                vh = get_vol_hole()
                for symbol in selected_stocks:
                    with st.expander(
                        f"📈 {symbol} — {MINING_STOCKS.get(symbol, symbol)}",
                        expanded=(symbol == selected_stocks[0])
                    ):
                        with st.spinner(f"Analyzing {symbol}…"):
                            try:
                                vh.render(symbol, data_fetcher)
                            except Exception as e:
                                _tab_error(f"Volatility Hole ({symbol})", e)

    # ── 11 · Reflexivity ──────────────────────────────────────────────────────
    with tab_reflex:
        with st.spinner("Computing reflexivity metrics…"):
            try:
                get_reflexivity().render(selected_stocks, MINING_STOCKS)
            except Exception as e:
                _tab_error("Reflexivity", e)

    # ── Auto-refresh ──────────────────────────────────────────────────────────
    if auto_refresh:
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = time.time()
        elapsed = time.time() - st.session_state.last_refresh
        if elapsed >= 30:
            st.session_state.last_refresh = time.time()
            st.cache_data.clear()
            st.rerun()
        else:
            st.sidebar.caption(f"↻ Refresh in {30 - elapsed:.0f} s")


if __name__ == "__main__":
    main()
