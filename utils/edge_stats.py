"""
utils/edge_stats.py — the honest-backtest engine behind the 🧪 Edge Lab page.

Every Edge Lab tool produces a *point-in-time* signal: the value on date t uses
only prices up to and including t.  This module asks one question of each
signal: "after the signal said X, did the next H trading days really turn out
different from the times it did not say X?"

Method (deliberately conservative)
----------------------------------
1. Sample the signal every `step` bars (weekly by default) so neighbouring
   samples are not near-duplicates.
2. Outcome for a sample at t: the forward log return over the next `horizon`
   bars, or the worst drawdown from the close at t within those bars.  The
   outcome only uses bars t+1 … t+horizon, so nothing from the future leaks
   into the signal and the signal never sees its own outcome.
3. Statistic = mean outcome when the signal is ON minus mean when OFF.
4. Significance by a *circular-shift permutation*: the ON/OFF sequence is
   rotated by a random offset (at least one horizon) against the outcomes many
   times.  Rotation keeps the signal's own clustering and the outcomes'
   autocorrelation, so overlapping forward windows cannot fake significance
   the way a naive t-test would.  The rotated signals are also the "random
   baseline": a signal with the same on/off rhythm but no information.
5. Out-of-sample split: first 60% of dates = in-sample, last 40% = OOS.  Every
   threshold in Edge Lab is fixed in advance (never tuned), so the OOS half is
   a genuine hold-out.
6. Verdict
   * "insufficient data" — fewer than MIN_EFF independent ON (or OFF) episodes
     overall or fewer than MIN_EFF_OOS in the hold-out.
   * "edge found" — the effect points the hypothesised way in BOTH halves,
     full-sample p < 0.05 and hold-out p < 0.10.
   * "no reliable edge" — anything else.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Optional

import numpy as np
import pandas as pd

EDGE = "edge found"
NO_EDGE = "no reliable edge"
INSUFFICIENT = "insufficient data"

MIN_EFF = 6.0       # independent ON / OFF episodes needed over the full sample
MIN_EFF_OOS = 3.0   # … and inside the hold-out
P_FULL = 0.05
P_OOS = 0.10


def forward_log_return(price: pd.Series, horizon: int) -> pd.Series:
    """log(P[t+h]/P[t]) stamped at t (NaN for the last h bars)."""
    lp = np.log(price.astype(float))
    return lp.shift(-horizon) - lp


def forward_drawdown(price: pd.Series, horizon: int) -> pd.Series:
    """Worst close in (t, t+h] relative to the close at t, minus 1 (≤ 0), stamped at t."""
    p = price.astype(float).values
    n = len(p)
    out = np.full(n, np.nan)
    for i in range(n - horizon):
        out[i] = p[i + 1:i + 1 + horizon].min() / p[i] - 1.0
    return pd.Series(np.minimum(out, 0.0), index=price.index)


def _diff(on: np.ndarray, y: np.ndarray) -> float:
    a, b = y[on], y[~on]
    if len(a) == 0 or len(b) == 0:
        return np.nan
    return float(a.mean() - b.mean())


def shift_permutation_p(on: np.ndarray, y: np.ndarray, min_shift: int, n_perm: int = 2000,
                        seed: int = 0) -> tuple[float, float, np.ndarray]:
    """Two-sided p-value of mean(y|on) − mean(y|off) against circular shifts of `on`."""
    obs = _diff(on, y)
    n = len(on)
    if np.isnan(obs) or n < 2 * min_shift + 2:
        return obs, np.nan, np.array([])
    rng = np.random.default_rng(seed)
    shifts = rng.integers(min_shift, n - min_shift, size=n_perm)
    null = np.array([_diff(np.roll(on, k), y) for k in shifts])
    null = null[~np.isnan(null)]
    if len(null) == 0:
        return obs, np.nan, null
    p = (1 + np.sum(np.abs(null) >= abs(obs) - 1e-15)) / (1 + len(null))
    return obs, float(p), null


@dataclass
class EdgeResult:
    verdict: str
    hypothesis: str
    effect: Optional[float]           # mean(on) − mean(off), full sample
    p_full: Optional[float]
    effect_is: Optional[float]
    effect_oos: Optional[float]
    p_oos: Optional[float]
    mean_on: Optional[float]
    mean_off: Optional[float]
    baseline: Optional[float]         # unconditional mean outcome (= buy-and-hold for returns)
    null_band: Optional[tuple]        # 5–95% of the random (shifted-signal) effects
    n_samples: int
    n_on: int
    eff_on: float                     # ≈ independent ON episodes (= n_on·step/horizon)
    eff_off: float
    eff_on_oos: float
    split_date: Optional[str]
    start: Optional[str]
    end: Optional[str]
    horizon: int
    outcome: str

    def as_dict(self):
        return asdict(self)


def _f(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(x)


def evaluate_signal(signal: pd.Series, outcome: pd.Series, horizon: int, *, direction: int,
                    hypothesis: str, outcome_name: str = "fwd log return", step: int = 5,
                    oos_frac: float = 0.4, n_perm: int = 2000, seed: int = 0) -> EdgeResult:
    """Test a boolean point-in-time `signal` against a forward `outcome` (both indexed by date).

    direction = +1 if the hypothesis says outcomes are HIGHER when ON, −1 if LOWER.
    `signal` may contain NaN (= not computable yet) — those dates are skipped.
    """
    df = pd.DataFrame({"s": signal, "y": outcome}).dropna()
    df = df.iloc[::max(1, step)]
    n = len(df)
    on = df["s"].astype(bool).values
    y = df["y"].astype(float).values
    k = max(1, int(np.ceil(horizon / max(1, step))))   # samples per independent window
    eff = lambda m: float(m) / k  # noqa: E731
    empty = EdgeResult(INSUFFICIENT, hypothesis, None, None, None, None, None, None, None,
                       _f(y.mean()) if n else None, None, n, int(on.sum()) if n else 0,
                       eff(on.sum()) if n else 0.0, eff((~on).sum()) if n else 0.0, 0.0, None,
                       str(df.index[0].date()) if n else None, str(df.index[-1].date()) if n else None,
                       horizon, outcome_name)
    if n < 4 * k or on.sum() == 0 or (~on).sum() == 0:
        return empty
    cut = int(round(n * (1 - oos_frac)))
    obs, p, null = shift_permutation_p(on, y, k, n_perm, seed)
    e_is, _, _ = shift_permutation_p(on[:cut], y[:cut], k, 1, seed)
    e_oos, p_oos, _ = shift_permutation_p(on[cut:], y[cut:], k, n_perm, seed + 1)
    res = EdgeResult(
        verdict=NO_EDGE, hypothesis=hypothesis, effect=_f(obs), p_full=_f(p), effect_is=_f(e_is),
        effect_oos=_f(e_oos), p_oos=_f(p_oos), mean_on=_f(y[on].mean()), mean_off=_f(y[~on].mean()),
        baseline=_f(y.mean()),
        null_band=(float(np.percentile(null, 5)), float(np.percentile(null, 95))) if len(null) else None,
        n_samples=n, n_on=int(on.sum()), eff_on=eff(on.sum()), eff_off=eff((~on).sum()),
        eff_on_oos=eff(on[cut:].sum()), split_date=str(df.index[cut].date()) if cut < n else None,
        start=str(df.index[0].date()), end=str(df.index[-1].date()), horizon=horizon, outcome=outcome_name)
    if (res.eff_on < MIN_EFF or res.eff_off < MIN_EFF or res.eff_on_oos < MIN_EFF_OOS
            or eff((~on[cut:]).sum()) < MIN_EFF_OOS):
        res.verdict = INSUFFICIENT
        return res
    same_way = all(v is not None and np.sign(v) == np.sign(direction) for v in (res.effect_is, res.effect_oos))
    if same_way and res.p_full is not None and res.p_full < P_FULL and res.p_oos is not None and res.p_oos < P_OOS:
        res.verdict = EDGE
    return res


def expanding_pct_rank(x: pd.Series, min_periods: int = 252) -> pd.Series:
    """Point-in-time percentile (0–1) of each value among all values up to and including that date."""
    v = x.values.astype(float)
    out = np.full(len(v), np.nan)
    hist = []
    import bisect
    for i, xi in enumerate(v):
        if np.isnan(xi):
            continue
        bisect.insort(hist, xi)
        if len(hist) >= min_periods:
            out[i] = bisect.bisect_right(hist, xi) / len(hist)
    return pd.Series(out, index=x.index)


def stationary_bootstrap_idx(n: int, block: float, rng: np.random.Generator) -> np.ndarray:
    """Politis–Romano stationary bootstrap indices (mean block length `block`)."""
    idx = np.empty(n, dtype=int)
    idx[0] = rng.integers(n)
    p = 1.0 / block
    for i in range(1, n):
        idx[i] = rng.integers(n) if rng.random() < p else (idx[i - 1] + 1) % n
    return idx
