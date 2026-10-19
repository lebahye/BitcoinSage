"""Upcoming market events that matter to a bitcoin-miner holder.

- Earnings dates: Yahoo Finance `Ticker.calendar` (often an *estimate* until the company confirms).
- FOMC meetings: hardcoded from the Federal Reserve's published schedule (decision = 2nd day).
- CPI releases: hardcoded from the BLS release schedule.
- Next Bitcoin halving: block-height based (every 210,000 blocks), from the live block height.
Hardcoded schedules carry their source URL and the date they were last checked; update yearly.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Iterable, List, Optional

FOMC_SOURCE = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
CPI_SOURCE = "https://www.bls.gov/schedule/news_release/cpi.htm"
SCHEDULES_LAST_VERIFIED = date(2026, 10, 19)

# (first day, decision day, has Summary of Economic Projections)
FOMC_MEETINGS = [
    ("2026-01-27", "2026-01-28", False), ("2026-03-17", "2026-03-18", True),
    ("2026-04-28", "2026-04-29", False), ("2026-06-16", "2026-06-17", True),
    ("2026-07-28", "2026-07-29", False), ("2026-09-15", "2026-09-16", True),
    ("2026-10-27", "2026-10-28", False), ("2026-12-08", "2026-12-09", True),
    ("2027-01-26", "2027-01-27", False), ("2027-03-16", "2027-03-17", True),
    ("2027-04-27", "2027-04-28", False), ("2027-06-08", "2027-06-09", True),
    ("2027-07-27", "2027-07-28", False), ("2027-09-14", "2027-09-15", True),
    ("2027-10-26", "2027-10-27", False), ("2027-12-07", "2027-12-08", True),
]

# (reference month, release date) — 08:30 ET
CPI_RELEASES = [
    ("October 2026", "2026-11-10"), ("November 2026", "2026-12-10"), ("December 2026", "2027-01-13"),
    ("January 2027", "2027-02-11"), ("February 2027", "2027-03-10"), ("March 2027", "2027-04-13"),
    ("April 2027", "2027-05-12"), ("May 2027", "2027-06-10"), ("June 2027", "2027-07-14"),
    ("July 2027", "2027-08-11"), ("August 2027", "2027-09-14"), ("September 2027", "2027-10-14"),
    ("October 2027", "2027-11-10"), ("November 2027", "2027-12-10"),
]

HALVING_INTERVAL = 210_000
TARGET_BLOCK_SECONDS = 600
FLAG_DAYS = 14


@dataclass
class Event:
    when: date
    kind: str          # Earnings | FOMC | CPI | Halving
    title: str
    detail: str = ""
    source: str = ""
    estimated: bool = False

    def days_away(self, today: date) -> int:
        return (self.when - today).days


def _d(s: str) -> date:
    return date.fromisoformat(s)


def fomc_events(today: date) -> List[Event]:
    out = []
    for start, end, sep in FOMC_MEETINGS:
        if _d(end) >= today:
            out.append(Event(_d(end), "FOMC", "Fed rate decision (FOMC)",
                             f"Meeting {start[5:]}–{end[5:]}; statement 2:00 pm ET" + (", with new economic projections" if sep else ""),
                             FOMC_SOURCE, estimated=False))
    return out


def cpi_events(today: date) -> List[Event]:
    return [Event(_d(d), "CPI", f"CPI inflation report ({m})", "08:30 am ET", CPI_SOURCE)
            for m, d in CPI_RELEASES if _d(d) >= today]


def halving_estimate(height: int, now: Optional[datetime] = None, block_seconds: float = TARGET_BLOCK_SECONDS) -> dict:
    now = now or datetime.now(timezone.utc)
    next_h = (height // HALVING_INTERVAL + 1) * HALVING_INTERVAL
    blocks_left = next_h - height
    eta = now + timedelta(seconds=blocks_left * block_seconds)
    return {"height": height, "halving_height": next_h, "blocks_left": blocks_left, "eta": eta.date(),
            "epoch": next_h // HALVING_INTERVAL, "reward_after": 50 / 2 ** (next_h // HALVING_INTERVAL)}


def halving_event(height: Optional[int], today: date) -> Optional[Event]:
    if not height:
        return None
    h = halving_estimate(height, datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc))
    return Event(h["eta"], "Halving", "Next Bitcoin halving (estimate)",
                 f"Block {h['halving_height']:,} — {h['blocks_left']:,} blocks to go from {height:,}; "
                 f"reward drops to {h['reward_after']:g} BTC/block. Date assumes 10-minute blocks (± several weeks).",
                 "live block height (blockchain.info / mempool.space)", estimated=True)


def earnings_events(cal: dict, today: date) -> List[Event]:
    """cal = {symbol: [date, ...]} from Yahoo. Past dates dropped. Ranges → first date, flagged estimate."""
    out = []
    for sym, dates in cal.items():
        ds = sorted(d for d in (dates or []) if isinstance(d, date) and d >= today)
        if not ds:
            continue
        rng = len(dates or []) > 1
        out.append(Event(ds[0], "Earnings", f"{sym} earnings",
                         ("Window " + " – ".join(x.isoformat() for x in sorted(dates)) if rng else "Date per Yahoo Finance")
                         + " · confirm on the company's investor-relations site", "Yahoo Finance calendar", estimated=True))
    return out


def build_calendar(today: date, earnings_cal: dict, block_height: Optional[int], horizon_days: int = 120) -> List[Event]:
    ev = earnings_events(earnings_cal, today) + fomc_events(today) + cpi_events(today)
    ev = [e for e in ev if e.days_away(today) <= horizon_days]
    h = halving_event(block_height, today)
    if h:
        ev.append(h)  # always shown, even if far away
    return sorted(ev, key=lambda e: e.when)


def flagged(events: Iterable[Event], today: date, days: int = FLAG_DAYS) -> List[Event]:
    return [e for e in events if 0 <= e.days_away(today) <= days]


# ── live fetchers (network) ────────────────────────────────────────────────
def fetch_block_height() -> Optional[int]:
    import requests
    for url in ("https://blockchain.info/q/getblockcount", "https://mempool.space/api/blocks/tip/height"):
        try:
            r = requests.get(url, timeout=8)
            if r.ok and r.text.strip().isdigit():
                return int(r.text.strip())
        except Exception:
            continue
    return None


def fetch_earnings(symbols: Iterable[str]) -> dict:
    import yfinance as yf
    out = {}
    for s in symbols:
        try:
            c = yf.Ticker(s).calendar
            ds = c.get("Earnings Date") if isinstance(c, dict) else None
            out[s] = [d.date() if isinstance(d, datetime) else d for d in (ds or [])]
        except Exception:
            out[s] = []
    return out
