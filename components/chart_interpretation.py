import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class ChartInterpretation:
    """Professional chart interpretation and technical analysis with plain-English explanations"""
    
    def __init__(self):
        self.support_color = "#00ff88"
        self.resistance_color = "#ff4444"
        self.bullish_color = "#00ff88"
        self.bearish_color = "#ff4444"
        
    def render(self, symbol, stock_data, data_fetcher):
        """Render comprehensive chart interpretation for a stock"""
        
        st.subheader(f"📊 {symbol} - Professional Chart Analysis")
        
        # Get extended data for better analysis
        extended_data = data_fetcher.get_stock_data([symbol], period='3M')
        
        if extended_data.empty or symbol not in extended_data.columns:
            st.warning(f"No data available for {symbol}")
            return
        
        prices = extended_data[symbol].dropna()
        
        # Calculate technical indicators
        analysis = self._analyze_technical_setup(prices)
        
        # Render three-column layout
        col1, col2 = st.columns([2, 1])
        
        with col1:
            # Main chart with annotations
            self._render_annotated_chart(symbol, prices, analysis)
        
        with col2:
            # Interpretation panel
            self._render_interpretation_panel(symbol, analysis)
        
        # Detailed analysis sections
        self._render_detailed_analysis(symbol, prices, analysis)
    
    def _analyze_technical_setup(self, prices):
        """Comprehensive technical analysis"""
        
        current_price = prices.iloc[-1]
        
        # Volatility analysis (ATR-based)
        high_low_range = self._calculate_atr(prices, period=14)
        volatility_levels = self._calculate_volatility_zones(prices, high_low_range)
        
        # Momentum analysis
        momentum = self._calculate_momentum(prices)
        
        # Volume pattern (using price changes as proxy)
        volume_pattern = self._analyze_volume_pattern(prices)
        
        # Support/Resistance
        support_resistance = self._find_support_resistance(prices)
        
        # Trend analysis
        trend = self._analyze_trend(prices)
        
        # Breakout detection
        breakouts = self._detect_breakouts(prices, volatility_levels)
        
        # Price action signals
        signals = self._generate_signals(prices, momentum, trend)
        
        return {
            'current_price': current_price,
            'volatility_levels': volatility_levels,
            'momentum': momentum,
            'volume_pattern': volume_pattern,
            'support_resistance': support_resistance,
            'trend': trend,
            'breakouts': breakouts,
            'signals': signals,
            'atr': high_low_range
        }
    
    def _calculate_atr(self, prices, period=14):
        """Calculate Average True Range for volatility"""
        # Simplified ATR using rolling std as proxy
        returns = prices.pct_change()
        atr = returns.rolling(window=period).std() * prices
        return atr.iloc[-1] if not atr.empty else 0
    
    def _calculate_volatility_zones(self, prices, atr):
        """Calculate volatility-based support/resistance zones"""
        current = prices.iloc[-1]
        
        return {
            'extreme_high': current + (2 * atr),
            'high': current + atr,
            'mid': current,
            'low': current - atr,
            'extreme_low': current - (2 * atr)
        }
    
    def _calculate_momentum(self, prices):
        """Calculate momentum indicators"""
        # RSI-like momentum
        changes = prices.diff()
        gains = changes.where(changes > 0, 0).rolling(window=14).mean()
        losses = -changes.where(changes < 0, 0).rolling(window=14).mean()
        
        rs = gains / losses.replace(0, 1)
        rsi = 100 - (100 / (1 + rs))
        
        current_rsi = rsi.iloc[-1] if not rsi.empty else 50
        
        # MACD-like momentum
        ema_12 = prices.ewm(span=12).mean()
        ema_26 = prices.ewm(span=26).mean()
        macd = ema_12 - ema_26
        signal_line = macd.ewm(span=9).mean()
        
        return {
            'rsi': current_rsi,
            'macd': macd.iloc[-1] if not macd.empty else 0,
            'macd_signal': signal_line.iloc[-1] if not signal_line.empty else 0,
            'strength': 'Strong Bullish' if current_rsi > 60 else 'Bullish' if current_rsi > 50 else 'Bearish' if current_rsi > 40 else 'Strong Bearish'
        }
    
    def _analyze_volume_pattern(self, prices):
        """Analyze price action as volume proxy"""
        # Use price volatility and range as volume indicator
        recent_changes = prices.pct_change().tail(20)
        
        positive_days = (recent_changes > 0).sum()
        negative_days = (recent_changes < 0).sum()
        
        avg_up_move = recent_changes[recent_changes > 0].mean() * 100 if (recent_changes > 0).any() else 0
        avg_down_move = abs(recent_changes[recent_changes < 0].mean() * 100) if (recent_changes < 0).any() else 0
        
        # Determine pattern
        if positive_days > negative_days * 1.5:
            pattern = 'Accumulation'
            color = 'green'
        elif negative_days > positive_days * 1.5:
            pattern = 'Distribution'
            color = 'red'
        else:
            pattern = 'Consolidation'
            color = 'yellow'
        
        return {
            'pattern': pattern,
            'color': color,
            'positive_days': positive_days,
            'negative_days': negative_days,
            'avg_up_move': avg_up_move,
            'avg_down_move': avg_down_move
        }
    
    def _find_support_resistance(self, prices):
        """Find key support and resistance levels"""
        # Recent highs and lows
        recent_high = prices.tail(20).max()
        recent_low = prices.tail(20).min()
        
        # Pivot points
        pivot = (recent_high + recent_low + prices.iloc[-1]) / 3
        
        return {
            'resistance_1': recent_high,
            'resistance_2': pivot + (recent_high - recent_low),
            'support_1': recent_low,
            'support_2': pivot - (recent_high - recent_low),
            'pivot': pivot
        }
    
    def _analyze_trend(self, prices):
        """Analyze current trend"""
        # Multiple timeframe moving averages
        sma_20 = prices.rolling(window=20).mean().iloc[-1]
        sma_50 = prices.rolling(window=50).mean().iloc[-1]
        sma_100 = prices.rolling(window=min(100, len(prices))).mean().iloc[-1]
        
        current = prices.iloc[-1]
        
        # Trend determination
        if current > sma_20 > sma_50:
            trend = 'Strong Uptrend'
            emoji = '🚀'
        elif current > sma_20:
            trend = 'Uptrend'
            emoji = '📈'
        elif current < sma_20 < sma_50:
            trend = 'Strong Downtrend'
            emoji = '📉'
        elif current < sma_20:
            trend = 'Downtrend'
            emoji = '⬇️'
        else:
            trend = 'Sideways'
            emoji = '➡️'
        
        return {
            'direction': trend,
            'emoji': emoji,
            'sma_20': sma_20,
            'sma_50': sma_50,
            'sma_100': sma_100
        }
    
    def _detect_breakouts(self, prices, vol_levels):
        """Detect breakouts from volatility zones"""
        current = prices.iloc[-1]
        prev_high = prices.tail(10).max()
        prev_low = prices.tail(10).min()
        
        breakouts = []
        
        if current > prev_high * 1.02:
            breakouts.append({
                'type': 'Upside Breakout',
                'level': prev_high,
                'strength': 'Strong' if current > prev_high * 1.05 else 'Moderate'
            })
        
        if current < prev_low * 0.98:
            breakouts.append({
                'type': 'Downside Break',
                'level': prev_low,
                'strength': 'Strong' if current < prev_low * 0.95 else 'Moderate'
            })
        
        # Check volatility zones
        if current > vol_levels['high']:
            breakouts.append({
                'type': 'Breached Volatility High',
                'level': vol_levels['high'],
                'strength': 'Extreme' if current > vol_levels['extreme_high'] else 'Strong'
            })
        
        return breakouts
    
    def _generate_signals(self, prices, momentum, trend):
        """Generate trading signals"""
        signals = []
        
        # RSI signals
        if momentum['rsi'] > 70:
            signals.append({
                'type': 'Overbought',
                'indicator': 'RSI',
                'action': 'Consider taking profits or selling calls',
                'strength': 'Strong' if momentum['rsi'] > 80 else 'Moderate'
            })
        elif momentum['rsi'] < 30:
            signals.append({
                'type': 'Oversold',
                'indicator': 'RSI',
                'action': 'Potential buying opportunity or protective puts',
                'strength': 'Strong' if momentum['rsi'] < 20 else 'Moderate'
            })
        
        # Trend signals
        if 'Strong Uptrend' in trend['direction']:
            signals.append({
                'type': 'Strong Trend',
                'indicator': 'Moving Averages',
                'action': 'Hold long positions, sell OTM calls for income',
                'strength': 'Strong'
            })
        
        return signals
    
    def _render_annotated_chart(self, symbol, prices, analysis):
        """Render chart with technical annotations"""
        
        fig = go.Figure()
        
        # Price line
        fig.add_trace(go.Scatter(
            x=prices.index,
            y=prices.values,
            name='Price',
            line=dict(color='#2196F3', width=2)
        ))
        
        # Support/Resistance levels
        sr = analysis['support_resistance']
        
        fig.add_hline(y=sr['resistance_1'], line_dash="dash", line_color="#ff4444",
                     annotation_text="Resistance", annotation_position="right")
        fig.add_hline(y=sr['support_1'], line_dash="dash", line_color="#00ff88",
                     annotation_text="Support", annotation_position="right")
        
        # Volatility zones
        vol = analysis['volatility_levels']
        current = analysis['current_price']
        
        fig.add_hline(y=vol['high'], line_dash="dot", line_color="orange",
                     annotation_text="Vol High", annotation_position="left")
        fig.add_hline(y=vol['low'], line_dash="dot", line_color="orange",
                     annotation_text="Vol Low", annotation_position="left")
        
        # Trend indicators (SMAs)
        sma_20 = prices.rolling(window=20).mean()
        sma_50 = prices.rolling(window=50).mean()
        
        fig.add_trace(go.Scatter(
            x=sma_20.index,
            y=sma_20.values,
            name='SMA 20',
            line=dict(color='yellow', width=1, dash='dot')
        ))
        
        fig.add_trace(go.Scatter(
            x=sma_50.index,
            y=sma_50.values,
            name='SMA 50',
            line=dict(color='purple', width=1, dash='dot')
        ))
        
        # Mark breakouts
        for breakout in analysis['breakouts']:
            fig.add_annotation(
                x=prices.index[-1],
                y=current,
                text=f"🔥 {breakout['type']}",
                showarrow=True,
                arrowhead=2,
                arrowcolor="red" if "Downside" in breakout['type'] else "green"
            )
        
        fig.update_layout(
            title=f"{symbol} Technical Chart - {analysis['trend']['direction']} {analysis['trend']['emoji']}",
            xaxis_title="Date",
            yaxis_title="Price ($)",
            template="plotly_dark",
            height=500,
            showlegend=True,
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
    
    def _render_interpretation_panel(self, symbol, analysis):
        """Render plain-English interpretation"""
        
        st.markdown("### 🎯 What This Means")
        
        # Overall signal
        trend = analysis['trend']['direction']
        momentum_strength = analysis['momentum']['strength']
        vol_pattern = analysis['volume_pattern']['pattern']
        
        if 'Uptrend' in trend and 'Bullish' in momentum_strength:
            signal = "🟢 BULLISH"
            color = "green"
        elif 'Downtrend' in trend and 'Bearish' in momentum_strength:
            signal = "🔴 BEARISH"
            color = "red"
        else:
            signal = "🟡 NEUTRAL"
            color = "orange"
        
        st.markdown(f"**Overall Signal:** :{color}[{signal}]")
        
        # Key insights
        st.markdown("**Key Insights:**")
        
        insights = []
        
        # Trend insight
        if 'Strong' in trend:
            insights.append(f"• **{analysis['trend']['emoji']} Strong momentum** in {trend.lower()} direction")
        else:
            insights.append(f"• **{analysis['trend']['emoji']} Trend:** {trend}")
        
        # Volume insight
        vol_emoji = "🟢" if vol_pattern == "Accumulation" else "🔴" if vol_pattern == "Distribution" else "🟡"
        insights.append(f"• **{vol_emoji} Volume:** {vol_pattern} pattern detected")
        
        # Momentum insight
        rsi = analysis['momentum']['rsi']
        if rsi > 70:
            insights.append(f"• **⚠️ Overbought:** RSI at {rsi:.0f} - Consider profit-taking")
        elif rsi < 30:
            insights.append(f"• **💡 Oversold:** RSI at {rsi:.0f} - Potential entry point")
        else:
            insights.append(f"• **Momentum:** {momentum_strength} (RSI: {rsi:.0f})")
        
        # Breakout insights
        if analysis['breakouts']:
            for breakout in analysis['breakouts']:
                emoji = "🚀" if "Upside" in breakout['type'] else "⚠️"
                insights.append(f"• **{emoji} {breakout['type']}** - {breakout['strength']} signal")
        
        for insight in insights:
            st.markdown(insight)
        
        st.divider()
        
        # Trading implications
        st.markdown("**📊 For Your Options Strategy:**")
        
        if 'Uptrend' in trend and 'Accumulation' in vol_pattern:
            st.success("""
            **Covered Call Strategy:**
            - Sell calls 10-15% OTM
            - Strong uptrend may cap your gains
            - Consider higher strikes or rolling
            """)
        elif 'Downtrend' in trend:
            st.warning("""
            **Protection Strategy:**
            - Consider protective puts
            - Or wait for reversal signals
            - Avoid selling calls until stabilization
            """)
        else:
            st.info("""
            **Neutral Strategy:**
            - Sell ATM/near-the-money calls
            - Higher premiums in range-bound market
            - Monitor for breakout signals
            """)
    
    def _render_detailed_analysis(self, symbol, prices, analysis):
        """Render detailed technical breakdown"""
        
        with st.expander("📈 Detailed Technical Breakdown", expanded=False):
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**Support & Resistance**")
                sr = analysis['support_resistance']
                st.metric("Resistance", f"${sr['resistance_1']:.2f}")
                st.metric("Support", f"${sr['support_1']:.2f}")
                st.metric("Pivot", f"${sr['pivot']:.2f}")
            
            with col2:
                st.markdown("**Momentum Indicators**")
                mom = analysis['momentum']
                st.metric("RSI", f"{mom['rsi']:.0f}")
                st.metric("MACD", f"{mom['macd']:.3f}")
                st.metric("Strength", mom['strength'])
            
            with col3:
                st.markdown("**Volatility Analysis**")
                vol = analysis['volatility_levels']
                current = analysis['current_price']
                st.metric("Current", f"${current:.2f}")
                st.metric("ATR", f"${analysis['atr']:.2f}")
                st.metric("Vol High", f"${vol['high']:.2f}")
            
            # Volume pattern details
            st.markdown("**📊 Volume Pattern Analysis**")
            vp = analysis['volume_pattern']
            
            vol_col1, vol_col2 = st.columns(2)
            with vol_col1:
                st.metric("Pattern", vp['pattern'])
                st.metric("Up Days", vp['positive_days'])
            with vol_col2:
                st.metric("Avg Up Move", f"{vp['avg_up_move']:.1f}%")
                st.metric("Down Days", vp['negative_days'])
            
            # Signals
            if analysis['signals']:
                st.markdown("**🎯 Active Signals**")
                for signal in analysis['signals']:
                    st.markdown(f"""
                    **{signal['type']}** ({signal['indicator']})  
                    → {signal['action']}  
                    *Strength: {signal['strength']}*
                    """)


def render_all_stocks_interpretation(selected_stocks, data_fetcher):
    """Render chart interpretation for all selected stocks"""
    
    st.title("📊 Professional Chart Interpretation")
    st.markdown("### Technical Analysis with Plain-English Explanations")
    
    interpreter = ChartInterpretation()
    
    # Get data for all stocks
    stock_data = data_fetcher.get_stock_data(selected_stocks, period='3M')
    
    for symbol in selected_stocks:
        with st.expander(f"📈 {symbol} Analysis", expanded=False):
            interpreter.render(symbol, stock_data, data_fetcher)
            st.divider()