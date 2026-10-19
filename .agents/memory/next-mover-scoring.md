---
name: Next Mover Engine — Technical Scoring
description: Why the technical score always showed 50 and how it was fixed
---

The original `analyze_technical_setup()` used binary thresholds that only fired in extreme conditions:
- RSI < 30 or < 40 (never happens in bull market where RSI runs 52–78)
- Exact MACD crossover (prev<=0, cur>0) — rare, usually already happened
- Volume > 1.5x only

**Result:** 7 of 9 stocks scored exactly 50 in any normal market.

**Fix:** Rewrote to continuous scoring with multiple tiers:
- RSI: 7 bands from <30 (+30pts) to >80 (-28pts), including neutral 50-60 zone (0pts)
- MACD: 6 states including accelerating/strengthening/fading/crossover
- Price vs MA20/MA50: above both / mixed / below (new signal)
- Volume: 5 bands 0.8x–2x+

**Why:** Scores need to differentiate stocks in *any* market, not just extremes. The goal is ranking relative to peers.
