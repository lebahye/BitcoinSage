import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np


class RIOTProtection:
    """Dedicated RIOT share protection strategies with real-time options data"""
    
    def __init__(self):
        self.user_position = {
            'shares': 10000,
            'cost_basis': 18.22,
            'total_investment': 182200
        }
    
    def render(self, data_fetcher, options_analyzer):
        """Render RIOT protection strategies interface"""
        st.title("🛡️ RIOT Share Protection Strategies")
        st.markdown("### Protecting Your 10,000 RIOT Shares WITHOUT CASH - Generate Income!")
        st.info("💡 **No Cash Required!** All strategies use your existing shares to generate income or provide protection at zero cost.")
        
        # Display current position
        col1, col2, col3 = st.columns(3)
        
        # Get real-time RIOT data
        riot_data = data_fetcher.get_stock_data(['RIOT'], period='1D')
        current_price = riot_data['RIOT'].iloc[-1] if not riot_data.empty else 0
        
        with col1:
            st.metric("Your Position", "10,000 shares")
            st.metric("Cost Basis", "$18.22")
        
        with col2:
            st.metric("Current Price", f"${current_price:.2f}")
            unrealized_pnl = (current_price - self.user_position['cost_basis']) * self.user_position['shares']
            st.metric("Unrealized P&L", f"${unrealized_pnl:,.0f}", 
                     delta=f"{((current_price - self.user_position['cost_basis']) / self.user_position['cost_basis'] * 100):.1f}%")
        
        with col3:
            st.metric("Total Investment", f"${self.user_position['total_investment']:,}")
            current_value = current_price * self.user_position['shares']
            st.metric("Current Value", f"${current_value:,.0f}")
        
        st.divider()
        
        # Get real-time options data
        calls_df, puts_df = data_fetcher.get_options_data('RIOT')
        
        if calls_df is not None and puts_df is not None and not puts_df.empty:
            # Protection strategy tabs - NO CASH REQUIRED
            prot_tab1, prot_tab2, prot_tab3, prot_tab4 = st.tabs([
                "💰 Covered Calls", 
                "🎯 Zero-Cost Collars", 
                "🛡️ Cash-Neutral Protection",
                "📊 Income Scenarios"
            ])
            
            with prot_tab1:
                self._render_covered_calls(calls_df, current_price)
            
            with prot_tab2:
                self._render_zero_cost_collars(calls_df, puts_df, current_price)
            
            with prot_tab3:
                self._render_cash_neutral_protection(calls_df, puts_df, current_price)
            
            with prot_tab4:
                self._render_income_scenarios(current_price)
        else:
            st.error("Unable to fetch real-time RIOT options data. Please try again.")
    
    def _render_covered_calls(self, calls_df, current_price):
        """Render covered calls strategy - NO CASH REQUIRED"""
        st.subheader("💰 Covered Call Strategy - GENERATE INCOME!")
        st.markdown("""
        **Strategy:** Sell call options against your existing shares to generate immediate income.
        
        **How it works - NO CASH NEEDED:**
        - Keep all 10,000 RIOT shares
        - **SELL call options** (you receive premium immediately)
        - Generate monthly income while holding shares
        - If RIOT stays below strike, keep premium + shares
        - If RIOT rises above strike, shares may be called away at profit
        
        **Perfect for your situation:** Generate income without any upfront cost!
        """)
        
        # Filter relevant calls for covered call writing (above current price)
        relevant_calls = calls_df[
            (calls_df['strike'] >= current_price * 1.02) & 
            (calls_df['strike'] <= current_price * 1.20) &
            (calls_df['volume'] > 0)
        ].copy()
        
        if not relevant_calls.empty:
            st.markdown("### 💰 Recommended Covered Call Options - IMMEDIATE INCOME")
            
            # Calculate income potential and upside caps
            relevant_calls['upside_cap'] = ((relevant_calls['strike'] / current_price) - 1) * 100
            relevant_calls['total_income'] = relevant_calls['lastPrice'] * 100  # 100 shares per contract = 100 contracts for 10k shares
            relevant_calls['income_per_share'] = relevant_calls['lastPrice']
            relevant_calls['monthly_yield'] = (relevant_calls['income_per_share'] / current_price) * 100
            
            # Display top recommendations
            display_puts = relevant_puts.sort_values('volume', ascending=False).head(5)
            
            for idx, put in display_puts.iterrows():
                with st.expander(f"PUT ${put['strike']} - {put['protection_level']:.1f}% Protection", 
                               expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Strike Price", f"${put['strike']}")
                        st.metric("Premium", f"${put['lastPrice']:.2f}")
                    
                    with col2:
                        st.metric("Total Cost", f"${put['total_cost']:,.0f}")
                        st.metric("Expiration", put.get('expiration', 'Next Expiry'))
                    
                    with col3:
                        st.metric("Max Loss Protected", f"${(current_price - put['strike']) * self.user_position['shares']:,.0f}")
                        st.metric("Volume", f"{put['volume']:,.0f}")
                    
                    with col4:
                        st.metric("Annual Cost %", f"{put['annual_cost_pct']:.2f}%")
                        st.metric("Implied Vol", f"{put.get('impliedVolatility', 0)*100:.1f}%")
                    
                    # Calculate breakeven and scenarios
                    breakeven = current_price - put['lastPrice']
                    
                    st.markdown(f"""
                    **Strategy Details:**
                    - **Protection Level:** {put['protection_level']:.1f}% below current price
                    - **Breakeven Price:** ${breakeven:.2f}
                    - **Max Protected Loss:** ${(current_price - put['strike']) * self.user_position['shares']:,.0f}
                    - **Insurance Cost:** ${put['total_cost']:,.0f} ({put['annual_cost_pct']:.2f}% of position)
                    
                    **Why This Works:**
                    - If RIOT drops below ${put['strike']}, put gains value to offset share losses
                    - Your maximum loss is limited to ${(self.user_position['cost_basis'] - put['strike']) * self.user_position['shares']:,.0f} plus premium
                    - You keep all upside participation above ${breakeven:.2f}
                    """)
        else:
            st.warning("No suitable protective puts found. Market may be closed or low liquidity.")
    
    def _render_collar_strategy(self, calls_df, puts_df, current_price):
        """Render collar strategy (protective put + covered call)"""
        st.subheader("🎯 Collar Strategy")
        st.markdown("""
        **Strategy:** Combine protective puts with covered calls to reduce cost.
        
        **How it works:**
        - Buy protective puts (downside protection)
        - Sell covered calls (generate income, limited upside)
        - Net cost is lower than puts alone
        - Creates a "collar" around your position
        """)
        
        # Find suitable collar combinations
        if not puts_df.empty and not calls_df.empty:
            # Filter liquid options
            liquid_puts = puts_df[
                (puts_df['strike'] >= current_price * 0.85) & 
                (puts_df['strike'] <= current_price * 0.95) &
                (puts_df['volume'] > 0)
            ].copy()
            
            liquid_calls = calls_df[
                (calls_df['strike'] >= current_price * 1.05) & 
                (calls_df['strike'] <= current_price * 1.25) &
                (calls_df['volume'] > 0)
            ].copy()
            
            if not liquid_puts.empty and not liquid_calls.empty:
                st.markdown("### 🎯 Recommended Collar Combinations")
                
                # Create collar combinations
                collar_combinations = []
                for _, put in liquid_puts.head(3).iterrows():
                    for _, call in liquid_calls.head(3).iterrows():
                        net_cost = put['lastPrice'] - call['lastPrice']
                        collar_combinations.append({
                            'put_strike': put['strike'],
                            'call_strike': call['strike'],
                            'put_premium': put['lastPrice'],
                            'call_premium': call['lastPrice'],
                            'net_cost': net_cost,
                            'total_cost': net_cost * self.user_position['shares'] * 100,
                            'protection_level': ((put['strike'] / current_price) - 1) * 100,
                            'upside_cap': ((call['strike'] / current_price) - 1) * 100
                        })
                
                # Sort by best risk/reward
                collar_combinations.sort(key=lambda x: x['net_cost'])
                
                for i, collar in enumerate(collar_combinations[:3]):
                    with st.expander(f"Collar #{i+1}: PUT ${collar['put_strike']} / CALL ${collar['call_strike']}", 
                                   expanded=i==0):
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            st.markdown("**Protection Side:**")
                            st.metric("Put Strike", f"${collar['put_strike']}")
                            st.metric("Put Premium", f"${collar['put_premium']:.2f}")
                            st.metric("Protection", f"{collar['protection_level']:.1f}%")
                        
                        with col2:
                            st.markdown("**Income Side:**")
                            st.metric("Call Strike", f"${collar['call_strike']}")
                            st.metric("Call Premium", f"${collar['call_premium']:.2f}")
                            st.metric("Upside Cap", f"{collar['upside_cap']:.1f}%")
                        
                        with col3:
                            st.markdown("**Net Strategy:**")
                            cost_color = "inverse" if collar['net_cost'] < 0 else "normal"
                            st.metric("Net Cost", f"${collar['net_cost']:.2f}", delta_color=cost_color)
                            st.metric("Total Cost", f"${collar['total_cost']:,.0f}")
                        
                        # Calculate scenarios
                        max_loss = (self.user_position['cost_basis'] - collar['put_strike']) * self.user_position['shares'] + collar['total_cost']
                        max_gain = (collar['call_strike'] - self.user_position['cost_basis']) * self.user_position['shares'] - collar['total_cost']
                        
                        st.markdown(f"""
                        **Collar Strategy Details:**
                        - **Cost:** {"CREDIT" if collar['net_cost'] < 0 else "DEBIT"} of ${abs(collar['total_cost']):,.0f}
                        - **Protection:** Losses limited below ${collar['put_strike']:.2f}
                        - **Cap:** Gains limited above ${collar['call_strike']:.2f}
                        - **Max Loss:** ${max_loss:,.0f}
                        - **Max Gain:** ${max_gain:,.0f}
                        
                        **Perfect for your outlook:**
                        - Protects against 10-15% volatility swings
                        - Maintains exposure to moderate gains
                        - {"Generates income" if collar['net_cost'] < 0 else "Low cost protection"}
                        """)
            else:
                st.warning("Insufficient options liquidity for collar strategies.")
    
    def _render_scenario_analysis(self, current_price):
        """Render profit/loss scenario analysis"""
        st.subheader("📊 Scenario Analysis")
        st.markdown("### See how different strategies perform across price scenarios")
        
        # Create price scenarios
        price_scenarios = np.linspace(current_price * 0.7, current_price * 1.4, 50)
        
        # Unprotected position
        unprotected_pnl = [(price - self.user_position['cost_basis']) * self.user_position['shares'] 
                          for price in price_scenarios]
        
        # Example protected position (using typical put)
        put_strike = current_price * 0.9
        put_premium = current_price * 0.02  # Estimate 2% premium
        put_cost = put_premium * self.user_position['shares']
        
        protected_pnl = []
        for price in price_scenarios:
            share_pnl = (price - self.user_position['cost_basis']) * self.user_position['shares']
            put_pnl = max(0, put_strike - price) * self.user_position['shares']
            total_pnl = share_pnl + put_pnl - put_cost
            protected_pnl.append(total_pnl)
        
        # Create interactive chart
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=price_scenarios,
            y=unprotected_pnl,
            mode='lines',
            name='Unprotected Position',
            line=dict(color='red', width=2)
        ))
        
        fig.add_trace(go.Scatter(
            x=price_scenarios,
            y=protected_pnl,
            mode='lines',
            name=f'Protected (${put_strike:.0f} Put)',
            line=dict(color='green', width=2)
        ))
        
        # Add current price line
        fig.add_vline(x=current_price, line_dash="dash", 
                     annotation_text=f"Current: ${current_price:.2f}")
        
        # Add cost basis line
        fig.add_vline(x=self.user_position['cost_basis'], line_dash="dot",
                     annotation_text=f"Your Cost: ${self.user_position['cost_basis']}")
        
        fig.update_layout(
            title="P&L Scenarios: Protected vs Unprotected Position",
            xaxis_title="RIOT Price",
            yaxis_title="Total P&L ($)",
            hovermode='x unified',
            height=500
        )
        
        fig.update_yaxis(tickformat='$,.0f')
        fig.update_xaxis(tickformat='$,.2f')
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Key scenarios table
        st.markdown("### 🎯 Key Price Scenarios")
        scenarios_data = []
        key_prices = [current_price * 0.8, current_price * 0.9, current_price, 
                     current_price * 1.1, current_price * 1.2]
        
        for price in key_prices:
            unprotected = (price - self.user_position['cost_basis']) * self.user_position['shares']
            share_pnl = (price - self.user_position['cost_basis']) * self.user_position['shares']
            put_pnl = max(0, put_strike - price) * self.user_position['shares']
            protected = share_pnl + put_pnl - put_cost
            
            scenarios_data.append({
                'RIOT Price': f"${price:.2f}",
                'Price Change': f"{((price/current_price - 1) * 100):+.1f}%",
                'Unprotected P&L': f"${unprotected:,.0f}",
                'Protected P&L': f"${protected:,.0f}",
                'Protection Value': f"${protected - unprotected:,.0f}"
            })
        
        scenarios_df = pd.DataFrame(scenarios_data)
        st.dataframe(scenarios_df, use_container_width=True)
        
        # Strategy recommendations
        st.markdown("### 🎯 Strategy Recommendations for Your RIOT Position")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("""
            **✅ BEST: Protective Puts**
            - Perfect for your bullish mid-2026 outlook
            - Protects against 10-15% volatility
            - Keep full upside participation
            - Cost: ~2-4% of position annually
            """)
        
        with col2:
            st.markdown("""
            **✅ ALTERNATIVE: Collar Strategy**
            - Lower cost or even generate income
            - Still provides downside protection
            - Caps upside at call strike
            - Good if you want to reduce volatility
            """)
        
        st.info("""
        **💡 For your specific situation:** With 10,000 shares and belief in long-term growth through mid-2026, 
        protective puts are ideal. They let you sleep better during the inevitable 10-15% swings while keeping 
        all the upside when RIOT moves higher. Consider rolling the puts quarterly to maintain protection.
        """)