import numpy as np
import pandas as pd

from utils.riot_correlation import compute_correlations, group_summary, divergence_check


def _synthetic():
    rng = np.random.default_rng(1)
    days = pd.bdate_range("2025-09-01", periods=300)
    common = rng.normal(0, 0.03, len(days))
    riot = 20 * np.exp(np.cumsum(common + rng.normal(0, 0.01, len(days))))
    peer = 10 * np.exp(np.cumsum(common + rng.normal(0, 0.01, len(days))))
    inv = 15 * np.exp(np.cumsum(-0.5 * common + rng.normal(0, 0.01, len(days))))
    noise = 50 * np.exp(np.cumsum(rng.normal(0, 0.02, len(days))))
    return pd.DataFrame({"RIOT": riot, "PEER": peer, "INV": inv, "NOISE": noise}, index=days)


UNI = {"PEER": ("Miners", "peer"), "INV": ("Macro", "inverse"), "NOISE": ("Bitcoin", "unrelated")}


def test_ranking_and_signs():
    df = compute_correlations(_synthetic(), "RIOT", UNI)
    assert df.iloc[0]["ticker"] == "PEER" and df.iloc[0]["corr_1y"] > 0.8
    inv = df[df.ticker == "INV"].iloc[0]
    assert inv["corr_1y"] < -0.5 and inv["stability"] == "steady"
    g = group_summary(df)
    assert g.index[0] == "Miners"


def test_divergence_runs():
    d = divergence_check(_synthetic(), ["PEER"], "RIOT")
    assert d is not None and d["corr_year"] > 0.8
