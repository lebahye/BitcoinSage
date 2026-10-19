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
