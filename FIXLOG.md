# BitcoinSage — Dashboard Hardening Fix Log

Branch: `global/dashboard-hardening` (local only — not pushed)
Base: `a08553d` (GitHub `main`, Replit push 2026-10-19 13:16 ET — confirms GitHub was updated today)

Smoke test used after every step (`/workspace/bs_tools/smoke.py`): runs `app.py` headless with
Streamlit `AppTest` against live Yahoo Finance data and records uncaught exceptions and every
`st.error` box. Plus `python -m py_compile` on touched files and `pytest tests/`.

## Baseline (before any change)
- `requirements.txt` was missing **scipy** → with only `requirements.txt` installed, `app.py` and 9 modules fail to import
  (`ModuleNotFoundError: scipy`). Replit happened to work because `pyproject.toml` lists scipy.
- App ran in 35 s with 0 uncaught exceptions but these tabs showed error boxes:
  - **RIOT Protection**: `'RIOTProtection' object has no attribute 'config'`
  - **Backtesting → Options**: `cannot import name 'DEFAULT_POSITIONS' from components.personal_portfolio`
  - **Reflexivity → Coupling**: `No module named 'statsmodels'`
  - **Risk Center → Beta**: "Unable to calculate beta analysis - insufficient data overlap"
- Fake defaults visible on screen: `Beta to Bitcoin 1.50` (hardcoded fallback), `₿ BTC Correlation 50/100` on all 9 stocks,
  `Miner Beta 1.00×`, `Breakeven BTC $30,000` (fixed constant), stress-test "Portfolio Value After $-5" (sum of share prices × 1.5 fake beta).
- Root cause of the BTC bugs (verified): Yahoo stamps BTC-USD bars at 00:00 **UTC** and US stocks at 00:00 **America/New_York**,
  so `index.intersection` → **0 shared days** (3-month RIOT vs BTC test: `shared raw: 0`). Intraday (1h) data never overlaps either.
- `_render_decision_summary` existed in app.py but was never called.
- `BITF` → `KEEL` rename was already done in the latest Replit push (no `BITF` references remain).

## Steps

### Step 0 — Dependencies
- Added `scipy>=1.16.2` to `requirements.txt` (was only in `pyproject.toml`; `scripts/post-merge.sh` installs from requirements.txt).
- Test: all modules import with requirements.txt + scipy. ✅

### Step 1 — Fix Bitcoin date alignment; remove fake beta/correlation defaults (Priority A)
- New `utils/market_data.py`: `to_daily`, `to_stock_calendar` (BTC carried onto stock trading days → weekend moves fold into Monday),
  `aligned_returns`, `beta_corr` (returns `None` under 20 shared days), `align_frame`, cached `fetch_daily_closes` (15-min cache).
- New `tests/test_market_data.py` (5 tests): reproduces the original 0-overlap bug, checks weekend folding, beta recovery, insufficient-data → None.
- `utils/risk_engine.py`: beta analysis uses aligned daily data; stress test now measures the basket's real 1y beta to BTC
  (hardcoded `beta = 1.5` fallback removed → returns an error message instead). Stress test is expressed per $10,000 invested
  (the old "portfolio value" was the sum of share prices, e.g. "$99", and could go negative); a stock can't fall more than 100%.
- `components/risk_center.py`: stress tab shows "Insufficient data" when beta can't be measured; relabelled "Bitcoin Drop / Expected Basket Drop".
- `components/reflexivity_dashboard.py`: prices aligned on the stock calendar; removed fake `corr=0.0`, `beta=1.0`,
  and fixed `$30,000` breakeven fallbacks (margin shown as n/a and dropped from the index with weights rescaled when
  difficulty data is unavailable); replaced plotly `trendline="ols"` (needed statsmodels, crashed the Coupling tab) with a numpy fit.
- `utils/next_mover_engine.py` + dashboard: BTC factor computed from aligned 3-month daily data (was hourly UTC vs hourly NY → every stock 50/100).
  If unavailable, shows "n/a" and the composite re-weights the other factors.
- Smoke result: 0 exceptions. Now live: Beta to Bitcoin 1.10 (was fake 1.50), BTC Correlation 45–65/100 per stock (was 50 for all),
  Miner Beta 1.10× (was 1.00×), Coupling 0.53, Coupling tab no longer errors. RIOT 1y corr to BTC = 0.49 (matches the separate RIOT analysis). ✅

### Step 2 — Fix crashing tabs and hardcoded RIOT position
- `components/personal_portfolio.py`: export `DEFAULT_POSITIONS` alias → Backtesting "Options Strategy" tab no longer crashes.
- `components/riot_protection.py`: `self.config` was never defined (crashed the Income Scenarios tab). Shares/cost basis are now
  read from the Portfolio tab's saved positions every render (no more hardcoded 10,975 / $18.22 / "109 contracts" in ~15 places).
  The hardcoded "Total Investment $199,755" was also wrong arithmetic (10,975 × $18.22 = $199,964).
- Replaced the stale hardcoded expiration advice ("Use 31 OCT 25 (39 days)", "26 SEP / 3 OCT / 10 OCT" — dates from 2025) with the
  live listed expiry closest to 30–45 days; the covered-call/collar tables now load that expiry's chain (previously they used the
  nearest weekly while telling the user to use a 30–45 day option). Broker instructions show the user's real contract count
  (was "100 contracts"). Removed the unsupported "$2,000–$5,000+ monthly income" claim.
- `components/reflexivity_dashboard.py`: blockchain.info returns `[{"x":..,"y":..}]` but the parser expected pairs → hashrate and
  difficulty were *always* empty. Fixed; estimated breakeven (labelled as an estimate with its assumptions) now shows ≈ $76,000.
- Smoke result: 0 exceptions, **0 error boxes** (baseline had 3). ✅

### Step 3 — Centralize tickers and the BITF → KEEL rename (Priority B)
- New `utils/tickers.py`: `TICKER_ALIASES` (`BITF → KEEL`), `MINING_STOCKS` (sidebar), `WATCHLIST` (9-stock engines),
  `CORRELATION_UNIVERSE` (peer groups for the RIOT map), `resolve*()` helpers. New `tests/test_tickers.py` (4 tests).
- `app.py`, `utils/trade_signal_engine.py`, `utils/next_mover_engine.py`, `components/trade_signals_dashboard.py` now import
  from it (3 duplicated lists removed).
- `components/personal_portfolio.py`: saved positions, targets and stop-losses are passed through `resolve_keys`, so a local
  `data/positions.json` on Replit that still says `BITF` is shown as `KEEL` (share counts untouched; nothing invented).
- Smoke: 9 tests pass, 0 exceptions, 0 error boxes. ✅

### Step 4 — RIOT Correlation Map + consolidate correlation panels (Priority C/D)
- New `utils/riot_correlation.py` (ported from the standalone RIOT study): ranks 26 tickers vs RIOT over 1Y and 3M (log returns on
  RIOT's trading days, BTC weekend moves rolled into Monday), quarter-by-quarter stability badge (steady / flips), group averages,
  and a divergence check (RIOT's last 20 trading days vs its 5 closest miners). New `tests/test_riot_correlation.py` (2 tests).
- New `components/riot_correlation_map.py` tab "🔗 RIOT Correlation Map": headline metrics, plain-English verdict, divergence alert,
  ranked chart (1Y bars + 3M markers, coloured by group), group comparison, inverse/hedge panel (VIX, UUP, USO, TLT with
  stable/flips badge and per-quarter numbers), full table + CSV download, data source and computed-at timestamp.
- Live result reproduces the earlier analysis: CLSK 0.84, KEEL 0.81, HUT 0.80, MARA 0.78 …; miners avg 0.76, AI data centers 0.60,
  Bitcoin 0.49; VIX −0.50 (steady), UUP −0.28 and USO −0.25 (flip), TLT +0.17.
- Removed duplicates: Market Overview correlation heatmap + "Correlation Insights", Risk Center "Correlation" tab, Sentiment tab
  "Crypto Market Correlation" (was always empty — same alignment bug), and Market Overview's BTC/VIX/S&P strip (duplicate of the
  Command Center). Each now shows a one-line pointer to the new tab.
- Smoke: 11 tests pass, 0 exceptions, 0 error boxes; new tab metrics populated. ✅

### Step 5 — "🧭 My Plan": one canonical Hold / Trim / Sell / Rotate call (Priority D/E)
- New `utils/holding_advisor.py` (pure logic, `tests/test_holding_advisor.py` 6 tests) and `components/holding_plan.py` (first tab).
- Inputs (all live or user-saved): price vs 200-day/50-day average, drawdown from 52-week high, Bitcoin vs its 200-day average,
  VIX level, RIOT-vs-peers divergence (from the correlation module), gain vs cost basis, concentration (% of saved holdings),
  the user's own target price (`portfolio_targets.json`), Yahoo analyst low/avg/high targets (shown as context, not scored).
  Missing inputs are listed as missing and lower confidence — never defaulted.
- Rules tuned for a risk-averse 2030 holder: default HOLD; TRIM when own target hit (25%), concentration > 40% (10%), or big gain
  + ≥3 risk points (20%); SELL only at ≥5/8 risk points; ROTATE a slice only when RIOT lags peers by >15% and a peer is in an uptrend.
  Each call shows reasons, confidence, risk points and "What would change my mind" price levels. When a trim would realise a loss
  it says so and offers the minimum alternative (stop adding).
- Path to 2030: plan-year slider, editable Bear/Base/Bull yearly-return assumptions (clearly labelled as assumptions), a data-driven
  ±1σ range from the stock's own volatility, analyst 12-month markers, the user's target line, and position value in each scenario.
  Plus a staged-exit education box and an "all holdings at a glance" table.
- `app.py`: removed the never-called `_render_decision_summary`; Command Center rewritten (Bitcoin, VIX with calm/nervous/fear,
  selected miners' real daily change — the old "Sector Pulse" compared the last two *hourly* bars of a price-weighted average —
  data freshness, and a one-line "Your RIOT plan right now" pointer). Tabs reordered: long-term tabs first, trading tools after;
  "New here?" guide added. Trade Signals labelled as short-term.
- Live result today: RIOT **TRIM ~10% (Medium, 3/8 risk)** — driven by 80% concentration, price 28% below the 200-day average and
  a −51% drawdown; Bitcoin above its 200-day and calm VIX keep it from SELL.
- Smoke: 17 tests pass, 0 exceptions, 0 error boxes. ✅

### Step 6 — Beginner help, remaining static/mislabelled numbers, speed (Priorities F/G/D)
- New `utils/explain.py`: plain-English glossary (beta, correlation, VIX, drawdown, volatility, 200-day average, cost basis,
  target price, analyst targets, projections, decoupling, reflexivity, VaR, Monte Carlo, how the recommendation works).
  Used as `help=` tooltips on metrics and "ℹ️ What is this?" expanders in My Plan, Correlation Map, Risk Center, Reflexivity, Portfolio.
- Risk Center: VaR and Monte Carlo now use a $10,000 equal-weight basket (the old "portfolio value" was the sum of share prices);
  VaR % is now scaled to the chosen horizon like the $ figure; "Sharpe Ratio" relabelled "Return / Risk" with an honest tooltip.
- Market Overview performance table rebuilt from daily closes (old "Daily %" was the last *hour*, "Week %" the last 5 hours,
  volatility annualised from hourly returns). Adds 3-month, 1-year and drawdown columns.
- Portfolio: removed hardcoded "RIOT (10,975 shares) + KEEL (1,700 shares)", "9 mining positions", "your HIVE plan",
  "$2,000–4,000/month per position"; income projections now use the expiry closest to 30 days (was the nearest weekly × 12)
  and warn that at-the-money calls risk having shares called away.
- Trade Signals: targets were Fibonacci *extensions above the 60-day high* even after a 40% crash, and the stop could sit 1%
  under price → risk/reward like 17:1 and 121:1. Now: next Fibonacci levels above entry (retracements below the high), stop ≥ 1 ATR
  below entry; labels show which level. New `tests/test_trade_targets.py`.
- Polymarket: the Active/Analysis/Mining tab strip was rendered twice (first copy empty) — now one strip, live-arb last.
- Caching: `fetch_daily_closes`, the correlation map and analyst targets no longer cache failed/rate-limited downloads.
- **Speed / rate limits:** during testing Yahoo returned "Too Many Requests" because every one of the 15 tabs ran on every click.
  Top-level `st.tabs` replaced with a horizontal section selector — only the chosen section runs. Short-term tools are labelled as such.
- Smoke (now visits all 15 sections one by one): 18 tests pass, 0 exceptions, 0 failure boxes in any section
  (remaining red boxes are intentional indicators like "Trading Below VWAP"); whole sweep 41 s, most sections < 2 s. ✅

### Final verification
- `pytest tests/` — 18 passed (market-data alignment, tickers, RIOT correlation, holding advisor, trade targets).
- `python -m py_compile` on every touched file — OK.
- `streamlit run app.py --server.headless true` — server starts, `/_stcore/health` = ok, `/` = 200.
- AppTest sweep of all 15 sections — 0 uncaught exceptions, 0 failure boxes.
- `origin/main` still at `a08553d` (no new pushes while working). Nothing pushed; branch is local only.

## Remaining risks / not done
- **Yahoo Finance rate limits**: the app still relies on many unauthenticated Yahoo calls (now far fewer per click). If Yahoo
  throttles, sections show clear "unavailable" messages rather than fake numbers. Schwab real-time path untouched (credentials not touched).
- **Sentiment** still shows "Neutral (50)" when the Alpha Vantage free tier is exhausted (pre-existing, already labelled in the UI;
  it's the same for every stock so it doesn't change rankings).
- A few deep technical helpers still fall back to neutral values on errors (e.g. RSI/Stochastic = 50 in `advanced_ta_dashboard.py`,
  probability = 50 in `weekly_outlook.py`). Low impact; not part of the hold/sell call.
- The Hold/Trim/Sell rules and the Bear/Base/Bull yearly-return defaults (−20% / +5% / +25%) are judgement calls, clearly labelled
  and editable — not predictions. The breakeven/margin estimate assumes 30 J/TH rigs and $0.05/kWh.
- "Share of portfolio" only counts holdings saved in the app, not the user's whole net worth.
- `use_container_width` deprecation warnings (Streamlit pinned at 1.49.1, still works; removal is after 2025-12-31 in newer versions).
- The section selector replaces tabs: users click a section name at the top instead of a tab (same order/names).

---

# Branch `global/signals-v2` (based on origin/main @ 93e344a — no new Replit pushes found on 2026-10-19)

Same test gate after every step: `py_compile`, `pytest tests`, `streamlit run --server.headless` health check
(`/workspace/bs_tools/headless.sh`), and the AppTest sweep of all 15 sections (`run_smoke.sh`).
Note: the smoke "error boxes" count per section (Risk Center 6, Polymarket 18, …) is content styled with
`st.error` (e.g. "Large drawdown"), unchanged from the baseline; the filtered failure list stays empty.

## V2 Step 1 — Good-time-to-add (ADD / WAIT) signal
- `utils/holding_advisor.py`: Wilder RSI(14) (`rsi_wilder`, `rsi_series`) added to `compute_facts`;
  new pure `add_rule()` (scalars only, so the backtest uses the exact same rule) and `add_signal()`.
  ADD = at least 2 of 3 "on sale" checks (RSI < 35; ≥20% below 200-day; ≥40% below 52-week high)
  AND all 3 backdrop checks (BTC ≥ −5% vs its 200-day; VIX < 25; equal-weight miner-peer basket ≥ −10% vs its 200-day).
  Never ADD if the stock is > 40% of the portfolio — says so explicitly. Outputs confidence and trigger price levels.
- `market_risk_score()` mirrors the market-only risk points of `advise()` (test asserts they match) for the backtest.
  Existing Hold/Trim/Sell/Rotate logic untouched.
- `components/holding_plan.py`: new "➕ Good time to add more?" block inside My Plan; glossary entries `rsi`, `add_signal`.
- Live today: RIOT = WAIT (High) — 80% of portfolio > 40% cap; also peer basket −41% vs its 200-day.
- Tests: 24 pass (6 new). Headless: ok. Smoke: 0 exceptions, 0 failure boxes; My Plan shows the new block.
