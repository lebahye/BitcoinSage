# Schwab API Setup Guide

BitcoinSage supports real-time market data via the Charles Schwab API.
Without it the app falls back to Yahoo Finance (15-minute delayed data).

---

## Canonical Auth Scripts

| File | Purpose | When to use |
|------|---------|-------------|
| `schwab_manual_auth.py` | **CLI setup** — generates `schwab_token.json` interactively | First-time setup on local machine or SSH |
| `schwab_oauth_page.py` | **Streamlit UI** — browser-based OAuth flow | Replit / cloud environments |

All other auth scripts in this repo have been consolidated into the two above.

---

## Quick Start (Replit)

### Step 1 — Set environment variables

In Replit Secrets, add:

```
SCHWAB_APP_KEY     = your_app_key_from_developer_portal
SCHWAB_APP_SECRET  = your_app_secret_from_developer_portal
SCHWAB_CALLBACK_URL = https://127.0.0.1:8182
```

### Step 2 — Run the OAuth page

```bash
streamlit run schwab_oauth_page.py
```

Follow the on-screen steps:
1. Click **Open Schwab Authorization** — log in with your **brokerage** account (not dev portal)
2. After redirect, copy the full URL from your browser
3. Paste it into the text box and click **Complete OAuth**
4. `schwab_token.json` is created — you're done

### Step 3 — Verify

```bash
python schwab_manual_auth.py
```

You should see `✅ Connection test successful!` with a live AAPL quote.

---

## Token Refresh

Schwab access tokens expire after ~30 minutes.
`SchwabDataFetcher` in `utils/unified_data_fetcher.py` handles automatic refresh
via the `schwab-py` library as long as `schwab_token.json` is present.

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `Token file not found` | Run `schwab_oauth_page.py` to generate it |
| `401 Unauthorized` | Re-run OAuth — token may have expired permanently |
| `Callback URL mismatch` | Ensure Replit secret matches app registered URL |
| App still using Yahoo Finance | Check `SCHWAB_APP_KEY` / `SCHWAB_APP_SECRET` are set |

---

## Developer Portal

https://developer.schwab.com — register your app and get credentials.
Callback URL to register: `https://127.0.0.1:8182`
