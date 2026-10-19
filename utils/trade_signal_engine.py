"""
Trade Signal Engine  v2
Synthesizes RSI (Wilder), MACD, Bollinger Bands, Stochastic, OBV, volume
(price-direction aware), BTC momentum, and news sentiment into BUY/HOLD/SELL
verdicts with ATR-based price targets.

Improvements over v1
─────────────────────
• Wilder's RSI (EWM alpha=1/14) — correct, not simple rolling mean
• BTC momentum as a real scored factor (+/- 20 pts)
• Volume score is direction-aware (surge on down day = bearish distribution)
• Bollinger Band %B position as a factor
• Stochastic (14,3) — second momentum confirmation
• OBV slope — institutional accumulation / distribution
• Trend regime gate — oversold in strong downtrend → HOLD not BUY
• ATR-normalized stop losses (2× ATR)
• 5-minute TTL cache (no more all-session stale data)
• data_timestamp returned with every result
"""

import time
import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime
from utils.sentiment_analyzer import SentimentAnalyzer


class TradeSignalEngine:
    MINING_STOCKS = ['RIOT', 'MARA', 'CLSK', 'HUT', 'IREN', 'KEEL', 'BTBT', 'WULF', 'CIFR']
    CACHE_TTL = 300  # seconds (5 min)

    def __init__(self):
        self.sentiment_analyzer = SentimentAnalyzer()
        self._cache: dict = {}          # key → (value, epoch_time)

    # ──────────────────────────────────────────────────────────────────────────
    # Cache helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _cache_get(self, key):
        if key in self._cache:
            val, ts = self._cache[key]
            if time.time() - ts < self.CACHE_TTL:
                return val
        return None

    def _cache_set(self, key, val):
        self._cache[key] = (val, time.time())

    def _cache_age(self, key) -> float:
        """Return seconds since cached, or inf if not cached."""
        if key in self._cache:
            return time.time() - self._cache[key][1]
        return float('inf')

    # ──────────────────────────────────────────────────────────────────────────
    # Data helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _get_ohlcv(self, symbol: str, period: str = '3mo') -> pd.DataFrame:
        key = f"ohlcv_{symbol}_{period}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        try:
            hist = yf.Ticker(symbol).history(period=period, interval='1d', auto_adjust=True)
            self._cache_set(key, hist)
            return hist
        except Exception:
            return pd.DataFrame()

    def _get_btc_data(self) -> pd.DataFrame:
        key = "btc_ohlcv"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        try:
            btc = yf.Ticker("BTC-USD").history(period='10d', interval='1d', auto_adjust=True)
            self._cache_set(key, btc)
            return btc
        except Exception:
            return pd.DataFrame()

    def _get_sentiment_score(self, symbol: str) -> float:
        key = f"sentiment_{symbol}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        try:
            raw = self.sentiment_analyzer.get_news_sentiment([symbol], limit=20)
            if 'error' in raw:
                self._cache_set(key, 0.0)
                return 0.0
            df = self.sentiment_analyzer.parse_sentiment_data(raw, ticker=symbol)
            agg = self.sentiment_analyzer.get_aggregate_sentiment(df, ticker=symbol)
            score = float(np.clip(agg.get('avg_sentiment', 0.0), -1.0, 1.0))
            self._cache_set(key, score)
            return score
        except Exception:
            self._cache_set(key, 0.0)
            return 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # Technical indicators
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_rsi(self, close: pd.Series, period: int = 14) -> float:
        """Wilder's RSI using EWM (alpha = 1/period) — correct formula."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta.where(delta < 0, 0.0))
        avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        val = rsi.iloc[-1]
        return float(val) if pd.notna(val) else 50.0

    def _calc_macd(self, close: pd.Series):
        """Return (macd_line, signal_line, histogram_now, histogram_prev)."""
        ema12 = close.ewm(span=12, adjust=False).mean()
        ema26 = close.ewm(span=26, adjust=False).mean()
        macd = ema12 - ema26
        signal = macd.ewm(span=9, adjust=False).mean()
        hist = macd - signal
        return (
            float(macd.iloc[-1]) if not macd.empty else 0.0,
            float(signal.iloc[-1]) if not signal.empty else 0.0,
            float(hist.iloc[-1]) if not hist.empty else 0.0,
            float(hist.iloc[-2]) if len(hist) > 1 else 0.0,
        )

    def _calc_atr(self, hist: pd.DataFrame, period: int = 14) -> float:
        """Wilder's ATR using EWM."""
        h = hist['High']
        l = hist['Low']
        c = hist['Close']
        prev_c = c.shift(1)
        tr = pd.concat([(h - l), (h - prev_c).abs(), (l - prev_c).abs()], axis=1).max(axis=1)
        atr = tr.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
        val = atr.iloc[-1]
        return float(val) if pd.notna(val) else float((h - l).mean())

    def _calc_bollinger(self, close: pd.Series, period: int = 20, n_std: float = 2.0):
        """Return (pct_b, upper, middle, lower). %B=0 at lower, 1 at upper."""
        ma = close.rolling(period).mean()
        sd = close.rolling(period).std()
        upper = ma + n_std * sd
        lower = ma - n_std * sd
        cur = close.iloc[-1]
        bw = upper.iloc[-1] - lower.iloc[-1]
        pct_b = (cur - lower.iloc[-1]) / bw if bw > 0 else 0.5
        return float(pct_b), float(upper.iloc[-1]), float(ma.iloc[-1]), float(lower.iloc[-1])

    def _calc_stochastic(self, hist: pd.DataFrame, k_period: int = 14, d_period: int = 3):
        """Return (%K, %D)."""
        low_min = hist['Low'].rolling(k_period).min()
        high_max = hist['High'].rolling(k_period).max()
        denom = (high_max - low_min).replace(0, np.nan)
        k = 100 * (hist['Close'] - low_min) / denom
        d = k.rolling(d_period).mean()
        k_val = k.iloc[-1]
        d_val = d.iloc[-1]
        return (
            float(k_val) if pd.notna(k_val) else 50.0,
            float(d_val) if pd.notna(d_val) else 50.0,
        )

    def _calc_obv_slope(self, hist: pd.DataFrame, window: int = 10) -> float:
        """Normalised OBV slope over last `window` bars. Positive = accumulation."""
        delta = hist['Close'].diff()
        direction = np.sign(delta).fillna(0)
        obv = (direction * hist['Volume']).cumsum()
        if len(obv) < window + 1:
            return 0.0
        base = abs(obv.iloc[-(window + 1)]) + 1
        slope = (obv.iloc[-1] - obv.iloc[-(window + 1)]) / base
        return float(np.clip(slope, -3.0, 3.0))

    def _calc_moving_averages(self, close: pd.Series):
        """Return (pct_vs_20ma, pct_vs_50ma, ma50_slope_10d)."""
        ma20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else close.mean()
        ma50_ser = close.rolling(50).mean() if len(close) >= 50 else close.rolling(len(close)).mean()
        ma50 = ma50_ser.iloc[-1]
        cur = close.iloc[-1]
        pct20 = (cur - ma20) / ma20 * 100 if ma20 > 0 else 0.0
        pct50 = (cur - ma50) / ma50 * 100 if ma50 > 0 else 0.0
        # 10-bar MA50 slope as trend regime proxy
        if len(ma50_ser.dropna()) >= 11:
            ma50_10ago = ma50_ser.dropna().iloc[-11]
            slope = (ma50 - ma50_10ago) / ma50_10ago * 100 if ma50_10ago > 0 else 0.0
        else:
            slope = 0.0
        return float(pct20), float(pct50), float(slope)

    def _calc_volume_ratio(self, volume: pd.Series, window: int = 20) -> float:
        if len(volume) < window + 1:
            return 1.0
        avg = volume.iloc[-(window + 1):-1].mean()
        cur = volume.iloc[-1]
        return float(cur / avg) if avg > 0 else 1.0

    def _calc_btc_factors(self) -> dict:
        """Return BTC 1-day and 5-day momentum and a score component."""
        btc = self._get_btc_data()
        if btc.empty or len(btc) < 2:
            return {'btc_1d': 0.0, 'btc_5d': 0.0, 'btc_score': 0, 'btc_label': 'N/A'}
        c = btc['Close']
        pct_1d = (c.iloc[-1] - c.iloc[-2]) / c.iloc[-2] * 100
        pct_5d = (c.iloc[-1] - c.iloc[max(0, len(c) - 6)]) / c.iloc[max(0, len(c) - 6)] * 100 if len(c) >= 6 else pct_1d
        # Score: BTC up strongly = tailwind; down strongly = headwind
        score = 0
        if pct_1d >= 4:
            score += 20
        elif pct_1d >= 2:
            score += 12
        elif pct_1d >= 0.5:
            score += 5
        elif pct_1d <= -4:
            score -= 20
        elif pct_1d <= -2:
            score -= 12
        elif pct_1d <= -0.5:
            score -= 5
        label = f"BTC {'▲' if pct_1d >= 0 else '▼'}{abs(pct_1d):.1f}% today"
        return {
            'btc_1d': round(pct_1d, 2),
            'btc_5d': round(pct_5d, 2),
            'btc_score': score,
            'btc_label': label,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Price targets (ATR-based)
    # ──────────────────────────────────────────────────────────────────────────

    def _calc_price_targets(self, hist: pd.DataFrame):
        if hist.empty or len(hist) < 20:
            return None
        close = hist['Close']
        cur = float(close.iloc[-1])
        atr = self._calc_atr(hist)

        # Stop: 2× ATR below entry, floored at 20-day low
        low_20 = float(hist['Low'].tail(20).min())
        stop_atr = cur - 2.0 * atr
        stop_loss = max(stop_atr, low_20)
        # Clamp stop to no more than 15% away (don't let massive ATR make stop useless)
        stop_loss = max(stop_loss, cur * 0.85)

        # Entry: current price or 5-day support
        support = float(hist['Low'].tail(5).mean())
        entry = min(cur, support * 1.005)

        # Fibonacci extension targets from 60-day swing
        swing_lo = float(hist['Low'].tail(60).min())
        swing_hi = float(hist['High'].tail(60).max())
        diff = swing_hi - swing_lo
        tp1 = swing_hi + diff * 0.272
        tp2 = swing_hi + diff * 0.618
        if cur >= swing_hi:
            tp1 = cur + 3.0 * atr
            tp2 = cur + 5.0 * atr

        risk = max(entry - stop_loss, 0.01)
        rr = (tp1 - entry) / risk
        return {
            'current_price': round(cur, 2),
            'entry': round(entry, 2),
            'stop_loss': round(stop_loss, 2),
            'take_profit_1': round(tp1, 2),
            'take_profit_2': round(tp2, 2),
            'atr': round(atr, 2),
            'risk_pct': round((entry - stop_loss) / entry * 100, 1),
            'reward_pct_tp1': round((tp1 - entry) / entry * 100, 1),
            'reward_pct_tp2': round((tp2 - entry) / entry * 100, 1),
            'risk_reward': round(rr, 1),
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Signal classifier
    # ──────────────────────────────────────────────────────────────────────────

    def classify_signal(
        self,
        rsi: float,
        macd_hist: float,
        macd_hist_prev: float,
        volume_ratio: float,
        daily_return: float,         # today's price change %
        sentiment_score: float,
        pct_vs_20ma: float,
        pct_vs_50ma: float,
        ma50_slope: float,            # trend regime: + = uptrend, - = downtrend
        pct_b: float,                 # Bollinger %B (0=at lower, 1=at upper)
        stoch_k: float,
        stoch_d: float,
        obv_slope: float,
        btc_score: int,
    ) -> dict:
        score = 0
        reasons = []

        # ── Trend regime ──────────────────────────────────────────────────────
        in_downtrend = ma50_slope < -2.5   # MA50 fell > 2.5% in 10 days
        in_uptrend   = ma50_slope >  1.0

        if in_downtrend:
            reasons.append(f"⚠️ Downtrend regime (50-MA slope {ma50_slope:+.1f}%) — reducing buy signals")
        elif in_uptrend:
            reasons.append(f"✅ Uptrend regime (50-MA slope {ma50_slope:+.1f}%) — dips are buying opportunities")

        # ── Wilder RSI ────────────────────────────────────────────────────────
        if rsi < 25:
            pts = 20 if not in_downtrend else 8   # oversold in downtrend = caution
            score += pts
            reasons.append(f"RSI deeply oversold ({rsi:.0f}){' — downtrend caution' if in_downtrend else ' — strong bounce candidate'}")
        elif rsi < 35:
            pts = 14 if not in_downtrend else 4
            score += pts
            reasons.append(f"RSI oversold ({rsi:.0f}){' — downtrend caution' if in_downtrend else ' — potential reversal zone'}")
        elif rsi < 45:
            score += 6
            reasons.append(f"RSI below midpoint ({rsi:.0f}) — mild bullish bias")
        elif rsi > 78:
            score -= 28
            reasons.append(f"RSI extremely overbought ({rsi:.0f}) — take profits, risk of sharp reversal")
        elif rsi > 68:
            score -= 15
            reasons.append(f"RSI overbought ({rsi:.0f}) — reduced upside, watch for rollover")
        elif rsi > 55:
            score -= 4
            reasons.append(f"RSI elevated ({rsi:.0f}) — slight overbought bias")
        else:
            score += 2

        # ── Stochastic confirmation ───────────────────────────────────────────
        stoch_cross_up = stoch_k > stoch_d and stoch_k < 30
        stoch_cross_dn = stoch_k < stoch_d and stoch_k > 70
        if stoch_cross_up:
            pts = 15 if not in_downtrend else 5
            score += pts
            reasons.append(f"Stochastic bullish cross from oversold ({stoch_k:.0f}/{stoch_d:.0f})")
        elif stoch_k < 25:
            score += 8
            reasons.append(f"Stochastic oversold ({stoch_k:.0f}) — accumulation zone")
        elif stoch_cross_dn:
            score -= 15
            reasons.append(f"Stochastic bearish cross from overbought ({stoch_k:.0f}/{stoch_d:.0f})")
        elif stoch_k > 75:
            score -= 8
            reasons.append(f"Stochastic overbought ({stoch_k:.0f}) — watch for reversal")

        # ── MACD ──────────────────────────────────────────────────────────────
        if macd_hist > 0 and macd_hist_prev <= 0:
            score += 25
            reasons.append("MACD bullish crossover — momentum flipped positive ✅")
        elif macd_hist > 0 and macd_hist > macd_hist_prev:
            score += 12
            reasons.append("MACD histogram expanding bullishly")
        elif macd_hist < 0 and macd_hist_prev >= 0:
            score -= 25
            reasons.append("MACD bearish crossover — momentum flipped negative ⚠️")
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            score -= 12
            reasons.append("MACD histogram contracting (bearish)")
        else:
            score += 2

        # ── Volume (direction-aware) ───────────────────────────────────────────
        if volume_ratio >= 2.0:
            if daily_return > 0.005:
                score += 20
                reasons.append(f"Volume surge {volume_ratio:.1f}x on UP day — confirmed institutional buying 🔥")
            elif daily_return < -0.005:
                score -= 20
                reasons.append(f"Volume surge {volume_ratio:.1f}x on DOWN day — distribution/selling pressure 🚨")
            else:
                score += 5
                reasons.append(f"High volume {volume_ratio:.1f}x — watching direction")
        elif volume_ratio >= 1.5:
            if daily_return > 0:
                score += 12
                reasons.append(f"Above-average volume ({volume_ratio:.1f}x) on up day — good confirmation")
            else:
                score -= 8
                reasons.append(f"Above-average volume ({volume_ratio:.1f}x) on down day — selling pressure")
        elif volume_ratio < 0.5:
            score -= 8
            reasons.append(f"Very low volume ({volume_ratio:.1f}x avg) — weak conviction, wait for volume")

        # ── Bollinger Bands (%B) ───────────────────────────────────────────────
        if pct_b < 0.05:
            pts = 14 if not in_downtrend else 4
            score += pts
            reasons.append(f"Price at/below lower Bollinger Band (%B={pct_b:.2f}) — extreme oversold")
        elif pct_b < 0.2:
            score += 8
            reasons.append(f"Near lower Bollinger Band (%B={pct_b:.2f}) — potential support")
        elif pct_b > 0.95:
            score -= 14
            reasons.append(f"Price at/above upper Bollinger Band (%B={pct_b:.2f}) — extended, risk of mean reversion")
        elif pct_b > 0.80:
            score -= 7
            reasons.append(f"Near upper Bollinger Band (%B={pct_b:.2f}) — stretched")

        # ── OBV slope (accumulation / distribution) ───────────────────────────
        if obv_slope > 0.5:
            score += 10
            reasons.append(f"OBV rising (slope={obv_slope:.2f}) — smart money accumulating")
        elif obv_slope > 0.15:
            score += 5
            reasons.append(f"OBV mildly rising — moderate accumulation")
        elif obv_slope < -0.5:
            score -= 10
            reasons.append(f"OBV falling (slope={obv_slope:.2f}) — smart money distributing")
        elif obv_slope < -0.15:
            score -= 5
            reasons.append(f"OBV mildly falling — mild distribution")

        # ── Moving average position ───────────────────────────────────────────
        if pct_vs_20ma < -12:
            score += 10
            reasons.append(f"{abs(pct_vs_20ma):.1f}% below 20-day MA — deep oversold vs trend")
        elif pct_vs_20ma < -6:
            score += 5
            reasons.append(f"{abs(pct_vs_20ma):.1f}% below 20-day MA — near support")
        elif pct_vs_20ma > 20:
            score -= 12
            reasons.append(f"{pct_vs_20ma:.1f}% above 20-day MA — extended, risk of pullback")
        elif pct_vs_20ma > 10:
            score -= 5
            reasons.append(f"{pct_vs_20ma:.1f}% above 20-day MA — slightly stretched")

        if pct_vs_50ma < 0 and not in_downtrend:
            score += 4
            reasons.append("Price below 50-day MA in uptrend — value zone")
        elif pct_vs_50ma > 30:
            score -= 8
            reasons.append(f"{pct_vs_50ma:.1f}% above 50-day MA — very extended")

        # ── Sentiment ─────────────────────────────────────────────────────────
        if sentiment_score >= 0.3:
            score += 14
            reasons.append(f"News sentiment strongly bullish ({sentiment_score:+.2f})")
        elif sentiment_score >= 0.1:
            score += 7
            reasons.append(f"News sentiment mildly bullish ({sentiment_score:+.2f})")
        elif sentiment_score <= -0.3:
            score -= 14
            reasons.append(f"News sentiment strongly bearish ({sentiment_score:+.2f})")
        elif sentiment_score <= -0.1:
            score -= 7
            reasons.append(f"News sentiment mildly bearish ({sentiment_score:+.2f})")

        # ── BTC momentum factor ───────────────────────────────────────────────
        score += btc_score

        # ── Classify ──────────────────────────────────────────────────────────
        clamped = max(-100, min(100, score))

        # In strong downtrend, require more conviction to call BUY
        buy_threshold  = 40 if in_downtrend else 28
        sell_threshold = -20

        if clamped >= buy_threshold:
            signal = "BUY"
        elif clamped <= sell_threshold:
            signal = "SELL"
        else:
            signal = "HOLD"

        # Confidence: how far past the threshold, scaled to 50–95%
        if signal == "BUY":
            confidence = min(95, 50 + int((clamped - buy_threshold) * 0.8))
        elif signal == "SELL":
            confidence = min(95, 50 + int((abs(clamped) - abs(sell_threshold)) * 0.8))
        else:
            # Distance from nearest threshold
            dist = min(abs(clamped - buy_threshold), abs(clamped - sell_threshold))
            confidence = max(35, 55 - int(dist * 0.6))

        return {
            'signal': signal,
            'confidence': confidence,
            'raw_score': clamped,
            'reasons': reasons,
            'in_downtrend': in_downtrend,
            'in_uptrend': in_uptrend,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Main public methods
    # ──────────────────────────────────────────────────────────────────────────

    def analyze_stock(self, symbol: str) -> dict:
        hist = self._get_ohlcv(symbol)
        cache_age = self._cache_age(f"ohlcv_{symbol}_3mo")

        if hist.empty or len(hist) < 30:
            return {
                'symbol': symbol, 'signal': 'HOLD', 'confidence': 40,
                'error': 'Insufficient data', 'rsi': 50.0, 'macd_direction': 'Neutral',
                'volume_ratio': 1.0, 'sentiment_score': 0.0, 'sentiment_label': 'Neutral',
                'reasons': ['Insufficient data for analysis'], 'price_targets': None,
                'current_price': 0.0, 'data_age_seconds': cache_age,
                'stoch_k': 50.0, 'stoch_d': 50.0, 'pct_b': 0.5, 'obv_slope': 0.0,
                'atr': 0.0, 'btc_factors': {}, 'ma50_slope': 0.0,
            }

        close  = hist['Close']
        volume = hist['Volume']

        # All indicators
        rsi                      = self._calc_rsi(close)
        macd_val, sig_val, macd_hist, macd_hist_prev = self._calc_macd(close)
        volume_ratio             = self._calc_volume_ratio(volume)
        pct_vs_20ma, pct_vs_50ma, ma50_slope = self._calc_moving_averages(close)
        pct_b, bb_upper, bb_mid, bb_lower    = self._calc_bollinger(close)
        stoch_k, stoch_d         = self._calc_stochastic(hist)
        obv_slope                = self._calc_obv_slope(hist)
        atr                      = self._calc_atr(hist)
        btc_factors              = self._calc_btc_factors()
        sentiment_score          = self._get_sentiment_score(symbol)
        price_targets            = self._calc_price_targets(hist)
        cur_price                = float(close.iloc[-1])
        daily_return             = float((close.iloc[-1] - close.iloc[-2]) / close.iloc[-2]) if len(close) > 1 else 0.0

        classification = self.classify_signal(
            rsi=rsi, macd_hist=macd_hist, macd_hist_prev=macd_hist_prev,
            volume_ratio=volume_ratio, daily_return=daily_return,
            sentiment_score=sentiment_score,
            pct_vs_20ma=pct_vs_20ma, pct_vs_50ma=pct_vs_50ma,
            ma50_slope=ma50_slope, pct_b=pct_b,
            stoch_k=stoch_k, stoch_d=stoch_d,
            obv_slope=obv_slope, btc_score=btc_factors['btc_score'],
        )

        # Labels
        if sentiment_score >= 0.15:
            sentiment_label = "🟢 Bullish"
        elif sentiment_score <= -0.15:
            sentiment_label = "🔴 Bearish"
        else:
            sentiment_label = "🟡 Neutral"

        if macd_hist > 0 and macd_hist > macd_hist_prev:
            macd_direction = "📈 Bullish"
        elif macd_hist > 0:
            macd_direction = "↗️ Weak Bullish"
        elif macd_hist < 0 and macd_hist < macd_hist_prev:
            macd_direction = "📉 Bearish"
        else:
            macd_direction = "↘️ Weak Bearish"

        return {
            'symbol': symbol,
            'signal': classification['signal'],
            'confidence': classification['confidence'],
            'raw_score': classification['raw_score'],
            'reasons': classification['reasons'],
            'current_price': cur_price,
            'daily_return_pct': round(daily_return * 100, 2),
            'rsi': round(rsi, 1),
            'macd_direction': macd_direction,
            'macd_hist': round(macd_hist, 4),
            'volume_ratio': round(volume_ratio, 2),
            'pct_vs_20ma': round(pct_vs_20ma, 1),
            'pct_vs_50ma': round(pct_vs_50ma, 1),
            'ma50_slope': round(ma50_slope, 2),
            'pct_b': round(pct_b, 3),
            'bb_upper': round(bb_upper, 2),
            'bb_lower': round(bb_lower, 2),
            'stoch_k': round(stoch_k, 1),
            'stoch_d': round(stoch_d, 1),
            'obv_slope': round(obv_slope, 3),
            'atr': round(atr, 2),
            'sentiment_score': round(sentiment_score, 3),
            'sentiment_label': sentiment_label,
            'btc_factors': btc_factors,
            'in_downtrend': classification['in_downtrend'],
            'in_uptrend': classification['in_uptrend'],
            'price_targets': price_targets,
            'data_timestamp': datetime.now().strftime('%H:%M:%S'),
            'data_age_seconds': int(cache_age) if cache_age != float('inf') else 0,
        }

    def analyze_all(self) -> list:
        results = []
        for symbol in self.MINING_STOCKS:
            try:
                results.append(self.analyze_stock(symbol))
            except Exception as e:
                results.append({
                    'symbol': symbol, 'signal': 'HOLD', 'confidence': 40,
                    'error': str(e), 'rsi': 50.0, 'macd_direction': 'Unknown',
                    'volume_ratio': 1.0, 'sentiment_score': 0.0,
                    'sentiment_label': '🟡 Neutral', 'reasons': [f'Error: {e}'],
                    'price_targets': None, 'current_price': 0.0,
                    'pct_b': 0.5, 'stoch_k': 50.0, 'stoch_d': 50.0,
                    'obv_slope': 0.0, 'atr': 0.0, 'btc_factors': {},
                    'ma50_slope': 0.0, 'daily_return_pct': 0.0,
                    'data_timestamp': datetime.now().strftime('%H:%M:%S'),
                    'data_age_seconds': 0,
                })

        order = {'BUY': 0, 'HOLD': 1, 'SELL': 2}
        results.sort(key=lambda x: (order.get(x['signal'], 1), -x.get('confidence', 0)))
        return results
