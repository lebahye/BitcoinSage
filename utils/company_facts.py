"""utils/company_facts.py — dated, cited balance-sheet facts per company (one entry per ticker).

Every value is (value, as_of, source_key, note).  A field that the company has not disclosed, or that could not be
verified from a filing / company release, is simply ABSENT and shows as "N/A" — nothing is estimated or invented.
Where a filing figure is missing, callers may fall back to Yahoo's latest quarterly balance sheet and must label
that fallback as "Yahoo" (see `cash_debt`).  RIOT's detailed AI-lease terms stay in utils/riot_facts.py.
Update after each quarterly report.  LAST_VERIFIED is the date these were checked.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from utils.riot_facts import Q2_2026 as _RIOT, RIOT_CIK
from utils.deep_facts import AI_PEERS, CONVERTS

LAST_VERIFIED = date(2026, 10, 19)

FIELDS = {
    "btc_held": ("Bitcoin held", "BTC"),
    "btc_pledged": ("…of which pledged / loaned", "BTC"),
    "cash_usd": ("Cash & equivalents", "$"),
    "debt_usd": ("Debt", "$"),
    "cost_to_mine_ex_da": ("Cost to mine 1 BTC (cash, excl. depreciation)", "$"),
    "cost_to_mine_incl_da": ("Cost to mine 1 BTC (all-in, incl. depreciation)", "$"),
    "converts_principal_usd": ("Convertible notes outstanding", "$"),
    "ai_contracted_mw": ("AI/HPC contracted MW", "MW"),
    "ai_contract_value_usd": ("AI/HPC contracted revenue", "$"),
}
CORE = ("btc_held", "cash_usd", "debt_usd", "cost_to_mine_ex_da", "converts_principal_usd", "ai_contracted_mw")

SOURCES = {
    "riot_q2": (_RIOT["label"], _RIOT["url"]),
    "riot_10q": ("Riot 10-Q, quarter ended Jun 30 2026",
                 "https://www.sec.gov/Archives/edgar/data/1167419/000110465926093448/riot-20260630x10q.htm"),
    "mara_q2": ("MARA Q2 2026 shareholder letter (8-K ex-99.1)",
                "https://www.sec.gov/Archives/edgar/data/1507605/000150760526000020/q226shareholderletter.htm"),
    "clsk_jun": ("CleanSpark June 2026 production update (via Blockspace)",
                 "https://blockspace.media/insight/cleanspark-bitcoin-production-holdings-june-2026/"),
    "clsk_q3": ("CleanSpark fiscal Q3 2026 results (balance sheet, Jun 30 2026)",
                "https://investors.cleanspark.com/news/news-details/2026/CleanSpark-Reports-Third-Fiscal-Quarter-2026-Results/"),
    "hut_10q": ("Hut 8 10-Q, quarter ended Jun 30 2026 (Note 5, digital assets)",
                "https://www.sec.gov/Archives/edgar/data/1964789/000110465926090025/hut-20260630x10q.htm"),
    "hut_q2": ("Hut 8 Q2 2026 results (8-K ex-99.1)",
               "https://www.sec.gov/Archives/edgar/data/1964789/000110465926090041/tm2621890d1_ex99-1.htm"),
    "cifr_10q": ("Cipher 10-Q, quarter ended Jun 30 2026 (balance sheet)",
                 "https://www.sec.gov/Archives/edgar/data/1819989/000181998926000041/cifr-20260630.htm"),
    "wulf_10q": ("TeraWulf 10-Q, quarter ended Jun 30 2026",
                 "https://www.sec.gov/Archives/edgar/data/1083301/000108330126000166/wulf-20260630.htm"),
    "wulf_pr": ("TeraWulf Q2 2026 investor presentation (8-K)",
                "https://www.sec.gov/Archives/edgar/data/1083301/000108330126000162/terawulfq22026investorpr.htm"),
    "iren_fy26": ("IREN FY26 results (quarter ended Jun 30 2026)",
                  "https://www.sec.gov/Archives/edgar/data/1878848/000187884826000051/irenreportsfy26results.htm"),
    "corz_q2": ("Core Scientific Q2 2026 results (balance sheet, Jun 30 2026)",
                "https://investors.corescientific.com/news-events/press-releases/detail/139/core-scientific-announces-second-quarter-2026-results"),
    "corz_10q": ("Core Scientific 10-Q, quarter ended Jun 30 2026",
                 "https://www.sec.gov/Archives/edgar/data/1839341/000183934126000014/core-20260630.htm"),
    "keel_q2": ("Keel Infrastructure Q2 2026 results (Aug 10 2026)", "https://ir.keelinfra.com/node/12451/pdf"),
    "btdr_sep": ("Bitdeer September 2026 production & operations update (Oct 19 2026)",
                 "https://www.globenewswire.com/news-release/2026/10/19/3383905/0/en/bitdeer-announces-september-2026-production-and-operations-update.html"),
    "btbt_10q": ("Bit Digital 10-Q, quarter ended Jun 30 2026",
                 "https://www.sec.gov/Archives/edgar/data/1710350/000121390026088709/ea0300693-10q_bitdigital.htm"),
    "mstr_8k": ("Strategy 8-K, Oct 19 2026 (holdings as of Oct 18 2026)",
                "https://www.sec.gov/Archives/edgar/data/1050446/000119312526424688/0001193125-26-424688-index.htm"),
}

_J30 = date(2026, 6, 30)

COMPANIES = {
    "RIOT": {"name": "Riot Platforms", "cik": RIOT_CIK, "fields": {
        "btc_held": (_RIOT["btc_held"], _J30, "riot_q2", ""),
        "btc_pledged": (_RIOT["btc_pledged"], _J30, "riot_q2", "pledged for a $200M Coinbase loan (repaid Sep 2026 per 8-K)"),
        "cash_usd": (_RIOT["cash_usd"], _J30, "riot_q2", f"incl. ${_RIOT['cash_restricted_usd']/1e6:.1f}M restricted"),
        "cost_to_mine_ex_da": (_RIOT["cost_to_mine_ex_da"], _J30, "riot_q2", "Q2 2026"),
        "cost_to_mine_incl_da": (_RIOT["cost_to_mine_incl_da"], _J30, "riot_q2", "Q2 2026"),
        "converts_principal_usd": (CONVERTS["RIOT"]["notes"][0]["principal"], _J30, "riot_10q", "0.75% notes due 2030"),
    }},
    "MARA": {"name": "MARA Holdings", "cik": "0001507605", "fields": {
        "btc_held": (35_577, _J30, "mara_q2", ""),
        "btc_pledged": (9_270, _J30, "mara_q2", "loaned, pledged or held as collateral"),
    }, "notes": "Purchased-energy cost was $38,690 per BTC at owned sites in Q2 2026 (energy only — not a full cost to "
                "mine). Repurchased ~$1.0B of convertible principal in H1 2026; remaining principal not verified here."},
    "CLSK": {"name": "CleanSpark", "cik": "0000827876", "fields": {
        "btc_held": (13_924, _J30, "clsk_jun", ""),
        "btc_pledged": (1_719, _J30, "clsk_jun", "held as collateral"),
        "cash_usd": (202.601e6, _J30, "clsk_q3", ""),
        "debt_usd": (1_782.364e6, _J30, "clsk_q3", "carrying value: long-term $1,780.0M + current $2.4M"),
    }},
    "HUT": {"name": "Hut 8", "cik": "0001964789", "fields": {
        "btc_held": (17_316, _J30, "hut_10q", "consolidated; includes 8,002 BTC of majority-owned American Bitcoin"),
        "btc_pledged": (7_940, _J30, "hut_10q", "4,850 pledged as collateral + 3,090 pledged to Bitmain"),
    }, "notes": "Parent-level general recourse debt: none after the Coatue convertible converted; $7.5B of project notes "
                "are non-recourse to Hut 8 (Q2 release)."},
    "CIFR": {"name": "Cipher Digital (ex-Cipher Mining)", "cik": "0001819989", "fields": {
        "btc_held": (646, _J30, "cifr_10q", "carried at $37.8M"),
        "cash_usd": (831.829e6, _J30, "cifr_10q", "plus $3.7B restricted cash for data-centre builds"),
        "debt_usd": (5_541.350e6, _J30, "cifr_10q", "carrying value: long-term $5,446.9M + short-term $94.5M"),
        "converts_principal_usd": (1_472.5e6, _J30, "cifr_10q", "$172.5M 1.75% due 2030 + $1.3B 0% due 2031"),
    }},
    "WULF": {"name": "TeraWulf", "cik": "0001083301", "fields": {
        "btc_held": (2, _J30, "wulf_10q", "sells what it mines"),
        "cash_usd": (2_619.191e6, _J30, "wulf_10q", "plus $409M restricted"),
        "debt_usd": (5.7e9, _J30, "wulf_pr", "principal: $2.5B converts + $3.2B senior secured (WULF Compute)"),
        "converts_principal_usd": (2.5e9, _J30, "wulf_pr", ""),
    }},
    "IREN": {"name": "IREN", "cik": "0001878848", "fields": {},
             "notes": "Cash + restricted cash $7.62B at Jun 30 2026 (FY26 results; split not verified). Bitcoin held, "
                      "debt and converts principal after the Q4 $3.0B convert issue: not verified here → N/A."},
    "CORZ": {"name": "Core Scientific", "cik": "0001839341", "fields": {
        "btc_held": (848, _J30, "corz_10q", "carried at $49.7M"),
        "cash_usd": (1_769.735e6, _J30, "corz_q2", "plus $781.7M restricted"),
        "debt_usd": (4_297.967e6, _J30, "corz_q2", "long-term debt, carrying value"),
        "converts_principal_usd": (1.085e9, _J30, "corz_10q", ""),
    }},
    "KEEL": {"name": "Keel Infrastructure (ex-Bitfarms)", "cik": "0001812477", "fields": {
        "btc_held": (1_861, date(2026, 8, 7), "keel_q2", "winding down the Bitcoin position during 2026"),
        "cash_usd": (698e6, date(2026, 8, 7), "keel_q2", "approx. unrestricted cash"),
        "converts_principal_usd": (458e6, _J30, "keel_q2", "raised via a convertible note offering in Q2 2026"),
    }},
    "BTDR": {"name": "Bitdeer", "cik": None, "fields": {
        "btc_held": (47, date(2026, 9, 30), "btdr_sep", "zero-treasury policy: sells weekly; includes pledged BTC"),
    }, "notes": "Foreign private issuer (20-F/6-K); quarterly balance sheet not loaded here."},
    "BTBT": {"name": "Bit Digital", "cik": "0001710350", "fields": {
        "cash_usd": (83.6e6, _J30, "btbt_10q", "incl. $56.1M at majority-owned WhiteFiber"),
    }, "notes": "Treasury is mainly ETH (~164,310 ETH at Jun 30 2026); bitcoin mining being wound down → BTC held N/A."},
    "MSTR": {"name": "Strategy", "cik": "0001050446", "fields": {
        "btc_held": (848_517, date(2026, 10, 18), "mstr_8k", "average cost $75,446/BTC"),
    }, "notes": "Not a miner: cost to mine N/A. Debt/preferred stack not loaded here (see filings)."},
    "APLD": {"name": "Applied Digital", "cik": None, "fields": {}},
}

# AI/HPC contracts come from the cited peer table (one source of truth with the Verdict's peer valuation)
for _t, _p in AI_PEERS.items():
    _c = COMPANIES.setdefault(_t, {"name": _t, "cik": None, "fields": {}})
    _c["fields"].setdefault("ai_contracted_mw", (_p["mw"], _p["as_of"], f"ai_{_t}", _p.get("kind", "")))
    _c["fields"].setdefault("ai_contract_value_usd", (_p["contract_usd"], _p["as_of"], f"ai_{_t}", ""))
    SOURCES[f"ai_{_t}"] = ("AI/HPC contract tracker", _p["source"])


def alias(ticker: str) -> str:
    return {"BITF": "KEEL"}.get((ticker or "").upper(), (ticker or "").upper())


def get(ticker: str, field: str) -> Optional[dict]:
    """{'value','as_of','source','url','note'} or None (→ N/A)."""
    c = COMPANIES.get(alias(ticker))
    v = c and c["fields"].get(field)
    if not v:
        return None
    lab, url = SOURCES.get(v[2], (v[2], None))
    return {"value": v[0], "as_of": v[1], "source": lab, "url": url, "note": v[3]}


def value(ticker: str, field: str):
    f = get(ticker, field)
    return None if f is None else f["value"]


def coverage(ticker: str) -> str:
    c = COMPANIES.get(alias(ticker))
    if not c:
        return "none"
    n = sum(1 for k in CORE if k in c["fields"])
    return "full" if n == len(CORE) else "partial" if n else "none"


def cik(ticker: str) -> Optional[str]:
    c = COMPANIES.get(alias(ticker))
    return c.get("cik") if c else None


def cash_debt(ticker: str, yahoo_balance: Optional[dict] = None) -> dict:
    """Cash and debt with provenance: the cited filing figure if on file, else Yahoo's balance sheet, else None."""
    bal = yahoo_balance or {}
    out = {}
    for field, ykey in (("cash_usd", "cash"), ("debt_usd", "total_debt")):
        f = get(ticker, field)
        if f:
            out[field] = (f["value"], f"filing {f['as_of']:%b %d %Y}")
        elif bal.get(ykey) is not None:
            out[field] = (bal[ykey], f"Yahoo balance sheet {bal.get('date', '')}".strip())
        else:
            out[field] = (None, "N/A")
    return out


def sop_inputs(ticker: str, yahoo_balance: Optional[dict] = None) -> dict:
    """Default sum-of-parts inputs for any ticker.  Undisclosed items are 0 and listed in `missing`."""
    cd = cash_debt(ticker, yahoo_balance)
    t = alias(ticker)
    d = {"btc_held": value(t, "btc_held"), "btc_pledged": value(t, "btc_pledged") or 0,
         "cash": cd["cash_usd"][0], "debt": cd["debt_usd"][0],
         "cash_src": cd["cash_usd"][1], "debt_src": cd["debt_usd"][1],
         "lease_noi": 0.0, "lease_years": 15, "lease_start": 0.0, "lease_disclosed": False}
    if t == "RIOT":
        yrs = max(0.0, (_RIOT["lease_191mw_full"] - date.today()).days / 365.25)
        d.update(lease_noi=(_RIOT["lease_191mw_noi_low"] + _RIOT["lease_191mw_noi_high"]) / 2,
                 lease_years=_RIOT["lease_191mw_term_years"], lease_start=round(yrs, 1), lease_disclosed=True)
    d["missing"] = [lab for k, lab in (("btc_held", "bitcoin held"), ("cash", "cash"), ("debt", "debt")) if d[k] is None]
    if value(t, "ai_contracted_mw") and not d["lease_disclosed"]:
        d["missing"].append("AI-lease operating income (contracts exist but NOI not disclosed)")
    return d


def miner_cost(ticker: str) -> Optional[dict]:
    ex, incl = get(ticker, "cost_to_mine_ex_da"), get(ticker, "cost_to_mine_incl_da")
    if not (ex and incl):
        return None
    return {"ex_da": ex["value"], "incl_da": incl["value"], "as_of": ex["as_of"], "source": ex["source"], "url": ex["url"]}


def facts_table(ticker: str):
    """Rows for a per-company facts table (every field, N/A where not on file)."""
    rows = []
    for k, (lab, unit) in FIELDS.items():
        f = get(ticker, k)
        if f is None:
            rows.append({"Fact": lab, "Value": "N/A", "As of": "—", "Source": "not disclosed / not verified"})
            continue
        v = f["value"]
        txt = (f"{v:,.0f} BTC" if unit == "BTC" else f"{v:,.0f} MW" if unit == "MW" else
               f"${v/1e9:,.2f}B" if v >= 1e9 else f"${v/1e6:,.1f}M" if v >= 1e6 else f"${v:,.0f}")
        rows.append({"Fact": lab, "Value": txt + (f" ({f['note']})" if f["note"] else ""),
                     "As of": f"{f['as_of']:%b %d %Y}", "Source": f["url"] or f["source"]})
    return rows
