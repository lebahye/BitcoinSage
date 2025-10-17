#!/usr/bin/env python3
"""
Complete Schwab OAuth with redirect URL
"""

import sys
import os
from schwab import auth
import requests

API_KEY = os.environ.get('SCHWAB_APP_KEY', 'fnB6k1X6JSFlQHravRt6T9m86AZlkD04')
APP_SECRET = os.environ.get('SCHWAB_APP_SECRET', '23a9fLgi45m0dhHc')
CALLBACK_URL = 'https://127.0.0.1:8182'
TOKEN_PATH = './schwab_token.json'

def extract_code_from_url(redirect_url):
    """Extract authorization code from redirect URL"""
    from urllib.parse import urlparse, parse_qs
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)
    return params.get('code', [None])[0]

def exchange_code_for_token(auth_code):
    """Exchange authorization code for access token"""
    import base64
    
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
    
    response = requests.post(token_url, headers=headers, data=data)
    
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Token exchange failed: {response.status_code} - {response.text}")

def main():
    if len(sys.argv) < 2:
        print("❌ Error: Please provide the redirect URL")
        print("\nUsage:")
        print("  python complete_oauth.py 'https://127.0.0.1:8182?code=XXXXX&state=XXXXX'")
        return 1
    
    redirect_url = sys.argv[1]
    
    print("=" * 70)
    print("COMPLETING SCHWAB OAUTH AUTHENTICATION")
    print("=" * 70)
    
    # Extract code
    print("\n📋 Extracting authorization code...")
    auth_code = extract_code_from_url(redirect_url)
    
    if not auth_code:
        print("❌ Error: Could not extract authorization code from URL")
        print(f"URL provided: {redirect_url}")
        return 1
    
    print(f"✅ Authorization code extracted: {auth_code[:20]}...")
    
    # Exchange for token
    print("\n🔄 Exchanging code for access token...")
    try:
        token_data = exchange_code_for_token(auth_code)
        
        # Save token
        import json
        with open(TOKEN_PATH, 'w') as f:
            json.dump(token_data, f, indent=2)
        
        print(f"✅ Token saved to: {TOKEN_PATH}")
        print("\n" + "=" * 70)
        print("🎉 SUCCESS! Schwab API authentication complete!")
        print("=" * 70)
        print("\nYour app will now use real-time Schwab data.")
        print("Token expires in 7 days - re-run this process when needed.")
        
        return 0
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
