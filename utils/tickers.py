"""
utils/tickers.py — single source of truth for symbols, names and renames.

If a company changes its ticker, add it to TICKER_ALIASES; saved positions,
targets and lists that still use the old symbol are mapped automatically.
"""

from typing import Dict, Iterable, List

# Old symbol -> current symbol
TICKER_ALIASES: Dict[str, str] = {
    "BITF": "KEEL",   # Bitfarms -> Keel Infrastructure (Nasdaq: KEEL, April 2026)
}

# Sidebar universe (symbol -> display name)
MINING_STOCKS: Dict[str, str] = {
    "MARA": "MARA Holdings (Marathon)",
    "RIOT": "Riot Platforms Inc",
    "CLSK": "CleanSpark Inc",
    "HUT":  "Hut 8 Corp",
    "KEEL": "Keel Infrastructure (ex-Bitfarms)",
    "BTBT": "Bit Digital Inc",
    "CIFR": "Cipher Mining Inc",
    "CORZ": "Core Scientific Inc",
    "IREN": "IREN Ltd (Iris Energy)",
    "WULF": "TeraWulf Inc",
}

# The 9-stock watchlist used by Trade Signals and AI Predictions
WATCHLIST: List[str] = ["RIOT", "MARA", "CLSK", "HUT", "IREN", "KEEL", "BTBT", "WULF", "CIFR"]

# Peer universe for the RIOT Correlation Map: symbol -> (group, description)
CORRELATION_UNIVERSE: Dict[str, tuple] = {
    # Bitcoin miners (many now also host AI / HPC)
    "CLSK": ("Miners", "CleanSpark — US bitcoin miner"),
    "MARA": ("Miners", "MARA — largest US miner, big BTC holder"),
    "HUT":  ("Miners", "Hut 8 — mining + AI compute"),
    "KEEL": ("Miners", "Keel (ex-Bitfarms) — moving to AI hosting"),
    "CIFR": ("Miners", "Cipher — Texas miner with AI leases"),
    "BTBT": ("Miners", "Bit Digital — miner with AI compute arm"),
    "CORZ": ("Miners", "Core Scientific — AI hosting for CoreWeave"),
    "HIVE": ("Miners", "HIVE — miner + GPU cloud"),
    "WULF": ("Miners", "TeraWulf — low-carbon miner, AI leases"),
    "IREN": ("Miners", "IREN — miner turned AI cloud"),
    "BTDR": ("Miners", "Bitdeer — rig maker + miner"),
    # AI data-center / compute
    "APLD": ("AI data centers", "Applied Digital — AI data-center developer"),
    "GLXY": ("AI data centers", "Galaxy Digital — crypto + AI campus"),
    "CRWV": ("AI data centers", "CoreWeave — AI cloud"),
    "NBIS": ("AI data centers", "Nebius — AI cloud"),
    "VRT":  ("AI data centers", "Vertiv — data-center power/cooling"),
    "NVDA": ("AI data centers", "NVIDIA — AI chips"),
    # Bitcoin itself
    "BTC-USD": ("Bitcoin", "Bitcoin spot price"),
    "IBIT":    ("Bitcoin", "iShares spot Bitcoin ETF"),
    "MSTR":    ("Bitcoin", "Strategy (MicroStrategy) — BTC treasury"),
    # Broad risk appetite
    "ARKK": ("Risk appetite", "ARK Innovation ETF — speculative growth"),
    "IWM":  ("Risk appetite", "Russell 2000 — small caps"),
    "QQQ":  ("Risk appetite", "Nasdaq-100"),
    # Macro / potential hedges (inverse panel)
    "^VIX": ("Macro", "VIX — stock-market fear gauge"),
    "UUP":  ("Macro", "US dollar (ETF)"),
    "USO":  ("Macro", "Oil (ETF)"),
    "TLT":  ("Macro", "Long-term US Treasury bonds (ETF)"),
}

INVERSE_PANEL = ["^VIX", "UUP", "USO", "TLT"]


def resolve(symbol: str) -> str:
    """Map an old/renamed ticker to its current symbol (case-insensitive)."""
    s = (symbol or "").strip().upper()
    return TICKER_ALIASES.get(s, s)


def resolve_all(symbols: Iterable[str]) -> List[str]:
    out: List[str] = []
    for s in symbols:
        r = resolve(s)
        if r and r not in out:
            out.append(r)
    return out


def resolve_keys(d: dict) -> dict:
    """Return a copy of a {symbol: value} dict with renamed tickers mapped.
    If both old and new symbols exist, the current symbol's entry wins."""
    out = {}
    for k, v in d.items():
        r = resolve(k)
        if r in out and r == k:
            out[r] = v
        elif r not in out:
            out[r] = v
    return out
