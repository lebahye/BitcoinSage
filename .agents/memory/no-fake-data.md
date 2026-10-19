---
name: No-Fake-Data Rule
description: Hard project constraint — every number must come from live API or real computation
---

## The Rule
No mock, fake, static, or placeholder data permitted anywhere in the app.
Every number displayed must come from a live API call or real computation on live data.
If a data source is unavailable, show a clear error — never substitute fake values silently.

**Why:** This is an explicit user requirement in replit.md.

**How to Apply:**
- Never hardcode price tables, pattern data, or option premiums
- Always fetch from yfinance, Alpha Vantage, or Schwab
- For estimated values (e.g. Black-Scholes premiums), label them as estimates in the UI
- Show st.error() or st.warning() when data is unavailable rather than falling back to fake numbers
