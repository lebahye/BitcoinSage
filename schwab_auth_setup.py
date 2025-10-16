#!/usr/bin/env python3
"""
Schwab API OAuth Token Generator
Run this script on your LOCAL computer to generate authentication token
"""

from schwab import auth
import os

# Your Schwab API credentials
API_KEY = 'fnB6k1X6JSFlQHravRt6T9m86AZlkD04'
APP_SECRET = '23a9fLgi45m0dhHc'
CALLBACK_URL = 'https://127.0.0.1:8182'
TOKEN_PATH = './schwab_token.json'

def main():
    print("=" * 60)
    print("SCHWAB API OAUTH SETUP")
    print("=" * 60)
    print("\nThis script will:")
    print("1. Open your browser to Schwab login page")
    print("2. You'll login with your BROKERAGE account credentials")
    print("3. Select which accounts to authorize")
    print("4. Generate schwab_token.json file")
    print("\nIMPORTANT:")
    print("- Use your Schwab BROKERAGE login (not developer account)")
    print("- Browser will show security warning - click 'Advanced' then 'Proceed'")
    print("- Token expires after 7 days - you'll need to re-run this")
    print("\n" + "=" * 60)
    
    input("\nPress ENTER to start OAuth flow...")
    
    try:
        # This will open browser for OAuth login
        client = auth.easy_client(
            api_key=API_KEY,
            app_secret=APP_SECRET,
            callback_url=CALLBACK_URL,
            token_path=TOKEN_PATH
        )
        
        print("\n✅ SUCCESS! Token generated successfully!")
        print(f"\n📁 Token file created: {TOKEN_PATH}")
        print("\nNext steps:")
        print("1. Upload 'schwab_token.json' to your Replit project")
        print("2. Restart your Streamlit app")
        print("3. You'll see '✅ Using Schwab API (Real-time data)' in the app")
        
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
        
    except Exception as e:
        print(f"\n❌ Error during OAuth setup: {str(e)}")
        print("\nCommon issues:")
        print("- Make sure your app is 'Ready For Use' in Schwab Developer Portal")
        print("- Check callback URL matches exactly: https://127.0.0.1:8182")
        print("- Use your brokerage account credentials (not developer account)")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())
