"""
utils/explain.py — plain-English "What is this?" help for beginners.

Usage:
    st.metric("Beta", "1.2", help=HELP["beta"])   # hover tooltip
    explain("beta")                                # collapsible "What is this?" box

Each entry answers: what it is, and why it matters to someone holding RIOT /
bitcoin-miner shares for the long term.
"""

import streamlit as st

GLOSSARY = {
    "beta": (
        "Beta vs Bitcoin",
        "**What it is:** how much a stock has typically moved for each 1% move in Bitcoin. "
        "Beta 1.5 = when Bitcoin drops 10%, the stock has tended to drop about 15%.\n\n"
        "**Why it matters to you:** miners are a leveraged bet on Bitcoin. A higher beta means bigger "
        "swings in both directions — more upside in a Bitcoin rally, deeper losses in a crash."
    ),
    "correlation": (
        "Correlation",
        "**What it is:** a score from -1 to +1 for how closely two things move together day to day. "
        "+1 = always move the same direction, 0 = unrelated, -1 = always opposite.\n\n"
        "**Why it matters to you:** if everything you own has a correlation near +1 with RIOT, "
        "you're not diversified — one bad day hits the whole portfolio. Something with a reliably "
        "negative correlation (like the VIX) can act as a hedge."
    ),
    "riot_corr_map": (
        "RIOT Correlation Map",
        "**What it is:** a ranking of which stocks and markets move most like RIOT, measured over the last "
        "year and the last 3 months of daily prices.\n\n"
        "**How to read it:** if RIOT's link to other miners and AI data-center stocks is stronger than its "
        "link to Bitcoin, RIOT is trading as an 'AI infrastructure' story as much as a Bitcoin story. "
        "'Steady' links held in every quarter of the year; 'flips' means the relationship changed sign "
        "and shouldn't be relied on.\n\n"
        "**Why it matters to you:** it tells you what is really driving your shares — and whether "
        "owning other miners actually diversifies you (usually it doesn't)."
    ),
    "vix": (
        "VIX (the 'fear gauge')",
        "**What it is:** a measure of how much turbulence options traders expect in the S&P 500 over the next "
        "30 days. Under ~20 is calm, 20–30 is nervous, above 30 is fear.\n\n"
        "**Why it matters to you:** RIOT has tended to fall when the VIX jumps (see the live number in the RIOT "
        "Correlation Map). A spiking VIX is an early warning for miner stocks."
    ),
    "drawdown": (
        "Drawdown",
        "**What it is:** how far the price is below its highest point over a period. -40% means the stock "
        "would need to rise ~67% to get back to that high.\n\n"
        "**Why it matters to you:** miners routinely fall 50–80% in crypto winters. Knowing the current "
        "drawdown helps you judge whether you're buying/holding near a peak or a trough."
    ),
    "volatility": (
        "Volatility",
        "**What it is:** how wildly the price swings, expressed per year. 100% annual volatility means a "
        "typical year could see the price double or halve.\n\n"
        "**Why it matters to you:** as a risk-averse holder, high volatility means you should size the "
        "position so a 50% drop wouldn't force you to sell at the bottom."
    ),
    "rsi": (
        "RSI (Relative Strength Index)",
        "**What it is:** a 0–100 gauge of how hard a stock has been bought or sold over the last 14 trading days. "
        "Under 30–35 = 'oversold' (sold off hard), over 70 = 'overbought'.\n\n"
        "**Why it matters to you:** oversold readings alone don't mean 'buy' — falling stocks can stay oversold. "
        "The plan only says ADD when oversold lines up with a healthy Bitcoin trend, healthy peers and calm markets."
    ),
    "add_signal": (
        "Good time to add? (ADD / WAIT)",
        "**What it is:** a separate check for *buying more*, built for a cautious long-term holder. It says **ADD** only when "
        "the stock is deeply on sale (at least 2 of: RSI under 35, 20%+ below its 200-day average, 40%+ below its 52-week high) "
        "**and** the backdrop is healthy (Bitcoin near/above its 200-day average, VIX under 25, miner peers not in a deep "
        "downtrend). Otherwise it says **WAIT**.\n\n"
        "**Size cap:** it never suggests adding to a stock that's already more than 40% of your portfolio.\n\n"
        "**Why both conditions:** 'cheap' stocks in a crypto bear market often get cheaper. Waiting for a healthy backdrop "
        "gives up some of the bottom in exchange for fewer falling-knife buys. Check the Track Record below to see how "
        "this rule has done in the past."
    ),
    "call_alerts": (
        "How do call-change alerts work?",
        "**What it is:** each time you open My Plan, the dashboard saves today's call (HOLD/TRIM/SELL/ROTATE and ADD/WAIT) "
        "in `data/last_calls.json` on your Replit. If the next check gives a different call, an orange **What changed** "
        "banner shows the old vs new call and which checks flipped, until you click *Got it*.\n\n"
        "**Phone/email alerts (optional, off by default):** in Replit open **Tools → Secrets** and add either\n"
        "- Telegram: `TELEGRAM_BOT_TOKEN` (from @BotFather) and `TELEGRAM_CHAT_ID` (your chat id), or\n"
        "- Email: `SMTP_HOST`, `SMTP_PORT` (587, or 465 for SSL), `SMTP_USER`, `SMTP_PASSWORD` (an app password), "
        "`ALERT_EMAIL_TO`, optional `SMTP_FROM`.\n\n"
        "Then tick *Send me an alert when a call changes* below. An alert is only sent when a change is detected "
        "while the dashboard is open — it doesn't run in the background."
    ),
    "event_calendar": (
        "Why these events matter",
        "**Earnings:** each quarter the company reports results; miners often move 10–20% in a day. Re-check My Plan after.\n\n"
        "**FOMC (Fed rate decision):** the Federal Reserve sets US interest rates 8 times a year. Lower or falling rates "
        "tend to help risky assets like bitcoin and miners; surprises in either direction can move them sharply.\n\n"
        "**CPI (inflation report):** monthly inflation numbers. Hotter-than-expected inflation can mean higher rates for "
        "longer, which usually hurts speculative stocks.\n\n"
        "**Bitcoin halving:** about every 4 years (every 210,000 blocks) the bitcoin miners earn per block is cut in half. "
        "It's the single biggest scheduled hit to miner revenue — unless the bitcoin price rises to make up for it. "
        "Miners that are efficient and have AI/data-center income are better placed to survive it.\n\n"
        "**Tip for a long-term holder:** avoid making big buy/sell decisions on the day before these events; let the "
        "news land, then re-check."
    ),
    "track_record": (
        "How to read the track record (and its limits)",
        "**What it is:** the dashboard pretends it's each day of the last 5 years, looks only at prices known on that day, "
        "and writes down what My Plan would have said. Then it checks what RIOT actually did 1, 3, 6 and 12 months later, "
        "and compares that with buying on *any* random day.\n\n"
        "**Honest limits:**\n"
        "- Only a handful of signals (often under 10). A few lucky or unlucky trades swing the numbers a lot.\n"
        "- Only the market rules can be replayed. Your personal rules (position size, your target, cost basis) and "
        "analyst targets aren't in it.\n"
        "- Miner stocks swing wildly, so a signal can be 'right' at 1 month and 'wrong' at 12.\n"
        "- The peer group is today's list of miners, which slightly flatters the past.\n"
        "- Past results don't predict future ones.\n\n"
        "**How to use it:** if a signal hasn't clearly beaten 'any day', treat it as a prompt to look closer rather than a "
        "trading instruction. For a 2030 holder the position-size rule usually matters more than timing."
    ),
    "sma200": (
        "200-day moving average",
        "**What it is:** the average closing price over the last 200 trading days (~10 months). "
        "Long-term investors use it as a simple trend line.\n\n"
        "**Why it matters to you:** above it = long-term uptrend; below it = long-term downtrend. "
        "Many cautious investors avoid adding while the price is below it."
    ),
    "cost_basis": (
        "Cost basis & unrealized gain",
        "**What it is:** the average price you paid per share. Unrealized gain is the profit you'd lock in "
        "if you sold today (before taxes).\n\n"
        "**Why it matters to you:** selling part of a big winner ('trimming') locks in gains and reduces "
        "the damage if the stock falls back. Long-term (>1 year) gains are usually taxed less in the US."
    ),
    "target_price": (
        "Your target price",
        "**What it is:** the sell target you saved in the Portfolio tab (from `portfolio_targets.json`).\n\n"
        "**Why it matters to you:** when the price reaches your own target, the plan says consider trimming — "
        "this keeps emotion out of the decision."
    ),
    "analyst_targets": (
        "Wall Street analyst targets",
        "**What it is:** 12-month price targets published by brokerage analysts, as reported by Yahoo Finance "
        "(low / average / high).\n\n"
        "**Why it matters to you:** they show what professionals expect, but they're often too optimistic and "
        "change after the price moves. Treat them as one input, not a promise."
    ),
    "projection": (
        "Price projections (bull / base / bear)",
        "**What it is:** 'what-if' price paths to a future date. Each scenario uses a stated yearly return "
        "assumption, and the shaded band shows the range implied by RIOT's own historical volatility.\n\n"
        "**Why it matters to you:** no one can predict the price. Scenarios help you decide in advance what "
        "you'd do in each case — e.g. trim if the bull case arrives early, re-check the thesis if the bear "
        "case shows up."
    ),
    "decoupling": (
        "BTC vs miner decoupling",
        "**What it is:** when miners stop following Bitcoin — e.g. Bitcoin rises but RIOT falls.\n\n"
        "**Why it matters to you:** a lasting gap can mean company-specific problems (dilution, costs, debt) or "
        "a new story (AI hosting). It's a signal to look closer, not to panic."
    ),
    "reflexivity": (
        "Reflexivity (boom/bust loop)",
        "**What it is:** George Soros's idea that prices and fundamentals feed each other. For miners: rising "
        "Bitcoin → fatter margins → miners expand → stocks rise → cheaper capital → more expansion — and the "
        "same loop in reverse during busts.\n\n"
        "**How to read it:** the Reflexivity Index (0–100) is high when miners are tightly coupled to Bitcoin and "
        "amplifying its moves. High + falling prices = bust loop; high + rising prices = boom loop."
    ),
    "var": (
        "Value at Risk (VaR)",
        "**What it is:** the daily loss you shouldn't exceed on 95% of days, based on past price swings. "
        "The other 5% of days can be worse.\n\n"
        "**Why it matters to you:** a quick sense of how much your holdings can move in a single bad day."
    ),
    "monte_carlo": (
        "Monte Carlo simulation",
        "**What it is:** thousands of random future price paths built from the stock's recent average return "
        "and volatility.\n\n"
        "**Caveat:** it assumes the recent past repeats. It's useful for the *range* of outcomes, not the "
        "direction."
    ),
    "recommendation": (
        "How the Hold / Trim / Sell / Rotate call is made",
        "The plan scores a handful of checks (trend vs the 200-day average, drawdown, Bitcoin trend, "
        "fear/VIX, whether RIOT is decoupling from Bitcoin and peers, your gain vs cost basis, your target "
        "price, and how big the position is in your portfolio). It is built for a **risk-averse, long-term holder "
        "with a 2030 plan**, so it favours *Hold* unless several warning signs line up, and favours *Trim* "
        "(not all-out selling) when risk or concentration gets high.\n\n"
        "**Hold** = no action needed. **Trim** = sell a slice (e.g. 10–25%) to lock gains/cut risk. "
        "**Sell** = several serious warnings at once. **Rotate** = move some money from RIOT into a peer "
        "that is doing the same job with better momentum.\n\n"
        "This is an educational tool, **not financial advice**."
    ),
}

from utils.explain_signals import SIGNAL_GLOSSARY  # noqa: E402  (signals / news / forecast help)
GLOSSARY.update(SIGNAL_GLOSSARY)

HELP = {k: v[1].replace("**", "") for k, v in GLOSSARY.items()}


def explain(key: str, expanded: bool = False) -> None:
    """Render a small 'ℹ️ What is this?' expander for a glossary key."""
    item = GLOSSARY.get(key)
    if not item:
        return
    title, body = item
    with st.expander(f"ℹ️ What is this? — {title}", expanded=expanded):
        st.markdown(body)
