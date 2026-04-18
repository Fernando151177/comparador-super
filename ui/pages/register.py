"""Página de registro de nuevos usuarios."""
import streamlit as st

from auth.register import registrar_usuario, RegistrationError
from auth.session import guardar_sesion

_DIAS = {
    "Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3,
    "Viernes": 4, "Sábado": 5, "Domingo": 6,
}
_PAIS_MAP = {"🇪🇸 España": "ES", "🇵🇹 Portugal": "PT", "🌍 Ambos": "AMBOS"}


def _reverse_geocode(lat: str, lon: str) -> tuple[str, str]:
    """Devuelve (codigo_postal, codigo_pais) usando Nominatim. '' si falla."""
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


def mostrar() -> None:
    st.markdown("### 📝 Crear cuenta")

    # Procesar geo params si vienen de la redirección JS
    cp_default = "28001"
    pais_default = "🇪🇸 España"
    geo_info = ""

    if "geo_lat" in st.query_params:
        lat = st.query_params.get("geo_lat", "")
        lon = st.query_params.get("geo_lon", "")
        for key in ("geo_lat", "geo_lon"):
            if key in st.query_params:
                del st.query_params[key]
        if lat and lon:
            cp_det, country_det = _reverse_geocode(lat, lon)
            if cp_det:
                cp_default = cp_det
                if country_det == "PT":
                    pais_default = "🇵🇹 Portugal"
                elif country_det == "ES":
                    pais_default = "🇪🇸 España"
                geo_info = f"📍 Ubicación detectada: CP {cp_det}"

    if geo_info:
        st.success(geo_info)

    with st.form("register_form"):
        nombre   = st.text_input("Nombre")
        email    = st.text_input("Email", placeholder="tu@email.com")
        password = st.text_input("Contraseña", type="password",
                                 help="Mínimo 8 caracteres")
        password2 = st.text_input("Repetir contraseña", type="password")

        col1, col2 = st.columns(2)
        with col1:
            pais = st.selectbox(
                "País principal",
                list(_PAIS_MAP.keys()),
                index=list(_PAIS_MAP.keys()).index(pais_default),
            )
        with col2:
            cp = st.text_input(
                "Código postal",
                value=cp_default,
                help="O usa el botón de abajo para detectarlo automáticamente.",
            )

        dia_label = st.selectbox("Día de compra habitual", list(_DIAS.keys()), index=5)
        submit = st.form_submit_button("Crear cuenta", use_container_width=True, type="primary")

    # Botón de geolocalización — fuera del form
    st.caption("¿No sabes tu código postal?")
    st.html(
        """
        <script>
        function detectarUbicacion() {
            var btn = document.getElementById('geo-reg-btn');
            btn.disabled = true;
            btn.textContent = 'Detectando…';
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
        <button id="geo-reg-btn"
                onclick="detectarUbicacion()"
                style="padding:5px 12px;border:1px solid #d0d0d0;border-radius:4px;
                       cursor:pointer;background:#fafafa;font-size:13px;color:#333">
            📍 Detectar automáticamente
        </button>
        """
    )

    if submit:
        if password != password2:
            st.error("Las contraseñas no coinciden.")
            return

        try:
            usuario, token = registrar_usuario(
                nombre=nombre,
                email=email,
                password=password,
                pais_activo=_PAIS_MAP[pais],
                codigo_postal=cp,
                dia_compra=_DIAS[dia_label],
            )
            if token:
                guardar_sesion(token)
                st.session_state["usuario"] = usuario
                st.success(f"¡Bienvenido/a, {usuario.nombre}!")
                st.rerun()
            else:
                st.success(
                    f"Cuenta creada, {usuario.nombre}. "
                    "Revisa tu email y haz clic en el enlace de confirmación para entrar."
                )
        except RegistrationError as exc:
            st.error(str(exc))
