"""components/trim_rebuy.py — the ♻️ Trim & Rebuy page.

Question: "If I sell part of a stock when it looks stretched and buy it back cheaper, do I end up with MORE SHARES
than if I had just held — after New York + federal tax and trading costs?"  Every rule is pre-registered, backtested
point-in-time with an in-sample / hold-out split and a random-date baseline (utils/trim_rebuy.py), and taxed with
utils/tax_ny.py.  NOTHING on this page feeds My Plan or the Stock Verdict.  Not tax advice.
"""
from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils import signal_hub
from utils import tax_ny as tx
from utils import trim_rebuy as tr

YEARS = 10                      # backtest window (most recent N years of daily closes)
EXTRA_PEERS = ("HUT", "CORZ", "BTDR")
DEFAULT_SHARES = 1_000

TIPS = {
    "share_eq": "After-tax share-equivalents: what you'd have after ALL taxes if you sold everything on the last "
                "day, divided by that day's price — for the rule and for just holding. Counting the tax that holding "
                "still owes on its gain keeps the comparison fair. Taxes along the way are paid from outside cash.",
    "liq": "Harsher view: each year's tax is paid by selling shares at that year-end's price (refunds buy shares), "
           "and the hold side's unrealised tax is ignored. Shows how much paying tax early can cost a long-term holder.",
    "hit": "Share of round trips where you bought back MORE shares than you sold.",
    "p": "How often the SAME number of trims, of the same lengths, placed on RANDOM dates did at least as well. "
         "Small = the rule's timing beats luck. Below 0.05 (full) and 0.10 (hold-out) is required.",
    "is_oos": "The rule was checked on the first 60% of history (in-sample) and, separately, on the last 40% it "
              "was never tuned on (hold-out). An edge must be positive in BOTH.",
    "wash": "Wash sale: if you sell at a loss and buy the same stock within 30 days before or after, the IRS "
            "disallows the loss for now; it's added to the new shares' cost instead (IRS Pub. 550).",
    "st_lt": "Held 1 year or less = short-term (taxed like wages). More than 1 year = long-term (lower federal rate). "
             "Selling and rebuying RESTARTS the clock for the rebought shares.",
    "fifo": "Which shares count as sold. FIFO (first in, first out) is Schwab's default; 'specific ID' lets you pick "
            "the highest-cost shares to sell first (less tax). You must pick lots at Schwab before the trade settles.",
}


# ── data (cached; failures raise so they are not cached) ─────────────
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _ohlcv(symbol: str) -> pd.DataFrame:
    h = signal_hub.get_ohlcv(symbol, "max")
    if h is None or h.empty or len(h) < 260:
        raise RuntimeError("no data")
    h = h[h.index >= h.index[-1] - pd.Timedelta(days=365 * YEARS)]
    return h.dropna(subset=["Close"])


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _earnings_cached(symbol: str) -> list:
    import yfinance as yf
    e = yf.Ticker(symbol).get_earnings_dates(limit=40)
    if e is None or e.empty:
        raise RuntimeError("no earnings dates")
    return [pd.Timestamp(x) for x in e.index]


def _earnings(symbol: str) -> list:
    try:
        return _earnings_cached(symbol)
    except Exception:
        return []


def _safe_ohlcv(symbol: str):
    try:
        return _ohlcv(symbol)
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _evaluate(symbol: str, status: str, other: float, nyc: bool, method: str, cost: float, shares: float) -> dict:
    df = _ohlcv(symbol)
    prof = tx.TaxProfile(status, other, nyc, "taxable")
    earn = _earnings(symbol)
    out = {}
    for r in tr.RULES:
        res = tr.evaluate_rule(r, df, prof, method, earn, shares0=shares, cost=cost)
        out[r.key] = _slim(res)
    out["_earn_n"] = len(earn)
    return out


def _slim(res: dict) -> dict:
    """Keep only plain data (cache-friendly)."""
    o = {"verdict": res["verdict"], "stats": res["stats"]}
    for w in ("full", "in_sample", "hold_out"):
        x = res[w]
        o[w] = {"n": x["n_trips"], "p": x["p_random"], "rand_med": x["random_median"], "trips": x["trips"],
                "pre": {k: x["pre"][k] for k in ("share_gain_pct", "share_gain", "liq_gain_pct")},
                "post": {k: x["post"][k] for k in ("share_gain_pct", "share_gain", "liq_gain_pct", "tax_paid",
                                                   "disallowed", "taxes", "taxpaid_shares_pct")}}
    o["log"] = res["full"]["post"]["log"]
    return o


def _holdings():
    try:
        from components.holding_plan import _load_user_data
        pos, _ = _load_user_data()
    except Exception:
        pos = {}
    from utils.tickers import resolve
    return {resolve(k): v for k, v in pos.items() if (v or {}).get("shares", 0) > 0}


def _choices(held: dict) -> list:
    try:
        from components.edge_lab import stock_choices
        more = stock_choices()
    except Exception:
        more = []
    return list(dict.fromkeys(sorted(held, key=lambda t: -held[t]["shares"]) + more))


def _pct(x, nd=1, sign=True):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "N/A"
    return f"{x*100:+.{nd}f}%" if sign else f"{x*100:.{nd}f}%"


def _usd(x, nd=0):
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "N/A"
    return f"-${-x:,.{nd}f}" if x < 0 else f"${x:,.{nd}f}"


BADGE = {tr.EDGE: "✅ edge found", tr.NO_EDGE: "⚪ no reliable edge", tr.INSUFFICIENT: "🟡 insufficient data"}


# ── page ──────────────────────────────────────────────────────────────
def render():
    st.header("♻️ Trim & Rebuy")
    st.caption("Can selling part of a stock and buying it back cheaper leave you with **more shares** than just "
               "holding — after New York + federal tax and costs? Swing trades (days to months), not day trading. "
               "Experimental: nothing here changes 🧭 My Plan or ⚖️ Stock Verdict.")
    st.warning("**Not tax advice.** These are estimates with simplified 2026 rules. Confirm with a CPA before you "
               "trade, especially around wash sales and lot selection.", icon="⚠️")

    with st.expander("ℹ️ How to read this page", expanded=False):
        st.markdown(f"""
- **The goal:** finish with more shares than a buy-and-hold investor who started with the same shares on the same day.
- **Seven pre-set rules** (no tuning) decide when to sell 10% or 25% and when to buy it back. Every rule has a
  **maximum wait**: if the price never comes back, you buy back anyway (that is the risk — a *missed rebound*).
- **Point-in-time:** a rule only sees prices up to yesterday's close and trades at today's close.
- **Honesty checks:** {TIPS['is_oos']} {TIPS['p']}
- **Taxes:** {TIPS['st_lt']} {TIPS['wash']}
- **Two account types:** in an IRA / Roth IRA trades aren't taxed, so the *pre-tax* column is your result there.
""")

    held = _holdings()
    opts = _choices(held) or ["RIOT"]
    from components.stock_verdict import pick_following_verdict
    c1, c2 = st.columns([1, 2])
    sym = pick_following_verdict(c1, "Stock", opts, "trim_symbol", "RIOT",
                                 help="Your holdings first (largest position), then other miners. Follows the "
                                      "⚖️ Stock Verdict choice.")
    pos = held.get(sym)
    shares = float(pos["shares"]) if pos else float(DEFAULT_SHARES)
    basis = float(pos.get("cost_basis") or 0) if pos else None
    c2.markdown(f"**Your position:** {shares:,.0f} shares @ {_usd(basis, 2)} average cost" if pos else
                f"You don't hold **{sym}** — results use {DEFAULT_SHARES:,} hypothetical shares.")

    # tax settings
    with st.expander("🧾 Your tax settings (New York) — set these first", expanded=True):
        a, b, c = st.columns(3)
        status = a.selectbox("Filing status", tx.STATUSES, format_func=tx.STATUS_LABEL.get, key="trim_status",
                             help="Single is the default. Married filing jointly uses the joint brackets.")
        other = b.number_input("Other taxable income this year ($)", 0, 10_000_000, 100_000, 5_000, key="trim_income",
                               help="Wages, interest, etc. BEFORE any trading. Sets your tax bracket.")
        nyc = c.toggle("NYC resident", True, key="trim_nyc",
                       help="New York City residents pay NYC income tax (3.078%–3.876%) on top of NY State.")
        d, e, f = st.columns(3)
        method = d.radio("Which shares are sold", ["fifo", "specific"], key="trim_method", horizontal=True,
                         format_func={"fifo": "FIFO (Schwab default)", "specific": "Specific ID (highest cost)"}.get,
                         help=TIPS["fifo"])
        cost_bp = e.number_input("Slippage per trade (%)", 0.0, 1.0, 0.05, 0.01, key="trim_cost",
                                 help="Schwab charges $0 commission on online US stock trades; this covers the "
                                      "bid/ask spread and price movement while your order fills.")
        lt_now = f.checkbox("I bought these shares more than 1 year ago", True, key="trim_lt",
                            help="Used only for today's tax-loss-harvest calculator (your exact lot dates aren't "
                                 "in the app). Long-term losses offset long-term gains first.")
        st.info(f"⚠️ **Other income = {_usd(other)} is a placeholder** — change it to your real number; it drives "
                "every after-tax figure. Rates: 2026 IRS / NY DTF tables (sources below).")
    prof = tx.TaxProfile(status, float(other), bool(nyc), "taxable")
    mr = tx.marginal_rates(prof)
    st.caption(f"Your combined marginal rate on extra gains: **short-term {_pct(mr['st'], 1, False)}**, "
               f"**long-term {_pct(mr['lt'], 1, False)}** (federal + NIIT if applicable + NY State"
               f"{' + NYC' if nyc else ''}). IRA/Roth: 0% on trades.")

    df = _safe_ohlcv(sym)
    if df is None:
        st.error(f"No price history for {sym} right now (Yahoo Finance). Try again later — nothing is shown "
                 "rather than guessing.")
        return
    with st.spinner("Backtesting 7 rules × 200 random-date baselines…"):
        try:
            R = _evaluate(sym, status, float(other), bool(nyc), method, cost_bp / 100, shares)
        except Exception as ex:
            st.error(f"Backtest failed: {ex}")
            return
    cost = cost_bp / 100
    rules = [r for r in tr.RULES]
    verdicts = [R[r.key]["verdict"] for r in rules]
    overall = tr.EDGE if tr.EDGE in verdicts else (tr.INSUFFICIENT if all(v == tr.INSUFFICIENT for v in verdicts)
                                                   else tr.NO_EDGE)
    span = f"{df.index[0]:%b %Y} – {df.index[-1]:%b %Y}"
    passed = [r for r in rules if R[r.key]["verdict"] == tr.EDGE]
    if overall == tr.EDGE:
        st.success(f"### ✅ Edge found for {sym}: " + ", ".join(r.key for r in passed) +
                   f"\nThese rules ended with more shares than holding after tax, in both halves of {span}, and beat "
                   "random dates. Still: 7 rules were tested, so one passing can be luck — size small.")
    elif overall == tr.INSUFFICIENT:
        st.warning(f"### 🟡 Insufficient data for {sym}\nToo few trims happened in {span} to judge any rule.")
    else:
        st.info(f"### ⚪ No reliable edge for {sym}\nNone of the 7 rules passed every check (more shares than "
                f"holding after tax in both halves of {span}, AND better than the same trims on random dates). "
                "Some rules may show gains below, but they look like luck, not timing — holding is the simpler choice.")

    # ── summary table ─────────────────────────────────────────────
    st.subheader("Each rule vs. just holding")
    rows = []
    for r in rules:
        x = R[r.key]
        f_, i_, o_ = x["full"], x["in_sample"], x["hold_out"]
        rows.append({
            "Rule": f"{r.key} · {r.label}", "Round trips": f_["n"], "Hit rate": _pct(x["stats"]["hit"], 0, False),
            "Shares vs hold — IRA/Roth (pre-tax)": _pct(f_["pre"]["share_gain_pct"]),
            "Shares vs hold — taxable (after tax)": _pct(f_["post"]["share_gain_pct"]),
            "Taxable, tax paid from shares": _pct(f_["post"]["taxpaid_shares_pct"]),
            "In-sample (after tax)": _pct(i_["post"]["share_gain_pct"]),
            "Hold-out (after tax)": _pct(o_["post"]["share_gain_pct"]),
            "Random-date p (full / hold-out)": f"{_p(f_['p'])} / {_p(o_['p'])}",
            "Verdict": BADGE[x["verdict"]],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", column_config={
        "Round trips": st.column_config.NumberColumn(help="Sell-then-buy-back cycles over the whole period."),
        "Hit rate": st.column_config.TextColumn(help=TIPS["hit"]),
        "Shares vs hold — IRA/Roth (pre-tax)": st.column_config.TextColumn(help="No tax inside an IRA/Roth. " + TIPS["share_eq"]),
        "Shares vs hold — taxable (after tax)": st.column_config.TextColumn(help=TIPS["share_eq"]),
        "Taxable, tax paid from shares": st.column_config.TextColumn(help=TIPS["liq"]),
        "In-sample (after tax)": st.column_config.TextColumn(help=TIPS["is_oos"]),
        "Hold-out (after tax)": st.column_config.TextColumn(help=TIPS["is_oos"]),
        "Random-date p (full / hold-out)": st.column_config.TextColumn(help=TIPS["p"]),
    })
    if R["_earn_n"] == 0:
        st.caption("E1/E2: no earnings-date history from Yahoo Finance for this ticker → N/A (insufficient data).")
    st.caption(f"Backtest: {span} daily closes, {shares:,.0f} shares, start cost = first day's price (bought >1 year "
               "before, so the starting shares are long-term). 2026 tax rules applied to every year. A rule needs "
               f"≥{tr.MIN_TRIPS} trips (≥{tr.MIN_TRIPS_OOS} in hold-out) to be judged.")

    # ── one rule in detail ────────────────────────────────────────
    st.subheader("Look inside one rule")
    key = st.selectbox("Rule", [r.key for r in rules], format_func=lambda k: f"{k} · {tr.RULE_BY_KEY[k].label}",
                       key="trim_rule")
    rule = tr.RULE_BY_KEY[key]
    x = R[key]
    st.caption(rule.help)
    s_ = x["stats"]
    eq = tr.equity_paths(df["Close"], [tuple(t) for t in x["full"]["trips"]], rule.trim, shares0=shares, cost=cost)
    m = st.columns(5)
    m[0].metric("Round trips", x["full"]["n"])
    m[1].metric("Hit rate", _pct(s_["hit"], 0, False), help=TIPS["hit"])
    m[2].metric("Avg win / avg loss", f"{_pct(s_['avg_win'])} / {_pct(s_['avg_loss'])}",
                help="Average change in shares per round trip (as % of shares sold), winners vs losers.")
    m[3].metric("Days out of the market", s_["days_out"], help="Trading days the trimmed slice sat in cash.")
    dd_r = tr.max_drawdown(eq["rule_value"]) if len(eq) else None
    dd_h = tr.max_drawdown(eq["hold_value"]) if len(eq) else None
    m[4].metric("Max drawdown rule / hold", f"{_pct(dd_r, 0)} / {_pct(dd_h, 0)}",
                help="Largest peak-to-trough fall in $ value (pre-tax).")
    if s_["worst"]:
        w = s_["worst"]
        st.caption(f"**Worst miss:** sold {w['date']} at ${w['sell']:,.2f}, had to buy back at ${w['rebuy']:,.2f} "
                   f"→ {_pct(w['pct'])} shares on that slice (the stock kept running).")
    if len(eq):
        fig = go.Figure()
        fig.add_scatter(x=eq.index, y=eq["rule_shares_eq"], name=f"{key}: share-equivalents (pre-tax)")
        fig.add_scatter(x=eq.index, y=[shares] * len(eq), name="Just hold", line=dict(dash="dash"))
        fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Shares",
                          title="Share count vs. holding (cash while trimmed counted as shares at that day's price)")
        st.plotly_chart(fig, width="stretch")
    log = pd.DataFrame(x["log"])
    if log.empty:
        st.caption("No round trips for this rule in the period (N/A).")
    else:
        show = log[["Sold on", "Sell price", "Shares sold", "Rebought on", "Rebuy price", "Shares rebought",
                    "Share gain", "Days out", "Realized gain $", "Term", "Est. tax $"]]
        st.dataframe(show, hide_index=True, width="stretch", column_config={
            "Sell price": st.column_config.NumberColumn(format="$%.2f"),
            "Rebuy price": st.column_config.NumberColumn(format="$%.2f"),
            "Shares sold": st.column_config.NumberColumn(format="%.1f"),
            "Shares rebought": st.column_config.NumberColumn(format="%.1f"),
            "Share gain": st.column_config.NumberColumn(format="%+.1f", help="Shares rebought minus shares sold (pre-tax)."),
            "Realized gain $": st.column_config.NumberColumn(format="$%.0f", help="Taxable gain/loss on the sale "
                                                             "(FIFO/specific-ID basis, after any wash-sale adjustment)."),
            "Term": st.column_config.TextColumn(help=TIPS["st_lt"]),
            "Est. tax $": st.column_config.NumberColumn(format="$%.0f", help="That year's extra tax (federal + NY"
                                                        " + NYC), split across the year's trades by size of gain. "
                                                        "Negative = tax saved."),
        })
        pt = x["full"]["post"]
        st.caption(f"Total extra tax over the period: {_usd(pt['tax_paid'])}; losses disallowed by wash sales: "
                   f"{_usd(pt['disallowed'])} (added to the rebought shares' cost, not lost).")

    # ── today ─────────────────────────────────────────────────────
    st.subheader("Today")
    c = df["Close"]
    price = float(c.iloc[-1])
    if passed:
        for r in passed:
            z = tr.zones_today(r, df)
            if z:
                st.success(f"**{r.key}** (passed): trim zone **≥ ${z['trim_at']:,.2f}**, buy-back zone "
                           f"**≤ ${z['rebuy_at']:,.2f}** ({z['basis']}). Price now ${price:,.2f}.")
            else:
                st.success(f"**{r.key}** (passed): earnings-based — see 📅 dates in ⚖️ Stock Verdict.")
    else:
        sma50, sma200 = c.rolling(50).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
        rs = tr.rsi(c).iloc[-1]
        st.caption(f"No rule passed, so **no trim or buy-back prices are suggested**. Context only: price "
                   f"${price:,.2f} is {_ratio(price, sma50)} its 50-day average and {_ratio(price, sma200)} its "
                   f"200-day average; RSI(14) {rs:.0f}." if np.isfinite(rs) else "Context: N/A")

    _covered_calls(sym, df, prof, method, shares, cost)
    _harvest(sym, df, prof, method, shares, basis, lt_now, held, cost)
    _sources(status)


def _p(p):
    return "N/A" if p is None else f"{p:.2f}"


def _ratio(a, b):
    if b is None or not np.isfinite(b) or b == 0:
        return "N/A vs"
    return f"{(a / b - 1) * 100:+.0f}% vs"


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _cc_cached(symbol, status, other, nyc, method, shares, cost):
    df = _ohlcv(symbol)
    out = []
    for cfg in tr.CC_SETS:
        row = {"cfg": cfg}
        for acct in ("ira", "taxable"):
            r = tr.simulate_cc(df["Close"], cfg, tx.TaxProfile(status, other, nyc, acct), method, shares0=shares,
                               cost=cost)
            row[acct] = {k: r[k] for k in ("share_gain_pct", "taxpaid_shares_pct", "cycles", "assigned", "premium", "tax_paid")}
        out.append(row)
    return out


def _covered_calls(sym, df, prof, method, shares, cost):
    st.subheader("📞 Covered-call overlay (model)")
    st.caption("Sell a call option on half your shares every ~35 days at a strike the market rates ~25% likely to be "
               "hit; keep the premium. If the stock ends above the strike, your shares are 'called away' at the "
               "strike and we buy them back at the market price (so big rallies cost shares).")
    try:
        rows = _cc_cached(sym, prof.status, prof.other_income, prof.nyc_resident, method, shares, cost)
    except Exception as ex:
        st.caption(f"N/A ({ex})")
        return
    st.dataframe(pd.DataFrame([{
        "Setup": r["cfg"]["label"], "Cycles": r["ira"]["cycles"], "Assigned": r["ira"]["assigned"],
        "Shares vs hold — IRA (pre-tax)": _pct(r["ira"]["share_gain_pct"]),
        "Shares vs hold — taxable (after tax)": _pct(r["taxable"]["share_gain_pct"]),
        "Taxable, tax paid from shares": _pct(r["taxable"]["taxpaid_shares_pct"]),
    } for r in rows]), hide_index=True, width="stretch")
    st.caption("**Assumptions (model, not market quotes):** Black-Scholes prices with volatility = last 21-day "
               "realized volatility (×1.0) or ×1.2 as a stand-in for implied volatility (historical option quotes "
               "aren't available here); 4% risk-free rate; premiums received 5% below model (bid/ask); fractional "
               "contracts; premiums reinvested in shares; premiums and assignment gains taxed as short-term. Real "
               "option prices, early assignment and the 100-share contract size will differ.")


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _tlh_cached(symbol, peers, status, other, nyc, method, shares, cost):
    df = _ohlcv(symbol)
    cl = {}
    for p in peers:
        h = _safe_ohlcv(p)
        if h is not None:
            cl[p] = h["Close"]
    if not cl:
        raise RuntimeError("no peer prices")
    cands = pd.DataFrame(cl)
    out = {}
    for acct in ("ira", "taxable"):
        r = tr.simulate_tlh(df["Close"], cands, tx.TaxProfile(status, other, nyc, acct), method,
                            shares0=shares, cost=cost)
        out[acct] = {k: r[k] for k in ("share_gain_pct", "taxpaid_shares_pct", "swaps", "harvested", "tax_paid",
                                       "tracking_mean", "peers_used")}
    return out


def _harvest(sym, df, prof, method, shares, basis, lt_now, held, cost):
    st.subheader("🌾 Tax-loss harvest swap")
    st.caption("If a position is ≥15% below what you paid: sell it to lock in the loss, buy the most closely moving "
               "other miner for 31 days (the wash-sale window is 30), then switch back. You stay invested; the loss "
               "lowers your taxes now (up to $3,000/yr against other income, the rest carries forward).")
    price = float(df["Close"].iloc[-1])
    peers = tuple(p for p in dict.fromkeys(list(held) + list(EXTRA_PEERS)) if p != sym)
    if basis:
        h = tr.harvest_now(shares, price, basis, prof, lt_now)
        if h["loss"] > 0:
            nxt = h.get("next_years_saving") or []
            pc = {p: h_["Close"] for p in peers if (h_ := _safe_ohlcv(p)) is not None}
            pr = tr._best_peer(df["Close"], pd.DataFrame(pc).reindex(df.index).ffill(), len(df) - 1) if pc else None
            if h["carry"] > 0:
                carry_line = (f"- **{_usd(h['carry'])}** would carry forward to future years"
                              + (f" (about {_usd(sum(nxt))} more saved in the next {len(nxt)} years at $3,000/yr at "
                                 "today's income; capital gains you realise later use it up faster)" if nxt else "")
                              + ".")
            else:
                carry_line = "- The whole loss fits inside this year's $3,000 limit (nothing carries forward)."
            lines = [
                f"**Your {sym} today:** {shares:,.0f} sh @ {_usd(basis, 2)} cost vs ${price:,.2f} now → unrealised "
                f"loss **{_usd(h['loss'])}** ({(price / basis - 1) * 100:+.0f}%).",
                "",
                f"- Harvesting it now would cut this year's tax by about **{_usd(h['saving_now'])}** (from the $3,000 "
                "limit against other income — more if you also have gains this year).",
                carry_line,
                f"- Your new cost becomes ${price:,.2f}/share, so a future sale owes more tax — harvesting mostly "
                "**defers** tax; it pays off most if you'd otherwise have gains to offset.",
                f"- Closest-moving peer over the last year: **{pr or 'N/A'}**. Don't rebuy {sym} (or buy it in an "
                "IRA) within 30 days, or the loss is disallowed (wash sale).",
                f"- ⚠️ Your other accounts count too: an automatic dividend reinvestment or IRA purchase of {sym} "
                "within 30 days also triggers a wash sale.",
            ]
            st.markdown("\n".join(lines))
        else:
            st.caption(f"Your {sym} is above your cost ({_usd(basis, 2)}), so there is no loss to harvest today.")
    try:
        t = _tlh_cached(sym, peers, prof.status, prof.other_income, prof.nyc_resident, method, shares, cost)
    except Exception as ex:
        st.caption(f"Backtest N/A ({ex}).")
        return
    a, b = t["ira"], t["taxable"]
    st.dataframe(pd.DataFrame([{
        "Swaps": b["swaps"], "Losses harvested": _usd(b["harvested"]),
        "Shares vs hold — IRA (no tax benefit; tracking cost only)": _pct(a["share_gain_pct"]),
        "Shares vs hold — taxable (after tax)": _pct(b["share_gain_pct"]),
        "Taxable, tax paid from shares": _pct(b["taxpaid_shares_pct"]),
        "Peer minus stock over each swap (avg)": _pct(b["tracking_mean"]),
        "Peers used": ", ".join(sorted(set(b["peers_used"]))) or "—",
    }]), hide_index=True, width="stretch")
    st.caption("Backtest assumes the start price as cost, picks the peer by trailing 1-year correlation at each swap "
               "(no look-ahead), and treats a different company as *not 'substantially identical'* (IRS Pub. 550 — "
               "a judgment; confirm with a CPA). The after-tax result counts the bigger future tax from the lower "
               "cost (the gain is deferred, not erased); the 'tax paid from shares' view converts each refund into "
               "shares at that year-end's price.")


def _sources(status):
    with st.expander("📚 Tax assumptions & sources (tax year 2026)"):
        st.dataframe(pd.DataFrame(tx.bracket_table(status)), hide_index=True, width="stretch")
        st.markdown(f"""
- Standard deduction: federal {_usd(tx.FED_STD[status])}, NY {_usd(tx.NY_STD[status])}. No itemizing, credits or AMT.
- Capital losses: net losses offset up to $3,000/yr of other income; the rest carries forward, keeping its
  short/long-term character.
- Wash sales: loss disallowed if the same stock is bought 30 days before or after; added to the new shares' cost and
  holding period. Purchases in your other accounts (incl. IRAs) count too — the app can't see those.
- **Not modelled:** NY's supplemental "recapture" tax above NY AGI $107,650 (understates NY tax for high incomes),
  state tax credits, estimated-tax timing (tax is settled each Dec 31), and 2026 rules are applied to every past year.
- Lot method: FIFO is Schwab's default; specific-ID here means highest cost first.
""")
        for k, (label, url) in tx.SOURCES.items():
            st.markdown(f"- {label} — <{url}> (checked {tx.VERIFIED})")
        st.caption("Not tax advice — confirm with a CPA.")
