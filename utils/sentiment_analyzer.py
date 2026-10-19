import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import os

class SentimentAnalyzer:
    
    def __init__(self):
        self.base_url = "https://www.alphavantage.co/query"
        
    def get_news_sentiment(self, tickers, limit=50, time_from=None):
        api_key = os.environ.get('ALPHA_VANTAGE_API_KEY')
        
        if not api_key:
            return {
                'error': 'ALPHA_VANTAGE_API_KEY not set',
                'message': 'Please add your Alpha Vantage API key to continue'
            }
        
        if isinstance(tickers, list):
            tickers = ','.join(tickers)
        
        if not time_from:
            time_from = (datetime.now() - timedelta(days=7)).strftime('%Y%m%dT%H%M')
        
        params = {
            'function': 'NEWS_SENTIMENT',
            'tickers': tickers,
            'time_from': time_from,
            'limit': limit,
            'apikey': api_key
        }
        
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'Error Message' in data:
                    return {'error': data['Error Message']}
                
                # Alpha Vantage signals rate limits / bad keys with 'Note' (old) or
                # 'Information' (current) and NO feed — previously this slipped through
                # as an empty feed and was shown as a silent 'Neutral 0.0'.
                for k in ('Note', 'Information'):
                    if k in data and 'feed' not in data:
                        return {'error': 'API rate limit reached or key rejected', 'message': data[k]}
                
                return data
            else:
                return {'error': f'API request failed with status {response.status_code}'}
                
        except Exception as e:
            return {'error': f'Request failed: {str(e)}'}
    
    def parse_sentiment_data(self, data, ticker=None):
        if 'error' in data:
            return None
        
        feed = data.get('feed', [])
        
        if not feed:
            return pd.DataFrame()
        
        articles = []
        
        for article in feed:
            article_data = {
                'title': article.get('title', 'N/A'),
                'source': article.get('source', 'N/A'),
                'time_published': article.get('time_published', ''),
                'summary': article.get('summary', ''),
                'url': article.get('url', ''),
                'overall_sentiment': article.get('overall_sentiment_label', 'Neutral'),
                'overall_score': float(article.get('overall_sentiment_score', 0))
            }
            
            if ticker:
                ticker_sentiments = article.get('ticker_sentiment', [])
                ticker_data = next((t for t in ticker_sentiments if t['ticker'] == ticker), None)
                
                if ticker_data:
                    article_data['ticker_sentiment'] = ticker_data.get('ticker_sentiment_label', 'Neutral')
                    article_data['ticker_score'] = float(ticker_data.get('ticker_sentiment_score', 0))
                    article_data['relevance'] = float(ticker_data.get('relevance_score', 0))
                else:
                    article_data['ticker_sentiment'] = 'Neutral'
                    article_data['ticker_score'] = 0.0
                    article_data['relevance'] = 0.0
            
            articles.append(article_data)
        
        df = pd.DataFrame(articles)
        
        if not df.empty and 'time_published' in df.columns:
            df['time_published'] = pd.to_datetime(df['time_published'], format='%Y%m%dT%H%M%S', errors='coerce')
            df = df.sort_values('time_published', ascending=False)
        
        return df
    
    def get_aggregate_sentiment(self, df, ticker=None):
        if df is None or df.empty:
            return {
                'avg_sentiment': 0.0,
                'sentiment_label': 'Neutral',
                'bullish_pct': 0.0,
                'bearish_pct': 0.0,
                'neutral_pct': 0.0,
                'article_count': 0
            }
        
        score_col = 'ticker_score' if ticker and 'ticker_score' in df.columns else 'overall_score'
        sentiment_col = 'ticker_sentiment' if ticker and 'ticker_sentiment' in df.columns else 'overall_sentiment'
        
        avg_score = df[score_col].mean()
        
        if avg_score >= 0.15:
            sentiment_label = 'Bullish'
        elif avg_score <= -0.15:
            sentiment_label = 'Bearish'
        else:
            sentiment_label = 'Neutral'
        
        total = len(df)
        bullish_count = len(df[df[sentiment_col].str.contains('Bullish', na=False)])
        bearish_count = len(df[df[sentiment_col].str.contains('Bearish', na=False)])
        neutral_count = total - bullish_count - bearish_count
        
        return {
            'avg_sentiment': avg_score,
            'sentiment_label': sentiment_label,
            'bullish_pct': (bullish_count / total * 100) if total > 0 else 0,
            'bearish_pct': (bearish_count / total * 100) if total > 0 else 0,
            'neutral_pct': (neutral_count / total * 100) if total > 0 else 0,
            'article_count': total
        }
    
    def get_sentiment_color(self, score):
        if score >= 0.15:
            return "🟢"
        elif score <= -0.15:
            return "🔴"
        else:
            return "🟡"
    
    def get_sentiment_trend(self, df, ticker=None):
        if df is None or df.empty or len(df) < 2:
            return "No trend data"
        
        score_col = 'ticker_score' if ticker and 'ticker_score' in df.columns else 'overall_score'
        
        df_sorted = df.sort_values('time_published')
        
        recent = df_sorted.tail(len(df_sorted) // 2)[score_col].mean()
        older = df_sorted.head(len(df_sorted) // 2)[score_col].mean()
        
        if recent > older + 0.05:
            return "📈 Improving"
        elif recent < older - 0.05:
            return "📉 Declining"
        else:
            return "➡️ Stable"
