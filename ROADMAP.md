# BitcoinSage Roadmap

*Owned by Sage agent (@Arb_system_bot). Last updated: 2026-03-06*

---

## Current State
- 17 tabs, significant duplicate code across components and utils
- Polymarket tab: REST polling every 30s (stale data)
- 3 data fetchers doing similar work
- 2 options analysis modules
- 2 sentiment components, 2 risk components, 2+ TA components

## Target State
- 10 consolidated tabs, zero duplicate logic
- Polymarket tab: **live Redis feed** from arb scanners (real-time)
- 1 unified data fetcher
- 1 canonical options analytics module
- Clean, maintainable codebase

---

## Phase 1: Live Polymarket Feed ✅ (Done 2026-03-06)
- [x] Created `utils/polymarket_live_feed.py` — Redis Stream reader
- [x] Updated `components/polymarket_tracker.py` — added "Live Arb Signals" tab
- [ ] Test with live Redis data (requires arb scanners running)
- [ ] Add auto-refresh (st.rerun every 5s when live tab is active)

## Phase 2: Consolidate Utils
- [ ] Create `utils/unified_data_fetcher.py` — merge data_fetcher + enhanced_data_fetcher + schwab_fetcher
- [ ] Update all components to use UnifiedDataFetcher
- [ ] Remove `utils/options_analyzer.py` — update imports to use `options_analytics.py`
- [ ] Remove `utils/data_fetcher.py` and `utils/enhanced_data_fetcher.py` after migration

## Phase 3: Consolidate Components
- [ ] Merge `risk_management.py` + `risk_dashboard.py` → `risk_center.py`
- [ ] Merge `options_dashboard.py` + `pro_options_dashboard.py` → `unified_options.py` (keep `options_evaluator.py` as sub-section)
- [ ] Merge `enhanced_technical.py` into `advanced_ta_dashboard.py`
- [ ] Remove `sentiment_dashboard.py` — keep `sentiment_analysis.py`

## Phase 4: 10-Tab Restructure
- [ ] Update `app.py` — new tab structure (10 tabs)
- [ ] Update all imports
- [ ] Test all tabs
- [ ] Remove deprecated files

## Phase 5: UI Polish
- [ ] Consistent styling across all components
- [ ] Shared CSS constants
- [ ] Loading states + error handling
- [ ] Mobile-responsive layout improvements

---

## Duplicate File Map (Reference)

| Remove | Keep |
|--------|------|
| `utils/data_fetcher.py` | `utils/unified_data_fetcher.py` (new) |
| `utils/enhanced_data_fetcher.py` | ^ |
| `utils/schwab_fetcher.py` | ^ (Schwab logic stays in schwab_client.py) |
| `utils/options_analyzer.py` | `utils/options_analytics.py` |
| `components/sentiment_dashboard.py` | `components/sentiment_analysis.py` |
| `components/risk_management.py` | `components/risk_center.py` (new merged) |
| `components/risk_dashboard.py` | ^ |
| `components/options_dashboard.py` | `components/unified_options.py` (new merged) |
| `components/pro_options_dashboard.py` | ^ |
| `components/enhanced_technical.py` | `components/advanced_ta_dashboard.py` |
