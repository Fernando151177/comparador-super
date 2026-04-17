"""User profile and preferences page."""
import streamlit as st

from auth.session import cerrar_sesion
from database.repositories.usuarios_repo import UsuariosRepo
from domain.models import Usuario

_DIAS = {
    0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
    4: "Viernes", 5: "Sábado", 6: "Domingo",
}
_DIAS_INV = {v: k for k, v in _DIAS.items()}
_PAISES = {"ES": "🇪🇸 España", "PT": "🇵🇹 Portugal", "AMBOS": "🌍 Ambos"}
_PAISES_INV = {v: k for k, v in _PAISES.items()}


def mostrar(usuario: Usuario) -> None:
    st.title("👤 Mi perfil")

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
        # Refresh usuario in session_state
        updated = UsuariosRepo().get_by_id(usuario.id)
        if updated:
            st.session_state["usuario"] = updated
        st.rerun()

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
