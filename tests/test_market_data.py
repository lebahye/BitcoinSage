import numpy as np
import pandas as pd

from utils.market_data import to_daily, to_stock_calendar, aligned_returns, beta_corr, align_frame


def _stock_and_btc():
    # Stock: weekdays at 00:00 New York; BTC: every day at 00:00 UTC (Yahoo's real stamps)
    days = pd.date_range("2026-01-01", "2026-06-30", freq="D")
    rng = np.random.default_rng(0)
    btc_ret = rng.normal(0, 0.03, len(days))
    btc = pd.Series(50000 * np.cumprod(1 + btc_ret), index=days.tz_localize("UTC"))
    wd = days[days.dayofweek < 5]
    btc_on_wd = btc.copy(); btc_on_wd.index = days
    btc_on_wd = btc_on_wd.reindex(wd)
    stock_ret = 2.0 * btc_on_wd.pct_change().fillna(0) + rng.normal(0, 0.005, len(wd))
    stock = pd.Series(10 * np.cumprod(1 + stock_ret.values), index=wd.tz_localize("America/New_York"))
    return stock, btc


def test_raw_join_has_no_overlap_but_aligned_does():
    stock, btc = _stock_and_btc()
    raw = pd.DataFrame({"s": stock.pct_change(), "b": btc.pct_change()}).dropna()
    assert len(raw) == 0  # this is the original bug
    r = aligned_returns(stock, btc)
    assert len(r) > 100


def test_weekend_folded_into_monday():
    btc = pd.Series([100, 110, 121, 133.1], index=pd.to_datetime(
        ["2026-03-06", "2026-03-07", "2026-03-08", "2026-03-09"]).tz_localize("UTC"))  # Fri..Mon
    stock_dates = pd.to_datetime(["2026-03-06", "2026-03-09"])
    on = to_stock_calendar(btc, stock_dates)
    assert list(on.values) == [100, 133.1]
    assert abs(on.pct_change().iloc[-1] - 0.331) < 1e-9  # Fri->Mon includes weekend


def test_beta_recovers_true_value():
    stock, btc = _stock_and_btc()
    bc = beta_corr(stock, btc)
    assert bc is not None
    assert 1.7 < bc["beta"] < 2.3
    assert bc["corr"] > 0.9


def test_insufficient_data_returns_none():
    stock, btc = _stock_and_btc()
    assert beta_corr(stock.iloc[:5], btc) is None


def test_align_frame_uses_stock_calendar():
    stock, btc = _stock_and_btc()
    df = align_frame(pd.DataFrame({"RIOT": to_daily(stock), "BTC-USD": to_daily(btc)}))
    assert (df.index.dayofweek < 5).all()
    assert df["BTC-USD"].notna().sum() > 100
