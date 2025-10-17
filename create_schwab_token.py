#!/usr/bin/env python3
"""
Create Schwab token using schwab-py library format
"""

import sys
import os
import json
from schwab import auth
import httpx

API_KEY = os.environ.get('SCHWAB_APP_KEY')
APP_SECRET = os.environ.get('SCHWAB_APP_SECRET')
CALLBACK_URL = 'https://127.0.0.1:8182'
TOKEN_PATH = './schwab_token.json'

def exchange_code_for_token_schwabpy_format(auth_code):
    """Exchange authorization code for token using schwab-py internal methods"""
    import base64
    from schwab.auth import _token_from_response
    
    # Prepare credentials
    credentials = f"{API_KEY}:{APP_SECRET}"
    base64_creds = base64.b64encode(credentials.encode()).decode()
    
    # Token endpoint
    token_url = "https://api.schwabapi.com/v1/oauth/token"
    
    headers = {
        "Authorization": f"Basic {base64_creds}",
        "Content-Type": "application/x-www-form-urlencoded"
    }
    
    data = {
        "grant_type": "authorization_code",
        "code": auth_code,
        "redirect_uri": CALLBACK_URL
    }
    
    # Use httpx (same as schwab-py uses)
    with httpx.Client() as client:
        response = client.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        token_data = response.json()
        
        # Add timestamp for schwab-py compatibility
        import time
        token_data['creation_timestamp'] = int(time.time())
        
        return token_data
    else:
        raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")

def main():
    if len(sys.argv) < 2:
        print("Usage: python create_schwab_token.py 'REDIRECT_URL'")
        return 1
    
    redirect_url = sys.argv[1]
    
    # Extract code
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    auth_code = params.get('code', [None])[0]
    
    if not auth_code:
        print("❌ Could not extract authorization code")
        return 1
    
    print(f"📋 Authorization code: {auth_code[:30]}...")
    print("🔄 Exchanging for token...")
    
    try:
        token_data = exchange_code_for_token_schwabpy_format(auth_code)
        
        # Save token
        with open(TOKEN_PATH, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"✅ Token saved to: {TOKEN_PATH}")
        
        # Verify it works
        print("\n🧪 Testing token...")
        client = auth.client_from_token_file(TOKEN_PATH, API_KEY, APP_SECRET)
        resp = client.get_quote('AAPL')
        
        if resp.status_code == 200:
            data = resp.json()
            price = data['AAPL'].get('quote', {}).get('lastPrice', 'N/A')
            print(f"✅ Test successful! AAPL: ${price}")
            print("\n🎉 Schwab API is now working with real-time data!")
        else:
            print(f"⚠️ Test returned status: {resp.status_code}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
