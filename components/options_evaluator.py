import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import yfinance as yf

class OptionsEvaluator:
    """Advanced options evaluation and purchase recommendation system"""
    
    def render(self, selected_stocks, options_analyzer, chart_builder):
        """Render the options evaluation dashboard"""
        
        st.subheader("🎯 Options Purchase Recommendations")
        st.write("AI-powered analysis to identify the best options to buy based on profit potential, risk, and market conditions.")
        
        # Overall recommendations summary
        self._render_recommendations_summary(selected_stocks)
        
        # Detailed analysis for each stock
        for symbol in selected_stocks:
            with st.expander(f"{symbol} - Detailed Options Evaluation", expanded=False):
                self._render_stock_options_evaluation(symbol, options_analyzer, chart_builder)
    
    def _render_recommendations_summary(self, selected_stocks):
        """Render top recommendations across all stocks"""
        
        st.subheader("🏆 Top Options Recommendations")
        
        all_recommendations = []
        
        for symbol in selected_stocks:
            try:
                recommendations = self._analyze_stock_options(symbol)
                for rec in recommendations[:2]:  # Top 2 per stock
                    rec['symbol'] = symbol
                    all_recommendations.append(rec)
            except Exception as e:
                st.warning(f"Could not analyze {symbol}: {str(e)}")
                continue
        
        # Sort by overall score and show top recommendations
        if all_recommendations:
            sorted_recs = sorted(all_recommendations, key=lambda x: x['score'], reverse=True)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**🥇 Best Call Options**")
                call_recs = [r for r in sorted_recs if r['type'] == 'Call'][:3]
                for i, rec in enumerate(call_recs):
                    self._display_recommendation_card(rec, i+1)
            
            with col2:
                st.write("**🥈 Best Put Options**") 
                put_recs = [r for r in sorted_recs if r['type'] == 'Put'][:3]
                for i, rec in enumerate(put_recs):
                    self._display_recommendation_card(rec, i+1)
        else:
            st.info("Unable to generate recommendations at this time. Please try again later.")
    
    def _display_recommendation_card(self, rec, rank):
        """Display a single recommendation card"""
        
        profit_color = "🟢" if rec['profit_potential'] > 30 else "🟡" if rec['profit_potential'] > 15 else "🔴"
        risk_color = "🟢" if rec['risk_level'] == 'Low' else "🟡" if rec['risk_level'] == 'Medium' else "🔴"
        
        st.markdown(f"""
        **#{rank}. {rec['symbol']} {rec['strike']} {rec['type']} - {rec['expiry']}**  
        {profit_color} **Profit Potential:** {rec['profit_potential']:.1f}%  
        {risk_color} **Risk Level:** {rec['risk_level']}  
        💰 **Premium:** ${rec['premium']:.2f}  
        📊 **Score:** {rec['score']:.1f}/10  
        💡 **Why:** {rec['reasoning']}
        """)
        st.divider()
    
    def _render_stock_options_evaluation(self, symbol, options_analyzer, chart_builder):
        """Render detailed options evaluation for a single stock"""
        
        try:
            # Get stock data and options
            ticker = yf.Ticker(symbol)
            stock_info = ticker.info
            current_price = stock_info.get('regularMarketPrice', stock_info.get('currentPrice', 100))
            
            # Get options data
            options_dates = ticker.options
            if not options_dates:
                st.warning(f"No options data available for {symbol}")
                return
            
            # Analyze next 2 expiration dates
            recommendations = self._analyze_stock_options(symbol)
            
            if not recommendations:
                st.warning(f"No recommendations generated for {symbol}")
                return
            
            # Display stock context
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Current Price", f"${current_price:.2f}")
            with col2:
                # Calculate simple momentum
                hist = ticker.history(period='1mo')
                if not hist.empty:
                    momentum = ((current_price - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
                    st.metric("1M Return", f"{momentum:+.1f}%")
            with col3:
                volatility = self._calculate_volatility(ticker)
                st.metric("Volatility", f"{volatility:.1f}%")
            
            # Show recommendations table
            st.subheader(f"📋 {symbol} Options Recommendations")
            
            # Create DataFrame for display
            df_data = []
            for rec in recommendations:
                df_data.append({
                    'Rank': f"#{len(df_data)+1}",
                    'Type': rec['type'],
                    'Strike': f"${rec['strike']}",
                    'Expiry': rec['expiry'],
                    'Premium': f"${rec['premium']:.2f}",
                    'Profit %': f"{rec['profit_potential']:.1f}%",
                    'Risk': rec['risk_level'],
                    'Score': f"{rec['score']:.1f}/10"
                })
            
            if df_data:
                df = pd.DataFrame(df_data)
                st.dataframe(df, width=800)
                
                # Detailed reasoning for top 3
                st.subheader("🔍 Detailed Analysis")
                for i, rec in enumerate(recommendations[:3]):
                    with st.expander(f"#{i+1} - {rec['type']} ${rec['strike']} - {rec['expiry']}", expanded=i==0):
                        
                        col1, col2 = st.columns([2, 1])
                        
                        with col1:
                            st.write("**Investment Thesis:**")
                            st.write(rec['detailed_reasoning'])
                            
                            st.write("**Key Metrics:**")
                            metrics_text = f"""
                            • **Breakeven Price:** ${rec['breakeven']:.2f}
                            • **Max Profit:** {rec['max_profit']:.1f}%
                            • **Probability of Profit:** {rec['prob_profit']:.0f}%
                            • **Days to Expiry:** {rec['days_to_expiry']}
                            • **Liquidity Score:** {rec['liquidity_score']}/10
                            """
                            st.markdown(metrics_text)
                        
                        with col2:
                            # Visual score breakdown
                            st.write("**Score Breakdown:**")
                            st.write(f"Profit Potential: {rec['profit_score']:.1f}/3")
                            st.write(f"Risk Assessment: {rec['risk_score']:.1f}/3") 
                            st.write(f"Liquidity: {rec['liquidity_score']:.1f}/2")
                            st.write(f"Time Value: {rec['time_score']:.1f}/2")
                            
                            # Overall score bar
                            score_pct = rec['score'] / 10
                            st.progress(score_pct)
                            st.write(f"Overall: {rec['score']:.1f}/10")
            
        except Exception as e:
            st.error(f"Error analyzing {symbol} options: {str(e)}")
    
    def _analyze_stock_options(self, symbol):
        """Analyze all options for a stock and return ranked recommendations"""
        
        try:
            ticker = yf.Ticker(symbol)
            stock_info = ticker.info
            current_price = stock_info.get('regularMarketPrice', stock_info.get('currentPrice', 100))
            
            options_dates = ticker.options
            if not options_dates:
                return []
            
            recommendations = []
            
            # Analyze first 3 expiration dates
            for exp_date in options_dates[:3]:
                try:
                    options_chain = ticker.option_chain(exp_date)
                    calls_df = options_chain.calls
                    puts_df = options_chain.puts
                    
                    # Calculate days to expiry
                    exp_datetime = datetime.strptime(exp_date, '%Y-%m-%d')
                    days_to_expiry = (exp_datetime - datetime.now()).days
                    
                    if days_to_expiry < 1:
                        continue
                    
                    # Analyze calls
                    for _, call in calls_df.iterrows():
                        if call['volume'] > 0 and call['openInterest'] > 10:  # Basic liquidity filter
                            rec = self._evaluate_option(call, current_price, days_to_expiry, 'Call', exp_date)
                            if rec['score'] > 4:  # Only include decent options
                                recommendations.append(rec)
                    
                    # Analyze puts
                    for _, put in puts_df.iterrows():
                        if put['volume'] > 0 and put['openInterest'] > 10:
                            rec = self._evaluate_option(put, current_price, days_to_expiry, 'Put', exp_date)
                            if rec['score'] > 4:
                                recommendations.append(rec)
                                
                except Exception:
                    continue
            
            # Sort by score and return top recommendations
            recommendations.sort(key=lambda x: x['score'], reverse=True)
            return recommendations[:10]  # Top 10 recommendations
            
        except Exception:
            return []
    
    def _evaluate_option(self, option, current_price, days_to_expiry, option_type, exp_date):
        """Evaluate a single option and return recommendation"""
        
        strike = option['strike']
        premium = option['lastPrice']
        volume = option.get('volume', 0)
        open_interest = option.get('openInterest', 0)
        
        # Calculate key metrics
        if option_type == 'Call':
            breakeven = strike + premium
            intrinsic_value = max(0, current_price - strike)
            profit_target_price = strike + premium * 2  # 100% profit target
            profit_potential = ((profit_target_price - strike - premium) / premium) * 100
        else:  # Put
            breakeven = strike - premium
            intrinsic_value = max(0, strike - current_price)
            profit_target_price = strike - premium * 2
            profit_potential = ((strike - profit_target_price - premium) / premium) * 100
        
        time_value = premium - intrinsic_value
        
        # Calculate probability of profit (simplified)
        distance_to_breakeven = abs(current_price - breakeven) / current_price
        prob_profit = max(20, 80 - (distance_to_breakeven * 200))  # Simplified calculation
        
        # Scoring system (out of 10)
        profit_score = min(3, profit_potential / 20)  # Max 3 points for 60%+ profit potential
        
        # Risk scoring (lower risk = higher score)
        if distance_to_breakeven < 0.05:  # Within 5%
            risk_score = 3
            risk_level = 'Low'
        elif distance_to_breakeven < 0.15:  # Within 15%
            risk_score = 2
            risk_level = 'Medium'
        else:
            risk_score = 1
            risk_level = 'High'
        
        # Liquidity scoring
        liquidity_score = min(2, (volume + open_interest/10) / 50)  # Max 2 points
        
        # Time value scoring
        if days_to_expiry < 30:
            time_score = 1  # Less time value
        elif days_to_expiry < 60:
            time_score = 2
        else:
            time_score = 1.5  # Too much time decay risk
        
        overall_score = profit_score + risk_score + liquidity_score + time_score
        
        # Generate reasoning
        reasoning = self._generate_reasoning(option_type, strike, current_price, profit_potential, risk_level, days_to_expiry)
        detailed_reasoning = self._generate_detailed_reasoning(option_type, strike, current_price, premium, profit_potential, days_to_expiry, volume, open_interest)
        
        return {
            'type': option_type,
            'strike': strike,
            'expiry': exp_date,
            'premium': premium,
            'profit_potential': profit_potential,
            'risk_level': risk_level,
            'score': overall_score,
            'reasoning': reasoning,
            'detailed_reasoning': detailed_reasoning,
            'breakeven': breakeven,
            'max_profit': profit_potential,
            'prob_profit': prob_profit,
            'days_to_expiry': days_to_expiry,
            'liquidity_score': liquidity_score * 5,  # Convert to 0-10 scale
            'profit_score': profit_score,
            'risk_score': risk_score,
            'time_score': time_score
        }
    
    def _generate_reasoning(self, option_type, strike, current_price, profit_potential, risk_level, days_to_expiry):
        """Generate concise reasoning for the recommendation"""
        
        distance_pct = abs(strike - current_price) / current_price * 100
        
        if option_type == 'Call':
            if strike <= current_price:
                return f"ITM call with {profit_potential:.0f}% upside potential, {risk_level.lower()} risk"
            else:
                return f"OTM call needs {distance_pct:.1f}% move up, high reward potential"
        else:
            if strike >= current_price:
                return f"ITM put with {profit_potential:.0f}% profit potential, {risk_level.lower()} risk"
            else:
                return f"OTM put needs {distance_pct:.1f}% move down, good hedging play"
    
    def _generate_detailed_reasoning(self, option_type, strike, current_price, premium, profit_potential, days_to_expiry, volume, open_interest):
        """Generate detailed reasoning for the recommendation"""
        
        moneyness = "in-the-money" if (option_type == 'Call' and strike <= current_price) or (option_type == 'Put' and strike >= current_price) else "out-of-the-money"
        
        liquidity_desc = "excellent" if (volume + open_interest) > 100 else "moderate" if (volume + open_interest) > 50 else "limited"
        
        time_desc = "short-term" if days_to_expiry < 30 else "medium-term" if days_to_expiry < 60 else "long-term"
        
        reasoning = f"""
        This {moneyness} {option_type.lower()} option offers {profit_potential:.1f}% profit potential with {time_desc} expiration 
        in {days_to_expiry} days. The option has {liquidity_desc} liquidity with {volume} volume and {open_interest} open interest.
        
        At current premium of ${premium:.2f}, this represents good value given the underlying stock's volatility and recent momentum.
        The risk-reward profile is favorable for traders expecting {"upward" if option_type == "Call" else "downward"} movement 
        in the underlying stock over the next {"few weeks" if days_to_expiry < 45 else "month or two"}.
        
        Consider this position as part of a diversified options strategy, with proper position sizing based on your risk tolerance.
        """
        
        return reasoning.strip()
    
    def _calculate_volatility(self, ticker):
        """Calculate simple volatility measure"""
        try:
            hist = ticker.history(period='1mo')
            if not hist.empty:
                returns = hist['Close'].pct_change().dropna()
                volatility = returns.std() * np.sqrt(252) * 100  # Annualized volatility
                return volatility
        except:
            pass
        return 25.0  # Default volatility