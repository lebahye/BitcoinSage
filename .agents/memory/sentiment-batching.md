---
name: Sentiment API Batching — Alpha Vantage
description: Why sentiment always showed 50 and the fix
---

Original `analyze_sentiment_scores()` called `_get_sentiment_score(symbol)` in a for-loop — 9 separate Alpha Vantage API calls per page load.

**Problem:** Free tier is 25 calls/day. First page load hits the limit; subsequent calls silently return error → fall back to score=50 for all stocks.

**Fix:** Single batched call in `analyze_sentiment_scores()` using `get_news_sentiment(self.mining_stocks, limit=50)` — Alpha Vantage NEWS_SENTIMENT endpoint accepts comma-separated tickers. Parse `feed[].ticker_sentiment[]` per article to build per-ticker averages.

**Sentinel field:** Each row now includes `Sentiment Live: bool` — False when defaulted. Dashboard shows a warning banner when sentiment is unavailable so the user understands why it shows Neutral.

**Why:** 1 API call instead of 9 keeps well within free tier. Scores only go stale at day 25+, not immediately.
