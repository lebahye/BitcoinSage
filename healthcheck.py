"""
healthcheck.py — BitcoinSage System Health Check
Run with: streamlit run healthcheck.py

Tests every import, API, and data source live.
Shows exactly what's working, what's broken, and what data is fresh.
"""

import streamlit as st
import time
import traceback
from datetime import datetime

st.set_page_config(page_title="BitcoinSage Health Check", page_icon="🩺", layout="wide")
st.title("🩺 BitcoinSage Health Check")
st.caption(f"Run at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")

# ─── helpers ─────────────────────────────────────────────────────────────────

def ok(msg):
    st.markdown(f"✅ **{msg}**")

def fail(msg, detail=""):
    st.markdown(f"❌ **{msg}**")
    if detail:
        st.code(detail, language="text")

def warn(msg):
    st.markdown(f"⚠️ {msg}")

def section(title):
    st.markdown(f"### {title}")


# ═══════════════════════════════════════════════════════════════════════════════
# 1. IMPORTS
# ═══════════════════════════════════════════════════════════════════════════════

section("1️⃣ Python Imports")
col1, col2 = st.columns(2)

import_results = {}

third_party = {
    "yfinance":        "yfinance",
    "pandas":          "pandas",
    "numpy":           "numpy",
    "plotly":          "plotly",
    "requests":        "requests",
    "streamlit":       "streamlit",
    "redis":           "redis",
}

internal_utils = {
    "unified_data_fetcher":  "utils.unified_data_fetcher",
    "options_analytics":     "utils.options_analytics",
    "chart_builder":         "utils.chart_builder",
    "styles":                "utils.styles",
    "risk_engine":           "utils.risk_engine",
    "backtesting_engine":    "utils.backtesting_engine",
    "next_mover_engine":     "utils.next_mover_engine",
    "sentiment_analyzer":    "utils.sentiment_analyzer",
    "advanced_ta":           "utils.advanced_ta",
    "polymarket_fetcher":    "utils.polymarket_fetcher",
    "polymarket_live_feed":  "utils.polymarket_live_feed",
    "schwab_client":         "utils.schwab_client",
}

internal_components = {
    "stock_dashboard":       "components.stock_dashboard",
    "next_mover_dashboard":  "components.next_mover_dashboard",
    "unified_options":       "components.unified_options",
    "dark_pool_tracker":     "components.dark_pool_tracker",
    "advanced_ta_dashboard": "components.advanced_ta_dashboard",
    "polymarket_tracker":    "components.polymarket_tracker",
    "sentiment_analysis":    "components.sentiment_analysis",
    "risk_center":           "components.risk_center",
    "personal_portfolio":    "components.personal_portfolio",
    "riot_protection":       "components.riot_protection",
    "backtesting_dashboard": "components.backtesting_dashboard",
    "weekly_outlook":        "components.weekly_outlook",
    "volatility_hole_chart": "components.volatility_hole_chart",
    "reflexivity_dashboard": "components.reflexivity_dashboard",
}

with col1:
    st.markdown("**Third-party packages**")
    for name, mod in third_party.items():
        try:
            __import__(mod)
            ok(name)
            import_results[name] = True
        except Exception as e:
            fail(name, str(e))
            import_results[name] = False

    st.markdown("**Internal utils**")
    for name, mod in internal_utils.items():
        try:
            __import__(mod)
            ok(name)
            import_results[name] = True
        except Exception as e:
            fail(name, traceback.format_exc()[-300:])
            import_results[name] = False

with col2:
    st.markdown("**Components**")
    for name, mod in internal_components.items():
        try:
            __import__(mod)
            ok(name)
            import_results[name] = True
        except Exception as e:
            fail(name, traceback.format_exc()[-400:])
            import_results[name] = False

all_imports_ok = all(import_results.values())
if all_imports_ok:
    st.success("✅ ALL IMPORTS PASSING")
else:
    failed = [k for k, v in import_results.items() if not v]
    st.error(f"❌ {len(failed)} imports failing: {', '.join(failed)}")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 2. YAHOO FINANCE — Core data source
# ═══════════════════════════════════════════════════════════════════════════════

section("2️⃣ Yahoo Finance (Primary Data Source)")

import yfinance as yf
import pandas as pd

test_symbols = ["BTC-USD", "MARA", "RIOT", "CLSK"]
yf_results = {}

cols = st.columns(len(test_symbols))
for col, sym in zip(cols, test_symbols):
    with col:
        try:
            t0   = time.time()
            hist = yf.Ticker(sym).history(period="5d", timeout=10)
            ms   = int((time.time() - t0) * 1000)
            if hist.empty:
                st.metric(sym, "⚠️ Empty", f"{ms}ms")
                yf_results[sym] = None
            else:
                price     = hist["Close"].iloc[-1]
                last_date = hist.index[-1]
                staleness = (datetime.utcnow() - last_date.replace(tzinfo=None)).days
                color     = "🟢" if staleness <= 1 else "🟡" if staleness <= 3 else "🔴"
                st.metric(sym, f"${price:,.2f}", f"{color} {ms}ms · {staleness}d old")
                yf_results[sym] = {"price": price, "staleness_days": staleness, "ms": ms}
        except Exception as e:
            st.metric(sym, "❌ Error", str(e)[:30])
            yf_results[sym] = None

# Options check
st.markdown("**Options chain (MARA)**")
try:
    t0   = time.time()
    tk   = yf.Ticker("MARA")
    exps = tk.options
    ms   = int((time.time() - t0) * 1000)
    if exps:
        chain = tk.option_chain(exps[0])
        ncalls = len(chain.calls)
        nputs  = len(chain.puts)
        ok(f"Options: {len(exps)} expirations · {ncalls} calls / {nputs} puts · {ms}ms")
    else:
        warn(f"Options: no expirations returned ({ms}ms) — likely weekend/market closed")
except Exception as e:
    fail("Options", traceback.format_exc()[-300:])

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 3. BLOCKCHAIN.INFO — Hashrate / Difficulty (optional)
# ═══════════════════════════════════════════════════════════════════════════════

section("3️⃣ Blockchain.info (Hashrate & Difficulty — Optional)")

import requests

for chart, label in [("hash-rate", "Hashrate"), ("difficulty", "Difficulty")]:
    try:
        t0   = time.time()
        url  = f"https://api.blockchain.info/charts/{chart}?timespan=30days&format=json&cors=true"
        resp = requests.get(url, timeout=8)
        ms   = int((time.time() - t0) * 1000)
        if resp.status_code == 200:
            vals = resp.json().get("values", [])
            if vals:
                latest = vals[-1]["y"]
                ok(f"{label}: {latest:,.0f} · {len(vals)} data points · {ms}ms")
            else:
                warn(f"{label}: empty response ({ms}ms)")
        else:
            warn(f"{label}: HTTP {resp.status_code} ({ms}ms) — will use fallback")
    except Exception as e:
        warn(f"{label}: unreachable ({str(e)[:60]}) — Reflexivity tab will use price-only fallback ✅")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 4. REDIS — Polymarket live feed
# ═══════════════════════════════════════════════════════════════════════════════

section("4️⃣ Redis (Polymarket Live Feed)")

try:
    import redis
    import os

    redis_url  = os.environ.get("REDIS_URL", "redis://localhost:6379")
    r          = redis.from_url(redis_url, socket_connect_timeout=3)
    t0         = time.time()
    pong       = r.ping()
    ms         = int((time.time() - t0) * 1000)

    if pong:
        # Check for Polymarket stream keys
        edge_keys   = r.keys("edge_signals*")
        stream_keys = r.keys("polymarket*")
        ok(f"Redis connected · {ms}ms · {len(edge_keys)} edge keys · {len(stream_keys)} polymarket keys")

        if edge_keys:
            # Show latest edge signal
            latest = r.xrevrange(edge_keys[0], count=1)
            if latest:
                entry_id, fields = latest[0]
                ok(f"Latest edge signal: {dict(fields)}")
        else:
            warn("No edge signals in Redis yet — scanner may not be running")
    else:
        warn("Redis connected but ping failed")

except ImportError:
    warn("redis-py not installed — `pip install redis`")
except Exception as e:
    warn(f"Redis unavailable: {str(e)[:80]} — Polymarket tab will show static data")

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SCHWAB API — Real-time data (optional)
# ═══════════════════════════════════════════════════════════════════════════════

section("5️⃣ Schwab API (Real-time — Optional)")

import os

schwab_key    = os.environ.get("SCHWAB_APP_KEY", "")
schwab_secret = os.environ.get("SCHWAB_APP_SECRET", "")
token_file    = "./schwab_token.json"

if not schwab_key or not schwab_secret:
    warn("SCHWAB_APP_KEY / SCHWAB_APP_SECRET not set in Replit Secrets → using Yahoo Finance (15-min delay)")
elif not os.path.exists(token_file):
    warn(f"Schwab credentials found but no token file ({token_file}) → run `streamlit run schwab_oauth_page.py` to authenticate")
else:
    try:
        import json
        with open(token_file) as f:
            token_data = json.load(f)
        ok(f"Schwab token file exists · keys: {list(token_data.keys())[:4]}")
        warn("Token validity not verified here — run the app to confirm live data")
    except Exception as e:
        fail("Schwab token file unreadable", str(e))

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 6. DATA FRESHNESS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

section("6️⃣ Data Freshness Summary")

freshness_data = []
for sym, result in yf_results.items():
    if result:
        status = ("🟢 Fresh" if result["staleness_days"] <= 1
                  else "🟡 Weekend gap" if result["staleness_days"] <= 3
                  else "🔴 Stale")
        freshness_data.append({
            "Symbol":    sym,
            "Price":     f"${result['price']:,.2f}",
            "Last Data": f"{result['staleness_days']}d ago",
            "Latency":   f"{result['ms']}ms",
            "Status":    status,
        })
    else:
        freshness_data.append({
            "Symbol": sym, "Price": "N/A",
            "Last Data": "N/A", "Latency": "N/A",
            "Status": "❌ Failed"
        })

if freshness_data:
    st.dataframe(pd.DataFrame(freshness_data), use_container_width=True, hide_index=True)

st.caption(
    "🟢 Fresh = data from today or yesterday  ·  "
    "🟡 Weekend gap = normal (markets closed Sat/Sun)  ·  "
    "🔴 Stale = potential issue"
)

st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
# 7. OVERALL VERDICT
# ═══════════════════════════════════════════════════════════════════════════════

section("7️⃣ Overall Verdict")

yf_ok      = any(v is not None for v in yf_results.values())
imports_ok = all_imports_ok

if imports_ok and yf_ok:
    st.success(
        "✅ **SYSTEM READY** — All imports pass, Yahoo Finance is live. "
        "Pull latest code from GitHub and run `streamlit run app.py`"
    )
elif not imports_ok and yf_ok:
    failed_imports = [k for k, v in import_results.items() if not v]
    st.error(
        f"❌ **IMPORTS BROKEN** — Fix these before running the app: "
        f"{', '.join(failed_imports)}"
    )
elif imports_ok and not yf_ok:
    st.error(
        "❌ **DATA UNAVAILABLE** — Imports OK but Yahoo Finance is not responding. "
        "Wait 30s and re-run this check."
    )
else:
    st.error("❌ **BROKEN** — Both imports and data sources failing. Check Replit environment.")

st.markdown("---")
st.caption(
    "💡 Tip: Bookmark this page and run it whenever you see errors. "
    "It tells you exactly what's broken so fixes are targeted."
)
