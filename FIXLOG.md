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

## V2 Step 2 — Alerts when the call changes
- New `utils/call_tracker.py`: saves the latest call per ticker (HOLD/TRIM/SELL/ROTATE + ADD/WAIT, confidence, price,
  every check's status) to `data/last_calls.json` (data/ is already gitignored). A flip is stored as a pending change
  (old vs new + which checks flipped) and keeps showing until "Got it"; last 50 changes kept as history.
- New `utils/notifier.py`: optional Telegram (`TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`) and SMTP email. OFF by default;
  sends only if enabled in My Plan → 🔔 Alert settings AND secrets are set AND not under test
  (`PYTEST_CURRENT_TEST`/`BITCOINSAGE_NO_NOTIFY`). Errors report only the exception type (Telegram URLs contain the token).
  Each change is sent at most once.
- My Plan: orange "🔔 What changed since last check" banner at the top; settings + history expander; glossary `call_alerts`;
  Replit Secrets how-to in replit.md.
- Tests: 26 pass (2 new: change detection/persistence/ack; notifier off-by-default and blocked under pytest).
  Headless ok; smoke 0 exceptions / 0 failure boxes (run with BITCOINSAGE_NO_NOTIFY=1). Manual AppTest: seeded an older
  HOLD call → banner showed "HOLD → TRIM, Concentration warn → bad"; "Got it" cleared it. No message was sent at any point
  (no secrets configured on the box, alerts disabled). Test state file removed afterwards.

## V2 Step 3 — Event calendar
- New `utils/event_calendar.py`: FOMC 2026–2027 (Fed schedule, decision day = 2nd day, SEP meetings marked) and CPI
  release dates Nov 2026–Dec 2027 (BLS schedule), both hardcoded with source URLs and `SCHEDULES_LAST_VERIFIED = 2026-10-19`
  (fetched and checked today). Earnings from Yahoo `Ticker.calendar` for the selected stock + RIOT, MARA, CLSK, HUT, KEEL,
  CIFR, WULF, IREN, CORZ (marked "est."). Next halving from live block height (blockchain.info, mempool.space fallback):
  block 1,050,000; date assumes 10-minute blocks.
- My Plan: "⏰ Coming up in the next 14 days" line above the checks, plus a "📅 Event calendar" table (next 120 days +
  halving) with sources and a plain-English glossary entry. Cached (earnings 6h, block height 30m); empty/failed fetches
  are not cached and degrade to a note.
- Live today: FOMC Oct 28 (9d), RIOT earnings Oct 29 (10d, est.), CIFR Nov 2 (14d) flagged; CPI Nov 10; halving est.
  Apr 11 2028 (height 972,201, 77,799 blocks to go).
- Tests: 29 pass (3 new: halving math, schedule sanity, 14-day flagging). Headless ok; smoke 0 exceptions / 0 failure boxes.

## V2 Step 4 — Signal track record (backtest)
- New `utils/signal_backtest.py`: replays the market rules day by day on 10y of Yahoo daily closes, evaluating the last
  5 years for RIOT. Uses the *same* functions as the live call (`add_rule`, `market_risk_score`, `rsi_series`).
  No-lookahead safeguards: rolling/EWM indicators only; Bitcoin lagged one day (Yahoo's BTC bar closes ~4h after the
  US close); entries at the NEXT day's close; signals collapsed into episodes (20-day cooldown; a state already on at the
  window start is not counted). A test proves features on past days are identical with or without later data.
- Shows ADD, SELL (≥5 risk pts) and Caution (≥3) signals with 1/3/6/12-month forward returns, hit rates, an "any day
  (just holding)" baseline, a simple follow-the-rules vs hold equity curve, every past signal (CSV download), sample-size
  trust labels and a glossary entry on limits. Cached 24h; failures not cached. One-line summary under the verdict card.
- **Result today (honest):** ADD 5 signals, 6M avg −8% vs +18% any day; SELL 8 signals, 6M avg +33% (selling would have
  hurt); Caution 7 signals, +48%. Follow-the-rules −70% vs hold −55% (no costs). All samples small → trust "low".
  The market-timing rules have **no demonstrated edge** on RIOT; the dashboard now says so.
- Not replayable: concentration/target/cost-basis rules, analyst targets, the 40% size cap. Peers = today's WATCHLIST
  (mild survivorship bias).
- Tests: 32 pass (3 new: no-lookahead, episodes/forward-return timing, end-to-end shapes). Headless ok; smoke 0
  exceptions / 0 failure boxes (one intermediate run hit Yahoo "Too Many Requests" in Options/Flow after ~10 back-to-back
  sweeps; re-run after a pause was clean).

---

# Signals audit — Trade Signals, "AI Predictions", Sentiment & News (branch `global/signals-audit`, Oct 19 2026)

Base: origin/main 5c63f21 (includes the V2 ADD/WAIT, alerts, event calendar and track record).
Every step: `py_compile`, all tests, headless `streamlit run` health check, AppTest smoke visiting all 15 sections.

## Audit findings (before fixes, live data Oct 19 2026)
| Feature | File | Works live? | Real or fake? | Actual AI/ML? | Contradictions |
|---|---|---|---|---|---|
| 🚦 Trade Signals BUY/HOLD/SELL | utils/trade_signal_engine.py | Yes | Real rules (8 indicators); fell back to fake `HOLD 40%` + RSI 50 on missing data; sentiment factor always 0 without an Alpha Vantage key | No — points system | Own 3-month download; SELL cards showed *long* entry/stop/targets labelled "Short Entry" |
| 🎯 "AI Predictions" (Next-Mover) | utils/next_mover_engine.py | Yes | Real rules; "Run Probability" was just the weighted score with a % sign; missing factors filled with 50 | **No** — weighted score, no model | RSI used a simple-average formula → **RIOT RSI 10.7 here vs 27.1 on Trade Signals / My Plan** |
| 📈 Technical Analysis RSI/MACD | components/advanced_ta_dashboard.py | Yes | Real; RSI 50 on error | No | Same RSI mismatch (10.7); MACD with adjust=True EMAs (differs from other tabs) |
| 🔮 Forecast Center targets | components/weekly_outlook.py | Yes | **Fake**: target = price × (1 ± \|score\|×5%×horizon); "probability"/"confidence" = 50 + \|score\|×8/×10. RIOT: 1W $8.31 (−40%) at "95%", 4W **$1.61 (−88%) at "86%"**, outside its own "range" $11.73–16.21. "Options flow" score used no options data; "Dark pool" score used no dark-pool data | No | A third BUY/SELL ("Avoid / Hedge") contradicting My Plan (TRIM) and Trade Signals (HOLD) |
| 📰 "Mining Sector Sentiment" | components/sentiment_analysis.py | Yes | **Mislabelled**: price momentum vs BTC, not sentiment; 5.0/10 on error | No | Duplicated Next-Mover relative strength |
| 📰 News | components/sentiment_analysis.py | — | **No news at all** in the "Sentiment & News" tab | — | — |
| 😨 Fear & Greed | components/sentiment_analysis.py | Yes | Home-made composite (VIX/BTC/DXY/gold/SPY step points); silent 50 on error. Today 50 vs the published Crypto F&G 59 | No | Forecast Center treated "greed" as both bullish (+0.5) and bearish (−0.5) |
| Alpha Vantage sentiment | utils/sentiment_analyzer.py | Key not set on the box | AV's current rate-limit reply (`Information`) slipped through as an empty feed → silent Neutral 0.0 | AV's NLP is real when it works | Next-Mover warning blamed "free-tier limit" even when no key was set |
| 🎲 Monte Carlo outlook | utils/risk_engine.py | Yes | Unseeded (numbers changed every rerun); drift = past average return; said "Good time to hold or add" / "Consider reducing exposure" | No | Buy/sell advice competing with My Plan |
| 🌊 "Dark pool" | utils/unified_data_fetcher.py | Yes | Ordinary Yahoo volume + VWAP labelled as dark-pool activity | No | — |
| 🧭 My Plan HOLD/TRIM/SELL/ROTATE + ADD/WAIT, track record | utils/holding_advisor.py, signal_backtest.py | Yes | Real, transparent rules; backtest honest (no edge shown) | No (rules + backtest) | Source of truth — unchanged |
| Path-to-2030 bands | components/holding_plan.py | Yes | Real (editable scenarios + volatility band) | Statistical, labelled | — |

**Is there an actual AI prediction anywhere? No.** No model is trained or called and no LLM API is used. Every
"prediction" is rules arithmetic. The only statistical forecasts are My Plan's volatility band and (new) the Forecast
Center range, both labelled as such.

## Step A1 — One source of truth for prices and indicators
- New `utils/indicators.py` (Wilder RSI shared with My Plan, adjust=False MACD, Bollinger, Stochastic, ATR, SMA, volume
  ratio; `None` when data is short — never RSI 50). New `utils/signal_hub.py`: cached 2-year daily OHLCV (15 min, failures
  not cached), indicator snapshot, `short_term_signal()`, `long_term_call()` (wraps My Plan), `reconcile()` wording.
- Trade Signals, Next-Mover and Technical Analysis now read bars from the hub and indicators from `utils/indicators`.
  Live after fix: **RIOT RSI 27.1 on all four tabs** (was 27.1 / 10.7 / 10.7 / 27.1); all 9 miners agree likewise.
- Missing data → `N/A` signal (grey) instead of a fake HOLD; Next-Mover drops missing factors and re-weights (no 50s).
- "🎯 AI Predictions" renamed **🎯 Next-Mover Ranking** with a plain statement: rules-based, not AI, score not a probability,
  not backtested. "Run Probability" removed. Top pick no longer recomputes the whole ranking twice.

## Step A2 — Real news and an honest sentiment score (no new keys)
- New `utils/news_sentiment.py`: headlines from Yahoo Finance search + Google News RSS (7 days, de-duplicated), scored by a
  transparent finance keyword list (score −1…+1, Bullish ≥ +0.15, Bearish ≤ −0.15); uses Alpha Vantage NLP instead when a
  key is set and works. Published **Crypto Fear & Greed Index** (alternative.me). Unavailable → `n/a`, never neutral.
- `components/sentiment_analysis.py` rewritten: tone table for RIOT + selected miners, clickable headlines with date,
  publisher and the words that drove the score, F&G gauge with yesterday/week-ago. Removed the momentum-as-sentiment table,
  the home-made F&G and dead code.
- Trade Signals and Next-Mover use the same news numbers (live: RIOT −0.06 Neutral, 38 headlines; MARA −0.27 Bearish).
- `utils/sentiment_analyzer.py`: AV `Information`/`Note` replies are now errors.

## Step A3 — Forecast Center: honest statistical range
- New `utils/stat_forecast.py`: centre = today's price (no direction guess), 68%/90% bands from last-year daily volatility
  × √days, plus a **point-in-time backtest of the hit rate** over 3 years. RIOT live: 1-month 68% range $10.84–$18.00
  (held 70% of the time), 90% $9.21–$21.20 (held 97%); RIOT finished a month higher 50% of the time (why no direction).
- `components/weekly_outlook.py` rewritten: range table, fan chart, and "Every signal in one place" (My Plan, Trade Signals,
  news tone, reconciled). Removed invented targets/probabilities/confidence and the mislabelled options/dark-pool scores.

## Step A4 — Reconcile tabs; remove competing advice
- My Plan: expander "🔗 How the short-term tabs see RIOT right now" (Trade Signals, news tone, reconciliation sentence).
- Trade Signals: My Plan banner at the top for your holdings (e.g. "Your long-term plan for RIOT: TRIM … short-term HOLD");
  SELL cards no longer show long-trade levels or "Short Entry"; "Confidence %" explained as not a probability.
- Command Center: one caption with the short-term signal and news tone, marked as not overriding the plan.
- Monte Carlo: fixed seed (stable numbers) and descriptive text instead of "add"/"reduce" advice.
- Institutional Flow: honest caption that "dark pool" readings are estimated from ordinary volume.
- Beginner help: `utils/explain_signals.py` (signal hierarchy, trade signal, news tone, fear & greed, next-mover,
  statistical range), merged into `GLOSSARY`/`HELP` with a 2-line change in `utils/explain.py`.

## Tests and verification
- New: `tests/test_signal_consistency.py` (RSI identical across My Plan, Trade Signals, TA, Next-Mover and the hub; MACD;
  price; N/A on no data; reconcile wording; forecast centre = My Plan price; Monte Carlo stable + no advice),
  `tests/test_news_sentiment.py`, `tests/test_stat_forecast.py` (coverage ≈ 68%/90% on a random walk; target inside range).
- **55 tests pass** (32 before). Headless health ok. Smoke: 0 exceptions, 0 failure boxes, all 15 sections load; Strategy Lab
  error boxes 2 → 0.

## Remaining risks
- Headline keyword tone is crude (misses negation/sarcasm; some non-English headlines score 0) and is not validated as
  predictive — labelled as such. Google News RSS / Yahoo search are unofficial endpoints and may change or rate-limit.
- Trade Signals and Next-Mover rules remain untested on history; only My Plan has a track record (and shows no timing edge).
- Volatility bands assume recent volatility persists; crashes are fatter-tailed than the bands (hit rates shown).
- Each section now shares one 2-year download per ticker; the first load after the 15-minute cache expires is slower.

# BTC-2030 — Bitcoin scenarios to 2030 and the RIOT↔BTC link (branch global/btc-2030)

**Request:** "there is no Bitcoin price correlation with future price prediction of the stocks… e.g. in 2030 if RIOT is at a
bull of $40 or higher, show the price of bitcoin at that price. Make sure the BTC prediction takes policy, politics,
financial adoption, rising inflation etc. into account."

| # | Gap found | Fix |
|---|-----------|-----|
| B1 | No Bitcoin view anywhere in the 2030 plan. My Plan's Bear/Base/Bull were RIOT-only yearly returns that quietly assumed something about BTC | `utils/btc_scenarios.py`: Bear/Base/Bull/Super-bull from the **live** BTC price. Growth/yr = sum of 8 editable drivers (adoption trend, 2028 halving, ETF/institutional, US policy, money/inflation/rates, corporate treasuries, global adoption, risks). Each driver has a beginner tooltip and dated sources (Fed 2026-09-16, BLS CPI 2026-10-14, Fed H.6 M2 2026-09-22, Senate cloture 2026-09-15, DGI 2026-10-15, SBR EO 2025-03-06). Published forecasts (ARK, Standard Chartered, Bernstein) are shown only as reference markers with links |
| B2 | Only a daily correlation (~0.5) existed, which says nothing about 2030 | `utils/riot_btc_link.py`: quarterly log-return fit (beta 1.12 ± 0.21, R² 0.47, 2018–2026), level-fit stray σ and AR(1) persistence for horizon ranges, rolling 3-yr beta/R² (0.17–1.73). The **last 3 yrs beta is 0.17 (R² 0.01)**, so both regimes can be selected. Point-in-time: `as_of`, with a leakage test |
| B3 | No way to answer "what BTC price lines up with RIOT $40" | Forward (BTC path → RIOT with range) and inverse (RIOT $X → BTC needed with range) mappings, exact inverses (tested). Non-BTC factors: dilution (default = measured 12-mo share growth from Yahoo), hashprice headwind, energy, AI/HPC uplift. Shows "N/A — Bitcoin alone can't plausibly do it" when BTC would need over 100× |
| B4 | Two 2030 views could disagree unexplained | Reconciliation rows give the BTC price each My Plan Bear/Base/Bull case implies. A two-panel chart overlays the BTC paths, RIOT-implied paths and the My Plan dashed lines, with a caption explaining why they differ |
| B5 | Missing context | Halving-cycle table computed from data (peaks 17.2/17.9/17.5 months after halving; falls of −83%/−77% afterwards). Next-halving estimate from the live block height. Peak window Apr–Oct 2029, so 2030 was historically a down year. Dated policy/macro watchlist (FOMC, CPI, midterms, new Congress/CLARITY, halving, 2028 election, SBR bill). Sell/rotate milestone checklist with live status |

**Single source of truth:** today's RIOT and BTC prices come from the same My Plan closes. Long history comes from
`signal_hub.get_ohlcv(…, "max")`, and share counts from the new `signal_hub.get_shares`. Every data failure shows N/A; the
panel is wrapped so it can never break My Plan.

**Tests:** `tests/test_btc_2030.py` (16): scenario sum/compounding/ordering, driver edits are isolated, no live price
means no scenarios, every source has a URL and date, forward↔inverse round trip and range direction, unreachable/tiny
beta, factor signs, synthetic beta recovery, **no future leakage** (future data ×50 leaves the point-in-time fit
unchanged), minimum history, horizon σ bound, dilution, halving-cycle detection. The suite is 71 passed.

**Risks / limits:** driver numbers are assumptions, not data. The beta is unstable (regime change after the AI pivot).
The range is a ±1σ historical stray, not a guarantee. The halving pattern rests on 3 cycles. Published targets come from
bullish shops. Hardcoded policy dates and facts were verified 2026-10-19 and need a yearly refresh.

# Reflexivity v2 — honest, backtested, Riot-aware (branch global/reflexivity-v2)

**Request:** "Take a look at the reflexivity tab… is there room for improvement and greatness?" Both rounds of the SME review were approved.

| # | Problem (old file:line) | Fix |
|---|---|---|
| R1 | Basket = average of share PRICES (old L214); HUT ($68) was 70% of it | `rx.equal_weight_index` builds the basket from daily RETURNS. Adds a focus stock (default: largest miner holding) and a basket that defaults to the miners you hold |
| R2 | Forecast/advice wording ("Bullish loop active", "momentum likely to continue", "consider hedging", "historically strong buy signal") was never backtested. A quick check showed "Expansionary" was followed by −17% / 63 days | Phases are now descriptive only (Boom / Bust / Miners lagging / Miners leading / No clear loop), each with a plain sentence. The banner (`signal_reconcile.render_reflexivity_banner`) says My Plan is the final word |
| R3 | Margin used fixed 30 J/TH, $0.05/kWh, 3.125 BTC and no fees; it was called "all-in" | Editable J/TH and $/kWh. Subsidy comes from the live block height and fees from mempool.space (last 1,008 blocks). Labelled power-only. Shows Riot's reported cost to mine: $49,912 ex-D&A / $90,631 incl. (Q2 2026, cited), the derived power cost per BTC, a difficulty-adjusted estimate, and breakeven after the 2028 halving |
| R4 | blockchain.info was uncached; data was 5 days old without saying so | `utils/network_data.py`: mempool.space first, blockchain.info as fallback, cached 1 h, "data as of" shown everywhere |
| R5 | The difficulty loop was presented as reflexive; the "Expansion Proxy" label was wrong | Two diagrams: the stabilising network loop vs the reflexive capital-markets loop. Charts relabelled, hashrate and hashprice panels added |
| R6 | The 30-day beta here vs the long-run sensitivity in Bitcoin-to-2030 was unexplained | Horizon note pulls both numbers from the same `btc_2030._load_fit` |
| R7 | No backtest | `rx.phase_frame` + `rx.backtest_labels`, 2018–2026, point-in-time. The phase is acted on the next close (BTC's UTC bar ends after the NY close). Cases are non-overlapping per phase; averages use log returns; the verdict needs n≥8 and abs(t)≥2 vs a non-overlapping baseline. Covers phases, index buckets and hashprice-stress, at 63 and 126 days. **Result: no reliable difference anywhere** (RIOT and the 8-stock basket) |
| R8 | No valuation | Riot sum-of-parts from dated filing facts (`utils/riot_facts.py`): BTC held 11,380 (5,821 pledged), cash $548.9M, lease NOI $365–411M/yr from Jun 2028 for 20 yrs. Debt comes from Yahoo. Build cost, mining and other parts are user inputs with default 0. Also shows the assumption-free "market price for everything except BTC & net cash" |
| R9 | No dilution view | Share history and yearly growth (`signal_hub.get_shares`). Optional EDGAR 424B/S-3/S-8 check (`utils/edgar.py`, SEC-style User-Agent, cached 6 h); degrades to a link when blocked (403 from this box) |
| R10 | Miner stress only via a fake margin | Hashprice now vs its 2-year percentile and history (subsidy correct by date, incl. fees) |
| R11 | Loop strength not tracked | Price→next-quarter issuance (rolling 2-yr corr), BTC→next-3-month hashrate (rolling 2-yr corr), quarterly BTC beta (same as Bitcoin-to-2030) |
| R12 | — | The regime is **not** in My Plan's call (no edge). My Plan shows a one-line context caption saying why |
| Low | Rolling beta dated one day late; ">40" vs "<10" message; `pct_change` without `fill_method`; raw tracebacks; coupling shown twice; prices not from signal_hub | All fixed. The beta window now ends on the date shown (tested). Errors show a short N/A warning. Coupling appears once. Prices come from `signal_hub.get_ohlcv` |

**Tests:** `tests/test_reflexivity.py` (24): equal-weight basket uses returns, beta dating, index bounds/N/A, phases, **no look-ahead** in the phase frame, non-overlapping entries, next-day action and full windows only, a planted edge is found while noise isn't, subsidy by height/date, breakeven formula and halving doubling, hashprice, the point-in-time percentile, annuity PV, sum-of-parts arithmetic, dilution, EDGAR parser and graceful failure, cited facts. Suite: 95 passed.

**Risks:** the backtest rests on one 2018–2026 history (about 2 cycles, 12–35 cases per cell). The lease PV ignores the undisclosed build cost unless the user enters it. The difficulty-adjusted Riot cost is an estimate. EDGAR is blocked from some hosts. mempool.space and blockchain.info are free and unauthenticated, so they may rate-limit, and the tab then shows N/A. Riot facts must be refreshed after each quarterly report.

# ⚖️ Stock Verdict — one call per stock from every tab (branch global/verdict-page)

**Request:** "pull all the data from all the tabs and use it to determine what to do with the stock. I want to see only one
stock at a time with a pull-down option to select the stock." The user chose a NEW one-stock page; the other tabs are unchanged.

| # | What | How |
|---|---|---|
| V1 | New first section, the default landing page | `app.py` SECTIONS starts with "⚖️ Stock Verdict". The "New here?" guide points to it first |
| V2 | Pull-down, one stock at a time | `ticker_universe()`: holdings first (RIOT first, then by share count), then the other miners and the Correlation-Map stocks/ETFs (not ^VIX/BTC-USD/macro ETFs). The choice is kept in `session_state` across section switches. The widget is seeded from a saved copy, with **no `index=`**, because a changing index gave the widget a new identity and undid every second selection (found by AppTest, fixed before commit) |
| V3 | One verdict: HOLD / ADD / TRIM / SELL / ROTATE + confidence | `utils/verdict.py` (pure, deterministic). **Held:** action = `combine_plan(My Plan, Add/Wait)`: HOLD+ADD → ADD, otherwise My Plan's call. **Not held:** `combine_not_held`: no personal rules; SELL (= avoid) at 5+ market risk points, ADD (= small starter) if the entry rule fires, otherwise HOLD (= watch only) |
| V4 | Same answer everywhere | The evidence can only move confidence, by at most one notch (agree → up, clash ≥0.6 → down, all-N/A → down). My Plan shows "⚖️ Stock Verdict: X" from the same `combine_plan`. Tests cover 162 synthetic My Plan states × 4 evidence sets, plus the page's wiring (`build_for`) and the My Plan source. A full-app AppTest checked RIOT and MARA on both pages |
| V5 | Evidence from all tabs, weighted toward long-term/tested | Weighted (sum 100 when held): My Plan market checks 30 (backtested), your position rules 25 (personal rule), Add/Wait 10 (backtested), Bitcoin-to-2030 10 (model, untested; bullish only if both beta regimes imply ≥20% upside), dilution 5 (measured), sum-of-parts 5 and miner stress 5 (RIOT only). Price-swing risk counts 10 for stocks you don't own. **Weight 0 (context):** track record, analyst targets, Reflexivity phase (tested, no edge), Forecast Center range (non-directional), Trade Signals, TA indicators, Next-Mover (lazy; watchlist only), news tone, Fear & Greed, correlations vs BTC/VIX/UUP, events in the next 14 days. **Not used, with the reason shown:** options, institutional flow, Monte Carlo |
| V6 | Transparency | Evidence table (source, reading, leans, weight, tested?, what it is) with column tooltips. "Why" bullets (strongest weighted pulls first, plus the confidence reasoning). A "where the tabs disagree" panel. "What would change the verdict": My Plan triggers, ADD levels, Bitcoin needed for your target, and for concentration the shares to sell to reach 40% (two cases: money reinvested vs to cash) |
| V7 | N/A, never faked | Each source fails on its own and shows N/A. Sum-of-parts and miner stress say "RIOT only" elsewhere. With no price, the verdict is N/A with a warning. Non-miners get a caveat that My Plan's checks were built for miners |
| V8 | Speed | Reuses the cached engines (My Plan bundle 15 min, backtest 24 h, BTC fit 15 min, reflexivity 1 h, news 30 min). Next-Mover only loads behind "Load slower extras". The verdict page does **not** record calls or send notifications; My Plan still does that |

**Tests:** `tests/test_verdict.py` (14): combine truth tables (held and not held), the held verdict never contradicts My Plan (and confidence stays within one notch), the My Plan page uses `combine_plan`, `build_for` wiring (held and not held), determinism (including row order), weighted score and confidence notches, N/A rows ignored and an all-N/A or no-price verdict, every lean rule returns None on missing input, lean directions, disagreements, the concentration share math, ticker order. Suite: 109 passed. AppTests:
- RIOT, MARA, CLSK, HUT (not held) and NVDA (not held): no exceptions or errors, about 2–7 s cold.
- The selection survives switching to My Plan and back.
- With "slow extras" on, Next-Mover adds about 6 s.
- The degraded run (secondary sources down) gives the same action with N/A rows, and the price-down run gives N/A plus a warning.
- All-section smoke: error counts unchanged from baseline.

**Risks:** the verdict for a holding is only as good as My Plan's rules, and its own 5-year track record shows the timing rules
did not beat holding, so the page leans on them for risk control, not prediction. The weights and lean thresholds are judgement calls
(documented and tested, not optimised). Bitcoin-to-2030 and sum-of-parts depend on assumptions (the build cost is undisclosed, so the parts are overstated).
For non-miners the Bitcoin/peer checks are a rough fit. Confidence on this page can differ by one notch from My Plan's badge,
and the page explains why.

# 🧪 Edge Lab — experimental "obscure math" tools with honest backtests (branch global/edge-lab)

**Request:** "Develop a new idea, tool, TA, analysis … something no one is using that will give me an edge … put it in its own page."
New page `🧪 Edge Lab` (after 🔬 Strategy Lab). **Nothing on it feeds My Plan or the Stock Verdict** (enforced by a test).

| # | Step | What |
|---|---|---|
| E1 | Engine + tools | `utils/edge_stats.py`: forward outcomes stamped at entry (use bars t+1…t+H only), weekly sampling, mean(ON)−mean(OFF), **circular-shift permutation** p-value (2,000 random baselines that keep the signal's on/off rhythm and the outcomes' autocorrelation), 60/40 in-sample / hold-out split, effective independent-episode counts, verdict = `edge found` (right direction in both halves, p<0.05 full, p<0.10 hold-out) / `no reliable edge` / `insufficient data` (<6 independent ON or OFF episodes, <3 in hold-out). `utils/edge_lab.py`: 6 tools (below). |
| E2 | Speed + report | LPPLS fits use cached pseudo-inverses of the whole (tc, m, ω) grid per window length → ~20× faster with identical output (RIOT 0.6 s, BTC 1.1 s). `utils/edge_report.py` runs every tool with rules **fixed in advance** (never tuned), adds Bitcoin's VaR test and a peer robustness check (same rules on RIOT, MARA, CLSK, HUT). |
| E3 | Page | `components/edge_lab.py`: stock pull-down (RIOT/MARA/CLSK/HUT; kept across section switches), scorecard, one tab per tool (plain-English "What is this?", today's reading with ⓘ tooltips, chart, backtest box with ON/OFF/buy-and-hold/p/hold-out/random-baseline band), Robustness tab (opt-in), method notes. Cached 6 h; download failure → error box, not cached, no fake values. `app.py`: one menu entry + 7-line render block. |

**Tools:** (1) LPPLS bubble hazard (Sornette; 9 windows 60–440 bars, Filimonov–Sornette linearisation, standard filters: damping ≥0.8, ≥2.5 oscillations, 2<ω<15). (2) Fragility meter, an original blend of critical-slowing-down signals: Kendall-τ trends of 6-month variance, lag-1 autocorrelation and Bandt–Pompe permutation entropy, each ranked against its own past, then the blend ranked again. (3) Trend memory: rolling 252-day DFA Hurst α, tested on whether a 3-month-trend/1-month-hold bet pays more when α ≥ 0.55. (4) Crash odds: a POT-GPD 1-in-100-day loss tested walk-forward with Kupiec against a bell curve; GPD odds of a ≥30% monthly fall; rank-copula tail dependence λL vs λU vs BTC with a stationary-bootstrap CI and a half-vs-half stability check. (5) Halving clock: phase-folding by days since the halving, plus a leave-the-future-out sign test that needs at least 4 earlier cycles. (6) Tail-aware Kelly: empirical-distribution Kelly on monthly returns, walk-forward half-Kelly compared with fixed 80%, 40% and 100% weights, with a block bootstrap.

**History used:** RIOT from 2017-10-04 (it was the biotech Bioptix before). MARA from Nov 2017 and CLSK from Dec 2020, when each began mining. Fragility rule note: the first draft compared the average of three ranks with 0.8, which almost never fired (about 1 episode). Before looking at outcomes, it was changed to rank the blend itself.

**Results (2026-10-19, RIOT):** no tool showed a reliable buy/sell edge. LPPLS: insufficient data. Bubbles pointed the predicted way on all 4 miners but had only 0.5–1.8 independent episodes each. On BTC, bubble readings were followed by *higher* 3-month returns (+29% vs +11%, p 0.29), consistent with the literature that daily LPPLS fails on BTC. Fragility: insufficient data on RIOT, and no edge on BTC. Hurst: no edge (p 0.48; hold-out +1.0 pts, p 0.88). EVT: for **Bitcoin** the GPD is calibrated (35 breaches vs 37 expected) while the bell curve is not (68), so it is a better *risk* estimate but not a signal. For RIOT both are calibrated (11 vs 15). Tail asymmetry: full history shows no reliable asymmetry. The last 3 years show RIOT rallying with BTC more than it crashes with it (45% vs 32%, CI −22 to −1 pts). Halving clock: hit 77% vs 59% for "always up", but at most 3 earlier cycles, so insufficient data. Kelly: walk-forward half-Kelly cut the worst fall (−59% vs −84%) but cost 20 pts/yr of growth vs holding 80%, so no edge. A static 40% had a similar drawdown (−55%) with much more growth (30% vs 13% CAGR).

**Tests:** `tests/test_edge_lab.py` (24) covers:
- **Engine:** forward-outcome stamping, random signal → no edge, a planted future-peeking signal → edge, determinism, insufficient-data rule, point-in-time expanding rank.
- **Tool math:** LPPLS finds a synthetic bubble but not noise; PE extremes and rolling = direct; Kendall trend; DFA white noise ≈ 0.5 and AR(1) > 0.6; GPD recovers ξ and VaR/tail-probability consistency; Kupiec; tail-dependence bounds and a planted crash-only link; VaR calibrated on t-noise; Kelly known answers (f* = p/a − q/b).
- **No look-ahead:** truncation-invariance for LPPLS, fragility, DFA, the halving fold (future changed → fold unchanged) and walk-forward Kelly.
- **Report and isolation:** report determinism and N/A on short history; isolation from My Plan, Verdict and signal_hub.

Suite: 133 passed. AppTest: RIOT, MARA, CLSK and HUT each about 9 s cold with no exceptions or errors. The peer check works, the selection survives switching sections, and with prices down the page shows an error box. All-section smoke: error counts unchanged from baseline.

**Risks:**
- Small samples. Bubbles and crashes are rare, so most tests can only say "insufficient data".
- The rules are judgement calls, fixed in advance. Other thresholds might look different, and we deliberately did not search them.
- The GPD fit on overlapping 21-day windows is a rough base rate.
- The Kelly results depend on the 2020–2026 path and a 3% cash assumption.
- Yahoo is free and unauthenticated, so it may rate-limit; the page then shows an error.

# 🔎 Deeper evidence — 8 extra analyses on the Stock Verdict (branch global/verdict-deep, from main @ 7282c14)

Everything new lives in one **collapsed** "Deeper evidence" expander under the verdict card, grouped
Long-cycle / Company / Market mood. Each row: one-line takeaway, tooltip, source + as-of date,
tested/untested status, weight. The main card and the action are unchanged — deep rows can only move
confidence (≤ one notch, same rule as before) and never flip the action; held stocks still = My Plan.

| # | Analysis | Data | Weight |
|---|---|---|---|
| 1 | MVRV-Z, Puell, realized price | CoinMetrics community API (free). Realized cap = market cap ÷ MVRV because `CapRealUSD` is paywalled (documented). | 5 only if the current zone's point-in-time backtest on the stock shows an edge (n≥8, \|t\|≥2, 2-day publication lag); else 0 |
| 2 | Miner treasury (mined / sold / held) | `utils/deep_facts.py` TREASURY — RIOT Q1+Q2 2026, MARA Q2, CLSK Jun 2026, each with filing/press URL | 0 (context; flows are lumpy) |
| 3 | Converts & warrants → potential shares | RIOT 0.75% 2030 notes ($594.4M, $14.86, 39.99M shares), warrants, RSUs, $500M ATM — 10-Q Jun 30 2026 + notes 8-K. Also shown in Reflexivity → Dilution tab. | 5 (structural) |
| 4 | AI/HPC peer EV per contracted MW / per HPC revenue | Contracted MW + value per peer (cited trackers / filings, editable table) × live EV from yfinance | 5 (structural); N/A outside the AI-hosting peer set |
| 5 | Options fear: 25-delta skew, max pain, put/call OI | yfinance chain, expiry 20–75 days, Black-Scholes deltas | 0 (untested); loaded only on the "Load live market data" tick |
| 6 | Prediction markets: CLARITY Act, House/Senate, Fed | Polymarket gamma + Kalshi public API (bid/ask mid) | 0 (untested context); live tick only |
| 7 | Volatility regime (calm/normal/stormy) | 21-day realised vol ranked vs trailing 2 years; backtested point-in-time | 5 only with edge; currently 0 for all tested tickers |
| 8 | Short interest & days to cover | yfinance shortPercentOfFloat / shortRatio | 0 (untested) |

Fixes during the build: Kalshi `last_price` was stale → use quote mid; Riot's Q2 "sold" in a press
headline was a net change → derived from the 10-Q H1 figure (holdings reconcile within 25 BTC, tested);
regime takeaway now says "calm" means small daily moves, not direction.

Verification: py_compile; pytest 123 passed (14 new in tests/test_deep_evidence.py, incl. no-look-ahead,
converts cross-check principal×rate, facts cited+dated, deep rows never flip the action, all-sources-down → N/A);
headless ok; full smoke 54 s, 0 exceptions, error counts = baseline; Verdict AppTest RIOT/MARA/CLSK/HUT +
live toggle 0 exceptions; Verdict = My Plan for RIOT/MARA. No app.py edits.

Risks: peer MW/contract figures come from secondary trackers and go stale; Polymarket slugs can be retired
(→ N/A); yfinance short interest is ~2 weeks old; only RIOT has a converts map so far.

# 🌐 All stocks, not just RIOT (branch global/verdict-deep, rebased on main @ 1f97c04)

| Page / util | RIOT-only before? | Now |
|---|---|---|
| Reflexivity: focus stock | No (selectable), defaulted to largest holding | Follows the ⚖️ Verdict stock (when it's in the miner list), else largest holding |
| Reflexivity: 💰 value check (sum of parts) | **Yes** ("RIOT only") | Any ticker: BTC held from `utils/company_facts.py`; cash/debt from the filing if on file, else Yahoo (labelled); per-company facts table with N/A per field; AI-lease NOI only pre-filled for RIOT (others 0 = not disclosed); mNAV hidden when a company holds almost no BTC |
| Reflexivity: ⛏️ miner stress vs cost to mine | **Yes** (Riot's cost) | The focus company's cited cost to mine; N/A where not disclosed (only RIOT on file) |
| Reflexivity: 🧾 dilution SEC filings check | **Yes** (Riot CIK) | Any US filer via CIK in the facts file; N/A for foreign filers (BTDR) |
| Reflexivity: converts map | RIOT (new) | Any ticker in `deep_facts.CONVERTS` (RIOT only so far; others N/A) |
| ⚖️ Verdict: sum-of-parts + miner-stress rows | **Yes** ("RIOT only", weight 0) | Any ticker; weighted only when BTC, cash and debt are on file **and** no undisclosed AI-lease income would be missing (AI hosts → context only, weight 0); miner stress N/A without a cited cost |
| 🧭 My Plan: holding selector | Defaulted to RIOT | Holdings largest-first; follows the Verdict stock when held; remembered across sections |
| 🧭 My Plan: "moving with peers?" divergence check | **Yes** | Any stock in the correlation universe (anchor = that stock) |
| ₿ Bitcoin to 2030 | No (used My Plan's stock) but Riot-specific texts/AI sources | Generic factor help; AI facts per company (cited MW/contract value or N/A); Riot-only caption only for RIOT |
| 🔗 Correlation Map | **Yes** (anchor RIOT) | Anchor selector (holdings + miners + AI hosts), follows the Verdict; RIOT is included as a peer for other anchors; one shared cached download. Menu label in app.py left as "RIOT Correlation Map" (app.py kept minimal) |
| 🧪 Edge Lab dropdown | RIOT/MARA/CLSK/HUT only | Holdings + every miner the app tracks (13), follows the Verdict; peer robustness check still uses the 4-stock set (each is a full lab run); note shown when no mining-start date is on file |
| Trade Signals / Strategy Lab / Sentiment / Weekly outlook | No — RIOT is only a default/first item | unchanged |
| app.py Command Center line "Your RIOT plan" | Yes (RIOT is the largest holding) | unchanged (app.py kept minimal) — noted |
| 🛡️ RIOT Protection (Portfolio sub-tab) | Yes by design (protects the RIOT position) | unchanged — noted |

Facts coverage (`utils/company_facts.py`, LAST_VERIFIED 2026-10-19, every value cited + dated; core = BTC held, cash, debt,
cost to mine, converts, AI MW): no company is "full". RIOT 5/6 (debt from Yahoo); CIFR, WULF, CORZ 5/6 (no cost to mine);
CLSK 4/6; KEEL 3/6; HUT 2/6; MARA, BTDR, MSTR, IREN, BTBT 1/6. Not verified → N/A (e.g. MARA cash/debt, IREN BTC/debt).
Tests: tests/test_all_stocks.py (30) run every generalised function for 5–14 tickers.

# ♻️ Trim & Rebuy (branch global/trim-rebuy, from main @ 9852ccb)

New page: can selling part of a holding and buying it back cheaper leave you with **more shares** than holding,
after NY State + NYC + federal tax and costs? Experimental; **not wired into My Plan or ⚖️ Verdict**. Not tax advice.

| Piece | What |
|---|---|
| `utils/tax_ny.py` | 2026 federal ordinary brackets, long-term 0/15/20% bands stacked on ordinary income, 3.8% NIIT, NY State 2026 rates (Ch. 59 L. 2025), NYC resident rates, federal and NY standard deductions; single and married filing jointly. ST/LT netting, $3,000 loss limit, carryforward keeps its character. IRA/Roth = no tax. Incremental tax = tax(other income + gains) − tax(other income). Every table cited + dated in `SOURCES` (IRS Rev. Proc. 2025-32, IRS Topics 409/559, Pub. 550, NY DTF, NYC Comptroller, Schwab FIFO default). |
| `utils/trim_rebuy.py` | Lot ledger (FIFO = Schwab default, or specific-ID highest-cost-first); holding period restarts on rebuy; wash sale both ways (±30 days; disallowed loss → replacement lot's basis; holding period tacked); yearly settlement. 7 pre-registered rules (A1–A3 stretch, E1–E2 earnings, B1 Bollinger, B2 ATR), every one with a max-wait timeout and a 5-day cool-down; signal at close t → trade at close t+1. In-sample 60% / hold-out 40%; random-date baseline (same trims, sizes and lengths on random non-overlapping dates, 200 runs, seeded). Edge = positive pre-tax and after-tax in full sample, after-tax in both halves, p ≤ 0.05 full and ≤ 0.10 hold-out, ≥6 trips (≥3 hold-out). Covered-call overlay (Black-Scholes, labelled assumptions) and tax-loss-harvest swap into the most correlated peer for 31 days (point-in-time peer pick). Live harvest calculator from the user's cost basis. |
| `components/trim_rebuy.py` | Page: stock dropdown (holdings first + every miner) that follows the Verdict; tax settings (filing status, other income placeholder with a prominent note, NYC toggle, FIFO/specific-ID, slippage, "bought > 1 year ago"); verdict banner; rule table with IRA/Roth (pre-tax) and taxable (after-tax) columns; rule detail (hit rate, avg win/loss, worst miss, days out, drawdown, share-count chart vs hold, trade log with est. tax); today's zones **only if a rule passed** (else context only); covered calls; harvest; sources + brackets; CPA note. |
| `app.py` | One menu entry "♻️ Trim & Rebuy" (lazy import, `_tab_error` wrapper). |

After-tax metric: after-tax share-equivalents = (after-tax value if everything were sold on the last day) ÷ last price,
for the rule and for holding from the same start (the hold's deferred tax counts too). Taxes along the way are paid from
outside cash (nominal); a leftover loss carryforward is valued at the long-term marginal rate for both sides. A harsher
view ("tax paid from shares") is shown too. Backtest = last 10 years, start cost = first day's price (long-term).

Result (single, $100k placeholder income, NYC, FIFO, 0.05% slippage): **no rule passes for any of the 9 holdings** (or HUT).
Tests: tests/test_tax_ny.py (8 hand-checked worked examples), tests/test_trim_rebuy.py (17: wash sale ×4, holding period
reset, FIFO vs specific-ID, $3k limit/carryforward in the ledger, no look-ahead, next-close execution, timeout,
determinism, earnings N/A, reaction-day timing, random-baseline shape, Black-Scholes, harvest calculator, 31-day swap).

Not modelled / risks: NY supplemental "recapture" tax above NY AGI $107,650; credits, AMT, itemizing; 2026 rules applied to
every past year; tax settled each Dec 31 (no estimated-tax timing); wash-sale adjustment that crosses an already
settled year is booked in the rebuy year; unknown real lot dates (one "bought > 1 year ago" checkbox); purchases in other
accounts/IRAs (wash sales) not visible; "different company = not substantially identical" is a judgment; option prices
are modelled (realized vol ×1.0/×1.2, 5% haircut, fractional contracts), not quotes; 7 rules + 3 CC + TLH tested = multiple
testing, so a single pass could be luck.
