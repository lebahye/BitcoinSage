import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta
import requests

class SentimentAnalysis:
    """Market sentiment and news correlation analysis"""
    
    def __init__(self):
        self.sentiment_data = {}
    
    def render(self, selected_stocks, stock_names):
        """Render sentiment analysis dashboard"""
        
        st.subheader("📰 Market Sentiment Analysis")
        st.write("Track market sentiment, fear/greed indicators, and correlation signals across crypto and traditional markets.")
        
        # Market levels (BTC / VIX / S&P) are shown once in the Command Center;
        # correlations live in the RIOT Correlation Map tab (the old crypto-correlation
        # box here was always empty because of the BTC date-alignment bug).
        
        # Sector sentiment
        self._render_sector_sentiment(selected_stocks, stock_names)
        
        # Fear & Greed analysis
        self._render_fear_greed_analysis()
    
    def _render_market_sentiment_overview(self):
        """Render overall market sentiment"""
        st.subheader("🌍 Overall Market Sentiment")
        
        col1, col2, col3, col4 = st.columns(4)
        
        try:
            # VIX Fear Index
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period='5d')
            
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                prev_vix = vix_data['Close'].iloc[-2] if len(vix_data) > 1 else current_vix
                vix_change = current_vix - prev_vix
                
                with col1:
                    st.metric("VIX Fear Index", f"{current_vix:.2f}", f"{vix_change:+.2f}")
                    if current_vix > 30:
                        st.error("High Fear")
                    elif current_vix > 20:
                        st.warning("Moderate Fear")
                    else:
                        st.success("Low Fear")
            
            # Bitcoin sentiment
            btc = yf.Ticker("BTC-USD")
            btc_data = btc.history(period='5d')
            
            if not btc_data.empty:
                btc_price = btc_data['Close'].iloc[-1]
                btc_change = ((btc_price - btc_data['Close'].iloc[-2]) / btc_data['Close'].iloc[-2]) * 100
                
                with col2:
                    st.metric("Bitcoin Price", f"${btc_price:,.0f}", f"{btc_change:+.2f}%")
                    if btc_change > 5:
                        st.success("Very Bullish")
                    elif btc_change > 2:
                        st.success("Bullish")
                    elif btc_change < -5:
                        st.error("Very Bearish")
                    elif btc_change < -2:
                        st.error("Bearish")
                    else:
                        st.info("Neutral")
            
            # Dollar strength
            dxy = yf.Ticker("DX-Y.NYB")
            dxy_data = dxy.history(period='5d')
            
            if not dxy_data.empty:
                dxy_price = dxy_data['Close'].iloc[-1]
                dxy_change = ((dxy_price - dxy_data['Close'].iloc[-2]) / dxy_data['Close'].iloc[-2]) * 100
                
                with col3:
                    st.metric("Dollar Index", f"{dxy_price:.2f}", f"{dxy_change:+.2f}%")
                    if dxy_change > 1:
                        st.warning("Strong Dollar (Crypto Negative)")
                    elif dxy_change < -1:
                        st.success("Weak Dollar (Crypto Positive)")
                    else:
                        st.info("Neutral Dollar")
            
            # Gold sentiment (risk-off indicator)
            gold = yf.Ticker("GC=F")
            gold_data = gold.history(period='5d')
            
            if not gold_data.empty:
                gold_price = gold_data['Close'].iloc[-1]
                gold_change = ((gold_price - gold_data['Close'].iloc[-2]) / gold_data['Close'].iloc[-2]) * 100
                
                with col4:
                    st.metric("Gold Price", f"${gold_price:.2f}", f"{gold_change:+.2f}%")
                    if gold_change > 2:
                        st.warning("Risk-Off Sentiment")
                    elif gold_change < -2:
                        st.success("Risk-On Sentiment")
                    else:
                        st.info("Neutral Risk")
                        
        except Exception as e:
            st.error(f"Error fetching market sentiment data: {str(e)}")
    
    def _render_crypto_correlation(self, selected_stocks):
        """Render crypto correlation analysis"""
        st.subheader("₿ Crypto Market Correlation")
        
        try:
            # Get crypto data
            crypto_symbols = ["BTC-USD", "ETH-USD"]
            crypto_data = {}
            
            for symbol in crypto_symbols:
                ticker = yf.Ticker(symbol)
                data = ticker.history(period='1mo')
                if not data.empty:
                    crypto_data[symbol] = data['Close']
            
            # Get mining stock data
            stock_data = {}
            for symbol in selected_stocks[:4]:  # Limit to 4 stocks
                ticker = yf.Ticker(symbol)
                data = ticker.history(period='1mo')
                if not data.empty:
                    stock_data[symbol] = data['Close']
            
            if crypto_data and stock_data:
                # Combine data
                all_data = {**crypto_data, **stock_data}
                df = pd.DataFrame(all_data)
                df = df.dropna()
                
                if len(df) > 10:
                    # Calculate correlations
                    returns = df.pct_change().dropna()
                    correlation_matrix = returns.corr()
                    
                    # Create correlation heatmap
                    fig = px.imshow(
                        correlation_matrix.values,
                        x=correlation_matrix.columns,
                        y=correlation_matrix.columns,
                        color_continuous_scale='RdYlBu_r',
                        aspect="auto",
                        title="Crypto-Mining Stock Correlations"
                    )
                    
                    fig.update_layout(
                        template='plotly_dark',
                        height=400,
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Correlation insights
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Bitcoin Correlations:**")
                        btc_corrs = correlation_matrix.loc['BTC-USD', stock_data.keys()].sort_values(ascending=False)
                        for stock, corr in btc_corrs.items():
                            if corr > 0.7:
                                st.success(f"{stock}: {corr:.3f} (Strong)")
                            elif corr > 0.5:
                                st.info(f"{stock}: {corr:.3f} (Moderate)")
                            else:
                                st.warning(f"{stock}: {corr:.3f} (Weak)")
                    
                    with col2:
                        if 'ETH-USD' in correlation_matrix.columns:
                            st.write("**Ethereum Correlations:**")
                            eth_corrs = correlation_matrix.loc['ETH-USD', stock_data.keys()].sort_values(ascending=False)
                            for stock, corr in eth_corrs.items():
                                if corr > 0.7:
                                    st.success(f"{stock}: {corr:.3f} (Strong)")
                                elif corr > 0.5:
                                    st.info(f"{stock}: {corr:.3f} (Moderate)")
                                else:
                                    st.warning(f"{stock}: {corr:.3f} (Weak)")
                
        except Exception as e:
            st.error(f"Error analyzing crypto correlations: {str(e)}")
    
    def _render_sector_sentiment(self, selected_stocks, stock_names):
        """Render mining sector sentiment"""
        st.subheader("⛏️ Mining Sector Sentiment")
        
        try:
            sentiment_scores = []
            
            for symbol in selected_stocks:
                score = self._calculate_stock_sentiment_score(symbol)
                sentiment_scores.append({
                    'Symbol': symbol,
                    'Company': stock_names.get(symbol, symbol),
                    'Sentiment Score': score,
                    'Sentiment': self._interpret_sentiment_score(score)
                })
            
            if sentiment_scores:
                df = pd.DataFrame(sentiment_scores)
                
                # Display sentiment table
                st.dataframe(df, use_container_width=True, hide_index=True)
                
                # Sentiment distribution chart
                sentiment_counts = df['Sentiment'].value_counts()
                
                fig = px.pie(
                    values=sentiment_counts.values,
                    names=sentiment_counts.index,
                    title="Sector Sentiment Distribution",
                    color_discrete_map={
                        'Very Bullish': '#00ff00',
                        'Bullish': '#90EE90',
                        'Neutral': '#FFD700',
                        'Bearish': '#FF6347',
                        'Very Bearish': '#ff0000'
                    }
                )
                
                fig.update_layout(
                    template='plotly_dark',
                    height=400,
                    margin=dict(l=0, r=0, t=40, b=0)
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Sector insights
                avg_score = np.mean([s['Sentiment Score'] for s in sentiment_scores])
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Average Sentiment", f"{avg_score:.1f}/10")
                
                with col2:
                    bullish_count = len([s for s in sentiment_scores if 'Bullish' in s['Sentiment']])
                    st.metric("Bullish Stocks", f"{bullish_count}/{len(sentiment_scores)}")
                
                with col3:
                    if avg_score > 7:
                        st.success("🟢 Very Positive Sector Sentiment")
                    elif avg_score > 5.5:
                        st.success("🟢 Positive Sector Sentiment")
                    elif avg_score > 4.5:
                        st.info("🟡 Neutral Sector Sentiment")
                    elif avg_score > 3:
                        st.warning("🟠 Negative Sector Sentiment")
                    else:
                        st.error("🔴 Very Negative Sector Sentiment")
        
        except Exception as e:
            st.error(f"Error analyzing sector sentiment: {str(e)}")
    
    def _render_fear_greed_analysis(self):
        """Render fear & greed analysis"""
        st.subheader("😨😈 Fear & Greed Analysis")
        
        try:
            # Calculate composite fear/greed score
            fear_greed_score = self._calculate_fear_greed_score()
            
            # Create gauge chart
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=fear_greed_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': "Market Fear & Greed Index"},
                delta={'reference': 50},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 25], 'color': "darkred"},
                        {'range': [25, 45], 'color': "red"},
                        {'range': [45, 55], 'color': "yellow"},
                        {'range': [55, 75], 'color': "lightgreen"},
                        {'range': [75, 100], 'color': "green"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))
            
            fig.update_layout(
                template='plotly_dark',
                height=400,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            
            col1, col2 = st.columns([1, 1])
            
            with col1:
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.write("**Fear & Greed Interpretation:**")
                
                if fear_greed_score <= 25:
                    st.error("🔴 **Extreme Fear** - Potential buying opportunity")
                    st.write("• Market sentiment is very pessimistic")
                    st.write("• Contrarian indicator suggests upside potential")
                    st.write("• Good time for accumulation")
                elif fear_greed_score <= 45:
                    st.warning("🟠 **Fear** - Cautious market sentiment")
                    st.write("• Below-average market confidence")
                    st.write("• Some selling pressure present")
                    st.write("• Watch for reversal signals")
                elif fear_greed_score <= 55:
                    st.info("🟡 **Neutral** - Balanced market sentiment")
                    st.write("• Market sentiment is balanced")
                    st.write("• No extreme emotions driving prices")
                    st.write("• Look for directional catalysts")
                elif fear_greed_score <= 75:
                    st.success("🟢 **Greed** - Optimistic market sentiment")
                    st.write("• Above-average market confidence")
                    st.write("• Some buying pressure present")
                    st.write("• Momentum may continue")
                else:
                    st.error("🔴 **Extreme Greed** - Potential selling opportunity")
                    st.write("• Market sentiment is very optimistic")
                    st.write("• Contrarian indicator suggests downside risk")
                    st.write("• Consider taking profits")
                
                # Historical context
                st.write("**Key Factors:**")
                factors = self._get_fear_greed_factors()
                for factor in factors:
                    st.write(f"• {factor}")
        
        except Exception as e:
            st.error(f"Error in fear & greed analysis: {str(e)}")
    
    def _calculate_stock_sentiment_score(self, symbol):
        """Calculate sentiment score for individual stock (0-10 scale)"""
        try:
            score = 5.0  # Start neutral
            
            # Technical momentum factor
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if not hist.empty:
                # Price momentum (30%)
                current_price = hist['Close'].iloc[-1]
                month_ago_price = hist['Close'].iloc[0]
                month_return = (current_price - month_ago_price) / month_ago_price
                
                if month_return > 0.2:
                    score += 2.0
                elif month_return > 0.1:
                    score += 1.0
                elif month_return > 0:
                    score += 0.5
                elif month_return < -0.2:
                    score -= 2.0
                elif month_return < -0.1:
                    score -= 1.0
                elif month_return < 0:
                    score -= 0.5
                
                # Volume trend (20%)
                if 'Volume' in hist.columns:
                    recent_volume = hist['Volume'].tail(5).mean()
                    older_volume = hist['Volume'].head(10).mean()
                    
                    if recent_volume > older_volume * 1.5:
                        score += 1.0
                    elif recent_volume > older_volume * 1.2:
                        score += 0.5
                    elif recent_volume < older_volume * 0.8:
                        score -= 0.5
                
                # Volatility factor (15%)
                returns = hist['Close'].pct_change().dropna()
                volatility = returns.std()
                
                if volatility > 0.08:  # High volatility
                    score -= 0.5
                elif volatility < 0.03:  # Low volatility
                    score += 0.5
                
                # Relative performance vs Bitcoin (35%)
                btc = yf.Ticker("BTC-USD")
                btc_hist = btc.history(period='1mo')
                
                if not btc_hist.empty:
                    btc_return = (btc_hist['Close'].iloc[-1] - btc_hist['Close'].iloc[0]) / btc_hist['Close'].iloc[0]
                    relative_performance = month_return - btc_return
                    
                    if relative_performance > 0.1:
                        score += 1.5
                    elif relative_performance > 0.05:
                        score += 1.0
                    elif relative_performance > 0:
                        score += 0.5
                    elif relative_performance < -0.1:
                        score -= 1.5
                    elif relative_performance < -0.05:
                        score -= 1.0
                    elif relative_performance < 0:
                        score -= 0.5
            
            return max(0, min(10, score))
            
        except Exception as e:
            return 5.0  # Return neutral if error
    
    def _interpret_sentiment_score(self, score):
        """Interpret sentiment score"""
        if score >= 8:
            return "Very Bullish"
        elif score >= 6.5:
            return "Bullish"
        elif score >= 3.5:
            return "Neutral"
        elif score >= 2:
            return "Bearish"
        else:
            return "Very Bearish"
    
    def _calculate_fear_greed_score(self):
        """Calculate composite fear/greed score (0-100)"""
        try:
            score = 50  # Start neutral
            
            # VIX component (25% weight)
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period='5d')
            
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                
                if current_vix > 30:
                    score -= 15  # High fear
                elif current_vix > 25:
                    score -= 10  # Moderate fear
                elif current_vix > 20:
                    score -= 5   # Some fear
                elif current_vix < 15:
                    score += 15  # Low fear (greed)
                elif current_vix < 18:
                    score += 10  # Moderate greed
            
            # Bitcoin momentum (25% weight)
            btc = yf.Ticker("BTC-USD")
            btc_data = btc.history(period='7d')
            
            if not btc_data.empty:
                btc_change = (btc_data['Close'].iloc[-1] - btc_data['Close'].iloc[0]) / btc_data['Close'].iloc[0]
                
                if btc_change > 0.15:
                    score += 15  # Strong greed
                elif btc_change > 0.1:
                    score += 10  # Moderate greed
                elif btc_change > 0.05:
                    score += 5   # Mild greed
                elif btc_change < -0.15:
                    score -= 15  # Strong fear
                elif btc_change < -0.1:
                    score -= 10  # Moderate fear
                elif btc_change < -0.05:
                    score -= 5   # Mild fear
            
            # Dollar strength (20% weight)
            dxy = yf.Ticker("DX-Y.NYB")
            dxy_data = dxy.history(period='7d')
            
            if not dxy_data.empty:
                dxy_change = (dxy_data['Close'].iloc[-1] - dxy_data['Close'].iloc[0]) / dxy_data['Close'].iloc[0]
                
                if dxy_change > 0.02:
                    score -= 10  # Strong dollar = crypto fear
                elif dxy_change > 0.01:
                    score -= 5   # Moderate dollar strength
                elif dxy_change < -0.02:
                    score += 10  # Weak dollar = crypto greed
                elif dxy_change < -0.01:
                    score += 5   # Moderate dollar weakness
            
            # Gold movement (15% weight)
            gold = yf.Ticker("GC=F")
            gold_data = gold.history(period='7d')
            
            if not gold_data.empty:
                gold_change = (gold_data['Close'].iloc[-1] - gold_data['Close'].iloc[0]) / gold_data['Close'].iloc[0]
                
                if gold_change > 0.03:
                    score -= 8   # Flight to safety (fear)
                elif gold_change > 0.015:
                    score -= 4   # Some safe haven demand
                elif gold_change < -0.03:
                    score += 8   # Risk-on sentiment (greed)
                elif gold_change < -0.015:
                    score += 4   # Moderate risk appetite
            
            # S&P 500 momentum (15% weight)
            spy = yf.Ticker("SPY")
            spy_data = spy.history(period='7d')
            
            if not spy_data.empty:
                spy_change = (spy_data['Close'].iloc[-1] - spy_data['Close'].iloc[0]) / spy_data['Close'].iloc[0]
                
                if spy_change > 0.05:
                    score += 8   # Strong market greed
                elif spy_change > 0.02:
                    score += 4   # Moderate market optimism
                elif spy_change < -0.05:
                    score -= 8   # Strong market fear
                elif spy_change < -0.02:
                    score -= 4   # Moderate market pessimism
            
            return max(0, min(100, score))
            
        except Exception as e:
            return 50  # Return neutral if error
    
    def _get_fear_greed_factors(self):
        """Get key factors affecting fear/greed"""
        factors = []
        
        try:
            # VIX level
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period='2d')
            
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                if current_vix > 25:
                    factors.append(f"VIX at {current_vix:.1f} shows elevated fear")
                elif current_vix < 18:
                    factors.append(f"VIX at {current_vix:.1f} shows low fear/complacency")
                else:
                    factors.append(f"VIX at {current_vix:.1f} shows moderate volatility")
            
            # Bitcoin performance
            btc = yf.Ticker("BTC-USD")
            btc_data = btc.history(period='7d')
            
            if not btc_data.empty:
                btc_change = (btc_data['Close'].iloc[-1] - btc_data['Close'].iloc[0]) / btc_data['Close'].iloc[0]
                if btc_change > 0.1:
                    factors.append(f"Bitcoin up {btc_change:.1%} in 7 days - strong crypto optimism")
                elif btc_change < -0.1:
                    factors.append(f"Bitcoin down {btc_change:.1%} in 7 days - crypto weakness")
                else:
                    factors.append(f"Bitcoin {btc_change:+.1%} in 7 days - moderate crypto sentiment")
            
            # Dollar impact
            dxy = yf.Ticker("DX-Y.NYB")
            dxy_data = dxy.history(period='7d')
            
            if not dxy_data.empty:
                dxy_change = (dxy_data['Close'].iloc[-1] - dxy_data['Close'].iloc[0]) / dxy_data['Close'].iloc[0]
                if abs(dxy_change) > 0.015:
                    factors.append(f"Dollar {'strength' if dxy_change > 0 else 'weakness'} affecting crypto sentiment")
            
            if len(factors) < 3:
                factors.append("Market sentiment influenced by multiple cross-asset correlations")
            
        except:
            factors = ["Market sentiment analysis based on volatility and momentum indicators"]
        
        return factors
    
    def get_sentiment_data(self, selected_stocks):
        """Get sentiment data for integration with weekly outlook"""
        sentiment_data = {}
        
        # Calculate overall market sentiment
        market_sentiment = {
            'fear_greed_score': self._calculate_fear_greed_score(),
            'market_bias': 'Bullish' if self._calculate_fear_greed_score() > 55 else 'Bearish' if self._calculate_fear_greed_score() < 45 else 'Neutral'
        }
        
        # Calculate individual stock sentiment
        for symbol in selected_stocks:
            score = self._calculate_stock_sentiment_score(symbol)
            sentiment_data[symbol] = {
                'sentiment_score': score,
                'sentiment_signal': self._interpret_sentiment_score(score),
                'sentiment_bias': 1 if score > 6 else -1 if score < 4 else 0
            }
        
        sentiment_data['market'] = market_sentiment
        
        return sentiment_data