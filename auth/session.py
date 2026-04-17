"""Gestión de sesiones de usuario.

El token (cadena aleatoria de 32 bytes) se guarda en la tabla 'sesiones'
de Supabase PostgreSQL y en st.session_state para no consultar la BD
en cada clic de Streamlit.
"""
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from database.connection import get_connection
from database.repositories.usuarios_repo import UsuariosRepo
from domain.models import Usuario
from utils.config import SESSION_EXPIRY_DAYS


def crear_sesion(usuario_id: str) -> str:
    """Genera un token nuevo, lo guarda en la BD y lo devuelve."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_EXPIRY_DAYS)

    with get_connection() as conn:
        conn.execute(
            "INSERT INTO sesiones (usuario_id, token, expires_at) VALUES (%s, %s, %s)",
            (usuario_id, token, expires_at),
        )
    return token


def validar_sesion(token: str) -> Optional[Usuario]:
    """Comprueba el token en la BD y devuelve el Usuario si es válido."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT s.usuario_id, s.expires_at
            FROM sesiones s
            JOIN usuarios u ON u.id = s.usuario_id
            WHERE s.token = %s AND u.activo = TRUE
            """,
            (token,),
        )
        row = cur.fetchone()

    if row is None:
        return None

    # Comprobar si el token ha expirado
    expiry = row["expires_at"]
    if hasattr(expiry, 'tzinfo') and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > expiry:
        _borrar_token(token)
        return None

    repo = UsuariosRepo()
    repo.update_ultimo_acceso(str(row["usuario_id"]))
    return repo.get_by_id(str(row["usuario_id"]))


def cerrar_sesion(token: str) -> None:
    """Elimina el token de la BD."""
    _borrar_token(token)


def get_usuario_actual() -> Optional[Usuario]:
    """Lee el token de st.session_state y devuelve el Usuario si la sesión es válida."""
    import streamlit as st

    token: Optional[str] = st.session_state.get("token")
    if not token:
        return None

    usuario = validar_sesion(token)
    if usuario is None:
        st.session_state.pop("token", None)
        st.session_state.pop("usuario", None)
    return usuario


def guardar_sesion(token: str) -> None:
    """Guarda el token en st.session_state."""
    import streamlit as st
    st.session_state["token"] = token


# ── Helpers privados ──────────────────────────────────────────────────────────

def _borrar_token(token: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM sesiones WHERE token = %s", (token,))
