import streamlit as st
import pandas as pd
from utils.unified_data_fetcher import DataFetcher

class OptionsDashboard:
    """Options flow and put-call ratio analysis dashboard"""
    
    def render(self, selected_stocks, options_analyzer, chart_builder):
        """Render the options analysis dashboard"""
        
        st.subheader("⚡ Options Flow Analysis")
        st.write("Monitor put-call ratios and unusual options activity to identify potential volatility.")
        
        # Options analysis for each stock
        for symbol in selected_stocks:
            with st.expander(f"{symbol} Options Analysis", expanded=True):
                self._render_single_stock_options(symbol, options_analyzer, chart_builder)
        
        # Sector-wide options summary
        st.subheader("📊 Sector Options Summary")
        self._render_sector_summary(selected_stocks, options_analyzer)
    
    def _render_single_stock_options(self, symbol, options_analyzer, chart_builder):
        """Render options analysis for a single stock"""
        
        try:
            # Fetch options data
            data_fetcher = DataFetcher()
            calls_df, puts_df = data_fetcher.get_options_data(symbol)
            
            if calls_df is None and puts_df is None:
                st.warning(f"No options data available for {symbol}")
                return
            
            # Get current stock price for context
            stock_info = data_fetcher.get_stock_info(symbol)
            current_price = stock_info.get('current_price', 0)
            
            # Analyze put-call ratio
            pc_analysis = options_analyzer.analyze_put_call_ratio(calls_df, puts_df)
            
            # Display key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric(
                    "Put-Call Ratio",
                    f"{pc_analysis['put_call_ratio']:.2f}",
                    help="Ratio of put volume to call volume. >1.0 indicates bearish sentiment"
                )
            
            with col2:
                st.metric(
                    "Call Volume",
                    f"{pc_analysis['call_volume']:,}",
                    help="Total call options volume"
                )
            
            with col3:
                st.metric(
                    "Put Volume", 
                    f"{pc_analysis['put_volume']:,}",
                    help="Total put options volume"
                )
            
            with col4:
                # Volatility signal with color coding
                signal = pc_analysis['volatility_signal']
                if "Bearish" in signal:
                    st.error(signal)
                elif "Bullish" in signal:
                    st.success(signal)
                else:
                    st.info(signal)
            
            # Put-Call Ratio Chart
            col1, col2 = st.columns(2)
            
            with col1:
                pc_chart = chart_builder.create_put_call_ratio_chart(symbol, pc_analysis)
                if pc_chart:
                    st.plotly_chart(pc_chart, use_container_width=True)
            
            with col2:
                # Options flow metrics
                flow_metrics = options_analyzer.calculate_options_flow_metrics(
                    calls_df, puts_df, current_price
                )
                
                st.subheader("Smart Money Flow")
                smart_money_indicator = flow_metrics.get('smart_money_indicator', 'No Data')
                
                if "Bullish" in smart_money_indicator:
                    st.success(f"📈 {smart_money_indicator}")
                elif "Bearish" in smart_money_indicator:
                    st.error(f"📉 {smart_money_indicator}")
                else:
                    st.info(f"➡️ {smart_money_indicator}")
                
                # Additional flow metrics
                if 'avg_call_iv' in flow_metrics:
                    st.metric("Avg Call IV", f"{flow_metrics['avg_call_iv']:.1%}")
                if 'avg_put_iv' in flow_metrics:
                    st.metric("Avg Put IV", f"{flow_metrics['avg_put_iv']:.1%}")
            
            # Unusual Options Activity
            st.subheader("🚨 Unusual Options Activity")
            unusual_activity = options_analyzer.analyze_unusual_options_activity(calls_df, puts_df)
            
            if unusual_activity:
                activity_df = pd.DataFrame(unusual_activity)
                
                # Format the dataframe for better display
                activity_df['Volume'] = activity_df['volume'].apply(lambda x: f"{x:,}")
                activity_df['Open Interest'] = activity_df['open_interest'].apply(lambda x: f"{x:,}")
                activity_df['Strike'] = activity_df['strike'].apply(lambda x: f"${x:.2f}")
                activity_df['Last Price'] = activity_df['last_price'].apply(lambda x: f"${x:.2f}")
                activity_df['IV'] = activity_df['implied_volatility'].apply(lambda x: f"{x:.1%}")
                
                display_df = activity_df[['type', 'Strike', 'Volume', 'Open Interest', 'Last Price', 'IV']]
                display_df.columns = ['Type', 'Strike', 'Volume', 'Open Interest', 'Last Price', 'IV']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                st.info("No unusual options activity detected")
            
            # Volatility Forecast
            st.subheader("🔮 Volatility Forecast")
            forecast = options_analyzer.get_volatility_forecast(pc_analysis['put_call_ratio'])
            
            col1, col2 = st.columns(2)
            with col1:
                outlook = forecast['volatility_outlook']
                if "High" in outlook:
                    st.error(f"⚠️ {outlook}")
                elif "Low" in outlook:
                    st.success(f"✅ {outlook}")
                else:
                    st.info(f"➡️ {outlook}")
            
            with col2:
                confidence = forecast['confidence']
                st.metric("Confidence", confidence)
            
            # Key factors
            if forecast['key_factors']:
                st.write("**Key Factors:**")
                for factor in forecast['key_factors']:
                    st.write(f"• {factor}")
                    
        except Exception as e:
            st.error(f"Error analyzing options for {symbol}: {str(e)}")
    
    def _render_sector_summary(self, selected_stocks, options_analyzer):
        """Render sector-wide options summary"""
        
        try:
            summary_data = []
            data_fetcher = DataFetcher()
            
            for symbol in selected_stocks:
                try:
                    calls_df, puts_df = data_fetcher.get_options_data(symbol)
                    
                    if calls_df is not None or puts_df is not None:
                        pc_analysis = options_analyzer.analyze_put_call_ratio(calls_df, puts_df)
                        
                        summary_data.append({
                            'Symbol': symbol,
                            'P/C Ratio': pc_analysis['put_call_ratio'],
                            'Call Volume': pc_analysis['call_volume'],
                            'Put Volume': pc_analysis['put_volume'],
                            'Total Volume': pc_analysis['total_volume'],
                            'Volatility Signal': pc_analysis['volatility_signal']
                        })
                        
                except Exception as e:
                    st.warning(f"Could not fetch options data for {symbol}: {str(e)}")
                    continue
            
            if summary_data:
                summary_df = pd.DataFrame(summary_data)
                
                # Format numeric columns
                summary_df['P/C Ratio'] = summary_df['P/C Ratio'].apply(lambda x: f"{x:.2f}")
                summary_df['Call Volume'] = summary_df['Call Volume'].apply(lambda x: f"{x:,}")
                summary_df['Put Volume'] = summary_df['Put Volume'].apply(lambda x: f"{x:,}")
                summary_df['Total Volume'] = summary_df['Total Volume'].apply(lambda x: f"{x:,}")
                
                st.dataframe(summary_df, use_container_width=True, hide_index=True)
                
                # Calculate sector metrics
                numeric_data = pd.DataFrame(summary_data)
                avg_pc_ratio = numeric_data['P/C Ratio'].mean()
                total_sector_volume = numeric_data['Total Volume'].sum()
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Avg P/C Ratio", f"{avg_pc_ratio:.2f}")
                
                with col2:
                    st.metric("Total Options Volume", f"{total_sector_volume:,}")
                
                with col3:
                    # Sector sentiment
                    if avg_pc_ratio > 1.2:
                        st.error("Bearish Sector Sentiment")
                    elif avg_pc_ratio > 0.8:
                        st.warning("Neutral Sector Sentiment")  
                    else:
                        st.success("Bullish Sector Sentiment")
                
                # Options activity insights
                st.subheader("💡 Options Insights")
                
                high_activity_stocks = numeric_data[numeric_data['Total Volume'] > numeric_data['Total Volume'].median()]
                
                if not high_activity_stocks.empty:
                    st.info(f"**High Activity Stocks:** {', '.join(high_activity_stocks['Symbol'].tolist())}")
                
                bearish_sentiment = numeric_data[numeric_data['P/C Ratio'] > 1.0]
                if not bearish_sentiment.empty:
                    st.warning(f"**Bearish Sentiment:** {', '.join(bearish_sentiment['Symbol'].tolist())}")
                
                bullish_sentiment = numeric_data[numeric_data['P/C Ratio'] < 0.7]
                if not bullish_sentiment.empty:
                    st.success(f"**Bullish Sentiment:** {', '.join(bullish_sentiment['Symbol'].tolist())}")
            
            else:
                st.warning("No options data available for sector analysis")
                
        except Exception as e:
            st.error(f"Error in sector options summary: {str(e)}")
