import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import requests
import streamlit as st

class DataFetcher:
    """Handles all data fetching operations for stocks and market data"""
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_stock_data(self, symbols, period='1M'):
        """Fetch stock data for given symbols"""
        try:
            # Convert period to yfinance format
            period_map = {
                '1D': '1d',
                '5D': '5d', 
                '1M': '1mo',
                '3M': '3mo',
                '6M': '6mo',
                '1Y': '1y'
            }
            
            yf_period = period_map.get(period, '1mo')
            
            # Fetch data for all symbols
            tickers = yf.Tickers(' '.join(symbols))
            
            data_dict = {}
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=yf_period)
                    
                    if not hist.empty:
                        data_dict[symbol] = hist['Close']
                    else:
                        st.warning(f"No data available for {symbol}")
                        
                except Exception as e:
                    st.error(f"Error fetching data for {symbol}: {str(e)}")
                    continue
            
            if data_dict:
                return pd.DataFrame(data_dict)
            else:
                return pd.DataFrame()
                
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
        """Fetch options data for a symbol"""
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
            
            return calls, puts
            
        except Exception as e:
            st.error(f"Error fetching options data for {symbol}: {str(e)}")
            return None, None
    
    def get_volume_data(self, symbols, period='1M'):
        """Fetch volume data for dark pool analysis"""
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
            
            yf_period = period_map.get(period, '1mo')
            
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period=yf_period)
                    
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
            
            return volume_data
            
        except Exception as e:
            st.error(f"Error in get_volume_data: {str(e)}")
            return {}
    
    def calculate_dark_pool_indicators(self, symbol):
        """Calculate dark pool activity indicators"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
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
            vix_data = vix.history(period='5d')
            
            # Fetch Bitcoin price for correlation
            btc = yf.Ticker("BTC-USD")
            btc_data = btc.history(period='5d')
            
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
