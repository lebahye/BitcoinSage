"""
📰 Sentiment & News — real headlines, an honest headline-tone score, and the published
Crypto Fear & Greed Index.

Audit note (Oct 2026): the previous version of this tab showed **no news at all**.  Its
"Mining Sector Sentiment" was a price-momentum score relabelled as sentiment (and fell back
to a silent 5.0/10 on any error), and its "Fear & Greed Index" was a home-made composite that
fell back to 50 on error.  Both are replaced; numbers come from utils.news_sentiment, the same
module Trade Signals and the Next-Mover ranking use.
"""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.explain import HELP, explain
from utils.news_sentiment import crypto_fear_greed, news_sentiment

_TONE_ICON = {"Bullish": "🟢", "Neutral": "🟡", "Bearish": "🔴", "n/a": "⚪"}


class SentimentAnalysis:
    """Market sentiment and news (shared numbers via utils.news_sentiment)."""

    def render(self, selected_stocks, stock_names):
        st.subheader("📰 Sentiment & News")
        st.caption("What the news is saying about your miners this week, and the overall crypto mood. "
                   "Context only — your Hold/Sell call is in 🧭 My Plan.")
        self._render_news(selected_stocks, stock_names)
        st.divider()
        self._render_fear_greed()

    # ------------------------------------------------------------------
    def _render_news(self, selected_stocks, stock_names):
        st.markdown("### 🗞️ Headlines & headline tone (last 7 days)")
        symbols = list(dict.fromkeys(["RIOT"] + list(selected_stocks)))
        rows, results = [], {}
        with st.spinner("Fetching headlines…"):
            for sym in symbols:
                r = news_sentiment(sym)
                results[sym] = r
                rows.append({
                    "Stock": sym,
                    "Tone": f"{_TONE_ICON.get(r['label'], '⚪')} {r['label']}",
                    "Score (−1 to +1)": "n/a" if r.get("score") is None else f"{r['score']:+.2f}",
                    "Headlines": r.get("n_headlines", 0),
                    "Positive / Negative": (f"{r.get('n_pos', 0)} / {r.get('n_neg', 0)}" if r.get("available") else "n/a"),
                    "Sources": ", ".join(r.get("sources", [])) or "unavailable",
                })
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True,
                     column_config={"Score (−1 to +1)": st.column_config.TextColumn(help=HELP["news_tone"])})
        live = [r for r in results.values() if r.get("available")]
        if not live:
            st.warning("⚪ No headlines could be fetched right now (news sources unreachable). "
                       "Tone is shown as n/a — nothing is filled in. Try 🔄 Refresh Data later.")
        else:
            st.caption(f"Method: {live[0].get('method', '')}. Same tone numbers feed 🚦 Trade Signals and the "
                       f"🎯 Next-Mover ranking. Fetched {live[0].get('fetched', '')}, cached 30 min.")
        explain("news_tone")

        for sym in symbols:
            r = results[sym]
            title = f"{_TONE_ICON.get(r['label'], '⚪')} {sym} — {stock_names.get(sym, sym)} · {r.get('n_headlines', 0)} headlines"
            with st.expander(title, expanded=(sym == "RIOT")):
                if not r.get("available"):
                    st.info("No headlines available right now." + (f" ({r['error']})" if r.get("error") else ""))
                    continue
                for it in r["items"][:12]:
                    when = it["published"].strftime("%b %d") if it.get("published") else ""
                    tone = it.get("score", 0.0)
                    icon = "🟢" if tone > 0 else "🔴" if tone < 0 else "⚪"
                    words = ", ".join([f"+{w}" for w in it.get("pos", [])] + [f"−{w}" for w in it.get("neg", [])])
                    link = f"[{it['title']}]({it['link']})" if it.get("link") else it["title"]
                    st.markdown(f"{icon} {link}  \n<span style='color:#999;font-size:.85em'>{when} · "
                                f"{it.get('publisher', '')} · via {it.get('via', '')}"
                                + (f" · words: {words}" if words else "") + "</span>", unsafe_allow_html=True)

    # ------------------------------------------------------------------
    def _render_fear_greed(self):
        st.markdown("### 😨😈 Crypto Fear & Greed Index")
        fg = crypto_fear_greed()
        if not fg:
            st.warning("Crypto Fear & Greed Index unavailable right now (alternative.me unreachable) — not shown.")
            explain("fear_greed")
            return
        c1, c2 = st.columns([1, 1])
        with c1:
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta", value=fg["value"],
                delta={"reference": fg["yesterday"]} if fg.get("yesterday") is not None else None,
                title={"text": f"{fg['label']}"},
                gauge={"axis": {"range": [0, 100]}, "bar": {"color": "#29b6f6"},
                       "steps": [{"range": [0, 25], "color": "#8b0000"}, {"range": [25, 45], "color": "#d32f2f"},
                                 {"range": [45, 56], "color": "#fbc02d"}, {"range": [56, 76], "color": "#7cb342"},
                                 {"range": [76, 100], "color": "#2e7d32"}]}))
            fig.update_layout(template="plotly_dark", height=300, margin=dict(l=20, r=20, t=40, b=10))
            st.plotly_chart(fig, use_container_width=True)
        with c2:
            st.metric("Today", f"{fg['value']} — {fg['label']}", help=HELP["fear_greed"])
            if fg.get("yesterday") is not None:
                st.metric("Yesterday", fg["yesterday"])
            if fg.get("week_ago") is not None:
                st.metric("A week ago", fg["week_ago"])
            v = fg["value"]
            if v >= 76:
                st.warning("Extreme greed — historically a poor time to add new money. Not a reason to sell a long-term holding by itself.")
            elif v <= 24:
                st.info("Extreme fear — panic selling here has often meant selling near a low. Stick to My Plan's rules.")
            else:
                st.caption("Mood is within the normal range — no extreme to act on.")
        st.caption(f"Source: {fg['source']} (as of {fg['as_of']}, cached 1 h). "
                   "The stock-market fear gauge (VIX) is shown in the Command Center at the top.")
        explain("fear_greed")

    # ------------------------------------------------------------------
    def get_sentiment_data(self, selected_stocks):
        """Real sentiment inputs for the Forecast Center: news tone per stock + the crypto F&G index.
        Values are None when unavailable (callers must not treat that as neutral data)."""
        fg = crypto_fear_greed()
        out = {"market": {"fear_greed_score": fg["value"] if fg else None,
                          "market_bias": (None if not fg else "Bullish" if fg["value"] > 55
                                          else "Bearish" if fg["value"] < 45 else "Neutral")}}
        for sym in selected_stocks:
            r = news_sentiment(sym)
            out[sym] = {"news_score": r.get("score") if r.get("available") else None, "news_label": r.get("label", "n/a")}
        return out
