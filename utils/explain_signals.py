"""Beginner explanations for the short-term signal / news / forecast features
(merged into utils.explain.GLOSSARY so `explain()` and `HELP[...]` work for them)."""

SIGNAL_GLOSSARY = {
    "signal_hierarchy": (
        "Which signal do I follow?",
        "**🧭 My Plan is the final word** for a long-term holder: Hold / Trim / Sell / Rotate, plus Add / Wait. "
        "Its rules have a published track record (📊 Track record in My Plan).\n\n"
        "**🚦 Trade Signals** (BUY / HOLD / SELL) is a *short-term* momentum read for the next days–weeks. "
        "It is often 'SELL' during a normal dip while My Plan still says HOLD — that is not a contradiction, "
        "they answer different questions. Never sell a 2030 position on a short-term signal alone.\n\n"
        "**Next-Mover ranking, Forecast Center lean and news tone** are background context only."
    ),
    "trade_signal": (
        "Short-term trade signal (BUY / HOLD / SELL)",
        "**What it is:** a points score from 8 technical rules (RSI, Stochastic, MACD, volume, Bollinger %B, "
        "OBV, news tone, Bitcoin's daily move). Score ≥ 28 → BUY, ≤ −20 → SELL, otherwise HOLD.\n\n"
        "**What it is not:** a prediction, AI, or a probability. The 'confidence %' only says how far past the "
        "threshold the score is. These short-term rules have not been backtested.\n\n"
        "**Why it matters to you:** useful for *timing* a trim or an add that My Plan already recommends — e.g. "
        "carry out a trim on a short-term BUY bounce rather than on a SELL day."
    ),
    "news_tone": (
        "News tone (headline sentiment)",
        "**What it is:** recent headlines about the stock (Yahoo Finance + Google News, last 7 days), each scored by "
        "counting positive words (beat, surge, upgrade…) and negative words (miss, plunge, dilution…). "
        "The average runs from −1 (very negative) to +1 (very positive); above +0.15 = Bullish, below −0.15 = Bearish. "
        "If an Alpha Vantage key is configured, its NLP scores are used instead.\n\n"
        "**Limits:** it reads the *tone of headlines*, not whether they're right; it can miss sarcasm or 'not'. "
        "It is not AI and hasn't been shown to predict prices.\n\n"
        "**Why it matters to you:** a quick way to spot *why* the stock is moving — read the actual headlines."
    ),
    "fear_greed": (
        "Crypto Fear & Greed Index",
        "**What it is:** a published 0–100 index (alternative.me) built from Bitcoin volatility, momentum, social media, "
        "surveys, dominance and search trends. 0–24 extreme fear, 25–44 fear, 45–55 neutral, 56–75 greed, 76–100 extreme greed.\n\n"
        "**Why it matters to you:** extreme greed has often come near short-term tops and extreme fear near bottoms — "
        "a reason not to add in euphoria or panic-sell in fear. It's a mood gauge, not a timing tool."
    ),
    "next_mover": (
        "Next-Mover ranking",
        "**What it is:** a weighted score (relative strength 30%, technicals 40%, Bitcoin beta 15%, news tone 15%) used "
        "to rank the 9 miners against each other. Previously labelled 'AI Predictions' — it is **not AI or machine "
        "learning**, and the score is **not a probability** of anything.\n\n"
        "**Why it matters to you:** shows which miners look strongest/weakest this week. Not a reason to change a "
        "long-term holding."
    ),
    "stat_forecast": (
        "Statistical price range (Forecast Center)",
        "**What it is:** the range the price would land in about 68% (and 90%) of the time if the stock keeps its "
        "recent volatility, centered on today's price (no up/down guess). Built from the last year of daily moves.\n\n"
        "**How accurate is it?** We replay it on the past few years and show how often the real price actually ended "
        "inside the range ('hit rate'). Close to 68% / 90% = the range is honest; much lower = it was too narrow.\n\n"
        "**What it is not:** a price target. Nobody can reliably forecast a miner's direction week to week."
    ),
}
