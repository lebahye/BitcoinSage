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
    """Top-level command center: source, freshness, BTC pulse, sector pulse."""
    st.subheader("🧭 Command Center")

    source_label = (
        "Schwab (real-time)" if getattr(data_fetcher, 'using_schwab', False) and stock_data_available
        else "Yahoo Finance (delayed)" if stock_data_available
        else "Offline / rate-limited"
    )

    last_update = "N/A"
    sector_change = None
    if stock_data_available and not stock_data.empty:
        try:
            last_idx = stock_data.index[-1]
            last_update = str(last_idx)[:19]
            if len(stock_data) > 1:
                latest = stock_data.iloc[-1].mean()
                prev = stock_data.iloc[-2].mean()
                sector_change = ((latest - prev) / prev) * 100 if prev else 0
        except Exception:
            pass

    btc_price = None
    btc_change = None
    vix = None
    try:
        sentiment = data_fetcher.get_market_sentiment()
        btc_price = sentiment.get('btc_price')
        btc_change = sentiment.get('btc_change')
        vix = sentiment.get('vix')
    except Exception:
        pass

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Data Source", source_label)
    with c2:
        st.metric("Selected Miners", len(selected_stocks))
    with c3:
        st.metric("Last Price Update", last_update)
    with c4:
        if btc_price is not None:
            st.metric("BTC", f"${btc_price:,.0f}", f"{btc_change:+.2f}%")
        else:
            st.metric("BTC", "N/A")
    with c5:
        if sector_change is not None:
            st.metric("Sector Pulse", f"{sector_change:+.2f}%")
        elif vix is not None:
            st.metric("VIX", f"{vix:.2f}")
        else:
            st.metric("Sector Pulse", "N/A")

    if not stock_data_available:
        st.warning("Price feed degraded. Use healthcheck.py before trusting analytics-heavy tabs.")
    else:
        st.caption("Use this strip as your quick read before diving into tabs.")


def _render_decision_summary(selected_stocks, stock_data, stock_data_available, data_fetcher, options_analyzer):
    """Consensus layer: regime, best long, biggest risk, best options setup, action bias."""
    st.subheader("🧠 Decision Summary")

    if not stock_data_available or stock_data.empty:
        st.info("Decision Summary is limited because core price data is unavailable.")
        return

    # 1) Regime
    btc_change = None
    try:
        sentiment = data_fetcher.get_market_sentiment()
        btc_change = sentiment.get('btc_change')
    except Exception:
        pass

    sector_change = 0.0
    try:
        if len(stock_data) > 1:
            latest = stock_data.iloc[-1].mean()
            prev = stock_data.iloc[-2].mean()
            sector_change = ((latest - prev) / prev) * 100 if prev else 0
    except Exception:
        pass

    if btc_change is None:
        regime = "Mixed / Unknown"
    elif btc_change > 2 and sector_change > 2:
        regime = "Bullish Expansion"
    elif btc_change < -2 and sector_change < -2:
        regime = "Bearish Contraction"
    elif btc_change > 0 and sector_change < 0:
        regime = "Divergence"
    else:
        regime = "Neutral / Mixed"

    # 2) Canonical best idea from Forecast Center
    best_long = "N/A"
    best_long_reason = ""
    best_long_action = ""
    try:
        from components.weekly_outlook import WeeklyOutlook
        fc = WeeklyOutlook()
        forecasts = fc.get_forecast_data(selected_stocks, MINING_STOCKS, 'Weekly')
        if forecasts:
            forecasts = sorted(forecasts, key=lambda x: x.get('score', 0), reverse=True)
            row = forecasts[0]
            best_long = row.get('symbol', 'N/A')
            best_long_action = row.get('action_label', '')
            best_long_reason = (
                f"{row.get('direction', 'N/A')} · {row.get('confidence', 0)}% confidence · "
                f"target ${row.get('price_target', 0):.2f} · "
                f"range ${row.get('range_low', 0):.2f}-${row.get('range_high', 0):.2f}"
            )
    except Exception:
        pass
    # 3) Biggest risk candidate from risk scores
    biggest_risk = "N/A"
    biggest_risk_reason = ""
    try:
        from components.risk_center import RiskCenter
        rc = RiskCenter()
        rdata = rc.get_risk_data(selected_stocks)
        ranked = []
        for sym in selected_stocks:
            if sym in rdata:
                ranked.append((sym, rdata[sym].get('risk_score', 0), rdata[sym].get('volatility', 0)))
        if ranked:
            ranked.sort(key=lambda x: x[1], reverse=True)
            sym, score, vol = ranked[0]
            biggest_risk = sym
            biggest_risk_reason = f"risk score {score:.1f}, volatility {vol:.1f}%"
    except Exception:
        pass

    # 4) Best options setup by total options volume
    best_options = "N/A"
    best_options_reason = ""
    try:
        best_vol = -1
        for sym in selected_stocks:
            calls, puts = data_fetcher.get_options_data(sym)
            if calls is None or puts is None:
                continue
            pc = options_analyzer.analyze_put_call_ratio(calls, puts)
            total_vol = pc.get('total_volume', 0)
            if total_vol > best_vol:
                best_vol = total_vol
                best_options = sym
                best_options_reason = f"total options volume {int(total_vol):,}, P/C {pc.get('put_call_ratio', 0):.2f}"
    except Exception:
        pass

    # 5) Suggested action
    if best_long_action in ["Accumulate", "Accumulate / Hold", "Hold / Selective Buy"] and best_long != "N/A":
        action = f"Forecast Center favors {best_long} ({best_long_action}). Use options selectively if liquidity is good."
    elif regime == "Bearish Contraction":
        action = f"Prioritize protection; watch {biggest_risk} closely and avoid forcing entries."
    elif regime == "Divergence":
        action = f"Stay selective. Prefer leaders with confirmation and avoid crowded laggard bets."
    else:
        action = "Reduce conviction. Let Risk / Reflexivity / Options confirm before acting."

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Regime", regime)
    c2.metric("Best Forecast", best_long)
    c3.metric("Biggest Risk", biggest_risk)
    c4.metric("Best Options Setup", best_options)
    c5.metric("Action Bias", "Actionable" if "Lean" in action or "Prioritize" in action else "Wait / Selective")

    st.markdown(
        f"**Best Forecast — {best_long}:** {(best_long_reason or 'Insufficient signal detail')} {('· ' + best_long_action) if best_long_action else ''}  \n"
        f"**Biggest Risk — {biggest_risk}:** {biggest_risk_reason or 'Insufficient risk detail'}  \n"
        f"**Best Options Setup — {best_options}:** {best_options_reason or 'Insufficient options data'}  \n"
        f"**Suggested Action:** {action}"
    )


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

    # ── 12 Tabs ───────────────────────────────────────────────────────────────
    tabs = st.tabs([
        "📊 Market Overview",
        "🔗 RIOT Correlation Map",
        "🚦 Trade Signals",
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
        "📖 Research",
    ])

    (tab_market, tab_corr, tab_signals, tab_ai, tab_options, tab_flow, tab_ta,
     tab_poly, tab_sentiment, tab_risk, tab_portfolio, tab_lab,
     tab_reflex, tab_research) = tabs

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

    # ── RIOT Correlation Map (single home for correlation) ───────────────────
    with tab_corr:
        try:
            get_riot_corr().render(selected_stocks)
        except Exception as e:
            _tab_error("RIOT Correlation Map", e)

    # ── 2 · Trade Signals ─────────────────────────────────────────────────────
    with tab_signals:
        with st.spinner("Computing BUY/HOLD/SELL signals for all 9 stocks…"):
            try:
                get_trade_signals().render(data_fetcher, options_analyzer)
            except Exception as e:
                _tab_error("Trade Signals", e)

    # ── 3 · AI Predictions ────────────────────────────────────────────────────
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
                get_sentiment().render(selected_stocks, MINING_STOCKS)
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
    with tab_reflex:
        with st.spinner("Computing reflexivity metrics…"):
            try:
                get_reflexivity().render(selected_stocks, MINING_STOCKS)
            except Exception as e:
                _tab_error("Reflexivity", e)

    # ── 12 · Research ─────────────────────────────────────────────────────────
    with tab_research:
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
