import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st

class AdvancedTA:
    """Advanced Technical Analysis Library - Professional-grade indicators"""
    
    def __init__(self):
        self.cache = {}
    
    def calculate_volume_profile(self, symbol, period='3mo', num_levels=24):
        """
        Calculate Volume Profile (Market Profile) - shows where volume is concentrated
        Professional traders use this to identify value areas and high-volume nodes
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval='1d')
            
            if hist.empty:
                return {}
            
            price_min = hist['Low'].min()
            price_max = hist['High'].max()
            price_range = price_max - price_min
            
            price_levels = np.linspace(price_min, price_max, num_levels)
            volume_at_price = np.zeros(num_levels)
            
            for idx, row in hist.iterrows():
                low = row['Low']
                high = row['High']
                volume = row['Volume']
                candle_range = high - low
                
                if candle_range < 0.01:
                    close_price = row['Close']
                    closest_idx = np.argmin(np.abs(price_levels - close_price))
                    volume_at_price[closest_idx] += volume
                else:
                    buckets_touched = 0
                    for i, price in enumerate(price_levels):
                        if low <= price <= high:
                            buckets_touched += 1
                    
                    if buckets_touched > 0:
                        volume_per_bucket = volume / buckets_touched
                        for i, price in enumerate(price_levels):
                            if low <= price <= high:
                                volume_at_price[i] += volume_per_bucket
            
            total_volume = volume_at_price.sum()
            volume_pct = (volume_at_price / total_volume * 100) if total_volume > 0 else volume_at_price
            
            poc_idx = np.argmax(volume_at_price)
            poc_price = float(price_levels[poc_idx])
            
            if not np.isfinite(poc_price):
                poc_price = float(hist['Close'].iloc[-1])
            
            sorted_indices = np.argsort(volume_at_price)[::-1]
            cumsum = 0
            value_area_indices = []
            
            for idx in sorted_indices:
                cumsum += volume_at_price[idx]
                value_area_indices.append(idx)
                if cumsum >= total_volume * 0.70:
                    break
            
            if not value_area_indices:
                value_area_indices = [poc_idx]
            
            value_area_high = float(price_levels[max(value_area_indices)])
            value_area_low = float(price_levels[min(value_area_indices)])
            
            if not np.isfinite(value_area_high):
                value_area_high = float(hist['High'].max())
            if not np.isfinite(value_area_low):
                value_area_low = float(hist['Low'].min())
            
            current_price = float(hist['Close'].iloc[-1])
            
            if current_price > value_area_high:
                position = "Above Value Area (Bullish)"
            elif current_price < value_area_low:
                position = "Below Value Area (Bearish)"
            else:
                position = "In Value Area (Neutral)"
            
            return {
                'price_levels': price_levels.tolist(),
                'volume_at_price': volume_at_price.tolist(),
                'volume_pct': volume_pct.tolist(),
                'poc': poc_price,
                'value_area_high': value_area_high,
                'value_area_low': value_area_low,
                'current_price': current_price,
                'position': position,
                'signal': self._interpret_volume_profile(current_price, poc_price, value_area_high, value_area_low)
            }
            
        except Exception as e:
            st.error(f"Error calculating volume profile for {symbol}: {str(e)}")
            return {}
    
    def _interpret_volume_profile(self, current_price, poc, vah, val):
        """Interpret volume profile for trading signals"""
        if current_price > vah:
            if current_price > poc * 1.05:
                return "Strong breakout above value - potential continuation or exhaustion"
            else:
                return "Above value area - test resistance, consider taking profits"
        elif current_price < val:
            if current_price < poc * 0.95:
                return "Strong breakdown below value - potential reversal or further decline"
            else:
                return "Below value area - test support, potential accumulation zone"
        else:
            distance_to_poc = abs(current_price - poc) / poc
            if distance_to_poc < 0.02:
                return "At POC (Point of Control) - high volume node, expect support/resistance"
            else:
                return "In value area - consolidation, wait for breakout direction"
    
    def calculate_anchored_vwap(self, symbol, anchor_date=None, period='1y'):
        """
        Calculate Anchored VWAP from a specific date (earnings, pivot, etc.)
        Institutional traders use this to gauge entry/exit efficiency
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval='1d')
            
            if hist.empty:
                return {}
            
            if anchor_date is None:
                anchor_date = hist.index[0]
            
            if isinstance(anchor_date, str):
                anchor_date = pd.to_datetime(anchor_date)
            
            anchor_idx = hist.index.searchsorted(anchor_date)
            hist_anchored = hist.iloc[anchor_idx:]
            
            if hist_anchored.empty:
                return {}
            
            typical_price = (hist_anchored['High'] + hist_anchored['Low'] + hist_anchored['Close']) / 3
            vwap = (typical_price * hist_anchored['Volume']).cumsum() / hist_anchored['Volume'].cumsum()
            
            std = np.sqrt(((typical_price - vwap)**2 * hist_anchored['Volume']).cumsum() / hist_anchored['Volume'].cumsum())
            
            upper_band_1 = vwap + std
            lower_band_1 = vwap - std
            upper_band_2 = vwap + 2 * std
            lower_band_2 = vwap - 2 * std
            
            current_price = hist_anchored['Close'].iloc[-1]
            current_vwap = vwap.iloc[-1]
            
            if current_price > upper_band_2.iloc[-1]:
                signal = "Extreme Overbought - Institutions may take profits"
            elif current_price > upper_band_1.iloc[-1]:
                signal = "Overbought - Above institutional average, watch for reversal"
            elif current_price < lower_band_2.iloc[-1]:
                signal = "Extreme Oversold - Institutions may accumulate"
            elif current_price < lower_band_1.iloc[-1]:
                signal = "Oversold - Below institutional average, potential bounce"
            elif current_price > current_vwap:
                signal = "Above VWAP - Bullish, institutional buyers in control"
            else:
                signal = "Below VWAP - Bearish, institutional sellers in control"
            
            return {
                'dates': hist_anchored.index.tolist(),
                'vwap': vwap.tolist(),
                'upper_band_1': upper_band_1.tolist(),
                'lower_band_1': lower_band_1.tolist(),
                'upper_band_2': upper_band_2.tolist(),
                'lower_band_2': lower_band_2.tolist(),
                'current_vwap': current_vwap,
                'current_price': current_price,
                'anchor_date': str(anchor_date),
                'signal': signal,
                'distance_from_vwap_pct': ((current_price - current_vwap) / current_vwap * 100)
            }
            
        except Exception as e:
            st.error(f"Error calculating anchored VWAP for {symbol}: {str(e)}")
            return {}
    
    def calculate_ichimoku_cloud(self, symbol, period='6mo'):
        """
        Calculate Ichimoku Cloud - Complete trend-following system
        Used by professional traders for trend direction, momentum, and support/resistance
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval='1d')
            
            if hist.empty or len(hist) < 52:
                return {}
            
            high_9 = hist['High'].rolling(window=9).max()
            low_9 = hist['Low'].rolling(window=9).min()
            tenkan_sen = (high_9 + low_9) / 2
            
            high_26 = hist['High'].rolling(window=26).max()
            low_26 = hist['Low'].rolling(window=26).min()
            kijun_sen = (high_26 + low_26) / 2
            
            senkou_span_a = ((tenkan_sen + kijun_sen) / 2).shift(26)
            
            high_52 = hist['High'].rolling(window=52).max()
            low_52 = hist['Low'].rolling(window=52).min()
            senkou_span_b = ((high_52 + low_52) / 2).shift(26)
            
            chikou_span = hist['Close'].shift(-26)
            
            current_price = hist['Close'].iloc[-1]
            current_tenkan = tenkan_sen.iloc[-1] if not pd.isna(tenkan_sen.iloc[-1]) else 0
            current_kijun = kijun_sen.iloc[-1] if not pd.isna(kijun_sen.iloc[-1]) else 0
            
            cloud_top = max(senkou_span_a.iloc[-1], senkou_span_b.iloc[-1]) if not pd.isna(senkou_span_a.iloc[-1]) else 0
            cloud_bottom = min(senkou_span_a.iloc[-1], senkou_span_b.iloc[-1]) if not pd.isna(senkou_span_a.iloc[-1]) else 0
            
            if current_price > cloud_top:
                trend = "Strong Bullish (Above Cloud)"
            elif current_price < cloud_bottom:
                trend = "Strong Bearish (Below Cloud)"
            else:
                trend = "Neutral (In Cloud - Consolidation)"
            
            tk_cross = None
            if len(tenkan_sen) > 1 and len(kijun_sen) > 1:
                if tenkan_sen.iloc[-1] > kijun_sen.iloc[-1] and tenkan_sen.iloc[-2] <= kijun_sen.iloc[-2]:
                    tk_cross = "Bullish TK Cross (Golden Cross)"
                elif tenkan_sen.iloc[-1] < kijun_sen.iloc[-1] and tenkan_sen.iloc[-2] >= kijun_sen.iloc[-2]:
                    tk_cross = "Bearish TK Cross (Death Cross)"
            
            signals = []
            if current_price > cloud_top and tk_cross == "Bullish TK Cross (Golden Cross)":
                signals.append("STRONG BUY - All Ichimoku signals bullish")
            elif current_price < cloud_bottom and tk_cross == "Bearish TK Cross (Death Cross)":
                signals.append("STRONG SELL - All Ichimoku signals bearish")
            elif current_price > cloud_top:
                signals.append("HOLD/BUY - Uptrend confirmed")
            elif current_price < cloud_bottom:
                signals.append("HOLD/SELL - Downtrend confirmed")
            else:
                signals.append("WAIT - Consolidation, no clear trend")
            
            return {
                'dates': hist.index.tolist(),
                'price': hist['Close'].tolist(),
                'tenkan_sen': tenkan_sen.tolist(),
                'kijun_sen': kijun_sen.tolist(),
                'senkou_span_a': senkou_span_a.tolist(),
                'senkou_span_b': senkou_span_b.tolist(),
                'chikou_span': chikou_span.tolist(),
                'current_price': current_price,
                'cloud_top': cloud_top,
                'cloud_bottom': cloud_bottom,
                'trend': trend,
                'tk_cross': tk_cross,
                'signals': signals,
                'cloud_color': 'bullish' if senkou_span_a.iloc[-1] > senkou_span_b.iloc[-1] else 'bearish'
            }
            
        except Exception as e:
            st.error(f"Error calculating Ichimoku Cloud for {symbol}: {str(e)}")
            return {}
    
    def calculate_fibonacci_extensions(self, symbol, period='1y'):
        """
        Calculate Fibonacci Extensions for price targets
        Professional traders use these for take-profit levels after breakouts
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval='1d')
            
            if hist.empty:
                return {}
            
            recent_high = hist['High'].max()
            recent_low = hist['Low'].min()
            
            high_date = hist['High'].idxmax()
            low_date = hist['Low'].idxmin()
            
            if high_date > low_date:
                swing_high = recent_high
                swing_low = recent_low
                direction = "bullish"
            else:
                swing_high = recent_high
                swing_low = recent_low
                direction = "bearish"
            
            diff = swing_high - swing_low
            
            retracements = {
                '0.0%': swing_high,
                '23.6%': swing_high - (diff * 0.236),
                '38.2%': swing_high - (diff * 0.382),
                '50.0%': swing_high - (diff * 0.5),
                '61.8%': swing_high - (diff * 0.618),
                '78.6%': swing_high - (diff * 0.786),
                '100.0%': swing_low
            }
            
            extensions = {
                '127.2%': swing_high + (diff * 0.272),
                '161.8%': swing_high + (diff * 0.618),
                '200.0%': swing_high + diff,
                '261.8%': swing_high + (diff * 1.618),
                '423.6%': swing_high + (diff * 3.236)
            }
            
            current_price = hist['Close'].iloc[-1]
            
            targets = []
            if direction == "bullish":
                for level, price in extensions.items():
                    if price > current_price:
                        targets.append({
                            'level': level,
                            'price': price,
                            'distance_pct': ((price - current_price) / current_price * 100)
                        })
                targets = sorted(targets, key=lambda x: x['price'])[:3]
            
            support_levels = []
            for level, price in retracements.items():
                if price < current_price:
                    support_levels.append({
                        'level': level,
                        'price': price,
                        'distance_pct': ((current_price - price) / current_price * 100)
                    })
            support_levels = sorted(support_levels, key=lambda x: x['price'], reverse=True)[:3]
            
            return {
                'swing_high': swing_high,
                'swing_low': swing_low,
                'direction': direction,
                'retracements': retracements,
                'extensions': extensions,
                'current_price': current_price,
                'next_targets': targets,
                'support_levels': support_levels
            }
            
        except Exception as e:
            st.error(f"Error calculating Fibonacci extensions for {symbol}: {str(e)}")
            return {}
    
    def calculate_market_breadth(self, symbols, period='1mo'):
        """
        Calculate Market Breadth indicators for sector analysis
        Shows strength of overall mining sector movement
        """
        try:
            advance_decline_data = []
            volume_data = []
            
            for symbol in symbols:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period=period, interval='1d')
                
                if hist.empty:
                    continue
                
                advances = (hist['Close'] > hist['Open']).sum()
                declines = (hist['Close'] < hist['Open']).sum()
                advance_decline_data.append({
                    'symbol': symbol,
                    'advances': advances,
                    'declines': declines,
                    'ad_ratio': advances / declines if declines > 0 else advances
                })
                
                avg_volume = hist['Volume'].mean()
                current_volume = hist['Volume'].iloc[-1]
                volume_data.append({
                    'symbol': symbol,
                    'avg_volume': avg_volume,
                    'current_volume': current_volume,
                    'volume_ratio': current_volume / avg_volume if avg_volume > 0 else 1
                })
            
            total_advances = sum([x['advances'] for x in advance_decline_data])
            total_declines = sum([x['declines'] for x in advance_decline_data])
            ad_line = total_advances - total_declines
            
            bullish_stocks = len([x for x in advance_decline_data if x['ad_ratio'] > 1])
            bearish_stocks = len([x for x in advance_decline_data if x['ad_ratio'] < 1])
            
            high_volume_stocks = len([x for x in volume_data if x['volume_ratio'] > 1.2])
            
            if bullish_stocks > bearish_stocks * 1.5:
                sector_strength = "Strong Bullish"
            elif bullish_stocks > bearish_stocks:
                sector_strength = "Moderately Bullish"
            elif bearish_stocks > bullish_stocks * 1.5:
                sector_strength = "Strong Bearish"
            elif bearish_stocks > bullish_stocks:
                sector_strength = "Moderately Bearish"
            else:
                sector_strength = "Neutral"
            
            return {
                'advance_decline_line': ad_line,
                'bullish_stocks': bullish_stocks,
                'bearish_stocks': bearish_stocks,
                'total_stocks': len(symbols),
                'bullish_pct': (bullish_stocks / len(symbols) * 100) if len(symbols) > 0 else 0,
                'high_volume_stocks': high_volume_stocks,
                'sector_strength': sector_strength,
                'advance_decline_data': advance_decline_data,
                'volume_data': volume_data
            }
            
        except Exception as e:
            st.error(f"Error calculating market breadth: {str(e)}")
            return {}
    
    def calculate_money_flow_index(self, symbol, period='3mo', window=14):
        """
        Calculate Money Flow Index (MFI) - Volume-weighted RSI
        Shows buying/selling pressure with volume consideration
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval='1d')
            
            if hist.empty or len(hist) < window:
                return {}
            
            typical_price = (hist['High'] + hist['Low'] + hist['Close']) / 3
            raw_money_flow = typical_price * hist['Volume']
            
            money_flow_diff = typical_price.diff()
            
            positive_flow = pd.Series(0.0, index=hist.index)
            negative_flow = pd.Series(0.0, index=hist.index)
            
            positive_flow[money_flow_diff > 0] = raw_money_flow[money_flow_diff > 0]
            negative_flow[money_flow_diff < 0] = raw_money_flow[money_flow_diff < 0]
            
            positive_mf = positive_flow.rolling(window=window).sum()
            negative_mf = negative_flow.rolling(window=window).sum()
            
            money_flow_ratio = positive_mf / negative_mf
            mfi = 100 - (100 / (1 + money_flow_ratio))
            
            current_mfi = mfi.iloc[-1] if not pd.isna(mfi.iloc[-1]) else 50
            
            if current_mfi > 80:
                signal = "Extreme Overbought - High volume selling pressure likely"
            elif current_mfi > 60:
                signal = "Overbought - Consider taking profits"
            elif current_mfi < 20:
                signal = "Extreme Oversold - High volume buying opportunity"
            elif current_mfi < 40:
                signal = "Oversold - Potential accumulation zone"
            else:
                signal = "Neutral - Balanced buying/selling pressure"
            
            return {
                'dates': hist.index.tolist(),
                'mfi': mfi.tolist(),
                'current_mfi': current_mfi,
                'signal': signal,
                'positive_money_flow': positive_mf.iloc[-1],
                'negative_money_flow': negative_mf.iloc[-1],
                'money_flow_ratio': money_flow_ratio.iloc[-1] if not pd.isna(money_flow_ratio.iloc[-1]) else 1
            }
            
        except Exception as e:
            st.error(f"Error calculating Money Flow Index for {symbol}: {str(e)}")
            return {}
    
    def calculate_elder_ray(self, symbol, period='3mo', ema_period=13):
        """
        Calculate Elder Ray Index (Bull Power & Bear Power)
        Measures buying and selling pressure relative to EMA
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period=period, interval='1d')
            
            if hist.empty or len(hist) < ema_period:
                return {}
            
            ema = hist['Close'].ewm(span=ema_period, adjust=False).mean()
            
            bull_power = hist['High'] - ema
            bear_power = hist['Low'] - ema
            
            current_bull = bull_power.iloc[-1]
            current_bear = bear_power.iloc[-1]
            
            if current_bull > 0 and current_bear > 0:
                signal = "Strong Bullish - Bulls control both highs and lows"
            elif current_bull > 0 and current_bear < 0:
                signal = "Mixed - Bulls control highs, bears control lows"
            elif current_bull < 0 and current_bear < 0:
                signal = "Strong Bearish - Bears control both highs and lows"
            else:
                signal = "Neutral"
            
            bull_trend = "Increasing" if bull_power.iloc[-1] > bull_power.iloc[-5] else "Decreasing"
            bear_trend = "Increasing" if abs(bear_power.iloc[-1]) > abs(bear_power.iloc[-5]) else "Decreasing"
            
            return {
                'dates': hist.index.tolist(),
                'bull_power': bull_power.tolist(),
                'bear_power': bear_power.tolist(),
                'ema': ema.tolist(),
                'current_bull_power': current_bull,
                'current_bear_power': current_bear,
                'bull_trend': bull_trend,
                'bear_trend': bear_trend,
                'signal': signal
            }
            
        except Exception as e:
            st.error(f"Error calculating Elder Ray Index for {symbol}: {str(e)}")
            return {}
