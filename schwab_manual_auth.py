#!/usr/bin/env python3
"""
Schwab API Manual OAuth Token Generator
This works in cloud environments (Replit) without opening a browser
"""

from schwab import auth
import os

# Your Schwab API credentials from environment
API_KEY = os.environ.get('SCHWAB_APP_KEY', 'fnB6k1X6JSFlQHravRt6T9m86AZlkD04')
APP_SECRET = os.environ.get('SCHWAB_APP_SECRET', '23a9fLgi45m0dhHc')
CALLBACK_URL = os.environ.get('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')
TOKEN_PATH = './schwab_token.json'

def main():
    print("=" * 70)
    print("SCHWAB API MANUAL OAUTH SETUP (Cloud-Friendly)")
    print("=" * 70)
    print("\nThis manual flow allows authentication without opening a browser.")
    print("You'll copy-paste URLs to complete the OAuth process.")
    print("\n" + "=" * 70)
    
    try:
        print("\n🔐 Starting manual OAuth flow...")
        print("\nIMPORTANT: Use your SCHWAB BROKERAGE account credentials")
        print("(NOT your developer portal login)\n")
        
        # This will guide you through manual OAuth
        client = auth.client_from_manual_flow(
            api_key=API_KEY,
            app_secret=APP_SECRET,
            callback_url=CALLBACK_URL,
            token_path=TOKEN_PATH
        )
        
        print("\n" + "=" * 70)
        print("✅ SUCCESS! Token created successfully!")
        print(f"📁 Token file created: {TOKEN_PATH}")
        print("=" * 70)
        
        # Test the connection
        print("\n🧪 Testing connection...")
        resp = client.get_quote('AAPL')
        if resp.status_code == 200:
            print("✅ Connection test successful!")
            data = resp.json()
            if 'AAPL' in data:
                quote = data['AAPL'].get('quote', {})
                price = quote.get('lastPrice', 'N/A')
                print(f"   AAPL current price: ${price}")
        else:
            print(f"⚠️ Connection test returned status: {resp.status_code}")
        
        print("\n" + "=" * 70)
        print("🎉 Setup complete! Your app will now use real-time Schwab data.")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Error during OAuth setup: {str(e)}")
        print("\nTroubleshooting:")
        print("- Make sure callback URL matches: https://127.0.0.1:8182")
        print("- Use your brokerage account credentials (not developer account)")
        print("- Check that your app is 'Ready For Use' in Schwab Developer Portal")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
