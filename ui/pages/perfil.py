"""User profile and preferences page — diseño premium."""
import streamlit as st
import streamlit.components.v1 as components

from auth.session import cerrar_sesion
from database.repositories.usuarios_repo import UsuariosRepo
from domain.models import Usuario
from ordering.supermarket_links import get_by_pais
from ui.styles import page_header, section_header

_DIAS = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}
_DIAS_INV = {v: k for k, v in _DIAS.items()}
_PAISES = {"ES": "🇪🇸 España", "PT": "🇵🇹 Portugal", "AMBOS": "🌍 Ambos"}
_PAISES_INV = {v: k for k, v in _PAISES.items()}


def _reverse_geocode(lat: str, lon: str) -> tuple[str, str]:
    import requests as req
    try:
        resp = req.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "SmartShoppingIberia/1.0"},
            timeout=6,
        )
        data = resp.json()
        address = data.get("address", {})
        return address.get("postcode", "").strip(), address.get("country_code", "").upper()
    except Exception:
        return "", ""


def _geo_button() -> None:
    components.html(
        """
        <script>
        function detectarUbicacion() {
            var btn = document.getElementById('geo-btn');
            btn.disabled = true; btn.textContent = 'Detectando…';
            if (!navigator.geolocation) {
                alert('Tu navegador no soporta geolocalización.');
                btn.disabled = false; btn.textContent = '📍 Detectar automáticamente';
                return;
            }
            navigator.geolocation.getCurrentPosition(
                function(pos) {
                    var url = new URL(window.parent.location.href);
                    url.searchParams.set('geo_lat', pos.coords.latitude.toFixed(6));
                    url.searchParams.set('geo_lon', pos.coords.longitude.toFixed(6));
                    window.parent.location.href = url.toString();
                },
                function(err) {
                    btn.disabled = false; btn.textContent = '📍 Detectar automáticamente';
                    var msgs = {1:'Permiso denegado.',2:'Posición no disponible.',3:'Tiempo agotado.'};
                    alert('No se pudo obtener la ubicación: ' + (msgs[err.code] || err.message));
                },
                {timeout: 10000, maximumAge: 300000}
            );
        }
        </script>
        <button id="geo-btn" onclick="detectarUbicacion()"
                style="padding:6px 14px;border:1px solid #CED4DA;border-radius:6px;
                       cursor:pointer;background:white;font-size:13px;color:#2D6A4F;
                       font-weight:600">
            📍 Detectar automáticamente
        </button>
        """,
        height=44,
    )


def _handle_geo_params() -> None:
    if "geo_lat" not in st.query_params:
        return
    lat = st.query_params.get("geo_lat", "")
    lon = st.query_params.get("geo_lon", "")
    del st.query_params["geo_lat"]
    if "geo_lon" in st.query_params:
        del st.query_params["geo_lon"]
    if not lat or not lon:
        return
    with st.spinner("Obteniendo código postal…"):
        cp, country = _reverse_geocode(lat, lon)
    if cp:
        st.session_state["geo_cp"] = cp
        st.session_state["geo_country"] = country
        st.success(f"Ubicación detectada — CP: **{cp}**" + (f" ({country})" if country else ""))
    else:
        st.warning("No se pudo obtener el código postal. Introdúcelo manualmente.")


def mostrar(usuario: Usuario) -> None:
    page_header("Mi perfil", subtitle="Gestiona tus preferencias y cuenta.", emoji="👤")

    _handle_geo_params()

    cp_default = st.session_state.pop("geo_cp", usuario.codigo_postal or "")
    country_detected = st.session_state.pop("geo_country", "")

    # ── Verificación de email ─────────────────────────────────────────────────
    if not usuario.email_verificado:
        st.warning(
            "📧 **Email sin verificar** — Revisa tu bandeja de entrada y haz clic en el "
            "enlace de confirmación.",
            icon="📬",
        )
        col_v1, col_v2 = st.columns([3, 1])
        with col_v2:
            if st.button("🔄 Reenviar email", use_container_width=True):
                _reenviar_verificacion(usuario)

    # ── Datos personales ──────────────────────────────────────────────────────
    section_header("📝 Datos personales")
    with st.form("perfil_form"):
        nombre = st.text_input("Nombre", value=usuario.nombre)
        st.text_input("Email", value=usuario.email, disabled=True,
                      help="El email no se puede cambiar.")

        col1, col2 = st.columns(2)
        with col1:
            pais_sugerido = usuario.pais_activo
            if country_detected in ("ES", "PT") and country_detected != usuario.pais_activo:
                pais_sugerido = country_detected
            pais_label = st.selectbox(
                "País activo",
                list(_PAISES.values()),
                index=list(_PAISES.keys()).index(pais_sugerido),
                help="Detectado automáticamente" if country_detected else None,
            )
        with col2:
            cp = st.text_input("Código postal", value=cp_default,
                               help="Introducido manualmente o detectado por GPS.")

        dia_label = st.selectbox(
            "Día de compra habitual",
            list(_DIAS.values()),
            index=usuario.dia_compra,
        )
        save = st.form_submit_button("💾 Guardar cambios", type="primary",
                                     use_container_width=True)

    st.caption("¿No sabes tu código postal?")
    _geo_button()

    if save:
        UsuariosRepo().update_preferences(
            usuario.id,
            nombre=nombre.strip() or None,
            pais_activo=_PAISES_INV[pais_label],
            codigo_postal=cp.strip() or None,
            dia_compra=_DIAS_INV[dia_label],
        )
        st.success("Preferencias guardadas.")
        updated = UsuariosRepo().get_by_id(usuario.id)
        if updated:
            st.session_state["usuario"] = updated
        st.rerun()

    # ── Hábitos de compra ─────────────────────────────────────────────────────
    section_header("🏪 Hábitos de compra",
                   "El optimizador usa estos datos para calcular si merece ir a un segundo supermercado.")

    supers_disponibles = get_by_pais(usuario.pais_activo)
    opciones_nombre = {s["nombre"]: s["codigo"] for s in supers_disponibles}
    favoritos_nombres = [
        s["nombre"] for s in supers_disponibles
        if s["codigo"] in usuario.supermercados_favoritos
    ]

    with st.form("habitos_form"):
        seleccion = st.multiselect(
            "Mis supermercados habituales",
            options=list(opciones_nombre.keys()),
            default=favoritos_nombres,
        )
        coste = st.number_input(
            "Coste de desplazamiento extra (€/visita)",
            min_value=0.0, max_value=20.0,
            value=float(usuario.coste_desplazamiento),
            step=0.50,
            help="Gasolina + tiempo. Se descuenta del ahorro al valorar si merece visitar un supermercado extra.",
        )
        save_hab = st.form_submit_button("💾 Guardar hábitos", type="primary",
                                         use_container_width=True)

    if save_hab:
        repo = UsuariosRepo()
        codigos = [opciones_nombre[n] for n in seleccion]
        repo.update_favoritos(usuario.id, codigos)
        repo.update_coste_desplazamiento(usuario.id, coste)
        st.success("Hábitos de compra guardados.")
        updated = repo.get_by_id(usuario.id)
        if updated:
            st.session_state["usuario"] = updated
        st.rerun()

    # ── Notificaciones ────────────────────────────────────────────────────────
    section_header("📧 Notificaciones por email",
                   "Aviso cuando el precio de un producto de tu lista baje ≥15%.")

    with st.form("notif_form"):
        notif_activa = st.toggle(
            "Recibir alertas por email",
            value=usuario.notificaciones_email,
        )
        save_notif = st.form_submit_button("💾 Guardar", type="primary",
                                           use_container_width=True)

    if save_notif:
        UsuariosRepo().update_notificaciones_email(usuario.id, notif_activa)
        st.success("Preferencia de notificaciones guardada.")
        updated = UsuariosRepo().get_by_id(usuario.id)
        if updated:
            st.session_state["usuario"] = updated
        st.rerun()

    # ── Seguridad ─────────────────────────────────────────────────────────────
    section_header("🔐 Seguridad")
    st.caption(f"Último acceso: {usuario.ultimo_acceso or 'primera vez'}")
    st.caption(f"Cuenta creada: {usuario.created_at[:10] if usuario.created_at else '—'}")

    if st.button("🚪 Cerrar sesión", type="secondary"):
        token = st.session_state.get("token")
        if token:
            cerrar_sesion(token)
        st.session_state.clear()
        if "t" in st.query_params:
            del st.query_params["t"]
        st.rerun()


def _reenviar_verificacion(usuario: Usuario) -> None:
    try:
        import uuid
        from utils.config import APP_URL
        from utils.email_sender import build_verification_email, send_email

        token = str(uuid.uuid4())
        UsuariosRepo().set_verification_token(usuario.id, token)
        url = f"{APP_URL}?verify_token={token}"
        html = build_verification_email(usuario.nombre, url)
        ok = send_email(usuario.email, "Verifica tu cuenta — Smart Shopping Iberia", html)
        if ok:
            st.success(f"Email de verificación enviado a **{usuario.email}**.")
        else:
            st.warning("No se pudo enviar el email. Comprueba la configuración SMTP.")
    except Exception as exc:
        st.error(f"Error al reenviar: {exc}")
