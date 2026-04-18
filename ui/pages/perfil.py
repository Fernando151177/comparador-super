"""User profile and preferences page."""
import streamlit as st
import streamlit.components.v1 as components

from auth.session import cerrar_sesion
from database.repositories.usuarios_repo import UsuariosRepo
from domain.models import Usuario
from ordering.supermarket_links import get_by_pais

_DIAS = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}
_DIAS_INV = {v: k for k, v in _DIAS.items()}
_PAISES = {"ES": "🇪🇸 España", "PT": "🇵🇹 Portugal", "AMBOS": "🌍 Ambos"}
_PAISES_INV = {v: k for k, v in _PAISES.items()}


# ── Geolocalización ───────────────────────────────────────────────────────────

def _reverse_geocode(lat: str, lon: str) -> tuple[str, str]:
    """Devuelve (codigo_postal, codigo_pais) usando Nominatim.  '' si falla."""
    import requests as req
    try:
        resp = req.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={"lat": lat, "lon": lon, "format": "json"},
            headers={"User-Agent": "SmartShoppingIberia/1.0 (contact@smartshopping.app)"},
            timeout=6,
        )
        data = resp.json()
        address = data.get("address", {})
        cp      = address.get("postcode", "").strip()
        country = address.get("country_code", "").upper()
        return cp, country
    except Exception:
        return "", ""


def _geo_button() -> None:
    """Renderiza un botón HTML/JS que obtiene la ubicación del navegador
    y recarga la página con ?geo_lat=X&geo_lon=Y en la URL."""
    components.html(
        """
        <script>
        function detectarUbicacion() {
            var btn = document.getElementById('geo-btn');
            btn.disabled = true;
            btn.textContent = 'Detectando…';
            if (!navigator.geolocation) {
                alert('Tu navegador no soporta geolocalización.');
                btn.disabled = false;
                btn.textContent = '📍 Detectar automáticamente';
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
                    btn.disabled = false;
                    btn.textContent = '📍 Detectar automáticamente';
                    var msgs = {1: 'Permiso denegado.', 2: 'Posición no disponible.',
                                3: 'Tiempo de espera agotado.'};
                    alert('No se pudo obtener la ubicación: ' + (msgs[err.code] || err.message));
                },
                {timeout: 10000, maximumAge: 300000}
            );
        }
        </script>
        <button id="geo-btn"
                onclick="detectarUbicacion()"
                style="padding:5px 12px;border:1px solid #d0d0d0;border-radius:4px;
                       cursor:pointer;background:#fafafa;font-size:13px;
                       color:#333;white-space:nowrap">
            📍 Detectar automáticamente
        </button>
        """,
        height=42,
    )


def _handle_geo_params() -> None:
    """Lee ?geo_lat / ?geo_lon, llama a Nominatim y guarda el resultado
    en session_state para que el formulario lo use como valor por defecto."""
    if "geo_lat" not in st.query_params:
        return

    lat = st.query_params.get("geo_lat", "")
    lon = st.query_params.get("geo_lon", "")

    # Limpiar params de la URL antes de continuar
    del st.query_params["geo_lat"]
    if "geo_lon" in st.query_params:
        del st.query_params["geo_lon"]

    if not lat or not lon:
        return

    with st.spinner("Obteniendo código postal…"):
        cp, country = _reverse_geocode(lat, lon)

    if cp:
        st.session_state["geo_cp"]      = cp
        st.session_state["geo_country"] = country
        st.success(f"Ubicación detectada — CP: **{cp}**" + (f" ({country})" if country else ""))
    else:
        st.warning("No se pudo obtener el código postal. Introdúcelo manualmente.")


# ── Página principal ──────────────────────────────────────────────────────────

def mostrar(usuario: Usuario) -> None:
    st.title("👤 Mi perfil")

    # Procesar geo params si vienen de la redirección JS
    _handle_geo_params()

    # Valor prefill para el CP: geo detectado > valor actual del usuario
    cp_default = st.session_state.pop("geo_cp", usuario.codigo_postal or "")
    country_detected = st.session_state.pop("geo_country", "")

    # ── Datos personales ──────────────────────────────────────────────────────
    with st.form("perfil_form"):
        nombre = st.text_input("Nombre", value=usuario.nombre)
        st.text_input("Email", value=usuario.email, disabled=True,
                      help="El email no se puede cambiar.")

        col1, col2 = st.columns(2)
        with col1:
            # Sugerir cambio de país si la geo detectó ES o PT distinto al activo
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
            cp = st.text_input(
                "Código postal",
                value=cp_default,
                help="Introducido manualmente o detectado por GPS.",
            )

        dia_label = st.selectbox(
            "Día de compra habitual",
            list(_DIAS.values()),
            index=usuario.dia_compra,
        )
        save = st.form_submit_button("💾 Guardar cambios", type="primary")

    # Botón de geolocalización — fuera del form para poder usar components.html
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
    st.markdown("---")
    st.subheader("🏪 Hábitos de compra")
    st.caption(
        "Indica en qué supermercados sueles comprar y cuánto te cuesta "
        "desplazarte a uno adicional. El optimizador usará estos datos para "
        "calcular si merece la pena ir a un segundo supermercado."
    )

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
            help="El optimizador en modo 'habitual' solo usará estos supermercados.",
        )
        coste = st.number_input(
            "Coste de desplazamiento a un supermercado extra (€)",
            min_value=0.0,
            max_value=20.0,
            value=float(usuario.coste_desplazamiento),
            step=0.50,
            help="Gasolina + tiempo. Se descuenta del ahorro al valorar si merece visitar un supermercado extra.",
        )
        save_hab = st.form_submit_button("💾 Guardar hábitos", type="primary")

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

    # ── Notificaciones por email ───────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📧 Notificaciones por email")
    st.caption(
        "Cuando el scraper diario detecte una bajada de precio ≥15% en tu lista, "
        "te avisamos por email. Requiere que el administrador configure el servidor SMTP."
    )

    with st.form("notif_form"):
        notif_activa = st.toggle(
            "Recibir alertas por email",
            value=usuario.notificaciones_email,
        )
        save_notif = st.form_submit_button("💾 Guardar", type="primary")

    if save_notif:
        UsuariosRepo().update_notificaciones_email(usuario.id, notif_activa)
        st.success("Preferencia de notificaciones guardada.")
        updated = UsuariosRepo().get_by_id(usuario.id)
        if updated:
            st.session_state["usuario"] = updated
        st.rerun()

    # ── Seguridad ─────────────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("Seguridad")
    st.caption(f"Último acceso: {usuario.ultimo_acceso or 'primera vez'}")

    if st.button("🚪 Cerrar sesión", type="secondary"):
        token = st.session_state.get("token")
        if token:
            cerrar_sesion(token)
        st.session_state.clear()
        if "t" in st.query_params:
            del st.query_params["t"]
        st.rerun()
