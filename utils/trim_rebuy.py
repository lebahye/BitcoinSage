"""utils/trim_rebuy.py — "sell part, buy back cheaper" swing rules, backtested honestly, before AND after tax.

Goal metric: END WITH MORE SHARES than just holding.  Every result is measured in *after-tax share-equivalents*:
    (what you'd have after tax if everything were sold on the last day) ÷ final price
for the rule AND for buy-and-hold from the same start, so the tax that holding still owes on its unrealised gain is
counted too (apples to apples).  Taxes paid / refunded along the way are cash from outside the position, not
reinvested (nominal $); a loss carryforward left at the end is valued at the long-term marginal rate for both sides.
In an IRA / Roth there is no tax, so this is simply shares (+ leftover cash) vs. hold, after costs.
A second, harsher view ("taxpaid_shares_pct") pays each year's tax by selling shares at that year-end's price.

Point-in-time: a rule looks at closes up to day t and trades at the close of day t+1 (no same-bar look-ahead).
Every rule has a max-wait TIMEOUT, so a trimmed slice is always bought back.  Parameters are pre-registered
(fixed below, never tuned).  Significance: the same number of trims with the same trim sizes and durations placed at
random dates (seeded, non-overlapping) — the "random-date baseline"; and an in-sample (first 60%) / hold-out
(last 40%) split, exactly like the 🧪 Edge Lab.

Taxes come from utils/tax_ny.py: lots (FIFO = Schwab's default, or specific-ID highest-cost-first), the holding period
restarts for rebought shares, wash sales (loss disallowed when replacement shares are bought within 30 days before or
after; the disallowed loss and the old holding period move to the replacement shares), yearly netting, $3,000 loss
limit and carryforward.  Taxes are settled on Dec 31 of each year (or on the last day) as a cash flow.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from utils import tax_ny as tx

COST = 0.0005          # 0.05% per side for spread/slippage (Schwab: $0 online stock commissions)
IS_FRAC = 0.60         # in-sample share of dates; the rest is the hold-out
N_RANDOM = 200
SEED = 7
MIN_TRIPS, MIN_TRIPS_OOS = 6, 3
P_FULL, P_OOS = 0.05, 0.10
EDGE, NO_EDGE, INSUFFICIENT = "edge found", "no reliable edge", "insufficient data"


# ════════════════════════════════════════════════════════════════════════
# Lots, wash sales and yearly tax
# ════════════════════════════════════════════════════════════════════════
@dataclass
class Lot:
    seq: int
    shares: float
    basis: float             # total $ basis (incl. any wash-sale adjustment)
    acquired: date           # holding-period start (may be tacked back by a wash sale)
    bought: date             # actual purchase date (for the 30-day window)
    repl_used: float = 0.0   # shares already used as wash-sale replacement


@dataclass
class Ledger:
    profile: tx.TaxProfile
    method: str = "fifo"                      # 'fifo' | 'specific' (highest cost per share first)
    lots: List[Lot] = field(default_factory=list)
    cash: float = 0.0                         # trading cash (sale proceeds not yet reinvested)
    tax_cash: float = 0.0                     # cumulative tax paid (−) / refunded (+), in $
    tax_shares: float = 0.0                   # the same, in shares at each payment date's price (paid by selling shares)
    realized: Dict[int, List[float]] = field(default_factory=dict)   # year -> [st, lt]
    carry: tx.Carry = field(default_factory=tx.Carry)
    pending: List[dict] = field(default_factory=list)                 # loss sales still inside their 30-day window
    events: List[dict] = field(default_factory=list)
    taxes: Dict[int, float] = field(default_factory=dict)
    disallowed: float = 0.0
    _seq: int = 0
    cost: float = COST                        # slippage per side

    @property
    def shares(self) -> float:
        return sum(l.shares for l in self.lots)

    def _real(self, d: date, st: float, lt: float):
        r = self.realized.setdefault(d.year, [0.0, 0.0])
        r[0] += st
        r[1] += lt

    def buy(self, d: date, price: float, dollars: Optional[float] = None, shares: Optional[float] = None,
            acquired: Optional[date] = None, cost: Optional[float] = None) -> float:
        cost = self.cost if cost is None else cost
        if shares is None:
            shares = dollars / (price * (1 + cost))
        spent = shares * price * (1 + cost)
        self.cash -= spent
        self._seq += 1
        lot = Lot(self._seq, shares, spent, acquired or d, d)
        self.lots.append(lot)
        # wash sale (buy within 30 days AFTER an earlier loss sale)
        for p in self.pending:
            if 0 <= (d - p["date"]).days <= 30 and p["open"] > 1e-9:
                self._apply_wash(p, lot)
        return shares

    def _apply_wash(self, p: dict, lot: Lot):
        free = lot.shares - lot.repl_used
        n = min(p["open"], free)
        if n <= 1e-12:
            return
        dis = p["loss_ps"] * n                       # loss per share (positive) × replacement shares
        lot.basis += dis
        lot.repl_used += n
        # tack on the old holding period (proportionally simplified: whole lot takes the earlier start)
        lot.acquired = min(lot.acquired, lot.bought - timedelta(days=p["held_days"]))
        p["open"] -= n
        self.disallowed += dis
        # add the disallowed part back to the sale year's result (loss is negative).  If that year's tax was already
        # settled (sale in late Dec, rebuy in Jan), the adjustment is booked in the rebuy year instead (simplification).
        y = p["date"] if p["date"].year not in self.taxes else lot.bought
        self._real(y, p["st"] * dis / p["loss"], p["lt"] * dis / p["loss"])

    def sell(self, d: date, price: float, shares: float, cost: Optional[float] = None) -> dict:
        cost = self.cost if cost is None else cost
        shares = min(shares, self.shares)
        order = (sorted(self.lots, key=lambda l: l.seq) if self.method == "fifo"
                 else sorted(self.lots, key=lambda l: -l.basis / l.shares))
        left, st, lt, held_w, gain_total = shares, 0.0, 0.0, 0.0, 0.0
        proceeds_ps = price * (1 - cost)
        for l in order:
            if left <= 1e-12:
                break
            n = min(l.shares, left)
            b = l.basis * n / l.shares
            g = n * proceeds_ps - b
            long = (d - l.acquired).days > 365
            if long:
                lt += g
            else:
                st += g
            held_w += n * (d - l.acquired).days
            gain_total += g
            l.basis -= b
            l.shares -= n
            l.repl_used = min(l.repl_used, l.shares)
            left -= n
        self.lots = [l for l in self.lots if l.shares > 1e-12]
        self.cash += shares * proceeds_ps
        self._real(d, st, lt)
        out = {"date": d, "shares": shares, "price": price, "gain": gain_total, "st": st, "lt": lt}
        loss = min(0.0, st) + min(0.0, lt)
        if loss < 0 and self.profile.taxed():
            p = {"date": d, "loss": loss, "st": min(0.0, st), "lt": min(0.0, lt), "open": shares,
                 "loss_ps": -loss / shares, "held_days": int(held_w / shares) if shares else 0}
            # wash sale (replacement bought within 30 days BEFORE the sale, still held)
            for lot in sorted(self.lots, key=lambda l: l.seq):
                if 0 <= (d - lot.bought).days <= 30 and p["open"] > 1e-9:
                    self._apply_wash(p, lot)
            self.pending.append(p)
        self.pending = [p for p in self.pending if (d - p["date"]).days <= 30 and p["open"] > 1e-9]
        return out

    def settle_year(self, year: int, d: date, price: Optional[float] = None):
        """Pay (or receive) this year's incremental tax.  It is expressed in shares at `price`: the shares you
        would have to sell to pay the bill (or could buy with a refund) — so the goal 'more shares' is after tax."""
        st, lt = self.realized.get(year, [0.0, 0.0])
        r = tx.year_tax(self.profile, st, lt, self.carry)
        self.carry = r["carry"]
        self.taxes[year] = r["tax"]
        self.tax_cash -= r["tax"]
        if price:
            self.tax_shares += r["tax"] / price

    def liquidate_value(self, d: date, price: float) -> float:
        """After-tax $ if everything were sold on day d (includes this year's other realized results + carryover)."""
        tmp = Ledger(self.profile, self.method, [replace(l) for l in self.lots], self.cash, self.tax_cash, 0.0,
                     {k: list(v) for k, v in self.realized.items()}, replace(self.carry), [], [], dict(self.taxes),
                     cost=self.cost)
        tmp.sell(d, price, tmp.shares)
        st, lt = tmp.realized.get(d.year, [0.0, 0.0])
        if d.year in self.taxes:
            return tmp.cash + tmp.tax_cash
        r = tx.year_tax(self.profile, st, lt, self.carry)
        # a loss carryforward left over still has value later; count it at the long-term marginal rate (as if it
        # offsets future gains) — the same for the rule and for plain holding, so neither side is penalised by the
        # $3,000/yr cap on the last day.
        left = (r["carry"].st + r["carry"].lt) * tx.marginal_rates(self.profile)["lt"]
        return tmp.cash + tmp.tax_cash - r["tax"] + left


# ════════════════════════════════════════════════════════════════════════
# Indicators (point-in-time) and the pre-registered rules
# ════════════════════════════════════════════════════════════════════════
def rsi(close: pd.Series, n: int = 14) -> pd.Series:
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def atr(df: pd.DataFrame, n: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


@dataclass(frozen=True)
class Rule:
    key: str
    family: str             # stretch | earnings | band
    label: str
    trim: float
    timeout: int            # max trading days out of the market
    params: tuple = ()
    help: str = ""


RULES: List[Rule] = [
    Rule("A1", "stretch", "Stretch trim 10%: price ≥1.30× its 50-day avg or RSI ≥ 75", 0.10, 60,
         (("ma", 50), ("mult", 1.30), ("rsi", 75), ("rebuy_ma", 1.00), ("drop", 0.15)),
         "Sell 10% when the stock is far above its 50-day average (or RSI says 'overbought'); buy back when it falls "
         "back to that average, or 15% below the sale price, or after 60 trading days at the latest."),
    Rule("A2", "stretch", "Stretch trim 25%: same trigger as A1", 0.25, 60,
         (("ma", 50), ("mult", 1.30), ("rsi", 75), ("rebuy_ma", 1.00), ("drop", 0.15)),
         "Same as A1 but sells a quarter of the position."),
    Rule("A3", "stretch", "Big-stretch trim 25%: price ≥1.60× its 200-day avg", 0.25, 120,
         (("ma", 200), ("mult", 1.60), ("rsi", None), ("rebuy_ma", 1.10), ("drop", 0.25)),
         "Sell 25% only in a big run-up (60% above the 200-day average); buy back near 1.1× that average, 25% below "
         "the sale price, or after 120 trading days."),
    Rule("E1", "earnings", "Earnings trim 10%: sell 2 days before, rebuy 3 days after", 0.10, 5, (("pre", 2), ("post", 3)),
         "Sell 10% two trading days before the earnings reaction day and buy back three trading days after it."),
    Rule("E2", "earnings", "Earnings trim 25%: sell 2 days before, rebuy 3 days after", 0.25, 5, (("pre", 2), ("post", 3)),
         "Same as E1 with a quarter of the position."),
    Rule("B1", "band", "Bollinger trim 10%: close above the 20-day 2.5σ band", 0.10, 30, (("kind", "boll"), ("k", 2.5)),
         "Sell 10% when the close is above the upper Bollinger band (20-day average + 2.5 standard deviations); buy "
         "back at the 20-day average, 10% lower, or after 30 trading days."),
    Rule("B2", "band", "ATR trim 10%: close ≥ 20-day avg + 3×ATR", 0.10, 30, (("kind", "atr"), ("k", 3.0)),
         "Sell 10% when the close is more than 3 'average true ranges' (typical daily ranges) above its 20-day average; "
         "same buy-back rules as B1."),
]
RULE_BY_KEY = {r.key: r for r in RULES}


def reaction_days(index: pd.DatetimeIndex, earnings: List[pd.Timestamp]) -> List[int]:
    """Bar index of the first session that can react to each report (after 4 pm ET → next session)."""
    out = []
    for e in earnings:
        e = pd.Timestamp(e)
        after = e.tz_convert("America/New_York").hour >= 16 if e.tzinfo else False
        day = pd.Timestamp(e.date())
        i = index.searchsorted(day + (pd.Timedelta(days=1) if after else pd.Timedelta(0)))
        if 0 <= i < len(index):
            out.append(int(i))
    return sorted(set(out))


def generate_trips(rule: Rule, df: pd.DataFrame, earnings: Optional[List[pd.Timestamp]] = None,
                   lo: int = 0, hi: Optional[int] = None) -> List[Tuple[int, int]]:
    """Round trips (sell bar, buy bar) — both are execution bars (close).  Signals use bars ≤ execution − 1.

    Only trips that start and end inside [lo, hi) are produced; a trip still open at hi−1 is closed there."""
    c = df["Close"].astype(float)
    n = len(c)
    hi = n if hi is None else hi
    p = dict(rule.params)
    trips: List[Tuple[int, int]] = []
    if rule.family == "earnings":
        if not earnings:
            return []
        for r in reaction_days(c.index, earnings):
            s, b = r - p["pre"], r + p["post"]
            if s - 1 >= lo and b < hi and (not trips or s > trips[-1][1]):
                trips.append((s, b))
        return trips
    if rule.family == "stretch":
        ma = c.rolling(p["ma"]).mean()
        r_ = rsi(c)
        trig = (c >= p["mult"] * ma) | ((r_ >= p["rsi"]) if p["rsi"] else False)
        back = c <= p["rebuy_ma"] * ma
    else:
        ma = c.rolling(20).mean()
        if p["kind"] == "boll":
            trig = c > ma + p["k"] * c.rolling(20).std()
        else:
            trig = c >= ma + p["k"] * atr(df)
        back = c <= ma
        p["drop"] = 0.10
    trig, back = trig.fillna(False).values, back.fillna(False).values
    cv = c.values
    i = max(lo, 1)
    while i < hi - 1:
        if trig[i]:
            s = i + 1                                  # execute next close
            j = s
            while j < hi - 1:
                if back[j] or cv[j] <= cv[s] * (1 - p["drop"]) or j - s >= rule.timeout - 1:
                    break
                j += 1
            b = min(j + 1, hi - 1)
            if b > s:
                trips.append((s, b))
            i = b + 5                                  # 5-day cool-down after a rebuy
        else:
            i += 1
    return trips


# ════════════════════════════════════════════════════════════════════════
# Simulation
# ════════════════════════════════════════════════════════════════════════
def _d(ts) -> date:
    return pd.Timestamp(ts).date()


def _px_on(c: pd.Series, d: date) -> float:
    """Last close on or before d (the price at which a year-end tax bill is converted to shares)."""
    i = int(c.index.searchsorted(pd.Timestamp(d), side="right")) - 1
    return float(c.iloc[max(i, 0)])


def simulate(close: pd.Series, trips: List[Tuple[int, int]], trim: float, profile: tx.TaxProfile,
             method: str = "fifo", lo: int = 0, hi: Optional[int] = None, shares0: float = 1_000.0,
             basis0: Optional[float] = None, acquired0: Optional[date] = None, log: bool = False,
             cost: float = COST) -> dict:
    """Run round trips on a position that starts with `shares0` shares at bar lo.  Returns share-equivalents etc."""
    c = close.astype(float)
    hi = len(c) if hi is None else hi
    idx = c.index
    p0 = float(c.iloc[lo])
    led = Ledger(profile, method, cost=cost)
    start = _d(idx[lo])
    led._seq += 1
    led.lots.append(Lot(led._seq, shares0, shares0 * (basis0 if basis0 is not None else p0),
                        acquired0 or start - timedelta(days=400), start - timedelta(days=400)))
    rows = []
    year = start.year

    def roll_years(to: date):
        nonlocal year
        while year < to.year:
            led.settle_year(year, date(year, 12, 31), _px_on(c, date(year, 12, 31)))
            year += 1

    for s, b in trips:
        if s < lo or b >= hi:
            continue
        ds, db = _d(idx[s]), _d(idx[b])
        roll_years(ds)
        sold = led.shares * trim
        r = led.sell(ds, float(c.iloc[s]), sold)
        roll_years(db)
        cash = led.cash
        got = led.buy(db, float(c.iloc[b]), dollars=cash)
        if log:
            rows.append({"Sold on": ds, "Sell price": float(c.iloc[s]), "Shares sold": sold, "Rebought on": db,
                         "Rebuy price": float(c.iloc[b]), "Shares rebought": got, "Share gain": got - sold,
                         "Days out": int(np.busday_count(ds, db)), "Realized gain $": r["gain"],
                         "Term": "long" if r["lt"] and not r["st"] else "short" if r["st"] else "—"})
    end = _d(idx[hi - 1])
    roll_years(end)
    pe = float(c.iloc[hi - 1])
    liq_s = led.liquidate_value(end, pe)          # before the final year is settled (sale + this year together)
    led.settle_year(end.year, end, pe)
    paid_eq = led.shares + led.cash / pe - led.tax_shares
    hold = Ledger(profile, method, cost=cost)     # buy-and-hold from the same start
    hold.lots.append(Lot(1, shares0, shares0 * (basis0 if basis0 is not None else p0),
                         acquired0 or start - timedelta(days=400), start - timedelta(days=400)))
    liq_h = hold.liquidate_value(end, pe)
    share_eq = shares0 * liq_s / liq_h if liq_h > 0 else float("nan")
    if log:
        _attach_tax(rows, led)
    n_tr = sum(1 for s, b in trips if s >= lo and b < hi)
    return {"share_eq": share_eq, "hold_shares": shares0, "share_gain": share_eq - shares0,
            "share_gain_pct": share_eq / shares0 - 1, "trips": n_tr,
            "tax_paid": -led.tax_cash, "taxes": dict(led.taxes), "carry": led.carry, "disallowed": led.disallowed,
            "after_tax_liq": liq_s, "hold_after_tax_liq": liq_h,
            "liq_gain_pct": (liq_s / liq_h - 1) if liq_h else None, "log": rows, "end_price": pe,
            "taxpaid_shares_pct": paid_eq / shares0 - 1}


def _liq_pair(led: Ledger, profile, method, shares0, basis_ps, start: date, end: date, pe: float) -> dict:
    """After-tax value if everything were sold on the last day: strategy vs plain hold (deferred tax counted)."""
    hold = Ledger(profile, method, cost=led.cost)
    hold.lots.append(Lot(1, shares0, shares0 * basis_ps, start - timedelta(days=400), start - timedelta(days=400)))
    a, b = led.liquidate_value(end, pe), hold.liquidate_value(end, pe)
    return {"after_tax_liq": a, "hold_after_tax_liq": b, "liq_gain_pct": (a / b - 1) if b else None}


def _attach_tax(rows: List[dict], led: Ledger):
    """Spread each year's incremental tax over that year's trips in proportion to their gains (display only)."""
    by_year: Dict[int, float] = {}
    for r in rows:
        by_year[r["Sold on"].year] = by_year.get(r["Sold on"].year, 0.0) + abs(r["Realized gain $"])
    for r in rows:
        y = r["Sold on"].year
        tot = by_year.get(y) or 0.0
        r["Est. tax $"] = led.taxes.get(y, 0.0) * abs(r["Realized gain $"]) / tot if tot else 0.0


def equity_paths(close: pd.Series, trips, trim: float, lo: int = 0, hi: Optional[int] = None,
                 shares0: float = 1_000.0, cost: float = COST) -> pd.DataFrame:
    """Daily share count and $ value (pre-tax, after costs) of the rule vs hold — for the chart."""
    c = close.astype(float)
    hi = len(c) if hi is None else hi
    sh = np.full(hi - lo, shares0, dtype=float)
    cash = np.zeros(hi - lo)
    cur_sh, cur_cash = shares0, 0.0
    t_iter = iter([t for t in trips if t[0] >= lo and t[1] < hi])
    nxt = next(t_iter, None)
    out_until = -1
    for k, i in enumerate(range(lo, hi)):
        if nxt and i == nxt[0]:
            sold = cur_sh * trim
            cur_sh -= sold
            cur_cash += sold * c.iloc[i] * (1 - cost)
            out_until = nxt[1]
        if i == out_until:
            cur_sh += cur_cash / (c.iloc[i] * (1 + cost))
            cur_cash = 0.0
            nxt = next(t_iter, None)
            out_until = -1
        sh[k], cash[k] = cur_sh, cur_cash
    px = c.iloc[lo:hi].values
    return pd.DataFrame({"rule_shares_eq": sh + cash / px, "rule_value": sh * px + cash, "hold_value": shares0 * px},
                        index=c.index[lo:hi])


def max_drawdown(v: pd.Series) -> float:
    v = v.astype(float)
    return float((v / v.cummax() - 1).min())


def trip_stats(log: List[dict]) -> dict:
    if not log:
        return {"n": 0, "hit": None, "avg_win": None, "avg_loss": None, "worst": None, "days_out": 0}
    g = np.array([r["Share gain"] / r["Shares sold"] for r in log])
    wins, losses = g[g > 0], g[g <= 0]
    w = min(log, key=lambda r: r["Share gain"] / r["Shares sold"])
    return {"n": len(log), "hit": float((g > 0).mean()), "avg_win": float(wins.mean()) if len(wins) else None,
            "avg_loss": float(losses.mean()) if len(losses) else None,
            "worst": {"date": w["Sold on"], "pct": w["Share gain"] / w["Shares sold"],
                      "sell": w["Sell price"], "rebuy": w["Rebuy price"]},
            "days_out": int(sum(r["Days out"] for r in log))}


def random_trips(trips: List[Tuple[int, int]], lo: int, hi: int, rng: np.random.Generator,
                 tries: int = 400) -> List[Tuple[int, int]]:
    """Same number and lengths of trips at random, non-overlapping dates inside [lo, hi)."""
    lens = [b - s for s, b in trips]
    rng.shuffle(lens)
    out: List[Tuple[int, int]] = []
    for L in lens:
        for _ in range(tries):
            s = int(rng.integers(lo + 1, max(lo + 2, hi - L - 1)))
            b = s + L
            if b < hi and all(b + 5 < s2 or s > b2 + 5 for s2, b2 in out):
                out.append((s, b))
                break
    return sorted(out)


def evaluate_rule(rule: Rule, df: pd.DataFrame, profile: tx.TaxProfile, method: str = "fifo",
                  earnings=None, n_random: int = N_RANDOM, seed: int = SEED, shares0: float = 1_000.0,
                  cost: float = COST) -> dict:
    """Full-sample, in-sample and hold-out results, pre-tax (IRA) and after-tax, plus random-date p-values."""
    c = df["Close"].astype(float)
    n = len(c)
    cut = int(n * IS_FRAC)
    ira = replace(profile, account="ira")
    res = {"rule": rule}
    windows = {"full": (0, n), "in_sample": (0, cut), "hold_out": (cut, n)}
    rng = np.random.default_rng(seed)
    for name, (lo, hi) in windows.items():
        tr = generate_trips(rule, df, earnings, lo, hi)
        pre = simulate(c, tr, rule.trim, ira, method, lo, hi, shares0, log=(name == "full"), cost=cost)
        post = simulate(c, tr, rule.trim, profile, method, lo, hi, shares0, log=(name == "full"), cost=cost)
        rnd = []
        if tr and n_random:
            for _ in range(n_random if name != "in_sample" else 0):
                rt = random_trips(tr, lo, hi, rng)
                rnd.append(simulate(c, rt, rule.trim, ira, method, lo, hi, shares0, cost=cost)["share_gain_pct"])
        pval = (1 + sum(r >= pre["share_gain_pct"] for r in rnd)) / (len(rnd) + 1) if rnd else None
        res[name] = {"pre": pre, "post": post, "n_trips": len(tr), "p_random": pval,
                     "random_median": float(np.median(rnd)) if rnd else None, "trips": tr}
    res["stats"] = trip_stats(res["full"]["post"]["log"])
    res["verdict"] = verdict(res)
    return res


def verdict(res: dict) -> str:
    f, i, o = res["full"], res["in_sample"], res["hold_out"]
    if f["n_trips"] < MIN_TRIPS or o["n_trips"] < MIN_TRIPS_OOS:
        return INSUFFICIENT
    ok = (i["post"]["share_gain_pct"] > 0 and o["post"]["share_gain_pct"] > 0
          and f["pre"]["share_gain_pct"] > 0 and f["post"]["share_gain_pct"] > 0
          and (f["p_random"] or 1) < P_FULL and (o["p_random"] or 1) < P_OOS)
    return EDGE if ok else NO_EDGE


def overall(results: List[dict]) -> str:
    vs = [r["verdict"] for r in results]
    if EDGE in vs:
        return EDGE
    if all(v == INSUFFICIENT for v in vs):
        return INSUFFICIENT
    return NO_EDGE


# ════════════════════════════════════════════════════════════════════════
# (d) Covered-call overlay — Black-Scholes, labelled assumptions
# ════════════════════════════════════════════════════════════════════════
from math import erf, exp, log as _ln, sqrt


def _N(x):
    return 0.5 * (1 + erf(x / sqrt(2)))


def bs_call(S, K, T, sig, r=0.04):
    if T <= 0 or sig <= 0:
        return max(0.0, S - K)
    d1 = (_ln(S / K) + (r + sig * sig / 2) * T) / (sig * sqrt(T))
    return S * _N(d1) - K * exp(-r * T) * _N(d1 - sig * sqrt(T))


def strike_for_delta(S, T, sig, delta, r=0.04):
    """Strike whose call delta = N(d1) equals `delta`."""
    from statistics import NormalDist
    d1 = NormalDist().inv_cdf(delta)
    return S * exp((r + sig * sig / 2) * T - d1 * sig * sqrt(T))


CC_SETS = [
    {"key": "CC1", "label": "Covered calls on 50% of shares, 0.25 delta, ~35 days, IV = realized vol",
     "cover": 0.5, "delta": 0.25, "days": 25, "iv_mult": 1.0},
    {"key": "CC2", "label": "Covered calls on 50% of shares, 0.25 delta, ~35 days, IV = 1.2 × realized (proxy)",
     "cover": 0.5, "delta": 0.25, "days": 25, "iv_mult": 1.2},
    {"key": "CC3", "label": "Covered calls on 50% of shares, 0.20 delta, ~45 days, IV = 1.2 × realized (proxy)",
     "cover": 0.5, "delta": 0.20, "days": 31, "iv_mult": 1.2},
]
CC_HAIRCUT = 0.05      # sell at 5% below the model mid (bid/ask)


def simulate_cc(close: pd.Series, cfg: dict, profile: tx.TaxProfile, method: str = "fifo", lo: int = 0,
                hi: Optional[int] = None, shares0: float = 1_000.0, cost: float = COST) -> dict:
    """Write calls every cycle; if assigned, shares are sold at the strike and bought back at the expiry close."""
    c = close.astype(float)
    hi = len(c) if hi is None else hi
    vol = np.log(c).diff().rolling(21).std() * np.sqrt(252)
    led = Ledger(profile, method, cost=cost)
    start = _d(c.index[lo])
    led.lots.append(Lot(1, shares0, shares0 * float(c.iloc[lo]), start - timedelta(days=400), start - timedelta(days=400)))
    led._seq = 1
    year, i = start.year, max(lo, 22)
    cycles = assigned = 0
    prem_total = 0.0
    while i + cfg["days"] < hi:
        S, sig = float(c.iloc[i]), float(vol.iloc[i]) * cfg["iv_mult"]
        if not np.isfinite(sig) or sig <= 0:
            i += 1
            continue
        T = cfg["days"] * 365 / 252 / 365
        K = strike_for_delta(S, T, sig, cfg["delta"])
        n = led.shares * cfg["cover"]
        prem = bs_call(S, K, T, sig) * (1 - CC_HAIRCUT) * n
        e = i + cfg["days"]
        de = _d(c.index[e])
        while year < de.year:
            led.settle_year(year, date(year, 12, 31), _px_on(c, date(year, 12, 31)))
            year += 1
        led.cash += prem
        led._real(de, prem, 0.0)                     # option premium: short-term gain at expiry/assignment
        prem_total += prem
        ST = float(c.iloc[e])
        if ST > K:                                   # assigned → sell at K, buy back at the close
            assigned += 1
            led.sell(de, K, n, cost=0.0)
        led.buy(de, ST, dollars=led.cash)            # buy back assigned shares and reinvest the premium
        cycles += 1
        i = e + 1
    end = _d(c.index[hi - 1])
    while year < end.year:
        led.settle_year(year, date(year, 12, 31), _px_on(c, date(year, 12, 31)))
        year += 1
    pe = float(c.iloc[hi - 1])
    liq = _liq_pair(led, profile, method, shares0, float(c.iloc[lo]), start, end, pe)
    led.settle_year(end.year, end, pe)
    paid_eq = led.shares + led.cash / pe - led.tax_shares
    share_eq = shares0 * (1 + liq["liq_gain_pct"]) if liq["liq_gain_pct"] is not None else float("nan")
    return {**liq, "share_eq": share_eq, "share_gain_pct": share_eq / shares0 - 1,
            "taxpaid_shares_pct": paid_eq / shares0 - 1, "cycles": cycles, "assigned": assigned,
            "premium": prem_total, "tax_paid": -led.tax_cash, "disallowed": led.disallowed}


# ════════════════════════════════════════════════════════════════════════
# (e) Tax-loss-harvest swap into a correlated peer for 31 days
# ════════════════════════════════════════════════════════════════════════
TLH = {"loss_trigger": 0.15, "days_in_peer": 31, "cooldown_days": 60}


def simulate_tlh(close: pd.Series, peer, profile: tx.TaxProfile, method: str = "fifo", lo: int = 0,
                 hi: Optional[int] = None, shares0: float = 1_000.0, basis0: Optional[float] = None,
                 cost: float = COST) -> dict:
    """When the position is ≥15% below its tax basis: sell it all, buy the peer, wait 31 calendar days (outside the
    30-day wash-sale window), sell the peer, buy the stock back.  The peer is a different company, so it is assumed
    NOT 'substantially identical' (IRS Pub. 550) — a judgment the user should confirm with a CPA."""
    c = close.astype(float)
    if isinstance(peer, pd.DataFrame):           # candidates: pick the most correlated one at each swap (point-in-time)
        cands = peer.reindex(c.index).ffill().astype(float)
    else:
        cands = pd.DataFrame({"PEER": peer}).reindex(c.index).ffill().astype(float)
    hi = len(c) if hi is None else hi
    idx = c.index
    used: List[str] = []
    led = Ledger(profile, method, cost=cost)
    start = _d(idx[lo])
    b0 = basis0 if basis0 is not None else float(c.iloc[lo])
    led.lots.append(Lot(1, shares0, shares0 * b0, start - timedelta(days=400), start - timedelta(days=400)))
    led._seq = 1
    year, i, last = start.year, lo + 1, None
    swaps, harvested, track = 0, 0.0, []
    while i < hi - 1:
        d = _d(idx[i])
        basis_ps = sum(l.basis for l in led.lots) / led.shares
        name = None
        if (float(c.iloc[i]) <= basis_ps * (1 - TLH["loss_trigger"])
                and (last is None or (d - last).days >= TLH["cooldown_days"])):
            name = _best_peer(c, cands, i)
        if name is not None:
            pr = cands[name]
            used.append(name)
            j = int(idx.searchsorted(pd.Timestamp(d + timedelta(days=TLH["days_in_peer"]))))
            if j >= hi:
                break
            while year < d.year:
                led.settle_year(year, date(year, 12, 31), _px_on(c, date(year, 12, 31)))
                year += 1
            r = led.sell(d, float(c.iloc[i]), led.shares)
            harvested += -min(0.0, r["gain"])
            peer_sh = led.cash / (float(pr.iloc[i]) * (1 + cost))
            peer_cost = led.cash
            led.cash = 0.0
            dj = _d(idx[j])
            while year < dj.year:
                led.settle_year(year, date(year, 12, 31), _px_on(c, date(year, 12, 31)))
                year += 1
            proceeds = peer_sh * float(pr.iloc[j]) * (1 - cost)
            g = proceeds - peer_cost
            days = (dj - d).days
            led._real(dj, g if days <= 365 else 0.0, g if days > 365 else 0.0)
            led.cash = proceeds
            led.buy(dj, float(c.iloc[j]), dollars=led.cash)
            track.append(float(np.log(pr.iloc[j] / pr.iloc[i]) - np.log(c.iloc[j] / c.iloc[i])))
            swaps += 1
            last = dj
            i = j + 1
            continue
        i += 1
    end = _d(idx[hi - 1])
    while year < end.year:
        led.settle_year(year, date(year, 12, 31), _px_on(c, date(year, 12, 31)))
        year += 1
    pe = float(c.iloc[hi - 1])
    liq = _liq_pair(led, profile, method, shares0, b0, start, end, pe)
    led.settle_year(end.year, end, pe)
    paid_eq = led.shares + led.cash / pe - led.tax_shares
    share_eq = shares0 * (1 + liq["liq_gain_pct"]) if liq["liq_gain_pct"] is not None else float("nan")
    return {**liq, "share_eq": share_eq, "share_gain_pct": share_eq / shares0 - 1,
            "taxpaid_shares_pct": paid_eq / shares0 - 1, "swaps": swaps, "harvested": harvested,
            "tax_paid": -led.tax_cash, "carry": led.carry, "tracking_mean": float(np.mean(track)) if track else None,
            "tracking": track, "peers_used": used}


def _best_peer(c: pd.Series, cands: pd.DataFrame, i: int, lookback: int = 252) -> Optional[str]:
    """Most correlated candidate over the trailing `lookback` bars ending at bar i (no look-ahead)."""
    lo = max(0, i - lookback)
    if i - lo < 60:
        return None
    r = np.log(c.iloc[lo:i + 1]).diff()
    best, bc = None, -2.0
    for k in cands.columns:
        x = cands[k].iloc[lo:i + 1]
        if x.isna().mean() > 0.2 or not np.isfinite(cands[k].iloc[i]):
            continue
        cc = r.corr(np.log(x).diff())
        if np.isfinite(cc) and cc > bc:
            best, bc = k, cc
    return best


def harvest_now(shares: float, price: float, basis_ps: float, profile: tx.TaxProfile, long_term: bool = True) -> dict:
    """Today's tax-loss harvest for the user's real position: this year's saving and the carryforward left."""
    loss = (basis_ps - price) * shares
    if loss <= 0 or not profile.taxed():
        return {"loss": max(0.0, loss), "saving_now": 0.0, "carry": 0.0}
    st, lt = (0.0, -loss) if long_term else (-loss, 0.0)
    r = tx.year_tax(profile, st, lt, tx.Carry())
    carry = r["carry"].st + r["carry"].lt
    yrs = []
    c = r["carry"]
    for k in range(1, 6):                         # how fast the carryforward is used against ordinary income alone
        if c.st + c.lt <= 0:
            break
        rr = tx.year_tax(profile, 0.0, 0.0, c)
        yrs.append(-rr["tax"])
        c = rr["carry"]
    return {"loss": loss, "saving_now": -r["tax"], "carry": carry, "next_years_saving": yrs,
            "new_basis_ps": price, "deferred_gain_per_share": basis_ps - price}


def peer_for(symbol: str, closes: pd.DataFrame, as_of: Optional[pd.Timestamp] = None, lookback: int = 252) -> Optional[str]:
    """Most correlated other stock over the trailing year (point-in-time if as_of is given)."""
    if symbol not in closes:
        return None
    px = closes if as_of is None else closes[closes.index <= as_of]
    r = np.log(px.iloc[-lookback:]).diff()
    cors = r.corr()[symbol].drop(symbol, errors="ignore").dropna()
    return None if cors.empty else str(cors.idxmax())


def zones_today(rule: Rule, df: pd.DataFrame) -> Optional[dict]:
    """Price that would trigger a trim today and the buy-back level, for a rule that PASSED (else not shown)."""
    c = df["Close"].astype(float)
    p = dict(rule.params)
    if rule.family == "stretch":
        ma = float(c.rolling(p["ma"]).mean().iloc[-1])
        return {"trim_at": p["mult"] * ma, "rebuy_at": p["rebuy_ma"] * ma, "basis": f"{p['ma']}-day average {ma:,.2f}"}
    if rule.family == "band":
        ma = float(c.rolling(20).mean().iloc[-1])
        w = (p["k"] * float(c.rolling(20).std().iloc[-1]) if p["kind"] == "boll" else p["k"] * float(atr(df).iloc[-1]))
        return {"trim_at": ma + w, "rebuy_at": ma, "basis": f"20-day average {ma:,.2f}"}
    return None
