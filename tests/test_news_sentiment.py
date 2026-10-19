from datetime import datetime, timezone

import utils.news_sentiment as ns


def test_headline_scoring_is_transparent():
    assert ns.score_headline("Riot beats estimates, shares surge")["score"] == 1.0
    assert ns.score_headline("MARA plunges after dilutive offering")["score"] == -1.0
    r = ns.score_headline("Riot stock selloff raises questions")
    assert r["score"] < 0 and "selloff" in r["neg"] and "raises" in r["pos"]
    assert ns.score_headline("Form 144 filed")["score"] == 0.0


def test_aggregate_and_labels():
    items = [ns.score_headline(t) for t in ["shares surge", "stock plunges", "quarterly report", "record growth"]]
    a = ns.aggregate(items)
    assert a["available"] and a["n_headlines"] == 4 and a["n_pos"] == 2 and a["n_neg"] == 1
    assert a["label"] == ns.label(a["score"])
    assert ns.label(0.2) == "Bullish" and ns.label(-0.2) == "Bearish" and ns.label(0.0) == "Neutral"


def test_empty_is_unavailable_not_neutral():
    a = ns.aggregate([])
    assert a["available"] is False and a["score"] is None and a["label"] == "n/a"


def test_total_outage_returns_unavailable(monkeypatch):
    def boom(_):
        raise ConnectionError("offline")
    monkeypatch.setattr(ns, "_yahoo_items", boom)
    monkeypatch.setattr(ns, "_google_items", boom)
    monkeypatch.setattr(ns, "_alpha_vantage", lambda s: None)
    r = ns.news_sentiment("ZZZZ")
    assert r["available"] is False and r["score"] is None


def test_engines_share_news_numbers(monkeypatch):
    fake = {"available": True, "score": -0.4, "label": "Bearish", "items": [], "n_headlines": 5}
    monkeypatch.setattr(ns, "news_sentiment", lambda s: fake)
    from utils.trade_signal_engine import TradeSignalEngine
    from utils.next_mover_engine import NextMoverEngine
    assert TradeSignalEngine()._get_sentiment_score("RIOT") == -0.4
    eng = NextMoverEngine.__new__(NextMoverEngine); eng.mining_stocks = ["RIOT"]
    s = eng.analyze_sentiment_scores()["RIOT"]
    assert s["live"] and s["raw"] == -0.4 and s["label"] == "Bearish"


def test_unavailable_news_is_left_out(monkeypatch):
    monkeypatch.setattr(ns, "news_sentiment", lambda s: {"available": False, "score": None, "label": "n/a"})
    from utils.trade_signal_engine import TradeSignalEngine
    assert TradeSignalEngine()._get_sentiment_score("RIOT") is None
    c = TradeSignalEngine().classify_signal(rsi=50, macd_hist=0, macd_hist_prev=0, volume_ratio=1, daily_return=0,
                                            sentiment_score=None, pct_vs_20ma=0, pct_vs_50ma=0, ma50_slope=0,
                                            pct_b=0.5, stoch_k=50, stoch_d=50, obv_slope=0, btc_score=0)
    assert any("unavailable" in r for r in c["reasons"])


def test_alpha_vantage_information_is_an_error(monkeypatch):
    import utils.sentiment_analyzer as sa

    class R:
        status_code = 200
        def json(self):
            return {"Information": "We have detected your API key ... rate limit"}
    monkeypatch.setenv("ALPHA_VANTAGE_API_KEY", "dummy")
    monkeypatch.setattr(sa.requests, "get", lambda *a, **k: R())
    assert "error" in sa.SentimentAnalyzer().get_news_sentiment(["RIOT"])
