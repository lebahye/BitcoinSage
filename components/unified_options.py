"""
components/unified_options.py
Merged from: options_dashboard.py + pro_options_dashboard.py + options_evaluator.py
UnifiedOptions combines options flow analysis, professional IV/Greeks analytics,
and purchase recommendations into a single tabbed component.
"""

from utils.styles import data_lineage_panel

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import yfinance as yf
from utils.unified_data_fetcher import DataFetcher
from utils.options_analytics import OptionsAnalytics


class UnifiedOptions:
    """Unified Options Center — flow analysis, pro analytics, evaluator in one component"""

    def __init__(self):
        self.analytics = OptionsAnalytics()
        self.data_fetcher = DataFetcher()

    def render(self, selected_stocks, options_analyzer, chart_builder, stock_names=None):
        """Render the full unified options dashboard"""
        if stock_names is None:
            stock_names = {s: s for s in selected_stocks}

        st.header("⚡ Options Center")
        data_lineage_panel(["<strong>Direct:</strong> Yahoo Finance options chain + stock price", "<strong>Estimated:</strong> volatility forecast and evaluator scoring", "<strong>Freshness risk:</strong> options premiums may be stale outside market hours", "<strong>Execution note:</strong> displayed premiums are analytical, not guaranteed fills"], title="Options Data Quality")

        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Options Flow",
            "📈 IV & Chain Scanner",
            "🎨 Greeks & Term Structure",
            "🎯 Options Evaluator"
        ])

        with tab1:
            self._render_options_flow_tab(selected_stocks, options_analyzer, chart_builder)

        with tab2:
            self._render_iv_chain_tab(selected_stocks, stock_names)

        with tab3:
            self._render_greeks_term_tab(selected_stocks, stock_names)

        with tab4:
            self._render_evaluator_tab(selected_stocks, options_analyzer, chart_builder)

    # -----------------------------------------------------------------------
    # Tab 1 — Options Flow (from OptionsDashboard)
    # -----------------------------------------------------------------------

    def _render_options_flow_tab(self, selected_stocks, options_analyzer, chart_builder):
        st.subheader("⚡ Options Flow Analysis")
        st.write("Put-call ratios and unusual options activity to identify potential volatility.")

        for symbol in selected_stocks:
            with st.expander(f"{symbol} Options Analysis", expanded=True):
                self._render_single_stock_options(symbol, options_analyzer, chart_builder)

        st.subheader("📊 Sector Options Summary")
        self._render_sector_summary(selected_stocks, options_analyzer)

    def _render_single_stock_options(self, symbol, options_analyzer, chart_builder):
        try:
            calls_df, puts_df = self.data_fetcher.get_options_data(symbol)
            if calls_df is None and puts_df is None:
                st.warning(f"No options data available for {symbol}")
                return
            stock_info = self.data_fetcher.get_stock_info(symbol)
            current_price = stock_info.get('current_price', 0)
            pc_analysis = options_analyzer.analyze_put_call_ratio(calls_df, puts_df)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Put-Call Ratio", f"{pc_analysis['put_call_ratio']:.2f}")
            with col2:
                st.metric("Call Volume", f"{pc_analysis['call_volume']:,}")
            with col3:
                st.metric("Put Volume", f"{pc_analysis['put_volume']:,}")
            with col4:
                signal = pc_analysis['volatility_signal']
                if "Bearish" in signal: st.error(signal)
                elif "Bullish" in signal: st.success(signal)
                else: st.info(signal)

            col1, col2 = st.columns(2)
            with col1:
                pc_chart = chart_builder.create_put_call_ratio_chart(symbol, pc_analysis)
                if pc_chart:
                    st.plotly_chart(pc_chart, use_container_width=True)
            with col2:
                flow_metrics = options_analyzer.calculate_options_flow_metrics(
                    calls_df, puts_df, current_price)
                st.subheader("Smart Money Flow")
                smi = flow_metrics.get('smart_money_indicator', 'No Data')
                if "Bullish" in smi: st.success(f"📈 {smi}")
                elif "Bearish" in smi: st.error(f"📉 {smi}")
                else: st.info(f"➡️ {smi}")
                if 'avg_call_iv' in flow_metrics:
                    st.metric("Avg Call IV", f"{flow_metrics['avg_call_iv']:.1%}")
                if 'avg_put_iv' in flow_metrics:
                    st.metric("Avg Put IV", f"{flow_metrics['avg_put_iv']:.1%}")

            st.subheader("🚨 Unusual Options Activity")
            unusual = options_analyzer.analyze_unusual_options_activity(calls_df, puts_df)
            if unusual:
                df = pd.DataFrame(unusual)
                df['Volume'] = df['volume'].apply(lambda x: f"{x:,}")
                df['Open Interest'] = df['open_interest'].apply(lambda x: f"{x:,}")
                df['Strike'] = df['strike'].apply(lambda x: f"${x:.2f}")
                df['Last Price'] = df['last_price'].apply(lambda x: f"${x:.2f}")
                df['IV'] = df['implied_volatility'].apply(lambda x: f"{x:.1%}")
                st.dataframe(df[['type', 'Strike', 'Volume', 'Open Interest', 'Last Price', 'IV']]
                             .rename(columns={'type': 'Type'}),
                             use_container_width=True, hide_index=True)
            else:
                st.info("No unusual options activity detected")

            st.subheader("🔮 Volatility Forecast")
            forecast = options_analyzer.get_volatility_forecast(pc_analysis['put_call_ratio'])
            col1, col2 = st.columns(2)
            with col1:
                outlook = forecast['volatility_outlook']
                if "High" in outlook: st.error(f"⚠️ {outlook}")
                elif "Low" in outlook: st.success(f"✅ {outlook}")
                else: st.info(f"➡️ {outlook}")
            with col2:
                st.metric("Confidence", forecast['confidence'])
            if forecast['key_factors']:
                for f in forecast['key_factors']:
                    st.write(f"• {f}")
        except Exception as e:
            st.error(f"Error analyzing options for {symbol}: {str(e)}")

    def _render_sector_summary(self, selected_stocks, options_analyzer):
        try:
            summary_data = []
            for symbol in selected_stocks:
                try:
                    calls_df, puts_df = self.data_fetcher.get_options_data(symbol)
                    if calls_df is not None or puts_df is not None:
                        pc = options_analyzer.analyze_put_call_ratio(calls_df, puts_df)
                        summary_data.append({'Symbol': symbol,
                                             'P/C Ratio': pc['put_call_ratio'],
                                             'Call Volume': pc['call_volume'],
                                             'Put Volume': pc['put_volume'],
                                             'Total Volume': pc['total_volume'],
                                             'Signal': pc['volatility_signal']})
                except Exception:
                    continue
            if not summary_data:
                st.warning("No options data available for sector analysis")
                return
            num_df = pd.DataFrame(summary_data)
            display = num_df.copy()
            display['P/C Ratio'] = display['P/C Ratio'].apply(lambda x: f"{x:.2f}")
            for col in ['Call Volume', 'Put Volume', 'Total Volume']:
                display[col] = display[col].apply(lambda x: f"{x:,}")
            st.dataframe(display.rename(columns={'Signal': 'Volatility Signal'}),
                         use_container_width=True, hide_index=True)
            avg_pc = num_df['P/C Ratio'].mean()
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Avg P/C Ratio", f"{avg_pc:.2f}")
            with col2: st.metric("Total Volume", f"{num_df['Total Volume'].sum():,}")
            with col3:
                if avg_pc > 1.2: st.error("Bearish Sector")
                elif avg_pc > 0.8: st.warning("Neutral Sector")
                else: st.success("Bullish Sector")
        except Exception as e:
            st.error(f"Error in sector options summary: {str(e)}")

    # -----------------------------------------------------------------------
    # Tab 2 — IV Percentile + Chain Scanner (from ProOptionsDashboard)
    # -----------------------------------------------------------------------

    def _render_iv_chain_tab(self, selected_stocks, stock_names):
        sub1, sub2 = st.tabs(["📈 IV Percentile/Rank", "🔍 Chain Scanner"])

        with sub1:
            st.subheader("📈 IV Percentile & Rank")
            st.write("**> 75% = Options EXPENSIVE (sell) | < 25% = Options CHEAP (buy)**")
            for symbol in selected_stocks[:3]:
                with st.expander(f"📊 {symbol} IV Analysis", expanded=True):
                    iv_data = self.analytics.calculate_iv_percentile(symbol, 0, period_days=252)
                    if not iv_data or 'error' in iv_data:
                        st.warning(f"Unable to calculate IV for {symbol}")
                        continue
                    col1, col2, col3, col4 = st.columns(4)
                    iv_pct = iv_data['iv_percentile']
                    with col1:
                        st.metric("IV Percentile", f"{iv_pct:.1f}%",
                                  delta="🔴" if iv_pct > 75 else "🟢" if iv_pct < 25 else "🟡")
                    with col2: st.metric("IV Rank", f"{iv_data['iv_rank']:.1f}%")
                    with col3: st.metric("Current IV", f"{iv_data['current_iv']*100:.1f}%")
                    with col4: st.metric("Median IV 1Y", f"{iv_data['median_iv']*100:.1f}%")
                    st.info(f"**Signal:** {iv_data['signal']}")
                    if iv_data.get('iv_history'):
                        ivs = [x['iv'] * 100 for x in iv_data['iv_history']]
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=[x['date'] for x in iv_data['iv_history']], y=ivs,
                            name='IV History', line=dict(color='cyan', width=2),
                            fill='tozeroy', fillcolor='rgba(0,255,255,0.1)'))
                        fig.add_hline(y=iv_data['current_iv']*100, line_color="white",
                                      annotation_text="Current")
                        fig.add_hline(y=iv_data['median_iv']*100, line_dash="dash", line_color="yellow",
                                      annotation_text="Median")
                        p25, p75 = np.percentile(ivs, 25), np.percentile(ivs, 75)
                        fig.add_hrect(y0=p75, y1=max(ivs), fillcolor="red", opacity=0.1,
                                      annotation_text="Expensive")
                        fig.add_hrect(y0=0, y1=p25, fillcolor="green", opacity=0.1,
                                      annotation_text="Cheap")
                        fig.update_layout(title=f'{symbol} IV History',
                                          template='plotly_dark', height=400)
                        st.plotly_chart(fig, use_container_width=True)

        with sub2:
            st.subheader("🔍 Options Chain Scanner")
            strategy = st.selectbox("Select Strategy",
                ['covered_calls', 'protective_puts', 'long_calls'],
                format_func=lambda x: {'covered_calls': '💰 Covered Calls',
                                        'protective_puts': '🛡️ Protective Puts',
                                        'long_calls': '🚀 Long Calls'}[x])
            for symbol in selected_stocks[:2]:
                with st.expander(f"🎯 {symbol} — {stock_names.get(symbol, symbol)}", expanded=True):
                    scan = self.analytics.scan_options_chain(symbol, strategy=strategy)
                    if not scan or not scan.get('recommendations'):
                        st.warning(f"No recommendations for {symbol}")
                        continue
                    st.metric("Current Price", f"${scan['current_price']:.2f}")
                    st.metric("Opportunities", scan['total_opportunities'])
                    recs_df = pd.DataFrame(scan['recommendations'])
                    if strategy == 'covered_calls':
                        cols = ['expiration', 'days_to_exp', 'strike', 'premium', 'annual_return', 'delta']
                        df = recs_df[cols].head(10).copy()
                        df['strike'] = df['strike'].apply(lambda x: f"${x:.2f}")
                        df['premium'] = df['premium'].apply(lambda x: f"${x:.2f}")
                        df['annual_return'] = df['annual_return'].apply(lambda x: f"{x:.1f}%")
                        df['delta'] = df['delta'].apply(lambda x: f"{x:.2f}")
                        df.columns = ['Expiration', 'Days', 'Strike', 'Premium', 'Annual Return', 'Delta']
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    elif strategy == 'protective_puts':
                        cols = ['expiration', 'days_to_exp', 'strike', 'premium', 'cost_pct', 'protection_pct']
                        df = recs_df[cols].head(10).copy()
                        df['strike'] = df['strike'].apply(lambda x: f"${x:.2f}")
                        df['premium'] = df['premium'].apply(lambda x: f"${x:.2f}")
                        df['cost_pct'] = df['cost_pct'].apply(lambda x: f"{x:.2f}%")
                        df['protection_pct'] = df['protection_pct'].apply(lambda x: f"{x:.2f}%")
                        df.columns = ['Expiration', 'Days', 'Strike', 'Premium', 'Cost %', 'Protection %']
                        st.dataframe(df, use_container_width=True, hide_index=True)
                    elif strategy == 'long_calls':
                        cols = ['expiration', 'days_to_exp', 'strike', 'premium', 'breakeven', 'delta', 'leverage', 'moneyness']
                        df = recs_df[cols].head(10).copy()
                        df['strike'] = df['strike'].apply(lambda x: f"${x:.2f}")
                        df['premium'] = df['premium'].apply(lambda x: f"${x:.2f}")
                        df['breakeven'] = df['breakeven'].apply(lambda x: f"${x:.2f}")
                        df['delta'] = df['delta'].apply(lambda x: f"{x:.2f}")
                        df['leverage'] = df['leverage'].apply(lambda x: f"{x:.1f}x")
                        df.columns = ['Expiration', 'Days', 'Strike', 'Premium', 'Breakeven', 'Delta', 'Leverage', 'Moneyness']
                        st.dataframe(df, use_container_width=True, hide_index=True)

    # -----------------------------------------------------------------------
    # Tab 3 — Greeks Surface + IV Term Structure (from ProOptionsDashboard)
    # -----------------------------------------------------------------------

    def _render_greeks_term_tab(self, selected_stocks, stock_names):
        sub1, sub2 = st.tabs(["🎨 Greeks Surface", "📊 IV Term Structure"])

        with sub1:
            st.subheader("🎨 Greeks Surface")
            for symbol in selected_stocks[:2]:
                with st.expander(f"📊 {symbol} Greeks", expanded=True):
                    gs = self.analytics.calculate_greeks_surface(symbol)
                    if not gs or gs.get('greeks_data') is None or gs['greeks_data'].empty:
                        st.warning(f"Unable to calculate Greeks for {symbol}")
                        continue
                    st.metric("Current Price", f"${gs['current_price']:.2f}")
                    greek_type = st.selectbox(f"Greek ({symbol})",
                        ['delta', 'gamma', 'theta', 'vega'],
                        key=f"greek_{symbol}", format_func=str.upper)
                    df = gs['greeks_data']
                    call_data = df[df['type'] == 'call']
                    fig = go.Figure()
                    for exp in call_data['expiration'].unique()[:4]:
                        ed = call_data[call_data['expiration'] == exp]
                        days = ed['days_to_exp'].iloc[0] if not ed.empty else 0
                        fig.add_trace(go.Scatter(x=ed['strike'], y=ed[greek_type],
                                                 name=f"{exp} ({days}d)", mode='lines+markers'))
                    fig.add_vline(x=gs['current_price'], line_dash="dash", line_color="white")
                    fig.update_layout(title=f'{symbol} {greek_type.upper()} Surface',
                                      template='plotly_dark', height=500, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)

        with sub2:
            st.subheader("📊 IV Term Structure")
            for symbol in selected_stocks[:3]:
                with st.expander(f"📈 {symbol} IV Term Structure", expanded=True):
                    ts = self.analytics.calculate_iv_term_structure(symbol)
                    if not ts or not ts.get('term_structure'):
                        st.warning(f"Unable to calculate term structure for {symbol}")
                        continue
                    col1, col2, col3 = st.columns(3)
                    with col1: st.metric("Near-Term IV", f"{ts['near_term_iv']:.1f}%")
                    with col2: st.metric("Far-Term IV", f"{ts['far_term_iv']:.1f}%")
                    with col3: st.metric("Term Spread", f"{ts['term_spread']:.1f}%")
                    st.info(f"**Shape:** {ts['shape']}")
                    tsd = ts['term_structure']
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=[x['days_to_exp'] for x in tsd],
                        y=[x['iv'] * 100 for x in tsd],
                        name='ATM IV', line=dict(color='cyan', width=3), mode='lines+markers'))
                    fig.add_trace(go.Scatter(
                        x=[x['days_to_exp'] for x in tsd],
                        y=[x['call_iv'] * 100 for x in tsd],
                        name='Call IV', line=dict(color='green', width=2, dash='dot'), opacity=0.6))
                    fig.add_trace(go.Scatter(
                        x=[x['days_to_exp'] for x in tsd],
                        y=[x['put_iv'] * 100 for x in tsd],
                        name='Put IV', line=dict(color='red', width=2, dash='dot'), opacity=0.6))
                    fig.update_layout(title=f'{symbol} IV Term Structure',
                                      xaxis_title='Days to Expiration', yaxis_title='IV (%)',
                                      template='plotly_dark', height=400, hovermode='x unified')
                    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Tab 4 — Options Evaluator (from OptionsEvaluator)
    # -----------------------------------------------------------------------

    def _render_evaluator_tab(self, selected_stocks, options_analyzer, chart_builder):
        st.subheader("🎯 Options Purchase Recommendations")
        st.write("Identify the best options to buy based on profit potential, risk, and market conditions.")

        self._render_recommendations_summary(selected_stocks)

        for symbol in selected_stocks:
            with st.expander(f"{symbol} - Detailed Options Evaluation", expanded=False):
                self._render_stock_options_evaluation(symbol, options_analyzer, chart_builder)

    def _render_recommendations_summary(self, selected_stocks):
        st.subheader("🏆 Top Options Recommendations")
        all_recs = []
        for symbol in selected_stocks:
            try:
                recs = self._analyze_stock_options(symbol)
                for r in recs[:2]:
                    r['symbol'] = symbol
                    all_recs.append(r)
            except Exception as e:
                st.warning(f"Could not analyze {symbol}: {str(e)}")
        if not all_recs:
            st.info("No recommendations available — check data connection")
            return
        sorted_recs = sorted(all_recs, key=lambda x: x.get('score', 0), reverse=True)
        col1, col2 = st.columns(2)
        with col1:
            st.write("**🥇 Best Call Options**")
            for i, r in enumerate([x for x in sorted_recs if x.get('type') == 'Call'][:3], 1):
                st.write(f"{i}. **{r['symbol']}** — Strike: ${r.get('strike', 0):.0f} "
                         f"| Exp: {r.get('expiry', 'N/A')} | Score: {r.get('score', 0):.1f}")
        with col2:
            st.write("**🥇 Best Put Options**")
            for i, r in enumerate([x for x in sorted_recs if x.get('type') == 'Put'][:3], 1):
                st.write(f"{i}. **{r['symbol']}** — Strike: ${r.get('strike', 0):.0f} "
                         f"| Exp: {r.get('expiry', 'N/A')} | Score: {r.get('score', 0):.1f}")

    def _render_stock_options_evaluation(self, symbol, options_analyzer, chart_builder):
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get('currentPrice', 0)
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]

            st.write(f"**Current Price:** ${current_price:.2f}")

            calls_df, puts_df = self.data_fetcher.get_options_data(symbol)
            if calls_df is None:
                st.warning("No options data available")
                return

            pc = options_analyzer.analyze_put_call_ratio(calls_df, puts_df)
            flow = options_analyzer.calculate_options_flow_metrics(calls_df, puts_df, current_price)
            forecast = options_analyzer.get_volatility_forecast(pc['put_call_ratio'])

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Put-Call Ratio", f"{pc['put_call_ratio']:.2f}")
                st.metric("Volatility Signal", pc['volatility_signal'][:20])
            with col2:
                st.metric("Smart Money", flow.get('smart_money_indicator', 'N/A')[:20])
                st.metric("Volatility Outlook", forecast['volatility_outlook'][:25])
            with col3:
                st.metric("Total Options Volume", f"{pc.get('total_volume', 0):,}")
                st.metric("Total OI", f"{pc.get('total_oi', 0):,}")

            recs = self._analyze_stock_options(symbol)
            if recs:
                st.write("**Top Picks:**")
                for r in recs[:3]:
                    st.write(f"• {r.get('type')} ${r.get('strike', 0):.0f} exp {r.get('expiry', 'N/A')} "
                             f"— Score: {r.get('score', 0):.1f} — {r.get('reason', '')}")
        except Exception as e:
            st.error(f"Evaluation error for {symbol}: {str(e)}")

    def _analyze_stock_options(self, symbol):
        """Generate scored options recommendations"""
        recs = []
        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get('currentPrice', 0)
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            if current_price <= 0:
                return recs
            expirations = ticker.options
            if not expirations:
                return recs
            for exp in expirations[:2]:
                chain = ticker.option_chain(exp)
                days_to_exp = (pd.to_datetime(exp) - datetime.now()).days
                if days_to_exp <= 0:
                    continue
                # Score calls
                atm_calls = chain.calls[
                    (chain.calls['strike'] >= current_price * 0.95) &
                    (chain.calls['strike'] <= current_price * 1.10)
                ]
                for _, opt in atm_calls.head(3).iterrows():
                    iv = opt.get('impliedVolatility', 0)
                    vol = opt.get('volume', 0) or 0
                    oi = opt.get('openInterest', 0) or 0
                    score = (vol / (oi + 1)) * 10 + (1 - abs(opt['strike'] - current_price) / current_price) * 5
                    recs.append({'type': 'Call', 'symbol': symbol, 'strike': opt['strike'],
                                 'expiry': exp, 'iv': iv, 'score': score,
                                 'reason': f"IV {iv*100:.0f}%, {days_to_exp}d to exp"})
                # Score puts
                atm_puts = chain.puts[
                    (chain.puts['strike'] >= current_price * 0.90) &
                    (chain.puts['strike'] <= current_price * 1.05)
                ]
                for _, opt in atm_puts.head(3).iterrows():
                    iv = opt.get('impliedVolatility', 0)
                    vol = opt.get('volume', 0) or 0
                    oi = opt.get('openInterest', 0) or 0
                    score = (vol / (oi + 1)) * 10 + (1 - abs(opt['strike'] - current_price) / current_price) * 5
                    recs.append({'type': 'Put', 'symbol': symbol, 'strike': opt['strike'],
                                 'expiry': exp, 'iv': iv, 'score': score,
                                 'reason': f"IV {iv*100:.0f}%, {days_to_exp}d to exp"})
        except Exception:
            pass
        return sorted(recs, key=lambda x: x.get('score', 0), reverse=True)
