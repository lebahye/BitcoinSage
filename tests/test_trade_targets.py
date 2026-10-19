import numpy as np
import pandas as pd

from utils.trade_signal_engine import TradeSignalEngine


def _crash_hist():
    # rally to 28 then crash to 14 — the shape that produced 17:1 / 121:1 risk-reward before
    up = np.linspace(20, 28, 40); down = np.linspace(28, 14, 25)
    c = np.concatenate([up, down])
    idx = pd.bdate_range("2026-07-01", periods=len(c))
    return pd.DataFrame({"Open": c, "High": c * 1.02, "Low": c * 0.98, "Close": c, "Volume": 1e6}, index=idx)


def test_targets_below_swing_high_after_crash():
    pt = TradeSignalEngine()._calc_price_targets(_crash_hist())
    swing_hi = 28 * 1.02
    assert pt["take_profit_1"] < swing_hi
    assert "retracement" in pt["tp1_label"]
    assert pt["entry"] - pt["stop_loss"] >= pt["atr"] * 0.99 or pt["stop_loss"] <= pt["current_price"] * 0.85 + 1e-6
    assert pt["risk_reward"] < 10
