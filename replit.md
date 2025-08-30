# Bitcoin Mining Stock Tracker

## Overview

This is a comprehensive financial analytics application built with Streamlit that specializes in tracking and analyzing Bitcoin mining stocks. The application provides real-time market data analysis, options flow monitoring, and dark pool activity tracking to help users make informed investment decisions. The system combines traditional stock analysis with cryptocurrency market correlation insights, focusing specifically on the mining sector which is highly sensitive to Bitcoin price movements.

## User Preferences

Preferred communication style: Simple, everyday language.

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