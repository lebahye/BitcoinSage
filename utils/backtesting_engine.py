import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime, timedelta
import streamlit as st

class BacktestingEngine:
    """Professional Backtesting Framework - Test strategies on historical data"""
    
    def __init__(self):
        self.results = {}
    
    def run_strategy_backtest(self, symbol, strategy_signals, start_date, end_date, initial_capital=10000):
        """
        Run backtest for a trading strategy
        
        strategy_signals: DataFrame with 'date' and 'signal' columns
                         signal values: 1 (buy), -1 (sell), 0 (hold)
        """
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                return {}
            
            hist = hist.reset_index()
            hist['Date'] = pd.to_datetime(hist['Date']).dt.date
            
            merged = pd.merge(hist, strategy_signals, left_on='Date', right_on='date', how='left')
            merged['signal'] = merged['signal'].fillna(0)
            
            capital = initial_capital
            position = 0
            shares = 0
            trades = []
            equity_curve = []
            
            for idx, row in merged.iterrows():
                date = row['Date']
                price = row['Close']
                signal = row['signal']
                
                if signal == 1 and position == 0:
                    shares = capital / price
                    position = 1
                    trades.append({
                        'date': date,
                        'action': 'BUY',
                        'price': price,
                        'shares': shares,
                        'capital': capital
                    })
                
                elif signal == -1 and position == 1:
                    capital = shares * price
                    trades.append({
                        'date': date,
                        'action': 'SELL',
                        'price': price,
                        'shares': shares,
                        'capital': capital
                    })
                    shares = 0
                    position = 0
                
                current_value = capital if position == 0 else shares * price
                equity_curve.append({
                    'date': date,
                    'equity': current_value,
                    'price': price
                })
            
            if position == 1:
                final_price = merged.iloc[-1]['Close']
                capital = shares * final_price
                trades.append({
                    'date': merged.iloc[-1]['Date'],
                    'action': 'SELL (Final)',
                    'price': final_price,
                    'shares': shares,
                    'capital': capital
                })
            
            equity_df = pd.DataFrame(equity_curve)
            trades_df = pd.DataFrame(trades)
            
            final_capital = capital
            total_return = ((final_capital - initial_capital) / initial_capital) * 100
            
            buy_hold_return = ((merged.iloc[-1]['Close'] - merged.iloc[0]['Close']) / merged.iloc[0]['Close']) * 100
            
            total_days = (merged.iloc[-1]['Date'] - merged.iloc[0]['Date']).days
            cagr = (((final_capital / initial_capital) ** (365 / total_days)) - 1) * 100 if total_days > 0 else 0
            
            if len(equity_df) > 1:
                equity_df['returns'] = equity_df['equity'].pct_change()
                daily_returns = equity_df['returns'].dropna()
                
                sharpe_ratio = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() != 0 else 0
                
                equity_df['peak'] = equity_df['equity'].cummax()
                equity_df['drawdown'] = (equity_df['equity'] - equity_df['peak']) / equity_df['peak'] * 100
                max_drawdown = equity_df['drawdown'].min()
                
                buy_trades = trades_df[trades_df['action'] == 'BUY'].copy()
                sell_trades = trades_df[trades_df['action'].str.contains('SELL')].copy()
                
                if len(buy_trades) > 0 and len(sell_trades) > 0:
                    paired_trades = []
                    for i in range(min(len(buy_trades), len(sell_trades))):
                        buy_capital = buy_trades.iloc[i]['capital']
                        sell_capital = sell_trades.iloc[i]['capital']
                        profit = sell_capital - buy_capital
                        paired_trades.append({'profit': profit, 'is_win': profit > 0})
                    
                    if paired_trades:
                        win_rate = sum(1 for t in paired_trades if t['is_win']) / len(paired_trades) * 100
                    else:
                        win_rate = 0
                else:
                    win_rate = 0
            else:
                sharpe_ratio = 0
                max_drawdown = 0
                win_rate = 0
                cagr = 0
            
            num_trades = len(buy_trades) if 'buy_trades' in locals() else len(trades_df) // 2
            
            return {
                'symbol': symbol,
                'initial_capital': initial_capital,
                'final_capital': final_capital,
                'total_return_pct': total_return,
                'buy_hold_return_pct': buy_hold_return,
                'cagr_pct': cagr,
                'sharpe_ratio': sharpe_ratio,
                'max_drawdown_pct': max_drawdown,
                'num_trades': num_trades,
                'win_rate_pct': win_rate,
                'equity_curve': equity_df,
                'trades': trades_df,
                'outperformance': total_return - buy_hold_return
            }
            
        except Exception as e:
            st.error(f"Backtesting error for {symbol}: {str(e)}")
            return {}
    
    def test_ma_crossover_strategy(self, symbol, start_date, end_date, short_window=20, long_window=50, initial_capital=10000):
        """Test Moving Average Crossover Strategy"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                return {}
            
            hist['SMA_short'] = hist['Close'].rolling(window=short_window).mean()
            hist['SMA_long'] = hist['Close'].rolling(window=long_window).mean()
            
            signals = pd.DataFrame()
            signals['date'] = hist.index.date
            signals['signal'] = 0
            
            signals.loc[hist['SMA_short'] > hist['SMA_long'], 'signal'] = 1
            signals.loc[hist['SMA_short'] < hist['SMA_long'], 'signal'] = -1
            
            signals['signal'] = signals['signal'].diff()
            signals.loc[signals['signal'] > 0, 'signal'] = 1
            signals.loc[signals['signal'] < 0, 'signal'] = -1
            signals.loc[signals['signal'] == 0, 'signal'] = 0
            
            result = self.run_strategy_backtest(symbol, signals, start_date, end_date, initial_capital)
            result['strategy_name'] = f'MA Crossover ({short_window}/{long_window})'
            result['strategy_params'] = {'short_window': short_window, 'long_window': long_window}
            
            return result
            
        except Exception as e:
            st.error(f"MA Crossover backtest error: {str(e)}")
            return {}
    
    def test_rsi_strategy(self, symbol, start_date, end_date, rsi_period=14, oversold=30, overbought=70, initial_capital=10000):
        """Test RSI Mean Reversion Strategy"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                return {}
            
            delta = hist['Close'].diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            
            avg_gain = gain.rolling(window=rsi_period).mean()
            avg_loss = loss.rolling(window=rsi_period).mean()
            
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            signals = pd.DataFrame()
            signals['date'] = hist.index.date
            signals['signal'] = 0
            
            signals.loc[rsi < oversold, 'signal'] = 1
            signals.loc[rsi > overbought, 'signal'] = -1
            
            signals['signal'] = signals['signal'].diff()
            signals.loc[signals['signal'] > 0, 'signal'] = 1
            signals.loc[signals['signal'] < 0, 'signal'] = -1
            signals.loc[signals['signal'] == 0, 'signal'] = 0
            
            result = self.run_strategy_backtest(symbol, signals, start_date, end_date, initial_capital)
            result['strategy_name'] = f'RSI Mean Reversion ({oversold}/{overbought})'
            result['strategy_params'] = {'rsi_period': rsi_period, 'oversold': oversold, 'overbought': overbought}
            
            return result
            
        except Exception as e:
            st.error(f"RSI strategy backtest error: {str(e)}")
            return {}
    
    def test_volume_breakout_strategy(self, symbol, start_date, end_date, volume_threshold=1.5, initial_capital=10000):
        """Test Volume Breakout Strategy"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                return {}
            
            hist['Volume_MA'] = hist['Volume'].rolling(window=20).mean()
            hist['Volume_Ratio'] = hist['Volume'] / hist['Volume_MA']
            
            hist['Price_Change'] = hist['Close'].pct_change()
            
            signals = pd.DataFrame()
            signals['date'] = hist.index.date
            signals['signal'] = 0
            
            breakout_condition = (hist['Volume_Ratio'] > volume_threshold) & (hist['Price_Change'] > 0.02)
            signals.loc[breakout_condition, 'signal'] = 1
            
            breakdown_condition = (hist['Volume_Ratio'] > volume_threshold) & (hist['Price_Change'] < -0.02)
            signals.loc[breakdown_condition, 'signal'] = -1
            
            result = self.run_strategy_backtest(symbol, signals, start_date, end_date, initial_capital)
            result['strategy_name'] = f'Volume Breakout ({volume_threshold}x)'
            result['strategy_params'] = {'volume_threshold': volume_threshold}
            
            return result
            
        except Exception as e:
            st.error(f"Volume breakout backtest error: {str(e)}")
            return {}
    
    def test_momentum_strategy(self, symbol, start_date, end_date, lookback_period=20, hold_period=5, initial_capital=10000):
        """Test Momentum Strategy"""
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)
            
            if hist.empty:
                return {}
            
            hist['Returns'] = hist['Close'].pct_change(lookback_period)
            
            signals = pd.DataFrame()
            signals['date'] = hist.index.date
            signals['signal'] = 0
            
            top_quartile = hist['Returns'].quantile(0.75)
            bottom_quartile = hist['Returns'].quantile(0.25)
            
            signals.loc[hist['Returns'] > top_quartile, 'signal'] = 1
            signals.loc[hist['Returns'] < bottom_quartile, 'signal'] = -1
            
            result = self.run_strategy_backtest(symbol, signals, start_date, end_date, initial_capital)
            result['strategy_name'] = f'Momentum ({lookback_period}-day)'
            result['strategy_params'] = {'lookback_period': lookback_period, 'hold_period': hold_period}
            
            return result
            
        except Exception as e:
            st.error(f"Momentum strategy backtest error: {str(e)}")
            return {}
    
    def compare_strategies(self, results_list):
        """Compare multiple strategy results"""
        comparison = []
        
        for result in results_list:
            if result:
                comparison.append({
                    'Strategy': result.get('strategy_name', 'Unknown'),
                    'Total Return': f"{result.get('total_return_pct', 0):.2f}%",
                    'Buy & Hold': f"{result.get('buy_hold_return_pct', 0):.2f}%",
                    'Outperformance': f"{result.get('outperformance', 0):.2f}%",
                    'Sharpe Ratio': f"{result.get('sharpe_ratio', 0):.2f}",
                    'Max Drawdown': f"{result.get('max_drawdown_pct', 0):.2f}%",
                    'Win Rate': f"{result.get('win_rate_pct', 0):.1f}%",
                    'Trades': result.get('num_trades', 0)
                })
        
        return pd.DataFrame(comparison)
    
    def calculate_portfolio_metrics(self, equity_curve):
        """Calculate additional portfolio metrics"""
        try:
            if equity_curve.empty or len(equity_curve) < 2:
                return {}
            
            total_days = (equity_curve['date'].iloc[-1] - equity_curve['date'].iloc[0]).days
            total_return = (equity_curve['equity'].iloc[-1] / equity_curve['equity'].iloc[0] - 1) * 100
            
            cagr = (((equity_curve['equity'].iloc[-1] / equity_curve['equity'].iloc[0]) ** (365 / total_days)) - 1) * 100 if total_days > 0 else 0
            
            equity_curve['returns'] = equity_curve['equity'].pct_change()
            daily_returns = equity_curve['returns'].dropna()
            
            volatility = daily_returns.std() * np.sqrt(252) * 100
            
            equity_curve['peak'] = equity_curve['equity'].cummax()
            equity_curve['drawdown'] = (equity_curve['equity'] - equity_curve['peak']) / equity_curve['peak']
            
            max_dd_idx = equity_curve['drawdown'].idxmin()
            peak_idx = equity_curve.loc[:max_dd_idx, 'peak'].idxmax()
            
            recovery_data = equity_curve.loc[max_dd_idx:]
            recovery_idx = recovery_data[recovery_data['equity'] >= equity_curve.loc[peak_idx, 'equity']].index
            recovery_days = (equity_curve.loc[recovery_idx[0], 'date'] - equity_curve.loc[max_dd_idx, 'date']).days if len(recovery_idx) > 0 else None
            
            return {
                'total_return_pct': total_return,
                'cagr_pct': cagr,
                'volatility_pct': volatility,
                'max_drawdown_pct': equity_curve['drawdown'].min() * 100,
                'recovery_days': recovery_days,
                'total_days': total_days
            }
            
        except Exception as e:
            st.error(f"Portfolio metrics calculation error: {str(e)}")
            return {}
