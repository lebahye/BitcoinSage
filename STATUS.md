# BitcoinSage Status

_Last updated: 2026-03-08_

## Snapshot

BitcoinSage is a consolidated Streamlit dashboard focused on **Bitcoin miners**, with:
- market overview
- AI prediction engine
- options center
- institutional flow / dark pool analysis
- technical analysis
- Polymarket integration
- sentiment analysis
- risk center
- portfolio / RIOT protection
- strategy lab
- reflexivity analysis

## Current Architecture

### Root
- `app.py` — main application shell
- `healthcheck.py` — runtime/API/import validation
- `ROADMAP.md` — forward plan
- `SCHWAB_SETUP.md` — Schwab setup guide

### Components
- `stock_dashboard.py`
- `next_mover_dashboard.py`
- `unified_options.py`
- `dark_pool_tracker.py`
- `advanced_ta_dashboard.py`
- `polymarket_tracker.py`
- `sentiment_analysis.py`
- `risk_center.py`
- `personal_portfolio.py`
- `riot_protection.py`
- `backtesting_dashboard.py`
- `weekly_outlook.py`
- `volatility_hole_chart.py`
- `reflexivity_dashboard.py`

### Utils
- `unified_data_fetcher.py`
- `options_analytics.py`
- `chart_builder.py`
- `advanced_ta.py`
- `backtesting_engine.py`
- `next_mover_engine.py`
- `risk_engine.py`
- `polymarket_fetcher.py`
- `polymarket_live_feed.py`
- `sentiment_analyzer.py`
- `schwab_client.py`
- `styles.py`

## Data Sources

### Primary
- **Yahoo Finance** — prices, options, BTC reference data
- **Redis** — live Polymarket / edge feed

### Optional / Enhanced
- **Schwab API** — real-time brokerage data
- **blockchain.info** — hashrate / difficulty enhancement for Reflexivity

## Data Trust Notes

The app is designed to use **real live data** wherever possible.

Important distinctions:
- Some metrics are **direct** (price, options chain, BTC, volume)
- Some are **estimated** (miner breakeven, margin, reflexivity sub-scores)
- Some are **proxy-derived** (options-flow proxy in weekly outlook when no full options model is used)

The app should increasingly label these more explicitly in the UI.

## Known Strengths
- Consolidated architecture versus earlier duplicate-file state
- Strong differentiation via Reflexivity tab
- Better styling and loading behavior than earlier versions
- Health check page added for Replit validation
- Major stale import issues already cleaned up

## Known Risks
- Heavy Yahoo Finance dependency
- Replit runtime is the real test environment, not local verification
- Large component files are harder to maintain
- Some tabs may still degrade under rate limits or market-closed conditions
- Polymarket/Redis and Schwab need real environment validation to be fully trusted

## What “good” looks like
A trustworthy production-like state means:
- `streamlit run healthcheck.py` passes imports and core APIs
- `streamlit run app.py` loads all tabs without runtime exceptions
- price-heavy tabs clearly signal freshness / degraded mode
- RIOT protection and options views show quote quality clearly
- Reflexivity works even when blockchain.info is unavailable

## Recommended Validation Loop
1. Pull latest from GitHub on Replit
2. Run `streamlit run healthcheck.py`
3. Run `streamlit run app.py`
4. Open each tab once
5. Screenshot any failures
6. Fix only based on observed runtime behavior
