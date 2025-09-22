import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
import time


class PolymarketFetcher:
    """Fetch Bitcoin mining prediction market data from Polymarket"""
    
    def __init__(self):
        self.base_url = "https://gamma-api.polymarket.com"
        self.cache = {}
        self.cache_timestamps = {}
        self.cache_duration = 30  # 30 second cache for real-time updates
        
        # Bitcoin mining related keywords for filtering
        self.mining_keywords = [
            'bitcoin mining', 'mining', 'hashrate', 'difficulty', 
            'miners', 'mining pool', 'mining reward', 'halving',
            'MARA', 'RIOT', 'CLSK', 'HUT', 'marathon digital',
            'riot platforms', 'core scientific', 'hut 8'
        ]
    
    def _get_cache_key(self, method_name, *args):
        """Generate cache key for method and arguments"""
        return f"{method_name}_{hash(str(args))}"
    
    def _get_from_cache(self, cache_key):
        """Get data from cache if still valid"""
        if cache_key in self.cache and cache_key in self.cache_timestamps:
            cached_time = self.cache_timestamps[cache_key]
            if (time.time() - cached_time) < self.cache_duration:
                return self.cache[cache_key]
        return None
    
    def _store_in_cache(self, cache_key, data):
        """Store data in cache with timestamp"""
        self.cache[cache_key] = data
        self.cache_timestamps[cache_key] = time.time()
    
    def get_bitcoin_mining_markets(self):
        """Fetch Bitcoin mining related prediction markets"""
        cache_key = self._get_cache_key('bitcoin_mining_markets')
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            # Search for Bitcoin and mining related markets
            mining_markets = []
            
            # Search with different keywords
            search_terms = ['bitcoin mining', 'mining', 'MARA', 'RIOT', 'CLSK', 'HUT']
            
            for term in search_terms:
                url = f"{self.base_url}/markets"
                params = {
                    'search': term,
                    'active': True,
                    'limit': 50
                }
                
                response = requests.get(url, params=params, timeout=10)
                if response.status_code == 200:
                    markets = response.json()
                    
                    # Filter for mining-related markets
                    for market in markets:
                        if self._is_mining_related(market):
                            mining_markets.append(market)
            
            # Remove duplicates based on market ID
            unique_markets = {market['id']: market for market in mining_markets}
            result = list(unique_markets.values())
            
            # Sort by volume
            result.sort(key=lambda x: float(x.get('volume', 0)), reverse=True)
            
            self._store_in_cache(cache_key, result)
            return result
            
        except Exception as e:
            st.error(f"Error fetching Polymarket data: {str(e)}")
            return []
    
    def _is_mining_related(self, market):
        """Check if market is related to Bitcoin mining"""
        question = market.get('question', '').lower()
        description = market.get('description', '').lower()
        
        # Check for mining keywords
        text_to_check = f"{question} {description}"
        
        for keyword in self.mining_keywords:
            if keyword.lower() in text_to_check:
                return True
        
        return False
    
    def get_market_details(self, market_id):
        """Get detailed information for a specific market"""
        cache_key = self._get_cache_key('market_details', market_id)
        cached_result = self._get_from_cache(cache_key)
        if cached_result is not None:
            return cached_result
        
        try:
            url = f"{self.base_url}/markets/{market_id}"
            response = requests.get(url, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                self._store_in_cache(cache_key, result)
                return result
            else:
                return None
                
        except Exception as e:
            st.error(f"Error fetching market details: {str(e)}")
            return None
    
    def get_market_orderbook(self, token_id):
        """Get order book data for a market token"""
        try:
            # Use CLOB API for orderbook data
            url = f"https://clob.polymarket.com/book"
            params = {'token_id': token_id}
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return None
                
        except Exception as e:
            st.warning(f"Order book data unavailable: {str(e)}")
            return None
    
    def calculate_market_metrics(self, market):
        """Calculate useful metrics for a prediction market"""
        try:
            metrics = {}
            
            # Basic market info
            metrics['question'] = market.get('question', 'N/A')
            metrics['description'] = market.get('description', 'N/A')
            metrics['volume'] = float(market.get('volume', 0))
            metrics['volume_24h'] = float(market.get('volume24hr', 0))
            
            # Token prices (YES/NO probabilities)
            tokens = market.get('tokens', [])
            if len(tokens) >= 2:
                yes_token = next((t for t in tokens if 'yes' in str(t.get('outcome', '')).lower()), tokens[0])
                no_token = next((t for t in tokens if 'no' in str(t.get('outcome', '')).lower()), tokens[1])
                
                metrics['yes_price'] = float(yes_token.get('price', 0))
                metrics['no_price'] = float(no_token.get('price', 0))
                metrics['implied_probability'] = metrics['yes_price'] * 100
                
                # Calculate implied odds
                if metrics['yes_price'] > 0:
                    metrics['yes_odds'] = 1 / metrics['yes_price']
                    metrics['no_odds'] = 1 / metrics['no_price'] if metrics['no_price'] > 0 else float('inf')
                else:
                    metrics['yes_odds'] = float('inf')
                    metrics['no_odds'] = 1
            
            # Market status and timing
            end_date = market.get('end_date_iso')
            if end_date:
                end_datetime = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
                now = datetime.now(end_datetime.tzinfo)
                metrics['days_remaining'] = (end_datetime - now).days
                metrics['end_date'] = end_datetime.strftime('%Y-%m-%d')
            else:
                metrics['days_remaining'] = None
                metrics['end_date'] = 'TBD'
            
            # Market activity indicators
            metrics['active'] = market.get('active', False)
            metrics['closed'] = market.get('closed', False)
            metrics['resolved'] = market.get('resolved', False)
            
            # Liquidity indicators
            if metrics['volume'] > 0:
                if metrics['volume'] > 1000000:  # $1M+
                    metrics['liquidity_tier'] = 'High'
                elif metrics['volume'] > 100000:  # $100K+
                    metrics['liquidity_tier'] = 'Medium'
                else:
                    metrics['liquidity_tier'] = 'Low'
            else:
                metrics['liquidity_tier'] = 'Very Low'
            
            return metrics
            
        except Exception as e:
            st.error(f"Error calculating market metrics: {str(e)}")
            return {}
    
    def search_markets_by_keyword(self, keyword):
        """Search for markets by specific keyword"""
        try:
            url = f"{self.base_url}/markets"
            params = {
                'search': keyword,
                'limit': 100,
                'active': True
            }
            
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                return response.json()
            else:
                return []
                
        except Exception as e:
            st.error(f"Error searching markets: {str(e)}")
            return []
    
    def get_trending_mining_markets(self):
        """Get trending Bitcoin mining markets based on volume"""
        try:
            all_markets = self.get_bitcoin_mining_markets()
            
            # Filter for high activity and recent markets
            trending = []
            for market in all_markets:
                metrics = self.calculate_market_metrics(market)
                
                # Criteria for trending: high volume, active, not resolved
                if (metrics.get('volume_24h', 0) > 1000 and 
                    metrics.get('active', False) and 
                    not metrics.get('resolved', False)):
                    trending.append({
                        'market': market,
                        'metrics': metrics
                    })
            
            # Sort by 24h volume
            trending.sort(key=lambda x: x['metrics'].get('volume_24h', 0), reverse=True)
            
            return trending[:10]  # Top 10 trending
            
        except Exception as e:
            st.error(f"Error getting trending markets: {str(e)}")
            return []