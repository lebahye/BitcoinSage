"""
Options Strategy Backtester
Simulates covered calls, protective puts, and collars on an actual stock position.
Premiums estimated using Black-Scholes + realized historical volatility.
"""

import numpy as np
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from scipy.stats import norm


def _bs_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes call price. Returns 0 on invalid inputs."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2))


def _bs_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    """Black-Scholes put price. Returns 0 on invalid inputs."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return 0.0
    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    d2 = d1 - sigma * np.sqrt(T)
    return float(K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1))


def _annualized_vol(prices: pd.Series, window: int = 30) -> float:
    """Annualized realized volatility from a window of daily closing prices."""
    if len(prices) < 5:
        return 0.60  # reasonable default for mining stocks
    returns = np.log(prices / prices.shift(1)).dropna()
    if len(returns) < 3:
        return 0.60
    return float(returns.std() * np.sqrt(252))


class OptionsBacktester:
    """
    Backtests options income / protection strategies on a held stock position.
    All premiums are estimated via Black-Scholes with rolling realized volatility.
    """

    RISK_FREE_RATE = 0.05  # 5% — US short-term treasury proxy

    def __init__(self):
        self._price_cache: dict = {}

    # ── Public API ───────────────────────────────────────────────────────────

    def run(
        self,
        symbol: str,
        shares: int,
        cost_basis: float,
        strategy: str,          # 'covered_call' | 'protective_put' | 'collar'
        months: int = 12,
        call_otm_pct: float = 0.10,
        put_otm_pct: float = 0.10,
        dte: int = 30,
    ) -> dict | None:
        """
        Run a full strategy backtest.
        Returns a result dict suitable for the dashboard, or None on data failure.
        """
        hist = self._get_prices(symbol, months)
        if hist is None or len(hist) < 30:
            return None

        if strategy == 'covered_call':
            return self._run_covered_call(hist, shares, cost_basis, call_otm_pct, dte)
        elif strategy == 'protective_put':
            return self._run_protective_put(hist, shares, cost_basis, put_otm_pct, dte)
        elif strategy == 'collar':
            return self._run_collar(hist, shares, cost_basis, call_otm_pct, put_otm_pct, dte)
        return None

    # ── Strategy implementations ─────────────────────────────────────────────

    def _run_covered_call(self, hist, shares, cost_basis, otm_pct, dte):
        """
        Monthly covered-call cycle.
        At each entry: sell a call at (price × (1+otm_pct)), collect premium.
        At expiry:
          - price < strike  → keep premium + shares
          - price ≥ strike  → assigned at strike; "roll back" to maintain position size
        Compared against plain buy-and-hold over same period.
        """
        trades = []
        gross_premiums    = 0.0
        net_cycle_total   = 0.0
        assignment_count  = 0
        r = self.RISK_FREE_RATE
        T = dte / 365.0
        dates = hist.index

        i = 0
        while i < len(dates) - dte:
            entry_date = dates[i]
            expiry_idx = min(i + dte, len(dates) - 1)
            expiry_date = dates[expiry_idx]

            S     = float(hist['Close'].iloc[i])
            S_exp = float(hist['Close'].iloc[expiry_idx])
            K     = S * (1 + otm_pct)

            # Historical vol using 30 days prior to entry
            vol_window = hist['Close'].iloc[max(0, i - 30): i + 1]
            sigma = _annualized_vol(vol_window)

            premium_per_share = _bs_call(S, K, T, r, sigma)
            total_premium     = premium_per_share * shares
            gross_premiums   += total_premium

            assigned = S_exp >= K
            if assigned:
                assignment_count += 1
                # When assigned: collect premium but miss upside above strike
                missed_upside = (S_exp - K) * shares
            else:
                missed_upside = 0.0

            # Cycle net = actual economic impact (premium minus capped upside loss)
            cycle_net       = total_premium - missed_upside
            net_cycle_total += cycle_net

            trades.append({
                'Entry Date':     entry_date.date(),
                'Expiry Date':    expiry_date.date(),
                'Entry Price':    round(S, 2),
                'Strike':         round(K, 2),
                'Implied Vol':    round(sigma * 100, 1),
                'Premium/Share':  round(premium_per_share, 3),
                'Total Premium':  round(total_premium, 0),
                'Expiry Price':   round(S_exp, 2),
                'Assigned':       '✅ Yes' if assigned else '❌ No',
                'Missed Upside':  round(missed_upside, 0),
                'Cycle Net ($)':  round(cycle_net, 0),
            })
            i += dte

        return self._package_results(
            hist, shares, cost_basis, trades,
            net_income=net_cycle_total,          # true edge: premiums - missed upside
            gross_income=gross_premiums,         # gross premiums collected (for yield display)
            event_count=assignment_count,
            strategy_name='Covered Call',
            description=f"Sell {dte}-day calls {otm_pct*100:.0f}% OTM monthly",
        )

    def _run_protective_put(self, hist, shares, cost_basis, otm_pct, dte):
        """Monthly protective puts — pay premium to floor the downside."""
        trades = []
        cumulative_cost = 0.0
        put_triggered    = 0
        r = self.RISK_FREE_RATE
        T = dte / 365.0
        dates = hist.index

        i = 0
        while i < len(dates) - dte:
            entry_date  = dates[i]
            expiry_idx  = min(i + dte, len(dates) - 1)
            expiry_date = dates[expiry_idx]

            S     = float(hist['Close'].iloc[i])
            S_exp = float(hist['Close'].iloc[expiry_idx])
            K     = S * (1 - otm_pct)

            vol_window = hist['Close'].iloc[max(0, i - 30): i + 1]
            sigma = _annualized_vol(vol_window)

            premium_per_share = _bs_put(S, K, T, r, sigma)
            total_cost        = premium_per_share * shares
            cumulative_cost  += total_cost

            triggered   = S_exp < K
            put_payoff  = max(0.0, K - S_exp) * shares
            cycle_net   = put_payoff - total_cost

            if triggered:
                put_triggered += 1

            trades.append({
                'Entry Date':     entry_date.date(),
                'Expiry Date':    expiry_date.date(),
                'Entry Price':    round(S, 2),
                'Strike (Floor)': round(K, 2),
                'Implied Vol':    round(sigma * 100, 1),
                'Premium/Share':  round(premium_per_share, 3),
                'Total Cost':     round(total_cost, 0),
                'Expiry Price':   round(S_exp, 2),
                'Put Triggered':  '✅ Yes' if triggered else '❌ No',
                'Put Payoff ($)': round(put_payoff, 0),
                'Cycle Net ($)':  round(cycle_net, 0),
            })
            i += dte

        total_payoff = sum(t['Put Payoff ($)'] for t in trades)
        net_cycle_total = sum(t['Cycle Net ($)'] for t in trades)  # payoffs - costs
        net_value = total_payoff - cumulative_cost

        return self._package_results(
            hist, shares, cost_basis, trades,
            net_income=net_cycle_total,        # sum of (payoff - cost) each cycle
            gross_income=-cumulative_cost,     # negative = cost (for yield display)
            event_count=put_triggered,
            strategy_name='Protective Put',
            description=f"Buy {dte}-day puts {otm_pct*100:.0f}% OTM monthly",
            extra={
                'Total Put Cost':       round(cumulative_cost, 0),
                'Total Put Payoff':     round(total_payoff, 0),
                'Net Protection Value': round(net_value, 0),
            }
        )

    def _run_collar(self, hist, shares, cost_basis, call_otm, put_otm, dte):
        """Monthly collar = sell call + buy put simultaneously."""
        trades = []
        cumulative_net = 0.0
        assignments    = 0
        put_triggered  = 0
        r = self.RISK_FREE_RATE
        T = dte / 365.0
        dates = hist.index

        i = 0
        while i < len(dates) - dte:
            entry_date  = dates[i]
            expiry_idx  = min(i + dte, len(dates) - 1)
            expiry_date = dates[expiry_idx]

            S     = float(hist['Close'].iloc[i])
            S_exp = float(hist['Close'].iloc[expiry_idx])
            K_call = S * (1 + call_otm)
            K_put  = S * (1 - put_otm)

            vol_window = hist['Close'].iloc[max(0, i - 30): i + 1]
            sigma = _annualized_vol(vol_window)

            call_prem = _bs_call(S, K_call, T, r, sigma)
            put_cost  = _bs_put(S,  K_put,  T, r, sigma)
            net_prem  = (call_prem - put_cost) * shares
            cumulative_net += net_prem

            assigned      = S_exp >= K_call
            put_fires     = S_exp <= K_put
            if assigned:     assignments    += 1
            if put_fires:    put_triggered  += 1

            # Outcome
            if assigned:
                missed    = (S_exp - K_call) * shares
                cycle_net = net_prem - missed
            elif put_fires:
                saved     = (K_put - S_exp) * shares
                cycle_net = net_prem + saved
            else:
                cycle_net = net_prem

            trades.append({
                'Entry Date':      entry_date.date(),
                'Expiry Date':     expiry_date.date(),
                'Entry Price':     round(S, 2),
                'Call Strike':     round(K_call, 2),
                'Put Floor':       round(K_put, 2),
                'Implied Vol':     round(sigma * 100, 1),
                'Call Premium':    round(call_prem, 3),
                'Put Cost':        round(put_cost, 3),
                'Net Premium/Sh':  round(call_prem - put_cost, 3),
                'Net Position ($)': round(net_prem, 0),
                'Expiry Price':    round(S_exp, 2),
                'Outcome':         '🔴 Assigned' if assigned else ('🟢 Put Triggered' if put_fires else '⚪ Expired'),
                'Cycle Net ($)':   round(cycle_net, 0),
            })
            i += dte

        net_cycle_total = sum(t['Cycle Net ($)'] for t in trades)  # includes assignment/put impacts

        return self._package_results(
            hist, shares, cost_basis, trades,
            net_income=net_cycle_total,     # full net: premiums ± assignment losses ± put payoffs
            gross_income=cumulative_net,    # net premiums (call - put) before outcome adjustments
            event_count=assignments,
            strategy_name='Collar',
            description=f"Sell {call_otm*100:.0f}% OTM call + Buy {put_otm*100:.0f}% OTM put ({dte}-day)",
            extra={'Put Triggers': put_triggered}
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_prices(self, symbol: str, months: int):
        key = f"{symbol}_{months}"
        if key in self._price_cache:
            return self._price_cache[key]
        try:
            period_map = {3: '3mo', 6: '6mo', 12: '1y', 24: '2y'}
            period = period_map.get(months, '1y')
            ticker = yf.Ticker(symbol)
            hist   = ticker.history(period=period)
            if hist.empty:
                return None
            hist.index = pd.to_datetime(hist.index).tz_localize(None)
            hist = hist[~hist.index.duplicated(keep='last')]
            self._price_cache[key] = hist
            return hist
        except Exception:
            return None

    def _package_results(
        self, hist, shares, cost_basis, trades,
        net_income: float,      # sum of cycle_nets — true economic edge vs B&H
        gross_income: float,    # gross premiums collected (or cost paid) before outcome adjustments
        event_count: int,
        strategy_name: str,
        description: str,
        extra: dict = None,
    ) -> dict:
        """Build the standard result dict for the dashboard."""
        if not trades:
            return None

        df_trades = pd.DataFrame(trades)

        # Buy-and-hold baseline
        start_price = float(hist['Close'].iloc[0])
        final_price = float(hist['Close'].iloc[-1])
        bah_pnl     = (final_price - cost_basis) * shares
        bah_return  = (final_price / start_price - 1) * 100

        # Strategy total P&L = B&H stock P&L + net options edge
        # net_income = sum(cycle_nets) already captures the full options economics
        strategy_pnl    = bah_pnl + net_income
        starting_value  = max(cost_basis * shares, 1.0)
        strategy_return = strategy_pnl / starting_value * 100

        # Years elapsed
        first_date = pd.Timestamp(str(trades[0]['Entry Date']))
        last_date  = pd.Timestamp(str(trades[-1]['Expiry Date']))
        years = max((last_date - first_date).days / 365.25, 0.08)

        # Annual yield based on gross_income (what you actually put in/got out)
        annual_yield = (abs(gross_income) / starting_value / years * 100)

        # Cumulative cycle_net series for chart (real economics over time)
        cum_dates  = [t['Entry Date'] for t in trades]
        cum_values = np.cumsum([t['Cycle Net ($)'] for t in trades])

        # Also cumulative gross premiums for income display
        cum_gross_values = np.cumsum([
            t.get('Total Premium', t.get('Net Position ($)', 0)) for t in trades
        ])

        result = {
            'strategy_name':      strategy_name,
            'description':        description,
            'shares':             shares,
            'cost_basis':         cost_basis,
            'start_price':        round(start_price, 2),
            'final_price':        round(final_price, 2),

            # Core metrics
            'net_income':         round(net_income, 0),       # true edge (premiums - missed upside)
            'gross_income':       round(gross_income, 0),     # gross premiums collected/paid
            'event_count':        event_count,
            'annual_yield_pct':   round(annual_yield, 2),
            'num_cycles':         len(trades),

            # P&L comparison
            'bah_pnl':            round(bah_pnl, 0),
            'bah_return_pct':     round(bah_return, 2),
            'strategy_pnl':       round(strategy_pnl, 0),
            'strategy_return_pct': round(strategy_return, 2),
            'strategy_edge':      round(net_income, 0),  # additional $ vs pure B&H

            # Time series for charts (cumulative cycle net — real economic impact)
            'cum_dates':       cum_dates,
            'cum_income':      [round(float(v), 0) for v in cum_values],
            'cum_gross':       [round(float(v), 0) for v in cum_gross_values],

            # Price series
            'price_dates':  hist.index.tolist(),
            'prices':       hist['Close'].tolist(),

            # Trade log
            'trades_df': df_trades,

            # Extra strategy-specific metrics
            'extra': extra or {},
        }
        return result
