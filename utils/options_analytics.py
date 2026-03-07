import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st
from scipy.stats import norm

class OptionsAnalytics:
    """Professional-grade options analytics for institutional-level analysis"""
    
    def __init__(self):
        self.cache = {}
        self.iv_history_cache = {}
    
    def calculate_iv_percentile(self, symbol, current_iv, period_days=252):
        """
        Calculate IV Percentile - shows where current IV ranks historically
        0% = lowest IV in period, 100% = highest IV in period
        Professional traders use this to know if options are cheap or expensive
        """
        try:
            ticker = yf.Ticker(symbol)
            
            end_date = datetime.now()
            start_date = end_date - timedelta(days=period_days)
            
            hist = ticker.history(start=start_date, end=end_date, interval='1d')
            
            if hist.empty or len(hist) < 30:
                return {}
            
            iv_history = []
            
            for i in range(len(hist)):
                date_point = hist.index[i]
                close_price = hist['Close'].iloc[i]
                
                try:
                    expirations = ticker.options
                    if not expirations:
                        continue
                    
                    nearest_exp = expirations[0]
                    chain = ticker.option_chain(nearest_exp)
                    
                    atm_calls = chain.calls[
                        (chain.calls['strike'] >= close_price * 0.95) & 
                        (chain.calls['strike'] <= close_price * 1.05)
                    ]
                    
                    if not atm_calls.empty and 'impliedVolatility' in atm_calls.columns:
                        avg_iv = atm_calls['impliedVolatility'].mean()
                        if avg_iv > 0 and not np.isnan(avg_iv):
                            iv_history.append({
                                'date': date_point,
                                'iv': float(avg_iv)
                            })
                except:
                    continue
            
            if len(iv_history) < 10:
                return {'error': 'Insufficient IV history data'}
            
            iv_values = [x['iv'] for x in iv_history]
            iv_values_sorted = sorted(iv_values)
            
            if current_iv <= 0:
                current_iv = iv_values[-1]
            
            values_below = len([x for x in iv_values if x < current_iv])
            iv_percentile = (values_below / len(iv_values)) * 100
            
            values_equal_or_below = len([x for x in iv_values if x <= current_iv])
            iv_rank = (values_equal_or_below / len(iv_values)) * 100
            
            min_iv = min(iv_values)
            max_iv = max(iv_values)
            median_iv = np.median(iv_values)
            
            if iv_percentile >= 75:
                signal = "IV VERY HIGH - Options expensive, great for selling premium"
            elif iv_percentile >= 50:
                signal = "IV HIGH - Options moderately expensive, consider selling"
            elif iv_percentile >= 25:
                signal = "IV NORMAL - Fair pricing, neutral strategy"
            else:
                signal = "IV LOW - Options cheap, good for buying protection"
            
            return {
                'iv_percentile': iv_percentile,
                'iv_rank': iv_rank,
                'current_iv': current_iv,
                'min_iv': min_iv,
                'max_iv': max_iv,
                'median_iv': median_iv,
                'iv_history': iv_history,
                'signal': signal,
                'period_days': len(iv_values)
            }
            
        except Exception as e:
            st.error(f"Error calculating IV percentile for {symbol}: {str(e)}")
            return {}
    
    def scan_options_chain(self, symbol, strategy='covered_calls'):
        """
        Full options chain scanner with strategy recommendations
        Identifies best strikes based on strategy type
        """
        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get('currentPrice', 0)
            
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            expirations = ticker.options
            
            if not expirations:
                return {}
            
            recommendations = []
            
            for i, exp_date in enumerate(expirations[:4]):
                try:
                    chain = ticker.option_chain(exp_date)
                    calls = chain.calls
                    puts = chain.puts
                    
                    days_to_exp = (pd.to_datetime(exp_date) - datetime.now()).days
                    
                    if strategy == 'covered_calls':
                        otm_calls = calls[calls['strike'] > current_price * 1.01]
                        
                        for _, option in otm_calls.head(5).iterrows():
                            strike = option['strike']
                            premium = option.get('lastPrice', option.get('bid', 0))
                            iv = option.get('impliedVolatility', 0)
                            delta = option.get('delta', self._estimate_delta('call', current_price, strike, days_to_exp, iv))
                            
                            if premium > 0:
                                annual_return = (premium / current_price) * (365 / days_to_exp) * 100
                                
                                recommendations.append({
                                    'type': 'Covered Call',
                                    'expiration': exp_date,
                                    'days_to_exp': days_to_exp,
                                    'strike': strike,
                                    'premium': premium,
                                    'iv': iv * 100 if iv > 0 else 0,
                                    'delta': delta,
                                    'annual_return': annual_return,
                                    'max_gain': ((strike - current_price) + premium) / current_price * 100,
                                    'breakeven': current_price
                                })
                    
                    elif strategy == 'protective_puts':
                        otm_puts = puts[puts['strike'] < current_price * 0.99]
                        
                        for _, option in otm_puts.tail(5).iterrows():
                            strike = option['strike']
                            premium = option.get('lastPrice', option.get('ask', 0))
                            iv = option.get('impliedVolatility', 0)
                            delta = option.get('delta', self._estimate_delta('put', current_price, strike, days_to_exp, iv))
                            
                            if premium > 0:
                                cost_pct = (premium / current_price) * 100
                                protection_pct = ((current_price - strike) / current_price) * 100
                                
                                recommendations.append({
                                    'type': 'Protective Put',
                                    'expiration': exp_date,
                                    'days_to_exp': days_to_exp,
                                    'strike': strike,
                                    'premium': premium,
                                    'iv': iv * 100 if iv > 0 else 0,
                                    'delta': delta,
                                    'cost_pct': cost_pct,
                                    'protection_pct': protection_pct,
                                    'protected_price': strike
                                })
                    
                    elif strategy == 'long_calls':
                        atm_otm_calls = calls[
                            (calls['strike'] >= current_price * 0.98) & 
                            (calls['strike'] <= current_price * 1.10)
                        ]
                        
                        for _, option in atm_otm_calls.head(8).iterrows():
                            strike = option['strike']
                            premium = option.get('lastPrice', option.get('ask', 0))
                            iv = option.get('impliedVolatility', 0)
                            delta = option.get('delta', self._estimate_delta('call', current_price, strike, days_to_exp, iv))
                            gamma = option.get('gamma', 0)
                            theta = option.get('theta', 0)
                            
                            if premium > 0:
                                breakeven = strike + premium
                                leverage = (delta * current_price) / premium if premium > 0 else 0
                                
                                recommendations.append({
                                    'type': 'Long Call',
                                    'expiration': exp_date,
                                    'days_to_exp': days_to_exp,
                                    'strike': strike,
                                    'premium': premium,
                                    'iv': iv * 100 if iv > 0 else 0,
                                    'delta': delta,
                                    'gamma': gamma,
                                    'theta': theta,
                                    'breakeven': breakeven,
                                    'leverage': leverage,
                                    'moneyness': 'ITM' if strike < current_price else 'ATM' if abs(strike - current_price) < 0.02 * current_price else 'OTM'
                                })
                
                except Exception as e:
                    continue
            
            recommendations_df = pd.DataFrame(recommendations)
            
            if not recommendations_df.empty:
                if strategy == 'covered_calls':
                    recommendations_df = recommendations_df.sort_values('annual_return', ascending=False)
                elif strategy == 'protective_puts':
                    recommendations_df['score'] = recommendations_df['protection_pct'] / recommendations_df['cost_pct']
                    recommendations_df = recommendations_df.sort_values('score', ascending=False)
                elif strategy == 'long_calls':
                    recommendations_df['score'] = recommendations_df['delta'] * recommendations_df['leverage'] / (recommendations_df['premium'] + 0.01)
                    recommendations_df = recommendations_df.sort_values('score', ascending=False)
            
            return {
                'current_price': current_price,
                'strategy': strategy,
                'recommendations': recommendations_df.to_dict('records') if not recommendations_df.empty else [],
                'total_opportunities': len(recommendations_df)
            }
            
        except Exception as e:
            st.error(f"Error scanning options chain for {symbol}: {str(e)}")
            return {}
    
    def _estimate_delta(self, option_type, spot, strike, days_to_exp, iv):
        """Estimate delta using Black-Scholes approximation"""
        try:
            if days_to_exp <= 0 or iv <= 0:
                return 0.5 if option_type == 'call' else -0.5
            
            T = days_to_exp / 365.0
            r = 0.05
            
            d1 = (np.log(spot / strike) + (r + 0.5 * iv**2) * T) / (iv * np.sqrt(T))
            
            if option_type == 'call':
                delta = norm.cdf(d1)
            else:
                delta = norm.cdf(d1) - 1
            
            return float(delta)
            
        except:
            return 0.5 if option_type == 'call' else -0.5
    
    def calculate_greeks_surface(self, symbol):
        """
        Calculate Greeks surface across all strikes and expirations
        Visualizes how Greeks change with price and time
        """
        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get('currentPrice', 0)
            
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            expirations = ticker.options[:6]
            
            greeks_data = []
            
            for exp_date in expirations:
                try:
                    chain = ticker.option_chain(exp_date)
                    days_to_exp = (pd.to_datetime(exp_date) - datetime.now()).days
                    
                    for _, call in chain.calls.iterrows():
                        strike = call['strike']
                        greeks_data.append({
                            'expiration': exp_date,
                            'days_to_exp': days_to_exp,
                            'strike': strike,
                            'type': 'call',
                            'delta': call.get('delta', 0),
                            'gamma': call.get('gamma', 0),
                            'theta': call.get('theta', 0),
                            'vega': call.get('vega', 0),
                            'iv': call.get('impliedVolatility', 0)
                        })
                    
                    for _, put in chain.puts.iterrows():
                        strike = put['strike']
                        greeks_data.append({
                            'expiration': exp_date,
                            'days_to_exp': days_to_exp,
                            'strike': strike,
                            'type': 'put',
                            'delta': put.get('delta', 0),
                            'gamma': put.get('gamma', 0),
                            'theta': put.get('theta', 0),
                            'vega': put.get('vega', 0),
                            'iv': put.get('impliedVolatility', 0)
                        })
                
                except:
                    continue
            
            df = pd.DataFrame(greeks_data)
            
            return {
                'current_price': current_price,
                'greeks_data': df,
                'expirations': expirations
            }
            
        except Exception as e:
            st.error(f"Error calculating Greeks surface for {symbol}: {str(e)}")
            return {}
    
    def calculate_iv_term_structure(self, symbol):
        """
        Calculate IV Term Structure - how IV changes across expirations
        Shows if near-term or far-term options are more expensive
        """
        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.info.get('currentPrice', 0)
            
            if current_price == 0:
                hist = ticker.history(period='1d')
                if not hist.empty:
                    current_price = hist['Close'].iloc[-1]
            
            expirations = ticker.options
            
            term_structure = []
            
            for exp_date in expirations:
                try:
                    chain = ticker.option_chain(exp_date)
                    days_to_exp = (pd.to_datetime(exp_date) - datetime.now()).days
                    
                    if days_to_exp < 1:
                        continue
                    
                    atm_calls = chain.calls[
                        (chain.calls['strike'] >= current_price * 0.98) & 
                        (chain.calls['strike'] <= current_price * 1.02)
                    ]
                    
                    atm_puts = chain.puts[
                        (chain.puts['strike'] >= current_price * 0.98) & 
                        (chain.puts['strike'] <= current_price * 1.02)
                    ]
                    
                    if not atm_calls.empty:
                        call_iv = atm_calls['impliedVolatility'].mean()
                    else:
                        call_iv = 0
                    
                    if not atm_puts.empty:
                        put_iv = atm_puts['impliedVolatility'].mean()
                    else:
                        put_iv = 0
                    
                    avg_iv = (call_iv + put_iv) / 2 if call_iv > 0 and put_iv > 0 else max(call_iv, put_iv)
                    
                    if avg_iv > 0:
                        term_structure.append({
                            'expiration': exp_date,
                            'days_to_exp': days_to_exp,
                            'iv': float(avg_iv),
                            'call_iv': float(call_iv),
                            'put_iv': float(put_iv)
                        })
                
                except:
                    continue
            
            if len(term_structure) < 2:
                return {}
            
            term_structure = sorted(term_structure, key=lambda x: x['days_to_exp'])
            
            near_term_iv = term_structure[0]['iv'] if len(term_structure) > 0 else 0
            far_term_iv = term_structure[-1]['iv'] if len(term_structure) > 0 else 0
            
            if near_term_iv > far_term_iv * 1.1:
                shape = "Inverted (Backwardation) - Near-term event expected"
            elif far_term_iv > near_term_iv * 1.1:
                shape = "Normal (Contango) - Uncertainty increases over time"
            else:
                shape = "Flat - Stable expectations across time"
            
            return {
                'current_price': current_price,
                'term_structure': term_structure,
                'shape': shape,
                'near_term_iv': near_term_iv * 100,
                'far_term_iv': far_term_iv * 100,
                'term_spread': (far_term_iv - near_term_iv) * 100
            }
            
        except Exception as e:
            st.error(f"Error calculating IV term structure for {symbol}: {str(e)}")
            return {}


    # -----------------------------------------------------------------------
    # Flow analysis methods — ported from options_analyzer.py
    # -----------------------------------------------------------------------

    def analyze_put_call_ratio(self, calls_df, puts_df):
        """Calculate put-call ratio and related metrics with caching"""
        calls_hash = hash(str(calls_df.values.tobytes())) if calls_df is not None and not calls_df.empty else None
        puts_hash  = hash(str(puts_df.values.tobytes()))  if puts_df  is not None and not puts_df.empty  else None
        cache_key  = f"pcr_{calls_hash}_{puts_hash}"

        if cache_key in self.cache:
            return self.cache[cache_key]

        try:
            if calls_df is None or puts_df is None or calls_df.empty or puts_df.empty:
                return {'put_call_ratio': 0, 'call_volume': 0, 'put_volume': 0,
                        'call_oi': 0, 'put_oi': 0, 'volatility_signal': 'No Data'}

            call_volume = calls_df['volume'].fillna(0).sum()
            put_volume  = puts_df['volume'].fillna(0).sum()
            call_oi     = calls_df['openInterest'].fillna(0).sum()
            put_oi      = puts_df['openInterest'].fillna(0).sum()

            pc_ratio_volume = put_volume / call_volume if call_volume > 0 else 0
            pc_ratio_oi     = put_oi / call_oi         if call_oi     > 0 else 0

            result = {
                'put_call_ratio':    pc_ratio_volume,
                'put_call_ratio_oi': pc_ratio_oi,
                'call_volume':  call_volume,
                'put_volume':   put_volume,
                'call_oi':      call_oi,
                'put_oi':       put_oi,
                'volatility_signal': self._interpret_pc_ratio(pc_ratio_volume),
                'total_volume': call_volume + put_volume,
                'total_oi':     call_oi + put_oi,
            }
            self.cache[cache_key] = result
            return result

        except Exception as e:
            st.error(f"Error analyzing put-call ratio: {str(e)}")
            return {'put_call_ratio': 0, 'call_volume': 0, 'put_volume': 0,
                    'call_oi': 0, 'put_oi': 0, 'volatility_signal': 'Error'}

    def _interpret_pc_ratio(self, ratio):
        if ratio == 0:        return "No Data"
        elif ratio > 1.2:     return "High Volatility Expected (Bearish)"
        elif ratio > 0.8:     return "Moderate Volatility (Neutral)"
        elif ratio > 0.6:     return "Low Volatility (Bullish)"
        else:                 return "Very Bullish Sentiment"

    def analyze_unusual_options_activity(self, calls_df, puts_df):
        """Identify unusual options activity"""
        try:
            unusual_activity = []
            for df, kind in [(calls_df, 'Call'), (puts_df, 'Put')]:
                if df is not None and not df.empty:
                    df = df.copy()
                    df['volume_oi_ratio'] = df['volume'] / (df['openInterest'] + 1)
                    unusual = df[df['volume_oi_ratio'] > 0.5]
                    for _, row in unusual.head(5).iterrows():
                        unusual_activity.append({
                            'type':               kind,
                            'strike':             row['strike'],
                            'volume':             row['volume'],
                            'open_interest':      row['openInterest'],
                            'implied_volatility': row.get('impliedVolatility', 0),
                            'last_price':         row.get('lastPrice', 0),
                        })
            return unusual_activity
        except Exception as e:
            st.error(f"Error analyzing unusual options activity: {str(e)}")
            return []

    def calculate_options_flow_metrics(self, calls_df, puts_df, current_price):
        """Calculate options flow and smart money indicators"""
        try:
            metrics = {
                'call_put_skew':          0,
                'moneyness_distribution': {},
                'iv_percentile':          0,
                'smart_money_indicator':  'Neutral',
            }
            if calls_df is not None and not calls_df.empty:
                atm_calls = calls_df[abs(calls_df['strike'] - current_price) <= current_price * 0.05]
                if not atm_calls.empty:
                    metrics['avg_call_iv'] = atm_calls['impliedVolatility'].mean()
            if puts_df is not None and not puts_df.empty:
                atm_puts = puts_df[abs(puts_df['strike'] - current_price) <= current_price * 0.05]
                if not atm_puts.empty:
                    metrics['avg_put_iv'] = atm_puts['impliedVolatility'].mean()
            if calls_df is not None and puts_df is not None:
                metrics['moneyness_distribution'] = self._calculate_moneyness_distribution(
                    calls_df, puts_df, current_price)
            metrics['smart_money_indicator'] = self._calculate_smart_money_indicator(
                calls_df, puts_df, current_price)
            return metrics
        except Exception as e:
            st.error(f"Error calculating options flow metrics: {str(e)}")
            return {}

    def _calculate_moneyness_distribution(self, calls_df, puts_df, current_price):
        try:
            distribution = {'deep_otm': 0, 'otm': 0, 'atm': 0, 'itm': 0, 'deep_itm': 0}
            calls_c = calls_df.copy() if calls_df is not None and not calls_df.empty else pd.DataFrame()
            puts_c  = puts_df.copy()  if puts_df  is not None and not puts_df.empty  else pd.DataFrame()
            if not calls_c.empty: calls_c['option_type'] = 'call'
            if not puts_c.empty:  puts_c['option_type']  = 'put'
            all_opts = pd.concat([calls_c, puts_c], ignore_index=True)
            if not all_opts.empty:
                for _, opt in all_opts.iterrows():
                    strike   = opt['strike']
                    volume   = opt['volume'] if pd.notna(opt['volume']) else 0
                    is_call  = opt.get('option_type') == 'call'
                    itm      = (strike < current_price) if is_call else (strike > current_price)
                    distance = abs(strike - current_price) / current_price
                    if itm:
                        distribution['deep_itm' if distance > 0.1 else 'itm'] += volume
                    else:
                        if distance <= 0.05:       distribution['atm']      += volume
                        elif distance <= 0.15:     distribution['otm']      += volume
                        else:                      distribution['deep_otm'] += volume
            return distribution
        except Exception as e:
            st.error(f"Error calculating moneyness distribution: {str(e)}")
            return {}

    def _calculate_smart_money_indicator(self, calls_df, puts_df, current_price):
        try:
            if calls_df is None and puts_df is None:
                return 'No Data'
            score = 0
            if calls_df is not None and not calls_df.empty:
                large = calls_df[calls_df['volume'] > 100]
                for _, t in large.iterrows():
                    w = max(0, 1 - abs(t['strike'] - current_price) / current_price * 2)
                    score += t['volume'] * w
            if puts_df is not None and not puts_df.empty:
                large = puts_df[puts_df['volume'] > 100]
                for _, t in large.iterrows():
                    w = max(0, 1 - abs(t['strike'] - current_price) / current_price * 2)
                    score -= t['volume'] * w
            if score > 1000:   return 'Strong Bullish Flow'
            elif score > 500:  return 'Moderate Bullish Flow'
            elif score > -500: return 'Neutral Flow'
            elif score > -1000:return 'Moderate Bearish Flow'
            else:              return 'Strong Bearish Flow'
        except Exception as e:
            st.error(f"Error calculating smart money indicator: {str(e)}")
            return 'Error'

    def get_volatility_forecast(self, put_call_ratio, iv_data=None):
        """Forecast volatility based on options data"""
        try:
            forecast = {'volatility_outlook': 'Neutral', 'confidence': 'Medium', 'key_factors': []}
            if put_call_ratio > 1.2:
                forecast.update({'volatility_outlook': 'High Volatility Expected', 'confidence': 'High'})
                forecast['key_factors'].append('Elevated put-call ratio indicates fear')
            elif put_call_ratio < 0.6:
                forecast.update({'volatility_outlook': 'Low Volatility Expected', 'confidence': 'Medium'})
                forecast['key_factors'].append('Low put-call ratio suggests complacency')
            if iv_data:
                forecast['key_factors'].append('Implied volatility analysis included')
            return forecast
        except Exception as e:
            st.error(f"Error generating volatility forecast: {str(e)}")
            return {'volatility_outlook': 'Error', 'confidence': 'Low',
                    'key_factors': ['Error in analysis']}


# Backward-compatibility alias
OptionsAnalyzer = OptionsAnalytics
