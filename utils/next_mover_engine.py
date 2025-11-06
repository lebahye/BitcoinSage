"""
Next Mover Prediction Engine
Analyzes all 9 mining stocks to predict which will run next
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.data_fetcher import DataFetcher
from utils.advanced_ta import AdvancedTA
from utils.options_analyzer import OptionsAnalyzer


class NextMoverEngine:
    """Predictive engine to identify which mining stock will move next"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.advanced_ta = AdvancedTA()
        self.options_analyzer = OptionsAnalyzer()
        
        # All 9 mining stocks in user's portfolio
        self.mining_stocks = ['RIOT', 'MARA', 'CLSK', 'HUT', 'IREN', 'BITF', 'BTBT', 'WULF', 'CIFR']
        
    def get_comparative_performance(self, period='3M'):
        """
        Get normalized performance chart data (like screenshot)
        Returns DataFrame with normalized prices for all stocks
        """
        # Fetch data for all mining stocks
        stock_data = self.data_fetcher.get_stock_data(self.mining_stocks, period=period)
        
        if stock_data.empty:
            return pd.DataFrame()
        
        # Normalize to 100 at start (percentage performance)
        normalized = pd.DataFrame()
        for symbol in self.mining_stocks:
            if symbol in stock_data.columns:
                prices = stock_data[symbol].dropna()
                if len(prices) > 0:
                    normalized[symbol] = (prices / prices.iloc[0]) * 100
        
        return normalized
    
    def analyze_relative_strength(self, period='1M'):
        """
        Identify laggards (underperformers likely to catch up)
        Returns dict with relative strength scores
        """
        stock_data = self.data_fetcher.get_stock_data(self.mining_stocks, period=period)
        
        if stock_data.empty:
            return {}
        
        scores = {}
        performances = {}
        
        # Calculate performance for each stock
        for symbol in self.mining_stocks:
            if symbol in stock_data.columns:
                prices = stock_data[symbol].dropna()
                if len(prices) > 1:
                    performance = ((prices.iloc[-1] / prices.iloc[0]) - 1) * 100
                    performances[symbol] = performance
        
        if not performances:
            return {}
        
        # Average performance
        avg_performance = np.mean(list(performances.values()))
        
        # Score based on underperformance (laggards get higher scores)
        for symbol, perf in performances.items():
            gap = avg_performance - perf
            # Positive gap = underperforming = likely to catch up
            if gap > 5:
                score = min(100, 50 + (gap * 5))  # Strong catchup potential
            elif gap > 0:
                score = 50 + (gap * 3)  # Moderate catchup potential
            else:
                score = max(0, 50 + (gap * 2))  # Outperforming = less upside
            
            scores[symbol] = {
                'score': score,
                'performance': perf,
                'gap_to_avg': gap,
                'signal': 'Laggard - Catchup Play' if gap > 5 else ('Neutral' if abs(gap) < 2 else 'Leader')
            }
        
        return scores
    
    def analyze_technical_setup(self):
        """
        Analyze technical indicators for buy signals
        Returns dict with technical scores
        """
        scores = {}
        
        for symbol in self.mining_stocks:
            try:
                # Get recent data
                stock_data = self.data_fetcher.get_stock_data([symbol], period='3M')
                if stock_data.empty:
                    continue
                
                current_price = stock_data[symbol].iloc[-1]
                
                # Calculate RSI
                delta = stock_data[symbol].diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = 100 - (100 / (1 + rs))
                current_rsi = rsi.iloc[-1] if not rsi.empty else 50
                
                # Calculate MACD
                ema12 = stock_data[symbol].ewm(span=12).mean()
                ema26 = stock_data[symbol].ewm(span=26).mean()
                macd = ema12 - ema26
                signal_line = macd.ewm(span=9).mean()
                macd_histogram = macd - signal_line
                
                current_macd_hist = macd_histogram.iloc[-1] if not macd_histogram.empty else 0
                prev_macd_hist = macd_histogram.iloc[-2] if len(macd_histogram) > 1 else 0
                
                # Volume analysis
                vol_avg = stock_data[symbol].rolling(20).mean()
                if vol_avg.iloc[-1] > 0:
                    vol_ratio = current_price / vol_avg.iloc[-1]
                else:
                    vol_ratio = 1
                
                # Scoring
                tech_score = 0
                signals = []
                
                # RSI signals (oversold = bullish)
                if current_rsi < 30:
                    tech_score += 30
                    signals.append("RSI Oversold (<30)")
                elif current_rsi < 40:
                    tech_score += 20
                    signals.append("RSI Near Oversold")
                elif current_rsi > 70:
                    tech_score -= 10
                    signals.append("RSI Overbought")
                
                # MACD crossover
                if current_macd_hist > 0 and prev_macd_hist <= 0:
                    tech_score += 25
                    signals.append("MACD Bullish Crossover")
                elif current_macd_hist > prev_macd_hist:
                    tech_score += 10
                    signals.append("MACD Strengthening")
                
                # Volume
                if vol_ratio > 1.5:
                    tech_score += 15
                    signals.append("High Volume Breakout")
                
                # Normalize score
                tech_score = max(0, min(100, 50 + tech_score))
                
                scores[symbol] = {
                    'score': tech_score,
                    'rsi': current_rsi,
                    'macd_signal': 'Bullish' if current_macd_hist > 0 else 'Bearish',
                    'volume_ratio': vol_ratio,
                    'signals': signals
                }
                
            except Exception as e:
                scores[symbol] = {'score': 50, 'signals': ['Error calculating'], 'rsi': 50}
        
        return scores
    
    def analyze_bitcoin_correlation(self, period='1M'):
        """
        Analyze correlation to Bitcoin and identify high-beta stocks
        Returns dict with correlation scores
        """
        scores = {}
        
        try:
            # Get Bitcoin data
            btc_data = self.data_fetcher.get_stock_data(['BTC-USD'], period=period)
            if btc_data.empty:
                return {}
            
            btc_returns = btc_data['BTC-USD'].pct_change().dropna()
            btc_trend = ((btc_data['BTC-USD'].iloc[-1] / btc_data['BTC-USD'].iloc[0]) - 1) * 100
            
            # Get stock data
            stock_data = self.data_fetcher.get_stock_data(self.mining_stocks, period=period)
            
            for symbol in self.mining_stocks:
                if symbol not in stock_data.columns:
                    continue
                
                stock_returns = stock_data[symbol].pct_change().dropna()
                
                # Align indices
                common_idx = btc_returns.index.intersection(stock_returns.index)
                if len(common_idx) < 10:
                    continue
                
                btc_aligned = btc_returns.loc[common_idx]
                stock_aligned = stock_returns.loc[common_idx]
                
                # Calculate correlation and beta
                correlation = btc_aligned.corr(stock_aligned)
                beta = stock_aligned.cov(btc_aligned) / btc_aligned.var() if btc_aligned.var() > 0 else 1
                
                # Score: High beta + BTC trending up = bullish
                if btc_trend > 0:  # BTC is rallying
                    if beta > 1.5:
                        corr_score = 80
                        signal = "High Beta to BTC Rally"
                    elif beta > 1.0:
                        corr_score = 65
                        signal = "Above Average Beta"
                    else:
                        corr_score = 45
                        signal = "Low Beta to BTC"
                else:  # BTC declining
                    if beta < 0.8:
                        corr_score = 70
                        signal = "Low Beta - Defensive"
                    else:
                        corr_score = 40
                        signal = "High Beta - BTC Exposure"
                
                scores[symbol] = {
                    'score': corr_score,
                    'correlation': correlation,
                    'beta': beta,
                    'btc_trend': btc_trend,
                    'signal': signal
                }
        
        except Exception as e:
            pass
        
        return scores
    
    def calculate_composite_score(self):
        """
        Calculate final composite score from all factors
        Returns ranked DataFrame with predictions
        """
        # Get all factor scores
        relative_strength = self.analyze_relative_strength()
        technical_setup = self.analyze_technical_setup()
        btc_correlation = self.analyze_bitcoin_correlation()
        
        # Combine scores
        composite_scores = []
        
        for symbol in self.mining_stocks:
            # Extract scores (default to 50 if missing)
            rs_score = relative_strength.get(symbol, {}).get('score', 50)
            tech_score = technical_setup.get(symbol, {}).get('score', 50)
            btc_score = btc_correlation.get(symbol, {}).get('score', 50)
            
            # Weighted average (customize weights based on preference)
            weights = {
                'relative_strength': 0.35,  # Laggards catching up
                'technical': 0.40,          # Technical setup  
                'btc_correlation': 0.25     # Bitcoin trend
            }
            
            composite = (
                rs_score * weights['relative_strength'] +
                tech_score * weights['technical'] +
                btc_score * weights['btc_correlation']
            )
            
            # Build reasoning
            reasons = []
            
            if rs_score > 60:
                rs_signal = relative_strength.get(symbol, {}).get('signal', '')
                if rs_signal:
                    reasons.append(f"🎯 {rs_signal}")
            
            tech_signals = technical_setup.get(symbol, {}).get('signals', [])
            if tech_signals:
                reasons.extend([f"📈 {sig}" for sig in tech_signals[:2]])
            
            btc_signal = btc_correlation.get(symbol, {}).get('signal', '')
            if btc_signal and btc_score > 55:
                reasons.append(f"₿ {btc_signal}")
            
            composite_scores.append({
                'Symbol': symbol,
                'Run Probability': f"{composite:.1f}%",
                'Score': composite,
                'RS Score': rs_score,
                'Tech Score': tech_score,
                'BTC Score': btc_score,
                'Key Signals': ' | '.join(reasons) if reasons else 'Neutral Setup',
                'Performance Gap': relative_strength.get(symbol, {}).get('gap_to_avg', 0),
                'RSI': technical_setup.get(symbol, {}).get('rsi', 50)
            })
        
        # Convert to DataFrame and sort by score
        df = pd.DataFrame(composite_scores)
        df = df.sort_values('Score', ascending=False).reset_index(drop=True)
        
        # Add ranking
        df.insert(0, 'Rank', range(1, len(df) + 1))
        
        return df
    
    def get_top_pick(self):
        """Get the #1 predicted stock with detailed analysis"""
        rankings = self.calculate_composite_score()
        
        if rankings.empty:
            return None
        
        top_pick = rankings.iloc[0]
        
        # Get current price
        try:
            price_data = self.data_fetcher.get_stock_data([top_pick['Symbol']], period='1D')
            current_price = price_data[top_pick['Symbol']].iloc[-1] if not price_data.empty else None
        except:
            current_price = None
        
        return {
            'symbol': top_pick['Symbol'],
            'rank': top_pick['Rank'],
            'probability': top_pick['Run Probability'],
            'score': top_pick['Score'],
            'signals': top_pick['Key Signals'],
            'current_price': current_price,
            'rsi': top_pick['RSI'],
            'performance_gap': top_pick['Performance Gap']
        }
