import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import time
from typing import Dict, List, Optional, Tuple
from utils.schwab_client import SchwabClient, schwab_quotes_to_dataframe, schwab_options_to_dataframe
from utils.data_fetcher import DataFetcher  # Fallback to Yahoo Finance

class EnhancedDataFetcher:
    """Enhanced data fetcher that prioritizes Schwab real-time data with Yahoo Finance fallback"""
    
    def __init__(self):
        self.schwab_client = SchwabClient()
        self.yahoo_fetcher = DataFetcher()  # Fallback
        self.data_source = "yahoo"  # Start with yahoo, upgrade to schwab when configured
        self.last_data_timestamp = {}
        
        # Load Schwab credentials if available
        self._load_schwab_config()
    
    def _load_schwab_config(self):
        """Load Schwab API configuration from environment or session state"""
        try:
            # Check session state for credentials
            if hasattr(st.session_state, 'schwab_app_key') and hasattr(st.session_state, 'schwab_app_secret'):
                self.schwab_client.configure_credentials(
                    st.session_state.schwab_app_key,
                    st.session_state.schwab_app_secret
                )
                
                # Check for existing tokens
                if hasattr(st.session_state, 'schwab_access_token'):
                    self.schwab_client.access_token = st.session_state.schwab_access_token
                    self.schwab_client.refresh_token = getattr(st.session_state, 'schwab_refresh_token', None)
                    self.schwab_client.token_expires = getattr(st.session_state, 'schwab_token_expires', None)
                    self.data_source = "schwab"
                    
        except Exception as e:
            st.warning(f"Schwab configuration issue: {e}")
    
    def configure_schwab_api(self, app_key: str, app_secret: str):
        """Configure Schwab API credentials"""
        self.schwab_client.configure_credentials(app_key, app_secret)
        
        # Store in session state
        st.session_state.schwab_app_key = app_key
        st.session_state.schwab_app_secret = app_secret
        
        st.success("Schwab API credentials configured!")
    
    def authenticate_schwab(self, auth_code: str) -> bool:
        """Complete Schwab OAuth authentication"""
        try:
            token_data = self.schwab_client.exchange_code_for_tokens(auth_code)
            
            # Store tokens in session state
            st.session_state.schwab_access_token = self.schwab_client.access_token
            st.session_state.schwab_refresh_token = self.schwab_client.refresh_token
            st.session_state.schwab_token_expires = self.schwab_client.token_expires
            
            self.data_source = "schwab"
            st.success("🎉 Schwab API authenticated! Now using real-time data.")
            return True
            
        except Exception as e:
            st.error(f"Schwab authentication failed: {e}")
            return False
    
    def get_data_source_status(self) -> Dict:
        """Get current data source status and freshness"""
        status = {
            'source': self.data_source,
            'is_realtime': self.data_source == 'schwab',
            'last_update': self.last_data_timestamp.get('last_fetch'),
            'token_expires': None,
            'needs_auth': False
        }
        
        if self.data_source == 'schwab':
            status['token_expires'] = self.schwab_client.token_expires
            status['needs_auth'] = not self.schwab_client.access_token
            
        return status
    
    def get_stock_data(self, symbols: List[str], period: str = '1M') -> pd.DataFrame:
        """Get stock data with real-time priority"""
        try:
            if self.data_source == 'schwab' and self.schwab_client.access_token:
                return self._get_schwab_stock_data(symbols, period)
            else:
                return self._get_yahoo_stock_data(symbols, period)
                
        except Exception as e:
            st.warning(f"Primary data source failed, using fallback: {e}")
            return self._get_yahoo_stock_data(symbols, period)
    
    def _get_schwab_stock_data(self, symbols: List[str], period: str) -> pd.DataFrame:
        """Get real-time stock data from Schwab"""
        try:
            # For real-time quotes
            if period == '1D':
                quotes_data = self.schwab_client.get_quotes(symbols)
                df = schwab_quotes_to_dataframe(quotes_data)
                
                # Convert to time series format expected by app
                result = pd.DataFrame(index=[datetime.now()])
                for _, row in df.iterrows():
                    result[row['symbol']] = row['price']
                
                self.last_data_timestamp['last_fetch'] = datetime.now()
                return result
            
            # For historical data, use price history endpoint
            else:
                period_map = {
                    '5D': {'periodType': 'day', 'period': 5, 'frequencyType': 'minute', 'frequency': 30},
                    '1M': {'periodType': 'month', 'period': 1, 'frequencyType': 'daily', 'frequency': 1},
                    '3M': {'periodType': 'month', 'period': 3, 'frequencyType': 'daily', 'frequency': 1},
                    '6M': {'periodType': 'month', 'period': 6, 'frequencyType': 'daily', 'frequency': 1},
                    '1Y': {'periodType': 'year', 'period': 1, 'frequencyType': 'daily', 'frequency': 1}
                }
                
                params = period_map.get(period, period_map['1M'])
                
                data_dict = {}
                for symbol in symbols:
                    try:
                        history_data = self.schwab_client.get_price_history(symbol, **params)
                        
                        if 'candles' in history_data:
                            prices = []
                            timestamps = []
                            
                            for candle in history_data['candles']:
                                timestamps.append(datetime.fromtimestamp(candle['datetime'] / 1000))
                                prices.append(candle['close'])
                            
                            data_dict[symbol] = pd.Series(prices, index=timestamps)
                            
                    except Exception as e:
                        st.warning(f"Failed to get {symbol} history: {e}")
                        continue
                
                if data_dict:
                    result = pd.DataFrame(data_dict)
                    self.last_data_timestamp['last_fetch'] = datetime.now()
                    return result
                    
                return pd.DataFrame()
                
        except Exception as e:
            raise Exception(f"Schwab data fetch failed: {e}")
    
    def _get_yahoo_stock_data(self, symbols: List[str], period: str) -> pd.DataFrame:
        """Fallback to Yahoo Finance data"""
        result = self.yahoo_fetcher.get_stock_data(symbols, period)
        self.last_data_timestamp['last_fetch'] = datetime.now()
        return result
    
    def get_options_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Get options data with real-time priority"""
        try:
            if self.data_source == 'schwab' and self.schwab_client.access_token:
                return self._get_schwab_options_data(symbol)
            else:
                return self._get_yahoo_options_data(symbol)
                
        except Exception as e:
            st.warning(f"Primary options data source failed, using fallback: {e}")
            return self._get_yahoo_options_data(symbol)
    
    def _get_schwab_options_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Get real-time options data from Schwab"""
        try:
            options_data = self.schwab_client.get_option_chain(symbol, strike_count=20)
            calls_df, puts_df = schwab_options_to_dataframe(options_data)
            
            self.last_data_timestamp[f'{symbol}_options'] = datetime.now()
            return calls_df, puts_df
            
        except Exception as e:
            raise Exception(f"Schwab options data failed: {e}")
    
    def _get_yahoo_options_data(self, symbol: str) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Fallback to Yahoo Finance options data"""
        result = self.yahoo_fetcher.get_options_data(symbol)
        self.last_data_timestamp[f'{symbol}_options'] = datetime.now()
        return result
    
    def get_stock_info(self, symbol: str) -> Dict:
        """Get stock information"""
        try:
            if self.data_source == 'schwab' and self.schwab_client.access_token:
                # Get real-time quote which includes basic info
                quote_data = self.schwab_client.get_quote(symbol)
                
                if symbol in quote_data and 'quote' in quote_data[symbol]:
                    quote = quote_data[symbol]['quote']
                    return {
                        'current_price': quote.get('lastPrice', 0),
                        'regularMarketPrice': quote.get('lastPrice', 0),
                        'bid': quote.get('bidPrice', 0),
                        'ask': quote.get('askPrice', 0),
                        'volume': quote.get('totalVolume', 0),
                        'marketCap': quote.get('marketCap', 0),
                        'shortName': quote.get('description', symbol),
                        'data_source': 'schwab_realtime'
                    }
            
            # Fallback to Yahoo Finance
            result = self.yahoo_fetcher.get_stock_info(symbol)
            result['data_source'] = 'yahoo_delayed'
            return result
            
        except Exception as e:
            st.warning(f"Stock info fetch failed: {e}")
            return {'current_price': 0, 'data_source': 'error'}
    
    def start_real_time_streaming(self, symbols: List[str], callback=None) -> bool:
        """Start real-time streaming for symbols"""
        if self.data_source != 'schwab' or not self.schwab_client.access_token:
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