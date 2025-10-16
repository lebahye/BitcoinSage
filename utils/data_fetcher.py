import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import streamlit as st
from utils.schwab_fetcher import SchwabDataFetcher

class DataFetcher:
    """Handles all data fetching operations for stocks and market data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Add caching for better performance
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_duration = 30  # 30 second cache for real-time updates
        
        # Initialize Schwab API for real-time data
        self.schwab = SchwabDataFetcher()
        self.using_schwab = self.schwab.is_available()
    
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
        import time
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
        import time
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = time.time()
    
    def get_stock_data(self, symbols, period='1M'):
        """Fetch stock data for given symbols with caching - uses Schwab API first, Yahoo Finance fallback"""
        
        # Check cache first
        cache_key = self._get_cache_key('stock_data', symbols, period)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        # Try Schwab API first for real-time data
        if self.using_schwab:
            try:
                result = self.schwab.get_stock_data_realtime(symbols, period)
                if not result.empty:
                    st.success("✅ Using Schwab API (Real-time data)")
                    self._store_in_cache(cache_key, result)
                    return result
            except Exception as e:
                st.warning(f"Schwab API error, falling back to Yahoo Finance: {str(e)}")
        
        # Fallback to Yahoo Finance
        try:
            # Convert period to yfinance format with intraday intervals for real-time data
            period_map = {
                '1D': '1d',
                '5D': '5d', 
                '1M': '1mo',
                '3M': '3mo',
                '6M': '6mo',
                '1Y': '1y'
            }
            
            # Use intraday intervals for better real-time accuracy
            interval_map = {
                '1D': '5m',  # 5-minute intervals for 1 day
                '5D': '15m', # 15-minute intervals for 5 days
                '1M': '1h',  # 1-hour intervals for 1 month
                '3M': '1d',  # Daily for 3 months
                '6M': '1d',  # Daily for 6 months
                '1Y': '1d'   # Daily for 1 year
            }
            
            yf_period = period_map.get(period, '1mo')
            yf_interval = interval_map.get(period, '1d')
            
            st.info("ℹ️ Using Yahoo Finance (15-min delayed data)")
            
            # Fetch data for all symbols
            tickers = yf.Tickers(' '.join(symbols))
            
            data_dict = {}
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=yf_period, interval=yf_interval)
                    
                    if not hist.empty:
                        data_dict[symbol] = hist['Close']
                    else:
                        st.warning(f"No data available for {symbol}")
                        
                except Exception as e:
                    st.error(f"Error fetching data for {symbol}: {str(e)}")
                    continue
            
            if data_dict:
                result = pd.DataFrame(data_dict)
                # Store in cache
                self._store_in_cache(cache_key, result)
                return result
            else:
                empty_result = pd.DataFrame()
                self._store_in_cache(cache_key, empty_result)
                return empty_result
                
        except Exception as e:
            st.error(f"Error in get_stock_data: {str(e)}")
            return pd.DataFrame()
    
    def get_stock_info(self, symbol):
        """Get detailed stock information"""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            return {
                'current_price': info.get('currentPrice', 0),
                'previous_close': info.get('previousClose', 0),
                'open_price': info.get('open', 0),
                'day_high': info.get('dayHigh', 0),
                'day_low': info.get('dayLow', 0),
                'volume': info.get('volume', 0),
                'avg_volume': info.get('averageVolume', 0),
                'market_cap': info.get('marketCap', 0),
                'pe_ratio': info.get('trailingPE', 0),
                'beta': info.get('beta', 0),
                'fifty_two_week_high': info.get('fiftyTwoWeekHigh', 0),
                'fifty_two_week_low': info.get('fiftyTwoWeekLow', 0)
            }
            
        except Exception as e:
            st.error(f"Error fetching info for {symbol}: {str(e)}")
            return {}
    
    def get_options_data(self, symbol):
        """Fetch options data for a symbol with caching"""
        
        # Check cache first
        cache_key = self._get_cache_key('options_data', symbol)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
            
        try:
            ticker = yf.Ticker(symbol)
            
            # Get available expiration dates
            expirations = ticker.options
            
            if not expirations:
                return None, None
                
            # Get options chain for the nearest expiration
            nearest_exp = expirations[0]
            option_chain = ticker.option_chain(nearest_exp)
            
            calls = option_chain.calls
            puts = option_chain.puts
            
            result = (calls, puts)
            # Store in cache
            self._store_in_cache(cache_key, result)
            return result
            
        except Exception as e:
            st.error(f"Error fetching options data for {symbol}: {str(e)}")
            result = (None, None)
            self._store_in_cache(cache_key, result)
            return result
    
    def get_volume_data(self, symbols, period='1M'):
        """Fetch volume data for dark pool analysis with caching"""
        
        # Check cache first
        cache_key = self._get_cache_key('volume_data', symbols, period)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
            
        try:
            volume_data = {}
            
            period_map = {
                '1D': '1d',
                '5D': '5d',
                '1M': '1mo',
                '3M': '3mo',
                '6M': '6mo',
                '1Y': '1y'
            }
            
            # Use intraday intervals for better real-time accuracy
            interval_map = {
                '1D': '5m',  # 5-minute intervals for 1 day
                '5D': '15m', # 15-minute intervals for 5 days
                '1M': '1h',  # 1-hour intervals for 1 month
                '3M': '1d',  # Daily for 3 months
                '6M': '1d',  # Daily for 6 months
                '1Y': '1d'   # Daily for 1 year
            }
            
            yf_period = period_map.get(period, '1mo')
            yf_interval = interval_map.get(period, '1d')
            
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=yf_period, interval=yf_interval)
                    
                    if not hist.empty:
                        # Calculate volume metrics
                        volume_data[symbol] = {
                            'volume': hist['Volume'].values,
                            'close': hist['Close'].values,
                            'high': hist['High'].values,
                            'low': hist['Low'].values,
                            'dates': hist.index
                        }
                        
                except Exception as e:
                    st.error(f"Error fetching volume data for {symbol}: {str(e)}")
                    continue
            
            # Store in cache
            self._store_in_cache(cache_key, volume_data)
            return volume_data
            
        except Exception as e:
            st.error(f"Error in get_volume_data: {str(e)}")
            empty_result = {}
            self._store_in_cache(cache_key, empty_result)
            return empty_result
    
    def calculate_dark_pool_indicators(self, symbol):
        """Calculate dark pool activity indicators"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo', interval='1d')
            
            if hist.empty:
                return {}
            
            # Volume analysis
            volumes = hist['Volume']
            prices = hist['Close']
            
            # Calculate volume-weighted average price (VWAP)
            vwap = (prices * volumes).cumsum() / volumes.cumsum()
            
            # Unusual volume detection (volume > 1.5x average)
            avg_volume = volumes.rolling(20).mean()
            unusual_volume_days = volumes > (avg_volume * 1.5)
            
            # Price-volume divergence
            price_change = prices.pct_change()
            volume_ratio = volumes / avg_volume
            
            return {
                'vwap': vwap.iloc[-1] if len(vwap) > 0 else 0,
                'current_price': prices.iloc[-1] if len(prices) > 0 else 0,
                'unusual_volume_pct': (unusual_volume_days.sum() / len(unusual_volume_days)) * 100,
                'avg_volume': avg_volume.iloc[-1] if len(avg_volume) > 0 else 0,
                'current_volume': volumes.iloc[-1] if len(volumes) > 0 else 0,
                'volume_ratio': volume_ratio.iloc[-1] if len(volume_ratio) > 0 else 0
            }
            
        except Exception as e:
            st.error(f"Error calculating dark pool indicators for {symbol}: {str(e)}")
            return {}
    
    def get_market_sentiment(self):
        """Get overall market sentiment indicators"""
        try:
            # Fetch VIX data as market fear gauge
            vix = yf.Ticker("^VIX")
            vix_data = vix.history(period='5d', interval='1d')
            
            # Fetch Bitcoin price for correlation
            btc = yf.Ticker("BTC-USD")
            btc_data = btc.history(period='5d', interval='1d')
            
            sentiment = {}
            
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                sentiment['vix'] = current_vix
                sentiment['fear_greed'] = self._calculate_fear_greed(current_vix)
            
            if not btc_data.empty:
                btc_price = btc_data['Close'].iloc[-1]
                btc_change = ((btc_price - btc_data['Close'].iloc[-2]) / btc_data['Close'].iloc[-2]) * 100
                sentiment['btc_price'] = btc_price
                sentiment['btc_change'] = btc_change
            
            return sentiment
            
        except Exception as e:
            st.error(f"Error fetching market sentiment: {str(e)}")
            return {}
    
    def _calculate_fear_greed(self, vix_value):
        """Calculate fear/greed indicator based on VIX"""
        if vix_value > 30:
            return "Fear"
        elif vix_value > 20:
            return "Neutral"
        else:
            return "Greed"
