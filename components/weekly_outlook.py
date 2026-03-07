import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.unified_data_fetcher import DataFetcher
from utils.options_analytics import OptionsAnalytics as OptionsAnalyzer
from components.advanced_ta_dashboard import AdvancedTADashboard
from components.sentiment_analysis import SentimentAnalysis
from components.risk_center import RiskCenter

class WeeklyOutlook:
    """Weekly/Monthly price direction analysis component"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.options_analyzer = OptionsAnalyzer()
        self.enhanced_technical = AdvancedTADashboard()
        self.sentiment_analysis = SentimentAnalysis()
        self.risk_management = RiskCenter()
    
    def render(self, selected_stocks, stock_names):
        """Render weekly/monthly outlook dashboard"""
        
        # Time period selector
        col1, col2 = st.columns([3, 1])
        
        with col1:
            st.subheader("🔮 Price Direction Outlook")
            st.write("Comprehensive analysis combining all data sources for intelligent price predictions.")
        
        with col2:
            time_frame = st.selectbox(
                "Analysis Period",
                ["Weekly", "Monthly"],
                index=0,
                help="Choose prediction timeframe"
            )
        
        # Dynamic title based on selection
        period_emoji = "📅" if time_frame == "Weekly" else "📆"
        st.markdown(f"### {period_emoji} {time_frame} Market Direction Analysis")
        
        # Disclaimer
        with st.expander("⚠️ Important Disclaimer", expanded=False):
            st.warning("""
            **This is not financial advice.** Price predictions are based on technical analysis and current market data patterns. 
            Markets are unpredictable and any prediction can be wrong. Past performance doesn't guarantee future results.
            Use this analysis as one factor among many in your trading decisions.
            """)
        
        # Get integrated data from all components
        technical_data = self.enhanced_technical.get_technical_data(selected_stocks)
        sentiment_data = self.sentiment_analysis.get_sentiment_data(selected_stocks)
        risk_data = self.risk_management.get_risk_data(selected_stocks)
        
        # Generate outlook for each stock
        outlook_data = []
        
        for symbol in selected_stocks:
            outlook = self._analyze_stock_outlook(
                symbol, 
                stock_names.get(symbol, symbol),
                time_frame,
                technical_data.get(symbol, {}),
                sentiment_data.get(symbol, {}),
                risk_data.get(symbol, {}),
                sentiment_data.get('market', {})
            )
            if outlook:
                outlook_data.append(outlook)
        
        if outlook_data:
            # Summary overview
            self._render_sector_summary(outlook_data, time_frame)
            
            # Individual stock outlooks
            st.subheader("📊 Individual Stock Outlooks")
            for outlook in outlook_data:
                self._render_stock_outlook(outlook)
        else:
            st.error("Unable to generate outlook data. Please try refreshing.")
    
    def _analyze_stock_outlook(self, symbol, company_name, time_frame, technical_data, sentiment_data, risk_data, market_data):
        """Analyze individual stock for weekly/monthly outlook"""
        try:
            outlook = {
                'symbol': symbol,
                'company': company_name,
                'direction': 'Neutral',
                'confidence': 0,
                'factors': [],
                'score': 0,
                'technical_score': 0,
                'options_score': 0,
                'volume_score': 0,
                'sentiment_score': 0,
                'risk_score': 0,
                'time_frame': time_frame,
                'price_target': 0,
                'probability': 0
            }
            
            # Get stock data for analysis
            period = '2M' if time_frame == 'Monthly' else '1M'
            stock_data = self.data_fetcher.get_stock_data([symbol], period)
            if stock_data.empty or symbol not in stock_data.columns:
                return None
                
            prices = stock_data[symbol].dropna()
            if len(prices) < 20:
                return None
            
            current_price = prices.iloc[-1]
            
            # Enhanced Technical Analysis Score (-3 to +3) - Using new component data
            technical_score = self._calculate_enhanced_technical_score(prices, technical_data)
            outlook['technical_score'] = technical_score
            
            # Sentiment Analysis Score (-3 to +3) - New component
            sentiment_score = self._calculate_sentiment_score(sentiment_data, market_data)
            outlook['sentiment_score'] = sentiment_score
            
            # Risk-Adjusted Score (-2 to +2) - New component  
            risk_score = self._calculate_risk_adjusted_score(risk_data)
            outlook['risk_score'] = risk_score
            
            # Options Flow Score (-3 to +3)  
            options_score = self._calculate_options_score(symbol, current_price)
            outlook['options_score'] = options_score
            
            # Volume/Dark Pool Score (-3 to +3)
            volume_score = self._calculate_volume_score(symbol)
            outlook['volume_score'] = volume_score
            
            # Combined Score (Enhanced with all components)
            total_score = technical_score + options_score + volume_score + sentiment_score + risk_score
            outlook['score'] = total_score
            
            # Calculate price target and probability
            outlook['price_target'] = self._calculate_price_target(current_price, total_score, time_frame)
            outlook['probability'] = self._calculate_probability(total_score, time_frame)
            
            # Determine direction and confidence (Enhanced with better thresholds)
            if total_score >= 3:
                outlook['direction'] = 'Strong Bullish'
                outlook['confidence'] = min(95, 70 + (total_score - 3) * 5)
            elif total_score >= 1.5:
                outlook['direction'] = 'Bullish'
                outlook['confidence'] = min(85, 60 + (total_score - 1.5) * 8)
            elif total_score >= 0.5:
                outlook['direction'] = 'Mild Bullish'
                outlook['confidence'] = 50 + total_score * 10
            elif total_score <= -3:
                outlook['direction'] = 'Strong Bearish'
                outlook['confidence'] = min(95, 70 + abs(total_score + 3) * 5)
            elif total_score <= -1.5:
                outlook['direction'] = 'Bearish'
                outlook['confidence'] = min(85, 60 + abs(total_score + 1.5) * 8)
            elif total_score <= -0.5:
                outlook['direction'] = 'Mild Bearish'  
                outlook['confidence'] = 50 + abs(total_score) * 10
            else:
                outlook['direction'] = 'Neutral'
                outlook['confidence'] = 40 + abs(total_score) * 5
            
            # Generate explanatory factors
            outlook['factors'] = self._generate_factors(outlook, technical_data, sentiment_data, risk_data, market_data)
            
            return outlook
            
        except Exception as e:
            st.error(f"Error analyzing {symbol}: {str(e)}")
            return None
    
    def _calculate_enhanced_technical_score(self, prices, technical_data):
        """Calculate enhanced technical score using advanced indicators"""
        try:
            score = 0
            
            # Use data from enhanced technical component if available
            if technical_data:
                trend_signal = technical_data.get('trend_signal', 'Neutral')
                momentum_signal = technical_data.get('momentum_signal', 'Mixed')
                technical_score = technical_data.get('technical_score', 0)
                
                # Convert enhanced component data to score
                if trend_signal == 'Bullish':
                    score += 1.5
                elif trend_signal == 'Bearish':
                    score -= 1.5
                
                if momentum_signal == 'Strong':
                    score += 1.0
                elif momentum_signal == 'Weak':
                    score -= 1.0
                
                # Use normalized technical score from component
                score += (technical_score / 5.0) * 0.5  # Convert 5-point scale to 0.5 contribution
            else:
                # Fallback to basic technical analysis
                score = self._calculate_technical_score(prices)
            
            return max(-3, min(3, score))
            
        except Exception as e:
            return 0
    
    def _calculate_sentiment_score(self, sentiment_data, market_data):
        """Calculate sentiment score from sentiment analysis component"""
        try:
            score = 0
            
            if sentiment_data:
                # Individual stock sentiment
                sentiment_bias = sentiment_data.get('sentiment_bias', 0)
                score += sentiment_bias
                
                # Sentiment score normalization
                sentiment_score = sentiment_data.get('sentiment_score', 5.0)
                normalized_sentiment = (sentiment_score - 5.0) / 5.0 * 2.0  # Convert to -2 to +2 scale
                score += normalized_sentiment
            
            if market_data:
                # Market-wide sentiment influence
                market_bias = market_data.get('market_bias', 'Neutral')
                if market_bias == 'Bullish':
                    score += 0.5
                elif market_bias == 'Bearish':
                    score -= 0.5
                
                # Fear/Greed influence
                fear_greed = market_data.get('fear_greed_score', 50)
                if fear_greed > 70:
                    score -= 0.5  # Extreme greed is bearish
                elif fear_greed < 30:
                    score += 0.5  # Extreme fear is bullish
            
            return max(-3, min(3, score))
            
        except Exception as e:
            return 0
    
    def _calculate_risk_adjusted_score(self, risk_data):
        """Calculate risk-adjusted score from risk management component"""
        try:
            score = 0
            
            if risk_data:
                # Risk adjustment factor
                risk_adjustment = risk_data.get('risk_adjustment', 0)
                score += risk_adjustment
                
                # Volatility adjustment
                volatility = risk_data.get('volatility', 50)
                if volatility > 80:
                    score -= 1.0  # High volatility reduces conviction
                elif volatility > 60:
                    score -= 0.5  # Moderate volatility slight reduction
                elif volatility < 30:
                    score += 0.5  # Low volatility increases conviction
                
                # Risk score influence
                risk_score = risk_data.get('risk_score', 5.0)
                if risk_score > 8:
                    score -= 0.5  # Very risky reduces conviction
                elif risk_score < 3:
                    score += 0.5  # Low risk increases conviction
            
            return max(-2, min(2, score))
            
        except Exception as e:
            return 0
    
    def _calculate_price_target(self, current_price, total_score, time_frame):
        """Calculate price target based on score and timeframe"""
        try:
            # Base movement percentage based on score strength
            base_move = abs(total_score) * 0.05  # 5% per point
            
            # Adjust for timeframe
            if time_frame == 'Monthly':
                base_move *= 2.0  # Monthly targets can be larger
            
            # Direction
            if total_score > 0:
                target = current_price * (1 + base_move)
            else:
                target = current_price * (1 - base_move)
            
            return round(target, 2)
            
        except Exception as e:
            return current_price
    
    def _calculate_probability(self, total_score, time_frame):
        """Calculate probability of direction based on score"""
        try:
            # Base probability from score strength
            base_prob = min(95, 50 + abs(total_score) * 8)
            
            # Adjust for timeframe (longer term is less certain)
            if time_frame == 'Monthly':
                base_prob *= 0.9
            
            return round(base_prob)
            
        except Exception as e:
            return 50
    
    def _generate_factors(self, outlook, technical_data, sentiment_data, risk_data, market_data):
        """Generate explanatory factors for the outlook"""
        factors = []
        
        try:
            # Technical factors
            if outlook['technical_score'] > 1:
                factors.append("🟢 Strong technical indicators support upward momentum")
            elif outlook['technical_score'] < -1:
                factors.append("🔴 Technical indicators suggest downward pressure")
            
            if technical_data:
                trend = technical_data.get('trend_signal', '')
                if trend == 'Bullish':
                    factors.append("📈 Bullish trend confirmation across multiple timeframes")
                elif trend == 'Bearish':
                    factors.append("📉 Bearish trend signals dominating")
            
            # Sentiment factors
            if outlook['sentiment_score'] > 1:
                factors.append("😊 Positive market sentiment and crypto correlation")
            elif outlook['sentiment_score'] < -1:
                factors.append("😰 Negative sentiment weighing on mining sector")
            
            # Risk factors
            if outlook['risk_score'] < -0.5:
                factors.append("⚠️ High volatility and risk metrics suggest caution")
            elif outlook['risk_score'] > 0.5:
                factors.append("✅ Risk metrics support position sizing")
            
            # Options factors
            if outlook['options_score'] > 1:
                factors.append("⚡ Options flow showing institutional bullish positioning")
            elif outlook['options_score'] < -1:
                factors.append("⚡ Options activity suggests bearish institutional sentiment")
            
            # Volume factors
            if outlook['volume_score'] > 1:
                factors.append("🌊 Dark pool activity and volume support the move")
            elif outlook['volume_score'] < -1:
                factors.append("🌊 Volume patterns show distribution/selling pressure")
            
            # Market context
            if market_data:
                fear_greed = market_data.get('fear_greed_score', 50)
                if fear_greed > 75:
                    factors.append("🚨 Extreme greed levels suggest potential reversal risk")
                elif fear_greed < 25:
                    factors.append("💎 Extreme fear creates contrarian opportunity")
            
            # Confidence context
            if outlook['confidence'] > 80:
                factors.append(f"🎯 High confidence {outlook['time_frame'].lower()} prediction")
            elif outlook['confidence'] < 50:
                factors.append(f"🤔 Lower confidence due to mixed signals")
            
            return factors[:6]  # Limit to 6 most relevant factors
            
        except Exception as e:
            return ["Analysis based on available market data"]
    
    def _render_sector_summary(self, outlook_data, time_frame):
        """Render sector summary with enhanced metrics"""
        st.subheader(f"🎯 {time_frame} Sector Summary")
        
        # Calculate summary statistics
        total_stocks = len(outlook_data)
        bullish_count = len([x for x in outlook_data if 'Bullish' in x['direction']])
        bearish_count = len([x for x in outlook_data if 'Bearish' in x['direction']])
        neutral_count = total_stocks - bullish_count - bearish_count
        
        avg_confidence = np.mean([x['confidence'] for x in outlook_data])
        avg_score = np.mean([x['score'] for x in outlook_data])
        
        # Display summary metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            st.metric("Bullish Signals", f"{bullish_count}/{total_stocks}")
            if bullish_count > total_stocks / 2:
                st.success("Sector Bullish")
            
        with col2:
            st.metric("Bearish Signals", f"{bearish_count}/{total_stocks}")
            if bearish_count > total_stocks / 2:
                st.error("Sector Bearish")
        
        with col3:
            st.metric("Neutral", f"{neutral_count}/{total_stocks}")
        
        with col4:
            st.metric("Avg Confidence", f"{avg_confidence:.0f}%")
        
        with col5:
            st.metric("Sector Score", f"{avg_score:+.1f}")
            if avg_score > 1:
                st.success("Strong")
            elif avg_score < -1:
                st.error("Weak")
            else:
                st.info("Mixed")
        
        # Sector outlook
        if avg_score > 1.5:
            sector_outlook = f"🟢 **Strong {time_frame} Bullish Outlook** - Multiple confirmations across technical, sentiment, and flow analysis"
        elif avg_score > 0.5:
            sector_outlook = f"🟢 **{time_frame} Bullish Bias** - Positive signals outweigh negative factors"
        elif avg_score < -1.5:
            sector_outlook = f"🔴 **Strong {time_frame} Bearish Outlook** - Multiple bearish confirmations across data sources"
        elif avg_score < -0.5:
            sector_outlook = f"🔴 **{time_frame} Bearish Bias** - Negative signals dominating"
        else:
            sector_outlook = f"🟡 **{time_frame} Neutral/Mixed** - Conflicting signals require selective stock picking"
        
        st.markdown(sector_outlook)
        
        # Top picks based on score
        sorted_outlooks = sorted(outlook_data, key=lambda x: x['score'], reverse=True)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**🏆 Top Bullish Picks:**")
            for i, outlook in enumerate(sorted_outlooks[:3]):
                if outlook['score'] > 0:
                    st.write(f"{i+1}. **{outlook['symbol']}** - {outlook['direction']} ({outlook['confidence']}% confidence)")
        
        with col2:
            st.write("**🔻 Most Bearish:**")
            for i, outlook in enumerate(reversed(sorted_outlooks[-3:])):
                if outlook['score'] < 0:
                    st.write(f"{i+1}. **{outlook['symbol']}** - {outlook['direction']} ({outlook['confidence']}% confidence)")
    
    def _render_stock_outlook(self, outlook):
        """Render individual stock outlook with enhanced display"""
        with st.expander(f"{outlook['symbol']} - {outlook['company']} | {outlook['direction']} ({outlook['confidence']}%)", expanded=False):
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Direction and confidence
                direction_color = "🟢" if "Bullish" in outlook['direction'] else "🔴" if "Bearish" in outlook['direction'] else "🟡"
                st.markdown(f"### {direction_color} {outlook['direction']}")
                st.markdown(f"**Confidence:** {outlook['confidence']}%")
                st.markdown(f"**{outlook['time_frame']} Price Target:** ${outlook['price_target']:.2f}")
                st.markdown(f"**Probability:** {outlook['probability']}%")
                
                # Score breakdown
                st.write("**Score Breakdown:**")
                st.write(f"• Technical: {outlook['technical_score']:+.1f}")
                st.write(f"• Sentiment: {outlook['sentiment_score']:+.1f}")
                st.write(f"• Options Flow: {outlook['options_score']:+.1f}")
                st.write(f"• Volume/Dark Pool: {outlook['volume_score']:+.1f}")
                st.write(f"• Risk Adjustment: {outlook['risk_score']:+.1f}")
                st.write(f"**Total Score: {outlook['score']:+.1f}**")
            
            with col2:
                # Visual score representation
                score_normalized = max(0, min(100, (outlook['score'] + 5) / 10 * 100))  # Convert -5 to +5 to 0-100, clamp to valid range
                st.progress(score_normalized / 100)
                st.write(f"Overall Strength: {score_normalized:.0f}%")
            
            # Factors
            if outlook['factors']:
                st.write("**Key Factors:**")
                for factor in outlook['factors']:
                    st.write(f"• {factor}")
    
    # Keep existing methods for backward compatibility
    def _calculate_technical_score(self, prices):
        """Basic technical analysis (fallback method)"""
        try:
            score = 0
            
            # Simple moving averages
            sma_20 = prices.rolling(20).mean()
            sma_50 = prices.rolling(50).mean() if len(prices) >= 50 else sma_20
            
            current_price = prices.iloc[-1]
            
            # Price vs moving averages
            if current_price > sma_20.iloc[-1]:
                score += 0.5
            if current_price > sma_50.iloc[-1]:
                score += 0.5
                
            # Moving average trend
            if sma_20.iloc[-1] > sma_20.iloc[-5]:
                score += 0.5
            if len(prices) >= 50 and sma_50.iloc[-1] > sma_50.iloc[-10]:
                score += 0.5
                
            # Recent momentum
            recent_change = (current_price - prices.iloc[-5]) / prices.iloc[-5]
            if recent_change > 0.05:
                score += 1
            elif recent_change < -0.05:
                score -= 1
                
            return max(-3, min(3, score))
            
        except Exception as e:
            return 0
    
    def _calculate_options_score(self, symbol, current_price):
        """Calculate options flow score"""
        try:
            # Options score proxy: uses real yfinance price/volume data
            # (IV proxy from realized vol + volume ratio — no options chain needed)
            score = 0
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if not hist.empty:
                # Calculate implied volatility proxy from price movements
                returns = hist['Close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252)  # Annualized volatility
                
                # Volume-based analysis
                recent_volume = hist['Volume'].tail(5).mean()
                avg_volume = hist['Volume'].mean()
                
                volume_ratio = recent_volume / avg_volume if avg_volume > 0 else 1
                
                # Score based on volatility and volume
                if volatility > 0.6:  # High volatility suggests options activity
                    if volume_ratio > 1.5:  # High volume with high volatility
                        score += 1
                    elif volume_ratio < 0.7:  # Low volume with high volatility
                        score -= 0.5
                
                # Price momentum factor
                if len(hist) >= 5:
                    price_change = (current_price - hist['Close'].iloc[-5]) / hist['Close'].iloc[-5]
                    if price_change > 0.05:  # Strong upward movement
                        score += 0.5
                    elif price_change < -0.05:  # Strong downward movement
                        score -= 0.5
                
                # Recent trend confirmation
                if hist['Close'].iloc[-1] > hist['Close'].rolling(10).mean().iloc[-1]:
                    score += 0.5
                else:
                    score -= 0.5
                
            return max(-3, min(3, score))
            
        except Exception as e:
            return 0
    
    def _calculate_volume_score(self, symbol):
        """Calculate volume/dark pool score"""
        try:
            volume_data = self.data_fetcher.get_stock_data([symbol], '1M')
            
            if volume_data.empty or 'Volume' not in volume_data.columns:
                return 0
                
            volumes = volume_data['Volume'].dropna()
            prices = volume_data[symbol].dropna()
            
            if len(volumes) < 10:
                return 0
                
            score = 0
            
            # Volume trend
            recent_vol = volumes.tail(5).mean()
            older_vol = volumes.head(10).mean()
            
            if recent_vol > older_vol * 1.5:
                score += 1
            elif recent_vol < older_vol * 0.7:
                score -= 0.5
                
            # Price-volume correlation
            price_changes = prices.pct_change().dropna()
            volume_changes = volumes.pct_change().dropna()
            
            # Align the data
            common_index = price_changes.index.intersection(volume_changes.index)
            if len(common_index) > 10:
                correlation = np.corrcoef(
                    price_changes.loc[common_index], 
                    volume_changes.loc[common_index]
                )[0, 1]
                
                if not np.isnan(correlation):
                    if correlation > 0.3:  # Positive correlation is bullish
                        score += 1
                    elif correlation < -0.3:  # Negative correlation is bearish
                        score -= 1
            
            return max(-3, min(3, score))
            
        except Exception as e:
            return 0