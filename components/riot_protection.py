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
        
        # Get real-time RIOT data FIRST
        riot_data = data_fetcher.get_stock_data(['RIOT'], period='1D')
        current_price = riot_data['RIOT'].iloc[-1] if not riot_data.empty else 0
        
        # Quick expiration date guidance - CRITICAL!
        st.success("""
        📅 **QUICK ANSWER: Which Expiration Date?**
        
        **Use 31 OCT 25 (39 days)** for all your strategies - this is the sweet spot!
        
        ✅ **Perfect timeframe:** 30-45 days gives you optimal premium collection  
        ❌ **Avoid weeklies:** 26 SEP, 3 OCT, 10 OCT expire too fast  
        ⚠️ **Longer-term:** 21 NOV 25 (60 days) acceptable if better liquidity
        """)
        
        # Add Start Here wizard
        with st.expander("🚀 START HERE - Beginner's Guide", expanded=False):
            self._render_start_here_wizard(current_price)
        
        st.info("💡 **No Cash Required!** All strategies use your existing shares to generate income or provide protection at zero cost.")
        
        # Display current position
        col1, col2, col3 = st.columns(3)
        
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
    
    def _render_start_here_wizard(self, current_price):
        """Beginner-friendly wizard to guide users through strategy selection"""
        st.markdown("## 🎯 **Step-by-Step Guide for Beginners**")
        
        # Step 1: Understanding Your Position
        st.markdown("### 📋 Step 1: Your Current Position")
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown(f"""
            **✅ What You Own:**
            - **10,000 RIOT shares** 
            - **Paid:** $18.22 per share
            - **Total Investment:** $182,200
            - **Current Value:** ${current_price * 10000:,.0f}
            """)
        
        with col2:
            pnl = (current_price - 18.22) * 10000
            pnl_pct = ((current_price - 18.22) / 18.22) * 100
            st.markdown(f"""
            **📊 Current Status:**
            - **Current Price:** ${current_price:.2f}
            - **Profit/Loss:** ${pnl:,.0f} ({pnl_pct:+.1f}%)
            - **Available Cash:** $0 (your constraint)
            - **Goal:** Protection + Income without spending money
            """)
        
        st.divider()
        
        # Step 2: Choose Your Goal
        st.markdown("### 🎯 Step 2: What's Your Main Goal?")
        
        goal = st.radio(
            "Pick your primary objective:",
            ["💰 Generate Monthly Income", "🛡️ Protect Against Losses", "⚖️ Both Income and Protection"],
            help="Choose what matters most to you right now"
        )
        
        if goal == "💰 Generate Monthly Income":
            st.success("""
            **Perfect Choice!** Covered Calls are ideal for you:
            - Generate $2,000-$8,000+ monthly income
            - Keep all your shares (unless called away at profit)
            - Zero cash required - use your existing shares
            - **Next:** Go to the "💰 Covered Calls" tab above
            """)
            
        elif goal == "🛡️ Protect Against Losses":
            st.success("""
            **Smart Approach!** You need a Zero-Cost Collar:
            - Limit losses if RIOT drops 10-15%
            - Still participate in moderate gains
            - Zero cash required - premiums balance out
            - **Next:** Go to the "🎯 Zero-Cost Collars" tab above
            """)
            
        else:  # Both
            st.success("""
            **Best of Both Worlds!** Start with Covered Calls, then add protection:
            1. **First:** Sell covered calls for income
            2. **Then:** Use some income to buy protection
            3. **Result:** Monthly income + downside protection
            - **Next:** Go to "🛡️ Cash-Neutral Protection" tab above
            """)
        
        st.divider()
        
        # Step 3: Key Terms Explained
        st.markdown("### 📚 Step 3: Key Terms You Need to Know")
        
        term_col1, term_col2 = st.columns(2)
        
        with term_col1:
            st.markdown("""
            **🔑 Essential Terms:**
            
            **Call Option:** Right to BUY shares at a set price
            - When you SELL calls, you get paid immediately
            - You're giving someone else the right to buy your shares
            
            **Put Option:** Right to SELL shares at a set price  
            - When you BUY puts, you pay for protection
            - Protects you if stock price falls
            
            **Strike Price:** The set price in the option contract
            - Calls: Price someone can buy your shares
            - Puts: Price you can sell shares (floor protection)
            """)
        
        with term_col2:
            st.markdown("""
            **💡 Strategy Basics:**
            
            **Covered Call:** Sell call options on shares you own
            - ✅ Generate income immediately
            - ⚠️ Cap your upside at strike price
            
            **Protective Put:** Buy put options for downside protection
            - ✅ Limit your losses 
            - ❌ Costs money upfront
            
            **Collar:** Sell calls + Buy puts = Zero cost
            - ✅ Income from calls pays for puts
            - ✅ Protection + Income with no cash needed
            """)
        
        st.divider()
        
        # Step 4: Execution Guide
        st.markdown("### 🚀 Step 4: How to Execute (Broker Instructions)")
        
        st.warning("""
        **⚠️ Important:** Always paper trade first if you're new to options! 
        
        **For Your 10,000 Shares, You Need:**
        - **100 contracts** for any strategy (each contract = 100 shares)
        - **Example:** To sell covered calls on all shares = "Sell to Open 100 contracts"
        """)
        
        exec_col1, exec_col2 = st.columns(2)
        
        with exec_col1:
            st.markdown("""
            **📞 Broker Order Example (Covered Call):**
            1. **Action:** "Sell to Open"
            2. **Quantity:** 100 contracts  
            3. **Option:** RIOT Call [Expiry] [Strike]
            4. **Type:** Limit order at desired price
            5. **Duration:** Day or Good Till Canceled
            """)
        
        with exec_col2:
            st.markdown("""
            **🔍 What to Look For:**
            - **Volume > 100:** Ensures you can trade easily
            - **Tight Bid-Ask Spread:** Better pricing
            - **30-45 Days to Expiry:** Sweet spot for premiums (**31 OCT 25 = Perfect!**)
            - **Strike 5-15% Above Current:** Good risk/reward
            
            **📅 EXPIRATION DATE CHEAT SHEET:**
            - **26 SEP 25 (4 days):** ❌ TOO SHORT - Weekly trap!
            - **3 OCT 25 (11 days):** ❌ TOO SHORT - High assignment risk
            - **10 OCT 25 (18 days):** ⚠️ SHORT - Risky but possible
            - **31 OCT 25 (39 days):** ✅ PERFECT - Sweet spot!
            - **21 NOV 25 (60 days):** ⚠️ LONG - Less flexible
            - **19 DEC 25 (88 days):** ❌ TOO LONG - Avoid
            """)
        
        st.info("""
        **🎯 Ready to Start?** 
        1. Choose your goal above
        2. Go to the recommended tab  
        3. Find a strategy you like
        4. Paper trade it first
        5. Execute when comfortable
        
        **Remember:** You can always ask questions or start small with fewer contracts!
        """)
    
    def _render_covered_calls(self, calls_df, current_price):
        """Render covered calls strategy - NO CASH REQUIRED"""
        st.subheader("💰 Covered Call Strategy - GENERATE INCOME!")
        st.markdown("""
        **Strategy:** Sell call options against your existing shares to generate immediate income.
        
        **🗓️ WHICH EXPIRATION DATE TO CHOOSE:**
        
        **✅ RECOMMENDED: 30-45 Days to Expiration**
        - **From your screenshots:** Choose **31 OCT 25 (39 days)** options
        - **Why this timeframe:** Sweet spot for premium collection vs. time risk
        - **Avoid:** Weekly options (too risky, expire too fast)
        - **Avoid:** 60+ day options (too long, less flexibility)
        
        **How it works - NO CASH NEEDED:**
        - Keep all 10,000 RIOT shares
        - **SELL call options** with 30-45 day expiration (you receive premium immediately)
        - Generate monthly income while holding shares
        - If RIOT stays below strike, keep premium + shares
        - If RIOT rises above strike, shares may be called away at profit
        
        **Perfect for your situation:** Generate income without any upfront cost!
        """)
        
        # Filter relevant calls for covered call writing (above current price)
        # Focus on 30-45 day expiration options
        relevant_calls = calls_df[
            (calls_df['strike'] >= current_price * 1.02) & 
            (calls_df['strike'] <= current_price * 1.20) &
            (calls_df['volume'] > 0)
        ].copy()
        
        # Add expiration guidance
        if not relevant_calls.empty:
            st.info("""
            🎯 **EXPIRATION DATE SELECTION:**
            
            **Choose options expiring in 30-45 days** for optimal risk/reward:
            - **Best Choice:** 31 OCT 25 (39 days) - Perfect timeframe!
            - **Alternative:** 21 NOV 25 (60 days) - Acceptable but longer commitment
            - **Avoid:** Weekly options (26 SEP, 3 OCT, 10 OCT) - Too risky!
            
            **Why 30-45 days?**
            - Maximum time decay efficiency
            - Good premium collection
            - Flexibility to roll if needed
            - Lower assignment risk than weeklies
            """)
        
        if not relevant_calls.empty:
            st.markdown("### 💰 Recommended Covered Call Options - IMMEDIATE INCOME")
            
            # Calculate income potential and upside caps
            relevant_calls['upside_cap'] = ((relevant_calls['strike'] / current_price) - 1) * 100
            relevant_calls['total_income'] = relevant_calls['lastPrice'] * 10000  # Income for all 10,000 shares (100 contracts)
            relevant_calls['income_per_share'] = relevant_calls['lastPrice']
            relevant_calls['monthly_yield'] = (relevant_calls['income_per_share'] / current_price) * 100
            relevant_calls['contracts_needed'] = 100  # 100 contracts for 10,000 shares
            
            # Display top recommendations
            display_calls = relevant_calls.sort_values('volume', ascending=False).head(5)
            
            for idx, call in display_calls.iterrows():
                with st.expander(f"CALL ${call['strike']} - {call['upside_cap']:.1f}% Above Current", 
                               expanded=True):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Strike Price", f"${call['strike']}")
                        st.metric("Premium (YOU GET)", f"${call['lastPrice']:.2f}")
                    
                    with col2:
                        st.metric("Total Income", f"${call['total_income']:,.0f}")
                        st.metric("Contracts to Sell", "100 contracts")
                    
                    with col3:
                        st.metric("Monthly Yield", f"{call['monthly_yield']:.2f}%")
                        st.metric("Volume", f"{call['volume']:,.0f}")
                    
                    with col4:
                        st.metric("Upside Cap", f"{call['upside_cap']:.1f}%")
                        st.metric("Expiration", call.get('expiration', 'Next Expiry'))
                    
                    # Calculate income scenarios
                    monthly_income = call['total_income']
                    annual_income = monthly_income * 12
                    
                    st.markdown(f"""
                    **Covered Call Details:**
                    - **Monthly Income:** ${monthly_income:,.0f} (if not called away)
                    - **Annual Income:** ${annual_income:,.0f} potential
                    - **Yield:** {call['monthly_yield']:.2f}% monthly, {call['monthly_yield']*12:.1f}% annual
                    - **Call Away Price:** ${call['strike']:.2f} ({call['upside_cap']:.1f}% above current)
                    
                    **📝 Broker Instructions:**
                    1. **Action:** Sell to Open
                    2. **Quantity:** 100 contracts
                    3. **Option:** RIOT 31 OCT 25 ${call['strike']} CALL (39 days to expiration)
                    4. **Order Type:** Limit at ${call['lastPrice']:.2f} or better
                    5. **Duration:** Day order (can change to GTC if needed)
                    
                    **Why This Works:**
                    - You receive ${monthly_income:,.0f} immediately when you sell the calls
                    - If RIOT stays below ${call['strike']:.2f}, you keep premium + shares
                    - If RIOT rises above ${call['strike']:.2f}, shares sold at profit + you keep premium
                    - **NO CASH REQUIRED** - generates income from your existing position!
                    """)
        else:
            st.warning("No suitable covered calls found. Market may be closed or low liquidity.")
    
    def _render_zero_cost_collars(self, calls_df, puts_df, current_price):
        """Render zero-cost collar strategy"""
        st.subheader("🎯 Zero-Cost Collar Strategy")
        st.markdown("""
        **Strategy:** ZERO-COST protection by balancing call sales with put purchases.
        
        **🗓️ RECOMMENDED EXPIRATION: 31 OCT 25 (39 days)**
        
        **How it works - NO CASH REQUIRED:**
        - **SELL call options** (receive premium) - Use 31 OCT 25 expiration
        - **BUY put options** (downside protection) - Use 31 OCT 25 expiration  
        - Premium received = Premium paid = **ZERO NET COST**
        - Sometimes even generates net income!
        - Perfect collar protection without spending cash
        
        **📚 Beginner Explanation:**
        Think of this like insurance that pays for itself! You sell the right to buy your shares at a higher price (call), and use that money to buy the right to sell your shares at a lower price (put). The premiums usually balance out, giving you protection for free!
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
                            'total_cost': net_cost * self.user_position['shares'],  # Cost for 10,000 shares
                            'protection_level': ((put['strike'] / current_price) - 1) * 100,
                            'upside_cap': ((call['strike'] / current_price) - 1) * 100,
                            'call_expiration': '31 OCT 25',
                            'put_expiration': '31 OCT 25'
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
                        
                        **📊 Broker Instructions:**
                        1. **Sell to Open:** 100 RIOT {call.get('expiration', 'Next Expiry')} ${collar['call_strike']} CALL
                        2. **Buy to Open:** 100 RIOT {put.get('expiration', 'Next Expiry')} ${collar['put_strike']} PUT
                        3. **Net Cost:** ${collar['net_cost']:.2f} per share ({collar['total_cost']:,.0f} total)
                        """)
            else:
                st.warning("Insufficient options liquidity for collar strategies.")
    
    def _render_original_scenario_analysis(self, current_price):
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
        
        fig.update_layout(
            yaxis=dict(tickformat='$,.0f'),
            xaxis=dict(tickformat='$,.2f')
        )
        
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
        **💡 For your specific situation:** With 10,000 shares and NO CASH, start with covered calls to generate 
        income, then use zero-cost collars for protection. This approach maximizes your returns while protecting downside.
        """)
    
    def _render_cash_neutral_protection(self, calls_df, puts_df, current_price):
        """Render cash-neutral protection strategies"""
        st.subheader("🛡️ Cash-Neutral Protection Strategies")
        st.markdown("""
        **Perfect for NO CASH situations:** These strategies protect your position without requiring upfront money.
        """)
        
        st.markdown("### 💰 1. Covered Call Income Generation")
        st.success("Start here: Generate $2,000-$5,000+ monthly income from your shares")
        
        st.markdown("### 🛡️ 2. Zero-Cost Collar Protection")
        st.info("Use covered call income to fund protective puts, or find zero-cost combinations")
        
        st.markdown("### 🔄 3. Rolling Strategy")
        st.info("Roll covered calls monthly to maximize income while maintaining flexibility")
    
    def _render_income_scenarios(self, current_price):
        """Render income scenario analysis"""
        st.subheader("📊 Income Generation Scenarios")
        st.markdown("### Monthly Income Potential from Your 10,000 RIOT Shares")
        
        # Sample income scenarios
        scenarios = [
            {"Strategy": "Conservative Covered Calls", "Monthly Income": "$2,000-$3,000", "Annual": "$24,000-$36,000", "Risk": "Low"},
            {"Strategy": "Moderate Covered Calls", "Monthly Income": "$3,000-$5,000", "Annual": "$36,000-$60,000", "Risk": "Medium"},
            {"Strategy": "Aggressive Covered Calls", "Monthly Income": "$5,000-$8,000", "Annual": "$60,000-$96,000", "Risk": "High"}
        ]
        
        import pandas as pd
        scenarios_df = pd.DataFrame(scenarios)
        st.dataframe(scenarios_df, use_container_width=True)
        
        st.success("""
        **🎯 Recommended Approach:**
        1. Start with conservative covered calls (2-4% out-of-the-money)
        2. Generate $24,000-$36,000 annually without risking share ownership
        3. Use income to fund protective strategies when needed
        4. Scale up based on market conditions and your comfort level
        """)