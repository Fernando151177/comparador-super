"""Autenticación de usuario con bcrypt."""
import bcrypt

from auth.session import crear_sesion
from database.repositories.usuarios_repo import UsuariosRepo
from domain.models import Usuario


class AuthenticationError(Exception):
    """Se lanza cuando el login falla."""


def login_usuario(email: str, password: str) -> tuple[Usuario, str]:
    """Autentica al usuario y devuelve (usuario, token_sesion).

    Raises:
        AuthenticationError: si las credenciales son incorrectas.
    """
    if not email.strip() or not password:
        raise AuthenticationError("Email y contraseña son obligatorios.")

    repo = UsuariosRepo()
    usuario = repo.get_by_email(email)

    if usuario is None or not usuario.activo:
        raise AuthenticationError("Email o contraseña incorrectos.")

    if not _verificar_password(password, usuario.password_hash):
        raise AuthenticationError("Email o contraseña incorrectos.")

    token = crear_sesion(usuario.id)
    return usuario, token


def _verificar_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
