"""Página de inicio de sesión."""
import streamlit as st

from auth.login import login_usuario, AuthenticationError
from auth.session import guardar_sesion


def mostrar() -> None:
    st.markdown("### 🔐 Iniciar sesión")

    with st.form("login_form"):
        email = st.text_input("Email", placeholder="tu@email.com")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar", use_container_width=True, type="primary")

    if submit:
        if not email or not password:
            st.error("Introduce email y contraseña.")
            return
        try:
            usuario, token = login_usuario(email, password)
            guardar_sesion(token)
            st.session_state["usuario"] = usuario
            st.rerun()
        except AuthenticationError as exc:
            st.error(str(exc))
