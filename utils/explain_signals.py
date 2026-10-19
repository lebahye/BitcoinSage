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
    "btc_2030": (
        "Bitcoin 2030 scenarios — what are these?",
        "**What it is:** four 'what-if' paths for Bitcoin's price to your plan year. Each path's yearly growth is simply "
        "the **sum of eight drivers** (adoption, the 2028 halving, ETFs, US policy, interest rates & inflation, company "
        "buyers, other countries, and risks). Every driver number is an **assumption you can edit**, with the dated facts "
        "behind it listed underneath.\n\n"
        "**What it is not:** a forecast. Nobody knows Bitcoin's 2030 price. Published forecasts (ARK, Standard Chartered, "
        "Bernstein) are shown for comparison — they come from bullish research shops and have been cut before.\n\n"
        "**Why it matters to you:** RIOT's value is still partly driven by Bitcoin, so your 2030 plan quietly assumes "
        "something about Bitcoin. This makes that assumption visible."
    ),
    "btc_link": (
        "BTC sensitivity (beta) and R² — how much Bitcoin moves the stock",
        "**Beta:** if Bitcoin rises 10% over a quarter, the stock has on average moved about beta × 10%. Beta 1.1 = a bit "
        "more than Bitcoin; beta 0.2 = barely at all.\n\n"
        "**R²:** how much of the stock's quarterly moves Bitcoin explains (0 = none, 1 = all). About 0.47 means Bitcoin "
        "explains roughly half; the other half is company news, dilution, AI deals, the stock market…\n\n"
        "**Why two numbers:** over 2018–2026 RIOT followed Bitcoin closely, but in the last 3 years — after its move into "
        "AI data centres — it barely did. Nobody knows which regime holds to 2030, so both are shown.\n\n"
        "**Daily correlation (~0.5)** measures day-to-day co-movement; it says little about where the stock ends up in 2030."
    ),
    "btc_for_target": (
        "'Bitcoin price that lines up with' a stock price",
        "Runs the BTC→stock relationship backwards: *if history holds, what would Bitcoin need to be for the stock to reach "
        "$X?* The range shows the BTC level needed if the stock does better (lower BTC needed) or worse (higher) than "
        "Bitcoin alone implies — the usual 'stray' seen historically (about 2 in 3 cases fell inside).\n\n"
        "It is **not** a promise that the stock will be $X when Bitcoin is there — dilution, mining economics and AI deals "
        "all move it too, and you can set those below."
    ),
    "halving_cycle": (
        "The 4-year halving cycle",
        "About every 4 years the reward for mining a Bitcoin block is cut in half. In the last three cycles Bitcoin's peak "
        "came **about 17–18 months after the halving**, followed by a fall of roughly 50–85% over the next year.\n\n"
        "**Why it matters to a 2030 seller:** the next halving is estimated for ~April 2028. If the pattern repeated, the peak "
        "would be around **late 2029** and **2030 would be a down year**. Three cycles is a tiny sample and many analysts "
        "think ETFs are changing the pattern — so treat it as a reason to start staged selling earlier, not as a rule."
    ),
    "reflexivity": (
        "Reflexivity — two feedback loops for a bitcoin miner",
        "**The network loop (stabilising):** Bitcoin rises → mining pays more → miners plug in more machines → the "
        "network's difficulty rises → each machine earns less again. This loop *pulls margins back down*; it is not a "
        "boom/bust amplifier.\n\n"
        "**The capital-markets loop (reflexive, George Soros's idea):** the share price rises → the company sells new "
        "shares at high prices → buys machines, bitcoin or data centres → per-share numbers and the story improve → the "
        "price rises more. In reverse: the price falls → new shares are sold cheaply (dilution) or bitcoin is sold → "
        "value per share falls → the price falls more.\n\n"
        "**What this tab can and can't do:** it describes which loop seems active today. Its phases were tested over "
        "2018–2026 and did **not** reliably predict the next 3–6 months, so they are context — 🧭 My Plan stays the "
        "final word."
    ),
    "coupling_index": (
        "Bitcoin co-movement index (0–100)",
        "How tightly the stock is tracking — and amplifying — Bitcoin **over the last 30 trading days**: "
        "correlation (3/8 weight), beta capped at 3× (3/8) and whether both moved the same way (2/8). "
        "High = moving in lockstep with Bitcoin; low = doing its own thing (company news, AI deals, dilution).\n\n"
        "It used to be called the 'Reflexivity Index', but it measures co-movement, not the capital-markets loop. "
        "Backtested 2018–2026: high or low readings did not reliably predict what came next."
    ),
    "hashprice": (
        "Hashprice and miner stress",
        "**Hashprice** = how many dollars one unit of mining power (1 PH/s) earns per day, from new coins plus fees. "
        "It falls when Bitcoin falls, when more machines join the network, and it halves overnight at each halving.\n\n"
        "**Miner stress** compares the Bitcoin price with what it costs to mine one: the network-wide *power-only* "
        "estimate (from your machine-efficiency and power-price inputs) and Riot's own reported cost to mine. "
        "When Bitcoin is below a miner's all-in cost, it may have to sell bitcoin or new shares to pay its bills — the "
        "start of the bust side of the loop."
    ),
    "sum_of_parts": (
        "Riot value check (sum of the parts)",
        "Adds up what Riot's pieces may be worth — bitcoin held, cash, the AI data-centre lease (today's value of its "
        "expected yearly operating income), the mining business and anything else you enter — minus debt and the cost "
        "still needed to build the data centre — and compares it with what the stock market values the whole company at.\n\n"
        "Facts come from Riot's own filings (dated). Things Riot hasn't disclosed — like the build cost — are **your** "
        "inputs. A result far above or below the market value is a prompt to look closer, not a buy/sell signal."
    ),
    "dilution": (
        "Dilution (new shares)",
        "When a company sells new shares, each existing share owns a smaller slice. Miners often fund growth this way, "
        "especially when their share price is high (the reflexive loop). Riot's share count grew about 45% a year in "
        "2019–2024; growth has been much slower recently. Prospectus supplements (form 424B5) and shelf registrations "
        "(S-3) are the SEC filings that usually come with share sales."
    ),
}
