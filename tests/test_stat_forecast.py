import numpy as np
import pandas as pd
import pytest

from utils.stat_forecast import backtest_coverage, forecast_range, coverage_verdict


def _gbm(n=1500, sigma=0.04, seed=3):
    rng = np.random.default_rng(seed)
    return pd.Series(15 * np.exp(np.cumsum(rng.normal(0, sigma, n))), index=pd.bdate_range("2019-01-01", periods=n))


def test_range_brackets_price_and_widens_with_horizon():
    px = _gbm()
    w, m = forecast_range(px, 5), forecast_range(px, 21)
    for f in (w, m):
        assert f["low_90%"] < f["low_68%"] < f["price"] < f["high_68%"] < f["high_90%"]
        assert f["centre"] == f["price"]          # no directional guess
    assert m["high_68%"] - m["low_68%"] > w["high_68%"] - w["low_68%"]


def test_coverage_matches_theory_on_random_walk():
    cov = backtest_coverage(_gbm(), 21, years=4, step=1)
    assert cov["hit_68%"] == pytest.approx(0.68, abs=0.08)
    assert cov["hit_90%"] == pytest.approx(0.90, abs=0.06)
    assert "Well calibrated" in coverage_verdict(cov)


def test_short_history_returns_none():
    px = _gbm(n=40)
    assert forecast_range(px, 5) is None and backtest_coverage(px, 5) is None
    assert "Not enough" in coverage_verdict(None)


def test_target_inside_its_own_range():
    # Regression: old Forecast Center showed a 1-month 'target' of -88% outside its own 'expected range'.
    f = forecast_range(_gbm(), 21)
    assert f["low_90%"] <= f["centre"] <= f["high_90%"]
