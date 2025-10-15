import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import plotly.graph_objects as go
from plotly.subplots import make_subplots

class VolatilityHoleChart:
    """
    Volatility Hole Indicator - Identifies periods of volatility contraction (holes) 
    followed by expansion (breakouts). Based on Danny Cheng's technical analysis approach.
    """
    
    def __init__(self):
        self.hole_color = "#FFD700"  # Gold for holes
        self.breakout_up_color = "#00FF88"
        self.breakout_down_color = "#FF4444"
        
    def render(self, symbol, data_fetcher):
        """Render volatility hole chart for a stock"""
        
        st.subheader(f"🕳️ {symbol} - Volatility Hole Analysis")
        st.markdown("*Danny Cheng's favorite indicator: spots low volatility zones before major moves*")
        
        # Get extended data
        prices_df = data_fetcher.get_stock_data([symbol], period='6M')
        
        if prices_df.empty or symbol not in prices_df.columns:
            st.warning(f"No data available for {symbol}")
            return
        
        prices = prices_df[symbol].dropna()
        
        # Calculate volatility metrics
        volatility_data = self._calculate_volatility_metrics(prices)
        
        # Identify volatility holes and breakouts
        holes = self._identify_volatility_holes(prices, volatility_data)
        
        # Create the chart
        self._render_volatility_hole_chart(symbol, prices, volatility_data, holes)
        
        # Render interpretation
        self._render_interpretation(symbol, prices, volatility_data, holes)
        
    def _calculate_volatility_metrics(self, prices):
        """Calculate comprehensive volatility metrics"""
        
        # 1. Bollinger Band Width (primary volatility measure)
        sma_20 = prices.rolling(window=20).mean()
        std_20 = prices.rolling(window=20).std()
        
        upper_bb = sma_20 + (2 * std_20)
        lower_bb = sma_20 - (2 * std_20)
        bb_width = ((upper_bb - lower_bb) / sma_20) * 100
        
        # 2. ATR (Average True Range)
        high = prices.rolling(window=2).max()
        low = prices.rolling(window=2).min()
        tr = high - low
        atr = tr.rolling(window=14).mean()
        atr_pct = (atr / prices) * 100
        
        # 3. Historical Volatility (standard deviation of returns)
        returns = prices.pct_change()
        hist_vol = returns.rolling(window=20).std() * np.sqrt(252) * 100
        
        # 4. Normalized volatility score (0-100)
        vol_score = bb_width.rolling(window=50).apply(
            lambda x: (x.iloc[-1] - x.min()) / (x.max() - x.min()) * 100 if x.max() > x.min() else 50
        )
        
        return {
            'bb_width': bb_width,
            'upper_bb': upper_bb,
            'lower_bb': lower_bb,
            'sma_20': sma_20,
            'atr': atr,
            'atr_pct': atr_pct,
            'hist_vol': hist_vol,
            'vol_score': vol_score
        }
    
    def _identify_volatility_holes(self, prices, vol_data):
        """
        Identify volatility holes (contraction zones) and breakouts
        
        Volatility Hole = When volatility contracts below 30th percentile
        Breakout = When price moves beyond BB after hole formation
        """
        
        bb_width = vol_data['bb_width']
        vol_score = vol_data['vol_score']
        
        holes = []
        in_hole = False
        hole_start = None
        hole_low_vol = None
        
        for i in range(20, len(prices)):
            current_vol_score = vol_score.iloc[i] if not pd.isna(vol_score.iloc[i]) else 50
            current_bb_width = bb_width.iloc[i] if not pd.isna(bb_width.iloc[i]) else 0
            
            # Hole formation: volatility score drops below 25 (bottom quartile)
            if current_vol_score < 25 and not in_hole:
                in_hole = True
                hole_start = i
                hole_low_vol = current_bb_width
            
            # Hole breakout: volatility expands above 60 after being in hole
            elif current_vol_score > 60 and in_hole:
                hole_end = i
                
                # Determine breakout direction
                price_change = (prices.iloc[hole_end] - prices.iloc[hole_start]) / prices.iloc[hole_start] * 100
                
                # Check if price breached BB
                breached_upper = prices.iloc[hole_end] > vol_data['upper_bb'].iloc[hole_end]
                breached_lower = prices.iloc[hole_end] < vol_data['lower_bb'].iloc[hole_end]
                
                breakout_type = None
                if breached_upper:
                    breakout_type = "Upside Breakout"
                elif breached_lower:
                    breakout_type = "Downside Break"
                elif price_change > 5:
                    breakout_type = "Upside Expansion"
                elif price_change < -5:
                    breakout_type = "Downside Expansion"
                else:
                    breakout_type = "Consolidation End"
                
                holes.append({
                    'start_idx': hole_start,
                    'end_idx': hole_end,
                    'start_date': prices.index[hole_start],
                    'end_date': prices.index[hole_end],
                    'start_price': prices.iloc[hole_start],
                    'end_price': prices.iloc[hole_end],
                    'price_change_pct': price_change,
                    'min_volatility': hole_low_vol,
                    'breakout_type': breakout_type,
                    'breached_upper': breached_upper,
                    'breached_lower': breached_lower
                })
                
                in_hole = False
                hole_start = None
        
        # Check if currently in a hole
        if in_hole and hole_start is not None:
            holes.append({
                'start_idx': hole_start,
                'end_idx': len(prices) - 1,
                'start_date': prices.index[hole_start],
                'end_date': prices.index[-1],
                'start_price': prices.iloc[hole_start],
                'end_price': prices.iloc[-1],
                'price_change_pct': (prices.iloc[-1] - prices.iloc[hole_start]) / prices.iloc[hole_start] * 100,
                'min_volatility': hole_low_vol,
                'breakout_type': "In Hole Now",
                'breached_upper': False,
                'breached_lower': False
            })
        
        return holes
    
    def _render_volatility_hole_chart(self, symbol, prices, vol_data, holes):
        """Render the volatility hole chart with annotations"""
        
        # Create subplots: price chart + volatility chart + momentum bars
        fig = make_subplots(
            rows=3, cols=1,
            row_heights=[0.5, 0.25, 0.25],
            subplot_titles=(f'{symbol} Price with Volatility Holes', 
                          'Volatility Score (Hole = Below 25)', 
                          'Momentum Bars'),
            vertical_spacing=0.08,
            shared_xaxes=True
        )
        
        # Row 1: Price with Bollinger Bands
        fig.add_trace(go.Scatter(
            x=prices.index,
            y=prices.values,
            name='Price',
            line=dict(color='#2196F3', width=2)
        ), row=1, col=1)
        
        # Bollinger Bands
        fig.add_trace(go.Scatter(
            x=vol_data['upper_bb'].index,
            y=vol_data['upper_bb'].values,
            name='Upper BB',
            line=dict(color='rgba(255,100,100,0.5)', width=1, dash='dot'),
            showlegend=False
        ), row=1, col=1)
        
        fig.add_trace(go.Scatter(
            x=vol_data['lower_bb'].index,
            y=vol_data['lower_bb'].values,
            name='Lower BB',
            line=dict(color='rgba(100,255,100,0.5)', width=1, dash='dot'),
            fill='tonexty',
            fillcolor='rgba(100,100,100,0.1)',
            showlegend=False
        ), row=1, col=1)
        
        # Mark volatility holes
        for hole in holes:
            hole_dates = prices.index[hole['start_idx']:hole['end_idx']+1]
            hole_prices = prices.iloc[hole['start_idx']:hole['end_idx']+1]
            
            # Highlight hole region
            fig.add_trace(go.Scatter(
                x=hole_dates,
                y=hole_prices,
                mode='lines',
                line=dict(color=self.hole_color, width=4),
                name='Volatility Hole',
                showlegend=False
            ), row=1, col=1)
            
            # Add circle annotation at breakout
            if hole['breakout_type'] != "In Hole Now":
                breakout_color = self.breakout_up_color if "Upside" in hole['breakout_type'] else self.breakout_down_color
                
                fig.add_annotation(
                    x=hole['end_date'],
                    y=hole['end_price'],
                    text=f"🔥 {hole['breakout_type']}",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor=breakout_color,
                    arrowsize=1.5,
                    arrowwidth=2,
                    ax=0,
                    ay=-40 if "Upside" in hole['breakout_type'] else 40,
                    font=dict(size=10, color=breakout_color),
                    row=1, col=1
                )
            else:
                # Current hole
                fig.add_annotation(
                    x=hole['end_date'],
                    y=hole['end_price'],
                    text="⚠️ In Volatility Hole",
                    showarrow=True,
                    arrowhead=2,
                    arrowcolor=self.hole_color,
                    font=dict(size=10, color=self.hole_color),
                    row=1, col=1
                )
        
        # Row 2: Volatility Score
        vol_score = vol_data['vol_score']
        
        # Color-code volatility: low = yellow (hole), high = red (expansion)
        colors = ['#FFD700' if v < 25 else '#FF4444' if v > 75 else '#888888' 
                 for v in vol_score.fillna(50)]
        
        fig.add_trace(go.Scatter(
            x=vol_score.index,
            y=vol_score.values,
            mode='lines',
            line=dict(color='white', width=1),
            fill='tozeroy',
            fillcolor='rgba(255,215,0,0.3)',
            name='Vol Score'
        ), row=2, col=1)
        
        # Add threshold lines
        fig.add_hline(y=25, line_dash="dash", line_color="yellow", 
                     annotation_text="Hole Zone", annotation_position="right", row=2, col=1)
        fig.add_hline(y=75, line_dash="dash", line_color="red",
                     annotation_text="Expansion", annotation_position="right", row=2, col=1)
        
        # Row 3: Momentum Bars (like volume but showing direction)
        returns = prices.pct_change() * 100
        momentum_colors = ['#00FF88' if r > 0 else '#FF4444' for r in returns]
        
        fig.add_trace(go.Bar(
            x=returns.index,
            y=abs(returns.values),
            marker_color=momentum_colors,
            name='Momentum',
            showlegend=False
        ), row=3, col=1)
        
        # Layout
        fig.update_layout(
            height=900,
            template="plotly_dark",
            hovermode='x unified',
            showlegend=True
        )
        
        fig.update_yaxes(title_text="Price ($)", row=1, col=1)
        fig.update_yaxes(title_text="Volatility Score", row=2, col=1)
        fig.update_yaxes(title_text="Momentum %", row=3, col=1)
        fig.update_xaxes(title_text="Date", row=3, col=1)
        
        st.plotly_chart(fig, width="stretch")
    
    def _render_interpretation(self, symbol, prices, vol_data, holes):
        """Render plain-English interpretation of volatility holes"""
        
        st.markdown("### 🎯 What This Chart Tells You")
        
        # Current status
        current_vol_score = vol_data['vol_score'].iloc[-1] if not pd.isna(vol_data['vol_score'].iloc[-1]) else 50
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if current_vol_score < 25:
                st.error("⚠️ **IN VOLATILITY HOLE**")
                st.markdown("Low volatility = Big move coming soon")
            elif current_vol_score > 75:
                st.success("🔥 **VOLATILITY EXPANDING**")
                st.markdown("High volatility = Active breakout")
            else:
                st.info("📊 **NORMAL VOLATILITY**")
                st.markdown("Moderate volatility = Watch for setup")
        
        with col2:
            st.metric("Current Volatility Score", f"{current_vol_score:.0f}/100")
            st.metric("Total Holes Found", len([h for h in holes if h['breakout_type'] != "In Hole Now"]))
        
        with col3:
            recent_holes = [h for h in holes[-3:] if h['breakout_type'] != "In Hole Now"]
            if recent_holes:
                avg_move = np.mean([abs(h['price_change_pct']) for h in recent_holes])
                st.metric("Avg Breakout Move", f"{avg_move:.1f}%")
                
                upside_breaks = len([h for h in recent_holes if "Upside" in h['breakout_type']])
                st.metric("Recent Breakout Direction", 
                         "⬆️ Bullish" if upside_breaks >= len(recent_holes)/2 else "⬇️ Bearish")
        
        st.divider()
        
        # Explanation
        with st.expander("📚 Understanding Volatility Holes", expanded=True):
            st.markdown("""
            ### What is a Volatility Hole?
            
            **A volatility hole is a period when a stock's price movement slows down dramatically** - like the calm before a storm. 
            The price "consolidates" in a tight range, and the Bollinger Bands squeeze together.
            
            ### Why Does It Matter?
            
            **Low volatility doesn't last forever.** Just like a compressed spring, when volatility drops to extreme lows, 
            it's followed by a sharp expansion - a breakout in either direction.
            
            ### How to Use It:
            
            1. **🟡 Yellow Line on Price Chart** = Volatility Hole Period
               - Price is consolidating
               - Traders are indecisive
               - Energy building for next move
            
            2. **📊 Volatility Score Below 25** = Hole Forming
               - Get ready for a move
               - Set alerts for breakout
               - Prepare options strategies
            
            3. **🔥 Breakout Markers** = Hole Released
               - Green arrow = Upside breakout (bullish)
               - Red arrow = Downside break (bearish)
               - Usually 5-15% move follows
            
            ### For Your Options Strategy:
            
            **During Volatility Hole (Score < 25):**
            - ⏸️ **Wait to sell calls** - Premium is low due to low volatility
            - 💡 **Consider straddles** - Buy both call and put (expensive but can profit from breakout)
            - 🎯 **Set alerts** - Be ready to act when breakout happens
            
            **After Breakout (Score > 75):**
            - ✅ **Sell calls on upside breakout** - High IV = fat premiums
            - 🛡️ **Buy protective puts on downside** - Protect your position
            - 💰 **Roll existing positions** - Adjust strikes for new price level
            
            **Currently In Hole:**
            - 🚫 **Don't sell calls yet** - Wait for expansion
            - 👀 **Watch for direction** - Which way will it break?
            - ⏰ **Be patient** - Best opportunities come after breakout
            """)
        
        # Recent holes analysis
        if holes:
            with st.expander(f"📜 Recent Volatility Holes ({len(holes)} found)", expanded=False):
                for i, hole in enumerate(reversed(holes[-10:])):  # Show last 10
                    status_emoji = "⚠️" if hole['breakout_type'] == "In Hole Now" else "✅"
                    color = "yellow" if hole['breakout_type'] == "In Hole Now" else (
                        "green" if "Upside" in hole['breakout_type'] else "red"
                    )
                    
                    st.markdown(f"""
                    **{status_emoji} Hole #{len(holes)-i}** - {hole['start_date'].strftime('%b %d')} to {hole['end_date'].strftime('%b %d, %Y')}
                    - **Breakout Type:** :{color}[{hole['breakout_type']}]
                    - **Price Move:** ${hole['start_price']:.2f} → ${hole['end_price']:.2f} ({hole['price_change_pct']:+.1f}%)
                    - **Min Volatility:** {hole['min_volatility']:.2f}%
                    - **Duration:** {(hole['end_date'] - hole['start_date']).days} days
                    ---
                    """)


def render_volatility_hole_for_all_stocks(selected_stocks, data_fetcher):
    """Render volatility hole analysis for all stocks"""
    
    st.title("🕳️ Volatility Hole Indicator")
    st.markdown("### Danny Cheng's Favorite Indicator - Spot Low Volatility Before Major Moves")
    
    st.info("""
    **What You'll See:**
    - 🟡 **Yellow lines** = Volatility holes (consolidation zones)
    - 🔥 **Breakout markers** = When the hole releases (up or down)
    - 📊 **Volatility score** = Below 25 = hole forming, Above 75 = breakout happening
    - 📊 **Momentum bars** = Green/red showing price direction and strength
    """)
    
    chart_builder = VolatilityHoleChart()
    
    for symbol in selected_stocks:
        with st.expander(f"📈 {symbol} - Volatility Hole Analysis", expanded=True if symbol == 'RIOT' else False):
            chart_builder.render(symbol, data_fetcher)
            st.divider()
