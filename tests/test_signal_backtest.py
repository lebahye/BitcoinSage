import numpy as np
import pandas as pd
from utils import signal_backtest as sb


def _closes(n=1600, seed=0):
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range("2019-01-01", periods=n)
    riot = pd.Series(10 * np.exp(np.cumsum(rng.normal(0, 0.04, n))), idx)
    peers = {p: pd.Series(10 * np.exp(np.cumsum(rng.normal(0, 0.04, n))), idx) for p in ("MARA", "CLSK")}
    bidx = pd.date_range(idx[0], idx[-1], freq="D")
    btc = pd.Series(30000 * np.exp(np.cumsum(rng.normal(0, 0.02, len(bidx)))), bidx)
    vix = pd.Series(np.clip(20 + np.cumsum(rng.normal(0, 0.5, n)), 10, 60), idx)
    return pd.DataFrame({"RIOT": riot, **peers, "^VIX": vix}).join(btc.rename("BTC-USD"), how="outer")


def test_no_lookahead_features_unchanged_by_future_data():
    c = _closes()
    full = sb.score_days(sb.build_features(c, "RIOT", ["MARA", "CLSK"]))
    cut = c.loc[: "2023-06-30"]
    part = sb.score_days(sb.build_features(cut, "RIOT", ["MARA", "CLSK"]))
    common = part.index.intersection(full.index)
    cols = ["sma200", "drawdown", "rsi", "btc200", "peer_vs_200", "risk", "add"]
    pd.testing.assert_frame_equal(part.loc[common, cols], full.loc[common, cols], check_dtype=False)


def test_episodes_and_forward_returns():
    flag = pd.Series([False, True, True, False, True] + [False] * 30 + [True], index=pd.bdate_range("2024-01-01", periods=36))
    ep = sb.episodes(flag, cooldown=20)
    assert list(ep) == [flag.index[1], flag.index[35]]
    px = pd.Series(np.arange(1.0, 301.0), index=pd.bdate_range("2024-01-01", periods=300))
    fr = sb.forward_returns(px, pd.DatetimeIndex([px.index[0]]))
    assert fr["entry"].iloc[0] == 2.0                      # next day's close
    assert abs(fr["1M"].iloc[0] - (23.0 / 2.0 - 1)) < 1e-12
    assert np.isnan(sb.forward_returns(px, pd.DatetimeIndex([px.index[-30]]))["3M"].iloc[0])


def test_run_backtest_shapes():
    r = sb.run_backtest(_closes(), "RIOT", ["MARA", "CLSK"], years=3)
    assert set(r["summary"]) == {"ADD", "SELL (5+ risk pts)", "Caution (3+ risk pts)"}
    assert "Just hold" in r["strategy"]["equity"].columns
    assert r["baseline"]["1M"]["n"] > 500
    assert "Trust" in sb.verdict("ADD", r["summary"]["ADD"], r["baseline"]) or "no completed" in sb.verdict("ADD", r["summary"]["ADD"], r["baseline"])
