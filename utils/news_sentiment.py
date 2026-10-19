"""
utils/news_sentiment.py — real headlines and an honest headline-tone score, no API key needed.

Sources (all free, no key):
  1. Yahoo Finance news search (yfinance `Search`) — headlines tagged with the ticker.
  2. Google News RSS search for the company name / ticker (last 7 days).
  3. Optional: if ALPHA_VANTAGE_API_KEY is set and the call succeeds, Alpha Vantage's
     per-ticker NLP sentiment scores are used instead of the keyword method.

Scoring (when Alpha Vantage isn't available) is a transparent keyword count on each
headline using a short finance word list (inspired by the Loughran-McDonald dictionary):
    headline tone = (positive words − negative words) / (positive + negative), 0 if none.
The stock's tone is the average over its recent headlines, from −1 (very negative) to +1.
This reads the *tone of the headlines*; it is not AI, it can misread sarcasm/negation,
and it has not been shown to predict prices.  It is labelled that way in the UI.

When nothing can be fetched the result is {'available': False} — never a fake neutral.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import quote_plus

try:
    import streamlit as st
    _cache30 = st.cache_data(ttl=1800, show_spinner=False)
    _cache60 = st.cache_data(ttl=3600, show_spinner=False)
except Exception:  # pragma: no cover
    def _cache30(fn):
        return fn
    _cache60 = _cache30

LOOKBACK_DAYS = 7
BULLISH, BEARISH = 0.15, -0.15        # same label cut-offs Alpha Vantage uses

# Company names for news search (keep in sync with utils/tickers.py)
SEARCH_NAMES: Dict[str, str] = {
    "RIOT": "Riot Platforms", "MARA": "MARA Holdings", "CLSK": "CleanSpark", "HUT": "Hut 8",
    "KEEL": "Keel Infrastructure", "BTBT": "Bit Digital", "CIFR": "Cipher Mining",
    "CORZ": "Core Scientific", "IREN": "IREN Ltd", "WULF": "TeraWulf", "BTC-USD": "Bitcoin",
}

POSITIVE = {
    "beat", "beats", "surge", "surges", "surged", "soar", "soars", "soared", "jump", "jumps", "jumped",
    "rally", "rallies", "rallied", "gain", "gains", "gained", "record", "upgrade", "upgrades", "upgraded",
    "outperform", "outperforms", "bullish", "growth", "profit", "profitable", "strong", "stronger",
    "rise", "rises", "rose", "climb", "climbs", "climbed", "boost", "boosts", "expands", "expansion",
    "deal", "partnership", "lease", "leases", "contract", "wins", "win", "approval", "approved", "buy",
    "optimistic", "high", "highs", "rebound", "rebounds", "recover", "recovers", "recovery", "raises",
    "accelerates", "milestone", "breakout", "upside", "undervalued",
}
NEGATIVE = {
    "miss", "misses", "missed", "plunge", "plunges", "plunged", "fall", "falls", "fell", "drop", "drops",
    "dropped", "slump", "slumps", "slide", "slides", "tumble", "tumbles", "crash", "crashes", "selloff",
    "sell-off", "downgrade", "downgrades", "downgraded", "underperform", "bearish", "loss", "losses",
    "weak", "weaker", "decline", "declines", "declined", "cut", "cuts", "lawsuit", "probe", "investigation",
    "dilution", "dilutive", "offering", "debt", "risk", "risks", "concern", "concerns", "warning", "warns",
    "low", "lows", "sell", "selling", "fears", "fear", "pressure", "halt", "delay", "delays", "struggle",
    "struggles", "harder", "downside", "questions", "bankruptcy", "default", "overvalued",
}
_WORD = re.compile(r"[a-z][a-z\-']+")


def score_headline(title: str) -> dict:
    """Keyword tone of one headline: score in [-1, 1] plus the words that matched."""
    words = _WORD.findall((title or "").lower())
    pos = [w for w in words if w in POSITIVE]
    neg = [w for w in words if w in NEGATIVE]
    n = len(pos) + len(neg)
    return {"score": (len(pos) - len(neg)) / n if n else 0.0, "pos": pos, "neg": neg}


def label(score: Optional[float]) -> str:
    if score is None:
        return "n/a"
    return "Bullish" if score >= BULLISH else "Bearish" if score <= BEARISH else "Neutral"


def aggregate(items: List[dict]) -> dict:
    """Average tone over headlines (pure function, unit-tested)."""
    if not items:
        return {"available": False, "score": None, "label": "n/a", "n_headlines": 0, "n_with_keywords": 0}
    scores = [it["score"] for it in items]
    avg = sum(scores) / len(scores)
    return {"available": True, "score": avg, "label": label(avg), "n_headlines": len(items),
            "n_with_keywords": sum(1 for it in items if it.get("pos") or it.get("neg")),
            "n_pos": sum(1 for s in scores if s > 0), "n_neg": sum(1 for s in scores if s < 0)}


def _norm(t: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", (t or "").lower().split(" - ")[0]).strip()


def _yahoo_items(symbol: str) -> List[dict]:
    import yfinance as yf
    out = []
    for n in (yf.Search(symbol, news_count=20).news or []):
        rel = n.get("relatedTickers") or []
        if symbol not in rel and symbol.lower() not in (n.get("title") or "").lower():
            continue
        ts = n.get("providerPublishTime")
        out.append({"title": n.get("title", ""), "publisher": n.get("publisher", ""), "link": n.get("link", ""),
                    "published": datetime.fromtimestamp(ts, timezone.utc) if ts else None, "via": "Yahoo Finance"})
    return out


def _google_items(symbol: str) -> List[dict]:
    import requests
    name = SEARCH_NAMES.get(symbol, symbol)
    q = quote_plus(f'"{name}" OR "{symbol} stock" when:{LOOKBACK_DAYS}d')
    r = requests.get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", timeout=12,
                     headers={"User-Agent": "Mozilla/5.0 BitcoinSage"})
    r.raise_for_status()
    out = []
    for it in ET.fromstring(r.content).iter("item"):
        title = it.findtext("title") or ""
        src = it.findtext("source") or ""
        if src and title.endswith(" - " + src):
            title = title[: -len(" - " + src)]
        try:
            pub = parsedate_to_datetime(it.findtext("pubDate"))
        except Exception:
            pub = None
        out.append({"title": title, "publisher": src, "link": it.findtext("link") or "", "published": pub,
                    "via": "Google News"})
    return out[:30]


def _alpha_vantage(symbol: str) -> Optional[dict]:
    """Alpha Vantage per-ticker NLP scores, or None (no key / rate limit / error)."""
    if not os.environ.get("ALPHA_VANTAGE_API_KEY"):
        return None
    from utils.sentiment_analyzer import SentimentAnalyzer
    raw = SentimentAnalyzer().get_news_sentiment([symbol], limit=50)
    if not isinstance(raw, dict) or "error" in raw or not raw.get("feed"):
        return None
    items = []
    for a in raw["feed"]:
        ts = next((t for t in a.get("ticker_sentiment", []) if t.get("ticker") == symbol), None)
        if not ts or float(ts.get("relevance_score", 0) or 0) < 0.1:
            continue
        try:
            pub = datetime.strptime(a.get("time_published", ""), "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
        except Exception:
            pub = None
        items.append({"title": a.get("title", ""), "publisher": a.get("source", ""), "link": a.get("url", ""),
                      "published": pub, "via": "Alpha Vantage", "score": float(ts.get("ticker_sentiment_score", 0)),
                      "pos": [], "neg": []})
    return {"items": items} if items else None


@_cache30
def _news_cached(symbol: str) -> dict:
    errors = []
    av = None
    try:
        av = _alpha_vantage(symbol)
    except Exception as e:
        errors.append(f"Alpha Vantage: {type(e).__name__}")
    if av:
        items, method = av["items"], "Alpha Vantage NLP sentiment (per-ticker scores)"
    else:
        items, seen = [], set()
        for fn in (_yahoo_items, _google_items):
            try:
                for it in fn(symbol):
                    k = _norm(it["title"])
                    if k and k not in seen:
                        seen.add(k)
                        items.append(it)
            except Exception as e:
                errors.append(f"{fn.__name__.strip('_').split('_')[0].title()}: {type(e).__name__}")
        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
        items = [it for it in items if it["published"] is None or it["published"] >= cutoff]
        for it in items:
            it.update(score_headline(it["title"]))
        method = "Keyword tone of headlines (finance word list) — not AI, not validated as predictive"
    if not items and len(errors) >= 2:
        raise RuntimeError("; ".join(errors))      # don't cache a total outage
    items.sort(key=lambda it: it["published"] or datetime(1970, 1, 1, tzinfo=timezone.utc), reverse=True)
    out = aggregate(items)
    out.update({"symbol": symbol, "method": method, "items": items[:25], "errors": errors,
                "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
                "sources": sorted({it["via"] for it in items})})
    return out


def news_sentiment(symbol: str) -> dict:
    """Headlines + tone for one ticker (cached 30 min). {'available': False, ...} on failure."""
    try:
        return _news_cached(symbol)
    except Exception as e:
        return {"available": False, "score": None, "label": "n/a", "symbol": symbol, "items": [],
                "n_headlines": 0, "error": str(e), "method": "", "sources": []}


@_cache60
def _fng_cached() -> dict:
    import requests
    d = requests.get("https://api.alternative.me/fng/?limit=8", timeout=10).json()["data"]
    cur = d[0]
    return {"value": int(cur["value"]), "label": cur["value_classification"],
            "yesterday": int(d[1]["value"]) if len(d) > 1 else None,
            "week_ago": int(d[7]["value"]) if len(d) > 7 else None,
            "as_of": datetime.fromtimestamp(int(cur["timestamp"]), timezone.utc).strftime("%Y-%m-%d"),
            "source": "alternative.me Crypto Fear & Greed Index"}


def crypto_fear_greed() -> Optional[dict]:
    """The published Crypto Fear & Greed Index (0 = extreme fear, 100 = extreme greed), or None."""
    try:
        return _fng_cached()
    except Exception:
        return None
