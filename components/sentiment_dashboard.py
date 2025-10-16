import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
from utils.sentiment_analyzer import SentimentAnalyzer
from datetime import datetime, timedelta

class SentimentDashboard:
    
    def __init__(self):
        self.analyzer = SentimentAnalyzer()
    
    def render(self, mining_stocks):
        st.header("📰 News Sentiment Analysis")
        st.markdown("Track market sentiment from financial news sources powered by Alpha Vantage")
        
        tab1, tab2, tab3 = st.tabs(["📊 Stock Sentiment", "📈 Sentiment Trends", "📋 News Feed"])
        
        with tab1:
            self._render_stock_sentiment(mining_stocks)
        
        with tab2:
            self._render_sentiment_trends(mining_stocks)
        
        with tab3:
            self._render_news_feed(mining_stocks)
    
    def _render_stock_sentiment(self, mining_stocks):
        st.subheader("Individual Stock Sentiment Analysis")
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            selected_stock = st.selectbox(
                "Select Stock",
                mining_stocks,
                key='sentiment_stock'
            )
        
        with col2:
            days_back = st.selectbox(
                "Time Period",
                [7, 14, 30],
                format_func=lambda x: f"Last {x} days",
                key='sentiment_days'
            )
        
        if st.button("🔍 Analyze Sentiment", key='analyze_sentiment', type='primary'):
            with st.spinner(f"Analyzing news sentiment for {selected_stock}..."):
                time_from = (datetime.now() - timedelta(days=days_back)).strftime('%Y%m%dT%H%M')
                
                data = self.analyzer.get_news_sentiment([selected_stock], limit=100, time_from=time_from)
                
                if 'error' in data:
                    st.error(f"❌ {data.get('message', data['error'])}")
                    
                    if 'ALPHA_VANTAGE_API_KEY not set' in data.get('error', ''):
                        st.info("💡 **How to get a free API key:**\n1. Visit https://www.alphavantage.co/support/#api-key\n2. Enter your email to get a free API key\n3. Add the API key using the button below")
                        
                        if st.button("➕ Add Alpha Vantage API Key"):
                            st.info("Use the 🔑 secrets tool to add ALPHA_VANTAGE_API_KEY")
                    return
                
                df = self.analyzer.parse_sentiment_data(data, ticker=selected_stock)
                
                if df is None or df.empty:
                    st.warning(f"No news articles found for {selected_stock} in the last {days_back} days")
                    return
                
                agg = self.analyzer.get_aggregate_sentiment(df, ticker=selected_stock)
                
                st.markdown("---")
                st.subheader(f"📊 Sentiment Summary for {selected_stock}")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    color_indicator = self.analyzer.get_sentiment_color(agg['avg_sentiment'])
                    st.metric(
                        "Avg Sentiment",
                        f"{agg['avg_sentiment']:.3f}",
                        delta=f"{color_indicator} {agg['sentiment_label']}"
                    )
                
                with col2:
                    st.metric(
                        "Bullish Articles",
                        f"{agg['bullish_pct']:.1f}%"
                    )
                
                with col3:
                    st.metric(
                        "Bearish Articles",
                        f"{agg['bearish_pct']:.1f}%"
                    )
                
                with col4:
                    st.metric(
                        "Total Articles",
                        agg['article_count']
                    )
                
                trend = self.analyzer.get_sentiment_trend(df, ticker=selected_stock)
                st.info(f"**Sentiment Trend:** {trend}")
                
                st.markdown("---")
                st.subheader("📈 Sentiment Distribution")
                
                fig = go.Figure()
                
                fig.add_trace(go.Bar(
                    x=['Bullish', 'Neutral', 'Bearish'],
                    y=[agg['bullish_pct'], agg['neutral_pct'], agg['bearish_pct']],
                    marker_color=['#00ff00', '#ffff00', '#ff0000'],
                    text=[f"{agg['bullish_pct']:.1f}%", f"{agg['neutral_pct']:.1f}%", f"{agg['bearish_pct']:.1f}%"],
                    textposition='auto'
                ))
                
                fig.update_layout(
                    title=f"Sentiment Distribution for {selected_stock}",
                    xaxis_title="Sentiment",
                    yaxis_title="Percentage (%)",
                    template='plotly_dark',
                    height=400
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                st.session_state['sentiment_df'] = df
                st.session_state['sentiment_ticker'] = selected_stock
    
    def _render_sentiment_trends(self, mining_stocks):
        st.subheader("Multi-Stock Sentiment Comparison")
        
        selected_stocks = st.multiselect(
            "Select Stocks to Compare",
            mining_stocks,
            default=mining_stocks[:3] if len(mining_stocks) >= 3 else mining_stocks,
            key='sentiment_compare'
        )
        
        if not selected_stocks:
            st.warning("Please select at least one stock")
            return
        
        if st.button("📊 Compare Sentiment", key='compare_sentiment', type='primary'):
            with st.spinner("Analyzing sentiment for selected stocks..."):
                sentiment_data = []
                
                for stock in selected_stocks:
                    data = self.analyzer.get_news_sentiment([stock], limit=50)
                    
                    if 'error' not in data:
                        df = self.analyzer.parse_sentiment_data(data, ticker=stock)
                        agg = self.analyzer.get_aggregate_sentiment(df, ticker=stock)
                        
                        sentiment_data.append({
                            'Stock': stock,
                            'Avg Sentiment': agg['avg_sentiment'],
                            'Label': agg['sentiment_label'],
                            'Bullish %': agg['bullish_pct'],
                            'Bearish %': agg['bearish_pct'],
                            'Articles': agg['article_count']
                        })
                
                if sentiment_data:
                    import pandas as pd
                    compare_df = pd.DataFrame(sentiment_data)
                    
                    fig = go.Figure()
                    
                    fig.add_trace(go.Bar(
                        x=compare_df['Stock'],
                        y=compare_df['Avg Sentiment'],
                        marker_color=['#00ff00' if s >= 0.15 else '#ff0000' if s <= -0.15 else '#ffff00' 
                                     for s in compare_df['Avg Sentiment']],
                        text=[f"{s:.3f}" for s in compare_df['Avg Sentiment']],
                        textposition='auto'
                    ))
                    
                    fig.update_layout(
                        title="Average Sentiment Score Comparison",
                        xaxis_title="Stock",
                        yaxis_title="Sentiment Score",
                        template='plotly_dark',
                        height=400
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("---")
                    st.subheader("📋 Detailed Comparison")
                    st.dataframe(compare_df, use_container_width=True)
                else:
                    st.error("Failed to retrieve sentiment data")
    
    def _render_news_feed(self, mining_stocks):
        st.subheader("Latest News Articles with Sentiment")
        
        if 'sentiment_df' in st.session_state and 'sentiment_ticker' in st.session_state:
            df = st.session_state['sentiment_df']
            ticker = st.session_state['sentiment_ticker']
            
            st.info(f"Showing news for **{ticker}** (from previous analysis)")
            
            if not df.empty:
                for idx, row in df.head(10).iterrows():
                    with st.expander(f"📰 {row['title']} - {row['source']}"):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**Published:** {row['time_published']}")
                            st.markdown(f"**Summary:** {row['summary']}")
                            st.markdown(f"[Read Full Article]({row['url']})")
                        
                        with col2:
                            if 'ticker_sentiment' in row:
                                sentiment = row['ticker_sentiment']
                                score = row['ticker_score']
                                relevance = row['relevance']
                                
                                st.metric("Sentiment", sentiment)
                                st.metric("Score", f"{score:.3f}")
                                st.metric("Relevance", f"{relevance:.2%}")
                            else:
                                st.metric("Overall Sentiment", row['overall_sentiment'])
                                st.metric("Score", f"{row['overall_score']:.3f}")
        else:
            st.info("👆 Run a sentiment analysis from the 'Stock Sentiment' tab first to see the news feed")
