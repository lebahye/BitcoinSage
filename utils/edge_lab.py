"""
utils/edge_lab.py — experimental "obscure math" tools for the 🧪 Edge Lab page.

Pure functions only (no Streamlit, no network) so every tool is unit-tested on
synthetic data and every number is point-in-time: a reading stamped on date t
uses prices up to and including t, never after.

Tools
  1. LPPLS bubble hazard        (Sornette's log-periodic power law singularity)
  2. Fragility meter             (critical slowing down + rising variance + permutation entropy)
  3. Trend-memory regime         (Hurst exponent via detrended fluctuation analysis)
  4. Crash odds                  (extreme-value GPD tails + copula tail asymmetry vs BTC)
  5. Halving clock               (phase-folding Bitcoin's 4-year cycle)
  6. Tail-aware Kelly sizer      (growth-optimal RIOT weight, walk-forward)

Nothing here is wired into My Plan or the Stock Verdict.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

import numpy as np
import pandas as pd

from utils import edge_stats as es

# RIOT was Bioptix (a biotech) until it renamed to Riot Blockchain on 2017-10-04.
# Before that date its price has nothing to do with bitcoin mining.
# Same idea for peers: Marathon Patent Group began mining in late 2017, CleanSpark (an energy-software
# company) bought its first mining site in Dec 2020.
MINER_START = {"RIOT": "2017-10-04", "MARA": "2017-11-01", "CLSK": "2020-12-10"}
HALVINGS = [date(2012, 11, 28), date(2016, 7, 9), date(2020, 5, 11), date(2024, 4, 20)]
NEXT_HALVING_EST = date(2028, 4, 15)


def clean(series: pd.Series, symbol: str = "") -> pd.Series:
    s = series.dropna().astype(float)
    s = s[s > 0]
    st = MINER_START.get(symbol.upper())
    if st:
        s = s[s.index >= pd.Timestamp(st)]
    return s


# ════════════════════════════════════════════════════════════════════════
# 1 · LPPLS bubble hazard
# ════════════════════════════════════════════════════════════════════════
# ln p(t) = A + B·τ^m + C1·τ^m·cos(ω ln τ) + C2·τ^m·sin(ω ln τ),  τ = tc − t
# For fixed (tc, m, ω) the model is linear in (A, B, C1, C2) — Filimonov &
# Sornette (2013) — so we grid-search the 3 nonlinear parameters and solve the
# 4 linear ones exactly by least squares.  A window "qualifies" as a bubble if
# its best fit passes the standard Sornette filters:
#   0.01 < m < 0.99, 2 < ω < 15, tc within (t2, t2 + 0.2·dt],
#   damping m|B| / (ω|C|) ≥ 0.8, oscillations ω/π·ln((tc−t1)/(tc−t2)) ≥ 2.5,
#   B < 0 → positive (upward, crash-prone) bubble; B > 0 → negative bubble (anti-bubble).
# LPPLS confidence = share of the fitting windows (different start dates, same end)
# that qualify.  It is causal by construction.
LPPLS_WINDOWS = (60, 90, 125, 165, 210, 260, 315, 375, 440)
LPPLS_TC = (0.02, 0.05, 0.1, 0.15, 0.2)       # tc − t2 as a fraction of the window length
LPPLS_M = (0.1, 0.25, 0.4, 0.55, 0.7, 0.85)
LPPLS_W = (3.0, 4.5, 6.0, 7.5, 9.0, 11.0, 13.0)


from functools import lru_cache  # noqa: E402


@lru_cache(maxsize=64)
def _lppls_basis(n: int):
    """Design matrices and pseudo-inverses for every (tc, m, ω) grid point for a window of n bars.
    They depend only on n (time runs 0…n−1), so each is built once and reused for every date."""
    t = np.arange(n, dtype=float)
    dt = float(n - 1)
    Xs, params = [], []
    for tcf in LPPLS_TC:
        tc = dt + tcf * dt
        tau = tc - t
        ltau = np.log(tau)
        for m in LPPLS_M:
            f = tau ** m
            for w in LPPLS_W:
                Xs.append(np.column_stack([np.ones(n), f, f * np.cos(w * ltau), f * np.sin(w * ltau)]))
                params.append((tcf, tc, m, w))
    X = np.stack(Xs)                                   # (G, n, 4)
    Xp = np.linalg.pinv(X)                             # (G, 4, n)
    return X, Xp, params


def lppls_fit_window(logp: np.ndarray) -> Optional[dict]:
    """Best grid fit of one window. Returns params + whether it qualifies (positive / negative)."""
    logp = np.asarray(logp, float)
    n = len(logp)
    if n < 30 or not np.all(np.isfinite(logp)):
        return None
    X, Xp, params = _lppls_basis(n)
    coefs = Xp @ logp                                  # (G, 4) exact least squares per grid point
    resid = logp[None, :] - np.einsum("gnk,gk->gn", X, coefs)
    sse = np.einsum("gn,gn->g", resid, resid)
    g = int(np.argmin(sse))
    tcf, tc, m, w = params[g]
    A, B, C1, C2 = coefs[g]
    dt = float(n - 1)
    C = float(np.hypot(C1, C2))
    damping = m * abs(B) / (w * C) if C > 0 else np.inf
    osc = w / np.pi * np.log(tc / (tc - dt))
    ok = (0.01 < m < 0.99) and (2 < w < 15) and damping >= 0.8 and osc >= 2.5
    return {"A": float(A), "B": float(B), "C": C, "m": m, "omega": w, "tc_frac": tcf, "tc_bars": tc - dt,
            "damping": float(damping), "oscillations": float(osc), "sse": float(sse[g]),
            "positive": bool(ok and B < 0), "negative": bool(ok and B > 0)}


def lppls_confidence_at(logp: np.ndarray, end: int, windows=LPPLS_WINDOWS) -> Optional[dict]:
    """Confidence using only logp[: end + 1]."""
    fits = []
    for L in windows:
        if end + 1 - L < 0:
            continue
        fr = lppls_fit_window(logp[end + 1 - L:end + 1])
        if fr:
            fits.append(fr)
    if len(fits) < 3:
        return None
    pos = [f for f in fits if f["positive"]]
    return {"pos": len(pos) / len(fits), "neg": sum(f["negative"] for f in fits) / len(fits),
            "n_windows": len(fits),
            "tc_bars_median": float(np.median([f["tc_bars"] for f in pos])) if pos else None}


def lppls_series(price: pd.Series, step: int = 5, windows=LPPLS_WINDOWS) -> pd.DataFrame:
    """Point-in-time LPPLS confidence every `step` bars (columns pos, neg), forward-filled
    only until the next computation date (it never borrows a later value)."""
    p = price.dropna().astype(float)
    lp = np.log(p.values)
    rows, idx = [], []
    start = min(windows) + 2 * min(windows)          # need a few windows before the first reading
    ends = list(range(start, len(lp), step))
    if ends and ends[-1] != len(lp) - 1:
        ends.append(len(lp) - 1)
    for e in ends:
        c = lppls_confidence_at(lp, e, windows)
        if c:
            rows.append((c["pos"], c["neg"]))
            idx.append(p.index[e])
    df = pd.DataFrame(rows, index=pd.DatetimeIndex(idx), columns=["pos", "neg"])
    return df.reindex(p.index).ffill(limit=step - 1) if len(df) else df


LPPLS_ON = 0.2   # fixed in advance: ≥ 20% of windows see a bubble


# ════════════════════════════════════════════════════════════════════════
# 2 · Fragility meter (critical slowing down + variability + entropy)
# ════════════════════════════════════════════════════════════════════════
def permutation_entropy(x: np.ndarray, order: int = 4) -> float:
    """Normalised Bandt–Pompe permutation entropy (0 = perfectly regular, 1 = random)."""
    import math
    x = np.asarray(x, float)
    if len(x) < order + 10:
        return np.nan
    pats = np.array([x[i:len(x) - order + 1 + i] for i in range(order)]).T
    codes = np.argsort(pats, axis=1, kind="stable")
    keys = codes @ (order ** np.arange(order))
    _, counts = np.unique(keys, return_counts=True)
    pr = counts / counts.sum()
    return float(-(pr * np.log(pr)).sum() / np.log(math.factorial(order)))


def rolling_permutation_entropy(r: pd.Series, window: int = 126, order: int = 4) -> pd.Series:
    import math
    x = r.values.astype(float)
    n = len(x)
    out = np.full(n, np.nan)
    if n < order + window:
        return pd.Series(out, index=r.index)
    pats = np.array([x[i:n - order + 1 + i] for i in range(order)]).T       # pattern ending at j+order-1
    keys = np.argsort(pats, axis=1, kind="stable") @ (order ** np.arange(order))
    uniq, inv = np.unique(keys, return_inverse=True)
    onehot = np.zeros((len(keys), len(uniq)))
    onehot[np.arange(len(keys)), inv] = 1
    cs = np.vstack([np.zeros(len(uniq)), np.cumsum(onehot, axis=0)])
    wpat = window - order + 1
    norm = np.log(math.factorial(order))
    for j in range(wpat - 1, len(keys)):
        c = cs[j + 1] - cs[j + 1 - wpat]
        pr = c[c > 0] / wpat
        out[j + order - 1] = -(pr * np.log(pr)).sum() / norm
    return pd.Series(out, index=r.index)


def kendall_trend(x: pd.Series, window: int) -> pd.Series:
    """Rolling Kendall τ of x against time (the standard early-warning trend statistic)."""
    v = x.values.astype(float)
    n = len(v)
    out = np.full(n, np.nan)
    for i in range(window - 1, n):
        w = v[i - window + 1:i + 1]
        if np.isnan(w).any():
            continue
        d = np.sign(w[None, :] - w[:, None])
        tri = np.triu(np.ones((window, window), bool), 1)
        out[i] = d[tri].sum() / tri.sum()
    return pd.Series(out, index=x.index)


def fragility_frame(price: pd.Series, window: int = 126, trend: int = 126) -> pd.DataFrame:
    """Point-in-time early-warning indicators on daily log returns.

    ac1   rolling lag-1 autocorrelation (critical slowing down)
    var   rolling variance (rising variability — the precursor that did show up before crashes in
          Diks et al. 2019 / PLOS One 2015)
    pe    permutation entropy (falling = more ordered, herd-like moves)
    score average of the expanding percentile ranks of trend(var), trend(ac1) and −trend(pe):
          0 = calmest ever seen so far, 1 = most fragile ever seen so far.
    """
    r = np.log(price.astype(float)).diff().dropna()
    ac1 = r.rolling(window).apply(lambda w: np.corrcoef(w[:-1], w[1:])[0, 1], raw=True)
    var = r.rolling(window).var()
    pe = rolling_permutation_entropy(r, window)
    t_var, t_ac, t_pe = kendall_trend(var, trend), kendall_trend(ac1, trend), kendall_trend(pe, trend)
    ranks = pd.concat([es.expanding_pct_rank(t_var), es.expanding_pct_rank(t_ac),
                       es.expanding_pct_rank(-t_pe)], axis=1)
    score = ranks.mean(axis=1, skipna=False)
    # Rank the blend itself against its own past so "0.8" always means "more fragile than 80% of
    # every earlier reading" (an average of three ranks rarely reaches 0.8 on its own).
    rank = es.expanding_pct_rank(score, min_periods=126)
    return pd.DataFrame({"ac1": ac1, "var": var, "pe": pe, "tau_var": t_var, "tau_ac1": t_ac,
                         "tau_pe": t_pe, "score": score, "rank": rank})


FRAGILITY_ON = 0.8  # fixed in advance: fragility rank in the top 20% of everything seen so far


# ════════════════════════════════════════════════════════════════════════
# 3 · Trend-memory regime (Hurst exponent by DFA)
# ════════════════════════════════════════════════════════════════════════
def dfa_alpha(r: np.ndarray, scales=(8, 12, 16, 24, 32, 48, 63)) -> float:
    """Detrended fluctuation analysis exponent of a return series.
    ≈0.5 random walk, >0.5 trends persist, <0.5 moves tend to reverse."""
    r = np.asarray(r, float)
    r = r[np.isfinite(r)]
    if len(r) < 4 * max(scales):
        scales = tuple(s for s in scales if 4 * s <= len(r))
    if len(scales) < 3:
        return np.nan
    y = np.cumsum(r - r.mean())
    F = []
    for s in scales:
        k = len(y) // s
        seg = y[:k * s].reshape(k, s)
        t = np.arange(s)
        A = np.vstack([t, np.ones(s)]).T
        coef = np.linalg.lstsq(A, seg.T, rcond=None)[0]
        resid = seg.T - A @ coef
        F.append(np.sqrt((resid ** 2).mean()))
    return float(np.polyfit(np.log(scales), np.log(F), 1)[0])


def rolling_dfa(price: pd.Series, window: int = 252, step: int = 5) -> pd.Series:
    r = np.log(price.astype(float)).diff().dropna()
    v = r.values
    out = pd.Series(np.nan, index=r.index)
    for i in range(window - 1, len(v), step):
        out.iloc[i] = dfa_alpha(v[i - window + 1:i + 1])
    if len(v) >= window and np.isnan(out.iloc[-1]):
        out.iloc[-1] = dfa_alpha(v[-window:])
    return out.ffill(limit=step - 1)


HURST_ON = 0.55     # fixed in advance
MOM_LOOKBACK = 63
MOM_HOLD = 21


def momentum_outcome(price: pd.Series, lookback: int = MOM_LOOKBACK, hold: int = MOM_HOLD) -> pd.Series:
    """Return of a simple trend-follow bet placed at t: sign(past `lookback` return) × next `hold` return."""
    lp = np.log(price.astype(float))
    past = lp - lp.shift(lookback)
    return np.sign(past) * (lp.shift(-hold) - lp)


# ════════════════════════════════════════════════════════════════════════
# 4 · Crash odds: GPD tails (EVT) + copula tail asymmetry vs BTC
# ════════════════════════════════════════════════════════════════════════
def gpd_fit(losses: np.ndarray, q: float = 0.9) -> Optional[dict]:
    """Peaks-over-threshold: fit a Generalised Pareto to losses above their q-quantile."""
    from scipy.stats import genpareto
    L = np.asarray(losses, float)
    L = L[np.isfinite(L)]
    if len(L) < 200:
        return None
    u = float(np.quantile(L, q))
    exc = L[L > u] - u
    if len(exc) < 20:
        return None
    xi, _, beta = genpareto.fit(exc, floc=0)
    return {"u": u, "xi": float(xi), "beta": float(beta), "zeta": len(exc) / len(L), "n": len(L)}


def gpd_var(fit: dict, p: float = 0.99) -> float:
    """Loss level exceeded with probability 1−p (McNeil–Frey POT formula)."""
    u, xi, beta, z = fit["u"], fit["xi"], fit["beta"], fit["zeta"]
    if abs(xi) < 1e-6:
        return u + beta * np.log(z / (1 - p))
    return u + beta / xi * (((1 - p) / z) ** (-xi) - 1)


def gpd_tail_prob(fit: dict, loss: float) -> float:
    """P(loss > x) for x above the threshold."""
    u, xi, beta, z = fit["u"], fit["xi"], fit["beta"], fit["zeta"]
    if loss <= u:
        return np.nan
    if abs(xi) < 1e-6:
        return float(z * np.exp(-(loss - u) / beta))
    base = 1 + xi * (loss - u) / beta
    return float(z * base ** (-1 / xi)) if base > 0 else 0.0


def kupiec_pof(n: int, x: int, p: float) -> float:
    """Kupiec proportion-of-failures test p-value (H0: exceedance rate = p)."""
    from scipy.stats import chi2
    if n == 0:
        return np.nan
    phat = x / n
    def ll(q):
        q = min(max(q, 1e-12), 1 - 1e-12)
        return (n - x) * np.log(1 - q) + x * np.log(q)
    lr = -2 * (ll(p) - ll(phat))
    return float(1 - chi2.cdf(max(lr, 0.0), 1))


def var_backtest(price: pd.Series, p: float = 0.99, train: int = 750, refit: int = 21) -> Optional[dict]:
    """Walk-forward daily VaR: refit every `refit` days on the trailing `train` days, predict the
    next days, count breaches.  GPD vs a Normal (bell-curve) VaR baseline."""
    from scipy.stats import norm
    r = np.log(price.astype(float)).diff().dropna().values
    if len(r) < train + 250:
        return None
    br_g = br_n = n = 0
    for s in range(train, len(r), refit):
        hist = -r[s - train:s]
        fit = gpd_fit(hist)
        if not fit:
            continue
        vg = gpd_var(fit, p)
        vn = -(r[s - train:s].mean() + norm.ppf(1 - p) * r[s - train:s].std(ddof=1))
        fut = -r[s:s + refit]
        n += len(fut)
        br_g += int((fut > vg).sum())
        br_n += int((fut > vn).sum())
    if n == 0:
        return None
    return {"days": n, "expected": n * (1 - p), "gpd_breaches": br_g, "normal_breaches": br_n,
            "gpd_p": kupiec_pof(n, br_g, 1 - p), "normal_p": kupiec_pof(n, br_n, 1 - p)}


def var_verdict(bt: Optional[dict]) -> str:
    """'edge found' here = the fat-tail model is calibrated (Kupiec p ≥ 0.05) while the bell curve is not."""
    if not bt or bt["expected"] < 10:
        return es.INSUFFICIENT
    return es.EDGE if (bt["gpd_p"] >= 0.05 and bt["normal_p"] < 0.05) else es.NO_EDGE


def tail_dependence(x: np.ndarray, y: np.ndarray, q: float = 0.1) -> dict:
    """Empirical (rank-copula) tail dependence: λL = P(Y in its worst q | X in its worst q),
    λU = same for the best q.  Independence gives q; moving in lock-step gives 1."""
    from scipy.stats import rankdata
    x, y = np.asarray(x, float), np.asarray(y, float)
    u, v = rankdata(x) / (len(x) + 1), rankdata(y) / (len(y) + 1)
    lo, hi = u <= q, u >= 1 - q
    lam_l = float((v[lo] <= q).mean()) if lo.any() else np.nan
    lam_u = float((v[hi] >= 1 - q).mean()) if hi.any() else np.nan
    return {"lower": lam_l, "upper": lam_u, "asym": lam_l - lam_u, "n": len(x)}


def tail_asym_bootstrap(x: np.ndarray, y: np.ndarray, q: float = 0.1, n_boot: int = 500,
                        block: float = 20.0, seed: int = 0) -> dict:
    """Stationary-bootstrap 90% interval for λL − λU (keeps volatility clustering)."""
    rng = np.random.default_rng(seed)
    base = tail_dependence(x, y, q)
    vals = []
    for _ in range(n_boot):
        ix = es.stationary_bootstrap_idx(len(x), block, rng)
        vals.append(tail_dependence(x[ix], y[ix], q)["asym"])
    lo, hi = np.percentile(vals, [5, 95])
    return {**base, "ci": (float(lo), float(hi))}


def monthly_crash_odds(price: pd.Series, drop: float = 0.30, years: int = 3) -> Optional[dict]:
    """Odds of a ≥`drop` fall over the next 21 trading days from a GPD fitted to the LOSS side of
    overlapping 21-day returns of the last `years` (overlap shown as a caveat), plus the plain count."""
    s = price.astype(float).dropna()
    s = s[s.index >= s.index[-1] - pd.DateOffset(years=years)]
    if len(s) < 300:
        return None
    r21 = np.log(s).diff(21).dropna().values
    loss = -r21
    fit = gpd_fit(loss, q=0.8) if len(loss) >= 200 else None
    x = -np.log(1 - drop)
    emp = float((loss >= x).mean())
    model = gpd_tail_prob(fit, x) if fit else np.nan
    return {"empirical": emp, "gpd": model, "fit": fit, "windows": len(loss)}


# ════════════════════════════════════════════════════════════════════════
# 5 · Halving clock
# ════════════════════════════════════════════════════════════════════════
def halving_phase(d) -> Optional[dict]:
    d = pd.Timestamp(d).date()
    past = [h for h in HALVINGS if h <= d]
    if not past:
        return None
    h = past[-1]
    nxt = next((x for x in HALVINGS if x > d), NEXT_HALVING_EST)
    days = (d - h).days
    return {"halving": h, "days": days, "cycle_frac": days / (nxt - h).days, "next": nxt}


def halving_fold(price: pd.Series, as_of, horizons=(91, 182, 365)) -> list:
    """For every *earlier* halving: the forward return from the same number of days after that
    halving as `as_of` is after its own.  Only uses data available before `as_of`."""
    ph = halving_phase(as_of)
    if not ph:
        return []
    p = price.dropna().astype(float)
    p = p[p.index <= pd.Timestamp(as_of)]
    out = []
    for h in HALVINGS:
        if h >= ph["halving"]:
            break
        t0 = pd.Timestamp(h) + pd.Timedelta(days=ph["days"])
        if t0 < p.index[0]:
            continue
        b = p[p.index <= t0]
        if b.empty:
            continue
        row = {"halving": h, "start": b.index[-1].date(), "p0": float(b.iloc[-1])}
        for H in horizons:
            t1 = t0 + pd.Timedelta(days=H)
            a = p[p.index <= t1]
            row[H] = float(a.iloc[-1] / b.iloc[-1] - 1) if t1 <= p.index[-1] else None
        # peak-to-date in that cycle at the same phase: how far below the cycle high was price?
        cyc = p[(p.index >= pd.Timestamp(h)) & (p.index <= t0)]
        row["below_cycle_high"] = float(b.iloc[-1] / cyc.max() - 1) if len(cyc) else None
        out.append(row)
    return out


def halving_backtest(price: pd.Series, horizon: int = 182, step_days: int = 30) -> dict:
    """Leave-the-future-out test: on each month-end, the 'clock' predicts the sign of the next
    `horizon`-day return as the sign of the average of earlier cycles at the same phase.
    Hit rate vs always-up (buy-and-hold) baseline; independent samples ≈ cycles, not months."""
    p = price.dropna().astype(float)
    dates = pd.date_range(p.index[0], p.index[-1] - pd.Timedelta(days=horizon), freq=f"{step_days}D")
    rows = []
    for d in dates:
        fold = halving_fold(p, d, horizons=(horizon,))
        vals = [r[horizon] for r in fold if r.get(horizon) is not None]
        if not vals:
            continue
        b = p[p.index <= d].iloc[-1]
        a = p[p.index <= d + pd.Timedelta(days=horizon)].iloc[-1]
        rows.append((d, np.sign(np.mean(vals)), np.sign(a / b - 1), len(vals)))
    if not rows:
        return {"verdict": es.INSUFFICIENT, "n": 0, "cycles_used_max": 0}
    df = pd.DataFrame(rows, columns=["d", "pred", "real", "k"])
    hit = float((df.pred == df.real).mean())
    up = float((df.real > 0).mean())
    eff = len(df) * step_days / horizon
    cycles = int(df.k.max())
    verdict = es.INSUFFICIENT if (cycles < 4 or eff < 12) else (
        es.EDGE if hit - up > 0.1 else es.NO_EDGE)
    return {"verdict": verdict, "n": len(df), "eff": eff, "hit": hit, "always_up": up,
            "cycles_used_max": cycles, "start": str(df.d.iloc[0].date()), "end": str(df.d.iloc[-1].date())}


# ════════════════════════════════════════════════════════════════════════
# 6 · Tail-aware Kelly sizer
# ════════════════════════════════════════════════════════════════════════
KELLY_GRID = np.round(np.arange(0.0, 1.0001, 0.05), 2)


def kelly_fraction(r_stock: np.ndarray, r_cash: float = 0.0, grid=KELLY_GRID) -> float:
    """Weight in the stock (rest in cash, no leverage) that maximises average log growth
    over the sample of period returns — the Kelly criterion, using the actual fat-tailed
    history instead of a bell-curve formula."""
    r = np.asarray(r_stock, float)
    r = r[np.isfinite(r)]
    if len(r) < 12:
        return np.nan
    g = [np.mean(np.log1p(f * r + (1 - f) * r_cash)) for f in grid]
    return float(grid[int(np.argmax(g))])


def _monthly(price: pd.Series, step: int = 21) -> pd.Series:
    p = price.dropna().astype(float)
    return p.iloc[::step].pct_change().dropna()


def kelly_walkforward(price: pd.Series, lookback_m: int = 36, frac: float = 0.5,
                      cash_annual: float = 0.03, static=(0.8, 0.4, 1.0)) -> Optional[dict]:
    """Each month: estimate Kelly from the trailing `lookback_m` months only, hold frac×Kelly
    for the next month.  Compared with fixed weights (the user's ~80%, a 40% cap, 100%)."""
    m = _monthly(price)
    rc = (1 + cash_annual) ** (1 / 12) - 1
    if len(m) < lookback_m + 24:
        return None
    w, rets = [], []
    for i in range(lookback_m, len(m)):
        f = kelly_fraction(m.values[i - lookback_m:i], rc) * frac
        w.append(f)
        rets.append(f * m.values[i] + (1 - f) * rc)
    idx = m.index[lookback_m:]
    out = {"weights": pd.Series(w, idx), "kelly": pd.Series(rets, idx)}
    for s in static:
        out[f"static_{int(s*100)}"] = pd.Series(s * m.values[lookback_m:] + (1 - s) * rc, idx)
    stats = {}
    for k, v in out.items():
        if k == "weights":
            continue
        eq = (1 + v).cumprod()
        yrs = len(v) / 12
        stats[k] = {"cagr": float(eq.iloc[-1] ** (1 / yrs) - 1), "maxdd": float((eq / eq.cummax() - 1).min()),
                    "final": float(eq.iloc[-1])}
    out["stats"] = stats
    return out


def kelly_verdict(wf: Optional[dict], n_boot: int = 2000, seed: int = 0) -> dict:
    """Does walk-forward half-Kelly beat holding a fixed 80%?  Block-bootstrap the monthly
    log-growth difference; 'edge' only if growth is higher with ≥95% bootstrap support and the
    worst drawdown is not deeper.  Also checks each half separately (out-of-sample stability)."""
    if not wf:
        return {"verdict": es.INSUFFICIENT}
    a = np.log1p(wf["kelly"].values)
    b = np.log1p(wf["static_80"].values)
    d = a - b
    n = len(d)
    if n < 36:
        return {"verdict": es.INSUFFICIENT, "months": n}
    rng = np.random.default_rng(seed)
    boots = np.array([d[es.stationary_bootstrap_idx(n, 6.0, rng)].mean() for _ in range(n_boot)])
    support = float((boots > 0).mean())
    h = n // 2
    halves = (float(d[:h].mean() * 12), float(d[h:].mean() * 12))
    st = wf["stats"]
    dd_ok = st["kelly"]["maxdd"] >= st["static_80"]["maxdd"]
    edge = support >= 0.95 and dd_ok and all(x > 0 for x in halves)
    return {"verdict": es.EDGE if edge else es.NO_EDGE, "months": n, "growth_diff_pa": float(d.mean() * 12),
            "support": support, "halves_pa": halves, "dd_better": bool(dd_ok)}
