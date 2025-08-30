import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.data_fetcher import DataFetcher
from utils.options_analyzer import OptionsAnalyzer

class WeeklyOutlook:
    """Weekly price direction analysis component"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.options_analyzer = OptionsAnalyzer()
    
    def render(self, selected_stocks, stock_names):
        """Render weekly outlook dashboard"""
        
        st.subheader("🔮 Weekly Price Outlook")
        st.write("Algorithmic analysis combining technical indicators, options flow, and dark pool activity to predict weekly direction.")
        
        # Disclaimer
        with st.expander("⚠️ Important Disclaimer", expanded=False):
            st.warning("""
            **This is not financial advice.** Price predictions are based on technical analysis and current market data patterns. 
            Markets are unpredictable and any prediction can be wrong. Past performance doesn't guarantee future results.
            Use this analysis as one factor among many in your trading decisions.
            """)
        
        # Generate outlook for each stock
        outlook_data = []
        
        for symbol in selected_stocks:
            outlook = self._analyze_stock_outlook(symbol, stock_names.get(symbol, symbol))
            if outlook:
                outlook_data.append(outlook)
        
        if outlook_data:
            # Summary overview
            self._render_sector_summary(outlook_data)
            
            # Individual stock outlooks
            st.subheader("📊 Individual Stock Outlooks")
            for outlook in outlook_data:
                self._render_stock_outlook(outlook)
        else:
            st.error("Unable to generate outlook data. Please try refreshing.")
    
    def _analyze_stock_outlook(self, symbol, company_name):
        """Analyze individual stock for weekly outlook"""
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
                'volume_score': 0
            }
            
            # Get stock data for technical analysis
            stock_data = self.data_fetcher.get_stock_data([symbol], '1M')
            if stock_data.empty or symbol not in stock_data.columns:
                return None
                
            prices = stock_data[symbol].dropna()
            if len(prices) < 20:
                return None
            
            current_price = prices.iloc[-1]
            
            # Technical Analysis Score (-3 to +3)
            technical_score = self._calculate_technical_score(prices)
            outlook['technical_score'] = technical_score
            
            # Options Flow Score (-3 to +3)  
            options_score = self._calculate_options_score(symbol, current_price)
            outlook['options_score'] = options_score
            
            # Volume/Dark Pool Score (-3 to +3)
            volume_score = self._calculate_volume_score(symbol)
            outlook['volume_score'] = volume_score
            
            # Combined Score
            total_score = technical_score + options_score + volume_score
            outlook['score'] = total_score
            
            # Determine direction and confidence
            if total_score >= 2:
                outlook['direction'] = 'Bullish'
                outlook['confidence'] = min(90, 60 + (total_score - 2) * 10)
            elif total_score >= 1:
                outlook['direction'] = 'Mild Bullish'
                outlook['confidence'] = 55 + total_score * 5
            elif total_score <= -2:
                outlook['direction'] = 'Bearish'
                outlook['confidence'] = min(90, 60 + abs(total_score + 2) * 10)
            elif total_score <= -1:
                outlook['direction'] = 'Mild Bearish'  
                outlook['confidence'] = 55 + abs(total_score) * 5
            else:
                outlook['direction'] = 'Neutral'
                outlook['confidence'] = 40 + abs(total_score) * 5
            
            # Generate reasoning factors
            outlook['factors'] = self._generate_factors(technical_score, options_score, volume_score, symbol)
            
            return outlook
            
        except Exception as e:
            st.error(f"Error analyzing {symbol}: {str(e)}")
            return None
    
    def _calculate_technical_score(self, prices):
        """Calculate technical analysis score (-3 to +3)"""
        score = 0
        
        try:
            current_price = prices.iloc[-1]
            
            # Moving Average Analysis
            if len(prices) >= 20:
                sma_20 = prices.rolling(20).mean().iloc[-1]
                if current_price > sma_20 * 1.02:  # Above SMA20 by 2%
                    score += 1
                elif current_price < sma_20 * 0.98:  # Below SMA20 by 2%
                    score -= 1
            
            if len(prices) >= 50:
                sma_50 = prices.rolling(50).mean().iloc[-1]
                if current_price > sma_50 * 1.03:  # Above SMA50 by 3%
                    score += 1
                elif current_price < sma_50 * 0.97:  # Below SMA50 by 3%
                    score -= 1
            
            # Momentum Analysis
            if len(prices) >= 5:
                week_change = (current_price - prices.iloc[-5]) / prices.iloc[-5]
                if week_change > 0.05:  # Up 5% in a week
                    score += 1
                elif week_change < -0.05:  # Down 5% in a week
                    score -= 1
            
            # RSI Analysis
            if len(prices) >= 14:
                rsi = self._calculate_rsi(prices)
                if rsi < 30:  # Oversold
                    score += 1
                elif rsi > 70:  # Overbought
                    score -= 1
            
            return max(-3, min(3, score))
            
        except Exception:
            return 0
    
    def _calculate_options_score(self, symbol, current_price):
        """Calculate options flow score (-3 to +3)"""
        score = 0
        
        try:
            calls_df, puts_df = self.data_fetcher.get_options_data(symbol)
            
            if calls_df is None and puts_df is None:
                return 0
                
            # Put-Call Ratio Analysis
            pc_analysis = self.options_analyzer.analyze_put_call_ratio(calls_df, puts_df)
            pc_ratio = pc_analysis.get('put_call_ratio', 1.0)
            
            if pc_ratio < 0.6:  # Very bullish
                score += 2
            elif pc_ratio < 0.8:  # Bullish
                score += 1
            elif pc_ratio > 1.4:  # Very bearish
                score -= 2
            elif pc_ratio > 1.2:  # Bearish
                score -= 1
            
            # Options Flow Analysis
            flow_metrics = self.options_analyzer.calculate_options_flow_metrics(
                calls_df, puts_df, current_price
            )
            
            smart_money = flow_metrics.get('smart_money_indicator', 'Neutral')
            if 'Strong Bullish' in smart_money:
                score += 1
            elif 'Bullish' in smart_money:
                score += 0.5
            elif 'Strong Bearish' in smart_money:
                score -= 1
            elif 'Bearish' in smart_money:
                score -= 0.5
            
            return max(-3, min(3, int(score)))
            
        except Exception:
            return 0
    
    def _calculate_volume_score(self, symbol):
        """Calculate volume/dark pool score (-3 to +3)"""
        score = 0
        
        try:
            indicators = self.data_fetcher.calculate_dark_pool_indicators(symbol)
            
            if not indicators:
                return 0
            
            volume_ratio = indicators.get('volume_ratio', 1.0)
            unusual_volume_pct = indicators.get('unusual_volume_pct', 0)
            current_price = indicators.get('current_price', 0)
            vwap = indicators.get('vwap', 0)
            
            # Volume Analysis
            if volume_ratio > 3.0:  # Very high volume
                score += 1
            elif volume_ratio > 2.0:  # High volume  
                score += 0.5
            elif volume_ratio < 0.5:  # Low volume
                score -= 0.5
            
            # VWAP Analysis
            if vwap > 0:
                vwap_diff = (current_price - vwap) / vwap
                if vwap_diff > 0.02:  # Above VWAP
                    score += 1
                elif vwap_diff < -0.02:  # Below VWAP
                    score -= 1
            
            # Unusual Activity
            if unusual_volume_pct > 40:  # Frequent unusual activity
                score += 0.5
            
            return max(-3, min(3, int(score)))
            
        except Exception:
            return 0
    
    def _calculate_rsi(self, prices, window=14):
        """Calculate RSI"""
        try:
            delta = prices.diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else 50.0
        except:
            return 50.0
    
    def _generate_factors(self, tech_score, options_score, volume_score, symbol):
        """Generate reasoning factors"""
        factors = []
        
        # Technical factors
        if tech_score >= 2:
            factors.append("Strong technical momentum with price above key moving averages")
        elif tech_score >= 1:
            factors.append("Positive technical signals from trend and momentum indicators")
        elif tech_score <= -2:
            factors.append("Weak technical picture with bearish momentum signals")
        elif tech_score <= -1:
            factors.append("Technical indicators showing downward pressure")
        
        # Options factors
        if options_score >= 2:
            factors.append("Bullish options flow with low put-call ratio")
        elif options_score >= 1:
            factors.append("Options activity suggests mild bullish sentiment")
        elif options_score <= -2:
            factors.append("Heavy put buying indicates bearish options positioning")
        elif options_score <= -1:
            factors.append("Options flow shows defensive positioning")
        
        # Volume factors
        if volume_score >= 1:
            factors.append("High volume activity with institutional accumulation signs")
        elif volume_score <= -1:
            factors.append("Volume patterns suggest distribution or low interest")
        
        if not factors:
            factors.append("Mixed signals across technical, options, and volume indicators")
        
        return factors
    
    def _render_sector_summary(self, outlook_data):
        """Render sector-wide summary"""
        st.subheader("🎯 Sector Summary")
        
        # Calculate sector metrics
        bullish_count = len([x for x in outlook_data if 'Bullish' in x['direction']])
        bearish_count = len([x for x in outlook_data if 'Bearish' in x['direction']])
        neutral_count = len(outlook_data) - bullish_count - bearish_count
        
        avg_confidence = np.mean([x['confidence'] for x in outlook_data])
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Bullish Stocks", bullish_count)
            
        with col2:
            st.metric("Bearish Stocks", bearish_count)
            
        with col3:
            st.metric("Neutral Stocks", neutral_count)
            
        with col4:
            st.metric("Avg Confidence", f"{avg_confidence:.0f}%")
        
        # Sector bias
        if bullish_count > bearish_count:
            st.success(f"🟢 **Sector Bias: BULLISH** - {bullish_count} stocks showing upward signals")
        elif bearish_count > bullish_count:
            st.error(f"🔴 **Sector Bias: BEARISH** - {bearish_count} stocks showing downward signals") 
        else:
            st.info("⚪ **Sector Bias: NEUTRAL** - Mixed signals across mining stocks")
    
    def _render_stock_outlook(self, outlook):
        """Render individual stock outlook"""
        
        with st.expander(f"{outlook['symbol']} - {outlook['company']}", expanded=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # Direction and confidence
                direction = outlook['direction']
                confidence = outlook['confidence']
                
                if 'Bullish' in direction:
                    st.success(f"📈 **{direction.upper()}** - {confidence}% confidence")
                elif 'Bearish' in direction:
                    st.error(f"📉 **{direction.upper()}** - {confidence}% confidence")
                else:
                    st.info(f"➡️ **{direction.upper()}** - {confidence}% confidence")
                
                # Factors
                st.write("**Key Factors:**")
                for factor in outlook['factors']:
                    st.write(f"• {factor}")
            
            with col2:
                # Score breakdown
                st.write("**Signal Breakdown:**")
                st.write(f"Technical: {outlook['technical_score']:+d}/3")
                st.write(f"Options: {outlook['options_score']:+d}/3")
                st.write(f"Volume: {outlook['volume_score']:+d}/3")
                st.write(f"**Total: {outlook['score']:+d}/9**")
                
                # Confidence bar
                confidence_color = "green" if confidence > 70 else "orange" if confidence > 50 else "red"
                st.progress(confidence/100)
                st.caption(f"{confidence}% confidence")