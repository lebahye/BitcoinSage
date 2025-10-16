import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from schwab import auth, client
import httpx
import json

class SchwabDataFetcher:
    """Real-time market data fetcher using Schwab API"""
    
    def __init__(self):
        self.client = None
        self.token_path = './schwab_token.json'
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Schwab API client with OAuth2 authentication"""
        try:
            api_key = os.environ.get('SCHWAB_APP_KEY')
            app_secret = os.environ.get('SCHWAB_APP_SECRET')
            callback_url = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')
            
            if not api_key or not app_secret:
                st.warning("⚠️ Schwab API credentials not configured. Using Yahoo Finance fallback.")
                return None
            
            if os.path.exists(self.token_path):
                with open(self.token_path, 'r') as f:
                    token_data = json.load(f)
                    
                self.client = auth.client_from_token_file(
                    self.token_path,
                    api_key,
                    app_secret
                )
            else:
                st.info("🔐 First-time Schwab API setup required. This will open a browser window for authentication.")
                
                self.client = auth.easy_client(
                    api_key=api_key,
                    app_secret=app_secret,
                    callback_url=callback_url,
                    token_path=self.token_path
                )
            
            return self.client
            
        except Exception as e:
            st.error(f"Schwab API initialization error: {str(e)}")
            return None
    
    def is_available(self):
        """Check if Schwab API is available"""
        return self.client is not None
    
    def get_quote(self, symbol):
        """Get real-time quote for a symbol"""
        if not self.client:
            return None
        
        try:
            resp = self.client.get_quote(symbol)
            
            if resp.status_code == httpx.codes.OK:
                data = resp.json()
                return data.get(symbol, {})
            else:
                st.error(f"Error fetching quote for {symbol}: {resp.status_code}")
                return None
                
        except Exception as e:
            st.error(f"Schwab API error for {symbol}: {str(e)}")
            return None
    
    def get_quotes(self, symbols):
        """Get real-time quotes for multiple symbols"""
        if not self.client:
            return {}
        
        try:
            resp = self.client.get_quotes(symbols)
            
            if resp.status_code == httpx.codes.OK:
                return resp.json()
            else:
                st.error(f"Error fetching quotes: {resp.status_code}")
                return {}
                
        except Exception as e:
            st.error(f"Schwab API error: {str(e)}")
            return {}
    
    def get_price_history(self, symbol, period_type='month', period=1, frequency_type='daily', frequency=1):
        """
        Get historical price data
        
        period_type: day, month, year, ytd
        period: number of periods
        frequency_type: minute, daily, weekly, monthly
        frequency: interval
        """
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
                    candles = data['candles']
                    df = pd.DataFrame(candles)
                    
                    df['datetime'] = pd.to_datetime(df['datetime'], unit='ms')
                    df.set_index('datetime', inplace=True)
                    
                    df.rename(columns={
                        'open': 'Open',
                        'high': 'High',
                        'low': 'Low',
                        'close': 'Close',
                        'volume': 'Volume'
                    }, inplace=True)
                    
                    return df
                else:
                    return None
                    
            else:
                st.error(f"Error fetching price history for {symbol}: {resp.status_code}")
                return None
                
        except Exception as e:
            st.error(f"Schwab price history error for {symbol}: {str(e)}")
            return None
    
    def get_option_chain(self, symbol, contract_type='ALL', strike_count=20, include_quotes=True):
        """
        Get options chain for a symbol
        
        contract_type: CALL, PUT, or ALL
        strike_count: number of strikes to return
        include_quotes: include underlying quote
        """
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
            else:
                st.error(f"Error fetching option chain for {symbol}: {resp.status_code}")
                return None
                
        except Exception as e:
            st.error(f"Schwab option chain error for {symbol}: {str(e)}")
            return None
    
    def get_stock_data_realtime(self, symbols, period='1M'):
        """
        Get real-time stock data for given symbols
        Returns DataFrame with Close prices for compatibility with existing code
        """
        if not self.client:
            return pd.DataFrame()
        
        try:
            period_map = {
                '1D': {'period_type': 'day', 'period': 1, 'frequency_type': 'minute', 'frequency': 5},
                '5D': {'period_type': 'day', 'period': 5, 'frequency_type': 'minute', 'frequency': 15},
                '1M': {'period_type': 'month', 'period': 1, 'frequency_type': 'daily', 'frequency': 1},
                '3M': {'period_type': 'month', 'period': 3, 'frequency_type': 'daily', 'frequency': 1},
                '6M': {'period_type': 'month', 'period': 6, 'frequency_type': 'daily', 'frequency': 1},
                '1Y': {'period_type': 'year', 'period': 1, 'frequency_type': 'daily', 'frequency': 1}
            }
            
            params = period_map.get(period, period_map['1M'])
            
            data_dict = {}
            for symbol in symbols:
                df = self.get_price_history(
                    symbol,
                    period_type=params['period_type'],
                    period=params['period'],
                    frequency_type=params['frequency_type'],
                    frequency=params['frequency']
                )
                
                if df is not None and not df.empty:
                    data_dict[symbol] = df['Close']
            
            if data_dict:
                return pd.DataFrame(data_dict)
            else:
                return pd.DataFrame()
                
        except Exception as e:
            st.error(f"Error fetching real-time stock data: {str(e)}")
            return pd.DataFrame()
    
    def get_realtime_prices(self, symbols):
        """Get current real-time prices for symbols"""
        if not self.client:
            return {}
        
        quotes = self.get_quotes(symbols)
        prices = {}
        
        for symbol in symbols:
            if symbol in quotes:
                quote_data = quotes[symbol].get('quote', {})
                prices[symbol] = {
                    'price': quote_data.get('lastPrice', 0),
                    'change': quote_data.get('netChange', 0),
                    'change_percent': quote_data.get('netPercentChange', 0),
                    'volume': quote_data.get('totalVolume', 0),
                    'bid': quote_data.get('bidPrice', 0),
                    'ask': quote_data.get('askPrice', 0),
                    'high': quote_data.get('highPrice', 0),
                    'low': quote_data.get('lowPrice', 0),
                    'open': quote_data.get('openPrice', 0),
                    'close': quote_data.get('closePrice', 0)
                }
        
        return prices
