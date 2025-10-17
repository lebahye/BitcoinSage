#!/usr/bin/env python3
"""
Streamlit OAuth Helper for Schwab API
Run this to complete OAuth authentication in the browser
"""

import streamlit as st
import os
import requests
import base64
from urllib.parse import urlencode, parse_qs, urlparse
import secrets
import json

# Configuration
API_KEY = os.environ.get('SCHWAB_APP_KEY', 'fnB6k1X6JSFlQHravRt6T9m86AZlkD04')
APP_SECRET = os.environ.get('SCHWAB_APP_SECRET', '23a9fLgi45m0dhHc')
CALLBACK_URL = 'https://127.0.0.1:8182'
TOKEN_PATH = './schwab_token.json'

st.set_page_config(page_title="Schwab OAuth Setup", page_icon="🔐")

st.title("🔐 Schwab API OAuth Setup")
st.markdown("---")

# Step 1: Generate Authorization URL
if 'auth_state' not in st.session_state:
    st.session_state.auth_state = secrets.token_urlsafe(22)

params = {
    'response_type': 'code',
    'client_id': API_KEY,
    'redirect_uri': CALLBACK_URL,
    'state': st.session_state.auth_state
}
auth_url = f"https://api.schwabapi.com/v1/oauth/authorize?{urlencode(params)}"

st.subheader("Step 1: Authorize Your App")
st.markdown("""
1. Click the button below to open Schwab authorization
2. Login with your **SCHWAB BROKERAGE account** credentials
3. Click **"Allow"** when prompted
4. Copy the **FULL URL** from the browser address bar after redirect
5. Paste it in the box below
""")

st.link_button("🚀 Open Schwab Authorization", auth_url, use_container_width=True)

st.markdown("---")

# Step 2: Complete OAuth
st.subheader("Step 2: Complete Authentication")

redirect_url = st.text_input(
    "Paste the redirect URL here:",
    placeholder="https://127.0.0.1:8182/?code=XXXXX&state=XXXXX",
    key="redirect_url"
)

if st.button("✅ Complete OAuth", type="primary", use_container_width=True):
    if not redirect_url:
        st.error("Please paste the redirect URL first!")
    else:
        with st.spinner("Exchanging code for token..."):
            try:
                # Extract authorization code
                parsed = urlparse(redirect_url)
                params = parse_qs(parsed.query)
                auth_code = params.get('code', [None])[0]
                
                if not auth_code:
                    st.error("❌ Could not extract authorization code from URL")
                    st.stop()
                
                st.info(f"📋 Authorization code: {auth_code[:30]}...")
                
                # Exchange for token
                credentials = f"{API_KEY}:{APP_SECRET}"
                base64_creds = base64.b64encode(credentials.encode()).decode()
                
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
                    token_data = response.json()
                    
                    # Save token
                    with open(TOKEN_PATH, 'w') as f:
                        json.dump(token_data, f, indent=2)
                    
                    st.success("✅ SUCCESS! Token created successfully!")
                    st.success(f"📁 Token saved to: {TOKEN_PATH}")
                    st.balloons()
                    
                    st.markdown("---")
                    st.info("🎉 Your main app will now use real-time Schwab data!")
                    st.info("💡 Token expires in 7 days - re-run this setup when needed")
                    
                else:
                    error_data = response.json() if response.headers.get('content-type') == 'application/json' else response.text
                    st.error(f"❌ Token exchange failed: {response.status_code}")
                    st.error(f"Error: {error_data}")
                    
                    if "expired" in str(error_data).lower():
                        st.warning("⏱️ Authorization code expired. Please start over from Step 1.")
                    
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")

st.markdown("---")

# Check if token exists
if os.path.exists(TOKEN_PATH):
    st.success(f"✅ Token file exists: {TOKEN_PATH}")
    
    # Show token info (without revealing sensitive data)
    try:
        with open(TOKEN_PATH) as f:
            token_data = json.load(f)
        st.info(f"🕐 Token type: {token_data.get('token_type', 'N/A')}")
        st.info(f"⏳ Expires in: {token_data.get('expires_in', 'N/A')} seconds")
    except:
        pass
else:
    st.warning("⚠️ No token file found yet. Complete the steps above to create one.")
