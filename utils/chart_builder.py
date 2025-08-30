import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import streamlit as st

class ChartBuilder:
    """Creates interactive charts for financial data visualization"""
    
    def __init__(self):
        self.color_scheme = {
            'bullish': '#00ff88',
            'bearish': '#ff4444',
            'neutral': '#888888',
            'background': '#0e1117',
            'grid': '#262730'
        }
    
    def create_price_chart(self, symbol, data, show_volume=True):
        """Create an interactive price chart with volume"""
        try:
            if data.empty or symbol not in data.columns:
                return None
            
            prices = data[symbol].dropna()
            if len(prices) < 2:
                return None
            
            # Create subplot with secondary y-axis for volume
            fig = make_subplots(
                rows=2 if show_volume else 1,
                cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=(f'{symbol} Price', 'Volume') if show_volume else (f'{symbol} Price',),
                row_heights=[0.7, 0.3] if show_volume else [1.0]
            )
            
            # Price line
            fig.add_trace(
                go.Scatter(
                    x=prices.index,
                    y=prices.values,
                    name=f'{symbol} Price',
                    line=dict(color=self.color_scheme['bullish'], width=2),
                    hovertemplate='<b>%{fullData.name}</b><br>' +
                                  'Date: %{x}<br>' +
                                  'Price: $%{y:.2f}<extra></extra>'
                ),
                row=1, col=1
            )
            
            # Add moving averages
            if len(prices) >= 20:
                sma_20 = prices.rolling(20).mean()
                fig.add_trace(
                    go.Scatter(
                        x=sma_20.index,
                        y=sma_20.values,
                        name='SMA 20',
                        line=dict(color='orange', width=1, dash='dot'),
                        opacity=0.7
                    ),
                    row=1, col=1
                )
            
            if len(prices) >= 50:
                sma_50 = prices.rolling(50).mean()
                fig.add_trace(
                    go.Scatter(
                        x=sma_50.index,
                        y=sma_50.values,
                        name='SMA 50',
                        line=dict(color='purple', width=1, dash='dash'),
                        opacity=0.7
                    ),
                    row=1, col=1
                )
            
            # Volume bars (if available and requested)
            if show_volume:
                try:
                    import yfinance as yf
                    ticker = yf.Ticker(symbol)
                    hist = ticker.history(period='1mo')
                    
                    if not hist.empty and 'Volume' in hist.columns:
                        volumes = hist['Volume']
                        # Color volume bars based on price movement
                        colors = ['green' if hist['Close'].iloc[i] >= hist['Open'].iloc[i] 
                                else 'red' for i in range(len(hist))]
                        
                        fig.add_trace(
                            go.Bar(
                                x=volumes.index,
                                y=volumes.values,
                                name='Volume',
                                marker_color=colors,
                                opacity=0.6
                            ),
                            row=2, col=1
                        )
                except:
                    pass  # Skip volume if not available
            
            # Update layout
            fig.update_layout(
                title=f'{symbol} Price Chart',
                template='plotly_dark',
                hovermode='x unified',
                showlegend=True,
                height=600 if show_volume else 400,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            fig.update_xaxes(showgrid=True, gridcolor='#333333')
            fig.update_yaxes(showgrid=True, gridcolor='#333333')
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating price chart for {symbol}: {str(e)}")
            return None
    
    def create_candlestick_chart(self, symbol, data):
        """Create a candlestick chart with technical indicators"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if hist.empty:
                return None
            
            fig = go.Figure()
            
            # Candlestick chart
            fig.add_trace(
                go.Candlestick(
                    x=hist.index,
                    open=hist['Open'],
                    high=hist['High'],
                    low=hist['Low'],
                    close=hist['Close'],
                    name=symbol,
                    increasing_line_color=self.color_scheme['bullish'],
                    decreasing_line_color=self.color_scheme['bearish']
                )
            )
            
            # Add Bollinger Bands
            if len(hist) >= 20:
                sma = hist['Close'].rolling(20).mean()
                std = hist['Close'].rolling(20).std()
                upper_band = sma + (std * 2)
                lower_band = sma - (std * 2)
                
                fig.add_trace(
                    go.Scatter(
                        x=hist.index,
                        y=upper_band,
                        name='Upper BB',
                        line=dict(color='rgba(255,255,255,0.3)', width=1),
                        showlegend=False
                    )
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=hist.index,
                        y=lower_band,
                        name='Lower BB',
                        line=dict(color='rgba(255,255,255,0.3)', width=1),
                        fill='tonexty',
                        fillcolor='rgba(255,255,255,0.1)',
                        showlegend=False
                    )
                )
            
            fig.update_layout(
                title=f'{symbol} Candlestick Chart',
                template='plotly_dark',
                xaxis_title='Date',
                yaxis_title='Price ($)',
                height=500,
                showlegend=True,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            fig.update_xaxes(rangeslider_visible=False)
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating candlestick chart for {symbol}: {str(e)}")
            return None
    
    def create_volume_chart(self, symbol, data):
        """Create volume analysis chart"""
        try:
            import yfinance as yf
            
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period='1mo')
            
            if hist.empty or 'Volume' in hist.columns:
                return None
            
            # Calculate volume moving average
            hist['Volume_MA'] = hist['Volume'].rolling(20).mean()
            
            # Color based on price movement
            colors = []
            for i in range(len(hist)):
                if hist['Close'].iloc[i] >= hist['Open'].iloc[i]:
                    colors.append(self.color_scheme['bullish'])
                else:
                    colors.append(self.color_scheme['bearish'])
            
            fig = go.Figure()
            
            # Volume bars
            fig.add_trace(
                go.Bar(
                    x=hist.index,
                    y=hist['Volume'],
                    name='Volume',
                    marker_color=colors,
                    opacity=0.7
                )
            )
            
            # Volume moving average
            fig.add_trace(
                go.Scatter(
                    x=hist.index,
                    y=hist['Volume_MA'],
                    name='Volume MA (20)',
                    line=dict(color='white', width=2),
                    opacity=0.8
                )
            )
            
            fig.update_layout(
                title=f'{symbol} Volume Analysis',
                template='plotly_dark',
                xaxis_title='Date',
                yaxis_title='Volume',
                height=300,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating volume chart for {symbol}: {str(e)}")
            return None
    
    def create_put_call_ratio_chart(self, symbol, pc_data):
        """Create put-call ratio visualization"""
        try:
            if not pc_data:
                return None
            
            # Create gauge chart for put-call ratio
            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=pc_data.get('put_call_ratio', 0),
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"{symbol} Put-Call Ratio"},
                delta={'reference': 1.0},
                gauge={
                    'axis': {'range': [None, 2]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 0.6], 'color': self.color_scheme['bullish']},
                        {'range': [0.6, 1.2], 'color': 'yellow'},
                        {'range': [1.2, 2], 'color': self.color_scheme['bearish']}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 1.0
                    }
                }
            ))
            
            fig.update_layout(
                template='plotly_dark',
                height=300,
                margin=dict(l=20, r=20, t=40, b=20)
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating put-call ratio chart: {str(e)}")
            return None
    
    def create_dark_pool_chart(self, symbol, volume_data):
        """Create dark pool activity visualization"""
        try:
            if not volume_data or symbol not in volume_data:
                return None
            
            data = volume_data[symbol]
            volumes = data['volume']
            prices = data['close']
            dates = data['dates']
            
            # Calculate VWAP
            vwap = np.cumsum(prices * volumes) / np.cumsum(volumes)
            
            # Calculate volume percentiles to identify unusual activity
            volume_percentiles = np.percentile(volumes, [50, 75, 90, 95])
            
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.02,
                subplot_titles=('Price vs VWAP', 'Volume Activity')
            )
            
            # Price vs VWAP
            fig.add_trace(
                go.Scatter(
                    x=dates, y=prices,
                    name='Price',
                    line=dict(color=self.color_scheme['bullish'])
                ),
                row=1, col=1
            )
            
            fig.add_trace(
                go.Scatter(
                    x=dates, y=vwap,
                    name='VWAP',
                    line=dict(color='orange', dash='dot')
                ),
                row=1, col=1
            )
            
            # Volume with unusual activity highlighting
            colors = []
            for vol in volumes:
                if vol > volume_percentiles[3]:  # > 95th percentile
                    colors.append('red')
                elif vol > volume_percentiles[2]:  # > 90th percentile
                    colors.append('orange')
                else:
                    colors.append('blue')
            
            fig.add_trace(
                go.Bar(
                    x=dates, y=volumes,
                    name='Volume',
                    marker_color=colors,
                    opacity=0.7
                ),
                row=2, col=1
            )
            
            fig.update_layout(
                title=f'{symbol} Dark Pool Activity Analysis',
                template='plotly_dark',
                height=600,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating dark pool chart: {str(e)}")
            return None
    
    def create_correlation_heatmap(self, data):
        """Create correlation heatmap for mining stocks"""
        try:
            if data.empty:
                return None
            
            # Calculate returns for correlation
            returns = data.pct_change().dropna()
            correlation_matrix = returns.corr()
            
            fig = go.Figure(data=go.Heatmap(
                z=correlation_matrix.values,
                x=correlation_matrix.columns,
                y=correlation_matrix.columns,
                colorscale='RdYlBu_r',
                zmid=0,
                text=np.round(correlation_matrix.values, 2),
                texttemplate='%{text}',
                textfont={'size': 12},
                hoverongaps=False
            ))
            
            fig.update_layout(
                title='Mining Stocks Correlation Matrix',
                template='plotly_dark',
                height=500,
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating correlation heatmap: {str(e)}")
            return None
    
    def create_performance_comparison(self, data, period_returns):
        """Create performance comparison chart"""
        try:
            if data.empty:
                return None
            
            # Normalize prices to show relative performance
            normalized_data = data.div(data.iloc[0]) * 100
            
            fig = go.Figure()
            
            for symbol in normalized_data.columns:
                fig.add_trace(
                    go.Scatter(
                        x=normalized_data.index,
                        y=normalized_data[symbol],
                        name=symbol,
                        line=dict(width=2),
                        hovertemplate=f'<b>{symbol}</b><br>' +
                                      'Date: %{x}<br>' +
                                      'Relative Performance: %{y:.1f}%<extra></extra>'
                    )
                )
            
            fig.update_layout(
                title='Mining Stocks Relative Performance',
                template='plotly_dark',
                xaxis_title='Date',
                yaxis_title='Relative Performance (%)',
                height=500,
                hovermode='x unified',
                margin=dict(l=0, r=0, t=40, b=0)
            )
            
            fig.add_hline(y=100, line_dash="dot", line_color="white", opacity=0.5)
            
            return fig
            
        except Exception as e:
            st.error(f"Error creating performance comparison: {str(e)}")
            return None
