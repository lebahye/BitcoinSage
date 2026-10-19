"""
utils/edge_report.py — runs every 🧪 Edge Lab tool for one stock (+ Bitcoin) and its honest backtest.

All rules (thresholds, horizons) are fixed here IN ADVANCE and never tuned on the results.
Pure: takes price series, returns plain dicts.  The page caches the result.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd

from utils import edge_lab as el
from utils import edge_stats as es
from utils.market_data import align_frame

H_STOCK = 63    # ≈ 3 months of trading days
H_BTC = 91      # ≈ 3 months of calendar days (Bitcoin trades every day)
PEERS = ("RIOT", "MARA", "CLSK", "HUT")


def _last(s: pd.Series):
    s = s.dropna() if s is not None else pd.Series(dtype=float)
    return (float(s.iloc[-1]), s.index[-1].date()) if len(s) else (None, None)


def _bt(sig: pd.Series, price: pd.Series, H: int, kind: str, direction: int, hyp: str) -> es.EdgeResult:
    y = es.forward_log_return(price, H) if kind == "ret" else es.forward_drawdown(price, H)
    name = "next-3-month return (log)" if kind == "ret" else "worst drop within next 3 months"
    return es.evaluate_signal(sig, y, H, direction=direction, hypothesis=hyp, outcome_name=name)


# ── 1 LPPLS ───────────────────────────────────────────────────────────
def lppls_tool(price: pd.Series, H: int) -> dict:
    L = el.lppls_series(price)
    if L.empty:
        return {"available": False}
    pos, neg = L["pos"], L["neg"]
    on = (pos >= el.LPPLS_ON).where(pos.notna())
    anti = (neg >= el.LPPLS_ON).where(neg.notna())
    return {"available": True, "series": L,
            "now_pos": _last(pos), "now_neg": _last(neg),
            "bt_ret": _bt(on, price, H, "ret", -1, "After a bubble reading, the next 3 months are worse"),
            "bt_dd": _bt(on, price, H, "dd", -1, "After a bubble reading, the next 3 months hold a deeper drop"),
            "bt_anti": _bt(anti, price, H, "ret", +1, "After an anti-bubble (crash pattern), the next 3 months bounce")}


# ── 2 Fragility ──────────────────────────────────────────────────────
def fragility_tool(price: pd.Series, H: int) -> dict:
    F = el.fragility_frame(price)
    if F["rank"].dropna().empty:
        return {"available": False}
    on = (F["rank"] >= el.FRAGILITY_ON).where(F["rank"].notna())
    last = F.dropna().iloc[-1] if len(F.dropna()) else None
    return {"available": True, "frame": F, "now_rank": _last(F["rank"]),
            "now": None if last is None else last.to_dict(),
            "bt_dd": _bt(on, price, H, "dd", -1, "When fragility is in its top 20%, the next 3 months hold a deeper drop"),
            "bt_ret": _bt(on, price, H, "ret", -1, "When fragility is in its top 20%, the next 3 months are worse")}


# ── 3 Hurst ───────────────────────────────────────────────────────────
def hurst_tool(price: pd.Series) -> dict:
    a = el.rolling_dfa(price)
    if a.dropna().empty:
        return {"available": False}
    on = (a >= el.HURST_ON).where(a.notna())
    y = el.momentum_outcome(price)
    bt = es.evaluate_signal(on, y, el.MOM_HOLD, direction=+1,
                            hypothesis="Trend-following pays more when trend memory is high (α ≥ 0.55)",
                            outcome_name="1-month return of following the 3-month trend")
    return {"available": True, "series": a, "now": _last(a), "bt": bt,
            "long_run": float(a.mean())}


# ── 4 Tails ───────────────────────────────────────────────────────────
def tails_tool(price: pd.Series, btc: Optional[pd.Series]) -> dict:
    out = {"available": True}
    out["var_bt"] = el.var_backtest(price)
    out["var_verdict"] = el.var_verdict(out["var_bt"])
    out["var_bt_btc"] = el.var_backtest(btc) if btc is not None and len(btc.dropna()) > 1000 else None
    out["var_verdict_btc"] = el.var_verdict(out["var_bt_btc"])
    r = np.log(price.astype(float)).diff().dropna()
    fit_now = el.gpd_fit(-r.values[-750:]) if len(r) >= 750 else None
    out["var99_now"] = float(1 - np.exp(-el.gpd_var(fit_now, 0.99))) if fit_now else None
    out["crash"] = el.monthly_crash_odds(price, 0.30)
    if btc is not None and len(btc.dropna()):
        A = align_frame(pd.DataFrame({"S": price, "B": btc}), calendar_col="S").dropna()
        lr = np.log(A).diff().dropna()
        if len(lr) >= 500:
            full = el.tail_asym_bootstrap(lr["B"].values, lr["S"].values)
            r3 = lr[lr.index >= lr.index[-1] - pd.DateOffset(years=3)]
            recent = el.tail_asym_bootstrap(r3["B"].values, r3["S"].values)
            h = len(lr) // 2
            halves = (el.tail_dependence(lr["B"].values[:h], lr["S"].values[:h])["asym"],
                      el.tail_dependence(lr["B"].values[h:], lr["S"].values[h:])["asym"])
            stable = np.sign(halves[0]) == np.sign(halves[1]) != 0
            if full["ci"][0] > 0 or full["ci"][1] < 0:
                v = es.EDGE if stable else es.NO_EDGE
            else:
                v = es.NO_EDGE
            out["tail"] = {"full": full, "recent": recent, "halves": halves, "verdict": v,
                           "start": str(lr.index[0].date())}
    return out


# ── 5 Halving clock ───────────────────────────────────────────────────
def halving_tool(btc: pd.Series, stock: Optional[pd.Series], as_of) -> dict:
    ph = el.halving_phase(as_of)
    if ph is None or btc is None or btc.dropna().empty:
        return {"available": False}
    b = btc.dropna()
    cyc = b[b.index >= pd.Timestamp(ph["halving"])]
    return {"available": True, "phase": ph,
            "btc_fold": el.halving_fold(b, as_of),
            "stock_fold": el.halving_fold(stock, as_of) if stock is not None and len(stock.dropna()) else [],
            "btc_below_high_now": float(b.iloc[-1] / cyc.max() - 1) if len(cyc) else None,
            "bt": el.halving_backtest(b)}


# ── 6 Kelly ───────────────────────────────────────────────────────────
def kelly_tool(price: pd.Series, cash_annual: float = 0.03) -> dict:
    wf = el.kelly_walkforward(price, cash_annual=cash_annual)
    m = el._monthly(price)
    rc = (1 + cash_annual) ** (1 / 12) - 1
    full_now = el.kelly_fraction(m.values[-36:], rc) if len(m) >= 36 else np.nan
    return {"available": wf is not None, "wf": wf, "verdict": el.kelly_verdict(wf),
            "full_now": None if np.isnan(full_now) else full_now,
            "half_now": None if np.isnan(full_now) else full_now / 2, "cash_annual": cash_annual}


def peer_check(prices: Dict[str, pd.Series]) -> pd.DataFrame:
    """Robustness: the same fixed rules on each miner.  An edge only counts if it shows up on the
    focus stock AND points the same way on most peers."""
    rows = []
    for sym, p in prices.items():
        if p is None or len(p.dropna()) < 600:
            continue
        L = el.lppls_series(p)
        F = el.fragility_frame(p)
        a = el.rolling_dfa(p)
        tests = {
            "LPPLS bubble → worse 3 months": _bt((L["pos"] >= el.LPPLS_ON).where(L["pos"].notna()), p, H_STOCK, "ret", -1, "")
            if not L.empty else None,
            "Fragility → deeper 3-month drop": _bt((F["rank"] >= el.FRAGILITY_ON).where(F["rank"].notna()), p, H_STOCK, "dd", -1, ""),
            "High trend memory → trend-following pays": es.evaluate_signal(
                (a >= el.HURST_ON).where(a.notna()), el.momentum_outcome(p), el.MOM_HOLD, direction=1, hypothesis=""),
        }
        for name, r in tests.items():
            if r is None:
                continue
            rows.append({"stock": sym, "test": name, "verdict": r.verdict, "effect": r.effect,
                         "p": r.p_full, "right_way": None if r.effect is None else bool(np.sign(r.effect) == np.sign(
                             -1 if "→ worse" in name or "deeper" in name else 1)), "independent_on": r.eff_on})
    return pd.DataFrame(rows)


def build(symbol: str, stock: pd.Series, btc: Optional[pd.Series], as_of=None) -> dict:
    stock = el.clean(stock, symbol)
    btc_c = el.clean(btc) if btc is not None else None
    as_of = as_of or (stock.index[-1] if len(stock) else None)
    rep = {"symbol": symbol, "as_of": str(pd.Timestamp(as_of).date()) if as_of is not None else None,
           "stock_start": str(stock.index[0].date()) if len(stock) else None}
    rep["lppls"] = lppls_tool(stock, H_STOCK) if len(stock) > 400 else {"available": False}
    rep["lppls_btc"] = lppls_tool(btc_c, H_BTC) if btc_c is not None and len(btc_c) > 400 else {"available": False}
    rep["fragility"] = fragility_tool(stock, H_STOCK) if len(stock) > 600 else {"available": False}
    rep["fragility_btc"] = fragility_tool(btc_c, H_BTC) if btc_c is not None and len(btc_c) > 600 else {"available": False}
    rep["hurst"] = hurst_tool(stock) if len(stock) > 400 else {"available": False}
    rep["tails"] = tails_tool(stock, btc_c) if len(stock) > 400 else {"available": False}
    rep["halving"] = halving_tool(btc_c, stock, as_of) if btc_c is not None else {"available": False}
    rep["kelly"] = kelly_tool(stock) if len(stock) > 400 else {"available": False}
    return rep


def scorecard(rep: dict) -> pd.DataFrame:
    """One row per tool: its headline backtest verdict (for the focus stock)."""
    def v(x):
        return x.verdict if isinstance(x, es.EdgeResult) else (x or es.INSUFFICIENT)
    rows = []
    L, F, Hh, T, Hv, K = (rep.get(k, {}) for k in ("lppls", "fragility", "hurst", "tails", "halving", "kelly"))
    rows.append(("1 · LPPLS bubble hazard", "Bubble reading → worse next 3 months", v(L.get("bt_ret")) if L.get("available") else es.INSUFFICIENT))
    rows.append(("2 · Fragility meter", "Top-20% fragility → deeper drop next 3 months", v(F.get("bt_dd")) if F.get("available") else es.INSUFFICIENT))
    rows.append(("3 · Trend memory (Hurst)", "Trend-following pays more when α ≥ 0.55", v(Hh.get("bt")) if Hh.get("available") else es.INSUFFICIENT))
    sym = rep.get("symbol") or "stock"
    rows.append((f"4a · Crash odds (EVT) — {sym}", "Fat-tail risk model calibrated where a bell curve is not", T.get("var_verdict", es.INSUFFICIENT)))
    rows.append(("4a · Crash odds (EVT) — Bitcoin", "Same test on Bitcoin's own daily moves", T.get("var_verdict_btc", es.INSUFFICIENT)))
    rows.append(("4b · Crash-together asymmetry", f"{sym}↔BTC tails differ, stably", (T.get("tail") or {}).get("verdict", es.INSUFFICIENT)))
    rows.append(("5 · Halving clock", "Earlier cycles at the same phase call the next 6 months", (Hv.get("bt") or {}).get("verdict", es.INSUFFICIENT)))
    rows.append(("6 · Tail-aware Kelly", "Walk-forward half-Kelly beats holding 80%", (K.get("verdict") or {}).get("verdict", es.INSUFFICIENT)))
    return pd.DataFrame(rows, columns=["Tool", "What was tested", "Backtest result"])
