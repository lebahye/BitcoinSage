"""
components/holding_plan.py — "🧭 My Plan": the ONE place the dashboard says
Hold / Trim / Sell / Rotate, written for a risk-averse long-term holder with a
2030 sell-or-rotate plan who is new to investing.
"""

from datetime import date

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.explain import explain, HELP, GLOSSARY
from utils.holding_advisor import advise, compute_facts, scenario_paths, years_to, add_signal, peer_vs_200
from utils.market_data import fetch_daily_closes, fetched_at
from utils.tickers import WATCHLIST, MINING_STOCKS, resolve

_ACTION_STYLE = {
    "HOLD":   ("#00c853", "🟢"),
    "TRIM":   ("#ffb300", "🟡"),
    "ROTATE": ("#29b6f6", "🔄"),
    "SELL":   ("#ff1744", "🔴"),
}
_STATUS_ICON = {"good": "✅", "warn": "⚠️", "bad": "🚨", "info": "ℹ️", "missing": "❔"}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _analyst_targets_cached(symbol: str) -> dict:
    import yfinance as yf
    info = yf.Ticker(symbol).info or {}   # raises on rate limit -> not cached
    out = {"low": info.get("targetLowPrice"), "mean": info.get("targetMeanPrice"),
           "high": info.get("targetHighPrice"), "n": info.get("numberOfAnalystOpinions"),
           "rating": info.get("recommendationKey")}
    return out if out["mean"] else {}


_EVENT_PEERS = ("RIOT", "MARA", "CLSK", "HUT", "KEEL", "CIFR", "WULF", "IREN", "CORZ")


class _NoData(Exception):
    pass


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _earnings_cached(symbols: tuple) -> dict:
    from utils.event_calendar import fetch_earnings
    out = fetch_earnings(symbols)
    if not any(out.values()):
        raise _NoData()          # don't cache an all-empty (likely rate-limited) result
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def _block_height_cached() -> int:
    from utils.event_calendar import fetch_block_height
    h = fetch_block_height()
    if not h:
        raise _NoData()
    return h


def load_events(symbol: str):
    from datetime import date as _date
    from utils.event_calendar import build_calendar
    syms = tuple(dict.fromkeys((symbol,) + _EVENT_PEERS))
    try:
        earn = _earnings_cached(syms)
    except Exception:
        earn = {}
    try:
        height = _block_height_cached()
    except Exception:
        height = None
    today = _date.today()
    return today, build_calendar(today, earn, height), bool(earn), height


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _backtest_cached(symbol: str, years: int) -> dict:
    from utils.market_data import fetch_daily_closes
    from utils.signal_backtest import run_backtest
    syms = tuple(dict.fromkeys((symbol, "BTC-USD", "^VIX") + tuple(WATCHLIST)))
    closes = fetch_daily_closes(syms, period="10y")
    if closes.empty or symbol not in closes.columns or "BTC-USD" not in closes.columns:
        raise _NoData()
    r = run_backtest(closes, symbol, [w for w in WATCHLIST if w != symbol], years=years)
    if not r:
        raise _NoData()
    return r


def load_backtest(symbol: str, years: int = 5):
    try:
        return _backtest_cached(symbol, years)
    except Exception:
        return None


def _analyst_targets(symbol: str) -> dict:
    try:
        return _analyst_targets_cached(symbol)
    except Exception:
        return {}


def _load_user_data():
    from components.personal_portfolio import PersonalPortfolio
    positions = PersonalPortfolio._load_positions()
    targets = PersonalPortfolio._load_targets()
    return positions, targets


def _market_bundle(symbols):
    tickers = tuple(sorted(set(list(symbols) + list(WATCHLIST) + ["BTC-USD", "^VIX"])))
    return fetch_daily_closes(tickers, "2y")


def _best_peer(closes, exclude):
    best = None
    for t in WATCHLIST:
        if t == exclude or t not in closes.columns:
            continue
        f = compute_facts(closes[t])
        if not f or f.get("sma200") is None or f.get("ret_3m") is None:
            continue
        if f["price"] > f["sma200"] and (best is None or f["ret_3m"] > best["ret_3m"]):
            best = {"ticker": t, "ret_3m": f["ret_3m"]}
    return best


def get_advice(symbol: str = "RIOT"):
    """Compute advice for one holding (used by the tab and the Command Center line)."""
    symbol = resolve(symbol)
    positions, targets = _load_user_data()
    closes = _market_bundle(list(positions.keys()) + [symbol])
    if closes.empty or symbol not in closes.columns:
        return None, closes, positions, targets
    last = {s: float(closes[s].dropna().iloc[-1]) for s in positions if s in closes.columns and closes[s].notna().any()}
    port_value = sum(positions[s]["shares"] * last[s] for s in last) or None
    btc = compute_facts(closes["BTC-USD"]) if "BTC-USD" in closes.columns else {}
    vix = float(closes["^VIX"].dropna().iloc[-1]) if "^VIX" in closes.columns and closes["^VIX"].notna().any() else None
    div = None
    from utils.tickers import CORRELATION_UNIVERSE
    if symbol == "RIOT" or symbol in CORRELATION_UNIVERSE:     # any stock with a peer set (was RIOT only)
        try:
            from utils.riot_correlation import load_riot_correlations
            div = load_riot_correlations(symbol).get("divergence")
        except Exception:
            div = None
    pos = positions.get(symbol, {})
    adv = advise(symbol, compute_facts(closes[symbol]), btc, vix,
                 shares=pos.get("shares", 0), cost_basis=pos.get("cost_basis", 0.0),
                 portfolio_value=port_value, target_price=targets.get(symbol),
                 analyst=_analyst_targets(symbol), divergence=div,
                 best_peer=_best_peer(closes, symbol))
    return adv, closes, positions, targets


def get_add_advice(symbol, closes, positions):
    """ADD / WAIT for one holding, from the same price bundle."""
    last = {s: float(closes[s].dropna().iloc[-1]) for s in positions if s in closes.columns and closes[s].notna().any()}
    port_value = sum(positions[s]["shares"] * last[s] for s in last) or None
    pos = positions.get(symbol, {})
    weight = (pos.get("shares", 0) * last[symbol] / port_value) if (port_value and symbol in last) else None
    btc = compute_facts(closes["BTC-USD"]) if "BTC-USD" in closes.columns else {}
    vix = float(closes["^VIX"].dropna().iloc[-1]) if "^VIX" in closes.columns and closes["^VIX"].notna().any() else None
    peers = [t for t in WATCHLIST if t != symbol]
    return add_signal(compute_facts(closes[symbol]), btc, vix, peer_vs_200(closes, peers), weight)


class HoldingPlan:
    def render(self):
        st.header("🧭 My Plan — Hold, Trim, Sell or Rotate?")
        st.caption("Built for a **risk-averse, long-term holder** planning to sell or rotate around **2030**. "
                   "Uses live prices plus your own positions, cost basis and target prices from the 🏆 Portfolio tab. "
                   "Educational tool — **not financial advice**.")

        positions, _ = _load_user_data()
        held = sorted([s for s, p in positions.items() if p.get("shares", 0) > 0],
                      key=lambda s: -positions[s].get("shares", 0)) or ["RIOT"]
        from components.stock_verdict import pick_following_verdict
        symbol = pick_following_verdict(
            st, "Which holding?", held, "plan_symbol", held[0],
            format_func=lambda s: f"{s} — {MINING_STOCKS.get(s, positions.get(s, {}).get('name', s))}",
            help="Your holdings from the Portfolio tab (largest first). Follows the stock picked on ⚖️ Stock Verdict "
                 "when you hold it. Bitcoin to 2030 below uses the same stock.")

        with st.spinner("Checking prices, Bitcoin, the VIX and your position…"):
            adv, closes, positions, targets = get_advice(symbol)
        if adv is None:
            st.error(f"⚠️ No price data for {symbol} from Yahoo Finance right now — no recommendation shown. "
                     "Try 🔄 Refresh Data in a minute.")
            return
        add = get_add_advice(symbol, closes, positions)
        self._render_change_banner(symbol, adv, add)

        # ── Verdict card ─────────────────────────────────────────────────
        color, icon = _ACTION_STYLE[adv.action]
        st.markdown(
            f'<div style="background:{color}1a;border:2px solid {color};border-radius:12px;padding:18px 22px;margin:6px 0 12px">'
            f'<div style="font-size:.85rem;color:#bbb">Recommendation for {symbol} · confidence: <b>{adv.confidence}</b> · '
            f'risk points {adv.risk_score}/{adv.max_score}</div>'
            f'<div style="font-size:2rem;font-weight:800;color:{color};margin:4px 0">{icon} {adv.action}</div>'
            f'<div style="font-size:1.05rem;color:#eee">{adv.headline}</div></div>',
            unsafe_allow_html=True)
        explain("recommendation")
        from utils.verdict import combine_plan
        _vd = combine_plan(adv.action, add.action if add else None)
        st.caption(f"⚖️ **Stock Verdict: {_vd}** — the same single call the ⚖️ Stock Verdict page shows for {symbol} "
                   + ("(this HOLD plus the ADD signal below)." if _vd != adv.action else "(My Plan's call is the verdict).")
                   + " That page adds every other tab's evidence, which can only change how sure it is.")
        _bt = load_backtest(symbol)
        if _bt:
            _sm, _b = _bt["summary"], _bt["baseline"]["6M"]
            _beat = [n.split(" ")[0] for n, v in _sm.items() if v["6M"]["n"] and
                     ((v["6M"]["avg"] > _b["avg"]) if n.startswith("ADD") else (v["6M"]["avg"] < _b["avg"]))]
            st.caption("📊 Track record (last 5 yrs): " + (
                "none of the timing signals beat simply holding — treat SELL/ADD timing as a prompt to look closer, "
                "not an instruction; the position-size rule matters more." if not _beat else
                f"{', '.join(_beat)} signals did better than a random day, on small samples.")
                + " Details in 📊 Track record below.")

        f = adv.facts
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Last close", f"${f['price']:,.2f}", help="Latest daily close from Yahoo Finance (may be delayed).")
        c2.metric("Your position value", f"${f['value']:,.0f}" if f["value"] else "n/a",
                  help=HELP["cost_basis"])
        c3.metric("Gain vs cost basis", "n/a" if np.isnan(f["gain"]) else f"{f['gain']:+.0%}", help=HELP["cost_basis"])
        c4.metric("Share of your portfolio", "n/a" if np.isnan(f["weight"]) else f"{f['weight']:.0%}",
                  help="This position's value ÷ the value of all positions saved in the Portfolio tab.")

        today, events, have_earn, height = load_events(symbol)
        from utils.event_calendar import flagged
        soon = flagged(events, today)
        if soon:
            st.markdown("⏰ **Coming up in the next 14 days:** " + " · ".join(
                f"**{e.title}** {e.when:%a %b %d} ({e.days_away(today)}d)" for e in soon)
                + " — expect bigger price swings around these. See 📅 Event calendar below.")

        # ── The checks ───────────────────────────────────────────────────
        st.subheader("Why — the checks behind the call")
        for chk in adv.checks:
            pts = f" · **+{chk.points} risk**" if chk.points else ""
            st.markdown(f"{_STATUS_ICON.get(chk.status, '•')} **{chk.name}** — {chk.detail}{pts}")
        keys = [c.help_key for c in adv.checks if c.help_key]
        with st.expander("ℹ️ What do these checks mean? (plain English)"):
            for k in dict.fromkeys(keys):
                title, body = GLOSSARY[k]
                st.markdown(f"**{title}**  \n{body}")
                st.markdown("---")

        self._render_add(add)
        try:
            from components.signal_reconcile import render_cross_tab_panel
            render_cross_tab_panel(symbol, adv.action, add.action if add else None)
        except Exception:
            pass
        try:
            from components.signal_reconcile import render_reflexivity_context
            render_reflexivity_context(symbol)
        except Exception:
            pass

        self._render_events(symbol, today, events, have_earn, height)

        st.subheader("🔁 What would change my mind")
        for line in adv.change_my_mind:
            st.markdown(f"- {line}")
        st.caption("Re-check after each quarterly earnings report and whenever one of these levels is crossed.")

        self._render_track_record(symbol)

        # ── Path to 2030 ─────────────────────────────────────────────────
        plan_year, plan_cagr = self._render_path(symbol, closes, positions, targets, adv)

        # ── Bitcoin to 2030 (scenarios, BTC↔stock link, cycle, watchlist, milestones) ──
        try:
            from components import btc_2030
            from utils.holding_advisor import years_to as _yt
            btc_2030.render(symbol, closes, targets, plan_year, _yt(plan_year), plan_cagr, height)
        except Exception as e:  # never let this panel break My Plan
            st.warning(f"₿ Bitcoin-to-{plan_year} panel unavailable right now ({type(e).__name__}) — N/A.")

        # ── All holdings at a glance ─────────────────────────────────────
        self._render_all_holdings(closes, positions, targets)

        last_date = closes[symbol].dropna().index[-1].date()
        st.caption(f"Sources: Yahoo Finance daily closes to {last_date} (2 years, cached 15 min), Yahoo analyst targets "
                   f"(cached 6 h), your saved positions/targets. Computed {fetched_at()}. "
                   "This is an educational tool, not financial advice — markets can do anything.")

    # ------------------------------------------------------------------
    def _render_path(self, symbol, closes, positions, targets, adv):
        st.subheader(f"🗺️ Path to 2030 — what {symbol} could be worth")
        explain("projection")
        f = compute_facts(closes[symbol])
        price, vol = f["price"], f.get("vol_1y")
        c1, c2 = st.columns([1, 2])
        with c1:
            year = st.slider("Plan year", 2027, 2032, 2030, help="The year you plan to sell or rotate.")
        with c2:
            with st.expander("⚙️ Scenario assumptions (yearly return) — edit to your own view"):
                a1, a2, a3 = st.columns(3)
                bear = a1.number_input("Bear %/yr", -60.0, 0.0, -20.0, 5.0,
                                       help="Crypto winter / dilution / AI-hosting story fails.") / 100
                base = a2.number_input("Base %/yr", -20.0, 40.0, 5.0, 5.0,
                                       help="Muddle-through: Bitcoin and AI hosting grow modestly, dilution continues.") / 100
                bull = a3.number_input("Bull %/yr", 0.0, 100.0, 25.0, 5.0,
                                       help="Strong Bitcoin cycle plus successful AI data-center conversion.") / 100
        yrs = years_to(year)
        sc = scenario_paths(price, yrs, {"Bear": bear, "Base": base, "Bull": bull}, vol)
        shares = positions.get(symbol, {}).get("shares", 0)

        months = pd.date_range(date.today(), periods=max(2, int(yrs * 12) + 1), freq="MS")
        t = np.array([(d.date() - date.today()).days / 365.25 for d in months]).clip(min=0)
        fig = go.Figure()
        hist = closes[symbol].dropna().iloc[-504:]
        fig.add_trace(go.Scatter(x=hist.index, y=hist.values, name="History", line=dict(color="#bbb", width=1.5)))
        if vol:
            fig.add_trace(go.Scatter(x=list(months) + list(months[::-1]),
                                     y=list(price * np.exp(vol * np.sqrt(t))) + list((price * np.exp(-vol * np.sqrt(t)))[::-1]),
                                     fill="toself", fillcolor="rgba(255,255,255,.07)", line=dict(width=0),
                                     name=f"Typical range (±1σ, {vol:.0%} vol)", hoverinfo="skip"))
        for name, g, colr in [("Bull", bull, "#00c853"), ("Base", base, "#ffd600"), ("Bear", bear, "#ff1744")]:
            fig.add_trace(go.Scatter(x=months, y=price * (1 + g) ** t, name=f"{name} ({g:+.0%}/yr)",
                                     line=dict(color=colr, width=2, dash="dash")))
        an = _analyst_targets(symbol)
        if an:
            one_year = pd.Timestamp(date.today()) + pd.DateOffset(years=1)
            fig.add_trace(go.Scatter(x=[one_year] * 3, y=[an.get("low"), an.get("mean"), an.get("high")],
                                     mode="markers+text", text=["analyst low", "analyst avg", "analyst high"],
                                     textposition="middle right", marker=dict(size=9, color="#29b6f6"),
                                     name="Analyst 12-mo targets"))
        tgt = targets.get(symbol)
        if tgt:
            fig.add_hline(y=tgt, line_dash="dot", line_color="#ffb300", annotation_text=f"Your target ${tgt:,.2f}")
        fig.update_layout(template="plotly_dark", height=460, yaxis_title="Price ($)", hovermode="x unified",
                          legend=dict(orientation="h"), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig, use_container_width=True)

        rows = []
        for name in ["Bear", "Base", "Bull"]:
            p = sc[name]
            rows.append({"Scenario": name, f"Price end of {year}": f"${p:,.2f}", "Change": f"{p/price-1:+.0%}",
                         "Your position value": f"${p*shares:,.0f}" if shares else "n/a"})
        if vol:
            rows.append({"Scenario": "Typical range (data-driven)",
                         f"Price end of {year}": f"${sc['band_low']:,.2f} – ${sc['band_high']:,.2f}",
                         "Change": f"{sc['band_low']/price-1:+.0%} to {sc['band_high']/price-1:+.0%}",
                         "Your position value": (f"${sc['band_low']*shares:,.0f} – ${sc['band_high']*shares:,.0f}" if shares else "n/a")})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("Bear/Base/Bull are **assumptions you can edit**, not predictions. The 'typical range' uses only "
                   f"{symbol}'s own last-year volatility (about 2 in 3 outcomes historically fall inside it) — "
                   "it shows how wide the possibilities are, not which way the price will go. "
                   "The ₿ Bitcoin section below shows the Bitcoin price each of these cases quietly assumes.")

        with st.expander("📅 A simple, low-stress 2030 exit framework (education, not advice)"):
            st.markdown(f"""
- **Don't plan to sell everything on one day.** Miners can move 10% in a day. Selling in stages
  (for example a third in late {year-1}, a third in early {year}, the rest later in {year}) averages out your exit price.
- **Trim on strength, not on panic.** If your own target or the bull case arrives early, selling 10–25% locks in gains
  and lowers risk while keeping you in for the rest of the plan.
- **Keep any single stock to a size you can sleep with.** If one position is more than ~40% of your portfolio,
  gradually rotating some into less volatile holdings reduces the chance one bad year wrecks the plan.
- **Know your re-check triggers** (listed above under "What would change my mind") and look again after each earnings report.
- **Taxes:** shares held over a year usually qualify for lower long-term capital-gains rates in the US. Check with a tax adviser before large sales.
""")
        return year, {"Bear": bear, "Base": base, "Bull": bull}

    # ------------------------------------------------------------------
    def _render_change_banner(self, symbol, adv, add):
        """Persist this call; show a banner if it differs from the last check (until acknowledged)."""
        from utils import call_tracker, notifier
        try:
            change = call_tracker.record(symbol, call_tracker.snapshot(adv, add))
        except Exception as e:
            st.caption(f"(Couldn't save the call history: {type(e).__name__})")
            return
        pend = call_tracker.pending(symbol)
        if change and not change.get("notified"):
            result = notifier.notify(f"BitcoinSage: {symbol} call changed", call_tracker.format_change(change))
            if result:
                call_tracker.mark_notified(symbol)
                st.session_state[f"notify_result_{symbol}"] = result
        if pend:
            o, n = pend["old"], pend["new"]
            when = (o.get("ts") or "")[:16].replace("T", " ")
            st.markdown(
                f'<div style="background:#ffab001f;border:2px solid #ffab00;border-radius:12px;padding:14px 18px;margin:4px 0 10px">'
                f'<div style="font-size:1.15rem;font-weight:800;color:#ffab00">🔔 What changed since last check ({when} UTC)</div>'
                f'<div style="color:#eee;margin-top:4px">Hold/Sell call: <b>{o["action"]}</b> → <b>{n["action"]}</b>'
                f' &nbsp;·&nbsp; Add more?: <b>{o.get("add_action") or "n/a"}</b> → <b>{n.get("add_action") or "n/a"}</b>'
                + (f' &nbsp;·&nbsp; price ${o["price"]:,.2f} → ${n["price"]:,.2f}' if o.get("price") and n.get("price") else "")
                + '</div></div>', unsafe_allow_html=True)
            if pend.get("why"):
                st.markdown("**Why:** " + "; ".join(pend["why"][:8]))
            res = st.session_state.get(f"notify_result_{symbol}")
            if res:
                st.caption("Alert delivery: " + ", ".join(f"{k} {v}" for k, v in res.items()))
            if st.button("✅ Got it — hide this", key=f"ack_{symbol}"):
                call_tracker.acknowledge(symbol)
                st.rerun()
        else:
            st.caption(f"🔔 No change in the {symbol} call since your last check. "
                       "A banner will appear here if the call flips (e.g. HOLD → TRIM or WAIT → ADD).")
        with st.expander("🔔 Alert settings (optional — off by default)"):
            explain("call_alerts")
            cfg = notifier.configured()
            settings = notifier.load_settings()
            st.markdown(f"Telegram secrets set: **{'yes' if cfg['telegram'] else 'no'}** · "
                        f"Email (SMTP) secrets set: **{'yes' if cfg['email'] else 'no'}**")
            en = st.checkbox("Send me an alert when a call changes", value=settings["enabled"], key="notify_enabled",
                             help="Off by default. Only works once the matching Replit Secrets are set.")
            tg = st.checkbox("…by Telegram", value=settings["telegram"], key="notify_tg")
            em = st.checkbox("…by email", value=settings["email"], key="notify_em")
            new = {"enabled": en, "telegram": tg, "email": em}
            if new != settings:
                notifier.save_settings(new)
                st.caption("Saved.")
            if en and not (cfg["telegram"] or cfg["email"]):
                st.info("Alerts are on, but no Telegram or email secrets are set yet, so nothing will be sent. "
                        "See 'How do call-change alerts work?' above.")
            hist = call_tracker.history(symbol)
            if hist:
                st.markdown("**Past call changes**")
                st.dataframe(pd.DataFrame([{"When (UTC)": (h["new"].get("ts") or "")[:16].replace("T", " "),
                                            "Call": f'{h["old"]["action"]} → {h["new"]["action"]}',
                                            "Add?": f'{h["old"].get("add_action")} → {h["new"].get("add_action")}'}
                                           for h in reversed(hist)]), hide_index=True, use_container_width=True)

    # ------------------------------------------------------------------
    def _render_events(self, symbol, today, events, have_earn, height):
        from utils.event_calendar import FLAG_DAYS, FOMC_SOURCE, CPI_SOURCE, SCHEDULES_LAST_VERIFIED
        st.subheader("📅 Event calendar")
        if not events:
            st.caption("No upcoming events available right now.")
            return
        rows = [{"": "⏰" if 0 <= e.days_away(today) <= FLAG_DAYS else "",
                 "Date": e.when.strftime("%a %b %d, %Y") + (" (est.)" if e.estimated else ""),
                 "In": f"{e.days_away(today)} days", "Event": e.title, "Details": e.detail} for e in events]
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        notes = []
        if not have_earn:
            notes.append("earnings dates unavailable from Yahoo right now (try Refresh later)")
        if not height:
            notes.append("live block height unavailable, so no halving estimate")
        st.caption(f"⏰ = within {FLAG_DAYS} days. Earnings: Yahoo Finance (often estimated until the company confirms). "
                   f"FOMC: [Federal Reserve]({FOMC_SOURCE}); CPI: [BLS]({CPI_SOURCE}) — schedules last verified "
                   f"{SCHEDULES_LAST_VERIFIED:%b %d, %Y}. Showing the next 120 days plus the halving."
                   + (" Note: " + "; ".join(notes) + "." if notes else ""))
        explain("event_calendar")

    # ------------------------------------------------------------------
    def _render_track_record(self, symbol):
        from utils.signal_backtest import HORIZONS, verdict, trust_label
        st.subheader("📊 Track record — how much to trust these signals")
        with st.spinner("Replaying the rules on 5 years of history…"):
            r = load_backtest(symbol)
        if not r:
            st.caption("Track record unavailable right now (not enough history from Yahoo Finance). Try again later.")
            return
        st.caption(f"The same ADD and sell-side rules replayed day by day on {symbol} from {r['start']:%b %Y} to "
                   f"{r['end']:%b %d, %Y} ({r['days']:,} trading days), using only data available on each day.")
        for name in r["summary"]:
            st.markdown("- " + verdict(name, r["summary"][name], r["baseline"]))
        rows = []
        for name, sm in r["summary"].items():
            row = {"Signal": name, "Signals": sm["1M"]["n"]}
            for k in HORIZONS:
                v = sm[k]
                row[f"{k} avg"] = "n/a" if not v["n"] else f"{v['avg']:+.0%}"
                row[f"{k} hit"] = "n/a" if not v["n"] else f"{v['hit']:.0%}"
            rows.append(row)
        b = r["baseline"]
        rows.append({"Signal": "Any day (just holding)", "Signals": b["1M"]["n"],
                     **{f"{k} avg": f"{b[k]['avg']:+.0%}" for k in HORIZONS},
                     **{f"{k} hit": f"{b[k]['up']:.0%} up" for k in HORIZONS}})
        st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
        st.caption("avg = average return from the next day's close. hit = how often the signal was 'right': for ADD the "
                   "price was higher later; for SELL/Caution the price was lower later.")
        stg = r.get("strategy") or {}
        if stg:
            c1, c2, c3 = st.columns(3)
            c1.metric("Just hold (5 yrs)", f"{stg['hold_total']:+.0%}", help=f"Worst drop along the way {stg['hold_mdd']:.0%}.")
            c2.metric("Follow the rules", f"{stg['strategy_total']:+.0%}",
                      f"{stg['strategy_total'] - stg['hold_total']:+.0%} vs hold",
                      help="Sell the day after a SELL signal; buy back the day after an ADD or once risk points fall to 2 "
                           f"or less. Worst drop {stg['strategy_mdd']:.0%}; invested {stg['time_invested']:.0%} of days; "
                           f"{stg['switches']} switches. No trading costs or taxes included.")
            c3.metric("Days in each state", f"ADD {r['days_in_state']['ADD']} · SELL {r['days_in_state']['SELL']}",
                      help="Trading days the condition was on. Many in-a-row days count as one signal above.")
            st.line_chart(stg["equity"], height=220)
        with st.expander(f"📜 Every past signal ({len(r['signals'])})"):
            if len(r["signals"]):
                df = r["signals"].copy()
                for k in HORIZONS:
                    df[k] = df[k].map(lambda x: "pending" if pd.isna(x) else f"{x:+.0%}")
                df["Price next close"] = df["Price next close"].map(lambda x: f"${x:,.2f}")
                df["RSI"] = df["RSI"].map(lambda x: f"{x:.0f}")
                st.dataframe(df, hide_index=True, use_container_width=True)
                st.download_button("⬇️ Download signals (CSV)", r["signals"].to_csv(index=False),
                                   f"{symbol}_signal_track_record.csv", "text/csv", key=f"bt_dl_{symbol}")
        explain("track_record")

    # ------------------------------------------------------------------
    def _render_add(self, a):
        st.subheader("➕ Good time to add more?")
        color = "#00c853" if a.action == "ADD" else "#90a4ae"
        st.markdown(
            f'<div style="background:{color}1a;border-left:5px solid {color};border-radius:8px;padding:12px 16px;margin:4px 0 8px">'
            f'<b style="color:{color};font-size:1.3rem">{"➕ ADD" if a.action == "ADD" else "⏸️ WAIT"}</b>'
            f' <span style="color:#bbb">· confidence {a.confidence}</span><br>'
            f'<span style="color:#eee">{a.headline}</span></div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Is it on sale?** (need 2 of 3)")
            for chk in a.oversold:
                st.markdown(f"{'✅' if chk.status == 'good' else '❔' if chk.status == 'missing' else '▫️'} "
                            f"**{chk.name}** — {chk.detail}")
        with c2:
            st.markdown("**Is the backdrop healthy?** (need all 3)")
            for chk in a.backdrop:
                st.markdown(f"{_STATUS_ICON.get(chk.status, '•')} **{chk.name}** — {chk.detail}")
        with st.expander("📍 Price / condition levels that would trigger ADD"):
            for lv in a.levels:
                st.markdown(f"- {lv}")
        explain("add_signal")
        explain("rsi")

    # ------------------------------------------------------------------
    def _render_all_holdings(self, closes, positions, targets):
        st.subheader("📋 All your holdings at a glance")
        rows = []
        last = {s: float(closes[s].dropna().iloc[-1]) for s in positions if s in closes.columns and closes[s].notna().any()}
        port_value = sum(positions[s]["shares"] * last[s] for s in last) or None
        btc = compute_facts(closes["BTC-USD"]) if "BTC-USD" in closes.columns else {}
        vix = float(closes["^VIX"].dropna().iloc[-1]) if "^VIX" in closes.columns and closes["^VIX"].notna().any() else None
        for s, p in positions.items():
            if p.get("shares", 0) <= 0:
                continue
            if s not in closes.columns:
                rows.append({"Stock": s, "Call": "n/a (no data)"})
                continue
            a = advise(s, compute_facts(closes[s]), btc, vix, shares=p["shares"], cost_basis=p["cost_basis"],
                       portfolio_value=port_value, target_price=targets.get(s))
            rows.append({"Stock": s, "Call": f"{_ACTION_STYLE[a.action][1]} {a.action}", "Confidence": a.confidence,
                         "Risk pts": a.risk_score, "Last": f"${a.facts['price']:,.2f}",
                         "Gain": "n/a" if np.isnan(a.facts["gain"]) else f"{a.facts['gain']:+.0%}",
                         "Weight": "n/a" if np.isnan(a.facts["weight"]) else f"{a.facts['weight']:.0%}",
                         "Your target": f"${targets[s]:,.2f}" if targets.get(s) else "—"})
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption("Same rules as above (the RIOT-only peer-divergence check is applied to RIOT only). "
                       "Edit shares, cost basis and targets in 🏆 Portfolio.")
