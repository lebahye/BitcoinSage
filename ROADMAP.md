# BitcoinSage Roadmap

_Last updated: 2026-03-08_

This roadmap reflects the **current repo reality**, not the earlier consolidation plan.

---

## Current State

BitcoinSage is now a consolidated Streamlit dashboard for Bitcoin miners with:
- **11 primary tabs** in `app.py`
- Unified data layer via `utils/unified_data_fetcher.py`
- Unified options and risk components
- Dedicated **Reflexivity** analysis for Bitcoin miners
- `healthcheck.py` for runtime/API validation on Replit

The codebase is no longer in the “duplicate file sprawl” phase.
The next phase is **runtime reliability, observability, and product polish**.

---

## ✅ Completed

### Architecture consolidation
- [x] Merged data fetchers into `utils/unified_data_fetcher.py`
- [x] Removed legacy `data_fetcher.py`, `enhanced_data_fetcher.py`, `schwab_fetcher.py`
- [x] Consolidated options logic into `utils/options_analytics.py`
- [x] Merged:
  - [x] `risk_management.py` + `risk_dashboard.py` → `risk_center.py`
  - [x] `options_dashboard.py` + `pro_options_dashboard.py` + evaluator → `unified_options.py`
  - [x] `enhanced_technical.py` into `advanced_ta_dashboard.py`
- [x] Removed deprecated component files

### App structure
- [x] Rebuilt `app.py` into clean tab-based navigation
- [x] Added shared styling with `utils/styles.py`
- [x] Added cached component/resource initialization
- [x] Added loading spinners and error wrappers

### Polymarket
- [x] Added live Polymarket integration path
- [x] Added Redis-backed feed support
- [x] Added Polymarket live feed tab wiring

### Reflexivity
- [x] Added `components/reflexivity_dashboard.py`
- [x] Added Reflexivity tab to app
- [x] Added fallback logic so it still works when blockchain.info is unavailable

### Operational tooling
- [x] Added `healthcheck.py`
- [x] Cleaned Schwab auth clutter
- [x] Added `SCHWAB_SETUP.md`

---

## 🟡 In Progress / Needs Runtime Validation

These are implemented in code but need continued Replit validation:

- [ ] All 11 tabs load cleanly on Replit with no runtime exceptions
- [ ] Yahoo Finance behavior under Replit rate limits is stable enough for normal use
- [ ] Polymarket Redis feed confirmed live end-to-end on Replit
- [ ] Reflexivity tab validated with live price data in production environment
- [ ] RIOT protection tab validated during market-open and market-closed conditions
- [ ] Schwab real-time flow validated on Replit with live token setup

---

## 🔴 P0 — Highest Priority Next

### 1. Runtime confidence / observability
- [ ] Add a visible **data freshness + source badge** inside more tabs, not just sidebar/top
- [ ] Add “last successful fetch” timestamps per data-heavy tab
- [ ] Add clear degraded-mode messaging when Yahoo / Redis / blockchain.info are unavailable
- [ ] Add a simple `STATUS.md` / validation record for current production state

### 2. Replit validation workflow
- [ ] Add tab-by-tab smoke checklist
- [ ] Add a machine-readable smoke test script (in addition to `healthcheck.py`)
- [ ] Record known-good environment assumptions in docs

### 3. Data trust clarity
- [ ] Explicitly label metrics as:
  - Direct data
  - Estimated
  - Proxy-derived
  - Unavailable
- [ ] Improve options quote quality messaging (last trade vs spread vs stale quotes)

---

## 🟠 P1 — Product / UX Improvements

### 4. Dashboard command layer
- [x] Add top-level command center strip
- [ ] Add a concise “What matters now” summary block
- [ ] Add best opportunity / biggest risk summary cards
- [ ] Add today’s market regime summary at top of app

### 5. UI consistency
- [ ] Standardize severity language and color usage across all tabs
- [ ] Reduce over-explanation in tabs; move deep explanations into expanders
- [ ] Improve narrow-screen / mobile layout behavior
- [ ] Improve empty-state UX (better than plain warnings)

### 6. Health / diagnostics UX
- [ ] Link to `healthcheck.py` from main app sidebar
- [ ] Add one-click diagnostics section in app
- [ ] Show import/API failures more clearly for non-technical users

---

## 🟢 P2 — Code Quality / Maintainability

### 7. Split oversized files
Priority split targets:
- [ ] `components/advanced_ta_dashboard.py`
- [ ] `components/reflexivity_dashboard.py`
- [ ] `components/weekly_outlook.py`
- [ ] `components/risk_center.py`
- [ ] `components/unified_options.py`

### 8. Better layering
- [ ] Separate fetch / compute / render responsibilities more clearly
- [ ] Reduce implicit state across components
- [ ] Add more reusable plotting helpers

### 9. Testing
- [ ] Add import smoke tests
- [ ] Add data-source fetch tests
- [ ] Add options-chain availability tests
- [ ] Add Redis connectivity tests

---

## North Star

BitcoinSage should feel like:
> **a dependable decision workstation for Bitcoin miner analysis**

—not just a collection of impressive tabs.

That means the next phase is less about adding more features, and more about:
- trust
- freshness
- observability
- clarity
- runtime reliability
