"""Global styles and reusable UI components for Smart Shopping Iberia."""
import streamlit as st

# ── Design tokens ─────────────────────────────────────────────────────────────
VERDE_OSCURO = "#1B4332"
VERDE_MEDIO  = "#2D6A4F"
VERDE_LIMA   = "#52B788"
BLANCO       = "#FFFFFF"
GRIS_SUAVE   = "#F8F9FA"
DORADO       = "#FFB703"
ROJO         = "#E63946"

_FONT_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800'
    '&display=swap" rel="stylesheet">'
)

_CSS = """
/* ── Base & font ── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu           { visibility: hidden !important; }
footer              { visibility: hidden !important; }
[data-testid="stToolbar"]    { display: none !important; }
[data-testid="stDecoration"] { display: none !important; }

/* ── Custom scrollbar ── */
::-webkit-scrollbar       { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #F8F9FA; }
::-webkit-scrollbar-thumb { background: #52B788; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2D6A4F; }

/* ── Sidebar — dark green ── */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B4332 0%, #2D6A4F 100%) !important;
}
section[data-testid="stSidebar"] .stMarkdown p,
section[data-testid="stSidebar"] .stMarkdown span,
section[data-testid="stSidebar"] .stMarkdown a,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] .stCaption p,
section[data-testid="stSidebar"] small {
    color: rgba(255,255,255,0.88) !important;
}
section[data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.15) !important;
    margin: 12px 0 !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
    padding: 9px 14px !important;
    border-radius: 9px !important;
    transition: background 0.15s !important;
    margin-bottom: 3px !important;
    font-weight: 500 !important;
}
section[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label:hover {
    background: rgba(255,255,255,0.13) !important;
}
section[data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.1) !important;
    border: 1px solid rgba(255,255,255,0.2) !important;
    color: white !important;
    font-weight: 600 !important;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.2) !important;
}

/* ── Native metric widgets ── */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 20px !important;
    box-shadow: 0 2px 12px rgba(0,0,0,.08);
    border: 1px solid #E9ECEF;
}
[data-testid="stMetricValue"] {
    color: #1B4332 !important;
    font-weight: 700 !important;
}
[data-testid="stMetricLabel"] {
    font-weight: 500 !important;
    color: #6C757D !important;
}

/* ── Primary buttons ── */
.stButton > button {
    border-radius: 9px !important;
    font-weight: 600 !important;
    font-family: 'Inter', sans-serif !important;
    transition: all 0.18s ease !important;
    letter-spacing: 0.01em !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #52B788 0%, #40916C 100%) !important;
    border-color: #52B788 !important;
    color: white !important;
    box-shadow: 0 3px 10px rgba(82,183,136,0.35) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #40916C 0%, #2D6A4F 100%) !important;
    border-color: #40916C !important;
    box-shadow: 0 5px 18px rgba(82,183,136,0.45) !important;
    transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"]:hover {
    border-color: #52B788 !important;
    color: #1B4332 !important;
}

/* ── Input fields ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div {
    border-radius: 9px !important;
    font-family: 'Inter', sans-serif !important;
    border-color: #E9ECEF !important;
}
.stTextInput > div > div > input:focus,
.stNumberInput > div > div > input:focus {
    border-color: #52B788 !important;
    box-shadow: 0 0 0 3px rgba(82,183,136,0.18) !important;
}

/* ── Expanders / cards ── */
details[data-testid="stExpander"] {
    border: 1px solid #E9ECEF !important;
    border-radius: 12px !important;
    overflow: hidden !important;
    box-shadow: 0 2px 12px rgba(0,0,0,.07) !important;
    margin-bottom: 10px !important;
}
details[data-testid="stExpander"] summary {
    padding: 14px 18px !important;
    font-weight: 600 !important;
    background: #F8F9FA !important;
    font-family: 'Inter', sans-serif !important;
}
details[data-testid="stExpander"] summary:hover {
    background: #EEF7F3 !important;
}

/* ── Progress bar ── */
.stProgress > div > div > div > div {
    background: linear-gradient(90deg, #52B788 0%, #40916C 100%) !important;
    border-radius: 4px !important;
}

/* ── Alerts / info / success ── */
.stAlert {
    border-radius: 10px !important;
    border-left-width: 4px !important;
}

/* ── Tabs ── */
.stTabs [data-baseweb="tab"] {
    font-family: 'Inter', sans-serif !important;
    font-weight: 500 !important;
}
.stTabs [aria-selected="true"] {
    color: #1B4332 !important;
    font-weight: 700 !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #52B788 !important;
}

/* ── Dividers ── */
hr { border-color: #E9ECEF !important; margin: 20px 0 !important; }

/* ── Checkbox ── */
.stCheckbox label span { font-family: 'Inter', sans-serif !important; }

/* ── Mobile responsive ── */
@media (max-width: 768px) {
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
}
"""


def inject_css() -> None:
    """Inyecta la hoja de estilos global de Smart Shopping Iberia."""
    st.markdown(_FONT_LINK, unsafe_allow_html=True)
    st.markdown(f"<style>{_CSS}</style>", unsafe_allow_html=True)


# ── Component helpers ─────────────────────────────────────────────────────────

def page_header(title: str, subtitle: str = "", emoji: str = "") -> None:
    """Header de página con degradado verde oscuro."""
    em   = f"{emoji} " if emoji else ""
    sub  = f'<p style="margin:6px 0 0;opacity:.85;font-size:.9rem;font-weight:400">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""<div style="background:linear-gradient(135deg,#1B4332 0%,#2D6A4F 100%);
             border-radius:14px;padding:24px 28px;color:white;margin-bottom:24px;
             box-shadow:0 4px 20px rgba(27,67,50,.25)">
             <h1 style="margin:0;font-size:1.65rem;font-weight:800;color:white !important;
                        letter-spacing:-.02em">{em}{title}</h1>
             {sub}
        </div>""",
        unsafe_allow_html=True,
    )


def section_header(title: str, subtitle: str = "") -> None:
    """Encabezado de sección con acento verde."""
    sub = f'<p style="margin:4px 0 0;font-size:.83rem;color:#6C757D;font-weight:400">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""<div style="margin:28px 0 14px;padding-bottom:10px;
             border-bottom:2.5px solid #52B788">
             <h2 style="margin:0;font-size:1.12rem;font-weight:700;color:#1B4332;
                        letter-spacing:-.01em">{title}</h2>
             {sub}
        </div>""",
        unsafe_allow_html=True,
    )


def metric_cards(cards: list[dict]) -> None:
    """
    Renderiza tarjetas de métricas custom en columnas.
    Cada dict debe tener: icon, value, label  [opcionales: delta, color]
    """
    cols = st.columns(len(cards))
    for col, c in zip(cols, cards):
        color = c.get("color", "#1B4332")
        delta_html = (
            f'<div style="font-size:.78rem;color:#52B788;font-weight:700;margin-top:6px">{c["delta"]}</div>'
            if c.get("delta") else ""
        )
        with col:
            st.markdown(
                f"""<div style="background:white;border-radius:14px;padding:22px 18px;
                     box-shadow:0 2px 14px rgba(0,0,0,.08);border:1px solid #E9ECEF;
                     text-align:center;transition:box-shadow .2s">
                     <div style="font-size:1.9rem;margin-bottom:8px;line-height:1">{c['icon']}</div>
                     <div style="font-size:1.65rem;font-weight:800;color:{color};line-height:1.1;
                                 letter-spacing:-.02em">{c['value']}</div>
                     <div style="font-size:.8rem;color:#6C757D;font-weight:500;margin-top:7px;
                                 text-transform:uppercase;letter-spacing:.04em">{c['label']}</div>
                     {delta_html}
                </div>""",
                unsafe_allow_html=True,
            )


def empty_state(icon: str, title: str, msg: str = "") -> None:
    """Estado vacío decorativo con borde punteado."""
    msg_html = f'<p style="color:#6C757D;margin:6px 0 0;font-size:.88rem;font-weight:400">{msg}</p>' if msg else ""
    st.markdown(
        f"""<div style="text-align:center;padding:48px 24px;background:#F8F9FA;
             border-radius:14px;border:2px dashed #DEE2E6;margin:16px 0">
             <div style="font-size:2.8rem;margin-bottom:14px;line-height:1">{icon}</div>
             <h3 style="color:#1B4332;font-weight:700;margin:0;font-size:1rem">{title}</h3>
             {msg_html}
        </div>""",
        unsafe_allow_html=True,
    )


def savings_hero(amount: float, label: str = "Ahorro acumulado del año") -> None:
    """Hero numérico de ahorro con gradiente oscuro."""
    st.markdown(
        f"""<div style="text-align:center;padding:36px 24px;
             background:linear-gradient(135deg,#1B4332 0%,#2D6A4F 100%);
             border-radius:14px;color:white;margin-bottom:24px;
             box-shadow:0 6px 24px rgba(27,67,50,.3)">
             <div style="font-size:3.8rem;font-weight:800;line-height:1;letter-spacing:-.04em">
                 {amount:.2f} €</div>
             <div style="font-size:.95rem;opacity:.82;margin-top:10px;font-weight:400">{label}</div>
        </div>""",
        unsafe_allow_html=True,
    )


def badge_html(text: str, bg: str = "#D8F3DC", color: str = "#1B4332") -> str:
    """Retorna HTML de un badge inline."""
    return (
        f'<span style="display:inline-block;padding:3px 10px;border-radius:20px;'
        f'background:{bg};color:{color};font-size:.7rem;font-weight:700;'
        f'letter-spacing:.06em;text-transform:uppercase;vertical-align:middle">{text}</span>'
    )


def alert_card_html(
    nombre: str, super_nombre: str, pct: float, precio_hoy: float, precio_hab: float
) -> str:
    """HTML para una card de alerta de bajada de precio."""
    return f"""
<div style="background:white;border-radius:12px;padding:16px 20px;
     box-shadow:0 2px 12px rgba(0,0,0,.08);border:1px solid #E9ECEF;
     margin-bottom:12px;display:flex;align-items:center;gap:18px">
  <div style="min-width:62px;text-align:center;background:#FFF0F0;border-radius:10px;padding:8px 4px">
    <div style="font-size:1.35rem;font-weight:800;color:#E63946;line-height:1">-{pct:.0f}%</div>
    <div style="font-size:.65rem;color:#E63946;font-weight:600;text-transform:uppercase">bajada</div>
  </div>
  <div style="flex:1;min-width:0">
    <div style="font-weight:700;font-size:.93rem;color:#212529;white-space:nowrap;
                overflow:hidden;text-overflow:ellipsis">{nombre}</div>
    <div style="font-size:.78rem;color:#6C757D;margin-top:2px">📍 {super_nombre}</div>
  </div>
  <div style="text-align:right;white-space:nowrap">
    <div style="font-size:1.15rem;font-weight:800;color:#52B788">{precio_hoy:.2f} €</div>
    <div style="font-size:.78rem;color:#ADB5BD;text-decoration:line-through">
        antes {precio_hab:.2f} €</div>
  </div>
</div>"""


def super_result_card(nombre: str, productos: int, subtotal: float, color: str, es_fav: bool) -> str:
    """HTML del encabezado de una card de supermercado en el optimizador."""
    fav_badge = badge_html("favorito", "#FFF3CD", "#856404") if es_fav else ""
    return f"""
<div style="border-radius:12px;padding:18px 22px;background:white;
     box-shadow:0 2px 14px rgba(0,0,0,.09);border-left:5px solid {color};
     display:flex;align-items:center;justify-content:space-between;
     margin-bottom:4px">
  <div>
    <div style="font-weight:800;font-size:1.05rem;color:#1B4332">🏪 {nombre} {fav_badge}</div>
    <div style="font-size:.8rem;color:#6C757D;margin-top:4px">{productos} producto(s)</div>
  </div>
  <div style="font-size:1.5rem;font-weight:800;color:{color}">{subtotal:.2f} €</div>
</div>"""


def savings_comparison_html(total_sin: float, total_con: float, ahorro: float) -> str:
    """Banner de comparativa de ahorro."""
    return f"""
<div style="background:linear-gradient(135deg,#1B4332 0%,#2D6A4F 100%);border-radius:14px;
     padding:22px 28px;color:white;margin:20px 0;text-align:center;
     box-shadow:0 4px 20px rgba(27,67,50,.25)">
  <div style="font-size:.88rem;opacity:.8;margin-bottom:8px">
    Sin optimizar gastarías hasta
    <span style="text-decoration:line-through;opacity:.9">{total_sin:.2f} €</span>
  </div>
  <div style="font-size:2rem;font-weight:800;letter-spacing:-.03em">
    Con Smart Shopping: {total_con:.2f} €
  </div>
  <div style="font-size:1rem;color:#95D5B2;font-weight:700;margin-top:10px">
    🎉 Ahorro estimado: {ahorro:.2f} €
  </div>
</div>"""
