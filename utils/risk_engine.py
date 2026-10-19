import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st
from scipy.stats import norm
from utils.market_data import fetch_daily_closes, align_frame, beta_corr, aligned_returns

class RiskEngine:
    """Professional Portfolio Risk Engine - VaR, CVaR, Stress Testing, Monte Carlo"""
    
    def __init__(self):
        self.cache = {}
    
    def calculate_var_cvar(self, portfolio_data, confidence_level=0.95, time_horizon_days=1):
        """
        Calculate Value at Risk (VaR) and Conditional VaR (CVaR)
        VaR = Maximum expected loss at confidence level
        CVaR = Average loss beyond VaR (worst-case scenario)
        """
        try:
            returns = portfolio_data.pct_change().dropna()
            
            if returns.empty or len(returns) < 30:
                return {}
            
            portfolio_returns = returns.mean(axis=1)
            
            var_percentile = (1 - confidence_level) * 100
            var = np.percentile(portfolio_returns, var_percentile)
            
            losses_beyond_var = portfolio_returns[portfolio_returns <= var]
            cvar = losses_beyond_var.mean() if len(losses_beyond_var) > 0 else var
            
            portfolio_value = portfolio_data.iloc[-1].sum()
            var_dollar = var * portfolio_value * np.sqrt(time_horizon_days)
            cvar_dollar = cvar * portfolio_value * np.sqrt(time_horizon_days)
            
            daily_volatility = portfolio_returns.std()
            annualized_volatility = daily_volatility * np.sqrt(252)
            
            z_score = norm.ppf(1 - confidence_level)
            parametric_var = -z_score * daily_volatility * np.sqrt(time_horizon_days)
            parametric_var_dollar = parametric_var * portfolio_value
            
            worst_day = portfolio_returns.min()
            worst_day_dollar = worst_day * portfolio_value
            best_day = portfolio_returns.max()
            best_day_dollar = best_day * portfolio_value
            
            return {
                # scale % to the chosen horizon too (previously only $ was scaled)
                'var_pct': float(var * 100 * np.sqrt(time_horizon_days)),
                'cvar_pct': float(cvar * 100 * np.sqrt(time_horizon_days)),
                'var_dollar': float(var_dollar),
                'cvar_dollar': float(cvar_dollar),
                'parametric_var_pct': float(parametric_var * 100),
                'parametric_var_dollar': float(parametric_var_dollar),
                'confidence_level': confidence_level,
                'time_horizon_days': time_horizon_days,
                'portfolio_value': float(portfolio_value),
                'daily_volatility': float(daily_volatility * 100),
                'annualized_volatility': float(annualized_volatility * 100),
                'worst_day_pct': float(worst_day * 100),
                'worst_day_dollar': float(worst_day_dollar),
                'best_day_pct': float(best_day * 100),
                'best_day_dollar': float(best_day_dollar),
                'interpretation': self._interpret_var(var * 100, confidence_level)
            }
            
        except Exception as e:
            st.error(f"Error calculating VaR/CVaR: {str(e)}")
            return {}
    
    def _interpret_var(self, var_pct, confidence_level):
        """Interpret VaR results for users"""
        conf_pct = int(confidence_level * 100)
        
        if abs(var_pct) > 10:
            return f"HIGH RISK: {conf_pct}% chance you won't lose more than {abs(var_pct):.1f}% in a day. Your portfolio is very volatile!"
        elif abs(var_pct) > 5:
            return f"MODERATE RISK: {conf_pct}% chance you won't lose more than {abs(var_pct):.1f}% in a day. Normal mining stock volatility."
        else:
            return f"LOW RISK: {conf_pct}% chance you won't lose more than {abs(var_pct):.1f}% in a day. Portfolio is relatively stable."
    
    def calculate_correlation_matrix(self, symbols, period='3mo'):
        """
        Calculate correlation matrix between stocks
        Shows which stocks move together (diversification analysis)
        """
        try:
            data_dict = {}
            
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period)
                
                if not hist.empty:
                    data_dict[symbol] = hist['Close']
            
            if not data_dict:
                return {}
            
            df = pd.DataFrame(data_dict)
            
            returns = df.pct_change().dropna()
            correlation_matrix = returns.corr()
            
            avg_correlation = correlation_matrix.values[np.triu_indices_from(correlation_matrix.values, k=1)].mean()
            
            highly_correlated_pairs = []
            for i in range(len(correlation_matrix)):
                for j in range(i+1, len(correlation_matrix)):
                    corr = correlation_matrix.iloc[i, j]
                    if abs(corr) > 0.7:
                        highly_correlated_pairs.append({
                            'stock1': correlation_matrix.index[i],
                            'stock2': correlation_matrix.columns[j],
                            'correlation': float(corr)
                        })
            
            if avg_correlation > 0.8:
                diversification = "POOR - Stocks move together, high concentration risk"
            elif avg_correlation > 0.6:
                diversification = "MODERATE - Some diversification, but still correlated"
            else:
                diversification = "GOOD - Stocks show independent movements"
            
            return {
                'correlation_matrix': correlation_matrix,
                'avg_correlation': float(avg_correlation),
                'highly_correlated_pairs': highly_correlated_pairs,
                'diversification_score': diversification,
                'returns_data': returns
            }
            
        except Exception as e:
            st.error(f"Error calculating correlation matrix: {str(e)}")
            return {}
    
    def run_stress_test(self, portfolio_data, symbols, notional=10_000.0):
        """
        Stress test: "if Bitcoin falls X%, how much would an equal-weight basket
        of these stocks be expected to fall?"  Uses the basket's measured daily
        beta to BTC (1y, aligned on the stock calendar).  If beta cannot be
        measured we return {'error': ...} — never a made-up beta.
        Dollar figures are per `notional` invested (default $10,000).
        """
        try:
            closes = fetch_daily_closes(tuple(list(symbols) + ["BTC-USD"]), "1y")
            if closes.empty or "BTC-USD" not in closes.columns:
                return {'error': "Bitcoin price history unavailable from Yahoo Finance."}
            stock_cols = [c for c in symbols if c in closes.columns]
            if not stock_cols:
                return {'error': "No stock price history available."}
            aligned = align_frame(closes[stock_cols + ["BTC-USD"]])
            basket = aligned[stock_cols].pct_change(fill_method=None).mean(axis=1)
            basket_px = (1 + basket.fillna(0)).cumprod()
            bc = beta_corr(basket_px, aligned["BTC-USD"])
            if bc is None:
                return {'error': "Not enough overlapping trading days between these stocks and Bitcoin to measure beta."}
            beta = bc['beta']

            scenarios = [
                ('Bitcoin -10%', -0.10, 'Ordinary pullback (happens several times a year)'),
                ('Bitcoin -20%', -0.20, 'Sharp correction'),
                ('Bitcoin -30%', -0.30, 'Bear-market leg (e.g. mid-2021, mid-2022)'),
                ('Bitcoin -50%', -0.50, 'Deep bear market'),
                ('Bitcoin -70%', -0.70, 'Crypto-winter level (2018, 2022 peak-to-trough)'),
            ]
            stress_results = []
            for name, btc_drop, desc in scenarios:
                # a stock can't fall more than 100%
                drop = max(-1.0, btc_drop * beta)
                stress_results.append({
                    'scenario': name,
                    'description': desc,
                    'market_drop_pct': btc_drop * 100,
                    'portfolio_drop_pct': drop * 100,
                    'portfolio_loss_dollar': float(notional * drop),
                    'portfolio_value_after': float(notional * (1 + drop)),
                    'severity': 'LOW' if abs(btc_drop) < 0.15 else 'MODERATE' if abs(btc_drop) < 0.35 else 'SEVERE',
                })
            worst_scenario = min(stress_results, key=lambda x: x['portfolio_value_after'])
            return {
                'current_value': float(notional),
                'beta_to_bitcoin': float(beta),
                'corr_to_bitcoin': float(bc['corr']),
                'n_days': bc['n_days'],
                'stress_scenarios': stress_results,
                'worst_scenario': worst_scenario,
                'recommendation': self._stress_test_recommendation(beta, worst_scenario),
            }
        except Exception as e:
            return {'error': f"Stress test failed: {e}"}

    def _stress_test_recommendation(self, beta, worst_scenario):
        """Generate stress test recommendation"""
        loss_pct = abs(worst_scenario['portfolio_drop_pct'])
        
        if beta > 2.0:
            risk = "EXTREME"
            action = "Consider hedging with protective puts or reducing position size significantly"
        elif beta > 1.5:
            risk = "HIGH"
            action = "Portfolio 50% more volatile than Bitcoin. Consider partial hedge or stop-loss orders"
        elif beta > 1.0:
            risk = "MODERATE"
            action = "Portfolio moves with Bitcoin. Monitor closely and have exit plan ready"
        else:
            risk = "LOW"
            action = "Portfolio less volatile than Bitcoin. Current risk level acceptable"
        
        return f"{risk} RISK (Beta: {beta:.2f}). {action}. Worst case: {loss_pct:.1f}% loss."
    
    def run_monte_carlo_simulation(self, portfolio_data, num_simulations=1000, days_forward=30):
        """
        Monte Carlo simulation - predict future portfolio values
        Shows probability distribution of outcomes
        """
        try:
            returns = portfolio_data.pct_change().dropna()
            portfolio_returns = returns.mean(axis=1)
            
            mean_return = portfolio_returns.mean()
            std_return = portfolio_returns.std()
            
            current_value = portfolio_data.iloc[-1].sum()
            
            simulations = np.zeros((days_forward, num_simulations))
            
            for sim in range(num_simulations):
                daily_returns = np.random.normal(mean_return, std_return, days_forward)
                
                portfolio_path = current_value * (1 + daily_returns).cumprod()
                simulations[:, sim] = portfolio_path
            
            final_values = simulations[-1, :]
            
            percentile_5 = np.percentile(final_values, 5)
            percentile_25 = np.percentile(final_values, 25)
            percentile_50 = np.percentile(final_values, 50)
            percentile_75 = np.percentile(final_values, 75)
            percentile_95 = np.percentile(final_values, 95)
            
            expected_value = final_values.mean()
            
            prob_profit = (final_values > current_value).sum() / num_simulations * 100
            prob_loss = (final_values < current_value).sum() / num_simulations * 100
            
            prob_gain_10 = (final_values > current_value * 1.10).sum() / num_simulations * 100
            prob_loss_10 = (final_values < current_value * 0.90).sum() / num_simulations * 100
            
            return {
                'current_value': float(current_value),
                'days_forward': days_forward,
                'num_simulations': num_simulations,
                'simulations': simulations,
                'percentile_5': float(percentile_5),
                'percentile_25': float(percentile_25),
                'percentile_50': float(percentile_50),
                'percentile_75': float(percentile_75),
                'percentile_95': float(percentile_95),
                'expected_value': float(expected_value),
                'prob_profit': float(prob_profit),
                'prob_loss': float(prob_loss),
                'prob_gain_10_pct': float(prob_gain_10),
                'prob_loss_10_pct': float(prob_loss_10),
                'mean_return_daily': float(mean_return * 100),
                'volatility_daily': float(std_return * 100),
                'interpretation': self._interpret_monte_carlo(prob_profit, prob_loss_10)
            }
            
        except Exception as e:
            st.error(f"Error running Monte Carlo simulation: {str(e)}")
            return {}
    
    def _interpret_monte_carlo(self, prob_profit, prob_loss_10):
        """Interpret Monte Carlo results"""
        if prob_profit > 70 and prob_loss_10 < 15:
            return "BULLISH OUTLOOK: High probability of gains with limited downside risk. Good time to hold or add."
        elif prob_profit > 55:
            return "MODERATELY BULLISH: More likely to gain than lose, but significant volatility expected."
        elif prob_profit < 45:
            return "BEARISH OUTLOOK: Higher probability of losses. Consider reducing exposure or hedging."
        else:
            return "NEUTRAL: Equal chance of gains/losses. Market direction unclear, wait for better setup."
    
    def calculate_beta_analysis(self, symbols, benchmark='BTC-USD', period='1y'):
        """
        Calculate Beta for each stock vs Bitcoin
        Beta > 1 = More volatile than Bitcoin
        Beta < 1 = Less volatile than Bitcoin
        """
        try:
            closes = fetch_daily_closes(tuple(list(symbols) + [benchmark]), period)
            if closes.empty or benchmark not in closes.columns:
                st.warning(f"Could not fetch {benchmark} data for beta calculation")
                return {}
            benchmark_close = closes[benchmark].dropna()
            
            beta_results = []
            failed_symbols = []
            
            for symbol in symbols:
                try:
                    if symbol not in closes.columns or closes[symbol].dropna().empty:
                        failed_symbols.append(f"{symbol} (no data)")
                        continue
                    stock_close = closes[symbol].dropna()
                    # Align BTC onto the stock trading calendar (weekends folded into Monday)
                    bc = beta_corr(stock_close, benchmark_close)
                    if bc is None:
                        n = len(aligned_returns(stock_close, benchmark_close))
                        failed_symbols.append(f"{symbol} (insufficient data: {n} days)")
                        continue
                    beta = bc['beta']
                    correlation = bc['corr']
                    r_squared = bc['r_squared']
                    stock_std = stock_close.pct_change(fill_method=None).dropna().std() * np.sqrt(252)
                    
                    if beta > 1.5:
                        risk_level = "VERY HIGH"
                        interpretation = f"50% more volatile than Bitcoin - aggressive stock"
                    elif beta > 1.0:
                        risk_level = "HIGH"
                        interpretation = f"Moves with Bitcoin but amplified"
                    elif beta > 0.7:
                        risk_level = "MODERATE"
                        interpretation = f"Tracks Bitcoin somewhat"
                    else:
                        risk_level = "LOW"
                        interpretation = f"Independent of Bitcoin movements"
                    
                    beta_results.append({
                        'symbol': symbol,
                        'beta': float(beta),
                        'correlation': float(correlation),
                        'r_squared': float(r_squared),
                        'annualized_volatility': float(stock_std * 100),
                        'risk_level': risk_level,
                        'interpretation': interpretation
                    })
                except Exception as e:
                    failed_symbols.append(f"{symbol} (error: {str(e)})")
            
            if failed_symbols and beta_results:
                st.info(f"Note: Could not calculate beta for: {', '.join(failed_symbols)}")
            
            if not beta_results:
                return {}
            
            beta_results = sorted(beta_results, key=lambda x: x['beta'], reverse=True)
            
            avg_beta = np.mean([x['beta'] for x in beta_results]) if beta_results else 0
            
            return {
                'benchmark': benchmark,
                'beta_results': beta_results,
                'avg_portfolio_beta': float(avg_beta),
                'portfolio_risk_assessment': self._assess_portfolio_beta(avg_beta)
            }
            
        except Exception as e:
            st.error(f"Error calculating beta analysis: {str(e)}")
            return {}
    
    def _assess_portfolio_beta(self, avg_beta):
        """Assess overall portfolio risk based on average beta"""
        if avg_beta > 1.5:
            return "AGGRESSIVE PORTFOLIO: 50%+ more volatile than Bitcoin. Expect large swings. Consider hedging."
        elif avg_beta > 1.2:
            return "MODERATELY AGGRESSIVE: 20% more volatile than Bitcoin. Normal for mining stocks."
        elif avg_beta > 0.8:
            return "BALANCED: Moves roughly with Bitcoin. Diversification is working."
        else:
            return "CONSERVATIVE: Less volatile than Bitcoin. Well-diversified portfolio."
