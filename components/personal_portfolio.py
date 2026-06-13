import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.unified_data_fetcher import DataFetcher

class PersonalPortfolio:
    """Personalized portfolio management for user's actual mining stock positions"""
    
    def __init__(self):
        # User's actual positions
        self.positions = {
            'BITF': {'shares': 1700, 'name': 'Bitfarms Ltd'},
            'BTBT': {'shares': 600, 'name': 'Bit Digital Inc'}, 
            'CLSK': {'shares': 300, 'name': 'CleanSpark Inc'},
            'MARA': {'shares': 200, 'name': 'Marathon Digital'},
            'RIOT': {'shares': 10975, 'name': 'Riot Platforms Inc'},
            'CIFR': {'shares': 500, 'name': 'Cipher Mining Inc'},
            'IREN': {'shares': 500, 'name': 'Iris Energy Ltd'},
            'MSTR': {'shares': 38, 'name': 'MicroStrategy Inc'},
            'WULF': {'shares': 500, 'name': 'TeraWulf Inc'}
        }
        
        self.total_shares = sum(pos['shares'] for pos in self.positions.values())
    
    def render(self, data_fetcher, options_analyzer):
        """Render personalized portfolio dashboard"""
        st.title("🏆 Your Personal Mining Portfolio Command Center")
        st.markdown("### Real-Time Analysis of Your Actual Holdings")
        
        # Portfolio overview
        self._render_portfolio_overview(data_fetcher)
        
        # Income strategies by position size
        self._render_income_strategies(data_fetcher, options_analyzer)
        
        # Cross-portfolio strategies
        self._render_cross_portfolio_strategies(data_fetcher, options_analyzer)
        
        # Total portfolio projections
        self._render_total_projections(data_fetcher, options_analyzer)
    
    def _render_portfolio_overview(self, data_fetcher):
        """Show current portfolio value and metrics"""
        st.subheader("📊 Your Current Portfolio")
        
        # Get current prices for all positions
        symbols = list(self.positions.keys())
        current_data = {}
        total_value = 0
        
        for symbol in symbols:
            try:
                stock_data = data_fetcher.get_stock_data([symbol], period='1D')
                if not stock_data.empty:
                    current_price = stock_data[symbol].iloc[-1]
                    current_data[symbol] = current_price
                    position_value = current_price * self.positions[symbol]['shares']
                    total_value += position_value
            except Exception as _exc:
                import logging
                logging.warning("Price fetch failed for %s: %s", symbol, _exc)
                current_data[symbol] = None
        
        # Portfolio summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Positions", f"{len(self.positions)}")
            st.metric("Total Shares", f"{self.total_shares:,}")
        
        with col2:
            st.metric("Portfolio Value", f"${total_value:,.0f}")
            largest_position = max(self.positions.items(), key=lambda x: x[1]['shares'])
            st.metric("Largest Position", f"{largest_position[0]} ({largest_position[1]['shares']:,})")
        
        with col3:
            # Calculate RIOT dominance
            riot_value = current_data.get('RIOT', 0) * self.positions['RIOT']['shares']
            riot_percentage = (riot_value / total_value * 100) if total_value > 0 else 0
            st.metric("RIOT Dominance", f"{riot_percentage:.1f}%")
            
        with col4:
            # Options-ready positions (>= 100 shares)
            options_ready = sum(1 for pos in self.positions.values() if pos['shares'] >= 100)
            st.metric("Options-Ready", f"{options_ready}/9 positions")
        
        # Detailed position table
        st.subheader("📋 Position Details")
        
        position_data = []
        for symbol, data in self.positions.items():
            current_price = current_data.get(symbol, 0)
            position_value = current_price * data['shares']
            
            # Calculate contracts available (100 shares per contract)
            max_contracts = data['shares'] // 100
            
            position_data.append({
                'Symbol': symbol,
                'Company': data['name'],
                'Shares': f"{data['shares']:,}",
                'Current Price': f"${current_price:.2f}",
                'Position Value': f"${position_value:,.0f}",
                'Max Contracts': max_contracts,
                'Strategy Tier': self._get_strategy_tier(data['shares'])
            })
        
        df = pd.DataFrame(position_data)
        st.dataframe(df, use_container_width=True)
    
    def _get_strategy_tier(self, shares):
        """Determine strategy tier based on position size"""
        if shares >= 1000:
            return "🔥 MEGA (Multi-tranche)"
        elif shares >= 500:
            return "🎯 LARGE (Full strategies)" 
        elif shares >= 200:
            return "💡 MEDIUM (Basic coverage)"
        elif shares >= 100:
            return "📈 SMALL (Limited options)"
        else:
            return "🔒 MICRO (No options)"
    
    def _render_income_strategies(self, data_fetcher, options_analyzer):
        """Show income strategies by position tier"""
        st.subheader("💰 Position-Specific Income Strategies")
        
        # Group by strategy tier
        mega_positions = {k: v for k, v in self.positions.items() if v['shares'] >= 1000}
        large_positions = {k: v for k, v in self.positions.items() if 500 <= v['shares'] < 1000}
        medium_positions = {k: v for k, v in self.positions.items() if 200 <= v['shares'] < 500}
        small_positions = {k: v for k, v in self.positions.items() if 100 <= v['shares'] < 200}
        
        # MEGA Positions - Multi-tranche strategies
        if mega_positions:
            with st.expander("🔥 MEGA Positions - Multi-Tranche Strategies", expanded=True):
                st.markdown("**These positions are large enough for sophisticated multi-layer strategies like your HIVE plan**")
                
                for symbol, data in mega_positions.items():
                    st.markdown(f"### {symbol} - {data['shares']:,} shares")
                    
                    # Calculate potential tranches
                    contracts_available = data['shares'] // 100
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**Contracts Available:** {contracts_available}")
                        st.info(f"**Monthly Income Tier:** 50-75% of position")
                    
                    with col2:
                        st.success(f"**Quarterly Income Tier:** 25-30% of position")
                        st.success(f"**Long-term LEAPs:** Remaining contracts")
                    
                    with col3:
                        monthly_contracts = int(contracts_available * 0.6)
                        quarterly_contracts = int(contracts_available * 0.25)
                        leaps_contracts = contracts_available - monthly_contracts - quarterly_contracts
                        
                        st.markdown(f"**Suggested Split:**")
                        st.markdown(f"- Monthly: {monthly_contracts} contracts")
                        st.markdown(f"- Quarterly: {quarterly_contracts} contracts") 
                        st.markdown(f"- LEAPs: {leaps_contracts} contracts")
                    
                    st.divider()
        
        # LARGE Positions - Full strategies
        if large_positions:
            with st.expander("🎯 LARGE Positions - Full Coverage Strategies", expanded=False):
                for symbol, data in large_positions.items():
                    st.markdown(f"**{symbol}:** {data['shares']:,} shares → {data['shares']//100} contracts available")
                    st.markdown(f"- **Strategy:** Monthly covered calls + protective puts")
                    st.markdown(f"- **Income Potential:** $2,000-4,000/month per position")
        
        # MEDIUM/SMALL Positions
        if medium_positions or small_positions:
            with st.expander("💡 MEDIUM/SMALL Positions - Focused Strategies", expanded=False):
                all_smaller = {**medium_positions, **small_positions}
                
                for symbol, data in all_smaller.items():
                    contracts = data['shares'] // 100
                    if contracts > 0:
                        st.markdown(f"**{symbol}:** {data['shares']:,} shares → {contracts} contracts")
                        st.markdown(f"- **Strategy:** Conservative covered calls or protective puts")
    
    def _render_cross_portfolio_strategies(self, data_fetcher, options_analyzer):
        """Show strategies that work across multiple positions"""
        st.subheader("🔗 Cross-Portfolio Strategies")
        
        tab1, tab2, tab3 = st.tabs(["Portfolio Collars", "Sector Hedging", "Income Laddering"])
        
        with tab1:
            st.markdown("**Portfolio-Wide Collar Strategy**")
            st.info("""
            **Concept:** Use your RIOT mega-position as the anchor:
            - **SELL calls** on RIOT (huge premium)
            - **BUY puts** across smaller positions for protection
            - **Result:** Income from RIOT funds protection for entire portfolio
            """)
            
            # Show which positions could work together
            st.markdown("**Optimal Pairing:**")
            st.markdown("- **Income Generator:** RIOT (10,975 shares) + BITF (1,700 shares)")
            st.markdown("- **Protection Targets:** MARA, CLSK, WULF, IREN, CIFR")
        
        with tab2:
            st.markdown("**Sector Risk Management**")
            st.warning("""
            **Portfolio Risk:** You're heavily concentrated in Bitcoin mining
            - **9 mining positions** = High correlation risk
            - **MSTR** provides some diversification (software vs mining)
            - **Suggestion:** Consider VIX calls or QQQ puts for broader protection
            """)
        
        with tab3:
            st.markdown("**Staggered Income Generation**")
            st.success("""
            **Income Laddering Strategy:**
            - **Week 1:** RIOT + BITF covered calls
            - **Week 2:** WULF + IREN covered calls  
            - **Week 3:** CIFR + BTBT covered calls
            - **Week 4:** MARA + CLSK covered calls
            
            **Result:** Weekly income instead of monthly lump sums
            """)
    
    def _render_total_projections(self, data_fetcher, options_analyzer):
        """Calculate total portfolio income potential"""
        st.subheader("🚀 Total Portfolio Income Projections")
        
        # Conservative estimates based on position sizes
        income_estimates = {
            'RIOT': {'monthly': 8000, 'reasoning': '109 contracts @ ~$73 avg premium'},
            'BITF': {'monthly': 1200, 'reasoning': '17 contracts @ ~$70 avg premium'},
            'BTBT': {'monthly': 400, 'reasoning': '6 contracts @ ~$67 avg premium'},
            'WULF': {'monthly': 350, 'reasoning': '5 contracts @ ~$70 avg premium'},
            'IREN': {'monthly': 350, 'reasoning': '5 contracts @ ~$70 avg premium'},
            'CIFR': {'monthly': 350, 'reasoning': '5 contracts @ ~$70 avg premium'},
            'CLSK': {'monthly': 200, 'reasoning': '3 contracts @ ~$67 avg premium'},
            'MARA': {'monthly': 140, 'reasoning': '2 contracts @ ~$70 avg premium'},
            'MSTR': {'monthly': 0, 'reasoning': 'Only 38 shares - no options'}
        }
        
        total_monthly = sum(est['monthly'] for est in income_estimates.values())
        total_annual = total_monthly * 12
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Monthly Income Potential", f"${total_monthly:,}")
        with col2:
            st.metric("Annual Income Potential", f"${total_annual:,}")
        with col3:
            # Compute actual portfolio value from live prices
            live_portfolio_value = 0.0
            for sym, pos in self.positions.items():
                try:
                    stock_data = data_fetcher.get_stock_data([sym], period='1D')
                    if not stock_data.empty and sym in stock_data.columns:
                        live_portfolio_value += stock_data[sym].iloc[-1] * pos['shares']
                except Exception:
                    pass  # Partial value if some tickers fail; logged by data_fetcher
            annual_return = (total_annual / live_portfolio_value * 100) if live_portfolio_value > 0 else 0
            st.metric("Estimated Annual Return", f"{annual_return:.1f}%")
        with col4:
            total_contracts = sum(pos['shares']//100 for pos in self.positions.values())
            st.metric("Total Contracts Available", total_contracts)
        
        # Detailed breakdown
        st.markdown("### 📊 Income Breakdown by Position")
        
        income_data = []
        for symbol, estimate in income_estimates.items():
            shares = self.positions[symbol]['shares']
            contracts = shares // 100
            income_data.append({
                'Symbol': symbol,
                'Shares': f"{shares:,}",
                'Contracts': contracts,
                'Monthly Income': f"${estimate['monthly']:,}",
                'Annual Income': f"${estimate['monthly'] * 12:,}",
                'Strategy Notes': estimate['reasoning']
            })
        
        df = pd.DataFrame(income_data)
        st.dataframe(df, use_container_width=True)
        
        st.success(f"""
        🎯 **Your Portfolio Has SERIOUS Income Potential!**
        
        **Conservative Strategy:** ${total_monthly:,}/month (${total_annual:,}/year)
        **Aggressive Strategy:** Could potentially generate 50%+ more
        
        **Key Advantage:** Your RIOT position alone could generate $8,000+ monthly!
        """)