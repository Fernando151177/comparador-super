"""User profile and preferences page."""
import streamlit as st

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


def mostrar(usuario: Usuario) -> None:
    st.title("👤 Mi perfil")

    # ── Datos personales ──────────────────────────────────────────────────────
    with st.form("perfil_form"):
        nombre = st.text_input("Nombre", value=usuario.nombre)
        st.text_input("Email", value=usuario.email, disabled=True,
                      help="El email no se puede cambiar.")

        col1, col2 = st.columns(2)
        with col1:
            pais_label = st.selectbox(
                "País activo",
                list(_PAISES.values()),
                index=list(_PAISES.keys()).index(usuario.pais_activo),
            )
        with col2:
            cp = st.text_input("Código postal", value=usuario.codigo_postal)

        dia_label = st.selectbox(
            "Día de compra habitual",
            list(_DIAS.values()),
            index=usuario.dia_compra,
        )
        save = st.form_submit_button("💾 Guardar cambios", type="primary")

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
    # Preselección: códigos favoritos actuales → nombres
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
