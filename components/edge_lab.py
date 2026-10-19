"""components/edge_lab.py — the 🧪 Edge Lab page (experimental).

Six lesser-known quantitative tools, each with a plain-English explanation, today's reading and an
honest, point-in-time backtest that ends in one of three labels: ✅ edge found / ⚪ no reliable edge /
🟡 insufficient data.  NOTHING on this page feeds My Plan or the Stock Verdict.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from utils import edge_lab as el
from utils import edge_report as er
from utils import edge_stats as es
from utils import signal_hub

SYMBOLS = list(er.PEERS)

GLOSSARY = {
    "page": ("How to read this page", """
This is a **lab**, not advice. Each tool is an idea from academic research that most dashboards don't use.
For every tool we ask one strict question: **"if you had followed this signal in the past, using only what
you knew at the time, would you have done better than ignoring it?"**

* **✅ Edge found** — the effect pointed the predicted way in *both* the older 60% of history and the most
  recent 40% (the "hold-out" the rule never saw), and was unlikely to be luck (p < 0.05 overall, p < 0.10 in the hold-out).
* **⚪ No reliable edge** — we tested it and it did not beat chance. Treat its reading as background only.
* **🟡 Insufficient data** — the signal fired too few independent times to judge. Not proof it fails; just unproven.

The rules (thresholds, horizons) were **fixed before looking at results** and were not tuned, so a pass is meaningful.
"Random baseline" = the same on/off pattern slid to random dates — a signal with the same rhythm but no information.
"""),
    "lppls": ("LPPLS bubble hazard (Sornette)", """
Physicist Didier Sornette noticed that real bubbles don't just rise — they rise **faster and faster** with
**speeding-up wiggles**, like a market that is herding toward a breaking point. The *log-periodic power law
singularity* (LPPLS) model fits exactly that shape:

`ln price = A + B·(tc−t)^m + C·(tc−t)^m·cos(ω·ln(tc−t) − φ)`

`tc` is the model's "critical time" when the bubble is most likely to end. We fit the model on 9 different
look-back windows (60 to 440 days) ending today and count how many pass Sornette's quality filters.
**Bubble confidence = share of windows that see an upward bubble.** "Anti-bubble" = the mirror image, an
accelerating crash (which sometimes precedes a bounce). 0% = no bubble shape at all.
"""),
    "fragility": ("Fragility meter (critical slowing down)", """
Before ecosystems, climates and some markets **tip over**, they show "critical slowing down": shocks take
longer to fade (rising **autocorrelation**), swings get bigger (rising **variance**) and moves become more
herd-like and orderly (falling **permutation entropy**, a measure of how random the up/down pattern is).

We measure the **trend** of each over the last 6 months and blend them into one score, then rank today's
score against **every earlier day** (so 0.80 = more fragile than 80% of history). Research (PLOS One 2015,
Diks et al. 2019) found rising variance was the most consistent warning before big crashes — but with false alarms.
"""),
    "hurst": ("Trend memory (Hurst exponent, DFA)", """
Does today's direction tend to **continue** or **reverse**? The Hurst exponent (measured by *detrended
fluctuation analysis*, DFA) answers that from the last year of daily moves:

* **α ≈ 0.50** — random walk; past direction tells you nothing.
* **α > 0.55** — trends persist ("memory"); trend-following should work better.
* **α < 0.45** — moves tend to reverse.

We test: when α ≥ 0.55, did "follow the 3-month trend for 1 month" pay more than when α was lower?
"""),
    "tails": ("Crash odds (extreme-value theory) & crash-together asymmetry", """
Normal "bell-curve" risk models badly underestimate big drops. **Extreme-value theory** fits a special
curve (the *Generalised Pareto Distribution*) only to the worst days, so it can estimate the odds of moves
bigger than any in the sample.

*Test:* each month, using only the past 3 years, we set the "1-in-100-days" loss and count how often the
next days broke it. A good model breaks it ~1% of the time (Kupiec test). We compare with a bell curve.

**Crash-together asymmetry** (a copula idea): when Bitcoin has one of its worst 10% days, how often is
RIOT also in its worst 10%? And the same for the best days. If RIOT **crashes with Bitcoin more than it
rallies with it**, holding it as a "Bitcoin proxy" is a bad deal.
"""),
    "halving": ("Halving clock (cycle phase-folding)", """
Every ~4 years the Bitcoin reward per block halves. We "fold" history: take today's **number of days
since the last halving** and look at what happened after the **same day count** in every earlier cycle.
It is the simplest cycle model there is — but there have only been **3 complete cycles**, so no
statistical test can confirm it yet.
"""),
    "kelly": ("Tail-aware Kelly sizer", """
The **Kelly criterion** finds the share of your money in one bet that grows wealth fastest over time.
Bet more than Kelly and big losses compound against you; bet much more and ruin becomes likely.
Most people use a bell-curve formula; we use RIOT's **actual monthly returns** (with all their fat tails)
from the last 3 years. Cautious investors use **half-Kelly** (half the growth-optimal amount) because
the estimate itself is noisy.

*Test:* each month, recompute half-Kelly from the previous 36 months only, hold that for a month, and
compare with simply holding ~80% (your current concentration), a 40% cap, and 100%.
"""),
}


def _explain(key, expanded=False):
    t, b = GLOSSARY[key]
    with st.expander(f"ℹ️ What is this? — {t}", expanded=expanded):
        st.markdown(b)


BADGE = {es.EDGE: "✅ Edge found", es.NO_EDGE: "⚪ No reliable edge", es.INSUFFICIENT: "🟡 Insufficient data"}


def _badge(v):
    return BADGE.get(v, "🟡 Insufficient data")


def _pct(x, nd=1, signed=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "N/A"
    return f"{x*100:+.{nd}f}%" if signed else f"{x*100:.{nd}f}%"


def _lr(x):  # log return → simple %
    return None if x is None else float(np.exp(x) - 1)


def _p(x):
    return "N/A" if x is None else (f"{x:.3f}" if x >= 0.001 else "<0.001")


# ── data ──────────────────────────────────────────────────────────────
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _build_cached(symbol: str) -> dict:
    s = signal_hub.get_ohlcv(symbol, "max")
    b = signal_hub.get_ohlcv("BTC-USD", "max")
    if s.empty or b.empty:
        raise RuntimeError("price download failed")  # raising = not cached; retried next run
    return er.build(symbol, s["Close"], b["Close"])


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _peers_cached(symbols: tuple) -> pd.DataFrame:
    prices = {}
    for sym in symbols:
        h = signal_hub.get_ohlcv(sym, "max")
        if not h.empty:
            prices[sym] = el.clean(h["Close"], sym)
    if not prices:
        raise RuntimeError("no peer data")
    return er.peer_check(prices)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _closes(symbol: str) -> pd.Series:
    h = signal_hub.get_ohlcv(symbol, "max")
    if h.empty:
        raise RuntimeError("no data")
    return el.clean(h["Close"], symbol)


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None


# ── shared backtest box ───────────────────────────────────────────────
def _bt_box(r: es.EdgeResult, kind: str, title: str = "Backtest"):
    if r is None:
        st.info("Backtest: N/A")
        return
    fmt = (lambda x: _pct(_lr(x))) if kind == "ret" else (lambda x: _pct(x))
    st.markdown(f"**{title}: {_badge(r.verdict)}** — *{r.hypothesis}*")
    c = st.columns(4)
    c[0].metric("When signal ON", fmt(r.mean_on), help=f"Average {r.outcome} after the signal was on.")
    c[1].metric("When OFF", fmt(r.mean_off), help=f"Average {r.outcome} the rest of the time.")
    c[2].metric("All days (buy & hold)", fmt(r.baseline), help="Average over every sampled day — the do-nothing baseline.")
    c[3].metric("Chance it's luck (p)", _p(r.p_full),
                help="Share of 2,000 random baselines (same on/off rhythm slid to random dates) that looked at least "
                     "this different. Below 0.05 = unlikely to be luck.")
    band = r.null_band
    st.caption(
        f"Tested {r.start} → {r.end} · {r.n_samples} weekly samples · signal on {r.n_on} times ≈ **{r.eff_on:.1f} "
        f"independent episodes** (need ≥{es.MIN_EFF:.0f}; ≥{es.MIN_EFF_OOS:.0f} in the hold-out, had {r.eff_on_oos:.1f}). "
        f"Older 60% effect {('N/A' if r.effect_is is None else f'{r.effect_is*100:+.1f} pts')}, "
        f"hold-out since {r.split_date or 'N/A'} {('N/A' if r.effect_oos is None else f'{r.effect_oos*100:+.1f} pts')} "
        f"(p {_p(r.p_oos)}). Random baseline 5–95%: "
        f"{'N/A' if not band else f'{band[0]*100:+.1f} to {band[1]*100:+.1f} pts'}."
    )


# ── sections ──────────────────────────────────────────────────────────
def _lppls(rep, symbol):
    _explain("lppls")
    for key, name, H in (("lppls", symbol, er.H_STOCK), ("lppls_btc", "Bitcoin", er.H_BTC)):
        L = rep.get(key, {})
        st.markdown(f"#### {name}")
        if not L.get("available"):
            st.info("N/A — not enough price history.")
            continue
        (pos, d), (neg, _) = L["now_pos"], L["now_neg"]
        c = st.columns(2)
        c[0].metric("Bubble confidence today", _pct(pos, 0, False),
                    help="Share of the 9 look-back windows whose best LPPLS fit passes the filters as an UPWARD "
                         f"bubble. Alert level used in the test: ≥{el.LPPLS_ON:.0%}. As of {d}.")
        c[1].metric("Anti-bubble (crash pattern) today", _pct(neg, 0, False),
                    help="Share of windows that see an accelerating DOWNWARD pattern.")
        ser = L["series"].dropna()
        if len(ser):
            px = rep["_px"][name] if "_px" in rep and name in rep["_px"] else None
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            fig.add_bar(x=ser.index, y=ser["pos"], name="Bubble confidence", marker_color="rgba(239,68,68,0.6)")
            fig.add_bar(x=ser.index, y=-ser["neg"], name="Anti-bubble (shown below 0)", marker_color="rgba(34,197,94,0.6)")
            if px is not None:
                fig.add_scatter(x=px.index, y=px.values, name=f"{name} price (log)", secondary_y=True,
                                line=dict(color="#94a3b8", width=1))
                fig.update_yaxes(type="log", secondary_y=True)
            fig.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10), barmode="overlay",
                              legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig, width="stretch", key=f"edge_lppls_{key}")
        _bt_box(L["bt_ret"], "ret", "Backtest — bubble → worse next 3 months?")
        with st.expander("More tests: bubble → deeper drop · anti-bubble → bounce"):
            _bt_box(L["bt_dd"], "dd", "Bubble → deeper drop")
            _bt_box(L["bt_anti"], "ret", "Anti-bubble → bounce")


def _fragility(rep, symbol):
    _explain("fragility")
    for key, name in (("fragility", symbol), ("fragility_btc", "Bitcoin")):
        F = rep.get(key, {})
        st.markdown(f"#### {name}")
        if not F.get("available"):
            st.info("N/A — needs about 2.5 years of history.")
            continue
        rank, d = F["now_rank"]
        now = F["now"] or {}
        c = st.columns(4)
        c[0].metric("Fragility rank today", "N/A" if rank is None else f"{rank:.2f}",
                    help=f"0 = calmest ever seen so far, 1 = most fragile. Alert level in the test: ≥{el.FRAGILITY_ON}. As of {d}.")
        c[1].metric("Variance trend (τ)", f"{now.get('tau_var', np.nan):+.2f}",
                    help="Kendall τ of the 6-month variance over the last 6 months: +1 = swings growing every day, −1 = shrinking.")
        c[2].metric("Autocorrelation trend (τ)", f"{now.get('tau_ac1', np.nan):+.2f}",
                    help="Rising = shocks are taking longer to fade (critical slowing down).")
        c[3].metric("Entropy trend (τ)", f"{now.get('tau_pe', np.nan):+.2f}",
                    help="Falling permutation entropy = moves becoming more orderly/herd-like (a warning).")
        fr = F["frame"]["rank"].dropna()
        fig = go.Figure()
        fig.add_scatter(x=fr.index, y=fr.values, name="Fragility rank", line=dict(color="#f59e0b"))
        fig.add_hline(y=el.FRAGILITY_ON, line_dash="dash", line_color="#ef4444", annotation_text="alert level")
        fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=[0, 1]))
        st.plotly_chart(fig, width="stretch", key=f"edge_frag_{key}")
        _bt_box(F["bt_dd"], "dd", "Backtest — top-20% fragility → deeper drop within 3 months?")
        with st.expander("More: fragility → worse 3-month return"):
            _bt_box(F["bt_ret"], "ret", "Fragility → worse return")


def _hurst(rep, symbol):
    _explain("hurst")
    Hh = rep.get("hurst", {})
    if not Hh.get("available"):
        st.info("N/A — not enough history.")
        return
    a, d = Hh["now"]
    regime = "N/A" if a is None else ("trends persisting" if a >= el.HURST_ON else
                                      "tends to reverse" if a < 0.45 else "close to random")
    c = st.columns(3)
    c[0].metric(f"{symbol} trend memory α", "N/A" if a is None else f"{a:.2f}",
                help=f"DFA exponent of the last 252 daily returns. As of {d}.")
    c[1].metric("Reading", regime)
    c[2].metric("Long-run average α", f"{Hh['long_run']:.2f}", help="Average of every rolling reading since 2017.")
    s = Hh["series"].dropna()
    fig = go.Figure()
    fig.add_scatter(x=s.index, y=s.values, name="α", line=dict(color="#6366f1"))
    fig.add_hline(y=0.5, line_dash="dot", annotation_text="random walk")
    fig.add_hline(y=el.HURST_ON, line_dash="dash", line_color="#22c55e", annotation_text="trend memory")
    fig.update_layout(height=250, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, width="stretch", key="edge_hurst")
    _bt_box(Hh["bt"], "ret", "Backtest — does trend-following pay more when α ≥ 0.55?")


def _tails(rep, symbol):
    _explain("tails")
    T = rep.get("tails", {})
    if not T.get("available"):
        st.info("N/A — not enough history.")
        return
    cr = T.get("crash") or {}
    c = st.columns(3)
    c[0].metric("Bad-day loss (1 day in 100)", _pct(T.get("var99_now"), 1, False),
                help=f"Extreme-value estimate from the last 3 years: on about 1 trading day in 100, {symbol} "
                     "falls at least this much.")
    c[1].metric("Odds of a ≥30% fall within a month", _pct(cr.get("gpd"), 1, False),
                help="Extreme-value fit to the worst 20% of 21-day moves over the last 3 years. Overlapping "
                     "windows, so treat it as a rough base rate.")
    c[2].metric("…plain count from the last 3 years", _pct(cr.get("empirical"), 1, False),
                help="Share of all 21-day windows in the last 3 years that fell ≥30%.")
    for lbl, bt, v in ((symbol, T.get("var_bt"), T.get("var_verdict")), ("Bitcoin", T.get("var_bt_btc"), T.get("var_verdict_btc"))):
        if bt:
            st.markdown(f"**Risk-model test ({lbl}): {_badge(v)}** — over {bt['days']:,} out-of-sample days the "
                        f"1-in-100 loss was expected to be broken **{bt['expected']:.0f}** times. Extreme-value model: "
                        f"**{bt['gpd_breaches']}** (Kupiec p {_p(bt['gpd_p'])}); bell curve: **{bt['normal_breaches']}** "
                        f"(p {_p(bt['normal_p'])}). p ≥ 0.05 = calibrated.")
        else:
            st.markdown(f"**Risk-model test ({lbl}):** 🟡 Insufficient data")
    st.caption("'Edge found' here means the fat-tail model is calibrated where a bell curve is not — a better "
               "**risk** estimate, not a buy/sell signal. If both are calibrated the fat-tail model adds nothing.")
    tl = T.get("tail")
    st.markdown("#### Does it crash with Bitcoin more than it rallies with it?")
    if not tl:
        st.info("N/A")
        return
    fig = go.Figure()
    for nm, dct in (("Since " + tl["start"][:4], tl["full"]), ("Last 3 years", tl["recent"])):
        fig.add_bar(x=["Crash together (worst 10% days)", "Rally together (best 10% days)"],
                    y=[dct["lower"], dct["upper"]], name=nm)
    fig.add_hline(y=0.1, line_dash="dot", annotation_text="no link (10%)")
    fig.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(tickformat=".0%"))
    st.plotly_chart(fig, width="stretch", key="edge_tail")
    f, r = tl["full"], tl["recent"]
    st.markdown(
        f"On Bitcoin's worst 10% of days, {symbol} was also in its worst 10% **{f['lower']:.0%}** of the time; on "
        f"Bitcoin's best days it was in its best 10% **{f['upper']:.0%}** of the time (difference "
        f"{f['asym']*100:+.0f} pts, 90% range {f['ci'][0]*100:+.0f} to {f['ci'][1]*100:+.0f}). Last 3 years: "
        f"{r['lower']:.0%} vs {r['upper']:.0%} ({r['asym']*100:+.0f} pts, range {r['ci'][0]*100:+.0f} to {r['ci'][1]*100:+.0f}). "
        f"First vs second half of history: {tl['halves'][0]*100:+.0f} / {tl['halves'][1]*100:+.0f} pts.")
    st.markdown(f"**Pattern test: {_badge(tl['verdict'])}** — counts only if the full-history range excludes zero "
                "AND both halves point the same way. Negative = it rallies with Bitcoin more than it crashes with it.")


def _halving(rep, symbol):
    _explain("halving")
    Hv = rep.get("halving", {})
    if not Hv.get("available"):
        st.info("N/A")
        return
    ph = Hv["phase"]
    c = st.columns(3)
    c[0].metric("Days since the April 2024 halving", f"{ph['days']:,}",
                help=f"Last halving {ph['halving']}; next expected around {ph['next']} (estimate).")
    c[1].metric("Share of this cycle elapsed", _pct(ph["cycle_frac"], 0, False))
    c[2].metric("Bitcoin vs this cycle's high", _pct(Hv.get("btc_below_high_now")))
    rows = []
    for lbl, fold in (("Bitcoin", Hv["btc_fold"]), (symbol, Hv["stock_fold"])):
        for r in fold:
            rows.append({"Asset": lbl, "Cycle (halving)": str(r["halving"]), "Same day in that cycle": str(r["start"]),
                         "Below its cycle high then": _pct(r.get("below_cycle_high"), 0),
                         "Next 3 months": _pct(r.get(91), 0), "Next 6 months": _pct(r.get(182), 0),
                         "Next 12 months": _pct(r.get(365), 0)})
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if symbol == "RIOT":
        st.caption("RIOT only has 2 earlier cycles as a miner (it was a biotech before Oct 2017).")
    bt = Hv.get("bt") or {}
    if bt.get("n"):
        st.markdown(f"**Backtest: {_badge(bt['verdict'])}** — predicting the sign of Bitcoin's next 6 months from the "
                    f"earlier cycles at the same phase was right **{bt['hit']:.0%}** of the time ({bt['start']} → {bt['end']}, "
                    f"{bt['n']} monthly checks ≈ {bt['eff']:.0f} independent periods) vs **{bt['always_up']:.0%}** for "
                    f"'always up'. But it never had more than **{bt['cycles_used_max']} earlier cycles** to learn from; "
                    "we require at least 4 before calling it an edge.")
    st.caption("Context only. A pattern seen 3 times can break the 4th time — especially now that ETFs and "
               "companies hold a large share of Bitcoin.")


def _kelly(rep, symbol):
    _explain("kelly")
    K = rep.get("kelly", {})
    if not K.get("available"):
        st.info("N/A — needs about 5 years of monthly history.")
        return
    c = st.columns(2)
    c[0].metric("Growth-optimal weight (full Kelly)", _pct(K["full_now"], 0, False),
                help=f"From {symbol}'s last 36 monthly returns vs cash at {K['cash_annual']:.0%}/yr. "
                     "Capped at 100% (no borrowing). Very noisy.")
    c[1].metric("Half-Kelly (cautious)", _pct(K["half_now"], 0, False),
                help="What a risk-averse Kelly user would hold, as a share of the money you have in this stock + cash.")
    wf = K["wf"]
    st_ = wf["stats"]
    tbl = pd.DataFrame([{"Strategy": n, "Yearly growth (CAGR)": _pct(st_[k]["cagr"], 0),
                         "Worst fall": _pct(st_[k]["maxdd"], 0), "$1 became": f"${st_[k]['final']:.2f}"}
                        for k, n in (("kelly", "Half-Kelly, re-set monthly"), ("static_80", "Hold 80% (about your RIOT share)"),
                                     ("static_40", "Hold 40% (My Plan cap)"), ("static_100", "Hold 100%"))])
    st.dataframe(tbl, hide_index=True, width="stretch")
    fig = go.Figure()
    for k, n in (("kelly", "Half-Kelly"), ("static_80", "80%"), ("static_40", "40%"), ("static_100", "100%")):
        eq = (1 + wf[k]).cumprod()
        fig.add_scatter(x=eq.index, y=eq.values, name=n)
    fig.update_layout(height=280, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(type="log", title="$1 grows to"))
    st.plotly_chart(fig, width="stretch", key="edge_kelly")
    v = K["verdict"]
    if v.get("months"):
        st.markdown(f"**Backtest: {_badge(v['verdict'])}** — over {v['months']} months, re-setting to half-Kelly changed "
                    f"growth by **{v.get('growth_diff_pa', 0)*100:+.0f} pts/yr** vs holding 80% (bootstrap support "
                    f"{v.get('support', 0):.0%}; first/second half {v['halves_pa'][0]*100:+.0f} / {v['halves_pa'][1]*100:+.0f} "
                    f"pts/yr; worst fall {'smaller' if v.get('dd_better') else 'not smaller'}).")
    st.caption("Kelly says how much a bet is worth *if the past repeats*. It does not time the market.")


def render():
    st.subheader("🧪 Edge Lab — experimental")
    st.warning("**Experimental research tools.** Nothing here changes My Plan or the Stock Verdict. Each tool shows "
               "its own honest backtest; most ideas — even famous ones — fail that test. Not financial advice.")
    _explain("page")
    if "edge_symbol_saved" not in st.session_state:
        st.session_state["edge_symbol_saved"] = "RIOT"
    if "edge_symbol" not in st.session_state:
        st.session_state["edge_symbol"] = st.session_state["edge_symbol_saved"]
    symbol = st.selectbox("Stock", SYMBOLS, key="edge_symbol",
                          help="Bitcoin is always analysed alongside. Miner history starts when each company began mining.")
    st.session_state["edge_symbol_saved"] = symbol
    with st.spinner(f"Running the lab for {symbol} (first run ≈ 10–20 s, then cached 6 h)…"):
        rep = _safe(_build_cached, symbol)
    if not rep:
        st.error("Price data is unavailable right now (Yahoo Finance). Try again in a few minutes.")
        return
    rep["_px"] = {symbol: _safe(_closes, symbol), "Bitcoin": _safe(_closes, "BTC-USD")}

    st.markdown(f"#### Scorecard — {symbol} (data from {rep['stock_start']} to {rep['as_of']})")
    sc = er.scorecard(rep)
    sc["Backtest result"] = sc["Backtest result"].map(_badge)
    st.dataframe(sc, hide_index=True, width="stretch",
                 column_config={"What was tested": st.column_config.TextColumn(help="The rule, fixed in advance."),
                                "Backtest result": st.column_config.TextColumn(help="✅ edge found / ⚪ no reliable edge / 🟡 insufficient data")})
    n_edge = (er.scorecard(rep)["Backtest result"] == es.EDGE).sum()
    if n_edge == 0:
        st.info(f"**Bottom line for {symbol}:** none of these tools showed a reliable buy/sell edge on its own history. "
                "Their readings are shown as context, not signals.")
    else:
        st.info(f"**Bottom line:** {n_edge} test(s) passed. Read what each one passed — a better *risk estimate* is not a "
                "buy/sell signal. Nothing here is wired into My Plan.")

    tabs = st.tabs(["🫧 Bubble hazard", "🧊 Fragility", "🧠 Trend memory", "🌋 Crash odds", "⏳ Halving clock",
                    "⚖️ Kelly sizing", "🔁 Robustness"])
    with tabs[0]:
        _lppls(rep, symbol)
    with tabs[1]:
        _fragility(rep, symbol)
    with tabs[2]:
        _hurst(rep, symbol)
    with tabs[3]:
        _tails(rep, symbol)
    with tabs[4]:
        _halving(rep, symbol)
    with tabs[5]:
        _kelly(rep, symbol)
    with tabs[6]:
        st.markdown("Would the same fixed rules have worked on the **other** miners? An idea that only works on one "
                    "stock is probably luck.")
        if st.checkbox("Run the check on all four miners (≈10 s)", key="edge_peers"):
            pc = _safe(_peers_cached, tuple(SYMBOLS))
            if pc is None or pc.empty:
                st.info("N/A — peer data unavailable.")
            else:
                show = pc.copy()
                show["verdict"] = show["verdict"].map(_badge)
                show["effect"] = show["effect"].map(lambda x: "N/A" if x is None or pd.isna(x) else f"{x*100:+.1f} pts")
                show["p"] = show["p"].map(lambda x: "N/A" if x is None or pd.isna(x) else _p(x))
                show["right_way"] = show["right_way"].map({True: "yes", False: "no"}).fillna("N/A")
                show["independent_on"] = show["independent_on"].map(lambda x: f"{x:.1f}")
                st.dataframe(show.rename(columns={"right_way": "Pointed the predicted way?",
                                                  "independent_on": "Independent ON episodes"}),
                             hide_index=True, width="stretch")
    with st.expander("🔬 Method & honesty notes"):
        st.markdown(f"""
* **No look-ahead:** every reading on a date uses prices up to that date only (unit-tested by re-running on
  truncated history and checking earlier readings don't change).
* **Outcomes** are the next 3 months (63 trading days; 91 calendar days for Bitcoin). Samples weekly.
* **Significance:** circular-shift permutation (2,000 random baselines) — keeps clustering, so overlapping
  3-month windows can't fake a result. **Hold-out:** last 40% of each history.
* **Rules fixed in advance:** LPPLS ≥{el.LPPLS_ON:.0%} of windows; fragility rank ≥{el.FRAGILITY_ON}; Hurst α ≥{el.HURST_ON};
  1-in-100-day risk; 30% monthly fall; half-Kelly from 36 months; halving test needs ≥4 earlier cycles.
* **History:** RIOT from 2017-10-04 (it was the biotech Bioptix before), MARA from Nov 2017, CLSK from Dec 2020.
* Free Yahoo Finance daily prices only; no keys.
""")
