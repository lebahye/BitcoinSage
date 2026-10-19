# Bitcoin Mining Stock Tracker

## Overview

This is a comprehensive financial analytics application built with Streamlit that specializes in tracking and analyzing Bitcoin mining stocks. The application provides real-time market data analysis, options flow monitoring, and dark pool activity tracking to help users make informed investment decisions. The system combines traditional stock analysis with cryptocurrency market correlation insights, focusing specifically on the mining sector which is highly sensitive to Bitcoin price movements.

## User Preferences

Preferred communication style: Simple, everyday language.

**Data policy: No mock, fake, static, or placeholder data is permitted anywhere in the app. Every number displayed must come from a live API call or real computation on live data. If a data source is unavailable, show a clear error — never substitute fake values silently.**

## System Architecture

### Frontend Architecture
The application uses Streamlit as the primary web framework, implementing a component-based architecture with modular dashboards. The main application (`app.py`) serves as the orchestrator, coordinating between specialized dashboard components:

- **StockDashboard**: Handles core stock price analysis and correlation studies
- **OptionsDashboard**: Manages options flow analysis and put-call ratio monitoring  
- **DarkPoolTracker**: Monitors institutional trading activity and unusual volume patterns

Each component is self-contained and renders its own UI sections, promoting code reusability and maintainability. The frontend uses custom CSS styling for professional appearance with a dark theme optimized for financial data visualization.

### Data Layer Architecture
The data fetching layer is centralized through the `DataFetcher` class, which handles all external API interactions and data normalization. This design pattern ensures consistent data handling across the application and provides a single point for caching and error handling. The fetcher supports multiple data sources including Yahoo Finance for stock data and options chains.

### Analytics Engine
The application implements specialized analyzer classes for different types of financial analysis:

- **OptionsAnalyzer**: Calculates put-call ratios, volatility signals, and options flow metrics
- **ChartBuilder**: Creates interactive financial charts using Plotly with customizable indicators
- **Dark Pool Analysis**: Identifies unusual volume patterns and institutional activity
- **AdvancedTA**: Professional-grade technical analysis library featuring:
  - **Volume Profile (Market Profile)**: Identifies institutional price levels and high-volume nodes (POC)
  - **Anchored VWAP**: Tracks institutional entry/exit efficiency from key dates
  - **Ichimoku Cloud**: Complete trend-following system with multiple confirmation signals
  - **Fibonacci Extensions**: Professional price targets for take-profit planning
  - **Market Breadth**: Sector-wide strength analysis (Advance-Decline metrics)
  - **Money Flow Index (MFI)**: Volume-weighted RSI for buying/selling pressure
  - **Elder Ray Index**: Bull/Bear power analysis relative to EMA

- **BacktestingEngine**: Strategy validation framework for historical performance testing:
  - **MA Crossover Strategy**: Dual moving average crossover signals (configurable short/long windows)
  - **RSI Mean Reversion**: Oversold/overbought level trading (configurable periods and thresholds)
  - **Volume Breakout**: High-volume breakout detection (configurable threshold multiplier)
  - **Momentum Strategy**: Price momentum trading (configurable lookback periods)
  - **Performance Metrics**: CAGR, Sharpe ratio, max drawdown, win rate, trade count
  - **Strategy Comparison**: Run all strategies simultaneously to identify best performers
  - **Trade Pairing**: Accurate profit/loss calculation by properly pairing BUY/SELL trades

This modular approach allows for easy extension of analytical capabilities and maintains separation of concerns between data processing and visualization.

### Chart and Visualization System
The charting system is built on Plotly for interactive financial visualizations, supporting candlestick charts, volume analysis, correlation heatmaps, and custom technical indicators. The chart builder implements a consistent color scheme and styling optimized for financial data readability.

### Session Management
The application leverages Streamlit's built-in session state management for maintaining user selections and cached data across page interactions. This approach provides a smooth user experience without requiring external session storage.

## External Dependencies

### Core Framework Dependencies
- **Streamlit**: Primary web application framework for building the interactive dashboard interface
- **Pandas**: Data manipulation and analysis, handling time series financial data
- **NumPy**: Numerical computations for financial calculations and statistical analysis

### Financial Data Sources
- **yfinance (Yahoo Finance)**: Primary data source for stock prices, historical data, and options chains
- **requests**: HTTP client for additional API calls and data fetching operations

### Visualization Libraries
- **Plotly**: Interactive charting library for financial visualizations including candlestick charts, volume indicators, and correlation matrices
- **Plotly Express**: Simplified plotting interface for quick statistical visualizations

### Python Standard Libraries
- **datetime/timedelta**: Time-based calculations for market hours, data ranges, and temporal analysis
- **time**: Performance monitoring and rate limiting for API calls

The application is designed to be self-contained with minimal external service dependencies, relying primarily on publicly available financial data APIs. The modular architecture allows for easy integration of additional data sources or analytical tools as needed.
## October 2026 hardening (branch global/dashboard-hardening)
- `utils/market_data.py` — all cross-asset maths (BTC vs stocks) must go through `align_frame` / `beta_corr`: BTC is stamped
  in UTC and trades weekends, stocks are New York time; never join their raw indexes.
- `utils/tickers.py` — single list of symbols + rename map (`BITF → KEEL`).
- `utils/riot_correlation.py` + `components/riot_correlation_map.py` — the only correlation view.
- `utils/holding_advisor.py` + `components/holding_plan.py` — "🧭 My Plan", the single Hold/Trim/Sell/Rotate call.
- `utils/explain.py` — plain-English glossary for tooltips and "What is this?" boxes.
- Top-level navigation is a section selector (only the chosen section runs) to stay under Yahoo's rate limits.
- `FIXLOG.md` lists every change and test result. Run `pytest tests/` after changes.

## Optional call-change alerts (off by default)
My Plan saves the latest call per ticker in `data/last_calls.json` (gitignored) and shows a
"🔔 What changed since last check" banner when it flips. To also get a Telegram or email message:
1. In Replit open **Tools → Secrets** and add
   - Telegram: `TELEGRAM_BOT_TOKEN` (create a bot with @BotFather), `TELEGRAM_CHAT_ID` (message the bot, then read your id from
     `https://api.telegram.org/bot<token>/getUpdates`), and/or
   - Email: `SMTP_HOST`, `SMTP_PORT` (587 STARTTLS or 465 SSL), `SMTP_USER`, `SMTP_PASSWORD` (use an app password),
     `ALERT_EMAIL_TO`, optional `SMTP_FROM`.
2. In My Plan → **🔔 Alert settings**, tick "Send me an alert when a call changes" (saved in `data/notify_settings.json`).
Alerts are sent only while the dashboard is open and a change is detected; nothing is sent when
`BITCOINSAGE_NO_NOTIFY` or `PYTEST_CURRENT_TEST` is set. Secret values are never displayed or logged.
