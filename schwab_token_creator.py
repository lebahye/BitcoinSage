#!/usr/bin/env python3
"""
Create Schwab token using schwab-py's client_from_manual_flow
with programmatic input
"""

import sys
import os
from schwab import auth

API_KEY = os.environ.get('SCHWAB_APP_KEY')
APP_SECRET = os.environ.get('SCHWAB_APP_SECRET')
CALLBACK_URL = 'https://127.0.0.1:8182'
TOKEN_PATH = './schwab_token.json'

def create_token_from_redirect_url(redirect_url):
    """Create token using schwab-py by providing redirect URL programmatically"""
    
    # Monkey-patch input to provide the redirect URL automatically
    original_input = __builtins__.input
    
    def fake_input(prompt):
        if 'Redirect URL' in prompt or 'redirect' in prompt.lower():
            print(f"{prompt}")
            print(f"[Auto-provided]: {redirect_url}")
            return redirect_url
        return original_input(prompt)
    
    __builtins__.input = fake_input
    
    try:
        client = auth.client_from_manual_flow(
            api_key=API_KEY,
            app_secret=APP_SECRET,
            callback_url=CALLBACK_URL,
            token_path=TOKEN_PATH
        )
        
        print(f"\n✅ Token created successfully at: {TOKEN_PATH}")
        
        # Test it
        print("\n🧪 Testing token with real-time quote...")
        resp = client.get_quote('RIOT')
        if resp.status_code == 200:
            data = resp.json()
            quote = data['RIOT'].get('quote', {})
            price = quote.get('lastPrice', 'N/A')
            change = quote.get('netChange', 'N/A')
            print(f"✅ RIOT Price: ${price} (Change: ${change})")
            print("\n🎉 Schwab API working with real-time data!")
            return 0
        else:
            print(f"⚠️ Test returned status: {resp.status_code}")
            return 1
            
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        __builtins__.input = original_input

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python schwab_token_creator.py 'REDIRECT_URL'")
        sys.exit(1)
    
    redirect_url = sys.argv[1]
    sys.exit(create_token_from_redirect_url(redirect_url))
