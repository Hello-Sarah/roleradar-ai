"""Calm Intelligence design tokens and responsive Streamlit overrides."""

from __future__ import annotations

import streamlit as st


def calm_intelligence_css() -> str:
    return """
    :root {
      --rr-canvas: #F5F5F7; --rr-surface: #FFFFFF; --rr-text: #1D1D1F;
      --rr-secondary: #6E6E73; --rr-blue: #0071E3; --rr-success: #248A3D;
      --rr-warning: #B35C00; --rr-danger: #D70015; --rr-hairline: #D2D2D7;
      --rr-radius: 18px;
    }
    html, body, button, input, textarea, select, [data-testid="stMarkdownContainer"] {
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
        "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    }
    html, body {
      background: var(--rr-canvas) !important; color: var(--rr-text) !important;
      font-size: 16px;
    }
    .stApp {
      background: var(--rr-canvas) !important; color: var(--rr-text) !important;
      overflow-x: hidden;
    }
    [data-testid="stMainBlockContainer"] { max-width: 1440px; padding: 2rem 2.5rem 4rem; }
    [data-testid="stSidebar"] {
      background: rgba(255, 255, 255, .88); border-right: 1px solid var(--rr-hairline);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
      background: var(--rr-surface); border: 1px solid rgba(210, 210, 215, .7);
      border-radius: var(--rr-radius); box-shadow: 0 4px 20px rgba(0, 0, 0, .035);
    }
    .stApp h1 {
      color: var(--rr-text) !important; font-size: clamp(2rem, 3vw, 3rem);
      letter-spacing: -.035em;
    }
    .stApp h2, .stApp h3 { color: var(--rr-text) !important; letter-spacing: -.015em; }
    .stApp p, .stApp label, [data-testid="stCaptionContainer"] {
      color: var(--rr-secondary) !important;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p {
      color: #454549 !important; opacity: 1 !important;
    }
    .stApp [data-testid="stAlert"] p,
    .stApp [data-testid="stAlert"] strong { color: #3A3A3C !important; }
    .stApp [data-variant="segmented_control"] p { color: #3A3A3C !important; }
    [data-testid="stCaptionContainer"] { font-size: 13px; }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
      background: var(--rr-blue); border-color: var(--rr-blue);
      border-radius: 999px; min-height: 44px;
    }
    .stButton > button[kind="primary"] p,
    .stButton > button[kind^="primary"] p,
    .stFormSubmitButton > button[kind^="primary"] p { color: #FFFFFF !important; }
    .stButton > button:not([kind^="primary"]) p,
    .stFormSubmitButton > button:not([kind^="primary"]) p,
    [data-testid="stBaseButton-secondary"] p { color: #3A3A3C !important; }
    [data-testid="stSidebarCollapseButton"] { display: none; }
    button:focus-visible, a:focus-visible, input:focus-visible, textarea:focus-visible,
    [role="button"]:focus-visible, [role="radio"]:focus-visible {
      outline: 3px solid rgba(0, 113, 227, .45) !important; outline-offset: 3px;
    }
    .rr-kicker { color: var(--rr-blue); font-size: 13px; font-weight: 650; letter-spacing: .04em; }
    .rr-copilot { min-width: 0; }
    .st-key-mobile_copilot_launcher { display: none; }
    @media (max-width: 390px) {
      html, body, .stApp { max-width: 100vw; overflow-x: hidden; }
      [data-testid="stMainBlockContainer"] { padding: 1rem 1rem 3rem; max-width: 100%; }
      [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
      [data-testid="stSidebar"][aria-expanded="true"] {
        width: 100vw !important; min-width: 100vw !important; max-width: 100vw !important;
      }
      [data-testid="stSidebarCollapseButton"] { display: block; }
      [data-testid="stSidebarCollapsedControl"] button [data-testid="stIconMaterial"],
      [data-testid="stSidebarCollapseButton"] button [data-testid="stIconMaterial"] {
        font-size: 0 !important;
      }
      [data-testid="stSidebarCollapsedControl"] button,
      [data-testid="stSidebarCollapseButton"] button { font-size: 0; }
      [data-testid="stSidebarCollapsedControl"] button::before,
      [data-testid="stSidebarCollapseButton"] button::before {
        content: "☰"; color: var(--rr-text); font-size: 20px;
      }
      [data-testid="column"] { width: 100% !important; flex: 1 1 100% !important; min-width: 0; }
      .st-key-mobile_copilot_launcher { display: block; }
      .st-key-desktop_copilot_panel { display: none; }
      [data-testid="stDialog"] [role="dialog"] {
        position: fixed; inset: 0; width: 100vw; max-width: none;
        height: 100dvh; max-height: none; border-radius: 0;
        background: var(--rr-surface) !important; overflow-y: auto;
      }
      .rr-copilot { width: 100%; min-height: 100%; }
      [data-testid="stDataFrame"] { max-width: calc(100vw - 2rem); overflow-x: auto; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: .01ms !important; transition-duration: .01ms !important;
      }
    }
    """


def apply_theme() -> None:
    st.markdown(f"<style>{calm_intelligence_css()}</style>", unsafe_allow_html=True)
