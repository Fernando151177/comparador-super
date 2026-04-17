"""Registro de nuevos usuarios."""
import uuid

import bcrypt

from auth.session import crear_sesion
from database.repositories.usuarios_repo import UsuariosRepo
from domain.models import Usuario


class RegistrationError(Exception):
    """Se lanza cuando el registro no puede completarse."""


def registrar_usuario(
    nombre: str,
    email: str,
    password: str,
    *,
    pais_activo: str = "ES",
    codigo_postal: str = "28001",
    dia_compra: int = 5,
) -> tuple[Usuario, str]:
    """Crea una nueva cuenta y devuelve (usuario, token_sesion).

    Raises:
        RegistrationError: si los datos no son válidos o el email ya existe.
    """
    _validar(nombre, email, password)

    repo = UsuariosRepo()
    if repo.email_exists(email):
        raise RegistrationError("Este email ya está registrado.")

    nuevo_id = str(uuid.uuid4())
    password_hash = _hash_password(password)

    try:
        usuario = repo.create(
            id=nuevo_id,
            nombre=nombre.strip(),
            email=email.strip().lower(),
            password_hash=password_hash,
            pais_activo=pais_activo,
            codigo_postal=codigo_postal.strip(),
            dia_compra=dia_compra,
        )
    except Exception as exc:
        raise RegistrationError(f"Error al crear la cuenta: {exc}") from exc

    token = crear_sesion(usuario.id)
    return usuario, token


def _validar(nombre: str, email: str, password: str) -> None:
    if not nombre.strip():
        raise RegistrationError("El nombre no puede estar vacío.")
    if len(nombre.strip()) < 2:
        raise RegistrationError("El nombre debe tener al menos 2 caracteres.")
    if "@" not in email or "." not in email.split("@")[-1]:
        raise RegistrationError("Introduce un email válido.")
    if len(password) < 8:
        raise RegistrationError("La contraseña debe tener al menos 8 caracteres.")


def _hash_password(password: str) -> str:
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
