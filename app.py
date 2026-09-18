import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import time
import random
import math
import requests # NOUVEAU : Pour chercher les taux en ligne
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import base64
import hashlib
import io
import json
import html
import os
import shutil
import sqlite3
import tempfile
import unicodedata
import uuid
from contextlib import contextmanager

try:
    from equipment_models_catalog import (
        CATALOG_NOTE,
        TOP_USED_BRAND,
        format_model_label,
        get_brands_sorted,
        get_models_for_brand,
        get_reference_payload_tonnes,
        get_tonnage_preset_values,
    )
except ImportError:
    CATALOG_NOTE = ""
    TOP_USED_BRAND = ""
    def get_brands_sorted():  # type: ignore
        return ["Autre / saisie libre"]
    def get_models_for_brand(_brand: str):  # type: ignore
        return []
    def get_reference_payload_tonnes(*_a, **_k):  # type: ignore
        return None
    def get_tonnage_preset_values():  # type: ignore
        return [30.0, 55.0, 91.0, 100.0, 240.0, 400.0]
    def format_model_label(brand: str, model: str, free_text: str = "") -> str:  # type: ignore
        if (brand or "").strip() == "Autre / saisie libre":
            return (free_text or "").strip()
        if TOP_USED_BRAND and (brand or "").strip() == TOP_USED_BRAND:
            return (model or "").strip()
        if not (model or "").strip():
            return (free_text or "").strip()
        return f"{(brand or '').strip()} {(model or '').strip()}".strip()

# Pandas 3.x a retiré Styler.applymap au profit de Styler.map.
# On garde une compatibilité avec les versions précédentes.
def _apply_add_mach_ton_preset_cb():
    raw = st.session_state.get("add_mach_ton_preset", "—")
    if raw == "—":
        return
    try:
        st.session_state["add_machine_capacity_tons"] = float(
            str(raw).replace(" t", "").replace(",", ".").strip()
        )
    except ValueError:
        pass


def _apply_edit_mach_ton_preset_cb():
    raw = st.session_state.get("edit_mach_ton_preset", "—")
    if raw == "—":
        return
    try:
        st.session_state["edit_machine_capacity_tons"] = float(
            str(raw).replace(" t", "").replace(",", ".").strip()
        )
    except ValueError:
        pass


def _styler_cell_map(styler, func, subset=None):
    if hasattr(styler, "map"):
        return styler.map(func, subset=subset)
    return styler.applymap(func, subset=subset)

def _normalize_login_secret(value):
    """Mot de passe identique pour l'utilisateur même si tiret « spécial » ou espaces (copier-coller)."""
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value)).strip()
    for ch in (
        "\u2010",
        "\u2011",
        "\u2012",
        "\u2013",
        "\u2014",
        "\u2212",
        "\uff0d",
        "\u00ad",
    ):
        s = s.replace(ch, "-")
    return s


def _hash_password(raw_password: str) -> str:
    """Retourne le SHA-256 du mot de passe après normalisation NFKC."""
    normalized = _normalize_login_secret(raw_password)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def _is_hashed(value: str) -> bool:
    """Vérifie si la valeur est un hash SHA-256 valide (64 caractères hexadécimaux)."""
    v = (value or "").strip()
    return len(v) == 64 and all(c in '0123456789abcdef' for c in v.lower())


# Pictogramme marque (SVG uniquement — engrenage + pics, couleurs unifiées #F5B800)
GOOD_ENGINEERS_BANNER_MARK_SVG = """
<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
  <g fill="none" stroke-linecap="round" stroke-linejoin="round">
    <circle cx="100" cy="100" r="86" stroke="#F5B800" stroke-width="1.25" opacity="0.16"/>
    <path d="M100 22 L108 48 L136 38 L126 66 L158 74 L132 94 L156 122 L124 118 L118 150 L100 128 L82 150 L76 118 L44 122 L68 94 L42 74 L74 66 L64 38 L92 48 Z"
          stroke="#F5B800" stroke-width="3.5"/>
    <circle cx="100" cy="100" r="17" fill="#0F2A44" stroke="#F5B800" stroke-width="3"/>
    <path d="M58 54 L142 146" stroke="#F5E6A8" stroke-width="5"/>
    <path d="M142 54 L58 146" stroke="#F5E6A8" stroke-width="5"/>
    <path d="M58 54 L48 40 L66 50z" fill="#F5B800"/>
    <path d="M142 146 L152 160 L134 150z" fill="#F5B800"/>
    <path d="M142 54 L152 40 L134 50z" fill="#F5B800"/>
    <path d="M58 146 L48 160 L66 150z" fill="#F5B800"/>
  </g>
</svg>
""".strip()


# ==============================================================================
# 1. CONFIGURATION & STYLE (DESIGN FAEST STORE)
# ==============================================================================
st.set_page_config(
    page_title="GOOD ENGINEERS OS", 
    page_icon="🏗️", 
    layout="wide",
    # Ouverte par défaut : en « collapsed », le bouton pour rouvrir la sidebar est dans stHeader,
    # or le thème masque stHeader (Déployer / menu) — la bande verticale devient invisible en ligne.
    initial_sidebar_state="expanded",
)


def _hero_masthead_png_path():
    """
    Visuel principal du hero (logo + titre jaune intégrés), dans assets/.
    Ordre : masthead dédié, logo, puis ancienne carte (legacy).
    """
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
    for name in (
        "good_engineers_hero_masthead.png",
        "good_engineers_logo.png",
        "good_engineers_brand_card.png",
    ):
        p = os.path.join(base, name)
        if os.path.isfile(p):
            return p
    return None


@st.cache_data(show_spinner=False)
def _hero_masthead_b64(_mtime: float = 0.0):
    p = _hero_masthead_png_path()
    if not p:
        return None
    try:
        with open(p, "rb") as f:
            raw = f.read()
        if len(raw) < 64:
            return None
        return base64.b64encode(raw).decode("ascii")
    except Exception:
        return None


def _hero_masthead_b64_for_banner():
    p = _hero_masthead_png_path()
    if not p:
        return None
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        mtime = 0.0
    return _hero_masthead_b64(mtime)


def render_good_engineers_banner(strapline_html=None):
    """
    Hero : PNG masthead (logo en haut + titre or sur l'image) si présent,
    sinon pictogramme SVG + titre en #F5B800 (HTML).
    """
    subtitle = strapline_html or "Système de Gestion Minière et Extraction d&apos;Or"
    b64 = _hero_masthead_b64_for_banner()
    hero_cls = "ge-hero ge-hero--masthead ge-hero--main-fixed" if b64 else "ge-hero ge-hero--main-fixed"
    if b64:
        body = f"""
    <h1 class="ge-hero__sr-only">GOOD ENGINEERS</h1>
    <div class="ge-hero__masthead-wrap">
      <img src="data:image/png;base64,{b64}" class="ge-hero__masthead"
           alt="GOOD ENGINEERS — identité visuelle" decoding="async" />
    </div>
    <div class="ge-hero__divider" aria-hidden="true"></div>
    <p class="ge-hero__tagline">DISCIPLINE &bull; RIGUEUR &bull; PERFORMANCE</p>
    <p class="ge-hero__subtitle">{subtitle}</p>"""
    else:
        body = f"""
    <div class="ge-hero__mark" aria-hidden="true">{GOOD_ENGINEERS_BANNER_MARK_SVG}</div>
    <h1 class="ge-hero__title">GOOD ENGINEERS</h1>
    <div class="ge-hero__divider" aria-hidden="true"></div>
    <p class="ge-hero__tagline">DISCIPLINE &bull; RIGUEUR &bull; PERFORMANCE</p>
    <p class="ge-hero__subtitle">{subtitle}</p>"""
    # st.markdown + unsafe_allow_html traverse le parseur Markdown (GFM) qui peut
    # supprimer le bloc HTML ; st.html sanifie via DOMPurify et conserve img data: URI.
    st.html(
        f"""
<div class="{hero_cls}" role="banner">
  <div class="ge-hero__layer ge-hero__layer--gradient"></div>
  <div class="ge-hero__layer ge-hero__layer--radial"></div>
  <div class="ge-hero__content">{body}
  </div>
</div>
"""
    )
    _inject_ge_hero_fixed_pin()


def _inject_ge_hero_fixed_pin():
    """
    Streamlit casse souvent position:sticky (overflow sur ancêtres). On fige le bandeau
    en position:fixed via le document parent, avec largeur/left alignés sur stMain.
    """
    components.html(
        """
<script>
(function () {
  function doc() {
    try { return window.parent.document; } catch (e) { return document; }
  }
  var debounce = null;
  function apply() {
    var d = doc();
    if (!d) return;
    var hero = d.querySelector(".ge-hero--main-fixed");
    var main = d.querySelector('section[data-testid="stMain"]');
    if (!hero || !main) return;
    var wrap =
      hero.closest('[data-testid="stElementContainer"]') ||
      hero.closest(".element-container") ||
      hero.parentElement;
    var hdr = d.querySelector('[data-testid="stHeader"]');
    var topPx = hdr ? Math.ceil(hdr.getBoundingClientRect().height) : 56;
    var mr = main.getBoundingClientRect();
    var h = Math.max(Math.round(hero.offsetHeight), Math.round(hero.getBoundingClientRect().height));
    if (wrap && h > 20) {
      wrap.style.minHeight = h + "px";
      wrap.style.boxSizing = "border-box";
    }
    hero.style.setProperty("position", "fixed", "important");
    hero.style.setProperty("top", topPx + "px", "important");
    hero.style.setProperty("left", Math.round(mr.left) + "px", "important");
    hero.style.setProperty("width", Math.round(mr.width) + "px", "important");
    hero.style.setProperty("max-width", "none", "important");
    hero.style.setProperty("z-index", "999", "important");
    hero.style.setProperty("box-sizing", "border-box", "important");
  }
  function schedule() {
    clearTimeout(debounce);
    debounce = setTimeout(function () {
      requestAnimationFrame(apply);
    }, 50);
  }
  schedule();
  try {
    window.parent.addEventListener("resize", schedule);
  } catch (e) {
    window.addEventListener("resize", schedule);
  }
  var d0 = doc();
  var main0 = d0.querySelector('section[data-testid="stMain"]');
  if (main0 && typeof ResizeObserver !== "undefined") {
    new ResizeObserver(schedule).observe(main0);
  }
  var hero0 = d0.querySelector(".ge-hero--main-fixed");
  if (hero0) {
    var im = hero0.querySelector("img.ge-hero__masthead");
    if (im && !im.complete) im.addEventListener("load", schedule);
  }
  setTimeout(schedule, 200);
  setTimeout(schedule, 600);
})();
</script>
""",
        height=0,
        scrolling=False,
    )


# Optimisations pour tablettes et mobile
st.markdown("""
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<style>
    /* Optimisations pour tablettes */
    @media (max-width: 1024px) {
        .stApp {
            padding: 0.5rem !important;
        }
        .stButton > button {
            min-height: 68px !important;
            font-size: 22px !important;
            font-weight: 900 !important;
            padding: 16px 28px !important;
            background: linear-gradient(180deg, #FFC107 0%, #E6AC00 100%) !important;
            color: #0F2A44 !important;
            border: 2px solid #FFC107 !important;
        }
        /* Boutons plus grands pour tablettes */
        button[kind="primary"] {
            min-height: 88px !important;
            font-size: 26px !important;
            font-weight: 900 !important;
        }
        /* Titres responsive */
        h1 {
            font-size: 48px !important;
            line-height: 1.2 !important;
        }
        .hero-banner {
            padding: 8px 0 !important;
            min-height: 38px !important;
        }
        .marquee-text {
            font-size: 18px !important;
        }
        .gold-text {
            font-size: 21px !important;
        }
    }
    /* Optimisations pour mobile */
    @media (max-width: 768px) {
        .stApp {
            padding: 0.25rem !important;
        }
        .stButton > button {
            min-height: 56px !important;
            font-size: 17px !important;
            font-weight: 900 !important;
            padding: 14px 22px !important;
            background: linear-gradient(180deg, #FFC107 0%, #E6AC00 100%) !important;
            color: #0F2A44 !important;
            border: 2px solid #FFC107 !important;
        }
        button[kind="primary"] {
            min-height: 64px !important;
            font-size: 20px !important;
            font-weight: 900 !important;
        }
        /* Titres responsive mobile */
        h1 {
            font-size: 32px !important;
            letter-spacing: 2px !important;
            line-height: 1.2 !important;
        }
        h2 {
            font-size: 24px !important;
        }
        h3 {
            font-size: 20px !important;
        }
        .hero-banner {
            padding: 6px 0 !important;
            min-height: 34px !important;
            margin-bottom: 10px !important;
        }
        .marquee-text {
            font-size: 15px !important;
            letter-spacing: 1px !important;
        }
        .gold-text {
            font-size: 17px !important;
            letter-spacing: 2px !important;
        }
        /* Conteneurs responsive */
        .content-card {
            padding: 15px !important;
            margin-bottom: 15px !important;
        }
        /* Onglets responsive */
        .stTabs [data-baseweb="tab"] {
            height: 50px !important;
            font-size: 14px !important;
            padding: 8px 12px !important;
        }
        /* Métriques responsive */
        [data-testid="stMetricValue"] {
            font-size: 28px !important;
        }
        [data-testid="stMetricLabel"] {
            font-size: 14px !important;
        }
    }
    /* Correction des débordements */
    * {
        box-sizing: border-box !important;
    }
    .stApp {
        overflow-x: hidden !important;
    }
    body {
        overflow-x: hidden !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialiser le mode (dark/light) avant les styles
if 'theme_mode' not in st.session_state:
    st.session_state.theme_mode = 'dark'

# Panneau latéral : réduit pour agrandir la zone « centre de contrôle » (réversible)
if 'ge_sidebar_collapsed' not in st.session_state:
    st.session_state.ge_sidebar_collapsed = False

_ge_sidebar_collapse_extra = ""
if st.session_state.get("ge_sidebar_collapsed"):
    _ge_sidebar_collapse_extra = """
    /* Sidebar repliée : libère la largeur pour le contenu principal */
    section[data-testid="stSidebar"] {
        flex: 0 0 0px !important;
        flex-basis: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        width: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        margin: 0 !important;
        opacity: 0 !important;
        transform: translateX(-100%) !important;
        border: none !important;
        border-right-width: 0 !important;
        overflow: hidden !important;
        pointer-events: none !important;
    }
    section[data-testid="stMain"] {
        flex: 1 1 0% !important;
        min-width: 0 !important;
        max-width: 100% !important;
    }
    """

# Design system industriel (minière — contraste élevé, mode sombre)
primary_blue = '#0F2A44'
accent = '#FFC107'  # jaune sécurité industriel (charte GOOD ENGINEERS)
warning_c = '#FF6B00'
success_c = '#28A745'
danger_c = '#DC3545'

# Variables CSS selon le mode (les deux variantes restent sombres / lisibles)
if st.session_state.theme_mode == 'dark':
    bg_main = '#121212'
    bg_card = '#1E1E1E'
    bg_secondary = '#2F2F2F'
    bg_hover = '#383838'
    bg_zebra = '#252525'
    text_primary = '#EAEAEA'
    text_secondary = '#A0A0A0'
    border_color = '#404040'
else:
    bg_main = '#161B22'
    bg_card = '#1E2329'
    bg_secondary = '#2F2F2F'
    bg_hover = '#3D4349'
    bg_zebra = '#282E36'
    text_primary = '#EAEAEA'
    text_secondary = '#A0A0A0'
    border_color = '#4A5058'

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;900&family=Montserrat:wght@700;900&family=Oswald:wght@500;600;700&family=Material+Symbols+Rounded:opsz,wght,FILL,GRAD@24,400,0,0&display=swap');
    :root {{
        --ge-primary: {primary_blue};
        --ge-accent: {accent};
        --ge-warning: {warning_c};
        --ge-success: {success_c};
        --ge-danger: {danger_c};
        --ge-surface: {bg_card};
        --ge-elevated: {bg_secondary};
        --ge-text: {text_primary};
        --ge-text-muted: {text_secondary};
        --ge-transition: 150ms ease-out;
    }}
    /* Base typo — ne pas cibler [class*="css"] ni tous les div (sinon les widgets Streamlit / Base Web se chevauchent) */
    html, body {{
        font-family: 'Inter', 'Segoe UI', 'Arial', sans-serif !important;
        color: {text_primary} !important;
        font-size: 18px !important;
    }}
    .main .block-container, .stMarkdown {{
        color: {text_primary} !important;
    }}
    .stMarkdown p, .stMarkdown span, .stMarkdown li,
    [data-testid="stMarkdownContainer"] p,
    [data-testid="stMarkdownContainer"] span {{
        font-size: 18px !important;
        color: {text_primary} !important;
        line-height: 1.58 !important;
    }}
    label[data-testid="stWidgetLabel"] {{
        font-size: 18px !important;
        color: {text_primary} !important;
        line-height: 1.4 !important;
        font-weight: 600 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}
    body {{ font-weight: 400 !important; background: {bg_main} !important; }}
    /* Empêcher l'affichage du code HTML brut */
    pre, code {{
        display: none !important;
        visibility: hidden !important;
    }}
    /* Masquer les éléments qui affichent du code HTML brut */
    div[data-testid="stMarkdownContainer"] pre,
    div[data-testid="stMarkdownContainer"] code,
    .stMarkdown pre,
    .stMarkdown code {{
        display: none !important;
        visibility: hidden !important;
    }}
    /* S'assurer que le HTML est bien rendu */
    div[data-testid="stMarkdownContainer"] {{
        white-space: normal !important;
    }}
    /* Forcer le rendu HTML correct */
    div[data-testid="stMarkdownContainer"] p {{
        display: block !important;
        white-space: normal !important;
    }}
    .stApp {{ 
        background: {bg_main} !important;
        min-height: 100vh;
        color-scheme: dark;
    }}
    /* Masquer la barre noire Streamlit (Déployer, menu ⋮) */
    [data-testid="stHeader"] {{
        display: none !important;
        height: 0 !important;
        max-height: 0 !important;
        overflow: hidden !important;
        visibility: hidden !important;
    }}
    #MainMenu {{
        visibility: hidden !important;
        display: none !important;
    }}
    /* Remonter le hero : padding principal équivalent à la sidebar (logo ~ même niveau que le bandeau GOOD ENGINEERS) */
    section[data-testid="stSidebar"] .block-container {{
        padding-top: 0.85rem !important;
        padding-bottom: 1.5rem !important;
    }}
    .main .block-container {{
        padding-top: 0.85rem !important;
    }}
    @keyframes gradientShift {{
        0% {{ background-position: 0% 50%; }}
        50% {{ background-position: 100% 50%; }}
        100% {{ background-position: 0% 50%; }}
    }}
    
    /* SIDEBAR */
    .sidebar-logo-container {{ 
        text-align: center; 
        padding: 12px; 
        background: linear-gradient(180deg, {primary_blue} 0%, #0a1f33 100%) !important; 
        border-radius: 8px; 
        margin-bottom: 20px; 
        border: 1px solid rgba(255, 193, 7, 0.38);
        box-shadow: 0 4px 16px rgba(0,0,0,0.35);
        display: flex;
        align-items: center;
        justify-content: center;
        min-height: 120px;
        width: 100%;
        box-sizing: border-box;
    }}
    .sidebar-logo-container img {{
        max-width: 100% !important;
        max-height: 150px !important;
        width: 100% !important;
        height: auto !important;
        object-fit: contain !important;
        display: block;
    }}
    .sidebar-logo-text {{ 
        font-family: 'Montserrat', sans-serif; 
        font-size: 36px !important; 
        line-height: 1.2; 
        color: {accent} !important;
        font-weight: 900; 
        letter-spacing: 0.02em;
        width: 100%;
    }}
    @keyframes goldGlow {{
        0% {{ filter: brightness(1) drop-shadow(0 0 10px rgba(255, 193, 7, 0.5)); }}
        100% {{ filter: brightness(1.3) drop-shadow(0 0 20px rgba(255, 193, 7, 0.85)); }}
    }}
    
    /* Hero GOOD ENGINEERS — logo complet, centré, pacing type landing industrielle */
    @keyframes geHeroFadeIn {{
        from {{ opacity: 0; transform: translateY(14px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    .ge-hero {{
        position: relative;
        display: flex;
        flex-direction: column;
        width: 100%;
        max-width: 100%;
        min-height: clamp(110px, 16vh, 220px);
        margin: 0 auto clamp(8px, 1.2vw, 16px) auto;
        border-radius: 20px;
        overflow: hidden;
        box-sizing: border-box;
        border: 1px solid rgba(245, 184, 0, 0.42);
        box-shadow: 0 20px 56px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(245, 184, 0, 0.1);
    }}
    .ge-hero--masthead {{
        min-height: clamp(125px, 17vh, 260px);
    }}
    .ge-hero__layer--gradient {{
        position: absolute;
        inset: 0;
        z-index: 0;
        background: linear-gradient(165deg, #0F2A44 0%, #050d18 50%, #000000 100%);
    }}
    .ge-hero__layer--radial {{
        position: absolute;
        inset: 0;
        z-index: 0;
        pointer-events: none;
        background:
            radial-gradient(
                ellipse 65% 55% at 50% 42%,
                rgba(245, 184, 0, 0.16) 0%,
                rgba(255, 152, 0, 0.06) 42%,
                transparent 70%
            ),
            radial-gradient(
                ellipse 90% 45% at 50% 0%,
                rgba(245, 184, 0, 0.09) 0%,
                transparent 55%
            );
    }}
    .ge-hero__content {{
        position: relative;
        z-index: 1;
        flex: 1 1 auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        min-height: 0;
        padding: clamp(16px, 2.8vh, 36px) clamp(12px, 2.5vw, 22px) clamp(18px, 3.5vh, 42px);
        box-sizing: border-box;
    }}
    .ge-hero--masthead .ge-hero__content {{
        padding: clamp(10px, 1.6vh, 24px) clamp(10px, 2vw, 18px) clamp(14px, 2.6vh, 32px);
        justify-content: center;
    }}
    .ge-hero__sr-only {{
        position: absolute !important;
        width: 1px !important;
        height: 1px !important;
        padding: 0 !important;
        margin: -1px !important;
        overflow: hidden !important;
        clip: rect(0, 0, 0, 0) !important;
        white-space: nowrap !important;
        border: 0 !important;
        border-bottom: none !important;
        display: block !important;
    }}
    .ge-hero__masthead-wrap {{
        margin: 0 0 clamp(8px, 1.5vw, 14px) 0;
        padding: 0;
        border: 0;
        display: flex;
        justify-content: center;
        align-items: flex-start;
        width: 100%;
        max-width: 100%;
        box-sizing: border-box;
        animation: geHeroFadeIn 0.9s ease-out 0.06s both;
    }}
    .ge-hero__masthead {{
        display: block;
        width: auto;
        height: auto;
        max-width: min(420px, 88vw);
        max-height: min(17vh, 170px);
        object-fit: contain;
        object-position: center top;
        margin: 0 auto;
        filter: drop-shadow(0 16px 44px rgba(0, 0, 0, 0.55)) drop-shadow(0 0 32px rgba(245, 184, 0, 0.12));
    }}
    .ge-hero__mark {{
        margin-bottom: clamp(10px, 1.6vw, 18px);
        animation: geHeroFadeIn 0.85s ease-out 0.06s both;
    }}
    .ge-hero__mark svg {{
        display: block;
        width: clamp(60px, 14vw, 92px);
        height: auto;
        margin: 0 auto;
        filter: drop-shadow(0 0 20px rgba(245, 184, 0, 0.35)) drop-shadow(0 6px 24px rgba(0, 0, 0, 0.45));
    }}
    .ge-hero__title {{
        font-family: 'Oswald', 'Montserrat', 'Inter', sans-serif;
        font-weight: 700;
        font-size: clamp(22px, 5.2vw, 46px);
        letter-spacing: -0.03em;
        line-height: 1.14;
        padding-top: 0.06em;
        color: #F5B800;
        text-transform: uppercase;
        margin: 0 auto clamp(10px, 1.5vw, 16px) auto;
        text-shadow:
            0 0 42px rgba(245, 184, 0, 0.55),
            0 0 24px rgba(245, 184, 0, 0.4),
            0 4px 20px rgba(0, 0, 0, 0.68);
        animation: geHeroFadeIn 0.85s ease-out 0.12s both;
    }}
    .ge-hero__divider {{
        width: min(90%, 520px);
        height: 2px;
        margin: 0 auto clamp(10px, 1.5vw, 16px) auto;
        border: none;
        border-radius: 2px;
        align-self: center;
        background: linear-gradient(
            90deg,
            rgba(245, 184, 0, 0) 0%,
            rgba(245, 184, 0, 0.45) 15%,
            #F5B800 50%,
            rgba(245, 184, 0, 0.45) 85%,
            rgba(245, 184, 0, 0) 100%
        );
        box-shadow: 0 0 10px rgba(245, 184, 0, 0.35), 0 0 20px rgba(245, 184, 0, 0.2);
        animation: geHeroFadeIn 0.85s ease-out 0.18s both;
    }}
    .ge-hero__tagline {{
        font-family: 'Montserrat', 'Inter', sans-serif;
        font-weight: 800;
        font-size: clamp(10px, 1.95vw, 15px);
        letter-spacing: 0.34em;
        color: #F5B800;
        text-transform: uppercase;
        margin: 0 0 clamp(8px, 1.2vw, 14px) 0;
        line-height: 1.4;
        text-shadow: 0 0 18px rgba(245, 184, 0, 0.35);
        animation: geHeroFadeIn 0.85s ease-out 0.24s both;
    }}
    .ge-hero__subtitle {{
        font-family: 'Inter', 'Segoe UI', sans-serif;
        font-size: clamp(11px, 1.65vw, 15px);
        font-weight: 500;
        color: #A0A0A0;
        margin: 0 auto;
        max-width: 640px;
        width: 100%;
        line-height: 1.55;
        letter-spacing: 0.03em;
        text-align: center;
        align-self: center;
        box-sizing: border-box;
        animation: geHeroFadeIn 0.85s ease-out 0.32s both;
    }}
    /* Streamlit : hero via st.html (data-testid=stHtml) ou markdown — charte + pleine largeur */
    div[data-testid="stHtml"],
    div[data-testid="stHtml"]:has(.ge-hero) {{
        width: 100% !important;
        max-width: 100% !important;
    }}
    div[data-testid="stMarkdownContainer"]:has(.ge-hero),
    .stMarkdown:has(.ge-hero) {{
        width: 100% !important;
        max-width: 100% !important;
        margin-left: auto !important;
        margin-right: auto !important;
        text-align: center !important;
    }}
    div.element-container:has(.ge-hero) {{
        width: 100% !important;
    }}
    /* Pleine largeur du panneau principal + bandeau figé (sticky) jusqu'au ticker — même zone que le tracé utilisateur */
    section[data-testid="stMain"] div.element-container:has(.ge-hero--main-fixed) {{
        width: calc(100% + 2 * clamp(0.75rem, 4vw, 5rem)) !important;
        max-width: none !important;
        margin-left: calc(-1 * clamp(0.75rem, 4vw, 5rem)) !important;
        margin-right: calc(-1 * clamp(0.75rem, 4vw, 5rem)) !important;
        margin-top: calc(-1 * 0.85rem) !important;
        margin-bottom: 0 !important;
    }}
    section[data-testid="stMain"] div[data-testid="stHtml"]:has(.ge-hero--main-fixed) {{
        width: 100% !important;
        max-width: none !important;
    }}
    /* Figé en réalité via JS (components) — position ici = repli avant script + évite saut layout */
    .ge-hero--main-fixed {{
        position: relative !important;
        z-index: 100 !important;
        width: 100% !important;
        max-width: none !important;
        margin-left: 0 !important;
        margin-right: 0 !important;
        margin-bottom: 0 !important;
        border-radius: 0 !important;
        border-left: none !important;
        border-right: none !important;
        border-top: none !important;
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.5) !important;
        min-height: clamp(110px, 17vh, 250px) !important;
    }}
    .ge-hero--masthead.ge-hero--main-fixed {{
        min-height: clamp(120px, 18vh, 265px) !important;
    }}
    div[data-testid="stHtml"] .ge-hero h1.ge-hero__title,
    div[data-testid="stMarkdownContainer"] .ge-hero h1.ge-hero__title,
    .stMarkdown .ge-hero h1.ge-hero__title {{
        color: #F5B800 !important;
    }}
    div[data-testid="stHtml"] .ge-hero p.ge-hero__tagline,
    div[data-testid="stMarkdownContainer"] .ge-hero p.ge-hero__tagline,
    .stMarkdown .ge-hero p.ge-hero__tagline {{
        color: #F5B800 !important;
    }}
    div[data-testid="stHtml"] .ge-hero p.ge-hero__subtitle,
    div[data-testid="stMarkdownContainer"] .ge-hero p.ge-hero__subtitle,
    .stMarkdown .ge-hero p.ge-hero__subtitle {{
        color: #A0A0A0 !important;
        text-align: center !important;
        margin-left: auto !important;
        margin-right: auto !important;
    }}
    @media (max-width: 768px) {{
        section[data-testid="stMain"] div.element-container:has(.ge-hero--main-fixed) {{
            width: calc(100% + 2 * 0.75rem) !important;
            margin-left: -0.75rem !important;
            margin-right: -0.75rem !important;
        }}
        .ge-hero--main-fixed {{
            min-height: clamp(105px, 22vh, 220px) !important;
        }}
        .ge-hero--masthead.ge-hero--main-fixed {{
            min-height: clamp(118px, 24vh, 235px) !important;
        }}
        .ge-hero:not(.ge-hero--main-fixed) {{
            border-radius: 14px;
        }}
        .ge-hero__content {{
            padding: clamp(14px, 4vw, 28px) 12px clamp(16px, 5vw, 32px);
        }}
        .ge-hero--masthead .ge-hero__content {{
            padding: clamp(10px, 3vw, 22px) 10px clamp(14px, 4vw, 28px);
        }}
        .ge-hero__masthead {{
            max-width: min(360px, 94vw);
            max-height: min(16vh, 160px);
        }}
        .ge-hero__mark svg {{
            width: clamp(52px, 15vw, 84px);
        }}
        .ge-hero__tagline {{
            letter-spacing: 0.18em;
            font-size: clamp(9px, 2.8vw, 12px);
        }}
    }}
    @media (min-width: 1100px) {{
        .ge-hero__masthead {{
            max-width: min(420px, 44vw);
            max-height: min(17vh, 170px);
        }}
    }}
    
    /* Bandeau / en-tête contrôle minière */
    .hero-banner {{ 
        background: linear-gradient(168deg, #0F2A44 0%, #060d16 55%, #000000 100%); 
        padding: 9px 0; 
        border-radius: 8px; 
        border: 2px solid rgba(255, 193, 7, 0.55); 
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.55), inset 0 1px 0 rgba(255, 193, 7, 0.1);
        margin-bottom: 10px; 
        overflow: hidden; 
        white-space: nowrap; 
        position: relative; 
        min-height: 42px;
        max-width: 100%;
        box-sizing: border-box;
    }}
    .hero-banner::before {{
        content: '';
        position: absolute;
        inset: 0;
        background: radial-gradient(ellipse 80% 70% at 50% 40%, rgba(255, 193, 7, 0.07) 0%, transparent 55%);
        pointer-events: none;
    }}
    .marquee-text {{ 
        display: inline-block; 
        font-family: 'Montserrat', sans-serif; 
        font-size: clamp(14px, 2.6vw, 32px); 
        font-weight: 900; 
        color: {accent}; 
        text-transform: uppercase; 
        padding-left: 100%; 
        animation: scroll-left 35s linear infinite; 
        letter-spacing: clamp(1px, 0.35vw, 3px);
        line-height: 1.15;
    }}
    .gold-text {{ 
        color: {accent}; 
        font-weight: 900 !important;
        font-size: clamp(15px, 3vw, 38px);
        letter-spacing: clamp(1px, 0.45vw, 4px);
    }}
    @keyframes scroll-left {{ 0% {{ transform: translateX(0); }} 100% {{ transform: translateX(-100%); }} }}
    @media (max-width: 768px) {{
        .hero-banner {{
            padding: 6px 0 !important;
            min-height: 34px !important;
        }}
        .marquee-text {{
            font-size: 15px !important;
            letter-spacing: 1px !important;
        }}
        .gold-text {{
            font-size: 17px !important;
            letter-spacing: 2px !important;
        }}
    }}
    

    /* Navigation par onglets — style poste de contrôle premium */
    .stTabs [data-baseweb="tab-list"] {{
        display: flex;
        width: 100%;
        gap: 5px;
        background: rgba(15, 42, 68, 0.8) !important;
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        padding: 10px 12px;
        border-radius: 14px;
        border: 1px solid rgba(245, 184, 0, 0.22);
        box-shadow: 0 4px 24px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.04);
        flex-wrap: wrap;
        margin-bottom: 16px;
    }}
    .stTabs [data-baseweb="tab"] {{
        flex-grow: 1;
        min-height: 58px;
        background: rgba(47, 47, 47, 0.6) !important;
        backdrop-filter: blur(6px);
        -webkit-backdrop-filter: blur(6px);
        color: {text_secondary} !important;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 10px;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        font-size: 13px !important;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        transition: all 180ms ease-out;
        padding: 10px 8px !important;
        white-space: nowrap;
    }}

    .stTabs [data-baseweb="tab"]:hover {{
        background: rgba(70, 70, 70, 0.75) !important;
        color: {text_primary} !important;
        border-color: rgba(245, 184, 0, 0.4) !important;
        box-shadow: 0 4px 16px rgba(245, 184, 0, 0.12);
        transform: translateY(-1px);
    }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(135deg, {accent} 0%, #e6a800 100%) !important;
        color: {primary_blue} !important;
        border-color: {accent} !important;
        font-weight: 900;
        box-shadow: 0 4px 18px rgba(245, 184, 0, 0.45), 0 0 0 1px rgba(245, 184, 0, 0.6);
        transform: translateY(-2px);
    }}
    .stTabs [aria-selected="true"] p, .stTabs [aria-selected="true"] span {{
        color: {primary_blue} !important;
        font-weight: 900 !important;
    }}
    /* Indicateur soulignement — on masque l'original Streamlit */
    .stTabs [data-baseweb="tab-highlight"] {{
        display: none !important;
    }}
    .stTabs [data-baseweb="tab-border"] {{
        display: none !important;
    }}

    /* Cartes KPI / contenu — glassmorphism industriel */
    .content-card {{
        background: rgba(30, 35, 45, 0.72) !important;
        backdrop-filter: blur(14px) !important;
        -webkit-backdrop-filter: blur(14px) !important;
        padding: 24px 28px;
        border-radius: 16px;
        border: 1px solid rgba(245, 184, 0, 0.14);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.38), inset 0 1px 0 rgba(255,255,255,0.05);
        margin-bottom: 20px;
        transition: box-shadow 180ms ease-out, border-color 180ms ease-out, transform 180ms ease-out;
    }}
    .content-card:hover {{
        box-shadow: 0 12px 40px rgba(0, 0, 0, 0.48);
        border-color: rgba(245, 184, 0, 0.32);
        transform: translateY(-2px);
    }}
    .kpi-card {{
        background: rgba(20, 28, 42, 0.80) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 18px 22px;
        box-shadow: 0 4px 20px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.04);
        border-left: 4px solid {accent};
        transition: box-shadow 180ms ease-out, border-color 180ms ease-out, transform 180ms ease-out;
    }}
    .kpi-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 28px rgba(0,0,0,0.38);
        border-color: rgba(245, 184, 0, 0.30);
    }}
    
    /* Tableaux — en-têtes collants, zébrage discret */
    [data-testid="stDataFrame"] {{ 
        border: 1px solid {border_color}; 
        border-radius: 8px; 
        overflow: auto;
        background: {bg_card} !important;
        max-width: 100%;
        box-sizing: border-box;
    }}
    [data-testid="stDataFrame"] thead th {{
        position: sticky !important;
        top: 0 !important;
        z-index: 4 !important;
    }}
    @media (max-width: 768px) {{
        [data-testid="stDataFrame"] {{
            font-size: 12px !important;
        }}
        [data-testid="stDataFrame"] table {{
            display: block;
            overflow-x: auto;
            white-space: nowrap;
        }}
    }}
    thead tr th {{ 
        background: {primary_blue} !important; 
        color: {text_primary} !important; 
        font-family: 'Inter', 'Segoe UI', sans-serif !important; 
        text-transform: uppercase; 
        font-size: clamp(12px, 1.4vw, 15px) !important; 
        font-weight: 700;
        padding: 12px 14px !important;
        border-bottom: 2px solid {accent};
        letter-spacing: 0.06em;
    }}
    tbody tr:nth-child(even) {{
        background-color: {bg_zebra} !important;
    }}
    tbody tr:nth-child(odd) {{
        background-color: {bg_card} !important;
    }}
    tbody tr:hover {{
        background-color: {bg_hover} !important;
        transition: background-color var(--ge-transition);
    }}
    tbody td {{
        font-size: 17px !important;
        color: {text_primary} !important;
        padding: 12px !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}
    
    /* Hiérarchie boutons : primaire = jaune sécurité, secondaire = gris industriel */
    button[data-testid="baseButton-primary"],
    .stButton > button[kind="primary"] {{
        font-family: 'Inter', 'Segoe UI', sans-serif !important; 
        font-weight: 800 !important; 
        font-size: 16px !important;
        border-radius: 8px !important; 
        text-transform: uppercase; 
        letter-spacing: 0.05em;
        background: linear-gradient(180deg, {accent} 0%, #D9A000 100%) !important;
        color: {primary_blue} !important;
        border: 1px solid rgba(245, 184, 0, 0.9) !important;
        padding: 12px 22px !important;
        min-height: 48px !important;
        transition: transform var(--ge-transition), box-shadow var(--ge-transition), filter var(--ge-transition) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
    }}
    button[data-testid="baseButton-primary"]:hover,
    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-1px);
        filter: brightness(1.06);
        box-shadow: 0 4px 14px rgba(245, 184, 0, 0.35);
    }}
    button[data-testid="baseButton-secondary"],
    .stButton > button[kind="secondary"] {{
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        font-weight: 600 !important;
        font-size: 15px !important;
        border-radius: 8px !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        background: {bg_secondary} !important;
        color: {text_primary} !important;
        border: 1px solid {border_color} !important;
        padding: 11px 20px !important;
        min-height: 44px !important;
        transition: background-color var(--ge-transition), border-color var(--ge-transition), color var(--ge-transition) !important;
    }}
    button[data-testid="baseButton-secondary"]:hover,
    .stButton > button[kind="secondary"]:hover {{
        background: {bg_hover} !important;
        border-color: rgba(245, 184, 0, 0.35) !important;
        color: {text_primary} !important;
    }}
    /* Boutons Streamlit sans kind explicite — traités comme primaires (actions terrain) */
    .stButton > button:not([kind="secondary"]) {{
        font-family: 'Inter', 'Segoe UI', sans-serif !important; 
        font-weight: 800 !important; 
        font-size: 16px !important;
        border-radius: 8px !important; 
        text-transform: uppercase; 
        background: linear-gradient(180deg, {accent} 0%, #D9A000 100%) !important;
        color: {primary_blue} !important;
        border: 1px solid rgba(245, 184, 0, 0.9) !important;
        transition: transform var(--ge-transition), box-shadow var(--ge-transition), filter var(--ge-transition) !important;
    }}
    .stButton > button:not([kind="secondary"]):hover {{
        transform: translateY(-1px);
        filter: brightness(1.06);
    }}
    
    /* Encarts taux / live */
    .rate-box {{ 
        background: {bg_card} !important; 
        color: {accent}; 
        padding: 14px; 
        border-radius: 8px; 
        text-align: center; 
        margin-bottom: 10px; 
        font-family: 'Inter', 'Segoe UI', sans-serif !important; 
        font-size: 17px !important;
        border: 1px solid {border_color};
        border-left: 4px solid {accent};
        box-shadow: 0 2px 12px rgba(0,0,0,0.2);
    }}
    
    /* Titres — lisibilité maximale (hors hero : sr-only / titre éviter bordure + inline fantôme) */
    h1:not(.ge-hero__title):not(.ge-hero__sr-only) {{
        color: {text_primary} !important;
        font-size: clamp(32px, 4vw, 48px) !important;
        font-weight: 800 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        letter-spacing: -0.02em;
        line-height: 1.2;
        border-bottom: 2px solid {accent};
        padding-bottom: 8px;
        display: inline-block;
    }}
    h2 {{
        color: {text_primary} !important;
        font-size: clamp(26px, 3vw, 36px) !important;
        font-weight: 700 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        letter-spacing: -0.01em;
        line-height: 1.25;
    }}
    h3 {{
        color: {text_primary} !important;
        font-size: clamp(20px, 2.2vw, 28px) !important;
        font-weight: 700 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}
    h4 {{
        color: {text_secondary} !important;
        font-size: clamp(18px, 1.8vw, 22px) !important;
        font-weight: 600 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}
    
    /* Métriques tableau de bord */
    [data-testid="stMetricContainer"] {{
        background: {bg_card} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        box-shadow: 0 2px 10px rgba(0,0,0,0.18);
        border-left: 3px solid {accent};
    }}
    [data-testid="stMetricValue"] {{
        font-weight: 800;
        color: {accent} !important;
        font-size: clamp(28px, 3.5vw, 40px) !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}
    [data-testid="stMetricLabel"] {{
        font-size: 18px !important;
        color: {text_secondary} !important;
        font-weight: 600 !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }}
    
    /* Champs & listes — surfaces sombres, focus jaune sécurité */
    .stSelectbox, .stTextInput, .stNumberInput {{
        border-radius: 8px;
    }}
    [data-baseweb="select"] > div {{
        background: {bg_secondary} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        transition: border-color var(--ge-transition), box-shadow var(--ge-transition) !important;
    }}
    [data-baseweb="select"] > div:hover {{
        border-color: rgba(245, 184, 0, 0.45) !important;
    }}
    [data-baseweb="select"]:focus-within > div {{
        border-color: {accent} !important;
        box-shadow: 0 0 0 2px rgba(245, 184, 0, 0.2);
    }}
    div[data-baseweb="select"] span {{
        color: {text_primary} !important;
        font-weight: 600 !important;
        font-size: 16px !important;
    }}
    ul[role="listbox"], [data-baseweb="popover"], [data-baseweb="menu"] {{
        background: {bg_card} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        box-shadow: 0 10px 32px rgba(0, 0, 0, 0.45) !important;
    }}
    ul[role="listbox"] li, [data-baseweb="menu"] li {{
        color: {text_primary} !important;
        font-weight: 500 !important;
        padding: 10px 14px !important;
        border-bottom: 1px solid {border_color} !important;
    }}
    ul[role="listbox"] li:hover, [data-baseweb="menu"] li:hover {{
        background: {bg_hover} !important;
    }}
    ul[role="listbox"] li[aria-selected="true"], [data-baseweb="menu"] li[aria-selected="true"] {{
        background: rgba(245, 184, 0, 0.15) !important;
        color: {accent} !important;
        font-weight: 700 !important;
    }}
    div[data-baseweb="popover"] li[aria-selected="true"],
    div[data-baseweb="popover"] div[role="option"][aria-selected="true"] {{
        background: rgba(245, 184, 0, 0.2) !important;
        color: {accent} !important;
    }}
    /* Champs texte — ne pas forcer le layout des enfants Base Web (sinon chevauchement icône / libellé / texte brut) */
    div[data-baseweb="input"] {{
        background-color: {bg_secondary} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
        min-height: 44px !important;
    }}
    /* Glyphes Material Symbols des widgets Streamlit (sinon noms d'icônes visibles, ex. arrow_right) */
    .material-symbols-rounded,
    .stApp span[class*="material-symbols"] {{
        font-family: "Material Symbols Rounded", sans-serif !important;
        font-weight: 400 !important;
        font-style: normal !important;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
        letter-spacing: normal !important;
        text-transform: none !important;
        -webkit-font-smoothing: antialiased !important;
    }}
    div[data-baseweb="input"] input {{
        font-size: 16px !important;
        line-height: 1.25 !important;
        color: {text_primary} !important;
        background: transparent !important;
        border: none !important;
        flex: 1 1 auto !important;
        min-width: 0 !important;
    }}
    input[type="text"], input[type="password"], input[type="number"], textarea {{
        font-size: 16px !important;
        line-height: 1.25 !important;
        color: {text_primary} !important;
        background-color: {bg_secondary} !important;
        border: 1px solid {border_color} !important;
        border-radius: 8px !important;
    }}
    textarea {{ min-height: 5rem !important; }}
    
    /* Expanders — ne pas forcer font-family sur l'en-tête (sinon la flèche Material devient du texte _arrow_right) */
    .streamlit-expanderHeader {{
        background: {bg_card} !important;
        border-radius: 8px;
        padding: 12px 14px;
        font-weight: 700;
        color: {text_primary} !important;
        border: 1px solid {border_color};
        border-left: 4px solid {accent};
        font-size: 16px !important;
        transition: background-color var(--ge-transition), border-color var(--ge-transition);
    }}
    .streamlit-expanderHeader:hover {{
        background: {bg_secondary} !important;
    }}
    .streamlit-expanderHeader p,
    .streamlit-expanderHeader [data-testid="stMarkdownContainer"] {{
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        color: {text_primary} !important;
    }}
    .streamlit-expanderHeader .material-symbols-rounded,
    .streamlit-expanderHeader span[class*="material-symbols"] {{
        font-family: "Material Symbols Rounded", sans-serif !important;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
    }}
    
    /* Sidebar — fond bleu industriel, séparation nette       Streamlit replie la sidebar (min-width 0 + translateX) quand l'état « replié » est
       mémorisé (localStorage) ; le bouton pour rouvrir est dans stHeader, masqué par le thème.
       Forcer largeur + transform évite la disparition sur le domaine de prod vs localhost. */
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {primary_blue} 0%, #0c1f30 100%) !important;
        border-right: 1px solid {border_color};
        min-width: min(21rem, 90vw) !important;
        max-width: min(28rem, 40vw) !important;
        transform: translateX(0) !important;
        visibility: visible !important;
        transition: transform 0.28s ease, opacity 0.25s ease, flex-basis 0.28s ease,
            min-width 0.28s ease, max-width 0.28s ease, width 0.28s ease,
            padding 0.22s ease, border-width 0.2s ease !important;
    }}
    /* Pas de « section … span » global : cela écrase les icônes Material (expander, widgets) avec Inter !important */
    section[data-testid="stSidebar"] p,
    section[data-testid="stSidebar"] .stMarkdown span,
    section[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] span,
    section[data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {{
        color: {text_primary} !important;
        font-size: 18px !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
        line-height: 1.6 !important;
    }}
    section[data-testid="stSidebar"] .material-symbols-rounded,
    section[data-testid="stSidebar"] span[class*="material-symbols"] {{
        font-family: "Material Symbols Rounded", sans-serif !important;
        font-variation-settings: "FILL" 0, "wght" 400, "GRAD" 0, "opsz" 24 !important;
        letter-spacing: normal !important;
        font-style: normal !important;
    }}
    section[data-testid="stSidebar"] input {{ 
        color: {text_primary} !important; 
        font-size: 18px !important;
        background-color: {bg_secondary} !important;
        border: 1px solid {border_color} !important;
    }}
    
    /* Alertes Streamlit — mode sombre, codes couleur terrain */
    div[data-testid="stAlert"] {{
        border-radius: 8px !important;
        border: 1px solid {border_color} !important;
        background: {bg_card} !important;
    }}
    div[data-testid="stAlert"] p, div[data-testid="stAlert"] div {{
        color: {text_primary} !important;
    }}
    div[data-baseweb="notification"] {{
        border-radius: 8px !important;
    }}
    .stInfo, [data-testid="stNotification"] {{
        border-left: 4px solid {accent} !important;
        background: {bg_card} !important;
    }}
    .stSuccess {{
        border-left: 4px solid {success_c} !important;
        background: rgba(40, 167, 69, 0.12) !important;
    }}
    .stWarning {{
        border-left: 4px solid {warning_c} !important;
        background: rgba(255, 107, 0, 0.12) !important;
    }}
    .stError {{
        border-left: 4px solid {danger_c} !important;
        background: rgba(220, 53, 69, 0.12) !important;
    }}
    
    /* Statuts équipements / flotte (à utiliser en HTML/markdown) */
    .status-active {{ color: {success_c} !important; font-weight: 700 !important; }}
    .status-idle {{ color: {text_secondary} !important; font-weight: 600 !important; }}
    .status-maintenance {{ color: {warning_c} !important; font-weight: 700 !important; }}
    .status-breakdown {{ color: {danger_c} !important; font-weight: 700 !important; }}
    
    /* Graphiques */
    .js-plotly-plot {{
        border-radius: 8px;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.3);
        border: 1px solid {border_color};
    }}
    
    /* Animations pour la page d'accueil */
    @keyframes float {{
        0%, 100% {{ transform: translateY(0px); }}
        50% {{ transform: translateY(-20px); }}
    }}
    @keyframes rotate {{
        from {{ transform: rotate(0deg); }}
        to {{ transform: rotate(360deg); }}
    }}
    @keyframes pulse {{
        0%, 100% {{ opacity: 1; }}
        50% {{ opacity: 0.7; }}
    }}
    .animated-icon {{
        animation: float 3s ease-in-out infinite;
    }}
    .rotating-icon {{
        animation: rotate 10s linear infinite;
    }}
    .pulsing-text {{
        animation: pulse 2s ease-in-out infinite;
    }}
    {_ge_sidebar_collapse_extra}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# 2. CLASSES MÉTIERS & API
# ==============================================================================

# --- FONCTION API TAUX DE CHANGE ---
@st.cache_data(ttl=3600) # Mise en cache pour 1 heure pour ne pas ralentir l'app
def get_exchange_rates():
    """Récupère les taux USD, EUR, XOF en ligne"""
    try:
        # API Gratuite Open Exchange Rates (Base USD)
        url = "https://open.er-api.com/v6/latest/USD"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        if data['result'] == 'success':
            rates = data['rates']
            return {
                'USD': 1.0,
                'EUR': rates.get('EUR', 0.92),
                'CFA': rates.get('XOF', 610.0) # XOF est le code ISO du CFA
            }
    except:
        pass
    # Valeurs par défaut si pas d'internet
    return {'USD': 1.0, 'EUR': 0.92, 'CFA': 610.0}

@st.cache_data(ttl=900)
def get_weather(lat, lon):
    """Retourne la météo courante via Open-Meteo (sans clé API)."""
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat:.3f}&longitude={lon:.3f}&current_weather=true"
        )
        resp = requests.get(url, timeout=5)
        if resp.status_code == 200:
            cw = resp.json().get("current_weather", {})
            if cw:
                return {
                    "temp": cw.get("temperature"),
                    "windspeed": cw.get("windspeed"),
                    "winddir": cw.get("winddirection"),
                    "time": cw.get("time"),
                }
    except Exception:
        pass
    return None

@st.cache_data(ttl=300)  # Cache de 5 minutes pour le prix de l'or
def get_gold_price():
    """Récupère le prix de l'or en temps réel (once troy)"""
    try:
        # API gratuite pour le prix de l'or (MetalAPI)
        url = "https://api.metals.live/v1/spot/gold"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, dict) and 'price' in data:
                return {
                    'price_per_ounce_usd': float(data['price']),
                    'currency': 'USD',
                    'unit': 'once troy',
                    'timestamp': datetime.now()
                }
        
        # Alternative: API gratuite alternative
        url2 = "https://api.goldapi.io/api/xau/USD"
        headers = {
            'x-access-token': 'goldapi-io-free',  # Token gratuit
            'Content-Type': 'application/json'
        }
        response2 = requests.get(url2, headers=headers, timeout=5)
        if response2.status_code == 200:
            data2 = response2.json()
            if 'price' in data2:
                return {
                    'price_per_ounce_usd': float(data2['price']),
                    'currency': 'USD',
                    'unit': 'once troy',
                    'timestamp': datetime.now()
                }
    except:
        pass
    
    # Valeur par défaut si l'API n'est pas disponible
    return {
        'price_per_ounce_usd': 2000.0,  # Prix approximatif
        'currency': 'USD',
        'unit': 'once troy',
        'timestamp': datetime.now()
    }

@st.cache_data(ttl=3600)  # Cache de 1 heure pour les données historiques
def get_gold_historical_data(period='daily'):
    """
    Génère des données historiques simulées du prix de l'or
    period: 'daily' (30 derniers jours), 'weekly' (52 semaines), 'monthly' (12 mois), 'yearly' (10 ans)
    """
    current_price = get_gold_price()['price_per_ounce_usd']
    base_price = current_price * 0.85  # Prix de base (15% inférieur)
    
    if period == 'daily':
        days = 30
        dates = [(date.today() - timedelta(days=i)) for i in range(days, -1, -1)]
    elif period == 'weekly':
        weeks = 52
        dates = [(date.today() - timedelta(weeks=i)) for i in range(weeks, -1, -1)]
    elif period == 'monthly':
        months = 12
        dates = []
        for i in range(months, -1, -1):
            d = date.today()
            for _ in range(i):
                if d.month == 1:
                    d = d.replace(year=d.year - 1, month=12)
                else:
                    d = d.replace(month=d.month - 1)
            dates.append(d)
        dates = sorted(dates)
    else:  # yearly
        years = 10
        dates = []
        for i in range(years, -1, -1):
            d = date.today().replace(month=1, day=1)
            d = d.replace(year=d.year - i)
            dates.append(d)
    
    # Générer des prix avec variation réaliste (seed déterministe → graphique stable entre les refreshs)
    rng = random.Random(f"{period}-{date.today().isoformat()}")
    prices = []
    trend_factor = (current_price - base_price) / len(dates)

    for i, d in enumerate(dates):
        base = base_price + (trend_factor * i)
        variation = rng.uniform(-0.02, 0.02)
        cycle = 0.01 * math.sin(2 * math.pi * i / 7)
        price = base * (1 + variation + cycle)
        prices.append(round(price, 2))
    
    return {
        'dates': dates,
        'prices': prices,
        'period': period
    }

class AuditLog:
    """Classe pour représenter un log d'audit"""
    def __init__(self, action_type, entity_type, entity_id, entity_name, user, timestamp=None, changes=None, details=""):
        self.action_type = action_type  # "CREATE", "UPDATE", "DELETE", "DEACTIVATE", "REACTIVATE"
        self.entity_type = entity_type  # "EMPLOYEE", "MACHINE", "USER", "STOCK", etc.
        self.entity_id = entity_id  # ID de l'entité (matricule, ID machine, username, etc.)
        self.entity_name = entity_name  # Nom de l'entité
        self.user = user  # Utilisateur qui a effectué l'action
        self.timestamp = timestamp if timestamp else datetime.now()
        self.changes = changes if changes else {}  # Dictionnaire des changements (avant/après)
        self.details = details  # Détails supplémentaires

class AuditManager:
    """Gestionnaire des logs d'audit"""
    def __init__(self):
        self.logs = []
    
    def log_action(self, action_type, entity_type, entity_id, entity_name, user, changes=None, details=""):
        """Enregistre une action dans les logs d'audit"""
        log = AuditLog(action_type, entity_type, entity_id, entity_name, user, changes=changes, details=details)
        self.logs.append(log)
        # Garder seulement les 1000 derniers logs pour éviter la surcharge mémoire
        if len(self.logs) > 1000:
            self.logs = self.logs[-1000:]
    
    def get_logs_df(self, entity_type=None, user=None, action_type=None, start_date=None, end_date=None):
        """Retourne un DataFrame avec les logs filtrés"""
        filtered_logs = self.logs
        
        if entity_type:
            filtered_logs = [log for log in filtered_logs if log.entity_type == entity_type]
        if user:
            filtered_logs = [log for log in filtered_logs if log.user == user]
        if action_type:
            filtered_logs = [log for log in filtered_logs if log.action_type == action_type]
        if start_date:
            filtered_logs = [log for log in filtered_logs if log.timestamp >= start_date]
        if end_date:
            filtered_logs = [log for log in filtered_logs if log.timestamp <= end_date]
        
        # Trier par date décroissante (plus récent en premier)
        filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
        
        data = []
        for log in filtered_logs:
            changes_str = ""
            if log.changes:
                changes_list = []
                for key, value in log.changes.items():
                    if isinstance(value, dict) and 'before' in value and 'after' in value:
                        changes_list.append(f"{key}: {value['before']} → {value['after']}")
                    else:
                        changes_list.append(f"{key}: {value}")
                changes_str = " | ".join(changes_list)
            
            data.append({
                "Date/Heure": log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Utilisateur": log.user,
                "Action": log.action_type,
                "Type d'Entité": log.entity_type,
                "ID Entité": log.entity_id,
                "Nom Entité": log.entity_name,
                "Changements": changes_str,
                "Détails": log.details
            })
        
        if not data:
            return pd.DataFrame(columns=["Date/Heure", "Utilisateur", "Action", "Type d'Entité", "ID Entité", "Nom Entité", "Changements", "Détails"])
        
        return pd.DataFrame(data)
    
    def get_user_activity_summary(self, user):
        """Retourne un résumé des activités d'un utilisateur"""
        user_logs = [log for log in self.logs if log.user == user]
        summary = {
            "total_actions": len(user_logs),
            "creates": len([log for log in user_logs if log.action_type == "CREATE"]),
            "updates": len([log for log in user_logs if log.action_type == "UPDATE"]),
            "deletes": len([log for log in user_logs if log.action_type == "DELETE"]),
            "last_activity": max([log.timestamp for log in user_logs]) if user_logs else None
        }
        return summary

class UserManager:
    def __init__(self):
        # Permissions par défaut pour chaque rôle
        self.default_permissions = {
            "Administrateur": {
                "dashboard": True, "cycles": True, "carburant": True, "maintenance": True, "stock": True,
                "carte": True, "finance": True, "rh": True, "admin": True, "validation_operateur": True,
                "donnees_ingenierie": True, "messagerie": True, "sst": True,
                "can_add_users": True, "can_modify_users": True, "can_delete_users": True,
                "can_view_all": True, "can_export": True, "can_modify_data": True
            },
            "Ingenieur": {
                "dashboard": True, "cycles": True, "carburant": False, "maintenance": True, "stock": True,
                "carte": True, "finance": False, "rh": False, "admin": False, "validation_operateur": True,
                "donnees_ingenierie": True, "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": True, "can_export": True, "can_modify_data": True
            },
            "RH": {
                "dashboard": True, "cycles": False, "carburant": False, "maintenance": False, "stock": True,
                "carte": False, "finance": False, "rh": True, "admin": False, "validation_operateur": False,
                "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": False, "can_export": True, "can_modify_data": True
            },
            "Invite": {
                "dashboard": True, "cycles": True, "carburant": False, "maintenance": False, "stock": False,
                "carte": True, "finance": False, "rh": False, "admin": False, "validation_operateur": False,
                "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": False, "can_export": False, "can_modify_data": False
            },
            "Superviseur Production": {
                "dashboard": True, "cycles": True, "carburant": True, "maintenance": True, "stock": True,
                "carte": True, "finance": True, "rh": False, "admin": False, "validation_operateur": True,
                "donnees_ingenierie": True, "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": True, "can_export": True, "can_modify_data": True
            },
            "Superviseur Mecanicien": {
                "dashboard": True, "cycles": True, "carburant": True, "maintenance": True, "stock": True,
                "carte": True, "finance": False, "rh": False, "admin": False, "validation_operateur": True,
                "donnees_ingenierie": True, "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": True, "can_export": True, "can_modify_data": True
            },
            "Operateur": {
                "dashboard": False, "cycles": False, "carburant": False, "maintenance": False, "stock": False,
                "carte": False, "finance": False, "rh": False, "admin": False,
                "validation_operateur": True,  # Permission spécifique pour validation opérateur
                "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": False, "can_export": False, "can_modify_data": False
            },
            "Gestionnaire": {
                "dashboard": False, "cycles": False, "carburant": False, "maintenance": False, "stock": False,
                "carte": False, "finance": False, "rh": False, "admin": False,
                "donnees_ingenierie": False, "validation_operateur": False,
                "messagerie": False, "sst": False,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": False, "can_export": False, "can_modify_data": False,
                "platform_admin": True,
            },
        }
        
        self.users_db = []
        self._bootstrap_users()
    
    def persist_users(self):
        db = get_database()
        db["users_list"] = self.users_db
        save_database(db)

    def reload_users_from_disk(self):
        """Relit users_list depuis app_database.json (nouveaux comptes créés ailleurs / autre session)."""
        db = get_database()
        loaded = db.get("users_list")
        if loaded and isinstance(loaded, list) and len(loaded) > 0:
            self.users_db = loaded
        self._migrate_users()

    def _bootstrap_users(self):
        db = get_database()
        loaded = db.get("users_list")
        if loaded and isinstance(loaded, list) and len(loaded) > 0:
            self.users_db = loaded
        else:
            self.users_db = [
                {
                    "user": "admin",
                    "pass": "admin",
                    "role": "Administrateur",
                    "tenant_id": "default",
                    "permissions": self.default_permissions["Administrateur"].copy(),
                },
                {
                    "user": "gestionnaire",
                    "pass": "ge-plateforme",
                    "role": "Gestionnaire",
                    "tenant_id": "__platform__",
                    "permissions": self.default_permissions["Gestionnaire"].copy(),
                },
                {
                    "user": "rh",
                    "pass": "rh",
                    "role": "RH",
                    "tenant_id": "default",
                    "permissions": self.default_permissions["RH"].copy(),
                },
                {
                    "user": "visiteur",
                    "pass": "visiteur",
                    "role": "Invite",
                    "tenant_id": "default",
                    "permissions": self.default_permissions["Invite"].copy(),
                },
            ]
            self.persist_users()
        self._migrate_users()

    def _migrate_users(self):
        """Ajoute permissions, tenant_id et champs manquants."""
        changed = False
        for u in self.users_db:
            if not isinstance(u, dict):
                continue
            if "user" not in u or u.get("user") is None or str(u.get("user", "")).strip() == "":
                alt = u.get("username") or u.get("login")
                if alt is not None and str(alt).strip():
                    u["user"] = str(alt).strip()
                    changed = True
            elif isinstance(u.get("user"), str):
                su = u["user"].strip()
                if su != u["user"]:
                    u["user"] = su
                    changed = True
            if "pass" not in u and u.get("password") is not None:
                u["pass"] = u["password"]
                changed = True
            if "tenant_id" not in u:
                u["tenant_id"] = "default"
                changed = True
            if "permissions" not in u or not u["permissions"]:
                role = u.get("role", "Invite")
                if role in self.default_permissions:
                    u["permissions"] = self.default_permissions[role].copy()
                else:
                    u["permissions"] = {
                        "dashboard": True, "cycles": False, "carburant": False, "maintenance": False,
                        "carte": False, "finance": False, "rh": False, "admin": False,
                        "messagerie": True, "sst": True,
                        "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                        "can_view_all": False, "can_export": False, "can_modify_data": False,
                    }
                changed = True
            if u.get("role") == "Gestionnaire":
                if not u["permissions"].get("platform_admin"):
                    u["permissions"]["platform_admin"] = True
                    changed = True
            role = u.get("role", "Invite")
            tpl = self.default_permissions.get(role)
            if tpl and isinstance(u.get("permissions"), dict):
                for k, v in tpl.items():
                    if k not in u["permissions"]:
                        u["permissions"][k] = v
                        changed = True
        # Aucun compte Gestionnaire : en recréer un (copies Docker / JSON anciens sans ce rôle)
        if not any(u.get("role") == "Gestionnaire" for u in self.users_db):
            self.users_db.append(
                {
                    "user": "gestionnaire",
                    "pass": "ge-plateforme",
                    "role": "Gestionnaire",
                    "tenant_id": "__platform__",
                    "permissions": self.default_permissions["Gestionnaire"].copy(),
                }
            )
            changed = True
        # Réinitialiser le mot de passe plateforme (uniquement si la variable d'environnement est activée)
        _reset_g = os.environ.get("GOOD_ENGINEERS_RESET_GESTIONNAIRE", "").strip().lower()
        if _reset_g in ("1", "true", "yes", "oui"):
            for u in self.users_db:
                if (
                    u.get("role") == "Gestionnaire"
                    and str(u.get("user", "")).strip().lower() == "gestionnaire"
                ):
                    u["pass"] = _hash_password("ge-plateforme")
                    changed = True
        # Migrer les mots de passe en clair vers des hashes SHA-256
        for u in self.users_db:
            if not isinstance(u, dict):
                continue
            raw_pass = str(u.get("pass", ""))
            if raw_pass and not _is_hashed(raw_pass):
                u["pass"] = _hash_password(raw_pass)
                changed = True
        if changed:
            self.persist_users()
    
    def verify_login(self, username, password):
        u_in = (username or "").strip()
        if not u_in or not password:
            return None
        u_in_lower = u_in.lower()
        p_hashed = _hash_password(password)
        for u in self.users_db:
            if not isinstance(u, dict):
                continue
            u_name = str(u.get("user", "") or u.get("username") or u.get("login") or "").strip()
            if not u_name:
                continue
            stored = str(u.get("pass", u.get("password", "")))
            if u_name.lower() == u_in_lower and stored == p_hashed:
                return u
        return None
    
    def add_user(self, username, password, role, custom_permissions=None, tenant_id="default"):
        """Ajoute un nouvel utilisateur avec permissions (rattaché à une entreprise / tenant)."""
        ul = (username or "").strip().lower()
        for u in self.users_db:
            if str(u.get("user", "")).strip().lower() == ul:
                return False
        
        if custom_permissions:
            permissions = custom_permissions
        elif role in self.default_permissions:
            permissions = self.default_permissions[role].copy()
        else:
            permissions = {
                "dashboard": True, "cycles": False, "carburant": False, "maintenance": False,
                "carte": False, "finance": False, "rh": False, "admin": False,
                "messagerie": True, "sst": True,
                "can_add_users": False, "can_modify_users": False, "can_delete_users": False,
                "can_view_all": False, "can_export": False, "can_modify_data": False
            }
        
        user_entry = {
            "user": username.strip(),
            "pass": _hash_password(password),
            "role": role,
            "tenant_id": _safe_tenant_id(tenant_id),
            "permissions": permissions
        }

        self.users_db.append(user_entry)
        self.persist_users()
        return True
    
    def update_user(self, username, password=None, role=None, permissions=None):
        """Met à jour un utilisateur existant"""
        un = (username or "").strip().lower()
        for u in self.users_db:
            if not isinstance(u, dict):
                continue
            u_name = str(u.get("user", "") or u.get("username") or "").strip().lower()
            if u_name == un:
                if password:
                    u['pass'] = _hash_password(password)
                if role:
                    u['role'] = role
                    if role in self.default_permissions:
                        u['permissions'] = self.default_permissions[role].copy()
                if permissions:
                    u['permissions'] = permissions
                self.persist_users()
                return True
        return False
    
    def delete_user(self, username):
        """Supprime un utilisateur (comptes protégés)."""
        if username in ("admin", "gestionnaire"):
            return False
        self.users_db = [u for u in self.users_db if u['user'] != username]
        self.persist_users()
        return True
    
    def get_user(self, username):
        """Retourne un utilisateur par son nom (insensible à la casse, comme la connexion)."""
        un = (username or "").strip()
        if not un:
            return None
        ul = un.lower()
        for u in self.users_db:
            if not isinstance(u, dict):
                continue
            u_name = str(u.get("user", "") or u.get("username") or u.get("login") or "").strip().lower()
            if u_name == ul:
                return u
        return None
    
    def get_users_df(self):
        """Retourne un DataFrame avec tous les utilisateurs (sans les mots de passe)"""
        data = []
        for u in self.users_db:
            perms = u.get('permissions', {})
            data.append({
                "Utilisateur": u['user'],
                "Rôle": u['role'],
                "Entreprise (id)": u.get("tenant_id", "default"),
                "Dashboard": "✅" if perms.get('dashboard') else "❌",
                "Cycles": "✅" if perms.get('cycles') else "❌",
                "Carburant": "✅" if perms.get('carburant') else "❌",
                "Maintenance": "✅" if perms.get('maintenance') else "❌",
                "Stock": "✅" if perms.get('stock') else "❌",
                "Carte": "✅" if perms.get('carte') else "❌",
                "Finance": "✅" if perms.get('finance') else "❌",
                "RH": "✅" if perms.get('rh') else "❌",
                "Admin": "✅" if perms.get('admin') else "❌",
                "Export": "✅" if perms.get('can_export') else "❌",
                "Modifier": "✅" if perms.get('can_modify_data') else "❌"
            })
        return pd.DataFrame(data)

    def users_in_current_tenant(self):
        """Utilisateurs rattachés au même tenant que la session (hors console plateforme)."""
        try:
            tid = _safe_tenant_id(st.session_state.get("tenant_id", "default"))
        except Exception:
            tid = "default"
        return [u for u in self.users_db if _safe_tenant_id(u.get("tenant_id", "default")) == tid]


def render_change_own_password_form(user_mgr, key_prefix="pwd_self"):
    """Chaque utilisateur entreprise peut changer son propre mot de passe (après saisie de l'ancien)."""
    me = st.session_state.get("username")
    if not me:
        st.error("Session invalide.")
        return
    with st.form(f"form_own_pwd_{key_prefix}"):
        st.caption("Réservé à votre compte — les administrateurs peuvent aussi réinitialiser les mots de passe dans l'onglet **ADMIN**.")
        cur = st.text_input("Mot de passe actuel", type="password", key=f"{key_prefix}_cur")
        nw = st.text_input("Nouveau mot de passe", type="password", key=f"{key_prefix}_nw")
        nw2 = st.text_input("Confirmer le nouveau mot de passe", type="password", key=f"{key_prefix}_nw2")
        submitted = st.form_submit_button("Enregistrer le nouveau mot de passe", use_container_width=True)
    if submitted:
        if not cur or not nw:
            st.warning("Indiquez le mot de passe actuel et le nouveau.")
        elif nw != nw2:
            st.error("Les deux saisies du nouveau mot de passe ne correspondent pas.")
        elif len(nw.strip()) < 4:
            st.error("Le nouveau mot de passe doit contenir au moins 4 caractères.")
        elif not user_mgr.verify_login(me, cur):
            st.error("Mot de passe actuel incorrect.")
        elif user_mgr.update_user(me, password=nw):
            st.success("Mot de passe mis à jour.")
            st.rerun()
        else:
            st.error("Impossible de mettre à jour le mot de passe.")


class Employee:
    def __init__(self, name, role, team, shift_type="Standard", matricule=None, date_arrivee=None, statut="Actif", date_depart=None):
        # Numéro matricule personnalisé ou généré
        if matricule:
            self.matricule = matricule
        else:
            self.matricule = f"MAT-{random.randint(1000,9999)}"
        
        self.name = name
        self.role = role  # Operateur, Superviseur Production, Superviseur Mecanicien, Ingenieur, Mecanicien, Electricien
        self.team = team  # A, B, C, etc.
        self.shift_type = shift_type
        
        # Date d'arrivée pour calculer l'ancienneté
        if date_arrivee:
            self.date_arrivee = date_arrivee
        else:
            self.date_arrivee = date.today()
        
        # Statut de l'employé (Actif/Inactif) - pour soft delete
        self.statut = statut  # "Actif" ou "Inactif"
        self.date_depart = date_depart  # Date de départ si inactif
        
        # Performance et assignation
        self.performance_score = 0
        self.assigned_machine = "Aucune"
        self.production_tonnes = 0  # Production totale en tonnes
        
        # Suivi de présence
        self.presence_log = []  # Liste de dicts: {"date": "2024-01-15", "statut": "present", "retard": False}
        self.jours_sans_retard_absence = 0  # Compteur de jours consécutifs sans retard ni absence
        self.total_retards = 0
        self.total_absences = 0

class StaffManager:
    def __init__(self):
        # Employés initiaux avec dates d'arrivée
        today = date.today()
        self.staff = [
            Employee("Moussa Koné", "Operateur", "A", "3x8", "MAT-1001", today - timedelta(days=365)),
            Employee("Jean Ouedraogo", "Operateur", "B", "3x8", "MAT-1002", today - timedelta(days=180)),
            Employee("Fatou Diallo", "Ingenieur", "A", "Standard", "MAT-3001", today - timedelta(days=120)),
            Employee("Ibrahim Sano", "Mecanicien", "A", "Standard", "MAT-4001", today - timedelta(days=200)),
            Employee("Aminata Coulibaly", "Electricien", "B", "Standard", "MAT-4002", today - timedelta(days=150)),
            Employee("Boubacar Traoré", "Superviseur Production", "A", "3x8", "MAT-2002", today - timedelta(days=400)),
            Employee("Sékou Diarra", "Superviseur Mecanicien", "A", "Standard", "MAT-2003", today - timedelta(days=500))
        ]
        # S'assurer que tous les employés ont les attributs nécessaires (migration)
        self._migrate_employees()
    
    def _migrate_employees(self):
        """Initialise les attributs manquants pour les employés existants (migration)"""
        for emp in self.staff:
            if not hasattr(emp, 'production_tonnes'):
                emp.production_tonnes = 0
            if not hasattr(emp, 'presence_log'):
                emp.presence_log = []
            if not hasattr(emp, 'jours_sans_retard_absence'):
                emp.jours_sans_retard_absence = 0
            if not hasattr(emp, 'total_retards'):
                emp.total_retards = 0
            if not hasattr(emp, 'total_absences'):
                emp.total_absences = 0
            if not hasattr(emp, 'date_arrivee'):
                emp.date_arrivee = date.today()
            # Migration pour le statut (soft delete)
            if not hasattr(emp, 'statut'):
                emp.statut = "Actif"
            if not hasattr(emp, 'date_depart'):
                emp.date_depart = None
    
    def add_employee(self, name, role, team, shift_type, matricule=None, date_arrivee=None):
        """Ajoute un nouvel employé"""
        if not matricule:
            # Générer un matricule unique
            existing_matricules = [e.matricule for e in self.staff]
            base_num = 1000
            while f"MAT-{base_num}" in existing_matricules:
                base_num += 1
            matricule = f"MAT-{base_num}"
        
        self.staff.append(Employee(name, role, team, shift_type, matricule, date_arrivee, statut="Actif"))
        return True
    
    def desactiver_employee(self, matricule, date_depart=None):
        """Désactive un employé (soft delete) - garde toutes les données historiques"""
        emp = self.get_employee_by_matricule(matricule)
        if emp:
            emp.statut = "Inactif"
            if date_depart:
                emp.date_depart = date_depart
            else:
                emp.date_depart = date.today()
            return True
        return False
    
    def reactiver_employee(self, matricule):
        """Réactive un employé précédemment désactivé"""
        emp = self.get_employee_by_matricule(matricule)
        if emp:
            emp.statut = "Actif"
            emp.date_depart = None
            return True
        return False
    
    def get_active_staff(self):
        """Retourne uniquement les employés actifs"""
        return [e for e in self.staff if getattr(e, 'statut', 'Actif') == 'Actif']
    
    def get_inactive_staff(self):
        """Retourne uniquement les employés inactifs"""
        return [e for e in self.staff if getattr(e, 'statut', 'Actif') == 'Inactif']
    
    def remove_employee(self, matricule):
        """Supprime définitivement un employé de la base de données (hard delete)"""
        emp = self.get_employee_by_matricule(matricule)
        if emp:
            self.staff.remove(emp)
            return True
        return False
    
    def get_employee_by_matricule(self, matricule):
        """Retourne un employé par son matricule"""
        for e in self.staff:
            if e.matricule == matricule:
                return e
        return None
    
    def enregistrer_presence(self, matricule, date_presence, statut="present", retard=False):
        """Enregistre la présence d'un employé pour une date donnée"""
        emp = self.get_employee_by_matricule(matricule)
        if not emp:
            return False
        
        # Initialiser les attributs s'ils n'existent pas
        if not hasattr(emp, 'presence_log'):
            emp.presence_log = []
        if not hasattr(emp, 'jours_sans_retard_absence'):
            emp.jours_sans_retard_absence = 0
        if not hasattr(emp, 'total_retards'):
            emp.total_retards = 0
        if not hasattr(emp, 'total_absences'):
            emp.total_absences = 0
        
        date_str = date_presence.strftime("%Y-%m-%d") if isinstance(date_presence, date) else date_presence
        
        # Vérifier si déjà enregistré pour cette date
        for log in emp.presence_log:
            if log["date"] == date_str:
                # Mettre à jour
                log["statut"] = statut
                log["retard"] = retard
                self._recalculer_assiduite(emp)
                return True
        
        # Nouvel enregistrement
        emp.presence_log.append({
            "date": date_str,
            "statut": statut,  # "present", "absent", "retard"
            "retard": retard
        })
        
        if statut == "absent":
            emp.total_absences += 1
        elif retard:
            emp.total_retards += 1
        
        self._recalculer_assiduite(emp)
        return True
    
    def _recalculer_assiduite(self, emp):
        """Recalcule les jours consécutifs sans retard ni absence"""
        if not hasattr(emp, 'presence_log') or not emp.presence_log:
            emp.jours_sans_retard_absence = 0
            return
        
        # Trier par date décroissante
        sorted_logs = sorted(emp.presence_log, key=lambda x: x["date"], reverse=True)
        
        count = 0
        today = date.today()
        
        for log in sorted_logs:
            log_date = datetime.strptime(log["date"], "%Y-%m-%d").date()
            # Ne compter que les jours passés
            if log_date > today:
                continue
            
            if log["statut"] == "present" and not log["retard"]:
                count += 1
            else:
                break
        
        emp.jours_sans_retard_absence = count
    
    def ajouter_production(self, matricule, tonnes):
        """Ajoute de la production à un opérateur"""
        emp = self.get_employee_by_matricule(matricule)
        if emp:
            # Initialiser l'attribut s'il n'existe pas
            if not hasattr(emp, 'production_tonnes'):
                emp.production_tonnes = 0
            if not hasattr(emp, 'performance_score'):
                emp.performance_score = 0
            
            emp.production_tonnes += tonnes
            emp.performance_score += tonnes
            return True
        return False
    
    def get_all_staff_df(self, statut_filter=None):
        """Retourne un DataFrame avec tous les employés (ou filtrés par statut)"""
        data = []
        today = date.today()
        
        for e in self.staff:
            # Filtrer par statut si demandé
            statut_emp = getattr(e, 'statut', 'Actif')
            if statut_filter and statut_emp != statut_filter:
                continue
            
            # Utiliser getattr avec valeurs par défaut pour compatibilité
            date_arrivee = getattr(e, 'date_arrivee', today)
            production_tonnes = getattr(e, 'production_tonnes', 0)
            jours_sans = getattr(e, 'jours_sans_retard_absence', 0)
            total_retards = getattr(e, 'total_retards', 0)
            total_absences = getattr(e, 'total_absences', 0)
            date_depart = getattr(e, 'date_depart', None)
            
            # Calculer l'ancienneté en jours
            anciennete_jours = (today - date_arrivee).days
            anciennete_annees = anciennete_jours / 365.25
            
            data.append({
                "Matricule": e.matricule,
                "Nom": e.name,
                "Rôle": e.role,
                "Équipe": e.team,
                "Shift": e.shift_type,
                "Statut": statut_emp,
                "Date Arrivée": date_arrivee.strftime("%Y-%m-%d"),
                "Date Départ": date_depart.strftime("%Y-%m-%d") if date_depart else "En cours",
                "Ancienneté (ans)": round(anciennete_annees, 1),
                "Production (T)": int(production_tonnes),
                "Jours Sans Retard/Absence": jours_sans,
                "Total Retards": total_retards,
                "Total Absences": total_absences,
                "Machine Assignée": getattr(e, 'assigned_machine', "Aucune")
            })
        
        # Si pas de données, retourner un DataFrame vide avec les colonnes définies
        if not data:
            return pd.DataFrame(columns=[
                "Matricule", "Nom", "Rôle", "Équipe", "Shift", "Statut", "Date Arrivée", "Date Départ",
                "Ancienneté (ans)", "Production (T)", "Jours Sans Retard/Absence",
                "Total Retards", "Total Absences", "Machine Assignée"
            ])
        
        return pd.DataFrame(data)
    
    def get_classement_anciennete(self):
        """Retourne les employés classés par ancienneté (plus ancien en premier)"""
        today = date.today()
        sorted_staff = sorted(self.staff, key=lambda e: getattr(e, 'date_arrivee', today))
        return sorted_staff
    
    def get_classement_production(self):
        """Retourne les opérateurs classés par production (décroissant)"""
        operateurs = [e for e in self.staff if e.role == "Operateur"]
        sorted_ops = sorted(operateurs, key=lambda e: getattr(e, 'production_tonnes', 0), reverse=True)
        return sorted_ops
    
    def get_classement_assiduite(self):
        """Retourne les opérateurs classés par jours sans retard/absence (décroissant)"""
        operateurs = [e for e in self.staff if e.role == "Operateur"]
        sorted_ops = sorted(operateurs, key=lambda e: getattr(e, 'jours_sans_retard_absence', 0), reverse=True)
        return sorted_ops
    
    def get_team_by_shift(self, shift_name):
        mapping = {"Matin": "A", "Soir": "B", "Nuit": "C"}
        target = mapping.get(shift_name, "A")
        return [e for e in self.staff if e.team == target]
    
    def assign_machine(self, operator_name, machine_id):
        for e in self.staff:
            if e.name == operator_name: 
                e.assigned_machine = machine_id
                return True
        return False
    
    def add_score(self, operator_name, tonnes):
        for e in self.staff:
            if e.name == operator_name: 
                e.performance_score += tonnes
                e.production_tonnes += tonnes
                return True
        return False

class MiningContract:
    """Représente un contrat minier"""
    def __init__(self, contract_id, name, contract_type, rate, start_date=None, somme_negociee=None, client_name=None, rate_currency="USD", original_rate=None):
        self.contract_id = contract_id  # ID du contrat
        self.name = name  # Nom du contrat (ex: "Contrat Mine A")
        self.contract_type = contract_type  # "BCM" ou "HOURLY"
        self.rate = rate  # Taux en USD (pour les calculs internes)
        self.rate_currency = rate_currency  # Devise du taux (USD, CFA, EUR)
        self.original_rate = original_rate if original_rate else rate  # Taux dans la devise d'origine
        self.somme_negociee = somme_negociee  # Montant négocié total du contrat (optionnel)
        self.somme_negociee_currency = "USD"  # Devise de la somme négociée
        self.client_name = client_name  # Nom de l'entreprise/mine cliente
        self.start_date = start_date if start_date else date.today()
        self.end_date = None
        self.active = True
        
        # Suivi des volumes/heures par période
        self.volume_jour = 0  # BCM transportés aujourd'hui
        self.volume_semaine = 0  # BCM transportés cette semaine
        self.volume_mois = 0  # BCM transportés ce mois
        self.volume_annee = 0  # BCM transportés cette année
        
        self.heures_jour = 0  # Heures travaillées aujourd'hui (pour contrats horaires)
        self.heures_semaine = 0  # Heures travaillées cette semaine
        self.heures_mois = 0  # Heures travaillées ce mois
        self.heures_annee = 0  # Heures travaillées cette année
        
        # Revenus calculés
        self.revenu_jour = 0
        self.revenu_semaine = 0
        self.revenu_mois = 0
        self.revenu_annee = 0
        
        # Machines associées au contrat
        self.machines_ids = []  # Liste des IDs de machines sous ce contrat
        
        # Conversion BCM : 1 tonne ≈ 0.7 BCM (variable selon densité du matériau)
        self.tonnes_to_bcm_factor = 0.7
        
        # Convertir le taux initial en USD si nécessaire
        # Le taux est déjà en USD si rate_currency n'est pas spécifié
        # Cette conversion sera gérée lors de la création via add_contract
    
    def update_rate(self, new_rate, currency="USD", exchange_rates=None):
        """Met à jour le taux du contrat avec conversion en USD"""
        if exchange_rates is None:
            # Taux par défaut si non fourni
            exchange_rates = get_exchange_rates()
        
        # Convertir en USD
        if currency == "USD":
            self.rate = new_rate
        elif currency == "EUR":
            self.rate = new_rate / exchange_rates['EUR']
        elif currency == "CFA":
            self.rate = new_rate / exchange_rates['CFA']
        else:
            self.rate = new_rate  # Par défaut, considérer comme USD
        
        self.original_rate = new_rate
        self.rate_currency = currency
        # Recalculer les revenus
        self._recalculate_revenue()
    
    def add_volume(self, bcm):
        """Ajoute du volume transporté (en BCM)"""
        self.volume_jour += bcm
        self.volume_semaine += bcm
        self.volume_mois += bcm
        self.volume_annee += bcm
        self._recalculate_revenue()
    
    def add_hours(self, hours):
        """Ajoute des heures travaillées (pour contrats horaires)"""
        self.heures_jour += hours
        self.heures_semaine += hours
        self.heures_mois += hours
        self.heures_annee += hours
        self._recalculate_revenue()
    
    def _recalculate_revenue(self):
        """Recalcule les revenus selon le type de contrat"""
        if self.contract_type == "BCM":
            self.revenu_jour = self.volume_jour * self.rate
            self.revenu_semaine = self.volume_semaine * self.rate
            self.revenu_mois = self.volume_mois * self.rate
            self.revenu_annee = self.volume_annee * self.rate
        elif self.contract_type == "HOURLY":
            self.revenu_jour = self.heures_jour * self.rate
            self.revenu_semaine = self.heures_semaine * self.rate
            self.revenu_mois = self.heures_mois * self.rate
            self.revenu_annee = self.heures_annee * self.rate
    
    def reset_daily(self):
        """Remet à zéro les compteurs journaliers (à appeler à minuit)"""
        self.volume_jour = 0
        self.heures_jour = 0
        self.revenu_jour = 0
    
    def reset_weekly(self):
        """Remet à zéro les compteurs hebdomadaires"""
        self.volume_semaine = 0
        self.heures_semaine = 0
        self.revenu_semaine = 0
    
    def reset_monthly(self):
        """Remet à zéro les compteurs mensuels"""
        self.volume_mois = 0
        self.heures_mois = 0
        self.revenu_mois = 0

def _mime_from_upload_name(filename: str) -> str:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"


class CompanyInfo:
    """Gère les informations de l'entreprise/mine cliente"""
    def __init__(self):
        self.company_name = "GOOD ENGINEERS"
        self.address = "Adresse de l'entreprise"
        self.phone = "+XXX XX XX XX XX"
        self.email = "contact@goodengineers.com"
        self.logo_path = None  # Chemin vers le logo (sera géré avec base64)
        self.logo_base64 = None  # Logo en base64 pour l'inclusion dans les factures
        self.logo_mime = "image/png"
        self.tax_id = "N° Fiscal: XXX-XXX-XXX"
        self.rccm = ""
        self.bank_info = "Banque: XXX | IBAN: XXX"
        # Cachet & signature (factures / documents PDF-HTML)
        self.stamp_base64 = None
        self.stamp_mime = "image/png"
        self.signature_base64 = None
        self.signature_mime = "image/png"
        self.signatory_title = ""
        self.signatory_name = ""
        self.document_stamp_legend = ""

    def set_logo_from_file(self, uploaded_file):
        """Convertit un fichier logo en base64"""
        import base64
        if uploaded_file:
            self.logo_base64 = base64.b64encode(uploaded_file.read()).decode()
            self.logo_path = uploaded_file.name
            self.logo_mime = _mime_from_upload_name(uploaded_file.name)
            return True
        return False

    def set_stamp_from_file(self, uploaded_file):
        import base64
        if uploaded_file:
            self.stamp_base64 = base64.b64encode(uploaded_file.read()).decode()
            self.stamp_mime = _mime_from_upload_name(uploaded_file.name)
            return True
        return False

    def set_signature_from_file(self, uploaded_file):
        import base64
        if uploaded_file:
            self.signature_base64 = base64.b64encode(uploaded_file.read()).decode()
            self.signature_mime = _mime_from_upload_name(uploaded_file.name)
            return True
        return False

# ==============================================================================
# BASE DE DONNÉES SQLITE - PERSISTANCE ABSOLUE (multi-entreprise / tenant)
# ==============================================================================
def _app_data_root():
    """Répertoire persistant des données (VPS, Docker). Variable d'environnement optionnelle."""
    root = os.environ.get("GOOD_ENGINEERS_DATA_DIR", "").strip()
    if root:
        p = os.path.abspath(os.path.expanduser(root))
        os.makedirs(p, exist_ok=True)
        return p
    # Par défaut : dossier de app.py (sinon un lancement depuis un autre cwd charge un mauvais app_database.json)
    try:
        return os.path.abspath(os.path.dirname(__file__))
    except NameError:
        return os.path.abspath(os.getcwd())


_APP_DATA_ROOT = _app_data_root()
TENANT_DATA_DIR = os.path.join(_APP_DATA_ROOT, "tenant_data")
LEGACY_DB_FILE = os.path.join(_APP_DATA_ROOT, "geo_data.db")


def _safe_tenant_id(tid):
    """Normalise l'id tenant. « __platform__ » reste réservé au rôle Gestionnaire (ne pas mapper sur default)."""
    raw = (tid or "default").strip()
    low = raw.lower()
    if low == "__platform__":
        return "__platform__"
    if low in ("", "none"):
        return "default"
    out = "".join(c for c in low if c.isalnum() or c in "-_")
    return out[:64] if out else "default"


def _collaboration_base_dir():
    """Dossier messagerie / SST / pièces jointes par tenant."""
    tid = _safe_tenant_id(st.session_state.get("tenant_id", "default"))
    root = os.path.join(TENANT_DATA_DIR, tid, "collaboration")
    os.makedirs(os.path.join(root, "shared_files"), exist_ok=True)
    os.makedirs(os.path.join(root, "sst_uploads"), exist_ok=True)
    return root


def _load_collab_messages():
    path = os.path.join(_collaboration_base_dir(), "messages.json")
    if not os.path.isfile(path):
        return {"messages": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "messages" not in data:
                return {"messages": []}
            return data
    except Exception:
        return {"messages": []}


def _save_collab_messages(data):
    path = os.path.join(_collaboration_base_dir(), "messages.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_sst_entries():
    path = os.path.join(_collaboration_base_dir(), "sst_records.json")
    if not os.path.isfile(path):
        return {"entries": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "entries" not in data:
                return {"entries": []}
            return data
    except Exception:
        return {"entries": []}


def _save_sst_entries(data):
    path = os.path.join(_collaboration_base_dir(), "sst_records.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_driver_safety_checks():
    """Contrôles terrain par conducteur : inspection véhicule, Take 5, test de frein (JSON par tenant)."""
    path = os.path.join(_collaboration_base_dir(), "sst_driver_checks.json")
    if not os.path.isfile(path):
        return {"records": []}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, dict) or "records" not in data:
                return {"records": []}
            return data
    except Exception:
        return {"records": []}


def _save_driver_safety_checks(data):
    path = os.path.join(_collaboration_base_dir(), "sst_driver_checks.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _message_visible_for_user(msg, username):
    if msg.get("kind") == "communique" and msg.get("to") == "__all__":
        return True
    if msg.get("kind") == "message" and msg.get("to") == "__team__":
        return True
    if msg.get("to") == username or msg.get("from") == username:
        return True
    return False


def _sub_tab_index(labels, label):
    return labels.index(label) if label in labels else -1


def _dl_key(*parts):
    h = hashlib.md5("|".join(str(p) for p in parts).encode("utf-8", errors="replace")).hexdigest()[:14]
    return f"k_{h}"


def render_messagerie_tab(user_mgr, user_info):
    """Messagerie interne, pièces jointes, communiqués admin, assistant SST (FAQ)."""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.subheader("💬 Messagerie & échanges")
    perms = (user_info or {}).get("permissions", {})
    me = st.session_state.get("username", "")
    is_admin = bool(perms.get("admin"))

    data = _load_collab_messages()
    msgs = data.get("messages", [])

    visible = [m for m in msgs if _message_visible_for_user(m, me)]
    visible.sort(key=lambda x: x.get("ts", ""), reverse=True)

    communs = [m for m in visible if m.get("kind") == "communique"]
    if communs:
        st.markdown("#### 📢 Communiqués")
        for c in communs[:15]:
            ts = c.get("ts", "")[:19].replace("T", " ")
            st.warning(f"**{c.get('from', '—')}** — {ts}\n\n{c.get('body', '')}")
            for att in c.get("attachments", []) or []:
                fp = os.path.join(_collaboration_base_dir(), att.get("relpath", ""))
                if os.path.isfile(fp):
                    with open(fp, "rb") as f:
                        st.download_button(
                            f"Télécharger : {att.get('name', 'fichier')}",
                            f.read(),
                            file_name=att.get("name", "piece_jointe"),
                            key=_dl_key("dlc", c.get("id"), att.get("name")),
                        )

    st.markdown("#### 💡 Assistant SST / rappels (FAQ)")
    with st.expander("Poser une question simple", expanded=False):
        q = st.text_input("Votre question", key="faq_chat_q", placeholder="Ex. EPI, casque, urgence…")
        if st.button("Obtenir une réponse indicative", key="faq_chat_go"):
            ql = (q or "").lower()
            if "casque" in ql or "epi" in ql:
                st.info(
                    "🔧 **EPI** : portez toujours le casque, chaussures de sécurité, gants adaptés "
                    "et lunettes sur zones à risque. Signalez tout équipement défectueux à votre chef d'équipe."
                )
            elif "urgence" in ql or "secours" in ql or "accident" in ql:
                st.error(
                    "🚨 **Urgence** : alertez immédiatement votre **superviseur** et le **poste sécurité / infirmerie** "
                    "selon la procédure du site. En cas de danger vital, contactez les secours conformément au plan SST."
                )
            elif "incendie" in ql or "feu" in ql:
                st.warning(
                    "🔥 **Feu** : déclenchez l'alerte, évacuez si demandé, utilisez les extincteurs **uniquement** "
                    "si vous êtes formé et en sécurité."
                )
            else:
                st.caption(
                    "Pour une consigne précise, utilisez l'onglet **SST** ou contactez votre **référent santé-sécurité**. "
                    "Ce panneau donne des rappels généraux, pas une procédure officielle."
                )

    st.markdown("#### ✉️ Nouveau message")
    others = [u["user"] for u in user_mgr.users_in_current_tenant() if u["user"] != me]
    dest_choices = ["Salon équipe (tous)"] + others
    dest_lbl = st.selectbox("Destinataire", dest_choices, key="msg_dest")
    if dest_lbl.startswith("Salon équipe"):
        dest_to = "__team__"
    else:
        dest_to = dest_lbl
    body = st.text_area("Message", key="msg_body", height=120, placeholder="Votre texte…")
    up = st.file_uploader("Pièce jointe (optionnel)", key="msg_file")
    if st.button("Envoyer", type="primary", key="msg_send"):
        if not (body or "").strip() and up is None:
            st.error("Saisissez un message ou joignez un fichier.")
        else:
            attachments = []
            if up is not None:
                safe = "".join(c for c in up.name if c.isalnum() or c in "._- ")[:120]
                rel = f"shared_files/{uuid.uuid4().hex}_{safe}"
                fp = os.path.join(_collaboration_base_dir(), rel)
                with open(fp, "wb") as f:
                    f.write(up.getbuffer())
                attachments.append({"name": up.name, "relpath": rel})
            mid = uuid.uuid4().hex
            rec = {
                "id": mid,
                "ts": datetime.now().isoformat(),
                "from": me,
                "to": dest_to,
                "kind": "message",
                "body": (body or "").strip(),
                "attachments": attachments,
            }
            data.setdefault("messages", []).append(rec)
            _save_collab_messages(data)
            st.success("Message envoyé.")
            st.rerun()

    if is_admin:
        st.markdown("---")
        st.markdown("#### 📢 Publier un communiqué (administrateur)")
        st.caption("Visible par **toute l'entreprise** dans cet espace.")
        c_title = st.text_input("Titre du communiqué", key="com_tit")
        c_body = st.text_area("Texte", key="com_body", height=140)
        c_up = st.file_uploader("Pièce jointe communiqué (PDF, image…)", key="com_file")
        if st.button("Publier le communiqué", key="com_pub"):
            if not (c_body or "").strip():
                st.error("Le texte du communiqué est requis.")
            else:
                data = _load_collab_messages()
                attachments = []
                if c_up is not None:
                    safe = "".join(c for c in c_up.name if c.isalnum() or c in "._- ")[:120]
                    rel = f"shared_files/{uuid.uuid4().hex}_{safe}"
                    fp = os.path.join(_collaboration_base_dir(), rel)
                    with open(fp, "wb") as f:
                        f.write(c_up.getbuffer())
                    attachments.append({"name": c_up.name, "relpath": rel})
                block = (f"**{c_title.strip()}**\n\n" if (c_title or "").strip() else "") + (c_body or "").strip()
                rec = {
                    "id": uuid.uuid4().hex,
                    "ts": datetime.now().isoformat(),
                    "from": me,
                    "to": "__all__",
                    "kind": "communique",
                    "body": block,
                    "attachments": attachments,
                }
                data.setdefault("messages", []).append(rec)
                _save_collab_messages(data)
                st.success("Communiqué publié.")
                st.rerun()

    st.markdown("#### Fil récent")
    for m in visible[:40]:
        if m.get("kind") == "communique":
            continue
        ts = m.get("ts", "")[:19].replace("T", " ")
        to_lbl = m.get("to", "")
        if to_lbl == "__team__":
            to_lbl = "Salon équipe"
        st.markdown(
            f"**{m.get('from', '?')}** → _{to_lbl}_ · _{ts}_\n\n{m.get('body', '')}",
            help=m.get("id"),
        )
        for att in m.get("attachments", []) or []:
            fp = os.path.join(_collaboration_base_dir(), att.get("relpath", ""))
            if os.path.isfile(fp):
                with open(fp, "rb") as f:
                    st.download_button(
                        f"⬇ {att.get('name', 'fichier')}",
                        f.read(),
                        file_name=att.get("name", "fichier"),
                        key=_dl_key("d", m.get("id"), att.get("name")),
                    )

    st.markdown('</div>', unsafe_allow_html=True)


def _sst_type_choices():
    """Types de fiches SST — ordre : documents terrain prioritaires en premier."""
    return [
        "Take 5 — contrôle avant tâche",
        "JHA — analyse des dangers du travail",
        "PTO / Inspection véhicule",
        "Inspection SST",
        "Incident / accident",
        "Presqu'accident (near miss)",
        "Formation / sensibilisation",
        "Arrêt sécurité",
        "Autre",
    ]


def _sst_entry_is_priority_terain(e):
    """Take 5, JHA, PTO / inspection véhicule (libellés historiques proches inclus)."""
    t = (e.get("type") or "").lower()
    if not t.strip():
        return False
    markers = (
        "take 5",
        "jha",
        "pto",
        "inspection véhicule",
        "inspection vehicule",
        "contrôle véhicule",
        "controle vehicule",
    )
    return any(m in t for m in markers)


def _safety_report_filter_by_period(items, date_key_candidates, ndays, today_d):
    """Filtre une liste de dicts sur une date ISO (champ date_* ou ts). ndays=None = tout."""
    if ndays is None:
        return list(items)
    cutoff = today_d - timedelta(days=ndays)
    out = []
    for e in items:
        raw = None
        for k in date_key_candidates:
            if e.get(k):
                raw = str(e.get(k))[:10]
                break
        if not raw:
            continue
        try:
            d = date.fromisoformat(raw)
            if d >= cutoff:
                out.append(e)
        except Exception:
            continue
    return out


def _safety_report_compute_metrics(entries, chk_records, ndays, today_d):
    """Calcule filtres + KPI + lignes de synthèse pour l'écran et le PDF."""
    today_d = today_d or date.today()
    ent_f = _safety_report_filter_by_period(entries, ("date_observation", "ts"), ndays, today_d)
    chk_f = _safety_report_filter_by_period(chk_records, ("date_controle", "ts"), ndays, today_d)
    tl = lambda s: (s or "").lower()
    n_inc = sum(
        1
        for e in ent_f
        if "incident" in tl(e.get("type")) or "accident" in tl(e.get("type"))
    )
    n_near = sum(
        1 for e in ent_f if "presqu" in tl(e.get("type")) or "near miss" in tl(e.get("type"))
    )
    n_arret = sum(1 for e in ent_f if "arrêt" in tl(e.get("type")) or "arret" in tl(e.get("type")))
    n_high = sum(1 for e in ent_f if (e.get("gravite") or "").strip() == "Élevée")
    n_form = sum(1 for e in ent_f if "formation" in tl(e.get("type")))
    n_prio_fiches = sum(1 for e in ent_f if _sst_entry_is_priority_terain(e))
    n_chk = len(chk_f)
    pct_complete = 0.0
    n_workers = 0
    sum_ins = sum_t5 = sum_br = 0
    if chk_f:
        df_chk = pd.DataFrame(chk_f)
        if "conducteur_nom" in df_chk.columns:
            n_workers = int(df_chk["conducteur_nom"].dropna().astype(str).str.strip().ne("").nunique())

        def _bcol(c):
            if c not in df_chk.columns:
                return 0
            return int(df_chk[c].fillna(False).astype(bool).sum())

        sum_ins = _bcol("inspection_vehicule")
        sum_t5 = _bcol("take5")
        sum_br = _bcol("test_frein")
        if len(df_chk) > 0:

            def _ok_row(r):
                return bool(r.get("inspection_vehicule")) and bool(r.get("take5")) and bool(r.get("test_frein"))

            pct_complete = 100.0 * sum(df_chk.apply(_ok_row, axis=1)) / len(df_chk)
    summary_rows = [
        {"Indicateur": "Période (jours)", "Valeur": str(ndays if ndays is not None else "Tout")},
        {"Indicateur": "Fiches SST", "Valeur": len(ent_f)},
        {"Indicateur": "Incidents / accidents", "Valeur": n_inc},
        {"Indicateur": "Presqu'accidents", "Valeur": n_near},
        {"Indicateur": "Gravité élevée", "Valeur": n_high},
        {"Indicateur": "Fiches terrain prioritaires", "Valeur": n_prio_fiches},
        {"Indicateur": "Arrêts sécurité", "Valeur": n_arret},
        {"Indicateur": "Formations / sensib.", "Valeur": n_form},
        {"Indicateur": "Lignes contrôles conducteur", "Valeur": n_chk},
        {"Indicateur": "Conducteurs distincts", "Valeur": n_workers},
        {"Indicateur": "Taux 3 contrôles (%)", "Valeur": round(pct_complete, 1)},
        {"Indicateur": "Somme inspections véh.", "Valeur": sum_ins},
        {"Indicateur": "Somme Take 5", "Valeur": sum_t5},
        {"Indicateur": "Somme tests frein", "Valeur": sum_br},
    ]
    return {
        "ent_f": ent_f,
        "chk_f": chk_f,
        "n_inc": n_inc,
        "n_near": n_near,
        "n_arret": n_arret,
        "n_high": n_high,
        "n_form": n_form,
        "n_prio_fiches": n_prio_fiches,
        "n_chk": n_chk,
        "n_workers": n_workers,
        "pct_complete": pct_complete,
        "sum_ins": sum_ins,
        "sum_t5": sum_t5,
        "sum_br": sum_br,
        "summary_rows": summary_rows,
    }


def _build_safety_report_pdf_bytes(m, period_label, today_d):
    """Génère un PDF UTF-8 (ReportLab + police DejaVu si disponible via matplotlib)."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    font_name = "Helvetica"
    try:
        import matplotlib

        _p = os.path.join(matplotlib.get_data_path(), "fonts", "ttf", "DejaVuSans.ttf")
        if os.path.isfile(_p):
            pdfmetrics.registerFont(TTFont("DejaVuSans", _p))
            font_name = "DejaVuSans"
    except Exception:
        pass

    styles = getSampleStyleSheet()
    title_st = ParagraphStyle(
        "RptTitle",
        parent=styles["Heading1"],
        fontName=font_name,
        fontSize=16,
        spaceAfter=12,
        textColor=colors.HexColor("#0F2A44"),
    )
    body_st = ParagraphStyle("RptBody", parent=styles["Normal"], fontName=font_name, fontSize=10, leading=14)
    h2_st = ParagraphStyle(
        "RptH2",
        parent=styles["Heading2"],
        fontName=font_name,
        fontSize=12,
        spaceAfter=8,
        textColor=colors.HexColor("#0F2A44"),
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.8 * cm,
        leftMargin=1.8 * cm,
        topMargin=1.8 * cm,
        bottomMargin=1.8 * cm,
        title="Rapport Safety",
    )
    story = []
    story.append(Paragraph("Rapport Safety — GOOD ENGINEERS OS", title_st))
    story.append(
        Paragraph(
            f"Date du rapport : {today_d.isoformat()} &mdash; Période sélectionnée : <b>{html.escape(str(period_label))}</b>",
            body_st,
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    sr = m["summary_rows"]
    data_pdf = [["Indicateur", "Valeur"]] + [[row["Indicateur"], str(row["Valeur"])] for row in sr]
    tbl = Table(data_pdf, colWidths=[10.5 * cm, 5.2 * cm])
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2A44")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), font_name),
                ("FONTSIZE", (0, 0), (-1, 0), 10),
                ("FONTNAME", (0, 1), (-1, -1), font_name),
                ("FONTSIZE", (0, 1), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#f5f5f5")]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 0.6 * cm))

    ent_f = m["ent_f"]
    if ent_f:
        story.append(Paragraph("Fiches SST — répartition par type (période)", h2_st))
        df_e = pd.DataFrame(ent_f)
        _types = df_e["type"] if "type" in df_e.columns else pd.Series(dtype=object)
        tc = _types.fillna("(Non renseigné)").astype(str).value_counts().head(20)
        tdata = [["Type de fiche", "Nombre"]] + [[str(k), str(int(v))] for k, v in tc.items()]
        tt = Table(tdata, colWidths=[12 * cm, 3.7 * cm])
        tt.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#F5B800")),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        story.append(tt)
        story.append(Spacer(1, 0.45 * cm))

        _zone_s = df_e["zone"] if "zone" in df_e.columns else pd.Series([""] * len(df_e))
        zn = _zone_s.fillna("").astype(str).str.strip()
        zn = zn[zn.ne("")]
        if len(zn) > 0:
            story.append(Paragraph("Zones / sites les plus cités (top 10)", h2_st))
            zc = zn.value_counts().head(10)
            zdata = [["Zone / site", "Nombre"]] + [[str(k), str(int(v))] for k, v in zc.items()]
            zt = Table(zdata, colWidths=[12 * cm, 3.7 * cm])
            zt.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2A44")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                        ("FONTNAME", (0, 0), (-1, -1), font_name),
                        ("FONTSIZE", (0, 0), (-1, -1), 9),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ]
                )
            )
            story.append(zt)
            story.append(Spacer(1, 0.45 * cm))

    chk_f = m["chk_f"]
    if chk_f:
        story.append(Paragraph("Contrôles conducteurs — derniers enregistrements (30 max.)", h2_st))
        rows_chk = [["Date", "Conducteur", "Véhicule", "Insp.", "T5", "Frein"]]
        chk_sorted = sorted(
            chk_f,
            key=lambda r: str(r.get("ts") or r.get("date_controle") or ""),
            reverse=True,
        )[:30]
        for r in chk_sorted:
            d0 = (r.get("date_controle") or r.get("ts") or "")[:10]
            rows_chk.append(
                [
                    d0,
                    str(r.get("conducteur_nom") or "")[:28],
                    str(r.get("vehicule") or "")[:18],
                    "Oui" if r.get("inspection_vehicule") else "Non",
                    "Oui" if r.get("take5") else "Non",
                    "Oui" if r.get("test_frein") else "Non",
                ]
            )
        cht = Table(rows_chk, colWidths=[2.2 * cm, 4.2 * cm, 3.2 * cm, 1.3 * cm, 1.3 * cm, 1.3 * cm])
        cht.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#28A745")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                    ("FONTNAME", (0, 0), (-1, -1), font_name),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ]
            )
        )
        story.append(cht)

    doc.build(story)
    return buf.getvalue()


def _render_safety_report(entries, chk_records):
    """Rapport Safety agrégé : fiches SST + contrôles conducteurs, KPI et graphiques."""
    st.markdown("#### Rapport Safety — statistiques & indicateurs")
    st.caption(
        "Synthèse des **fiches SST** et des **contrôles conducteurs** (Take 5, inspection véhicule, test de frein). "
        "Ajustez la période pour le tableau de bord. Export du résumé : **PDF**."
    )
    rp1, rp2 = st.columns([3, 1])
    with rp2:
        sfty_per = st.selectbox(
            "Période",
            ["30 jours", "90 jours", "7 jours", "Tout"],
            index=0,
            key="sfty_rpt_period",
        )
    days_map = {"7 jours": 7, "30 jours": 30, "90 jours": 90, "Tout": None}
    ndays = days_map[sfty_per]
    today_d = date.today()
    m = _safety_report_compute_metrics(entries, chk_records, ndays, today_d)
    ent_f = m["ent_f"]
    chk_f = m["chk_f"]
    n_inc = m["n_inc"]
    n_near = m["n_near"]
    n_arret = m["n_arret"]
    n_high = m["n_high"]
    n_form = m["n_form"]
    n_prio_fiches = m["n_prio_fiches"]
    n_chk = m["n_chk"]
    n_workers = m["n_workers"]
    pct_complete = m["pct_complete"]
    sum_ins = m["sum_ins"]
    sum_t5 = m["sum_t5"]
    sum_br = m["sum_br"]

    m1, m2, m3, m4, m5, m6 = st.columns(6)
    with m1:
        st.metric("Fiches SST", len(ent_f))
    with m2:
        st.metric("Incidents / accidents", n_inc, help="Types de fiche contenant « incident » ou « accident »")
    with m3:
        st.metric("Presqu'accidents", n_near)
    with m4:
        st.metric("Gravité élevée", n_high)
    with m5:
        st.metric("Fiches terrain prio.", n_prio_fiches, help="Take 5, JHA, PTO / inspection (libellés)")
    with m6:
        st.metric("Arrêts sécurité", n_arret)

    m7, m8, m9, m10 = st.columns(4)
    with m7:
        st.metric("Contrôles conducteur (lignes)", n_chk)
    with m8:
        st.metric("Conducteurs actifs (suivi)", n_workers, help="Nombre de noms distincts sur la période")
    with m9:
        st.metric("Taux « 3 contrôles »", f"{pct_complete:.0f} %", help="Même enregistrement : inspection + Take 5 + frein")
    with m10:
        st.metric("Formations / sensib.", n_form)

    st.markdown("##### Graphiques — fiches SST")
    if not ent_f:
        st.info("Aucune fiche SST sur cette période.")
    else:
        df_e = pd.DataFrame(ent_f)
        if "date_observation" in df_e.columns:
            df_e["_dt"] = pd.to_datetime(df_e["date_observation"], errors="coerce")
        elif "ts" in df_e.columns:
            df_e["_dt"] = pd.to_datetime(df_e["ts"], errors="coerce")
        else:
            df_e["_dt"] = pd.NaT
        cgr1, cgr2 = st.columns(2)
        with cgr1:
            _types = df_e["type"] if "type" in df_e.columns else pd.Series(dtype=object)
            tc = _types.fillna("(Non renseigné)").astype(str).value_counts().reset_index()
            tc.columns = ["Type", "Nombre"]
            if len(tc) > 0:
                fig_types = px.bar(
                    tc,
                    x="Type",
                    y="Nombre",
                    title="Fiches par type",
                    color="Nombre",
                    color_continuous_scale="YlOrRd",
                )
                fig_types.update_layout(showlegend=False, xaxis_tickangle=-35, height=400)
                st.plotly_chart(fig_types, width="stretch")
            else:
                st.caption("Pas de types de fiche à afficher.")
        with cgr2:
            _grav = df_e["gravite"] if "gravite" in df_e.columns else pd.Series(dtype=object)
            gc = _grav.fillna("—").astype(str).value_counts().reset_index()
            gc.columns = ["Gravité", "Nombre"]
            if len(gc) > 0 and gc["Nombre"].sum() > 0:
                fig_g = px.pie(gc, names="Gravité", values="Nombre", title="Répartition par gravité", hole=0.35)
                fig_g.update_layout(height=400)
                st.plotly_chart(fig_g, width="stretch")
            else:
                st.caption("Pas de données de gravité à afficher.")

        df_e2 = df_e[df_e["_dt"].notna()].copy()
        if len(df_e2) > 0:
            df_e2["_week"] = df_e2["_dt"].dt.to_period("W").astype(str)
            weekly = df_e2.groupby("_week", as_index=False).size()
            weekly.columns = ["Semaine", "Fiches"]
            fig_w = px.bar(weekly, x="Semaine", y="Fiches", title="Volume hebdomadaire de fiches SST", color="Fiches", color_continuous_scale="Blues")
            fig_w.update_layout(showlegend=False, height=360)
            st.plotly_chart(fig_w, width="stretch")

        _zone_s = df_e["zone"] if "zone" in df_e.columns else pd.Series([""] * len(df_e))
        zn = _zone_s.fillna("").astype(str).str.strip()
        zn = zn[zn.ne("")]
        if len(zn) > 0:
            zc = zn.value_counts().head(15).reset_index()
            zc.columns = ["Zone / site", "Nombre"]
            st.markdown("###### Zones les plus citées (top 15)")
            st.dataframe(zc, width="stretch", hide_index=True)

    st.markdown("##### Graphiques — contrôles conducteurs")
    if not chk_f:
        st.info("Aucun contrôle conducteur sur cette période.")
    else:
        dfk = pd.DataFrame(chk_f)
        bc1, bc2 = st.columns(2)
        with bc1:
            ctr_lbl = ["Inspection véhicule", "Take 5", "Test de frein"]
            fig_checks = px.bar(
                x=ctr_lbl,
                y=[sum_ins, sum_t5, sum_br],
                color=ctr_lbl,
                title="Nombre de cases cochées (cumul des enregistrements)",
                labels={"x": "", "y": "Nombre"},
                color_discrete_sequence=["#0F2A44", "#F5B800", "#28A745"],
            )
            fig_checks.update_layout(showlegend=False, height=380)
            st.plotly_chart(fig_checks, width="stretch")
        with bc2:
            if "date_controle" in dfk.columns:
                dfk["_dt"] = pd.to_datetime(dfk["date_controle"], errors="coerce")
            elif "ts" in dfk.columns:
                dfk["_dt"] = pd.to_datetime(dfk["ts"], errors="coerce")
            else:
                dfk["_dt"] = pd.NaT
            dfk2 = dfk[dfk["_dt"].notna()].copy()
            if len(dfk2) > 0:
                dfk2["_week"] = dfk2["_dt"].dt.to_period("W").astype(str)
                w2 = dfk2.groupby("_week", as_index=False).size()
                w2.columns = ["Semaine", "Enregistrements"]
                fig_cw = px.line(w2, x="Semaine", y="Enregistrements", markers=True, title="Enregistrements conducteur par semaine")
                fig_cw.update_layout(height=380)
                st.plotly_chart(fig_cw, width="stretch")
            else:
                st.caption("Pas assez de dates valides pour la courbe hebdomadaire.")

    st.markdown("##### Export du rapport (PDF)")
    df_sum = pd.DataFrame(m["summary_rows"])
    st.dataframe(df_sum, width="stretch", hide_index=True)
    try:
        pdf_bytes = _build_safety_report_pdf_bytes(m, sfty_per, today_d)
    except Exception as ex:
        pdf_bytes = None
        st.warning(f"Génération PDF indisponible ({ex}). Vérifiez l'installation : `pip install reportlab matplotlib`.")
    if pdf_bytes:
        st.download_button(
            "Télécharger le rapport Safety (PDF)",
            pdf_bytes,
            file_name=f"rapport_safety_{today_d.isoformat()}.pdf",
            mime="application/pdf",
            key="sfty_rpt_pdf_dl",
        )


def render_sst_tab(user_info, staff_mgr=None):
    """Santé et sécurité au travail — saisie et rapports."""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.subheader("🦺 Santé & sécurité au travail (SST)")
    me = st.session_state.get("username", "")
    data = _load_sst_entries()
    entries = data.get("entries", [])
    chk_data = _load_driver_safety_checks()
    chk_records = chk_data.get("records", [])

    _render_safety_report(entries, chk_records)
    st.markdown("---")

    st.markdown("#### Contrôles conducteurs (inspection véhicule · Take 5 · test de frein)")
    st.caption(
        "Enregistrez **qui** a effectué chaque contrôle pour une date donnée. "
        "Les totaux par personne et par type de contrôle sont calculés automatiquement."
    )
    actifs = staff_mgr.get_active_staff() if staff_mgr else []
    emp_sel = None
    dc1, dc2 = st.columns(2)
    with dc1:
        st.date_input("Date des contrôles", value=date.today(), key="drv_chk_date")
        if actifs:
            conducteur_labels = [f"{e.name} ({e.matricule}) — {e.role}" for e in actifs]
            sel_lbl = st.selectbox("Conducteur / travailleur", conducteur_labels, key="drv_chk_emp")
            emp_sel = actifs[conducteur_labels.index(sel_lbl)]
        else:
            st.warning("Aucun employé actif dans **RH** : utilisez la saisie libre.")
            st.text_input("Nom du conducteur (saisie libre)", key="drv_chk_nom_libre", placeholder="Nom complet")
    with dc2:
        _hint_veh = ""
        if emp_sel is not None:
            am = getattr(emp_sel, "assigned_machine", None) or ""
            if str(am).strip() and str(am).strip() != "Aucune":
                _hint_veh = str(am).strip()
        st.text_input(
            "Véhicule / engin",
            key="drv_chk_veh",
            placeholder=_hint_veh or "Ex. CAT-773, matricule parc…",
        )
        if _hint_veh:
            st.caption(f"Engin assigné en RH : **{_hint_veh}** (saisie manuelle au besoin).")
        st.markdown("**Contrôles effectués**")
        c_ins = st.checkbox("Inspection véhicule (PTO / pré‑départ)", value=True, key="drv_chk_ins")
        c_t5 = st.checkbox("Take 5 (avant la tâche)", value=True, key="drv_chk_t5")
        c_br = st.checkbox("Test de frein", value=True, key="drv_chk_br")
    st.text_input("Remarques (optionnel)", key="drv_chk_notes", placeholder="Anomalies, poste, shift…")

    if st.button("Enregistrer les contrôles conducteur", type="primary", key="drv_chk_save"):
        if actifs:
            nom_final = emp_sel.name
            mat_final = emp_sel.matricule
        else:
            nom_final = (st.session_state.get("drv_chk_nom_libre") or "").strip()
            mat_final = None
        veh_v = (st.session_state.get("drv_chk_veh") or "").strip()
        d_val = st.session_state.get("drv_chk_date", date.today())
        if hasattr(d_val, "isoformat"):
            d_iso = d_val.isoformat()
        else:
            d_iso = date.today().isoformat()
        if not nom_final:
            st.error("Indiquez le **conducteur** (liste RH ou saisie libre).")
        elif not veh_v:
            st.error("Indiquez le **véhicule / engin**.")
        elif not (c_ins or c_t5 or c_br):
            st.error("Cochez au moins un des trois contrôles.")
        else:
            rec_chk = {
                "id": uuid.uuid4().hex,
                "ts": datetime.now().isoformat(),
                "date_controle": d_iso,
                "matricule": mat_final,
                "conducteur_nom": nom_final,
                "vehicule": veh_v,
                "inspection_vehicule": bool(c_ins),
                "take5": bool(c_t5),
                "test_frein": bool(c_br),
                "notes": (st.session_state.get("drv_chk_notes") or "").strip(),
                "reporter": me,
            }
            chk_data.setdefault("records", []).insert(0, rec_chk)
            _save_driver_safety_checks(chk_data)
            st.success(f"Contrôles enregistrés pour **{nom_final}**.")
            st.rerun()

    st.markdown("##### Synthèse & comptage")
    if not chk_records:
        st.info("Aucun contrôle conducteur enregistré pour cet espace entreprise.")
    else:
        df_c = pd.DataFrame(chk_records)
        if "date_controle" in df_c.columns:
            df_c["_d"] = pd.to_datetime(df_c["date_controle"], errors="coerce").dt.date
        else:
            df_c["_d"] = pd.NaT
        c_s1, c_s2, c_s3 = st.columns(3)
        with c_s1:
            periode = st.selectbox("Période", ["30 derniers jours", "Tout", "7 derniers jours"], key="drv_sum_per")
        with c_s2:
            noms = sorted(
                {str(x) for x in df_c.get("conducteur_nom", pd.Series(dtype=object)).dropna().unique() if str(x).strip()}
            )
            filtre_nom = st.selectbox("Conducteur", ["(Tous)"] + noms, key="drv_sum_who")
        with c_s3:
            st.metric("Enregistrements (total)", len(chk_records))

        df_f = df_c.copy()
        today_d = date.today()
        if periode == "7 derniers jours" and "_d" in df_f.columns:
            df_f = df_f[df_f["_d"].notna() & (df_f["_d"] >= (today_d - timedelta(days=7)))]
        elif periode == "30 derniers jours" and "_d" in df_f.columns:
            df_f = df_f[df_f["_d"].notna() & (df_f["_d"] >= (today_d - timedelta(days=30)))]
        if filtre_nom != "(Tous)" and "conducteur_nom" in df_f.columns:
            df_f = df_f[df_f["conducteur_nom"] == filtre_nom]

        if len(df_f) == 0:
            st.caption("Aucune ligne pour ce filtre.")
        else:
            grp = (
                df_f.groupby("conducteur_nom", dropna=False)
                .agg(
                    enregistrements=("id", "count"),
                    inspection_veh=("inspection_vehicule", lambda s: int(s.fillna(False).astype(bool).sum())),
                    take5=("take5", lambda s: int(s.fillna(False).astype(bool).sum())),
                    test_frein=("test_frein", lambda s: int(s.fillna(False).astype(bool).sum())),
                )
                .reset_index()
            )
            grp = grp.rename(
                columns={
                    "conducteur_nom": "Conducteur",
                    "enregistrements": "Passages",
                    "inspection_veh": "Inspections véh.",
                    "take5": "Take 5",
                    "test_frein": "Tests frein",
                }
            )
            st.dataframe(grp, width="stretch", hide_index=True)

            def _row_complete(row):
                return bool(row.get("inspection_vehicule")) and bool(row.get("take5")) and bool(row.get("test_frein"))

            df_f2 = df_f.copy()
            df_f2["_complet"] = df_f2.apply(_row_complete, axis=1)
            n_complete = int(df_f2["_complet"].sum())
            st.caption(
                f"Sur la période et le filtre choisis : **{n_complete}** passage(s) avec les **trois** contrôles cochés, "
                f"**{len(df_f2) - n_complete}** avec au moins un contrôle partiel."
            )

            st.markdown("###### Détail récent (50 dernières lignes)")
            show_cols = [
                "date_controle",
                "conducteur_nom",
                "matricule",
                "vehicule",
                "inspection_vehicule",
                "take5",
                "test_frein",
                "reporter",
                "notes",
            ]
            exist = [c for c in show_cols if c in df_f.columns]
            sort_key = "ts" if "ts" in df_f.columns else (exist[0] if exist else None)
            if sort_key:
                st.dataframe(
                    df_f.sort_values(sort_key, ascending=False).head(50)[exist],
                    width="stretch",
                    hide_index=True,
                )

        csv_chk = pd.DataFrame(chk_records).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Exporter les contrôles conducteurs (CSV)",
            csv_chk,
            file_name=f"sst_controles_conducteurs_{date.today().isoformat()}.csv",
            mime="text/csv",
            key="drv_chk_csv_dl",
        )

    st.markdown("---")
    st.markdown("#### Documents terrain prioritaires")
    st.caption(
        "Mettez en avant les **Take 5**, **JHA** et **PTO / inspection véhicule** : un clic règle le type de fiche, "
        "puis complétez la zone, la description et les pièces jointes ci‑dessous."
    )
    sst_opts = _sst_type_choices()
    q1, q2, q3 = st.columns(3)
    with q1:
        if st.button("Take 5 — avant la tâche", key="sst_quick_take5", use_container_width=True):
            st.session_state["sst_type"] = sst_opts[0]
            st.rerun()
    with q2:
        if st.button("JHA — dangers du travail", key="sst_quick_jha", use_container_width=True):
            st.session_state["sst_type"] = sst_opts[1]
            st.rerun()
    with q3:
        if st.button("PTO / inspection véhicule", key="sst_quick_pto", use_container_width=True):
            st.session_state["sst_type"] = sst_opts[2]
            st.rerun()

    st.markdown("#### Nouvelle fiche / événement SST")
    c1, c2 = st.columns(2)
    with c1:
        evt = st.selectbox(
            "Type",
            sst_opts,
            key="sst_type",
        )
        zone = st.text_input("Site / zone / équipement", key="sst_zone", placeholder="Ex. Fosse nord, atelier…")
    with c2:
        grav = st.selectbox("Gravité", ["Basse", "Moyenne", "Élevée"], key="sst_grav")
        ed = st.date_input("Date", value=date.today(), key="sst_date")
    desc = st.text_area("Description / constats", key="sst_desc", height=120, placeholder="Faits, causes possibles, témoins…")
    actions = st.text_area("Actions correctives / recommandations", key="sst_act", height=80)
    rep_up = st.file_uploader("Rapport ou photo (PDF, image…)", key="sst_up")
    if st.button("Enregistrer la fiche SST", type="primary", key="sst_save"):
        if not (desc or "").strip():
            st.error("La description est obligatoire.")
        else:
            att_rel = None
            att_name = None
            if rep_up is not None:
                safe = "".join(c for c in rep_up.name if c.isalnum() or c in "._- ")[:120]
                att_rel = f"sst_uploads/{uuid.uuid4().hex}_{safe}"
                fp = os.path.join(_collaboration_base_dir(), att_rel)
                with open(fp, "wb") as f:
                    f.write(rep_up.getbuffer())
                att_name = rep_up.name
            rec = {
                "id": uuid.uuid4().hex,
                "ts": datetime.now().isoformat(),
                "date_observation": ed.isoformat(),
                "reporter": me,
                "type": evt,
                "zone": (zone or "").strip(),
                "gravite": grav,
                "description": (desc or "").strip(),
                "actions": (actions or "").strip(),
                "attachment": att_rel,
                "attachment_name": att_name,
            }
            data.setdefault("entries", []).insert(0, rec)
            _save_sst_entries(data)
            st.success("Fiche SST enregistrée.")
            st.rerun()

    st.markdown("---")
    st.markdown("#### Historique & rapports")
    if not entries:
        st.info("Aucune fiche enregistrée pour cet espace entreprise.")
    else:
        prio = [e for e in entries if _sst_entry_is_priority_terain(e)]
        other = [e for e in entries if not _sst_entry_is_priority_terain(e)]

        def _rows_for(entries_slice):
            rows = []
            for e in entries_slice[:200]:
                rows.append(
                    {
                        "Date": (e.get("date_observation") or e.get("ts", ""))[:10],
                        "Auteur": e.get("reporter", ""),
                        "Type": e.get("type", ""),
                        "Zone": e.get("zone", ""),
                        "Gravité": e.get("gravite", ""),
                        "Résumé": (e.get("description", "") or "")[:80]
                        + ("…" if len(e.get("description", "") or "") > 80 else ""),
                    }
                )
            return rows

        if prio:
            st.markdown(
                "##### Take 5 · JHA · PTO / inspection véhicule",
                help="Fiches identifiées comme contrôles terrain prioritaires (libellé de type ou mots-clés).",
            )
            st.dataframe(pd.DataFrame(_rows_for(prio)), width="stretch", hide_index=True)
        if other:
            st.markdown("##### Autres fiches SST")
            st.dataframe(pd.DataFrame(_rows_for(other)), width="stretch", hide_index=True)
        csv = pd.DataFrame(entries).to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Exporter l'historique SST (CSV)",
            csv,
            file_name=f"sst_export_{date.today().isoformat()}.csv",
            mime="text/csv",
            key="sst_csv_dl",
        )
        st.caption("Pour chaque ligne, le fichier joint (si présent) est stocké sur le serveur dans le dossier collaboration du tenant.")

    st.markdown('</div>', unsafe_allow_html=True)


def get_effective_db_path():
    """Fichier SQLite pour le tenant courant. Défaut = geo_data.db (existant)."""
    try:
        tid = st.session_state.get("tenant_id", "default")
    except Exception:
        tid = "default"
    tid = _safe_tenant_id(tid)
    if tid == "default":
        return os.path.abspath(LEGACY_DB_FILE)
    d = os.path.join(TENANT_DATA_DIR, tid)
    os.makedirs(d, exist_ok=True)
    return os.path.abspath(os.path.join(d, "geo_data.db"))


def _ensure_machines_extra_columns(conn):
    """Ajoute colonnes manquantes (migrations progressives sans recréer la BDD)."""
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(machines)")
        have = {row[1] for row in cur.fetchall()}
        for col, stmt in (
            ("bucket_capacity_m3", "ALTER TABLE machines ADD COLUMN bucket_capacity_m3 REAL DEFAULT 0"),
            ("blade_capacity_m3", "ALTER TABLE machines ADD COLUMN blade_capacity_m3 REAL DEFAULT 0"),
            ("operating_weight_t", "ALTER TABLE machines ADD COLUMN operating_weight_t REAL DEFAULT 0"),
        ):
            if col not in have:
                cur.execute(stmt)
        # Créer la table de suivi de durée de vie si absente (BDD existantes antérieures)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS part_life_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                part_name TEXT NOT NULL,
                production_tonnes_at_pose REAL DEFAULT 0,
                engine_hours_at_pose REAL DEFAULT 0,
                pose_date TEXT NOT NULL,
                maintenance_ref TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_by TEXT DEFAULT 'Système',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plt_machine ON part_life_tracking(machine_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_plt_part ON part_life_tracking(part_name)")
    except Exception:
        pass


@contextmanager
def get_connection():
    """Connexion SQLite pour le tenant actif (session Streamlit)."""
    db_path = get_effective_db_path()
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    if not os.path.exists(db_path) or os.path.getsize(db_path) == 0:
        init_database_at_path(db_path)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")
    except Exception:
        pass
    _ensure_machines_extra_columns(conn)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def init_database_at_path(db_path):
    """Initialise le schéma sur un fichier SQLite (sans utiliser get_connection)."""
    parent = os.path.dirname(db_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        cursor = conn.cursor()
        
        # Table machines - Stocke toutes les informations des machines
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS machines (
                id TEXT PRIMARY KEY,
                model TEXT NOT NULL,
                type TEXT NOT NULL,
                capacity REAL DEFAULT 0,
                hourly_rate REAL DEFAULT 150,
                status TEXT DEFAULT 'Active',
                operator TEXT DEFAULT 'Non Assigné',
                engine_hours REAL DEFAULT 0,
                fuel_tank REAL DEFAULT 100,
                lat REAL DEFAULT 12.3,
                lon REAL DEFAULT -1.5,
                cycle INTEGER DEFAULT 0,
                production_tonnes REAL DEFAULT 0,
                breakdown_reason TEXT DEFAULT '',
                breakdown_time TEXT DEFAULT '',
                load_type TEXT DEFAULT 'N/A',
                load_time TEXT,
                destination TEXT DEFAULT '',
                alert_trigger INTEGER DEFAULT 0,
                h_jour REAL DEFAULT 0,
                h_semaine REAL DEFAULT 0,
                h_mois REAL DEFAULT 0,
                last_pm_hours REAL DEFAULT 0,
                next_pm_interval REAL DEFAULT 250,
                next_maintenance TEXT,
                cons_jour REAL DEFAULT 0,
                cons_mois REAL DEFAULT 0,
                cons_annee REAL DEFAULT 0,
                cons_total REAL DEFAULT 0,
                bucket_capacity_m3 REAL DEFAULT 0,
                blade_capacity_m3 REAL DEFAULT 0,
                operating_weight_t REAL DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Table fuel_logs - Historique complet des ravitaillements
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS fuel_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                date TEXT NOT NULL,
                litres REAL NOT NULL,
                price_per_liter_usd REAL NOT NULL,
                currency_used TEXT DEFAULT 'USD',
                original_price REAL DEFAULT 0,
                total_usd REAL NOT NULL,
                engine_hours_at_refuel REAL NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
            )
        """)
        
        # Table maintenance_logs - Historique complet des maintenances
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS maintenance_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                maintenance_type TEXT NOT NULL,
                date_maintenance TEXT NOT NULL,
                mechanic_name TEXT,
                engine_hours_at_maintenance REAL DEFAULT 0,
                notes TEXT DEFAULT '',
                pieces_changed TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
            )
        """)
        
        # Table breakdowns - Historique des pannes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS breakdowns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                breakdown_time TEXT NOT NULL,
                repair_time TEXT,
                mechanic_name TEXT,
                status TEXT DEFAULT 'En cours',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
            )
        """)
        
        # Table manual_entries - Historique des entrées manuelles par shift
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS manual_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                shift TEXT NOT NULL,
                entry_date TEXT NOT NULL,
                hours_worked REAL DEFAULT 0,
                production_tonnes REAL DEFAULT 0,
                fuel_consumed REAL DEFAULT 0,
                fuel_price_usd REAL DEFAULT 1.5,
                update_period TEXT DEFAULT 'Journalière',
                revenue_jour REAL DEFAULT 0,
                revenue_hebdo REAL DEFAULT 0,
                revenue_mois REAL DEFAULT 0,
                cost_fuel REAL DEFAULT 0,
                profitability REAL DEFAULT 0,
                cycles_added REAL DEFAULT 0,
                cons_per_cycle REAL DEFAULT 0,
                cons_per_shift REAL DEFAULT 0,
                avg_cycle_time REAL DEFAULT 0,
                entered_by TEXT DEFAULT 'Système',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
            )
        """)
        
        # Table part_life_tracking — lie chaque pose de consommable à la production machine
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS part_life_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                machine_id TEXT NOT NULL,
                part_name TEXT NOT NULL,
                production_tonnes_at_pose REAL DEFAULT 0,
                engine_hours_at_pose REAL DEFAULT 0,
                pose_date TEXT NOT NULL,
                maintenance_ref TEXT DEFAULT '',
                notes TEXT DEFAULT '',
                created_by TEXT DEFAULT 'Système',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (machine_id) REFERENCES machines(id) ON DELETE CASCADE
            )
        """)

        # Index pour améliorer les performances
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fuel_machine ON fuel_logs(machine_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_fuel_date ON fuel_logs(date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_machine ON maintenance_logs(machine_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_maintenance_date ON maintenance_logs(date_maintenance)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_breakdown_machine ON breakdowns(machine_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_machine ON manual_entries(machine_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_date ON manual_entries(entry_date)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_manual_shift ON manual_entries(shift)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plt_machine ON part_life_tracking(machine_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_plt_part ON part_life_tracking(part_name)")
        
        _ensure_machines_extra_columns(conn)
        conn.commit()
    finally:
        conn.close()

# Schéma sur la base historique (tenant « default » = fichier racine)
init_database_at_path(os.path.abspath(LEGACY_DB_FILE))

# ==============================================================================
# SYSTÈME DE PLANS ET LIMITATIONS
# ==============================================================================

# Configuration des fonctionnalités par plan
FEATURE_PLANS = {
    "free": {
        "max_machines": 5,
        "max_users": 10,
        "data_retention_days": 30,
        "features": ["dashboard", "donnees_ingenierie", "cycles", "carburant", "maintenance", "carte", "validation_operateur"]
    },
    "standard": {
        "max_machines": 50,
        "max_users": 50,
        "data_retention_days": 365,
        "features": ["dashboard", "donnees_ingenierie", "cycles", "carburant", "maintenance", "carte", "validation_operateur", "stock", "finance", "rh", "marche_or", "export_basic"]
    },
    "premium": {
        "max_machines": -1,  # Illimité
        "max_users": -1,
        "data_retention_days": -1,
        "features": ["all"]  # Toutes les fonctionnalités
    }
}

def get_current_plan():
    """Plan SaaS : priorité au plan enregistré pour l'entreprise (tenant), sinon fallback JSON global."""
    try:
        tid = _safe_tenant_id(st.session_state.get("tenant_id", "default"))
    except Exception:
        tid = "default"
    try:
        t = get_tenants_registry().get(tid)
        if t and t.get("plan"):
            return t["plan"]
    except Exception:
        pass
    db = get_database()
    return db.get("subscription", {}).get("plan", "free")

def set_plan(plan_name):
    """Définit le plan de l'instance"""
    if plan_name not in FEATURE_PLANS:
        return False, f"Plan '{plan_name}' n'existe pas"
    
    db = get_database()
    if "subscription" not in db:
        db["subscription"] = {}
    
    db["subscription"]["plan"] = plan_name
    db["subscription"]["updated_at"] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    save_database(db)
    return True, f"Plan '{plan_name}' activé avec succès"

def has_feature(feature_name):
    """Vérifie si le plan actuel a accès à une fonctionnalité"""
    plan = get_current_plan()
    plan_config = FEATURE_PLANS.get(plan, FEATURE_PLANS["free"])
    
    if "all" in plan_config["features"]:
        return True
    
    # Mapping des noms d'onglets vers les noms de fonctionnalités
    feature_mapping = {
        "stock": "stock",
        "finance": "finance",
        "rh": "rh",
        "marche_or": "marche_or",
        "export_basic": "export_basic",
        "backup": "backup",  # Premium uniquement
        "audit": "audit"  # Premium uniquement
    }
    
    mapped_feature = feature_mapping.get(feature_name, feature_name)
    return mapped_feature in plan_config["features"]

def check_machine_limit():
    """Vérifie si la limite de machines est atteinte"""
    plan = get_current_plan()
    plan_config = FEATURE_PLANS.get(plan, FEATURE_PLANS["free"])
    max_machines = plan_config["max_machines"]
    
    if max_machines == -1:  # Illimité
        return True, None
    
    # Obtenir l'instance manager
    try:
        manager_obj = globals().get('manager', None)
        current_count = len(manager_obj.machines) if manager_obj and hasattr(manager_obj, 'machines') else 0
    except:
        current_count = 0
    
    if current_count >= max_machines:
        return False, f"Limite atteinte ({current_count}/{max_machines} machines). Passez au plan supérieur pour plus de machines."
    
    return True, None

def check_user_limit():
    """Vérifie si la limite d'utilisateurs est atteinte"""
    plan = get_current_plan()
    plan_config = FEATURE_PLANS.get(plan, FEATURE_PLANS["free"])
    max_users = plan_config["max_users"]
    
    if max_users == -1:  # Illimité
        return True, None
    
    try:
        user_mgr_obj = globals().get('user_mgr', None)
        tid = _current_tenant_id_for_limits()
        if user_mgr_obj and hasattr(user_mgr_obj, 'users_db'):
            current_count = sum(
                1
                for u in user_mgr_obj.users_db
                if _safe_tenant_id(u.get("tenant_id", "default")) == tid
                and u.get("role") != "Gestionnaire"
            )
        else:
            current_count = 0
    except Exception:
        current_count = 0
    
    if current_count >= max_users:
        return False, f"Limite atteinte ({current_count}/{max_users} utilisateurs). Passez au plan supérieur pour plus d'utilisateurs."
    
    return True, None

def get_plan_info():
    """Retourne les informations du plan actuel"""
    plan = get_current_plan()
    plan_config = FEATURE_PLANS.get(plan, FEATURE_PLANS["free"])
    
    # Obtenir les instances globales
    try:
        manager_obj = globals().get('manager', None)
        user_mgr_obj = globals().get('user_mgr', None)
        current_machines = len(manager_obj.machines) if manager_obj and hasattr(manager_obj, 'machines') else 0
        tid = _current_tenant_id_for_limits()
        if user_mgr_obj and hasattr(user_mgr_obj, 'users_db'):
            current_users = sum(
                1
                for u in user_mgr_obj.users_db
                if _safe_tenant_id(u.get("tenant_id", "default")) == tid
                and u.get("role") != "Gestionnaire"
            )
        else:
            current_users = 0
    except Exception:
        current_machines = 0
        current_users = 0
    
    return {
        "plan": plan,
        "max_machines": plan_config["max_machines"],
        "max_users": plan_config["max_users"],
        "data_retention_days": plan_config["data_retention_days"],
        "features": plan_config["features"],
        "current_machines": current_machines,
        "current_users": current_users
    }

def get_upgrade_message(feature_name=None):
    """Génère un message d'upgrade selon la fonctionnalité"""
    plan = get_current_plan()
    
    if plan == "premium":
        return None  # Déjà au plan maximum
    
    messages = {
        "finance": "💎 Cette fonctionnalité est disponible avec le plan Standard ou Premium. Passez à un plan supérieur pour accéder à la gestion financière complète.",
        "rh": "💎 Cette fonctionnalité est disponible avec le plan Standard ou Premium. Passez à un plan supérieur pour accéder à la gestion RH complète.",
        "stock": "💎 Cette fonctionnalité est disponible avec le plan Standard ou Premium. Passez à un plan supérieur pour accéder à la gestion de stock.",
        "export": "💎 L'export avancé est disponible avec le plan Standard ou Premium. Passez à un plan supérieur pour exporter vos données.",
        "backup": "💎 Les sauvegardes et restaurations sont disponibles avec le plan Premium uniquement. Passez au plan Premium pour cette fonctionnalité.",
        "audit": "💎 Les logs d'audit avancés sont disponibles avec le plan Premium uniquement. Passez au plan Premium pour cette fonctionnalité.",
        "marche_or": "💎 Le suivi du marché de l'or est disponible avec le plan Standard ou Premium. Passez à un plan supérieur pour accéder à cette fonctionnalité."
    }
    
    if feature_name and feature_name in messages:
        return messages[feature_name]
    
    if plan == "free":
        return "💎 Passez au plan Standard ou Premium pour débloquer plus de fonctionnalités."
    elif plan == "standard":
        return "💎 Passez au plan Premium pour débloquer toutes les fonctionnalités."
    
    return None

# ==============================================================================
# FONCTION POUR SUPPRIMER TOUTES LES DONNÉES DE SIMULATION
# ==============================================================================

def clear_all_simulation_data():
    """Supprime toutes les données de simulation de la base de données"""
    with get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Supprimer tous les logs de carburant
            cursor.execute("DELETE FROM fuel_logs")
            
            # Supprimer tous les logs de maintenance
            cursor.execute("DELETE FROM maintenance_logs")
            
            # Supprimer toutes les pannes
            cursor.execute("DELETE FROM breakdowns")
            
            # Supprimer toutes les entrées manuelles
            cursor.execute("DELETE FROM manual_entries")
            
            # Réinitialiser tous les compteurs des machines à 0
            cursor.execute("""
                UPDATE machines SET
                    engine_hours = 0,
                    fuel_tank = 0,
                    cycle = 0,
                    production_tonnes = 0,
                    h_jour = 0,
                    h_semaine = 0,
                    h_mois = 0,
                    last_pm_hours = 0,
                    cons_jour = 0,
                    cons_mois = 0,
                    cons_annee = 0,
                    cons_total = 0,
                    breakdown_reason = '',
                    breakdown_time = '',
                    load_type = 'N/A',
                    load_time = NULL,
                    destination = '',
                    alert_trigger = 0,
                    next_maintenance = NULL,
                    updated_at = CURRENT_TIMESTAMP
            """)
            
            return True, "Toutes les données de simulation ont été supprimées et tous les compteurs ont été réinitialisés à 0."
        except Exception as e:
            conn.rollback()
            return False, f"Erreur lors de la suppression : {str(e)}"

# ==============================================================================
# FONCTIONS POUR L'HISTORIQUE DES ENTRÉES MANUELLES
# ==============================================================================

def get_current_shift():
    """Détermine le shift actuel basé sur l'heure :
    - Jour : 5h30 à 18h00
    - Nuit : 18h30 à 5h00
    """
    now = datetime.now()
    current_hour = now.hour
    current_minute = now.minute
    current_time = current_hour + (current_minute / 60)
    
    # Shift Jour : 5h30 (5.5) à 18h00 (18.0)
    if 5.5 <= current_time < 18.0:
        return "Jour"
    # Shift Nuit : 18h30 (18.5) à 23h59 ou 0h00 à 5h00 (5.0)
    else:
        return "Nuit"

def save_manual_entry(machine_id, shift, entry_date, hours_worked, production_tonnes, 
                     fuel_consumed, fuel_price_usd, update_period, revenue_jour, revenue_hebdo,
                     revenue_mois, cost_fuel, profitability, cycles_added, cons_per_cycle,
                     cons_per_shift, avg_cycle_time, entered_by):
    """Sauvegarde une entrée manuelle dans l'historique"""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO manual_entries (
                machine_id, shift, entry_date, hours_worked, production_tonnes,
                fuel_consumed, fuel_price_usd, update_period, revenue_jour, revenue_hebdo,
                revenue_mois, cost_fuel, profitability, cycles_added, cons_per_cycle,
                cons_per_shift, avg_cycle_time, entered_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            machine_id, shift, entry_date, hours_worked, production_tonnes,
            fuel_consumed, fuel_price_usd, update_period, revenue_jour, revenue_hebdo,
            revenue_mois, cost_fuel, profitability, cycles_added, cons_per_cycle,
            cons_per_shift, avg_cycle_time, entered_by
        ))
        return cursor.lastrowid

def get_manual_entries_history(machine_id=None, shift=None, start_date=None, end_date=None, limit=100):
    """Récupère l'historique des entrées manuelles avec filtres"""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM manual_entries WHERE 1=1"
        params = []
        
        if machine_id:
            query += " AND machine_id = ?"
            params.append(machine_id)
        if shift:
            query += " AND shift = ?"
            params.append(shift)
        if start_date:
            query += " AND entry_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND entry_date <= ?"
            params.append(end_date)
        
        query += " ORDER BY entry_date DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def get_manual_entries_summary(machine_id=None, start_date=None, end_date=None):
    """Récupère un résumé des entrées manuelles"""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT 
                shift,
                COUNT(*) as total_entries,
                SUM(hours_worked) as total_hours,
                SUM(production_tonnes) as total_production,
                SUM(fuel_consumed) as total_fuel,
                SUM(revenue_jour) as total_revenue,
                SUM(cost_fuel) as total_cost,
                SUM(profitability) as total_profitability
            FROM manual_entries
            WHERE 1=1
        """
        params = []
        
        if machine_id:
            query += " AND machine_id = ?"
            params.append(machine_id)
        if start_date:
            query += " AND entry_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND entry_date <= ?"
            params.append(end_date)
        
        query += " GROUP BY shift ORDER BY shift"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_fuel_logs_for_date(report_date_str):
    """Ravitaillements enregistrés (onglet Carburant) pour une date YYYY-MM-DD."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, machine_id, date, litres, price_per_liter_usd, currency_used,
                   original_price, total_usd, engine_hours_at_refuel
            FROM fuel_logs
            WHERE date(date) = date(?)
            ORDER BY date
            """,
            (report_date_str,),
        )
        return [dict(row) for row in cursor.fetchall()]


def collect_fuel_expenses_for_finance(start_date, end_date):
    """
    Dépenses carburant pour Finance (période inclusive) :
    - fuel_logs : pleins saisis dans l'onglet Carburant ;
    - manual_entries : litres chargés × prix (Données ingénierie).
    Lecture directe SQLite pour éviter listes en mémoire vides ou désynchronisées.
    """
    sd = start_date.strftime("%Y-%m-%d")
    ed = end_date.strftime("%Y-%m-%d")

    def _parse_sql_date(val):
        s = str(val or "")
        if not s:
            return None
        try:
            if " " in s:
                return datetime.strptime(s.split()[0], "%Y-%m-%d").date()
            return datetime.strptime(s[:10], "%Y-%m-%d").date()
        except Exception:
            return None

    fuel_expenses = 0.0
    fuel_logs_in_period = []

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT machine_id, date, litres, total_usd
            FROM fuel_logs
            WHERE date(date) >= date(?) AND date(date) <= date(?)
            ORDER BY date
            """,
            (sd, ed),
        )
        for row in cursor.fetchall():
            r = dict(row)
            fuel_date = _parse_sql_date(r.get("date"))
            if fuel_date is None or not (start_date <= fuel_date <= end_date):
                continue
            cost = float(r.get("total_usd") or 0)
            liters = float(r.get("litres") or 0)
            fuel_expenses += cost
            fuel_logs_in_period.append(
                {
                    "machine": r["machine_id"],
                    "date": fuel_date,
                    "liters": liters,
                    "cost": cost,
                    "source": "Ravitaillement (Carburant)",
                }
            )

        cursor.execute(
            """
            SELECT machine_id, entry_date, shift, fuel_consumed, fuel_price_usd
            FROM manual_entries
            WHERE entry_date >= ? AND entry_date <= ?
              AND COALESCE(fuel_consumed, 0) > 0
            ORDER BY entry_date, machine_id
            """,
            (sd, ed),
        )
        for row in cursor.fetchall():
            r = dict(row)
            ent_date = _parse_sql_date(r.get("entry_date"))
            if ent_date is None or not (start_date <= ent_date <= end_date):
                continue
            liters = float(r.get("fuel_consumed") or 0)
            price = float(r.get("fuel_price_usd") or 0)
            cost = liters * price
            fuel_expenses += cost
            sh = r.get("shift") or ""
            fuel_logs_in_period.append(
                {
                    "machine": r["machine_id"],
                    "date": ent_date,
                    "liters": liters,
                    "cost": cost,
                    "source": f"Saisie ingénierie ({sh})" if sh else "Saisie ingénierie",
                }
            )

    fuel_logs_in_period.sort(key=lambda x: (x["date"], x["machine"], x["source"]))
    return fuel_expenses, fuel_logs_in_period


def get_manual_daily_totals(report_date_str):
    """Totaux journaliers des entrées manuelles ingénierie."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                COUNT(*) AS nb_entrees,
                COUNT(DISTINCT machine_id) AS nb_engins_saisie,
                SUM(hours_worked) AS total_heures,
                SUM(production_tonnes) AS total_tonnes,
                SUM(fuel_consumed) AS total_litres_manuel,
                SUM(cycles_added) AS total_cycles,
                SUM(CASE WHEN shift = 'Jour' THEN hours_worked ELSE 0 END) AS heures_shift_jour,
                SUM(CASE WHEN shift = 'Nuit' THEN hours_worked ELSE 0 END) AS heures_shift_nuit,
                SUM(CASE WHEN shift = 'Jour' THEN production_tonnes ELSE 0 END) AS tonnes_shift_jour,
                SUM(CASE WHEN shift = 'Nuit' THEN production_tonnes ELSE 0 END) AS tonnes_shift_nuit,
                SUM(CASE WHEN shift = 'Jour' THEN fuel_consumed ELSE 0 END) AS litres_shift_jour,
                SUM(CASE WHEN shift = 'Nuit' THEN fuel_consumed ELSE 0 END) AS litres_shift_nuit
            FROM manual_entries
            WHERE entry_date = ?
            """,
            (report_date_str,),
        )
        row = cursor.fetchone()
        if not row:
            return {}
        return dict(row)


def get_manual_daily_by_machine(report_date_str):
    """Agrégat par engin pour une date (tous shifts confondus)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT
                machine_id,
                COUNT(*) AS nb_entrees,
                SUM(hours_worked) AS heures,
                SUM(production_tonnes) AS tonnes,
                SUM(fuel_consumed) AS litres_charges,
                SUM(cycles_added) AS cycles,
                AVG(fuel_price_usd) AS prix_litre_moyen_usd
            FROM manual_entries
            WHERE entry_date = ?
            GROUP BY machine_id
            ORDER BY machine_id
            """,
            (report_date_str,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_manual_daily_fuel_cost_usd(report_date_str):
    """Coût carburant saisi (litres × prix USD de l'entrée) pour le jour."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COALESCE(SUM(fuel_consumed * fuel_price_usd), 0) AS cout_usd,
                   COALESCE(SUM(fuel_consumed), 0) AS litres
            FROM manual_entries
            WHERE entry_date = ?
            """,
            (report_date_str,),
        )
        row = cursor.fetchone()
        return dict(row) if row else {"cout_usd": 0.0, "litres": 0.0}


def get_manual_daily_revenue_estimate_usd(report_date_str, manager):
    """Revenu estimé : Σ (heures saisies × taux horaire engin)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT machine_id, SUM(hours_worked) AS h
            FROM manual_entries
            WHERE entry_date = ?
            GROUP BY machine_id
            """,
            (report_date_str,),
        )
        rows = cursor.fetchall()
    rate_by_id = {m.id: float(m.hourly_rate) for m in manager.machines}
    total = 0.0
    for row in rows:
        mid = row["machine_id"]
        h = float(row["h"] or 0)
        total += h * rate_by_id.get(mid, 150.0)
    return total


def get_breakdowns_count_for_date(report_date_str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM breakdowns
            WHERE date(breakdown_time) = date(?)
            """,
            (report_date_str,),
        )
        row = cursor.fetchone()
        return int(row["n"] or 0) if row else 0


def get_maintenance_count_for_date(report_date_str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*) AS n FROM maintenance_logs
            WHERE date_maintenance = ?
            """,
            (report_date_str,),
        )
        row = cursor.fetchone()
        return int(row["n"] or 0) if row else 0


def collect_daily_ingenierie_report(report_date_str, manager):
    """
    Construit les KPI et tableaux pour le rapport journalier
    (saisie ingénierie + ravitaillements SQLite).
    """
    z = lambda x: float(x or 0)
    totals = get_manual_daily_totals(report_date_str)
    if not totals:
        totals = {
            "nb_entrees": 0,
            "nb_engins_saisie": 0,
            "total_heures": 0,
            "total_tonnes": 0,
            "total_litres_manuel": 0,
            "total_cycles": 0,
            "heures_shift_jour": 0,
            "heures_shift_nuit": 0,
            "tonnes_shift_jour": 0,
            "tonnes_shift_nuit": 0,
            "litres_shift_jour": 0,
            "litres_shift_nuit": 0,
        }
    fuel_logs = get_fuel_logs_for_date(report_date_str)
    by_m = get_manual_daily_by_machine(report_date_str)
    fuel_cost_row = get_manual_daily_fuel_cost_usd(report_date_str)
    rev_est = get_manual_daily_revenue_estimate_usd(report_date_str, manager)
    cout_manuel = z(fuel_cost_row.get("cout_usd"))
    rent_est = rev_est - cout_manuel

    th = z(totals.get("total_heures"))
    tt = z(totals.get("total_tonnes"))
    tl = z(totals.get("total_litres_manuel"))
    tc = z(totals.get("total_cycles"))
    nb_e = int(totals.get("nb_engins_saisie") or 0)
    nb_ent = int(totals.get("nb_entrees") or 0)

    total_litres_rav = sum(z(r.get("litres")) for r in fuel_logs)
    total_usd_rav = sum(z(r.get("total_usd")) for r in fuel_logs)
    nb_rav = len(fuel_logs)
    engins_rav = len({r["machine_id"] for r in fuel_logs})

    tonnes_par_heure = tt / th if th > 0 else 0.0
    litres_par_heure = tl / th if th > 0 else 0.0
    litres_par_tonne = tl / tt if tt > 0 else 0.0
    cycles_par_heure = tc / th if th > 0 else 0.0
    tonnes_par_cycle = tt / tc if tc > 0 else 0.0
    heures_moy_par_engin = th / nb_e if nb_e > 0 else 0.0
    tonnes_moy_par_engin = tt / nb_e if nb_e > 0 else 0.0
    prix_moy_pond = (cout_manuel / tl) if tl > 0 else 1.5
    rev_par_heure = rev_est / th if th > 0 else 0.0
    rev_par_tonne = rev_est / tt if tt > 0 else 0.0
    cout_par_tonne = cout_manuel / tt if tt > 0 else 0.0
    marge_par_tonne = rent_est / tt if tt > 0 else 0.0

    df_fleet = manager.get_summary_dataframe()
    nb_flotte = len(df_fleet)
    actives = int((df_fleet["Statut"] == "Active").sum()) if nb_flotte else 0
    pannes = int((df_fleet["Statut"] == "Panne").sum()) if nb_flotte else 0

    kpi = {
        "date": report_date_str,
        "nb_entrees_manuelles": nb_ent,
        "nb_engins_avec_saisie": nb_e,
        "total_heures_saisies": th,
        "total_tonnes": tt,
        "total_litres_charges_manuel": tl,
        "total_cycles_saisis": tc,
        "heures_shift_jour": z(totals.get("heures_shift_jour")),
        "heures_shift_nuit": z(totals.get("heures_shift_nuit")),
        "tonnes_shift_jour": z(totals.get("tonnes_shift_jour")),
        "tonnes_shift_nuit": z(totals.get("tonnes_shift_nuit")),
        "litres_shift_jour": z(totals.get("litres_shift_jour")),
        "litres_shift_nuit": z(totals.get("litres_shift_nuit")),
        "tonnes_par_heure": tonnes_par_heure,
        "litres_par_heure": litres_par_heure,
        "litres_par_tonne": litres_par_tonne,
        "cycles_par_heure": cycles_par_heure,
        "tonnes_par_cycle": tonnes_par_cycle,
        "heures_moy_par_engin_saisi": heures_moy_par_engin,
        "tonnes_moy_par_engin_saisi": tonnes_moy_par_engin,
        "revenu_estime_usd": rev_est,
        "cout_carburant_manuel_usd": cout_manuel,
        "rentabilite_estimee_usd": rent_est,
        "prix_litre_moyen_pondere_usd": prix_moy_pond,
        "revenu_par_heure_usd": rev_par_heure,
        "revenu_par_tonne_usd": rev_par_tonne,
        "cout_carburant_par_tonne_usd": cout_par_tonne,
        "marge_par_tonne_usd": marge_par_tonne,
        "nb_ravitaillements": nb_rav,
        "litres_ravitaillements": total_litres_rav,
        "usd_ravitaillements": total_usd_rav,
        "nb_engins_ravitailles": engins_rav,
        "prix_moyen_rav_usd_l": (total_usd_rav / total_litres_rav) if total_litres_rav > 0 else 0.0,
        "litres_total_carburant_jour": tl + total_litres_rav,
        "pannes_signalees_jour": get_breakdowns_count_for_date(report_date_str),
        "maintenances_jour": get_maintenance_count_for_date(report_date_str),
        "flotte_nb_engins": nb_flotte,
        "flotte_actives": actives,
        "flotte_pannes": pannes,
    }

    cap_by_id = {m.id: float(m.capacity or 0) for m in manager.machines}
    rate_by_id = {m.id: float(m.hourly_rate) for m in manager.machines}
    type_by_id = {m.id: m.type for m in manager.machines}
    model_by_id = {m.id: m.model for m in manager.machines}

    rows_detail = []
    for r in by_m:
        mid = r["machine_id"]
        h = z(r.get("heures"))
        t = z(r.get("tonnes"))
        f = z(r.get("litres_charges"))
        cy = z(r.get("cycles"))
        rate = rate_by_id.get(mid, 150.0)
        rev_m = h * rate
        prix_e = z(r.get("prix_litre_moyen_usd")) or prix_moy_pond
        cout_m = f * prix_e
        rows_detail.append(
            {
                "machine_id": mid,
                "type": type_by_id.get(mid, ""),
                "modele": model_by_id.get(mid, ""),
                "nb_entrees": int(r.get("nb_entrees") or 0),
                "heures": round(h, 2),
                "tonnes": round(t, 2),
                "litres_charges": round(f, 2),
                "cycles": round(cy, 2),
                "taux_horaire_usd": rate,
                "capacite_t": cap_by_id.get(mid, 0),
                "revenu_estime_usd": round(rev_m, 2),
                "cout_carburant_estime_usd": round(cout_m, 2),
                "rentabilite_estimee_usd": round(rev_m - cout_m, 2),
                "tonnes_par_heure": round(t / h, 3) if h > 0 else 0.0,
                "litres_par_heure": round(f / h, 3) if h > 0 else 0.0,
                "litres_par_tonne": round(f / t, 3) if t > 0 else 0.0,
                "cycles_par_heure": round(cy / h, 3) if h > 0 else 0.0,
                "tonnes_par_cycle": round(t / cy, 3) if cy > 0 else 0.0,
            }
        )
    df_machines = pd.DataFrame(rows_detail) if rows_detail else pd.DataFrame()
    df_fuel = pd.DataFrame(fuel_logs) if fuel_logs else pd.DataFrame()
    df_kpi = pd.DataFrame([kpi])

    return {"kpi": kpi, "df_machines": df_machines, "df_fuel": df_fuel, "df_kpi": df_kpi}

# ==============================================================================
# BASE DE DONNÉES POUR SAUVEGARDE DES DONNÉES (Images)
# ==============================================================================
DATABASE_FILE = os.path.join(_APP_DATA_ROOT, "app_database.json")
BACKUP_DIR = os.path.join(_APP_DATA_ROOT, "backups")

def get_database():
    """Charge la base de données depuis le fichier JSON"""
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return create_empty_database()
    else:
        return create_empty_database()

def create_empty_database():
    """Crée une base de données vide"""
    return {
        "images_metadata": {},
        "settings": {},
        "backup_info": {
            "last_backup": None,
            "backup_count": 0
        },
        "version": "1.0"
    }

def save_database(db):
    """Sauvegarde la base JSON de façon atomique (réduit les fichiers corrompus / logins impossibles)."""
    parent = os.path.dirname(os.path.abspath(DATABASE_FILE)) or "."
    try:
        os.makedirs(parent, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(
            suffix=".json.tmp", prefix="app_db_", dir=parent, text=True
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, DATABASE_FILE)
            return True
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
    except Exception:
        try:
            with open(DATABASE_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False


def slugify_tenant_name(name):
    s = "".join(c.lower() if c.isalnum() else "-" for c in (name or "").strip())
    parts = [x for x in s.split("-") if x]
    return "-".join(parts)[:48] if parts else "societe"


def get_tenants_registry():
    """Registre des entreprises clientes (abonnement, plan, actif)."""
    db = get_database()
    if "tenants" not in db or not isinstance(db.get("tenants"), dict) or not db["tenants"]:
        db["tenants"] = {
            "default": {
                "name": "Entreprise par défaut",
                "plan": "standard",
                "subscription_end": "",
                "active": True,
            }
        }
        save_database(db)
    return db["tenants"]


def save_tenants_registry(tenants_dict):
    db = get_database()
    db["tenants"] = tenants_dict
    save_database(db)


def delete_tenant_and_data(tenant_id, user_mgr_ref):
    """
    Supprime une entreprise du registre SaaS, retire tous ses utilisateurs (hors Gestionnaire),
    et efface le dossier TENANT_DATA_DIR/<id>. Interdit pour default et __platform__.
    Retourne (ok, message).
    """
    tid = _safe_tenant_id(tenant_id)
    if tid in ("default", "__platform__"):
        return False, "Cet identifiant est réservé et ne peut pas être supprimé."
    reg = get_tenants_registry()
    if tid not in reg:
        return False, f"Aucune entreprise enregistrée sous l'identifiant « {tid} »."
    removed = 0
    kept = []
    for u in user_mgr_ref.users_db:
        if u.get("role") == "Gestionnaire":
            kept.append(u)
            continue
        if _safe_tenant_id(u.get("tenant_id", "default")) == tid:
            removed += 1
            continue
        kept.append(u)
    user_mgr_ref.users_db = kept
    user_mgr_ref.persist_users()
    tenants = get_tenants_registry().copy()
    del tenants[tid]
    save_tenants_registry(tenants)
    tenant_dir = os.path.join(TENANT_DATA_DIR, tid)
    folder_err = None
    if os.path.isdir(tenant_dir):
        try:
            shutil.rmtree(tenant_dir)
        except OSError as e:
            folder_err = str(e)
    try:
        get_shared_manager_v16.clear()
        get_shared_staff_v17.clear()
        get_shared_contracts_v2.clear()
        get_shared_audit_v1.clear()
    except Exception:
        pass
    if folder_err:
        return True, (
            f"Entreprise **{tid}** retirée du registre ; **{removed}** compte(s) supprimé(s). "
            f"Dossier de données : échec partiel — {folder_err}"
        )
    return True, f"Entreprise **{tid}** supprimée. **{removed}** compte(s) utilisateur retiré(s). Données sur disque effacées."


def get_tenant_record(tenant_id):
    """Fiche SaaS du tenant uniquement si présent dans le registre (pas de repli silencieux sur default)."""
    tid = _safe_tenant_id(tenant_id)
    return get_tenants_registry().get(tid)


def is_tenant_billing_ok(tenant_id):
    """Abonnement actif et (si renseignée) date de fin non dé surpassée."""
    tid = _safe_tenant_id(tenant_id)
    if tid in ("default", "__platform__"):
        return True
    t = get_tenant_record(tid)
    if not t:
        return False
    if t.get("active") is False:
        return False
    end = (t.get("subscription_end") or "").strip()
    if not end:
        return True
    try:
        return date.fromisoformat(end[:10]) >= date.today()
    except Exception:
        return True


def _current_tenant_id_for_limits():
    try:
        return _safe_tenant_id(st.session_state.get("tenant_id", "default"))
    except Exception:
        return "default"


def render_gestionnaire_console(user_mgr_ref):
    """Console réservée au rôle Gestionnaire (facturation multi-entreprises)."""
    st.markdown('<div class="content-card">', unsafe_allow_html=True)
    st.subheader("Plateforme SaaS — espaces entreprises")
    st.caption(
        "Modèle multi-tenant : chaque **entreprise cliente** a son identifiant, son abonnement et **sa base SQLite isolée**. "
        "Les utilisateurs (admin, RH, etc.) sont rattachés à une entreprise et ne voient que ses données."
    )
    tenants = get_tenants_registry().copy()

    tab_a, tab_b = st.tabs(["Entreprises & abonnements", "Nouveau client SaaS"])
    with tab_a:
        rows = []
        users_by_tenant = {}
        for u in user_mgr_ref.users_db:
            if u.get("role") == "Gestionnaire":
                continue
            tid_u = _safe_tenant_id(u.get("tenant_id", "default"))
            users_by_tenant[tid_u] = users_by_tenant.get(tid_u, 0) + 1
        for tid, meta in tenants.items():
            rows.append(
                {
                    "Identifiant": tid,
                    "Nom": meta.get("name", ""),
                    "RCCM": (meta.get("rccm") or "").strip() or "—",
                    "Contact": (meta.get("email") or meta.get("phone") or "—"),
                    "Plan": meta.get("plan", ""),
                    "Fin abonnement": meta.get("subscription_end", "") or "—",
                    "Actif": "Oui" if meta.get("active", True) else "Non",
                    "Comptes utilisateurs": users_by_tenant.get(tid, 0),
                }
            )
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

        st.markdown("##### Modifier une entreprise")
        st.caption(
            "Mettre à jour le nom, les identifiants fiscaux (**NIF / SIRET** et **RCCM**), les coordonnées, "
            "le plan, la date de fin d'abonnement, le statut actif et le logo."
        )
        _reg_all = get_tenants_registry()
        _edit_list = sorted(k for k in _reg_all.keys() if k != "__platform__")
        if not _edit_list:
            st.info("Aucune entreprise dans le registre.")
        else:
            edit_tid = st.selectbox(
                "Entreprise à modifier",
                _edit_list,
                key="gest_edit_pick",
            )
            em = dict(_reg_all.get(edit_tid) or {})
            ge1, ge2 = st.columns(2)
            with ge1:
                ge_name = st.text_input(
                    "Nom de l'entreprise",
                    value=str(em.get("name", "") or ""),
                    key=f"gest_edit_name_{edit_tid}",
                )
                _ge_plans = ["free", "standard", "premium"]
                _ge_pi = _ge_plans.index(em["plan"]) if em.get("plan") in _ge_plans else 1
                ge_plan = st.selectbox(
                    "Plan SaaS", _ge_plans, index=_ge_pi, key=f"gest_edit_plan_{edit_tid}"
                )
            with ge2:
                _ge_end_raw = (em.get("subscription_end") or "").strip()
                try:
                    _ge_end_d = (
                        date.fromisoformat(_ge_end_raw[:10])
                        if len(_ge_end_raw) >= 10
                        else date.today().replace(month=12, day=31)
                    )
                except Exception:
                    _ge_end_d = date.today().replace(month=12, day=31)
                ge_end = st.date_input(
                    "Fin d'abonnement", value=_ge_end_d, key=f"gest_edit_end_{edit_tid}"
                )
                ge_active = st.checkbox(
                    "Entreprise active",
                    value=bool(em.get("active", True)),
                    key=f"gest_edit_active_{edit_tid}",
                )
            ge_addr = st.text_area(
                "Adresse",
                value=str(em.get("address", "") or ""),
                key=f"gest_edit_addr_{edit_tid}",
                height=68,
            )
            gca, gcb = st.columns(2)
            with gca:
                ge_phone = st.text_input(
                    "Téléphone",
                    value=str(em.get("phone", "") or ""),
                    key=f"gest_edit_phone_{edit_tid}",
                )
                ge_email = st.text_input(
                    "Email",
                    value=str(em.get("email", "") or ""),
                    key=f"gest_edit_email_{edit_tid}",
                )
            with gcb:
                ge_tax = st.text_input(
                    "N° fiscal / NIF / SIRET",
                    value=str(em.get("tax_id", "") or ""),
                    key=f"gest_edit_tax_{edit_tid}",
                )
                ge_rccm = st.text_input(
                    "RCCM",
                    value=str(em.get("rccm", "") or ""),
                    key=f"gest_edit_rccm_{edit_tid}",
                    help="Registre du Commerce et du Crédit Mobilier.",
                )
            ge_bank = st.text_input(
                "Infos bancaires",
                value=str(em.get("bank_info", "") or ""),
                key=f"gest_edit_bank_{edit_tid}",
            )
            ge_logo = st.file_uploader(
                "Nouveau logo (sidebar & documents)",
                type=["png", "jpg", "jpeg", "webp"],
                key=f"gest_edit_logo_{edit_tid}",
            )
            ge_rm_logo = st.checkbox(
                "Supprimer le logo fichier sur le serveur",
                key=f"gest_edit_rm_logo_{edit_tid}",
            )
            if st.button("Enregistrer les modifications", type="primary", key="gest_edit_save_btn"):
                _tw = get_tenants_registry().copy()
                if edit_tid not in _tw:
                    st.error("Entreprise introuvable. Rechargez la page.")
                else:
                    rec = dict(_tw[edit_tid])
                    rec.update(
                        {
                            "name": (ge_name or "").strip(),
                            "plan": ge_plan,
                            "subscription_end": ge_end.isoformat(),
                            "active": bool(ge_active),
                            "address": (ge_addr or "").strip(),
                            "phone": (ge_phone or "").strip(),
                            "email": (ge_email or "").strip(),
                            "tax_id": (ge_tax or "").strip(),
                            "rccm": (ge_rccm or "").strip(),
                            "bank_info": (ge_bank or "").strip(),
                        }
                    )
                    _tw[edit_tid] = rec
                    save_tenants_registry(_tw)
                    if ge_rm_logo:
                        delete_tenant_branding_logo(edit_tid)
                    elif ge_logo is not None:
                        save_tenant_branding_logo(edit_tid, ge_logo)
                    st.success(f"Fiche **{edit_tid}** enregistrée.")
                    st.rerun()

        st.markdown("##### Activer / désactiver une entreprise")
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            pick = st.selectbox("Entreprise", list(tenants.keys()), key="gest_pick_tenant")
        with c2:
            act = st.toggle("Active", value=tenants[pick].get("active", True), key="gest_act_toggle")
        with c3:
            if st.button("Enregistrer le statut", key="gest_save_act"):
                tenants[pick]["active"] = act
                save_tenants_registry(tenants)
                st.success("Statut mis à jour.")
                st.rerun()

        st.markdown("##### Supprimer une entreprise")
        st.caption(
            "Action **irréversible** : retrait du registre SaaS, suppression de **tous les comptes** "
            "rattachés à ce tenant (sauf le rôle plateforme) et effacement du dossier de données SQLite / pièces jointes."
        )
        deletable = sorted(k for k in tenants.keys() if k not in ("default", "__platform__"))
        if not deletable:
            st.info("Aucune entreprise client supprimable (l'espace « default » est toujours conservé).")
        else:
            d1, d2 = st.columns([2, 1])
            with d1:
                del_pick = st.selectbox(
                    "Entreprise à supprimer", deletable, key="gest_del_pick"
                )
            with d2:
                st.write("")
                st.write("")
            confirm_id = st.text_input(
                "Confirmer en recopiant l'identifiant exact",
                placeholder=del_pick,
                key="gest_del_confirm",
            )
            if st.button("Supprimer définitivement cette entreprise", type="primary", key="gest_del_go"):
                if (confirm_id or "").strip() != del_pick:
                    st.error("La confirmation doit correspondre exactement à l'identifiant sélectionné.")
                else:
                    ok_del, msg_del = delete_tenant_and_data(del_pick, user_mgr_ref)
                    if ok_del:
                        st.success(msg_del)
                        st.rerun()
                    else:
                        st.error(msg_del)

    with tab_b:
        st.markdown("##### Assistant — entreprise + premier administrateur (recommandé)")
        st.caption(
            "Une seule action : enregistre l'entreprise dans le registre SaaS, initialise sa base de données "
            "et crée le compte **Administrateur** que le client utilisera pour se connecter."
        )
        w_name = st.text_input("Nom de l'entreprise (affiché / facturation)", key="gest_wiz_name")
        c1, c2 = st.columns(2)
        with c1:
            w_tid = st.text_input(
                "Identifiant technique (vide = dérivé du nom)", key="gest_wiz_tid"
            )
        with c2:
            w_plan = st.selectbox("Plan SaaS", ["free", "standard", "premium"], key="gest_wiz_plan")
        w_end = st.date_input(
            "Fin d'abonnement",
            value=date.today().replace(month=12, day=31),
            key="gest_wiz_end",
        )
        st.markdown("**Coordonnées & identité visuelle (factures / sidebar)**")
        w_addr = st.text_area(
            "Adresse",
            placeholder="Siège, ville, pays…",
            key="gest_wiz_addr",
            height=68,
        )
        wc1, wc2 = st.columns(2)
        with wc1:
            w_phone = st.text_input("Téléphone", key="gest_wiz_phone")
            w_email = st.text_input("Email", key="gest_wiz_email")
        with wc2:
            w_tax = st.text_input("N° fiscal / NIF / SIRET", key="gest_wiz_tax")
            w_rccm = st.text_input(
                "RCCM",
                key="gest_wiz_rccm",
                help="Registre du Commerce et du Crédit Mobilier (facultatif).",
            )
        w_bank = st.text_input("Infos bancaires (facultatif)", key="gest_wiz_bank")
        w_logo = st.file_uploader(
            "Logo entreprise (sidebar & documents)",
            type=["png", "jpg", "jpeg", "webp"],
            key="gest_wiz_logo",
            help="Affiché dans la barre latérale à la place du logo GOOD ENGINEERS pour cette entreprise.",
        )
        st.caption(
            "Ces informations sont enregistrées dans la fiche SaaS ; le logo est stocké dans le dossier de l'entreprise."
        )
        st.markdown("**Compte administrateur de l'entreprise**")
        c3, c4 = st.columns(2)
        with c3:
            w_adm_u = st.text_input("Identifiant de connexion admin", key="gest_wiz_adm_user")
        with c4:
            w_adm_p = st.text_input("Mot de passe admin", type="password", key="gest_wiz_adm_pass")
        w_adm_p2 = st.text_input(
            "Confirmer le mot de passe", type="password", key="gest_wiz_adm_pass2"
        )
        if st.button("Créer l'espace client + administrateur", type="primary", key="gest_wiz_go"):
            tid = (
                _safe_tenant_id(w_tid.strip())
                if w_tid.strip()
                else _safe_tenant_id(slugify_tenant_name(w_name))
            )
            if not w_name.strip():
                st.error("Indiquez un nom d'entreprise.")
            elif tid == "default":
                st.error("Réservez un identifiant autre que « default ».")
            elif tid in tenants:
                st.error("Cet identifiant d'entreprise existe déjà.")
            elif not w_adm_u.strip() or not w_adm_p.strip():
                st.error("Identifiant et mot de passe administrateur requis.")
            elif w_adm_p != w_adm_p2:
                st.error("Les deux mots de passe ne correspondent pas.")
            elif any(str(u.get("user", "")).strip().lower() == w_adm_u.strip().lower() for u in user_mgr_ref.users_db):
                st.error("Cet identifiant utilisateur existe déjà (choisissez un autre login).")
            else:
                tenants[tid] = {
                    "name": w_name.strip(),
                    "plan": w_plan,
                    "subscription_end": w_end.isoformat(),
                    "active": True,
                    "address": (w_addr or "").strip(),
                    "phone": (w_phone or "").strip(),
                    "email": (w_email or "").strip(),
                    "tax_id": (w_tax or "").strip(),
                    "rccm": (w_rccm or "").strip(),
                    "bank_info": (w_bank or "").strip(),
                }
                save_tenants_registry(tenants)
                dbp = os.path.abspath(os.path.join(TENANT_DATA_DIR, tid, "geo_data.db"))
                init_database_at_path(dbp)
                if w_logo is not None:
                    save_tenant_branding_logo(tid, w_logo)
                ok = user_mgr_ref.add_user(
                    w_adm_u.strip(), w_adm_p.strip(), "Administrateur", tenant_id=tid
                )
                if not ok:
                    del tenants[tid]
                    save_tenants_registry(tenants)
                    st.error(
                        "Échec lors de la création de l'administrateur : l'entreprise n'a pas été conservée. Réessayez."
                    )
                else:
                    try:
                        get_shared_users_v15.clear()
                    except Exception:
                        pass
                    st.success(
                        f"**Espace client prêt.** Entreprise `{tid}` — l'admin **{w_adm_u.strip()}** peut se connecter "
                        "depuis la page de connexion habituelle (même URL que vos utilisateurs)."
                    )
                    st.rerun()

        with st.expander("Création en deux étapes (sans admin tout de suite, ou admin supplémentaire)", expanded=False):
            st.markdown("##### Créer uniquement une entreprise")
            n_name = st.text_input("Nom de l'entreprise", key="gest_new_name")
            n_tid = st.text_input(
                "Identifiant technique (lettres, chiffres, tirets — vide = auto)", key="gest_new_tid"
            )
            n_plan = st.selectbox("Plan SaaS", ["free", "standard", "premium"], key="gest_new_plan")
            n_end = st.date_input(
                "Fin d'abonnement", value=date.today().replace(month=12, day=31), key="gest_new_end"
            )
            n_addr = st.text_area("Adresse", key="gest_new_addr", height=60)
            na1, na2 = st.columns(2)
            with na1:
                n_phone = st.text_input("Téléphone", key="gest_new_phone")
                n_email = st.text_input("Email", key="gest_new_email")
            with na2:
                n_tax = st.text_input("N° fiscal / NIF / SIRET", key="gest_new_tax")
                n_rccm = st.text_input(
                    "RCCM",
                    key="gest_new_rccm",
                    help="Registre du Commerce et du Crédit Mobilier (facultatif).",
                )
            n_bank = st.text_input("Infos bancaires", key="gest_new_bank")
            n_logo = st.file_uploader(
                "Logo entreprise",
                type=["png", "jpg", "jpeg", "webp"],
                key="gest_new_logo",
            )
            if st.button("Créer l'entreprise", key="gest_create_tenant"):
                tid = (
                    _safe_tenant_id(n_tid.strip())
                    if n_tid.strip()
                    else _safe_tenant_id(slugify_tenant_name(n_name))
                )
                tenants2 = get_tenants_registry().copy()
                if not n_name.strip():
                    st.error("Indiquez un nom d'entreprise.")
                elif tid == "default":
                    st.error("Réservez un identifiant autre que « default ».")
                elif tid in tenants2:
                    st.error("Cet identifiant existe déjà.")
                else:
                    tenants2[tid] = {
                        "name": n_name.strip(),
                        "plan": n_plan,
                        "subscription_end": n_end.isoformat(),
                        "active": True,
                        "address": (n_addr or "").strip(),
                        "phone": (n_phone or "").strip(),
                        "email": (n_email or "").strip(),
                        "tax_id": (n_tax or "").strip(),
                        "rccm": (n_rccm or "").strip(),
                        "bank_info": (n_bank or "").strip(),
                    }
                    save_tenants_registry(tenants2)
                    dbp = os.path.abspath(os.path.join(TENANT_DATA_DIR, tid, "geo_data.db"))
                    init_database_at_path(dbp)
                    if n_logo is not None:
                        save_tenant_branding_logo(tid, n_logo)
                    st.success(f"Entreprise créée : **{tid}**. Base initialisée.")
                    st.rerun()

            st.markdown("---")
            st.markdown("##### Créer un administrateur pour une entreprise existante")
            st.caption("Ajoute un compte Administrateur rattaché au tenant choisi (ex. second admin).")
            t_list = [k for k in get_tenants_registry().keys() if k != "__platform__"]
            adm_tenant = st.selectbox("Entreprise cible", t_list, key="gest_adm_tenant")
            adm_u = st.text_input("Identifiant admin", key="gest_adm_user")
            adm_p = st.text_input("Mot de passe admin", type="password", key="gest_adm_pass")
            if st.button("Créer l'administrateur", key="gest_create_adm"):
                if not adm_u.strip() or not adm_p.strip():
                    st.error("Identifiant et mot de passe requis.")
                elif any(str(u.get("user", "")).strip().lower() == adm_u.strip().lower() for u in user_mgr_ref.users_db):
                    st.error("Cet identifiant existe déjà.")
                elif user_mgr_ref.add_user(
                    adm_u.strip(), adm_p.strip(), "Administrateur", tenant_id=adm_tenant
                ):
                    try:
                        get_shared_users_v15.clear()
                    except Exception:
                        pass
                    st.success(f"Administrateur **{adm_u.strip()}** créé pour `{adm_tenant}`.")
                    st.rerun()
                else:
                    st.error("Impossible de créer l'utilisateur.")

    st.markdown('</div>', unsafe_allow_html=True)


def save_image_metadata(equipment_name, file_path, file_size, upload_date):
    """Sauvegarde les métadonnées d'une image"""
    db = get_database()
    safe_name = equipment_name.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
    
    db["images_metadata"][safe_name] = {
        "equipment_name": equipment_name,
        "file_path": file_path,
        "file_size": file_size,
        "upload_date": upload_date,
        "last_modified": upload_date
    }
    
    return save_database(db)

def get_image_metadata(equipment_name):
    """Récupère les métadonnées d'une image"""
    db = get_database()
    safe_name = equipment_name.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
    return db["images_metadata"].get(safe_name, None)

def delete_image_metadata(equipment_name):
    """Supprime les métadonnées d'une image"""
    db = get_database()
    safe_name = equipment_name.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
    
    if safe_name in db["images_metadata"]:
        del db["images_metadata"][safe_name]
        return save_database(db)
    return True

def create_backup():
    """Crée une sauvegarde de la base de données et des images"""
    try:
        # Créer le dossier de sauvegarde s'il n'existe pas
        if not os.path.exists(BACKUP_DIR):
            os.makedirs(BACKUP_DIR)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_folder = os.path.join(BACKUP_DIR, f"backup_{timestamp}")
        os.makedirs(backup_folder)
        
        # Sauvegarder la base de données
        db = get_database()
        backup_db_path = os.path.join(backup_folder, "database.json")
        with open(backup_db_path, 'w', encoding='utf-8') as f:
            json.dump(db, f, indent=2, ensure_ascii=False)
        
        # Sauvegarder les images
        images_dir = get_equipment_images_dir()
        if os.path.exists(images_dir):
            backup_images_dir = os.path.join(backup_folder, "images_engins")
            import shutil
            shutil.copytree(images_dir, backup_images_dir)
        
        # Mettre à jour les informations de sauvegarde
        db["backup_info"]["last_backup"] = timestamp
        db["backup_info"]["backup_count"] = db["backup_info"].get("backup_count", 0) + 1
        save_database(db)
        
        return True, backup_folder
    except Exception as e:
        return False, str(e)

def list_backups():
    """Liste toutes les sauvegardes disponibles"""
    if not os.path.exists(BACKUP_DIR):
        return []
    
    backups = []
    for item in os.listdir(BACKUP_DIR):
        backup_path = os.path.join(BACKUP_DIR, item)
        if os.path.isdir(backup_path) and item.startswith("backup_"):
            backups.append({
                "name": item,
                "path": backup_path,
                "date": item.replace("backup_", "").replace("_", " "),
                "size": get_folder_size(backup_path)
            })
    
    # Trier par date (plus récent en premier)
    backups.sort(key=lambda x: x["name"], reverse=True)
    return backups

def get_folder_size(folder_path):
    """Calcule la taille d'un dossier en MB"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                total_size += os.path.getsize(filepath)
    return round(total_size / (1024 * 1024), 2)  # Convertir en MB

def restore_backup(backup_path):
    """Restaure une sauvegarde"""
    try:
        backup_db_path = os.path.join(backup_path, "database.json")
        backup_images_dir = os.path.join(backup_path, "images_engins")
        
        # Restaurer la base de données
        if os.path.exists(backup_db_path):
            import shutil
            shutil.copy2(backup_db_path, DATABASE_FILE)
        
        # Restaurer les images
        if os.path.exists(backup_images_dir):
            images_dir = get_equipment_images_dir()
            if os.path.exists(images_dir):
                shutil.rmtree(images_dir)
            shutil.copytree(backup_images_dir, images_dir)
        
        return True
    except Exception as e:
        return False, str(e)

# ==============================================================================
# GESTION DES IMAGES D'ENGINS
# ==============================================================================
# ==============================================================================
# FONCTIONS POUR LA GESTION DU LOGO
# ==============================================================================

def get_logo_dir():
    """Crée et retourne le chemin du dossier logos"""
    logo_dir = os.path.join(_APP_DATA_ROOT, "logos")
    if not os.path.exists(logo_dir):
        os.makedirs(logo_dir)
    return logo_dir

def save_logo(uploaded_file):
    """Sauvegarde le logo uploadé"""
    try:
        logo_dir = get_logo_dir()
        logo_path = os.path.join(logo_dir, "good_engineers_logo.png")
        
        with open(logo_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        # Sauvegarder les métadonnées dans la base de données
        db = get_database()
        db["logo_metadata"] = {
            "file_path": logo_path,
            "file_size": os.path.getsize(logo_path),
            "upload_date": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "file_name": uploaded_file.name
        }
        save_database(db)
        
        return True, "Logo sauvegardé avec succès"
    except Exception as e:
        return False, f"Erreur lors de la sauvegarde: {str(e)}"

def get_logo_path():
    """Retourne le chemin du logo s'il existe"""
    logo_dir = get_logo_dir()
    logo_path = os.path.join(logo_dir, "good_engineers_logo.png")
    if os.path.exists(logo_path):
        return logo_path
    return None


def _image_file_to_data_url(logo_path: str):
    """Convertit une image disque en data URL (PNG / JPEG / WEBP)."""
    if not logo_path or not os.path.exists(logo_path):
        return None
    try:
        import base64
        with open(logo_path, "rb") as f:
            img_data = f.read()
            base64_data = base64.b64encode(img_data).decode()
        lp = logo_path.lower()
        if lp.endswith(".png"):
            mime_type = "image/png"
        elif lp.endswith(".jpg") or lp.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif lp.endswith(".webp"):
            mime_type = "image/webp"
        else:
            mime_type = "image/png"
        return f"data:{mime_type};base64,{base64_data}"
    except Exception:
        return None


def get_tenant_branding_dir(tenant_id: str) -> str:
    """Dossier branding d'une entreprise (logo sidebar, etc.)."""
    tid = _safe_tenant_id(tenant_id)
    d = os.path.join(TENANT_DATA_DIR, tid, "branding")
    os.makedirs(d, exist_ok=True)
    return d


def get_tenant_logo_path(tenant_id: str):
    """Chemin du logo entreprise si présent (company_logo.* dans branding/)."""
    tid = _safe_tenant_id(tenant_id)
    if tid in ("", "__platform__"):
        return None
    bd = os.path.join(TENANT_DATA_DIR, tid, "branding")
    if not os.path.isdir(bd):
        return None
    for name in (
        "company_logo.png",
        "company_logo.jpg",
        "company_logo.jpeg",
        "company_logo.webp",
    ):
        p = os.path.join(bd, name)
        if os.path.isfile(p):
            return p
    return None


def save_tenant_branding_logo(tenant_id, uploaded_file) -> bool:
    """Enregistre le logo entreprise pour la sidebar (remplace l'ancien fichier)."""
    if uploaded_file is None:
        return False
    try:
        bd = get_tenant_branding_dir(tenant_id)
        for f in os.listdir(bd):
            if f.startswith("company_logo."):
                try:
                    os.remove(os.path.join(bd, f))
                except OSError:
                    pass
        ext = os.path.splitext(uploaded_file.name)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            ext = ".png"
        dest = os.path.join(bd, f"company_logo{ext}")
        with open(dest, "wb") as f:
            f.write(uploaded_file.getbuffer())
        return True
    except Exception:
        return False


def delete_tenant_branding_logo(tenant_id) -> bool:
    """Supprime le fichier logo entreprise (revient au logo global GOOD ENGINEERS)."""
    p = get_tenant_logo_path(tenant_id)
    if p and os.path.isfile(p):
        try:
            os.remove(p)
            return True
        except OSError:
            return False
    return False


def _finance_company_profile_path(tid: str) -> str:
    return os.path.join(TENANT_DATA_DIR, _safe_tenant_id(tid), "branding", "finance_company_profile.json")


def load_finance_company_profile(company_info, tid: str) -> None:
    """Charge logo / coordonnées / cachet / signature pour les factures (par tenant)."""
    p = _finance_company_profile_path(tid)
    if not os.path.isfile(p):
        return
    try:
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        mapping = (
            ("company_name", "company_name"),
            ("address", "address"),
            ("phone", "phone"),
            ("email", "email"),
            ("tax_id", "tax_id"),
            ("rccm", "rccm"),
            ("bank_info", "bank_info"),
            ("logo_base64", "logo_base64"),
            ("logo_mime", "logo_mime"),
            ("stamp_base64", "stamp_base64"),
            ("stamp_mime", "stamp_mime"),
            ("signature_base64", "signature_base64"),
            ("signature_mime", "signature_mime"),
            ("signatory_title", "signatory_title"),
            ("signatory_name", "signatory_name"),
            ("document_stamp_legend", "document_stamp_legend"),
        )
        for json_key, attr in mapping:
            if json_key not in d:
                continue
            val = d[json_key]
            if val is None:
                continue
            if isinstance(val, str) and val == "" and attr in (
                "stamp_base64",
                "signature_base64",
                "logo_base64",
            ):
                setattr(company_info, attr, None)
                continue
            setattr(company_info, attr, val)
    except Exception:
        pass


def save_finance_company_profile(company_info, tid: str) -> bool:
    """Sauvegarde la fiche entreprise Finance (factures) pour le tenant."""
    try:
        p = _finance_company_profile_path(tid)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        d = {
            "company_name": company_info.company_name,
            "address": company_info.address,
            "phone": company_info.phone,
            "email": company_info.email,
            "tax_id": company_info.tax_id,
            "rccm": getattr(company_info, "rccm", "") or "",
            "bank_info": company_info.bank_info,
            "logo_base64": company_info.logo_base64,
            "logo_mime": getattr(company_info, "logo_mime", "image/png"),
            "stamp_base64": getattr(company_info, "stamp_base64", None),
            "stamp_mime": getattr(company_info, "stamp_mime", "image/png"),
            "signature_base64": getattr(company_info, "signature_base64", None),
            "signature_mime": getattr(company_info, "signature_mime", "image/png"),
            "signatory_title": getattr(company_info, "signatory_title", ""),
            "signatory_name": getattr(company_info, "signatory_name", ""),
            "document_stamp_legend": getattr(company_info, "document_stamp_legend", ""),
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_logo_url():
    """Logo sidebar : entreprise (tenant) si défini, sinon logo global GOOD ENGINEERS."""
    try:
        tid_cur = _safe_tenant_id(st.session_state.get("tenant_id", "default"))
    except Exception:
        tid_cur = "default"
    if tid_cur not in ("__platform__",):
        tlogo = get_tenant_logo_path(tid_cur)
        if tlogo:
            du = _image_file_to_data_url(tlogo)
            if du:
                return du
    logo_path = get_logo_path()
    return _image_file_to_data_url(logo_path) if logo_path else None

def delete_logo():
    """Supprime le logo"""
    try:
        logo_path = get_logo_path()
        if logo_path and os.path.exists(logo_path):
            os.remove(logo_path)
        
        # Supprimer les métadonnées
        db = get_database()
        if "logo_metadata" in db:
            del db["logo_metadata"]
        save_database(db)
        
        return True, "Logo supprimé avec succès"
    except Exception as e:
        return False, f"Erreur lors de la suppression: {str(e)}"

def get_equipment_images_dir():
    """Crée et retourne le chemin du dossier pour les images d'engins"""
    images_dir = os.path.join(_APP_DATA_ROOT, "images_engins")
    if not os.path.exists(images_dir):
        os.makedirs(images_dir)
    return images_dir

def save_equipment_image(equipment_name, uploaded_file):
    """Sauvegarde une image d'engin dans le dossier local et dans la base de données"""
    try:
        images_dir = get_equipment_images_dir()
        # Normaliser le nom de l'engin pour le nom de fichier
        safe_name = equipment_name.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
        # Déterminer l'extension du fichier
        file_extension = os.path.splitext(uploaded_file.name)[1] or ".jpg"
        file_path = os.path.join(images_dir, f"{safe_name}{file_extension}")
        
        # Sauvegarder le fichier
        uploaded_file.seek(0)
        file_content = uploaded_file.read()
        file_size = len(file_content)
        
        with open(file_path, "wb") as f:
            f.write(file_content)
        
        # Sauvegarder les métadonnées dans la base de données
        upload_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_image_metadata(equipment_name, file_path, file_size, upload_date)
        
        return True, file_path
    except Exception as e:
        return False, str(e)

def get_equipment_image_path(equipment_name):
    """Retourne le chemin de l'image locale si elle existe, sinon None"""
    images_dir = get_equipment_images_dir()
    safe_name = equipment_name.lower().replace(" ", "_").replace("é", "e").replace("è", "e")
    
    # Chercher les extensions communes
    extensions = [".jpg", ".jpeg", ".png", ".gif", ".webp"]
    for ext in extensions:
        file_path = os.path.join(images_dir, f"{safe_name}{ext}")
        if os.path.exists(file_path):
            return file_path
    
    return None

def get_equipment_image_url(equipment_name, default_url):
    """Retourne l'URL de l'image locale (en base64) si elle existe, sinon l'URL par défaut"""
    local_path = get_equipment_image_path(equipment_name)
    if local_path:
        try:
            import base64
            with open(local_path, "rb") as f:
                img_bytes = f.read()
                img_base64 = base64.b64encode(img_bytes).decode()
                # Déterminer le type MIME
                ext = os.path.splitext(local_path)[1].lower()
                mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png" if ext == ".png" else "image/gif" if ext == ".gif" else "image/webp"
                return f"data:{mime_type};base64,{img_base64}"
        except Exception as e:
            # En cas d'erreur, retourner l'URL par défaut
            return default_url
    return default_url

def get_gold_bar_image_url(default_url):
    """Retourne l'URL de l'image locale du lingot d'or (en base64) si elle existe, sinon l'URL par défaut"""
    local_path = get_equipment_image_path("Lingot_Or")
    if local_path:
        try:
            import base64
            with open(local_path, "rb") as f:
                img_bytes = f.read()
                img_base64 = base64.b64encode(img_bytes).decode()
                # Déterminer le type MIME
                ext = os.path.splitext(local_path)[1].lower()
                mime_type = "image/jpeg" if ext in [".jpg", ".jpeg"] else "image/png" if ext == ".png" else "image/gif" if ext == ".gif" else "image/webp"
                return f"data:{mime_type};base64,{img_base64}"
        except Exception as e:
            # En cas d'erreur, retourner l'URL par défaut
            return default_url
    return default_url

class ContractManager:
    """Gère les contrats miniers"""
    def __init__(self, tenant_id="default"):
        self.tenant_id = _safe_tenant_id(tenant_id or "default")
        self.contracts = []
        self.company_info = CompanyInfo()
        load_finance_company_profile(self.company_info, self.tenant_id)
        # Contrats par défaut
        self.contracts.append(MiningContract("CONT-001", "Contrat Mine A - BCM", "BCM", 15.0, None, 500000.0, "Mine A"))  # 15 $/BCM, 500K$ négociés
        self.contracts.append(MiningContract("CONT-002", "Contrat Mine B - Horaires", "HOURLY", 200.0, None, 1200000.0, "Mine B"))  # 200 $/heure, 1.2M$ négociés
    
    def add_contract(self, contract_id, name, contract_type, rate, start_date=None, somme_negociee=None, client_name=None, rate_currency="USD", original_rate=None):
        """Ajoute un nouveau contrat"""
        for c in self.contracts:
            if c.contract_id == contract_id:
                return False  # ID déjà utilisé
        
        # Convertir le taux en USD si nécessaire
        if rate_currency != "USD":
            rates = get_exchange_rates()
            if rate_currency == "EUR":
                rate_usd = rate / rates['EUR']
            elif rate_currency == "CFA":
                rate_usd = rate / rates['CFA']
            else:
                rate_usd = rate
        else:
            rate_usd = rate
        
        new_contract = MiningContract(contract_id, name, contract_type, rate_usd, start_date, somme_negociee, client_name, rate_currency, original_rate or rate)
        self.contracts.append(new_contract)
        return True
    
    def update_contract_rate(self, contract_id, new_rate, currency="USD"):
        """Met à jour le taux d'un contrat"""
        contract = self.get_contract(contract_id)
        if contract:
            rates = get_exchange_rates()
            contract.update_rate(new_rate, currency, rates)
            return True
        return False
    
    def get_contract(self, contract_id):
        """Retourne un contrat par son ID"""
        for c in self.contracts:
            if c.contract_id == contract_id:
                return c
        return None
    
    def update_contract_from_machines(self, fleet_manager):
        """Met à jour les volumes/heures des contrats à partir des machines de la flotte"""
        for contract in self.contracts:
            if not contract.active:
                continue
            
            # Réinitialiser les compteurs journaliers pour recalculer
            contract.volume_jour = 0
            contract.heures_jour = 0
            
            # Traiter les machines associées à ce contrat
            machines_to_process = []
            if contract.machines_ids:
                # Utiliser seulement les machines assignées au contrat
                for machine_id in contract.machines_ids:
                    machine = next((m for m in fleet_manager.machines if m.id == machine_id), None)
                    if machine:
                        machines_to_process.append(machine)
            else:
                # Si aucune machine n'est assignée, utiliser toutes les machines actives
                machines_to_process = [m for m in fleet_manager.machines if m.status == "Active"]
            
            # Traiter chaque machine
            for machine in machines_to_process:
                if contract.contract_type == "BCM":
                    # Calcul du volume BCM basé sur la production réelle
                    # Chaque cycle transporte la capacité de la machine
                    # Volume BCM = Production (tonnes) × facteur de conversion (tonnes vers BCM)
                    # On utilise la production journalière, hebdomadaire, mensuelle et annuelle
                    
                    # Production journalière (basée sur les cycles du jour)
                    # Approximation: cycles_jour ≈ cycles_totaux × (h_jour / h_total)
                    if machine.cycle > 0 and machine.engine_hours > 0:
                        # Calculer la production journalière proportionnelle
                        production_jour = (machine.production_tonnes * machine.h_jour) / max(1, machine.engine_hours)
                        production_semaine = (machine.production_tonnes * machine.h_semaine) / max(1, machine.engine_hours)
                        production_mois = (machine.production_tonnes * machine.h_mois) / max(1, machine.engine_hours)
                        production_annee = machine.production_tonnes  # Production totale
                        
                        # Convertir en BCM
                        bcm_jour = production_jour * contract.tonnes_to_bcm_factor
                        bcm_semaine = production_semaine * contract.tonnes_to_bcm_factor
                        bcm_mois = production_mois * contract.tonnes_to_bcm_factor
                        bcm_annee = production_annee * contract.tonnes_to_bcm_factor
                        
                        # Ajouter les volumes (la méthode add_volume les accumule)
                        contract.volume_jour += bcm_jour
                        contract.volume_semaine += bcm_semaine
                        contract.volume_mois += bcm_mois
                        contract.volume_annee += bcm_annee
                elif contract.contract_type == "HOURLY":
                    # Pour les contrats horaires, ajouter les heures travaillées
                    contract.heures_jour += machine.h_jour
                    contract.heures_semaine += machine.h_semaine
                    contract.heures_mois += machine.h_mois
                    contract.heures_annee += machine.h_mois  # Utiliser h_mois comme approximation annuelle (ou créer h_annee si disponible)
            
            # Recalculer les revenus
            contract._recalculate_revenue()
    
    def get_contracts_df(self):
        """Retourne un DataFrame avec tous les contrats et leurs revenus"""
        data = []
        for c in self.contracts:
            if c.contract_type == "BCM":
                data.append({
                    "ID Contrat": c.contract_id,
                    "Nom": c.name,
                    "Client": getattr(c, 'client_name', None) or "N/A",
                    "Type": "BCM (Volume)",
                    "Taux": f"{getattr(c, 'original_rate', c.rate):,.2f} {getattr(c, 'rate_currency', 'USD')}/BCM",
                    "Taux USD": f"{c.rate:,.2f} $/BCM",
                    "Somme Négociée": f"{getattr(c, 'somme_negociee', 0):,.2f} {getattr(c, 'somme_negociee_currency', 'USD')}" if getattr(c, 'somme_negociee', None) else "N/A",
                    "Volume Jour (BCM)": round(c.volume_jour, 2),
                    "Volume Semaine (BCM)": round(c.volume_semaine, 2),
                    "Volume Mois (BCM)": round(c.volume_mois, 2),
                    "Volume Année (BCM)": round(c.volume_annee, 2),
                    "Revenu Jour ($)": round(c.revenu_jour, 2),
                    "Revenu Semaine ($)": round(c.revenu_semaine, 2),
                    "Revenu Mois ($)": round(c.revenu_mois, 2),
                    "Revenu Année ($)": round(c.revenu_annee, 2),
                    "Statut": "✅ Actif" if c.active else "❌ Inactif"
                })
            else:  # HOURLY
                data.append({
                    "ID Contrat": c.contract_id,
                    "Nom": c.name,
                    "Client": getattr(c, 'client_name', None) or "N/A",
                    "Type": "Horaire",
                    "Taux": f"{getattr(c, 'original_rate', c.rate):,.2f} {getattr(c, 'rate_currency', 'USD')}/heure",
                    "Taux USD": f"{c.rate:,.2f} $/heure",
                    "Somme Négociée": f"{getattr(c, 'somme_negociee', 0):,.2f} {getattr(c, 'somme_negociee_currency', 'USD')}" if getattr(c, 'somme_negociee', None) else "N/A",
                    "Heures Jour": round(c.heures_jour, 2),
                    "Heures Semaine": round(c.heures_semaine, 2),
                    "Heures Mois": round(c.heures_mois, 2),
                    "Heures Année": round(c.heures_annee, 2),
                    "Revenu Jour ($)": round(c.revenu_jour, 2),
                    "Revenu Semaine ($)": round(c.revenu_semaine, 2),
                    "Revenu Mois ($)": round(c.revenu_mois, 2),
                    "Revenu Année ($)": round(c.revenu_annee, 2),
                    "Statut": "✅ Actif" if c.active else "❌ Inactif"
                })
        
        if not data:
            return pd.DataFrame(columns=[
                "ID Contrat", "Nom", "Client", "Type", "Taux", "Somme Négociée ($)",
                "Revenu Jour ($)", "Revenu Semaine ($)", "Revenu Mois ($)", "Revenu Année ($)", "Statut"
            ])
        
        return pd.DataFrame(data)
    
    def get_total_revenue_summary(self):
        """Retourne un résumé des revenus totaux"""
        total_jour = sum(c.revenu_jour for c in self.contracts if c.active)
        total_semaine = sum(c.revenu_semaine for c in self.contracts if c.active)
        total_mois = sum(c.revenu_mois for c in self.contracts if c.active)
        total_annee = sum(c.revenu_annee for c in self.contracts if c.active)
        
        return {
            "Revenu Jour ($)": total_jour,
            "Revenu Semaine ($)": total_semaine,
            "Revenu Mois ($)": total_mois,
            "Revenu Année ($)": total_annee
        }
    
    def generate_invoice_html(self, contract, period="mois", period_value=None):
        """Génère une facture HTML pour un contrat donné"""
        from datetime import datetime
        
        if period == "mois":
            if period_value is None:
                period_value = datetime.now().strftime("%B %Y")
            amount = contract.revenu_mois
            if contract.contract_type == "BCM":
                quantity = contract.volume_mois
                unit = "BCM"
            else:
                quantity = contract.heures_mois
                unit = "heures"
            period_label = f"Mois de {period_value}"
        elif period == "semaine":
            if period_value is None:
                period_value = f"Semaine du {datetime.now().strftime('%d/%m/%Y')}"
            amount = contract.revenu_semaine
            if contract.contract_type == "BCM":
                quantity = contract.volume_semaine
                unit = "BCM"
            else:
                quantity = contract.heures_semaine
                unit = "heures"
            period_label = period_value
        elif period == "jour":
            if period_value is None:
                period_value = datetime.now().strftime("%d/%m/%Y")
            amount = contract.revenu_jour
            if contract.contract_type == "BCM":
                quantity = contract.volume_jour
                unit = "BCM"
            else:
                quantity = contract.heures_jour
                unit = "heures"
            period_label = f"Jour du {period_value}"
        else:  # annuel
            if period_value is None:
                period_value = datetime.now().year
            amount = contract.revenu_annee
            if contract.contract_type == "BCM":
                quantity = contract.volume_annee
                unit = "BCM"
            else:
                quantity = contract.heures_annee
                unit = "heures"
            period_label = f"Année {period_value}"
        
        # Logo en base64 si disponible
        logo_html = ""
        if self.company_info.logo_base64:
            _lm = getattr(self.company_info, "logo_mime", "image/png")
            logo_html = f'<img src="data:{_lm};base64,{self.company_info.logo_base64}" style="max-height: 100px; max-width: 200px;" alt="Logo">'

        ci = self.company_info
        stamp_sig_html = ""
        _has_stamp = bool(getattr(ci, "stamp_base64", None))
        _has_sig = bool(getattr(ci, "signature_base64", None))
        if _has_stamp or _has_sig or (getattr(ci, "signatory_name", "") or "").strip() or (getattr(ci, "signatory_title", "") or "").strip():
            _parts = [
                '<div class="signatory-block" style="margin-top:36px;padding-top:16px;border-top:1px solid #ddd;">',
                '<div style="display:flex;justify-content:flex-end;align-items:flex-end;gap:36px;flex-wrap:wrap;">',
            ]
            if _has_stamp:
                _sm = getattr(ci, "stamp_mime", "image/png")
                _parts.append(
                    f'<div style="text-align:center;"><img src="data:{_sm};base64,{ci.stamp_base64}" '
                    f'alt="Cachet" style="max-height:120px;max-width:180px;object-fit:contain;" />'
                    f'<br/><span style="font-size:11px;color:#555;">Cachet</span></div>'
                )
            if _has_sig:
                _xm = getattr(ci, "signature_mime", "image/png")
                _parts.append(
                    f'<div style="text-align:center;"><img src="data:{_xm};base64,{ci.signature_base64}" '
                    f'alt="Signature" style="max-height:72px;max-width:240px;object-fit:contain;" />'
                    f'<br/><span style="font-size:11px;color:#555;">Signature</span></div>'
                )
            _parts.append('<div style="text-align:right;min-width:220px;">')
            _st = (getattr(ci, "signatory_title", "") or "").strip()
            _sn = (getattr(ci, "signatory_name", "") or "").strip()
            if _st:
                _parts.append(f'<p style="margin:4px 0;">{html.escape(_st)}</p>')
            if _sn:
                _parts.append(f'<p style="margin:4px 0;"><strong>{html.escape(_sn)}</strong></p>')
            _leg = (getattr(ci, "document_stamp_legend", "") or "").strip()
            if _leg:
                _parts.append(f'<p style="font-size:11px;color:#666;margin-top:8px;">{html.escape(_leg)}</p>')
            _parts.append("</div></div></div>")
            stamp_sig_html = "".join(_parts)
        
        # Ligne de somme négociée si disponible
        somme_negociee_row = ""
        if getattr(contract, 'somme_negociee', None):
            somme_negociee_row = f'<tr><td colspan="4"><strong>Somme Négociée Contractuelle:</strong></td><td>{contract.somme_negociee:,.2f} $</td></tr>'
        
        _rccm_inv = (getattr(self.company_info, "rccm", None) or "").strip()
        _invoice_rccm_line = f"<p>RCCM : {html.escape(_rccm_inv)}</p>" if _rccm_inv else ""

        invoice_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Facture {contract.contract_id}</title>
    <style>
        @media print {{
            @page {{
                size: A4;
                margin: 2cm;
            }}
            body {{
                font-family: Arial, sans-serif;
                color: #000;
            }}
        }}
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            color: #333;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 3px solid #F5B800;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }}
        .company-info {{
            flex: 1;
        }}
        .logo {{
            flex: 1;
            text-align: right;
        }}
        h1 {{
            color: #000;
            font-size: 28px;
            margin: 0;
        }}
        h2 {{
            color: #333;
            font-size: 18px;
            margin-top: 5px;
        }}
        .invoice-info {{
            display: flex;
            justify-content: space-between;
            margin: 30px 0;
        }}
        .invoice-details {{
            background-color: #f5f5f5;
            padding: 15px;
            border-radius: 5px;
            flex: 1;
            margin-right: 20px;
        }}
        .client-info {{
            background-color: #fff;
            padding: 15px;
            border: 1px solid #ddd;
            border-radius: 5px;
            flex: 1;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 30px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #F5B800;
            color: #000;
            font-weight: bold;
        }}
        .total-row {{
            background-color: #f5f5f5;
            font-weight: bold;
            font-size: 16px;
        }}
        .footer {{
            margin-top: 50px;
            padding-top: 20px;
            border-top: 2px solid #ddd;
            text-align: center;
            color: #666;
        }}
        .amount-box {{
            background-color: #F5B800;
            color: #000;
            padding: 15px;
            border-radius: 5px;
            text-align: center;
            font-size: 24px;
            font-weight: bold;
            margin: 20px 0;
        }}
    </style>
</head>
<body>
    <div class="header">
        <div class="company-info">
            <h1>{self.company_info.company_name}</h1>
            <p>{self.company_info.address}</p>
            <p>Tél: {self.company_info.phone} | Email: {self.company_info.email}</p>
            <p>{html.escape(str(self.company_info.tax_id))}</p>
            {_invoice_rccm_line}
            <p>{html.escape(str(self.company_info.bank_info))}</p>
        </div>
        <div class="logo">
            {logo_html}
        </div>
    </div>
    
    <h2>FACTURE N° {contract.contract_id} - {period_label}</h2>
    
    <div class="invoice-info">
        <div class="invoice-details">
            <strong>Informations Facture:</strong><br>
            Date d'émission: {datetime.now().strftime("%d/%m/%Y")}<br>
            Période: {period_label}<br>
            Contrat: {contract.name}<br>
            Type: {"BCM (Volume Transporté)" if contract.contract_type == "BCM" else "Horaire (Heures Travaillées)"}
        </div>
        <div class="client-info">
            <strong>Client:</strong><br>
            {getattr(contract, 'client_name', None) if getattr(contract, 'client_name', None) else "Non spécifié"}<br>
        </div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Description</th>
                <th>Quantité</th>
                <th>Unité</th>
                <th>Taux</th>
                <th>Montant ($)</th>
            </tr>
        </thead>
        <tbody>
            <tr>
                <td>{"Prestation de transport (BCM)" if contract.contract_type == "BCM" else "Prestation horaire"}</td>
                <td>{quantity:,.2f}</td>
                <td>{unit}</td>
                <td>{contract.rate:,.2f} $/{unit}</td>
                <td>{amount:,.2f} $</td>
            </tr>
            {somme_negociee_row}
            <tr class="total-row">
                <td colspan="4"><strong>TOTAL À PAYER</strong></td>
                <td><strong>{amount:,.2f} $</strong></td>
            </tr>
        </tbody>
    </table>
    
    <div class="amount-box">
        MONTANT TOTAL: {amount:,.2f} $ USD
    </div>
    
    {stamp_sig_html}
    
    <div class="footer">
        <p><strong>{self.company_info.company_name}</strong></p>
        <p>{self.company_info.address} | {self.company_info.phone} | {self.company_info.email}</p>
        <p style="margin-top: 20px; font-size: 12px;">
            Cette facture est générée automatiquement par le système de gestion GOOD ENGINEERS OS<br>
            Merci de votre confiance.
        </p>
    </div>
</body>
</html>
        """
        return invoice_html

class Machine:
    def __init__(self, id, model, m_type, capacity, hourly_rate=150, initial_hours=0):
        self.id = id; self.model = model; self.type = m_type
        self.capacity = capacity; self.hourly_rate = hourly_rate # Taux en USD par défaut
        self.status = "Active"; self.operator = "Non Assigné"
        
        # PRODUCTION
        self.cycle = 0; self.production_tonnes = 0
        self.breakdown_reason = ""; self.breakdown_time = ""
        self.load_type = "N/A"; self.load_time = None; self.destination = ""
        self.alert_trigger = False
        
        # COMPTEURS TEMPS
        self.engine_hours = initial_hours
        self.h_jour = 0; self.h_semaine = 0; self.h_mois = 0
        
        # MAINTENANCE
        self.last_pm_hours = 0; self.next_pm_interval = 250
        self.next_maintenance = None
        
        # CARBURANT & RENTABILITÉ
        self.fuel_tank = 0
        self.fuel_logs = []
        # Consommation accumulée
        self.cons_jour = 0; self.cons_mois = 0; self.cons_annee = 0; self.cons_total = 0
        
        self.lat = 12.3; self.lon = -1.5

        # Spécifications complémentaires (pelles, chargeuses, bulldozers…)
        self.bucket_capacity_m3 = 0.0
        self.blade_capacity_m3 = 0.0
        self.operating_weight_t = 0.0

    def update_hours(self, hours):
        """Met à jour les heures moteur - PERSISTÉ EN SQLITE"""
        if hours > self.engine_hours: 
            self.engine_hours = hours
            self.save_to_db()

    def add_fuel(self, liters, price_per_liter_usd, currency_used="USD", original_price=0):
        """Ajoute du carburant avec traçabilité de la devise - PERSISTÉ EN SQLITE"""
        fuel_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_usd = liters * price_per_liter_usd
        
        # Persister dans SQLite
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO fuel_logs 
                (machine_id, date, litres, price_per_liter_usd, currency_used, original_price, total_usd, engine_hours_at_refuel)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (self.id, fuel_date, liters, price_per_liter_usd, currency_used, original_price, total_usd, self.engine_hours))

        # Mettre à jour le réservoir et sauvegarder la machine
        self.fuel_tank = 100
        self.save_to_db()
        
        # Garder une copie en mémoire pour compatibilité (optionnel, peut être supprimé)
        self.fuel_logs.append({
            "Date": fuel_date,
            "Litres": liters, 
            "Prix Unitaire ($)": price_per_liter_usd, 
            "Devise Origine": currency_used,
            "Prix Origine": original_price,
            "Total ($)": total_usd,
            "H-Mètre": self.engine_hours
        })
    
    def save_to_db(self):
        """Sauvegarde l'état actuel de la machine dans SQLite"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO machines 
                (id, model, type, capacity, hourly_rate, status, operator, engine_hours, fuel_tank,
                 lat, lon, cycle, production_tonnes, breakdown_reason, breakdown_time, load_type,
                 load_time, destination, alert_trigger, h_jour, h_semaine, h_mois, last_pm_hours,
                 next_pm_interval, next_maintenance, cons_jour, cons_mois, cons_annee, cons_total,
                 bucket_capacity_m3, blade_capacity_m3, operating_weight_t, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                self.id, self.model, self.type, self.capacity, self.hourly_rate, self.status, self.operator,
                self.engine_hours, self.fuel_tank, self.lat, self.lon, self.cycle, self.production_tonnes,
                self.breakdown_reason, self.breakdown_time, self.load_type, 
                str(self.load_time) if self.load_time else None, self.destination,
                1 if self.alert_trigger else 0, self.h_jour, self.h_semaine, self.h_mois,
                self.last_pm_hours, self.next_pm_interval,
                self.next_maintenance.strftime("%Y-%m-%d") if self.next_maintenance else None,
                self.cons_jour, self.cons_mois, self.cons_annee, self.cons_total,
                float(getattr(self, "bucket_capacity_m3", 0) or 0),
                float(getattr(self, "blade_capacity_m3", 0) or 0),
                float(getattr(self, "operating_weight_t", 0) or 0),
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
    
    def _apply_row_from_sqlite(self, row):
        """Applique une ligne `SELECT * FROM machines` (sqlite3.Row) sans nouvelle requête."""
        self.model = row["model"]
        self.type = row["type"]
        self.capacity = row["capacity"]
        self.hourly_rate = row["hourly_rate"]
        self.status = row["status"]
        self.operator = row["operator"]
        self.engine_hours = row["engine_hours"]
        self.fuel_tank = row["fuel_tank"]
        self.lat = row["lat"]
        self.lon = row["lon"]
        self.cycle = row["cycle"]
        self.production_tonnes = row["production_tonnes"]
        self.breakdown_reason = row["breakdown_reason"]
        self.breakdown_time = row["breakdown_time"]
        self.load_type = row["load_type"]
        self.load_time = datetime.strptime(row["load_time"], "%Y-%m-%d %H:%M:%S") if row["load_time"] else None
        self.destination = row["destination"]
        self.alert_trigger = bool(row["alert_trigger"])
        self.h_jour = row["h_jour"]
        self.h_semaine = row["h_semaine"]
        self.h_mois = row["h_mois"]
        self.last_pm_hours = row["last_pm_hours"]
        self.next_pm_interval = row["next_pm_interval"]
        self.next_maintenance = (
            datetime.strptime(row["next_maintenance"], "%Y-%m-%d").date() if row["next_maintenance"] else None
        )
        self.cons_jour = row["cons_jour"]
        self.cons_mois = row["cons_mois"]
        self.cons_annee = row["cons_annee"]
        self.cons_total = row["cons_total"]
        rk = row.keys()
        self.bucket_capacity_m3 = float(row["bucket_capacity_m3"] or 0) if "bucket_capacity_m3" in rk else 0.0
        self.blade_capacity_m3 = float(row["blade_capacity_m3"] or 0) if "blade_capacity_m3" in rk else 0.0
        self.operating_weight_t = float(row["operating_weight_t"] or 0) if "operating_weight_t" in rk else 0.0

    def load_from_db(self):
        """Charge les données de la machine depuis SQLite"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM machines WHERE id = ?", (self.id,))
            row = cursor.fetchone()
            if row:
                self._apply_row_from_sqlite(row)
    
    def get_fuel_logs_from_db(self):
        """Récupère l'historique des ravitaillements depuis SQLite"""
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT date, litres, price_per_liter_usd, currency_used, original_price, total_usd, engine_hours_at_refuel
                FROM fuel_logs WHERE machine_id = ? ORDER BY date DESC
            """, (self.id,))
            logs = []
            for row in cursor.fetchall():
                logs.append({
                    "Date": row['date'],
                    "Litres": row['litres'],
                    "Prix Unitaire ($)": row['price_per_liter_usd'],
                    "Devise Origine": row['currency_used'],
                    "Prix Origine": row['original_price'],
                    "Total ($)": row['total_usd'],
                    "H-Mètre": row['engine_hours_at_refuel']
                })
            return logs 

    def get_maintenance_status(self):
        return self.next_pm_interval - (self.engine_hours - self.last_pm_hours)


class MaintenanceRecord:
    """Enregistre une maintenance/réparation avec les pièces changées"""
    def __init__(self, machine_id, maintenance_type, date_maintenance, mechanic_name, pieces_changed=None):
        self.machine_id = machine_id
        self.maintenance_type = maintenance_type  # "PM 250h", "PM 500h", "PM 1000h", "Réparation", etc.
        self.date_maintenance = date_maintenance
        self.mechanic_name = mechanic_name
        self.pieces_changed = pieces_changed if pieces_changed else []  # Liste de dict {"nom": "Filtre à huile", "quantite": 2, "cout": 150.0}
        self.engine_hours_at_maintenance = 0  # Heures moteur au moment de la maintenance
        self.notes = ""

class MaintenanceAlert:
    """Représente une alerte de maintenance planifiée"""
    def __init__(self, machine_id, planned_date, maintenance_type, created_by, created_at=None):
        self.machine_id = machine_id
        self.planned_date = planned_date
        self.maintenance_type = maintenance_type
        self.created_by = created_by
        self.created_at = created_at if created_at else datetime.now()
        self.acknowledged_by = []  # Liste des utilisateurs qui ont vu l'alerte
        self.status = "Planifiée"  # "Planifiée", "En cours", "Terminée", "Annulée"

class StockMovement:
    """Représente un mouvement de stock (entrée ou sortie)"""
    def __init__(self, part_name, movement_type, quantity, date_movement, reference=None, notes=""):
        self.part_name = part_name  # Nom de la pièce
        self.movement_type = movement_type  # "ENTREE" ou "SORTIE"
        self.quantity = quantity  # Quantité
        self.date_movement = date_movement  # Date du mouvement
        self.reference = reference  # Référence (ex: numéro de commande, ID maintenance)
        self.notes = notes  # Notes additionnelles
        self.created_by = None  # Utilisateur qui a créé le mouvement
        self.demandeur = None  # Personne qui demande la pièce (pour les sorties)

class StockManager:
    """Gère les quantités en stock et les mouvements"""
    def __init__(self):
        self.stock_levels = {}  # Dict: {"nom_piece": {"quantite": 10, "seuil_min": 5, "unite": "unité"}}
        self.movements = []  # Historique des mouvements de stock
    
    def initialize_stock(self, part_name, initial_quantity=0, seuil_min=5, unite="unité"):
        """Initialise le stock pour une pièce"""
        if part_name not in self.stock_levels:
            self.stock_levels[part_name] = {
                "quantite": initial_quantity,
                "seuil_min": seuil_min,
                "unite": unite
            }
    
    def add_stock_entry(self, part_name, quantity, date_entry=None, reference=None, notes="", created_by=None, demandeur=None):
        """Ajoute une entrée de stock"""
        if date_entry is None:
            date_entry = date.today()
        
        if part_name not in self.stock_levels:
            self.initialize_stock(part_name)
        
        self.stock_levels[part_name]["quantite"] += quantity
        
        movement = StockMovement(part_name, "ENTREE", quantity, date_entry, reference, notes)
        movement.created_by = created_by
        movement.demandeur = demandeur
        self.movements.append(movement)
        
        return movement
    
    def remove_stock_entry(self, part_name, quantity, date_exit=None, reference=None, notes="", created_by=None, demandeur=None):
        """Retire du stock (sortie)"""
        if date_exit is None:
            date_exit = date.today()
        
        if part_name not in self.stock_levels:
            self.initialize_stock(part_name)
        
        # Vérifier si le stock est suffisant
        if self.stock_levels[part_name]["quantite"] < quantity:
            return None  # Stock insuffisant
        
        self.stock_levels[part_name]["quantite"] -= quantity
        
        movement = StockMovement(part_name, "SORTIE", quantity, date_exit, reference, notes)
        movement.created_by = created_by
        movement.demandeur = demandeur
        self.movements.append(movement)
        
        return movement
    
    def set_stock_level(self, part_name, quantity, seuil_min=None):
        """Définit le niveau de stock manuellement"""
        if part_name not in self.stock_levels:
            self.initialize_stock(part_name)
        
        self.stock_levels[part_name]["quantite"] = quantity
        if seuil_min is not None:
            self.stock_levels[part_name]["seuil_min"] = seuil_min
    
    def set_seuil_min(self, part_name, seuil_min):
        """Définit le seuil minimum pour une pièce"""
        if part_name not in self.stock_levels:
            self.initialize_stock(part_name)
        
        self.stock_levels[part_name]["seuil_min"] = seuil_min
    
    def get_stock_level(self, part_name):
        """Retourne le niveau de stock d'une pièce"""
        if part_name in self.stock_levels:
            return self.stock_levels[part_name]
        return {"quantite": 0, "seuil_min": 5, "unite": "unité"}
    
    def get_low_stock_items(self):
        """Retourne les pièces avec stock bas (en dessous du seuil minimum)"""
        low_stock = []
        for part_name, stock_info in self.stock_levels.items():
            if stock_info["quantite"] <= stock_info["seuil_min"]:
                low_stock.append({
                    "nom": part_name,
                    "quantite": stock_info["quantite"],
                    "seuil_min": stock_info["seuil_min"],
                    "unite": stock_info.get("unite", "unité")
                })
        return low_stock
    
    def get_movements_for_part(self, part_name):
        """Retourne l'historique des mouvements pour une pièce"""
        return [m for m in self.movements if m.part_name == part_name]

class PartsCatalog:
    """Catalogue des pièces de rechange"""
    def __init__(self):
        # Catalogue par défaut avec des pièces courantes
        self.parts = [
            {"nom": "Filtre à huile moteur", "cout": 25.0, "categorie": "Filtres"},
            {"nom": "Filtre à air", "cout": 45.0, "categorie": "Filtres"},
            {"nom": "Filtre à carburant", "cout": 30.0, "categorie": "Filtres"},
            {"nom": "Filtre hydraulique", "cout": 55.0, "categorie": "Filtres"},
            {"nom": "Huile moteur (L)", "cout": 12.0, "categorie": "Lubrifiants"},
            {"nom": "Huile hydraulique (L)", "cout": 15.0, "categorie": "Lubrifiants"},
            {"nom": "Graisse (kg)", "cout": 8.0, "categorie": "Lubrifiants"},
            {"nom": "Pneu avant", "cout": 850.0, "categorie": "Pneus"},
            {"nom": "Pneu arrière", "cout": 1200.0, "categorie": "Pneus"},
            {"nom": "Chambre à air", "cout": 150.0, "categorie": "Pneus"},
            {"nom": "Courroie de distribution", "cout": 120.0, "categorie": "Transmission"},
            {"nom": "Courroie d'accessoires", "cout": 85.0, "categorie": "Transmission"},
            {"nom": "Joint de culasse", "cout": 200.0, "categorie": "Moteur"},
            {"nom": "Segment de piston", "cout": 350.0, "categorie": "Moteur"},
            {"nom": "Bougie de préchauffage", "cout": 25.0, "categorie": "Moteur"},
            {"nom": "Injecteur", "cout": 450.0, "categorie": "Moteur"},
            {"nom": "Pompe à eau", "cout": 380.0, "categorie": "Moteur"},
            {"nom": "Radiateur", "cout": 650.0, "categorie": "Moteur"},
            {"nom": "Ventilateur", "cout": 420.0, "categorie": "Moteur"},
            {"nom": "Alternateur", "cout": 850.0, "categorie": "Électrique"},
            {"nom": "Démarreur", "cout": 650.0, "categorie": "Électrique"},
            {"nom": "Batterie", "cout": 320.0, "categorie": "Électrique"},
            {"nom": "Joint torique", "cout": 5.0, "categorie": "Divers"},
            {"nom": "Vis/Écrous (lot)", "cout": 15.0, "categorie": "Divers"},
            {"nom": "Freins plaquettes", "cout": 180.0, "categorie": "Freinage"},
            {"nom": "Disque de frein", "cout": 280.0, "categorie": "Freinage"},
            {"nom": "Maître-cylindre", "cout": 450.0, "categorie": "Freinage"},
        ]
    
    def add_part(self, nom, cout, categorie="Divers"):
        """Ajoute une pièce au catalogue"""
        self.parts.append({"nom": nom, "cout": float(cout), "categorie": categorie})
    
    def get_parts_by_category(self, categorie=None):
        """Retourne les pièces filtrées par catégorie"""
        if categorie:
            return [p for p in self.parts if p["categorie"] == categorie]
        return self.parts
    
    def get_part_by_name(self, nom):
        """Retourne une pièce par son nom"""
        for p in self.parts:
            if p["nom"] == nom:
                return p
        return None
    
    def get_categories(self):
        """Retourne toutes les catégories disponibles"""
        return sorted(set(p["categorie"] for p in self.parts))

class MaintenanceManager:
    """Gère les maintenances, alertes et historique"""
    def __init__(self):
        self.maintenance_records = []  # Historique des maintenances effectuées
        self.active_alerts = []  # Alertes actives de maintenance planifiée
        self.parts_catalog = PartsCatalog()  # Catalogue de pièces
        self.stock_manager = StockManager()  # Gestionnaire de stock
    
    def create_maintenance_alert(self, machine_id, planned_date, maintenance_type, created_by):
        """Crée une alerte de maintenance planifiée visible par tous les utilisateurs"""
        alert = MaintenanceAlert(machine_id, planned_date, maintenance_type, created_by)
        self.active_alerts.append(alert)
        return alert
    
    def add_maintenance_record(self, machine_id, maintenance_type, date_maintenance, mechanic_name, pieces_changed=None):
        """Ajoute un enregistrement de maintenance avec les pièces changées"""
        record = MaintenanceRecord(machine_id, maintenance_type, date_maintenance, mechanic_name, pieces_changed)
        self.maintenance_records.append(record)
        
        # Marquer l'alerte correspondante comme terminée si elle existe
        for alert in self.active_alerts:
            if alert.machine_id == machine_id and alert.status == "Planifiée":
                # Si le type correspond exactement, ou si c'est une réparation (qui peut couvrir n'importe quelle maintenance)
                if alert.maintenance_type == maintenance_type or maintenance_type == "Réparation":
                    alert.status = "Terminée"
        
        return record
    
    def get_alerts_for_machine(self, machine_id):
        """Retourne toutes les alertes actives pour une machine"""
        return [a for a in self.active_alerts if a.machine_id == machine_id and a.status == "Planifiée"]
    
    def get_all_active_alerts(self):
        """Retourne toutes les alertes actives"""
        return [a for a in self.active_alerts if a.status == "Planifiée"]
    
    def acknowledge_alert(self, alert, username):
        """Marque une alerte comme vue par un utilisateur"""
        if username not in alert.acknowledged_by:
            alert.acknowledged_by.append(username)
    
    def get_maintenance_history_for_machine(self, machine_id):
        """Retourne l'historique des maintenances pour une machine"""
        return [r for r in self.maintenance_records if r.machine_id == machine_id]


def _ensure_fleet_summary_df(df):
    """Complète le schéma du récap flotte (évite KeyError: 'Production (T)' si DataFrame vide ou partiel)."""
    _defaults = (
        ("ID", ""), ("Type", ""), ("Modèle", ""), ("Statut", "Active"), ("Opérateur", ""),
        ("Production (T)", 0), ("Cycles", 0), ("Tps Cycle Moy (min)", 0.0),
        ("Prochaine PM", ""), ("Maint. Date", ""), ("Carburant (%)", 0),
        ("H. Total", 0), ("H. Run Jour", 0.0), ("H. Run Hebdo", 0.0), ("H. Run Mois", 0.0),
        ("Conso. Jour (L)", 0), ("Conso. Shift (L)", 0), ("Conso. Voyage (L)", 0.0),
        ("Conso. Mois (L)", 0), ("Conso. An (L)", 0),
        ("Rev. Jour ($)", 0), ("Rev. Hebdo ($)", 0), ("Rev. Mensuel ($)", 0),
        ("Coût Fuel ($)", 0), ("Rentabilité ($)", 0),
        ("lat", 0.0), ("lon", 0.0),
    )
    try:
        if df is None:
            df = pd.DataFrame()
        out = df.copy()
        for col, default in _defaults:
            if col not in out.columns:
                out[col] = default
        return out
    except Exception:
        return pd.DataFrame(columns=[c for c, _ in _defaults])


def _fleet_col_sum_int(df, col_name):
    try:
        df = _ensure_fleet_summary_df(df)
        if col_name not in df.columns:
            return 0
        return int(pd.to_numeric(df[col_name], errors="coerce").fillna(0).sum())
    except Exception:
        return 0


def _fleet_statut_count(df, statut):
    try:
        df = _ensure_fleet_summary_df(df)
        if "Statut" not in df.columns:
            return 0
        return int((df["Statut"] == statut).sum())
    except Exception:
        return 0


class FleetManager:
    def __init__(self):
        self.maintenance_manager = MaintenanceManager()
        # Charger les machines depuis SQLite (plateforme vide au démarrage)
        self.machines = self.load_machines_from_db()
    
    def load_machines_from_db(self):
        """Charge toutes les machines depuis SQLite (1 connexion, pas de N+1 requêtes)."""
        machines = []
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM machines ORDER BY id")
            rows = cursor.fetchall()
            if not rows:
                return []
            ids = [r["id"] for r in rows]
            fuel_by_mid = {mid: [] for mid in ids}
            placeholders = ",".join("?" * len(ids))
            cursor.execute(
                f"""
                SELECT machine_id, date, litres, price_per_liter_usd, currency_used, original_price, total_usd, engine_hours_at_refuel
                FROM fuel_logs WHERE machine_id IN ({placeholders})
                ORDER BY machine_id, date DESC
                """,
                ids,
            )
            for frow in cursor.fetchall():
                mid = frow["machine_id"]
                if mid not in fuel_by_mid:
                    fuel_by_mid[mid] = []
                fuel_by_mid[mid].append(
                    {
                        "Date": frow["date"],
                        "Litres": frow["litres"],
                        "Prix Unitaire ($)": frow["price_per_liter_usd"],
                        "Devise Origine": frow["currency_used"],
                        "Prix Origine": frow["original_price"],
                        "Total ($)": frow["total_usd"],
                        "H-Mètre": frow["engine_hours_at_refuel"],
                    }
                )
            for row in rows:
                machine = Machine(
                    row["id"],
                    row["model"],
                    row["type"],
                    row["capacity"],
                    row["hourly_rate"],
                    row["engine_hours"],
                )
                machine._apply_row_from_sqlite(row)
                machine.fuel_logs = fuel_by_mid.get(row["id"], [])
                machines.append(machine)
        return machines
    
    def save_all_machines_to_db(self):
        """Sauvegarde toutes les machines dans SQLite"""
        for machine in self.machines:
            machine.save_to_db()

    def add_machine(self, id, model, m_type, capacity):
        """Ajoute une machine - PERSISTÉ EN SQLITE"""
        if any(m.id == id for m in self.machines): return False
        new_machine = Machine(id, model, m_type, capacity)
        new_machine.save_to_db()  # Sauvegarder immédiatement
        self.machines.append(new_machine)
        return True

    def remove_machine(self, id):
        """Supprime une machine - PERSISTÉ EN SQLITE"""
        # Supprimer de SQLite (CASCADE supprimera aussi fuel_logs, maintenance_logs, breakdowns)
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM machines WHERE id = ?", (id,))
        # Supprimer de la liste en mémoire
        self.machines = [m for m in self.machines if m.id != id]

    def set_maintenance_date(self, machine_id, date_obj, maintenance_type="Maintenance préventive", created_by=None):
        """Planifie une maintenance et crée une alerte pour tous les utilisateurs"""
        for m in self.machines:
            if m.id == machine_id:
                m.next_maintenance = date_obj
                # Créer une alerte visible par tous les utilisateurs
                if created_by is None:
                    created_by = "Système"
                self.maintenance_manager.create_maintenance_alert(machine_id, date_obj, maintenance_type, created_by)
                return True
        return False

    def set_machine_rate(self, machine_id, new_rate):
        """Modifie le taux horaire - PERSISTÉ EN SQLITE"""
        for m in self.machines:
            if m.id == machine_id: 
                m.hourly_rate = new_rate
                m.save_to_db()
                break

    def assign_smart_destination(self, truck, material_type):
        if "STÉRILE" in material_type: truck.destination = "WASTE DUMP"
        else: truck.destination = "ROM PAD"
        truck.alert_trigger = True

    def report_breakdown(self, machine_id, reason):
        """Signale une panne - PERSISTÉ EN SQLITE"""
        breakdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for m in self.machines:
            if m.id == machine_id:
                m.status = "Panne"
                m.breakdown_reason = reason
                m.breakdown_time = breakdown_time
                m.load_time = None
                m.save_to_db()
                
                # Enregistrer la panne dans SQLite
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO breakdowns (machine_id, reason, breakdown_time, status)
                        VALUES (?, ?, ?, 'En cours')
                    """, (machine_id, reason, breakdown_time))
                break

    def repair_machine(self, machine_id, mechanic_name=None, pieces_changed=None, notes=""):
        """Répare une machine et enregistre les pièces changées - PERSISTÉ EN SQLITE"""
        repair_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for m in self.machines:
            if m.id == machine_id:
                m.status = "Active"
                m.breakdown_reason = ""
                m.alert_trigger = False
                m.save_to_db()
                
                # Mettre à jour le statut de la panne dans SQLite
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        UPDATE breakdowns
                        SET status = 'Réparé', repair_time = ?, mechanic_name = ?
                        WHERE id = (
                            SELECT id FROM breakdowns
                            WHERE machine_id = ? AND status = 'En cours'
                            ORDER BY id DESC LIMIT 1
                        )
                    """, (repair_time, mechanic_name, machine_id))
                
                # Enregistrer la réparation avec les pièces changées
                if mechanic_name:
                    record = self.maintenance_manager.add_maintenance_record(
                        machine_id, "Réparation", date.today(), mechanic_name, pieces_changed
                    )
                    record.engine_hours_at_maintenance = m.engine_hours
                    record.notes = notes
                    
                    # Persister la maintenance dans SQLite
                    self._save_maintenance_to_db(machine_id, "Réparation", date.today(), mechanic_name, m.engine_hours, notes, pieces_changed)
                    
                    # Déduire automatiquement le stock + enregistrer pose durée de vie
                    if pieces_changed:
                        for piece in pieces_changed:
                            part_name = piece.get("nom")
                            quantity = piece.get("quantite", 1)
                            reference = f"REP-{machine_id}"
                            stock_info = self.maintenance_manager.stock_manager.get_stock_level(part_name)
                            if stock_info["quantite"] >= quantity:
                                self.maintenance_manager.stock_manager.remove_stock_entry(
                                    part_name, quantity, date.today(), reference,
                                    f"Réparation sur {machine_id}", mechanic_name
                                )
                            # Snapshot de production au moment de la pose
                            if part_name:
                                try:
                                    record_part_pose(machine_id, part_name,
                                        m.production_tonnes, m.engine_hours,
                                        date.today(), reference,
                                        f"Réparation — {notes or ''}",
                                        mechanic_name or "Système")
                                except Exception:
                                    pass
                return True
        return False

    def _save_maintenance_to_db(self, machine_id, maintenance_type, date_maintenance, mechanic_name, engine_hours, notes, pieces_changed):
        """Sauvegarde une maintenance dans SQLite"""
        with get_connection() as conn:
            cursor = conn.cursor()
            pieces_json = json.dumps(pieces_changed) if pieces_changed else "[]"
            cursor.execute("""
                INSERT INTO maintenance_logs 
                (machine_id, maintenance_type, date_maintenance, mechanic_name, engine_hours_at_maintenance, notes, pieces_changed)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (machine_id, maintenance_type, date_maintenance.strftime("%Y-%m-%d"), mechanic_name, engine_hours, notes, pieces_json))

    def do_maintenance_pm(self, machine_id, maintenance_type="PM 250h", mechanic_name=None, pieces_changed=None, notes=""):
        """Effectue une maintenance préventive et enregistre les pièces changées - PERSISTÉ EN SQLITE"""
        for m in self.machines:
            if m.id == machine_id:
                m.last_pm_hours = m.engine_hours
                m.status = "Active"
                m.save_to_db()
                
                # Enregistrer la maintenance avec les pièces changées
                if mechanic_name:
                    record = self.maintenance_manager.add_maintenance_record(
                        machine_id, maintenance_type, date.today(), mechanic_name, pieces_changed
                    )
                    record.engine_hours_at_maintenance = m.engine_hours
                    record.notes = notes
                    
                    # Persister la maintenance dans SQLite
                    self._save_maintenance_to_db(machine_id, maintenance_type, date.today(), mechanic_name, m.engine_hours, notes, pieces_changed)
                    
                    # Déduire automatiquement le stock + enregistrer pose durée de vie
                    if pieces_changed:
                        for piece in pieces_changed:
                            part_name = piece.get("nom")
                            quantity = piece.get("quantite", 1)
                            reference = f"PM-{machine_id}-{maintenance_type}"
                            stock_info = self.maintenance_manager.stock_manager.get_stock_level(part_name)
                            if stock_info["quantite"] >= quantity:
                                self.maintenance_manager.stock_manager.remove_stock_entry(
                                    part_name, quantity, date.today(), reference,
                                    f"Maintenance {maintenance_type} sur {machine_id}", mechanic_name
                                )
                            # Snapshot de production au moment de la pose
                            if part_name:
                                try:
                                    record_part_pose(machine_id, part_name,
                                        m.production_tonnes, m.engine_hours,
                                        date.today(), reference,
                                        f"{maintenance_type} — {notes or ''}",
                                        mechanic_name or "Système")
                                except Exception:
                                    pass
                return True
        return False


    def get_summary_dataframe(self):
        data = []
        today = date.today()
        fuel_price_avg = 1.5 

        for m in self.machines:
            alert_msg = "OK"
            if m.next_maintenance:
                delta = (m.next_maintenance - today).days
                if delta < 0: alert_msg = "⚠️ RETARD"
                elif delta <= 7: alert_msg = f"⚠️ J-{delta}"
                else: alert_msg = f"Prévu: {m.next_maintenance}"
            
            h_restantes = m.get_maintenance_status()
            pm_status = f"OK ({int(h_restantes)}h)"
            if h_restantes <= 0: pm_status = "⚠️ DUE"

            # ANALYTICS
            cons_par_cycle = m.cons_jour / m.cycle if m.cycle > 0 else 0
            cons_par_shift = m.cons_jour / 3
            revenu_total = m.h_jour * m.hourly_rate 
            cout_total = m.cons_jour * fuel_price_avg
            rentabilite = revenu_total - cout_total
            
            revenu_hebdo = m.h_semaine * m.hourly_rate
            revenu_mensuel = m.h_mois * m.hourly_rate

            avg_cycle = 0
            if m.cycle > 0: avg_cycle = round((m.h_jour * 60) / m.cycle, 1)

            data.append({
                "ID": m.id, "Type": m.type, "Modèle": m.model, "Statut": m.status,
                "Opérateur": m.operator, "Production (T)": int(m.production_tonnes), 
                "Cycles": m.cycle, 
                "Tps Cycle Moy (min)": avg_cycle,
                "Prochaine PM": pm_status, "Maint. Date": alert_msg, "Carburant (%)": int(m.fuel_tank),
                # DONNÉES CLÉS
                "H. Total": int(m.engine_hours),
                "H. Run Jour": m.h_jour, 
                "H. Run Hebdo": m.h_semaine, 
                "H. Run Mois": m.h_mois,
                "Conso. Jour (L)": int(m.cons_jour),
                "Conso. Shift (L)": int(cons_par_shift),
                "Conso. Voyage (L)": round(cons_par_cycle, 1),
                "Conso. Mois (L)": int(m.cons_mois),
                "Conso. An (L)": int(m.cons_annee),
                "Rev. Jour ($)": int(revenu_total),
                "Rev. Hebdo ($)": int(revenu_hebdo),
                "Rev. Mensuel ($)": int(revenu_mensuel),
                "Coût Fuel ($)": int(cout_total),
                "Rentabilité ($)": int(rentabilite),
                "lat": m.lat, "lon": m.lon
            })
        if not data:
            return _ensure_fleet_summary_df(pd.DataFrame())
        return _ensure_fleet_summary_df(pd.DataFrame(data))

# ==============================================================================
# 3. INTERFACE (AVEC CARBURANT MULTI-DEVISES)
# ==============================================================================
@st.cache_resource
def get_shared_manager_v16(tenant_id: str):
    return FleetManager()


@st.cache_resource
def get_shared_staff_v17(tenant_id: str):
    return StaffManager()


@st.cache_resource
def get_shared_users_v15():
    return UserManager()


@st.cache_resource
def get_shared_contracts_v2(tenant_id: str):
    return ContractManager(_safe_tenant_id(tenant_id))


@st.cache_resource
def get_shared_audit_v1(tenant_id: str):
    return AuditManager()


user_mgr = get_shared_users_v15()

manager = None
staff_mgr = None
contract_mgr = None
audit_mgr = None

# Récupération des taux au chargement
rates = get_exchange_rates()

def play_notification_sound():
    st.markdown("""<audio autoplay><source src="https://actions.google.com/sounds/v1/alarms/beep_short.ogg" type="audio/ogg"></audio>""", unsafe_allow_html=True)

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# Session déjà authentifiée : recharger les comptes depuis le JSON et réaligner rôle / tenant / login
# (évite après F5 ou reconnexion une session Streamlit incohérente où l'identification « ne marche plus »).
if st.session_state.authenticated:
    try:
        user_mgr.reload_users_from_disk()
    except Exception:
        try:
            get_shared_users_v15.clear()
        except Exception:
            pass
        globals()["user_mgr"] = get_shared_users_v15()
        try:
            user_mgr.reload_users_from_disk()
        except Exception:
            pass
    _session_un = st.session_state.get("username")
    if _session_un is not None and not isinstance(_session_un, str):
        _session_un = str(_session_un).strip() or None
    elif isinstance(_session_un, str):
        _session_un = _session_un.strip() or None
    _sync_user = user_mgr.get_user(_session_un) if _session_un else None
    if not _sync_user and _session_un:
        try:
            get_shared_users_v15.clear()
            globals()["user_mgr"] = get_shared_users_v15()
            user_mgr.reload_users_from_disk()
            _sync_user = user_mgr.get_user(_session_un)
        except Exception:
            _sync_user = None
    if not _sync_user:
        st.session_state.authenticated = False
        for _pop_k in ("username", "role", "tenant_id"):
            st.session_state.pop(_pop_k, None)
        st.rerun()
    st.session_state.username = _sync_user.get("user") or _session_un
    st.session_state.role = _sync_user.get("role") or "Invite"
    _tid_sync = _sync_user.get("tenant_id")
    if _tid_sync is not None and str(_tid_sync).strip() != "":
        st.session_state.tenant_id = _safe_tenant_id(str(_tid_sync))

# LOGIN
if not st.session_state.authenticated:
    # Styles améliorés pour une meilleure lisibilité
    st.markdown("""
    <style>
        /* Connexion : remonter le contenu et élargir la zone utile (styles non présents après auth) */
        section[data-testid="stMain"] .main .block-container {
            padding-top: 0.1rem !important;
            padding-left: clamp(0.35rem, 1.8vw, 1rem) !important;
            padding-right: clamp(0.35rem, 1.8vw, 1rem) !important;
            max-width: min(1320px, 100%) !important;
            margin-left: auto !important;
            margin-right: auto !important;
        }
        section[data-testid="stMain"] div[data-testid="stVerticalBlockBorderWrapper"] {
            gap: 0.35rem !important;
        }
        .login-card {
            background: #1e1e2e !important;
            padding: 20px !important;
            border-radius: 15px;
            border: 2px solid #333344;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.5);
            margin-bottom: 18px;
        }
        .login-card--connexion {
            margin-top: -0.35rem !important;
            margin-bottom: 16px !important;
            max-width: min(960px, 100%) !important;
            width: 100% !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding: 18px 22px !important;
        }
        .login-title {
            color: #F5B800 !important;
            font-size: 64px !important;
            font-weight: 900 !important;
            text-align: center;
            margin-bottom: 15px !important;
            text-shadow: 0 0 20px rgba(245, 184, 0, 0.6);
            letter-spacing: 2px;
        }
        .login-subtitle {
            color: #e0e0e0 !important;
            font-size: 28px !important;
            font-weight: 600 !important;
            text-align: center;
            margin-bottom: 30px !important;
        }
        .section-title {
            color: #F5B800 !important;
            font-size: 32px !important;
            font-weight: 900 !important;
            margin-bottom: 20px !important;
            padding-bottom: 12px !important;
            border-bottom: 3px solid #F5B800 !important;
            text-align: center;
        }
        .equipment-label {
            color: #e0e0e0 !important;
            font-size: clamp(14px, 2vw, 18px) !important;
            font-weight: 700 !important;
            margin-top: 10px;
            word-wrap: break-word;
            overflow-wrap: break-word;
        }
        @media (max-width: 768px) {
            .equipment-label {
                font-size: 14px !important;
            }
        }
        .rule-text, .mission-text {
            color: #e0e0e0 !important;
            font-size: 17px !important;
            line-height: 1.8 !important;
            font-weight: 400;
        }
        .rule-title, .mission-title {
            color: #F5B800 !important;
            font-size: 22px !important;
            font-weight: 900 !important;
            margin-bottom: 8px;
        }
        .login-form-title {
            color: #F5B800 !important;
            font-size: 32px !important;
            font-weight: 900 !important;
            text-align: center;
            margin-bottom: 18px !important;
            margin-top: 0 !important;
            padding-bottom: 12px !important;
            border-bottom: 3px solid #F5B800 !important;
        }
    </style>
    """, unsafe_allow_html=True)
    
    # ── SPLIT-SCREEN LOGIN ────────────────────────────────────────────────────
    st.markdown("""
    <style>
    /* Split-screen : hauteur page complète, sidebar masquée */
    section[data-testid="stSidebar"] { display: none !important; }
    section[data-testid="stMain"] .block-container {
        padding-top: 0 !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        max-width: 100% !important;
    }
    /* Panel gauche — marque + formulaire */
    .login-left-panel {
        background: linear-gradient(175deg, #0a1827 0%, #0F2A44 50%, #081420 100%);
        border-radius: 20px;
        padding: clamp(28px, 5vw, 52px) clamp(20px, 4vw, 44px);
        min-height: 88vh;
        display: flex;
        flex-direction: column;
        justify-content: center;
        border-right: 1px solid rgba(245, 184, 0, 0.15);
        position: relative;
        overflow: hidden;
    }
    .login-left-panel::before {
        content: '';
        position: absolute;
        top: -60px; right: -60px;
        width: 260px; height: 260px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(245,184,0,0.08) 0%, transparent 70%);
        pointer-events: none;
    }
    .login-left-panel::after {
        content: '';
        position: absolute;
        bottom: -40px; left: -40px;
        width: 200px; height: 200px;
        border-radius: 50%;
        background: radial-gradient(circle, rgba(245,184,0,0.05) 0%, transparent 70%);
        pointer-events: none;
    }
    .login-brand-title {
        font-family: 'Montserrat', sans-serif;
        font-size: clamp(28px, 3.5vw, 42px) !important;
        font-weight: 900 !important;
        color: #F5B800 !important;
        letter-spacing: 0.06em;
        text-shadow: 0 0 30px rgba(245,184,0,0.35);
        margin-bottom: 4px !important;
        line-height: 1.1;
    }
    .login-brand-sub {
        font-size: clamp(11px, 1.2vw, 14px) !important;
        color: rgba(245,184,0,0.7) !important;
        letter-spacing: 0.20em;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 20px !important;
    }
    .login-brand-desc {
        font-size: clamp(13px, 1.4vw, 16px) !important;
        color: #8A9BB0 !important;
        font-weight: 500;
        line-height: 1.6;
        margin-bottom: 32px !important;
    }
    .login-divider {
        height: 1px;
        background: linear-gradient(90deg, rgba(245,184,0,0.5) 0%, rgba(245,184,0,0.05) 100%);
        margin: 20px 0 28px 0;
        border: none;
    }
    .login-field-label {
        font-size: 13px !important;
        font-weight: 700 !important;
        color: #F5B800 !important;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        margin-bottom: 6px !important;
        display: block;
    }
    /* Panel droit — vitrines fonctions + engins */
    .login-right-panel {
        background: #0d1520;
        border-radius: 20px;
        padding: clamp(24px, 4vw, 44px) clamp(18px, 3vw, 36px);
        min-height: 88vh;
    }
    .login-feature-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 12px;
        margin-bottom: 24px;
    }
    .login-feature-card {
        background: rgba(15, 42, 68, 0.75);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(245,184,0,0.14);
        border-radius: 14px;
        padding: 18px 16px;
        text-align: center;
        transition: border-color 180ms ease, transform 180ms ease;
    }
    .login-feature-card:hover {
        border-color: rgba(245,184,0,0.35);
        transform: translateY(-2px);
    }
    .login-feature-icon { font-size: 28px; margin-bottom: 8px; }
    .login-feature-label {
        font-size: 12px;
        font-weight: 800;
        color: #EAEAEA;
        text-transform: uppercase;
        letter-spacing: 0.08em;
    }
    .login-feature-desc { font-size: 11px; color: #7A8A9A; margin-top: 4px; font-weight: 500; }
    .login-equip-grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 10px;
        margin-bottom: 20px;
    }
    .login-equip-item {
        border-radius: 10px;
        overflow: hidden;
        border: 1px solid rgba(245,184,0,0.18);
        text-align: center;
        background: rgba(20,30,45,0.8);
    }
    .login-equip-item img { width: 100%; height: 80px; object-fit: cover; display: block; }
    .login-equip-item span {
        display: block;
        font-size: 10px;
        font-weight: 800;
        color: #F5B800;
        padding: 5px 4px;
        letter-spacing: 0.06em;
        text-transform: uppercase;
    }
    .login-values-row { display: flex; gap: 10px; flex-wrap: wrap; }
    .login-value-chip {
        background: rgba(245,184,0,0.1);
        border: 1px solid rgba(245,184,0,0.25);
        border-radius: 20px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 700;
        color: #F5B800;
        letter-spacing: 0.06em;
    }
    </style>
    """, unsafe_allow_html=True)

    _col_form, _col_vis = st.columns([1, 1.55], gap="small")

    # ── PANNEAU GAUCHE : marque + formulaire ──────────────────────────────────
    with _col_form:
        st.markdown('<div class="login-left-panel">', unsafe_allow_html=True)

        # Logo / marque
        _lp_b64 = _hero_masthead_b64_for_banner()
        if _lp_b64:
            st.markdown(f"""
            <div style="text-align:center; margin-bottom: 24px;">
              <img src="data:image/png;base64,{_lp_b64}"
                   style="max-width:100%; max-height:120px; object-fit:contain;"
                   alt="GOOD ENGINEERS" />
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="text-align:center; margin-bottom:8px;">
              <div style="display:inline-block; width:70px; height:70px; margin-bottom:12px;">
                {GOOD_ENGINEERS_BANNER_MARK_SVG}
              </div>
            </div>
            <p class="login-brand-title" style="text-align:center;">GOOD ENGINEERS</p>
            <p class="login-brand-sub" style="text-align:center;">DISCIPLINE &bull; RIGUEUR &bull; PERFORMANCE</p>
            """, unsafe_allow_html=True)

        st.markdown("""
        <p class="login-brand-desc" style="text-align:center;">
          Système d'exploitation minière &amp; gestion de flotte.<br>
          Plateforme SaaS multi-entreprise.
        </p>
        <hr class="login-divider"/>
        <p style="font-size:18px; font-weight:800; color:#EAEAEA; margin-bottom:20px; text-align:center; letter-spacing:0.06em; text-transform:uppercase;">
          🔐 Connexion
        </p>
        """, unsafe_allow_html=True)

        st.markdown('<span class="login-field-label">Identifiant</span>', unsafe_allow_html=True)
        u = st.text_input("Identifiant", key="login_username",
                          placeholder="Entrez votre identifiant",
                          label_visibility="collapsed")
        st.markdown('<span class="login-field-label" style="margin-top:12px; display:block;">Mot de passe</span>', unsafe_allow_html=True)
        p = st.text_input("Mot de passe", type="password", key="login_password",
                          placeholder="••••••••••••",
                          label_visibility="collapsed")

        st.markdown('<div style="margin-top: 18px;"></div>', unsafe_allow_html=True)
        if st.button("🔓 SE CONNECTER", use_container_width=True, type="primary"):
            try:
                user_mgr.reload_users_from_disk()
            except Exception:
                try:
                    get_shared_users_v15.clear()
                except Exception:
                    pass
                globals()["user_mgr"] = get_shared_users_v15()
            user_info = user_mgr.verify_login(u, p)
            if not user_info:
                try:
                    get_shared_users_v15.clear()
                    globals()["user_mgr"] = get_shared_users_v15()
                    user_mgr.reload_users_from_disk()
                    user_info = user_mgr.verify_login(u, p)
                except Exception:
                    user_info = None
            if user_info:
                st.session_state.authenticated = True
                st.session_state.username = user_info['user']
                st.session_state.role = user_info['role']
                st.session_state.tenant_id = user_info.get("tenant_id", "default")
                st.rerun()
            else:
                st.error("❌ Identifiant ou mot de passe incorrect")

        st.markdown('<hr class="login-divider"/>', unsafe_allow_html=True)
        st.caption(
            "Rôle **Gestionnaire** : créer des comptes entreprises et administrateurs "
            "(accès fourni par l'hébergeur)."
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── PANNEAU DROIT : fonctions + engins + valeurs ───────────────────────────
    with _col_vis:
        st.markdown('<div class="login-right-panel">', unsafe_allow_html=True)
        st.markdown("""
        <p style="font-size:clamp(16px,2vw,22px); font-weight:900; color:#F5B800;
                  text-transform:uppercase; letter-spacing:0.10em; margin-bottom:6px;">
          ⛏ Centre de contrôle opérationnel
        </p>
        <p style="font-size:13px; color:#7A8A9A; font-weight:500; margin-bottom:20px; line-height:1.5;">
          Pilotez votre flotte minière en temps réel — production, maintenance,
          carburant, RH, finance et sécurité dans un seul OS.
        </p>
        """, unsafe_allow_html=True)

        # Grille fonctions clés
        _features = [
            ("📊", "DASHBOARD", "KPI temps réel"),
            ("🔄", "CYCLES", "Suivi chargements"),
            ("⛽", "CARBURANT", "Consommations"),
            ("🔧", "MAINTENANCE", "PM & réparations"),
            ("📦", "STOCK", "Pièces & matériaux"),
            ("💰", "FINANCE", "Coûts & revenus"),
            ("👥", "RH", "Équipes & présences"),
            ("🦺", "SST", "Sécurité & incidents"),
        ]
        st.markdown('<div class="login-feature-grid">', unsafe_allow_html=True)
        for _icon, _lbl, _desc in _features:
            st.markdown(f"""
            <div class="login-feature-card">
              <div class="login-feature-icon">{_icon}</div>
              <div class="login-feature-label">{_lbl}</div>
              <div class="login-feature-desc">{_desc}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Galerie engins
        st.markdown('<p style="font-size:13px; font-weight:800; color:#F5B800; text-transform:uppercase; letter-spacing:0.10em; margin:18px 0 12px;">🚛 Flotte d\'engins prise en charge</p>', unsafe_allow_html=True)
        _equip_default = [
            ("https://images.unsplash.com/photo-1581091226825-a6a2a5aee158?w=300&h=200&fit=crop", "Camions"),
            ("https://images.unsplash.com/photo-1581094794329-c8112a89af12?w=300&h=200&fit=crop", "Excavatrices"),
            ("https://images.unsplash.com/photo-1621905251918-48416bd8575a?w=300&h=200&fit=crop", "Bulldozers"),
            ("https://images.unsplash.com/photo-1586528116311-ad8dd3c8310d?w=300&h=200&fit=crop", "Chargeurs"),
            ("https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=300&h=200&fit=crop", "Foreuses"),
            ("https://images.unsplash.com/photo-1611522135884-5b90cc5c2fb4?w=300&h=200&fit=crop", "Dumpers"),
        ]
        st.markdown('<div class="login-equip-grid">', unsafe_allow_html=True)
        for _eurl, _elbl in _equip_default:
            _eimg = get_equipment_image_url(_elbl, _eurl)
            st.markdown(f"""
            <div class="login-equip-item">
              <img src="{_eimg}" alt="{_elbl}" loading="lazy"/>
              <span>{_elbl}</span>
            </div>""", unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # Valeurs
        st.markdown("""
        <div class="login-values-row" style="margin-top:16px;">
          <span class="login-value-chip">🏆 Excellence</span>
          <span class="login-value-chip">🔒 Sécurité</span>
          <span class="login-value-chip">⚙️ Efficacité</span>
          <span class="login-value-chip">📊 Innovation</span>
          <span class="login-value-chip">🌍 Durabilité</span>
        </div>
        """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    st.stop()

# ── Traitement envoi chat flottant (query param bridge) ──────────────────────
try:
    _ge_qp = dict(st.query_params)
    _ge_fc_raw = _ge_qp.get("ge_fc", "")
    if isinstance(_ge_fc_raw, list):
        _ge_fc_raw = _ge_fc_raw[0] if _ge_fc_raw else ""
except Exception:
    _ge_fc_raw = ""

if _ge_fc_raw and str(_ge_fc_raw).strip():
    _ge_fc_body = str(_ge_fc_raw).strip()[:2000]
    _ge_fc_from = st.session_state.get("username", "Anonyme")
    _ge_fc_data = _load_collab_messages()
    _ge_fc_data.setdefault("messages", []).append({
        "id": uuid.uuid4().hex,
        "ts": datetime.now().isoformat(),
        "from": _ge_fc_from,
        "to": "__team__",
        "kind": "message",
        "body": _ge_fc_body,
        "attachments": [],
    })
    _save_collab_messages(_ge_fc_data)
    try:
        st.query_params.clear()
    except Exception:
        pass
    st.rerun()

# INTERFACE PRINCIPALE
user_role = st.session_state.role

# Obtenir les informations de l'utilisateur avec gestion d'erreur
user_info = None
try:
    if hasattr(user_mgr, 'get_user'):
        user_info = user_mgr.get_user(st.session_state.username)
except AttributeError:
    # Si la méthode n'existe pas encore, utiliser la méthode verify_login
    for u in user_mgr.users_db:
        if u['user'] == st.session_state.username:
            user_info = u
            break

# --- Multi-entreprise : isolation SQLite par tenant + managers ---
if user_role == "Gestionnaire":
    st.session_state.tenant_id = "__platform__"
    render_gestionnaire_console(user_mgr)
    if st.button("🚪 Déconnexion", key="gest_logout_main"):
        st.session_state.authenticated = False
        st.rerun()
    st.stop()

# Tenant réel du compte (évite de retomber sur default si user_info était incomplet après création SaaS)
_tid_login = None
if user_info:
    _tid_login = user_info.get("tenant_id")
if _tid_login is None or str(_tid_login).strip() == "":
    _tid_login = st.session_state.get("tenant_id") or "default"
_tid_login = str(_tid_login).strip()
if _tid_login == "__platform__" and user_role != "Gestionnaire":
    _tid_login = "default"
st.session_state.tenant_id = _safe_tenant_id(_tid_login)

if not is_tenant_billing_ok(st.session_state.tenant_id):
    st.error(
        "Compte entreprise inactif ou abonnement expiré. "
        "Contactez le gestionnaire de la plateforme GOOD ENGINEERS."
    )
    st.stop()

_tenant_key = st.session_state.tenant_id
manager = get_shared_manager_v16(_tenant_key)
staff_mgr = get_shared_staff_v17(_tenant_key)
contract_mgr = get_shared_contracts_v2(_tenant_key)
audit_mgr = get_shared_audit_v1(_tenant_key)
contract_mgr.update_contract_from_machines(manager)

# PAGE D'ACCUEIL — bandeau marque (même visuel que la page de connexion)
if user_role != "Operateur":
    render_good_engineers_banner()

# Déterminer les onglets autorisés basés sur les permissions
authorized_tabs = []

# PRIORITÉ ABSOLUE : Les opérateurs n'ont accès QU'À l'onglet VALIDATION OPÉRATEUR
if user_role == "Operateur":
    authorized_tabs = ["VALIDATION OPÉRATEUR"]  # SEULEMENT validation pour opérateurs
elif user_info and 'permissions' in user_info:
    perms = user_info['permissions']
    if perms.get('dashboard', False): authorized_tabs.append("DASHBOARD")
    if perms.get('cycles', False): authorized_tabs.append("CYCLES")
    if perms.get('carburant', False): authorized_tabs.append("CARBURANT")
    if perms.get('maintenance', False): authorized_tabs.append("MAINT.")
    if perms.get('stock', False): authorized_tabs.append("GESTION STOCK")
    if perms.get('carte', False): authorized_tabs.append("CARTE")
    if perms.get('finance', False): authorized_tabs.append("FINANCE")
    if perms.get('rh', False): authorized_tabs.append("RH")
    if perms.get('admin', False): authorized_tabs.append("ADMIN")
    if perms.get('donnees_ingenierie', False): authorized_tabs.append("DONNÉES INGÉNIERIE")
    if perms.get('messagerie', False): authorized_tabs.append("MESSAGERIE")
    if perms.get('sst', False): authorized_tabs.append("SST")
    # Onglet marché de l'or accessible à tous les utilisateurs avec dashboard
    if perms.get('dashboard', False): authorized_tabs.append("MARCHÉ OR")
    # Onglet validation opérateur accessible aux superviseurs
    if perms.get('validation_operateur', False) or perms.get('cycles', False) or user_role == "Superviseur Production": 
        authorized_tabs.append("VALIDATION OPÉRATEUR")
    
    # Si aucun onglet n'a été ajouté, ajouter au moins DASHBOARD et MARCHÉ OR
    if not authorized_tabs:
        authorized_tabs = ["DASHBOARD", "MARCHÉ OR"]
else:
    # Fallback pour les anciens utilisateurs sans permissions
    if user_role == "Administrateur": 
        authorized_tabs = ["DASHBOARD", "CYCLES", "CARBURANT", "MAINT.", "GESTION STOCK", "CARTE", "FINANCE", "RH", "ADMIN", "DONNÉES INGÉNIERIE", "MESSAGERIE", "SST", "MARCHÉ OR", "VALIDATION OPÉRATEUR"]
    elif user_role == "Visiteur": 
        authorized_tabs = ["DASHBOARD", "CYCLES", "CARTE", "MESSAGERIE", "SST", "MARCHÉ OR"] 
    elif user_role == "Ingenieur":
        authorized_tabs = ["DASHBOARD", "CYCLES", "MAINT.", "GESTION STOCK", "CARTE", "DONNÉES INGÉNIERIE", "MESSAGERIE", "SST", "MARCHÉ OR"]
    elif user_role == "Superviseur Production":
        authorized_tabs = ["DASHBOARD", "CYCLES", "CARBURANT", "MAINT.", "GESTION STOCK", "CARTE", "FINANCE", "DONNÉES INGÉNIERIE", "MESSAGERIE", "SST", "MARCHÉ OR", "VALIDATION OPÉRATEUR"]
    elif user_role == "Superviseur Mecanicien":
        authorized_tabs = ["DASHBOARD", "CYCLES", "CARBURANT", "MAINT.", "GESTION STOCK", "CARTE", "DONNÉES INGÉNIERIE", "MESSAGERIE", "SST", "MARCHÉ OR"]
    elif user_role == "RH":
        authorized_tabs = ["DASHBOARD", "GESTION STOCK", "RH", "MESSAGERIE", "SST", "MARCHÉ OR"]
    else: 
        # Fallback par défaut pour tous les autres rôles
        authorized_tabs = ["DASHBOARD", "MESSAGERIE", "SST", "MARCHÉ OR"]

# S'assurer qu'il y a au moins un onglet (fallback si aucune permission)
if not authorized_tabs:
    authorized_tabs = ["DASHBOARD", "MARCHÉ OR"]  # Onglets minimums pour tous

# Masquer la sidebar pour les opérateurs
if user_role != "Operateur":
    with st.sidebar:
        # Afficher le logo si disponible, sinon le texte
        _logo_alt = "GOOD ENGINEERS"
        try:
            _r_sb = get_tenant_record(_safe_tenant_id(st.session_state.get("tenant_id", "default")))
            if _r_sb and _r_sb.get("name"):
                _logo_alt = html.escape(str(_r_sb.get("name")).strip() or _logo_alt)
        except Exception:
            pass
        logo_url = get_logo_url()
        if logo_url:
            st.markdown(f"""
            <div class="sidebar-logo-container">
                <img src="{logo_url}" alt="{_logo_alt}">
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown("""<div class="sidebar-logo-container"><div class="sidebar-logo-text">GOOD<br>ENGINEERS</div></div>""", unsafe_allow_html=True)
        
        if not st.session_state.get("ge_sidebar_collapsed"):
            _sb_ar_l, _sb_ar_r = st.columns([5, 1])
            with _sb_ar_r:
                if st.button(
                    "\u25C0",
                    key="ge_sidebar_collapse_btn",
                    use_container_width=True,
                    help="Replier le panneau latéral — plus d'espace pour le centre de contrôle. "
                    "Flèche droite en haut de la page pour rouvrir.",
                ):
                    st.session_state.ge_sidebar_collapsed = True
                    st.rerun()
        
        # Toggle Mode Jour/Nuit
        st.markdown("---")
        col_mode1, col_mode2 = st.columns([1, 1])
        with col_mode1:
            if st.button("🌙" if st.session_state.theme_mode == 'dark' else "☀️", use_container_width=True):
                st.session_state.theme_mode = 'light' if st.session_state.theme_mode == 'dark' else 'dark'
                st.rerun()
        with col_mode2:
            mode_text = "Mode Nuit" if st.session_state.theme_mode == 'dark' else "Mode Jour"
            st.markdown(f"<p style='text-align: center; color: #F5B800; font-size: 16px; font-weight: 700; margin-top: 8px;'>{mode_text}</p>", unsafe_allow_html=True)
        
        # AFFICHAGE DES TAUX EN SIDEBAR
        st.markdown("---")
        st.markdown("**💱 TAUX DU JOUR (LIVE)**")
        rates = get_exchange_rates()
        st.markdown(f"1 USD = **{rates['CFA']:.0f} CFA**")
        st.markdown(f"1 USD = **{rates['EUR']:.2f} EUR**")
        
        st.markdown("---")
        st.markdown("**🥇 PRIX DE L'OR (LIVE)**")
        gold_price = get_gold_price()
        price_usd = gold_price['price_per_ounce_usd']
        price_cfa = price_usd * rates['CFA']
        price_per_gram_usd = price_usd / 31.1035
        price_per_gram_cfa = price_per_gram_usd * rates['CFA']
        st.markdown(f"**{price_usd:,.2f} $/once**")
        st.markdown(f"**{price_cfa:,.0f} F/once**")
        st.caption(f"1 once = 31.1035 g")
        st.caption(f"1 g = ${price_per_gram_usd:,.2f} ({price_per_gram_cfa:,.0f} F)")
        
        st.markdown("---")
        with st.expander("Mon mot de passe", expanded=False):
            render_change_own_password_form(user_mgr, key_prefix="sidebar_pwd")
        st.markdown("---")
        shifts = ["Matin", "Soir", "Nuit"]
        sel_shift = st.selectbox("Shift", shifts)
        st.markdown("---")
        if st.button("DÉCONNEXION", use_container_width=True):
            st.session_state.authenticated = False
            st.rerun()
else:
    # Masquer la sidebar pour les opérateurs
    st.markdown("""
    <style>
    section[data-testid="stSidebar"] {
        display: none !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Panneau réduit : flèche pour rouvrir (stHeader masqué = pas de toggle natif Streamlit)
if user_role != "Operateur" and st.session_state.get("ge_sidebar_collapsed"):
    _ex_l, _ex_r = st.columns([1, 24])
    with _ex_l:
        if st.button(
            "\u25B6",
            key="ge_sidebar_expand_main",
            use_container_width=True,
            help="Rouvrir le menu latéral (logo, taux, or, mode jour/nuit, déconnexion).",
        ):
            st.session_state.ge_sidebar_collapsed = False
            st.rerun()

# IMPORTANT: Appliquer les styles pour les opérateurs AVANT l'affichage du contenu
# Les opérateurs n'utilisent pas les onglets, donc on applique le CSS ici
if user_role == "Operateur":
    # Script JavaScript pour détecter la connexion et synchroniser les données hors ligne
    st.markdown("""
    <script>
    // Système de synchronisation hors ligne
    let isOnline = navigator.onLine;
    let offlineData = JSON.parse(localStorage.getItem('offline_validations') || '[]');
    let offlineNotifications = JSON.parse(localStorage.getItem('offline_notifications') || '[]');
    
    // Détecter les changements de connexion
    window.addEventListener('online', function() {
        console.log('Connexion rétablie - Synchronisation en cours...');
        isOnline = true;
        syncOfflineData();
    });
    
    window.addEventListener('offline', function() {
        console.log('Hors ligne - Mode hors ligne activé');
        isOnline = false;
    });
    
    // Fonction de synchronisation
    function syncOfflineData() {
        if (!isOnline) return;
        
        // Synchroniser les validations hors ligne
        if (offlineData.length > 0) {
            console.log('Synchronisation de ' + offlineData.length + ' validation(s)...');
            // Les données seront synchronisées lors du prochain rechargement de page
        }
        
        // Synchroniser les notifications hors ligne
        if (offlineNotifications.length > 0) {
            console.log('Synchronisation de ' + offlineNotifications.length + ' notification(s)...');
        }
        
        // Vider le localStorage après synchronisation
        localStorage.removeItem('offline_validations');
        localStorage.removeItem('offline_notifications');
        offlineData = [];
        offlineNotifications = [];
    }
    
    // Vérifier la connexion au chargement de la page
    if (isOnline) {
        syncOfflineData();
    }
    
    // Fonction pour stocker les données hors ligne
    function storeOfflineValidation(validation) {
        offlineData.push(validation);
        localStorage.setItem('offline_validations', JSON.stringify(offlineData));
        console.log('Validation stockée hors ligne:', validation);
    }
    
    function storeOfflineNotification(notification) {
        offlineNotifications.push(notification);
        localStorage.setItem('offline_notifications', JSON.stringify(offlineNotifications));
        console.log('Notification stockée hors ligne:', notification);
    }
    
    // Exposer les fonctions globalement
    window.storeOfflineValidation = storeOfflineValidation;
    window.storeOfflineNotification = storeOfflineNotification;
    window.isOnline = function() { return navigator.onLine; };
    window.syncOfflineData = syncOfflineData;
    
    // Vérifier périodiquement la connexion
    setInterval(function() {
        if (navigator.onLine && !isOnline) {
            isOnline = true;
            syncOfflineData();
            // Recharger la page pour synchroniser avec le serveur
            if (offlineData.length > 0 || offlineNotifications.length > 0) {
                window.location.reload();
            }
        }
        isOnline = navigator.onLine;
    }, 5000); // Vérifier toutes les 5 secondes
    </script>
    """, unsafe_allow_html=True)
    
    st.markdown("""
    <style>
    /* Masquer UNIQUEMENT la sidebar et le header - PAS le contenu */
    section[data-testid="stSidebar"] { display: none !important; }
    div[data-testid="stHeader"] { display: none !important; }
    #MainMenu { display: none !important; }
    footer { display: none !important; }
    
    /* Poste opérateur — fond sombre haute lisibilité (soleil / poussière) */
    .stApp {
        background: #121212 !important;
        background-image: linear-gradient(180deg, #0F2A44 0%, #121212 50%) !important;
    }
    
    .main .block-container {
        background: #1E1E1E !important;
        border-radius: 8px !important;
        padding: 1.5rem !important;
        box-shadow: 0 8px 28px rgba(0, 0, 0, 0.4) !important;
        margin: 0.75rem !important;
        border: 1px solid #404040 !important;
    }
    
    /* Forcer le plein écran */
    .main .block-container {
        padding-top: 2rem !important;
        padding-bottom: 2rem !important;
        max-width: 100% !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    
    /* Boutons tactiles — action primaire jaune sécurité */
    button[kind="primary"] {
        height: 170px !important;
        min-height: 170px !important;
        font-size: 80px !important;
        font-weight: 800 !important;
        color: #0F2A44 !important;
        padding: 32px 22px !important;
        border-radius: 8px !important;
        border: 2px solid #F5B800 !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: linear-gradient(180deg, #F5B800 0%, #D9A000 100%) !important;
        box-shadow: 0 6px 24px rgba(0, 0, 0, 0.35) !important;
        transition: transform 150ms ease, filter 150ms ease !important;
    }
    button[kind="primary"]:hover {
        transform: scale(1.02) !important;
        filter: brightness(1.06) !important;
    }
    button[kind="primary"] span {
        color: #0F2A44 !important;
        font-weight: 800 !important;
        font-size: 80px !important;
        width: 100% !important;
        text-align: center !important;
        display: block !important;
    }
    button:not([kind="primary"]) {
        height: 150px !important;
        min-height: 150px !important;
        font-size: 70px !important;
        font-weight: 700 !important;
        color: #EAEAEA !important;
        padding: 28px 22px !important;
        border-radius: 8px !important;
        width: 100% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: #2F2F2F !important;
        border: 2px solid #505050 !important;
        box-shadow: 0 4px 18px rgba(0, 0, 0, 0.3) !important;
        transition: transform 150ms ease, border-color 150ms ease !important;
    }
    button:not([kind="primary"]):hover {
        transform: scale(1.02) !important;
        border-color: #F5B800 !important;
    }
    button:not([kind="primary"]) span {
        color: #EAEAEA !important;
        font-weight: 700 !important;
        font-size: 70px !important;
        width: 100% !important;
        text-align: center !important;
        display: block !important;
    }
    button[kind="primary"], button[kind="primary"] * {
        color: #0F2A44 !important;
    }
    button:not([kind="primary"]) {
        color: #EAEAEA !important;
    }
    button:not([kind="primary"]) * {
        color: #EAEAEA !important;
    }
    /* S'assurer que le texte remplit bien les boutons */
    button p {
        margin: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        text-align: center !important;
    }
    
    p, span, div, label {
        color: #EAEAEA !important;
        font-weight: 600 !important;
        font-size: 40px !important;
    }
    h1, h2, h3, h4, h5, h6 {
        font-weight: 800 !important;
    }
    h1 {
        font-size: 80px !important;
        color: #F5B800 !important;
    }
    h2 {
        font-size: 64px !important;
        color: #EAEAEA !important;
    }
    h3 {
        font-size: 52px !important;
        color: #A0A0A0 !important;
    }
    h1[style*="color: #F5B800"], h2[style*="color: #F5B800"], h3[style*="color: #F5B800"] {
        color: #F5B800 !important;
    }
    
    .stSelectbox {
        display: block !important;
        margin: 24px 0 !important;
        padding: 16px !important;
        background: #1E1E1E !important;
        border: 1px solid #404040 !important;
        border-radius: 8px !important;
    }
    .stSelectbox label {
        font-size: 52px !important;
        font-weight: 700 !important;
        margin-bottom: 16px !important;
        color: #F5B800 !important;
    }
    .stSelectbox > div > div {
        font-size: 56px !important;
        padding: 28px !important;
        min-height: 120px !important;
        font-weight: 700 !important;
        color: #EAEAEA !important;
        background: #2F2F2F !important;
        border: 1px solid #F5B800 !important;
        border-radius: 8px !important;
    }
    section[data-testid="stSelectbox"] {
        margin: 20px 0 !important;
        padding: 16px !important;
        background: #1E1E1E !important;
        border: 1px solid #404040 !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="select"] {
        font-size:52px !important;
        min-height: 120px !important;
    }
    div[data-baseweb="select"] > div {
        font-size: 52px !important;
        padding: 28px !important;
        font-weight: 700 !important;
        color: #EAEAEA !important;
        background: #2F2F2F !important;
        border-radius: 8px !important;
    }
    div[data-baseweb="popover"] {
        font-size: 48px !important;
        background: #1E1E1E !important;
    }
    div[data-baseweb="popover"] li {
        font-size: 48px !important;
        padding: 20px !important;
        font-weight: 600 !important;
        color: #EAEAEA !important;
    }
    
    .stInfo, .stSuccess, .stError, .stWarning {
        font-size: 48px !important;
        font-weight: 700 !important;
        color: #EAEAEA !important;
        padding: 28px !important;
        min-height: 100px !important;
        border-radius: 8px !important;
        border: 1px solid #404040 !important;
        display: flex !important;
        align-items: center !important;
    }
    .stSuccess {
        background: rgba(40, 167, 69, 0.18) !important;
        border-left: 8px solid #28A745 !important;
    }
    .stInfo {
        background: rgba(245, 184, 0, 0.12) !important;
        border-left: 8px solid #F5B800 !important;
    }
    .stWarning {
        background: rgba(255, 107, 0, 0.15) !important;
        border-left: 8px solid #FF6B00 !important;
    }
    .stError {
        background: rgba(220, 53, 69, 0.15) !important;
        border-left: 8px solid #DC3545 !important;
    }
    .stInfo *, .stSuccess *, .stError *, .stWarning * {
        color: #EAEAEA !important;
        font-weight: 700 !important;
        font-size: 48px !important;
    }
    .stInfo > div, .stSuccess > div, .stError > div, .stWarning > div {
        min-height: 100px !important;
        padding: 24px !important;
    }
    </style>
    """, unsafe_allow_html=True)

# Ne pas afficher les éléments suivants pour les opérateurs - COMPLÈTEMENT SUPPRIMÉ
# Ces éléments ne doivent JAMAIS être affichés pour les opérateurs
# Ces éléments sont dans la sidebar pour les autres utilisateurs

df = _ensure_fleet_summary_df(manager.get_summary_dataframe())

# HEADER - Ne pas afficher pour les opérateurs
if user_role != "Operateur":
    prod_txt = f"{_fleet_col_sum_int(df, 'Production (T)')} T"
    active_txt = f"{_fleet_statut_count(df, 'Active')} ACTIVES"
    panne_txt = f"{_fleet_statut_count(df, 'Panne')} PANNES"
    st.markdown(f"""
    <div class="hero-banner">
        <div class="marquee-text">
            CENTRE DE CONTRÔLE <span class="gold-text">GOOD ENGINEERS</span> • 
            PRODUCTION: <span class="gold-text">{prod_txt}</span> • 
            FLOTTE: <span class="gold-text">{active_txt}</span> • 
            ATTENTION: <span class="gold-text">{panne_txt}</span> • 
            OPERATIONS LIVE • SAFETY FIRST • 
        </div>
    </div>
    """, unsafe_allow_html=True)

# IMPORTANT: Pour les opérateurs, on affiche directement le contenu SANS passer par les onglets
# On ne crée pas les onglets pour les opérateurs, on affiche directement le contenu

# Pour les opérateurs, afficher directement le contenu SANS onglets
if user_role == "Operateur":
    # Afficher directement le contenu de validation opérateur
    # Message de test pour vérifier que l'onglet s'affiche - TOUJOURS AFFICHÉ
    st.markdown("## 🔧 INTERFACE OPÉRATEUR - VALIDATION")
    st.success("✅ L'interface opérateur est chargée. Le contenu devrait apparaître ci-dessous.")
    st.write("**Rôle utilisateur:**", user_role)
    st.write("**Nom d'utilisateur:**", st.session_state.get('username', 'Non défini'))
    
    # Fonctions pour gérer les notifications de manière partagée (fichier JSON)
    NOTIFICATIONS_FILE = os.path.join(_APP_DATA_ROOT, "operator_notifications.json")
    
    def load_notifications():
        """Charge les notifications depuis le fichier JSON"""
        if os.path.exists(NOTIFICATIONS_FILE):
            try:
                with open(NOTIFICATIONS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def save_notifications(notifications):
        """Sauvegarde les notifications dans le fichier JSON"""
        try:
            with open(NOTIFICATIONS_FILE, 'w', encoding='utf-8') as f:
                json.dump(notifications, f, ensure_ascii=False, indent=2)
        except Exception as e:
            st.error(f"Erreur lors de la sauvegarde: {e}")
    
    def sync_offline_data():
        """Synchronise les données hors ligne avec le fichier partagé"""
        try:
            # Charger les données hors ligne depuis localStorage (via JavaScript)
            # Cette fonction sera appelée par JavaScript
            pass
        except:
            pass
    
    # Initialiser les systèmes de notification dans session_state
    if 'validations' not in st.session_state:
        st.session_state.validations = []
    if 'operator_notifications' not in st.session_state:
        # Charger depuis le fichier partagé
        st.session_state.operator_notifications = load_notifications()
    if 'loading_signals' not in st.session_state:
        st.session_state.loading_signals = []
    if 'breakdown_reports' not in st.session_state:
        st.session_state.breakdown_reports = []
    if 'cycle_events' not in st.session_state:
        st.session_state.cycle_events = []
    
    # Récupérer l'opérateur actuel
    current_operator = None
    # Trouver l'opérateur correspondant à l'utilisateur connecté
    for emp in staff_mgr.staff:
        if emp.role == "Operateur" and emp.name == st.session_state.username:
            current_operator = emp
            break
    
    # Récupérer les machines de l'opérateur pour déterminer le type
    df_machines = manager.get_summary_dataframe()
    operator_machines_list = []
    machine_types = []
    if current_operator:
        operator_machines_list = df_machines[df_machines['Opérateur'] == current_operator.name]['ID'].tolist()
        machine_types = df_machines[df_machines['Opérateur'] == current_operator.name]['Type'].tolist()
    
    # Déterminer le type d'opérateur depuis les données utilisateur ou les machines
    operator_type_from_user = None
    if user_info and 'operator_type' in user_info:
        operator_type_from_user = user_info['operator_type']
    
    # Si le type est défini dans les données utilisateur, l'utiliser en priorité
    if operator_type_from_user:
        is_loader = (operator_type_from_user == "loader")
        is_dumper = (operator_type_from_user == "dumper")
    else:
        # Sinon, détecter automatiquement à partir des machines assignées
        is_loader = any('CHARGE' in m.upper() or 'PELLE' in m.upper() or 'EXCAVATRICE' in m.upper() 
                      for m in machine_types) if machine_types else False
        is_dumper = any('DUMPER' in m.upper() or 'CAMION' in m.upper() 
                      for m in machine_types) if machine_types else False
    
    # CRÉER DES SOUS-ONGLETS SELON LE TYPE D'OPÉRATEUR
    show_loader_tab = True
    show_dumper_tab = True
    
    if is_loader and not is_dumper:
        # Opérateur de chargement uniquement
        show_dumper_tab = False
    elif is_dumper and not is_loader:
        # Opérateur de transport uniquement
        show_loader_tab = False
    
    # Créer les sous-onglets selon ce qui doit être affiché
    sub_tab_labels = []
    if show_loader_tab:
        sub_tab_labels.append("📦 Opérateur de Chargement")
    if show_dumper_tab:
        sub_tab_labels.append("🚚 Opérateur de Transport")
    
    # S'assurer qu'il y a au moins un sous-onglet
    if not sub_tab_labels:
        # Si aucun sous-onglet n'est défini, afficher les deux par défaut
        sub_tab_labels = ["📦 Opérateur de Chargement", "🚚 Opérateur de Transport"]
        show_loader_tab = True
        show_dumper_tab = True

    perms_op = (user_info or {}).get("permissions", {})
    if perms_op.get("messagerie"):
        sub_tab_labels.append("💬 Messagerie")
    if perms_op.get("sst"):
        sub_tab_labels.append("🦺 SST")
    
    # Créer les sous-onglets - TOUJOURS CRÉER AU MOINS UN
    if sub_tab_labels:
        sub_tabs = st.tabs(sub_tab_labels)
    else:
        # Fallback absolu - ne devrait jamais arriver
        sub_tabs = st.tabs(["📦 Opérateur de Chargement", "🚚 Opérateur de Transport"])
    
    loader_tab_idx = _sub_tab_index(sub_tab_labels, "📦 Opérateur de Chargement")
    dumper_tab_idx = _sub_tab_index(sub_tab_labels, "🚚 Opérateur de Transport")
    mess_idx = _sub_tab_index(sub_tab_labels, "💬 Messagerie")
    sst_idx = _sub_tab_index(sub_tab_labels, "🦺 SST")
    
    # SOUS-ONGLET 1: OPÉRATEUR DE CHARGEMENT
    if show_loader_tab and loader_tab_idx >= 0:
        with sub_tabs[loader_tab_idx]:
            st.markdown("### 📦 OPÉRATEUR DE CHARGEMENT")
            st.info("Interface de validation pour opérateur de chargement")
            
            # TYPE DE MINERAI - BOUTONS TOUJOURS VISIBLES
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%);
                        padding: 20px; border-radius: 15px; border: 3px solid #F5B800; margin: 20px 0;">
                <h2 style="color: #F5B800; text-align: center; font-size: 48px; font-weight: 900; margin-bottom: 20px;">
                    TYPE DE MINERAI
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🥇 OR", use_container_width=True, key="btn_or_loader", type="primary"):
                    st.session_state.selected_mineral_type = "OR"
                    st.rerun()
                if st.button("💎 DIAMANT", use_container_width=True, key="btn_diamond_loader"):
                    st.session_state.selected_mineral_type = "DIAMANT"
                    st.rerun()
            with col2:
                if st.button("⚫ CHARBON", use_container_width=True, key="btn_coal_loader"):
                    st.session_state.selected_mineral_type = "CHARBON"
                    st.rerun()
                if st.button("🔷 AUTRE", use_container_width=True, key="btn_other_loader"):
                    st.session_state.selected_mineral_type = "AUTRE"
                    st.rerun()
            
            # Afficher le type sélectionné
            if 'selected_mineral_type' in st.session_state:
                st.markdown(f"""
                <div style="background: #4CAF50; color: #000000; padding: 30px; border-radius: 15px; 
                            border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                            display: flex; align-items: center; justify-content: center;
                            font-size: 56px; font-weight: 900; text-align: center;">
                    ✅ TYPE DE MINERAI SÉLECTIONNÉ : <strong>{st.session_state.selected_mineral_type}</strong>
                </div>
                """, unsafe_allow_html=True)
            
            # GRADE/TENEUR - BOUTONS TOUJOURS VISIBLES
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%);
                        padding: 20px; border-radius: 15px; border: 3px solid #F5B800; margin: 20px 0;">
                <h2 style="color: #F5B800; text-align: center; font-size: 48px; font-weight: 900; margin-bottom: 20px;">
                    GRADE / TENEUR
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            col3, col4, col5 = st.columns(3)
            with col3:
                if st.button("⭐ HAUT", use_container_width=True, key="btn_high_loader", type="primary"):
                    st.session_state.selected_grade = "HAUT"
                    st.rerun()
            with col4:
                if st.button("⭐ MOYEN", use_container_width=True, key="btn_medium_loader"):
                    st.session_state.selected_grade = "MOYEN"
                    st.rerun()
            with col5:
                if st.button("⭐ BAS", use_container_width=True, key="btn_low_loader"):
                    st.session_state.selected_grade = "BAS"
                    st.rerun()
            
            # Afficher le grade sélectionné
            if 'selected_grade' in st.session_state:
                st.markdown(f"""
                <div style="background: #2196F3; color: #000000; padding: 30px; border-radius: 15px; 
                            border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                            display: flex; align-items: center; justify-content: center;
                            font-size: 56px; font-weight: 900; text-align: center;">
                    📊 GRADE SÉLECTIONNÉ : <strong>{st.session_state.selected_grade}</strong>
                </div>
                """, unsafe_allow_html=True)
            
            # SÉLECTION DU NUMÉRO DE CAMION - TOUJOURS VISIBLE
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%);
                        padding: 20px; border-radius: 15px; border: 3px solid #F5B800; margin: 20px 0;">
                <h2 style="color: #F5B800; text-align: center; font-size: 48px; font-weight: 900; margin-bottom: 20px;">
                    NUMÉRO DE CAMION
                </h2>
            </div>
            """, unsafe_allow_html=True)
            
            # Récupérer la liste des camions/dumpers disponibles
            df_machines_loader = manager.get_summary_dataframe()
            # Filtrer pour obtenir uniquement les dumpers et camions
            trucks_available = df_machines_loader[
                (df_machines_loader['Type'].str.contains('DUMPER', case=False, na=False)) |
                (df_machines_loader['Type'].str.contains('CAMION', case=False, na=False))
            ]
            
            # Créer une liste des numéros de camions disponibles
            truck_list = ["Sélectionner un camion..."] + trucks_available['ID'].tolist()
            
            # Si aucun camion n'est disponible, permettre la saisie manuelle
            if len(trucks_available) == 0:
                st.markdown("""
                <div style="background: #FF9800; color: #000000; padding: 30px; border-radius: 15px; 
                            border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                            display: flex; align-items: center; justify-content: center;
                            font-size: 56px; font-weight: 900; text-align: center;">
                    ⚠️ AUCUN CAMION DISPONIBLE DANS LE SYSTÈME. SAISIE MANUELLE POSSIBLE.
                </div>
                """, unsafe_allow_html=True)
                selected_truck = st.text_input(
                    "Numéro de camion",
                    value=st.session_state.get('selected_truck_loader', ''),
                    key="truck_input_loader",
                    placeholder="Ex: DT-01, CM-01, etc."
                )
                if selected_truck:
                    st.session_state.selected_truck_loader = selected_truck
            else:
                # Selectbox pour choisir le camion
                selected_truck_idx = 0
                if 'selected_truck_loader' in st.session_state:
                    try:
                        selected_truck_idx = truck_list.index(st.session_state.selected_truck_loader)
                    except ValueError:
                        selected_truck_idx = 0
                
                # Rendre le selectbox très visible avec un style personnalisé
                st.markdown("""
                <div style="background: rgba(245, 184, 0, 0.1); padding: 15px; border-radius: 10px; border: 2px solid #F5B800; margin: 20px 0;">
                    <p style="color: #F5B800; font-size: 42px; font-weight: 900; margin-bottom: 15px;">
                        Sélectionner le camion en cours de chargement
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                selected_truck = st.selectbox(
                    "",
                    truck_list,
                    index=selected_truck_idx,
                    key="truck_select_loader",
                    label_visibility="collapsed"
                )
                
                if selected_truck and selected_truck != "Sélectionner un camion...":
                    st.session_state.selected_truck_loader = selected_truck
                    # Afficher les informations du camion sélectionné
                    truck_info = trucks_available[trucks_available['ID'] == selected_truck]
                    if not truck_info.empty:
                        st.markdown(f"""
                        <div style="background: #4CAF50; color: #000000; padding: 30px; border-radius: 15px; 
                                    border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                                    display: flex; align-items: center; justify-content: center;
                                    font-size: 56px; font-weight: 900; text-align: center;">
                            ✅ CAMION SÉLECTIONNÉ : <strong>{selected_truck}</strong>
                        </div>
                        """, unsafe_allow_html=True)
                        st.markdown(f"""
                        <div style="background: #2196F3; color: #000000; padding: 30px; border-radius: 15px; 
                                    border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                                    display: flex; align-items: center; justify-content: center;
                                    font-size: 56px; font-weight: 900; text-align: center;">
                            📊 TYPE: {truck_info.iloc[0]['Type']} | STATUT: {truck_info.iloc[0]['Statut']}
                        </div>
                        """, unsafe_allow_html=True)
            
            # BOUTON DE VALIDATION - TOUJOURS VISIBLE
            st.markdown("---")
            if st.button("✅ VALIDER LE CHARGEMENT", use_container_width=True, key="btn_validate_loader", type="primary"):
                validation_errors = []
                if 'selected_mineral_type' not in st.session_state:
                    validation_errors.append("Type de minerai")
                if 'selected_grade' not in st.session_state:
                    validation_errors.append("Grade/Teneur")
                if 'selected_truck_loader' not in st.session_state or not st.session_state.selected_truck_loader:
                    validation_errors.append("Numéro de camion")
                
                if not validation_errors:
                    # Validation réussie
                    validation_data = {
                        "operator": st.session_state.username,
                        "truck": st.session_state.selected_truck_loader,
                        "mineral_type": st.session_state.selected_mineral_type,
                        "grade": st.session_state.selected_grade,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "type": "loading"
                    }
                    
                    # Ajouter à la liste des validations
                    if 'validations' not in st.session_state:
                        st.session_state.validations = []
                    st.session_state.validations.append(validation_data)
                    
                    # ENVOYER UNE NOTIFICATION À TOUS LES OPÉRATEURS DE DÉCHARGEMENT
                    # La notification sera visible par tous les opérateurs de déchargement
                    truck_id = st.session_state.selected_truck_loader
                    
                    # Créer la notification pour les opérateurs de déchargement
                    notification = {
                        "id": f"notif_{datetime.now().strftime('%Y%m%d%H%M%S')}_{truck_id}",
                        "from_operator": st.session_state.username,
                        "to_operator": "all_dumpers",  # Visible par tous les opérateurs de déchargement
                        "truck": truck_id,
                        "message": f"Chargement terminé pour le camion {truck_id}. Vous pouvez bouger !",
                        "mineral_type": st.session_state.selected_mineral_type,
                        "grade": st.session_state.selected_grade,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "status": "pending",  # pending, acknowledged
                        "type": "loading_complete"
                    }
                    
                    # Ajouter la notification au système global (accessible par tous les opérateurs de déchargement)
                    try:
                        # Charger les notifications existantes depuis le fichier
                        all_notifications = load_notifications()
                        all_notifications.append(notification)
                        # Sauvegarder dans le fichier partagé
                        save_notifications(all_notifications)
                        # Mettre à jour session_state pour l'affichage immédiat
                        st.session_state.operator_notifications = all_notifications
                    except Exception as e:
                        # Si erreur (hors ligne), stocker dans localStorage via JavaScript
                        notification_json = json.dumps(notification)
                        st.markdown(f"""
                        <script>
                        if (typeof storeOfflineNotification !== 'undefined') {{
                            storeOfflineNotification({notification_json});
                            console.log('Notification stockée hors ligne');
                        }} else {{
                            var offlineNotifs = JSON.parse(localStorage.getItem('offline_notifications') || '[]');
                            offlineNotifs.push({notification_json});
                            localStorage.setItem('offline_notifications', JSON.stringify(offlineNotifs));
                            console.log('Notification stockée hors ligne (fallback)');
                        }}
                        </script>
                        """, unsafe_allow_html=True)
                        st.warning("⚠️ Hors ligne - La notification sera synchronisée automatiquement lors de la reconnexion.")
                    
                    # Message de validation avec style uniforme et grand
                    st.markdown(f"""
                    <div style="background: #4CAF50; color: #000000; padding: 40px; border-radius: 15px; 
                                border: 4px solid #F5B800; margin: 30px 0; min-height: 200px; 
                                display: flex; flex-direction: column; justify-content: center; align-items: center;
                                font-size: 64px; font-weight: 900; text-align: center;">
                        <div style="font-size: 80px; font-weight: 900; margin-bottom: 20px;">✅</div>
                        <div style="font-size: 64px; font-weight: 900; color: #000000; margin-bottom: 15px;">
                            CHARGEMENT VALIDÉ AVEC SUCCÈS !
                        </div>
                        <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 20px;">
                            <strong>Camion:</strong> {st.session_state.selected_truck_loader}
                        </div>
                        <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                            <strong>Type de minerai:</strong> {st.session_state.selected_mineral_type}
                        </div>
                        <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                            <strong>Grade:</strong> {st.session_state.selected_grade}
                        </div>
                        <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                            <strong>Heure:</strong> {validation_data['timestamp']}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Message de confirmation d'envoi de notification
                    st.markdown(f"""
                    <div style="background: #2196F3; color: #000000; padding: 30px; border-radius: 15px; 
                                border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                                display: flex; align-items: center; justify-content: center;
                                font-size: 56px; font-weight: 900; text-align: center;">
                        🔔 NOTIFICATION ENVOYÉE AUX OPÉRATEURS DE DÉCHARGEMENT
                    </div>
                    """, unsafe_allow_html=True)
                    
                    # Réinitialiser les sélections (optionnel)
                    # st.session_state.selected_mineral_type = None
                    # st.session_state.selected_grade = None
                    # st.session_state.selected_truck_loader = None
                else:
                    st.markdown(f"""
                    <div style="background: #FF9800; color: #000000; padding: 40px; border-radius: 15px; 
                                border: 4px solid #F5B800; margin: 30px 0; min-height: 200px; 
                                display: flex; flex-direction: column; justify-content: center; align-items: center;
                                font-size: 64px; font-weight: 900; text-align: center;">
                        <div style="font-size: 80px; font-weight: 900; margin-bottom: 20px;">⚠️</div>
                        <div style="font-size: 64px; font-weight: 900; color: #000000;">
                            VEUILLEZ COMPLÉTER LES INFORMATIONS SUIVANTES :
                        </div>
                        <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 20px;">
                            {', '.join(validation_errors)}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
    
    # SOUS-ONGLET 2: OPÉRATEUR DE TRANSPORT (DUMPER)
    if show_dumper_tab and dumper_tab_idx >= 0:
        with sub_tabs[dumper_tab_idx]:
            st.markdown("### 🚚 OPÉRATEUR DE TRANSPORT")
            
            # SECTION NOTIFICATIONS - AFFICHER EN PREMIER
            col_notif_title, col_refresh = st.columns([4, 1])
            with col_notif_title:
                st.markdown("""
                <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%);
                            padding: 20px; border-radius: 15px; border: 3px solid #F5B800; margin: 20px 0;">
                    <h2 style="color: #F5B800; text-align: center; font-size: 48px; font-weight: 900; margin-bottom: 20px;">
                        🔔 NOTIFICATIONS DE CHARGEMENT
                    </h2>
                </div>
                """, unsafe_allow_html=True)
            with col_refresh:
                if st.button("🔄", use_container_width=True, key="refresh_notifications_dumper", help="Actualiser les notifications"):
                    st.rerun()
            
            # Charger les notifications depuis le fichier partagé (pour avoir les dernières)
            all_notifications = load_notifications()
            # Mettre à jour session_state
            st.session_state.operator_notifications = all_notifications
            
            # Récupérer les notifications pour cet opérateur
            if all_notifications:
                # Filtrer les notifications de type "loading_complete" qui sont en attente
                pending_notifications = [
                    n for n in all_notifications 
                    if n.get('type') == 'loading_complete' and n.get('status') == 'pending'
                ]
                
                if pending_notifications:
                    # Afficher les notifications en attente avec les informations validées
                    for idx, notif in enumerate(pending_notifications):
                        # Afficher l'ordre de déchargement avec les informations validées
                        st.markdown(f"""
                        <div style="background: #F5B800; color: #000000; padding: 40px; border-radius: 15px; 
                                    border: 4px solid #F5B800; margin: 20px 0; min-height: 300px; 
                                    display: flex; flex-direction: column; justify-content: center; align-items: center;
                                    font-size: 64px; font-weight: 900; text-align: center;">
                            <div style="font-size: 80px; font-weight: 900; margin-bottom: 20px;">📋</div>
                            <div style="font-size: 64px; font-weight: 900; color: #000000; margin-bottom: 20px;">
                                ORDRE DE DÉCHARGEMENT
                            </div>
                            <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 20px;">
                                <strong>Camion:</strong> {notif.get('truck', 'N/A')}
                            </div>
                            <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                <strong>Type de minerai:</strong> {notif.get('mineral_type', 'N/A')}
                            </div>
                            <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                <strong>Grade:</strong> {notif.get('grade', 'N/A')}
                            </div>
                            <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                <strong>Heure de chargement:</strong> {notif.get('timestamp', 'N/A')}
                            </div>
                            <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                <strong>Opérateur de chargement:</strong> {notif.get('from_operator', 'N/A')}
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Bouton unique pour confirmer le déchargement
                        st.markdown("---")
                        if st.button(f"✅ J'AI DÉCHARGÉ LE CAMION {notif.get('truck', 'N/A')}", 
                                   use_container_width=True, 
                                   key=f"unload_{notif.get('id')}",
                                   type="primary"):
                            # Créer une validation de déchargement
                            unload_validation = {
                                "operator": st.session_state.username,
                                "truck": notif.get('truck'),
                                "mineral_type": notif.get('mineral_type'),
                                "grade": notif.get('grade'),
                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                "loading_timestamp": notif.get('timestamp'),
                                "loading_operator": notif.get('from_operator'),
                                "type": "unloading"
                            }
                            
                            # Ajouter à la liste des validations
                            if 'validations' not in st.session_state:
                                st.session_state.validations = []
                            st.session_state.validations.append(unload_validation)
                            
                            # Marquer la notification comme traitée dans le fichier partagé
                            all_notifications = load_notifications()
                            for n in all_notifications:
                                if n.get('id') == notif.get('id'):
                                    n['status'] = 'acknowledged'
                                    break
                            save_notifications(all_notifications)
                            st.session_state.operator_notifications = all_notifications
                            
                            # Afficher un message de confirmation avec style uniforme
                            st.markdown(f"""
                            <div style="background: #4CAF50; color: #000000; padding: 40px; border-radius: 15px; 
                                        border: 4px solid #F5B800; margin: 30px 0; min-height: 200px; 
                                        display: flex; flex-direction: column; justify-content: center; align-items: center;
                                        font-size: 64px; font-weight: 900; text-align: center;">
                                <div style="font-size: 80px; font-weight: 900; margin-bottom: 20px;">✅</div>
                                <div style="font-size: 64px; font-weight: 900; color: #000000; margin-bottom: 15px;">
                                    DÉCHARGEMENT VALIDÉ AVEC SUCCÈS !
                                </div>
                                <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 20px;">
                                    <strong>Camion:</strong> {notif.get('truck', 'N/A')}
                                </div>
                                <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                    <strong>Type de minerai:</strong> {notif.get('mineral_type', 'N/A')}
                                </div>
                                <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                    <strong>Grade:</strong> {notif.get('grade', 'N/A')}
                                </div>
                                <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 15px;">
                                    <strong>Heure de déchargement:</strong> {unload_validation['timestamp']}
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            st.rerun()
                else:
                    st.markdown("""
                    <div style="background: #2196F3; color: #000000; padding: 30px; border-radius: 15px; 
                                border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                                display: flex; align-items: center; justify-content: center;
                                font-size: 56px; font-weight: 900; text-align: center;">
                        📭 AUCUNE NOTIFICATION EN ATTENTE
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background: #2196F3; color: #000000; padding: 30px; border-radius: 15px; 
                            border: 4px solid #F5B800; margin: 20px 0; min-height: 150px; 
                            display: flex; align-items: center; justify-content: center;
                            font-size: 56px; font-weight: 900; text-align: center;">
                    📭 AUCUNE NOTIFICATION EN ATTENTE
                </div>
                """, unsafe_allow_html=True)
            
            # Si aucune notification en attente, afficher un message
            # Recharger les notifications depuis le fichier pour être sûr d'avoir les dernières
            all_notifications_check = load_notifications()
            if not all_notifications_check:
                st.markdown("""
                <div style="background: #2196F3; color: #000000; padding: 40px; border-radius: 15px; 
                            border: 4px solid #F5B800; margin: 30px 0; min-height: 200px; 
                            display: flex; flex-direction: column; justify-content: center; align-items: center;
                            font-size: 64px; font-weight: 900; text-align: center;">
                    <div style="font-size: 80px; font-weight: 900; margin-bottom: 20px;">📭</div>
                    <div style="font-size: 64px; font-weight: 900; color: #000000;">
                        EN ATTENTE D'ORDRE DE DÉCHARGEMENT
                    </div>
                    <div style="font-size: 56px; font-weight: 900; color: #000000; margin-top: 20px;">
                                Les ordres de déchargement apparaîtront ici une fois que l'opérateur de chargement aura terminé.
                    </div>
                </div>
                """, unsafe_allow_html=True)
    
    if mess_idx >= 0:
        with sub_tabs[mess_idx]:
            render_messagerie_tab(user_mgr, user_info)
    if sst_idx >= 0:
        with sub_tabs[sst_idx]:
            render_sst_tab(user_info, staff_mgr)

    # Arrêter l'exécution ici pour les opérateurs - ne pas créer les autres onglets
    st.stop()

# Pour les autres utilisateurs, créer les onglets normalement
# Vérifier qu'il y a au moins un onglet avant de créer les tabs
if not authorized_tabs:
    authorized_tabs = ["DASHBOARD", "MARCHÉ OR"]  # Fallback si aucun onglet

_TAB_ICONS = {
    "DASHBOARD":          "📊 DASHBOARD",
    "CYCLES":             "🔄 CYCLES",
    "CARBURANT":          "⛽ CARBURANT",
    "MAINT.":             "🔧 MAINT.",
    "GESTION STOCK":      "📦 STOCK",
    "CARTE":              "🗺️ CARTE",
    "FINANCE":            "💰 FINANCE",
    "RH":                 "👥 RH",
    "ADMIN":              "⚙️ ADMIN",
    "DONNÉES INGÉNIERIE": "📐 ING.",
    "MESSAGERIE":         "💬 MESSAGERIE",
    "SST":                "🦺 SST",
    "MARCHÉ OR":          "🥇 OR",
    "VALIDATION OPÉRATEUR": "✅ VALIDATION",
}
_display_tabs = [_TAB_ICONS.get(t, t) for t in authorized_tabs]
tabs = st.tabs(_display_tabs)
tab_dict = dict(zip(authorized_tabs, tabs))

# --- DASHBOARD ---
if "DASHBOARD" in tab_dict:
    with tab_dict["DASHBOARD"]:
        # Calculs des métriques clés (accès tolérants si schéma inattendu / ancien cache)
        machines_actives = _fleet_statut_count(df, "Active")
        machines_pannes = _fleet_statut_count(df, "Panne")
        total_machines = len(df)
        disponibilite = round((machines_actives / total_machines * 100), 1) if total_machines > 0 else 0
        production_totale = _fleet_col_sum_int(df, "Production (T)")
        cycles_totaux = _fleet_col_sum_int(df, "Cycles")
        total_heures = _fleet_col_sum_int(df, "H. Total")
        heures_jour = _fleet_col_sum_int(df, "H. Run Jour")
        
        # Revenus et rentabilité (si disponible)
        revenu_jour = int(df['Rev. Jour ($)'].sum()) if 'Rev. Jour ($)' in df.columns else 0
        rentabilite_totale = int(df['Rentabilité ($)'].sum()) if 'Rentabilité ($)' in df.columns else 0
        
        # Alertes de maintenance
        active_alerts = manager.maintenance_manager.get_all_active_alerts()
        nb_alertes = len(active_alerts)
        
        # Stock bas
        stock_mgr = manager.maintenance_manager.stock_manager
        low_stock_items = stock_mgr.get_low_stock_items()
        nb_stock_bas = len(low_stock_items)
        
        fuel_avg = None
        if "Carburant (%)" in df.columns and not df.empty:
            try:
                fuel_avg = round(float(df["Carburant (%)"].mean()), 1)
            except Exception:
                fuel_avg = None
        
        # Cartes KPI — glassmorphism industriel
        st.markdown("""
        <style>
        .dashboard-kpi {
            background: rgba(20, 28, 45, 0.78);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 16px;
            padding: 20px 22px;
            margin: 8px 0;
            min-height: 132px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.05);
            transition: box-shadow 180ms ease, border-color 180ms ease, transform 180ms ease;
        }
        .dashboard-kpi:hover {
            box-shadow: 0 12px 42px rgba(0,0,0,0.45);
            border-color: rgba(245, 184, 0, 0.30);
            transform: translateY(-2px);
        }
        .dashboard-kpi .kpi-lab {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.10em;
            color: #8A9BB0;
            margin-bottom: 10px;
            line-height: 1.3;
        }
        .dashboard-kpi .kpi-val {
            font-size: clamp(28px, 2.8vw, 42px);
            font-weight: 900;
            color: #EAEAEA;
            line-height: 1.1;
            letter-spacing: -0.02em;
        }
        .dashboard-kpi .kpi-sub {
            font-size: 13px;
            color: #7A8A9A;
            margin-top: 10px;
            font-weight: 600;
        }
        .dashboard-kpi.kpi-border-success { border-left: 4px solid #28A745; box-shadow: 0 8px 32px rgba(0,0,0,0.35), -2px 0 16px rgba(40,167,69,0.12), inset 0 1px 0 rgba(255,255,255,0.05); }
        .dashboard-kpi.kpi-border-warning { border-left: 4px solid #FF6B00; box-shadow: 0 8px 32px rgba(0,0,0,0.35), -2px 0 16px rgba(255,107,0,0.12), inset 0 1px 0 rgba(255,255,255,0.05); }
        .dashboard-kpi.kpi-border-danger  { border-left: 4px solid #DC3545; box-shadow: 0 8px 32px rgba(0,0,0,0.35), -2px 0 16px rgba(220,53,69,0.12), inset 0 1px 0 rgba(255,255,255,0.05); }
        .dashboard-kpi.kpi-border-accent  { border-left: 4px solid #F5B800; box-shadow: 0 8px 32px rgba(0,0,0,0.35), -2px 0 16px rgba(245,184,0,0.15), inset 0 1px 0 rgba(255,255,255,0.05); }
        .dashboard-kpi.kpi-border-muted   { border-left: 4px solid #5A5A5A; }
        </style>
        """, unsafe_allow_html=True)
        
        # HEADER DU DASHBOARD
        today_str = date.today().strftime('%d %B %Y')
        st.markdown(f"""
        <div style="background: linear-gradient(90deg, #0F2A44 0%, #1E1E1E 100%); padding: 28px; border-radius: 8px; margin-bottom: 24px; text-align: center; box-shadow: 0 10px 30px rgba(0,0,0,0.4); border: 1px solid #404040;">
            <h1 style="color: #EAEAEA; margin: 0; font-size: clamp(28px, 4vw, 44px); font-weight: 800; letter-spacing: -0.02em;">
                🛰️ Centre de contrôle flotte
            </h1>
            <p style="color: #A0A0A0; margin: 10px 0 0 0; font-size: 16px; font-weight: 600;">
                KPI temps réel • {today_str}
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        kpi_idle_count = _fleet_statut_count(df, "Idle")
        if kpi_idle_count == 0 and "Statut" in df.columns and not df.empty:
            try:
                sl = df["Statut"].astype(str).str.strip().str.lower()
                kpi_idle_count = int(sl.isin(("idle", "arrêt", "arret", "inactive", "en attente")).sum())
            except Exception:
                kpi_idle_count = 0
        
        cls_panne = "status-breakdown" if machines_pannes else "status-idle"
        cls_maint_ct = "status-maintenance" if nb_alertes else "status-idle"
        cls_stock_ct = "status-maintenance" if nb_stock_bas else "status-active"
        
        # Rangée 1 — production, flotte, carburant, incidents
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            b1 = "kpi-border-success" if disponibilite >= 70 or total_machines == 0 else "kpi-border-warning"
            st.markdown(f"""
            <div class="dashboard-kpi {b1}">
                <div class="kpi-lab">🚛 Flotte active</div>
                <div class="kpi-val">{machines_actives} / {total_machines}</div>
                <div class="kpi-sub">Disponibilité <span class="status-active">{disponibilite}%</span>{f' • Arrêt {kpi_idle_count}' if kpi_idle_count else ''}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            b2 = "kpi-border-danger" if machines_pannes > 0 else "kpi-border-muted"
            st.markdown(f"""
            <div class="dashboard-kpi {b2}">
                <div class="kpi-lab">🔧 Arrêt / panne</div>
                <div class="kpi-val"><span class="{cls_panne}">{machines_pannes}</span></div>
                <div class="kpi-sub">{"⚠️ Intervention requise" if machines_pannes > 0 else "OK — ligne opérationnelle"}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="dashboard-kpi kpi-border-accent">
                <div class="kpi-lab">⛏ Production cumulée</div>
                <div class="kpi-val">{production_totale:,} t</div>
                <div class="kpi-sub">🔄 {cycles_totaux:,} cycles • Shift {heures_jour} h</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            if fuel_avg is not None:
                fuel_state = "status-active" if fuel_avg >= 40 else ("status-maintenance" if fuel_avg >= 20 else "status-breakdown")
                st.markdown(f"""
                <div class="dashboard-kpi kpi-border-accent">
                    <div class="kpi-lab">⛽ Niveau carburant (moy.)</div>
                    <div class="kpi-val"><span class="{fuel_state}">{fuel_avg} %</span></div>
                    <div class="kpi-sub">Réservoirs flotte • Surveiller sous 25 %</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="dashboard-kpi kpi-border-accent">
                    <div class="kpi-lab">⏱️ Heures shift (jour)</div>
                    <div class="kpi-val">{heures_jour} h</div>
                    <div class="kpi-sub">Cumul total {total_heures:,} h</div>
                </div>
                """, unsafe_allow_html=True)
        
        # Rangée 2 — finance ou cycles, maintenance, stock, perf cycle
        col5, col6, col7, col8 = st.columns(4)
        avg_cycle = round(df['Tps Cycle Moy (min)'].mean(), 1) if 'Tps Cycle Moy (min)' in df.columns and not df.empty else 0
        
        with col5:
            if revenu_jour > 0:
                st.markdown(f"""
                <div class="dashboard-kpi kpi-border-accent">
                    <div class="kpi-lab">💰 Revenus (jour)</div>
                    <div class="kpi-val">${revenu_jour:,}</div>
                    <div class="kpi-sub">Rentabilité cumul. ${rentabilite_totale:,}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="dashboard-kpi kpi-border-muted">
                    <div class="kpi-lab">🔄 Cycles (volume)</div>
                    <div class="kpi-val">{cycles_totaux:,}</div>
                    <div class="kpi-sub">🛰️ Temps cycle moy. {avg_cycle} min</div>
                </div>
                """, unsafe_allow_html=True)
        
        with col6:
            b6 = "kpi-border-warning" if nb_alertes > 0 else "kpi-border-success"
            st.markdown(f"""
            <div class="dashboard-kpi {b6}">
                <div class="kpi-lab">🔔 Maintenance ouverte</div>
                <div class="kpi-val"><span class="{cls_maint_ct}">{nb_alertes}</span></div>
                <div class="kpi-sub">{"Planifier interventions" if nb_alertes else "Aucune alerte active"}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col7:
            b7 = "kpi-border-warning" if nb_stock_bas > 0 else "kpi-border-success"
            st.markdown(f"""
            <div class="dashboard-kpi {b7}">
                <div class="kpi-lab">📦 Stock critique</div>
                <div class="kpi-val"><span class="{cls_stock_ct}">{nb_stock_bas}</span></div>
                <div class="kpi-sub">{"Réappro. nécessaire" if nb_stock_bas else "Seuils OK"}</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col8:
            st.markdown(f"""
            <div class="dashboard-kpi kpi-border-muted">
                <div class="kpi-lab">⚡ Perf. cycle</div>
                <div class="kpi-val">{avg_cycle} min</div>
                <div class="kpi-sub">Moyenne flotte • objectif terrain</div>
            </div>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # SECTION 3: GRAPHIQUES VISUELS
        col_graph1, col_graph2 = st.columns(2)
        
        with col_graph1:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📊 Répartition des Statuts")
            try:
                status_counts = df['Statut'].value_counts()
                fig_status = px.pie(
                    values=status_counts.values,
                    names=status_counts.index,
                    color_discrete_map={
                        'Active': '#28A745',
                        'Panne': '#DC3545',
                        'Maintenance': '#FF6B00',
                        'Idle': '#A0A0A0',
                    },
                    hole=0.4
                )
                fig_status.update_traces(textposition='inside', textinfo='percent+label', 
                                        textfont_size=14, marker=dict(line=dict(color='#FFFFFF', width=2)))
                fig_status.update_layout(showlegend=True, height=350, font=dict(size=12))
                st.plotly_chart(fig_status, width='stretch')
            except:
                st.info("Graphique disponible avec plotly")
            st.markdown('</div>', unsafe_allow_html=True)
        
        with col_graph2:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📈 Production par Machine")
            try:
                prod_df = df[['ID', 'Production (T)']].copy()
                prod_df = prod_df.sort_values('Production (T)', ascending=False).head(10)
                fig_prod = px.bar(
                    prod_df,
                    x='ID',
                    y='Production (T)',
                    color='Production (T)',
                    color_continuous_scale='Greens',
                    labels={'Production (T)': 'Production (T)', 'ID': 'Machine'}
                )
                fig_prod.update_layout(showlegend=False, height=350, xaxis_title="Machine", yaxis_title="Production (T)")
                st.plotly_chart(fig_prod, width='stretch')
            except:
                st.info("Graphique disponible avec plotly")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # SECTION 4: ALERTES ET ACTIONS REQUISES
        if machines_pannes > 0 or nb_alertes > 0 or nb_stock_bas > 0:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🚨 ALERTES & ACTIONS REQUISES")
            
            alert_col1, alert_col2, alert_col3 = st.columns(3)
            
            with alert_col1:
                if machines_pannes > 0:
                    st.error(f"**🔴 {machines_pannes} Machine(s) en Panne**")
                    for machine in df[df['Statut']=='Panne']['ID']:
                        st.write(f"- {machine}")
            
            with alert_col2:
                if nb_alertes > 0:
                    st.warning(f"**⚠️ {nb_alertes} Maintenance(s) Planifiée(s)**")
                    for alert in active_alerts[:5]:  # Afficher les 5 premières
                        st.write(f"- {alert.machine_id}: {alert.maintenance_type}")
            
            with alert_col3:
                if nb_stock_bas > 0:
                    st.warning(f"**📦 {nb_stock_bas} Pièce(s) en Stock Bas**")
                    for item in low_stock_items[:5]:  # Afficher les 5 premières
                        st.write(f"- {item['nom']}: {item['quantite']} {item['unite']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # SECTION 5: TABLEAU RÉCAPITULATIF
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("📋 VUE D'ENSEMBLE DE LA FLOTTE")
        
        # Sélection des colonnes importantes
        display_cols = ['ID', 'Type', 'Statut', 'Opérateur', 'Production (T)', 'Cycles', 
                       'H. Run Jour', 'Prochaine PM', 'Carburant (%)']
        available_cols = [col for col in display_cols if col in df.columns]
        
        # Style conditionnel pour les statuts
        def color_status(val):
            if val == 'Active':
                return 'background-color: rgba(40, 167, 69, 0.22); color: #EAEAEA; font-weight: bold'
            elif val == 'Panne':
                return 'background-color: rgba(220, 53, 69, 0.22); color: #EAEAEA; font-weight: bold'
            else:
                return 'background-color: rgba(255, 107, 0, 0.18); color: #EAEAEA; font-weight: bold'
        
        styled_df = _styler_cell_map(df[available_cols].style, color_status, subset=['Statut'])
        st.dataframe(styled_df, width='stretch', hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

# --- CYCLES ---
if "CYCLES" in tab_dict:
    with tab_dict["CYCLES"]:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("🚜 PERFORMANCE GLOBALE")
        avg_fleet = round(df['Tps Cycle Moy (min)'].mean(), 1) if not df.empty else 0
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("TOTAL HEURES", f"{_fleet_col_sum_int(df, 'H. Total')} h")
        k2.metric("HEURES SHIFT", f"{_fleet_col_sum_int(df, 'H. Run Jour')} h")
        k3.metric("CYCLES TOTAUX", f"{_fleet_col_sum_int(df, 'Cycles')}")
        k4.metric("PRODUCTION TOTALE", f"{_fleet_col_sum_int(df, 'Production (T)')} T")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TEMPS DE CYCLE DÉTAILLÉ ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("⏱️ TEMPS DE CYCLE - ANALYSE DÉTAILLÉE")
        
        if not df.empty and 'Tps Cycle Moy (min)' in df.columns:
            # Statistiques globales du temps de cycle
            cycle_times = df[df['Tps Cycle Moy (min)'] > 0]['Tps Cycle Moy (min)']
            if len(cycle_times) > 0:
                min_cycle = cycle_times.min()
                max_cycle = cycle_times.max()
                avg_cycle = cycle_times.mean()
                median_cycle = cycle_times.median()
                
                col_stat1, col_stat2, col_stat3, col_stat4, col_stat5 = st.columns(5)
                col_stat1.metric("⏱️ Temps Moyen", f"{avg_cycle:.1f} min")
                col_stat2.metric("⚡ Meilleur Temps", f"{min_cycle:.1f} min", delta=f"-{max_cycle - min_cycle:.1f} min")
                col_stat3.metric("🐌 Temps Max", f"{max_cycle:.1f} min", delta_color="inverse")
                col_stat4.metric("📊 Médiane", f"{median_cycle:.1f} min")
                
                # Identifier les engins avec le meilleur et pire temps
                best_machine = df.loc[df['Tps Cycle Moy (min)'].idxmin()] if 'ID' in df.columns else None
                worst_machine = df.loc[df['Tps Cycle Moy (min)'].idxmax()] if 'ID' in df.columns else None
                
                if best_machine is not None and worst_machine is not None:
                    col_stat5.markdown(f"""
                    <div style="padding: 10px; background: #f0f0f0; border-radius: 5px;">
                        <strong>🏆 Meilleur:</strong> {best_machine['ID']}<br>
                        <strong>⚠️ À améliorer:</strong> {worst_machine['ID']}
                    </div>
                    """, unsafe_allow_html=True)
                
                st.markdown("---")
                
                # Tableau détaillé du temps de cycle par engin
                cycle_cols = ['ID', 'Type', 'Opérateur', 'Cycles', 'Tps Cycle Moy (min)', 'H. Run Jour', 'Production (T)']
                cycle_df = df[cycle_cols].copy()
                
                # Calculer tonnes/heure pour l'efficacité
                cycle_df['Tonnes/Heure'] = (cycle_df['Production (T)'] / cycle_df['H. Run Jour']).round(2)
                cycle_df['Tonnes/Heure'] = cycle_df['Tonnes/Heure'].replace([float('inf'), float('-inf')], 0)
                cycle_df = cycle_df.fillna(0)
                
                # Trier par temps de cycle (du meilleur au pire)
                cycle_df = cycle_df.sort_values('Tps Cycle Moy (min)')
                
                st.dataframe(
                    cycle_df.style.format({
                        "Tps Cycle Moy (min)": "{:.1f} min",
                        "Tonnes/Heure": "{:.2f} T/h",
                        "Production (T)": "{:.0f} T"
                    }),
                    width='stretch',
                    hide_index=True
                )
        else:
            st.info("Aucune donnée de cycle disponible.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- PERFORMANCE DES ENGINS ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("🏭 PERFORMANCE DES ENGINS")
        
        if not df.empty:
            # Préparer les données de performance
            perf_data = []
            for idx, row in df.iterrows():
                # Calculer l'efficacité (tonnes/heure)
                tonnes_heure = (row['Production (T)'] / row['H. Run Jour']) if row['H. Run Jour'] > 0 else 0
                # Calculer les cycles/heure
                cycles_heure = (row['Cycles'] / row['H. Run Jour']) if row['H. Run Jour'] > 0 else 0
                
                perf_data.append({
                    "ID": row['ID'],
                    "Type": row['Type'],
                    "Opérateur": row.get('Opérateur', 'N/A'),
                    "Statut": row.get('Statut', 'N/A'),
                    "Cycles": int(row['Cycles']),
                    "Production (T)": int(row['Production (T)']),
                    "Tps Cycle Moy (min)": round(row.get('Tps Cycle Moy (min)', 0), 1),
                    "H. Run Jour": round(row['H. Run Jour'], 1),
                    "Tonnes/Heure": round(tonnes_heure, 2),
                    "Cycles/Heure": round(cycles_heure, 2),
                    "Efficacité (%)": round((row['H. Run Jour'] / 24) * 100, 1) if row['H. Run Jour'] > 0 else 0
                })
            
            df_perf = pd.DataFrame(perf_data)
            
            # Trier par performance (tonnes/heure décroissant)
            df_perf = df_perf.sort_values('Tonnes/Heure', ascending=False)
            
            # Classement
            df_perf.insert(0, 'Rang', range(1, len(df_perf) + 1))
            
            # Métriques globales
            col_p1, col_p2, col_p3, col_p4 = st.columns(4)
            avg_tonnes_heure = df_perf['Tonnes/Heure'].mean()
            best_engin = df_perf.iloc[0] if len(df_perf) > 0 else None
            total_prod = df_perf['Production (T)'].sum()
            avg_cycles_heure = df_perf['Cycles/Heure'].mean()
            
            col_p1.metric("📊 Moyenne Tonnes/Heure", f"{avg_tonnes_heure:.2f} T/h")
            col_p2.metric("🏆 Meilleur Engin", f"{best_engin['ID']}" if best_engin is not None else "N/A", f"{best_engin['Tonnes/Heure']:.2f} T/h" if best_engin is not None else "")
            col_p3.metric("📦 Production Totale", f"{total_prod:,.0f} T")
            col_p4.metric("⚡ Cycles/Heure Moy.", f"{avg_cycles_heure:.2f} cy/h")
            
            st.markdown("---")
            
            # Tableau de performance avec classement
            perf_cols = ['Rang', 'ID', 'Type', 'Opérateur', 'Statut', 'Cycles', 'Production (T)', 
                        'Tps Cycle Moy (min)', 'H. Run Jour', 'Tonnes/Heure', 'Cycles/Heure', 'Efficacité (%)']
            
            st.dataframe(
                df_perf[perf_cols].style.format({
                    "Tps Cycle Moy (min)": "{:.1f} min",
                    "Tonnes/Heure": "{:.2f} T/h",
                    "Cycles/Heure": "{:.2f} cy/h",
                    "Efficacité (%)": "{:.1f} %",
                    "Production (T)": "{:.0f} T",
                    "H. Run Jour": "{:.1f} h"
                }),
                width='stretch',
                hide_index=True
            )
            
            # Graphique de performance
            try:
                import plotly.express as px
                fig_perf = px.bar(
                    df_perf.head(10),  # Top 10
                    x='ID',
                    y='Tonnes/Heure',
                    title="Top 10 - Performance (Tonnes/Heure)",
                    color='Tonnes/Heure',
                    color_continuous_scale='Greens',
                    labels={'Tonnes/Heure': 'Tonnes/Heure', 'ID': 'Engin'}
                )
                fig_perf.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_perf, width='stretch')
            except:
                st.info("Graphique disponible avec plotly")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- PERFORMANCE DES OPÉRATEURS ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("👷 PERFORMANCE DES OPÉRATEURS")
        
        # Récupérer les opérateurs et leur performance
        operateurs = [e for e in staff_mgr.staff if e.role == "Operateur"]
        
        if operateurs and not df.empty:
            operator_perf = []
            
            for op in operateurs:
                # Trouver les machines assignées à cet opérateur
                machines_op = df[df['Opérateur'] == op.name]
                
                total_cycles = machines_op['Cycles'].sum() if len(machines_op) > 0 else 0
                total_production = machines_op['Production (T)'].sum() if len(machines_op) > 0 else 0
                total_hours = machines_op['H. Run Jour'].sum() if len(machines_op) > 0 else 0
                avg_cycle_time = machines_op['Tps Cycle Moy (min)'].mean() if len(machines_op) > 0 and machines_op['Tps Cycle Moy (min)'].mean() > 0 else 0
                
                tonnes_heure = (total_production / total_hours) if total_hours > 0 else 0
                
                # Nombre de machines assignées
                nb_machines = len(machines_op)
                machines_list = ", ".join(machines_op['ID'].tolist()) if len(machines_op) > 0 else "Aucune"
                
                operator_perf.append({
                    "Matricule": op.matricule,
                    "Nom": op.name,
                    "Équipe": op.team,
                    "Machines Assignées": machines_list,
                    "Nb Machines": nb_machines,
                    "Cycles Totaux": int(total_cycles),
                    "Production Totale (T)": int(total_production),
                    "Heures Travaillées": round(total_hours, 1),
                    "Tps Cycle Moy (min)": round(avg_cycle_time, 1) if avg_cycle_time > 0 else 0,
                    "Tonnes/Heure": round(tonnes_heure, 2),
                    "Performance Score": int(getattr(op, 'performance_score', 0))
                })
            
            if operator_perf:
                df_operators = pd.DataFrame(operator_perf)
                
                # Ajouter aussi les données de production depuis le StaffManager
                for idx, row in df_operators.iterrows():
                    op_staff = next((o for o in operateurs if o.matricule == row['Matricule']), None)
                    if op_staff:
                        # Utiliser la production totale de l'opérateur s'il n'a pas de machines assignées
                        if row['Nb Machines'] == 0 and hasattr(op_staff, 'production_tonnes'):
                            df_operators.loc[idx, 'Production Totale (T)'] = int(op_staff.production_tonnes)
                
                # Trier par production décroissante
                df_operators = df_operators.sort_values('Production Totale (T)', ascending=False)
                
                # Ajouter le classement
                df_operators.insert(0, 'Rang', range(1, len(df_operators) + 1))
                
                # Métriques globales opérateurs
                col_o1, col_o2, col_o3, col_o4 = st.columns(4)
                avg_op_tonnes_heure = df_operators['Tonnes/Heure'].mean()
                best_op = df_operators.iloc[0] if len(df_operators) > 0 else None
                total_op_prod = df_operators['Production Totale (T)'].sum()
                total_op_cycles = df_operators['Cycles Totaux'].sum()
                
                col_o1.metric("👥 Nombre Opérateurs", len(df_operators))
                col_o2.metric("🏆 Meilleur Opérateur", f"{best_op['Nom']}" if best_op is not None else "N/A", f"{best_op['Production Totale (T)']:,.0f} T" if best_op is not None else "")
                col_o3.metric("📊 Moyenne Tonnes/Heure", f"{avg_op_tonnes_heure:.2f} T/h")
                col_o4.metric("⚡ Cycles Totaux", f"{total_op_cycles:,}")
                
                st.markdown("---")
                
                # Tableau de performance des opérateurs
                operator_cols = ['Rang', 'Nom', 'Matricule', 'Équipe', 'Machines Assignées', 'Nb Machines',
                               'Cycles Totaux', 'Production Totale (T)', 'Heures Travaillées',
                               'Tps Cycle Moy (min)', 'Tonnes/Heure', 'Performance Score']
                
                st.dataframe(
                    df_operators[operator_cols].style.format({
                        "Production Totale (T)": "{:.0f} T",
                        "Heures Travaillées": "{:.1f} h",
                        "Tps Cycle Moy (min)": "{:.1f} min",
                        "Tonnes/Heure": "{:.2f} T/h",
                        "Cycles Totaux": "{:.0f}"
                    }),
                    width='stretch',
                    hide_index=True
                )
                
                # Graphique de classement des opérateurs
                try:
                    import plotly.express as px
                    fig_op = px.bar(
                        df_operators.head(10),  # Top 10
                        x='Nom',
                        y='Production Totale (T)',
                        title="Top 10 Opérateurs - Production Totale",
                        color='Tonnes/Heure',
                        color_continuous_scale='Blues',
                        labels={'Production Totale (T)': 'Production (T)', 'Nom': 'Opérateur'}
                    )
                    fig_op.update_layout(showlegend=False, height=400)
                    st.plotly_chart(fig_op, width='stretch')
                except:
                    st.info("Graphique disponible avec plotly")
            else:
                st.info("Aucune donnée de performance d'opérateur disponible.")
        else:
            st.info("Aucun opérateur trouvé ou aucune donnée de cycle disponible.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# --- CARBURANT (MULTI-DEVISE) ---
if "CARBURANT" in tab_dict:
    with tab_dict["CARBURANT"]:
        
        # 1. KPI GLOBAUX
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("⛽ GESTION CARBURANT & FOREX")
        
        c1, c2, c3 = st.columns(3)
        total_conso = int(df['Conso. Jour (L)'].sum())
        total_renta = int(df['Rentabilité ($)'].sum())
        
        c1.metric("CONSO. JOUR PARC", f"{total_conso} L", delta="Estimé")
        c2.metric("RENTABILITÉ NETTE", f"{total_renta} $", delta="En Dollar")
        
        # Affichage Taux Live
        with c3:
            st.markdown(f"""
            <div style="background:#222; color:#F5B800; padding:10px; border-radius:5px; text-align:center;">
                <b>TAUX DU JOUR (Source: API)</b><br>
                1 USD = {rates['CFA']:.0f} CFA<br>
                1 USD = {rates['EUR']:.2f} EUR
            </div>
            """, unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        # 2. TABLEAU DÉTAILLÉ
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 📋 TABLEAU DE BORD ÉNERGÉTIQUE")
        
        cols_fuel = [
            'ID', 'Type', 
            'Conso. Voyage (L)', 'Conso. Shift (L)', 'Conso. Jour (L)', 
            'Conso. Mois (L)', 
            'Rev. Jour ($)', 'Coût Fuel ($)', 'Rentabilité ($)'
        ]
        
        numeric_cols_to_format = ['Conso. Voyage (L)', 'Conso. Shift (L)', 'Conso. Jour (L)', 'Conso. Mois (L)', 'Rev. Jour ($)', 'Coût Fuel ($)', 'Rentabilité ($)']
        
        def color_rentabilite(val):
            color = '#2ecc71' if val > 0 else '#e74c3c'
            return f'color: {color}; font-weight: bold'

        st.dataframe(
            _styler_cell_map(df[cols_fuel].style, color_rentabilite, subset=['Rentabilité ($)'])
                               .format("{:.0f}", subset=numeric_cols_to_format), 
            width='stretch'
        )
        st.markdown('</div>', unsafe_allow_html=True)

        # 3. GRAPHIQUES & SAISIE MULTI-DEVISE
        c_g, c_d = st.columns([2, 1])
        with c_g:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📉 RENTABILITÉ vs CONSOMMATION")
            fig_renta = px.scatter(df, x="Conso. Jour (L)", y="Rentabilité ($)", 
                                   size="Production (T)", color="Type", hover_name="ID",
                                   color_discrete_sequence=['#F5B800', '#000', '#555'])
            st.plotly_chart(fig_renta, width='stretch')
            st.markdown('</div>', unsafe_allow_html=True)
        
        with c_d:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("➕ SAISIE PLEIN")
            
            with st.form("add_fuel"):
                m = st.selectbox("Engin", df['ID'])
                q = st.number_input("Quantité (Litres)", min_value=1)
                
                # SÉLECTEUR DE DEVISE
                col_dev, col_prix = st.columns([1, 2])
                with col_dev:
                    devise = st.selectbox("Devise", ["CFA", "EUR", "USD"])
                with col_prix:
                    p_input = st.number_input("Prix du Litre", value=600.0 if devise=="CFA" else 1.5)
                
                if st.form_submit_button("VALIDER"):
                    # CONVERSION AUTOMATIQUE EN USD
                    if devise == "CFA":
                        p_usd = p_input / rates['CFA']
                    elif devise == "EUR":
                        # Si 1 USD = 0.92 EUR, alors 1 EUR = 1/0.92 USD.
                        # Donc Prix_USD = Prix_EUR * (1/Rate_EUR) = Prix_EUR / Rate_EUR
                        p_usd = p_input / rates['EUR']
                    else:
                        p_usd = p_input

                    for mac in manager.machines:
                        if mac.id == m: 
                            mac.add_fuel(q, p_usd, devise, p_input)
                    
                    st.success(f"Plein ajouté ! (Conv: {p_usd:.2f} $/L)")
                    st.rerun()
                    
            st.markdown('</div>', unsafe_allow_html=True)

# --- MAINTENANCE ---
# --- MAINTENANCE (ONGLET 4 - EXPERT ATELIER) ---
if "MAINT." in tab_dict:
    with tab_dict["MAINT."]:
        
        # --- GESTION DE LA FLOTTE (BASE POUR RH ET ADMIN) ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("🚛 GESTION DE LA FLOTTE")
        st.markdown("""
        <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%); 
                    padding: 15px; border-radius: 10px; border: 2px solid #F5B800; margin-bottom: 20px;">
            <p style="color: #F5B800; font-size: 16px; font-weight: 700; margin: 0;">
                ℹ️ <strong>Base de données centrale de la flotte</strong> : Cette liste est utilisée par RH et Admin pour assigner les machines aux opérateurs.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        # Liste des types de machines (utilisée dans plusieurs onglets)
        machine_types_list = [
            "Dumper", "Excavatrice", "Chargeuse", "Bulldozer",
            "Tractopelle", "Grader", "Citerne Eau", "Citerne Gazoil", "Camion", "Benne"
        ]
        _MACHINE_TYPES_WITH_BUCKET = frozenset({"Excavatrice", "Chargeuse", "Tractopelle"})
        _MACHINE_TYPES_BLADE = frozenset({"Bulldozer"})
        
        # Créer des onglets pour la gestion de la flotte
        fleet_tabs = st.tabs(["📋 Liste de la Flotte", "➕ Ajouter une Machine", "✏️ Modifier une Machine", "🗑️ Supprimer une Machine"])
        
        # --- TAB 1: LISTE DE LA FLOTTE ---
        with fleet_tabs[0]:
            if manager.machines:
                # Créer un DataFrame personnalisé pour l'affichage de la flotte
                fleet_display_data = []
                for m in manager.machines:
                    # Trouver l'opérateur assigné
                    operator_name = "Non assigné"
                    for emp in staff_mgr.staff:
                        if hasattr(emp, 'assigned_machine') and emp.assigned_machine == m.id:
                            operator_name = emp.name
                            break
                    
                    fleet_display_data.append({
                        "ID": m.id,
                        "Modèle": m.model,
                        "Type": m.type,
                        "Capacité (T)": m.capacity,
                        "Godet (m³)": getattr(m, "bucket_capacity_m3", 0) or 0,
                        "Lame (m³)": getattr(m, "blade_capacity_m3", 0) or 0,
                        "Poids op. (t)": getattr(m, "operating_weight_t", 0) or 0,
                        "Heures Moteur": f"{m.engine_hours:,.0f} h",
                        "Statut": m.status,
                        "Opérateur": operator_name,
                        "Taux Horaire ($)": f"{m.hourly_rate:,.2f}"
                    })
                
                df_fleet_display = pd.DataFrame(fleet_display_data)
                st.dataframe(df_fleet_display, width='stretch', hide_index=True)
                
                # Statistiques
                st.markdown("---")
                st.markdown("#### 📊 Statistiques de la Flotte")
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("Total Machines", len(manager.machines))
                with col_stat2:
                    active_count = len([m for m in manager.machines if m.status == 'Active'])
                    st.metric("Machines Actives", active_count)
                with col_stat3:
                    pannes_count = len([m for m in manager.machines if m.status == 'Panne'])
                    st.metric("Machines en Panne", pannes_count)
                with col_stat4:
                    types_unique = len(set([m.type for m in manager.machines]))
                    st.metric("Types Différents", types_unique)
                
                # Répartition par type
                st.markdown("---")
                st.markdown("#### 📈 Répartition par Type de Machine")
                type_counts = df_fleet_display['Type'].value_counts()
                fig_types = px.bar(
                    x=type_counts.index,
                    y=type_counts.values,
                    labels={'x': 'Type de Machine', 'y': 'Nombre'},
                    color=type_counts.values,
                    color_continuous_scale='Viridis'
                )
                fig_types.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig_types, width='stretch')
            else:
                st.warning("⚠️ Aucune machine dans la flotte. Ajoutez des machines pour commencer.")
        
        # --- TAB 2: AJOUTER UNE MACHINE ---
        with fleet_tabs[1]:
            # Préréglage hors formulaire : on_change interdit à l'intérieur de st.form (Streamlit >= 1.33)
            _preset_opts_add = ["—"] + [
                f"{v:g} t" if float(v) == int(float(v)) else f"{v} t"
                for v in get_tonnage_preset_values()
            ]
            st.selectbox(
                "Préréglage capacité (tonnes) — s'applique au champ « Capacité » ci‑dessous",
                _preset_opts_add,
                key="add_mach_ton_preset",
                on_change=_apply_add_mach_ton_preset_cb,
                help="Choisissez un palier : la capacité (tonnes) du formulaire est mise à jour immédiatement.",
            )
            with st.form("add_machine_form"):
                st.markdown("#### ➕ Ajouter une Nouvelle Machine à la Flotte")
                use_model_catalog = st.toggle(
                    "Utiliser le catalogue constructeurs (marque + modèle)",
                    value=True,
                    help="Plusieurs centaines de références mondiales (mines & TP). Désactivez pour saisie libre uniquement.",
                )
                if CATALOG_NOTE and use_model_catalog:
                    st.caption(CATALOG_NOTE)
                
                col_id, col_model = st.columns(2)
                with col_id:
                    new_machine_id = st.text_input("ID Machine *", placeholder="Ex: DT-03, EX-03", help="Identifiant unique de la machine")
                with col_model:
                    if use_model_catalog:
                        cat_brand = st.selectbox("Marque *", get_brands_sorted(), key="add_mach_brand")
                        cat_models = get_models_for_brand(cat_brand)
                        if cat_brand == "Autre / saisie libre" or not cat_models:
                            cat_model = ""
                            cat_free = st.text_input(
                                "Modèle * (saisie libre)",
                                placeholder="Ex: 797F, PC4000, fabricant + type…",
                                key="add_mach_model_free",
                            )
                            if cat_brand != "Autre / saisie libre" and not cat_models:
                                st.caption(
                                    "Aucun modèle listé pour cette marque dans le catalogue — complétez à la main "
                                    "ou choisissez « Autre / saisie libre »."
                                )
                        else:
                            cat_model = st.selectbox(
                                "Modèle * (liste selon la marque)",
                                cat_models,
                                key="add_mach_model_sel",
                                help="Les références proposées changent lorsque vous modifiez la marque.",
                            )
                            cat_free = ""
                        new_machine_model = format_model_label(cat_brand, cat_model, cat_free)
                    else:
                        cat_brand = ""
                        cat_models = []
                        cat_model = ""
                        cat_free = ""
                        new_machine_model = st.text_input(
                            "Modèle *",
                            placeholder="Ex: 777E, PC2000",
                            help="Modèle de la machine",
                            key="add_mach_model_manual",
                        )
                
                col_type, col_capacity = st.columns(2)
                with col_type:
                    new_machine_type = st.selectbox("Type *", machine_types_list, help="Type de machine")
                with col_capacity:
                    _add_cap_last = "add_machine_capacity_last_src"
                    _add_cap_key = "add_machine_capacity_tons"
                    if _add_cap_key not in st.session_state:
                        st.session_state[_add_cap_key] = 0.0
                    ref_tons = None
                    if use_model_catalog:
                        msel = (cat_model or cat_free or "").strip()
                        ref_tons = get_reference_payload_tonnes(cat_brand, msel, cat_free)
                        _src = (cat_brand, msel, use_model_catalog)
                        if st.session_state.get(_add_cap_last) != _src:
                            st.session_state[_add_cap_last] = _src
                            if ref_tons is not None:
                                st.session_state[_add_cap_key] = float(ref_tons)
                    elif st.session_state.get(_add_cap_last) != ("manual_v1",):
                        st.session_state[_add_cap_last] = ("manual_v1",)
                    if new_machine_type in _MACHINE_TYPES_WITH_BUCKET:
                        cap_help = (
                            "Équivalent « charge par cycle » en tonnes si vous l'utilisez pour les calculs ; "
                            "sinon 0. Précisez surtout le **godet (m³)** ci‑dessous."
                        )
                    elif new_machine_type in _MACHINE_TYPES_BLADE:
                        cap_help = (
                            "Souvent **0** pour bulldozer (la **lame en m³** est saisie dans le bloc dédié). "
                            "Sinon charge utile si vous suivez un tonnage de production."
                        )
                    else:
                        cap_help = (
                            "Charge utile en tonnes (tombereaux, camions…). Préremplie si le catalogue connaît le modèle."
                        )
                    new_machine_capacity = st.number_input(
                        "Capacité (Tonnes)",
                        min_value=0.0,
                        step=0.1,
                        key=_add_cap_key,
                        help=cap_help,
                    )
                    if ref_tons is not None and new_machine_type not in _MACHINE_TYPES_WITH_BUCKET.union(_MACHINE_TYPES_BLADE):
                        st.caption(
                            f"Indicatif charge utile pour ce modèle : ≈ **{ref_tons:g} t** — à confirmer "
                            "(options, densité, réglementation)."
                        )
                
                new_bucket_m3 = 0.0
                new_blade_m3 = 0.0
                new_operating_weight_t = 0.0
                if new_machine_type in _MACHINE_TYPES_WITH_BUCKET:
                    st.markdown("##### 🪣 Godet & caractéristiques (pelle, chargeuse, tractopelle)")
                    _qb, _qw = st.columns(2)
                    with _qb:
                        new_bucket_m3 = st.number_input(
                            "Capacité godet (m³)",
                            min_value=0.0,
                            value=0.0,
                            step=0.01,
                            help="Volume godet (réf. constructeur : SAE / PCSA / tas — précisez votre norme en interne).",
                        )
                    with _qw:
                        new_operating_weight_t = st.number_input(
                            "Poids opérationnel (t)",
                            min_value=0.0,
                            value=0.0,
                            step=0.1,
                            help="Masse en service typique (fiche technique), optionnel.",
                        )
                    st.caption(
                        "Vous pouvez compléter avec un **équivalent tonnes** dans « Capacité (Tonnes) » si vos cycles sont calculés en tonnes."
                    )
                elif new_machine_type in _MACHINE_TYPES_BLADE:
                    st.markdown("##### ↧ Bulldozer — lame")
                    new_blade_m3 = st.number_input(
                        "Capacité / volume lame (m³, matériau ameublie)",
                        min_value=0.0,
                        value=0.0,
                        step=0.01,
                        help="Estimation du volume poussé par la lame (selon lame et matériau).",
                    )
                
                col_heures, col_taux = st.columns(2)
                with col_heures:
                    new_machine_hours = st.number_input("Heures Moteur Initiales", min_value=0.0, value=0.0, step=1.0, help="Heures moteur actuelles")
                with col_taux:
                    new_machine_rate = st.number_input("Taux Horaire ($)", min_value=0.0, value=100.0, step=1.0, help="Taux horaire en USD")
                
                if st.form_submit_button("✅ AJOUTER LA MACHINE", use_container_width=True):
                    if not new_machine_id or not new_machine_model or not new_machine_type:
                        st.warning("⚠️ Veuillez remplir tous les champs obligatoires (ID, Modèle, Type).")
                    else:
                        # Vérifier si l'ID existe déjà
                        existing_ids = [m.id for m in manager.machines]
                        if new_machine_id in existing_ids:
                            st.error(f"❌ L'ID '{new_machine_id}' existe déjà. Utilisez un autre ID.")
                        else:
                            # Créer la nouvelle machine
                            new_machine = Machine(
                                new_machine_id,
                                new_machine_model,
                                new_machine_type,
                                new_machine_capacity,
                                0,
                                new_machine_hours,
                            )
                            new_machine.hourly_rate = new_machine_rate
                            if new_machine_type in _MACHINE_TYPES_WITH_BUCKET:
                                new_machine.bucket_capacity_m3 = float(new_bucket_m3)
                                new_machine.operating_weight_t = float(new_operating_weight_t)
                                new_machine.blade_capacity_m3 = 0.0
                            elif new_machine_type in _MACHINE_TYPES_BLADE:
                                new_machine.blade_capacity_m3 = float(new_blade_m3)
                                new_machine.bucket_capacity_m3 = 0.0
                                new_machine.operating_weight_t = 0.0
                            else:
                                new_machine.bucket_capacity_m3 = 0.0
                                new_machine.blade_capacity_m3 = 0.0
                                new_machine.operating_weight_t = 0.0
                            new_machine.save_to_db()
                            
                            # Ajouter à la flotte
                            manager.machines.append(new_machine)
                            st.success(f"✅ Machine '{new_machine_id}' ({new_machine_model} - {new_machine_type}) ajoutée avec succès à la flotte !")
                            st.rerun()
        
        # --- TAB 3: MODIFIER UNE MACHINE ---
        with fleet_tabs[2]:
            if manager.machines:
                machine_ids_list = [m.id for m in manager.machines]
                selected_machine_to_edit = st.selectbox("Sélectionner la Machine à Modifier", machine_ids_list)
                
                machine_to_edit = next((m for m in manager.machines if m.id == selected_machine_to_edit), None)
                
                if machine_to_edit:
                    _edit_fleet_sid = "edit_fleet_selected_machine_id"
                    if st.session_state.get(_edit_fleet_sid) != machine_to_edit.id:
                        st.session_state[_edit_fleet_sid] = machine_to_edit.id
                        st.session_state["edit_machine_capacity_tons"] = float(machine_to_edit.capacity)
                        st.session_state["edit_machine_capacity_last_src"] = None
                    _preset_opts_edit = ["—"] + [
                        f"{v:g} t" if float(v) == int(float(v)) else f"{v} t"
                        for v in get_tonnage_preset_values()
                    ]
                    st.selectbox(
                        "Préréglage capacité (tonnes) — s'applique au champ « Capacité » du formulaire d'édition",
                        _preset_opts_edit,
                        key="edit_mach_ton_preset",
                        on_change=_apply_edit_mach_ton_preset_cb,
                        help="Palier courant ; mise à jour immédiate (le callback ne peut pas être dans le formulaire).",
                    )
                    with st.form("edit_machine_form"):
                        st.markdown(f"#### ✏️ Modifier la Machine : {machine_to_edit.id}")
                        use_cat_edit = st.toggle(
                            "Catalogue constructeurs pour le modèle",
                            value=False,
                            key="edit_mach_use_cat",
                        )
                        if CATALOG_NOTE and use_cat_edit:
                            st.caption(CATALOG_NOTE)
                        
                        col_id2, col_model2 = st.columns(2)
                        with col_id2:
                            edited_machine_id = st.text_input("ID Machine *", value=machine_to_edit.id, disabled=True, help="L'ID ne peut pas être modifié")
                        with col_model2:
                            eb, e_models, em, ef = "", [], "", ""
                            if use_cat_edit:
                                eb = st.selectbox("Marque *", get_brands_sorted(), key="edit_mach_brand")
                                e_models = get_models_for_brand(eb)
                                if eb == "Autre / saisie libre" or not e_models:
                                    em = ""
                                    ef = st.text_input(
                                        "Modèle * (libre)",
                                        value=machine_to_edit.model,
                                        key="edit_mach_model_free",
                                    )
                                    if eb != "Autre / saisie libre" and not e_models:
                                        st.caption(
                                            "Aucun modèle listé pour cette marque — saisie libre ou « Autre / saisie libre »."
                                        )
                                else:
                                    em = st.selectbox(
                                        "Modèle * (liste selon la marque)",
                                        e_models,
                                        key="edit_mach_model_sel",
                                        help="Les références proposées changent lorsque vous modifiez la marque.",
                                    )
                                    ef = ""
                                edited_machine_model = format_model_label(eb, em, ef)
                            else:
                                edited_machine_model = st.text_input(
                                    "Modèle *", value=machine_to_edit.model, key="edit_mach_model_manual"
                                )
                        
                        col_type2, col_capacity2 = st.columns(2)
                        with col_type2:
                            current_type_index = machine_types_list.index(machine_to_edit.type) if machine_to_edit.type in machine_types_list else 0
                            edited_machine_type = st.selectbox("Type *", machine_types_list, index=current_type_index)
                        with col_capacity2:
                            _ecl = "edit_machine_capacity_last_src"
                            _eck = "edit_machine_capacity_tons"
                            ref_et = None
                            if use_cat_edit:
                                emsel = (em or ef or "").strip()
                                ref_et = get_reference_payload_tonnes(eb, emsel, ef)
                                _esrc = (eb, emsel, use_cat_edit, machine_to_edit.id)
                                if st.session_state.get(_ecl) != _esrc:
                                    st.session_state[_ecl] = _esrc
                                    if ref_et is not None:
                                        st.session_state[_eck] = float(ref_et)
                            elif st.session_state.get(_ecl) != ("edit_manual_v1", machine_to_edit.id):
                                st.session_state[_ecl] = ("edit_manual_v1", machine_to_edit.id)
                            if _eck not in st.session_state:
                                st.session_state[_eck] = float(machine_to_edit.capacity)
                            if edited_machine_type in _MACHINE_TYPES_WITH_BUCKET:
                                _ec_help = (
                                    "Équivalent tonnes par cycle si utilisé dans les calculs ; sinon 0. "
                                    "Voir aussi le **godet (m³)** ci‑dessous."
                                )
                            elif edited_machine_type in _MACHINE_TYPES_BLADE:
                                _ec_help = "Souvent 0 ; la **lame (m³)** est dans le bloc dédié."
                            else:
                                _ec_help = (
                                    "Charge utile en tonnes. Préremplie si le catalogue connaît le modèle ; "
                                    "modifiable. Préréglages à droite."
                                )
                            edited_machine_capacity = st.number_input(
                                "Capacité (Tonnes)",
                                min_value=0.0,
                                step=0.1,
                                key=_eck,
                                help=_ec_help,
                            )
                            if ref_et is not None and edited_machine_type not in _MACHINE_TYPES_WITH_BUCKET.union(
                                _MACHINE_TYPES_BLADE
                            ):
                                st.caption(
                                    f"Indicatif charge utile : ≈ **{ref_et:g} t** — à confirmer selon votre contexte."
                                )
                        
                        edit_bucket_m3 = float(getattr(machine_to_edit, "bucket_capacity_m3", 0) or 0)
                        edit_blade_m3 = float(getattr(machine_to_edit, "blade_capacity_m3", 0) or 0)
                        edit_operating_weight_t = float(getattr(machine_to_edit, "operating_weight_t", 0) or 0)
                        if edited_machine_type in _MACHINE_TYPES_WITH_BUCKET:
                            st.markdown("##### 🪣 Godet & caractéristiques (pelle, chargeuse, tractopelle)")
                            _eb1, _eb2 = st.columns(2)
                            with _eb1:
                                edit_bucket_m3 = st.number_input(
                                    "Capacité godet (m³)",
                                    min_value=0.0,
                                    value=edit_bucket_m3,
                                    step=0.01,
                                    help="Volume godet (réf. constructeur).",
                                )
                            with _eb2:
                                edit_operating_weight_t = st.number_input(
                                    "Poids opérationnel (t)",
                                    min_value=0.0,
                                    value=edit_operating_weight_t,
                                    step=0.1,
                                )
                        elif edited_machine_type in _MACHINE_TYPES_BLADE:
                            st.markdown("##### ↧ Bulldozer — lame")
                            edit_blade_m3 = st.number_input(
                                "Capacité / volume lame (m³, matériau ameublie)",
                                min_value=0.0,
                                value=edit_blade_m3,
                                step=0.01,
                            )
                        
                        col_heures2, col_taux2 = st.columns(2)
                        with col_heures2:
                            edited_machine_hours = st.number_input("Heures Moteur", min_value=0.0, value=float(machine_to_edit.engine_hours), step=1.0)
                        with col_taux2:
                            edited_machine_rate = st.number_input("Taux Horaire ($)", min_value=0.0, value=float(machine_to_edit.hourly_rate), step=1.0)
                        
                        col_status, col_prod = st.columns(2)
                        with col_status:
                            status_options = ["Active", "Panne", "En maintenance"]
                            current_status_index = status_options.index(machine_to_edit.status) if machine_to_edit.status in status_options else 0
                            edited_machine_status = st.selectbox("Statut", status_options, index=current_status_index)
                        with col_prod:
                            edited_machine_production = st.number_input("Production Initiale (T)", min_value=0.0, value=float(machine_to_edit.production_tonnes), step=0.1)
                        
                        # Le bouton doit toujours être présent dans le formulaire
                        submitted = st.form_submit_button("✅ ENREGISTRER LES MODIFICATIONS", use_container_width=True)
                        
                        if submitted:
                            # Mettre à jour la machine
                            machine_to_edit.model = edited_machine_model
                            machine_to_edit.type = edited_machine_type
                            machine_to_edit.capacity = edited_machine_capacity
                            machine_to_edit.engine_hours = edited_machine_hours
                            machine_to_edit.hourly_rate = edited_machine_rate
                            machine_to_edit.status = edited_machine_status
                            machine_to_edit.production_tonnes = edited_machine_production
                            if edited_machine_type in _MACHINE_TYPES_WITH_BUCKET:
                                machine_to_edit.bucket_capacity_m3 = float(edit_bucket_m3)
                                machine_to_edit.operating_weight_t = float(edit_operating_weight_t)
                                machine_to_edit.blade_capacity_m3 = 0.0
                            elif edited_machine_type in _MACHINE_TYPES_BLADE:
                                machine_to_edit.blade_capacity_m3 = float(edit_blade_m3)
                                machine_to_edit.bucket_capacity_m3 = 0.0
                                machine_to_edit.operating_weight_t = 0.0
                            else:
                                machine_to_edit.bucket_capacity_m3 = 0.0
                                machine_to_edit.blade_capacity_m3 = 0.0
                                machine_to_edit.operating_weight_t = 0.0
                            machine_to_edit.save_to_db()
                            
                            st.success(f"✅ Machine '{machine_to_edit.id}' modifiée avec succès !")
                            st.rerun()
                else:
                    st.info("⚠️ Machine non trouvée.")
            else:
                st.info("Aucune machine dans la flotte. Ajoutez d'abord des machines.")
        
        # --- TAB 4: SUPPRIMER UNE MACHINE ---
        with fleet_tabs[3]:
            if manager.machines:
                st.warning("⚠️ **ATTENTION** : La suppression d'une machine est irréversible et affectera toutes les données associées (maintenance, assignations, etc.).")
                
                machine_ids_list_del = [m.id for m in manager.machines]
                selected_machine_to_delete = st.selectbox("Sélectionner la Machine à Supprimer", machine_ids_list_del)
                
                machine_to_delete = next((m for m in manager.machines if m.id == selected_machine_to_delete), None)
                
                if machine_to_delete:
                    st.markdown(f"### 🗑️ Supprimer la Machine : {machine_to_delete.id}")
                    
                    # Afficher les informations de la machine
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        st.info(f"""
                        **ID :** {machine_to_delete.id}
                        **Modèle :** {machine_to_delete.model}
                        **Type :** {machine_to_delete.type}
                        """)
                    with col_info2:
                        _bd = getattr(machine_to_delete, "bucket_capacity_m3", 0) or 0
                        _bl = getattr(machine_to_delete, "blade_capacity_m3", 0) or 0
                        _ow = getattr(machine_to_delete, "operating_weight_t", 0) or 0
                        _extra = ""
                        if _bd:
                            _extra += f"\n**Godet :** {_bd} m³"
                        if _bl:
                            _extra += f"\n**Lame :** {_bl} m³"
                        if _ow:
                            _extra += f"\n**Poids op. :** {_ow} t"
                        st.info(f"""
                        **Capacité :** {machine_to_delete.capacity} T{_extra}
                        **Heures Moteur :** {machine_to_delete.engine_hours:,} h
                        **Statut :** {machine_to_delete.status}
                        """)
                    
                    # Vérifier si la machine est assignée à un opérateur
                    assigned_to = None
                    for emp in staff_mgr.staff:
                        if hasattr(emp, 'assigned_machine') and emp.assigned_machine == machine_to_delete.id:
                            assigned_to = emp.name
                            break
                    
                    if assigned_to:
                        st.error(f"⚠️ Cette machine est actuellement assignée à **{assigned_to}**. Retirez d'abord l'assignation dans RH.")
                    
                    # Confirmation
                    confirm_delete = st.checkbox("✅ Je confirme vouloir supprimer cette machine", key="confirm_delete_machine")
                    
                    if confirm_delete and not assigned_to:
                        if st.button("🗑️ SUPPRIMER DÉFINITIVEMENT", use_container_width=True, type="primary"):
                            # Retirer toutes les assignations
                            for emp in staff_mgr.staff:
                                if hasattr(emp, 'assigned_machine') and emp.assigned_machine == machine_to_delete.id:
                                    emp.assigned_machine = "Aucune"
                            
                            # Supprimer la machine
                            manager.remove_machine(machine_to_delete.id)
                            st.success(f"✅ Machine '{machine_to_delete.id}' supprimée avec succès !")
                            st.rerun()
                    elif confirm_delete and assigned_to:
                        st.warning("⚠️ Veuillez d'abord retirer l'assignation de cette machine dans RH.")
            else:
                st.info("Aucune machine dans la flotte.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- 0. ALERTES DE MAINTENANCE PLANIFIÉES (VISIBLE PAR TOUS) ---
        active_alerts = manager.maintenance_manager.get_all_active_alerts()
        if active_alerts:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🔔 ALERTES DE MAINTENANCE PLANIFIÉES")
            st.info(f"📢 **{len(active_alerts)} maintenance(s) planifiée(s) - Visible par tous les utilisateurs**")
            
            # Grouper les alertes par date
            today = date.today()
            alerts_by_date = {}
            for alert in active_alerts:
                days_until = (alert.planned_date - today).days
                if days_until not in alerts_by_date:
                    alerts_by_date[days_until] = []
                alerts_by_date[days_until].append(alert)
            
            # Afficher les alertes par date (trier par proximité)
            for days_until in sorted(alerts_by_date.keys()):
                alerts_group = alerts_by_date[days_until]
                if days_until < 0:
                    st.error(f"⚠️ **EN RETARD ({abs(days_until)} jour(s)):**")
                elif days_until == 0:
                    st.warning(f"🔴 **AUJOURD'HUI:**")
                elif days_until <= 7:
                    st.warning(f"🟡 **DANS {days_until} JOUR(S):**")
                else:
                    st.info(f"🔵 **DANS {days_until} JOUR(S):**")
                
                for alert in alerts_group:
                    machine = next((m for m in manager.machines if m.id == alert.machine_id), None)
                    machine_type = machine.type if machine else "N/A"
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        st.write(f"🔧 **{alert.machine_id}** ({machine_type})")
                    with col2:
                        st.write(f"📅 **Date:** {alert.planned_date.strftime('%d/%m/%Y')} | **Type:** {alert.maintenance_type}")
                    with col3:
                        st.write(f"👤 Créée par: {alert.created_by}")
                st.markdown("---")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- 1. KPI DISPONIBILITÉ & SANTÉ ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("🔧 SANTÉ DU PARC")
        
        # Calculs
        nb_total = len(df)
        nb_pannes = len(df[df['Statut']=='Panne'])
        nb_actives = len(df[df['Statut']=='Active'])
        # Disponibilité mécanique (Formule simplifiée instantanée)
        dispo_pct = round((nb_actives / nb_total) * 100, 1) if nb_total > 0 else 0
        
        # Compter les PM en retard (celles qui ont "DUE" dans la colonne Prochaine PM)
        pm_retard = len(df[df['Prochaine PM'].str.contains("DUE")])

        # Compter les alertes actives
        nb_alertes = len(active_alerts)
        
        k1, k2, k3, k4, k5 = st.columns(5)
        k1.metric("DISPONIBILITÉ", f"{dispo_pct} %", delta="Cible: 90%")
        k2.metric("MACHINES À L'ARRÊT", f"{nb_pannes}", delta_color="inverse")
        k3.metric("PM EN RETARD", f"{pm_retard}", delta_color="inverse")
        k4.metric("MAINT. PLANIFIÉES", f"{nb_alertes}", delta="Alertes actives")
        k5.metric("ORDRES OUVERTS", f"{nb_pannes + pm_retard}", delta="Travaux en cours")
        st.markdown('</div>', unsafe_allow_html=True)

        # --- 2. GESTION DES PANNES (PRIORITÉ ABSOLUE) ---
        # On n'affiche ce bloc que s'il y a des pannes
        pannes_actives = [m for m in manager.machines if m.status == "Panne"]
        
        if pannes_actives:
            st.error(f"🚨 IL Y A {len(pannes_actives)} MACHINE(S) EN PANNE ACTUELLEMENT")
            
            cols_panne = st.columns(len(pannes_actives)) if len(pannes_actives) < 4 else st.columns(3)
            
            for i, machine in enumerate(pannes_actives):
                col = cols_panne[i % 3]
                with col:
                    with st.container():
                        st.markdown(f"""
                        <div style="background-color:#ffebee; border:2px solid #e53935; border-radius:10px; padding:15px; margin-bottom:10px;">
                            <h3 style="color:#c62828; margin:0;">{machine.id}</h3>
                            <p style="font-weight:bold;">Cause: {machine.breakdown_reason}</p>
                            <p>Arrêt: {machine.breakdown_time}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        # Formulaire pour terminer la réparation avec pièces changées
                        with st.expander(f"Terminer réparation {machine.id}", expanded=False):
                            # Initialiser session_state pour cette machine
                            repair_key = f"repair_pieces_{machine.id}"
                            if repair_key not in st.session_state:
                                st.session_state[repair_key] = []
                            
                            # ÉTAPE 1: SÉLECTION DES PIÈCES
                            st.markdown("**📦 ÉTAPE 1: Sélectionner les pièces changées**")
                            with st.form(f"select_parts_rep_form_{machine.id}"):
                                st.markdown("**Pièces depuis le catalogue:**")
                                
                                # Sélection par catégorie
                                catalog_rep = manager.maintenance_manager.parts_catalog
                                categories_rep = catalog_rep.get_categories()
                                selected_category_rep = st.selectbox(
                                    "Filtrer par catégorie (optionnel)",
                                    ["Toutes les catégories"] + categories_rep,
                                    key=f"cat_filter_rep_{machine.id}"
                                )
                                
                                # Obtenir les pièces selon la catégorie sélectionnée
                                if selected_category_rep == "Toutes les catégories":
                                    available_parts_rep = catalog_rep.get_parts_by_category()
                                else:
                                    available_parts_rep = catalog_rep.get_parts_by_category(selected_category_rep)
                                
                                # Créer une liste de sélection avec nom et prix
                                parts_options_rep = {f"{p['nom']} ({p['cout']:.2f} $)": p for p in available_parts_rep}
                                
                                # Multiselect pour choisir les pièces
                                selected_parts_labels_rep = st.multiselect(
                                    "Choisir les pièces changées",
                                    list(parts_options_rep.keys()),
                                    key=f"selected_parts_rep_{machine.id}"
                                )
                                
                                # Afficher les quantités pour les pièces sélectionnées
                                pieces_temp = []
                                if selected_parts_labels_rep:
                                    st.markdown("**Entrer les quantités:**")
                                    for part_label in selected_parts_labels_rep:
                                        part = parts_options_rep[part_label]
                                        col_q1, col_q2 = st.columns([3, 1])
                                        with col_q1:
                                            st.write(f"  • {part['nom']} ({part['cout']:.2f} $)")
                                        with col_q2:
                                            qte = st.number_input(
                                                "Qté",
                                                min_value=1,
                                                value=1,
                                                key=f"qte_{part['nom']}_rep_{machine.id}"
                                            )
                                        pieces_temp.append({
                                            "nom": part['nom'],
                                            "quantite": int(qte),
                                            "cout": float(part['cout'])
                                        })
                                
                                # Option pour ajouter des pièces personnalisées
                                st.markdown("---")
                                st.markdown("**Pièces personnalisées:**")
                                num_custom_pieces_rep = st.number_input(
                                    "Nombre de pièces personnalisées",
                                    min_value=0,
                                    max_value=10,
                                    value=0,
                                    key=f"num_custom_rep_{machine.id}"
                                )
                                
                                if num_custom_pieces_rep > 0:
                                    for i in range(num_custom_pieces_rep):
                                        col_c1, col_c2, col_c3 = st.columns([3, 1, 1])
                                        with col_c1:
                                            nom_custom = st.text_input(f"Nom pièce {i+1}", key=f"custom_nom_rep_{machine.id}_{i}")
                                        with col_c2:
                                            qte_custom = st.number_input(f"Qté", min_value=1, value=1, key=f"custom_qte_rep_{machine.id}_{i}")
                                        with col_c3:
                                            cout_custom = st.number_input(f"Coût ($)", min_value=0.0, value=0.0, step=0.01, key=f"custom_cout_rep_{machine.id}_{i}")
                                        
                                        if nom_custom:
                                            pieces_temp.append({
                                                "nom": nom_custom,
                                                "quantite": int(qte_custom),
                                                "cout": float(cout_custom)
                                            })
                                
                                # Bouton pour valider la sélection des pièces
                                if st.form_submit_button("✅ VALIDER LA SÉLECTION DES PIÈCES", use_container_width=True):
                                    st.session_state[repair_key] = pieces_temp
                                    st.success(f"✅ {len(pieces_temp)} pièce(s) sélectionnée(s) et validée(s) !")
                                    st.rerun()
                            
                            # ÉTAPE 2: RÉSUMÉ ET VALIDATION FINALE
                            if st.session_state[repair_key]:
                                st.markdown("---")
                                st.markdown("**✅ ÉTAPE 2: Confirmer la fin de réparation**")
                                
                                # Afficher le résumé des pièces validées
                                st.markdown("**📋 Résumé des pièces validées:**")
                                total_cost_rep = 0
                                for piece in st.session_state[repair_key]:
                                    cost = piece["cout"] * piece["quantite"]
                                    total_cost_rep += cost
                                    st.write(f"  • {piece['nom']}: {piece['quantite']} × {piece['cout']:,.2f} $ = {cost:,.2f} $")
                                
                                st.info(f"💰 **Coût total des pièces: {total_cost_rep:,.2f} $**")
                                
                                # Formulaire final pour valider la réparation
                                with st.form(f"final_repair_form_{machine.id}"):
                                    # Récupérer la liste des mécaniciens et superviseurs mécaniques depuis RH
                                    mechanics_list_rep = [
                                        emp for emp in staff_mgr.staff 
                                        if emp.role in ["Mecanicien", "Superviseur Mecanicien"]
                                    ]
                                    
                                    if mechanics_list_rep:
                                        # Créer une liste avec nom, matricule et rôle pour l'affichage
                                        mechanics_options_rep = {
                                            f"{emp.name} ({emp.matricule}) - {emp.role}": emp.name
                                            for emp in sorted(mechanics_list_rep, key=lambda e: e.name)
                                        }
                                        
                                        mechanic_name = st.selectbox(
                                            "Mécanicien/Superviseur *",
                                            [""] + list(mechanics_options_rep.keys()),
                                            key=f"mech_{machine.id}_final",
                                            help="Sélectionner depuis la liste des employés (rôles: Mécanicien, Superviseur Mécanicien) de l'onglet RH"
                                        )
                                        if mechanic_name and mechanic_name != "":
                                            mechanic_name = mechanics_options_rep[mechanic_name]
                                        else:
                                            mechanic_name = None
                                    else:
                                        st.warning("⚠️ Aucun mécanicien ou superviseur mécanique trouvé dans la liste RH. Ajoutez-en dans l'onglet RH.")
                                        mechanic_name = st.text_input("Nom du Mécanicien *", placeholder="Ex: Jean KOUANGA", key=f"mech_{machine.id}_final_fallback")
                                    
                                    notes = st.text_area("Notes/Observations", key=f"notes_{machine.id}_final", height=60)
                                    
                                    if st.form_submit_button(f"✅ TERMINER RÉPARATION ({machine.id})", use_container_width=True):
                                        if mechanic_name:
                                            manager.repair_machine(machine.id, mechanic_name, st.session_state[repair_key] if st.session_state[repair_key] else None, notes)
                                            st.success(f"{machine.id} est de retour en production !")
                                            # Réinitialiser les pièces validées
                                            st.session_state[repair_key] = []
                                            time.sleep(1)
                                            st.rerun()
                                        else:
                                            st.warning("⚠️ Veuillez sélectionner un mécanicien ou superviseur mécanique.")
                                
                                # Bouton pour annuler et recommencer
                                if st.button(f"❌ Annuler et recommencer", key=f"cancel_rep_{machine.id}", use_container_width=True):
                                    st.session_state[repair_key] = []
                                    st.rerun()

        # --- 3. VUE DÉTAILLÉE & PLANIFICATION ---
        c_suivi, c_action = st.columns([2, 1])

        # COLONNE GAUCHE : TABLEAU DE SUIVI
        with c_suivi:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📋 SUIVI PRÉVENTIF (H-MÈTRE & DATES)")
            
            # Fonction de style pour le tableau
            def highlight_status(val):
                if 'Panne' in str(val): return 'background-color: #ffcccc; color: red; font-weight: bold'
                if 'Active' in str(val): return 'background-color: #ccffcc; color: green'
                return ''
            
            def highlight_pm(val):
                if 'DUE' in str(val): return 'color: red; font-weight: bold; text-decoration: underline'
                if 'OK' in str(val): return 'color: green'
                return ''

            # Sélection des colonnes utiles pour la maintenance
            cols_maint = ['ID', 'Type', 'Statut', 'H. Total', 'Prochaine PM', 'Maint. Date']
            
            st.dataframe(
                df[cols_maint].style
                .pipe(_styler_cell_map, highlight_status, subset=['Statut'])
                .pipe(_styler_cell_map, highlight_pm, subset=['Prochaine PM']),
                width='stretch',
                height=400
            )
            st.markdown('</div>', unsafe_allow_html=True)

        # COLONNE DROITE : ACTIONS ATELIER
        with c_action:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🛠️ ATELIER EXPRESS")
            
            # A. VALIDATION PM
            st.markdown("#### 1. VALIDER UNE PM")
            
            # Initialiser session_state pour stocker les pièces validées
            if 'pm_pieces_validated' not in st.session_state:
                st.session_state.pm_pieces_validated = []
            
            # ÉTAPE 1: SÉLECTION DES PIÈCES
            st.markdown("**📦 ÉTAPE 1: Sélectionner les pièces changées**")
            with st.form("select_parts_pm_form"):
                mac_pm = st.selectbox("Engin sortant de maintenance", [m.id for m in manager.machines], key="mac_pm_select")
                type_pm = st.selectbox("Type d'intervention", ["PM 250h", "PM 500h", "PM 1000h", "Changement Pneus", "Autre"], key="type_pm_select")
                
                st.markdown("---")
                st.markdown("**Pièces depuis le catalogue:**")
                
                # Sélection par catégorie
                catalog = manager.maintenance_manager.parts_catalog
                categories = catalog.get_categories()
                selected_category = st.selectbox("Filtrer par catégorie (optionnel)", ["Toutes les catégories"] + categories, key="cat_filter_pm")
                
                # Obtenir les pièces selon la catégorie sélectionnée
                if selected_category == "Toutes les catégories":
                    available_parts = catalog.get_parts_by_category()
                else:
                    available_parts = catalog.get_parts_by_category(selected_category)
                
                # Créer une liste de sélection avec nom et prix
                parts_options = {f"{p['nom']} ({p['cout']:.2f} $)": p for p in available_parts}
                
                # Multiselect pour choisir les pièces
                selected_parts_labels = st.multiselect(
                    "Choisir les pièces changées",
                    list(parts_options.keys()),
                    key="selected_parts_pm"
                )
                
                # Afficher les quantités pour les pièces sélectionnées
                pieces_temp = []
                if selected_parts_labels:
                    st.markdown("**Entrer les quantités:**")
                    for part_label in selected_parts_labels:
                        part = parts_options[part_label]
                        col_q1, col_q2 = st.columns([3, 1])
                        with col_q1:
                            st.write(f"  • {part['nom']} ({part['cout']:.2f} $)")
                        with col_q2:
                            qte = st.number_input(
                                "Qté",
                                min_value=1,
                                value=1,
                                key=f"qte_{part['nom']}_pm"
                            )
                        pieces_temp.append({
                            "nom": part['nom'],
                            "quantite": int(qte),
                            "cout": float(part['cout'])
                        })
                
                # Option pour ajouter des pièces personnalisées
                st.markdown("---")
                st.markdown("**Pièces personnalisées:**")
                num_custom_pieces = st.number_input("Nombre de pièces personnalisées", min_value=0, max_value=10, value=0, key="num_custom_pm")
                
                if num_custom_pieces > 0:
                    for i in range(num_custom_pieces):
                        col_c1, col_c2, col_c3 = st.columns([3, 1, 1])
                        with col_c1:
                            nom_custom = st.text_input(f"Nom pièce {i+1}", key=f"custom_nom_pm_{i}")
                        with col_c2:
                            qte_custom = st.number_input(f"Qté", min_value=1, value=1, key=f"custom_qte_pm_{i}")
                        with col_c3:
                            cout_custom = st.number_input(f"Coût ($)", min_value=0.0, value=0.0, step=0.01, key=f"custom_cout_pm_{i}")
                        
                        if nom_custom:
                            pieces_temp.append({
                                "nom": nom_custom,
                                "quantite": int(qte_custom),
                                "cout": float(cout_custom)
                            })
                
                # Bouton pour valider la sélection des pièces
                if st.form_submit_button("✅ VALIDER LA SÉLECTION DES PIÈCES", use_container_width=True):
                    st.session_state.pm_pieces_validated = pieces_temp
                    st.session_state.pm_machine = mac_pm
                    st.session_state.pm_type = type_pm
                    st.success(f"✅ {len(pieces_temp)} pièce(s) sélectionnée(s) et validée(s) !")
                    st.rerun()
            
            # ÉTAPE 2: RÉSUMÉ ET VALIDATION FINALE
            if st.session_state.pm_pieces_validated:
                st.markdown("---")
                st.markdown("**✅ ÉTAPE 2: Confirmer la sortie de l'engin**")
                
                # Afficher le résumé des pièces validées
                st.markdown("**📋 Résumé des pièces validées:**")
                total_cost_pm = 0
                for piece in st.session_state.pm_pieces_validated:
                    cost = piece["cout"] * piece["quantite"]
                    total_cost_pm += cost
                    st.write(f"  • {piece['nom']}: {piece['quantite']} × {piece['cout']:,.2f} $ = {cost:,.2f} $")
                
                st.info(f"💰 **Coût total des pièces: {total_cost_pm:,.2f} $**")
                
                # Formulaire final pour valider la sortie
                with st.form("final_validate_pm_form"):
                    # Récupérer la liste des mécaniciens et superviseurs mécaniques depuis RH
                    mechanics_list = [
                        emp for emp in staff_mgr.staff 
                        if emp.role in ["Mecanicien", "Superviseur Mecanicien"]
                    ]
                    
                    if mechanics_list:
                        # Créer une liste avec nom, matricule et rôle pour l'affichage
                        mechanics_options = {
                            f"{emp.name} ({emp.matricule}) - {emp.role}": emp.name
                            for emp in sorted(mechanics_list, key=lambda e: e.name)
                        }
                        
                        mechanic_name_pm = st.selectbox(
                            "Mécanicien/Superviseur *",
                            [""] + list(mechanics_options.keys()),
                            key="mech_name_pm_final",
                            help="Sélectionner depuis la liste des employés de l'onglet RH (rôles: Mécanicien, Superviseur Mécanicien)"
                        )
                        if mechanic_name_pm and mechanic_name_pm != "":
                            mechanic_name_pm = mechanics_options[mechanic_name_pm]
                        else:
                            mechanic_name_pm = None
                    else:
                        st.warning("⚠️ Aucun mécanicien ou superviseur mécanique trouvé dans la liste RH. Ajoutez-en dans l'onglet RH.")
                        mechanic_name_pm = st.text_input("Nom du Mécanicien *", placeholder="Ex: Jean KOUANGA", key="mech_name_pm_final_fallback")
                    
                    notes_pm = st.text_area("Notes/Observations", key="notes_pm_final", height=60)
                    
                    col_info1, col_info2 = st.columns(2)
                    with col_info1:
                        st.write(f"**Engin:** {st.session_state.pm_machine}")
                    with col_info2:
                        st.write(f"**Type:** {st.session_state.pm_type}")
                    
                    if st.form_submit_button("✅ CONFIRMER LA SORTIE DE L'ENGIN", use_container_width=True):
                        if mechanic_name_pm:
                            manager.do_maintenance_pm(
                                st.session_state.pm_machine,
                                st.session_state.pm_type,
                                mechanic_name_pm,
                                st.session_state.pm_pieces_validated if st.session_state.pm_pieces_validated else None,
                                notes_pm
                            )
                            msg = f"{st.session_state.pm_type} effectuée sur {st.session_state.pm_machine}. H-Mètre de référence mis à jour."
                            if total_cost_pm > 0:
                                msg += f" Coût total pièces: {total_cost_pm:,.2f} $"
                            st.success(msg)
                            # Réinitialiser les pièces validées
                            st.session_state.pm_pieces_validated = []
                            st.session_state.pm_machine = None
                            st.session_state.pm_type = None
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("⚠️ Veuillez sélectionner un mécanicien ou superviseur mécanique.")
                
                # Bouton pour annuler et recommencer
                if st.button("❌ Annuler et recommencer", use_container_width=True):
                    st.session_state.pm_pieces_validated = []
                    st.session_state.pm_machine = None
                    st.session_state.pm_type = None
                    st.rerun()
            
            st.divider()
            
            # B. MISE A JOUR H-METRE MANUELLE
            st.markdown("#### 2. CORRECTION H-MÈTRE")
            with st.expander("Saisie manuelle index"):
                with st.form("update_h_form"):
                    mac_up = st.selectbox("Engin", [m.id for m in manager.machines], key="sel_up")
                    new_h = st.number_input("Nouvel Index", min_value=0)
                    if st.form_submit_button("Mettre à jour"):
                        for m in manager.machines:
                            if m.id == mac_up: m.update_hours(new_h)
                        st.rerun()

            st.divider()

            # C. PROGRAMMATION DATE
            st.markdown("#### 3. PLANIFIER MAINTENANCE")
            with st.form("prog_form"):
                mac_date = st.selectbox("Engin", [m.id for m in manager.machines], key="sel_date")
                new_date = st.date_input("Date prévue")
                maintenance_type_plan = st.selectbox("Type de maintenance", ["PM 250h", "PM 500h", "PM 1000h", "Changement Pneus", "Révision générale", "Autre"])
                created_by_plan = st.text_input("Planifié par", value=st.session_state.username if 'username' in st.session_state else "", key="created_by_plan")
                
                if st.form_submit_button("📅 PROGRAMMER (CRÉE ALERTE POUR TOUS)", use_container_width=True):
                    if manager.set_maintenance_date(mac_date, new_date, maintenance_type_plan, created_by_plan):
                        st.success(f"✅ Maintenance planifiée le {new_date.strftime('%d/%m/%Y')} pour {mac_date}. Alerte créée pour tous les utilisateurs !")
                        st.info("🔔 Tous les utilisateurs verront cette alerte dans la section Maintenance.")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de la planification.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- 4. HISTORIQUE DES MAINTENANCES ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("📜 HISTORIQUE DES MAINTENANCES")
        
        if manager.maintenance_manager.maintenance_records:
            # Afficher l'historique par machine
            machine_options_hist = ["Toutes les machines"] + [m.id for m in manager.machines]
            selected_machine_hist = st.selectbox("Filtrer par machine", machine_options_hist)
            
            if selected_machine_hist == "Toutes les machines":
                records_to_show = manager.maintenance_manager.maintenance_records
            else:
                records_to_show = manager.maintenance_manager.get_maintenance_history_for_machine(selected_machine_hist)
            
            if records_to_show:
                # Trier par date décroissante
                records_to_show.sort(key=lambda x: x.date_maintenance, reverse=True)
                
                for record in records_to_show:
                    machine = next((m for m in manager.machines if m.id == record.machine_id), None)
                    machine_type = machine.type if machine else "N/A"
                    
                    with st.expander(f"🔧 {record.machine_id} ({machine_type}) - {record.maintenance_type} - {record.date_maintenance.strftime('%d/%m/%Y')}", expanded=False):
                        col_h1, col_h2 = st.columns(2)
                        with col_h1:
                            st.write(f"**Type:** {record.maintenance_type}")
                            st.write(f"**Date:** {record.date_maintenance.strftime('%d/%m/%Y')}")
                            st.write(f"**Mécanicien:** {record.mechanic_name}")
                            st.write(f"**H-Mètre au moment de la maintenance:** {record.engine_hours_at_maintenance:,} h")
                        with col_h2:
                            if record.pieces_changed:
                                st.write("**Pièces Changées:**")
                                total_cost = 0
                                for piece in record.pieces_changed:
                                    cost_piece = piece.get("cout", 0) * piece.get("quantite", 1)
                                    total_cost += cost_piece
                                    st.write(f"- {piece.get('nom', 'N/A')}: {piece.get('quantite', 1)} × {piece.get('cout', 0):,.2f} $ = {cost_piece:,.2f} $")
                                st.markdown(f"**💰 Coût Total Pièces: {total_cost:,.2f} $**")
                            else:
                                st.write("**Pièces Changées:** Aucune pièce enregistrée")
                        
                        if record.notes:
                            st.markdown(f"**Notes/Observations:** {record.notes}")
            else:
                st.info("Aucune maintenance trouvée pour cette machine.")
        else:
            st.info("Aucun historique de maintenance disponible.")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # --- 5. RAPPORT JOURNALIER ---
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("📄 RAPPORT JOURNALIER DE MAINTENANCE")
        
        # Sélection de la date
        report_date = st.date_input("Sélectionner la date du rapport", value=date.today(), key="maintenance_report_date")
        
        # Filtrer les maintenances du jour sélectionné
        maintenances_du_jour = []
        for record in manager.maintenance_manager.maintenance_records:
            if isinstance(record.date_maintenance, date):
                record_date = record.date_maintenance
            else:
                try:
                    record_date = datetime.strptime(str(record.date_maintenance), "%Y-%m-%d").date()
                except:
                    continue
            
            if record_date == report_date:
                maintenances_du_jour.append(record)
        
        if maintenances_du_jour:
            st.success(f"✅ **{len(maintenances_du_jour)} maintenance(s) trouvée(s) pour le {report_date.strftime('%d/%m/%Y')}**")
            st.markdown("---")
            
            # Statistiques du jour
            total_cost_day = 0
            machines_concerned = set()
            mechanics_concerned = set()
            total_pieces = 0
            
            for record in maintenances_du_jour:
                machines_concerned.add(record.machine_id)
                mechanics_concerned.add(record.mechanic_name)
                
                if record.pieces_changed:
                    for piece in record.pieces_changed:
                        piece_name = piece.get("nom", "")
                        quantity = piece.get("quantite", 1)
                        # Chercher le prix dans le catalogue
                        part_info = manager.maintenance_manager.parts_catalog.get_part_by_name(piece_name)
                        if part_info:
                            piece_cost = part_info["cout"] * quantity
                        else:
                            piece_cost = piece.get("cout", 0) * quantity
                        total_cost_day += piece_cost
                        total_pieces += quantity
            
            # Métriques
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            col_stat1.metric("Maintenances", len(maintenances_du_jour))
            col_stat2.metric("Machines", len(machines_concerned))
            col_stat3.metric("Mécaniciens", len(mechanics_concerned))
            col_stat4.metric("Coût Total", f"{total_cost_day:,.2f} $")
            
            st.markdown("---")
            
            # Détails du rapport
            st.markdown("#### 📋 Détails des Maintenances")
            
            report_data = []
            for record in maintenances_du_jour:
                machine = next((m for m in manager.machines if m.id == record.machine_id), None)
                machine_type = machine.type if machine else "N/A"
                
                # Calculer le coût des pièces
                record_cost = 0
                pieces_list = []
                if record.pieces_changed:
                    for piece in record.pieces_changed:
                        piece_name = piece.get("nom", "")
                        quantity = piece.get("quantite", 1)
                        part_info = manager.maintenance_manager.parts_catalog.get_part_by_name(piece_name)
                        if part_info:
                            piece_cost = part_info["cout"] * quantity
                        else:
                            piece_cost = piece.get("cout", 0) * quantity
                        record_cost += piece_cost
                        pieces_list.append(f"{piece_name} (x{quantity})")
                
                report_data.append({
                    "Heure": record.date_maintenance.strftime("%H:%M") if isinstance(record.date_maintenance, datetime) else "N/A",
                    "Machine": record.machine_id,
                    "Type Machine": machine_type,
                    "Type Maintenance": record.maintenance_type,
                    "Mécanicien": record.mechanic_name,
                    "H-Mètre": f"{record.engine_hours_at_maintenance:,} h" if record.engine_hours_at_maintenance > 0 else "N/A",
                    "Pièces": ", ".join(pieces_list) if pieces_list else "Aucune",
                    "Coût ($)": f"{record_cost:,.2f}",
                    "Notes": record.notes if hasattr(record, 'notes') and record.notes else "N/A"
                })
            
            df_report = pd.DataFrame(report_data)
            st.dataframe(df_report, width='stretch', hide_index=True)
            
            st.markdown("---")
            
            # Résumé par machine
            st.markdown("#### 📊 Résumé par Machine")
            machine_summary = {}
            for record in maintenances_du_jour:
                if record.machine_id not in machine_summary:
                    machine_summary[record.machine_id] = {
                        "count": 0,
                        "cost": 0,
                        "types": []
                    }
                machine_summary[record.machine_id]["count"] += 1
                machine_summary[record.machine_id]["types"].append(record.maintenance_type)
                
                if record.pieces_changed:
                    for piece in record.pieces_changed:
                        piece_name = piece.get("nom", "")
                        quantity = piece.get("quantite", 1)
                        part_info = manager.maintenance_manager.parts_catalog.get_part_by_name(piece_name)
                        if part_info:
                            piece_cost = part_info["cout"] * quantity
                        else:
                            piece_cost = piece.get("cout", 0) * quantity
                        machine_summary[record.machine_id]["cost"] += piece_cost
            
            summary_data = []
            for machine_id, summary in machine_summary.items():
                summary_data.append({
                    "Machine": machine_id,
                    "Nb Maintenances": summary["count"],
                    "Types": ", ".join(set(summary["types"])),
                    "Coût Total ($)": f"{summary['cost']:,.2f}"
                })
            
            df_summary = pd.DataFrame(summary_data)
            st.dataframe(df_summary, width='stretch', hide_index=True)
            
            st.markdown("---")
            
            # Boutons d'export
            st.markdown("#### 📥 Exporter le Rapport")
            col_exp1, col_exp2, col_exp3 = st.columns(3)
            
            with col_exp1:
                try:
                    csv_report = df_report.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Télécharger en CSV",
                        data=csv_report,
                        file_name=f"rapport_maintenance_{report_date.strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                        width='stretch'
                    )
                except:
                    st.info("Export CSV disponible")
            
            with col_exp2:
                try:
                    import openpyxl
                    from io import BytesIO
                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_report.to_excel(writer, index=False, sheet_name='Détails')
                        df_summary.to_excel(writer, index=False, sheet_name='Résumé par Machine')
                    excel_data = output.getvalue()
                    st.download_button(
                        label="📊 Télécharger en Excel",
                        data=excel_data,
                        file_name=f"rapport_maintenance_{report_date.strftime('%Y%m%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        width='stretch'
                    )
                except ImportError:
                    st.info("Pour Excel: pip install openpyxl")
                except:
                    st.info("Export Excel disponible")
            
            with col_exp3:
                # Rapport texte formaté
                report_text = f"""
RAPPORT JOURNALIER DE MAINTENANCE
Date: {report_date.strftime('%d/%m/%Y')}
{'='*50}

STATISTIQUES GLOBALES
- Nombre de maintenances: {len(maintenances_du_jour)}
- Machines concernées: {len(machines_concerned)}
- Mécaniciens impliqués: {len(mechanics_concerned)}
- Coût total: {total_cost_day:,.2f} $
- Pièces utilisées: {total_pieces}

DÉTAILS DES MAINTENANCES
{'-'*50}
"""
                for record in maintenances_du_jour:
                    machine = next((m for m in manager.machines if m.id == record.machine_id), None)
                    machine_type = machine.type if machine else "N/A"
                    report_text += f"\nMachine: {record.machine_id} ({machine_type})\n"
                    report_text += f"Type: {record.maintenance_type}\n"
                    report_text += f"Mécanicien: {record.mechanic_name}\n"
                    if record.engine_hours_at_maintenance > 0:
                        report_text += f"H-Mètre: {record.engine_hours_at_maintenance:,} h\n"
                    if record.pieces_changed:
                        report_text += "Pièces changées:\n"
                        record_cost = 0
                        for piece in record.pieces_changed:
                            piece_name = piece.get("nom", "")
                            quantity = piece.get("quantite", 1)
                            part_info = manager.maintenance_manager.parts_catalog.get_part_by_name(piece_name)
                            if part_info:
                                piece_cost = part_info["cout"] * quantity
                            else:
                                piece_cost = piece.get("cout", 0) * quantity
                            record_cost += piece_cost
                            report_text += f"  - {piece_name}: {quantity} × {piece.get('cout', 0):,.2f} $ = {piece_cost:,.2f} $\n"
                        report_text += f"Coût total: {record_cost:,.2f} $\n"
                    if hasattr(record, 'notes') and record.notes:
                        report_text += f"Notes: {record.notes}\n"
                    report_text += "-" * 50 + "\n"
                
                st.download_button(
                    label="📄 Télécharger en TXT",
                    data=report_text.encode('utf-8'),
                    file_name=f"rapport_maintenance_{report_date.strftime('%Y%m%d')}.txt",
                    mime="text/plain",
                    width='stretch'
                )
        else:
            st.info(f"ℹ️ Aucune maintenance enregistrée pour le {report_date.strftime('%d/%m/%Y')}.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# ==============================================================================
# DURÉE DE VIE DES PIÈCES — fonctions SQLite
# ==============================================================================

def record_part_pose(machine_id: str, part_name: str, production_tonnes: float,
                     engine_hours: float, pose_date, maintenance_ref: str = "",
                     notes: str = "", created_by: str = "Système") -> int | None:
    """Enregistre la pose d'une pièce sur une machine avec le snapshot de production/heures."""
    try:
        date_str = pose_date.strftime("%Y-%m-%d") if hasattr(pose_date, "strftime") else str(pose_date)
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO part_life_tracking
                    (machine_id, part_name, production_tonnes_at_pose, engine_hours_at_pose,
                     pose_date, maintenance_ref, notes, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (machine_id, part_name, float(production_tonnes), float(engine_hours),
                  date_str, maintenance_ref or "", notes or "", created_by or "Système"))
            return cur.lastrowid
    except Exception:
        return None


def get_part_life_history(machine_id: str | None = None, part_name: str | None = None) -> list[dict]:
    """
    Retourne l'historique des poses avec la durée de vie calculée entre deux poses successives
    (production et heures entre chaque installation et la suivante).

    Chaque ligne représente une installation et indique combien la machine a produit
    pendant toute la durée de vie de cette pièce (jusqu'à son remplacement).
    """
    try:
        with get_connection() as conn:
            cur = conn.cursor()
            where_clauses = []
            params: list = []
            if machine_id:
                where_clauses.append("plt.machine_id = ?")
                params.append(machine_id)
            if part_name:
                where_clauses.append("plt.part_name = ?")
                params.append(part_name)
            where_sql = ("WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            cur.execute(f"""
                SELECT plt.id, plt.machine_id, plt.part_name,
                       plt.production_tonnes_at_pose, plt.engine_hours_at_pose,
                       plt.pose_date, plt.maintenance_ref, plt.notes, plt.created_by,
                       m.production_tonnes AS current_production,
                       m.engine_hours      AS current_hours,
                       m.model             AS machine_model
                FROM part_life_tracking plt
                LEFT JOIN machines m ON m.id = plt.machine_id
                {where_sql}
                ORDER BY plt.machine_id, plt.part_name, plt.pose_date ASC, plt.id ASC
            """, params)
            rows = [dict(r) for r in cur.fetchall()]
    except Exception:
        return []

    results: list[dict] = []
    # Groupe par (machine_id, part_name) pour calculer la vie entre poses successives
    from itertools import groupby
    key_fn = lambda r: (r["machine_id"], r["part_name"])  # noqa: E731
    for (mid, pname), group in groupby(rows, key=key_fn):
        items = list(group)
        for i, row in enumerate(items):
            if i + 1 < len(items):
                # Vie mesurée = production à la pose suivante − production à la pose actuelle
                next_row = items[i + 1]
                prod_life = max(0.0, (next_row["production_tonnes_at_pose"] or 0) - (row["production_tonnes_at_pose"] or 0))
                hours_life = max(0.0, (next_row["engine_hours_at_pose"] or 0) - (row["engine_hours_at_pose"] or 0))
                status = "Remplacée"
                next_pose_date = next_row["pose_date"]
            else:
                # Pièce encore en service : vie calculée jusqu'à la production courante
                prod_life = max(0.0, (row["current_production"] or 0) - (row["production_tonnes_at_pose"] or 0))
                hours_life = max(0.0, (row["current_hours"] or 0) - (row["engine_hours_at_pose"] or 0))
                status = "En service"
                next_pose_date = None
            results.append({
                "id": row["id"],
                "machine_id": mid,
                "machine_model": row["machine_model"] or mid,
                "part_name": pname,
                "pose_date": row["pose_date"],
                "pose_production_t": row["production_tonnes_at_pose"] or 0,
                "pose_hours": row["engine_hours_at_pose"] or 0,
                "prod_life_t": round(prod_life, 2),
                "hours_life": round(hours_life, 1),
                "status": status,
                "next_pose_date": next_pose_date,
                "maintenance_ref": row["maintenance_ref"] or "",
                "notes": row["notes"] or "",
                "created_by": row["created_by"] or "Système",
            })
    # Tri : pièces en service en premier, puis par production décroissante
    results.sort(key=lambda r: (r["status"] != "En service", -r["prod_life_t"]))
    return results


def get_part_life_summary() -> list[dict]:
    """Retourne les statistiques agrégées par nom de pièce (moyenne, max, total des remplacements)."""
    history = get_part_life_history()
    if not history:
        return []
    from collections import defaultdict
    agg: dict[str, dict] = defaultdict(lambda: {
        "total_poses": 0, "replaced": 0,
        "prod_lives": [], "hours_lives": [],
    })
    for row in history:
        pn = row["part_name"]
        agg[pn]["total_poses"] += 1
        if row["status"] == "Remplacée":
            agg[pn]["replaced"] += 1
            agg[pn]["prod_lives"].append(row["prod_life_t"])
            agg[pn]["hours_lives"].append(row["hours_life"])
    summary = []
    for pname, d in agg.items():
        pl = d["prod_lives"]
        hl = d["hours_lives"]
        summary.append({
            "Pièce": pname,
            "Nb poses": d["total_poses"],
            "Remplacements": d["replaced"],
            "Prod. moy. / vie (t)": round(sum(pl) / len(pl), 1) if pl else 0,
            "Prod. max / vie (t)": round(max(pl), 1) if pl else 0,
            "Prod. min / vie (t)": round(min(pl), 1) if pl else 0,
            "Heures moy. / vie": round(sum(hl) / len(hl), 1) if hl else 0,
        })
    summary.sort(key=lambda r: r["Prod. moy. / vie (t)"], reverse=True)
    return summary


# --- GESTION STOCK ---
# --- GESTION STOCK (GESTION DES QUANTITÉS EN STOCK) ---
if "GESTION STOCK" in tab_dict:
    with tab_dict["GESTION STOCK"]:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("📦 GESTIONNAIRE DE STOCK")
        st.markdown("Gérez les quantités en stock, les entrées, sorties et alertes de stock bas")
        st.markdown('</div>', unsafe_allow_html=True)
        
        stock_mgr = manager.maintenance_manager.stock_manager
        
        # Alertes de stock bas
        low_stock_items = stock_mgr.get_low_stock_items()
        if low_stock_items:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.error(f"⚠️ **ALERTE: {len(low_stock_items)} pièce(s) en stock bas ou épuisé(es)**")
            for item in low_stock_items:
                st.warning(f"🔴 **{item['nom']}**: {item['quantite']} {item['unite']} (Seuil minimum: {item['seuil_min']} {item['unite']})")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # Onglets internes Gestion Stock
        gestion_stock_tabs = st.tabs(["📊 État du Stock", "➕ Entrée Stock", "➖ Sortie Stock", "⚙️ Configuration", "📜 Historique", "📈 Durée de Vie Pièces"])
        
        with gestion_stock_tabs[0]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown("#### 📊 État du Stock Actuel")
            
            catalog = manager.maintenance_manager.parts_catalog
            
            # Statistiques globales
            total_items = len(catalog.parts)
            items_with_stock = len([p for p in catalog.parts if p["nom"] in stock_mgr.stock_levels])
            total_value_stock = 0
            
            for part in catalog.parts:
                stock_info = stock_mgr.get_stock_level(part["nom"])
                total_value_stock += stock_info["quantite"] * part["cout"]
            
            col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
            col_stat1.metric("Pièces en Catalogue", total_items)
            col_stat2.metric("Pièces avec Stock", items_with_stock)
            col_stat3.metric("Stock Bas", len(low_stock_items), delta_color="inverse")
            col_stat4.metric("Valeur Totale Stock", f"{total_value_stock:,.2f} $")
            
            st.markdown("---")
            
            # Filtrer par catégorie
            categories = catalog.get_categories()
            filter_cat_stock = st.selectbox("Filtrer par catégorie", ["Toutes les catégories"] + categories, key="filter_cat_stock")
            
            if filter_cat_stock == "Toutes les catégories":
                parts_to_show_stock = catalog.get_parts_by_category()
            else:
                parts_to_show_stock = catalog.get_parts_by_category(filter_cat_stock)
            
            if parts_to_show_stock:
                # Créer un DataFrame avec les niveaux de stock
                stock_data = []
                for p in parts_to_show_stock:
                    stock_info = stock_mgr.get_stock_level(p["nom"])
                    status = "🟢 OK"
                    if stock_info["quantite"] <= 0:
                        status = "🔴 ÉPUISÉ"
                    elif stock_info["quantite"] <= stock_info["seuil_min"]:
                        status = "🟡 STOCK BAS"
                    
                    stock_data.append({
                        "Pièce": p["nom"],
                        "Catégorie": p["categorie"],
                        "Quantité": f"{stock_info['quantite']} {stock_info['unite']}",
                        "Seuil Minimum": f"{stock_info['seuil_min']} {stock_info['unite']}",
                        "Prix Unitaire ($)": f"{p['cout']:,.2f}",
                        "Valeur Stock ($)": f"{stock_info['quantite'] * p['cout']:,.2f}",
                        "Statut": status
                    })
                
                df_stock = pd.DataFrame(stock_data)
                st.dataframe(df_stock, width='stretch', hide_index=True)
                
                # Boutons d'export
                col_exp1, col_exp2 = st.columns(2)
                with col_exp1:
                    try:
                        csv_stock = df_stock.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Télécharger en CSV",
                            data=csv_stock,
                            file_name=f"etat_stock_{date.today().strftime('%Y%m%d')}.csv",
                            mime="text/csv",
                            width='stretch'
                        )
                    except:
                        st.info("Export CSV disponible")
            else:
                st.info("Aucune pièce trouvée dans cette catégorie.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with gestion_stock_tabs[1]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown("#### ➕ Entrée de Stock (Réception)")
            
            with st.form("stock_entry_form"):
                catalog_entry = manager.maintenance_manager.parts_catalog
                parts_list = [p["nom"] for p in catalog_entry.parts]
                
                selected_part = st.selectbox("Pièce *", parts_list, key="entry_part")
                quantity_entry = st.number_input("Quantité *", min_value=1, value=1, key="entry_qty")
                
                col_ref, col_date = st.columns(2)
                with col_ref:
                    reference_entry = st.text_input("Référence (ex: N° Commande)", key="entry_ref", placeholder="Ex: CMD-2024-001")
                with col_date:
                    date_entry = st.date_input("Date de réception", value=date.today(), key="entry_date")
                
                notes_entry = st.text_area("Notes", key="entry_notes", height=60, placeholder="Ex: Commande fournisseur XYZ")
                
                if st.form_submit_button("✅ ENREGISTRER L'ENTRÉE", use_container_width=True):
                    created_by_entry = st.session_state.username if 'username' in st.session_state else "Système"
                    movement = stock_mgr.add_stock_entry(
                        selected_part, quantity_entry, date_entry, reference_entry, notes_entry, created_by_entry
                    )
                    if movement:
                        st.success(f"✅ {quantity_entry} {stock_mgr.get_stock_level(selected_part)['unite']} de '{selected_part}' ajouté(s) au stock !")
                        st.rerun()
                    else:
                        st.error("❌ Erreur lors de l'enregistrement de l'entrée.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with gestion_stock_tabs[2]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown("#### ➖ Sortie de Stock (Utilisation)")
            
            with st.form("stock_exit_form"):
                catalog_exit = manager.maintenance_manager.parts_catalog
                parts_list_exit = [p["nom"] for p in catalog_exit.parts]

                selected_part_exit = st.selectbox("Pièce *", parts_list_exit, key="exit_part")

                # Afficher le stock disponible
                stock_available = stock_mgr.get_stock_level(selected_part_exit)
                st.info(f"📦 Stock disponible: **{stock_available['quantite']} {stock_available['unite']}**")

                quantity_exit = st.number_input("Quantité à retirer *", min_value=1, max_value=stock_available['quantite'] if stock_available['quantite'] > 0 else 999999, value=1, key="exit_qty")

                # Récupérer la liste des mécaniciens et superviseurs mécaniciens
                mecaniciens_list = [
                    f"{emp.name} ({emp.role})"
                    for emp in staff_mgr.staff
                    if emp.role in ["Mecanicien", "Superviseur Mecanicien"]
                ]

                if mecaniciens_list:
                    demandeur_exit = st.selectbox("Demandeur *", mecaniciens_list, key="exit_demandeur")
                else:
                    st.warning("⚠️ Aucun mécanicien ou superviseur mécanicien trouvé dans le système.")
                    demandeur_exit = None

                col_ref_exit, col_date_exit = st.columns(2)
                with col_ref_exit:
                    reference_exit = st.text_input("Référence (ex: ID Maintenance)", key="exit_ref", placeholder="Ex: MAINT-001")
                with col_date_exit:
                    date_exit = st.date_input("Date de sortie", value=date.today(), key="exit_date")

                notes_exit = st.text_area("Notes", key="exit_notes", height=60, placeholder="Ex: Utilisé pour maintenance DT-01")

                # ── Liaison durée de vie : pose sur une machine ──────────────────
                st.divider()
                st.markdown("**📈 Suivi durée de vie** *(optionnel — lie cette sortie à une machine)*")
                machines_options = ["— Aucune machine —"] + [f"{m.id} — {m.model}" for m in manager.machines]
                machine_exit_sel = st.selectbox("Pose sur la machine", machines_options, key="exit_machine_link")
                pose_notes_exit = st.text_input("Note de pose", key="exit_pose_notes", placeholder="Ex: Remplacement filtre 500h PM")

                if st.form_submit_button("✅ ENREGISTRER LA SORTIE", use_container_width=True):
                    if not demandeur_exit:
                        st.error("❌ Veuillez indiquer qui demande la pièce.")
                    elif stock_available['quantite'] >= quantity_exit:
                        created_by_exit = st.session_state.get("username", "Système")
                        movement = stock_mgr.remove_stock_entry(
                            selected_part_exit, quantity_exit, date_exit, reference_exit, notes_exit, created_by_exit, demandeur_exit
                        )
                        if movement:
                            # Enregistrer la pose si une machine est sélectionnée
                            if machine_exit_sel and machine_exit_sel != "— Aucune machine —":
                                mid_exit = machine_exit_sel.split(" — ")[0].strip()
                                m_obj = next((m for m in manager.machines if m.id == mid_exit), None)
                                if m_obj:
                                    record_part_pose(
                                        machine_id=mid_exit,
                                        part_name=selected_part_exit,
                                        production_tonnes=m_obj.production_tonnes,
                                        engine_hours=m_obj.engine_hours,
                                        pose_date=date_exit,
                                        maintenance_ref=reference_exit or "",
                                        notes=pose_notes_exit or notes_exit or "",
                                        created_by=created_by_exit,
                                    )
                            st.success(f"✅ {quantity_exit} {stock_available['unite']} de '{selected_part_exit}' retiré(s) du stock !")
                            st.rerun()
                        else:
                            st.error("❌ Erreur lors de l'enregistrement de la sortie.")
                    else:
                        st.error(f"❌ Stock insuffisant ! Stock disponible: {stock_available['quantite']} {stock_available['unite']}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with gestion_stock_tabs[3]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown("#### ⚙️ Configuration du Stock")
            
            catalog_config = manager.maintenance_manager.parts_catalog
            parts_list_config = [p["nom"] for p in catalog_config.parts]
            
            selected_part_config = st.selectbox("Sélectionner une pièce", parts_list_config, key="config_part")
            
            stock_info_config = stock_mgr.get_stock_level(selected_part_config)
            
            with st.form("stock_config_form"):
                st.markdown(f"**Configuration pour: {selected_part_config}**")
                
                col_qty, col_seuil = st.columns(2)
                with col_qty:
                    new_quantity = st.number_input("Quantité actuelle", min_value=0, value=stock_info_config["quantite"], key="config_qty")
                with col_seuil:
                    new_seuil = st.number_input("Seuil minimum", min_value=0, value=stock_info_config["seuil_min"], key="config_seuil")
                
                unite_config = st.selectbox("Unité", ["unité", "L", "kg", "lot", "paquet"], index=0, key="config_unite")
                
                if st.form_submit_button("✅ METTRE À JOUR LE STOCK", use_container_width=True):
                    stock_mgr.set_stock_level(selected_part_config, new_quantity, new_seuil)
                    if selected_part_config not in stock_mgr.stock_levels:
                        stock_mgr.initialize_stock(selected_part_config, new_quantity, new_seuil, unite_config)
                    else:
                        stock_mgr.stock_levels[selected_part_config]["unite"] = unite_config
                    st.success(f"✅ Stock mis à jour pour '{selected_part_config}'")
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        with gestion_stock_tabs[4]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown("#### 📜 Historique des Mouvements")
            
            if stock_mgr.movements:
                # Filtrer par pièce
                catalog_hist = manager.maintenance_manager.parts_catalog
                parts_list_hist = ["Toutes les pièces"] + [p["nom"] for p in catalog_hist.parts]
                selected_part_hist = st.selectbox("Filtrer par pièce", parts_list_hist, key="hist_part")
                
                if selected_part_hist == "Toutes les pièces":
                    movements_to_show = stock_mgr.movements
                else:
                    movements_to_show = stock_mgr.get_movements_for_part(selected_part_hist)
                
                # Trier par date décroissante
                movements_to_show.sort(key=lambda x: x.date_movement, reverse=True)
                
                if movements_to_show:
                    movements_data = []
                    for m in movements_to_show:
                        movements_data.append({
                            "Date": m.date_movement.strftime("%d/%m/%Y"),
                            "Pièce": m.part_name,
                            "Type": "➕ ENTRÉE" if m.movement_type == "ENTREE" else "➖ SORTIE",
                            "Quantité": m.quantity,
                            "Référence": m.reference or "N/A",
                            "Demandeur": m.demandeur or "N/A",
                            "Créé par": m.created_by or "Système",
                            "Notes": m.notes or ""
                        })
                    
                    df_movements = pd.DataFrame(movements_data)
                    st.dataframe(df_movements, width='stretch', hide_index=True)
                else:
                    st.info("Aucun mouvement trouvé pour cette pièce.")
            else:
                st.info("Aucun mouvement de stock enregistré.")

            st.markdown('</div>', unsafe_allow_html=True)

        # ── Onglet 6 : Durée de vie des pièces ──────────────────────────────
        with gestion_stock_tabs[5]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.markdown("#### 📈 Durée de Vie des Consommables par Production")
            st.caption("Chaque ligne représente une installation de pièce. La production et les heures mesurées sont celles accumulées jusqu'au remplacement suivant (ou jusqu'à aujourd'hui si encore en service).")

            life_history = get_part_life_history()
            life_summary = get_part_life_summary()

            if life_summary:
                # ── KPIs ────────────────────────────────────────────────────
                best = max(life_summary, key=lambda r: r["Prod. moy. / vie (t)"])
                total_poses = sum(r["Nb poses"] for r in life_summary)
                total_replaced = sum(r["Remplacements"] for r in life_summary)

                kc1, kc2, kc3, kc4 = st.columns(4)
                kc1.metric("Pièces suivies", len(life_summary))
                kc2.metric("Total poses enregistrées", total_poses)
                kc3.metric("Remplacements mesurés", total_replaced)
                kc4.metric("Meilleure durée moy.", f"{best['Prod. moy. / vie (t)']:,.0f} t", help=f"Pièce : {best['Pièce']}")

                st.divider()

                # ── Tableau de synthèse ──────────────────────────────────────
                st.markdown("##### Synthèse par pièce")
                df_summary = pd.DataFrame(life_summary)
                st.dataframe(df_summary, hide_index=True, use_container_width=True)

                # ── Graphique barres — production moyenne par pièce ──────────
                if len(life_summary) > 1:
                    df_chart = pd.DataFrame([
                        {"Pièce": r["Pièce"], "Production moy. (t)": r["Prod. moy. / vie (t)"]}
                        for r in life_summary if r["Prod. moy. / vie (t)"] > 0
                    ]).sort_values("Production moy. (t)", ascending=True)
                    if not df_chart.empty:
                        fig_bar = go.Figure(go.Bar(
                            y=df_chart["Pièce"],
                            x=df_chart["Production moy. (t)"],
                            orientation="h",
                            marker_color="#F5B800",
                            text=df_chart["Production moy. (t)"].apply(lambda v: f"{v:,.0f} t"),
                            textposition="outside",
                        ))
                        fig_bar.update_layout(
                            title="Production moyenne par vie de pièce",
                            xaxis_title="Tonnes produites",
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font_color="#EAEAEA",
                            height=max(300, len(df_chart) * 35 + 80),
                            margin=dict(l=10, r=60, t=40, b=20),
                        )
                        fig_bar.update_xaxes(color="#EAEAEA", gridcolor="#333")
                        fig_bar.update_yaxes(color="#EAEAEA")
                        st.plotly_chart(fig_bar, use_container_width=True)

                st.divider()

                # ── Historique détaillé filtrable ────────────────────────────
                st.markdown("##### Historique détaillé par installation")

                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    all_parts = sorted({r["part_name"] for r in life_history})
                    filter_part = st.selectbox("Filtrer par pièce", ["Toutes"] + all_parts, key="plt_filter_part")
                with col_f2:
                    all_machines = sorted({r["machine_id"] for r in life_history})
                    filter_machine = st.selectbox("Filtrer par machine", ["Toutes"] + all_machines, key="plt_filter_machine")

                filtered_hist = life_history
                if filter_part != "Toutes":
                    filtered_hist = [r for r in filtered_hist if r["part_name"] == filter_part]
                if filter_machine != "Toutes":
                    filtered_hist = [r for r in filtered_hist if r["machine_id"] == filter_machine]

                if filtered_hist:
                    df_hist = pd.DataFrame([{
                        "Machine": f"{r['machine_id']} ({r['machine_model']})",
                        "Pièce": r["part_name"],
                        "Date de pose": r["pose_date"],
                        "Production à la pose (t)": f"{r['pose_production_t']:,.0f}",
                        "Heures à la pose": f"{r['pose_hours']:,.0f} h",
                        "Production vie (t)": f"{r['prod_life_t']:,.1f}",
                        "Heures vie": f"{r['hours_life']:,.0f} h",
                        "Statut": r["status"],
                        "Ref. maintenance": r["maintenance_ref"] or "—",
                        "Posé par": r["created_by"],
                        "Note": r["notes"] or "—",
                    } for r in filtered_hist])

                    def _color_status(val):
                        if val == "En service":
                            return "color: #28A745; font-weight: bold"
                        if val == "Remplacée":
                            return "color: #A0A0A0"
                        return ""

                    styled = df_hist.style.map(_color_status, subset=["Statut"])
                    st.dataframe(styled, hide_index=True, use_container_width=True)

                    # Export CSV
                    csv_life = df_hist.to_csv(index=False).encode("utf-8")
                    st.download_button(
                        "⬇️ Exporter CSV",
                        data=csv_life,
                        file_name=f"duree_vie_pieces_{date.today().strftime('%Y%m%d')}.csv",
                        mime="text/csv",
                    )
                else:
                    st.info("Aucune pose enregistrée pour ces filtres.")

                # ── Enregistrement manuel d'une pose ─────────────────────────
                st.divider()
                st.markdown("##### ✍️ Enregistrer manuellement une pose")
                st.caption("Utilisez ce formulaire pour déclarer rétroactivement la pose d'une pièce.")
                with st.form("form_manual_pose"):
                    mp_col1, mp_col2 = st.columns(2)
                    with mp_col1:
                        machines_list_mp = [f"{m.id} — {m.model}" for m in manager.machines]
                        mp_machine = st.selectbox("Machine *", machines_list_mp if machines_list_mp else ["Aucune machine"], key="mp_machine")
                        mp_part = st.selectbox("Pièce *", [p["nom"] for p in manager.maintenance_manager.parts_catalog.parts], key="mp_part")
                    with mp_col2:
                        mp_date = st.date_input("Date de pose *", value=date.today(), key="mp_date")
                        mp_ref = st.text_input("Référence", key="mp_ref", placeholder="Ex: PM-250h")
                    mp_prod = st.number_input("Production machine à la pose (t)", min_value=0.0, step=100.0, key="mp_prod")
                    mp_hours = st.number_input("Heures moteur à la pose", min_value=0.0, step=10.0, key="mp_hours")
                    mp_notes = st.text_input("Notes", key="mp_notes")
                    if st.form_submit_button("📌 ENREGISTRER LA POSE", use_container_width=True):
                        if machines_list_mp and mp_machine != "Aucune machine":
                            mid_mp = mp_machine.split(" — ")[0].strip()
                            record_part_pose(
                                machine_id=mid_mp,
                                part_name=mp_part,
                                production_tonnes=mp_prod,
                                engine_hours=mp_hours,
                                pose_date=mp_date,
                                maintenance_ref=mp_ref or "",
                                notes=mp_notes or "",
                                created_by=st.session_state.get("username", "Système"),
                            )
                            st.success(f"✅ Pose de « {mp_part} » enregistrée sur {mid_mp}.")
                            st.rerun()
                        else:
                            st.error("❌ Sélectionnez une machine.")

            else:
                st.info("Aucune donnée de durée de vie enregistrée pour l'instant.")
                st.markdown("""
**Comment alimenter ce suivi ?**
1. **Automatiquement** — lors d'une sortie de stock vers une machine (onglet *Sortie Stock*), ou lors d'une maintenance avec pièces changées.
2. **Manuellement** — via le formulaire ci-dessous si la pièce a été posée avant l'activation du suivi.
""")
                with st.form("form_manual_pose_empty"):
                    mp2_col1, mp2_col2 = st.columns(2)
                    with mp2_col1:
                        machines_list_mp2 = [f"{m.id} — {m.model}" for m in manager.machines]
                        mp2_machine = st.selectbox("Machine *", machines_list_mp2 if machines_list_mp2 else ["Aucune machine"], key="mp2_machine")
                        mp2_part = st.selectbox("Pièce *", [p["nom"] for p in manager.maintenance_manager.parts_catalog.parts], key="mp2_part")
                    with mp2_col2:
                        mp2_date = st.date_input("Date de pose *", value=date.today(), key="mp2_date")
                        mp2_ref = st.text_input("Référence", key="mp2_ref")
                    mp2_prod = st.number_input("Production machine à la pose (t)", min_value=0.0, step=100.0, key="mp2_prod")
                    mp2_hours = st.number_input("Heures moteur à la pose", min_value=0.0, step=10.0, key="mp2_hours")
                    mp2_notes = st.text_input("Notes", key="mp2_notes")
                    if st.form_submit_button("📌 ENREGISTRER LA POSE", use_container_width=True):
                        if machines_list_mp2 and mp2_machine != "Aucune machine":
                            mid_mp2 = mp2_machine.split(" — ")[0].strip()
                            record_part_pose(
                                machine_id=mid_mp2,
                                part_name=mp2_part,
                                production_tonnes=mp2_prod,
                                engine_hours=mp2_hours,
                                pose_date=mp2_date,
                                maintenance_ref=mp2_ref or "",
                                notes=mp2_notes or "",
                                created_by=st.session_state.get("username", "Système"),
                            )
                            st.success(f"✅ Pose de « {mp2_part} » enregistrée.")
                            st.rerun()
                        else:
                            st.error("❌ Sélectionnez une machine.")

            st.markdown('</div>', unsafe_allow_html=True)

# --- CARTE ---
# --- CARTE (TRACKING GPS & ZONES) ---
# --- CARTE (SUPER HUD : CLASSEMENT & TONNAGE) ---
if "CARTE" in tab_dict:
    with tab_dict["CARTE"]:
        
        # 1. CONTRÔLES
        c_ctrl_1, c_ctrl_2 = st.columns([1, 4])
        with c_ctrl_1:
            is_live = st.toggle("📡 MODE LIVE (5s)", value=False)
        with c_ctrl_2:
            if st.button("🔄 FORCER ACTUALISATION", use_container_width=True):
                st.rerun()

        c_map, c_dispatch = st.columns([3, 1])
        
        # 2. PRÉPARATION INTELLIGENTE DES DONNÉES
        def get_fleet_centroid(machines):
            if not machines:
                return (12.3, -1.5)
            lat = sum(m.lat for m in machines) / len(machines)
            lon = sum(m.lon for m in machines) / len(machines)
            return (lat, lon)

        fleet_lat, fleet_lon = get_fleet_centroid(manager.machines)
        weather = get_weather(fleet_lat, fleet_lon)

        # Encadré météo lié à la position moyenne de la flotte
        with st.container():
            st.markdown(
                "<div class='content-card'>", unsafe_allow_html=True
            )
            st.subheader("⛅ Météo (Open-Meteo)")
            if weather:
                st.markdown(
                    f"**Température :** {weather.get('temp', '?')} C  |  "
                    f"**Vent :** {weather.get('windspeed', '?')} km/h  "
                    f"(dir {weather.get('winddir', '?')}°)"
                )
                if weather.get("time"):
                    st.caption(f"Observation : {weather['time']}")
            else:
                st.warning("Météo indisponible (vérifier la connexion).")
            st.markdown(
                "</div>", unsafe_allow_html=True
            )

        if not df.empty:
            df_map = df.copy()
            
            # --- A. CALCUL DU CLASSEMENT (RANKING) ---
            # On trie les dumpers par production décroissante pour savoir qui est le 1er, 2ème...
            if 'Production (T)' in df_map.columns and 'Type' in df_map.columns:
                # On crée une colonne Rank uniquement pour les dumpers
                df_map['Rank'] = df_map[df_map['Type'] == 'Dumper']['Production (T)'].rank(ascending=False, method='min')
            else:
                df_map['Rank'] = None

            # --- B. CONSTRUCTION DE L'ÉTIQUETTE (SUPER LABEL) ---
            def get_super_label(row):
                # 1. Icône
                if "Dumper" in str(row.get('Type')): icon = "🚛"
                elif "Pelle" in str(row.get('Type')): icon = "🚜"
                else: icon = "⚙️"
                
                # 2. ID
                id_txt = row.get('ID', '?')
                
                # 3. Tonnage
                prod = int(row.get('Production (T)', 0))
                
                # 4. Gestion du Classement (Médailles) pour les Dumpers
                rank_txt = ""
                if row.get('Type') == 'Dumper' and pd.notnull(row.get('Rank')):
                    r = int(row['Rank'])
                    if r == 1: rank_txt = "🥇 #1"
                    elif r == 2: rank_txt = "🥈 #2"
                    elif r == 3: rank_txt = "🥉 #3"
                    else: rank_txt = f"#{r}"
                
                # Assemblage final : "🚛 DT-01 (🥇 #1) | 🧱 4500 T"
                # On met des retours à la ligne pour la clarté si besoin, mais Plotly préfère une ligne pour les labels simples
                if rank_txt:
                    return f"{icon} {id_txt} ({rank_txt}) | 🧱 {prod} T"
                else:
                    return f"{icon} {id_txt} | 🧱 {prod} T"

            # Application
            df_map['Label'] = df_map.apply(get_super_label, axis=1)
            
            # Taille des points
            if 'Type' in df_map.columns:
                df_map['Size'] = df_map['Type'].apply(lambda x: 25 if "Pelle" in str(x) else 15)
            else:
                df_map['Size'] = 15

            # 3. AFFICHAGE CARTE
            with c_map:
                st.markdown("### 📡 Radar de Production")
                
                color_map = {"Active": "#00E676", "Panne": "#FF1744", "Attente": "#FFC400", "Maintenance": "#2979FF"}
                
                fig_map = px.scatter_mapbox(
                    df_map, 
                    lat="lat", lon="lon", 
                    color="Statut", 
                    text="Label", # <--- AFFICHE TOUT (ID, RANK, TONNAGE)
                    size="Size",
                    color_discrete_map=color_map,
                    hover_name="ID",
                    hover_data={"lat": False, "lon": False, "Size": False, "Label": False, "Type": False, "Statut": False},
                    zoom=14.5, height=650
                )
                
                fig_map.update_layout(
                    mapbox_style="carto-darkmatter", 
                    margin={"r":0,"t":0,"l":0,"b":0},
                    mapbox=dict(pitch=60)  # Vue drone améliorée
                )
                
                # Texte blanc, gras, positionné sous le point
                fig_map.update_traces(
                    textposition='bottom center',
                    textfont=dict(size=13, color='white', family="Arial Black"),
                    marker=dict(opacity=0.9)
                )
                
                st.plotly_chart(fig_map, width='stretch', config={'scrollZoom': True})

            # 4. CLASSEMENT TEXTUEL (À DROITE)
            with c_dispatch:
                st.markdown("### 🏆 Top Dumpers")
                
                # On filtre et trie pour le tableau
                if 'Rank' in df_map.columns:
                    top_dumpers = df_map[df_map['Type'] == 'Dumper'].sort_values(by='Production (T)', ascending=False)
                    
                    if not top_dumpers.empty:
                        # Petit tableau stylé
                        st.dataframe(
                            top_dumpers[['ID', 'Production (T)', 'Carburant (%)']], 
                            hide_index=True,
                            width='stretch'
                        )
                    else:
                        st.info("Aucun dumper actif.")
                
                st.divider()
                st.markdown("#### 🧠 IA Trajet")
                # Logique distance simplifiée pour l'exemple
                if not df_map.empty and 'Type' in df_map.columns:
                    dumpers = df_map[(df_map['Type'] == 'Dumper') & (df_map['Statut'] == 'Active')]
                    pelles = df_map[(df_map['Type'].isin(['Pelle', 'Excavateur'])) & (df_map['Statut'] == 'Active')]
                    
                    if not dumpers.empty and not pelles.empty:
                        for _, dumper in dumpers.iterrows():
                            # Calcul simple vers la première pelle trouvée (simulation)
                            pelle = pelles.iloc[0] 
                            dist = ((dumper['lat']-pelle['lat'])**2 + (dumper['lon']-pelle['lon'])**2)**0.5 * 111
                            st.success(f"🚛 **{dumper['ID']}** ➜ 🚜 **{pelle['ID']}** ({dist:.2f}km)")
                    else:
                        st.caption("Flotte immobile.")

        # --- ACTUALISATION AUTOMATIQUE ---
        if is_live:
            time.sleep(5)
            st.rerun()
# --- FINANCE ---
if "FINANCE" in tab_dict:
    with tab_dict["FINANCE"]:
        # Mettre à jour les contrats avec les données actuelles des machines
        contract_mgr.update_contract_from_machines(manager)
        
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("💰 GESTION FINANCIÈRE - CONTRATS MINIERS")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Onglets internes Finance
        finance_tabs = st.tabs(
            [
                "📊 Vue d'Ensemble",
                "💰 Dépenses & Gains",
                "📋 Contrats BCM",
                "⏰ Contrats Horaire",
                "➕ Ajouter Contrat",
                "✏️ Modifier Taux",
                "⚙️ Informations Entreprise",
                "🧾 Générer Factures",
                "📈 Graphiques",
            ]
        )
        
        # --- TAB 1: VUE D'ENSEMBLE ---
        with finance_tabs[0]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📊 Résumé des Revenus - Tous Contrats Confondus")
            
            # Résumé total
            summary = contract_mgr.get_total_revenue_summary()
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Revenu Journalier", f"{summary['Revenu Jour ($)']:,.2f} $")
            col2.metric("💰 Revenu Hebdomadaire", f"{summary['Revenu Semaine ($)']:,.2f} $")
            col3.metric("💰 Revenu Mensuel", f"{summary['Revenu Mois ($)']:,.2f} $")
            col4.metric("💰 Revenu Annuel", f"{summary['Revenu Année ($)']:,.2f} $")
            
            st.markdown("---")
            
            # Détail par type de contrat
            st.markdown("#### 📊 Répartition par Type de Contrat")
            col_bcm, col_hourly = st.columns(2)
            
            with col_bcm:
                bcm_contracts = [c for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active]
                if bcm_contracts:
                    total_bcm_jour = sum(c.revenu_jour for c in bcm_contracts)
                    total_bcm_semaine = sum(c.revenu_semaine for c in bcm_contracts)
                    total_bcm_mois = sum(c.revenu_mois for c in bcm_contracts)
                    total_bcm_annee = sum(c.revenu_annee for c in bcm_contracts)
                    
                    st.markdown("**📋 Contrats BCM (Volume Transporté)**")
                    st.write(f"- Jour: **{total_bcm_jour:,.2f} $**")
                    st.write(f"- Semaine: **{total_bcm_semaine:,.2f} $**")
                    st.write(f"- Mois: **{total_bcm_mois:,.2f} $**")
                    st.write(f"- Année: **{total_bcm_annee:,.2f} $**")
                else:
                    st.info("Aucun contrat BCM actif")
            
            with col_hourly:
                hourly_contracts = [c for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active]
                if hourly_contracts:
                    total_hourly_jour = sum(c.revenu_jour for c in hourly_contracts)
                    total_hourly_semaine = sum(c.revenu_semaine for c in hourly_contracts)
                    total_hourly_mois = sum(c.revenu_mois for c in hourly_contracts)
                    total_hourly_annee = sum(c.revenu_annee for c in hourly_contracts)
                    
                    st.markdown("**⏰ Contrats Horaire (Heures Travaillées)**")
                    st.write(f"- Jour: **{total_hourly_jour:,.2f} $**")
                    st.write(f"- Semaine: **{total_hourly_semaine:,.2f} $**")
                    st.write(f"- Mois: **{total_hourly_mois:,.2f} $**")
                    st.write(f"- Année: **{total_hourly_annee:,.2f} $**")
                else:
                    st.info("Aucun contrat horaire actif")
            
            st.markdown("---")
            st.markdown("#### 📋 Tableau Récapitulatif de Tous les Contrats")
            df_contracts = contract_mgr.get_contracts_df()
            if not df_contracts.empty:
                st.dataframe(df_contracts, width='stretch', hide_index=True)
            else:
                st.info("Aucun contrat enregistré.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 2: DÉPENSES & GAINS ---
        with finance_tabs[1]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("💰 Dépenses & Rapport Gain")
            
            # Sélection de la période
            period_type = st.selectbox("Période", ["Journalier", "Hebdomadaire", "Mensuel", "Annuel"], key="expense_period")
            
            # Calcul des dates selon la période
            today = date.today()
            if period_type == "Journalier":
                start_date = today
                end_date = today
                period_label = f"du {start_date.strftime('%d/%m/%Y')}"
            elif period_type == "Hebdomadaire":
                # Semaine en cours (lundi à dimanche)
                days_since_monday = today.weekday()
                start_date = today - timedelta(days=days_since_monday)
                end_date = start_date + timedelta(days=6)
                period_label = f"du {start_date.strftime('%d/%m/%Y')} au {end_date.strftime('%d/%m/%Y')}"
            elif period_type == "Mensuel":
                start_date = today.replace(day=1)
                # Dernier jour du mois
                if today.month == 12:
                    end_date = today.replace(day=31)
                else:
                    end_date = (today.replace(month=today.month+1, day=1) - timedelta(days=1))
                period_label = f"de {start_date.strftime('%B %Y')}"
            else:  # Annuel
                start_date = today.replace(month=1, day=1)
                end_date = today.replace(month=12, day=31)
                period_label = f"de {start_date.year}"
            
            st.info(f"📅 Période sélectionnée : **{period_label}**")
            st.markdown("---")
            
            # Calcul des dépenses de maintenance
            maintenance_expenses = 0
            maintenance_records_in_period = []
            for record in manager.maintenance_manager.maintenance_records:
                if isinstance(record.date_maintenance, date):
                    record_date = record.date_maintenance
                else:
                    try:
                        record_date = datetime.strptime(str(record.date_maintenance), "%Y-%m-%d").date()
                    except:
                        continue
                
                if start_date <= record_date <= end_date:
                    # Calculer le coût des pièces changées
                    record_cost = 0
                    if record.pieces_changed:
                        for piece in record.pieces_changed:
                            piece_name = piece.get("nom", "")
                            quantity = piece.get("quantite", 1)
                            # Chercher le prix dans le catalogue
                            part_info = manager.maintenance_manager.parts_catalog.get_part_by_name(piece_name)
                            if part_info:
                                piece_cost = part_info["cout"] * quantity
                            else:
                                # Si pas trouvé, utiliser le coût direct s'il existe
                                piece_cost = piece.get("cout", 0) * quantity
                            record_cost += piece_cost
                            maintenance_expenses += piece_cost
                    maintenance_records_in_period.append((record, record_cost))
            
            # Dépenses carburant : SQLite (ravitaillements + saisie ingénierie)
            fuel_expenses, fuel_logs_in_period = collect_fuel_expenses_for_finance(start_date, end_date)
            
            # Calcul des revenus
            revenue_summary = contract_mgr.get_total_revenue_summary()
            if period_type == "Journalier":
                revenue = revenue_summary.get('Revenu Jour ($)', 0)
            elif period_type == "Hebdomadaire":
                revenue = revenue_summary.get('Revenu Semaine ($)', 0)
            elif period_type == "Mensuel":
                revenue = revenue_summary.get('Revenu Mois ($)', 0)
            else:  # Annuel
                revenue = revenue_summary.get('Revenu Année ($)', 0)
            
            # Calcul du rapport gain
            total_expenses = maintenance_expenses + fuel_expenses
            net_gain = revenue - total_expenses
            
            # Affichage des métriques
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("💰 Revenus", f"{revenue:,.2f} $", delta=None)
            col2.metric("🔧 Dépenses Maintenance", f"{maintenance_expenses:,.2f} $", delta=None, delta_color="inverse")
            col3.metric("⛽ Dépenses Carburant", f"{fuel_expenses:,.2f} $", delta=None, delta_color="inverse")
            col4.metric("📊 Gain Net", f"{net_gain:,.2f} $", delta=f"{net_gain:,.2f} $", delta_color="normal" if net_gain >= 0 else "inverse")
            
            st.markdown("---")
            
            # Détails des dépenses
            col_detail1, col_detail2 = st.columns(2)
            
            with col_detail1:
                st.markdown("#### 🔧 Détails Maintenance")
                if maintenance_records_in_period:
                    maint_data = []
                    for record, record_cost in maintenance_records_in_period:
                        maint_data.append({
                            "Date": record.date_maintenance.strftime("%d/%m/%Y") if isinstance(record.date_maintenance, date) else str(record.date_maintenance),
                            "Machine": record.machine_id,
                            "Type": record.maintenance_type,
                            "Mécanicien": record.mechanic_name,
                            "Coût ($)": f"{record_cost:,.2f}"
                        })
                    
                    df_maint = pd.DataFrame(maint_data)
                    st.dataframe(df_maint, width='stretch', hide_index=True)
                else:
                    st.info("Aucune dépense de maintenance pour cette période.")
            
            with col_detail2:
                st.markdown("#### ⛽ Détails Carburant")
                st.caption(
                    "Sources : pleins enregistrés dans **Carburant**, et **litres chargés** saisis dans **Données ingénierie** "
                    "(coût = litres × prix USD indiqué à l'enregistrement)."
                )
                if fuel_logs_in_period:
                    fuel_data = []
                    for log in fuel_logs_in_period:
                        fuel_data.append({
                            "Date": log["date"].strftime("%d/%m/%Y"),
                            "Machine": log["machine"],
                            "Source": log.get("source", ""),
                            "Litres": f"{log['liters']:,.2f}",
                            "Coût ($)": f"{log['cost']:,.2f}"
                        })
                    
                    df_fuel = pd.DataFrame(fuel_data)
                    st.dataframe(df_fuel, width='stretch', hide_index=True)
                    
                    # Total litres
                    total_liters = sum(log['liters'] for log in fuel_logs_in_period)
                    st.metric("Total Litres", f"{total_liters:,.2f} L")
                else:
                    st.info("Aucune dépense de carburant pour cette période.")
            
            st.markdown("---")
            
            # Graphique de répartition
            try:
                import plotly.express as px
                
                # Données pour le graphique
                categories = ["Revenus", "Maintenance", "Carburant"]
                values = [revenue, maintenance_expenses, fuel_expenses]
                colors = ["#2ecc71", "#e74c3c", "#f39c12"]
                
                fig = px.bar(
                    x=categories,
                    y=values,
                    title=f"Répartition Revenus vs Dépenses - {period_label}",
                    labels={"x": "Catégorie", "y": "Montant ($)"},
                    color=categories,
                    color_discrete_map={"Revenus": "#2ecc71", "Maintenance": "#e74c3c", "Carburant": "#f39c12"}
                )
                fig.update_layout(showlegend=False, height=400)
                st.plotly_chart(fig, width='stretch')
            except:
                st.info("Graphique disponible avec plotly")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 3: CONTRATS BCM ---
        with finance_tabs[2]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📋 Contrats en BCM (Volume Transporté)")
            
            bcm_contracts = [c for c in contract_mgr.contracts if c.contract_type == "BCM"]
            if bcm_contracts:
                bcm_data = []
                for c in bcm_contracts:
                    rate_currency = getattr(c, 'rate_currency', 'USD')
                    original_rate = getattr(c, 'original_rate', c.rate)
                    bcm_data.append({
                        "ID Contrat": c.contract_id,
                        "Nom": c.name,
                        "Client": getattr(c, 'client_name', None) or "N/A",
                        "Taux": f"{original_rate:,.2f} {rate_currency}/BCM",
                        "Taux USD": f"{c.rate:,.2f} $/BCM",
                        "Somme Négociée": f"{getattr(c, 'somme_negociee', 0):,.2f} {getattr(c, 'somme_negociee_currency', 'USD')}" if getattr(c, 'somme_negociee', None) else "N/A",
                        "Volume Jour (BCM)": round(c.volume_jour, 2),
                        "Volume Semaine (BCM)": round(c.volume_semaine, 2),
                        "Volume Mois (BCM)": round(c.volume_mois, 2),
                        "Volume Année (BCM)": round(c.volume_annee, 2),
                        "Revenu Jour ($)": round(c.revenu_jour, 2),
                        "Revenu Semaine ($)": round(c.revenu_semaine, 2),
                        "Revenu Mois ($)": round(c.revenu_mois, 2),
                        "Revenu Année ($)": round(c.revenu_annee, 2)
                    })
                
                df_bcm = pd.DataFrame(bcm_data)
                st.dataframe(df_bcm, width='stretch', hide_index=True)
                
                # Totaux
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    total_volume = df_bcm[["Volume Jour (BCM)", "Volume Semaine (BCM)", "Volume Mois (BCM)", "Volume Année (BCM)"]].sum()
                    st.markdown("**Total Volumes Transportés:**")
                    st.write(f"- Jour: {total_volume['Volume Jour (BCM)']:,.2f} BCM")
                    st.write(f"- Semaine: {total_volume['Volume Semaine (BCM)']:,.2f} BCM")
                    st.write(f"- Mois: {total_volume['Volume Mois (BCM)']:,.2f} BCM")
                    st.write(f"- Année: {total_volume['Volume Année (BCM)']:,.2f} BCM")
                
                with col2:
                    total_revenus = df_bcm[["Revenu Jour ($)", "Revenu Semaine ($)", "Revenu Mois ($)", "Revenu Année ($)"]].sum()
                    st.markdown("**Total Revenus BCM:**")
                    st.write(f"- Jour: {total_revenus['Revenu Jour ($)']:,.2f} $")
                    st.write(f"- Semaine: {total_revenus['Revenu Semaine ($)']:,.2f} $")
                    st.write(f"- Mois: {total_revenus['Revenu Mois ($)']:,.2f} $")
                    st.write(f"- Année: {total_revenus['Revenu Année ($)']:,.2f} $")
            else:
                st.info("Aucun contrat BCM enregistré.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 4: CONTRATS HORAIRES ---
        with finance_tabs[3]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("⏰ Contrats à l'Heure")
            
            hourly_contracts = [c for c in contract_mgr.contracts if c.contract_type == "HOURLY"]
            if hourly_contracts:
                hourly_data = []
                for c in hourly_contracts:
                    rate_currency = getattr(c, 'rate_currency', 'USD')
                    original_rate = getattr(c, 'original_rate', c.rate)
                    hourly_data.append({
                        "ID Contrat": c.contract_id,
                        "Nom": c.name,
                        "Client": getattr(c, 'client_name', None) or "N/A",
                        "Taux": f"{original_rate:,.2f} {rate_currency}/heure",
                        "Taux USD": f"{c.rate:,.2f} $/heure",
                        "Somme Négociée": f"{getattr(c, 'somme_negociee', 0):,.2f} {getattr(c, 'somme_negociee_currency', 'USD')}" if getattr(c, 'somme_negociee', None) else "N/A",
                        "Heures Jour": round(c.heures_jour, 2),
                        "Heures Semaine": round(c.heures_semaine, 2),
                        "Heures Mois": round(c.heures_mois, 2),
                        "Heures Année": round(c.heures_annee, 2),
                        "Revenu Jour ($)": round(c.revenu_jour, 2),
                        "Revenu Semaine ($)": round(c.revenu_semaine, 2),
                        "Revenu Mois ($)": round(c.revenu_mois, 2),
                        "Revenu Année ($)": round(c.revenu_annee, 2)
                    })
                
                df_hourly = pd.DataFrame(hourly_data)
                st.dataframe(df_hourly, width='stretch', hide_index=True)
                
                # Totaux
                st.markdown("---")
                col1, col2 = st.columns(2)
                with col1:
                    total_heures = df_hourly[["Heures Jour", "Heures Semaine", "Heures Mois", "Heures Année"]].sum()
                    st.markdown("**Total Heures Travaillées:**")
                    st.write(f"- Jour: {total_heures['Heures Jour']:,.2f} h")
                    st.write(f"- Semaine: {total_heures['Heures Semaine']:,.2f} h")
                    st.write(f"- Mois: {total_heures['Heures Mois']:,.2f} h")
                    st.write(f"- Année: {total_heures['Heures Année']:,.2f} h")
                
                with col2:
                    total_revenus = df_hourly[["Revenu Jour ($)", "Revenu Semaine ($)", "Revenu Mois ($)", "Revenu Année ($)"]].sum()
                    st.markdown("**Total Revenus Horaire:**")
                    st.write(f"- Jour: {total_revenus['Revenu Jour ($)']:,.2f} $")
                    st.write(f"- Semaine: {total_revenus['Revenu Semaine ($)']:,.2f} $")
                    st.write(f"- Mois: {total_revenus['Revenu Mois ($)']:,.2f} $")
                    st.write(f"- Année: {total_revenus['Revenu Année ($)']:,.2f} $")
            else:
                st.info("Aucun contrat horaire enregistré.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 5: AJOUTER CONTRAT ---
        with finance_tabs[4]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("➕ Ajouter un Nouveau Contrat")
            
            with st.form("add_contract_form"):
                col_id, col_name = st.columns(2)
                with col_id:
                    contract_id = st.text_input("ID Contrat *", placeholder="Ex: CONT-003")
                with col_name:
                    contract_name = st.text_input("Nom du Contrat *", placeholder="Ex: Contrat Mine C")
                
                contract_type = st.selectbox("Type de Contrat *", ["BCM", "HOURLY"])
                
                col_rate, col_currency, col_date = st.columns(3)
                with col_rate:
                    if contract_type == "BCM":
                        rate = st.number_input("Taux *", min_value=0.01, value=15.0, step=0.1)
                        st.caption("Revenu = Volume transporté (BCM) × Taux")
                    else:
                        rate = st.number_input("Taux *", min_value=0.01, value=200.0, step=1.0)
                        st.caption("Revenu = Heures travaillées × Taux")
                
                with col_currency:
                    rate_currency = st.selectbox("Devise du Taux *", ["USD", "CFA", "EUR"], index=0)
                    # Afficher le taux de change actuel
                    rates = get_exchange_rates()
                    if rate_currency == "CFA":
                        st.caption(f"1 USD = {rates['CFA']:.0f} CFA")
                    elif rate_currency == "EUR":
                        st.caption(f"1 USD = {rates['EUR']:.2f} EUR")
                    else:
                        st.caption("Taux en USD")
                
                with col_date:
                    start_date = st.date_input("Date de Début", value=date.today())
                
                # Aperçu du taux en USD
                if rate_currency != "USD":
                    rates_preview = get_exchange_rates()
                    if rate_currency == "CFA":
                        rate_usd_preview = rate / rates_preview['CFA']
                        unit_label = "BCM" if contract_type == "BCM" else "heure"
                        st.info(f"💡 **Taux équivalent en USD:** {rate_usd_preview:,.2f} $/{unit_label}")
                    elif rate_currency == "EUR":
                        rate_usd_preview = rate / rates_preview['EUR']
                        unit_label = "BCM" if contract_type == "BCM" else "heure"
                        st.info(f"💡 **Taux équivalent en USD:** {rate_usd_preview:,.2f} $/{unit_label}")
                
                st.markdown("---")
                col_client, col_somme = st.columns(2)
                with col_client:
                    client_name = st.text_input("Nom du Client/Mine *", placeholder="Ex: Mine A")
                with col_somme:
                    col_somme_val, col_somme_dev = st.columns([2, 1])
                    with col_somme_val:
                        somme_negociee = st.number_input("Somme Négociée", min_value=0.0, value=0.0, step=1000.0, help="Montant total négocié du contrat (optionnel)")
                    with col_somme_dev:
                        somme_currency = st.selectbox("Devise", ["USD", "CFA", "EUR"], index=0, key="somme_devise")
                
                # Sélection des machines associées
                st.markdown("---")
                st.markdown("#### 🚜 Machines Associées au Contrat")
                st.caption("Sélectionnez les machines qui contribuent à ce contrat (optionnel - toutes les machines actives seront utilisées si aucune n'est sélectionnée)")
                
                machine_options = [m.id for m in manager.machines]
                selected_machines = st.multiselect("Machines", machine_options)
                
                if st.form_submit_button("✅ CRÉER LE CONTRAT", use_container_width=True):
                    if contract_id and contract_name and client_name:
                        # Convertir la somme négociée en USD si nécessaire
                        somme_usd = None
                        if somme_negociee > 0:
                            rates_somme = get_exchange_rates()
                            if somme_currency == "USD":
                                somme_usd = somme_negociee
                            elif somme_currency == "EUR":
                                somme_usd = somme_negociee / rates_somme['EUR']
                            elif somme_currency == "CFA":
                                somme_usd = somme_negociee / rates_somme['CFA']
                            else:
                                somme_usd = somme_negociee
                        
                        if contract_mgr.add_contract(contract_id, contract_name, contract_type, rate, start_date, somme_usd, client_name, rate_currency, rate):
                            # Associer les machines au contrat
                            new_contract = contract_mgr.get_contract(contract_id)
                            if new_contract:
                                if selected_machines:
                                    new_contract.machines_ids = selected_machines
                                # Stocker aussi la devise de la somme négociée
                                if somme_usd:
                                    new_contract.somme_negociee_currency = somme_currency
                            
                            st.success(f"✅ Contrat {contract_id} créé avec succès ! Taux: {rate:,.2f} {rate_currency}")
                            st.rerun()
                        else:
                            st.error("❌ Erreur : Cet ID de contrat existe déjà.")
                    else:
                        st.warning("⚠️ Veuillez remplir tous les champs obligatoires.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 6: MODIFIER TAUX ---
        with finance_tabs[5]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("✏️ Modifier les Taux des Contrats")
            
            if not contract_mgr.contracts:
                st.info("Aucun contrat disponible.")
            else:
                # Sélection du contrat
                contract_options = {f"{c.contract_id} - {c.name}": c for c in contract_mgr.contracts}
                selected_contract_label = st.selectbox("Sélectionner un Contrat *", list(contract_options.keys()))
                selected_contract = contract_options[selected_contract_label]
                
                if selected_contract:
                    st.markdown("---")
                    st.markdown(f"**Contrat sélectionné:** {selected_contract.name}")
                    st.markdown(f"**Type:** {selected_contract.contract_type}")
                    st.markdown(f"**Taux actuel:** {getattr(selected_contract, 'original_rate', selected_contract.rate):,.2f} {getattr(selected_contract, 'rate_currency', 'USD')}")
                    if selected_contract.contract_type == "BCM":
                        st.markdown(f"**Taux actuel en USD:** {selected_contract.rate:,.2f} $/BCM")
                    else:
                        st.markdown(f"**Taux actuel en USD:** {selected_contract.rate:,.2f} $/heure")
                    
                    st.markdown("---")
                    
                    with st.form("modify_rate_form"):
                        col_new_rate, col_new_currency = st.columns(2)
                        with col_new_rate:
                            if selected_contract.contract_type == "BCM":
                                new_rate = st.number_input("Nouveau Taux *", min_value=0.01, value=float(getattr(selected_contract, 'original_rate', selected_contract.rate)), step=0.1)
                                st.caption("Taux par BCM")
                            else:
                                new_rate = st.number_input("Nouveau Taux *", min_value=0.01, value=float(getattr(selected_contract, 'original_rate', selected_contract.rate)), step=1.0)
                                st.caption("Taux par heure")
                        
                        with col_new_currency:
                            current_currency = getattr(selected_contract, 'rate_currency', 'USD')
                            currency_index = ["USD", "CFA", "EUR"].index(current_currency) if current_currency in ["USD", "CFA", "EUR"] else 0
                            new_currency = st.selectbox("Devise du Taux *", ["USD", "CFA", "EUR"], index=currency_index)
                            
                            # Afficher le taux de change actuel
                            rates = get_exchange_rates()
                            if new_currency == "CFA":
                                st.caption(f"1 USD = {rates['CFA']:.0f} CFA")
                                if new_currency != current_currency:
                                    # Conversion approximative pour info
                                    if current_currency == "USD":
                                        equivalent = new_rate * rates['CFA']
                                        st.info(f"≈ {equivalent:,.0f} CFA")
                            elif new_currency == "EUR":
                                st.caption(f"1 USD = {rates['EUR']:.2f} EUR")
                                if new_currency != current_currency:
                                    if current_currency == "USD":
                                        equivalent = new_rate * rates['EUR']
                                        st.info(f"≈ {equivalent:,.2f} EUR")
                            else:
                                st.caption("Taux en USD")
                        
                        # Aperçu de la conversion
                        st.markdown("---")
                        if new_currency != "USD":
                            rates = get_exchange_rates()
                            if new_currency == "CFA":
                                rate_usd = new_rate / rates['CFA']
                            elif new_currency == "EUR":
                                rate_usd = new_rate / rates['EUR']
                            else:
                                rate_usd = new_rate
                            
                            st.info(f"**Taux équivalent en USD:** {rate_usd:,.2f} $/{'BCM' if selected_contract.contract_type == 'BCM' else 'heure'}")
                        
                        if st.form_submit_button("✅ MODIFIER LE TAUX", use_container_width=True):
                            if contract_mgr.update_contract_rate(selected_contract.contract_id, new_rate, new_currency):
                                st.success(f"✅ Taux modifié avec succès ! Nouveau taux: {new_rate:,.2f} {new_currency}")
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la modification du taux.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 7: INFORMATIONS ENTREPRISE ---
        with finance_tabs[6]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("⚙️ Informations de l'Entreprise")
            st.caption("Configurez les informations de votre entreprise pour l'affichage sur les factures")
            
            with st.form("company_info_form"):
                col_name, col_phone = st.columns(2)
                with col_name:
                    company_name = st.text_input("Nom de l'Entreprise *", value=contract_mgr.company_info.company_name)
                with col_phone:
                    phone = st.text_input("Téléphone *", value=contract_mgr.company_info.phone)
                
                address = st.text_area("Adresse *", value=contract_mgr.company_info.address, height=80)
                
                col_email, col_tax, col_rccm = st.columns(3)
                with col_email:
                    email = st.text_input("Email *", value=contract_mgr.company_info.email)
                with col_tax:
                    tax_id = st.text_input("N° Fiscal / SIRET", value=contract_mgr.company_info.tax_id)
                with col_rccm:
                    rccm_fin = st.text_input(
                        "RCCM",
                        value=getattr(contract_mgr.company_info, "rccm", "") or "",
                        help="Registre du Commerce et du Crédit Mobilier (affiché sur les factures si renseigné).",
                    )
                
                bank_info = st.text_input("Informations Bancaires", value=contract_mgr.company_info.bank_info)
                
                st.markdown("---")
                st.markdown("#### 🖋️ Cachet & signature électroniques (factures)")
                st.caption(
                    "Images PNG / JPEG recommandées (cachet rond, signature manuscrite scannée). "
                    "Affichées sur les factures HTML / impression PDF."
                )
                document_stamp_legend = st.text_input(
                    "Mention sous le cachet (ex. document conforme — signature électronique)",
                    value=getattr(contract_mgr.company_info, "document_stamp_legend", ""),
                )
                col_sig1, col_sig2 = st.columns(2)
                with col_sig1:
                    signatory_title = st.text_input(
                        "Fonction du signataire",
                        value=getattr(contract_mgr.company_info, "signatory_title", ""),
                        placeholder="Ex. Le Directeur Général",
                    )
                with col_sig2:
                    signatory_name = st.text_input(
                        "Nom du signataire",
                        value=getattr(contract_mgr.company_info, "signatory_name", ""),
                        placeholder="Ex. Prénom NOM",
                    )
                rm_stamp = st.checkbox("Retirer le cachet enregistré", key="fin_rm_stamp")
                rm_sig = st.checkbox("Retirer la signature enregistrée", key="fin_rm_sig")
                
                if getattr(contract_mgr.company_info, "stamp_base64", None):
                    try:
                        from PIL import Image as _PILImage
                        import io as _io

                        st.image(
                            _PILImage.open(
                                _io.BytesIO(base64.b64decode(contract_mgr.company_info.stamp_base64))
                            ),
                            width=160,
                            caption="Cachet actuel",
                        )
                    except Exception:
                        st.caption("Cachet enregistré (aperçu indisponible)")
                stamp_file = st.file_uploader("Télécharger un cachet", type=["png", "jpg", "jpeg", "webp"], key="fin_stamp_up")
                
                if getattr(contract_mgr.company_info, "signature_base64", None):
                    try:
                        from PIL import Image as _PILImage2
                        import io as _io2

                        st.image(
                            _PILImage2.open(
                                _io2.BytesIO(base64.b64decode(contract_mgr.company_info.signature_base64))
                            ),
                            width=220,
                            caption="Signature actuelle",
                        )
                    except Exception:
                        st.caption("Signature enregistrée (aperçu indisponible)")
                signature_file = st.file_uploader(
                    "Télécharger une image de signature", type=["png", "jpg", "jpeg", "webp"], key="fin_sig_up"
                )
                
                st.markdown("---")
                st.markdown("#### 🖼️ Logo de l'Entreprise")
                
                # Afficher le logo actuel si disponible (avant le formulaire)
                if contract_mgr.company_info.logo_base64:
                    try:
                        import base64
                        from PIL import Image
                        import io
                        logo_bytes = base64.b64decode(contract_mgr.company_info.logo_base64)
                        img = Image.open(io.BytesIO(logo_bytes))
                        st.image(img, width=200, caption="Logo actuel")
                    except Exception as e:
                        st.info(f"Logo actuel disponible mais erreur d'affichage: {e}")
                
                logo_file = st.file_uploader("Télécharger un nouveau Logo", type=['png', 'jpg', 'jpeg'], help="Format recommandé: PNG transparent, max 500x500px")
                
                if logo_file:
                    # Afficher un aperçu du nouveau logo
                    try:
                        from PIL import Image
                        import io
                        logo_file.seek(0)  # Réinitialiser le pointeur de fichier
                        img_bytes = logo_file.read()
                        img = Image.open(io.BytesIO(img_bytes))
                        st.image(img, width=200, caption="Nouveau logo (aperçu)")
                        # Réinitialiser pour pouvoir le lire à nouveau lors de la soumission
                        logo_file.seek(0)
                    except Exception as e:
                        st.warning(f"Erreur lors de l'affichage de l'aperçu: {e}")
                
                submit_button = st.form_submit_button("✅ ENREGISTRER LES INFORMATIONS", use_container_width=True)
                
                if submit_button:
                    contract_mgr.company_info.company_name = company_name
                    contract_mgr.company_info.address = address
                    contract_mgr.company_info.phone = phone
                    contract_mgr.company_info.email = email
                    contract_mgr.company_info.tax_id = tax_id
                    contract_mgr.company_info.rccm = (rccm_fin or "").strip()
                    contract_mgr.company_info.bank_info = bank_info
                    contract_mgr.company_info.document_stamp_legend = document_stamp_legend.strip()
                    contract_mgr.company_info.signatory_title = signatory_title.strip()
                    contract_mgr.company_info.signatory_name = signatory_name.strip()
                    if rm_stamp:
                        contract_mgr.company_info.stamp_base64 = None
                    if rm_sig:
                        contract_mgr.company_info.signature_base64 = None
                    if stamp_file and not rm_stamp:
                        stamp_file.seek(0)
                        contract_mgr.company_info.set_stamp_from_file(stamp_file)
                    if signature_file and not rm_sig:
                        signature_file.seek(0)
                        contract_mgr.company_info.set_signature_from_file(signature_file)
                    
                    if logo_file:
                        logo_file.seek(0)
                        if not contract_mgr.company_info.set_logo_from_file(logo_file):
                            st.warning("⚠️ Erreur lors de l'enregistrement du logo")
                    
                    if save_finance_company_profile(contract_mgr.company_info, contract_mgr.tenant_id):
                        st.success("✅ Informations enregistrées (factures & cachet / signature).")
                    else:
                        st.error("Échec de la sauvegarde sur disque.")
                    
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 8: GÉNÉRER FACTURES ---
        with finance_tabs[7]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🧾 Génération de Factures Mensuelles")
            
            if not contract_mgr.contracts:
                st.info("Aucun contrat disponible pour générer des factures.")
            else:
                # Sélection du contrat et de la période
                active_contracts = [c for c in contract_mgr.contracts if c.active]
                if active_contracts:
                    contract_options = {f"{c.contract_id} - {c.name} ({getattr(c, 'client_name', None) or 'N/A'})": c for c in active_contracts}
                    selected_contract_label = st.selectbox("Sélectionner un Contrat *", list(contract_options.keys()))
                    selected_contract = contract_options[selected_contract_label]
                    
                    col_period, col_month = st.columns(2)
                    with col_period:
                        period = st.selectbox("Période *", ["mois", "semaine", "jour", "annuel"], index=0)
                    with col_month:
                        if period == "mois":
                            month_year = st.date_input("Mois et Année", value=date.today(), help="Sélectionnez n'importe quel jour du mois souhaité")
                            period_value = month_year.strftime("%B %Y")
                        elif period == "annuel":
                            year = st.number_input("Année", min_value=2020, max_value=2030, value=datetime.now().year)
                            period_value = str(year)
                        else:
                            period_value = datetime.now().strftime("%d/%m/%Y")
                    
                    st.markdown("---")
                    
                    # Générer la facture automatiquement
                    invoice_html = contract_mgr.generate_invoice_html(selected_contract, period, period_value)
                    
                    # Afficher l'aperçu
                    st.markdown("#### 📄 Aperçu de la Facture")
                    st.markdown(invoice_html, unsafe_allow_html=True)
                    
                    # Boutons de téléchargement
                    st.markdown("---")
                    col_dl1, col_dl2 = st.columns(2)
                    
                    # Nettoyer le nom du fichier
                    clean_period = period_value.replace(' ', '_').replace('/', '_').replace(',', '')
                    
                    with col_dl1:
                        st.download_button(
                            label="📥 Télécharger en HTML",
                            data=invoice_html,
                            file_name=f"facture_{selected_contract.contract_id}_{clean_period}.html",
                            mime="text/html",
                            width='stretch',
                            help="Téléchargez et ouvrez dans votre navigateur pour imprimer"
                        )
                    
                    with col_dl2:
                        # Export pour impression PDF
                        st.download_button(
                            label="🖨️ Télécharger pour Impression (PDF)",
                            data=invoice_html,
                            file_name=f"facture_{selected_contract.contract_id}_{clean_period}_impression.html",
                            mime="text/html",
                            width='stretch',
                            help="Ouvrez dans votre navigateur et utilisez Ctrl+P → Imprimer en PDF"
                        )
                else:
                    st.info("Aucun contrat actif disponible.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 9: GRAPHIQUES ---
        with finance_tabs[8]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📈 Visualisation des Revenus")
            
            if not contract_mgr.contracts:
                st.info("Aucun contrat pour générer des graphiques.")
            else:
                # Graphique 1: Comparaison des revenus par période
                fig1 = go.Figure()
                
                periods = ["Jour", "Semaine", "Mois", "Année"]
                bcm_revenus = []
                hourly_revenus = []
                
                bcm_total = sum(c.revenu_jour for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active)
                hourly_total = sum(c.revenu_jour for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active)
                
                fig1.add_trace(go.Bar(name="BCM", x=["Jour", "Semaine", "Mois", "Année"], 
                                      y=[
                                          sum(c.revenu_jour for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active),
                                          sum(c.revenu_semaine for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active),
                                          sum(c.revenu_mois for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active),
                                          sum(c.revenu_annee for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active)
                                      ]))
                fig1.add_trace(go.Bar(name="Horaire", x=["Jour", "Semaine", "Mois", "Année"],
                                      y=[
                                          sum(c.revenu_jour for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active),
                                          sum(c.revenu_semaine for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active),
                                          sum(c.revenu_mois for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active),
                                          sum(c.revenu_annee for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active)
                                      ]))
                
                fig1.update_layout(
                    title="Revenus par Type de Contrat et Période",
                    xaxis_title="Période",
                    yaxis_title="Revenus ($)",
                    barmode='group',
                    height=500
                )
                st.plotly_chart(fig1, width='stretch')
                
                # Graphique 2: Répartition des revenus totaux
                total_bcm = sum(c.revenu_annee for c in contract_mgr.contracts if c.contract_type == "BCM" and c.active)
                total_hourly = sum(c.revenu_annee for c in contract_mgr.contracts if c.contract_type == "HOURLY" and c.active)
                
                if total_bcm > 0 or total_hourly > 0:
                    fig2 = px.pie(
                        values=[total_bcm, total_hourly],
                        names=["BCM (Volume)", "Horaire"],
                        title="Répartition des Revenus Annuels par Type de Contrat"
                    )
                    st.plotly_chart(fig2, width='stretch')
            
        st.markdown('</div>', unsafe_allow_html=True)

# --- RH ---
if "RH" in tab_dict:
    with tab_dict["RH"]:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("👥 GESTION DES RESSOURCES HUMAINES")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # ===== ONGLETS INTERNES RH =====
        rh_tabs = st.tabs(["📋 Liste Employés", "➕ Ajouter Employé", "🗑️ Désactiver/Supprimer Employé", "🚛 Assigner Machines", "✅ Présence", "🏆 Classements", "👥 Par Équipe"])
        
        # --- TAB 1: LISTE DES EMPLOYÉS ---
        with rh_tabs[0]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📋 Liste Complète des Employés")
            
            df_staff = staff_mgr.get_all_staff_df()
            if not df_staff.empty and len(df_staff) > 0:
                # Boutons d'export et d'impression
                col_export1, col_export2 = st.columns(2)
                with col_export1:
                    # Export Excel/CSV
                    from io import BytesIO
                    try:
                        # Essayer d'abord avec openpyxl pour un vrai fichier Excel
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_staff.to_excel(writer, sheet_name='Liste Employés', index=False)
                        excel_data = output.getvalue()
                        st.download_button(
                            label="📥 Télécharger en Excel (.xlsx)",
                            data=excel_data,
                            file_name=f"liste_employes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            width='stretch',
                            help="Format Excel natif"
                        )
                    except (ImportError, ModuleNotFoundError):
                        # Si openpyxl n'est pas installé, proposer CSV (compatible Excel)
                        csv_data = df_staff.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label="📥 Télécharger en CSV (compatible Excel)",
                            data=csv_data,
                            file_name=f"liste_employes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            width='stretch',
                            help="Format CSV (s'ouvre dans Excel). Installez 'openpyxl' pour un format Excel natif: pip install openpyxl"
                        )
                    except Exception as e:
                        # Autre erreur, utiliser CSV
                        csv_data = df_staff.to_csv(index=False, encoding='utf-8-sig')
                        st.download_button(
                            label="📥 Télécharger en CSV",
                            data=csv_data,
                            file_name=f"liste_employes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            width='stretch',
                            help="Format CSV (ouvrable dans Excel)"
                        )
                
                with col_export2:
                    # Export CSV supplémentaire (toujours disponible)
                    csv_data = df_staff.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📄 Télécharger en CSV",
                        data=csv_data,
                        file_name=f"liste_employes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        width='stretch',
                        help="Format CSV standard (séparateur virgule)"
                    )
                
                # Bouton d'impression sur une nouvelle ligne
                st.markdown("---")
                col_print = st.columns(1)
                with col_print[0]:
                    # Impression - Générer un HTML formaté pour l'impression
                    html_content = f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <title>Liste des Employés - GOOD ENGINEERS</title>
                        <style>
                            @media print {{
                                @page {{
                                    size: A4 landscape;
                                    margin: 1cm;
                                }}
                                body {{
                                    font-family: Arial, sans-serif;
                                    font-size: 10pt;
                                }}
                                table {{
                                    width: 100%;
                                    border-collapse: collapse;
                                }}
                                th, td {{
                                    border: 1px solid #ddd;
                                    padding: 8px;
                                    text-align: left;
                                }}
                                th {{
                                    background-color: #F5B800;
                                    color: #000;
                                    font-weight: bold;
                                }}
                                tr:nth-child(even) {{
                                    background-color: #f2f2f2;
                                }}
                                h1 {{
                                    color: #000;
                                    text-align: center;
                                }}
                                .header {{
                                    text-align: center;
                                    margin-bottom: 20px;
                                }}
                            }}
                            body {{
                                font-family: Arial, sans-serif;
                            }}
                            table {{
                                width: 100%;
                                border-collapse: collapse;
                            }}
                            th, td {{
                                border: 1px solid #ddd;
                                padding: 8px;
                                text-align: left;
                            }}
                            th {{
                                background-color: #F5B800;
                                color: #000;
                                font-weight: bold;
                            }}
                            tr:nth-child(even) {{
                                background-color: #f2f2f2;
                            }}
                            h1 {{
                                color: #000;
                                text-align: center;
                            }}
                            .header {{
                                text-align: center;
                                margin-bottom: 20px;
                            }}
                        </style>
                    </head>
                    <body>
                        <div class="header">
                            <h1>GOOD ENGINEERS</h1>
                            <h2>Liste des Employés</h2>
                            <p>Date d'édition: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}</p>
                        </div>
                        {df_staff.to_html(index=False, classes='table', table_id='table_employes')}
                    </body>
                    </html>
                    """
                    st.download_button(
                        label="🖨️ Imprimer (HTML)",
                        data=html_content,
                        file_name=f"liste_employes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                        mime="text/html",
                        width='stretch',
                        help="Téléchargez et ouvrez le fichier HTML dans votre navigateur pour l'imprimer"
                    )
                
                st.markdown("---")
                
                # Enrichir le DataFrame avec le type d'opérateur
                if "Machine Assignée" in df_staff.columns:
                    df_machines_display = manager.get_summary_dataframe()
                    
                    def get_operator_type(row):
                        machine = row.get("Machine Assignée", "Aucune")
                        if machine != "Aucune":
                            machine_row = df_machines_display[df_machines_display['ID'] == machine]
                            if not machine_row.empty:
                                machine_type = machine_row.iloc[0]['Type']
                                machine_type_upper = machine_type.upper()
                                
                                # Types de chargement : Pelle, Excavatrice, Chargeuse, Bulldozer, Tractopelle, Grader, Benne
                                loader_types = ['PELLE', 'EXCAVATRICE', 'CHARGEUSE', 'CHARGEUR', 'BULLDOZER', 'TRACTOPELLE', 'GRADER', 'BENNE']
                                if any(lt in machine_type_upper for lt in loader_types):
                                    return "🚛 Chargement"
                                
                                # Types de transport : Dumper, Camion, Citerne
                                dumper_types = ['DUMPER', 'CAMION', 'CITERNE']
                                if any(dt in machine_type_upper for dt in dumper_types):
                                    return "🚚 Camion"
                        return "❌ Non assigné"
                    
                    df_staff['Type Opérateur'] = df_staff.apply(get_operator_type, axis=1)
                    
                    # Ajouter une colonne pour indiquer si l'employé a un compte (même entreprise)
                    existing_usernames_list = [u['user'] for u in user_mgr.users_in_current_tenant()]
                    
                    def has_account(row):
                        name = row.get("Nom", "")
                        # Chercher si un compte existe avec un nom d'utilisateur similaire au nom de l'employé
                        name_normalized = name.lower().replace(' ', '_').replace('-', '_')
                        name_words = set(name.lower().split())
                        
                        for username in existing_usernames_list:
                            u_lower = username.lower()
                            # Correspondance exacte ou proche (nom d'utilisateur = nom employé normalisé)
                            if u_lower == name_normalized:
                                return f"✅ {username}"
                            # Correspondance par mots communs (au moins 2 mots)
                            u_words = set(u_lower.replace('_', ' ').replace('-', ' ').split())
                            common_words = name_words.intersection(u_words)
                            if len(common_words) >= 2 and len(common_words) >= min(len(name_words), len(u_words)) * 0.5:
                                return f"✅ {username}"
                            # Correspondance par sous-chaîne significative (au moins 4 caractères)
                            if len(name_normalized) >= 4 and name_normalized in u_lower:
                                return f"✅ {username}"
                            if len(u_lower) >= 4 and u_lower in name_normalized:
                                return f"✅ {username}"
                        return "❌ Aucun compte"
                    
                    df_staff['Compte Utilisateur'] = df_staff.apply(has_account, axis=1)
                    
                    # Réorganiser les colonnes pour mettre "Type Opérateur" et "Compte Utilisateur" en avant
                    cols = df_staff.columns.tolist()
                    if "Type Opérateur" in cols and "Machine Assignée" in cols:
                        cols.remove("Type Opérateur")
                        cols.insert(cols.index("Machine Assignée") + 1, "Type Opérateur")
                    if "Compte Utilisateur" in cols:
                        cols.remove("Compte Utilisateur")
                        if "Type Opérateur" in cols:
                            cols.insert(cols.index("Type Opérateur") + 1, "Compte Utilisateur")
                        else:
                            cols.append("Compte Utilisateur")
                        df_staff = df_staff[cols]
                
                st.dataframe(df_staff, width='stretch', hide_index=True)
                
                # Statistiques globales
                st.markdown("---")
                if "Rôle" in df_staff.columns:
                    col1, col2, col3, col4, col5, col6 = st.columns(6)
                    col1.metric("Total", len(df_staff))
                    col2.metric("Opérateurs", len(df_staff[df_staff["Rôle"] == "Operateur"]))
                    col3.metric("Sup. Production", len(df_staff[df_staff["Rôle"] == "Superviseur Production"]))
                    col4.metric("Sup. Mécanique", len(df_staff[df_staff["Rôle"] == "Superviseur Mecanicien"]))
                    col5.metric("Mécaniciens", len(df_staff[df_staff["Rôle"] == "Mecanicien"]))
                    col6.metric("Électriciens", len(df_staff[df_staff["Rôle"] == "Electricien"]))
                    
                    # Deuxième ligne pour les ingénieurs
                    st.markdown("---")
                    col_eng = st.columns(1)
                    with col_eng[0]:
                        st.metric("Ingénieurs", len(df_staff[df_staff["Rôle"] == "Ingenieur"]))
                else:
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Employés", len(df_staff))
                    col2.metric("Opérateurs", 0)
                    col3.metric("Superviseurs", 0)
                    col4.metric("Ingénieurs", 0)
            else:
                st.info("Aucun employé enregistré.")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 2: AJOUTER UN EMPLOYÉ ---
        with rh_tabs[1]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("➕ Enregistrer un Nouvel Employé")
            st.caption("ℹ️ Le numéro matricule sera généré automatiquement")
            
            with st.form("add_employee_form"):
                nom = st.text_input("Nom Complet *", placeholder="Ex: Moussa Koné")
                
                col_role, col_equipe = st.columns(2)
                with col_role:
                    role = st.selectbox("Rôle *", [
                        "Operateur", 
                        "Superviseur Production",
                        "Superviseur Mecanicien",
                        "Ingenieur",
                        "Mecanicien",
                        "Electricien"
                    ])
                with col_equipe:
                    equipe = st.selectbox("Équipe *", ["A", "B", "C"])
                
                col_shift, col_date = st.columns(2)
                with col_shift:
                    shift = st.selectbox("Type de Shift", ["3x8", "Standard", "Jour", "Nuit"])
                with col_date:
                    date_arrivee = st.date_input("Date d'Arrivée *", value=date.today())
                
                if st.form_submit_button("✅ ENREGISTRER L'EMPLOYÉ", use_container_width=True):
                    if nom:
                        # Le matricule sera généré automatiquement par add_employee
                        if staff_mgr.add_employee(nom, role, equipe, shift, None, date_arrivee):
                            # Récupérer le matricule généré pour l'afficher
                            new_employee = staff_mgr.staff[-1]
                            # Enregistrer dans les logs d'audit
                            current_user = st.session_state.get('username', 'Système')
                            audit_mgr.log_action(
                                "CREATE", "EMPLOYEE", new_employee.matricule, new_employee.name,
                                current_user,
                                changes={"Rôle": role, "Équipe": equipe, "Shift": shift, "Date Arrivée": str(date_arrivee)},
                                details=f"Création d'un nouvel employé"
                            )
                            st.success(f"✅ Employé {nom} enregistré avec succès ! Matricule: {new_employee.matricule}")
                            st.rerun()
                        else:
                            st.error("Erreur lors de l'enregistrement.")
                    else:
                        st.warning("⚠️ Veuillez remplir au moins le nom.")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 3: DÉSACTIVER/SUPPRIMER EMPLOYÉ ---
        with rh_tabs[2]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🗑️ Désactiver/Supprimer un Employé")
            st.caption("ℹ️ La désactivation conserve les données historiques. La suppression est définitive.")
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%); 
                        padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #F5B800;">
                <h4 style="color: #F5B800; margin: 0 0 15px 0;">ℹ️ Différence entre Désactivation et Suppression :</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                    <div style="background: rgba(245, 184, 0, 0.1); padding: 15px; border-radius: 10px; border-left: 4px solid #F5B800;">
                        <strong style="color: #F5B800; font-size: 16px;">🔴 Désactivation (Recommandé)</strong>
                        <p style="color: #e0e0e0; margin: 10px 0 0 0; font-size: 14px;">
                            • Conserve toutes les données historiques<br>
                            • L'employé reste dans la base de données<br>
                            • Peut être réactivé à tout moment<br>
                            • Idéal pour les départs temporaires
                        </p>
                    </div>
                    <div style="background: rgba(255, 69, 0, 0.1); padding: 15px; border-radius: 10px; border-left: 4px solid #FF4500;">
                        <strong style="color: #FF4500; font-size: 16px;">🗑️ Suppression Définitive</strong>
                        <p style="color: #e0e0e0; margin: 10px 0 0 0; font-size: 14px;">
                            • Supprime l'employé de la base de données<br>
                            • Toutes les données sont perdues définitivement<br>
                            • Action irréversible<br>
                            • Utiliser uniquement en cas d'erreur d'enregistrement
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("---")
            
            # Section 1: Désactiver un employé
            st.markdown("#### 🔴 Désactiver un Employé")
            with st.form("desactiver_employee_form"):
                # Liste des employés actifs uniquement
                active_employees = staff_mgr.get_active_staff()
                if active_employees:
                    employee_names_active = [f"{e.name} ({e.matricule})" for e in active_employees]
                    selected_employee_to_deactivate = st.selectbox(
                        "Sélectionner l'employé à désactiver *",
                        ["Sélectionner..."] + employee_names_active,
                        key="deactivate_emp"
                    )
                    
                    col_date1, col_reason = st.columns(2)
                    with col_date1:
                        date_depart = st.date_input("Date de départ", value=date.today(), key="date_depart_deactivate")
                    
                    with col_reason:
                        raison_depart = st.text_area("Raison du départ (optionnel)", key="raison_depart", height=100)
                    
                    if st.form_submit_button("🔴 DÉSACTIVER L'EMPLOYÉ", use_container_width=True, type="primary"):
                        if selected_employee_to_deactivate and selected_employee_to_deactivate != "Sélectionner...":
                            # Extraire le matricule
                            matricule = selected_employee_to_deactivate.split("(")[1].split(")")[0]
                            
                            # Vérifier si l'employé a des machines assignées
                            emp = staff_mgr.get_employee_by_matricule(matricule)
                            if emp:
                                machines_assignees = getattr(emp, 'assigned_machine', "Aucune")
                                if machines_assignees != "Aucune":
                                    st.warning(f"⚠️ L'employé a une machine assignée ({machines_assignees}). Pensez à réassigner la machine avant de désactiver.")
                                
                                # Désactiver l'employé
                                if staff_mgr.desactiver_employee(matricule, date_depart):
                                    # Enregistrer dans les logs d'audit
                                    current_user = st.session_state.get('username', 'Système')
                                    audit_mgr.log_action(
                                        "DEACTIVATE", "EMPLOYEE", matricule, emp.name,
                                        current_user,
                                        changes={"Statut": {"before": "Actif", "after": "Inactif"}, "Date Départ": str(date_depart)},
                                        details=f"Désactivation de l'employé"
                                    )
                                    st.success(f"✅ Employé {emp.name} désactivé avec succès. Toutes les données historiques sont conservées.")
                                    st.info(f"📊 Statut: Inactif | Date de départ: {date_depart.strftime('%d/%m/%Y')}")
                                    st.rerun()
                                else:
                                    st.error("❌ Erreur lors de la désactivation.")
                            else:
                                st.error("❌ Employé non trouvé.")
                        else:
                            st.warning("⚠️ Veuillez sélectionner un employé.")
                else:
                    st.info("📭 Aucun employé actif à désactiver.")
            
            st.markdown("---")
            
            # Section 2: Réactiver un employé
            st.markdown("#### 🟢 Réactiver un Employé")
            with st.form("reactiver_employee_form"):
                # Liste des employés inactifs uniquement
                inactive_employees = staff_mgr.get_inactive_staff()
                if inactive_employees:
                    employee_names_inactive = [f"{e.name} ({e.matricule}) - Départ: {getattr(e, 'date_depart', 'N/A')}" for e in inactive_employees]
                    selected_employee_to_reactivate = st.selectbox(
                        "Sélectionner l'employé à réactiver *",
                        ["Sélectionner..."] + employee_names_inactive,
                        key="reactivate_emp"
                    )
                    
                    if st.form_submit_button("🟢 RÉACTIVER L'EMPLOYÉ", use_container_width=True, type="primary"):
                        if selected_employee_to_reactivate and selected_employee_to_reactivate != "Sélectionner...":
                            # Extraire le matricule
                            matricule = selected_employee_to_reactivate.split("(")[1].split(")")[0]
                            
                            # Réactiver l'employé
                            if staff_mgr.reactiver_employee(matricule):
                                emp = staff_mgr.get_employee_by_matricule(matricule)
                                # Enregistrer dans les logs d'audit
                                current_user = st.session_state.get('username', 'Système')
                                audit_mgr.log_action(
                                    "REACTIVATE", "EMPLOYEE", matricule, emp.name,
                                    current_user,
                                    changes={"Statut": {"before": "Inactif", "after": "Actif"}},
                                    details=f"Réactivation de l'employé"
                                )
                                st.success(f"✅ Employé {emp.name} réactivé avec succès.")
                                st.info(f"📊 Statut: Actif | Date d'arrivée: {emp.date_arrivee.strftime('%d/%m/%Y')}")
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la réactivation.")
                        else:
                            st.warning("⚠️ Veuillez sélectionner un employé.")
                else:
                    st.info("📭 Aucun employé inactif à réactiver.")
            
            st.markdown("---")
            
            # Section 3: Supprimer définitivement un employé
            st.markdown("#### ⚠️ Supprimer Définitivement un Employé")
            st.warning("🚨 **ATTENTION** : La suppression est définitive et irréversible. Toutes les données de l'employé seront perdues. Utilisez la désactivation si vous souhaitez conserver les données historiques.")
            
            with st.form("supprimer_employee_form"):
                # Liste de tous les employés (actifs et inactifs) pour la suppression
                all_employees_for_deletion = staff_mgr.staff
                if all_employees_for_deletion:
                    employee_names_all = [f"{e.name} ({e.matricule}) - Statut: {getattr(e, 'statut', 'Actif')}" for e in all_employees_for_deletion]
                    selected_employee_to_delete = st.selectbox(
                        "Sélectionner l'employé à supprimer définitivement *",
                        ["Sélectionner..."] + employee_names_all,
                        key="delete_emp"
                    )
                    
                    # Confirmation de suppression
                    confirm_delete = st.checkbox(
                        "⚠️ Je confirme vouloir supprimer définitivement cet employé et toutes ses données",
                        key="confirm_delete_checkbox"
                    )
                    
                    # Avertissement supplémentaire
                    if selected_employee_to_delete and selected_employee_to_delete != "Sélectionner...":
                        matricule_to_delete = selected_employee_to_delete.split("(")[1].split(")")[0]
                        emp_to_delete = staff_mgr.get_employee_by_matricule(matricule_to_delete)
                        if emp_to_delete:
                            st.error(f"🚨 **SUPPRESSION DÉFINITIVE** : Vous êtes sur le point de supprimer définitivement {emp_to_delete.name} ({emp_to_delete.matricule}). Cette action est irréversible et toutes les données (production, cycles, présence, etc.) seront perdues.")
                            
                            # Afficher les informations de l'employé
                            col_info1, col_info2 = st.columns(2)
                            with col_info1:
                                st.info(f"**Nom :** {emp_to_delete.name}\n\n**Matricule :** {emp_to_delete.matricule}\n\n**Rôle :** {emp_to_delete.role}")
                            with col_info2:
                                st.info(f"**Équipe :** {emp_to_delete.team}\n\n**Production totale :** {getattr(emp_to_delete, 'production_tonnes', 0)} T\n\n**Machine assignée :** {getattr(emp_to_delete, 'assigned_machine', 'Aucune')}")
                else:
                    st.info("📭 Aucun employé à supprimer.")
                    selected_employee_to_delete = None
                    confirm_delete = False
                
                # Le bouton doit toujours être présent dans le formulaire
                submitted = st.form_submit_button("🗑️ SUPPRIMER DÉFINITIVEMENT", use_container_width=True, type="primary")
                
                if submitted:
                    if all_employees_for_deletion and selected_employee_to_delete and selected_employee_to_delete != "Sélectionner..." and confirm_delete:
                        # Extraire le matricule
                        matricule = selected_employee_to_delete.split("(")[1].split(")")[0]
                        
                        # Vérifier si l'employé existe
                        emp = staff_mgr.get_employee_by_matricule(matricule)
                        if emp:
                            emp_name = emp.name
                            emp_matricule = emp.matricule
                            
                            # Vérifier si l'employé a des machines assignées
                            machines_assignees = getattr(emp, 'assigned_machine', "Aucune")
                            if machines_assignees != "Aucune":
                                st.warning(f"⚠️ L'employé a une machine assignée ({machines_assignees}). La machine sera libérée après suppression.")
                            
                            # Vérifier si l'employé a un compte utilisateur (même entreprise)
                            existing_usernames = [u['user'] for u in user_mgr.users_in_current_tenant()]
                            has_account = any(emp.name.lower() in u.lower() or u.lower() in emp.name.lower() for u in existing_usernames)
                            if has_account:
                                st.warning(f"⚠️ L'employé a un compte utilisateur associé. Le compte ne sera pas supprimé automatiquement.")
                            
                            # Supprimer l'employé
                            if staff_mgr.remove_employee(matricule):
                                # Enregistrer dans les logs d'audit
                                current_user = st.session_state.get('username', 'Système')
                                audit_mgr.log_action(
                                    "DELETE", "EMPLOYEE", emp_matricule, emp_name,
                                    current_user,
                                    changes={"Action": "Suppression définitive"},
                                    details=f"Suppression définitive de l'employé {emp_name} ({emp_matricule})"
                                )
                                st.success(f"✅ Employé {emp_name} ({emp_matricule}) supprimé définitivement de la base de données.")
                                st.info("📊 Toutes les données de cet employé ont été perdues. Cette action est irréversible.")
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la suppression.")
                        else:
                            st.error("❌ Employé non trouvé.")
                    elif not confirm_delete:
                        st.warning("⚠️ Veuillez cocher la case de confirmation pour supprimer l'employé.")
                    elif not selected_employee_to_delete or selected_employee_to_delete == "Sélectionner...":
                        st.warning("⚠️ Veuillez sélectionner un employé.")
                    else:
                        st.warning("⚠️ Aucun employé disponible pour suppression.")
            
            st.markdown("---")
            
            # Section 4: Statistiques
            st.markdown("#### 📊 Statistiques")
            col_stat1, col_stat2, col_stat3 = st.columns(3)
            with col_stat1:
                total_actifs = len(staff_mgr.get_active_staff())
                st.metric("Employés Actifs", total_actifs)
            with col_stat2:
                total_inactifs = len(staff_mgr.get_inactive_staff())
                st.metric("Employés Inactifs", total_inactifs)
            with col_stat3:
                total_general = len(staff_mgr.staff)
                st.metric("Total (Base de données)", total_general)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 4: ASSIGNER MACHINES AUX OPÉRATEURS ---
        with rh_tabs[3]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🚛 Assignation de Machines aux Opérateurs")
            st.caption("ℹ️ Assignez des machines aux opérateurs pour déterminer leur type (Chargement ou Camion)")
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%); 
                        padding: 20px; border-radius: 15px; margin: 20px 0; border: 2px solid #F5B800;">
                <h4 style="color: #F5B800; margin: 0 0 15px 0;">📋 Types d'Opérateurs :</h4>
                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 20px;">
                    <div style="background: rgba(245, 184, 0, 0.1); padding: 15px; border-radius: 10px; border-left: 4px solid #F5B800;">
                        <strong style="color: #F5B800; font-size: 18px;">🚛 Opérateur de Chargement</strong>
                        <p style="color: #e0e0e0; margin: 10px 0 0 0; font-size: 14px;">
                            Machines: <strong>Pelle</strong>, <strong>Chargeuse</strong>, <strong>Excavatrice</strong><br>
                            Exemples: EX-01, WL-01
                        </p>
                    </div>
                    <div style="background: rgba(38, 166, 154, 0.1); padding: 15px; border-radius: 10px; border-left: 4px solid #26a69a;">
                        <strong style="color: #26a69a; font-size: 18px;">🚚 Opérateur de Camion</strong>
                        <p style="color: #e0e0e0; margin: 10px 0 0 0; font-size: 14px;">
                            Machines: <strong>Dumper</strong><br>
                            Exemples: DT-01, DT-02
                        </p>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("---")
            
            with st.form("assign_machine_form"):
                col_op, col_mach = st.columns(2)
                
                with col_op:
                    # Liste des opérateurs
                    operateurs = [e for e in staff_mgr.get_active_staff() if e.role == "Operateur"]
                    if operateurs:
                        operateur_names = [e.name for e in operateurs]
                        selected_operator = st.selectbox(
                            "Sélectionner l'Opérateur *",
                            ["Sélectionner..."] + operateur_names,
                            key="assign_op"
                        )
                        
                        # Afficher la machine actuellement assignée et le type
                        if selected_operator and selected_operator != "Sélectionner...":
                            current_emp = next((e for e in operateurs if e.name == selected_operator), None)
                            if current_emp:
                                current_machine = getattr(current_emp, 'assigned_machine', "Aucune")
                                st.info(f"**Machine actuellement assignée :** {current_machine}")
                                
                                # Déterminer le type d'opérateur
                                if current_machine != "Aucune":
                                    df_machines_check = manager.get_summary_dataframe()
                                    machine_row = df_machines_check[df_machines_check['ID'] == current_machine]
                                    if not machine_row.empty:
                                        machine_type = machine_row.iloc[0]['Type']
                                        machine_type_upper = machine_type.upper()
                                        loader_types = ['PELLE', 'EXCAVATRICE', 'CHARGEUSE', 'CHARGEUR', 'BULLDOZER', 'TRACTOPELLE', 'GRADER', 'BENNE']
                                        dumper_types = ['DUMPER', 'CAMION', 'CITERNE']
                                        
                                        if any(lt in machine_type_upper for lt in loader_types):
                                            st.success("✅ Type actuel: **Opérateur de Chargement** 🚛")
                                        elif any(dt in machine_type_upper for dt in dumper_types):
                                            st.success("✅ Type actuel: **Opérateur de Camion** 🚚")
                                        else:
                                            st.info(f"ℹ️ Type de machine: {machine_type}")
                                    else:
                                        st.warning("⚠️ Machine non trouvée dans le système.")
                                else:
                                    st.warning("⚠️ Aucune machine assignée - Type: **Non défini**")
                    else:
                        st.warning("⚠️ Aucun opérateur enregistré. Ajoutez d'abord un opérateur dans l'onglet 'Ajouter Employé'.")
                        selected_operator = None
                
                with col_mach:
                    # Liste des machines disponibles
                    df_machines_assign = manager.get_summary_dataframe()
                    available_machines = df_machines_assign['ID'].tolist()
                    
                    if available_machines:
                        selected_machine = st.selectbox(
                            "Sélectionner la Machine *",
                            ["Aucune"] + available_machines,
                            key="assign_machine"
                        )
                        
                        # Afficher le type de machine sélectionnée
                        if selected_machine and selected_machine != "Aucune":
                            machine_info = df_machines_assign[df_machines_assign['ID'] == selected_machine]
                            if not machine_info.empty:
                                machine_type = machine_info.iloc[0]['Type']
                                machine_model = machine_info.iloc[0].get('Modèle', 'N/A')
                                st.info(f"**Type de machine :** {machine_type} ({machine_model})")
                                
                                # Prévisualiser le type d'opérateur qui sera créé
                                machine_type_upper = machine_type.upper()
                                loader_types = ['PELLE', 'EXCAVATRICE', 'CHARGEUSE', 'CHARGEUR', 'BULLDOZER', 'TRACTOPELLE', 'GRADER', 'BENNE']
                                dumper_types = ['DUMPER', 'CAMION', 'CITERNE']
                                
                                if any(lt in machine_type_upper for lt in loader_types):
                                    st.markdown("""
                                    <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%); 
                                                padding: 15px; border-radius: 10px; border: 2px solid #F5B800; margin-top: 10px;">
                                        <p style="color: #F5B800; font-size: 16px; font-weight: 700; margin: 0;">
                                            🎯 Cet opérateur sera un <strong>Opérateur de Chargement</strong> 🚛
                                        </p>
                                    </div>
                                    """, unsafe_allow_html=True)
                                elif any(dt in machine_type_upper for dt in dumper_types):
                                    st.markdown("""
                                    <div style="background: linear-gradient(135deg, rgba(38, 166, 154, 0.2) 0%, rgba(0, 137, 123, 0.2) 100%); 
                                                padding: 15px; border-radius: 10px; border: 2px solid #26a69a; margin-top: 10px;">
                                        <p style="color: #26a69a; font-size: 16px; font-weight: 700; margin: 0;">
                                            🎯 Cet opérateur sera un <strong>Opérateur de Camion</strong> 🚚
                                        </p>
                                    </div>
                                    """, unsafe_allow_html=True)
                    else:
                        st.warning("⚠️ Aucune machine disponible.")
                        selected_machine = None
                
                st.markdown("---")
                
                if st.form_submit_button("✅ ASSIGNER LA MACHINE", use_container_width=True):
                    if selected_operator and selected_operator != "Sélectionner..." and selected_machine:
                        if selected_machine == "Aucune":
                            # Retirer l'assignation
                            for e in staff_mgr.staff:
                                if e.name == selected_operator:
                                    e.assigned_machine = "Aucune"
                            st.success(f"✅ Machine retirée pour {selected_operator}")
                        else:
                            # Assigner la machine
                            if staff_mgr.assign_machine(selected_operator, selected_machine):
                                # Déterminer le type
                                machine_info = df_machines_assign[df_machines_assign['ID'] == selected_machine]
                                machine_type = machine_info.iloc[0]['Type'] if not machine_info.empty else "N/A"
                                machine_type_upper = machine_type.upper()
                                
                                loader_types = ['PELLE', 'EXCAVATRICE', 'CHARGEUSE', 'CHARGEUR', 'BULLDOZER', 'TRACTOPELLE', 'GRADER', 'BENNE']
                                dumper_types = ['DUMPER', 'CAMION', 'CITERNE']
                                
                                if any(lt in machine_type_upper for lt in loader_types):
                                    st.success(f"✅ Machine {selected_machine} assignée à {selected_operator} ! Cet opérateur est maintenant un **Opérateur de Chargement** 🚛")
                                elif any(dt in machine_type_upper for dt in dumper_types):
                                    st.success(f"✅ Machine {selected_machine} assignée à {selected_operator} ! Cet opérateur est maintenant un **Opérateur de Camion** 🚚")
                                else:
                                    st.success(f"✅ Machine {selected_machine} assignée à {selected_operator} !")
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de l'assignation.")
                    else:
                        st.warning("⚠️ Veuillez sélectionner un opérateur et une machine.")
            
            st.markdown("---")
            st.markdown("#### 📋 Liste des Assignations Actuelles")
            
            # Afficher la liste des assignations avec types
            assignation_data = []
            for emp in staff_mgr.staff:
                if emp.role == "Operateur":
                    assigned_machine = getattr(emp, 'assigned_machine', "Aucune")
                    machine_type = "N/A"
                    operator_type = "❌ Non assigné"
                    
                    if assigned_machine != "Aucune":
                        df_machines_display = manager.get_summary_dataframe()
                        machine_row = df_machines_display[df_machines_display['ID'] == assigned_machine]
                        if not machine_row.empty:
                            machine_type = machine_row.iloc[0]['Type']
                            machine_type_upper = machine_type.upper()
                            loader_types = ['PELLE', 'EXCAVATRICE', 'CHARGEUSE', 'CHARGEUR', 'BULLDOZER', 'TRACTOPELLE', 'GRADER', 'BENNE']
                            dumper_types = ['DUMPER', 'CAMION', 'CITERNE']
                            
                            if any(lt in machine_type_upper for lt in loader_types):
                                operator_type = "🚛 Opérateur de Chargement"
                            elif any(dt in machine_type_upper for dt in dumper_types):
                                operator_type = "🚚 Opérateur de Camion"
                    
                    assignation_data.append({
                        "Nom": emp.name,
                        "Matricule": emp.matricule,
                        "Machine Assignée": assigned_machine,
                        "Type Machine": machine_type,
                        "Type Opérateur": operator_type
                    })
            
            if assignation_data:
                df_assignations = pd.DataFrame(assignation_data)
                st.dataframe(df_assignations, width='stretch', hide_index=True)
                
                # Statistiques des types d'opérateurs
                st.markdown("---")
                st.markdown("#### 📊 Statistiques des Types d'Opérateurs")
                col_stat1, col_stat2, col_stat3 = st.columns(3)
                with col_stat1:
                    total_ops = len([a for a in assignation_data if a["Machine Assignée"] != "Aucune"])
                    st.metric("Opérateurs Assignés", total_ops)
                with col_stat2:
                    loaders = len([a for a in assignation_data if "Chargement" in a["Type Opérateur"]])
                    st.metric("🚛 Chargement", loaders)
                with col_stat3:
                    dumpers = len([a for a in assignation_data if "Camion" in a["Type Opérateur"]])
                    st.metric("🚚 Camion", dumpers)
            else:
                st.info("Aucune assignation enregistrée.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 4: GESTION DE PRÉSENCE ---
        with rh_tabs[3]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("✅ Enregistrement de Présence")
            
            with st.form("presence_form"):
                col_mat, col_date = st.columns(2)
                with col_mat:
                    matricules = [e.matricule for e in staff_mgr.staff]
                    if matricules:
                        matricule_sel = st.selectbox("Matricule Employé *", matricules)
                    else:
                        st.warning("Aucun employé enregistré.")
                        matricule_sel = None
                
                with col_date:
                    date_presence = st.date_input("Date de Présence *", value=date.today())
                
                col_statut, col_retard = st.columns(2)
                with col_statut:
                    statut = st.selectbox("Statut *", ["present", "absent"])
                with col_retard:
                    retard = st.checkbox("Retard", value=False)
                
                if st.form_submit_button("✅ ENREGISTRER PRÉSENCE", use_container_width=True):
                    if matricule_sel:
                        if staff_mgr.enregistrer_presence(matricule_sel, date_presence, statut, retard):
                            st.success(f"✅ Présence enregistrée pour {matricule_sel} le {date_presence.strftime('%d/%m/%Y')}")
                            st.rerun()
                        else:
                            st.error("Erreur lors de l'enregistrement.")
                    else:
                        st.warning("⚠️ Veuillez sélectionner un matricule.")
            
            st.markdown("---")
            st.markdown("#### 📊 Vue d'Ensemble des Présences")
            
            # Tableau récapitulatif des présences
            presence_data = []
            for emp in staff_mgr.staff:
                # Utiliser getattr avec valeurs par défaut pour compatibilité avec objets en cache
                presence_data.append({
                    "Matricule": emp.matricule,
                    "Nom": emp.name,
                    "Rôle": emp.role,
                    "Équipe": emp.team,
                    "Jours Sans Retard/Absence": getattr(emp, 'jours_sans_retard_absence', 0),
                    "Total Retards": getattr(emp, 'total_retards', 0),
                    "Total Absences": getattr(emp, 'total_absences', 0)
                })
            
            if presence_data:
                df_presence = pd.DataFrame(presence_data)
                st.dataframe(df_presence, width='stretch', hide_index=True)
            else:
                st.info("Aucune donnée de présence.")
            
            st.markdown("---")
            st.markdown("#### 🏭 Enregistrement de Production")
            st.caption("Enregistrez la production quotidienne des opérateurs")
            
            with st.form("production_form"):
                col_mat_prod, col_tonnes = st.columns(2)
                with col_mat_prod:
                    operateurs = [e for e in staff_mgr.get_active_staff() if e.role == "Operateur"]
                    if operateurs:
                        matricules_ops = [e.matricule for e in operateurs]
                        matricule_prod = st.selectbox("Matricule Opérateur *", matricules_ops, key="prod_mat")
                    else:
                        st.warning("Aucun opérateur enregistré.")
                        matricule_prod = None
                
                with col_tonnes:
                    tonnes = st.number_input("Production (Tonnes) *", min_value=0.0, value=0.0, step=0.1, key="prod_tonnes")
                
                if st.form_submit_button("✅ ENREGISTRER PRODUCTION", use_container_width=True):
                    if matricule_prod and tonnes > 0:
                        if staff_mgr.ajouter_production(matricule_prod, tonnes):
                            emp = staff_mgr.get_employee_by_matricule(matricule_prod)
                            st.success(f"✅ Production de {tonnes} T enregistrée pour {emp.name} ({matricule_prod})")
                            st.rerun()
                        else:
                            st.error("Erreur lors de l'enregistrement.")
                    else:
                        st.warning("⚠️ Veuillez sélectionner un opérateur et saisir une quantité.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 5: CLASSEMENTS ---
        with rh_tabs[4]:
            # Classement par Ancienneté
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📅 Classement par Ancienneté")
            
            anciens = staff_mgr.get_classement_anciennete()
            if anciens:
                anciennete_data = []
                for i, emp in enumerate(anciens, 1):
                    date_arrivee = getattr(emp, 'date_arrivee', date.today())
                    anciennete_jours = (date.today() - date_arrivee).days
                    anciennete_annees = anciennete_jours / 365.25
                    anciennete_data.append({
                        "Rang": i,
                        "Matricule": emp.matricule,
                        "Nom": emp.name,
                        "Rôle": emp.role,
                        "Équipe": emp.team,
                        "Date Arrivée": date_arrivee.strftime("%d/%m/%Y"),
                        "Ancienneté (ans)": round(anciennete_annees, 1)
                    })
                
                df_anciennete = pd.DataFrame(anciennete_data)
                st.dataframe(df_anciennete, width='stretch', hide_index=True)
            else:
                st.info("Aucun employé.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Classement par Production
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🏭 Classement des Opérateurs par Production")
            
            prod_ops = staff_mgr.get_classement_production()
            if prod_ops:
                prod_data = []
                for i, emp in enumerate(prod_ops, 1):
                    prod_data.append({
                        "Rang": i,
                        "Matricule": emp.matricule,
                        "Nom": emp.name,
                        "Équipe": emp.team,
                        "Production (T)": int(getattr(emp, 'production_tonnes', 0)),
                        "Machine Assignée": getattr(emp, 'assigned_machine', "Aucune")
                    })
                
                df_prod = pd.DataFrame(prod_data)
                st.dataframe(df_prod, width='stretch', hide_index=True)
            else:
                st.info("Aucun opérateur enregistré.")
            st.markdown('</div>', unsafe_allow_html=True)
            
            # Classement par Assiduité
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("⭐ Classement des Opérateurs par Assiduité")
            st.caption("Classement par nombre de jours consécutifs sans retard ni absence")
            
            assid_ops = staff_mgr.get_classement_assiduite()
            if assid_ops:
                assid_data = []
                for i, emp in enumerate(assid_ops, 1):
                    medaille = ""
                    if i == 1: medaille = "🥇"
                    elif i == 2: medaille = "🥈"
                    elif i == 3: medaille = "🥉"
                    
                    assid_data.append({
                        "Rang": f"{medaille} {i}" if medaille else str(i),
                        "Matricule": emp.matricule,
                        "Nom": emp.name,
                        "Équipe": emp.team,
                        "Jours Sans Retard/Absence": getattr(emp, 'jours_sans_retard_absence', 0),
                        "Total Retards": getattr(emp, 'total_retards', 0),
                        "Total Absences": getattr(emp, 'total_absences', 0)
                    })
                
                df_assid = pd.DataFrame(assid_data)
                st.dataframe(df_assid, width='stretch', hide_index=True)
            else:
                st.info("Aucun opérateur enregistré.")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 6: VUE PAR ÉQUIPE ---
        with rh_tabs[5]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("👥 Organisation par Équipe")
            
            equipes = sorted(set([e.team for e in staff_mgr.staff]))
            
            for equipe in equipes:
                st.markdown(f"### Équipe {equipe}")
                equipe_members = [e for e in staff_mgr.staff if e.team == equipe]
                
                if equipe_members:
                    equipe_data = []
                    for emp in equipe_members:
                        date_arrivee = getattr(emp, 'date_arrivee', date.today())
                        production_tonnes = getattr(emp, 'production_tonnes', 0)
                        jours_sans = getattr(emp, 'jours_sans_retard_absence', 0)
                        
                        equipe_data.append({
                            "Matricule": emp.matricule,
                            "Nom": emp.name,
                            "Rôle": emp.role,
                            "Shift": emp.shift_type,
                            "Date Arrivée": date_arrivee.strftime("%d/%m/%Y"),
                            "Production (T)": int(production_tonnes) if emp.role == "Operateur" else 0,
                            "Jours Sans Retard/Absence": jours_sans
                        })
                    
                    df_equipe = pd.DataFrame(equipe_data)
                    st.dataframe(df_equipe, width='stretch', hide_index=True)
                    
                    # Statistiques de l'équipe
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Effectif", len(equipe_members))
                    operateurs_equipe = [e for e in equipe_members if e.role == "Operateur"]
                    col2.metric("Opérateurs", len(operateurs_equipe))
                    if operateurs_equipe:
                        prod_totale = sum(getattr(e, 'production_tonnes', 0) for e in operateurs_equipe)
                        col3.metric("Production Totale", f"{int(prod_totale)} T")
                    
                    st.markdown("---")
                else:
                    st.info(f"Aucun membre dans l'équipe {equipe}.")
            
        st.markdown('</div>', unsafe_allow_html=True)

# --- MARCHÉ OR ---
if "MARCHÉ OR" in tab_dict:
    with tab_dict["MARCHÉ OR"]:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("🥇 ANALYSE DU MARCHÉ DE L'OR")
        st.markdown("Suivi en temps réel du prix de l'or et convertisseur")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Récupérer le prix de l'or
        gold_price = get_gold_price()
        rates = get_exchange_rates()
        
        # Prix de l'or en différentes devises
        price_usd = gold_price['price_per_ounce_usd']
        price_eur = price_usd * rates['EUR']
        price_cfa = price_usd * rates['CFA']
        
        # Prix par gramme
        price_per_gram_usd = price_usd / 31.1035  # 1 once troy = 31.1035 grammes
        price_per_gram_eur = price_per_gram_usd * rates['EUR']
        price_per_gram_cfa = price_per_gram_usd * rates['CFA']
        
        # Section 1: Prix en temps réel
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 💰 Prix de l'Or en Temps Réel")
        
        col_price1, col_price2, col_price3, col_price4 = st.columns(4)
        
        with col_price1:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #f6d365 0%, #fda085 100%); padding: 20px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">ONCE TROY (USD)</div>
                <div style="font-size: 36px; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                    ${price_usd:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_price2:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 20px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">ONCE TROY (EUR)</div>
                <div style="font-size: 36px; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                    €{price_eur:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_price3:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #30cfd0 0%, #330867 100%); padding: 20px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">ONCE TROY (CFA)</div>
                <div style="font-size: 36px; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                    {price_cfa:,.0f} F
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_price4:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #fa709a 0%, #fee140 100%); padding: 20px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">GRAMME (USD)</div>
                <div style="font-size: 36px; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                    ${price_per_gram_usd:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        # Ajouter une ligne supplémentaire pour les prix par gramme en EUR et FCFA
        st.markdown("<br>", unsafe_allow_html=True)
        col_price5, col_price6 = st.columns(2)
        
        with col_price5:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); padding: 20px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">GRAMME (EUR)</div>
                <div style="font-size: 36px; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                    €{price_per_gram_eur:,.2f}
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        with col_price6:
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #30cfd0 0%, #330867 100%); padding: 20px; border-radius: 15px; text-align: center; color: white; box-shadow: 0 4px 15px rgba(0,0,0,0.2);">
                <div style="font-size: 14px; font-weight: 700; margin-bottom: 10px;">GRAMME (FCFA)</div>
                <div style="font-size: 36px; font-weight: 900; text-shadow: 2px 2px 4px rgba(0,0,0,0.3);">
                    {price_per_gram_cfa:,.0f} F
                </div>
            </div>
            """, unsafe_allow_html=True)
        
        st.caption(f"🕐 Dernière mise à jour: {gold_price['timestamp'].strftime('%d/%m/%Y %H:%M:%S')}")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Section 2: Graphique de Trading Avancé
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 📈 GRAPHIQUE DE TRADING AVANCÉ - OR")
        
        # Sélection de la période et du type de graphique
        col_select1, col_select2 = st.columns(2)
        with col_select1:
            period_selection = st.selectbox(
                "Période d'analyse",
                ["Journalier (30 jours)", "Hebdomadaire (52 semaines)", "Mensuel (12 mois)", "Annuel (10 ans)"],
                key="gold_period"
            )
        with col_select2:
            chart_type = st.selectbox(
                "Type de graphique",
                ["Chandeliers (Candlestick)", "Ligne", "Chandeliers + Indicateurs"],
                key="chart_type"
            )
        
        # Mapper la sélection à la période
        period_map = {
            "Journalier (30 jours)": "daily",
            "Hebdomadaire (52 semaines)": "weekly",
            "Mensuel (12 mois)": "monthly",
            "Annuel (10 ans)": "yearly"
        }
        selected_period = period_map[period_selection]
        
        # Récupérer les données historiques
        hist_data = get_gold_historical_data(selected_period)
        
        # Créer des données OHLC (Open, High, Low, Close) à partir des prix
        prices = hist_data['prices']
        dates = hist_data['dates']
        
        # Générer des données OHLC simulées réalistes
        ohlc_data = []
        for i, price in enumerate(prices):
            if i == 0:
                open_price = price
            else:
                # Open price = close price du jour précédent avec une petite variation
                open_price = ohlc_data[i-1]['Close'] * (1 + random.uniform(-0.02, 0.02))
            
            # Générer High, Low, Close autour du prix
            daily_volatility = price * 0.02  # 2% de volatilité
            high_price = max(open_price, price) + random.uniform(0, daily_volatility * 0.5)
            low_price = min(open_price, price) - random.uniform(0, daily_volatility * 0.5)
            close_price = price
            
            ohlc_data.append({
                'Date': dates[i],
                'Open': open_price,
                'High': high_price,
                'Low': low_price,
                'Close': close_price
            })
        
        df_gold = pd.DataFrame(ohlc_data)
        df_gold['Prix (USD/once)'] = prices
        
        # Calculer les indicateurs techniques
        # Moyennes mobiles
        df_gold['MA_20'] = df_gold['Close'].rolling(window=min(20, len(df_gold)//2)).mean()
        df_gold['MA_50'] = df_gold['Close'].rolling(window=min(50, len(df_gold)//2)).mean()
        
        # Bandes de Bollinger (MA ± 2 écarts-types)
        df_gold['BB_Middle'] = df_gold['Close'].rolling(window=min(20, len(df_gold)//2)).mean()
        df_gold['BB_Std'] = df_gold['Close'].rolling(window=min(20, len(df_gold)//2)).std()
        df_gold['BB_Upper'] = df_gold['BB_Middle'] + (df_gold['BB_Std'] * 2)
        df_gold['BB_Lower'] = df_gold['BB_Middle'] - (df_gold['BB_Std'] * 2)
        
        # RSI (Relative Strength Index) - simplifié
        delta = df_gold['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=min(14, len(df_gold)//3)).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=min(14, len(df_gold)//3)).mean()
        rs = gain / loss
        df_gold['RSI'] = 100 - (100 / (1 + rs))
        
        # Volumes simulés
        df_gold['Volume'] = [random.uniform(1000000, 5000000) for _ in range(len(df_gold))]
        
        # Calculer les statistiques
        min_price = df_gold['Low'].min()
        max_price = df_gold['High'].max()
        avg_price = df_gold['Close'].mean()
        current_price_hist = df_gold['Close'].iloc[-1]
        first_price = df_gold['Close'].iloc[0]
        variation_pct = ((current_price_hist - first_price) / first_price) * 100
        current_rsi = df_gold['RSI'].iloc[-1]
        
        # Afficher les statistiques
        col_stat1, col_stat2, col_stat3, col_stat4, col_stat5, col_stat6 = st.columns(6)
        col_stat1.metric("Prix Actuel", f"${current_price_hist:,.2f}", f"{variation_pct:+.2f}%")
        col_stat2.metric("Prix Moyen", f"${avg_price:,.2f}")
        col_stat3.metric("Prix Min", f"${min_price:,.2f}")
        col_stat4.metric("Prix Max", f"${max_price:,.2f}")
        col_stat5.metric("Variation", f"${max_price - min_price:,.2f}", delta_color="inverse")
        rsi_color = "normal" if 30 <= current_rsi <= 70 else "inverse"
        col_stat6.metric("RSI", f"{current_rsi:.1f}", delta_color=rsi_color)
        
        st.markdown("---")
        
        # Créer le graphique de trading avancé
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
            
            if chart_type == "Chandeliers (Candlestick)" or chart_type == "Chandeliers + Indicateurs":
                # Créer un graphique avec sous-graphiques si on veut les indicateurs
                if chart_type == "Chandeliers + Indicateurs":
                    fig = make_subplots(
                        rows=3, cols=1,
                        shared_xaxes=True,
                        vertical_spacing=0.03,
                        row_heights=[0.6, 0.2, 0.2],
                        subplot_titles=('Prix de l\'Or (Chandeliers)', 'Volume', 'RSI'),
                        specs=[[{"secondary_y": False}],
                               [{"secondary_y": False}],
                               [{"secondary_y": False}]]
                    )
                else:
                    fig = go.Figure()
                
                # Graphique en chandeliers (Candlestick)
                candlestick = go.Candlestick(
                    x=df_gold['Date'],
                    open=df_gold['Open'],
                    high=df_gold['High'],
                    low=df_gold['Low'],
                    close=df_gold['Close'],
                    name='Prix de l\'Or',
                    increasing_line_color='#26a69a',  # Vert pour hausse
                    decreasing_line_color='#ef5350',  # Rouge pour baisse
                    increasing_fillcolor='#26a69a',
                    decreasing_fillcolor='#ef5350'
                )
                
                if chart_type == "Chandeliers + Indicateurs":
                    fig.add_trace(candlestick, row=1, col=1)
                    
                    # Ajouter les moyennes mobiles
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['MA_20'],
                        mode='lines',
                        name='MA 20',
                        line=dict(color='#FF9800', width=2),
                        opacity=0.8
                    ), row=1, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['MA_50'],
                        mode='lines',
                        name='MA 50',
                        line=dict(color='#2196F3', width=2),
                        opacity=0.8
                    ), row=1, col=1)
                    
                    # Ajouter les bandes de Bollinger
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['BB_Upper'],
                        mode='lines',
                        name='Bollinger Upper',
                        line=dict(color='rgba(128,128,128,0.3)', width=1, dash='dot'),
                        showlegend=False
                    ), row=1, col=1)
                    
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['BB_Lower'],
                        mode='lines',
                        name='Bollinger Lower',
                        line=dict(color='rgba(128,128,128,0.3)', width=1, dash='dot'),
                        fill='tonexty',
                        fillcolor='rgba(128,128,128,0.1)',
                        showlegend=False
                    ), row=1, col=1)
                    
                    # Graphique des volumes
                    colors_vol = ['#26a69a' if df_gold['Close'].iloc[i] >= df_gold['Open'].iloc[i] 
                                 else '#ef5350' for i in range(len(df_gold))]
                    fig.add_trace(go.Bar(
                        x=df_gold['Date'],
                        y=df_gold['Volume'],
                        name='Volume',
                        marker_color=colors_vol,
                        opacity=0.6
                    ), row=2, col=1)
                    
                    # Graphique RSI
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['RSI'],
                        mode='lines',
                        name='RSI',
                        line=dict(color='#9c27b0', width=2)
                    ), row=3, col=1)
                    
                    # Lignes de référence RSI
                    fig.add_hline(y=70, line_dash="dash", line_color="red", opacity=0.5, row=3, col=1)
                    fig.add_hline(y=30, line_dash="dash", line_color="green", opacity=0.5, row=3, col=1)
                    fig.add_hline(y=50, line_dash="dot", line_color="gray", opacity=0.3, row=3, col=1)
                    
                    fig.update_yaxes(title_text="Prix (USD/once)", row=1, col=1)
                    fig.update_yaxes(title_text="Volume", row=2, col=1)
                    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)
                    fig.update_xaxes(title_text="Date", row=3, col=1)
                    
                else:
                    fig.add_trace(candlestick)
                    
                    # Ajouter les moyennes mobiles
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['MA_20'],
                        mode='lines',
                        name='MA 20',
                        line=dict(color='#FF9800', width=2)
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['MA_50'],
                        mode='lines',
                        name='MA 50',
                        line=dict(color='#2196F3', width=2)
                    ))
                    
                    # Ajouter les bandes de Bollinger
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['BB_Upper'],
                        mode='lines',
                        name='Bollinger Upper',
                        line=dict(color='rgba(128,128,128,0.3)', width=1, dash='dot'),
                        showlegend=False
                    ))
                    
                    fig.add_trace(go.Scatter(
                        x=df_gold['Date'],
                        y=df_gold['BB_Lower'],
                        mode='lines',
                        name='Bollinger Lower',
                        line=dict(color='rgba(128,128,128,0.3)', width=1, dash='dot'),
                        fill='tonexty',
                        fillcolor='rgba(128,128,128,0.1)',
                        showlegend=False
                    ))
                
            else:
                # Graphique en ligne simple
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_gold['Date'],
                    y=df_gold['Close'],
                    mode='lines',
                    name='Prix de l\'Or',
                    line=dict(color='#F5B800', width=3),
                    fill='tonexty',
                    fillcolor='rgba(245, 184, 0, 0.2)'
                ))
            
            # Mise en forme du graphique
            fig.update_layout(
                title={
                    'text': f'Graphique de Trading - Or ({period_selection})',
                    'x': 0.5,
                    'xanchor': 'center',
                    'font': {'size': 24, 'color': '#F5B800', 'family': 'Inter'}
                },
                height=700 if chart_type == "Chandeliers + Indicateurs" else 600,
                hovermode='x unified',
                template='plotly_dark',
                plot_bgcolor='#1e1e2e',
                paper_bgcolor='#1e1e2e',
                font=dict(color='#e0e0e0', family='Inter'),
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02 if chart_type != "Chandeliers + Indicateurs" else 0.99,
                    xanchor="right",
                    x=1,
                    bgcolor='rgba(30,30,46,0.8)'
                ),
                xaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(128, 128, 128, 0.2)',
                    rangeselector=dict(
                        buttons=list([
                            dict(count=7, label="7j", step="day", stepmode="backward"),
                            dict(count=30, label="30j", step="day", stepmode="backward"),
                            dict(count=90, label="90j", step="day", stepmode="backward"),
                            dict(step="all")
                        ])
                    ),
                    rangeslider=dict(visible=False)
                ),
                yaxis=dict(
                    showgrid=True,
                    gridcolor='rgba(128, 128, 128, 0.2)'
                )
            )
            
            st.plotly_chart(fig, width='stretch', config={
                'displayModeBar': True,
                'displaylogo': False,
                'modeBarButtonsToAdd': ['drawline', 'drawopenpath', 'drawclosedpath', 'drawcircle', 'drawrect', 'eraseshape'],
                'toImageButtonOptions': {
                    'format': 'png',
                    'filename': f'gold_trading_{period_selection}',
                    'height': 600,
                    'width': 1200,
                    'scale': 1
                }
            })
            
        except Exception as e:
            st.error(f"Erreur lors de la création du graphique: {str(e)}")
            st.info("Affichage d'un graphique simplifié...")
            st.line_chart(df_gold.set_index('Date')['Close'])
        
        # Graphique en barres pour la variation
        st.markdown("---")
        st.markdown("#### 📊 Analyse des Variations")
        
        df_gold['Variation'] = df_gold['Close'].diff()
        df_gold['Variation %'] = (df_gold['Variation'] / df_gold['Close'].shift(1)) * 100
        
        col_var1, col_var2 = st.columns(2)
        
        with col_var1:
            st.markdown("**Variation Journalière**")
            fig_bar = px.bar(
                df_gold.tail(20),
                x='Date',
                y='Variation %',
                color='Variation %',
                color_continuous_scale=['#f44336', '#F5B800', '#4caf50'],
                color_continuous_midpoint=0,
                labels={'Variation %': 'Variation (%)', 'Date': 'Date'}
            )
            fig_bar.update_layout(
                height=300,
                showlegend=False,
                plot_bgcolor='#1e1e2e',
                paper_bgcolor='#1e1e2e',
                font=dict(color='#e0e0e0'),
                template='plotly_dark'
            )
            st.plotly_chart(fig_bar, width='stretch', use_container_width=True)
        
        with col_var2:
            st.markdown("**Volume vs Prix**")
            fig_scatter = px.scatter(
                df_gold.tail(20),
                x='Volume',
                y='Close',
                size='Volume',
                color='Variation %',
                color_continuous_scale=['#f44336', '#F5B800', '#4caf50'],
                labels={'Close': 'Prix (USD)', 'Volume': 'Volume'},
                hover_data=['Date']
            )
            fig_scatter.update_layout(
                height=300,
                plot_bgcolor='#1e1e2e',
                paper_bgcolor='#1e1e2e',
                font=dict(color='#e0e0e0'),
                template='plotly_dark'
            )
            st.plotly_chart(fig_scatter, width='stretch', use_container_width=True)
        
        # Tableau des données
        st.markdown("---")
        with st.expander("📋 Voir les données détaillées"):
            display_df = df_gold.copy()
            display_df['Date'] = display_df['Date'].apply(lambda x: x.strftime('%d/%m/%Y'))
            if 'Variation' in display_df.columns:
                display_df['Variation'] = display_df['Variation'].round(2)
                display_df['Variation %'] = display_df['Variation %'].round(2)
            st.dataframe(display_df, width='stretch', hide_index=True)
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Section 3: Convertisseur d'or
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 🔄 Convertisseur d'Or")
        
        col_conv1, col_conv2 = st.columns(2)
        
        with col_conv1:
            st.markdown("##### 💰 Conversion Poids → Valeur")
            with st.form("gold_converter_form"):
                amount = st.number_input("Quantité", min_value=0.0, value=1.0, step=0.01, key="gold_amount")
                unit = st.selectbox("Unité", ["Grammes", "Onces troy", "Kilogrammes"], key="gold_unit")
                currency = st.selectbox("Devise", ["USD", "EUR", "CFA"], key="gold_currency")
                
                if st.form_submit_button("🔄 Convertir", use_container_width=True):
                    # Conversion en grammes
                    if unit == "Grammes":
                        grams = amount
                    elif unit == "Onces troy":
                        grams = amount * 31.1035
                    else:  # Kilogrammes
                        grams = amount * 1000
                    
                    # Calcul de la valeur
                    value_usd = grams * price_per_gram_usd
                    
                    if currency == "USD":
                        result_value = value_usd
                        result_symbol = "$"
                    elif currency == "EUR":
                        result_value = value_usd * rates['EUR']
                        result_symbol = "€"
                    else:  # CFA
                        result_value = value_usd * rates['CFA']
                        result_symbol = "F"
                    
                    st.success(f"**Valeur:** {result_symbol}{result_value:,.2f}")
        
        with col_conv2:
            st.markdown("##### 💵 Conversion Valeur → Poids")
            with st.form("value_to_weight_form"):
                value_input = st.number_input("Valeur", min_value=0.0, value=1000.0, step=0.01, key="gold_value")
                currency_input = st.selectbox("Devise", ["USD", "EUR", "CFA"], key="value_currency")
                output_unit = st.selectbox("Unité de sortie", ["Grammes", "Onces troy", "Kilogrammes"], key="output_unit")
                
                if st.form_submit_button("🔄 Convertir", use_container_width=True):
                    # Conversion en USD
                    if currency_input == "USD":
                        value_usd = value_input
                    elif currency_input == "EUR":
                        value_usd = value_input / rates['EUR']
                    else:  # CFA
                        value_usd = value_input / rates['CFA']
                    
                    # Calcul du poids en grammes
                    grams = value_usd / price_per_gram_usd
                    
                    # Conversion selon l'unité demandée
                    if output_unit == "Grammes":
                        result_weight = grams
                        result_unit = "g"
                    elif output_unit == "Onces troy":
                        result_weight = grams / 31.1035
                        result_unit = "oz"
                    else:  # Kilogrammes
                        result_weight = grams / 1000
                        result_unit = "kg"
                    
                    st.success(f"**Poids:** {result_weight:,.4f} {result_unit}")
        
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Section 3: Tableau de conversion rapide
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### 📊 Tableau de Conversion Rapide")
        
        # Créer un tableau avec différentes quantités
        conversion_data = []
        quantities = [1, 5, 10, 50, 100, 500, 1000]  # En grammes
        
        for qty_grams in quantities:
            value_usd = qty_grams * price_per_gram_usd
            value_eur = value_usd * rates['EUR']
            value_cfa = value_usd * rates['CFA']
            qty_ounces = qty_grams / 31.1035
            
            conversion_data.append({
                "Grammes": f"{qty_grams:,} g",
                "Onces troy": f"{qty_ounces:.4f} oz",
                "Valeur USD": f"${value_usd:,.2f}",
                "Valeur EUR": f"€{value_eur:,.2f}",
                "Valeur CFA": f"{value_cfa:,.0f} F"
            })
        
        df_conversion = pd.DataFrame(conversion_data)
        st.dataframe(df_conversion, width='stretch', hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Section 4: Informations sur l'or
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.markdown("#### ℹ️ Informations sur l'Or")
        
        info_col1, info_col2 = st.columns(2)
        
        with info_col1:
            st.markdown("""
            **📏 Unités de mesure:**
            - **Once troy (oz t)**: 31.1035 grammes
            - **Once avoirdupois (oz)**: 28.3495 grammes
            - **Kilogramme (kg)**: 1000 grammes
            
            **💡 Note:** Le marché de l'or utilise généralement l'once troy.
            """)
        
        with info_col2:
            st.markdown(f"""
            **📈 Prix actuel:**
            - **1 once troy**: ${price_usd:,.2f} USD
            - **1 gramme**: ${price_per_gram_usd:,.2f} USD
            - **1 kilogramme**: ${price_per_gram_usd * 1000:,.2f} USD
            
            **🔄 Taux de change:**
            - 1 USD = {rates['EUR']:.2f} EUR
            - 1 USD = {rates['CFA']:.0f} CFA
            """)
        
        st.markdown('</div>', unsafe_allow_html=True)

# --- VALIDATION OPÉRATEUR ---
if "VALIDATION OPÉRATEUR" in tab_dict:
    with tab_dict["VALIDATION OPÉRATEUR"]:
        # Message de test pour vérifier que l'onglet s'affiche - TOUJOURS AFFICHÉ
        st.markdown("## 🔧 INTERFACE OPÉRATEUR - VALIDATION")
        st.success("✅ L'onglet VALIDATION OPÉRATEUR est chargé. Le contenu devrait apparaître ci-dessous.")
        st.write("**Rôle utilisateur:**", user_role)
        st.write("**Nom d'utilisateur:**", st.session_state.get('username', 'Non défini'))
        if user_role == "Operateur":
            with st.expander("🔐 Changer mon mot de passe", expanded=False):
                render_change_own_password_form(user_mgr, key_prefix="operateur_pwd")
        
        # Initialiser les systèmes de notification dans session_state
        if 'validations' not in st.session_state:
            st.session_state.validations = []
        if 'operator_notifications' not in st.session_state:
            st.session_state.operator_notifications = []
        if 'loading_signals' not in st.session_state:
            st.session_state.loading_signals = []
        if 'breakdown_reports' not in st.session_state:
            st.session_state.breakdown_reports = []
        if 'cycle_events' not in st.session_state:
            st.session_state.cycle_events = []
        
        # Récupérer l'opérateur actuel
        current_operator = None
        if user_role == "Operateur":
            # Trouver l'opérateur correspondant à l'utilisateur connecté
            for emp in staff_mgr.staff:
                if emp.role == "Operateur" and emp.name == st.session_state.username:
                    current_operator = emp
                    break
        
        # Récupérer les machines de l'opérateur pour déterminer le type
        df_machines = manager.get_summary_dataframe()
        operator_machines_list = []
        machine_types = []
        if current_operator:
            operator_machines_list = df_machines[df_machines['Opérateur'] == current_operator.name]['ID'].tolist()
            machine_types = df_machines[df_machines['Opérateur'] == current_operator.name]['Type'].tolist()
        
        # Déterminer le type d'opérateur depuis les données utilisateur ou les machines
        operator_type_from_user = None
        if user_info and 'operator_type' in user_info:
            operator_type_from_user = user_info['operator_type']
        
        # Si le type est défini dans les données utilisateur, l'utiliser en priorité
        if operator_type_from_user:
            is_loader = (operator_type_from_user == "loader")
            is_dumper = (operator_type_from_user == "dumper")
        else:
            # Sinon, détecter automatiquement à partir des machines assignées
            is_loader = any('CHARGE' in m.upper() or 'PELLE' in m.upper() or 'EXCAVATRICE' in m.upper() 
                          for m in machine_types) if machine_types else False
            is_dumper = any('DUMPER' in m.upper() or 'CAMION' in m.upper() 
                          for m in machine_types) if machine_types else False
        
        # CRÉER DES SOUS-ONGLETS SELON LE TYPE D'OPÉRATEUR
        # Si opérateur de chargement : seulement sous-onglet chargement
        # Si opérateur de transport : seulement sous-onglet transport
        # Si les deux ou aucun : afficher les deux
        show_loader_tab = True
        show_dumper_tab = True
        
        if user_role == "Operateur":
            if is_loader and not is_dumper:
                # Opérateur de chargement uniquement
                show_dumper_tab = False
            elif is_dumper and not is_loader:
                # Opérateur de transport uniquement
                show_loader_tab = False
        
        # Créer les sous-onglets selon ce qui doit être affiché
        sub_tab_labels = []
        if show_loader_tab:
            sub_tab_labels.append("📦 Opérateur de Chargement")
        if show_dumper_tab:
            sub_tab_labels.append("🚚 Opérateur de Transport")
        
        # S'assurer qu'il y a au moins un sous-onglet
        if not sub_tab_labels:
            # Si aucun sous-onglet n'est défini, afficher les deux par défaut
            sub_tab_labels = ["📦 Opérateur de Chargement", "🚚 Opérateur de Transport"]
            show_loader_tab = True
            show_dumper_tab = True
        
        # Créer les sous-onglets - TOUJOURS CRÉER AU MOINS UN
        if sub_tab_labels:
            sub_tabs = st.tabs(sub_tab_labels)
        else:
            # Fallback absolu - ne devrait jamais arriver
            sub_tabs = st.tabs(["📦 Opérateur de Chargement", "🚚 Opérateur de Transport"])
            show_loader_tab = True
            show_dumper_tab = True
        
        loader_tab_index = sub_tab_labels.index("📦 Opérateur de Chargement") if show_loader_tab else -1
        dumper_tab_index = sub_tab_labels.index("🚚 Opérateur de Transport") if show_dumper_tab else -1

        # SOUS-ONGLET 1: OPÉRATEUR DE CHARGEMENT - INTERFACE SIMPLIFIÉE
        if show_loader_tab and loader_tab_index >= 0:
            with sub_tabs[loader_tab_index]:
                # Message de test - TOUJOURS AFFICHÉ EN PREMIER
                st.markdown("### 📦 INTERFACE OPÉRATEUR DE CHARGEMENT")
                st.write("**Test d'affichage : Si vous voyez ce message, le sous-onglet fonctionne.**")
                
                # Initialiser les variables
                if 'loading_in_progress' not in st.session_state:
                    st.session_state.loading_in_progress = {}
                
                # Créer un opérateur temporaire si nécessaire
                if not current_operator and st.session_state.get('username'):
                    class TempOperator:
                        def __init__(self, name):
                            self.name = name
                    current_operator = TempOperator(st.session_state.username)
                
                # Message d'accueil - TOUJOURS AFFICHÉ
                if user_role == "Operateur":
                    if not current_operator:
                        st.error("⚠️ Aucun opérateur trouvé. Veuillez vérifier votre compte.")
                    else:
                        st.success(f"✅ Connecté en tant qu'opérateur de chargement : {current_operator.name}")
                else:
                    st.info("Mode superviseur : Vous pouvez valider les chargements.")
                
                # Toujours afficher l'interface - SANS CONDITIONS
                auto_machine = operator_machines_list[0] if operator_machines_list else None
                
                # Récupérer les opérateurs dumper disponibles
                dumper_operators = [e.name for e in staff_mgr.get_active_staff() if e.role == "Operateur"]
                dumper_machines = df_machines[df_machines['Type'].isin(['Dumper', 'Camion', 'Benne'])]['ID'].tolist()
                dumper_operators_with_trucks = []
                for op_name in dumper_operators:
                    op_machines = df_machines[df_machines['Opérateur'] == op_name]['ID'].tolist()
                    if any(m in dumper_machines for m in op_machines):
                        dumper_operators_with_trucks.append(op_name)
                
                # ZONE DE VALIDATION SIMPLIFIÉE - TOUJOURS AFFICHÉE
                st.markdown("""
                <div style="background: #1a1a1a; padding: 40px; border-radius: 15px; margin-bottom: 30px; 
                            border: 4px solid #F5B800; box-shadow: 0 15px 40px rgba(245, 184, 0, 0.6);">
                    <h2 style="color: #F5B800; text-align: center; font-size: 48px; margin: 0 0 30px 0; font-weight: 900;">
                        📦 VALIDATION DE CHARGEMENT
                    </h2>
                </div>
                """, unsafe_allow_html=True)
                
                # Sélection opérateur dumper (si disponible)
                if dumper_operators_with_trucks:
                    selected_dumper_operator = st.selectbox(
                        "🚚 SÉLECTIONNER L'OPÉRATEUR DUMPER",
                        ["Sélectionner..."] + dumper_operators_with_trucks,
                        key="dumper_operator_selection"
                    )
                    
                    if selected_dumper_operator and selected_dumper_operator != "Sélectionner...":
                        dumper_op_machines = df_machines[df_machines['Opérateur'] == selected_dumper_operator]['ID'].tolist()
                        dumper_trucks = [m for m in dumper_op_machines if m in dumper_machines]
                        if dumper_trucks:
                            st.session_state.loading_in_progress['truck'] = dumper_trucks[0]
                            st.session_state.loading_in_progress['dumper_operator'] = selected_dumper_operator
                else:
                    st.info("ℹ️ Aucun dumper disponible. Vous pouvez quand même sélectionner le type de minerai.")
                    selected_dumper_operator = None
                
                # TYPE DE MINERAI - BOUTONS TOUJOURS VISIBLES
                st.markdown("""
                <div style="background: #1a1a1a; padding: 30px; border-radius: 15px; margin: 30px 0; 
                            border: 3px solid #F5B800;">
                    <h3 style="color: #F5B800; text-align: center; font-size: 36px; margin: 0 0 20px 0; font-weight: 700;">
                        🥇 TYPE DE MINERAI
                    </h3>
                </div>
                """, unsafe_allow_html=True)
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("🥇 OR", use_container_width=True, key="btn_or", type="primary"):
                        st.session_state.loading_in_progress.update({
                            'mineral_type': 'Or',
                            'loading_start': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        st.rerun()
                    if st.button("🔶 CUIVRE", use_container_width=True, key="btn_cuivre"):
                        st.session_state.loading_in_progress.update({
                            'mineral_type': 'Cuivre',
                            'loading_start': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        st.rerun()
                with col2:
                    if st.button("⚫ FER", use_container_width=True, key="btn_fer"):
                        st.session_state.loading_in_progress.update({
                            'mineral_type': 'Fer',
                            'loading_start': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        st.rerun()
                    if st.button("🔵 ZINC", use_container_width=True, key="btn_zinc"):
                        st.session_state.loading_in_progress.update({
                            'mineral_type': 'Zinc',
                            'loading_start': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        })
                        st.rerun()
                
                # GRADE - BOUTONS TOUJOURS VISIBLES (si type de minerai sélectionné)
                if 'mineral_type' in st.session_state.loading_in_progress:
                    loading_info = st.session_state.loading_in_progress
                    st.markdown("""
                    <div style="background: #1a1a1a; padding: 30px; border-radius: 15px; margin: 30px 0; 
                                border: 3px solid #F5B800;">
                        <h3 style="color: #F5B800; text-align: center; font-size: 36px; margin: 0 0 20px 0; font-weight: 700;">
                            📊 GRADE DU MINERAI
                        </h3>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    col_g1, col_g2, col_g3 = st.columns(3)
                    with col_g1:
                        if st.button("🟢 HIGH GRADE", use_container_width=True, key="btn_high_grade", type="primary"):
                            st.session_state.loading_in_progress.update({'grade': 'High Grade'})
                            st.rerun()
                    with col_g2:
                        if st.button("🟡 MEDIUM GRADE", use_container_width=True, key="btn_medium_grade"):
                            st.session_state.loading_in_progress.update({'grade': 'Medium Grade'})
                            st.rerun()
                    with col_g3:
                        if st.button("🔴 LOW GRADE", use_container_width=True, key="btn_low_grade"):
                            st.session_state.loading_in_progress.update({'grade': 'Low Grade'})
                            st.rerun()
                    
                    # VALIDATION FINALE - BOUTON TOUJOURS VISIBLE (si grade sélectionné)
                    if 'grade' in st.session_state.loading_in_progress:
                        st.markdown(f"""
                        <div style="background: rgba(245, 184, 0, 0.3); padding: 40px; border-radius: 15px; 
                                    border: 4px solid #F5B800; margin: 30px 0; text-align: center;">
                            <p style="color: #000; font-size: 42px; margin: 15px 0; font-weight: 900;">
                                <strong>Minerai:</strong> {loading_info.get('mineral_type', 'N/A')} - {loading_info.get('grade', 'N/A')}
                            </p>
                            {f'<p style="color: #000; font-size: 42px; margin: 15px 0; font-weight: 900;"><strong>Camion:</strong> {loading_info.get("truck", "N/A")}</p>' if loading_info.get('truck') else ''}
                            {f'<p style="color: #000; font-size: 42px; margin: 15px 0; font-weight: 900;"><strong>Opérateur Dumper:</strong> {loading_info.get("dumper_operator", "N/A")}</p>' if loading_info.get('dumper_operator') else ''}
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button("✅ VALIDER LE CHARGEMENT", use_container_width=True, 
                                   type="primary", key="btn_validate_loading"):
                            if not current_operator:
                                st.error("❌ Impossible de valider : opérateur non trouvé")
                            else:
                                # Déterminer la destination
                                if loading_info.get('grade') == 'High Grade':
                                    destination = "ROMPAD High Grade"
                                elif loading_info.get('grade') == 'Medium Grade':
                                    destination = "ROMPAD Medium Grade"
                                else:
                                    destination = "ROMPAD Low Grade"
                                
                                # Utiliser les valeurs par défaut si pas de dumper sélectionné
                                dumper_op = loading_info.get('dumper_operator', 'Non assigné')
                                truck = loading_info.get('truck', 'Non assigné')
                                
                                loading_signal = {
                                    'id': len(st.session_state.loading_signals) + 1,
                                    'operator': current_operator.name,
                                    'dumper_operator': dumper_op,
                                    'machine': auto_machine,
                                    'truck': truck,
                                    'mineral_type': loading_info.get('mineral_type'),
                                    'grade': loading_info.get('grade'),
                                    'quantity': 50.0,
                                    'destination': destination,
                                    'loading_start': loading_info.get('loading_start'),
                                    'loading_end': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'status': 'Chargement validé - En attente de démarrage dumper'
                                }
                                st.session_state.loading_signals.append(loading_signal)
                                
                                if dumper_op != 'Non assigné':
                                    notification = {
                                        'type': 'loading_validated',
                                        'from_operator': current_operator.name,
                                        'target_operator': dumper_op,
                                        'truck': truck,
                                        'message': f"📦 Chargement validé ! {loading_info.get('mineral_type')} - {loading_info.get('grade')} → {destination}",
                                        'loading_signal_id': loading_signal['id'],
                                        'destination': destination,
                                        'mineral_type': loading_info.get('mineral_type'),
                                        'grade': loading_info.get('grade'),
                                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'read': False
                                    }
                                    st.session_state.operator_notifications.append(notification)
                                
                                cycle_event = {
                                    'type': 'loading_complete',
                                    'id': loading_signal['id'],
                                    'operator': current_operator.name,
                                    'dumper_operator': dumper_op,
                                    'machine': auto_machine,
                                    'truck': truck,
                                    'mineral_type': loading_info.get('mineral_type'),
                                    'grade': loading_info.get('grade'),
                                    'loading_end': loading_signal['loading_end'],
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                st.session_state.cycle_events.append(cycle_event)
                                
                                st.session_state.loading_in_progress = {}
                                st.success(f"✅ Chargement validé !")
                                st.rerun()
        
        # SOUS-ONGLET 2: OPÉRATEUR DE TRANSPORT (DUMPER) - INTERFACE SIMPLIFIÉE
        if show_dumper_tab and dumper_tab_index >= 0:
            with sub_tabs[dumper_tab_index]:
                # Message de test - TOUJOURS AFFICHÉ EN PREMIER
                st.markdown("### 🚚 INTERFACE OPÉRATEUR DE TRANSPORT")
                st.write("**Test d'affichage : Si vous voyez ce message, le sous-onglet fonctionne.**")
                
                # Message d'accueil pour les opérateurs de transport
                if user_role == "Operateur":
                    if not current_operator:
                        st.error("⚠️ Aucun opérateur trouvé. Veuillez vérifier votre compte.")
                    else:
                        st.success(f"✅ Connecté en tant qu'opérateur de transport : {current_operator.name}")
                else:
                    st.info("Mode superviseur : Vous pouvez valider les déchargements.")
                
                # Initialiser les variables
                if 'loading_in_progress' not in st.session_state:
                    st.session_state.loading_in_progress = {}
                
                # Créer un opérateur temporaire si nécessaire
                if not current_operator and st.session_state.get('username'):
                    class TempOperator:
                        def __init__(self, name):
                            self.name = name
                    current_operator = TempOperator(st.session_state.username)
                
                # Toujours afficher l'interface - SANS CONDITIONS
                # Chargements en cours de transport pour ce camion
                in_transit_loadings = []
                pending_loadings = []
                
                if current_operator:
                    in_transit_loadings = [l for l in st.session_state.loading_signals 
                                          if l.get('status') == 'En transport' 
                                          and l.get('dumper_operator') == current_operator.name]
                    
                    # Chargements validés en attente de démarrage
                    pending_loadings = [l for l in st.session_state.loading_signals 
                                       if l.get('status') == 'Chargement validé - En attente de démarrage dumper' 
                                       and l.get('dumper_operator') == current_operator.name]
                
                # ZONE DE VALIDATION SIMPLIFIÉE
                st.markdown("""
                <div style="background: #1a1a1a; padding: 40px; border-radius: 15px; margin-bottom: 30px; 
                            border: 4px solid #F5B800; box-shadow: 0 15px 40px rgba(245, 184, 0, 0.6);">
                    <h2 style="color: #F5B800; text-align: center; font-size: 48px; margin: 0 0 30px 0; font-weight: 900;">
                        🚚 VALIDATION DE TRANSPORT
                    </h2>
                </div>
                """, unsafe_allow_html=True)
                
                # CHARGEMENTS EN ATTENTE DE DÉMARRAGE
                if pending_loadings:
                    for loading in pending_loadings:
                        st.markdown(f"""
                        <div style="background: #1a1a1a; padding: 40px; border-radius: 15px; margin: 20px 0; 
                                    border: 4px solid #F5B800; box-shadow: 0 10px 30px rgba(245, 184, 0, 0.5);">
                            <h3 style="color: #F5B800; text-align: center; font-size: 36px; margin: 0 0 20px 0; font-weight: 700;">
                                📦 NOUVEAU CHARGEMENT
                            </h3>
                            <div style="color: #fff; font-size: 28px; margin: 15px 0; text-align: center;">
                                <p><strong>Type:</strong> {loading.get('mineral_type', 'N/A')} - {loading.get('grade', 'N/A')}</p>
                                <p><strong>Quantité:</strong> {loading.get('quantity', 0)} T</p>
                                <p><strong>Destination:</strong> {loading.get('destination', 'N/A')}</p>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"✅ VALIDER DÉMARRAGE", key=f"start_transport_{loading['id']}", 
                                   use_container_width=True, type="primary"):
                            if not current_operator:
                                st.error("❌ Impossible de valider : opérateur non trouvé")
                            else:
                                loading['status'] = 'En transport'
                                loading['transport_start'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                
                                notification = {
                                    'type': 'transport_started',
                                    'from_operator': current_operator.name,
                                    'target_operator': loading['operator'],
                                    'truck': loading.get('truck'),
                                    'message': f"🚚 Démarrage confirmé ! Transport vers {loading.get('destination', 'N/A')}",
                                    'loading_signal_id': loading['id'],
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                    'read': False
                                }
                                st.session_state.operator_notifications.append(notification)
                                
                                cycle_event = {
                                    'type': 'transport_start',
                                    'operator': current_operator.name,
                                    'loading_id': loading['id'],
                                    'truck': loading.get('truck'),
                                    'destination': loading.get('destination'),
                                    'transport_start': loading['transport_start'],
                                    'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                }
                                st.session_state.cycle_events.append(cycle_event)
                                
                                st.success("✅ Démarrage validé !")
                                st.rerun()
                
                # CHARGEMENTS EN TRANSPORT - VALIDATION DÉCHARGEMENT
                if in_transit_loadings:
                    for loading in in_transit_loadings:
                        st.markdown(f"""
                        <div style="background: #1a1a1a; padding: 40px; border-radius: 15px; margin: 20px 0; 
                                    border: 4px solid #26a69a; box-shadow: 0 10px 30px rgba(38, 166, 154, 0.5);">
                            <h3 style="color: #26a69a; text-align: center; font-size: 36px; margin: 0 0 20px 0; font-weight: 700;">
                                🚚 EN TRANSPORT
                            </h3>
                            <div style="color: #fff; font-size: 28px; margin: 15px 0; text-align: center;">
                                <p><strong>Type:</strong> {loading.get('mineral_type', 'N/A')} - {loading.get('grade', 'N/A')}</p>
                                <p><strong>Quantité:</strong> {loading.get('quantity', 0)} T</p>
                                <p><strong>Destination:</strong> {loading.get('destination', 'N/A')}</p>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        if st.button(f"✅ VALIDER DÉCHARGEMENT", key=f"unload_{loading['id']}", 
                                   use_container_width=True, type="primary"):
                            if not current_operator:
                                st.error("❌ Impossible de valider : opérateur non trouvé")
                            else:
                                loading['status'] = 'Déchargé'
                                loading['unload_time'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                loading['unload_operator'] = current_operator.name
                                
                                if loading.get('transport_start'):
                                    transport_start = datetime.strptime(loading['transport_start'], '%Y-%m-%d %H:%M:%S')
                                    unload_time = datetime.now()
                                    transport_duration = (unload_time - transport_start).total_seconds() / 60
                                    loading['transport_duration'] = transport_duration
                                
                                if loading.get('loading_end'):
                                    loading_end = datetime.strptime(loading['loading_end'], '%Y-%m-%d %H:%M:%S')
                                    unload_time = datetime.now()
                                    total_cycle = (unload_time - loading_end).total_seconds() / 60
                                    loading['total_cycle_time'] = total_cycle
                                
                                distance_km = 5.0
                                fuel_consumption = (distance_km / 100) * 20
                                loading['fuel_consumption'] = fuel_consumption
                                
                                loader_machines = df_machines[df_machines['Type'].isin(['Excavatrice', 'Chargeuse', 'Bulldozer', 'Tractopelle']) & 
                                                          (df_machines['Statut'] == 'Active')]
                                available_loaders = []
                                for idx, loader in loader_machines.iterrows():
                                    loader_loadings = [l for l in st.session_state.loading_signals 
                                                      if l.get('machine') == loader['ID'] 
                                                      and l.get('status') in ['En chargement', 'Chargement validé - En attente de démarrage dumper']]
                                    if not loader_loadings:
                                        available_loaders.append(loader)
                                
                                next_loader = available_loaders[0] if available_loaders else None
                                
                                if next_loader is not None:
                                    loading['next_loader'] = next_loader['ID']
                                    loading['next_loader_operator'] = next_loader.get('Opérateur', 'Non Assigné')
                                    
                                    notification = {
                                        'type': 'unload_complete',
                                        'from_operator': current_operator.name,
                                        'target_operator': loading['operator'],
                                        'truck': loading.get('truck'),
                                        'message': f"✅ Déchargement validé ! {loading.get('quantity', 0)} T déversés à {loading.get('destination', 'ROMPAD')}",
                                        'loading_signal_id': loading['id'],
                                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                                        'read': False
                                    }
                                    st.session_state.operator_notifications.append(notification)
                                    
                                    cycle_event = {
                                        'type': 'unload_complete',
                                        'operator': current_operator.name,
                                        'loading_id': loading['id'],
                                        'truck': loading.get('truck'),
                                        'destination': loading.get('destination'),
                                        'quantity': loading.get('quantity'),
                                        'mineral_type': loading.get('mineral_type'),
                                        'grade': loading.get('grade'),
                                        'unload_time': loading['unload_time'],
                                        'transport_duration': loading.get('transport_duration'),
                                        'total_cycle_time': loading.get('total_cycle_time'),
                                        'fuel_consumption': loading.get('fuel_consumption'),
                                        'next_loader': next_loader['ID'],
                                        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    }
                                    st.session_state.cycle_events.append(cycle_event)
                                    
                                    st.success("✅ Déchargement validé !")
                                    st.rerun()
                                else:
                                    st.warning("⚠️ Aucune pelle disponible")
                                    st.rerun()
                
                # AUCUN CHARGEMENT
                if not pending_loadings and not in_transit_loadings:
                    st.markdown("""
                    <div style="background: rgba(245, 184, 0, 0.2); padding: 60px; border-radius: 15px; 
                                border: 3px solid #F5B800; text-align: center;">
                        <p style="color: #F5B800; font-size: 48px; margin: 0; font-weight: 900;">📭 EN ATTENTE</p>
                        <p style="color: #F5B800; font-size: 32px; margin: 20px 0; font-weight: 700;">
                            Attendez les notifications de l'opérateur de chargement
                        </p>
                    </div>
                    """, unsafe_allow_html=True)

# --- MESSAGERIE (onglet principal) ---
if "MESSAGERIE" in tab_dict:
    with tab_dict["MESSAGERIE"]:
        render_messagerie_tab(user_mgr, user_info)

# --- SST (onglet principal) ---
if "SST" in tab_dict:
    with tab_dict["SST"]:
        render_sst_tab(user_info, staff_mgr)

# --- DONNÉES INGÉNIERIE ---
if "DONNÉES INGÉNIERIE" in tab_dict:
    with tab_dict["DONNÉES INGÉNIERIE"]:
        _ingenierie_finance_visible = False
        if user_info and isinstance(user_info.get("permissions"), dict):
            _ingenierie_finance_visible = bool(user_info["permissions"].get("finance", False))
        elif user_role in ("Administrateur", "Superviseur Production"):
            _ingenierie_finance_visible = True

        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("📊 Données Ingénierie - Système Hybride")
        st.caption("Heures = lecture H-mètre (fin − début). Carburant = litres chargés sur la période (proxy de consommation si la machine ne donne pas la conso).")
        if not _ingenierie_finance_visible:
            st.info(
                "Les **indicateurs financiers** (montants $, revenus, coûts, marges) et les **exports détaillés en dollars** "
                "ne sont pas affichés ici. Ils sont réservés aux profils avec accès à l'onglet **Finance**."
            )

        if _ingenierie_finance_visible:
            st.markdown("""
        <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px; border: 2px solid #F5B800;">
            <h4 style="color: #F5B800; margin: 0 0 10px 0;">ℹ️ Comment ça fonctionne :</h4>
            <ul style="color: #e0e0e0; margin: 0; padding-left: 20px; font-size: 16px;">
                <li><strong>Heures travaillées</strong> : calculées automatiquement (H-mètre fin − H-mètre début)</li>
                <li><strong>Production</strong> : production en tonnes réalisée sur la période</li>
                <li><strong>Carburant</strong> : saisir les <strong>litres chargés</strong> (pleins) — utilisés comme consommation pour les indicateurs</li>
                <li>Le système calcule aussi les agrégats financiers (revenus, coûts, rentabilité) visibles avec l'accès Finance</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        else:
            st.markdown("""
        <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%); 
                    padding: 20px; border-radius: 15px; margin-bottom: 20px; border: 2px solid #F5B800;">
            <h4 style="color: #F5B800; margin: 0 0 10px 0;">ℹ️ Comment ça fonctionne :</h4>
            <ul style="color: #e0e0e0; margin: 0; padding-left: 20px; font-size: 16px;">
                <li><strong>Heures</strong> : H-mètre fin − début</li>
                <li><strong>Production</strong> : tonnes sur la période</li>
                <li><strong>Carburant</strong> : litres chargés (suivi opérationnel)</li>
                <li>Indicateurs **techniques** : cycles, débits, temps de cycle — sans affichage des montants financiers</li>
            </ul>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("---")

        with st.expander("📅 Rapports journaliers — ingénierie, production & carburant (KPI + export)", expanded=False):
            st.markdown(
                "Rapport basé sur les **entrées manuelles** du jour (onglet ci‑dessous) et les **ravitaillements** "
                "enregistrés dans Carburant. L'état **flotte** est un instantané actuel."
            )
            rep_date = st.date_input(
                "Date du rapport",
                value=date.today(),
                key="ingenierie_rapport_date",
            )
            rep_str = rep_date.strftime("%Y-%m-%d")
            pack = collect_daily_ingenierie_report(rep_str, manager)
            k = pack["kpi"]

            st.markdown(f"### 📌 Synthèse — {rep_str}")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Entrées manuelles", f"{int(k['nb_entrees_manuelles'])}")
            c2.metric("Engins avec saisie", f"{int(k['nb_engins_avec_saisie'])}")
            c3.metric("Σ Heures (saisie)", f"{k['total_heures_saisies']:.1f} h")
            c4.metric("Σ Tonnes", f"{k['total_tonnes']:.1f} T")

            c5, c6, c7, c8 = st.columns(4)
            c5.metric("Σ Litres chargés (manuel)", f"{k['total_litres_charges_manuel']:.0f} L")
            c6.metric("Σ Cycles (saisie)", f"{k['total_cycles_saisis']:.1f}")
            c7.metric("Tonnes / heure", f"{k['tonnes_par_heure']:.2f}")
            c8.metric("Litres / tonne", f"{k['litres_par_tonne']:.2f}")

            st.markdown("#### ⏱️ Ingénierie & temps")
            i1, i2, i3, i4 = st.columns(4)
            i1.metric("Heures shift Jour", f"{k['heures_shift_jour']:.1f} h")
            i2.metric("Heures shift Nuit", f"{k['heures_shift_nuit']:.1f} h")
            i3.metric("Heures moy. / engin (saisi)", f"{k['heures_moy_par_engin_saisi']:.2f} h")
            i4.metric("Cycles / heure", f"{k['cycles_par_heure']:.2f}")

            st.markdown("#### 📦 Production")
            p1, p2, p3, p4 = st.columns(4)
            p1.metric("Tonnes shift Jour", f"{k['tonnes_shift_jour']:.1f} T")
            p2.metric("Tonnes shift Nuit", f"{k['tonnes_shift_nuit']:.1f} T")
            p3.metric("Tonnes / cycle", f"{k['tonnes_par_cycle']:.2f}")
            p4.metric("Tonnes moy. / engin (saisi)", f"{k['tonnes_moy_par_engin_saisi']:.2f} T")

            st.markdown("#### ⛽ Carburant")
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("Litres shift Jour (manuel)", f"{k['litres_shift_jour']:.0f} L")
            f2.metric("Litres shift Nuit (manuel)", f"{k['litres_shift_nuit']:.0f} L")
            f3.metric("Litres / heure (manuel)", f"{k['litres_par_heure']:.2f}")
            f4.metric("Litres total jour (manuel + rav.)", f"{k['litres_total_carburant_jour']:.0f} L")

            f5, f6, f7, f8 = st.columns(4)
            f5.metric("Ravitaillements (nb)", f"{int(k['nb_ravitaillements'])}")
            f6.metric("Litres ravitaillements", f"{k['litres_ravitaillements']:.0f} L")
            if _ingenierie_finance_visible:
                f7.metric("USD ravitaillements", f"${k['usd_ravitaillements']:,.0f}")
                f8.metric("Prix moy. rav. (USD/L)", f"{k['prix_moyen_rav_usd_l']:.3f}")
            else:
                f7.metric("Engins ravitailles (dist.)", f"{int(k['nb_engins_ravitailles'])}")
                f8.empty()

            if _ingenierie_finance_visible:
                st.markdown("#### 💵 Financier (estimé, saisie manuelle)")
                x1, x2, x3, x4 = st.columns(4)
                x1.metric("Revenu estimé (USD)", f"${k['revenu_estime_usd']:,.0f}")
                x2.metric("Coût carburant (USD)", f"${k['cout_carburant_manuel_usd']:,.0f}")
                x3.metric("Rentabilité estimée (USD)", f"${k['rentabilite_estimee_usd']:,.0f}")
                x4.metric("Prix L moy. pondéré", f"{k['prix_litre_moyen_pondere_usd']:.3f} $/L")

                x5, x6, x7, x8 = st.columns(4)
                x5.metric("Revenu / heure (USD)", f"${k['revenu_par_heure_usd']:.1f}")
                x6.metric("Revenu / tonne (USD)", f"${k['revenu_par_tonne_usd']:.1f}")
                x7.metric("Coût carburant / tonne", f"${k['cout_carburant_par_tonne_usd']:.1f}")
                x8.metric("Marge / tonne (USD)", f"${k['marge_par_tonne_usd']:.1f}")

            st.markdown("#### 🛠️ Maintenance & flotte (jour / instantané)")
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Maintenances (jour)", f"{int(k['maintenances_jour'])}")
            m2.metric("Pannes signalées (jour)", f"{int(k['pannes_signalees_jour'])}")
            m3.metric("Flotte — actives", f"{int(k['flotte_actives'])}")
            m4.metric("Flotte — pannes", f"{int(k['flotte_pannes'])}")

            st.caption(
                f"Flotte : {int(k['flotte_nb_engins'])} engins au total | "
                f"Engins distincts ravitailles ce jour : {int(k['nb_engins_ravitailles'])}"
            )

            st.markdown("#### 📋 Détail par engin (saisie du jour)")
            _df_machines_view = pack["df_machines"].copy()
            if not _df_machines_view.empty and not _ingenierie_finance_visible:
                for _c in ("taux_horaire_usd", "revenu_estime_usd", "cout_carburant_estime_usd", "rentabilite_estimee_usd"):
                    if _c in _df_machines_view.columns:
                        _df_machines_view.drop(columns=[_c], inplace=True)
            if not pack["df_machines"].empty:
                st.dataframe(_df_machines_view, width="stretch", hide_index=True)
            else:
                st.info("Aucune entrée manuelle pour cette date.")

            st.markdown("#### 🛢️ Détail ravitaillements (jour)")
            _df_fuel_view = pack["df_fuel"].copy()
            if not _df_fuel_view.empty and not _ingenierie_finance_visible:
                for _c in ("price_per_liter_usd", "total_usd", "original_price"):
                    if _c in _df_fuel_view.columns:
                        _df_fuel_view.drop(columns=[_c], inplace=True)
            if not pack["df_fuel"].empty:
                st.dataframe(_df_fuel_view, width="stretch", hide_index=True)
            else:
                st.caption("Aucun ravitaillement enregistré ce jour dans la base.")

            dlk1, dlk2, dlk3 = st.columns(3)
            _kpi_fin_cols = frozenset({
                "revenu_estime_usd", "cout_carburant_manuel_usd", "rentabilite_estimee_usd",
                "prix_litre_moyen_pondere_usd", "revenu_par_heure_usd", "revenu_par_tonne_usd",
                "cout_carburant_par_tonne_usd", "marge_par_tonne_usd", "usd_ravitaillements",
                "prix_moyen_rav_usd_l",
            })
            if _ingenierie_finance_visible:
                csv_kpi = pack["df_kpi"].to_csv(index=False, encoding="utf-8-sig")
                _kpi_btn_label = "📥 KPI (CSV)"
            else:
                _kpi_row = {kk: vv for kk, vv in k.items() if kk not in _kpi_fin_cols}
                csv_kpi = pd.DataFrame([_kpi_row]).to_csv(index=False, encoding="utf-8-sig")
                _kpi_btn_label = "📥 KPI opérationnels (CSV)"
            dlk1.download_button(
                _kpi_btn_label,
                data=csv_kpi,
                file_name=f"rapport_kpi_journalier_{rep_str}.csv",
                mime="text/csv",
                use_container_width=True,
            )
            csv_m = _df_machines_view.to_csv(index=False, encoding="utf-8-sig") if not pack["df_machines"].empty else ""
            dlk2.download_button(
                "📥 Détail par engin (CSV)",
                data=csv_m or "machine_id\n",
                file_name=f"rapport_detail_engins_{rep_str}.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=pack["df_machines"].empty,
            )
            csv_f = _df_fuel_view.to_csv(index=False, encoding="utf-8-sig") if not pack["df_fuel"].empty else ""
            dlk3.download_button(
                "📥 Ravitaillements (CSV)",
                data=csv_f or "machine_id\n",
                file_name=f"rapport_ravitaillements_{rep_str}.csv",
                mime="text/csv",
                use_container_width=True,
                disabled=pack["df_fuel"].empty,
            )

        st.markdown("---")
        
        # Sélectionner un engin
        machine_list = [f"{m.id} - {m.model} ({m.type})" for m in manager.machines]
        if not machine_list:
            st.info("ℹ️ Aucun engin disponible. Veuillez d'abord ajouter des engins.")
        else:
            selected_machine_display = st.selectbox(
                "Sélectionner l'engin",
                machine_list,
                help="Choisissez l'engin pour lequel vous souhaitez entrer des données manuelles",
                key="ingenierie_select_machine"
            )
            
            if selected_machine_display:
                # Extraire l'ID de l'engin sélectionné
                selected_machine_id = selected_machine_display.split(" - ")[0]
                selected_machine = next((m for m in manager.machines if m.id == selected_machine_id), None)
                
                if selected_machine:
                    st.markdown("---")
                    
                    # Afficher les données actuelles
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("Heures moteur actuelles", f"{int(selected_machine.engine_hours)} h")
                    with col_info2:
                        st.metric("Production actuelle", f"{int(selected_machine.production_tonnes)} T")
                    with col_info3:
                        st.metric("Consommation journalière", f"{int(selected_machine.cons_jour)} L")
                    
                    st.markdown("---")
                    
                    # Raccourci pour voir l'historique
                    col_hist_btn, col_hist_info = st.columns([1, 3])
                    with col_hist_btn:
                        show_history = st.button("📜 Voir l'Historique", use_container_width=True, help="Consulter les productions antérieures")
                    with col_hist_info:
                        if show_history:
                            st.info("ℹ️ Section historique affichée ci-dessous")
                    
                    st.markdown("---")
                    
                    # Section Historique (si demandé)
                    if show_history:
                        st.markdown("### 📜 Historique des Productions")
                        
                        # Filtres pour l'historique
                        col_filt1, col_filt2, col_filt3 = st.columns(3)
                        with col_filt1:
                            filter_shift = st.selectbox(
                                "Filtrer par shift",
                                ["Tous", "Jour", "Nuit"],
                                key="hist_filter_shift"
                            )
                        with col_filt2:
                            filter_start_date = st.date_input(
                                "Date de début",
                                value=date.today() - timedelta(days=30),
                                key="hist_start_date"
                            )
                        with col_filt3:
                            filter_end_date = st.date_input(
                                "Date de fin",
                                value=date.today(),
                                key="hist_end_date"
                            )
                        
                        # Récupérer l'historique
                        shift_filter = None if filter_shift == "Tous" else filter_shift
                        history = get_manual_entries_history(
                            machine_id=selected_machine_id,
                            shift=shift_filter,
                            start_date=filter_start_date.strftime('%Y-%m-%d'),
                            end_date=filter_end_date.strftime('%Y-%m-%d'),
                            limit=200
                        )
                        
                        if history:
                            # Résumé par shift
                            summary = get_manual_entries_summary(
                                machine_id=selected_machine_id,
                                start_date=filter_start_date.strftime('%Y-%m-%d'),
                                end_date=filter_end_date.strftime('%Y-%m-%d')
                            )
                            
                            if summary:
                                st.markdown("#### 📊 Résumé par Shift")
                                summary_cols = st.columns(len(summary) if summary else 1)
                                for idx, shift_summary in enumerate(summary):
                                    with summary_cols[idx]:
                                        shift_label = "🌅 Jour" if shift_summary['shift'] == "Jour" else "🌙 Nuit"
                                        st.metric(
                                            shift_label,
                                            f"{int(shift_summary['total_production'])} T",
                                            delta=f"{int(shift_summary['total_entries'])} entrées"
                                        )
                            
                            st.markdown("---")
                            st.markdown("#### 📋 Détail des Entrées")
                            
                            # Créer un DataFrame pour l'affichage
                            df_history = pd.DataFrame(history)
                            df_history['entry_date'] = pd.to_datetime(df_history['entry_date'])
                            df_history = df_history.sort_values('entry_date', ascending=False)
                            
                            # Formater les colonnes pour l'affichage
                            shift_display = df_history['shift'].apply(lambda x: "🌅 Jour" if x == "Jour" else ("🌙 Nuit" if x == "Nuit" else x))
                            _hist_cols = {
                                'Date': df_history['entry_date'].dt.strftime('%Y-%m-%d'),
                                'Shift': shift_display,
                                'Heures': df_history['hours_worked'].round(1),
                                'Production (T)': df_history['production_tonnes'].round(1),
                                'Litres chargés (L)': df_history['fuel_consumed'].round(1),
                                'Cycles': df_history['cycles_added'].round(1),
                                'Entré par': df_history['entered_by'],
                            }
                            if _ingenierie_finance_visible:
                                _hist_cols['Revenu ($)'] = df_history['revenue_jour'].round(0).astype(int)
                                _hist_cols['Coût ($)'] = df_history['cost_fuel'].round(0).astype(int)
                                _hist_cols['Rentabilité ($)'] = df_history['profitability'].round(0).astype(int)
                            display_df = pd.DataFrame(_hist_cols)
                            
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            # Export
                            csv = display_df.to_csv(index=False, encoding='utf-8-sig')
                            st.download_button(
                                label="📥 Télécharger l'historique (CSV)",
                                data=csv,
                                file_name=f"historique_{selected_machine_id}_{date.today().strftime('%Y%m%d')}.csv",
                                mime="text/csv",
                                use_container_width=True
                            )
                        else:
                            st.info("ℹ️ Aucune entrée trouvée pour cette période.")
                        
                        st.markdown("---")
                    
                    # Formulaire d'entrée manuelle
                    with st.form("ingenierie_manual_entry_form", clear_on_submit=False):
                        st.markdown("### 📝 Entrée Manuelle des Données")
                        
                        # Sélection du shift et de la date
                        col_shift_date1, col_shift_date2 = st.columns(2)
                        with col_shift_date1:
                            # Déterminer le shift actuel par défaut
                            default_shift = get_current_shift()
                            shift = st.selectbox(
                                "Shift *",
                                ["Jour", "Nuit"],
                                index=0 if default_shift == "Jour" else 1,
                                help="Jour : 5h30-18h00 | Nuit : 18h30-5h00",
                                key="ingenierie_shift"
                            )
                            # Afficher l'info du shift sélectionné
                            if shift == "Jour":
                                st.caption("🌅 Shift Jour : 5h30 - 18h00")
                            else:
                                st.caption("🌙 Shift Nuit : 18h30 - 5h00")
                        with col_shift_date2:
                            entry_date = st.date_input(
                                "Date de l'entrée *",
                                value=date.today(),
                                help="Date à laquelle ces données ont été collectées",
                                key="ingenierie_entry_date"
                            )
                        
                        st.markdown("---")
                        
                        col_data1, col_data2, col_data3 = st.columns(3)
                        
                        with col_data1:
                            st.markdown("#### ⏱️ Heures (H-mètre)")
                            compteur_debut = st.number_input(
                                "H-mètre début",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                help="Lecture compteur horaire au début de la période",
                                key="ingenierie_h_debut"
                            )
                            compteur_fin = st.number_input(
                                "H-mètre fin",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                help="Lecture compteur horaire à la fin de la période",
                                key="ingenierie_h_fin"
                            )
                            if compteur_fin >= compteur_debut:
                                hours_worked = max(0.0, compteur_fin - compteur_debut)
                            else:
                                hours_worked = 0.0
                            if (compteur_debut > 0 or compteur_fin > 0) and (
                                compteur_debut == 0 or compteur_fin == 0 or compteur_fin <= compteur_debut
                            ):
                                st.warning(
                                    "⚠️ H-mètre : renseignez **début** et **fin** (fin > début), ou laissez les deux à 0."
                                )
                            st.caption(f"Heures travaillées (calculées): **{hours_worked:.2f} h** (fin − début)")
                            st.caption(f"Heures moteur en base: {selected_machine.engine_hours:.1f} h → après enregistrement: {selected_machine.engine_hours + hours_worked:.1f} h")
                        
                        with col_data2:
                            st.markdown("#### 📦 Production")
                            production_tonnes = st.number_input(
                                "Production en tonnes",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                help="Production réalisée en tonnes",
                                key="ingenierie_production"
                            )
                            st.caption(f"Production actuelle: {int(selected_machine.production_tonnes)} T")
                            st.caption(f"Nouvelle production: {int(selected_machine.production_tonnes + production_tonnes)} T")
                        
                        with col_data3:
                            st.markdown("#### ⛽ Carburant (chargements)")
                            fuel_consumed = st.number_input(
                                "Litres chargés sur la période (L)",
                                min_value=0.0,
                                value=0.0,
                                step=0.1,
                                help="Total des litres mis en réservoir (pleins). Sans débitmètre, cela sert de consommation pour la période.",
                                key="ingenierie_fuel"
                            )
                            st.caption(f"Conso. jour en base: {selected_machine.cons_jour:.1f} L → après: {selected_machine.cons_jour + fuel_consumed:.1f} L")
                        
                        st.markdown("---")
                        
                        # Calculs automatiques (prévisualisation)
                        if hours_worked > 0 or production_tonnes > 0 or fuel_consumed > 0:
                            st.markdown("#### 📊 Calculs Automatiques (Prévisualisation)")
                            
                            # Calculs basés sur les nouvelles valeurs
                            new_engine_hours = selected_machine.engine_hours + hours_worked
                            new_production = selected_machine.production_tonnes + production_tonnes
                            new_cons_jour = selected_machine.cons_jour + fuel_consumed
                            
                            # Calculer les cycles (production / capacité)
                            if selected_machine.capacity > 0:
                                new_cycles = selected_machine.cycle + (production_tonnes / selected_machine.capacity)
                            else:
                                new_cycles = selected_machine.cycle
                            
                            # Calculer les revenus
                            new_h_jour = selected_machine.h_jour + hours_worked
                            new_h_semaine = selected_machine.h_semaine + hours_worked
                            new_h_mois = selected_machine.h_mois + hours_worked
                            
                            revenu_jour = new_h_jour * selected_machine.hourly_rate
                            revenu_hebdo = new_h_semaine * selected_machine.hourly_rate
                            revenu_mensuel = new_h_mois * selected_machine.hourly_rate
                            
                            # Coût du carburant (prix moyen: 1.5 USD/L)
                            fuel_price_avg = 1.5
                            cout_fuel = new_cons_jour * fuel_price_avg
                            
                            # Rentabilité
                            rentabilite = revenu_jour - cout_fuel
                            
                            # Consommation par cycle
                            cons_par_cycle = new_cons_jour / new_cycles if new_cycles > 0 else 0
                            
                            # Consommation par shift (3 shifts par jour)
                            cons_par_shift = new_cons_jour / 3
                            
                            # Temps de cycle moyen (en minutes)
                            avg_cycle_time = (new_h_jour * 60) / new_cycles if new_cycles > 0 else 0
                            
                            # Afficher les calculs (sans montants $ si pas d'accès Finance)
                            if _ingenierie_finance_visible:
                                col_calc1, col_calc2, col_calc3, col_calc4 = st.columns(4)
                                with col_calc1:
                                    st.metric("Revenu journalier", f"${int(revenu_jour):,}")
                                    st.metric("Revenu hebdomadaire", f"${int(revenu_hebdo):,}")
                                    st.metric("Revenu mensuel", f"${int(revenu_mensuel):,}")
                                with col_calc2:
                                    st.metric("Coût carburant", f"${int(cout_fuel):,}")
                                    st.metric(
                                        "Rentabilité",
                                        f"${int(rentabilite):,}",
                                        delta=f"{int(rentabilite - (selected_machine.h_jour * selected_machine.hourly_rate - selected_machine.cons_jour * fuel_price_avg))}",
                                    )
                                with col_calc3:
                                    st.metric("Cycles totaux", f"{int(new_cycles)}")
                                    st.metric("Cons. par cycle", f"{round(cons_par_cycle, 1)} L")
                                    st.metric("Cons. par shift", f"{round(cons_par_shift, 1)} L")
                                with col_calc4:
                                    st.metric("Temps cycle moyen", f"{round(avg_cycle_time, 1)} min")
                                    st.metric("H. jour", f"{round(new_h_jour, 1)} h")
                                    st.metric("H. semaine", f"{round(new_h_semaine, 1)} h")
                            else:
                                col_op1, col_op2 = st.columns(2)
                                with col_op1:
                                    st.metric("Cycles totaux", f"{int(new_cycles)}")
                                    st.metric("Cons. par cycle", f"{round(cons_par_cycle, 1)} L")
                                    st.metric("Cons. par shift", f"{round(cons_par_shift, 1)} L")
                                with col_op2:
                                    st.metric("Temps cycle moyen", f"{round(avg_cycle_time, 1)} min")
                                    st.metric("H. jour", f"{round(new_h_jour, 1)} h")
                                    st.metric("H. semaine", f"{round(new_h_semaine, 1)} h")
                            
                            st.markdown("---")
                        
                        # Options supplémentaires
                        st.markdown("#### ⚙️ Options")
                        col_opt1, col_opt2 = st.columns(2)
                        
                        with col_opt1:
                            update_period = st.selectbox(
                                "Période de mise à jour",
                                ["Journalière", "Hebdomadaire", "Mensuelle", "Toutes"],
                                help="Sélectionnez quelle période mettre à jour",
                                key="ingenierie_period"
                            )
                        
                        with col_opt2:
                            if _ingenierie_finance_visible:
                                fuel_price = st.number_input(
                                    "Prix du carburant (USD/L)",
                                    min_value=0.0,
                                    value=1.5,
                                    step=0.01,
                                    help="Prix du carburant pour les calculs et la comptabilité",
                                    key="ingenierie_fuel_price",
                                )
                            else:
                                fuel_price = 1.5
                                st.caption(
                                    "Prix carburant : valeur interne par défaut (1,50 USD/L) pour l'enregistrement. "
                                    "L'ajustement et la vision financière sont dans **Finance**."
                                )
                        
                        submitted = st.form_submit_button("✅ ENREGISTRER LES DONNÉES", use_container_width=True, type="primary")
                        
                        if submitted:
                            # Recalcul fiable des heures à partir du compteur (fin − début)
                            if compteur_debut == 0.0 and compteur_fin == 0.0:
                                hours_worked_submit = 0.0
                            elif compteur_debut > 0.0 and compteur_fin > compteur_debut:
                                hours_worked_submit = compteur_fin - compteur_debut
                            else:
                                hours_worked_submit = None

                            if hours_worked_submit is None:
                                st.error(
                                    "❌ H-mètre invalide : indiquez **début** et **fin** avec fin > début, ou laissez les deux à 0."
                                )
                            elif hours_worked_submit == 0 and production_tonnes == 0 and fuel_consumed == 0:
                                st.warning("⚠️ Veuillez entrer au moins une valeur (H-mètre début/fin, production ou litres chargés)")
                            else:
                                try:
                                    hours_worked = hours_worked_submit
                                    # Calculer les valeurs finales pour l'historique
                                    new_engine_hours = selected_machine.engine_hours + hours_worked
                                    new_production = selected_machine.production_tonnes + production_tonnes
                                    new_cons_jour = selected_machine.cons_jour + fuel_consumed
                                    
                                    # Calculer les cycles
                                    cycles_added = 0
                                    if production_tonnes > 0 and selected_machine.capacity > 0:
                                        cycles_added = production_tonnes / selected_machine.capacity
                                    
                                    # Calculer les revenus
                                    new_h_jour = selected_machine.h_jour + hours_worked
                                    new_h_semaine = selected_machine.h_semaine + hours_worked
                                    new_h_mois = selected_machine.h_mois + hours_worked
                                    
                                    revenu_jour = new_h_jour * selected_machine.hourly_rate
                                    revenu_hebdo = new_h_semaine * selected_machine.hourly_rate
                                    revenu_mois = new_h_mois * selected_machine.hourly_rate
                                    
                                    # Coût et rentabilité
                                    cout_fuel = new_cons_jour * fuel_price
                                    rentabilite = revenu_jour - cout_fuel
                                    
                                    # Consommation par cycle et shift
                                    new_cycles = selected_machine.cycle + cycles_added
                                    cons_par_cycle = new_cons_jour / new_cycles if new_cycles > 0 else 0
                                    cons_par_shift = new_cons_jour / 3
                                    
                                    # Temps de cycle moyen
                                    avg_cycle_time = (new_h_jour * 60) / new_cycles if new_cycles > 0 else 0
                                    
                                    # Mettre à jour les heures
                                    if hours_worked > 0:
                                        selected_machine.engine_hours += hours_worked
                                        selected_machine.h_jour += hours_worked
                                        if update_period in ["Hebdomadaire", "Mensuelle", "Toutes"]:
                                            selected_machine.h_semaine += hours_worked
                                        if update_period in ["Mensuelle", "Toutes"]:
                                            selected_machine.h_mois += hours_worked
                                    
                                    # Mettre à jour la production
                                    if production_tonnes > 0:
                                        selected_machine.production_tonnes += production_tonnes
                                        selected_machine.cycle += cycles_added
                                    
                                    # Mettre à jour le carburant (litres chargés = proxy de conso pour les indicateurs)
                                    if fuel_consumed > 0:
                                        selected_machine.cons_jour += fuel_consumed
                                        if update_period in ["Hebdomadaire", "Mensuelle", "Toutes"]:
                                            selected_machine.cons_mois += fuel_consumed
                                        if update_period in ["Mensuelle", "Toutes"]:
                                            selected_machine.cons_annee += fuel_consumed
                                        selected_machine.cons_total += fuel_consumed
                                        # Réservoir : les litres saisis sont des chargements → hausse estimée du %
                                        tank_capacity_liters = 1000
                                        fuel_tank_increase = (fuel_consumed / tank_capacity_liters) * 100
                                        selected_machine.fuel_tank = min(
                                            100, selected_machine.fuel_tank + fuel_tank_increase
                                        )
                                    
                                    # Sauvegarder dans la base de données
                                    selected_machine.save_to_db()
                                    
                                    # Sauvegarder dans l'historique des entrées manuelles
                                    current_user = st.session_state.get('username', 'Système')
                                    save_manual_entry(
                                        machine_id=selected_machine_id,
                                        shift=shift,
                                        entry_date=entry_date.strftime('%Y-%m-%d'),
                                        hours_worked=hours_worked,
                                        production_tonnes=production_tonnes,
                                        fuel_consumed=fuel_consumed,
                                        fuel_price_usd=fuel_price,
                                        update_period=update_period,
                                        revenue_jour=revenu_jour,
                                        revenue_hebdo=revenu_hebdo,
                                        revenue_mois=revenu_mois,
                                        cost_fuel=cout_fuel,
                                        profitability=rentabilite,
                                        cycles_added=cycles_added,
                                        cons_per_cycle=cons_par_cycle,
                                        cons_per_shift=cons_par_shift,
                                        avg_cycle_time=avg_cycle_time,
                                        entered_by=current_user
                                    )
                                    
                                    # Enregistrer dans les logs d'audit
                                    audit_mgr.log_action(
                                        "UPDATE", "MACHINE", selected_machine_id, selected_machine_id,
                                        current_user,
                                        changes={
                                            "Shift": shift,
                                            "Date": entry_date.strftime('%Y-%m-%d'),
                                            "H-mètre début": compteur_debut,
                                            "H-mètre fin": compteur_fin,
                                            "Heures (fin − début)": hours_worked,
                                            "Production ajoutée": production_tonnes,
                                            "Litres chargés (conso proxy)": fuel_consumed,
                                            "Période": update_period
                                        },
                                        details=f"Entrée manuelle ingénierie pour {selected_machine_id} - {shift}"
                                    )
                                    
                                    st.success(f"✅ Données enregistrées avec succès pour {selected_machine_id} - {shift} !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur lors de l'enregistrement: {str(e)}")
                else:
                    st.warning("⚠️ Engin non trouvé dans la flotte.")
            else:
                st.info("ℹ️ Veuillez sélectionner un engin pour commencer.")
        
        st.markdown('</div>', unsafe_allow_html=True)

# --- ADMIN ---
if "ADMIN" in tab_dict:
    with tab_dict["ADMIN"]:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.subheader("⚙️ GESTION DES UTILISATEURS")
        st.markdown('</div>', unsafe_allow_html=True)
        
        # Onglets internes ADMIN
        admin_tabs = st.tabs(["📋 Liste Utilisateurs", "➕ Ajouter Utilisateur", "✏️ Modifier Utilisateur", "🗑️ Supprimer Utilisateur", "🖼️ Images Engins", "🎨 Logo Entreprise", "💳 Gestion Plan", "🗑️ Réinitialiser Données", "💾 Sauvegarde/Restauration", "📊 Logs d'Audit"])
        
        # --- TAB 1: LISTE DES UTILISATEURS ---
        with admin_tabs[0]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📋 Liste des Utilisateurs")
            
            df_users = user_mgr.get_users_df()
            _utid_admin = _safe_tenant_id(st.session_state.get("tenant_id", "default"))
            if not df_users.empty and "Entreprise (id)" in df_users.columns:
                df_users = df_users[df_users["Entreprise (id)"] == _utid_admin]
            if not df_users.empty:
                st.dataframe(df_users, width='stretch', hide_index=True)
                
                st.markdown("---")
                st.markdown("#### 📊 Statistiques")
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Total Utilisateurs", len(df_users))
                with col2:
                    roles_count = df_users["Rôle"].value_counts()
                    st.write("**Répartition par rôle:**")
                    for role, count in roles_count.items():
                        st.write(f"- {role}: {count}")
            else:
                st.info("Aucun utilisateur enregistré.")
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 2: AJOUTER UN UTILISATEUR ---
        with admin_tabs[1]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("➕ Ajouter un Nouvel Utilisateur")
            
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%); 
                        padding: 20px; border-radius: 15px; margin-bottom: 20px; border: 2px solid #F5B800;">
                <h4 style="color: #F5B800; margin: 0 0 10px 0;">📋 Règles de Création de Compte :</h4>
                <ul style="color: #e0e0e0; margin: 0; padding-left: 20px; font-size: 16px;">
                    <li><strong>Invite</strong> : Peut être créé sans être enregistré dans RH</li>
                    <li><strong>Tous les autres rôles</strong> : L'employé doit être enregistré dans RH avant de créer un compte</li>
                    <li>Chaque employé ne peut avoir qu'<strong>un seul compte</strong></li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            with st.form("add_user_form"):
                # Modes de création : Invité libre ou Employé RH
                creation_mode = st.radio(
                    "Mode de Création *",
                    ["👤 Compte pour un Employé RH", "👥 Compte Invité"],
                    help="Sélectionnez si vous créez un compte pour un employé enregistré dans RH ou un compte Invité",
                    horizontal=True
                )
                
                selected_employee = None
                new_role = None
                
                if creation_mode == "👤 Compte pour un Employé RH":
                    # Afficher tous les employés RH disponibles, puis filtrer par rôle après sélection
                    st.markdown("---")
                    st.markdown("#### 👤 Sélectionner un Employé depuis RH")
                    
                    # Récupérer uniquement les employés actifs (pour la création de compte)
                    all_employees = staff_mgr.get_active_staff()
                    existing_usernames = [u['user'] for u in user_mgr.users_in_current_tenant()]
                    employees_without_account = []
                    employees_with_account = []
                    
                    for emp in all_employees:
                        # Vérifier si l'employé a déjà un compte (matching plus précis)
                        has_account = False
                        emp_name_normalized = emp.name.lower().replace(' ', '_').replace('-', '_')
                        emp_name_words = set(emp.name.lower().split())
                        
                        for u in existing_usernames:
                            u_lower = u.lower()
                            # Correspondance exacte ou proche (nom d'utilisateur = nom employé normalisé)
                            if u_lower == emp_name_normalized:
                                has_account = True
                                break
                            # Correspondance si le nom d'utilisateur contient tous les mots du nom de l'employé
                            # ou si le nom de l'employé contient tous les mots du nom d'utilisateur
                            u_words = set(u_lower.replace('_', ' ').replace('-', ' ').split())
                            # Vérifier si au moins 2 mots correspondent (pour éviter les faux positifs)
                            common_words = emp_name_words.intersection(u_words)
                            if len(common_words) >= 2 and len(common_words) >= min(len(emp_name_words), len(u_words)) * 0.5:
                                has_account = True
                                break
                            # Correspondance si le nom d'utilisateur est une sous-chaîne significative du nom
                            # (au moins 4 caractères pour éviter les faux positifs)
                            if len(emp_name_normalized) >= 4 and emp_name_normalized in u_lower:
                                has_account = True
                                break
                            if len(u_lower) >= 4 and u_lower in emp_name_normalized:
                                has_account = True
                                break
                        
                        if not has_account:
                            # Générer un nom d'utilisateur suggéré
                            username_from_name = emp.name.lower().replace(' ', '_').replace('-', '_')
                            employees_without_account.append({
                                'employee': emp,
                                'suggested_username': username_from_name
                            })
                        else:
                            employees_with_account.append(emp)
                    
                    if employees_without_account:
                        # Afficher les employés sans compte
                        employee_options = {f"{emp['employee'].name} ({emp['employee'].matricule}) - Rôle RH: {emp['employee'].role}": emp 
                                          for emp in employees_without_account}
                        selected_employee_display = st.selectbox(
                            "Choisir un Employé *",
                            ["Sélectionner..."] + list(employee_options.keys()),
                            key="select_employee_admin"
                        )
                        
                        if selected_employee_display and selected_employee_display != "Sélectionner...":
                            selected_employee = employee_options[selected_employee_display]
                            emp_info = selected_employee['employee']
                            
                            # Le rôle est automatiquement défini selon le rôle RH de l'employé
                            new_role = emp_info.role  # Rôle depuis RH
                            
                            # Nom d'utilisateur suggéré
                            suggested_username = selected_employee['suggested_username']
                            
                            # Afficher les infos de l'employé sélectionné
                            st.markdown("---")
                            col_emp1, col_emp2, col_emp3 = st.columns(3)
                            with col_emp1:
                                st.info(f"**👤 Nom :** {emp_info.name}\n\n**🆔 Matricule :** {emp_info.matricule}")
                            with col_emp2:
                                st.info(f"**📋 Rôle RH :** {emp_info.role}\n\n**👥 Équipe :** {emp_info.team}")
                            with col_emp3:
                                st.info(f"**🕐 Shift :** {emp_info.shift_type}\n\n**📅 Arrivée :** {emp_info.date_arrivee.strftime('%d/%m/%Y') if hasattr(emp_info.date_arrivee, 'strftime') else 'N/A'}")
                            
                            # Afficher le rôle qui sera assigné (non modifiable)
                            st.markdown(f"""
                            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.2) 0%, rgba(255, 165, 0, 0.2) 100%); 
                                        padding: 15px; border-radius: 10px; border: 2px solid #F5B800; margin: 15px 0;">
                                <p style="color: #F5B800; font-size: 18px; font-weight: 700; margin: 0;">
                                    ✅ Rôle du compte : <strong>{new_role}</strong> (basé sur le rôle RH de l'employé)
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            # Aucun employé sélectionné
                            selected_employee = None
                            suggested_username = ""
                            new_role = None
                    else:
                        st.warning("⚠️ Tous les employés enregistrés dans RH ont déjà un compte.")
                        selected_employee = None
                        suggested_username = ""
                        new_role = None
                    
                    # Afficher les employés qui ont déjà un compte (pour information)
                    if employees_with_account:
                        with st.expander(f"ℹ️ Employés ayant déjà un compte ({len(employees_with_account)})"):
                            for emp in employees_with_account[:10]:  # Limiter à 10 pour l'affichage
                                # Trouver le nom d'utilisateur correspondant
                                matching_username = next((u for u in existing_usernames 
                                                        if emp.name.lower() in u.lower() or u.lower() in emp.name.lower()), "N/A")
                                st.write(f"- **{emp.name}** ({emp.matricule}) - Rôle: {emp.role} → Compte: `{matching_username}`")
                            if len(employees_with_account) > 10:
                                st.caption(f"... et {len(employees_with_account) - 10} autres employés")
                
                else:  # Mode Invité
                    st.markdown("---")
                    st.markdown("#### 👥 Création de Compte Invité")
                    st.info("ℹ️ Les comptes Invité peuvent être créés librement sans être enregistrés dans RH.")
                    new_role = "Invite"
                    suggested_username = ""
                
                st.markdown("---")
                
                # Champs nom d'utilisateur et mot de passe
                col_user, col_pass = st.columns(2)
                with col_user:
                    if creation_mode == "👤 Compte pour un Employé RH":
                        if selected_employee:
                            # Pré-remplir avec le nom d'utilisateur suggéré
                            new_username = st.text_input(
                                "Nom d'utilisateur *", 
                                value=suggested_username,
                                placeholder="Ex: jean_dupont",
                                key="username_input",
                                help="Le nom d'utilisateur est généré automatiquement à partir du nom de l'employé. Vous pouvez le modifier si nécessaire."
                            )
                        else:
                            new_username = st.text_input("Nom d'utilisateur *", placeholder="Sélectionnez d'abord un employé", disabled=True, key="username_input")
                            st.warning("⚠️ Veuillez sélectionner un employé dans RH pour continuer.")
                    else:  # Invité
                        new_username = st.text_input("Nom d'utilisateur *", placeholder="Ex: invite_01", key="username_input")
                
                with col_pass:
                    new_password = st.text_input("Mot de passe *", type="password", placeholder="Définir un mot de passe", key="password_input")
                
                st.markdown("---")
                
                # Sélection du type d'opérateur (seulement si le rôle est "Operateur")
                operator_type = None
                if new_role == "Operateur":
                    st.markdown("#### 🚛 Type d'Opérateur *")
                    operator_type = st.selectbox(
                        "Choisir le type d'opérateur",
                        ["📦 Opérateur de Chargement", "🚚 Opérateur de Déchargement (Transport)"],
                        key="operator_type_select",
                        help="Sélectionnez si cet opérateur est responsable du chargement ou du déchargement/transport"
                    )
                    if operator_type == "📦 Opérateur de Chargement":
                        operator_type = "loader"
                    elif operator_type == "🚚 Opérateur de Déchargement (Transport)":
                        operator_type = "dumper"
                
                st.markdown("---")
                st.markdown("#### 🔐 Permissions Personnalisées")
                st.caption("Cochez les cases pour personnaliser les permissions (optionnel - les permissions par défaut du rôle seront utilisées si non modifiées)")
                
                # Permissions personnalisées (seulement si un rôle est défini)
                if new_role:
                    st.markdown("---")
                    st.markdown("#### 🔐 Permissions Personnalisées")
                    st.caption("Cochez les cases pour personnaliser les permissions (optionnel - les permissions par défaut du rôle seront utilisées si non modifiées)")
                    
                    # Permissions par onglets
                    col_perm1, col_perm2 = st.columns(2)
                    with col_perm1:
                        st.markdown("**Accès aux Onglets:**")
                        default_perms = user_mgr.default_permissions.get(new_role, {})
                        perm_dashboard = st.checkbox("Dashboard", value=default_perms.get('dashboard', True))
                        perm_cycles = st.checkbox("Cycles", value=default_perms.get('cycles', False))
                        perm_carburant = st.checkbox("Carburant", value=default_perms.get('carburant', False))
                        perm_maintenance = st.checkbox("Maintenance", value=default_perms.get('maintenance', False))
                        perm_stock = st.checkbox("Stock", value=default_perms.get('stock', False))
                        perm_carte = st.checkbox("Carte", value=default_perms.get('carte', False))
                        perm_finance = st.checkbox("Finance", value=default_perms.get('finance', False))
                        perm_rh = st.checkbox("RH", value=default_perms.get('rh', False))
                        perm_admin = st.checkbox("Admin", value=default_perms.get('admin', False))
                        perm_validation_operateur = st.checkbox("Validation Opérateur", value=default_perms.get('validation_operateur', False))
                        perm_messagerie = st.checkbox("Messagerie / communiqués", value=default_perms.get('messagerie', True))
                        perm_sst = st.checkbox("Santé & sécurité (SST)", value=default_perms.get('sst', True))
                    
                    with col_perm2:
                        st.markdown("**Actions Autorisées:**")
                        perm_export = st.checkbox("Export de données", value=default_perms.get('can_export', False))
                        perm_modify = st.checkbox("Modifier les données", value=default_perms.get('can_modify_data', False))
                        perm_view_all = st.checkbox("Voir toutes les données", value=default_perms.get('can_view_all', False))
                else:
                    # Valeurs par défaut si pas de rôle encore défini
                    perm_dashboard = True
                    perm_cycles = False
                    perm_carburant = False
                    perm_maintenance = False
                    perm_stock = False
                    perm_carte = False
                    perm_finance = False
                    perm_rh = False
                    perm_admin = False
                    perm_validation_operateur = False
                    perm_messagerie = True
                    perm_sst = True
                    perm_export = False
                    perm_modify = False
                    perm_view_all = False
                
                use_custom_permissions = st.checkbox("Utiliser les permissions personnalisées au lieu des permissions par défaut du rôle")
                
                if st.form_submit_button("✅ CRÉER L'UTILISATEUR", use_container_width=True):
                    # Vérifications
                    if not new_username or not new_password:
                        st.warning("⚠️ Veuillez remplir tous les champs obligatoires.")
                    elif creation_mode == "👤 Compte pour un Employé RH" and not selected_employee:
                        st.error("❌ Veuillez sélectionner un employé depuis RH.")
                    elif not new_role:
                        st.error("❌ Le rôle n'a pas été défini. Veuillez sélectionner un employé ou choisir le mode Invité.")
                    elif new_role == "Operateur" and not operator_type:
                        st.error("❌ Veuillez sélectionner le type d'opérateur (Chargement ou Déchargement).")
                    else:
                        # Vérifier que le nom d'utilisateur n'existe pas déjà
                        existing_usernames = [u['user'] for u in user_mgr.users_db]
                        if new_username in existing_usernames:
                            st.error(f"❌ Erreur : Le nom d'utilisateur '{new_username}' existe déjà.")
                        else:
                            if use_custom_permissions:
                                custom_perms = {
                                    "dashboard": perm_dashboard,
                                    "cycles": perm_cycles,
                                    "carburant": perm_carburant,
                                    "maintenance": perm_maintenance,
                                    "stock": perm_stock,
                                    "carte": perm_carte,
                                    "finance": perm_finance,
                                    "rh": perm_rh,
                                    "admin": perm_admin,
                                    "validation_operateur": perm_validation_operateur,
                                    "messagerie": perm_messagerie,
                                    "sst": perm_sst,
                                    "can_add_users": False,
                                    "can_modify_users": False,
                                    "can_delete_users": False,
                                    "can_view_all": perm_view_all,
                                    "can_export": perm_export,
                                    "can_modify_data": perm_modify
                                }
                            else:
                                custom_perms = None
                            
                            _tid_new = st.session_state.get("tenant_id", "default")
                            if user_mgr.add_user(
                                new_username, new_password, new_role, custom_perms, tenant_id=_tid_new
                            ):
                                # Ajouter le type d'opérateur aux données utilisateur si applicable
                                if new_role == "Operateur" and operator_type:
                                    created_user = user_mgr.get_user(new_username)
                                    if created_user:
                                        created_user['operator_type'] = operator_type
                                        user_mgr.persist_users()
                                
                                # Enregistrer dans les logs d'audit
                                current_user = st.session_state.get('username', 'Système')
                                changes = {"Rôle": new_role, "Mode": creation_mode}
                                if operator_type:
                                    changes["Type Opérateur"] = operator_type
                                audit_mgr.log_action(
                                    "CREATE", "USER", new_username, new_username,
                                    current_user,
                                    changes=changes,
                                    details=f"Création d'un nouvel utilisateur"
                                )
                                if creation_mode == "👥 Compte Invité":
                                    st.success(f"✅ Compte Invité '{new_username}' créé avec succès !\n\n**Rôle :** {new_role}")
                                else:
                                    emp_name = selected_employee['employee'].name
                                    emp_matricule = selected_employee['employee'].matricule
                                    st.success(f"""
                                    ✅ **Compte créé avec succès !**
                                    
                                    **👤 Employé :** {emp_name} ({emp_matricule})
                                    **👤 Nom d'utilisateur :** {new_username}
                                    **📋 Rôle :** {new_role} (basé sur le rôle RH de l'employé)
                                    """)
                                st.rerun()
                            else:
                                st.error("❌ Erreur lors de la création du compte.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 3: MODIFIER UN UTILISATEUR ---
        with admin_tabs[2]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("✏️ Modifier un Utilisateur")
            st.caption(
                "Vous pouvez **définir un nouveau mot de passe** pour un utilisateur de votre entreprise sans connaître l'ancien "
                "(réservé aux comptes disposant de l'onglet ADMIN)."
            )
            
            existing_users = [u['user'] for u in user_mgr.users_in_current_tenant()]
            if existing_users:
                selected_user = st.selectbox("Sélectionner l'utilisateur à modifier", existing_users)
                user_data = user_mgr.get_user(selected_user)
                
                if user_data:
                    with st.form("modify_user_form"):
                        st.markdown(f"**Modification de : {selected_user}**")
                        
                        col_pass, col_role = st.columns(2)
                        with col_pass:
                            new_pass = st.text_input("Nouveau mot de passe", type="password", placeholder="Laisser vide pour ne pas changer")
                            new_pass_confirm = st.text_input(
                                "Confirmer le nouveau mot de passe",
                                type="password",
                                placeholder="Obligatoire si vous changez le mot de passe",
                                key="mod_user_pass_confirm",
                            )
                        with col_role:
                            roles_list = ["Ingenieur", "RH", "Invite", "Superviseur Production", "Superviseur Mecanicien", "Operateur", "Administrateur"]
                            current_role_index = 0
                            if user_data['role'] in roles_list:
                                current_role_index = roles_list.index(user_data['role'])
                            new_role_sel = st.selectbox(
                                "Nouveau rôle",
                                roles_list,
                                index=current_role_index
                            )
                        
                        # Sélection du type d'opérateur (seulement si le rôle est "Operateur")
                        mod_operator_type = None
                        if new_role_sel == "Operateur":
                            st.markdown("---")
                            st.markdown("#### 🚛 Type d'Opérateur")
                            current_operator_type = user_data.get('operator_type', 'loader')
                            operator_type_options = ["📦 Opérateur de Chargement", "🚚 Opérateur de Déchargement (Transport)"]
                            current_index = 0 if current_operator_type == "loader" else 1
                            mod_operator_type_selected = st.selectbox(
                                "Choisir le type d'opérateur",
                                operator_type_options,
                                index=current_index,
                                key="mod_operator_type_select",
                                help="Sélectionnez si cet opérateur est responsable du chargement ou du déchargement/transport"
                            )
                            if mod_operator_type_selected == "📦 Opérateur de Chargement":
                                mod_operator_type = "loader"
                            elif mod_operator_type_selected == "🚚 Opérateur de Déchargement (Transport)":
                                mod_operator_type = "dumper"
                        
                        st.markdown("---")
                        st.markdown("#### 🔐 Modifier les Permissions")
                        
                        current_perms = user_data.get('permissions', {})
                        col_perm1, col_perm2 = st.columns(2)
                        with col_perm1:
                            st.markdown("**Accès aux Onglets:**")
                            mod_perm_dashboard = st.checkbox("Dashboard", value=current_perms.get('dashboard', False), key="mod_dash")
                            mod_perm_cycles = st.checkbox("Cycles", value=current_perms.get('cycles', False), key="mod_cycles")
                            mod_perm_carburant = st.checkbox("Carburant", value=current_perms.get('carburant', False), key="mod_carb")
                            mod_perm_maintenance = st.checkbox("Maintenance", value=current_perms.get('maintenance', False), key="mod_maint")
                            mod_perm_stock = st.checkbox("Stock", value=current_perms.get('stock', False), key="mod_stock")
                            mod_perm_carte = st.checkbox("Carte", value=current_perms.get('carte', False), key="mod_carte")
                            mod_perm_finance = st.checkbox("Finance", value=current_perms.get('finance', False), key="mod_fin")
                            mod_perm_rh = st.checkbox("RH", value=current_perms.get('rh', False), key="mod_rh")
                            mod_perm_admin = st.checkbox("Admin", value=current_perms.get('admin', False), key="mod_admin")
                            mod_perm_validation_operateur = st.checkbox("Validation Opérateur", value=current_perms.get('validation_operateur', False), key="mod_val_operateur")
                            mod_perm_messagerie = st.checkbox("Messagerie / communiqués", value=current_perms.get('messagerie', True), key="mod_msg")
                            mod_perm_sst = st.checkbox("Santé & sécurité (SST)", value=current_perms.get('sst', True), key="mod_sst")
                        
                        with col_perm2:
                            st.markdown("**Actions Autorisées:**")
                            mod_perm_export = st.checkbox("Export de données", value=current_perms.get('can_export', False), key="mod_export")
                            mod_perm_modify = st.checkbox("Modifier les données", value=current_perms.get('can_modify_data', False), key="mod_modify")
                            mod_perm_view_all = st.checkbox("Voir toutes les données", value=current_perms.get('can_view_all', False), key="mod_view")
                        
                        if st.form_submit_button("✅ MODIFIER L'UTILISATEUR", use_container_width=True):
                            pwd_err = None
                            if new_pass and new_pass != new_pass_confirm:
                                pwd_err = "❌ Les deux saisies du nouveau mot de passe ne correspondent pas."
                            elif new_pass and len(new_pass.strip()) < 4:
                                pwd_err = "❌ Le mot de passe doit contenir au moins 4 caractères."
                            if pwd_err:
                                st.error(pwd_err)
                            else:
                                updated_perms = {
                                    "dashboard": mod_perm_dashboard,
                                    "cycles": mod_perm_cycles,
                                    "carburant": mod_perm_carburant,
                                    "maintenance": mod_perm_maintenance,
                                    "stock": mod_perm_stock,
                                    "carte": mod_perm_carte,
                                    "finance": mod_perm_finance,
                                    "rh": mod_perm_rh,
                                    "admin": mod_perm_admin,
                                    "validation_operateur": mod_perm_validation_operateur,
                                    "messagerie": mod_perm_messagerie,
                                    "sst": mod_perm_sst,
                                    "can_add_users": False,
                                    "can_modify_users": False,
                                    "can_delete_users": False,
                                    "can_view_all": mod_perm_view_all,
                                    "can_export": mod_perm_export,
                                    "can_modify_data": mod_perm_modify
                                }
                                tpl_role = user_mgr.default_permissions.get(new_role_sel)
                                if tpl_role:
                                    for k, v in tpl_role.items():
                                        if k not in updated_perms:
                                            updated_perms[k] = v
                                if user_mgr.update_user(
                                    selected_user,
                                    password=new_pass if new_pass else None,
                                    role=new_role_sel,
                                    permissions=updated_perms,
                                ):
                                    updated_user = user_mgr.get_user(selected_user)
                                    if updated_user:
                                        if new_role_sel == "Operateur" and mod_operator_type:
                                            updated_user["operator_type"] = mod_operator_type
                                        elif new_role_sel != "Operateur" and "operator_type" in updated_user:
                                            del updated_user["operator_type"]
                                        user_mgr.persist_users()
                                    current_user = st.session_state.get("username", "Système")
                                    changes_dict = {}
                                    if new_pass:
                                        changes_dict["Mot de passe"] = "Modifié"
                                    if new_role_sel:
                                        changes_dict["Rôle"] = new_role_sel
                                    if mod_operator_type:
                                        changes_dict["Type Opérateur"] = mod_operator_type
                                        old_role = None
                                        for u in user_mgr.users_db:
                                            if u["user"] == selected_user:
                                                old_role = u.get("role", "N/A")
                                                break
                                        if old_role:
                                            changes_dict["Rôle"] = {"before": old_role, "after": new_role_sel}
                                    audit_mgr.log_action(
                                        "UPDATE",
                                        "USER",
                                        selected_user,
                                        selected_user,
                                        current_user,
                                        changes=changes_dict,
                                        details=f"Modification de l'utilisateur {selected_user}",
                                    )
                                    st.success(f"✅ Utilisateur {selected_user} modifié avec succès !")
                                    st.rerun()
                                else:
                                    st.error("❌ Erreur lors de la modification.")
            else:
                st.info("Aucun utilisateur à modifier.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 4: SUPPRIMER UN UTILISATEUR ---
        with admin_tabs[3]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🗑️ Supprimer un Utilisateur")
            st.warning("⚠️ Attention : Cette action est irréversible !")
            
            users_to_delete = [
                u['user']
                for u in user_mgr.users_in_current_tenant()
                if u['user'] not in ('admin', 'gestionnaire')
            ]
            if users_to_delete:
                user_to_delete = st.selectbox("Sélectionner l'utilisateur à supprimer", users_to_delete)
                
                if st.button("🗑️ SUPPRIMER L'UTILISATEUR", type="primary", use_container_width=True):
                    if user_mgr.delete_user(user_to_delete):
                        # Enregistrer dans les logs d'audit
                        current_user = st.session_state.get('username', 'Système')
                        audit_mgr.log_action(
                            "DELETE", "USER", user_to_delete, user_to_delete,
                            current_user,
                            changes={"Action": "Suppression"},
                            details=f"Suppression de l'utilisateur {user_to_delete}"
                        )
                        st.success(f"✅ Utilisateur {user_to_delete} supprimé avec succès !")
                        st.rerun()
                    else:
                        st.error("❌ Erreur : Impossible de supprimer cet utilisateur (peut-être l'administrateur).")
            else:
                st.info("Aucun utilisateur à supprimer (l'administrateur ne peut pas être supprimé).")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 5: IMAGES ENGINS ---
        with admin_tabs[4]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🖼️ Gestion des Images d'Engins et Lingot d'Or")
            st.caption("Téléchargez vos propres images pour les engins et le lingot d'or affichés sur la page d'identification")
            
            # Liste des engins disponibles + lingot d'or
            equipments_list = ["Camions", "Excavatrices", "BULDOZER", "Chargeurs", "Foreuses", "DUMPER", "Lingot d'Or"]
            
            selected_equipment = st.selectbox(
                "Sélectionnez un engin ou le lingot d'or",
                equipments_list,
                help="Choisissez l'engin ou le lingot d'or pour lequel vous souhaitez uploader une image"
            )
            
            st.markdown("---")
            
            # Afficher l'image actuelle si elle existe
            if selected_equipment == "Lingot d'Or":
                current_image_path = get_equipment_image_path("Lingot_Or")
            else:
                current_image_path = get_equipment_image_path(selected_equipment)
            if current_image_path:
                try:
                    from PIL import Image
                    img = Image.open(current_image_path)
                    st.image(img, width=300, caption=f"Image actuelle pour {selected_equipment}")
                    if st.button("🗑️ Supprimer l'image actuelle", use_container_width=True):
                        try:
                            os.remove(current_image_path)
                            # Supprimer aussi les métadonnées de la base de données
                            if selected_equipment == "Lingot d'Or":
                                delete_image_metadata("Lingot_Or")
                            else:
                                delete_image_metadata(selected_equipment)
                            display_name = selected_equipment
                            st.success(f"✅ Image de {display_name} supprimée avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur lors de la suppression: {e}")
                except Exception as e:
                    st.warning(f"Image actuelle disponible mais erreur d'affichage: {e}")
            else:
                st.info(f"ℹ️ Aucune image personnalisée pour {selected_equipment}. L'image par défaut est utilisée.")
            
            st.markdown("---")
            
            # Upload de nouvelle image
            uploaded_file = st.file_uploader(
                f"Télécharger une image pour {selected_equipment}",
                type=['png', 'jpg', 'jpeg', 'gif', 'webp'],
                help="Formats acceptés: PNG, JPG, JPEG, GIF, WEBP. Taille recommandée: 300x200px ou plus"
            )
            
            if uploaded_file:
                # Afficher un aperçu
                try:
                    from PIL import Image
                    import io
                    uploaded_file.seek(0)
                    img_bytes = uploaded_file.read()
                    img = Image.open(io.BytesIO(img_bytes))
                    st.image(img, width=300, caption=f"Aperçu de l'image pour {selected_equipment}")
                    uploaded_file.seek(0)
                except Exception as e:
                    st.warning(f"Erreur lors de l'affichage de l'aperçu: {e}")
                
                if st.button("✅ ENREGISTRER L'IMAGE", use_container_width=True):
                    # Utiliser "Lingot_Or" comme nom de fichier pour le lingot d'or
                    equipment_name = "Lingot_Or" if selected_equipment == "Lingot d'Or" else selected_equipment
                    success, result = save_equipment_image(equipment_name, uploaded_file)
                    if success:
                        st.success(f"✅ Image de {selected_equipment} enregistrée avec succès !")
                        st.rerun()
                    else:
                        st.error(f"❌ Erreur lors de l'enregistrement: {result}")
            
            st.markdown("---")
            st.markdown("#### 📋 Instructions")
            st.markdown("""
            - Sélectionnez un engin dans la liste déroulante
            - Téléchargez une image depuis votre ordinateur
            - L'image sera automatiquement utilisée sur la page d'identification
            - Vous pouvez remplacer une image existante en uploadant une nouvelle
            - Pour revenir à l'image par défaut, supprimez l'image personnalisée
            """)
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 6: LOGO ENTREPRISE ---
        with admin_tabs[5]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🎨 Logo — barre latérale")
            _tid_logo_adm = _safe_tenant_id(st.session_state.get("tenant_id", "default"))
            _is_plat_logo = _tid_logo_adm == "__platform__"
            if _is_plat_logo:
                st.caption(
                    "Rôle **Gestionnaire** : logo **global** (dossier `logos/good_engineers_logo.png`), "
                    "utilisé lorsqu'une entreprise n'a pas de logo dédié."
                )
            else:
                st.caption(
                    "Logo **de votre entreprise** : enregistré dans votre espace (`tenant_data/…/branding/`). "
                    "Il s'affiche dans la sidebar (comme sur votre maquette) pour tous les utilisateurs du tenant."
                )

            logo_url = get_logo_url()
            _tenant_lp = None if _is_plat_logo else get_tenant_logo_path(_tid_logo_adm)
            if logo_url:
                st.markdown("#### 📸 Aperçu (sidebar)")
                st.markdown(
                    f'<img src="{logo_url}" alt="Logo" style="max-width: 400px; max-height: 200px; object-fit: contain; border: 2px solid #F5B800; border-radius: 10px; padding: 10px;">',
                    unsafe_allow_html=True,
                )
                if _tenant_lp:
                    st.caption(f"Logo **entreprise** : `{os.path.basename(_tenant_lp)}`")
                elif not _is_plat_logo:
                    st.caption("Affichage actuel : **logo global** GOOD ENGINEERS (aucun fichier dédié enregistré).")
                db = get_database()
                if "logo_metadata" in db and (_is_plat_logo or not _tenant_lp):
                    metadata = db["logo_metadata"]
                    col_info1, col_info2, col_info3 = st.columns(3)
                    with col_info1:
                        st.metric("📁 Fichier", metadata.get("file_name", "N/A"))
                    with col_info2:
                        file_size_kb = metadata.get("file_size", 0) / 1024
                        st.metric("💾 Taille", f"{file_size_kb:.2f} KB")
                    with col_info3:
                        upload_date = metadata.get("upload_date", "N/A")
                        if upload_date and upload_date != "N/A":
                            upload_date = upload_date[:10] if len(upload_date) > 10 else upload_date
                        st.metric("📅 Upload", upload_date)
                st.markdown("---")
                if st.button("🗑️ Supprimer le logo affiché", use_container_width=True, type="secondary", key="del_logo_adm"):
                    if _tenant_lp and delete_tenant_branding_logo(_tid_logo_adm):
                        st.success("Logo entreprise supprimé — retour au logo global.")
                        st.rerun()
                    elif _is_plat_logo:
                        success, message = delete_logo()
                        if success:
                            st.success(message)
                            st.rerun()
                        st.error(message)
                    elif not _tenant_lp and not _is_plat_logo:
                        st.info("Aucun logo entreprise à supprimer ; le logo global s'affiche déjà.")
                    else:
                        st.error("Suppression impossible.")
                st.markdown("---")
            else:
                st.info("Aucun logo configuré : le texte « GOOD ENGINEERS » s'affiche par défaut dans la sidebar.")
                st.markdown("---")

            st.markdown("#### 📤 Téléverser un logo")
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%); 
                        padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 2px solid #F5B800;">
                <p style="color: #F5B800; margin: 0;">ℹ️ <strong>Recommandations :</strong></p>
                <ul style="color: #e0e0e0; margin: 10px 0 0 0; padding-left: 20px;">
                    <li>PNG, JPG, JPEG, WEBP — idéal : ~400×200 px, fond transparent (PNG)</li>
                    <li>Cadre doré de la sidebar : le navigateur adapte la taille</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)

            uploaded_logo = st.file_uploader(
                "Choisir une image",
                type=["png", "jpg", "jpeg", "webp"],
                help="Enregistré pour votre entreprise ou pour la plateforme (gestionnaire).",
                key="logo_uploader",
            )

            if uploaded_logo:
                try:
                    from PIL import Image
                    import io as _io

                    uploaded_logo.seek(0)
                    img_bytes = uploaded_logo.read()
                    img = Image.open(_io.BytesIO(img_bytes))
                    st.image(img, width=400, caption="Aperçu")
                    uploaded_logo.seek(0)
                except Exception as e:
                    st.warning(f"Aperçu indisponible : {e}")

                if st.button("✅ ENREGISTRER LE LOGO", use_container_width=True, type="primary", key="save_logo_btn"):
                    uploaded_logo.seek(0)
                    if not _is_plat_logo and save_tenant_branding_logo(_tid_logo_adm, uploaded_logo):
                        st.success("Logo entreprise enregistré — visible dans la sidebar après rechargement.")
                        st.rerun()
                    elif _is_plat_logo:
                        success, message = save_logo(uploaded_logo)
                        if success:
                            st.success(message)
                            st.rerun()
                        st.error(message)
                    else:
                        st.error("Échec de l'enregistrement du logo entreprise.")

            st.markdown("</div>", unsafe_allow_html=True)
        
        # --- TAB 7: GESTION PLAN ---
        with admin_tabs[6]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("💳 Gestion du Plan d'Abonnement")
            st.caption("Gérez votre plan d'abonnement et consultez les limitations actuelles")
            
            # Informations sur le plan actuel
            plan_info = get_plan_info()
            current_plan = plan_info["plan"]
            
            st.markdown("#### 📊 Plan Actuel")
            col_plan1, col_plan2, col_plan3 = st.columns(3)
            with col_plan1:
                plan_display = {
                    "free": "🆓 GRATUIT",
                    "standard": "⭐ STANDARD",
                    "premium": "💎 PREMIUM"
                }
                st.metric("Plan", plan_display.get(current_plan, current_plan.upper()))
            with col_plan2:
                machines_display = f"{plan_info['current_machines']}/{plan_info['max_machines']}" if plan_info['max_machines'] != -1 else f"{plan_info['current_machines']}/∞"
                st.metric("Machines", machines_display)
            with col_plan3:
                users_display = f"{plan_info['current_users']}/{plan_info['max_users']}" if plan_info['max_users'] != -1 else f"{plan_info['current_users']}/∞"
                st.metric("Utilisateurs", users_display)
            
            st.markdown("---")
            
            # Changer de plan
            st.markdown("#### 🔄 Changer de Plan")
            new_plan = st.selectbox(
                "Sélectionner un nouveau plan",
                ["free", "standard", "premium"],
                index=["free", "standard", "premium"].index(current_plan) if current_plan in ["free", "standard", "premium"] else 0,
                format_func=lambda x: {
                    "free": "🆓 GRATUIT",
                    "standard": "⭐ STANDARD",
                    "premium": "💎 PREMIUM"
                }.get(x, x),
                key="select_plan"
            )
            
            if new_plan != current_plan:
                if st.button("✅ CHANGER DE PLAN", use_container_width=True, type="primary"):
                    success, message = set_plan(new_plan)
                    if success:
                        st.success(f"✅ {message}")
                        st.info("🔄 L'application va se recharger pour appliquer les changements.")
                        st.rerun()
                    else:
                        st.error(f"❌ {message}")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 8: RÉINITIALISER DONNÉES ---
        with admin_tabs[7]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("🗑️ Réinitialiser Toutes les Données de Simulation")
            st.caption("⚠️ Cette action est irréversible. Toutes les données de simulation seront supprimées et tous les compteurs seront remis à 0.")
            
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(255, 69, 0, 0.2) 0%, rgba(255, 140, 0, 0.2) 100%); 
                        padding: 20px; border-radius: 10px; margin-bottom: 20px; border: 2px solid #FF4500;">
                <p style="color: #F5B800; margin: 0; font-weight: 700;">⚠️ <strong>ATTENTION : Action Irréversible</strong></p>
                <p style="color: #e0e0e0; margin: 10px 0 0 0;">Cette action va :</p>
                <ul style="color: #e0e0e0; margin: 10px 0 0 0; padding-left: 20px;">
                    <li>Supprimer <strong>TOUS</strong> les logs de carburant</li>
                    <li>Supprimer <strong>TOUS</strong> les logs de maintenance</li>
                    <li>Supprimer <strong>TOUTES</strong> les pannes enregistrées</li>
                    <li>Supprimer <strong>TOUTES</strong> les entrées manuelles</li>
                    <li>Réinitialiser <strong>TOUS</strong> les compteurs des machines à 0 (heures, production, consommation, etc.)</li>
                </ul>
                <p style="color: #FF4500; margin: 15px 0 0 0; font-weight: 700;">Les machines elles-mêmes ne seront PAS supprimées, seulement leurs données de simulation.</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Initialiser l'état de validation si nécessaire
            if 'reset_validation_step' not in st.session_state:
                st.session_state.reset_validation_step = 0
            
            # Étape 1 : Première confirmation
            if st.session_state.reset_validation_step == 0:
                st.markdown("""
                <div style="padding: 15px; background: #252538; border-radius: 10px; border: 1px solid #333344; margin-bottom: 20px;">
                    <p style="color: #F5B800; margin: 0; font-weight: 700;">ℹ️ Informations</p>
                    <p style="color: #e0e0e0; margin: 10px 0 0 0; font-size: 14px;">
                        Après la réinitialisation, vous devrez entrer manuellement toutes les nouvelles données.
                        Les machines existantes seront conservées mais avec tous leurs compteurs à 0.
                    </p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button("🗑️ COMMENCER LA RÉINITIALISATION", use_container_width=True, type="primary"):
                    st.session_state.reset_validation_step = 1
                    st.rerun()
            
            # Étape 2 : Deuxième confirmation
            elif st.session_state.reset_validation_step == 1:
                st.error("""
                ⚠️ **PREMIÈRE VALIDATION REQUISE**
                
                Vous êtes sur le point de supprimer **TOUTES** les données de simulation.
                Cette action est **IRRÉVERSIBLE**.
                """)
                
                confirmation_text_1 = st.text_input(
                    "Tapez 'SUPPRIMER' pour confirmer la première étape :",
                    key="confirmation_1",
                    placeholder="Tapez SUPPRIMER ici"
                )
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("✅ CONFIRMER ÉTAPE 1", use_container_width=True, type="primary"):
                        if confirmation_text_1 == "SUPPRIMER":
                            st.session_state.reset_validation_step = 2
                            st.rerun()
                        else:
                            st.error("❌ Le texte saisi ne correspond pas. Veuillez taper exactement 'SUPPRIMER'.")
                with col_btn2:
                    if st.button("❌ ANNULER", use_container_width=True):
                        st.session_state.reset_validation_step = 0
                        st.rerun()
            
            # Étape 3 : Troisième confirmation
            elif st.session_state.reset_validation_step == 2:
                st.error("""
                ⚠️ **DEUXIÈME VALIDATION REQUISE**
                
                Vous êtes toujours sur le point de supprimer **TOUTES** les données.
                Êtes-vous vraiment sûr de vouloir continuer ?
                """)
                
                confirmation_text_2 = st.text_input(
                    "Tapez 'JE CONFIRME' pour confirmer la deuxième étape :",
                    key="confirmation_2",
                    placeholder="Tapez JE CONFIRME ici"
                )
                
                col_btn3, col_btn4 = st.columns(2)
                with col_btn3:
                    if st.button("✅ CONFIRMER ÉTAPE 2", use_container_width=True, type="primary"):
                        if confirmation_text_2 == "JE CONFIRME":
                            st.session_state.reset_validation_step = 3
                            st.rerun()
                        else:
                            st.error("❌ Le texte saisi ne correspond pas. Veuillez taper exactement 'JE CONFIRME'.")
                with col_btn4:
                    if st.button("❌ ANNULER", use_container_width=True):
                        st.session_state.reset_validation_step = 0
                        st.rerun()
            
            # Étape 4 : Dernière confirmation avant exécution
            elif st.session_state.reset_validation_step == 3:
                st.error("""
                ⚠️⚠️⚠️ **DERNIÈRE VALIDATION - ACTION IRRÉVERSIBLE** ⚠️⚠️⚠️
                
                **DERNIÈRE CHANCE** : Vous êtes sur le point de supprimer définitivement :
                - Tous les logs de carburant
                - Tous les logs de maintenance
                - Toutes les pannes
                - Toutes les entrées manuelles
                - Tous les compteurs des machines
                
                **Cette action ne peut PAS être annulée !**
                """)
                
                confirmation_text_3 = st.text_input(
                    "Tapez 'RÉINITIALISER MAINTENANT' pour exécuter la suppression :",
                    key="confirmation_3",
                    placeholder="Tapez RÉINITIALISER MAINTENANT ici"
                )
                
                col_btn5, col_btn6 = st.columns(2)
                with col_btn5:
                    if st.button("🗑️ EXÉCUTER LA RÉINITIALISATION", use_container_width=True, type="primary"):
                        if confirmation_text_3 == "RÉINITIALISER MAINTENANT":
                            success, message = clear_all_simulation_data()
                            if success:
                                st.success(f"✅ {message}")
                                st.info("🔄 L'application va se recharger pour appliquer les changements.")
                                # Réinitialiser l'état de validation
                                st.session_state.reset_validation_step = 0
                                # Recharger les machines depuis la base de données
                                manager.machines = manager.load_machines_from_db()
                                st.rerun()
                            else:
                                st.error(f"❌ {message}")
                                st.session_state.reset_validation_step = 0
                        else:
                            st.error("❌ Le texte saisi ne correspond pas. Veuillez taper exactement 'RÉINITIALISER MAINTENANT'.")
                with col_btn6:
                    if st.button("❌ ANNULER", use_container_width=True):
                        st.session_state.reset_validation_step = 0
                        st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 8: SAUVEGARDE/RESTAURATION ---
        with admin_tabs[8]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("💾 Sauvegarde et Restauration des Données")
            st.caption("Sauvegardez vos données pour éviter toute perte d'information")
            
            # Informations sur la base de données
            db = get_database()
            col_info1, col_info2, col_info3 = st.columns(3)
            with col_info1:
                st.metric("📊 Images sauvegardées", len(db.get("images_metadata", {})))
            with col_info2:
                last_backup = db.get("backup_info", {}).get("last_backup", "Jamais")
                if last_backup and last_backup != "Jamais":
                    last_backup = last_backup.replace("_", " ").replace("backup ", "")
                st.metric("🕒 Dernière sauvegarde", last_backup if last_backup else "Jamais")
            with col_info3:
                backup_count = db.get("backup_info", {}).get("backup_count", 0)
                st.metric("📦 Nombre de sauvegardes", backup_count)
            
            st.markdown("---")
            
            # Section Créer une sauvegarde
            st.markdown("#### 💾 Créer une Sauvegarde")
            st.markdown("""
            <div style="background: linear-gradient(135deg, rgba(245, 184, 0, 0.1) 0%, rgba(255, 165, 0, 0.1) 100%); 
                        padding: 15px; border-radius: 10px; margin-bottom: 20px; border: 2px solid #F5B800;">
                <p style="color: #F5B800; margin: 0;">ℹ️ <strong>Une sauvegarde inclut :</strong></p>
                <ul style="color: #e0e0e0; margin: 10px 0 0 0; padding-left: 20px;">
                    <li>La base de données (métadonnées des images)</li>
                    <li>Toutes les images uploadées</li>
                    <li>Les paramètres de l'application</li>
                </ul>
            </div>
            """, unsafe_allow_html=True)
            
            if st.button("💾 CRÉER UNE SAUVEGARDE MAINTENANT", use_container_width=True, type="primary"):
                with st.spinner("Création de la sauvegarde en cours..."):
                    success, result = create_backup()
                    if success:
                        st.success(f"✅ Sauvegarde créée avec succès !\n📁 Emplacement: {result}")
                        st.rerun()
                    else:
                        st.error(f"❌ Erreur lors de la création de la sauvegarde: {result}")
            
            st.markdown("---")
            
            # Section Restaurer une sauvegarde
            st.markdown("#### 🔄 Restaurer une Sauvegarde")
            backups = list_backups()
            
            if backups:
                backup_options = {f"{b['name']} ({b['date']})": b for b in backups}
                selected_backup_display = st.selectbox(
                    "Sélectionner une sauvegarde à restaurer",
                    list(backup_options.keys()),
                    help="Choisissez la sauvegarde que vous souhaitez restaurer"
                )
                
                if selected_backup_display:
                    selected_backup = backup_options[selected_backup_display]
                    st.warning("⚠️ Attention : La restauration remplacera toutes les données actuelles !")
                    
                    if st.button("🔄 RESTAURER CETTE SAUVEGARDE", use_container_width=True, type="primary"):
                        with st.spinner("Restauration en cours..."):
                            success, result = restore_backup(selected_backup['path'])
                            if success:
                                st.success(f"✅ Sauvegarde restaurée avec succès !")
                                st.rerun()
                            else:
                                st.error(f"❌ Erreur lors de la restauration: {result}")
            else:
                st.info("📭 Aucune sauvegarde disponible.")
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # --- TAB 9: LOGS D'AUDIT ---
        with admin_tabs[9]:
            st.markdown('<div class="content-card">', unsafe_allow_html=True)
            st.subheader("📊 Logs d'Audit - Traçabilité des Modifications")
            st.caption("ℹ️ Consultez l'historique de toutes les modifications effectuées dans le système")
            
            # Filtres
            col_filter1, col_filter2, col_filter3, col_filter4 = st.columns(4)
            with col_filter1:
                filter_entity = st.selectbox(
                    "Type d'entité",
                    ["Tous", "EMPLOYEE", "USER", "MACHINE", "STOCK"],
                    key="audit_filter_entity"
                )
            with col_filter2:
                filter_user = st.selectbox(
                    "Utilisateur",
                    ["Tous"] + [u['user'] for u in user_mgr.users_in_current_tenant()],
                    key="audit_filter_user"
                )
            with col_filter3:
                filter_action = st.selectbox(
                    "Action",
                    ["Toutes", "CREATE", "UPDATE", "DELETE", "DEACTIVATE", "REACTIVATE"],
                    key="audit_filter_action"
                )
            with col_filter4:
                filter_days = st.selectbox(
                    "Période",
                    ["Tous", "7 derniers jours", "30 derniers jours", "90 derniers jours"],
                    key="audit_filter_days"
                )
            
            # Calculer les dates selon le filtre
            start_date = None
            end_date = None
            if filter_days == "7 derniers jours":
                start_date = datetime.now() - timedelta(days=7)
            elif filter_days == "30 derniers jours":
                start_date = datetime.now() - timedelta(days=30)
            elif filter_days == "90 derniers jours":
                start_date = datetime.now() - timedelta(days=90)
            
            # Appliquer les filtres
            entity_type_filter = None if filter_entity == "Tous" else filter_entity
            user_filter = None if filter_user == "Tous" else filter_user
            action_filter = None if filter_action == "Toutes" else filter_action
            
            # Récupérer les logs filtrés
            df_logs = audit_mgr.get_logs_df(
                entity_type=entity_type_filter,
                user=user_filter,
                action_type=action_filter,
                start_date=start_date,
                end_date=end_date
            )
            
            if not df_logs.empty:
                st.markdown("---")
                
                # Statistiques
                col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
                with col_stat1:
                    st.metric("Total Logs", len(df_logs))
                with col_stat2:
                    creates = len(df_logs[df_logs["Action"] == "CREATE"])
                    st.metric("Créations", creates)
                with col_stat3:
                    updates = len(df_logs[df_logs["Action"] == "UPDATE"])
                    st.metric("Modifications", updates)
                with col_stat4:
                    deletes = len(df_logs[df_logs["Action"] == "DELETE"])
                    st.metric("Suppressions", deletes)
                
                st.markdown("---")
                
                # Tableau des logs
                st.dataframe(df_logs, width='stretch', hide_index=True, height=600)
                
                # Export
                st.markdown("---")
                col_export1, col_export2 = st.columns(2)
                with col_export1:
                    csv_data = df_logs.to_csv(index=False, encoding='utf-8-sig')
                    st.download_button(
                        label="📥 Télécharger en CSV",
                        data=csv_data,
                        file_name=f"logs_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                with col_export2:
                    try:
                        from io import BytesIO
                        output = BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_logs.to_excel(writer, sheet_name='Logs Audit', index=False)
                        excel_data = output.getvalue()
                        st.download_button(
                            label="📥 Télécharger en Excel",
                            data=excel_data,
                            file_name=f"logs_audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    except:
                        st.info("💡 Installez 'openpyxl' pour l'export Excel: pip install openpyxl")
            else:
                st.info("📭 Aucun log d'audit trouvé avec les filtres sélectionnés.")
            
            st.markdown('</div>', unsafe_allow_html=True)

# --- EQUIPE ---
if "EQUIPE" in tab_dict:
    with tab_dict["EQUIPE"]:
        st.markdown('<div class="content-card">', unsafe_allow_html=True)
        st.dataframe(staff_mgr.get_all_staff_df(), width='stretch')
        st.markdown('</div>', unsafe_allow_html=True)

# =========================================================================
# WIDGETS FLOTTANTS : CHAT ENTREPRISE (bas-gauche) + BOT GUIDE (bas-droit)
# =========================================================================
_fc_me = st.session_state.get("username", "")
_fc_role = st.session_state.get("role", "")
_fc_all_msgs = _load_collab_messages().get("messages", [])
_fc_team_msgs = [m for m in _fc_all_msgs
                 if m.get("to") == "__team__" or m.get("kind") == "communique"]
_fc_team_last = _fc_team_msgs[-40:]
_fc_msgs_json = json.dumps(_fc_team_last, ensure_ascii=False, default=str)
_fc_current_url = ""  # resolved in JS

components.html(f"""
<script>
(function() {{
  /* ── évite la duplication lors des reruns Streamlit ── */
  var doc = (function() {{ try {{ return window.parent.document; }} catch(e) {{ return document; }} }})();
  if (doc.getElementById('ge-float-root')) return;

  var me = {json.dumps(_fc_me)};
  var msgs = {_fc_msgs_json};

  /* ═══════════════════════════════════════════════════════
     STYLES GLOBAUX
  ═══════════════════════════════════════════════════════ */
  var style = doc.createElement('style');
  style.id = 'ge-float-style';
  style.textContent = `
    .ge-fab {{
      position:fixed; bottom:24px; width:56px; height:56px; border-radius:50%;
      border:none; cursor:pointer; font-size:26px; display:flex; align-items:center;
      justify-content:center; box-shadow:0 4px 18px rgba(0,0,0,.55);
      transition:transform .18s,box-shadow .18s; z-index:9997;
    }}
    .ge-fab:hover {{ transform:scale(1.12); box-shadow:0 6px 24px rgba(0,0,0,.7); }}
    .ge-fab-left  {{ left:20px;  background:linear-gradient(135deg,#1565C0,#0D47A1); color:#fff; }}
    .ge-fab-right {{ right:20px; background:linear-gradient(135deg,#F5B800,#E6AC00); color:#0F2A44; }}
    .ge-panel {{
      position:fixed; bottom:90px; width:340px; max-height:480px;
      background:#1a1a2e; border:1.5px solid #333; border-radius:16px;
      box-shadow:0 8px 40px rgba(0,0,0,.7); display:flex; flex-direction:column;
      z-index:9998; overflow:hidden; transition:opacity .2s,transform .2s;
    }}
    .ge-panel.ge-hidden {{ opacity:0; pointer-events:none; transform:translateY(16px); }}
    .ge-panel-left  {{ left:20px; }}
    .ge-panel-right {{ right:20px; }}
    .ge-panel-head {{
      background:#0F2A44; padding:12px 16px; display:flex; align-items:center;
      justify-content:space-between; border-bottom:1px solid #333;
    }}
    .ge-panel-head h4 {{ margin:0; color:#F5B800; font-size:15px; font-weight:700; font-family:Inter,sans-serif; }}
    .ge-panel-head span {{ color:#888; font-size:11px; font-family:Inter,sans-serif; }}
    .ge-panel-close {{
      background:none; border:none; color:#888; font-size:18px; cursor:pointer; padding:0 4px; line-height:1;
    }}
    .ge-panel-close:hover {{ color:#F5B800; }}
    .ge-msgs {{
      flex:1; overflow-y:auto; padding:12px; display:flex; flex-direction:column; gap:8px;
      scrollbar-width:thin; scrollbar-color:#333 transparent;
    }}
    .ge-bubble {{
      max-width:86%; padding:8px 12px; border-radius:14px; font-size:13px; line-height:1.45;
      font-family:Inter,sans-serif; word-break:break-word;
    }}
    .ge-bubble-me  {{ align-self:flex-end; background:#1565C0; color:#fff; border-bottom-right-radius:4px; }}
    .ge-bubble-other {{ align-self:flex-start; background:#2a2a3e; color:#ddd; border-bottom-left-radius:4px; }}
    .ge-bubble-name {{ font-size:10px; color:#F5B800; margin-bottom:3px; font-weight:600; }}
    .ge-bubble-ts   {{ font-size:10px; color:#666; margin-top:3px; text-align:right; }}
    .ge-input-row {{
      display:flex; gap:8px; padding:10px 12px; border-top:1px solid #333; background:#111;
    }}
    .ge-input-row input {{
      flex:1; background:#1e1e2e; border:1px solid #444; border-radius:20px;
      padding:8px 14px; color:#eee; font-size:13px; outline:none; font-family:Inter,sans-serif;
    }}
    .ge-input-row input:focus {{ border-color:#F5B800; }}
    .ge-input-row button {{
      background:#F5B800; border:none; border-radius:20px; padding:8px 14px;
      color:#0F2A44; font-weight:700; cursor:pointer; font-size:13px; white-space:nowrap;
    }}
    .ge-input-row button:hover {{ background:#ffd033; }}
    .ge-bot-msgs {{
      flex:1; overflow-y:auto; padding:12px; display:flex; flex-direction:column; gap:8px;
      scrollbar-width:thin; scrollbar-color:#333 transparent;
    }}
    .ge-bot-user {{ align-self:flex-end; background:#1565C0; color:#fff; padding:8px 12px;
      border-radius:14px 14px 4px 14px; font-size:13px; max-width:86%; font-family:Inter,sans-serif; }}
    .ge-bot-resp {{ align-self:flex-start; background:#2a2a3e; color:#ddd; padding:8px 12px;
      border-radius:14px 14px 14px 4px; font-size:13px; max-width:90%; font-family:Inter,sans-serif; line-height:1.5; }}
    .ge-bot-chips {{ display:flex; flex-wrap:wrap; gap:6px; padding:8px 12px 0; }}
    .ge-bot-chip {{
      background:#0F2A44; border:1px solid #F5B800; color:#F5B800; border-radius:20px;
      padding:4px 10px; font-size:12px; cursor:pointer; font-family:Inter,sans-serif;
    }}
    .ge-bot-chip:hover {{ background:#F5B800; color:#0F2A44; }}
    .ge-unread {{
      position:absolute; top:-4px; right:-4px; background:#e53935; color:#fff;
      border-radius:50%; width:18px; height:18px; font-size:11px; font-weight:700;
      display:flex; align-items:center; justify-content:center; font-family:Inter,sans-serif;
    }}
    @media(max-width:480px){{
      .ge-panel {{ width:calc(100vw - 32px); left:16px!important; right:16px!important; }}
      .ge-panel-right {{ bottom:160px; }}
    }}
  `;
  doc.head.appendChild(style);

  /* ═══════════════════════════════════════════════════════
     BOT GUIDE — base de connaissance
  ═══════════════════════════════════════════════════════ */
  var BOT_FAQ = [
    {{ kw:["connexion","login","mot de passe","identifiant","compte","oublié"],
       a:"🔐 <b>Connexion</b> : Entrez votre identifiant et mot de passe. En cas d'oubli, un administrateur peut réinitialiser le mot de passe dans l'onglet <b>ADMIN → Gestion utilisateurs</b>." }},
    {{ kw:["dashboard","tableau de bord","kpi","accueil","résumé","aperçu"],
       a:"📊 <b>Dashboard</b> : Vue d'ensemble de la flotte. KPIs en temps réel : machines actives, production du jour, carburant, pannes. Chaque indicateur est cliquable." }},
    {{ kw:["cycle","voyage","rotation","shift","poste","chargement","production","tonne"],
       a:"🔄 <b>Cycles</b> : Enregistrez la production par shift (Jour 5h30→18h / Nuit 18h30→5h). Sélectionnez machine + shift → entrez les tonnes et heures travaillées. Le dashboard se met à jour automatiquement." }},
    {{ kw:["carburant","fuel","ravitaillement","litre","plein","vol","consommation","pompe"],
       a:"⛽ <b>Carburant</b> : Enregistrez chaque ravitaillement (machine, date, litres, prix/L). Le système calcule la conso/cycle et détecte les anomalies : chute > 5 % en 10 min → alerte vol automatique." }},
    {{ kw:["maintenance","pm","250h","500h","réparation","panne","mécanique","inspection"],
       a:"🔧 <b>Maintenance</b> : Planifiez les PM (250h, 500h…) et enregistrez les réparations. Renseignez les pièces changées pour alimenter le stock et le suivi de durée de vie. Les alertes s'affichent sur le dashboard." }},
    {{ kw:["stock","pièce","inventaire","rechange","seuil","alerte","entré","sortie"],
       a:"📦 <b>Stock</b> : Gérez l'inventaire des consommables. Définissez des seuils minimum (alerte automatique). Lors d'une sortie vers une machine, pointez la machine pour activer le suivi de durée de vie." }},
    {{ kw:["durée de vie","usure","vie pièce","production pièce","consommable"],
       a:"📈 <b>Durée de vie des pièces</b> : Onglet <b>Gestion Stock → Durée de Vie Pièces</b>. À chaque pose, la production de la machine est capturée. Quand la pièce est remplacée, le système calcule les tonnes produites pendant sa vie." }},
    {{ kw:["finance","facture","dépense","coût","revenu","rentabilité","comptabilité"],
       a:"💰 <b>Finance</b> : Créez des factures client, enregistrez les dépenses, consultez la rentabilité par machine et par période. Exportable en PDF. Disponible à partir du plan Standard." }},
    {{ kw:["rh","employé","personnel","équipe","présence","absence","retard","recrutement"],
       a:"👥 <b>RH</b> : Fiches du personnel (mécaniciens, opérateurs…), suivi des présences et absences, calcul de l'ancienneté. Disponible plan Standard+." }},
    {{ kw:["sst","sécurité","accident","risque","epi","incident","take 5","presqu"],
       a:"🦺 <b>SST</b> : Déclarez incidents/presqu'accidents, gérez les contrôles terrain (Take 5, inspection véhicule, test de frein). Générez des rapports PDF de sécurité par période." }},
    {{ kw:["carte","gps","localisation","position","map","zone","géographi"],
       a:"🗺️ <b>Carte GPS</b> : Position des machines sur carte interactive. Statut en couleur (vert = actif, rouge = panne, orange = maintenance). Mise à jour à chaque mouvement." }},
    {{ kw:["utilisateur","user","admin","permission","rôle","accès","créer compte"],
       a:"⚙️ <b>Admin</b> : Créez des utilisateurs, assignez les rôles (Administrateur, Ingénieur, Superviseur, Opérateur…) et personnalisez les accès onglet par onglet. Réservé aux administrateurs." }},
    {{ kw:["machine","engin","ajouter","créer","flotte","tombereau","pelle","chargeuse","camion"],
       a:"🏗️ <b>Machines</b> : Ajoutez une machine depuis les onglets Cycles ou Maintenance. ID unique, modèle, type, capacité. Catalogue de plus de 850 références OEM (Caterpillar, Komatsu, Liebherr…)." }},
    {{ kw:["rapport","export","pdf","excel","csv","télécharger","imprim"],
       a:"📄 <b>Exports</b> : Chaque onglet propose un export CSV ou Excel. Rapports PDF disponibles pour Maintenance, SST et Finance. Bouton ⬇️ présent dans chaque section." }},
    {{ kw:["opérateur","validation","tablette","chargement","terrain"],
       a:"📱 <b>Interface Opérateur</b> : Onglet <b>Validation Opérateur</b> optimisé pour tablette. L'opérateur valide les chargements avec des boutons larges, sans accès aux données sensibles." }},
    {{ kw:["plan","abonnement","free","standard","premium","limite","machine"],
       a:"💎 <b>Plans</b> : <b>Free</b> (5 machines, fonctions de base) · <b>Standard</b> (50 machines + Finance, RH, Stock, Or) · <b>Premium</b> (illimité + tout). S'active dans la console Gestionnaire." }},
    {{ kw:["sauvegarde","backup","restaurer","donnée","sauvegarder"],
       a:"💾 <b>Sauvegarde</b> : Plan Premium. ADMIN → Sauvegarde. Téléchargez un fichier zip de toutes vos données. La restauration écrase les données actuelles (à utiliser avec précaution)." }},
    {{ kw:["messagerie","message","communiqué","équipe","chat"],
       a:"💬 <b>Messagerie</b> : Envoyez des messages à l'équipe ou en privé. Les administrateurs publient des communiqués visibles par tous. Accessible aussi via ce chat flottant à gauche." }},
    {{ kw:["or","gold","prix","marché","cours","once","troy"],
       a:"🥇 <b>Marché de l'or</b> : Cours de l'or en temps réel (USD/once). Graphiques 30j, 52 semaines, 12 mois, 10 ans. Disponible plan Standard+." }},
    {{ kw:["bonjour","salut","hello","bonsoir","aide","help","quoi","comment","tutoriel","démarrer"],
       a:"👋 Bonjour ! Je suis le guide de <b>GOOD ENGINEERS OS</b>. Tapez un mot-clé ou cliquez sur une suggestion :<br><br>📊 Dashboard · 🔄 Cycles · ⛽ Carburant · 🔧 Maintenance · 📦 Stock · 💰 Finance · 👥 RH · 🦺 SST · 🗺️ Carte · 📱 Opérateur" }},
  ];

  var BOT_CHIPS = ["Dashboard","Cycles","Carburant","Maintenance","Stock","Durée de vie","Finance","RH","SST","Carte","Opérateur","Export","Plan"];

  function botAnswer(q) {{
    var ql = (q||"").toLowerCase().normalize("NFD").replace(/[\\u0300-\\u036f]/g,"");
    for (var i=0;i<BOT_FAQ.length;i++) {{
      for (var j=0;j<BOT_FAQ[i].kw.length;j++) {{
        var k = BOT_FAQ[i].kw[j].normalize("NFD").replace(/[\\u0300-\\u036f]/g,"");
        if (ql.includes(k)) return BOT_FAQ[i].a;
      }}
    }}
    return "❓ Je n'ai pas trouvé de réponse précise. Essayez un de ces mots-clés : <b>Dashboard, Cycles, Carburant, Maintenance, Stock, Finance, RH, SST, Carte, Opérateur, Sauvegarde, Plan</b>.";
  }}

  /* ═══════════════════════════════════════════════════════
     ROOT — conteneur injecté dans le parent
  ═══════════════════════════════════════════════════════ */
  var root = doc.createElement('div');
  root.id = 'ge-float-root';
  doc.body.appendChild(root);

  /* ═══════════════════════════════════════════════════════
     CHAT ENTREPRISE (gauche)
  ═══════════════════════════════════════════════════════ */
  var unreadCount = 0;

  function buildChatPanel() {{
    /* FAB */
    var fab = doc.createElement('button');
    fab.className = 'ge-fab ge-fab-left';
    fab.title = 'Chat Équipe';
    fab.innerHTML = '💬';
    fab.style.position = 'fixed';
    root.appendChild(fab);

    var badge = doc.createElement('div');
    badge.className = 'ge-unread';
    badge.style.display = 'none';
    badge.textContent = '0';
    fab.style.position = 'fixed';
    fab.appendChild(badge);

    /* Panel */
    var panel = doc.createElement('div');
    panel.className = 'ge-panel ge-panel-left ge-hidden';
    panel.innerHTML = `
      <div class="ge-panel-head">
        <div>
          <h4>💬 Chat Équipe</h4>
          <span>Messages visibles par toute l'équipe</span>
        </div>
        <button class="ge-panel-close" title="Fermer">✕</button>
      </div>
      <div class="ge-msgs" id="ge-chat-msgs"></div>
      <div class="ge-input-row">
        <input id="ge-chat-input" type="text" placeholder="Votre message…" maxlength="500" />
        <button id="ge-chat-send">Envoyer</button>
      </div>`;
    root.appendChild(panel);

    /* Remplir les messages */
    function renderMsgs() {{
      var container = doc.getElementById('ge-chat-msgs');
      if (!container) return;
      container.innerHTML = '';
      if (!msgs || msgs.length === 0) {{
        container.innerHTML = '<div style="color:#666;font-size:13px;text-align:center;padding:20px;">Aucun message pour l\'instant.<br>Soyez le premier à écrire !</div>';
        return;
      }}
      msgs.forEach(function(m) {{
        var isMe = (m.from === me);
        var ts = (m.ts||'').substring(0,16).replace('T',' ');
        var div = doc.createElement('div');
        div.className = 'ge-bubble ' + (isMe ? 'ge-bubble-me' : 'ge-bubble-other');
        div.innerHTML = (!isMe ? '<div class="ge-bubble-name">' + (m.from||'?') + '</div>' : '')
          + '<div>' + (m.body||'').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\\n/g,'<br>') + '</div>'
          + '<div class="ge-bubble-ts">' + ts + '</div>';
        container.appendChild(div);
      }});
      container.scrollTop = container.scrollHeight;
    }}

    renderMsgs();

    /* Toggle */
    var isOpen = sessionStorage.getItem('ge_chat_open') === '1';
    if (isOpen) panel.classList.remove('ge-hidden');

    fab.addEventListener('click', function() {{
      isOpen = !isOpen;
      sessionStorage.setItem('ge_chat_open', isOpen ? '1' : '0');
      panel.classList.toggle('ge-hidden', !isOpen);
      if (isOpen) {{ renderMsgs(); badge.style.display='none'; unreadCount=0; }}
    }});

    panel.querySelector('.ge-panel-close').addEventListener('click', function() {{
      isOpen = false;
      sessionStorage.setItem('ge_chat_open','0');
      panel.classList.add('ge-hidden');
    }});

    /* Envoi */
    function sendMsg() {{
      var inp = doc.getElementById('ge-chat-input');
      var txt = (inp ? inp.value : '').trim();
      if (!txt) return;
      /* Optimistic : ajouter localement */
      msgs.push({{ from: me, to:'__team__', kind:'message', body: txt, ts: new Date().toISOString(), id: Date.now().toString() }});
      renderMsgs();
      if (inp) inp.value = '';
      /* Envoyer via query param → Streamlit rerun */
      var url = new URL(window.parent.location.href);
      url.searchParams.set('ge_fc', encodeURIComponent(txt));
      window.parent.history.pushState({{}},'', url.toString());
      /* Déclencher un rerun Streamlit (reload silencieux) */
      setTimeout(function() {{ window.parent.location.href = url.toString(); }}, 200);
    }}

    var sendBtn = doc.getElementById('ge-chat-send');
    if (sendBtn) sendBtn.addEventListener('click', sendMsg);
    var chatInp = doc.getElementById('ge-chat-input');
    if (chatInp) chatInp.addEventListener('keydown', function(e) {{ if(e.key==='Enter') sendMsg(); }});
  }}

  /* ═══════════════════════════════════════════════════════
     BOT GUIDE (droite)
  ═══════════════════════════════════════════════════════ */
  function buildBotPanel() {{
    var fab = doc.createElement('button');
    fab.className = 'ge-fab ge-fab-right';
    fab.title = 'Guide d\'utilisation';
    fab.innerHTML = '🤖';
    root.appendChild(fab);

    var panel = doc.createElement('div');
    panel.className = 'ge-panel ge-panel-right ge-hidden';
    panel.innerHTML = `
      <div class="ge-panel-head">
        <div>
          <h4>🤖 Guide GOOD ENGINEERS</h4>
          <span>Assistant d'utilisation de la plateforme</span>
        </div>
        <button class="ge-panel-close" title="Fermer">✕</button>
      </div>
      <div class="ge-bot-msgs" id="ge-bot-msgs">
        <div class="ge-bot-resp">👋 Bonjour ! Je suis votre guide.<br>Tapez un mot-clé ou choisissez une suggestion.</div>
      </div>
      <div class="ge-bot-chips" id="ge-bot-chips"></div>
      <div class="ge-input-row" style="border-top:1px solid #333;">
        <input id="ge-bot-input" type="text" placeholder="Ex: maintenance, stock, carburant…" maxlength="200" />
        <button id="ge-bot-send">▶</button>
      </div>`;
    root.appendChild(panel);

    /* Chips suggérées */
    var chipsEl = doc.getElementById('ge-bot-chips');
    BOT_CHIPS.forEach(function(c) {{
      var ch = doc.createElement('span');
      ch.className = 'ge-bot-chip';
      ch.textContent = c;
      ch.addEventListener('click', function() {{ askBot(c); }});
      if (chipsEl) chipsEl.appendChild(ch);
    }});

    function askBot(q) {{
      var cont = doc.getElementById('ge-bot-msgs');
      if (!cont) return;
      /* bulle utilisateur */
      var uDiv = doc.createElement('div');
      uDiv.className = 'ge-bot-user';
      uDiv.textContent = q;
      cont.appendChild(uDiv);
      /* bulle réponse */
      var rDiv = doc.createElement('div');
      rDiv.className = 'ge-bot-resp';
      rDiv.innerHTML = botAnswer(q);
      cont.appendChild(rDiv);
      cont.scrollTop = cont.scrollHeight;
      var inp = doc.getElementById('ge-bot-input');
      if (inp) inp.value = '';
    }}

    var isOpenB = sessionStorage.getItem('ge_bot_open') === '1';
    if (isOpenB) panel.classList.remove('ge-hidden');

    fab.addEventListener('click', function() {{
      isOpenB = !isOpenB;
      sessionStorage.setItem('ge_bot_open', isOpenB ? '1' : '0');
      panel.classList.toggle('ge-hidden', !isOpenB);
    }});
    panel.querySelector('.ge-panel-close').addEventListener('click', function() {{
      isOpenB = false;
      sessionStorage.setItem('ge_bot_open','0');
      panel.classList.add('ge-hidden');
    }});

    var botSend = doc.getElementById('ge-bot-send');
    if (botSend) botSend.addEventListener('click', function() {{
      var inp = doc.getElementById('ge-bot-input');
      var q = inp ? inp.value.trim() : '';
      if (q) askBot(q);
    }});
    var botInp = doc.getElementById('ge-bot-input');
    if (botInp) botInp.addEventListener('keydown', function(e) {{
      if (e.key === 'Enter') {{
        var q = botInp.value.trim();
        if (q) askBot(q);
      }}
    }});
  }}

  buildChatPanel();
  buildBotPanel();
}})();
</script>
""", height=0, scrolling=False)