"""
utils/unified_data_fetcher.py
Unified data fetcher — merges data_fetcher.py, enhanced_data_fetcher.py, schwab_fetcher.py
into a single module. All three classes are preserved; internal cross-imports removed.
"""

import os
import yfinance as yf
import pandas as pd
import numpy as np
import streamlit as st
import requests
import json
import httpx
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

# Optional schwab library imports
try:
    from schwab import auth, client as schwab_client_lib
    SCHWAB_LIB_AVAILABLE = True
except ImportError:
    SCHWAB_LIB_AVAILABLE = False

try:
    from utils.schwab_client import SchwabClient, schwab_quotes_to_dataframe, schwab_options_to_dataframe
    SCHWAB_CLIENT_AVAILABLE = True
except ImportError:
    SCHWAB_CLIENT_AVAILABLE = False


# ---------------------------------------------------------------------------
# SchwabDataFetcher — direct schwab library wrapper (OAuth token-file based)
# ---------------------------------------------------------------------------

class SchwabDataFetcher:
    """Real-time market data fetcher using Schwab API (token-file based)"""

    def __init__(self):
        self.client = None
        self.token_path = './schwab_token.json'
        self._initialize_client()

    def _initialize_client(self):
        """Initialize Schwab API client with OAuth2 authentication"""
        if not SCHWAB_LIB_AVAILABLE:
            return None
        try:
            api_key = os.environ.get('SCHWAB_APP_KEY')
            app_secret = os.environ.get('SCHWAB_APP_SECRET')

            if not api_key or not app_secret:
                return None

            if os.path.exists(self.token_path):
                with open(self.token_path, 'r') as f:
                    json.load(f)  # validate JSON

                self.client = auth.client_from_token_file(
                    self.token_path, api_key, app_secret
                )
                st.success("✅ Schwab API authenticated - Using real-time data")
                return self.client
        except Exception:
            pass
        return None

    def is_available(self):
        return self.client is not None

    def get_quote(self, symbol):
        if not self.client:
            return None
        try:
            resp = self.client.get_quote(symbol)
            if resp.status_code == httpx.codes.OK:
                data = resp.json()
                return data.get(symbol, {})
            st.error(f"Error fetching quote for {symbol}: {resp.status_code}")
            return None
        except Exception as e:
            st.error(f"Schwab API error for {symbol}: {str(e)}")
            return None

    def get_quotes(self, symbols):
        if not self.client:
            return {}
        try:
            resp = self.client.get_quotes(symbols)
            if resp.status_code == httpx.codes.OK:
                return resp.json()
            st.error(f"Error fetching quotes: {resp.status_code}")
            return {}
        except Exception as e:
            st.error(f"Schwab API error: {str(e)}")
            return {}

    def get_price_history(self, symbol, period_type='month', period=1,
                          frequency_type='daily', frequency=1):
        if not self.client:
            return None
        try:
            resp = self.client.get_price_history(
                symbol,
                period_type=period_type,
                period=period,
                frequency_type=frequency_type,
                frequency=frequency
            )
            if resp.status_code == httpx.codes.OK:
                data = resp.json()
                if 'candles' in data:
                    df = pd.DataFrame(data['candles'])
                    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                    df.set_index('datetime', inplace=True)
                    df.rename(columns={
                        'open': 'Open', 'high': 'High',
                        'low': 'Low', 'close': 'Close', 'volume': 'Volume'
                    }, inplace=True)
                    return df
                return None
            st.error(f"Error fetching price history for {symbol}: {resp.status_code}")
            return None
        except Exception as e:
            st.error(f"Schwab price history error for {symbol}: {str(e)}")
            return None

    def get_option_chain(self, symbol, contract_type='ALL', strike_count=20,
                         include_quotes=True):
        if not self.client:
            return None
        try:
            resp = self.client.get_option_chain(
                symbol,
                contract_type=contract_type,
                strike_count=strike_count,
                include_quotes=include_quotes
            )
            if resp.status_code == httpx.codes.OK:
                return resp.json()
            st.error(f"Error fetching option chain for {symbol}: {resp.status_code}")
            return None
        except Exception as e:
            st.error(f"Schwab option chain error for {symbol}: {str(e)}")
            return None

    def get_stock_data_realtime(self, symbols, period='1M'):
        """Returns DataFrame with Close prices for compatibility"""
        if not self.client:
            return pd.DataFrame()
        try:
            period_map = {
                '1D': {'period_type': 'day',   'period': 1, 'frequency_type': 'minute', 'frequency': 5},
                '5D': {'period_type': 'day',   'period': 5, 'frequency_type': 'minute', 'frequency': 15},
                '1M': {'period_type': 'month', 'period': 1, 'frequency_type': 'daily',  'frequency': 1},
                '3M': {'period_type': 'month', 'period': 3, 'frequency_type': 'daily',  'frequency': 1},
                '6M': {'period_type': 'month', 'period': 6, 'frequency_type': 'daily',  'frequency': 1},
                '1Y': {'period_type': 'year',  'period': 1, 'frequency_type': 'daily',  'frequency': 1},
            }
            params = period_map.get(period, period_map['1M'])
            data_dict = {}
            for symbol in symbols:
                df = self.get_price_history(symbol, **params)
                if df is not None and not df.empty:
                    data_dict[symbol] = df['Close']
            return pd.DataFrame(data_dict) if data_dict else pd.DataFrame()
        except Exception as e:
            st.error(f"Error fetching real-time stock data: {str(e)}")
            return pd.DataFrame()

    def get_realtime_prices(self, symbols):
        if not self.client:
            return {}
        quotes = self.get_quotes(symbols)
        prices = {}
        for symbol in symbols:
            if symbol in quotes:
                q = quotes[symbol].get('quote', {})
                prices[symbol] = {
                    'price': q.get('lastPrice', 0),
                    'change': q.get('netChange', 0),
                    'change_percent': q.get('netPercentChange', 0),
                    'volume': q.get('totalVolume', 0),
                    'bid': q.get('bidPrice', 0),
                    'ask': q.get('askPrice', 0),
                    'high': q.get('highPrice', 0),
                    'low': q.get('lowPrice', 0),
                    'open': q.get('openPrice', 0),
                    'close': q.get('closePrice', 0),
                }
        return prices


# ---------------------------------------------------------------------------
# DataFetcher — caching layer + Yahoo Finance + SchwabDataFetcher fallback
# ---------------------------------------------------------------------------

class DataFetcher:
    """Handles all data fetching: Schwab real-time first, Yahoo Finance fallback"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self._cache = {}
        self._cache_timestamps = {}
        self.cache_duration = 30  # seconds

        self.schwab = SchwabDataFetcher()
        self.using_schwab = self.schwab.is_available()

    # -- Cache helpers -------------------------------------------------------

    def _get_cache_key(self, method_name, *args):
        stable_args = []
        for arg in args:
            if isinstance(arg, (list, tuple)):
                stable_args.append(str(sorted(str(i) for i in arg)))
            else:
                stable_args.append(str(arg))
        key_string = f"{method_name}|{'^'.join(sorted(stable_args))}"
        return f"{method_name}_{abs(hash(key_string))}"

    def _is_cache_valid(self, cache_key):
        if cache_key not in self._cache_timestamps:
            return False
        return (time.time() - self._cache_timestamps[cache_key]) < self.cache_duration

    def _get_from_cache(self, cache_key):
        return self._cache.get(cache_key) if self._is_cache_valid(cache_key) else None

    def _store_in_cache(self, cache_key, data):
        self._cache[cache_key] = data
        self._cache_timestamps[cache_key] = time.time()

    # -- Public API ----------------------------------------------------------

    def get_stock_data(self, symbols, period='1M'):
        """Fetch stock data — Schwab first, Yahoo fallback"""
        cache_key = self._get_cache_key('stock_data', symbols, period)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        if self.using_schwab:
            try:
                result = self.schwab.get_stock_data_realtime(symbols, period)
                if not result.empty:
                    st.success("✅ Using Schwab API (Real-time data)")
                    self._store_in_cache(cache_key, result)
                    return result
            except Exception as e:
                st.warning(f"Schwab API error, falling back to Yahoo Finance: {str(e)}")

        # Yahoo Finance fallback
        try:
            period_map = {
                '1D': '1d', '5D': '5d', '1M': '1mo',
                '3M': '3mo', '6M': '6mo', '1Y': '1y'
            }
            interval_map = {
                '1D': '5m', '5D': '15m', '1M': '1h',
                '3M': '1d', '6M': '1d', '1Y': '1d'
            }
            yf_period = period_map.get(period, '1mo')
            yf_interval = interval_map.get(period, '1d')

            st.info("ℹ️ Using Yahoo Finance (15-min delayed data)")
            data_dict = {}
            for symbol in symbols:
                try:
                    hist = yf.Ticker(symbol).history(period=yf_period, interval=yf_interval)
                    if not hist.empty:
                        data_dict[symbol] = hist['Close']
                    else:
                        st.warning(f"No data available for {symbol}")
                except Exception as e:
                    st.error(f"Error fetching data for {symbol}: {str(e)}")

            result = pd.DataFrame(data_dict) if data_dict else pd.DataFrame()
            self._store_in_cache(cache_key, result)
            return result

        except Exception as e:
            st.error(f"Error in get_stock_data: {str(e)}")
            return pd.DataFrame()

    def get_stock_info(self, symbol):
        """Get detailed stock information"""
        try:
            info = yf.Ticker(symbol).info
            return {
                'current_price':        info.get('currentPrice', 0),
                'previous_close':       info.get('previousClose', 0),
                'open_price':           info.get('open', 0),
                'day_high':             info.get('dayHigh', 0),
                'day_low':              info.get('dayLow', 0),
                'volume':               info.get('volume', 0),
                'avg_volume':           info.get('averageVolume', 0),
                'market_cap':           info.get('marketCap', 0),
                'pe_ratio':             info.get('trailingPE', 0),
                'beta':                 info.get('beta', 0),
                'fifty_two_week_high':  info.get('fiftyTwoWeekHigh', 0),
                'fifty_two_week_low':   info.get('fiftyTwoWeekLow', 0),
            }
        except Exception as e:
            st.error(f"Error fetching info for {symbol}: {str(e)}")
            return {}

    def get_options_data(self, symbol):
        """Fetch options data with caching"""
        cache_key = self._get_cache_key('options_data', symbol)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        try:
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return None, None
            chain = ticker.option_chain(expirations[0])
            result = (chain.calls, chain.puts)
            self._store_in_cache(cache_key, result)
            return result
        except Exception as e:
            st.error(f"Error fetching options data for {symbol}: {str(e)}")
            result = (None, None)
            self._store_in_cache(cache_key, result)
            return result

    def get_volume_data(self, symbols, period='1M'):
        """Fetch volume data for dark pool analysis"""
        cache_key = self._get_cache_key('volume_data', symbols, period)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached
        try:
            period_map = {
                '1D': '1d', '5D': '5d', '1M': '1mo',
                '3M': '3mo', '6M': '6mo', '1Y': '1y'
            }
            interval_map = {
                '1D': '5m', '5D': '15m', '1M': '1h',
                '3M': '1d', '6M': '1d', '1Y': '1d'
            }
            yf_period = period_map.get(period, '1mo')
            yf_interval = interval_map.get(period, '1d')

            volume_data = {}
            for symbol in symbols:
                try:
                    hist = yf.Ticker(symbol).history(period=yf_period, interval=yf_interval)
                    if not hist.empty:
                        volume_data[symbol] = {
                            'volume': hist['Volume'].values,
                            'close':  hist['Close'].values,
                            'high':   hist['High'].values,
                            'low':    hist['Low'].values,
                            'dates':  hist.index,
                        }
                except Exception as e:
                    st.error(f"Error fetching volume data for {symbol}: {str(e)}")

            self._store_in_cache(cache_key, volume_data)
            return volume_data
        except Exception as e:
            st.error(f"Error in get_volume_data: {str(e)}")
            empty = {}
            self._store_in_cache(cache_key, empty)
            return empty

    def calculate_dark_pool_indicators(self, symbol):
        """Calculate dark pool activity indicators"""
        try:
            hist = yf.Ticker(symbol).history(period='1mo', interval='1d')
            if hist.empty:
                return {}
            volumes = hist['Volume']
            prices  = hist['Close']
            vwap    = (prices * volumes).cumsum() / volumes.cumsum()
            avg_vol = volumes.rolling(20).mean()
            unusual = volumes > (avg_vol * 1.5)
            vol_ratio = volumes / avg_vol
            return {
                'vwap':               vwap.iloc[-1] if len(vwap) > 0 else 0,
                'current_price':      prices.iloc[-1] if len(prices) > 0 else 0,
                'unusual_volume_pct': (unusual.sum() / len(unusual)) * 100,
                'avg_volume':         avg_vol.iloc[-1] if len(avg_vol) > 0 else 0,
                'current_volume':     volumes.iloc[-1] if len(volumes) > 0 else 0,
                'volume_ratio':       vol_ratio.iloc[-1] if len(vol_ratio) > 0 else 0,
            }
        except Exception as e:
            st.error(f"Error calculating dark pool indicators for {symbol}: {str(e)}")
            return {}

    def get_market_sentiment(self):
        """Get overall market sentiment indicators"""
        try:
            sentiment = {}
            vix_data = yf.Ticker("^VIX").history(period='5d', interval='1d')
            btc_data = yf.Ticker("BTC-USD").history(period='5d', interval='1d')
            if not vix_data.empty:
                current_vix = vix_data['Close'].iloc[-1]
                sentiment['vix'] = current_vix
                sentiment['fear_greed'] = self._calculate_fear_greed(current_vix)
            if not btc_data.empty:
                btc_price  = btc_data['Close'].iloc[-1]
                btc_change = ((btc_price - btc_data['Close'].iloc[-2]) / btc_data['Close'].iloc[-2]) * 100
                sentiment['btc_price']  = btc_price
                sentiment['btc_change'] = btc_change
            return sentiment
        except Exception as e:
            st.error(f"Error fetching market sentiment: {str(e)}")
            return {}

    def _calculate_fear_greed(self, vix_value):
        if vix_value > 30:
            return "Fear"
        elif vix_value > 20:
            return "Neutral"
        return "Greed"


# ---------------------------------------------------------------------------
# EnhancedDataFetcher — full OAuth management + streaming (SchwabClient based)
# ---------------------------------------------------------------------------

class EnhancedDataFetcher:
    """Enhanced fetcher: Schwab real-time with full OAuth + DataFetcher fallback"""

    def __init__(self):
        self.yahoo_fetcher = DataFetcher()
        self.data_source = "yahoo"
        self.last_data_timestamp: Dict = {}

        if SCHWAB_CLIENT_AVAILABLE:
            self.schwab_client = SchwabClient()
            self._load_schwab_config()
        else:
            self.schwab_client = None

    def _load_schwab_config(self):
        if not self.schwab_client:
            return
        try:
            if (hasattr(st.session_state, 'schwab_app_key') and
                    hasattr(st.session_state, 'schwab_app_secret')):
                self.schwab_client.configure_credentials(
                    st.session_state.schwab_app_key,
                    st.session_state.schwab_app_secret,
                )
                if hasattr(st.session_state, 'schwab_access_token'):
                    self.schwab_client.access_token  = st.session_state.schwab_access_token
                    self.schwab_client.refresh_token = getattr(st.session_state, 'schwab_refresh_token', None)
                    self.schwab_client.token_expires = getattr(st.session_state, 'schwab_token_expires', None)
                    self.data_source = "schwab"
        except Exception as e:
            st.warning(f"Schwab configuration issue: {e}")

    def configure_schwab_api(self, app_key: str, app_secret: str):
        if not self.schwab_client:
            st.error("SchwabClient not available.")
            return
        self.schwab_client.configure_credentials(app_key, app_secret)
        st.session_state.schwab_app_key    = app_key
        st.session_state.schwab_app_secret = app_secret
        st.success("Schwab API credentials configured!")

    def authenticate_schwab(self, auth_code: str) -> bool:
        if not self.schwab_client:
            return False
        try:
            self.schwab_client.exchange_code_for_tokens(auth_code)
            st.session_state.schwab_access_token  = self.schwab_client.access_token
            st.session_state.schwab_refresh_token = self.schwab_client.refresh_token
            st.session_state.schwab_token_expires = self.schwab_client.token_expires
            self.data_source = "schwab"
            st.success("🎉 Schwab API authenticated! Now using real-time data.")
            return True
        except Exception as e:
            st.error(f"Schwab authentication failed: {e}")
            return False

    def get_data_source_status(self) -> Dict:
        status = {
            'source':      self.data_source,
            'is_realtime': self.data_source == 'schwab',
            'last_update': self.last_data_timestamp.get('last_fetch'),
            'token_expires': None,
            'needs_auth': False,
        }
        if self.data_source == 'schwab' and self.schwab_client:
            status['token_expires'] = self.schwab_client.token_expires
            status['needs_auth']    = not self.schwab_client.access_token
        return status

    def get_stock_data(self, symbols: List[str], period: str = '1M') -> pd.DataFrame:
        try:
            if (self.data_source == 'schwab' and self.schwab_client and
                    self.schwab_client.access_token):
                return self._get_schwab_stock_data(symbols, period)
            return self._get_yahoo_stock_data(symbols, period)
        except Exception as e:
            st.warning(f"Primary data source failed, using fallback: {e}")
            return self._get_yahoo_stock_data(symbols, period)

    def _get_schwab_stock_data(self, symbols: List[str], period: str) -> pd.DataFrame:
        try:
            if period == '1D':
                quotes_data = self.schwab_client.get_quotes(symbols)
                df = schwab_quotes_to_dataframe(quotes_data)
                result = pd.DataFrame(index=[datetime.now()])
                for _, row in df.iterrows():
                    result[row['symbol']] = row['price']
                self.last_data_timestamp['last_fetch'] = datetime.now()
                return result

            period_map = {
                '5D': {'periodType': 'day',   'period': 5, 'frequencyType': 'minute', 'frequency': 30},
                '1M': {'periodType': 'month', 'period': 1, 'frequencyType': 'daily',  'frequency': 1},
                '3M': {'periodType': 'month', 'period': 3, 'frequencyType': 'daily',  'frequency': 1},
                '6M': {'periodType': 'month', 'period': 6, 'frequencyType': 'daily',  'frequency': 1},
                '1Y': {'periodType': 'year',  'period': 1, 'frequencyType': 'daily',  'frequency': 1},
            }
            params = period_map.get(period, period_map['1M'])
            data_dict = {}
            for symbol in symbols:
                try:
                    history_data = self.schwab_client.get_price_history(symbol, **params)
                    if 'candles' in history_data:
                        prices     = [c['close'] for c in history_data['candles']]
                        timestamps = [datetime.fromtimestamp(c['datetime'] / 1000)
                                      for c in history_data['candles']]
                        data_dict[symbol] = pd.Series(prices, index=timestamps)
                except Exception as e:
                    st.warning(f"Failed to get {symbol} history: {e}")

            if data_dict:
                self.last_data_timestamp['last_fetch'] = datetime.now()
                return pd.DataFrame(data_dict)
            return pd.DataFrame()
        except Exception as e:
            raise Exception(f"Schwab data fetch failed: {e}")

    def _get_yahoo_stock_data(self, symbols: List[str], period: str) -> pd.DataFrame:
        result = self.yahoo_fetcher.get_stock_data(symbols, period)
        self.last_data_timestamp['last_fetch'] = datetime.now()
        return result

    def get_options_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        try:
            if (self.data_source == 'schwab' and self.schwab_client and
                    self.schwab_client.access_token):
                return self._get_schwab_options_data(symbol)
            return self._get_yahoo_options_data(symbol)
        except Exception as e:
            st.warning(f"Primary options data source failed, using fallback: {e}")
            return self._get_yahoo_options_data(symbol)

    def _get_schwab_options_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        try:
            options_data = self.schwab_client.get_option_chain(symbol, strike_count=20)
            calls_df, puts_df = schwab_options_to_dataframe(options_data)
            self.last_data_timestamp[f'{symbol}_options'] = datetime.now()
            return calls_df, puts_df
        except Exception as e:
            raise Exception(f"Schwab options data failed: {e}")

    def _get_yahoo_options_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        result = self.yahoo_fetcher.get_options_data(symbol)
        self.last_data_timestamp[f'{symbol}_options'] = datetime.now()
        return result

    def get_stock_info(self, symbol: str) -> Dict:
        try:
            if (self.data_source == 'schwab' and self.schwab_client and
                    self.schwab_client.access_token):
                quote_data = self.schwab_client.get_quote(symbol)
                if symbol in quote_data and 'quote' in quote_data[symbol]:
                    q = quote_data[symbol]['quote']
                    return {
                        'current_price':      q.get('lastPrice', 0),
                        'regularMarketPrice': q.get('lastPrice', 0),
                        'bid':        q.get('bidPrice', 0),
                        'ask':        q.get('askPrice', 0),
                        'volume':     q.get('totalVolume', 0),
                        'marketCap':  q.get('marketCap', 0),
                        'shortName':  q.get('description', symbol),
                        'data_source': 'schwab_realtime',
                    }
            result = self.yahoo_fetcher.get_stock_info(symbol)
            result['data_source'] = 'yahoo_delayed'
            return result
        except Exception as e:
            st.warning(f"Stock info fetch failed: {e}")
            return {'current_price': 0, 'data_source': 'error'}

    def start_real_time_streaming(self, symbols: List[str], callback=None) -> bool:
        if not self.schwab_client or self.data_source != 'schwab' or not self.schwab_client.access_token:
            st.error("Real-time streaming requires Schwab API authentication")
            return False
        try:
            success = self.schwab_client.start_streaming()
            if success and symbols:
                self.schwab_client.subscribe_quotes(symbols, callback)
                st.success(f"🚀 Real-time streaming started for: {', '.join(symbols)}")
                return True
            return False
        except Exception as e:
            st.error(f"Streaming failed: {e}")
            return False
