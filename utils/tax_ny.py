"""utils/tax_ny.py — tax-year-2026 US federal + New York State + New York City tax on capital gains.

Purpose: estimate the INCREMENTAL tax caused by trading (realized short/long-term gains and losses) for a New York
resident, so the ♻️ Trim & Rebuy page can compare strategies after tax.  It is an estimate, NOT tax advice.

Every rate / bracket below is cited (SOURCES) and dated.  Deliberate simplifications (all labelled in the UI):
  * "other income" is treated as ordinary (wage-type) income; no itemized deductions, credits, AMT, SALT or phase-outs.
  * standard deduction only (federal and NY).
  * NIIT: net investment income = this trading's net capital gain only (other investment income ignored).
  * NY's "supplemental tax" (benefit recapture for NY AGI > $107,650) is NOT modelled, so NY tax on high incomes is
    slightly understated; NY taxes capital gains as ordinary income (no preferential rate).
  * the same 2026 rules are applied to every year of a backtest.
Capital-loss rules (IRC §1211(b), §1212(b); IRS Topic 409): short- and long-term are netted, a net loss offsets up to
$3,000 of ordinary income per year ($1,500 married filing separately), the rest carries forward keeping its character.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

TAX_YEAR = 2026
VERIFIED = "2026-10-19"

SOURCES = {
    "fed_brackets": ("IRS Rev. Proc. 2025-32 §4.01 (2026 rate tables) and IRS newsroom, Oct 9 2025",
                     "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf"),
    "fed_news": ("IRS: tax inflation adjustments for tax year 2026 (standard deduction, brackets)",
                 "https://www.irs.gov/newsroom/irs-releases-tax-inflation-adjustments-for-tax-year-2026-including-amendments-from-the-one-big-beautiful-bill"),
    "ltcg": ("IRS Rev. Proc. 2025-32 §4.03 — maximum capital-gains rate thresholds for 2026",
             "https://www.irs.gov/pub/irs-drop/rp-25-32.pdf"),
    "niit": ("IRS Topic 559, Net Investment Income Tax (3.8%; thresholds set by statute, not indexed)",
             "https://www.irs.gov/taxtopics/tc559"),
    "loss_limit": ("IRS Topic 409, Capital gains and losses ($3,000 limit, carryover)",
                   "https://www.irs.gov/taxtopics/tc409"),
    "wash_sale": ("IRS Publication 550, Wash sales (30 days before/after; disallowed loss added to the new shares' "
                  "basis; holding period carries over)", "https://www.irs.gov/publications/p550"),
    "holding": ("IRS Publication 550, Holding period (more than 1 year = long-term; starts the day after purchase)",
                "https://www.irs.gov/publications/p550"),
    "ny_rates": ("NY Laws of 2025 ch. 59 Part A (A3009), 2026 rate schedules — summary by Thomson Reuters; NYS DTF "
                 "withholding pub. NYS-50-T-NYS (1/26)",
                 "https://tax.thomsonreuters.com/news/new-york-enacts-income-tax-reductions-new-tax-credits-makes-other-changes/"),
    "ny_dtf": ("NYS DTF: 2026 rate reductions (withholding tax rate changes)", "https://www.tax.ny.gov/bus/wt/rate.htm"),
    "ny_std": ("NYC Comptroller: NY taxable income & standard deduction ($8,000 single / $16,050 joint)",
               "https://comptroller.nyc.gov/reports/the-nyc-personal-income-tax-before-and-after-the-pandemic/"),
    "nyc_rates": ("NYC resident tax rate schedule (unchanged for 2026 — NYS DTF NYS-50-T-NYC (1/26); NYC Comptroller)",
                  "https://www.tax.ny.gov/pdf/publications/withholding/nys50_t_nyc.pdf"),
    "schwab_fifo": ("Schwab: FIFO is the default cost-basis method for equities and ETFs",
                    "https://help.streetsmart.schwab.com/Com/3.58/Content/Cost%20Basis%20Method.htm"),
    "ira": ("IRS Publication 590-B: no tax on trades inside a traditional/Roth IRA (tax only on distributions; "
            "qualified Roth distributions tax-free)", "https://www.irs.gov/publications/p590b"),
}

STATUSES = ("single", "married_joint")
STATUS_LABEL = {"single": "Single", "married_joint": "Married filing jointly"}

# (upper bound of bracket, rate); last bound = None
FED = {
    "single": [(12_400, .10), (50_400, .12), (105_700, .22), (201_775, .24), (256_225, .32), (640_600, .35), (None, .37)],
    "married_joint": [(24_800, .10), (100_800, .12), (211_400, .22), (403_550, .24), (512_450, .32), (768_700, .35),
                      (None, .37)],
}
FED_STD = {"single": 16_100, "married_joint": 32_200}
LTCG = {"single": (49_450, 545_500), "married_joint": (98_900, 613_700)}      # top of 0% band, top of 15% band
NIIT_RATE, NIIT_THRESHOLD = 0.038, {"single": 200_000, "married_joint": 250_000}
LOSS_LIMIT = {"single": 3_000, "married_joint": 3_000}

NY = {
    "single": [(8_500, .039), (11_700, .044), (13_900, .0515), (80_650, .054), (215_400, .059), (1_077_550, .0685),
               (5_000_000, .0965), (25_000_000, .103), (None, .109)],
    "married_joint": [(17_150, .039), (23_600, .044), (27_900, .0515), (161_550, .054), (323_200, .059),
                      (2_155_350, .0685), (5_000_000, .0965), (25_000_000, .103), (None, .109)],
}
NY_STD = {"single": 8_000, "married_joint": 16_050}
NYC = {
    "single": [(12_000, .03078), (25_000, .03762), (50_000, .03819), (None, .03876)],
    "married_joint": [(21_600, .03078), (45_000, .03762), (90_000, .03819), (None, .03876)],
}


def bracket_tax(income: float, brackets) -> float:
    tax, lo = 0.0, 0.0
    income = max(0.0, income)
    for hi, rate in brackets:
        top = income if hi is None else min(income, hi)
        if top > lo:
            tax += (top - lo) * rate
        if hi is None or income <= hi:
            break
        lo = hi
    return tax


def marginal_rate(income: float, brackets) -> float:
    for hi, rate in brackets:
        if hi is None or income < hi:
            return rate
    return brackets[-1][1]


@dataclass
class TaxProfile:
    status: str = "single"
    other_income: float = 100_000.0     # PLACEHOLDER — the user must set their own
    nyc_resident: bool = True
    account: str = "taxable"            # 'taxable' | 'ira' (traditional/Roth: trades not taxed)

    def taxed(self) -> bool:
        return self.account == "taxable"


@dataclass
class Carry:
    st: float = 0.0   # short-term loss carried forward (positive number)
    lt: float = 0.0


def net_capital(st: float, lt: float, carry: Carry, status: str = "single") -> dict:
    """Net one year's realized short/long-term results with prior carryovers (IRS Sch. D logic, simplified).

    Returns taxable st/lt gains (≥0), the ordinary-income deduction (≤ $3,000) and the new carryover."""
    st_n = st - carry.st
    lt_n = lt - carry.lt
    if st_n >= 0 and lt_n >= 0:
        return {"st_gain": st_n, "lt_gain": lt_n, "deduction": 0.0, "carry": Carry()}
    if st_n < 0 and lt_n > 0:                      # ST loss offsets LT gain
        lt_left = lt_n + st_n
        if lt_left >= 0:
            return {"st_gain": 0.0, "lt_gain": lt_left, "deduction": 0.0, "carry": Carry()}
        st_n, lt_n = lt_left, 0.0
    elif lt_n < 0 and st_n > 0:                    # LT loss offsets ST gain
        st_left = st_n + lt_n
        if st_left >= 0:
            return {"st_gain": st_left, "lt_gain": 0.0, "deduction": 0.0, "carry": Carry()}
        st_n, lt_n = 0.0, st_left
    # net loss: deduct up to the limit, short-term loss used first; the rest keeps its character
    st_loss, lt_loss = max(0.0, -st_n), max(0.0, -lt_n)
    ded = min(LOSS_LIMIT[status], st_loss + lt_loss)
    use_st = min(st_loss, ded)
    use_lt = ded - use_st
    return {"st_gain": 0.0, "lt_gain": 0.0, "deduction": ded, "carry": Carry(st_loss - use_st, lt_loss - use_lt)}


def total_tax(p: TaxProfile, st_gain: float = 0.0, lt_gain: float = 0.0, deduction: float = 0.0) -> dict:
    """Total federal + NY + NYC tax for one year, given already-netted gains (≥0) and the loss deduction."""
    if not p.taxed():
        return {"federal": 0.0, "niit": 0.0, "ny": 0.0, "nyc": 0.0, "total": 0.0}
    s = p.status
    agi = p.other_income + st_gain + lt_gain - deduction
    taxable = max(0.0, agi - FED_STD[s])
    pref = min(lt_gain, taxable)                    # long-term gain taxed at 0/15/20, stacked on top
    ordinary = taxable - pref
    fed = bracket_tax(ordinary, FED[s])
    z, f = LTCG[s]
    in0 = max(0.0, min(taxable, z) - ordinary)
    in15 = max(0.0, min(taxable, f) - max(ordinary, z))
    in20 = max(0.0, pref - in0 - in15)
    fed += 0.15 * in15 + 0.20 * in20
    nii = st_gain + lt_gain
    niit = NIIT_RATE * max(0.0, min(nii, agi - NIIT_THRESHOLD[s]))
    ny_taxable = max(0.0, agi - NY_STD[s])
    ny = bracket_tax(ny_taxable, NY[s])
    nyc = bracket_tax(ny_taxable, NYC[s]) if p.nyc_resident else 0.0
    return {"federal": fed, "niit": niit, "ny": ny, "nyc": nyc, "total": fed + niit + ny + nyc}


def year_tax(p: TaxProfile, st: float, lt: float, carry: Carry) -> dict:
    """Incremental tax caused by this year's realized results (vs. no trading), and the carryover to next year."""
    if not p.taxed():
        return {"tax": 0.0, "carry": Carry(), "deduction": 0.0, "st_gain": 0.0, "lt_gain": 0.0, "detail": {}}
    n = net_capital(st, lt, carry, p.status)
    base = total_tax(p)["total"]
    with_ = total_tax(p, n["st_gain"], n["lt_gain"], n["deduction"])
    return {"tax": with_["total"] - base, "carry": n["carry"], "deduction": n["deduction"],
            "st_gain": n["st_gain"], "lt_gain": n["lt_gain"], "detail": with_}


def marginal_rates(p: TaxProfile) -> dict:
    """Combined marginal rate on an extra $1 of short-term vs long-term gain at the profile's income (for display)."""
    if not p.taxed():
        return {"st": 0.0, "lt": 0.0}
    d = 1_000.0
    st = year_tax(p, d, 0.0, Carry())["tax"] / d
    lt = year_tax(p, 0.0, d, Carry())["tax"] / d
    return {"st": st, "lt": lt}


def bracket_table(status: str = "single") -> List[dict]:
    rows = []
    for name, br in (("Federal ordinary / short-term", FED[status]), ("New York State", NY[status]),
                     ("New York City (residents)", NYC[status])):
        lo = 0
        for hi, r in br:
            rows.append({"Tax": name, "Taxable income": f"${lo:,.0f} – " + ("and up" if hi is None else f"${hi:,.0f}"),
                         "Rate": f"{r*100:.3g}%"})
            lo = hi or lo
    z, f = LTCG[status]
    rows += [{"Tax": "Federal long-term gains", "Taxable income": f"$0 – ${z:,}", "Rate": "0%"},
             {"Tax": "Federal long-term gains", "Taxable income": f"${z:,} – ${f:,}", "Rate": "15%"},
             {"Tax": "Federal long-term gains", "Taxable income": f"over ${f:,}", "Rate": "20%"},
             {"Tax": "Net investment income tax", "Taxable income": f"MAGI over ${NIIT_THRESHOLD[status]:,}", "Rate": "3.8%"}]
    return rows
