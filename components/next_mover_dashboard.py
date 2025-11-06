"""
Next Mover Prediction Dashboard
Identifies which mining stock will run next based on multi-factor analysis
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime
from utils.next_mover_engine import NextMoverEngine


class NextMoverDashboard:
    """Dashboard for predicting which mining stock will move next"""
    
    def __init__(self):
        self.engine = NextMoverEngine()
    
    def render(self, data_fetcher, options_analyzer):
        """Render the Next Mover Prediction dashboard"""
        st.title("🎯 Next Mover Prediction Engine")
        st.markdown("### AI-Powered Analysis: Which Mining Stock Will Run Next?")
        
        st.info("""
        **How It Works:** This engine analyzes all 9 mining stocks across multiple factors:
        - 🎯 **Relative Strength**: Identifies laggards likely to catch up
        - 📈 **Technical Setup**: RSI, MACD, volume breakouts
        - ₿ **Bitcoin Correlation**: High-beta stocks when BTC rallies
        - 📊 **Multi-Factor Score**: Weighted composite ranking
        """)
        
        # Get predictions
        with st.spinner("Analyzing all mining stocks..."):
            rankings = self.engine.calculate_composite_score()
            top_pick = self.engine.get_top_pick()
        
        if rankings.empty:
            st.error("Unable to fetch data. Please try again.")
            return
        
        # TOP PICK HIGHLIGHT
        st.divider()
        st.subheader("🏆 #1 Predicted Next Mover")
        
        if top_pick:
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Symbol", top_pick['symbol'])
                if top_pick.get('current_price'):
                    st.metric("Current Price", f"${top_pick['current_price']:.2f}")
            
            with col2:
                st.metric("Run Probability", top_pick['probability'])
                st.metric("Composite Score", f"{top_pick['score']:.1f}/100")
            
            with col3:
                st.metric("RSI", f"{top_pick['rsi']:.1f}")
                gap = top_pick.get('performance_gap', 0)
                st.metric("Gap to Avg", f"{gap:+.1f}%", 
                         delta="Underperforming" if gap > 0 else "Outperforming")
            
            with col4:
                # Confidence level
                score = top_pick['score']
                if score >= 75:
                    confidence = "🔥 Very High"
                elif score >= 65:
                    confidence = "✅ High"
                elif score >= 55:
                    confidence = "⚠️ Moderate"
                else:
                    confidence = "❌ Low"
                st.metric("Confidence", confidence)
            
            # Key signals
            st.success(f"**Why {top_pick['symbol']}?** {top_pick['signals']}")
        
        st.divider()
        
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "📊 Full Rankings",
            "📈 Performance Chart",
            "🔬 Factor Analysis",
            "📚 Historical Leaders"
        ])
        
        with tab1:
            self._render_rankings(rankings)
        
        with tab2:
            self._render_performance_chart()
        
        with tab3:
            self._render_factor_analysis(rankings)
        
        with tab4:
            self._render_historical_analysis()
    
    def _render_rankings(self, rankings):
        """Display full stock rankings"""
        st.subheader("🏅 Complete Stock Rankings by Run Probability")
        
        # Format the display DataFrame
        display_df = rankings[['Rank', 'Symbol', 'Run Probability', 'Key Signals']].copy()
        
        # Style the dataframe
        def highlight_top_3(row):
            if row['Rank'] == 1:
                return ['background-color: #28a745; color: white'] * len(row)
            elif row['Rank'] == 2:
                return ['background-color: #ffc107; color: black'] * len(row)
            elif row['Rank'] == 3:
                return ['background-color: #fd7e14; color: white'] * len(row)
            return [''] * len(row)
        
        styled_df = display_df.style.apply(highlight_top_3, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        # Detailed breakdown
        st.markdown("### 📋 Detailed Score Breakdown")
        detail_df = rankings[['Symbol', 'RS Score', 'Tech Score', 'BTC Score', 'Score']].copy()
        detail_df.columns = ['Symbol', 'Relative Strength', 'Technical', 'Bitcoin Beta', 'Composite']
        
        st.dataframe(detail_df, use_container_width=True, hide_index=True)
        
        # Interpretation guide
        with st.expander("📖 How to Read These Scores"):
            st.markdown("""
            **Score Interpretation:**
            - **75-100%**: Very High Probability - Strong buy setup
            - **65-74%**: High Probability - Good entry opportunity  
            - **55-64%**: Moderate Probability - Watch for confirmation
            - **Below 55%**: Low Probability - Wait for better setup
            
            **Key Factors:**
            - **Relative Strength (35% weight)**: Laggards often catch up to leaders
            - **Technical (40% weight)**: RSI, MACD, volume signals
            - **Bitcoin Beta (25% weight)**: Correlation when BTC is moving
            """)
    
    def _render_performance_chart(self):
        """Render comparative performance chart (like screenshot)"""
        st.subheader("📈 Comparative Performance Chart - All Mining Stocks")
        st.markdown("*Normalized to 100 at start - shows which stocks are leading/lagging*")
        
        # Get performance data
        period = st.selectbox("Time Period", ['1M', '3M', '6M', '1Y'], index=1, key='perf_period')
        
        with st.spinner("Loading performance data..."):
            perf_data = self.engine.get_comparative_performance(period=period)
        
        if perf_data.empty:
            st.warning("Unable to fetch performance data")
            return
        
        # Create the chart (like the screenshot)
        fig = go.Figure()
        
        # Color mapping for stocks
        colors = {
            'RIOT': '#3366FF',   # Blue
            'MARA': '#FF6633',   # Orange  
            'CLSK': '#33CC33',   # Green
            'HUT': '#FF3366',    # Pink/Red
            'IREN': '#FFCC00',   # Yellow/Gold
            'BITF': '#9933FF',   # Purple
            'BTBT': '#00CCCC',   # Cyan
            'WULF': '#FF9933',   # Light Orange
            'CIFR': '#66CCFF'    # Light Blue
        }
        
        for symbol in perf_data.columns:
            fig.add_trace(go.Scatter(
                x=perf_data.index,
                y=perf_data[symbol],
                mode='lines',
                name=symbol,
                line=dict(color=colors.get(symbol, '#888888'), width=2.5),
                hovertemplate=f'{symbol}: %{{y:.1f}}<extra></extra>'
            ))
        
        # Update layout to match screenshot style
        fig.update_layout(
            title=f"Mining Stock Performance Comparison ({period})",
            xaxis_title="Date",
            yaxis_title="Normalized Performance (Start = 100)",
            hovermode='x unified',
            template='plotly_dark',
            height=600,
            showlegend=True,
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1,
                xanchor="right",
                x=1.15
            ),
            xaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)'),
            yaxis=dict(showgrid=True, gridcolor='rgba(128,128,128,0.2)')
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Performance summary
        st.markdown("### 🏆 Performance Summary")
        col1, col2 = st.columns(2)
        
        with col1:
            # Leaders
            latest_values = perf_data.iloc[-1].sort_values(ascending=False)
            st.markdown("**Top Performers:**")
            for i, (symbol, value) in enumerate(latest_values.head(3).items(), 1):
                change = value - 100
                st.write(f"{i}. **{symbol}**: {change:+.1f}% 🚀")
        
        with col2:
            # Laggards
            st.markdown("**Laggards (Catch-up Potential):**")
            for i, (symbol, value) in enumerate(latest_values.tail(3).items(), 1):
                change = value - 100
                st.write(f"{i}. **{symbol}**: {change:+.1f}% 🎯")
    
    def _render_factor_analysis(self, rankings):
        """Detailed breakdown of each factor"""
        st.subheader("🔬 Multi-Factor Analysis Breakdown")
        
        # Create factor comparison chart
        fig = go.Figure()
        
        symbols = rankings['Symbol'].tolist()
        
        fig.add_trace(go.Bar(
            name='Relative Strength',
            x=symbols,
            y=rankings['RS Score'],
            marker_color='#3366FF'
        ))
        
        fig.add_trace(go.Bar(
            name='Technical Setup',
            x=symbols,
            y=rankings['Tech Score'],
            marker_color='#FF6633'
        ))
        
        fig.add_trace(go.Bar(
            name='Bitcoin Correlation',
            x=symbols,
            y=rankings['BTC Score'],
            marker_color='#33CC33'
        ))
        
        fig.update_layout(
            title="Factor Scores by Stock",
            xaxis_title="Stock",
            yaxis_title="Score (0-100)",
            barmode='group',
            template='plotly_dark',
            height=500
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Factor explanations
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("""
            **🎯 Relative Strength (35%)**
            - Identifies underperformers
            - Mean reversion play
            - Laggards tend to catch up
            """)
        
        with col2:
            st.markdown("""
            **📈 Technical Setup (40%)**
            - RSI oversold signals
            - MACD crossovers
            - Volume breakouts
            """)
        
        with col3:
            st.markdown("""
            **₿ Bitcoin Beta (25%)**
            - Correlation to BTC
            - High beta in rallies
            - Defensive in drops
            """)
    
    def _render_historical_analysis(self):
        """Show historical pattern analysis"""
        st.subheader("📚 Historical Rally Patterns")
        
        st.info("""
        **Historical Insights:**
        - Mining stocks tend to move in rotations
        - Laggards often rally 10-30% to catch sector average
        - High-beta stocks amplify Bitcoin moves (1.5-2x)
        - Technical setups (RSI < 30) + sector rotation = highest win rate
        """)
        
        # Example historical patterns
        st.markdown("### 🔄 Typical Rotation Pattern:")
        
        pattern_data = {
            'Phase': ['1️⃣ Leaders Rally', '2️⃣ Laggards Catch Up', '3️⃣ Consolidation', '4️⃣ Next Wave'],
            'Typical Stocks': ['MARA, RIOT (high volume)', 'HUT, IREN, CLSK (catch up)', 'All stocks sideways', 'New leaders emerge'],
            'Duration': ['3-7 days', '5-10 days', '1-2 weeks', 'Varies'],
            'Strategy': ['Ride momentum', 'Buy laggards', 'Take profits', 'Reset positions']
        }
        
        pattern_df = pd.DataFrame(pattern_data)
        st.table(pattern_df)
        
        st.success("""
        **💡 Key Takeaway:** When leaders (MARA, RIOT) have run 20%+ and are overbought (RSI > 70),
        look for laggards with strong technical setups - they often rally next to close the gap.
        """)
