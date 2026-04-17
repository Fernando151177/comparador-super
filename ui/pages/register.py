"""Página de registro de nuevos usuarios."""
import streamlit as st

from auth.register import registrar_usuario, RegistrationError
from auth.session import guardar_sesion

_DIAS = {
    "Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3,
    "Viernes": 4, "Sábado": 5, "Domingo": 6,
}


def mostrar() -> None:
    st.markdown("### 📝 Crear cuenta")

    with st.form("register_form"):
        nombre = st.text_input("Nombre")
        email = st.text_input("Email", placeholder="tu@email.com")
        password = st.text_input("Contraseña", type="password",
                                 help="Mínimo 8 caracteres")
        password2 = st.text_input("Repetir contraseña", type="password")

        col1, col2 = st.columns(2)
        with col1:
            pais = st.selectbox("País principal", ["🇪🇸 España", "🇵🇹 Portugal", "🌍 Ambos"])
        with col2:
            cp = st.text_input("Código postal", value="28001")

        dia_label = st.selectbox("Día de compra habitual", list(_DIAS.keys()), index=5)
        submit = st.form_submit_button("Crear cuenta", use_container_width=True, type="primary")

    if submit:
        if password != password2:
            st.error("Las contraseñas no coinciden.")
            return

        pais_code = {"🇪🇸 España": "ES", "🇵🇹 Portugal": "PT", "🌍 Ambos": "AMBOS"}[pais]

        try:
            usuario, token = registrar_usuario(
                nombre=nombre,
                email=email,
                password=password,
                pais_activo=pais_code,
                codigo_postal=cp,
                dia_compra=_DIAS[dia_label],
            )
            if token:
                # Si Supabase no requiere confirmación de email, entramos directamente
                guardar_sesion(token)
                st.session_state["usuario"] = usuario
                st.success(f"¡Bienvenido/a, {usuario.nombre}!")
                st.rerun()
            else:
                # Supabase requiere confirmar el email antes de iniciar sesión
                st.success(
                    f"Cuenta creada, {usuario.nombre}. "
                    "Revisa tu email y haz clic en el enlace de confirmación para entrar."
                )
        except RegistrationError as exc:
            st.error(str(exc))
