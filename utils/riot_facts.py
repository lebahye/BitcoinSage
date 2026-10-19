"""utils/riot_facts.py — dated, cited facts from Riot Platforms' own filings / releases.

Only numbers the company reported are stored here, each with its source URL and date.  Anything the company has
NOT disclosed (e.g. the cost to build the AI data centre) is deliberately absent; the UI makes it an editable input.
Update after each quarterly report.
"""
from __future__ import annotations

from datetime import date

Q2_2026 = {
    "period_end": date(2026, 6, 30),
    "published": date(2026, 8, 10),
    "url": "https://www.riotplatforms.com/riot-platforms-reports-second-quarter-2026-financial-results-and-strategic-highlights/",
    "label": "Riot Q2 2026 results press release",
    "btc_held": 11_380,                 # of which pledged as collateral:
    "btc_pledged": 5_821,
    "cash_usd": 548.9e6,                # of which restricted:
    "cash_restricted_usd": 77.5e6,
    "cost_to_mine_ex_da": 49_912,       # $/BTC, excluding miner depreciation
    "cost_to_mine_incl_da": 90_631,     # $/BTC, including miner depreciation
    "production_value_per_btc": 71_667,
    "btc_mined_q": 1_587,
    "lease_191mw_noi_low": 365e6,       # estimated average annual NOI, frontier-AI-lab lease (Rockdale)
    "lease_191mw_noi_high": 411e6,
    "lease_191mw_term_years": 20,       # initial term through June 2048
    "lease_191mw_first_mw": "96 MW expected Dec 2027",
    "lease_191mw_full": date(2028, 6, 30),   # full 191 MW deployment expected by June 2028
    "lease_total_contracted_usd": 9.8e9,     # AMD + AI lab, total contract revenue
    "interim_facility_usd": 573e6,           # Morgan Stanley interim financing for the build
}
FACT_SOURCES = {
    "q2_2026": {"label": Q2_2026["label"], "url": Q2_2026["url"], "date": "2026-08-10"},
    "corsicana_8k": {"label": "Riot 8-K: Corsicana site under a NON-BINDING letter of intent (terms undisclosed)",
                     "url": "https://www.sec.gov/Archives/edgar/data/1167419/000110465926093406/riot-20260810x8k.htm",
                     "date": "2026-08-10"},
}
RIOT_CIK = "0001167419"
