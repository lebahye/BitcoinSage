import requests
import base64
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import streamlit as st
import time
import threading
import websocket
from typing import Dict, List, Optional, Callable

class SchwabClient:
    """Charles Schwab Trader API client for real-time market data"""
    
    def __init__(self):
        self.base_url = "https://api.schwabapi.com"
        self.app_key = None
        self.app_secret = None
        self.access_token = None
        self.refresh_token = None
        self.token_expires = None
        self.session = requests.Session()
        
        # Streaming components
        self.streaming_session = None
        self.request_id = 0
        self.subscriptions = {}
        self.callbacks = {}
        
    def configure_credentials(self, app_key: str, app_secret: str):
        """Configure API credentials"""
        self.app_key = app_key
        self.app_secret = app_secret
    
    def get_authorization_url(self) -> str:
        """Get URL for user authorization"""
        if not self.app_key:
            raise ValueError("App key not configured")
            
        params = {
            'client_id': self.app_key,
            'redirect_uri': 'https://127.0.0.1',
            'response_type': 'code'
        }
        
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        return f"https://api.schwabapi.com/v1/oauth/authorize?{query_string}"
    
    def exchange_code_for_tokens(self, auth_code: str) -> Dict:
        """Exchange authorization code for access/refresh tokens"""
        if not self.app_key or not self.app_secret:
            raise ValueError("App credentials not configured")
            
        # Encode credentials
        credentials = f"{self.app_key}:{self.app_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'authorization_code',
            'code': auth_code,
            'redirect_uri': 'https://127.0.0.1'
        }
        
        response = requests.post(
            f"{self.base_url}/v1/oauth/token",
            headers=headers,
            data=data
        )
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            self.refresh_token = token_data.get('refresh_token')
            # Access tokens expire in 30 minutes
            self.token_expires = time.time() + token_data.get('expires_in', 1800)
            return token_data
        else:
            raise Exception(f"Token exchange failed: {response.text}")
    
    def refresh_access_token(self) -> Dict:
        """Refresh expired access token"""
        if not self.refresh_token:
            raise ValueError("No refresh token available")
            
        credentials = f"{self.app_key}:{self.app_secret}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {encoded_credentials}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token
        }
        
        response = requests.post(
            f"{self.base_url}/v1/oauth/token",
            headers=headers,
            data=data
        )
        
        if response.status_code == 200:
            token_data = response.json()
            self.access_token = token_data.get('access_token')
            if 'refresh_token' in token_data:
                self.refresh_token = token_data['refresh_token']
            self.token_expires = time.time() + token_data.get('expires_in', 1800)
            return token_data
        else:
            raise Exception(f"Token refresh failed: {response.text}")
    
    def _ensure_valid_token(self):
        """Ensure we have a valid access token"""
        if not self.access_token:
            raise ValueError("No access token. Please authenticate first.")
            
        # Check if token expires in next 5 minutes
        if self.token_expires and time.time() > (self.token_expires - 300):
            try:
                self.refresh_access_token()
            except Exception as e:
                raise Exception(f"Token refresh failed: {e}")
    
    def _make_request(self, method: str, endpoint: str, params=None, data=None) -> requests.Response:
        """Make authenticated API request"""
        self._ensure_valid_token()
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{endpoint}"
        
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=data
        )
        
        return response
    
    def get_quote(self, symbol: str) -> Dict:
        """Get real-time quote for single symbol"""
        response = self._make_request('GET', f'/marketdata/v1/{symbol}/quotes')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Quote request failed for {symbol}: {response.text}")
    
    def get_quotes(self, symbols: List[str]) -> Dict:
        """Get real-time quotes for multiple symbols"""
        symbols_param = ','.join(symbols)
        params = {'symbols': symbols_param}
        
        response = self._make_request('GET', '/marketdata/v1/quotes', params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Quotes request failed: {response.text}")
    
    def get_price_history(self, symbol: str, period_type: str = 'day', 
                         period: int = 1, frequency_type: str = 'minute', 
                         frequency: int = 1) -> Dict:
        """Get historical price data"""
        params = {
            'periodType': period_type,
            'period': period,
            'frequencyType': frequency_type, 
            'frequency': frequency
        }
        
        response = self._make_request('GET', f'/marketdata/v1/pricehistory', 
                                    params={**params, 'symbol': symbol})
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Price history failed for {symbol}: {response.text}")
    
    def get_option_chain(self, symbol: str, contract_type: str = 'ALL', 
                        strike_count: int = 10) -> Dict:
        """Get options chain for symbol"""
        params = {
            'symbol': symbol,
            'contractType': contract_type,
            'strikeCount': strike_count
        }
        
        response = self._make_request('GET', '/marketdata/v1/chains', params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Options chain failed for {symbol}: {response.text}")
    
    def get_account_info(self, account_hash: str) -> Dict:
        """Get account information"""
        response = self._make_request('GET', f'/trader/v1/accounts/{account_hash}')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Account info failed: {response.text}")
    
    def get_positions(self, account_hash: str) -> Dict:
        """Get account positions"""
        response = self._make_request('GET', f'/trader/v1/accounts/{account_hash}/positions')
        
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Positions request failed: {response.text}")

    # Streaming WebSocket Methods
    
    def start_streaming(self) -> bool:
        """Initialize streaming WebSocket connection"""
        try:
            self._ensure_valid_token()
            
            # WebSocket URL for streaming
            ws_url = "wss://api.schwabapi.com/marketdata/v1/stream"
            
            self.streaming_session = websocket.WebSocketApp(
                ws_url,
                header=[f"Authorization: Bearer {self.access_token}"],
                on_message=self._on_streaming_message,
                on_error=self._on_streaming_error,
                on_close=self._on_streaming_close,
                on_open=self._on_streaming_open
            )
            
            # Start WebSocket in separate thread
            ws_thread = threading.Thread(target=self.streaming_session.run_forever)
            ws_thread.daemon = True
            ws_thread.start()
            
            return True
            
        except Exception as e:
            st.error(f"Streaming connection failed: {e}")
            return False
    
    def subscribe_quotes(self, symbols: List[str], callback: Callable = None):
        """Subscribe to real-time Level 1 quotes"""
        if not self.streaming_session:
            raise Exception("Streaming not started. Call start_streaming() first.")
            
        self.request_id += 1
        
        request = {
            "service": "LEVELONE_EQUITIES",
            "requestid": self.request_id,
            "command": "SUBS",
            "account": "",  # Not required for market data
            "source": "",
            "parameters": {
                "keys": ",".join(symbols),
                "fields": "0,1,2,3,4,5,8,9,10,11,12,13,28,29,30,31"  # Common quote fields
            }
        }
        
        self.subscriptions[self.request_id] = {
            'type': 'quotes',
            'symbols': symbols,
            'callback': callback
        }
        
        if callback:
            self.callbacks[self.request_id] = callback
            
        self.streaming_session.send(json.dumps(request))
    
    def subscribe_options(self, symbols: List[str], callback: Callable = None):
        """Subscribe to real-time options quotes"""
        if not self.streaming_session:
            raise Exception("Streaming not started. Call start_streaming() first.")
            
        self.request_id += 1
        
        request = {
            "service": "OPTION", 
            "requestid": self.request_id,
            "command": "SUBS",
            "account": "",
            "source": "",
            "parameters": {
                "keys": ",".join(symbols),
                "fields": "0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41"
            }
        }
        
        self.subscriptions[self.request_id] = {
            'type': 'options',
            'symbols': symbols, 
            'callback': callback
        }
        
        if callback:
            self.callbacks[self.request_id] = callback
            
        self.streaming_session.send(json.dumps(request))
    
    def _on_streaming_open(self, ws):
        """Called when WebSocket connection opens"""
        st.success("🟢 Real-time data stream connected!")
    
    def _on_streaming_message(self, ws, message):
        """Handle incoming streaming messages"""
        try:
            data = json.loads(message)
            
            # Find matching callback for this data
            if 'content' in data:
                for content in data['content']:
                    service = content.get('service')
                    
                    # Find subscription with matching callback
                    for req_id, sub_info in self.subscriptions.items():
                        if req_id in self.callbacks:
                            self.callbacks[req_id](content)
                            
        except Exception as e:
            st.error(f"Streaming message error: {e}")
    
    def _on_streaming_error(self, ws, error):
        """Handle WebSocket errors"""
        st.error(f"🔴 Streaming error: {error}")
    
    def _on_streaming_close(self, ws, close_status_code, close_msg):
        """Handle WebSocket close"""
        st.warning("🟡 Real-time data stream disconnected")

# Data conversion utilities
def schwab_quotes_to_dataframe(quotes_data: Dict) -> pd.DataFrame:
    """Convert Schwab quotes response to DataFrame"""
    rows = []
    
    for symbol, quote_data in quotes_data.items():
        if 'quote' in quote_data:
            quote = quote_data['quote']
            rows.append({
                'symbol': symbol,
                'price': quote.get('lastPrice', 0),
                'bid': quote.get('bidPrice', 0),
                'ask': quote.get('askPrice', 0),
                'volume': quote.get('totalVolume', 0),
                'change': quote.get('netChange', 0),
                'change_pct': quote.get('netPercentChangeInDouble', 0),
                'high': quote.get('highPrice', 0),
                'low': quote.get('lowPrice', 0),
                'open': quote.get('openPrice', 0),
                'close': quote.get('closePrice', 0),
                'timestamp': datetime.now()
            })
    
    return pd.DataFrame(rows)

def schwab_options_to_dataframe(options_data: Dict) -> tuple:
    """Convert Schwab options chain to calls/puts DataFrames"""
    calls_data = []
    puts_data = []
    
    if 'callExpDateMap' in options_data:
        for exp_date, strikes in options_data['callExpDateMap'].items():
            for strike, contracts in strikes.items():
                for contract in contracts:
                    calls_data.append({
                        'strike': float(strike),
                        'expiration': exp_date.split(':')[0],  # Remove days to expiry
                        'lastPrice': contract.get('last', 0),
                        'bid': contract.get('bid', 0),
                        'ask': contract.get('ask', 0),
                        'volume': contract.get('totalVolume', 0),
                        'openInterest': contract.get('openInterest', 0),
                        'impliedVolatility': contract.get('volatility', 0),
                        'delta': contract.get('delta', 0),
                        'gamma': contract.get('gamma', 0),
                        'theta': contract.get('theta', 0),
                        'vega': contract.get('vega', 0),
                        'timeValue': contract.get('timeValue', 0),
                        'intrinsicValue': contract.get('intrinsicValue', 0)
                    })
    
    if 'putExpDateMap' in options_data:
        for exp_date, strikes in options_data['putExpDateMap'].items():
            for strike, contracts in strikes.items():
                for contract in contracts:
                    puts_data.append({
                        'strike': float(strike),
                        'expiration': exp_date.split(':')[0],
                        'lastPrice': contract.get('last', 0),
                        'bid': contract.get('bid', 0),
                        'ask': contract.get('ask', 0),
                        'volume': contract.get('totalVolume', 0),
                        'openInterest': contract.get('openInterest', 0),
                        'impliedVolatility': contract.get('volatility', 0),
                        'delta': contract.get('delta', 0),
                        'gamma': contract.get('gamma', 0),
                        'theta': contract.get('theta', 0),
                        'vega': contract.get('vega', 0),
                        'timeValue': contract.get('timeValue', 0),
                        'intrinsicValue': contract.get('intrinsicValue', 0)
                    })
    
    calls_df = pd.DataFrame(calls_data) if calls_data else pd.DataFrame()
    puts_df = pd.DataFrame(puts_data) if puts_data else pd.DataFrame()
    
    return calls_df, puts_df