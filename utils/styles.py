"""
utils/styles.py
Shared CSS and styling utilities for BitcoinSage dashboard.
Call inject_styles() once in app.py — do not call from individual components.
"""

import streamlit as st
from datetime import datetime

# ─── Palette ──────────────────────────────────────────────────────────────────

COLORS = {
    "primary":   "#f7931e",   # Bitcoin orange
    "secondary": "#ffcc02",   # Gold
    "accent":    "#00ff88",   # Neon green
    "danger":    "#ff4444",
    "warning":   "#ffaa00",
    "success":   "#00cc66",
    "bg_card":   "#262730",
    "bg_dark":   "#1a1a2e",
    "text_muted":"#8b8b9b",
}

_CSS = """
.main-header { font-size: 2.8rem; font-weight: 800; text-align: center; margin-bottom: 1.5rem; background: linear-gradient(90deg, #ff6b35, #f7931e, #ffcc02); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; letter-spacing: -0.5px; }
.section-header { font-size: 1.4rem; font-weight: 700; color: #f7931e; margin-bottom: 0.75rem; border-bottom: 2px solid #f7931e33; padding-bottom: 0.4rem; }
.metric-card { background: #262730; padding: 1rem 1.25rem; border-radius: 0.6rem; border-left: 4px solid #00ff88; margin-bottom: 0.5rem; }
.metric-card-warning { background: #262730; padding: 1rem 1.25rem; border-radius: 0.6rem; border-left: 4px solid #ffaa00; margin-bottom: 0.5rem; }
.metric-card-danger { background: #262730; padding: 1rem 1.25rem; border-radius: 0.6rem; border-left: 4px solid #ff4444; margin-bottom: 0.5rem; }
.badge { display: inline-block; padding: 0.2rem 0.6rem; border-radius: 999px; font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; }
.badge-live { background: #00cc6622; color: #00cc66; border: 1px solid #00cc66; }
.badge-delayed { background: #ffaa0022; color: #ffaa00; border: 1px solid #ffaa00; }
.badge-offline { background: #ff444422; color: #ff4444; border: 1px solid #ff4444; }
.alert-box { background: #ff444418; border: 1px solid #ff4444; border-radius: 0.5rem; padding: 0.9rem 1.1rem; margin: 0.75rem 0; color: #ff8888; }
.success-box { background: #00cc6618; border: 1px solid #00cc66; border-radius: 0.5rem; padding: 0.9rem 1.1rem; margin: 0.75rem 0; color: #00ff88; }
.info-box { background: #f7931e18; border: 1px solid #f7931e55; border-radius: 0.5rem; padding: 0.9rem 1.1rem; margin: 0.75rem 0; color: #f7931e; }
.stDataFrame { border-radius: 0.5rem; overflow: hidden; }
.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { padding: 0.4rem 1rem; border-radius: 0.4rem 0.4rem 0 0; font-weight: 500; }
.css-1d391kg, [data-testid="stSidebar"] { background: #1a1a2e; }
.loading-overlay { text-align: center; padding: 2rem; color: #8b8b9b; font-size: 0.9rem; }
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #1a1a2e; }
::-webkit-scrollbar-thumb { background: #f7931e55; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #f7931e; }
"""

def inject_styles():
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)

def main_header(title: str = "₿ BitcoinSage"):
    st.markdown(f'<h1 class="main-header">{title}</h1>', unsafe_allow_html=True)

def section_header(title: str):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)

def metric_card(label: str, value: str, level: str = "normal"):
    css_class = {"warning": "metric-card-warning", "danger": "metric-card-danger"}.get(level, "metric-card")
    st.markdown(f'<div class="{css_class}"><strong>{label}</strong><br/><span style="font-size:1.3rem">{value}</span></div>', unsafe_allow_html=True)

def data_badge(source: str):
    labels = {"live": "● LIVE", "delayed": "◑ 15-MIN DELAY", "offline": "○ OFFLINE"}
    label = labels.get(source, source.upper())
    st.markdown(f'<span class="badge badge-{source}">{label}</span>', unsafe_allow_html=True)

def loading_placeholder(message: str = "Loading data…"):
    st.markdown(f'<div class="loading-overlay">⏳ {message}</div>', unsafe_allow_html=True)

def data_lineage_panel(items, title: str = "Data Quality"):
    """Compact panel for Direct / Estimated / Proxy / freshness notes."""
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    body = "<ul style='margin:0.35rem 0 0 1rem; padding:0;'>"
    for item in items:
        body += f"<li style='margin:0.18rem 0'>{item}</li>"
    body += "</ul>"
    st.markdown(
        f"<div class='info-box'><strong>{title}</strong>"
        f"<div style='font-size:0.8rem;color:#8b8b9b;margin-top:0.2rem'>Rendered {now}</div>"
        f"{body}</div>",
        unsafe_allow_html=True
    )
