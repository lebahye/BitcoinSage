"""
Next Mover Prediction Engine
Analyzes all 9 mining stocks to predict which will run next
"""

import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
from utils.unified_data_fetcher import DataFetcher
from utils.advanced_ta import AdvancedTA
from utils.options_analytics import OptionsAnalytics as OptionsAnalyzer
from utils.sentiment_analyzer import SentimentAnalyzer
from utils.tickers import WATCHLIST


class NextMoverEngine:
    """Predictive engine to identify which mining stock will move next"""
    
    def __init__(self):
        self.data_fetcher = DataFetcher()
        self.advanced_ta = AdvancedTA()
        self.options_analyzer = OptionsAnalyzer()
        self.sentiment_analyzer = SentimentAnalyzer()
        self._ohlcv_cache = {}
        
        # All 9 mining stocks in user's portfolio
        self.mining_stocks = list(WATCHLIST)

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_ohlcv(self, symbol: str, period: str = '3mo') -> 'pd.DataFrame':
        """Return daily OHLCV DataFrame for symbol (cached per session)."""
        cache_key = f"{symbol}_{period}"
        if cache_key in self._ohlcv_cache:
            return self._ohlcv_cache[cache_key]
        try:
            hist = yf.Ticker(symbol).history(period=period, interval='1d')
            self._ohlcv_cache[cache_key] = hist
            return hist
        except Exception:
            return pd.DataFrame()

    def _get_sentiment_score(self, symbol: str) -> float:
        """Return normalised sentiment score in [-1, +1]. 0.0 on error."""
        try:
            raw = self.sentiment_analyzer.get_news_sentiment([symbol], limit=20)
            if 'error' in raw:
                return 0.0
            df = self.sentiment_analyzer.parse_sentiment_data(raw, ticker=symbol)
            agg = self.sentiment_analyzer.get_aggregate_sentiment(df, ticker=symbol)
            score = agg.get('avg_sentiment', 0.0)
            return float(np.clip(score, -1.0, 1.0))
        except Exception:
            return 0.0

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
        Analyze technical indicators — continuous scoring that differentiates stocks
        in any market condition, not just extremes.
        Returns dict with technical scores.
        """
        scores = {}

        for symbol in self.mining_stocks:
            try:
                hist = self._get_ohlcv(symbol, period='3mo')
                if hist.empty or len(hist) < 30:
                    continue

                close  = hist['Close']
                volume = hist['Volume'] if 'Volume' in hist.columns else None

                # ── RSI (14) ────────────────────────────────────────────────
                delta = close.diff()
                gain  = delta.where(delta > 0, 0).rolling(14).mean()
                loss  = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs    = gain / loss.replace(0, np.nan)
                rsi   = (100 - 100 / (1 + rs)).fillna(50)
                current_rsi = float(rsi.iloc[-1])

                # Continuous RSI score (favours stocks with room to move up)
                if current_rsi < 30:
                    rsi_pts = 30;  rsi_label = f"RSI Oversold ({current_rsi:.0f})"
                elif current_rsi < 40:
                    rsi_pts = 20;  rsi_label = f"RSI Near Oversold ({current_rsi:.0f})"
                elif current_rsi < 50:
                    rsi_pts = 8;   rsi_label = f"RSI Recovering ({current_rsi:.0f})"
                elif current_rsi < 60:
                    rsi_pts = 0;   rsi_label = f"RSI Neutral ({current_rsi:.0f})"
                elif current_rsi < 70:
                    rsi_pts = -8;  rsi_label = f"RSI Elevated ({current_rsi:.0f})"
                elif current_rsi < 80:
                    rsi_pts = -18; rsi_label = f"RSI Overbought ({current_rsi:.0f})"
                else:
                    rsi_pts = -28; rsi_label = f"RSI Extremely OB ({current_rsi:.0f})"

                # ── MACD ────────────────────────────────────────────────────
                ema12 = close.ewm(span=12).mean()
                ema26 = close.ewm(span=26).mean()
                macd_line   = ema12 - ema26
                signal_line = macd_line.ewm(span=9).mean()
                hist_vals   = macd_line - signal_line
                cur_h  = float(hist_vals.iloc[-1]) if len(hist_vals) > 0 else 0
                prev_h = float(hist_vals.iloc[-2]) if len(hist_vals) > 1 else 0
                prev2_h= float(hist_vals.iloc[-3]) if len(hist_vals) > 2 else 0

                if cur_h > 0 and prev_h <= 0:
                    macd_pts   = 22; macd_label = "MACD Bullish Crossover 🚀"
                elif cur_h > 0 and cur_h > prev_h > prev2_h:
                    macd_pts   = 14; macd_label = "MACD Accelerating Up"
                elif cur_h > 0 and cur_h > prev_h:
                    macd_pts   = 8;  macd_label = "MACD Strengthening"
                elif cur_h > 0 and cur_h < prev_h:
                    macd_pts   = 2;  macd_label = "MACD Positive (Fading)"
                elif cur_h < 0 and cur_h > prev_h:
                    macd_pts   = -5; macd_label = "MACD Recovering"
                else:
                    macd_pts   = -14; macd_label = "MACD Bearish"

                # ── Moving Averages ─────────────────────────────────────────
                ma20 = close.rolling(20).mean().iloc[-1]
                ma50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else ma20
                cur_price = float(close.iloc[-1])

                pct_above_ma20 = (cur_price - float(ma20)) / float(ma20) * 100
                above_ma50 = cur_price > float(ma50)

                if pct_above_ma20 > 5 and above_ma50:
                    ma_pts = 10;  ma_label = "Above MA20 & MA50 (Trend Strong)"
                elif pct_above_ma20 > 0 and above_ma50:
                    ma_pts = 6;   ma_label = "Above Both MAs"
                elif pct_above_ma20 > 0 and not above_ma50:
                    ma_pts = -2;  ma_label = "Above MA20, Below MA50"
                elif -3 < pct_above_ma20 <= 0:
                    ma_pts = -6;  ma_label = "Just Below MA20 (Support Test)"
                else:
                    ma_pts = -14; ma_label = "Below MA20 & MA50"

                # ── Volume ──────────────────────────────────────────────────
                vol_ratio = 1.0
                if volume is not None and len(volume) >= 21:
                    avg_vol   = float(volume.iloc[-21:-1].mean())
                    cur_vol   = float(volume.iloc[-1])
                    vol_ratio = cur_vol / avg_vol if avg_vol > 0 else 1.0

                if vol_ratio >= 2.0:
                    vol_pts = 16; vol_label = f"Volume Surge ({vol_ratio:.1f}x avg)"
                elif vol_ratio >= 1.5:
                    vol_pts = 10; vol_label = f"High Volume ({vol_ratio:.1f}x avg)"
                elif vol_ratio >= 1.2:
                    vol_pts = 4;  vol_label = f"Above-Avg Volume ({vol_ratio:.1f}x)"
                elif vol_ratio >= 0.8:
                    vol_pts = 0;  vol_label = f"Normal Volume ({vol_ratio:.1f}x)"
                else:
                    vol_pts = -6; vol_label = f"Low Volume ({vol_ratio:.1f}x avg)"

                # ── Composite ───────────────────────────────────────────────
                raw_score = 50 + rsi_pts + macd_pts + ma_pts + vol_pts
                tech_score = max(0, min(100, raw_score))

                signals = [rsi_label, macd_label, ma_label]
                if vol_ratio >= 1.2 or vol_ratio < 0.8:
                    signals.append(vol_label)

                scores[symbol] = {
                    'score':        tech_score,
                    'rsi':          current_rsi,
                    'macd_signal':  'Bullish' if cur_h > 0 else 'Bearish',
                    'volume_ratio': vol_ratio,
                    'signals':      signals,
                    '_pts': {
                        'rsi': rsi_pts, 'macd': macd_pts,
                        'ma': ma_pts,   'vol': vol_pts,
                    }
                }

            except Exception:
                scores[symbol] = {'score': 50, 'signals': ['Data unavailable'], 'rsi': 50}

        return scores
    
    def analyze_bitcoin_correlation(self, period='1M'):
        """
        Analyze correlation to Bitcoin and identify high-beta stocks
        Returns dict with correlation scores
        """
        scores = {}
        
        try:
            # Daily closes, with BTC lined up on the stock trading calendar.
            # (The old code joined hourly UTC BTC bars to hourly New York stock
            # bars, which never matched, so every stock silently got 50/100.)
            from utils.market_data import fetch_daily_closes, beta_corr, to_daily
            closes = fetch_daily_closes(tuple(list(self.mining_stocks) + ['BTC-USD']), '3mo')
            if closes.empty or 'BTC-USD' not in closes.columns:
                return {}
            btc_close = closes['BTC-USD'].dropna()
            btc_trend = ((btc_close.iloc[-1] / btc_close.iloc[0]) - 1) * 100

            for symbol in self.mining_stocks:
                if symbol not in closes.columns:
                    continue
                bc = beta_corr(closes[symbol].dropna(), btc_close)
                if bc is None:
                    continue  # no score -> shown as "n/a", never a fake 50
                correlation = bc['corr']
                beta = bc['beta']

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
    
    def analyze_sentiment_scores(self):
        """
        Fetch sentiment scores for all mining stocks — ONE batched Alpha Vantage call
        for all 9 tickers instead of 9 separate calls (stays under free-tier limit).
        Returns dict {symbol: {'score': 0-100, 'raw': float, 'label': str, 'live': bool}}
        """
        scores = {}
        neutral = {'score': 50, 'raw': 0.0, 'label': 'Neutral', 'live': False}

        try:
            # Single batch call for all stocks
            raw_data = self.sentiment_analyzer.get_news_sentiment(
                self.mining_stocks, limit=50
            )

            if 'error' in raw_data:
                # Fall back: everyone gets neutral with live=False
                for sym in self.mining_stocks:
                    scores[sym] = dict(neutral)
                return scores

            feed = raw_data.get('feed', [])
            if not feed:
                for sym in self.mining_stocks:
                    scores[sym] = dict(neutral)
                return scores

            # Accumulate per-ticker sentiment from the batch response
            ticker_totals: dict = {s: [] for s in self.mining_stocks}
            for article in feed:
                for ts in article.get('ticker_sentiment', []):
                    sym = ts.get('ticker', '')
                    if sym in ticker_totals:
                        try:
                            ticker_totals[sym].append(
                                float(ts.get('ticker_sentiment_score', 0))
                            )
                        except (ValueError, TypeError):
                            pass

            for sym in self.mining_stocks:
                vals = ticker_totals.get(sym, [])
                if vals:
                    raw = float(np.mean(vals))
                    raw = float(np.clip(raw, -1.0, 1.0))
                    score_100 = (raw + 1) / 2 * 100
                    label = ('Bullish' if raw >= 0.15
                             else 'Bearish' if raw <= -0.15
                             else 'Neutral')
                    scores[sym] = {'score': score_100, 'raw': raw,
                                   'label': label, 'live': True}
                else:
                    scores[sym] = dict(neutral)

        except Exception:
            for sym in self.mining_stocks:
                scores[sym] = dict(neutral)

        return scores

    def calculate_composite_score(self):
        """
        Calculate final composite score from all factors.
        Weights: RS=30%, Technical=40%, BTC=15%, Sentiment=15%
        Returns ranked DataFrame with predictions.
        """
        # Get all factor scores
        relative_strength = self.analyze_relative_strength()
        technical_setup = self.analyze_technical_setup()
        btc_correlation = self.analyze_bitcoin_correlation()
        sentiment_scores = self.analyze_sentiment_scores()

        # Combine scores
        composite_scores = []

        for symbol in self.mining_stocks:
            # Extract scores (default to 50 if missing)
            rs_score   = relative_strength.get(symbol, {}).get('score', 50)
            tech_score = technical_setup.get(symbol, {}).get('score', 50)
            btc_live   = symbol in btc_correlation
            # Missing BTC factor: re-weight the other factors instead of inserting a fake 50
            btc_score  = btc_correlation.get(symbol, {}).get('score', float('nan'))
            sent_score = sentiment_scores.get(symbol, {}).get('score', 50)

            # Updated weights: RS=30%, Technical=40%, BTC=15%, Sentiment=15%
            if btc_live:
                composite = (
                    rs_score   * 0.30 +
                    tech_score * 0.40 +
                    btc_score  * 0.15 +
                    sent_score * 0.15
                )
            else:
                composite = (rs_score * 0.30 + tech_score * 0.40 + sent_score * 0.15) / 0.85

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
            if btc_signal and btc_live and btc_score > 55:
                reasons.append(f"₿ {btc_signal}")

            sent_label = sentiment_scores.get(symbol, {}).get('label', 'Neutral')
            if sent_label == 'Bullish':
                reasons.append("📰 News Sentiment Bullish")
            elif sent_label == 'Bearish':
                reasons.append("📰 News Sentiment Bearish")

            composite_scores.append({
                'Symbol': symbol,
                'Run Probability': f"{composite:.1f}%",
                'Score': composite,
                'RS Score': rs_score,
                'Tech Score': tech_score,
                'BTC Score': btc_score,
                'BTC Live': btc_live,
                'Sentiment Score': sent_score,
                'Sentiment Live': sentiment_scores.get(symbol, {}).get('live', False),
                'Key Signals': ' | '.join(reasons) if reasons else 'Neutral Setup',
                'Performance Gap': relative_strength.get(symbol, {}).get('gap_to_avg', 0),
                'RSI': technical_setup.get(symbol, {}).get('rsi', 50),
                'Tech Signals': technical_setup.get(symbol, {}).get('signals', []),
                'BTC Signal': btc_correlation.get(symbol, {}).get('signal', ''),
                'Sent Label': sentiment_scores.get(symbol, {}).get('label', 'Neutral'),
            })
        
        # Convert to DataFrame and sort by score
        df = pd.DataFrame(composite_scores)
        df = df.sort_values('Score', ascending=False).reset_index(drop=True)
        
        # Add ranking
        df.insert(0, 'Rank', range(1, len(df) + 1))
        
        return df
    
    def get_earnings_data(self):
        """
        Fetch next earnings date + last 3 historical earnings with price reaction
        for all 9 mining stocks.

        Returns list of dicts:
          {symbol, next_date, days_until, history: [{date, eps_est, eps_act,
           surprise_pct, price_before, price_after, reaction_pct, beat}]}
        """
        today = datetime.now().date()
        results = []

        for symbol in self.mining_stocks:
            row = {'symbol': symbol, 'next_date': None, 'days_until': None, 'history': []}
            try:
                ticker = yf.Ticker(symbol)

                # ── Next earnings date ───────────────────────────────────────
                try:
                    cal = ticker.calendar or {}
                    raw_dates = cal.get('Earnings Date', [])
                    if raw_dates:
                        next_d = raw_dates[0]
                        if hasattr(next_d, 'date'):
                            next_d = next_d.date()
                        row['next_date'] = next_d
                        row['days_until'] = (next_d - today).days
                except Exception:
                    pass

                # ── Historical earnings + price reaction ─────────────────────
                try:
                    ed = ticker.earnings_dates
                    if ed is None or ed.empty:
                        results.append(row)
                        continue

                    # Only past earnings with reported data
                    past = ed[
                        (ed['Event Type'] == 'Earnings') &
                        (ed['Reported EPS'].notna())
                    ].head(3)

                    # Price history for reaction calculation
                    hist = ticker.history(period='2y')
                    if hist.empty:
                        results.append(row)
                        continue

                    # Normalise index to date (tz-strip)
                    hist.index = pd.to_datetime(hist.index).tz_localize(None).normalize()
                    hist = hist[~hist.index.duplicated(keep='last')]
                    price_dates = hist.index

                    for earn_dt, earn_row in past.iterrows():
                        try:
                            # Normalise earnings timestamp to date
                            earn_date = pd.Timestamp(earn_dt).tz_localize(None).normalize()

                            # Day before and 1-2 days after (handle after-hours)
                            before_candidates = price_dates[price_dates < earn_date]
                            after_candidates  = price_dates[price_dates >= earn_date]

                            if before_candidates.empty or after_candidates.empty:
                                continue

                            day_before = before_candidates[-1]
                            day_after  = after_candidates[0] if len(after_candidates) > 0 else None
                            # Prefer next trading day after announcement for after-hours
                            if len(after_candidates) > 1:
                                day_after = after_candidates[1]

                            p_before = float(hist.loc[day_before, 'Close'])
                            p_after  = float(hist.loc[day_after,  'Close']) if day_after is not None else None

                            reaction = None
                            if p_after and p_before:
                                reaction = (p_after - p_before) / p_before * 100

                            eps_est = earn_row.get('EPS Estimate')
                            eps_act = earn_row.get('Reported EPS')
                            surp    = earn_row.get('Surprise(%)')

                            beat = None
                            if pd.notna(eps_est) and pd.notna(eps_act):
                                beat = float(eps_act) > float(eps_est)

                            row['history'].append({
                                'date':         earn_date.date(),
                                'eps_est':      float(eps_est) if pd.notna(eps_est) else None,
                                'eps_act':      float(eps_act) if pd.notna(eps_act) else None,
                                'surprise_pct': float(surp)    if pd.notna(surp)    else None,
                                'price_before': p_before,
                                'price_after':  p_after,
                                'reaction_pct': reaction,
                                'beat':         beat,
                            })
                        except Exception:
                            continue
                except Exception:
                    pass

            except Exception:
                pass

            results.append(row)

        return results

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
