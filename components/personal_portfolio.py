import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import numpy as np
import yfinance as yf
import json
import os
from datetime import datetime, timedelta
from utils.unified_data_fetcher import DataFetcher
from utils.tickers import resolve, resolve_keys
from utils.explain import explain, HELP

TARGETS_FILE = "portfolio_targets.json"
STOP_LOSS_FILE = "portfolio_stop_loss.json"
POSITIONS_FILE = "data/positions.json"
HISTORY_FILE = "portfolio_target_history.json"
POSITION_HISTORY_FILE = "data/position_history.json"

# Default positions — used only when no saved file exists
_DEFAULT_POSITIONS = {
    'RIOT': {'shares': 10975, 'name': 'Riot Platforms Inc',       'cost_basis': 18.22},
    'KEEL': {'shares': 1700,  'name': 'Keel Infrastructure Corp.','cost_basis': 2.85},
    'BTBT': {'shares': 600,   'name': 'Bit Digital Inc',          'cost_basis': 2.10},
    'CLSK': {'shares': 300,   'name': 'CleanSpark Inc',           'cost_basis': 8.12},
    'MARA': {'shares': 200,   'name': 'Marathon Digital',         'cost_basis': 14.50},
    'CIFR': {'shares': 500,   'name': 'Cipher Mining Inc',        'cost_basis': 3.20},
    'IREN': {'shares': 500,   'name': 'Iris Energy Ltd',          'cost_basis': 8.75},
    'MSTR': {'shares': 38,    'name': 'MicroStrategy Inc',        'cost_basis': 340.00},
    'WULF': {'shares': 500,   'name': 'TeraWulf Inc',             'cost_basis': 2.90},
}

# Public alias (other components import this name)
DEFAULT_POSITIONS = _DEFAULT_POSITIONS


class PersonalPortfolio:
    """Personalized portfolio management for user's actual mining stock positions"""
    
    def __init__(self):
        self.positions = self._load_positions()
        self.total_shares = sum(pos['shares'] for pos in self.positions.values())

    # ── Persistence helpers ──────────────────────────────────────────────────

    @staticmethod
    def _load_targets() -> dict:
        """Load saved price targets from disk. Returns {} if file missing/corrupt."""
        try:
            if os.path.exists(TARGETS_FILE):
                with open(TARGETS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return resolve_keys({k: float(v) for k, v in data.items()})
        except Exception:
            pass
        return {}

    @staticmethod
    def _save_targets(targets: dict) -> None:
        """Persist price targets to disk."""
        try:
            with open(TARGETS_FILE, "w") as f:
                json.dump({k: float(v) for k, v in targets.items()}, f)
        except Exception:
            pass

    @staticmethod
    def _load_stop_losses() -> dict:
        """Load saved stop-loss prices from disk. Returns {} if file missing/corrupt."""
        try:
            if os.path.exists(STOP_LOSS_FILE):
                with open(STOP_LOSS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return resolve_keys({k: float(v) for k, v in data.items()})
        except Exception:
            pass
        return {}

    @staticmethod
    def _save_stop_losses(stop_losses: dict) -> None:
        """Persist stop-loss prices to disk."""
        try:
            with open(STOP_LOSS_FILE, "w") as f:
                json.dump({k: float(v) for k, v in stop_losses.items()}, f)
        except Exception:
            pass

    # ── Target history helpers ───────────────────────────────────────────────

    @staticmethod
    def _load_target_history() -> list:
        """Load target history log from disk. Returns [] if missing/corrupt."""
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    @staticmethod
    def _save_target_history(history: list) -> None:
        """Persist target history log to disk."""
        try:
            with open(HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _log_target_event(symbol: str, event: str, target_price: float,
                          price_at_event: float = 0.0) -> None:
        """
        Append one event to the history log and save.
        event: "set" | "cleared" | "hit"
        """
        history = PersonalPortfolio._load_target_history()
        entry = {
            "event":           event,
            "symbol":          symbol,
            "target_price":    round(float(target_price), 4),
            "price_at_event":  round(float(price_at_event), 4),
            "timestamp":       datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }
        history.append(entry)
        PersonalPortfolio._save_target_history(history)

    @staticmethod
    def _load_positions() -> dict:
        """Load saved positions from disk. Falls back to defaults if file is missing or corrupt."""
        import copy
        try:
            if os.path.exists(POSITIONS_FILE):
                with open(POSITIONS_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data:
                    result = {}
                    for symbol, saved in resolve_keys(data).items():  # e.g. old BITF -> KEEL
                        default = _DEFAULT_POSITIONS.get(symbol, {})
                        result[symbol] = {
                            'shares':     int(saved.get('shares', default.get('shares', 0))),
                            'cost_basis': float(saved.get('cost_basis', default.get('cost_basis', 0.0))),
                            'name':       saved.get('name', default.get('name', symbol)),
                        }
                    return result
        except Exception:
            pass
        import copy
        return copy.deepcopy(_DEFAULT_POSITIONS)

    @staticmethod
    def _save_positions(positions: dict) -> None:
        """Persist positions to disk."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(POSITIONS_FILE, "w") as f:
                json.dump(
                    {sym: {'shares': pos['shares'],
                           'cost_basis': pos['cost_basis'],
                           'name': pos['name']}
                     for sym, pos in positions.items()},
                    f,
                    indent=2,
                )
        except Exception:
            pass

    # ── Position change history helpers ──────────────────────────────────────

    @staticmethod
    def _load_position_history() -> list:
        """Load position change history from disk. Returns [] if missing/corrupt."""
        try:
            if os.path.exists(POSITION_HISTORY_FILE):
                with open(POSITION_HISTORY_FILE, "r") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    @staticmethod
    def _save_position_history(history: list) -> None:
        """Persist position change history to disk."""
        try:
            os.makedirs("data", exist_ok=True)
            with open(POSITION_HISTORY_FILE, "w") as f:
                json.dump(history, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def _log_position_change(symbol: str, event: str,
                             old_shares: int, new_shares: int,
                             old_cost_basis: float, new_cost_basis: float) -> None:
        """
        Append one position-change entry to the history log and save.
        event: "updated" | "added" | "removed"
        """
        history = PersonalPortfolio._load_position_history()
        entry = {
            "timestamp":      datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "symbol":         symbol,
            "event":          event,
            "old_shares":     old_shares,
            "new_shares":     new_shares,
            "old_cost_basis": round(float(old_cost_basis), 4),
            "new_cost_basis": round(float(new_cost_basis), 4),
        }
        history.append(entry)
        PersonalPortfolio._save_position_history(history)

    # ── Browser notification helpers ─────────────────────────────────────────

    def _render_notification_controls(self) -> None:
        """Show opt-in toggle and current browser notification status."""
        enabled = st.session_state.get('notif_opt_in', False)

        col_text, col_btn = st.columns([4, 1])
        with col_text:
            st.caption(
                "🔔 **Browser notifications** — get alerted when a take-profit target is hit, "
                "even if you're on another tab. Click the button to enable, then allow the "
                "permission prompt your browser shows."
            )
        with col_btn:
            label = "🔕 Disable" if enabled else "🔔 Enable Alerts"
            if st.button(label, key="notif_toggle_btn", use_container_width=True):
                st.session_state['notif_opt_in'] = not enabled
                if not enabled:
                    st.session_state['notif_permission_requested'] = True
                st.rerun()

        if enabled:
            st.caption("✅ Browser alerts are **on**. Targets that have already fired will not repeat until the target price is changed.")

    def _fire_target_notifications(self, prices: dict) -> None:
        """
        Inject a tiny JS snippet that:
        1. Requests Notification permission (only on first opt-in).
        2. Fires a browser Notification for each target newly crossed this session.
        """
        opt_in = st.session_state.get('notif_opt_in', False)
        request_perm = st.session_state.pop('notif_permission_requested', False)

        if not opt_in and not request_perm:
            return

        targets = st.session_state.get('portfolio_targets', {})

        if 'notif_fired' not in st.session_state:
            st.session_state['notif_fired'] = set()

        # Build a set of already-logged hits from persisted history to avoid duplicates
        if 'history_hit_logged' not in st.session_state:
            existing_history = self._load_target_history()
            st.session_state['history_hit_logged'] = {
                f"{e['symbol']}_{float(e['target_price']):.4f}"
                for e in existing_history
                if e.get('event') == 'hit'
            }

        new_hits = []
        for symbol, tgt in targets.items():
            if tgt <= 0:
                continue
            price = prices.get(symbol, 0.0)
            if price <= 0:
                continue
            if price >= tgt:
                fire_key = f"{symbol}_{tgt:.4f}"
                if fire_key not in st.session_state['notif_fired']:
                    pos = self.positions.get(symbol, {})
                    cb = float(pos.get('cost_basis', 0.0))
                    shares = int(pos.get('shares', 0))
                    gain = round((tgt - cb) * shares)
                    new_hits.append({
                        'symbol': symbol,
                        'price': round(price, 2),
                        'target': round(tgt, 2),
                        'gain': gain,
                        'shares': shares,
                    })
                    st.session_state['notif_fired'].add(fire_key)
                # Log to persistent history if not already recorded
                if fire_key not in st.session_state['history_hit_logged']:
                    self._log_target_event(symbol, 'hit', tgt, prices.get(symbol, 0.0))
                    st.session_state['history_hit_logged'].add(fire_key)

        hits_json = json.dumps(new_hits)
        request_perm_js = 'true' if request_perm else 'false'

        js = f"""
<script>
(async function() {{
    const Notif = window.parent && window.parent.Notification
                  ? window.parent.Notification
                  : (typeof Notification !== 'undefined' ? Notification : null);
    if (!Notif) return;

    if ({request_perm_js}) {{
        try {{ await Notif.requestPermission(); }} catch(e) {{}}
    }}

    if (Notif.permission !== 'granted') return;

    const hits = {hits_json};
    for (const h of hits) {{
        try {{
            new Notif('\uD83C\uDFAF ' + h.symbol + ' \u2014 Take-Profit Hit!', {{
                body: 'Price $' + h.price.toFixed(2) +
                      ' hit your target of $' + h.target.toFixed(2) +
                      '\\nEst. gain: $' + h.gain.toLocaleString() +
                      ' \u00b7 ' + h.shares.toLocaleString() + ' shares',
                tag: 'tp-' + h.symbol,
                icon: 'https://upload.wikimedia.org/wikipedia/commons/thumb/4/46/Bitcoin.svg/64px-Bitcoin.svg.png'
            }});
        }} catch(e) {{}}
    }}
}})();
</script>
"""
        components.html(js, height=0, scrolling=False)

    def _render_edit_positions(self) -> bool:
        """
        Render an expandable form for editing share counts and cost basis,
        removing positions, and adding brand-new positions.
        Returns True if positions were changed (triggers a rerun).
        """
        with st.expander("✏️ Edit Positions", expanded=False):
            st.caption(
                "Update your share counts and cost basis here. "
                "Changes are saved to disk and persist across page refreshes."
            )

            symbols = list(self.positions.keys())
            # Lay out 3 positions per row
            ROW_SIZE = 3
            rows = [symbols[i:i + ROW_SIZE] for i in range(0, len(symbols), ROW_SIZE)]

            edits = {}
            remove_symbol = None
            for row_symbols in rows:
                cols = st.columns(ROW_SIZE)
                for col, symbol in zip(cols, row_symbols):
                    pos = self.positions[symbol]
                    with col:
                        header_col, remove_col = st.columns([3, 1])
                        with header_col:
                            st.markdown(f"**{symbol}** — {pos['name']}")
                        with remove_col:
                            if st.button("🗑️", key=f"remove_{symbol}",
                                         help=f"Remove {symbol} from portfolio",
                                         use_container_width=True):
                                remove_symbol = symbol
                        shares_val = st.number_input(
                            "Shares",
                            min_value=0,
                            value=int(pos['shares']),
                            step=1,
                            key=f"edit_shares_{symbol}",
                        )
                        cb_val = st.number_input(
                            "Cost Basis ($)",
                            min_value=0.0,
                            value=float(pos['cost_basis']),
                            step=0.01,
                            format="%.2f",
                            key=f"edit_cb_{symbol}",
                        )
                        edits[symbol] = {'shares': shares_val, 'cost_basis': cb_val}

            # Handle removal immediately (before save button)
            if remove_symbol:
                removed_pos = self.positions[remove_symbol]
                self._log_position_change(
                    symbol=remove_symbol,
                    event="removed",
                    old_shares=removed_pos['shares'],
                    new_shares=0,
                    old_cost_basis=removed_pos['cost_basis'],
                    new_cost_basis=0.0,
                )
                del self.positions[remove_symbol]
                self.total_shares = sum(p['shares'] for p in self.positions.values())
                self._save_positions(self.positions)
                st.session_state['portfolio_positions'] = self.positions
                st.success(f"✅ {remove_symbol} removed from portfolio.")
                return True

            if st.button("💾 Save Changes", type="primary"):
                for symbol, vals in edits.items():
                    old_pos = self.positions[symbol]
                    old_shares = old_pos['shares']
                    old_cb = old_pos['cost_basis']
                    new_shares = vals['shares']
                    new_cb = vals['cost_basis']
                    if old_shares != new_shares or round(old_cb, 4) != round(new_cb, 4):
                        self._log_position_change(
                            symbol=symbol,
                            event="updated",
                            old_shares=old_shares,
                            new_shares=new_shares,
                            old_cost_basis=old_cb,
                            new_cost_basis=new_cb,
                        )
                    self.positions[symbol]['shares'] = new_shares
                    self.positions[symbol]['cost_basis'] = new_cb
                self.total_shares = sum(p['shares'] for p in self.positions.values())
                self._save_positions(self.positions)
                # Update session_state so the rest of the page reflects edits immediately
                st.session_state['portfolio_positions'] = self.positions
                st.success("✅ Positions saved successfully!")
                return True

            # ── Add New Position ─────────────────────────────────────────────
            st.divider()
            st.markdown("#### ➕ Add New Position")
            st.caption("Enter the ticker symbol and details for a new holding.")

            add_col1, add_col2, add_col3, add_col4 = st.columns(4)
            with add_col1:
                new_ticker = st.text_input(
                    "Ticker Symbol",
                    placeholder="e.g. CLSK",
                    key="new_position_ticker",
                ).strip().upper()
            with add_col2:
                new_name = st.text_input(
                    "Company Name",
                    placeholder="e.g. CleanSpark Inc",
                    key="new_position_name",
                ).strip()
            with add_col3:
                new_shares = st.number_input(
                    "Shares",
                    min_value=0,
                    value=0,
                    step=1,
                    key="new_position_shares",
                )
            with add_col4:
                new_cb = st.number_input(
                    "Cost Basis ($)",
                    min_value=0.0,
                    value=0.0,
                    step=0.01,
                    format="%.2f",
                    key="new_position_cb",
                )

            if st.button("➕ Add Position", type="secondary"):
                if not new_ticker:
                    st.error("❌ Ticker symbol is required.")
                elif new_ticker in self.positions:
                    st.error(f"❌ {new_ticker} already exists. Edit it above.")
                elif new_shares <= 0:
                    st.error("❌ Shares must be greater than 0.")
                else:
                    display_name = new_name if new_name else new_ticker
                    self.positions[new_ticker] = {
                        'shares':     int(new_shares),
                        'cost_basis': float(new_cb),
                        'name':       display_name,
                    }
                    self._log_position_change(
                        symbol=new_ticker,
                        event="added",
                        old_shares=0,
                        new_shares=int(new_shares),
                        old_cost_basis=0.0,
                        new_cost_basis=float(new_cb),
                    )
                    self.total_shares = sum(p['shares'] for p in self.positions.values())
                    self._save_positions(self.positions)
                    st.session_state['portfolio_positions'] = self.positions
                    st.success(f"✅ {new_ticker} added to portfolio!")
                    return True

        return False

    def render(self, data_fetcher, options_analyzer):
        """Render personalized portfolio dashboard"""
        st.title("🏆 Your Personal Mining Portfolio Command Center")
        st.markdown("### Real-Time Analysis of Your Actual Holdings")

        # Sync positions from session_state (updated by the edit form)
        if 'portfolio_positions' in st.session_state:
            self.positions = st.session_state['portfolio_positions']
            self.total_shares = sum(p['shares'] for p in self.positions.values())
        else:
            st.session_state['portfolio_positions'] = self.positions

        # Edit positions form — always at the top so the user can update before data loads
        saved = self._render_edit_positions()
        if saved:
            st.rerun()

        # Portfolio overview
        self._render_portfolio_overview(data_fetcher)
        
        # Income strategies by position size
        self._render_income_strategies(data_fetcher, options_analyzer)
        
        # Cross-portfolio strategies
        self._render_cross_portfolio_strategies(data_fetcher, options_analyzer)
        
        # Total portfolio projections
        self._render_total_projections(data_fetcher, options_analyzer)
    
    def _fetch_prices(self, data_fetcher):
        """Fetch current prices for all positions. Returns dict {symbol: price}."""
        prices = {}
        for symbol in self.positions:
            try:
                stock_data = data_fetcher.get_stock_data([symbol], period='1D')
                if not stock_data.empty and symbol in stock_data.columns:
                    prices[symbol] = float(stock_data[symbol].iloc[-1])
                else:
                    prices[symbol] = 0.0
            except Exception:
                prices[symbol] = 0.0
        return prices

    def _render_portfolio_overview(self, data_fetcher):
        """Show current portfolio value, cost basis, and P&L for all positions."""
        st.subheader("📊 Your Current Portfolio")

        prices = self._fetch_prices(data_fetcher)

        # ── Aggregate calculations ──────────────────────────────────────────
        total_invested = 0.0
        total_value    = 0.0

        for symbol, pos in self.positions.items():
            cb    = pos.get('cost_basis', 0.0)
            price = prices.get(symbol, 0.0)
            total_invested += cb    * pos['shares']
            total_value    += price * pos['shares']

        total_pnl     = total_value - total_invested
        total_pnl_pct = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

        # ── Headline metrics ────────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            st.metric("💰 Total Invested",       f"${total_invested:,.0f}",
                      help="Shares × cost basis for every saved position — what you paid in total.")
        with c2:
            st.metric("📈 Current Value",         f"${total_value:,.0f}",
                      help="Shares × latest price (Yahoo Finance, delayed ~15 min).")
        with c3:
            delta_color = "normal" if total_pnl >= 0 else "inverse"
            st.metric("🏦 Total Gain / Loss $",
                      f"${total_pnl:,.0f}", help=HELP["cost_basis"],
                      delta_color=delta_color)
        with c4:
            st.metric("📊 Total Gain / Loss %",
                      f"{total_pnl_pct:+.1f}%",
                      delta_color="normal" if total_pnl_pct >= 0 else "inverse")

        explain("cost_basis")
        st.divider()

        # ── Target & Stop-Loss price inputs ─────────────────────────────────
        st.subheader("📋 Position Details — P&L Breakdown")
        st.caption(
            "Set a take-profit target (🎯) and/or a stop-loss level (🚨) per position. "
            "Leave at 0.00 to skip. Alerts fire when prices cross those levels."
        )

        # Seed session state from disk on first load
        if 'portfolio_targets' not in st.session_state:
            st.session_state['portfolio_targets'] = self._load_targets()
        if 'portfolio_stop_losses' not in st.session_state:
            st.session_state['portfolio_stop_losses'] = self._load_stop_losses()

        symbols = list(self.positions.keys())
        targets_changed = False
        stop_losses_changed = False

        for symbol in symbols:
            col_label, col_target, col_sl = st.columns([1.2, 1, 1])
            with col_label:
                st.markdown(f"**{symbol}**")
            with col_target:
                old_target = st.session_state['portfolio_targets'].get(symbol, 0.0)
                t = st.number_input(
                    f"🎯 Target $ ({symbol})",
                    min_value=0.0,
                    value=float(old_target),
                    step=0.5,
                    format="%.2f",
                    key=f"target_{symbol}",
                    label_visibility="visible",
                )
                if t != old_target:
                    targets_changed = True
                    current_price = prices.get(symbol, 0.0)
                    if t == 0.0:
                        self._log_target_event(symbol, "cleared", old_target, current_price)
                    else:
                        self._log_target_event(symbol, "set", t, current_price)
                st.session_state['portfolio_targets'][symbol] = t
            with col_sl:
                default_sl = st.session_state['portfolio_stop_losses'].get(symbol, 0.0)
                sl = st.number_input(
                    f"🚨 Stop-Loss $ ({symbol})",
                    min_value=0.0,
                    value=float(default_sl),
                    step=0.5,
                    format="%.2f",
                    key=f"stop_loss_{symbol}",
                    label_visibility="visible",
                )
                if sl != st.session_state['portfolio_stop_losses'].get(symbol, 0.0):
                    stop_losses_changed = True
                st.session_state['portfolio_stop_losses'][symbol] = sl

        # Persist to disk whenever any value changes
        if targets_changed:
            self._save_targets(st.session_state['portfolio_targets'])
        if stop_losses_changed:
            self._save_stop_losses(st.session_state['portfolio_stop_losses'])

        # ── Browser notification opt-in ──────────────────────────────────────
        self._render_notification_controls()

        # ── Position rows + total row ───────────────────────────────────────
        rows = []
        total_pnl_acc   = 0.0
        total_inv_acc   = 0.0
        total_mkt_acc   = 0.0

        for symbol, pos in self.positions.items():
            cb            = pos.get('cost_basis', 0.0)
            price         = prices.get(symbol, 0.0)
            shares        = pos['shares']
            invested      = cb * shares
            mkt_value     = price * shares
            pnl_dollars   = mkt_value - invested
            pnl_pct       = ((price - cb) / cb * 100) if cb > 0 else 0.0
            breakeven_gap = price - cb
            max_contracts = shares // 100
            target        = st.session_state['portfolio_targets'].get(symbol, 0.0)
            stop_loss     = st.session_state['portfolio_stop_losses'].get(symbol, 0.0)

            total_pnl_acc += pnl_dollars
            total_inv_acc += invested
            total_mkt_acc += mkt_value

            if price > 0 and cb > 0:
                status = "✅ Profit" if price >= cb else "🔴 Loss"
            else:
                status = "❓ N/A"

            # Stop-loss status
            if stop_loss > 0 and price > 0:
                if price <= stop_loss:
                    sl_str = f"🚨 BELOW ${stop_loss:.2f}"
                else:
                    gap = price - stop_loss
                    sl_str = f"${stop_loss:.2f} (gap +${gap:.2f})"
            else:
                sl_str = "—"

            # Progress toward target
            if target > 0 and cb > 0 and price > 0:
                needed_gain = target - cb
                current_gain = price - cb
                if needed_gain > 0:
                    progress_pct = min(100.0, max(0.0, current_gain / needed_gain * 100))
                    target_str   = f"{progress_pct:.0f}% of ${target:.2f}"
                elif price >= target:
                    progress_pct = 100.0
                    target_str   = "✅ Target reached!"
                else:
                    progress_pct = 0.0
                    target_str   = "Set target above cost basis"
            else:
                progress_pct = 0.0
                target_str   = "—"

            rows.append({
                'Symbol':           symbol,
                'Company':          pos['name'],
                'Shares':           f"{shares:,}",
                'Cost Basis':       f"${cb:.2f}",
                'Current':          f"${price:.2f}" if price > 0 else "N/A",
                'P&L $':            f"${pnl_dollars:,.0f}" if price > 0 else "N/A",
                'P&L %':            f"{pnl_pct:+.1f}%" if price > 0 else "N/A",
                'vs Breakeven':     f"{breakeven_gap:+.2f}" if price > 0 else "N/A",
                'Status':           status,
                'Target Progress':  target_str,
                'Stop-Loss':        sl_str,
                'Contracts':        max_contracts,
            })

        # Total row
        total_pnl_pct_acc = (total_pnl_acc / total_inv_acc * 100) if total_inv_acc > 0 else 0.0
        rows.append({
            'Symbol':          '**TOTAL**',
            'Company':         '—',
            'Shares':          '—',
            'Cost Basis':      '—',
            'Current':         '—',
            'P&L $':           f"${total_pnl_acc:,.0f}",
            'P&L %':           f"{total_pnl_pct_acc:+.1f}%",
            'vs Breakeven':    '—',
            'Status':          '✅ Profit' if total_pnl_acc >= 0 else '🔴 Loss',
            'Target Progress': '—',
            'Stop-Loss':       '—',
            'Contracts':       sum(pos['shares'] // 100 for pos in self.positions.values()),
        })

        df = pd.DataFrame(rows)

        def _style_pnl(row):
            if row['Symbol'] == '**TOTAL**':
                return ['font-weight: bold; background-color: rgba(100,100,200,0.15)'] * len(row)
            pnl = row['P&L %']
            if pnl == "N/A":
                return [''] * len(row)
            if pnl.startswith('+'):
                return ['background-color: rgba(0,200,83,0.12)'] * len(row)
            elif pnl.startswith('-'):
                return ['background-color: rgba(213,0,0,0.12)'] * len(row)
            return [''] * len(row)

        st.dataframe(df.style.apply(_style_pnl, axis=1),
                     use_container_width=True, hide_index=True)

        # ── Summary: positions at/above target and at/below stop-loss ───────
        targets_set = {
            s: st.session_state['portfolio_targets'].get(s, 0.0)
            for s in self.positions
        }
        stop_losses_set = {
            s: st.session_state['portfolio_stop_losses'].get(s, 0.0)
            for s in self.positions
        }
        at_target = [
            s for s, tgt in targets_set.items()
            if tgt > 0 and prices.get(s, 0.0) >= tgt
        ]
        at_stop_loss = [
            s for s, sl in stop_losses_set.items()
            if sl > 0 and prices.get(s, 0.0) > 0 and prices.get(s, 0.0) <= sl
        ]
        total_with_targets    = sum(1 for t in targets_set.values() if t > 0)
        total_with_stop_losses = sum(1 for sl in stop_losses_set.values() if sl > 0)

        has_summary = total_with_targets > 0 or total_with_stop_losses > 0
        if has_summary:
            st.divider()
            summary_cols = st.columns(4)
            with summary_cols[0]:
                st.metric("🎯 Targets Set", total_with_targets)
            with summary_cols[1]:
                st.metric(
                    "✅ At / Above Target",
                    len(at_target),
                    delta=f"{len(at_target)} of {total_with_targets}" if total_with_targets else None,
                    delta_color="normal" if at_target else "off",
                )
            with summary_cols[2]:
                st.metric("🚨 Stop-Losses Set", total_with_stop_losses)
            with summary_cols[3]:
                st.metric(
                    "⚠️ At / Below Stop-Loss",
                    len(at_stop_loss),
                    delta=f"{len(at_stop_loss)} of {total_with_stop_losses}" if total_with_stop_losses else None,
                    delta_color="inverse" if at_stop_loss else "off",
                )

        # ── 🎯 Take-Profit Alert Banners ────────────────────────────────────
        if at_target:
            st.divider()
            st.markdown("### 🎯 Take-Profit Alerts")
            for symbol in at_target:
                tgt   = targets_set[symbol]
                price = prices.get(symbol, 0.0)
                pos   = self.positions[symbol]
                shares = pos['shares']
                cb     = pos.get('cost_basis', 0.0)
                gain_at_target = (tgt - cb) * shares
                st.success(
                    f"🎯 **{symbol} — Take-Profit Target Reached!**  \n"
                    f"Current price **${price:.2f}** has hit your target of **${tgt:.2f}**.  \n"
                    f"Position: {shares:,} shares · Gain at target: **${gain_at_target:,.0f}**"
                )

        # ── 🚨 Stop-Loss Warning Banners ─────────────────────────────────────
        if at_stop_loss:
            st.divider()
            st.markdown("### 🚨 Stop-Loss Warnings")
            for symbol in at_stop_loss:
                sl    = stop_losses_set[symbol]
                price = prices.get(symbol, 0.0)
                pos   = self.positions[symbol]
                shares = pos['shares']
                cb     = pos.get('cost_basis', 0.0)
                loss_vs_sl = (price - sl) * shares
                st.error(
                    f"🚨 **{symbol} — Stop-Loss Warning!**  \n"
                    f"Current price **${price:.2f}** is at or below your stop-loss of **${sl:.2f}**.  \n"
                    f"Position: {shares:,} shares · "
                    f"Loss vs stop-loss level: **${loss_vs_sl:,.0f}**"
                )

        # ── Browser push notifications for newly hit targets ─────────────────
        self._fire_target_notifications(prices)

        # ── Per-position progress bars ──────────────────────────────────────
        non_zero_targets = {
            s: st.session_state['portfolio_targets'][s]
            for s in self.positions
            if st.session_state['portfolio_targets'].get(s, 0) > 0
        }
        if non_zero_targets:
            st.markdown("**📈 Progress Toward Price Targets**")
            for symbol, target in non_zero_targets.items():
                pos   = self.positions[symbol]
                cb    = pos.get('cost_basis', 0.0)
                price = prices.get(symbol, 0.0)
                if cb > 0 and price > 0:
                    if price >= target:
                        st.caption(f"🎯 **{symbol}: ${price:.2f} ≥ ${target:.2f} — TARGET REACHED!**")
                        st.progress(1.0)
                    elif target > cb:
                        needed_gain  = target - cb
                        current_gain = price - cb
                        pct          = min(1.0, max(0.0, current_gain / needed_gain))
                        color_label  = "🟡" if pct >= 0.5 else "🔴"
                        label        = (f"{symbol}: ${price:.2f} → ${target:.2f} "
                                        f"({color_label} {pct*100:.0f}% of the way)")
                        st.caption(label)
                        st.progress(pct)

        # ── Position value bar chart ────────────────────────────────────────
        import plotly.graph_objects as go
        fig_cols = ['Symbol', 'Invested $', 'Current $']
        chart_data = []
        for symbol, pos in self.positions.items():
            cb    = pos.get('cost_basis', 0.0)
            price = prices.get(symbol, 0.0)
            chart_data.append({
                'Symbol':     symbol,
                'Invested $': cb    * pos['shares'],
                'Current $':  price * pos['shares'],
            })
        cdf = pd.DataFrame(chart_data).sort_values('Current $', ascending=False)

        fig = go.Figure()
        fig.add_bar(name='Invested', x=cdf['Symbol'], y=cdf['Invested $'],
                    marker_color='rgba(100,120,200,0.6)')
        fig.add_bar(name='Current',  x=cdf['Symbol'], y=cdf['Current $'],
                    marker_color=[
                        'rgba(0,200,83,0.7)' if c >= i else 'rgba(213,0,0,0.7)'
                        for c, i in zip(cdf['Current $'], cdf['Invested $'])
                    ])
        fig.update_layout(
            barmode='group',
            title='Position Value: Cost Basis vs Current Market Value',
            template='plotly_dark',
            height=380,
            yaxis_title='Value ($)',
            showlegend=True,
        )
        st.plotly_chart(fig, use_container_width=True)

        # ── Target History ──────────────────────────────────────────────────
        self._render_target_history()

        # ── Position Change History ─────────────────────────────────────────
        self._render_position_history()

    def _render_target_history(self) -> None:
        """Show a collapsible log of all target set / cleared / hit events."""
        history = self._load_target_history()
        if not history:
            return

        with st.expander(f"📜 Target Price History ({len(history)} events)", expanded=False):
            st.caption(
                "A timestamped record of every price target you've set, changed, "
                "cleared, or had hit. Persisted across sessions in "
                f"`{HISTORY_FILE}`."
            )

            # Newest first
            rows = []
            for e in reversed(history):
                event = e.get('event', '')
                if event == 'set':
                    icon = "🎯"
                    label = "Target set"
                elif event == 'cleared':
                    icon = "🗑️"
                    label = "Target cleared"
                elif event == 'hit':
                    icon = "✅"
                    label = "Target HIT"
                else:
                    icon = "•"
                    label = event.capitalize()

                target_price = e.get('target_price', 0.0)
                price_at_event = e.get('price_at_event', 0.0)

                rows.append({
                    'Event':         f"{icon} {label}",
                    'Symbol':        e.get('symbol', ''),
                    'Target $':      f"${target_price:.2f}" if target_price else "—",
                    'Price at Event':f"${price_at_event:.2f}" if price_at_event else "—",
                    'Timestamp':     e.get('timestamp', ''),
                })

            df = pd.DataFrame(rows)

            def _style_event(row):
                ev = row['Event']
                if '✅' in ev:
                    return ['background-color: rgba(0,200,83,0.15)'] * len(row)
                if '🗑' in ev:
                    return ['background-color: rgba(150,150,150,0.10)'] * len(row)
                return [''] * len(row)

            st.dataframe(
                df.style.apply(_style_event, axis=1),
                use_container_width=True,
                hide_index=True,
            )

            col_dl, _ = st.columns([1, 3])
            with col_dl:
                try:
                    csv_bytes = df.to_csv(index=False).encode()
                    st.download_button(
                        "⬇️ Download as CSV",
                        data=csv_bytes,
                        file_name="portfolio_target_history.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                except Exception:
                    pass

    def _render_position_history(self) -> None:
        """Show a collapsible log of all position share/cost-basis changes."""
        history = self._load_position_history()
        if not history:
            return

        with st.expander(f"📋 Position Change History ({len(history)} entries)", expanded=False):
            st.caption(
                "A timestamped record of every time shares or cost basis were changed. "
                f"Persisted across sessions in `{POSITION_HISTORY_FILE}`."
            )

            rows = []
            for e in reversed(history):
                event = e.get('event', 'updated')
                if event == 'added':
                    icon = "➕"
                    label = "Added"
                elif event == 'removed':
                    icon = "🗑️"
                    label = "Removed"
                else:
                    icon = "✏️"
                    label = "Updated"

                old_shares    = e.get('old_shares', 0)
                new_shares    = e.get('new_shares', 0)
                old_cb        = e.get('old_cost_basis', 0.0)
                new_cb        = e.get('new_cost_basis', 0.0)

                shares_change = (
                    f"{old_shares:,} → {new_shares:,}"
                    if old_shares != new_shares
                    else f"{new_shares:,} (no change)"
                )
                cb_change = (
                    f"${old_cb:.2f} → ${new_cb:.2f}"
                    if round(old_cb, 4) != round(new_cb, 4)
                    else f"${new_cb:.2f} (no change)"
                )

                rows.append({
                    'Event':          f"{icon} {label}",
                    'Symbol':         e.get('symbol', ''),
                    'Shares Change':  shares_change,
                    'Cost Basis':     cb_change,
                    'Timestamp':      e.get('timestamp', ''),
                })

            df = pd.DataFrame(rows)

            def _style_pos_event(row):
                ev = row['Event']
                if '➕' in ev:
                    return ['background-color: rgba(0,200,83,0.12)'] * len(row)
                if '🗑' in ev:
                    return ['background-color: rgba(213,0,0,0.10)'] * len(row)
                return ['background-color: rgba(100,120,200,0.08)'] * len(row)

            st.dataframe(
                df.style.apply(_style_pos_event, axis=1),
                use_container_width=True,
                hide_index=True,
            )

            col_dl, _ = st.columns([1, 3])
            with col_dl:
                try:
                    csv_bytes = df.to_csv(index=False).encode()
                    st.download_button(
                        "⬇️ Download as CSV",
                        data=csv_bytes,
                        file_name="position_change_history.csv",
                        mime="text/csv",
                        use_container_width=True,
                    )
                except Exception:
                    pass

    def _get_strategy_tier(self, shares):
        """Determine strategy tier based on position size"""
        if shares >= 1000:
            return "🔥 MEGA (Multi-tranche)"
        elif shares >= 500:
            return "🎯 LARGE (Full strategies)" 
        elif shares >= 200:
            return "💡 MEDIUM (Basic coverage)"
        elif shares >= 100:
            return "📈 SMALL (Limited options)"
        else:
            return "🔒 MICRO (No options)"
    
    def _render_income_strategies(self, data_fetcher, options_analyzer):
        """Show income strategies by position tier"""
        st.subheader("💰 Position-Specific Income Strategies")
        
        # Group by strategy tier
        mega_positions = {k: v for k, v in self.positions.items() if v['shares'] >= 1000}
        large_positions = {k: v for k, v in self.positions.items() if 500 <= v['shares'] < 1000}
        medium_positions = {k: v for k, v in self.positions.items() if 200 <= v['shares'] < 500}
        small_positions = {k: v for k, v in self.positions.items() if 100 <= v['shares'] < 200}
        
        # MEGA Positions - Multi-tranche strategies
        if mega_positions:
            with st.expander("🔥 MEGA Positions - Multi-Tranche Strategies", expanded=True):
                st.markdown("**These positions are large enough for multi-layer (laddered) option strategies.**")
                
                for symbol, data in mega_positions.items():
                    st.markdown(f"### {symbol} - {data['shares']:,} shares")
                    
                    # Calculate potential tranches
                    contracts_available = data['shares'] // 100
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.info(f"**Contracts Available:** {contracts_available}")
                        st.info(f"**Monthly Income Tier:** 50-75% of position")
                    
                    with col2:
                        st.success(f"**Quarterly Income Tier:** 25-30% of position")
                        st.success(f"**Long-term LEAPs:** Remaining contracts")
                    
                    with col3:
                        monthly_contracts = int(contracts_available * 0.6)
                        quarterly_contracts = int(contracts_available * 0.25)
                        leaps_contracts = contracts_available - monthly_contracts - quarterly_contracts
                        
                        st.markdown(f"**Suggested Split:**")
                        st.markdown(f"- Monthly: {monthly_contracts} contracts")
                        st.markdown(f"- Quarterly: {quarterly_contracts} contracts") 
                        st.markdown(f"- LEAPs: {leaps_contracts} contracts")
                    
                    st.divider()
        
        # LARGE Positions - Full strategies
        if large_positions:
            with st.expander("🎯 LARGE Positions - Full Coverage Strategies", expanded=False):
                for symbol, data in large_positions.items():
                    st.markdown(f"**{symbol}:** {data['shares']:,} shares → {data['shares']//100} contracts available")
                    st.markdown(f"- **Strategy:** Monthly covered calls + protective puts")
                    st.caption("Live premium estimates for every position are in 🚀 Total Portfolio Income Projections below.")
        
        # MEDIUM/SMALL Positions
        if medium_positions or small_positions:
            with st.expander("💡 MEDIUM/SMALL Positions - Focused Strategies", expanded=False):
                all_smaller = {**medium_positions, **small_positions}
                
                for symbol, data in all_smaller.items():
                    contracts = data['shares'] // 100
                    if contracts > 0:
                        st.markdown(f"**{symbol}:** {data['shares']:,} shares → {contracts} contracts")
                        st.markdown(f"- **Strategy:** Conservative covered calls or protective puts")
    
    def _render_cross_portfolio_strategies(self, data_fetcher, options_analyzer):
        """Show strategies that work across multiple positions"""
        st.subheader("🔗 Cross-Portfolio Strategies")
        
        tab1, tab2, tab3 = st.tabs(["Portfolio Collars", "Sector Hedging", "Income Laddering"])
        
        with tab1:
            st.markdown("**Portfolio-Wide Collar Strategy**")
            st.info("""
            **Concept:** Use your RIOT mega-position as the anchor:
            - **SELL calls** on RIOT (huge premium)
            - **BUY puts** across smaller positions for protection
            - **Result:** Income from RIOT funds protection for entire portfolio
            """)
            
            # Show which positions could work together
            ranked = sorted(self.positions.items(), key=lambda kv: kv[1]['shares'], reverse=True)
            gens = [f"{s} ({p['shares']:,} shares)" for s, p in ranked if p['shares'] >= 500][:2]
            prot = [s for s, p in ranked if 0 < p['shares'] < 500]
            st.markdown("**Possible pairing (from your saved positions):**")
            st.markdown(f"- **Income Generator:** {' + '.join(gens) if gens else 'no position with 500+ shares'}")
            st.markdown(f"- **Protection Targets:** {', '.join(prot) if prot else '—'}")
        
        with tab2:
            st.markdown("**Sector Risk Management**")
            n_pos = sum(1 for p in self.positions.values() if p['shares'] > 0)
            st.warning(f"""
            **Portfolio Risk:** You're heavily concentrated in Bitcoin mining
            - **{n_pos} crypto-related positions** that tend to move together (see 🔗 RIOT Correlation Map)
            - Owning several miners is **not** real diversification — in sell-offs they fall together
            - The VIX has tended to rise when miners fall, which is why some investors use it as a hedge
            """)
        
        with tab3:
            st.markdown("**Staggered Income Generation**")
            st.success("""
            **Income Laddering Strategy:**
            - **Week 1:** RIOT + KEEL covered calls
            - **Week 2:** WULF + IREN covered calls  
            - **Week 3:** CIFR + BTBT covered calls
            - **Week 4:** MARA + CLSK covered calls
            
            **Result:** Weekly income instead of monthly lump sums
            """)
    
    def _get_atm_call_premium(self, symbol: str, current_price: float) -> tuple:
        """
        Fetch nearest-expiry ATM call premium from yfinance.
        Returns (premium_per_contract_dollar, iv, reasoning_str).
        Falls back to IV-based Black-Scholes estimate, then to $0.
        """
        try:
            ticker   = yf.Ticker(symbol)
            exps     = ticker.options
            if not exps:
                return 0.0, 0.0, "No options listed"

            # Use the expiry closest to ~30 days so "monthly income" really is monthly
            # (previously the nearest weekly was multiplied by 12).
            from datetime import date as _date
            today = _date.today()
            exp_date = min(exps, key=lambda e: abs((datetime.strptime(e, "%Y-%m-%d").date() - today).days - 30))
            chain    = ticker.option_chain(exp_date)
            calls    = chain.calls

            # ATM = within 5% of current price
            atm = calls[
                (calls['strike'] >= current_price * 0.97) &
                (calls['strike'] <= current_price * 1.05)
            ].copy()

            if atm.empty:
                # Widen to 10%
                atm = calls[
                    (calls['strike'] >= current_price * 0.90) &
                    (calls['strike'] <= current_price * 1.10)
                ].copy()

            if atm.empty:
                return 0.0, 0.0, "No ATM calls found"

            # Use lastPrice; fall back to mid of bid/ask
            atm['best_price'] = atm.apply(
                lambda r: r['lastPrice'] if r['lastPrice'] > 0
                else (r['bid'] + r['ask']) / 2 if (r['bid'] + r['ask']) > 0
                else 0.0,
                axis=1
            )
            avg_premium = float(atm['best_price'].mean())
            avg_iv      = float(atm['impliedVolatility'].mean()) if 'impliedVolatility' in atm.columns else 0.0

            # Multiply by 100 shares per contract
            contract_value = avg_premium * 100
            reasoning = f"{exp_date} exp · IV {avg_iv:.0%} · ATM ~${atm['strike'].mean():.2f}"
            return contract_value, avg_iv, reasoning
        except Exception:
            return 0.0, 0.0, "Options data unavailable"

    def _render_total_projections(self, data_fetcher, options_analyzer):
        """Calculate total portfolio income potential using live options IV data."""
        st.subheader("🚀 Total Portfolio Income Projections")
        st.caption("Estimates use live Yahoo Finance at-the-money call premiums for the expiry closest to 30 days out. "
                   "⚠️ Selling at-the-money calls means roughly a 50/50 chance your shares get sold (called away) at "
                   "that strike — for a long-term holder, out-of-the-money calls (lower income, less risk) are more typical. "
                   "Premiums change daily; this is not guaranteed income.")

        prices = self._fetch_prices(data_fetcher)

        income_data   = []
        total_monthly = 0.0

        with st.spinner("Fetching live options premiums for all positions…"):
            for symbol, pos in self.positions.items():
                shares    = pos['shares']
                contracts = shares // 100
                price     = prices.get(symbol, 0.0)

                if contracts == 0 or price == 0:
                    income_data.append({
                        'Symbol':         symbol,
                        'Shares':         f"{shares:,}",
                        'Contracts':      0,
                        'ATM Premium':    "$0.00",
                        'Monthly Income': "$0",
                        'Annual Income':  "$0",
                        'Live IV':        "N/A",
                        'Notes':          "< 100 shares — no options",
                    })
                    continue

                contract_value, iv, reasoning = self._get_atm_call_premium(symbol, price)
                monthly = contract_value * contracts
                total_monthly += monthly

                income_data.append({
                    'Symbol':         symbol,
                    'Shares':         f"{shares:,}",
                    'Contracts':      contracts,
                    'ATM Premium':    f"${contract_value:.2f}" if contract_value > 0 else "N/A",
                    'Monthly Income': f"${monthly:,.0f}" if monthly > 0 else "N/A",
                    'Annual Income':  f"${monthly * 12:,.0f}" if monthly > 0 else "N/A",
                    'Live IV':        f"{iv:.0%}" if iv > 0 else "N/A",
                    'Notes':          reasoning,
                })

        total_annual = total_monthly * 12

        # Re-fetch portfolio value for % return calc
        total_value = sum(
            prices.get(sym, 0.0) * pos['shares']
            for sym, pos in self.positions.items()
        )
        annual_return = (total_annual / total_value * 100) if total_value > 0 else 0.0

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Monthly Income Potential",  f"${total_monthly:,.0f}")
        with col2:
            st.metric("Annual Income Potential",   f"${total_annual:,.0f}")
        with col3:
            st.metric("Est. Annual Yield on Value",f"{annual_return:.1f}%",
                      help="Annual options income ÷ current portfolio market value")
        with col4:
            total_contracts = sum(pos['shares'] // 100 for pos in self.positions.values())
            st.metric("Total Contracts Available", total_contracts)

        st.markdown("### 📊 Income Breakdown by Position (Live Data)")
        df = pd.DataFrame(income_data)
        st.dataframe(df, use_container_width=True, hide_index=True)

        if total_monthly > 0:
            st.success(
                f"🎯 **Live estimate: ${total_monthly:,.0f}/month · ${total_annual:,.0f}/year** "
                f"({annual_return:.1f}% annual yield on current portfolio value). "
                f"Premiums shown are nearest-expiry ATM calls — actual income depends on strike selection and timing."
            )
        else:
            st.info("Options premium data unavailable at this time. Prices may be outside market hours.")