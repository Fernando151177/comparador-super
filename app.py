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
from database.init_db import init_db
init_db()

# ── Scheduler de alertas en background (daemon) ───────────────────────────────
from utils.scheduler import start_daemon as _start_daemon
_start_daemon()

# ── Configuración de la página ────────────────────────────────────────────────
st.set_page_config(
    page_title="Smart Shopping Iberia",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Inyectar estilos globales ─────────────────────────────────────────────────
from ui.styles import inject_css
inject_css()

# ── Verificación de email via enlace ─────────────────────────────────────────
_verify_token = st.query_params.get("verify_token")
if _verify_token:
    from database.repositories.usuarios_repo import UsuariosRepo as _Repo
    _uid = _Repo().verify_email_token(_verify_token)
    if _uid:
        st.success("✅ Email verificado correctamente. ¡Ya puedes disfrutar de todas las funciones!")
    else:
        st.warning("El enlace de verificación no es válido o ya fue usado.")
    st.query_params.clear()

# ── Comprobación de sesión ────────────────────────────────────────────────────
from auth.session import get_usuario_actual

usuario = get_usuario_actual()

# ── Sin sesión: pantalla de login premium ─────────────────────────────────────
if usuario is None:
    st.markdown(
        """
        <div style="text-align:center;padding:60px 24px 32px">
          <div style="font-size:3rem;margin-bottom:12px">🛒</div>
          <h1 style="font-size:2.2rem;font-weight:800;color:#1B4332;margin:0;letter-spacing:-.03em">
              Smart Shopping Iberia
          </h1>
          <p style="color:#6C757D;font-size:1rem;margin:10px 0 4px;font-weight:400">
              Compra inteligente. Ahorra de verdad.
          </p>
          <p style="color:#ADB5BD;font-size:.85rem;margin:0">
              🇪🇸 8 supermercados &nbsp;·&nbsp; 🇵🇹 7 supermercados
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        tab_login, tab_register = st.tabs(["  Iniciar sesión  ", "  Crear cuenta  "])
        with tab_login:
            from ui.pages.login import mostrar as login_page
            login_page()
        with tab_register:
            from ui.pages.register import mostrar as register_page
            register_page()

    st.stop()

# ── Con sesión: app completa ──────────────────────────────────────────────────
st.session_state["usuario"] = usuario

# ── Banner de verificación pendiente ─────────────────────────────────────────
if not usuario.email_verificado:
    st.info(
        "📧 **Verifica tu email** — Revisa tu bandeja de entrada y haz clic en el enlace "
        "de confirmación para activar las notificaciones de bajadas de precio.",
        icon="📬",
    )

# ── Barra lateral — diseño premium ───────────────────────────────────────────
_PAIS_FLAG = {"ES": "🇪🇸", "PT": "🇵🇹", "AMBOS": "🌍"}
flag = _PAIS_FLAG.get(usuario.pais_activo, "")

# Logotipo + avatar usuario
inicial = (usuario.nombre or "?")[0].upper()
st.sidebar.markdown(
    f"""<div style="padding:8px 4px 12px">
         <div style="font-size:1.15rem;font-weight:800;color:white;letter-spacing:-.02em">
             🛒 Smart Shopping
         </div>
         <div style="font-size:.78rem;color:rgba(255,255,255,.6);margin-top:2px">
             Compra inteligente. Ahorra de verdad.
         </div>
    </div>
    <div style="display:flex;align-items:center;gap:12px;
         background:rgba(255,255,255,.1);border-radius:10px;padding:10px 14px;
         margin-bottom:4px">
      <div style="width:34px;height:34px;border-radius:50%;
           background:linear-gradient(135deg,#52B788,#40916C);
           display:flex;align-items:center;justify-content:center;
           font-weight:800;color:white;font-size:.95rem;flex-shrink:0">{inicial}</div>
      <div>
        <div style="font-weight:700;color:white;font-size:.88rem">{usuario.nombre}</div>
        <div style="font-size:.72rem;color:rgba(255,255,255,.6)">{flag} activo</div>
      </div>
    </div>""",
    unsafe_allow_html=True,
)
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

# Navegación desde barra inferior móvil (query param ?nav=xxx)
_nav_param = st.query_params.get("nav", "")
_page_keys  = [p[1] for p in _PAGES]
_nav_index  = _page_keys.index(_nav_param) if _nav_param in _page_keys else 0

pagina = st.sidebar.radio(
    "Navegación",
    [p[0] for p in _PAGES],
    index=_nav_index,
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
st.sidebar.markdown(
    '<div style="font-size:.72rem;color:rgba(255,255,255,.5);text-align:center;padding:2px 0">'
    '🇪🇸 8 supermercados &nbsp;·&nbsp; 🇵🇹 7 supermercados</div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown("")

if st.sidebar.button("🚪 Cerrar sesión"):
    from auth.session import cerrar_sesion
    token = st.session_state.get("token")
    if token:
        cerrar_sesion(token)
    st.session_state.clear()
    st.rerun()

# ── Barra de navegación inferior (móvil) ─────────────────────────────────────
from ui.styles import render_mobile_nav
render_mobile_nav(page_key)

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
