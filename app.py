"""Smart Shopping Iberia — Punto de entrada principal de Streamlit.

Arrancar:
    streamlit run app.py                              # solo local
    streamlit run app.py --server.address 0.0.0.0    # accesible desde móvil/tablet en la misma WiFi

Flujo de autenticación:
    1. Al cargar, se comprueba st.session_state["token"] → se valida con Supabase.
    2. Si no hay sesión, se muestran las pestañas de Login / Registro.
    3. Si hay sesión válida, se muestra la app completa con navegación lateral.
"""
import sys
from pathlib import Path

# Aseguramos que el directorio raíz del proyecto esté en sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st

# ── Siembra los supermercados si todavía no están en Supabase ─────────────────
# (Es seguro llamarla en cada arranque: ON CONFLICT DO NOTHING evita duplicados)
from database.init_db import init_db
init_db()

# ── Configuración de la página ────────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Shopping Iberia",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Comprobación de sesión ────────────────────────────────────────────────────
from auth.session import get_usuario_actual

usuario = get_usuario_actual()

# ── Sin sesión: mostrar login / registro ──────────────────────────────────────
if usuario is None:
    st.markdown(
        "<h1 style='text-align:center;margin-top:2rem'>🛒 Smart Shopping Iberia</h1>"
        "<p style='text-align:center;color:gray'>Compara precios en 15 supermercados de España y Portugal</p>",
        unsafe_allow_html=True,
    )
    st.markdown("---")

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        tab_login, tab_register = st.tabs(["Iniciar sesión", "Crear cuenta"])
        with tab_login:
            from ui.pages.login import mostrar as login_page
            login_page()
        with tab_register:
            from ui.pages.register import mostrar as register_page
            register_page()

    st.stop()

# ── Con sesión: app completa ──────────────────────────────────────────────────
st.session_state["usuario"] = usuario

# ── Barra lateral de navegación ───────────────────────────────────────────────
_PAIS_FLAG = {"ES": "🇪🇸", "PT": "🇵🇹", "AMBOS": "🌍"}
flag = _PAIS_FLAG.get(usuario.pais_activo, "")

st.sidebar.title(f"🛒 Smart Shopping {flag}")
st.sidebar.caption(f"Hola, **{usuario.nombre}**")
st.sidebar.markdown("---")

from utils.config import ADMIN_EMAIL as _ADMIN_EMAIL

_PAGES = [
    ("🏠 Inicio",               "home"),
    ("📋 Mi lista",             "lista"),
    ("🗺️ Optimizador sábado",  "optimizer"),
    ("💰 Panel de ahorro",      "savings"),
    ("🔔 Alertas",              "alerts"),
    ("🛍️ Pedido online",       "order"),
    ("📷 Escáner",              "scanner"),
    ("👤 Mi perfil",            "profile"),
]

if _ADMIN_EMAIL and usuario.email.lower() == _ADMIN_EMAIL.lower():
    _PAGES.append(("🔧 Admin",  "admin"))

pagina = st.sidebar.radio(
    "Navegación",
    [p[0] for p in _PAGES],
    label_visibility="collapsed",
)
page_key = dict(_PAGES)[pagina]

# ── Selector de país en la barra lateral ─────────────────────────────────────
st.sidebar.markdown("---")
pais_options = {"🇪🇸 España": "ES", "🇵🇹 Portugal": "PT", "🌍 Ambos": "AMBOS"}
current_label = {v: k for k, v in pais_options.items()}.get(usuario.pais_activo, "🇪🇸 España")
new_pais_label = st.sidebar.radio(
    "País activo",
    list(pais_options.keys()),
    index=list(pais_options.keys()).index(current_label),
    horizontal=True,
)
new_pais = pais_options[new_pais_label]
if new_pais != usuario.pais_activo:
    from database.repositories.usuarios_repo import UsuariosRepo
    UsuariosRepo().update_preferences(usuario.id, pais_activo=new_pais)
    usuario.pais_activo = new_pais
    st.session_state["usuario"] = usuario

st.sidebar.markdown("---")
st.sidebar.caption("🇪🇸 8 supermercados · 🇵🇹 7 supermercados")

# Botón de cierre de sesión en la barra lateral
if st.sidebar.button("🚪 Cerrar sesión"):
    from auth.session import cerrar_sesion
    token = st.session_state.get("token")
    if token:
        cerrar_sesion(token)
    st.session_state.clear()
    st.rerun()

# ── Enrutar a la página correspondiente ──────────────────────────────────────
if page_key == "home":
    from ui.pages.home import mostrar
    mostrar(usuario)

elif page_key == "lista":
    from ui.pages.lista_compra import mostrar
    mostrar(usuario)

elif page_key == "optimizer":
    from ui.pages.optimizador_sabado import mostrar
    mostrar(usuario)

elif page_key == "savings":
    from ui.pages.panel_ahorro import mostrar
    mostrar(usuario)

elif page_key == "alerts":
    from ui.pages.alertas_ofertas import mostrar
    mostrar(usuario)

elif page_key == "order":
    from ui.pages.pedido_online import mostrar
    mostrar(usuario)

elif page_key == "scanner":
    from ui.pages.scanner import mostrar
    mostrar(usuario)

elif page_key == "profile":
    from ui.pages.perfil import mostrar
    mostrar(usuario)

elif page_key == "admin":
    from ui.pages.admin import mostrar
    mostrar(usuario)
