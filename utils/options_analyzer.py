import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, timedelta
import time

class OptionsAnalyzer:
    """Analyzes options data for put-call ratios and volatility indicators"""
    
    def __init__(self):
        self.cache_duration = 300  # 5 minutes cache
        self._cache = {}
        self._cache_timestamps = {}
    
    def _get_cache_key(self, method_name, *args):
        """Generate stable cache key for method and arguments"""
        # Create stable, sorted key that's not sensitive to argument order
        stable_args = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                # Sort lists/tuples for consistency
                stable_args.append(str(sorted(str(item) for item in arg)))
            else:
                stable_args.append(str(arg))
        
        # Join with delimiter and use stable hash
        key_string = f"{method_name}|{'^'.join(sorted(stable_args))}"
        return f"{method_name}_{abs(hash(key_string))}"
    
    def _is_cache_valid(self, cache_key):
        """Check if cached data is still valid"""
        if cache_key not in self._cache_timestamps:
            return False
        return (time.time() - self._cache_timestamps[cache_key]) < self.cache_duration
    
    def _get_from_cache(self, cache_key):
        """Get data from cache if valid"""
        if self._is_cache_valid(cache_key):
            return self._cache.get(cache_key)
        return None
    
    def _store_in_cache(self, cache_key, data):
        """Store data in cache with timestamp"""
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = time.time()
        
    def analyze_put_call_ratio(self, calls_df, puts_df):
        """Calculate put-call ratio and related metrics with caching"""
        
        # Generate cache key based on data content, not object ID
        calls_hash = hash(str(calls_df.values.tobytes())) if calls_df is not None and not calls_df.empty else None
        puts_hash = hash(str(puts_df.values.tobytes())) if puts_df is not None and not puts_df.empty else None
        cache_key = self._get_cache_key('put_call_ratio', calls_hash, puts_hash)
        
        # Check cache first
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
            
        try:
            if calls_df is None or puts_df is None or calls_df.empty or puts_df.empty:
                return {
                    'put_call_ratio': 0,
                    'call_volume': 0,
                    'put_volume': 0,
                    'call_oi': 0,
                    'put_oi': 0,
                    'volatility_signal': 'No Data'
                }
            
            # Calculate total volumes and open interest
            call_volume = calls_df['volume'].fillna(0).sum()
            put_volume = puts_df['volume'].fillna(0).sum()
            call_oi = calls_df['openInterest'].fillna(0).sum()
            put_oi = puts_df['openInterest'].fillna(0).sum()
            
            # Calculate put-call ratios
            pc_ratio_volume = put_volume / call_volume if call_volume > 0 else 0
            pc_ratio_oi = put_oi / call_oi if call_oi > 0 else 0
            
            # Determine volatility signal
            volatility_signal = self._interpret_pc_ratio(pc_ratio_volume)
            
            result = {
                'put_call_ratio': pc_ratio_volume,
                'put_call_ratio_oi': pc_ratio_oi,
                'call_volume': call_volume,
                'put_volume': put_volume,
                'call_oi': call_oi,
                'put_oi': put_oi,
                'volatility_signal': volatility_signal,
                'total_volume': call_volume + put_volume,
                'total_oi': call_oi + put_oi
            }
            
            # Store result in cache
            self._store_in_cache(cache_key, result)
            return result
            
        except Exception as e:
            st.error(f"Error analyzing put-call ratio: {str(e)}")
            return {
                'put_call_ratio': 0,
                'call_volume': 0,
                'put_volume': 0,
                'call_oi': 0,
                'put_oi': 0,
                'volatility_signal': 'Error'
            }
    
    def _interpret_pc_ratio(self, ratio):
        """Interpret put-call ratio for volatility signals"""
        if ratio == 0:
            return "No Data"
        elif ratio > 1.2:
            return "High Volatility Expected (Bearish)"
        elif ratio > 0.8:
            return "Moderate Volatility (Neutral)"
        elif ratio > 0.6:
            return "Low Volatility (Bullish)"
        else:
            return "Very Bullish Sentiment"
    
    def analyze_unusual_options_activity(self, calls_df, puts_df):
        """Identify unusual options activity"""
        try:
            unusual_activity = []
            
            if calls_df is not None and not calls_df.empty:
                # Find calls with high volume relative to open interest
                calls_df['volume_oi_ratio'] = calls_df['volume'] / (calls_df['openInterest'] + 1)
                unusual_calls = calls_df[calls_df['volume_oi_ratio'] > 0.5].copy()
                
                for _, row in unusual_calls.head(5).iterrows():
                    unusual_activity.append({
                        'type': 'Call',
                        'strike': row['strike'],
                        'volume': row['volume'],
                        'open_interest': row['openInterest'],
                        'implied_volatility': row.get('impliedVolatility', 0),
                        'last_price': row.get('lastPrice', 0)
                    })
            
            if puts_df is not None and not puts_df.empty:
                # Find puts with high volume relative to open interest
                puts_df['volume_oi_ratio'] = puts_df['volume'] / (puts_df['openInterest'] + 1)
                unusual_puts = puts_df[puts_df['volume_oi_ratio'] > 0.5].copy()
                
                for _, row in unusual_puts.head(5).iterrows():
                    unusual_activity.append({
                        'type': 'Put',
                        'strike': row['strike'],
                        'volume': row['volume'],
                        'open_interest': row['openInterest'],
                        'implied_volatility': row.get('impliedVolatility', 0),
                        'last_price': row.get('lastPrice', 0)
                    })
            
            return unusual_activity
            
        except Exception as e:
            st.error(f"Error analyzing unusual options activity: {str(e)}")
            return []
    
    def calculate_options_flow_metrics(self, calls_df, puts_df, current_price):
        """Calculate options flow and smart money indicators"""
        try:
            metrics = {
                'call_put_skew': 0,
                'moneyness_distribution': {},
                'iv_percentile': 0,
                'smart_money_indicator': 'Neutral'
            }
            
            if calls_df is not None and not calls_df.empty:
                # Calculate call skew
                atm_calls = calls_df[abs(calls_df['strike'] - current_price) <= (current_price * 0.05)]
                if not atm_calls.empty:
                    avg_call_iv = atm_calls['impliedVolatility'].mean()
                    metrics['avg_call_iv'] = avg_call_iv
            
            if puts_df is not None and not puts_df.empty:
                # Calculate put skew
                atm_puts = puts_df[abs(puts_df['strike'] - current_price) <= (current_price * 0.05)]
                if not atm_puts.empty:
                    avg_put_iv = atm_puts['impliedVolatility'].mean()
                    metrics['avg_put_iv'] = avg_put_iv
            
            # Calculate moneyness distribution
            if calls_df is not None and puts_df is not None:
                metrics['moneyness_distribution'] = self._calculate_moneyness_distribution(
                    calls_df, puts_df, current_price
                )
            
            # Smart money indicator based on large trades and IV
            metrics['smart_money_indicator'] = self._calculate_smart_money_indicator(
                calls_df, puts_df, current_price
            )
            
            return metrics
            
        except Exception as e:
            st.error(f"Error calculating options flow metrics: {str(e)}")
            return {}
    
    def _calculate_moneyness_distribution(self, calls_df, puts_df, current_price):
        """Calculate distribution of options by moneyness"""
        try:
            distribution = {
                'deep_otm': 0,
                'otm': 0,
                'atm': 0,
                'itm': 0,
                'deep_itm': 0
            }
            
            # Add type column to distinguish calls from puts before concat
            calls_with_type = calls_df.copy() if calls_df is not None and not calls_df.empty else pd.DataFrame()
            puts_with_type = puts_df.copy() if puts_df is not None and not puts_df.empty else pd.DataFrame()
            
            if not calls_with_type.empty:
                calls_with_type['option_type'] = 'call'
            if not puts_with_type.empty:
                puts_with_type['option_type'] = 'put'
            
            all_options = pd.concat([calls_with_type, puts_with_type], ignore_index=True)
            
            if not all_options.empty:
                for _, option in all_options.iterrows():
                    strike = option['strike']
                    volume_val = option['volume']
                    volume = volume_val if pd.notna(volume_val) else 0
                    
                    # Calculate moneyness properly for option type classification
                    # Use the type column we added instead of unreliable strike lookup
                    is_call = option.get('option_type') == 'call'
                    
                    if is_call:
                        # Call option: ITM when strike < current_price
                        itm = strike < current_price
                    else:
                        # Put option: ITM when strike > current_price  
                        itm = strike > current_price
                    
                    if itm:
                        # In-the-money: classify by distance
                        distance = abs(strike - current_price) / current_price
                        if distance > 0.1:
                            distribution['deep_itm'] += volume
                        else:
                            distribution['itm'] += volume
                    else:
                        # Out-of-the-money: classify by distance
                        distance = abs(strike - current_price) / current_price
                        if distance <= 0.05:
                            distribution['atm'] += volume
                        elif distance <= 0.15:
                            distribution['otm'] += volume
                        else:
                            distribution['deep_otm'] += volume
            
            return distribution
            
        except Exception as e:
            st.error(f"Error calculating moneyness distribution: {str(e)}")
            return {}
    
    def _calculate_smart_money_indicator(self, calls_df, puts_df, current_price):
        """Calculate smart money flow indicator"""
        try:
            if calls_df is None and puts_df is None:
                return 'No Data'
            
            large_trades_score = 0
            
            # Analyze large call trades
            if calls_df is not None and not calls_df.empty:
                large_calls = calls_df[calls_df['volume'] > 100]  # Large volume threshold
                if not large_calls.empty:
                    # Weight by how close to ATM
                    for _, trade in large_calls.iterrows():
                        distance = abs(trade['strike'] - current_price) / current_price
                        weight = max(0, 1 - distance * 2)  # Closer to ATM = higher weight
                        large_trades_score += trade['volume'] * weight
            
            # Analyze large put trades (negative score)
            if puts_df is not None and not puts_df.empty:
                large_puts = puts_df[puts_df['volume'] > 100]
                if not large_puts.empty:
                    for _, trade in large_puts.iterrows():
                        distance = abs(trade['strike'] - current_price) / current_price
                        weight = max(0, 1 - distance * 2)
                        large_trades_score -= trade['volume'] * weight
            
            # Interpret score
            if large_trades_score > 1000:
                return 'Strong Bullish Flow'
            elif large_trades_score > 500:
                return 'Moderate Bullish Flow'
            elif large_trades_score > -500:
                return 'Neutral Flow'
            elif large_trades_score > -1000:
                return 'Moderate Bearish Flow'
            else:
                return 'Strong Bearish Flow'
                
        except Exception as e:
            st.error(f"Error calculating smart money indicator: {str(e)}")
            return 'Error'
    
    def get_volatility_forecast(self, put_call_ratio, iv_data=None):
        """Forecast volatility based on options data"""
        try:
            forecast = {
                'volatility_outlook': 'Neutral',
                'confidence': 'Medium',
                'key_factors': []
            }
            
            # Analyze put-call ratio
            if put_call_ratio > 1.2:
                forecast['volatility_outlook'] = 'High Volatility Expected'
                forecast['confidence'] = 'High'
                forecast['key_factors'].append('Elevated put-call ratio indicates fear')
            elif put_call_ratio < 0.6:
                forecast['volatility_outlook'] = 'Low Volatility Expected'
                forecast['confidence'] = 'Medium'
                forecast['key_factors'].append('Low put-call ratio suggests complacency')
            
            # Add IV analysis if available
            if iv_data:
                forecast['key_factors'].append('Implied volatility analysis included')
            
            return forecast
            
        except Exception as e:
            st.error(f"Error generating volatility forecast: {str(e)}")
            return {
                'volatility_outlook': 'Error',
                'confidence': 'Low',
                'key_factors': ['Error in analysis']
            }
