"""
components/signal_reconcile.py — small panels that put My Plan (final word), the short-term
Trade Signal and news tone side by side, using the shared hub, so tabs never silently disagree.
"""
import streamlit as st

from utils.explain import HELP, explain


def render_cross_tab_panel(symbol: str, plan_action: str, add_action: str = None):
    """Used inside 🧭 My Plan: how the short-term tabs see this stock right now."""
    from utils.news_sentiment import news_sentiment
    from utils.signal_hub import reconcile, short_term_signal
    with st.expander(f"🔗 How the short-term tabs see {symbol} right now (and why My Plan still decides)"):
        stt = short_term_signal(symbol)
        news = news_sentiment(symbol)
        c1, c2, c3 = st.columns(3)
        c1.metric("🧭 My Plan", plan_action, f"Add more? {add_action}" if add_action else None, delta_color="off",
                  help=HELP["signal_hierarchy"])
        c2.metric("🚦 Trade Signals (days–weeks)", stt.get("signal", "N/A"),
                  f"RSI {stt['rsi']:.0f}" if stt.get("rsi") is not None else None, delta_color="off",
                  help=HELP["trade_signal"])
        c3.metric("📰 News tone (7 days)", news.get("label", "n/a"),
                  f"{news['score']:+.2f} · {news['n_headlines']} headlines" if news.get("available") else None,
                  delta_color="off", help=HELP["news_tone"])
        st.markdown(reconcile(stt.get("signal"), plan_action, symbol))
        st.caption("All three read the same shared prices (same last close and RSI). Headlines are in 📰 Sentiment & News.")
        explain("signal_hierarchy")


def render_plan_banner(watchlist):
    """Used at the top of 🚦 Trade Signals: the long-term call for your holdings, reconciled."""
    from utils.signal_hub import long_term_call, reconcile, short_term_signal
    try:
        from components.personal_portfolio import PersonalPortfolio
        held = [s for s, p in PersonalPortfolio._load_positions().items() if p.get("shares", 0) > 0 and s in watchlist]
    except Exception:
        held = []
    held = held or ["RIOT"]
    for sym in held[:3]:
        lt = long_term_call(sym)
        if not lt:
            continue
        stt = short_term_signal(sym)
        st.info(f"🧭 **Your long-term plan for {sym}: {lt['action']}** (My Plan — the final word). "
                + reconcile(stt.get("signal"), lt["action"], sym))


def render_reflexivity_banner(symbol: str, phase_label: str, edge: bool):
    """Used at the top of 🔄 Reflexivity: My Plan stays the final word; the phase is context."""
    from utils.signal_hub import long_term_call
    lt = long_term_call(symbol)
    plan = (lt["action"] + (f" (add more? {lt['add_action']})" if lt.get("add_action") else "")) if lt else "N/A"
    st.info(f"🧭 Your long-term plan for {symbol}: **{plan}** — My Plan is the final word.  \n"
            f"🔄 Reflexivity phase right now: **{phase_label or 'N/A'}** — "
            + ("historically this phase was followed by a measurably different 3–6 months (see 🧪 Track record), "
               "but it is still shown as context, not an instruction." if edge else
               "**context only**: in the 2018–2026 track record no phase or index level reliably predicted the next "
               "3–6 months (see 🧪 Track record), so it does not change My Plan's call."))


def render_reflexivity_context(symbol: str):
    """One-line context in 🧭 My Plan (deliberately NOT part of the call — see the Reflexivity track record)."""
    try:
        from components.reflexivity_dashboard import live_phase_and_edge
        ph, label, edge = live_phase_and_edge(symbol)
    except Exception:
        return
    if not label:
        return
    st.caption(f"🔄 Reflexivity context for {symbol}: **{label}**. Not used in the call above — "
               + ("its track record shows a difference, but it is kept as context."
                  if edge else "in a 2018–2026 backtest no reflexivity phase reliably predicted the next 3–6 months.")
               + " Details in the 🔄 Reflexivity tab.")
