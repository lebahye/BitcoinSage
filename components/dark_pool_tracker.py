import streamlit as st
import pandas as pd
import numpy as np

class DarkPoolTracker:
    """Dark pool activity monitoring component"""
    
    def render(self, selected_stocks, data_fetcher, chart_builder):
        """Render dark pool activity dashboard"""
        
        st.subheader("🌊 Dark Pool Activity Monitor")
        st.write("Track institutional order flow and unusual volume patterns that may indicate smart money movements.")
        
        # Overview metrics
        self._render_overview_metrics(selected_stocks, data_fetcher)
        
        # Individual stock analysis
        for symbol in selected_stocks:
            with st.expander(f"{symbol} Dark Pool Analysis", expanded=True):
                self._render_stock_dark_pool_analysis(symbol, data_fetcher, chart_builder)
        
        # Sector alerts
        st.subheader("🚨 Dark Pool Alerts")
        self._render_dark_pool_alerts(selected_stocks, data_fetcher)
    
    def _render_overview_metrics(self, selected_stocks, data_fetcher):
        """Render overview metrics for dark pool activity"""
        
        st.subheader("📊 Sector Dark Pool Overview")
        
        try:
            sector_metrics = {
                'high_dark_pool_activity': [],
                'unusual_volume': [],
                'price_volume_divergence': [],
                'total_unusual_volume': 0
            }
            
            for symbol in selected_stocks:
                try:
                    indicators = data_fetcher.calculate_dark_pool_indicators(symbol)
                    
                    if indicators:
                        # Check for high dark pool activity indicators
                        volume_ratio = indicators.get('volume_ratio', 0)
                        unusual_volume_pct = indicators.get('unusual_volume_pct', 0)
                        
                        if volume_ratio > 2.0:  # Volume 2x above average
                            sector_metrics['high_dark_pool_activity'].append(symbol)
                        
                        if unusual_volume_pct > 30:  # 30% of days with unusual volume
                            sector_metrics['unusual_volume'].append(symbol)
                        
                        # Price vs VWAP divergence
                        current_price = indicators.get('current_price', 0)
                        vwap = indicators.get('vwap', 0)
                        
                        if vwap > 0 and abs(current_price - vwap) / vwap > 0.02:  # 2% divergence
                            sector_metrics['price_volume_divergence'].append(symbol)
                        
                        sector_metrics['total_unusual_volume'] += indicators.get('current_volume', 0)
                        
                except Exception as e:
                    st.warning(f"Could not analyze {symbol}: {str(e)}")
                    continue
            
            # Display overview metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                high_activity_count = len(sector_metrics['high_dark_pool_activity'])
                st.metric(
                    "High Activity Stocks",
                    high_activity_count,
                    help="Stocks with volume >2x average"
                )
                if sector_metrics['high_dark_pool_activity']:
                    st.caption(f"Symbols: {', '.join(sector_metrics['high_dark_pool_activity'])}")
            
            with col2:
                unusual_count = len(sector_metrics['unusual_volume'])
                st.metric(
                    "Unusual Volume",
                    unusual_count,
                    help="Stocks with frequent volume spikes"
                )
                if sector_metrics['unusual_volume']:
                    st.caption(f"Symbols: {', '.join(sector_metrics['unusual_volume'])}")
            
            with col3:
                divergence_count = len(sector_metrics['price_volume_divergence'])
                st.metric(
                    "Price-VWAP Divergence",
                    divergence_count,
                    help="Stocks trading away from volume-weighted price"
                )
                if sector_metrics['price_volume_divergence']:
                    st.caption(f"Symbols: {', '.join(sector_metrics['price_volume_divergence'])}")
            
            with col4:
                st.metric(
                    "Total Sector Volume",
                    f"{sector_metrics['total_unusual_volume']:,.0f}",
                    help="Combined volume across tracked stocks"
                )
            
        except Exception as e:
            st.error(f"Error calculating sector metrics: {str(e)}")
    
    def _render_stock_dark_pool_analysis(self, symbol, data_fetcher, chart_builder):
        """Render dark pool analysis for individual stock"""
        
        try:
            # Get dark pool indicators
            indicators = data_fetcher.calculate_dark_pool_indicators(symbol)
            
            if not indicators:
                st.warning(f"No dark pool data available for {symbol}")
                return
            
            # Display key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            current_price = indicators.get('current_price', 0)
            vwap = indicators.get('vwap', 0)
            volume_ratio = indicators.get('volume_ratio', 0)
            unusual_volume_pct = indicators.get('unusual_volume_pct', 0)
            
            with col1:
                st.metric("Current Price", f"${current_price:.2f}")
            
            with col2:
                vwap_diff = ((current_price - vwap) / vwap * 100) if vwap > 0 else 0
                st.metric(
                    "VWAP", 
                    f"${vwap:.2f}",
                    f"{vwap_diff:+.2f}%",
                    help="Volume Weighted Average Price"
                )
            
            with col3:
                st.metric(
                    "Volume Ratio",
                    f"{volume_ratio:.1f}x",
                    help="Current volume vs 20-day average"
                )
            
            with col4:
                st.metric(
                    "Unusual Volume %",
                    f"{unusual_volume_pct:.1f}%",
                    help="Percentage of recent days with high volume"
                )
            
            # Volume analysis chart
            volume_data = data_fetcher.get_volume_data([symbol])
            if volume_data and symbol in volume_data:
                fig = chart_builder.create_dark_pool_chart(symbol, volume_data)
                if fig:
                    st.plotly_chart(fig, width='stretch')
            
            # Dark pool activity signals
            st.subheader("🔍 Activity Signals")
            
            signals = []
            
            # Volume-based signals
            if volume_ratio > 3.0:
                signals.append(("🚨 Extremely High Volume", "danger"))
            elif volume_ratio > 2.0:
                signals.append(("⚠️ High Volume Activity", "warning"))
            elif volume_ratio < 0.5:
                signals.append(("📉 Low Volume Period", "info"))
            
            # Price-VWAP signals
            if vwap > 0:
                vwap_deviation = abs(current_price - vwap) / vwap
                if vwap_deviation > 0.05:  # 5% deviation
                    if current_price > vwap:
                        signals.append(("📈 Trading Above VWAP", "success"))
                    else:
                        signals.append(("📉 Trading Below VWAP", "danger"))
            
            # Unusual activity percentage
            if unusual_volume_pct > 40:
                signals.append(("🌊 Frequent Dark Pool Activity", "warning"))
            elif unusual_volume_pct > 20:
                signals.append(("👁️ Moderate Dark Pool Interest", "info"))
            
            # Display signals
            if signals:
                for signal_text, signal_type in signals:
                    if signal_type == "danger":
                        st.error(signal_text)
                    elif signal_type == "warning":
                        st.warning(signal_text)
                    elif signal_type == "success":
                        st.success(signal_text)
                    else:
                        st.info(signal_text)
            else:
                st.info("No significant dark pool signals detected")
            
            # Order flow analysis
            st.subheader("📊 Order Flow Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                # Volume profile
                st.write("**Volume Profile:**")
                avg_volume = indicators.get('avg_volume', 0)
                current_volume = indicators.get('current_volume', 0)
                
                if avg_volume > 0:
                    volume_percentile = max(0, min(100, (current_volume / avg_volume) * 50))
                    st.progress(volume_percentile / 100)
                    st.caption(f"Current: {current_volume:,} vs Avg: {avg_volume:,.0f}")
            
            with col2:
                # Price momentum vs volume
                st.write("**Smart Money Indicator:**")
                
                # Simple smart money calculation
                if volume_ratio > 1.5 and abs(vwap_diff) < 2:
                    smart_money_score = "Accumulation"
                    st.success("🟢 Potential Accumulation")
                elif volume_ratio > 2.0 and vwap_diff < -2:
                    smart_money_score = "Distribution"
                    st.error("🔴 Potential Distribution")
                else:
                    smart_money_score = "Neutral"
                    st.info("⚪ Neutral Activity")
                
                st.caption(f"Status: {smart_money_score}")
            
        except Exception as e:
            st.error(f"Error analyzing dark pool activity for {symbol}: {str(e)}")
    
    def _render_dark_pool_alerts(self, selected_stocks, data_fetcher):
        """Render dark pool alerts and notifications"""
        
        try:
            alerts = []
            
            for symbol in selected_stocks:
                try:
                    indicators = data_fetcher.calculate_dark_pool_indicators(symbol)
                    
                    if not indicators:
                        continue
                    
                    volume_ratio = indicators.get('volume_ratio', 0)
                    unusual_volume_pct = indicators.get('unusual_volume_pct', 0)
                    current_price = indicators.get('current_price', 0)
                    vwap = indicators.get('vwap', 0)
                    
                    # Generate alerts based on thresholds
                    if volume_ratio > 5.0:
                        alerts.append({
                            'symbol': symbol,
                            'type': 'Critical',
                            'message': f'Extreme volume spike: {volume_ratio:.1f}x average',
                            'priority': 1
                        })
                    
                    elif volume_ratio > 3.0:
                        alerts.append({
                            'symbol': symbol,
                            'type': 'High',
                            'message': f'High volume activity: {volume_ratio:.1f}x average',
                            'priority': 2
                        })
                    
                    if vwap > 0:
                        vwap_deviation = abs(current_price - vwap) / vwap
                        if vwap_deviation > 0.1:  # 10% deviation
                            alerts.append({
                                'symbol': symbol,
                                'type': 'Medium',
                                'message': f'Significant VWAP deviation: {vwap_deviation:.1%}',
                                'priority': 3
                            })
                    
                    if unusual_volume_pct > 50:
                        alerts.append({
                            'symbol': symbol,
                            'type': 'Medium',
                            'message': f'Persistent unusual activity: {unusual_volume_pct:.0f}% of recent days',
                            'priority': 3
                        })
                
                except Exception as e:
                    continue
            
            # Sort alerts by priority
            alerts.sort(key=lambda x: x['priority'])
            
            if alerts:
                st.write("Recent dark pool activity alerts:")
                
                for alert in alerts[:10]:  # Show top 10 alerts
                    symbol = alert['symbol']
                    alert_type = alert['type']
                    message = alert['message']
                    
                    if alert_type == 'Critical':
                        st.error(f"🚨 **{symbol}**: {message}")
                    elif alert_type == 'High':
                        st.warning(f"⚠️ **{symbol}**: {message}")
                    else:
                        st.info(f"ℹ️ **{symbol}**: {message}")
            
            else:
                st.success("✅ No significant dark pool alerts at this time")
            
            # Market-wide insights
            if len(selected_stocks) > 1:
                st.subheader("🎯 Market Insights")
                
                # Calculate sector-wide metrics
                total_alerts = len(alerts)
                critical_alerts = len([a for a in alerts if a['type'] == 'Critical'])
                
                col1, col2 = st.columns(2)
                
                with col1:
                    if critical_alerts > 0:
                        st.error(f"⚠️ {critical_alerts} critical alerts detected")
                    elif total_alerts > 3:
                        st.warning(f"📊 {total_alerts} total alerts - increased activity")
                    else:
                        st.success("✅ Normal dark pool activity levels")
                
                with col2:
                    # Smart money flow summary
                    high_volume_stocks = len([symbol for symbol in selected_stocks 
                                            if self._get_volume_ratio(symbol, data_fetcher) > 2.0])
                    
                    if high_volume_stocks > len(selected_stocks) // 2:
                        st.info("🌊 Broad-based institutional interest detected")
                    elif high_volume_stocks > 1:
                        st.info("👀 Selective institutional activity")
                    else:
                        st.info("😴 Quiet institutional activity")
                        
        except Exception as e:
            st.error(f"Error generating dark pool alerts: {str(e)}")
    
    def _get_volume_ratio(self, symbol, data_fetcher):
        """Helper function to get volume ratio for a symbol"""
        try:
            indicators = data_fetcher.calculate_dark_pool_indicators(symbol)
            return indicators.get('volume_ratio', 0) if indicators else 0
        except:
            return 0
