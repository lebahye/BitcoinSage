"""
🔮 Forecast Center — honest statistical price ranges + every signal for a stock in one place.

Audit (Oct 2026) — what was removed and why:
  * "1W / 4W targets" were price × (1 ± |score| × 5% × horizon); with a score of −8.9 that gave
    RIOT a one-month "target" of $1.61 (−88%) at "86% probability" — outside its own "expected
    range".  The "probability" and "confidence" were 50 + |score| × 8 / × 10: invented numbers.
  * The "Options Flow" score used no options data (a price/volume proxy) and "Volume/Dark Pool"
    used no dark-pool data; both double-counted momentum already in the technical score.
  * Its BUY/SELL column was a third, separate signal that could contradict Trade Signals and
    My Plan.
Now: a volatility-based range with a backtested hit rate (utils.stat_forecast), and the ONE
long-term call (My Plan) + ONE short-term signal (Trade Signals) + news tone, reconciled.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.explain import HELP, explain
from utils.stat_forecast import HORIZONS, backtest_coverage, coverage_verdict, forecast_range


@st.cache_data(ttl=900, show_spinner=False)
def _range_and_coverage(symbol: str, h: int):
    from utils.signal_hub import get_ohlcv
    hist = get_ohlcv(symbol, "5y")
    if hist.empty:
        raise ValueError("no data")
    c = hist["Close"]
    return forecast_range(c, h), backtest_coverage(c, h), c.index[-1].date(), c.iloc[-504:]


def _safe_range(symbol, h):
    try:
        return _range_and_coverage(symbol, h)
    except Exception:
        return None, None, None, None


class WeeklyOutlook:
    """Forecast Center (kept class name for app.py compatibility)."""

    def render(self, selected_stocks, stock_names):
        st.title("🔮 Forecast Center")
        st.info("**What this shows, plainly:** the price range each stock is likely to stay inside, based only on how much "
                "it has been swinging. It does **not** guess up or down — no rule in this dashboard has shown it can "
                "reliably call a miner's direction week to week — and each range comes with its **real past hit rate**.")
        explain("stat_forecast")

        label = st.radio("Horizon", list(HORIZONS), index=1, horizontal=True, key="fc_horizon",
                         help="How far ahead the range is for (trading days: 1 week = 5, 1 month = 21, 3 months = 63).")
        h = HORIZONS[label]
        symbols = list(dict.fromkeys((["RIOT"] if "RIOT" in stock_names else []) + list(selected_stocks)))

        rows = []
        with st.spinner("Measuring volatility and checking past accuracy…"):
            for sym in symbols:
                f, cov, as_of, _ = _safe_range(sym, h)
                if not f:
                    rows.append({"Stock": sym, "Last close": "n/a", "68% range": "unavailable", "90% range": "",
                                 "Past hit rate (68% / 90%)": "", "Yearly volatility": ""})
                    continue
                rows.append({
                    "Stock": sym, "Last close": f"${f['price']:,.2f}",
                    "68% range": f"${f['low_68%']:,.2f} – ${f['high_68%']:,.2f}",
                    "90% range": f"${f['low_90%']:,.2f} – ${f['high_90%']:,.2f}",
                    "Past hit rate (68% / 90%)": (f"{cov['hit_68%']:.0%} / {cov['hit_90%']:.0%}" if cov else "n/a"),
                    "Yearly volatility": f"{f['annual_vol']:.0%}",
                })
        st.subheader(f"📏 Likely price range in {label}")
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                     column_config={"Past hit rate (68% / 90%)": st.column_config.TextColumn(
                         help="How often the real price ended inside the 68% / 90% range when this exact recipe was "
                              "replayed on the last 3 years (using only data available on each day).")})
        st.caption("Centre = today's close. Width = last year's daily volatility × √days. "
                   "Source: Yahoo Finance daily closes via the shared data hub (cached 15 min).")

        focus = st.selectbox("Look closer at", symbols, index=0, key="fc_focus",
                             format_func=lambda s: f"{s} — {stock_names.get(s, s)}")
        self._render_fan(focus, h, label)
        self._render_all_signals(focus)

    # ------------------------------------------------------------------
    def _render_fan(self, sym, h, label):
        f, cov, as_of, hist = _safe_range(sym, h)
        if not f:
            st.warning(f"No price history for {sym} right now — range unavailable.")
            return
        st.markdown(f"**{sym}: {coverage_verdict(cov)}**")
        end = pd.bdate_range(hist.index[-1], periods=h + 1)[-1]
        x = [hist.index[-1], end]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=hist.index, y=hist.values, name="History", line=dict(color="#bbb", width=1.5)))
        for k, fill in (("90%", "rgba(41,182,246,.12)"), ("68%", "rgba(41,182,246,.28)")):
            fig.add_trace(go.Scatter(x=x + x[::-1], y=[f["price"], f[f"high_{k}"], f[f"low_{k}"], f["price"]],
                                     fill="toself", fillcolor=fill, line=dict(width=0), name=f"{k} range in {label}"))
        fig.update_layout(template="plotly_dark", height=380, yaxis_title="Price ($)", hovermode="x unified",
                          legend=dict(orientation="h"), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)
        if cov:
            st.caption(f"Accuracy check: {cov['n']} past starting points from {cov['start']:%b %Y} to {cov['end']:%b %Y}. "
                       f"For comparison, {sym} finished higher {cov['up_share']:.0%} of the time over {label} — "
                       "close to a coin flip, which is why no direction is forecast.")

    # ------------------------------------------------------------------
    def _render_all_signals(self, sym):
        from utils.news_sentiment import news_sentiment
        from utils.signal_hub import long_term_call, reconcile, short_term_signal
        st.subheader(f"🧭 Every signal for {sym} in one place")
        with st.spinner("Collecting My Plan, Trade Signals and news…"):
            lt = long_term_call(sym)
            stt = short_term_signal(sym)
            news = news_sentiment(sym)
        c1, c2, c3 = st.columns(3)
        c1.metric("🧭 My Plan (final word)", lt["action"] if lt else "n/a",
                  (f"Add more? {lt['add_action']}" if lt and lt.get("add_action") else None), delta_color="off",
                  help=HELP["signal_hierarchy"])
        c2.metric("🚦 Short-term signal", stt.get("signal", "N/A"),
                  (f"RSI {stt['rsi']:.0f} · score {stt['raw_score']:+d}" if stt.get("rsi") is not None else None),
                  delta_color="off", help=HELP["trade_signal"])
        c3.metric("📰 News tone (7 days)", news.get("label", "n/a"),
                  (f"{news['score']:+.2f} from {news['n_headlines']} headlines" if news.get("available") else None),
                  delta_color="off", help=HELP["news_tone"])
        st.markdown(reconcile(stt.get("signal"), lt["action"] if lt else None, sym))
        explain("signal_hierarchy")
