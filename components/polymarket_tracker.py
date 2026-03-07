import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
from utils.polymarket_fetcher import PolymarketFetcher
from utils.polymarket_live_feed import PolymarketLiveFeed


class PolymarketTracker:
    """Bitcoin Mining Prediction Markets Tracker using Polymarket data + Live Arb Feed"""
    
    def __init__(self):
        self.polymarket = PolymarketFetcher()
        self.live_feed = PolymarketLiveFeed()
    
    def render(self):
        """Render Bitcoin mining prediction markets interface"""
        st.title("📡 Bitcoin Mining Prediction Markets")
        
        # Main market tabs — live feed first
        market_tab0, market_tab1, market_tab2, market_tab3 = st.tabs([
            "🔴 Live Arb Signals",
            "🔥 Active Markets", 
            "📊 Market Analysis", 
            "🎯 Mining Stocks Bets"
        ])
        
        with market_tab0:
            self._render_live_arb_feed()
        
        # Market overview metrics (REST)
        self._render_market_overview()
        
        # Main market tabs
        market_tab1, market_tab2, market_tab3 = st.tabs([
            "🔥 Active Markets", 
            "📊 Market Analysis", 
            "🎯 Mining Stocks Bets"
        ])
        
        with market_tab1:
            self._render_active_markets()
        
        with market_tab2:
            self._render_market_analysis()
        
        with market_tab3:
            self._render_mining_stocks_bets()
    
    def _render_live_arb_feed(self):
        """Render live arbitrage signals from the arb scanner system."""
        st.markdown("### 🔴 Live Polymarket Arbitrage Scanner")
        st.caption("Real-time edge signals from WebSocket orderbook monitoring (BTC + ETH markets)")

        summary = self.live_feed.get_summary()

        if not summary["connected"]:
            st.warning(f"⚠️ {summary['message']}")
            st.info("The arb scanner system (scanner-btc-15min, scanner-eth-15min) must be running for live data.")
            return

        # Scanner health row
        col1, col2, col3, col4 = st.columns(4)
        scanners = summary.get("scanners", {})
        btc_health = scanners.get("btc-15min", {})
        eth_health = scanners.get("eth-15min", {})

        btc_icon = "🟢" if btc_health.get("status") == "live" else "🔴"
        eth_icon = "🟢" if eth_health.get("status") == "live" else "🔴"

        with col1:
            st.metric("BTC Scanner", f"{btc_icon} {btc_health.get('status', 'unknown').upper()}")
        with col2:
            st.metric("ETH Scanner", f"{eth_icon} {eth_health.get('status', 'unknown').upper()}")
        with col3:
            st.metric("Recent Signals", summary.get("recent_edges", 0))
        with col4:
            best = summary.get("best_edge_pct")
            st.metric("Best Edge", f"{best:.2f}%" if best else "—")

        st.divider()

        # Live edge signals
        edges = self.live_feed.get_latest_edges(count=25)
        all_edges = []
        for scanner_name, edge_list in edges.items():
            for e in edge_list:
                e["_scanner"] = scanner_name
                all_edges.append(e)

        if not all_edges:
            st.info("No edge signals detected recently. Scanners are monitoring for YES + NO < $0.995 opportunities.")
            return

        # Sort by edge_pct descending
        all_edges.sort(key=lambda x: float(x.get("edge_pct", 0)), reverse=True)

        # Build display table
        rows = []
        for e in all_edges[:20]:
            ts_ms = e.get("timestamp_ms")
            ts_str = datetime.fromtimestamp(ts_ms / 1000).strftime("%H:%M:%S") if ts_ms else "—"
            rows.append({
                "Scanner": e.get("_scanner", "—"),
                "Market ID": (e.get("market_id") or "—")[:16] + "...",
                "YES Ask": f"${float(e.get('yes_ask', 0)):.4f}",
                "NO Ask": f"${float(e.get('no_ask', 0)):.4f}",
                "Combined": f"${float(e.get('combined_cost', 0)):.4f}",
                "Edge %": f"{float(e.get('edge_pct', 0)):.3f}%",
                "Time": ts_str,
            })

        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption(f"Last refreshed: {datetime.now().strftime('%H:%M:%S')} · Auto-refreshes on page interaction")

    def _render_market_overview(self):
        """Render market overview statistics"""
        st.markdown("### 📈 Bitcoin Mining Markets Overview")
        
        with st.spinner("Loading Polymarket data..."):
            markets = self.polymarket.get_bitcoin_mining_markets()
        
        if not markets:
            st.warning("No Bitcoin mining markets found. Markets may be closed or temporarily unavailable.")
            return
        
        # Calculate overview metrics
        total_volume = sum(float(m.get('volume', 0)) for m in markets)
        active_markets = sum(1 for m in markets if m.get('active', False))
        avg_probability = np.mean([
            float(m.get('tokens', [{}])[0].get('price', 0.5)) * 100 
            for m in markets if m.get('tokens')
        ])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Active Markets", active_markets)
        
        with col2:
            st.metric("Total Volume", f"${total_volume:,.0f}")
        
        with col3:
            st.metric("Avg. Probability", f"{avg_probability:.1f}%")
        
        with col4:
            st.metric("Last Updated", datetime.now().strftime("%H:%M:%S"))
    
    def _render_active_markets(self):
        """Render active Bitcoin mining prediction markets"""
        st.subheader("🔥 Active Bitcoin Mining Markets")
        
        markets = self.polymarket.get_bitcoin_mining_markets()
        
        if not markets:
            st.info("No active Bitcoin mining markets found at the moment.")
            return
        
        # Display top markets
        for i, market in enumerate(markets[:10]):
            metrics = self.polymarket.calculate_market_metrics(market)
            
            with st.expander(f"📊 {metrics['question'][:80]}...", expanded=i < 3):
                self._render_market_card(market, metrics)
    
    def _render_market_card(self, market, metrics):
        """Render individual market card"""
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col1:
            st.markdown(f"**Question:** {metrics['question']}")
            st.markdown(f"**Description:** {metrics['description'][:200]}...")
            
            # Market status indicators
            status_text = "🟢 Active" if metrics.get('active') else "🔴 Inactive"
            if metrics.get('resolved'):
                status_text = "✅ Resolved"
            st.markdown(f"**Status:** {status_text}")
        
        with col2:
            # Probability display
            prob = metrics.get('implied_probability', 0)
            st.metric("Probability", f"{prob:.1f}%")
            
            # Volume metrics
            volume = metrics.get('volume', 0)
            if volume > 0:
                st.metric("Volume", f"${volume:,.0f}")
            else:
                st.metric("Volume", "Low")
        
        with col3:
            # Yes/No prices
            yes_price = metrics.get('yes_price', 0)
            no_price = metrics.get('no_price', 0)
            
            st.metric("YES Price", f"${yes_price:.3f}")
            st.metric("NO Price", f"${no_price:.3f}")
            
            # Days remaining
            days_left = metrics.get('days_remaining')
            if days_left is not None and days_left > 0:
                st.metric("Days Left", f"{days_left}")
            else:
                st.metric("End Date", metrics.get('end_date', 'TBD'))
        
        # Probability visualization
        if prob > 0:
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = prob,
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Market Probability"},
                gauge = {
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 25], 'color': "lightgray"},
                        {'range': [25, 50], 'color': "gray"},
                        {'range': [50, 75], 'color': "lightgreen"},
                        {'range': [75, 100], 'color': "green"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        
        # Trading insights
        st.markdown("### 💡 Trading Insights")
        
        if prob > 75:
            st.success("🟢 **Strong Consensus** - Market heavily favors YES outcome")
        elif prob > 60:
            st.info("🔵 **Moderate Confidence** - Market leans toward YES")
        elif prob > 40:
            st.warning("🟡 **Uncertain** - Market is divided, high volatility expected")
        else:
            st.error("🔴 **Low Probability** - Market heavily favors NO outcome")
        
        # Liquidity assessment
        liquidity = metrics.get('liquidity_tier', 'Unknown')
        if liquidity == 'High':
            st.success(f"💰 **{liquidity} Liquidity** - Easy to trade large positions")
        elif liquidity == 'Medium':
            st.info(f"💰 **{liquidity} Liquidity** - Moderate trading activity")
        else:
            st.warning(f"💰 **{liquidity} Liquidity** - Limited trading activity")
    
    def _render_market_analysis(self):
        """Render market analysis and trends"""
        st.subheader("📊 Market Analysis & Trends")
        
        markets = self.polymarket.get_bitcoin_mining_markets()
        
        if not markets:
            st.info("No market data available for analysis.")
            return
        
        # Prepare data for analysis
        market_data = []
        for market in markets:
            metrics = self.polymarket.calculate_market_metrics(market)
            market_data.append({
                'Question': metrics['question'][:50] + '...',
                'Probability': metrics.get('implied_probability', 0),
                'Volume': metrics.get('volume', 0),
                'Days_Left': metrics.get('days_remaining', 0),
                'Liquidity': metrics.get('liquidity_tier', 'Unknown')
            })
        
        if not market_data:
            return
        
        df = pd.DataFrame(market_data)
        
        # Probability distribution
        st.markdown("### 🎯 Probability Distribution")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Histogram of probabilities
            fig = px.histogram(
                df, 
                x='Probability', 
                nbins=20,
                title="Distribution of Market Probabilities",
                labels={'Probability': 'Probability (%)', 'count': 'Number of Markets'}
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Volume vs Probability scatter
            fig = px.scatter(
                df, 
                x='Probability', 
                y='Volume',
                size='Volume',
                color='Liquidity',
                title="Volume vs Probability",
                labels={'Probability': 'Probability (%)', 'Volume': 'Volume ($)'}
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        
        # Top markets by volume
        st.markdown("### 💰 Top Markets by Volume")
        
        top_volume = df.nlargest(5, 'Volume')[['Question', 'Probability', 'Volume', 'Liquidity']]
        top_volume['Volume'] = top_volume['Volume'].apply(lambda x: f"${x:,.0f}")
        top_volume['Probability'] = top_volume['Probability'].apply(lambda x: f"{x:.1f}%")
        
        st.dataframe(top_volume, use_container_width=True)
        
        # Market sentiment analysis
        st.markdown("### 📈 Market Sentiment Analysis")
        
        avg_prob = df['Probability'].mean()
        high_confidence = len(df[df['Probability'] > 70])
        uncertain = len(df[(df['Probability'] >= 30) & (df['Probability'] <= 70)])
        low_confidence = len(df[df['Probability'] < 30])
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("High Confidence", f"{high_confidence} markets", f"{high_confidence/len(df)*100:.1f}%")
        
        with col2:
            st.metric("Uncertain", f"{uncertain} markets", f"{uncertain/len(df)*100:.1f}%")
        
        with col3:
            st.metric("Low Confidence", f"{low_confidence} markets", f"{low_confidence/len(df)*100:.1f}%")
        
        # Sentiment interpretation
        if avg_prob > 60:
            st.success("🟢 **Bullish Sentiment** - Markets generally optimistic about Bitcoin mining")
        elif avg_prob > 40:
            st.info("🔵 **Neutral Sentiment** - Markets are mixed on Bitcoin mining outlook")
        else:
            st.error("🔴 **Bearish Sentiment** - Markets pessimistic about Bitcoin mining")
    
    def _render_mining_stocks_bets(self):
        """Render specific mining stocks prediction markets"""
        st.subheader("🎯 Mining Stocks Prediction Markets")
        st.markdown("Markets specifically related to MARA, RIOT, CLSK, HUT and other mining stocks")
        
        # Search for specific mining stock markets
        mining_stocks = ['MARA', 'RIOT', 'CLSK', 'HUT', 'Marathon Digital', 'Riot Platforms']
        
        stock_markets = {}
        
        for stock in mining_stocks:
            markets = self.polymarket.search_markets_by_keyword(stock)
            if markets:
                stock_markets[stock] = markets
        
        if not stock_markets:
            st.info("No specific mining stock markets found. Check back later for new markets.")
            
            # Show general mining markets instead
            st.markdown("### 🔍 Related Mining Markets")
            general_markets = self.polymarket.get_bitcoin_mining_markets()
            
            for market in general_markets[:5]:
                metrics = self.polymarket.calculate_market_metrics(market)
                
                with st.expander(f"📊 {metrics['question'][:60]}..."):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown(f"**Probability:** {metrics.get('implied_probability', 0):.1f}%")
                        st.markdown(f"**Volume:** ${metrics.get('volume', 0):,.0f}")
                    
                    with col2:
                        st.markdown(f"**End Date:** {metrics.get('end_date', 'TBD')}")
                        st.markdown(f"**Status:** {'Active' if metrics.get('active') else 'Inactive'}")
            
            return
        
        # Display stock-specific markets
        for stock, markets in stock_markets.items():
            if markets:
                st.markdown(f"### 📈 {stock} Markets")
                
                for market in markets[:3]:  # Show top 3 per stock
                    metrics = self.polymarket.calculate_market_metrics(market)
                    
                    with st.expander(f"{stock}: {metrics['question'][:50]}..."):
                        self._render_market_card(market, metrics)
        
        # Stock market comparison
        if len(stock_markets) > 1:
            st.markdown("### 📊 Stock Market Comparison")
            
            comparison_data = []
            for stock, markets in stock_markets.items():
                if markets:
                    total_volume = sum(float(m.get('volume', 0)) for m in markets)
                    avg_prob = np.mean([
                        float(m.get('tokens', [{}])[0].get('price', 0.5)) * 100 
                        for m in markets if m.get('tokens')
                    ])
                    
                    comparison_data.append({
                        'Stock': stock,
                        'Markets': len(markets),
                        'Total Volume': total_volume,
                        'Avg Probability': avg_prob
                    })
            
            if comparison_data:
                comp_df = pd.DataFrame(comparison_data)
                
                # Bar chart comparison
                fig = px.bar(
                    comp_df, 
                    x='Stock', 
                    y='Total Volume',
                    title="Total Betting Volume by Mining Stock",
                    labels={'Total Volume': 'Volume ($)'}
                )
                st.plotly_chart(fig, use_container_width=True)
                
                # Data table
                comp_df['Total Volume'] = comp_df['Total Volume'].apply(lambda x: f"${x:,.0f}")
                comp_df['Avg Probability'] = comp_df['Avg Probability'].apply(lambda x: f"{x:.1f}%")
                st.dataframe(comp_df, use_container_width=True)