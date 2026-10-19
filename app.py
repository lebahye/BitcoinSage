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
from components.trade_signals_dashboard import TradeSignalsDashboard
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
from components.riot_correlation_map import RiotCorrelationMap
from components.holding_plan import HoldingPlan

# ─── Page config (must be first Streamlit call) ──────────────────────────────

st.set_page_config(
    page_title="BitcoinSage - Advanced Bitcoin Analytics",
    page_icon="₿",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ─── Mining stocks ───────────────────────────────────────────────────────────

from utils.tickers import MINING_STOCKS, WATCHLIST  # single source of truth (incl. BITF→KEEL rename)

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
def get_trade_signals():
    return TradeSignalsDashboard()

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

@st.cache_resource
def get_riot_corr():
    return RiotCorrelationMap()

@st.cache_resource
def get_holding_plan():
    return HoldingPlan()


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


def _render_command_center(selected_stocks, stock_data, stock_data_available, data_fetcher):
    """Single top strip: Bitcoin, fear gauge, miners today, data freshness, and the
    one-line Hold/Sell call (details live only in the 🧭 My Plan tab)."""
    from utils.explain import HELP
    from utils.market_data import fetch_daily_closes

    st.subheader("🧭 Command Center")
    btc_price = btc_change = vix = None
    try:
        sentiment = data_fetcher.get_market_sentiment()
        btc_price = sentiment.get('btc_price')
        btc_change = sentiment.get('btc_change')
        vix = sentiment.get('vix')
    except Exception:
        pass

    miners_today = None
    last_close_date = None
    try:
        daily = fetch_daily_closes(tuple(selected_stocks), "1mo")
        if not daily.empty and len(daily) > 1:
            chg = daily.pct_change(fill_method=None).iloc[-1].dropna()
            miners_today = float(chg.mean() * 100) if not chg.empty else None
            last_close_date = daily.index[-1].date()
    except Exception:
        pass

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Bitcoin", f"${btc_price:,.0f}" if btc_price is not None else "N/A",
              f"{btc_change:+.2f}% (24h)" if btc_change is not None else None,
              help="Bitcoin's price. Miner stocks are a leveraged bet on it.")
    if vix is not None:
        mood = "fear" if vix >= 30 else "nervous" if vix >= 20 else "calm"
        c2.metric("VIX fear gauge", f"{vix:.1f}", mood, delta_color="off", help=HELP["vix"])
    else:
        c2.metric("VIX fear gauge", "N/A")
    c3.metric("Selected miners today", f"{miners_today:+.2f}%" if miners_today is not None else "N/A",
              help="Average daily % change of the stocks picked in the sidebar (latest daily close vs the one before).")
    source_label = ("Schwab (real-time)" if getattr(data_fetcher, 'using_schwab', False) and stock_data_available
                    else "Yahoo (delayed)" if stock_data_available else "Offline")
    c4.metric("Data", source_label, f"last close {last_close_date}" if last_close_date else None, delta_color="off",
              help="Yahoo Finance prices are delayed ~15 minutes during market hours.")

    try:
        from components.holding_plan import get_advice
        adv, *_ = get_advice("RIOT")
        if adv is not None:
            icon = {"HOLD": "🟢", "TRIM": "🟡", "ROTATE": "🔄", "SELL": "🔴"}[adv.action]
            st.markdown(f"**Your RIOT plan right now: {icon} {adv.action}** ({adv.confidence} confidence, "
                        f"{adv.risk_score}/{adv.max_score} risk points) — full reasoning in the **🧭 My Plan** tab.")
            try:
                from utils.signal_hub import short_term_signal
                from utils.news_sentiment import news_sentiment
                stt, nws = short_term_signal("RIOT"), news_sentiment("RIOT")
                st.caption(f"Short-term context (doesn't override your plan): Trade Signals **{stt.get('signal', 'N/A')}** · "
                           f"news tone **{nws.get('label', 'n/a')}** · same prices and RSI on every tab.")
            except Exception:
                pass
    except Exception:
        pass

    if not stock_data_available:
        st.warning("Price feed degraded. Use healthcheck.py before trusting analytics-heavy tabs.")


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

    _render_command_center(selected_stocks, stock_data, stock_data_available, data_fetcher)

    with st.expander("👋 New here? How to use this dashboard", expanded=False):
        st.markdown("""
1. **⚖️ Stock Verdict** — start here. Pick one stock from the pull-down and get **one** call
   (**Hold / Add / Trim / Sell / Rotate**) built from every tab, with the evidence, where the tabs disagree and what
   would change it. For stocks you own it is exactly My Plan's call.
   **🧭 My Plan** — the full detail behind that call for each holding: reasons, track record, path-to-2030 price range.
2. **🏆 Portfolio** — enter or edit your shares, cost basis and target prices. Everything else uses these numbers.
3. **🔗 RIOT Correlation Map** — what really moves your RIOT shares (other miners, AI stocks, Bitcoin, market fear).
4. **⚠️ Risk Center** and **🔄 Reflexivity** — how bad a Bitcoin crash could hit you, and where we are in the boom/bust cycle.
5. The remaining tabs (Trade Signals, Next-Mover Ranking, Options, Flow, Technicals, Sentiment, Polymarket) are
   **short-term trading tools**. As a long-term holder you can mostly ignore them.

Hover over the small ⓘ next to any number, or open an "ℹ️ What is this?" box, for a plain-English explanation.
Nothing here is financial advice.
""")

    # ── Sections: long-term holder views first, short-term trading tools after ─
    # Only the selected section runs.  (With st.tabs every tab executed on every
    # rerun — hundreds of Yahoo Finance calls per click, which triggers Yahoo's
    # rate limit and made the app slow.)
    SECTIONS = [
        "⚖️ Stock Verdict",
        "🧭 My Plan",
        "🏆 Portfolio",
        "🔗 RIOT Correlation Map",
        "📊 Market Overview",
        "⚠️ Risk Center",
        "🔄 Reflexivity",
        "🔬 Strategy Lab",
        "🧪 Edge Lab",
        "🚦 Trade Signals",
        "🎯 Next-Mover Ranking",
        "⚡ Options Center",
        "🌊 Institutional Flow",
        "📈 Technical Analysis",
        "📰 Sentiment & News",
        "📡 Live Polymarket",
        "📖 Research",
    ]
    view = st.radio("Section", SECTIONS, horizontal=True, key="main_view",
                    label_visibility="collapsed",
                    help="First seven = long-term holder views. The rest are short-term trading tools.")
    st.divider()

    (tab_verdict, tab_plan, tab_portfolio, tab_corr, tab_market, tab_risk, tab_reflex, tab_lab,
     tab_signals, tab_ai, tab_options, tab_flow, tab_ta,
     tab_sentiment, tab_poly, tab_research) = [view == name for name in SECTIONS if name != "🧪 Edge Lab"]

    # ── 🧪 Edge Lab: experimental research tools, each with its own honest backtest (not used by My Plan) ──
    if view == "🧪 Edge Lab":
        try:
            from components.edge_lab import render as render_edge_lab
            render_edge_lab()
        except Exception as e:
            _tab_error("Edge Lab", e)

    # ── Stock Verdict: one call per stock from every tab (= My Plan's call for holdings) ──
    if tab_verdict:
        try:
            from components.stock_verdict import StockVerdict
            StockVerdict().render()
        except Exception as e:
            _tab_error("Stock Verdict", e)

    # ── My Plan: the single source of truth for Hold / Trim / Sell / Rotate ──
    if tab_plan:
        try:
            get_holding_plan().render()
        except Exception as e:
            _tab_error("My Plan", e)

    # ── 1 · Market Overview ───────────────────────────────────────────────────
    if tab_market:
        if not stock_data_available:
            _no_data_error("Market Overview")
        else:
            with st.spinner("Loading market overview…"):
                try:
                    get_stock_dashboard().render(
                        stock_data, selected_stocks, MINING_STOCKS, chart_builder)
                except Exception as e:
                    _tab_error("Market Overview", e)

    # ── RIOT Correlation Map (single home for correlation) ───────────────────
    if tab_corr:
        try:
            get_riot_corr().render(selected_stocks)
        except Exception as e:
            _tab_error("RIOT Correlation Map", e)

    # ── 2 · Trade Signals ─────────────────────────────────────────────────────
    if tab_signals:
        st.caption("⏱️ Short-term trading signals (days to weeks). For your long-term Hold/Sell call see 🧭 My Plan.")
        with st.spinner("Computing BUY/HOLD/SELL signals for all 9 stocks…"):
            try:
                get_trade_signals().render(data_fetcher, options_analyzer)
            except Exception as e:
                _tab_error("Trade Signals", e)

    # ── 3 · Next-Mover Ranking (rules-based; was mislabelled "AI Predictions") ────────────────────────────────────────────────────
    if tab_ai:
        st.caption("⏱️ Short-term trading tool (days to weeks). Your long-term Hold/Sell call lives in 🧭 My Plan.")
        with st.spinner("Ranking the 9 miners…"):
            try:
                get_next_mover().render(data_fetcher, options_analyzer)
            except Exception as e:
                _tab_error("Next-Mover Ranking", e)

    # ── 3 · Options Center ────────────────────────────────────────────────────
    if tab_options:
        st.caption("⏱️ Short-term trading tool (days to weeks). Your long-term Hold/Sell call lives in 🧭 My Plan.")
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
    if tab_flow:
        st.caption("⏱️ Short-term trading tool (days to weeks). Your long-term Hold/Sell call lives in 🧭 My Plan.")
        if not stock_data_available:
            _no_data_error("Institutional Flow")
        else:
            with st.spinner("Analyzing dark pool activity…"):
                try:
                    get_dark_pool().render(selected_stocks, data_fetcher, chart_builder)
                except Exception as e:
                    _tab_error("Institutional Flow", e)

    # ── 5 · Technical Analysis ────────────────────────────────────────────────
    if tab_ta:
        st.caption("⏱️ Short-term trading tool (days to weeks). Your long-term Hold/Sell call lives in 🧭 My Plan.")
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
    if tab_poly:
        st.caption("⏱️ Short-term trading tool (days to weeks). Your long-term Hold/Sell call lives in 🧭 My Plan.")
        with st.spinner("Connecting to Polymarket feed…"):
            try:
                get_polymarket().render()
            except Exception as e:
                _tab_error("Live Polymarket", e)

    # ── 7 · Sentiment & News ──────────────────────────────────────────────────
    if tab_sentiment:
        st.caption("⏱️ Short-term trading tool (days to weeks). Your long-term Hold/Sell call lives in 🧭 My Plan.")
        with st.spinner("Fetching news sentiment…"):
            try:
                get_sentiment().render(selected_stocks, MINING_STOCKS)
            except Exception as e:
                _tab_error("Sentiment & News", e)

    # ── 8 · Risk Center ───────────────────────────────────────────────────────
    if tab_risk:
        if not stock_data_available:
            _no_data_error("Risk Center")
        else:
            with st.spinner("Calculating risk metrics…"):
                try:
                    get_risk_center().render(selected_stocks, MINING_STOCKS)
                except Exception as e:
                    _tab_error("Risk Center", e)

    # ── 9 · Portfolio ─────────────────────────────────────────────────────────
    if tab_portfolio:
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
    if tab_lab:
        sub_bt, sub_out, sub_vol = st.tabs([
            "🔬 Backtesting",
            "🔮 Forecast Center",
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
                _no_data_error("Forecast Center")
            else:
                with st.spinner("Generating market outlook…"):
                    try:
                        get_weekly_outlook().render(selected_stocks, MINING_STOCKS)
                    except Exception as e:
                        _tab_error("Forecast Center", e)

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
    if tab_reflex:
        with st.spinner("Computing reflexivity metrics…"):
            try:
                get_reflexivity().render(selected_stocks, MINING_STOCKS)
            except Exception as e:
                _tab_error("Reflexivity", e)

    # ── 12 · Research ─────────────────────────────────────────────────────────
    if tab_research:
        try:
            import os, pathlib
            html_path = pathlib.Path(__file__).parent / "research.html"
            if html_path.exists():
                html_content = html_path.read_text(encoding="utf-8")
                st.components.v1.html(html_content, height=900, scrolling=True)
            else:
                st.error("research.html not found.")
        except Exception as e:
            _tab_error("Research", e)

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
