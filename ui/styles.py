"""Global styles and reusable UI components for Smart Shopping Iberia.

Paleta WCAG AA:
  #1B5E20  verde muy oscuro  → sidebar, hero backgrounds
  #2E7D32  verde oscuro      → botones primarios, acentos
  #43A047  verde medio       → barras de progreso
  #1A1A1A  casi negro        → texto principal sobre blanco
  #555555  gris oscuro       → texto secundario
  #F0F4F0  gris muy suave    → fondo secundario
"""
import streamlit as st

# ── Design tokens ─────────────────────────────────────────────────────────────
VERDE_OSCURO = "#1B5E20"
VERDE_MEDIO  = "#2E7D32"
VERDE_LIMA   = "#43A047"
BLANCO       = "#FFFFFF"
GRIS_SUAVE   = "#F0F4F0"
DORADO       = "#E65100"
ROJO         = "#C62828"
TEXTO        = "#1A1A1A"
TEXTO_SEC    = "#555555"

_FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800'
    '&display=swap" rel="stylesheet">'
)

_CSS = """
/* ── Base & font ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    font-size: 16px !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu                        { visibility: hidden !important; }
footer                           { visibility: hidden !important; }
[data-testid="stToolbar"]        { display: none !important; }
[data-testid="stDecoration"]     { display: none !important; }

/* ── Custom scrollbar ── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #F0F4F0; }
::-webkit-scrollbar-thumb { background: #2E7D32; border-radius: 3px; }

/* ══════════════════════════════════════
   SIDEBAR — desktop
   ══════════════════════════════════════ */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 100%) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stMarkdown a,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption p,
section[data-testid="stSidebar"] small {
    color: rgba(255,255,255,0.90) !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.18) !important;
    margin: 12px 0 !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
    padding: 10px 14px !important;
    border-radius: 9px !important;
    transition: background 0.15s !important;
    margin-bottom: 3px !important;
    font-weight: 600 !important;
    color: #FFFFFF !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover {
    background: rgba(255,255,255,0.15) !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[data-checked="true"],
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label[aria-checked="true"] {
    background: rgba(255,255,255,0.22) !important;
    color: #FFFFFF !important;
    font-weight: 700 !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.12) !important;
    border: 1px solid rgba(255,255,255,0.25) !important;
    color: white !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.22) !important;
}

/* ══════════════════════════════════════
   MÉTRICAS
   ══════════════════════════════════════ */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 20px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,.07);
    border: 1px solid #E0E0E0;
}
[data-testid="stMetricValue"] {
    color: #1B5E20 !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    font-weight: 500 !important;
    color: #555555 !important;
}

/* ══════════════════════════════════════
   BOTONES
   ══════════════════════════════════════ */
.stButton > button {
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.18s ease !important;
    min-height: 44px !important;
    font-size: 15px !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2E7D32 0%, #1B5E20 100%) !important;
    border-color: #2E7D32 !important;
    color: #FFFFFF !important;
    box-shadow: 0 3px 10px rgba(46,125,50,0.30) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1B5E20 0%, #144A1B 100%) !important;
    box-shadow: 0 5px 18px rgba(46,125,50,0.40) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #2E7D32 !important;
    color: #1B5E20 !important;
}

/* ══════════════════════════════════════
   INPUTS
   ══════════════════════════════════════ */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 9px !important;
    font-family: 'Inter', sans-serif !important;
    border-color: #E0E0E0 !important;
    font-size: 16px !important;
    min-height: 44px !important;
    color: #1A1A1A !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #2E7D32 !important;
    box-shadow: 0 0 0 3px rgba(46,125,50,0.15) !important;
}

/* ══════════════════════════════════════
   EXPANDERS
   ══════════════════════════════════════ */
details[data-testid="stExpander"] {
    border: 1px solid #E0E0E0 !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 2px 8px rgba(0,0,0,.05) !important;
    margin-bottom: 10px !important;
}
details[data-testid="stExpander"] summary {
    padding: 14px 18px !important;
    font-weight: 600 !important;
    background: #F0F4F0 !important;
    color: #1A1A1A !important;
    font-size: 15px !important;
}
details[data-testid="stExpander"] summary:hover {
    background: #E8F0E8 !important;
}

/* ══════════════════════════════════════
   PROGRESS BAR
   ══════════════════════════════════════ */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #43A047 0%, #2E7D32 100%) !important;
    border-radius: 4px !important;
}

/* ══════════════════════════════════════
   ALERTS
   ══════════════════════════════════════ */
.stAlert {
    border-radius: 10px !important;
    border-left-width: 4px !important;
    color: #1A1A1A !important;
}

/* ══════════════════════════════════════
   TABS
   ══════════════════════════════════════ */
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
    font-size: 15px !important;
    color: #555555 !important;
}
.stTabs [aria-selected="true"] {
    color: #1B5E20 !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #2E7D32 !important;
}

/* ══════════════════════════════════════
   DIVIDERS
   ══════════════════════════════════════ */
hr { border-color: #E0E0E0 !important; margin: 20px 0 !important; }

/* ══════════════════════════════════════
   PRODUCT CARDS (lista móvil)
   ══════════════════════════════════════ */
.ssi-card {
    background: #FFFFFF;
    border-radius: 12px;
    box-shadow: 0 2px 10px rgba(0,0,0,.08);
    border: 1px solid #E0E0E0;
    margin-bottom: 12px;
    overflow: hidden;
}
.ssi-card-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    padding: 14px 16px 10px;
    background: #F0F4F0;
    gap: 8px;
}
.ssi-product-name {
    font-size: 16px;
    font-weight: 700;
    color: #1A1A1A;
    line-height: 1.3;
    flex: 1;
}
.ssi-qty-badge {
    font-size: 14px;
    font-weight: 700;
    color: #555555;
    white-space: nowrap;
    padding: 2px 8px;
    background: #E0E0E0;
    border-radius: 20px;
    flex-shrink: 0;
}
.ssi-prices {
    padding: 4px 0 4px;
}
.ssi-price-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 16px;
    border-bottom: 1px solid #F0F4F0;
    font-size: 15px;
}
.ssi-price-row:last-child { border-bottom: none; }
.ssi-price-row.is-min {
    background: #F1F8F1;
}
.ssi-super-name {
    color: #1A1A1A;
    font-weight: 500;
}
.ssi-super-name.is-min {
    color: #1B5E20;
    font-weight: 700;
}
.ssi-price-val {
    font-weight: 600;
    color: #1A1A1A;
    display: flex;
    align-items: center;
    gap: 6px;
}
.ssi-price-val.is-min { color: #1B5E20; font-weight: 800; }
.ssi-badge-min {
    display: inline-block;
    background: #2E7D32;
    color: #FFFFFF;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 20px;
    letter-spacing: .04em;
}
.ssi-badge-oferta {
    display: inline-block;
    background: #E65100;
    color: #FFFFFF;
    font-size: 10px;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 20px;
}
.ssi-card-actions {
    display: flex;
    gap: 6px;
    padding: 8px 12px 10px;
    background: #FAFAFA;
    border-top: 1px solid #E0E0E0;
    align-items: center;
}
.ssi-no-price {
    padding: 10px 16px;
    color: #888888;
    font-size: 14px;
    font-style: italic;
}

/* ══════════════════════════════════════
   MOBILE OVERRIDES
   ══════════════════════════════════════ */
@media (max-width: 768px) {
    /* Ocultar sidebar en móvil */
    section[data-testid="stSidebar"]          { display: none !important; }
    [data-testid="collapsedControl"]           { display: none !important; }

    /* Espacio inferior para barra nav */
    .main .block-container {
        padding-bottom: 80px !important;
        padding-left: 12px !important;
        padding-right: 12px !important;
    }

    /* Texto mínimo 16px */
    p, span, div, label { font-size: 16px !important; }
    .stCaption p        { font-size: 13px !important; }

    /* Métricas más compactas */
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }

    /* Columnas con scroll horizontal para tablas */
    [data-testid="stHorizontalBlock"] {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
    }
}

/* ══════════════════════════════════════
   BOTTOM NAV BAR (solo móvil)
   ══════════════════════════════════════ */
#ssi-bottom-nav { display: none; }

@media (max-width: 768px) {
    #ssi-bottom-nav {
        display: flex;
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        height: 62px;
        background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 100%);
        z-index: 9999;
        align-items: stretch;
        box-shadow: 0 -2px 16px rgba(0,0,0,.30);
    }
    #ssi-bottom-nav a {
        flex: 1;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: rgba(255,255,255,0.65);
        text-decoration: none;
        font-size: 11px;
        font-weight: 600;
        gap: 3px;
        transition: background 0.15s;
        min-height: 44px;
        -webkit-tap-highlight-color: transparent;
    }
    #ssi-bottom-nav a .nav-icon {
        font-size: 22px;
        line-height: 1;
    }
    #ssi-bottom-nav a.active,
    #ssi-bottom-nav a:active {
        color: #FFFFFF;
        background: rgba(255,255,255,0.15);
    }
}
"""


def inject_css() -> None:
    st.markdown(_FONT_LINK, unsafe_allow_html=True)
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ── Barra de navegación inferior ─────────────────────────────────────────────

_NAV_ITEMS = [
    ("🏠", "Inicio",    "home"),
    ("📋", "Lista",     "lista"),
    ("🎯", "Optimizar", "optimizer"),
    ("🔔", "Alertas",   "alerts"),
    ("👤", "Perfil",    "profile"),
]


def render_mobile_nav(current_page: str) -> None:
    items_html = ""
    for icon, label, key in _NAV_ITEMS:
        active = 'class="active"' if key == current_page else ""
        items_html += (
            f'<a href="?nav={key}" {active}>'
            f'<span class="nav-icon">{icon}</span>'
            f'<span>{label}</span>'
            f'</a>'
        )
    st.markdown(f'<div id="ssi-bottom-nav">{items_html}</div>', unsafe_allow_html=True)


# ── Component helpers ─────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", emoji: str = "") -> None:
    em  = f"{emoji} " if emoji else ""
    sub = (
        f'<p style="margin:6px 0 0;opacity:.88;font-size:.9rem;font-weight:400;color:#FFFFFF">'
        f'{subtitle}</p>'
    ) if subtitle else ""
    st.markdown(
        f"""<div style="background:linear-gradient(135deg,#1B5E20 0%,#2E7D32 100%);
             border-radius:14px;padding:22px 24px;color:#FFFFFF;margin-bottom:20px;
             box-shadow:0 4px 20px rgba(27,94,32,.25)">
             <h1 style="margin:0;font-size:1.55rem;font-weight:800;color:#FFFFFF;
                        letter-spacing:-.02em">{em}{title}</h1>
             {sub}
        </div>""",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    sub = (
        f'<p style="margin:4px 0 0;font-size:.83rem;color:#555555;font-weight:400">'
        f'{subtitle}</p>'
    ) if subtitle else ""
    st.markdown(
        f"""<div style="margin:24px 0 12px;padding-bottom:10px;
             border-bottom:2.5px solid #2E7D32">
             <h2 style="margin:0;font-size:1.08rem;font-weight:700;color:#1A1A1A;
                        letter-spacing:-.01em">{title}</h2>
             {sub}
        </div>""",
        unsafe_allow_html=True,
    )


def metric_cards(cards: list[dict]) -> None:
    cols = st.columns(len(cards))
    for col, c in zip(cols, cards):
        color = c.get("color", "#1B5E20")
        delta_html = (
            f'<div style="font-size:.78rem;color:#2E7D32;font-weight:700;margin-top:6px">'
            f'{c["delta"]}</div>'
            if c.get("delta") else ""
        )
        with col:
            st.markdown(
                f"""<div style="background:#FFFFFF;border-radius:14px;padding:20px 16px;
                     box-shadow:0 2px 10px rgba(0,0,0,.07);border:1px solid #E0E0E0;
                     text-align:center">
                     <div style="font-size:1.8rem;margin-bottom:8px;line-height:1">{c['icon']}</div>
                     <div style="font-size:1.55rem;font-weight:800;color:{color};line-height:1.1;
                                 letter-spacing:-.02em">{c['value']}</div>
                     <div style="font-size:.78rem;color:#555555;font-weight:500;margin-top:6px;
                                 text-transform:uppercase;letter-spacing:.04em">{c['label']}</div>
                     {delta_html}
                </div>""",
                unsafe_allow_html=True,
            )


def empty_state(icon: str, title: str, msg: str = "") -> None:
    msg_html = (
        f'<p style="color:#555555;margin:6px 0 0;font-size:.88rem;font-weight:400">'
        f'{msg}</p>'
    ) if msg else ""
    st.markdown(
        f"""<div style="text-align:center;padding:48px 24px;background:#F0F4F0;
             border-radius:14px;border:2px dashed #E0E0E0;margin:16px 0">
             <div style="font-size:2.8rem;margin-bottom:14px;line-height:1">{icon}</div>
             <h3 style="color:#1A1A1A;font-weight:700;margin:0;font-size:1rem">{title}</h3>
             {msg_html}
        </div>""",
        unsafe_allow_html=True,
    )


def savings_hero(amount: float, label: str = "Ahorro acumulado del año") -> None:
    st.markdown(
        f"""<div style="text-align:center;padding:36px 24px;
             background:linear-gradient(135deg,#1B5E20 0%,#2E7D32 100%);
             border-radius:14px;color:#FFFFFF;margin-bottom:24px;
             box-shadow:0 6px 24px rgba(27,94,32,.28)">
             <div style="font-size:3.6rem;font-weight:800;line-height:1;letter-spacing:-.04em;
                         color:#FFFFFF">
                 {amount:.2f} €</div>
             <div style="font-size:.95rem;opacity:.85;margin-top:10px;font-weight:400;
                         color:#FFFFFF">{label}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def badge_html(text: str, bg: str = "#E8F5E9", color: str = "#1B5E20") -> str:
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;'
        f'background:{bg};color:{color};font-size:.7rem;font-weight:700;'
        f'letter-spacing:.06em;text-transform:uppercase;vertical-align:middle">{text}</span>'
    )


def alert_card_html(
    nombre: str, super_nombre: str, pct: float, precio_hoy: float, precio_hab: float
) -> str:
    return f"""
<div style="background:#FFFFFF;border-radius:12px;padding:16px 20px;
     box-shadow:0 2px 10px rgba(0,0,0,.07);border:1px solid #E0E0E0;
     margin-bottom:12px;display:flex;align-items:center;gap:16px">
  <div style="min-width:60px;text-align:center;background:#FBE9E7;border-radius:10px;padding:8px 4px">
    <div style="font-size:1.3rem;font-weight:800;color:#E65100;line-height:1">-{pct:.0f}%</div>
    <div style="font-size:.62rem;color:#E65100;font-weight:700;text-transform:uppercase">bajada</div>
  </div>
  <div style="flex:1;min-width:0">
    <div style="font-weight:700;font-size:.93rem;color:#1A1A1A;white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis">{nombre}</div>
    <div style="font-size:.78rem;color:#555555;margin-top:2px">📍 {super_nombre}</div>
  </div>
  <div style="text-align:right;white-space:nowrap">
    <div style="font-size:1.15rem;font-weight:800;color:#1B5E20">{precio_hoy:.2f} €</div>
    <div style="font-size:.78rem;color:#888888;text-decoration:line-through">
        antes {precio_hab:.2f} €</div>
  </div>
</div>"""


def super_result_card(nombre: str, productos: int, subtotal: float, color: str, es_fav: bool) -> str:
    fav_badge = badge_html("favorito", "#FFF8E1", "#E65100") if es_fav else ""
    return f"""
<div style="border-radius:12px;padding:18px 22px;background:#FFFFFF;
     box-shadow:0 2px 10px rgba(0,0,0,.08);border-left:5px solid {color};
     display:flex;align-items:center;justify-content:space-between;margin-bottom:4px">
  <div>
    <div style="font-weight:800;font-size:1.05rem;color:#1A1A1A">🏪 {nombre} {fav_badge}</div>
    <div style="font-size:.8rem;color:#555555;margin-top:4px">{productos} producto(s)</div>
  </div>
  <div style="font-size:1.5rem;font-weight:800;color:{color}">{subtotal:.2f} €</div>
</div>"""


def savings_comparison_html(total_sin: float, total_con: float, ahorro: float) -> str:
    return f"""
<div style="background:linear-gradient(135deg,#1B5E20 0%,#2E7D32 100%);border-radius:14px;
     padding:22px 28px;color:#FFFFFF;margin:20px 0;text-align:center;
     box-shadow:0 4px 20px rgba(27,94,32,.25)">
  <div style="font-size:.88rem;opacity:.85;margin-bottom:8px;color:#FFFFFF">
    Sin optimizar gastarías hasta
    <span style="text-decoration:line-through;opacity:.9">{total_sin:.2f} €</span>
  </div>
  <div style="font-size:2rem;font-weight:800;letter-spacing:-.03em;color:#FFFFFF">
    Con Smart Shopping: {total_con:.2f} €
  </div>
  <div style="font-size:1rem;color:#A5D6A7;font-weight:700;margin-top:10px">
    🎉 Ahorro estimado: {ahorro:.2f} €
  </div>
</div>"""
