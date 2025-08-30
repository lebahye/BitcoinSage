import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import yfinance as yf
from datetime import datetime, timedelta

class EnhancedTechnical:
    """Enhanced technical analysis with advanced indicators"""
    
    def __init__(self):
        self.indicators_data = {}
    
    def render(self, selected_stocks, stock_names):
        """Render enhanced technical analysis dashboard"""
        
        st.subheader("📈 Enhanced Technical Analysis")
        st.write("Advanced technical indicators and pattern recognition for deeper market analysis.")
        
        # Quick overview
        self._render_technical_overview(selected_stocks)
        
        # Individual stock analysis
        for symbol in selected_stocks:
            with st.expander(f"{symbol} - {stock_names.get(symbol, symbol)} Advanced Analysis", expanded=False):
                self._render_stock_technical_analysis(symbol)
    
    def _render_technical_overview(self, selected_stocks):
        """Render sector technical overview"""
        st.subheader("🎯 Sector Technical Overview")
        
        overview_data = []
        
        for symbol in selected_stocks:
            try:
                indicators = self._calculate_all_indicators(symbol)
                if indicators:
                    overview_data.append({
                        'Symbol': symbol,
                        'Trend': indicators.get('trend_signal', 'Neutral'),
                        'Momentum': indicators.get('momentum_signal', 'Neutral'),
                        'Volatility': indicators.get('volatility_signal', 'Normal'),
                        'Support': f"${indicators.get('support_level', 0):.2f}",
                        'Resistance': f"${indicators.get('resistance_level', 0):.2f}",
                        'Score': indicators.get('technical_score', 0)
                    })
            except Exception as e:
                continue
        
        if overview_data:
            df = pd.DataFrame(overview_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Summary metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                bullish_count = len([x for x in overview_data if x['Trend'] == 'Bullish'])
                st.metric("Bullish Trends", f"{bullish_count}/{len(overview_data)}")
            
            with col2:
                strong_momentum = len([x for x in overview_data if x['Momentum'] == 'Strong'])
                st.metric("Strong Momentum", f"{strong_momentum}/{len(overview_data)}")
            
            with col3:
                high_vol = len([x for x in overview_data if x['Volatility'] == 'High'])
                st.metric("High Volatility", f"{high_vol}/{len(overview_data)}")
            
            with col4:
                avg_score = np.mean([x['Score'] for x in overview_data])
                st.metric("Avg Technical Score", f"{avg_score:+.1f}")
    
    def _render_stock_technical_analysis(self, symbol):
        """Render individual stock technical analysis"""
        
        try:
            # Get stock data
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='6mo')
            
            if hist.empty:
                st.warning(f"No data available for {symbol}")
                return
            
            # Calculate all indicators
            indicators = self._calculate_all_indicators(symbol, hist)
            
            # Create tabs for different analysis types
            tab1, tab2, tab3 = st.tabs(["📊 Indicators", "📈 Patterns", "🎯 Levels"])
            
            with tab1:
                self._render_indicators_tab(symbol, hist, indicators)
            
            with tab2:
                self._render_patterns_tab(symbol, hist, indicators)
            
            with tab3:
                self._render_levels_tab(symbol, hist, indicators)
                
        except Exception as e:
            st.error(f"Error analyzing {symbol}: {str(e)}")
    
    def _render_indicators_tab(self, symbol, hist, indicators):
        """Render technical indicators"""
        
        col1, col2 = st.columns(2)
        
        with col1:
            # MACD Chart
            fig_macd = self._create_macd_chart(symbol, hist)
            if fig_macd:
                st.plotly_chart(fig_macd, use_container_width=True)
        
        with col2:
            # RSI and Stochastic
            fig_oscillators = self._create_oscillators_chart(symbol, hist)
            if fig_oscillators:
                st.plotly_chart(fig_oscillators, use_container_width=True)
        
        # Indicator readings
        st.subheader("Current Indicator Readings")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            rsi = indicators.get('rsi', 50)
            rsi_signal = "Overbought" if rsi > 70 else "Oversold" if rsi < 30 else "Neutral"
            st.metric("RSI", f"{rsi:.1f}", rsi_signal)
        
        with col2:
            macd_signal = indicators.get('macd_signal', 'Neutral')
            st.metric("MACD", macd_signal)
        
        with col3:
            bb_signal = indicators.get('bollinger_signal', 'Neutral')
            st.metric("Bollinger Bands", bb_signal)
        
        with col4:
            stoch = indicators.get('stochastic', 50)
            stoch_signal = "Overbought" if stoch > 80 else "Oversold" if stoch < 20 else "Neutral"
            st.metric("Stochastic", f"{stoch:.1f}", stoch_signal)
    
    def _render_patterns_tab(self, symbol, hist, indicators):
        """Render pattern analysis"""
        
        # Price action patterns
        st.subheader("📊 Price Action Patterns")
        
        patterns = indicators.get('patterns', [])
        
        if patterns:
            for pattern in patterns:
                if pattern['type'] == 'bullish':
                    st.success(f"🟢 {pattern['name']}: {pattern['description']}")
                elif pattern['type'] == 'bearish':
                    st.error(f"🔴 {pattern['name']}: {pattern['description']}")
                else:
                    st.info(f"🔵 {pattern['name']}: {pattern['description']}")
        else:
            st.info("No significant patterns detected")
        
        # Volume patterns
        st.subheader("📈 Volume Patterns")
        volume_analysis = indicators.get('volume_patterns', {})
        
        if volume_analysis:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Volume Trend:**", volume_analysis.get('trend', 'Neutral'))
                st.write("**Volume Strength:**", volume_analysis.get('strength', 'Normal'))
            
            with col2:
                st.write("**Price-Volume Correlation:**", volume_analysis.get('correlation', 'Neutral'))
                st.write("**Accumulation/Distribution:**", volume_analysis.get('accumulation', 'Neutral'))
    
    def _render_levels_tab(self, symbol, hist, indicators):
        """Render support/resistance levels"""
        
        # Support and Resistance Chart
        fig_levels = self._create_levels_chart(symbol, hist, indicators)
        if fig_levels:
            st.plotly_chart(fig_levels, use_container_width=True)
        
        # Key levels table
        st.subheader("🎯 Key Price Levels")
        
        levels_data = []
        
        # Support levels
        supports = indicators.get('support_levels', [])
        for i, level in enumerate(supports[:3]):
            levels_data.append({
                'Type': f'Support {i+1}',
                'Price': f'${level:.2f}',
                'Strength': self._calculate_level_strength(hist, level),
                'Distance': f'{((hist["Close"].iloc[-1] - level) / level * 100):+.1f}%'
            })
        
        # Resistance levels  
        resistances = indicators.get('resistance_levels', [])
        for i, level in enumerate(resistances[:3]):
            levels_data.append({
                'Type': f'Resistance {i+1}',
                'Price': f'${level:.2f}',
                'Strength': self._calculate_level_strength(hist, level),
                'Distance': f'{((level - hist["Close"].iloc[-1]) / hist["Close"].iloc[-1] * 100):+.1f}%'
            })
        
        if levels_data:
            df_levels = pd.DataFrame(levels_data)
            st.dataframe(df_levels, use_container_width=True, hide_index=True)
        
        # Fibonacci levels
        st.subheader("📐 Fibonacci Retracement Levels")
        fib_levels = indicators.get('fibonacci_levels', {})
        
        if fib_levels:
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**23.6%:**", f"${fib_levels.get('23.6', 0):.2f}")
                st.write("**38.2%:**", f"${fib_levels.get('38.2', 0):.2f}")
                st.write("**50.0%:**", f"${fib_levels.get('50.0', 0):.2f}")
            
            with col2:
                st.write("**61.8%:**", f"${fib_levels.get('61.8', 0):.2f}")
                st.write("**78.6%:**", f"${fib_levels.get('78.6', 0):.2f}")
    
    def _calculate_all_indicators(self, symbol, hist=None):
        """Calculate all technical indicators for a symbol"""
        
        try:
            if hist is None:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='6mo')
            
            if hist.empty:
                return {}
            
            indicators = {}
            
            # Basic indicators
            indicators['rsi'] = self._calculate_rsi(hist['Close'])
            indicators['macd_signal'] = self._calculate_macd_signal(hist['Close'])
            indicators['bollinger_signal'] = self._calculate_bollinger_signal(hist['Close'])
            indicators['stochastic'] = self._calculate_stochastic(hist)
            
            # Support and resistance
            indicators['support_levels'] = self._find_support_levels(hist)
            indicators['resistance_levels'] = self._find_resistance_levels(hist)
            indicators['support_level'] = indicators['support_levels'][0] if indicators['support_levels'] else 0
            indicators['resistance_level'] = indicators['resistance_levels'][0] if indicators['resistance_levels'] else 0
            
            # Fibonacci levels
            indicators['fibonacci_levels'] = self._calculate_fibonacci_levels(hist)
            
            # Pattern recognition
            indicators['patterns'] = self._detect_patterns(hist)
            indicators['volume_patterns'] = self._analyze_volume_patterns(hist)
            
            # Overall signals
            indicators['trend_signal'] = self._determine_trend_signal(indicators)
            indicators['momentum_signal'] = self._determine_momentum_signal(indicators)
            indicators['volatility_signal'] = self._determine_volatility_signal(hist)
            indicators['technical_score'] = self._calculate_technical_score(indicators)
            
            return indicators
            
        except Exception as e:
            return {}
    
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
    
    def _calculate_macd_signal(self, prices):
        """Calculate MACD signal"""
        try:
            ema_12 = prices.ewm(span=12).mean()
            ema_26 = prices.ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal = macd.ewm(span=9).mean()
            
            if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
                return "Bullish Crossover"
            elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
                return "Bearish Crossover"
            elif macd.iloc[-1] > signal.iloc[-1]:
                return "Bullish"
            else:
                return "Bearish"
        except:
            return "Neutral"
    
    def _calculate_bollinger_signal(self, prices, window=20):
        """Calculate Bollinger Bands signal"""
        try:
            sma = prices.rolling(window).mean()
            std = prices.rolling(window).std()
            upper = sma + (std * 2)
            lower = sma - (std * 2)
            
            current_price = prices.iloc[-1]
            
            if current_price > upper.iloc[-1]:
                return "Overbought"
            elif current_price < lower.iloc[-1]:
                return "Oversold"
            elif current_price > sma.iloc[-1]:
                return "Above Middle"
            else:
                return "Below Middle"
        except:
            return "Neutral"
    
    def _calculate_stochastic(self, hist, k_window=14, d_window=3):
        """Calculate Stochastic oscillator"""
        try:
            low_min = hist['Low'].rolling(window=k_window).min()
            high_max = hist['High'].rolling(window=k_window).max()
            k_percent = 100 * ((hist['Close'] - low_min) / (high_max - low_min))
            return k_percent.iloc[-1] if not pd.isna(k_percent.iloc[-1]) else 50.0
        except:
            return 50.0
    
    def _find_support_levels(self, hist):
        """Find support levels using pivot lows"""
        try:
            lows = hist['Low'].values
            support_levels = []
            
            for i in range(2, len(lows) - 2):
                if lows[i] < lows[i-1] and lows[i] < lows[i+1] and lows[i] < lows[i-2] and lows[i] < lows[i+2]:
                    support_levels.append(lows[i])
            
            # Remove levels too close to each other and sort
            support_levels = sorted(set([round(level, 2) for level in support_levels]))
            current_price = hist['Close'].iloc[-1]
            
            # Only return levels below current price
            support_levels = [level for level in support_levels if level < current_price * 0.95]
            
            return sorted(support_levels, reverse=True)[:5]  # Top 5 closest supports
        except:
            return []
    
    def _find_resistance_levels(self, hist):
        """Find resistance levels using pivot highs"""
        try:
            highs = hist['High'].values
            resistance_levels = []
            
            for i in range(2, len(highs) - 2):
                if highs[i] > highs[i-1] and highs[i] > highs[i+1] and highs[i] > highs[i-2] and highs[i] > highs[i+2]:
                    resistance_levels.append(highs[i])
            
            # Remove levels too close to each other and sort
            resistance_levels = sorted(set([round(level, 2) for level in resistance_levels]))
            current_price = hist['Close'].iloc[-1]
            
            # Only return levels above current price
            resistance_levels = [level for level in resistance_levels if level > current_price * 1.05]
            
            return sorted(resistance_levels)[:5]  # Top 5 closest resistances
        except:
            return []
    
    def _calculate_fibonacci_levels(self, hist):
        """Calculate Fibonacci retracement levels"""
        try:
            # Find recent high and low
            recent_data = hist.tail(50)  # Last 50 days
            high = recent_data['High'].max()
            low = recent_data['Low'].min()
            
            diff = high - low
            
            return {
                '0.0': high,
                '23.6': high - (diff * 0.236),
                '38.2': high - (diff * 0.382),
                '50.0': high - (diff * 0.5),
                '61.8': high - (diff * 0.618),
                '78.6': high - (diff * 0.786),
                '100.0': low
            }
        except:
            return {}
    
    def _detect_patterns(self, hist):
        """Detect basic chart patterns"""
        try:
            patterns = []
            
            # Simple pattern detection
            recent_prices = hist['Close'].tail(10).values
            
            # Ascending pattern
            if len(recent_prices) >= 5:
                if recent_prices[-1] > recent_prices[-5] and recent_prices[-2] > recent_prices[-4]:
                    patterns.append({
                        'name': 'Ascending Trend',
                        'type': 'bullish',
                        'description': 'Price making higher highs and higher lows'
                    })
                
                # Descending pattern
                elif recent_prices[-1] < recent_prices[-5] and recent_prices[-2] < recent_prices[-4]:
                    patterns.append({
                        'name': 'Descending Trend', 
                        'type': 'bearish',
                        'description': 'Price making lower highs and lower lows'
                    })
            
            # Consolidation
            price_range = (hist['High'].tail(20).max() - hist['Low'].tail(20).min()) / hist['Close'].iloc[-1]
            if price_range < 0.1:  # Less than 10% range
                patterns.append({
                    'name': 'Consolidation',
                    'type': 'neutral',
                    'description': 'Price trading in tight range - potential breakout setup'
                })
            
            return patterns
        except:
            return []
    
    def _analyze_volume_patterns(self, hist):
        """Analyze volume patterns"""
        try:
            if 'Volume' not in hist.columns:
                return {}
            
            volumes = hist['Volume'].tail(20)
            prices = hist['Close'].tail(20)
            
            # Volume trend
            vol_ma = volumes.rolling(10).mean()
            if volumes.iloc[-1] > vol_ma.iloc[-1] * 1.5:
                vol_trend = "Increasing"
                vol_strength = "Strong"
            elif volumes.iloc[-1] > vol_ma.iloc[-1]:
                vol_trend = "Increasing"
                vol_strength = "Moderate"
            else:
                vol_trend = "Decreasing"
                vol_strength = "Weak"
            
            # Price-volume correlation
            price_change = prices.pct_change()
            vol_change = volumes.pct_change()
            correlation = np.corrcoef(price_change.dropna(), vol_change.dropna())[0, 1]
            
            if correlation > 0.5:
                pv_correlation = "Strong Positive"
            elif correlation > 0.2:
                pv_correlation = "Moderate Positive"
            elif correlation < -0.5:
                pv_correlation = "Strong Negative"
            elif correlation < -0.2:
                pv_correlation = "Moderate Negative"
            else:
                pv_correlation = "Weak"
            
            # Accumulation/Distribution
            if vol_trend == "Increasing" and prices.iloc[-1] > prices.iloc[-5]:
                accumulation = "Accumulation"
            elif vol_trend == "Increasing" and prices.iloc[-1] < prices.iloc[-5]:
                accumulation = "Distribution"
            else:
                accumulation = "Neutral"
            
            return {
                'trend': vol_trend,
                'strength': vol_strength,
                'correlation': pv_correlation,
                'accumulation': accumulation
            }
        except:
            return {}
    
    def _determine_trend_signal(self, indicators):
        """Determine overall trend signal"""
        bullish_signals = 0
        bearish_signals = 0
        
        # MACD
        if 'Bullish' in indicators.get('macd_signal', ''):
            bullish_signals += 1
        elif 'Bearish' in indicators.get('macd_signal', ''):
            bearish_signals += 1
        
        # RSI
        rsi = indicators.get('rsi', 50)
        if rsi > 50:
            bullish_signals += 1
        else:
            bearish_signals += 1
        
        # Bollinger Bands
        bb_signal = indicators.get('bollinger_signal', '')
        if 'Above' in bb_signal:
            bullish_signals += 1
        elif 'Below' in bb_signal or 'Oversold' in bb_signal:
            bearish_signals += 1
        
        if bullish_signals > bearish_signals:
            return "Bullish"
        elif bearish_signals > bullish_signals:
            return "Bearish"
        else:
            return "Neutral"
    
    def _determine_momentum_signal(self, indicators):
        """Determine momentum signal"""
        rsi = indicators.get('rsi', 50)
        stoch = indicators.get('stochastic', 50)
        
        if rsi > 60 and stoch > 60:
            return "Strong"
        elif rsi > 50 and stoch > 50:
            return "Moderate"
        elif rsi < 40 and stoch < 40:
            return "Weak"
        else:
            return "Mixed"
    
    def _determine_volatility_signal(self, hist):
        """Determine volatility signal"""
        try:
            returns = hist['Close'].pct_change().dropna()
            volatility = returns.std() * np.sqrt(252)  # Annualized
            
            if volatility > 0.6:
                return "High"
            elif volatility > 0.3:
                return "Moderate"
            else:
                return "Low"
        except:
            return "Normal"
    
    def _calculate_technical_score(self, indicators):
        """Calculate overall technical score (-5 to +5)"""
        score = 0
        
        # Trend component
        trend = indicators.get('trend_signal', 'Neutral')
        if trend == 'Bullish':
            score += 2
        elif trend == 'Bearish':
            score -= 2
        
        # Momentum component
        momentum = indicators.get('momentum_signal', 'Mixed')
        if momentum == 'Strong':
            score += 1
        elif momentum == 'Weak':
            score -= 1
        
        # RSI component
        rsi = indicators.get('rsi', 50)
        if rsi < 30:
            score += 1  # Oversold bounce potential
        elif rsi > 70:
            score -= 1  # Overbought correction potential
        
        # MACD component
        macd = indicators.get('macd_signal', 'Neutral')
        if 'Bullish Crossover' in macd:
            score += 1
        elif 'Bearish Crossover' in macd:
            score -= 1
        
        return max(-5, min(5, score))
    
    def _calculate_level_strength(self, hist, level):
        """Calculate strength of support/resistance level"""
        try:
            # Count how many times price has tested this level
            touches = 0
            tolerance = level * 0.02  # 2% tolerance
            
            for price in hist['Low'].values:
                if abs(price - level) <= tolerance:
                    touches += 1
            
            for price in hist['High'].values:
                if abs(price - level) <= tolerance:
                    touches += 1
            
            if touches >= 3:
                return "Strong"
            elif touches >= 2:
                return "Moderate"
            else:
                return "Weak"
        except:
            return "Unknown"
    
    def _create_macd_chart(self, symbol, hist):
        """Create MACD chart"""
        try:
            ema_12 = hist['Close'].ewm(span=12).mean()
            ema_26 = hist['Close'].ewm(span=26).mean()
            macd = ema_12 - ema_26
            signal = macd.ewm(span=9).mean()
            histogram = macd - signal
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                              vertical_spacing=0.02,
                              subplot_titles=(f'{symbol} MACD', 'Histogram'))
            
            # MACD and Signal lines
            fig.add_trace(go.Scatter(x=hist.index, y=macd, name='MACD', 
                                   line=dict(color='blue')), row=1, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=signal, name='Signal', 
                                   line=dict(color='red')), row=1, col=1)
            
            # Histogram
            colors = ['green' if h >= 0 else 'red' for h in histogram]
            fig.add_trace(go.Bar(x=hist.index, y=histogram, name='Histogram',
                               marker_color=colors), row=2, col=1)
            
            fig.update_layout(template='plotly_dark', height=400, showlegend=True,
                            margin=dict(l=0, r=0, t=40, b=0))
            
            return fig
        except:
            return None
    
    def _create_oscillators_chart(self, symbol, hist):
        """Create RSI and Stochastic chart"""
        try:
            # Calculate RSI
            delta = hist['Close'].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            
            # Calculate Stochastic
            low_min = hist['Low'].rolling(window=14).min()
            high_max = hist['High'].rolling(window=14).max()
            k_percent = 100 * ((hist['Close'] - low_min) / (high_max - low_min))
            d_percent = k_percent.rolling(window=3).mean()
            
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                              vertical_spacing=0.02,
                              subplot_titles=(f'{symbol} RSI', 'Stochastic'))
            
            # RSI
            fig.add_trace(go.Scatter(x=hist.index, y=rsi, name='RSI', 
                                   line=dict(color='purple')), row=1, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)
            
            # Stochastic
            fig.add_trace(go.Scatter(x=hist.index, y=k_percent, name='%K',
                                   line=dict(color='blue')), row=2, col=1)
            fig.add_trace(go.Scatter(x=hist.index, y=d_percent, name='%D',
                                   line=dict(color='orange')), row=2, col=1)
            fig.add_hline(y=80, line_dash="dash", line_color="red", row=2, col=1)
            fig.add_hline(y=20, line_dash="dash", line_color="green", row=2, col=1)
            
            fig.update_layout(template='plotly_dark', height=400, showlegend=True,
                            margin=dict(l=0, r=0, t=40, b=0))
            
            return fig
        except:
            return None
    
    def _create_levels_chart(self, symbol, hist, indicators):
        """Create support/resistance levels chart"""
        try:
            fig = go.Figure()
            
            # Candlestick chart
            fig.add_trace(go.Candlestick(
                x=hist.index,
                open=hist['Open'],
                high=hist['High'], 
                low=hist['Low'],
                close=hist['Close'],
                name=symbol
            ))
            
            # Support levels
            for level in indicators.get('support_levels', [])[:3]:
                fig.add_hline(y=level, line_dash="dot", line_color="green",
                            annotation_text=f"Support ${level:.2f}")
            
            # Resistance levels
            for level in indicators.get('resistance_levels', [])[:3]:
                fig.add_hline(y=level, line_dash="dot", line_color="red",
                            annotation_text=f"Resistance ${level:.2f}")
            
            # Fibonacci levels
            fib_levels = indicators.get('fibonacci_levels', {})
            for level_name, level_value in fib_levels.items():
                if level_name in ['38.2', '50.0', '61.8']:
                    fig.add_hline(y=level_value, line_dash="dash", line_color="yellow",
                                opacity=0.5, annotation_text=f"Fib {level_name}%")
            
            fig.update_layout(
                title=f'{symbol} Support & Resistance Levels',
                template='plotly_dark',
                height=500,
                showlegend=False,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            fig.update_xaxes(rangeslider_visible=False)
            
            return fig
        except:
            return None

    def get_technical_data(self, selected_stocks):
        """Get technical analysis data for integration with weekly outlook"""
        technical_data = {}
        
        for symbol in selected_stocks:
            try:
                indicators = self._calculate_all_indicators(symbol)
                technical_data[symbol] = {
                    'trend_signal': indicators.get('trend_signal', 'Neutral'),
                    'momentum_signal': indicators.get('momentum_signal', 'Mixed'),
                    'technical_score': indicators.get('technical_score', 0),
                    'rsi': indicators.get('rsi', 50),
                    'support_level': indicators.get('support_level', 0),
                    'resistance_level': indicators.get('resistance_level', 0),
                    'volatility_signal': indicators.get('volatility_signal', 'Normal')
                }
            except:
                technical_data[symbol] = {
                    'trend_signal': 'Neutral',
                    'momentum_signal': 'Mixed', 
                    'technical_score': 0,
                    'rsi': 50,
                    'support_level': 0,
                    'resistance_level': 0,
                    'volatility_signal': 'Normal'
                }
        
        return technical_data