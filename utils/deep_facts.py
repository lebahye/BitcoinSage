"""utils/deep_facts.py — dated, cited company facts for the ⚖️ Stock Verdict "Deeper evidence" section.

Rules: every number has a source URL and an as-of date; nothing is estimated here.  Where a figure is derived
from two cited numbers the derivation is written out.  Anything not disclosed is simply absent (the UI shows N/A
or lets the user enter a value).  Last verified: 2026-10-19.  Refresh after each quarterly report.
"""
from __future__ import annotations

from datetime import date

LAST_VERIFIED = date(2026, 10, 19)

_RIOT_10Q_Q2 = "https://www.sec.gov/Archives/edgar/data/1167419/000110465926093448/riot-20260630x10q.htm"
_RIOT_8K_NOTES = "https://www.sec.gov/Archives/edgar/data/1167419/000110465924127656/tm2430044d5_8k.htm"

# ── 3. Convertible debt, warrants and other potential new shares ──────────
CONVERTS = {
    "RIOT": {
        "shares_outstanding": 375_258_935,
        "shares_as_of": date(2026, 8, 7),
        "shares_source": _RIOT_10Q_Q2,
        "notes": [{
            "name": "0.75% Convertible Senior Notes due 2030",
            "principal": 594.4e6,                 # 10-Q Note 11 (incl. initial purchasers' option)
            "conversion_price": 14.86,            # 67.2767 shares per $1,000 (8-K, Dec 11 2024)
            "conversion_rate_per_1000": 67.2767,
            "shares_if_converted": 39_988_127,    # 10-Q Note 17 (anti-dilutive securities table)
            "maturity": date(2030, 1, 15),
            "issuer_call_from": date(2028, 1, 20),   # if VWAP ≥130% of conversion price for 20 of 30 days
            "free_conversion_from": date(2029, 7, 15),
            "settlement": "cash, shares or both at Riot's election; 10-Q says Riot intends to settle in shares",
            "status_note": "Holder-convertible during Q3 2026: the stock closed above 130% of the conversion "
                           "price on 20 of the 30 trading days to Jun 30 2026 (10-Q).",
            "as_of": date(2026, 6, 30),
            "sources": [_RIOT_10Q_Q2, _RIOT_8K_NOTES],
        }],
        "other": [
            {"name": "Warrants", "shares": 63_000, "as_of": date(2026, 6, 30), "source": _RIOT_10Q_Q2},
            {"name": "Unvested RSUs (not yet in the share count)", "shares": 2_171_155, "as_of": date(2026, 6, 30),
             "source": _RIOT_10Q_Q2},
            {"name": "Equity plan shares reserved for future awards", "shares": 19_709_910, "as_of": date(2026, 6, 30),
             "source": _RIOT_10Q_Q2},
        ],
        "atm_capacity_usd": 500e6,          # 2025 ATM program, unused at Jun 30 2026 (10-Q Note 13)
        "atm_as_of": date(2026, 6, 30),
        "atm_source": _RIOT_10Q_Q2,
    },
}

# ── 2. Miner treasury flows (BTC produced vs sold vs held), per reported period ──
# Riot, MARA and CleanSpark moved to QUARTERLY production reports in 2026 (CleanSpark's last monthly was June 2026).
TREASURY = {
    "RIOT": [
        {"period": "Q1 2026", "end": date(2026, 3, 31), "produced": 1_473, "sold": 3_778, "held": 15_679,
         "note": "Sold for $289.5M net proceeds.",
         "source": "https://www.riotplatforms.com/riot-announces-first-quarter-2026-production-and-operations-updates/"},
        {"period": "Q2 2026", "end": date(2026, 6, 30), "produced": 1_587, "sold": 5_887, "held": 11_380,
         "note": "Sold = 10-Q six-month sales 9,665 − Q1 3,778. Produced = six-month 3,060 − Q1 1,473. "
                 "5,821 BTC were pledged for a $200M Coinbase loan (repaid Sep 21 2026 per an 8-K reported by BlockWest).",
         "source": _RIOT_10Q_Q2},
    ],
    "MARA": [
        {"period": "Q2 2026", "end": date(2026, 6, 30), "produced": 2_422, "sold": 2_213, "held": 35_577,
         "note": "Held includes 9,270 BTC loaned or pledged.",
         "source": "https://www.sec.gov/Archives/edgar/data/1507605/000150760526000020/q226shareholderletter.htm"},
    ],
    "CLSK": [
        {"period": "Jun 2026 (month)", "end": date(2026, 6, 30), "produced": 614, "sold": 429, "held": 13_924,
         "note": "Sold = 179 spot + 250 via call exercises; also bought 25 via puts and 244 in a basis trade. "
                 "Held includes 1,719 BTC posted as collateral/receivable. Monthly report as summarised by Blockspace.",
         "source": "https://blockspace.media/insight/cleanspark-bitcoin-production-holdings-june-2026/"},
    ],
}

# ── 4. AI/HPC peer valuation inputs (contracted critical-IT MW, contracted base-term revenue) ──
# Company totals as compiled from filings/releases by the cited trade-press tables (secondary sources — check the
# filings before relying on a single number).  Definitions differ by company (critical IT vs gross; leases vs
# GPU-cloud contracts); the table says which.  HPC revenue = latest reported quarter where cited, else not entered.
_SC = "https://www.supercomputing.news/ai/bitcoin-miners-didnt-bring-ai-compute-they-brought-grid-connected-megawatts"
_BW = "https://blockwest.co/research/bitcoin-miner-ai-hpc-hosting-tracker-2026/"
AI_PEERS = {
    "RIOT": {"mw": 241, "contract_usd": 9.8e9, "as_of": date(2026, 8, 10), "kind": "leases (AMD 50 + frontier AI lab 191)",
             "hpc_rev_q": 23.2e6, "hpc_rev_note": "Q2 2026 Data Center revenue; $18.3M of it is tenant fit-out "
             "reimbursement, $4.5M lease revenue (10-Q)", "source": _SC, "rev_source": _RIOT_10Q_Q2},
    "CORZ": {"mw": 1_119, "contract_usd": 24.0e9, "as_of": date(2026, 7, 27), "kind": "leases (CoreWeave, AMD, neocloud)",
             "hpc_rev_q": 136.7e6, "hpc_rev_note": "Q2 2026 colocation revenue",
             "source": _SC, "rev_source": "https://insights4.vc/blog/bitcoin-miners-pivot-to-ai-data-centers/"},
    "APLD": {"mw": 1_410, "contract_usd": 36.2e9, "as_of": date(2026, 6, 30), "kind": "leases (CoreWeave + 2 hyperscalers)",
             "hpc_rev_q": None, "source": _SC},
    "WULF": {"mw": 839, "contract_usd": 26.8e9, "as_of": date(2026, 8, 5), "kind": "leases (Core42, Fluidstack/Google, Anthropic)",
             "hpc_rev_q": None, "source": _SC, "contract_source": _BW},
    "CIFR": {"mw": 454, "contract_usd": 11.4e9, "as_of": date(2026, 8, 4), "kind": "leases (Fluidstack/Google, Amazon, AWS)",
             "hpc_rev_q": None, "source": _SC},
    "IREN": {"mw": 260, "contract_usd": 15.9e9, "as_of": date(2026, 8, 27), "kind": "GPU-cloud contracts (Microsoft, Nvidia, others) — not leases",
             "hpc_rev_q": None, "source": _BW},
    "HUT":  {"mw": 949, "contract_usd": 26.6e9, "as_of": date(2026, 8, 4), "kind": "leases (Fluidstack, investment-grade tenant)",
             "hpc_rev_q": None, "source": _SC},
    "CLSK": {"mw": 175, "contract_usd": 6.6e9, "as_of": date(2026, 7, 14), "kind": "lease (investment-grade tech company)",
             "hpc_rev_q": None, "source": _SC},
}
AI_PEER_SET = ("RIOT", "CORZ", "IREN", "APLD", "WULF", "CIFR", "HUT", "CLSK")
