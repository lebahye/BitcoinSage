"""
components/riot_correlation_map.py — the ONE place for correlation in the app.

Replaces three older, overlapping panels (Market Overview heatmap, Risk Center
correlation tab, Sentiment tab crypto-correlation box — the last one was
always empty because of the BTC date-alignment bug).
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.explain import explain, HELP
from utils.riot_correlation import load_riot_correlations

_GROUP_COLORS = {
    "Miners": "#f7931e", "AI data centers": "#7c4dff", "Bitcoin": "#ffd600",
    "Risk appetite": "#26c6da", "Macro": "#9e9e9e",
}


@st.cache_data(ttl=3600, show_spinner=False)
def _cached():
    return load_riot_correlations()


def _fmt(x):
    return "n/a" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:+.2f}"


class RiotCorrelationMap:
    def render(self, selected_stocks=None):
        st.header("🔗 RIOT Correlation Map")
        st.caption("What actually moves with your RIOT shares — miners, AI data-center stocks, Bitcoin, "
                   "or the broader market — and what tends to move the opposite way.")
        explain("riot_corr_map")

        with st.spinner("Downloading 1 year of daily prices for ~27 tickers…"):
            d = _cached()
        if not d.get("ok"):
            st.error(f"Correlation map unavailable: {d.get('error')} Try 🔄 Refresh Data in a minute.")
            return
        table, groups = d["table"], d["groups"]

        # ── Headline ─────────────────────────────────────────────────────
        def gavg(name, col="avg_corr_1y"):
            return float(groups.loc[name, col]) if name in groups.index else None

        miners, ai, btc = gavg("Miners"), gavg("AI data centers"), d["btc_corr_1y"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Avg vs other miners (1Y)", _fmt(miners), help=HELP["correlation"])
        c2.metric("Avg vs AI data centers (1Y)", _fmt(ai), help=HELP["correlation"])
        c3.metric("vs Bitcoin (1Y)", _fmt(btc),
                  delta=None if d["btc_corr_3m"] is None else f"3M: {d['btc_corr_3m']:+.2f}", delta_color="off",
                  help=HELP["correlation"])
        vix = table[table.ticker == "^VIX"]
        c4.metric("vs VIX fear gauge (1Y)", _fmt(float(vix.corr_1y.iloc[0])) if not vix.empty else "n/a",
                  help=HELP["vix"])

        if None not in (miners, ai, btc):
            if max(miners, ai) > btc + 0.1:
                st.info(f"**Plain English:** RIOT currently trades more like a **miner / AI-infrastructure stock** "
                        f"(miners {miners:.2f}, AI data centers {ai:.2f}) than like **Bitcoin itself** ({btc:.2f}). "
                        "Owning other miners does **not** diversify you — they fall together.")
            else:
                st.info(f"**Plain English:** RIOT is still mostly a **Bitcoin proxy** (Bitcoin {btc:.2f} vs "
                        f"miners {miners:.2f}, AI {ai:.2f}).")

        # ── Divergence alert ─────────────────────────────────────────────
        div = d.get("divergence")
        if div:
            msg = (f"Last {div['lookback']} trading days — RIOT **{div['riot_move']*100:+.1f}%** vs its closest peers "
                   f"({', '.join(div['peers'])}) **{div['peer_move']*100:+.1f}%**. Correlation with peers: "
                   f"{div['corr_recent']:.2f} recently vs {div['corr_year']:.2f} over the year.")
            (st.warning if div["diverging"] else st.success)(
                ("⚠️ **RIOT is moving apart from its peers.** " if div["diverging"] else "✅ **RIOT is moving with its peers.** ") + msg)
            explain("decoupling")

        tab1, tab2, tab3, tab4 = st.tabs(["🏆 Ranked list", "📊 Group comparison", "🔻 Inverse / hedges", "📋 Full table"])

        with tab1:
            top = table[table["corr_1y"] > 0].head(15).iloc[::-1]
            fig = go.Figure()
            fig.add_trace(go.Bar(y=top["ticker"], x=top["corr_1y"], orientation="h", name="1 year",
                                 marker_color=[_GROUP_COLORS.get(g, "#888") for g in top["group"]],
                                 text=[f"{v:.2f}" for v in top["corr_1y"]], textposition="outside",
                                 hovertext=top["description"]))
            fig.add_trace(go.Scatter(y=top["ticker"], x=top["corr_3m"], mode="markers", name="last 3 months",
                                     marker=dict(symbol="diamond", size=10, color="white")))
            fig.update_layout(template="plotly_dark", height=520, xaxis=dict(range=[0, 1.05], title="Correlation with RIOT"),
                              margin=dict(l=10, r=10, t=30, b=10), legend=dict(orientation="h"))
            st.plotly_chart(fig, use_container_width=True)
            st.caption("Bar colour = group (orange miners · purple AI data centers · yellow Bitcoin · teal broad market). "
                       "White diamond = last 3 months. In sell-offs correlations usually rise, so a higher 3-month "
                       "number is common and not by itself a warning.")

        with tab2:
            g = groups.reset_index()
            fig = go.Figure()
            fig.add_trace(go.Bar(x=g["group"], y=g["avg_corr_1y"], name="1 year",
                                 marker_color=[_GROUP_COLORS.get(x, "#888") for x in g["group"]]))
            fig.add_trace(go.Bar(x=g["group"], y=g["avg_corr_3m"], name="3 months", marker_color="rgba(255,255,255,.35)"))
            fig.update_layout(template="plotly_dark", height=380, barmode="group", yaxis_title="Average correlation with RIOT")
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(g.rename(columns={"group": "Group", "avg_corr_1y": "Avg 1Y", "avg_corr_3m": "Avg 3M",
                                           "n": "# tickers"}).round(2), hide_index=True, use_container_width=True)

        with tab3:
            st.markdown("These move **opposite** to RIOT (or are close to zero). A *steady* negative link is a "
                        "potential hedge; one that *flips* sign isn't reliable.")
            inv = d["inverse"].copy()
            if inv.empty:
                st.warning("Macro data (VIX, dollar, oil, bonds) unavailable right now.")
            else:
                for _, row in inv.sort_values("corr_1y").iterrows():
                    badge = "🟢 steady" if row["stability"] == "steady" else "🟠 flips"
                    qs = ", ".join(f"{q:+.2f}" for q in row["quarterly"])
                    direction = ("moves opposite to RIOT" if row["corr_1y"] < -0.15 else
                                 "moves with RIOT" if row["corr_1y"] > 0.15 else "roughly unrelated")
                    st.markdown(f"**{row['ticker']}** — {row['description']}: **{row['corr_1y']:+.2f}** (1Y), "
                                f"{row['corr_3m']:+.2f} (3M) · {badge} · {direction}  \n"
                                f"<span style='color:#999;font-size:.85rem'>Each quarter of the year: {qs}</span>",
                                unsafe_allow_html=True)
                tlt = inv[inv.ticker == "TLT"]
                if not tlt.empty and tlt.corr_1y.iloc[0] > 0:
                    st.caption("Note: long-term Treasury bonds (TLT) have *not* acted as a hedge for RIOT over the past year "
                               "— their correlation is positive.")
            explain("vix")

        with tab4:
            show = table.copy()
            show["quarterly"] = show["quarterly"].apply(lambda q: ", ".join(f"{x:+.2f}" for x in q))
            show = show[["ticker", "group", "description", "corr_1y", "corr_3m", "change", "riot_beta_to_it",
                         "stability", "quarterly", "n_days"]]
            show.columns = ["Ticker", "Group", "What it is", "Corr 1Y", "Corr 3M", "3M − 1Y", "RIOT beta to it",
                            "Stability", "Quarterly corr", "Days"]
            st.dataframe(show.round(2), hide_index=True, use_container_width=True)
            st.download_button("⬇️ Download CSV", show.to_csv(index=False).encode(), "riot_correlations.csv", "text/csv")

        st.caption(f"Source: Yahoo Finance daily closes (auto-adjusted), 1 year to {d['last_date']}; log returns on RIOT "
                   f"trading days, Bitcoin weekend moves rolled into Monday. Computed {d['fetched_at']} (cached 1 h). "
                   + (f"No data for: {', '.join(d['missing'])}. " if d["missing"] else "")
                   + "Correlation describes the past; it doesn't predict the future.")
