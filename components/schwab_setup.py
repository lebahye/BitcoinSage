import streamlit as st
from utils.enhanced_data_fetcher import EnhancedDataFetcher

class SchwabSetup:
    """Component for setting up Schwab API integration"""
    
    def __init__(self):
        self.data_fetcher = None
    
    def render(self):
        """Render Schwab API setup interface"""
        st.title("🏦 Charles Schwab API Setup")
        st.markdown("### Get Real-Time Market Data Through Your Broker Account")
        
        # Initialize enhanced data fetcher
        if 'enhanced_data_fetcher' not in st.session_state:
            st.session_state.enhanced_data_fetcher = EnhancedDataFetcher()
        
        self.data_fetcher = st.session_state.enhanced_data_fetcher
        
        # Show current data source status
        self._show_data_source_status()
        
        # Setup wizard
        with st.expander("🚀 Setup Wizard", expanded=True):
            self._render_setup_wizard()
        
        # API credentials configuration
        if not self._is_schwab_configured():
            self._render_credentials_setup()
        else:
            self._render_authentication_flow()
    
    def _show_data_source_status(self):
        """Display current data source and quality"""
        status = self.data_fetcher.get_data_source_status()
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if status['is_realtime']:
                st.success("🟢 **REAL-TIME DATA**")
                st.markdown("✅ Charles Schwab API")
            else:
                st.error("🔴 **DELAYED DATA**") 
                st.markdown("⚠️ Yahoo Finance (16+ hour delay)")
        
        with col2:
            if status['last_update']:
                st.metric("Last Update", status['last_update'].strftime("%H:%M:%S"))
            else:
                st.metric("Last Update", "Never")
        
        with col3:
            if status['source'] == 'schwab' and status['token_expires']:
                import time
                minutes_left = max(0, (status['token_expires'] - time.time()) / 60)
                st.metric("Token Expires", f"{minutes_left:.0f} min")
            else:
                st.metric("API Status", "Not Connected")
    
    def _render_setup_wizard(self):
        """Step-by-step setup guide"""
        st.markdown("### 📋 Quick Setup (20 minutes)")
        
        # Step 1: Developer Account
        with st.container():
            st.markdown("#### Step 1: Create Schwab Developer Account")
            st.markdown("""
            1. Go to **https://developer.schwab.com**
            2. Click **"Get Started"** and create developer account
            3. **Important:** This is separate from your trading account
            4. Verify email and complete registration
            """)
            
            if st.button("🔗 Open Schwab Developer Portal", type="secondary"):
                st.markdown("**Next:** Register your application after creating account")
        
        # Step 2: App Registration  
        with st.container():
            st.markdown("#### Step 2: Register Your Application")
            st.info("""
            **Application Details:**
            - **App Name:** Personal Trading Dashboard
            - **Callback URL:** `https://127.0.0.1`
            - **API Products:** Select BOTH:
              - ✅ Market Data Production 
              - ✅ Accounts and Trading Production
            """)
            
            st.warning("⏱️ **Approval takes 2-5 days** (usually faster)")
        
        # Step 3: Get Credentials
        with st.container():
            st.markdown("#### Step 3: Get Your API Credentials") 
            st.markdown("""
            After approval, you'll receive:
            - **App Key** (Client ID)
            - **App Secret** (Client Secret) 
            
            Enter these below to configure your connection.
            """)
    
    def _render_credentials_setup(self):
        """API credentials configuration form"""
        st.subheader("🔑 API Credentials Setup")
        
        with st.form("schwab_credentials"):
            st.markdown("Enter your Schwab API credentials:")
            
            app_key = st.text_input(
                "App Key (Client ID)", 
                type="password",
                help="From your registered application in Schwab developer portal"
            )
            
            app_secret = st.text_input(
                "App Secret (Client Secret)",
                type="password", 
                help="Keep this secret and never share it"
            )
            
            if st.form_submit_button("💾 Save Credentials", type="primary"):
                if app_key and app_secret:
                    self.data_fetcher.configure_schwab_api(app_key, app_secret)
                    st.rerun()
                else:
                    st.error("Please enter both App Key and App Secret")
    
    def _render_authentication_flow(self):
        """OAuth authentication flow"""
        st.subheader("🔐 Account Authentication")
        
        if not self.data_fetcher.schwab_client.access_token:
            st.markdown("### Connect Your Schwab Account")
            
            # Generate authorization URL
            try:
                auth_url = self.data_fetcher.schwab_client.get_authorization_url()
                
                st.markdown("**Step 1:** Click the button below to authorize access:")
                if st.button("🔗 Authorize Schwab Access", type="primary"):
                    st.markdown(f"**[Click Here to Authorize]({auth_url})**")
                
                st.markdown("**Step 2:** After authorization, you'll be redirected to a localhost URL. Copy the **authorization code** from the URL:")
                st.code("https://127.0.0.1/?code=YOUR_CODE_HERE")
                
                st.markdown("**Step 3:** Paste the authorization code below:")
                
                with st.form("auth_code_form"):
                    auth_code = st.text_input(
                        "Authorization Code",
                        help="The code parameter from the redirect URL"
                    )
                    
                    if st.form_submit_button("🚀 Complete Setup", type="primary"):
                        if auth_code:
                            success = self.data_fetcher.authenticate_schwab(auth_code)
                            if success:
                                st.balloons()
                                st.rerun()
                        else:
                            st.error("Please enter the authorization code")
                            
            except Exception as e:
                st.error(f"Authorization URL generation failed: {e}")
        
        else:
            # Already authenticated
            st.success("✅ **Schwab API Connected!**")
            st.markdown("You now have access to real-time market data.")
            
            # Test connection button
            if st.button("🧪 Test Real-Time Data", type="secondary"):
                self._test_realtime_data()
            
            # Token management
            import time
            if self.data_fetcher.schwab_client.token_expires:
                minutes_left = (self.data_fetcher.schwab_client.token_expires - time.time()) / 60
                if minutes_left < 60:
                    st.warning(f"⏰ Access token expires in {minutes_left:.0f} minutes. It will auto-refresh.")
    
    def _test_realtime_data(self):
        """Test real-time data connection"""
        try:
            with st.spinner("Testing real-time data connection..."):
                # Test with a few mining stocks
                test_symbols = ['RIOT', 'MARA', 'CLSK']
                stock_data = self.data_fetcher.get_stock_data(test_symbols, '1D')
                
                if not stock_data.empty:
                    st.success("🎉 **Real-time data test successful!**")
                    
                    # Show sample data with timestamps
                    st.markdown("**Sample Real-Time Quotes:**")
                    for symbol in test_symbols:
                        if symbol in stock_data.columns:
                            price = stock_data[symbol].iloc[-1]
                            st.metric(symbol, f"${price:.2f}", help="Real-time price")
                    
                    st.info(f"Data timestamp: {stock_data.index[-1]}")
                else:
                    st.error("No data received - check your API connection")
                    
        except Exception as e:
            st.error(f"Real-time data test failed: {e}")
    
    def _is_schwab_configured(self) -> bool:
        """Check if Schwab API is configured"""
        return (hasattr(st.session_state, 'schwab_app_key') and 
                hasattr(st.session_state, 'schwab_app_secret') and
                st.session_state.schwab_app_key and 
                st.session_state.schwab_app_secret)