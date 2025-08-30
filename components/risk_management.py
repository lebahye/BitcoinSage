import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import yfinance as yf
from datetime import datetime, timedelta

class RiskManagement:
    """Risk management and position sizing tools"""
    
    def __init__(self):
        self.risk_data = {}
    
    def render(self, selected_stocks, stock_names):
        """Render risk management dashboard"""
        
        st.subheader("⚠️ Risk Management & Position Sizing")
        st.write("Calculate optimal position sizes, risk metrics, and portfolio management guidelines.")
        
        # Portfolio input section
        portfolio_value = st.sidebar.number_input(
            "Portfolio Value ($)",
            min_value=1000,
            max_value=10000000,
            value=100000,
            step=1000,
            help="Enter your total portfolio value for position sizing calculations"
        )
        
        risk_per_trade = st.sidebar.slider(
            "Risk Per Trade (%)",
            min_value=0.5,
            max_value=5.0,
            value=2.0,
            step=0.1,
            help="Maximum percentage of portfolio to risk per trade"
        )
        
        # Risk overview
        self._render_risk_overview(selected_stocks, portfolio_value, risk_per_trade)
        
        # Individual stock risk analysis
        self._render_individual_risk_analysis(selected_stocks, stock_names, portfolio_value, risk_per_trade)
        
        # Portfolio optimization
        self._render_portfolio_optimization(selected_stocks, stock_names, portfolio_value)
        
        # Risk alerts
        self._render_risk_alerts(selected_stocks)
    
    def _render_risk_overview(self, selected_stocks, portfolio_value, risk_per_trade):
        """Render risk overview section"""
        st.subheader("📊 Portfolio Risk Overview")
        
        try:
            # Calculate sector-wide risk metrics
            risk_metrics = self._calculate_sector_risk_metrics(selected_stocks)
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                sector_volatility = risk_metrics.get('avg_volatility', 0)
                st.metric(
                    "Sector Volatility", 
                    f"{sector_volatility:.1f}%",
                    help="Average annualized volatility of mining stocks"
                )
                if sector_volatility > 80:
                    st.error("Very High Risk")
                elif sector_volatility > 60:
                    st.warning("High Risk")
                elif sector_volatility > 40:
                    st.info("Moderate Risk")
                else:
                    st.success("Lower Risk")
            
            with col2:
                max_drawdown = risk_metrics.get('max_drawdown', 0)
                st.metric(
                    "Max Drawdown",
                    f"{max_drawdown:.1f}%",
                    help="Maximum peak-to-trough decline"
                )
            
            with col3:
                sharpe_ratio = risk_metrics.get('sharpe_ratio', 0)
                st.metric(
                    "Sharpe Ratio",
                    f"{sharpe_ratio:.2f}",
                    help="Risk-adjusted return measure"
                )
            
            with col4:
                correlation = risk_metrics.get('avg_correlation', 0)
                st.metric(
                    "Avg Correlation",
                    f"{correlation:.2f}",
                    help="Average correlation between stocks"
                )
            
            # Risk capacity recommendations
            st.subheader("💡 Risk Capacity Recommendations")
            
            recommended_allocation = self._calculate_recommended_allocation(
                portfolio_value, risk_per_trade, sector_volatility
            )
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("**Conservative Allocation:**")
                st.write(f"• Total Crypto/Mining: {recommended_allocation['conservative']:.1f}%")
                st.write(f"• Per Stock: {recommended_allocation['conservative']/len(selected_stocks):.1f}%")
                st.write(f"• Max $ Amount: ${portfolio_value * recommended_allocation['conservative']/100:,.0f}")
            
            with col2:
                st.write("**Aggressive Allocation:**")
                st.write(f"• Total Crypto/Mining: {recommended_allocation['aggressive']:.1f}%")
                st.write(f"• Per Stock: {recommended_allocation['aggressive']/len(selected_stocks):.1f}%")
                st.write(f"• Max $ Amount: ${portfolio_value * recommended_allocation['aggressive']/100:,.0f}")
        
        except Exception as e:
            st.error(f"Error calculating risk overview: {str(e)}")
    
    def _render_individual_risk_analysis(self, selected_stocks, stock_names, portfolio_value, risk_per_trade):
        """Render individual stock risk analysis"""
        st.subheader("🎯 Individual Stock Risk Analysis")
        
        risk_data = []
        
        for symbol in selected_stocks:
            try:
                metrics = self._calculate_stock_risk_metrics(symbol)
                position_size = self._calculate_position_size(
                    symbol, portfolio_value, risk_per_trade, metrics
                )
                
                risk_data.append({
                    'Symbol': symbol,
                    'Company': stock_names.get(symbol, symbol)[:20],
                    'Volatility': f"{metrics.get('volatility', 0):.1f}%",
                    'Max Drawdown': f"{metrics.get('max_drawdown', 0):.1f}%",
                    'Beta': f"{metrics.get('beta', 0):.2f}",
                    'Position Size': f"${position_size.get('dollar_amount', 0):,.0f}",
                    'Shares': f"{position_size.get('shares', 0):.0f}",
                    'Stop Loss': f"${position_size.get('stop_loss', 0):.2f}",
                    'Risk Score': metrics.get('risk_score', 'N/A')
                })
                
            except Exception as e:
                continue
        
        if risk_data:
            df = pd.DataFrame(risk_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Risk distribution chart
            st.subheader("📈 Risk Distribution")
            
            volatilities = [float(item['Volatility'].rstrip('%')) for item in risk_data]
            symbols = [item['Symbol'] for item in risk_data]
            
            fig = px.bar(
                x=symbols,
                y=volatilities,
                title="Stock Volatility Comparison",
                labels={'x': 'Stock', 'y': 'Annualized Volatility (%)'},
                color=volatilities,
                color_continuous_scale='RdYlGn_r'
            )
            
            fig.update_layout(
                template='plotly_dark',
                height=400,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            st.plotly_chart(fig, use_container_width=True)
    
    def _render_portfolio_optimization(self, selected_stocks, stock_names, portfolio_value):
        """Render portfolio optimization section"""
        st.subheader("🎯 Portfolio Optimization")
        
        try:
            # Calculate optimal weights
            optimal_weights = self._calculate_optimal_weights(selected_stocks)
            
            if optimal_weights:
                col1, col2 = st.columns(2)
                
                with col1:
                    # Optimal allocation pie chart
                    fig = px.pie(
                        values=list(optimal_weights.values()),
                        names=list(optimal_weights.keys()),
                        title="Optimal Portfolio Allocation",
                        color_discrete_sequence=px.colors.qualitative.Set3
                    )
                    
                    fig.update_layout(
                        template='plotly_dark',
                        height=400,
                        margin=dict(l=0, r=0, t=40, b=0)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.write("**Optimal Allocation Table:**")
                    
                    allocation_data = []
                    for symbol, weight in optimal_weights.items():
                        dollar_amount = portfolio_value * weight
                        allocation_data.append({
                            'Stock': symbol,
                            'Weight': f"{weight:.1%}",
                            'Amount': f"${dollar_amount:,.0f}"
                        })
                    
                    allocation_df = pd.DataFrame(allocation_data)
                    st.dataframe(allocation_df, use_container_width=True, hide_index=True)
                    
                    # Portfolio statistics
                    portfolio_stats = self._calculate_portfolio_stats(selected_stocks, optimal_weights)
                    
                    st.write("**Portfolio Statistics:**")
                    st.write(f"• Expected Return: {portfolio_stats.get('expected_return', 0):.1f}%")
                    st.write(f"• Portfolio Volatility: {portfolio_stats.get('portfolio_volatility', 0):.1f}%")
                    st.write(f"• Sharpe Ratio: {portfolio_stats.get('sharpe_ratio', 0):.2f}")
                    st.write(f"• Diversification Ratio: {portfolio_stats.get('diversification_ratio', 0):.2f}")
            
        except Exception as e:
            st.error(f"Error in portfolio optimization: {str(e)}")
    
    def _render_risk_alerts(self, selected_stocks):
        """Render risk alerts section"""
        st.subheader("🚨 Risk Alerts")
        
        alerts = []
        
        for symbol in selected_stocks:
            try:
                stock_alerts = self._check_stock_risk_alerts(symbol)
                alerts.extend(stock_alerts)
            except Exception as e:
                continue
        
        if alerts:
            st.write("Current risk alerts for your watchlist:")
            
            for alert in alerts:
                if alert['severity'] == 'High':
                    st.error(f"🚨 **{alert['symbol']}**: {alert['message']}")
                elif alert['severity'] == 'Medium':
                    st.warning(f"⚠️ **{alert['symbol']}**: {alert['message']}")
                else:
                    st.info(f"ℹ️ **{alert['symbol']}**: {alert['message']}")
        else:
            st.success("✅ No significant risk alerts at this time")
        
        # Risk management tips
        with st.expander("💡 Risk Management Tips", expanded=False):
            st.write("""
            **Position Sizing Guidelines:**
            • Never risk more than 2% of portfolio on a single trade
            • Use stop losses 10-15% below entry price
            • Consider volatility when sizing positions
            
            **Diversification Rules:**
            • Don't put more than 20% in crypto/mining sector
            • Spread risk across 4-6 different mining stocks
            • Consider correlation between holdings
            
            **Risk Monitoring:**
            • Review positions when stocks move 15%+ in either direction
            • Rebalance portfolio quarterly
            • Adjust position sizes based on changing volatility
            
            **Market Conditions:**
            • Reduce position sizes during high VIX periods
            • Increase cash during bear market confirmation
            • Use trailing stops during strong uptrends
            """)
    
    def _calculate_sector_risk_metrics(self, selected_stocks):
        """Calculate sector-wide risk metrics"""
        try:
            volatilities = []
            drawdowns = []
            returns_data = []
            
            for symbol in selected_stocks:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='1y')
                
                if not hist.empty and len(hist) > 30:
                    # Volatility
                    returns = hist['Close'].pct_change().dropna()
                    volatility = returns.std() * np.sqrt(252) * 100
                    volatilities.append(volatility)
                    
                    # Max drawdown
                    peak = hist['Close'].expanding().max()
                    drawdown = ((hist['Close'] - peak) / peak * 100).min()
                    drawdowns.append(abs(drawdown))
                    
                    # Store returns for correlation
                    returns_data.append(returns)
            
            # Calculate correlations
            correlations = []
            if len(returns_data) > 1:
                for i in range(len(returns_data)):
                    for j in range(i+1, len(returns_data)):
                        if len(returns_data[i]) > 30 and len(returns_data[j]) > 30:
                            # Align data
                            common_dates = returns_data[i].index.intersection(returns_data[j].index)
                            if len(common_dates) > 30:
                                corr = np.corrcoef(
                                    returns_data[i].loc[common_dates], 
                                    returns_data[j].loc[common_dates]
                                )[0, 1]
                                if not np.isnan(corr):
                                    correlations.append(corr)
            
            # Calculate Sharpe ratio (simplified)
            avg_returns = [r.mean() * 252 * 100 for r in returns_data if len(r) > 30]
            avg_return = np.mean(avg_returns) if avg_returns else 0
            avg_volatility = np.mean(volatilities) if volatilities else 0
            sharpe_ratio = avg_return / avg_volatility if avg_volatility > 0 else 0
            
            return {
                'avg_volatility': np.mean(volatilities) if volatilities else 0,
                'max_drawdown': np.mean(drawdowns) if drawdowns else 0,
                'avg_correlation': np.mean(correlations) if correlations else 0,
                'sharpe_ratio': sharpe_ratio
            }
            
        except Exception as e:
            return {
                'avg_volatility': 0,
                'max_drawdown': 0,
                'avg_correlation': 0,
                'sharpe_ratio': 0
            }
    
    def _calculate_stock_risk_metrics(self, symbol):
        """Calculate risk metrics for individual stock"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1y')
            
            if hist.empty:
                return {}
            
            # Basic calculations
            returns = hist['Close'].pct_change().dropna()
            
            # Volatility (annualized)
            volatility = returns.std() * np.sqrt(252) * 100
            
            # Max drawdown
            peak = hist['Close'].expanding().max()
            drawdown = ((hist['Close'] - peak) / peak * 100).min()
            max_drawdown = abs(drawdown)
            
            # Beta (vs S&P 500)
            spy = yf.Ticker("SPY")
            spy_hist = spy.history(period='1y')
            
            beta = 1.0  # Default
            if not spy_hist.empty:
                spy_returns = spy_hist['Close'].pct_change().dropna()
                
                # Align dates
                common_dates = returns.index.intersection(spy_returns.index)
                if len(common_dates) > 30:
                    stock_aligned = returns.loc[common_dates]
                    spy_aligned = spy_returns.loc[common_dates]
                    
                    if spy_aligned.var() > 0:
                        beta = np.cov(stock_aligned, spy_aligned)[0, 1] / spy_aligned.var()
            
            # Risk score (1-10, 10 being highest risk)
            risk_score = min(10, max(1, (volatility / 10) + (max_drawdown / 10)))
            
            return {
                'volatility': volatility,
                'max_drawdown': max_drawdown,
                'beta': beta,
                'risk_score': f"{risk_score:.1f}/10"
            }
            
        except Exception as e:
            return {}
    
    def _calculate_position_size(self, symbol, portfolio_value, risk_per_trade, metrics):
        """Calculate optimal position size"""
        try:
            # Get current price
            ticker = yf.Ticker(symbol)
            info = ticker.info
            current_price = info.get('currentPrice', 0)
            
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            if current_price <= 0:
                return {'dollar_amount': 0, 'shares': 0, 'stop_loss': 0}
            
            # Risk amount
            risk_amount = portfolio_value * (risk_per_trade / 100)
            
            # Calculate stop loss level (based on volatility)
            volatility = metrics.get('volatility', 50) / 100  # Convert to decimal
            stop_loss_percent = max(0.10, min(0.20, volatility * 0.5))  # 10-20% stop
            stop_loss_price = current_price * (1 - stop_loss_percent)
            
            # Position size calculation
            risk_per_share = current_price - stop_loss_price
            shares = risk_amount / risk_per_share if risk_per_share > 0 else 0
            dollar_amount = shares * current_price
            
            # Apply volatility adjustment
            volatility_adjustment = 1.0
            if volatility > 0.8:  # Very high volatility
                volatility_adjustment = 0.5
            elif volatility > 0.6:  # High volatility
                volatility_adjustment = 0.7
            elif volatility > 0.4:  # Moderate volatility
                volatility_adjustment = 0.85
            
            shares *= volatility_adjustment
            dollar_amount *= volatility_adjustment
            
            return {
                'dollar_amount': dollar_amount,
                'shares': shares,
                'stop_loss': stop_loss_price
            }
            
        except Exception as e:
            return {'dollar_amount': 0, 'shares': 0, 'stop_loss': 0}
    
    def _calculate_recommended_allocation(self, portfolio_value, risk_per_trade, sector_volatility):
        """Calculate recommended allocation percentages"""
        
        # Base allocation
        base_conservative = 15.0  # 15% for conservative
        base_aggressive = 30.0    # 30% for aggressive
        
        # Adjust based on sector volatility
        if sector_volatility > 80:
            conservative_adj = -5.0
            aggressive_adj = -10.0
        elif sector_volatility > 60:
            conservative_adj = -2.5
            aggressive_adj = -5.0
        elif sector_volatility < 40:
            conservative_adj = 2.5
            aggressive_adj = 5.0
        else:
            conservative_adj = 0
            aggressive_adj = 0
        
        # Adjust based on portfolio size
        if portfolio_value > 1000000:
            size_adj = 2.5  # Larger portfolios can take more risk
        elif portfolio_value < 50000:
            size_adj = -2.5  # Smaller portfolios should be more careful
        else:
            size_adj = 0
        
        conservative = max(5.0, base_conservative + conservative_adj + size_adj)
        aggressive = max(10.0, base_aggressive + aggressive_adj + size_adj)
        
        return {
            'conservative': conservative,
            'aggressive': aggressive
        }
    
    def _calculate_optimal_weights(self, selected_stocks):
        """Calculate optimal portfolio weights using equal risk contribution"""
        try:
            risk_scores = []
            symbols = []
            
            for symbol in selected_stocks:
                metrics = self._calculate_stock_risk_metrics(symbol)
                volatility = metrics.get('volatility', 50)
                
                if volatility > 0:
                    # Inverse volatility weighting
                    risk_scores.append(1 / volatility)
                    symbols.append(symbol)
            
            if not risk_scores:
                # Equal weighting fallback
                weight = 1.0 / len(selected_stocks)
                return {symbol: weight for symbol in selected_stocks}
            
            # Normalize weights
            total_score = sum(risk_scores)
            weights = {symbols[i]: risk_scores[i] / total_score for i in range(len(symbols))}
            
            return weights
            
        except Exception as e:
            # Equal weighting fallback
            weight = 1.0 / len(selected_stocks)
            return {symbol: weight for symbol in selected_stocks}
    
    def _calculate_portfolio_stats(self, selected_stocks, weights):
        """Calculate portfolio statistics"""
        try:
            returns_data = []
            expected_returns = []
            
            for symbol in selected_stocks:
                if symbol in weights:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='6mo')
                    
                    if not hist.empty:
                        returns = hist['Close'].pct_change().dropna()
                        returns_data.append(returns)
                        expected_returns.append(returns.mean() * 252 * 100)  # Annualized
            
            if not returns_data:
                return {}
            
            # Portfolio expected return
            portfolio_return = sum(weights.get(selected_stocks[i], 0) * expected_returns[i] 
                                 for i in range(len(expected_returns)))
            
            # Portfolio volatility (simplified)
            weighted_vols = []
            for i, symbol in enumerate(selected_stocks):
                if i < len(returns_data) and symbol in weights:
                    vol = returns_data[i].std() * np.sqrt(252) * 100
                    weighted_vols.append(weights[symbol] * vol)
            
            portfolio_volatility = sum(weighted_vols) if weighted_vols else 0
            
            # Sharpe ratio
            sharpe_ratio = portfolio_return / portfolio_volatility if portfolio_volatility > 0 else 0
            
            # Diversification ratio (simplified)
            avg_correlation = 0.7  # Assumed average correlation for mining stocks
            diversification_ratio = 1 / np.sqrt(avg_correlation) if avg_correlation > 0 else 1
            
            return {
                'expected_return': portfolio_return,
                'portfolio_volatility': portfolio_volatility,
                'sharpe_ratio': sharpe_ratio,
                'diversification_ratio': diversification_ratio
            }
            
        except Exception as e:
            return {}
    
    def _check_stock_risk_alerts(self, symbol):
        """Check for risk alerts on individual stock"""
        alerts = []
        
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if hist.empty:
                return alerts
            
            current_price = hist['Close'].iloc[-1]
            
            # Volatility alert
            returns = hist['Close'].pct_change().dropna()
            if len(returns) > 10:
                recent_vol = returns.tail(5).std() * np.sqrt(252) * 100
                
                if recent_vol > 100:
                    alerts.append({
                        'symbol': symbol,
                        'severity': 'High',
                        'message': f'Extreme volatility detected: {recent_vol:.1f}% annualized'
                    })
                elif recent_vol > 80:
                    alerts.append({
                        'symbol': symbol,
                        'severity': 'Medium',
                        'message': f'High volatility: {recent_vol:.1f}% annualized'
                    })
            
            # Drawdown alert
            peak = hist['Close'].max()
            current_drawdown = (current_price - peak) / peak * 100
            
            if current_drawdown < -30:
                alerts.append({
                    'symbol': symbol,
                    'severity': 'High',
                    'message': f'Large drawdown: {current_drawdown:.1f}% from recent high'
                })
            elif current_drawdown < -20:
                alerts.append({
                    'symbol': symbol,
                    'severity': 'Medium',
                    'message': f'Moderate drawdown: {current_drawdown:.1f}% from recent high'
                })
            
            # Volume alert
            if 'Volume' in hist.columns:
                avg_volume = hist['Volume'].mean()
                recent_volume = hist['Volume'].iloc[-1]
                
                if recent_volume > avg_volume * 3:
                    alerts.append({
                        'symbol': symbol,
                        'severity': 'Medium',
                        'message': f'Unusual volume: {recent_volume/avg_volume:.1f}x average'
                    })
        
        except Exception as e:
            pass
        
        return alerts
    
    def get_risk_data(self, selected_stocks, portfolio_value=100000, risk_per_trade=2.0):
        """Get risk data for integration with weekly outlook"""
        risk_data = {}
        
        # Calculate sector risk
        sector_metrics = self._calculate_sector_risk_metrics(selected_stocks)
        
        risk_data['sector'] = {
            'volatility': sector_metrics.get('avg_volatility', 0),
            'risk_level': 'High' if sector_metrics.get('avg_volatility', 0) > 70 else 
                         'Moderate' if sector_metrics.get('avg_volatility', 0) > 50 else 'Low',
            'recommended_allocation': self._calculate_recommended_allocation(
                portfolio_value, risk_per_trade, sector_metrics.get('avg_volatility', 0)
            )
        }
        
        # Calculate individual stock risk
        for symbol in selected_stocks:
            try:
                metrics = self._calculate_stock_risk_metrics(symbol)
                position_size = self._calculate_position_size(
                    symbol, portfolio_value, risk_per_trade, metrics
                )
                
                risk_data[symbol] = {
                    'volatility': metrics.get('volatility', 0),
                    'risk_score': float(metrics.get('risk_score', '5.0').split('/')[0]),
                    'position_size': position_size.get('dollar_amount', 0),
                    'stop_loss': position_size.get('stop_loss', 0),
                    'risk_adjustment': -1 if metrics.get('volatility', 0) > 80 else 
                                     0 if metrics.get('volatility', 0) > 50 else 1
                }
            except:
                risk_data[symbol] = {
                    'volatility': 50,
                    'risk_score': 5.0,
                    'position_size': 0,
                    'stop_loss': 0,
                    'risk_adjustment': 0
                }
        
        return risk_data