#!/usr/bin/env python3
"""Generate Schwab OAuth Authorization URL"""

import os
from urllib.parse import urlencode
import secrets

API_KEY = os.environ.get('SCHWAB_APP_KEY', 'fnB6k1X6JSFlQHravRt6T9m86AZlkD04')
CALLBACK_URL = 'https://127.0.0.1:8182'

# Generate random state for security
state = secrets.token_urlsafe(22)

params = {
    'response_type': 'code',
    'client_id': API_KEY,
    'redirect_uri': CALLBACK_URL,
    'state': state
}

auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?{urlencode(params)}"

print("\n" + "=" * 70)
print("SCHWAB OAUTH AUTHORIZATION URL")
print("=" * 70)
print("\n1. Copy this URL and paste it in your browser:")
print("\n" + auth_url)
print("\n2. Login with your SCHWAB BROKERAGE account")
print("3. Click 'Allow' when asked")
print("4. IMMEDIATELY copy the full redirect URL from your browser")
print("5. Run: python complete_oauth.py 'PASTE_URL_HERE'")
print("\n⚠️  IMPORTANT: Do this quickly - codes expire in minutes!")
print("=" * 70 + "\n")
