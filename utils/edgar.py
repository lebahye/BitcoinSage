"""utils/edgar.py — OPTIONAL check of a company's recent SEC filings that can signal new shares being sold
(prospectus supplements 424B*, shelf registrations S-3/S-3ASR, and 8-Ks).

Free, no key.  The SEC asks automated clients to send a descriptive User-Agent with a contact address
(https://www.sec.gov/os/accessing-edgar-data); some hosting networks are still blocked (HTTP 403).
Every failure returns {"available": False, "reason": ...} so the UI simply says it couldn't check.
"""
from __future__ import annotations

from typing import Optional

try:
    import streamlit as st
    _cache6h = st.cache_data(ttl=21600, show_spinner=False)
except Exception:  # pragma: no cover
    def _cache6h(fn):
        return fn

USER_AGENT = "BitcoinSage research dashboard (contact: lebahye@users.noreply.github.com)"
OFFERING_FORMS = {"424B5": "prospectus supplement (often an at-the-market share sale)",
                  "424B3": "prospectus", "424B7": "prospectus supplement (resale)",
                  "S-3": "shelf registration (lets the company sell shares later)",
                  "S-3ASR": "automatic shelf registration (lets the company sell shares later)",
                  "S-8": "shares for employee pay plans"}


class _Blocked(Exception):
    pass


@_cache6h
def _submissions_cached(cik10: str) -> dict:
    import requests
    r = requests.get(f"https://data.sec.gov/submissions/CIK{cik10}.json", timeout=10,
                     headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip, deflate"})
    if r.status_code != 200:
        raise _Blocked(f"HTTP {r.status_code}")
    return r.json()


def parse_offering_filings(sub: dict, limit: int = 12) -> list:
    rec = (sub or {}).get("filings", {}).get("recent", {})
    forms, dates = rec.get("form", []), rec.get("filingDate", [])
    accs, docs = rec.get("accessionNumber", []), rec.get("primaryDocument", [])
    cik = str(int(sub.get("cik", 0))) if sub.get("cik") else None
    out = []
    for i, f in enumerate(forms):
        if f in OFFERING_FORMS:
            url = None
            if cik and i < len(accs) and i < len(docs):
                url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accs[i].replace('-', '')}/{docs[i]}"
            out.append({"form": f, "date": dates[i] if i < len(dates) else None,
                        "what": OFFERING_FORMS[f], "url": url})
        if len(out) >= limit:
            break
    return out


def offering_filings(cik10: Optional[str], limit: int = 12) -> dict:
    if not cik10:
        return {"available": False, "reason": "no SEC company number (CIK) on file for this stock"}
    try:
        sub = _submissions_cached(cik10)
    except Exception as e:
        return {"available": False, "reason": f"SEC EDGAR not reachable from this server ({type(e).__name__}: {e})"}
    return {"available": True, "filings": parse_offering_filings(sub, limit), "name": sub.get("name")}
