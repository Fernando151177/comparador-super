"""Tests del módulo de autenticación.

Los tests unitarios (sin marca) no tocan la base de datos — usan mocks.
Los tests de integración (marca @pytest.mark.integration) necesitan
una DATABASE_URL válida en el .env.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Helpers de validación (sin DB) ────────────────────────────────────────────

def test_validacion_nombre_vacio():
    from auth.register import _validar, RegistrationError
    with pytest.raises(RegistrationError, match="vacío"):
        _validar("", "a@b.com", "password123")


def test_validacion_nombre_corto():
    from auth.register import _validar, RegistrationError
    with pytest.raises(RegistrationError, match="2 caracteres"):
        _validar("A", "a@b.com", "password123")


def test_validacion_email_invalido():
    from auth.register import _validar, RegistrationError
    with pytest.raises(RegistrationError, match="email válido"):
        _validar("Usuario", "no-es-un-email", "password123")


def test_validacion_password_corta():
    from auth.register import _validar, RegistrationError
    with pytest.raises(RegistrationError, match="8 caracteres"):
        _validar("Usuario", "u@ejemplo.com", "corta")


def test_validacion_correcta():
    from auth.register import _validar
    _validar("Fernando", "f@ejemplo.com", "password123")  # no debe lanzar


# ── Bcrypt (sin DB) ────────────────────────────────────────────────────────────

def test_hash_y_verificacion_password():
    from auth.register import _hash_password
    from auth.login import _verificar_password

    pwd = "miContraseña99"
    hashed = _hash_password(pwd)
    assert hashed != pwd
    assert _verificar_password(pwd, hashed)
    assert not _verificar_password("otraContraseña", hashed)


def test_verificacion_hash_invalido_no_lanza():
    from auth.login import _verificar_password
    assert not _verificar_password("cualquier", "hash-no-valido")


# ── Login con DB mockeada ──────────────────────────────────────────────────────

def test_login_credenciales_vacias():
    from auth.login import login_usuario, AuthenticationError
    with pytest.raises(AuthenticationError, match="obligatorios"):
        login_usuario("", "password123")
    with pytest.raises(AuthenticationError, match="obligatorios"):
        login_usuario("user@test.com", "")


def test_login_usuario_no_encontrado():
    from auth.login import login_usuario, AuthenticationError
    mock_repo = MagicMock()
    mock_repo.get_by_email.return_value = None

    with patch("auth.login.UsuariosRepo", return_value=mock_repo):
        with pytest.raises(AuthenticationError, match="incorrectos"):
            login_usuario("ghost@test.com", "password123")


def test_login_usuario_inactivo():
    from auth.login import login_usuario, AuthenticationError
    from domain.models import Usuario

    usuario_inactivo = Usuario(
        id="uuid-1", nombre="Test", email="test@test.com",
        password_hash="hash", pais_activo="ES", codigo_postal="28001",
        dia_compra=5, created_at="2024-01-01", ultimo_acceso=None,
        activo=False,
    )
    mock_repo = MagicMock()
    mock_repo.get_by_email.return_value = usuario_inactivo

    with patch("auth.login.UsuariosRepo", return_value=mock_repo):
        with pytest.raises(AuthenticationError, match="incorrectos"):
            login_usuario("test@test.com", "password123")


def test_login_password_incorrecta():
    from auth.login import login_usuario, AuthenticationError
    from auth.register import _hash_password
    from domain.models import Usuario

    usuario = Usuario(
        id="uuid-1", nombre="Test", email="test@test.com",
        password_hash=_hash_password("passwordCorrecta"),
        pais_activo="ES", codigo_postal="28001",
        dia_compra=5, created_at="2024-01-01", ultimo_acceso=None,
        activo=True,
    )
    mock_repo = MagicMock()
    mock_repo.get_by_email.return_value = usuario

    with patch("auth.login.UsuariosRepo", return_value=mock_repo):
        with pytest.raises(AuthenticationError):
            login_usuario("test@test.com", "passwordErronea")


def test_login_credenciales_correctas():
    from auth.login import login_usuario
    from auth.register import _hash_password
    from domain.models import Usuario

    usuario = Usuario(
        id="uuid-1", nombre="Test", email="test@test.com",
        password_hash=_hash_password("passwordCorrecta"),
        pais_activo="ES", codigo_postal="28001",
        dia_compra=5, created_at="2024-01-01", ultimo_acceso=None,
        activo=True,
    )
    mock_repo = MagicMock()
    mock_repo.get_by_email.return_value = usuario

    with patch("auth.login.UsuariosRepo", return_value=mock_repo), \
         patch("auth.login.crear_sesion", return_value="token-abc"):
        u, token = login_usuario("test@test.com", "passwordCorrecta")
        assert u.email == "test@test.com"
        assert token == "token-abc"


# ── Registro con DB mockeada ───────────────────────────────────────────────────

def test_registro_email_duplicado():
    from auth.register import registrar_usuario, RegistrationError

    mock_repo = MagicMock()
    mock_repo.email_exists.return_value = True

    with patch("auth.register.UsuariosRepo", return_value=mock_repo):
        with pytest.raises(RegistrationError, match="ya está registrado"):
            registrar_usuario("Nombre", "dup@test.com", "password123")


def test_registro_exitoso():
    from auth.register import registrar_usuario
    from domain.models import Usuario

    nuevo = Usuario(
        id="uuid-nuevo", nombre="Fernando", email="fer@test.com",
        password_hash="hash", pais_activo="ES", codigo_postal="28001",
        dia_compra=5, created_at="2024-01-01", ultimo_acceso=None,
        activo=True,
    )
    mock_repo = MagicMock()
    mock_repo.email_exists.return_value = False
    mock_repo.create.return_value = nuevo

    with patch("auth.register.UsuariosRepo", return_value=mock_repo), \
         patch("auth.register.crear_sesion", return_value="token-xyz"):
        usuario, token = registrar_usuario("Fernando", "fer@test.com", "password123")
        assert usuario.email == "fer@test.com"
        assert token == "token-xyz"


# ── Integración real (requiere Supabase) ──────────────────────────────────────

@pytest.mark.integration
def test_integration_registro_y_login():
    """Registra un usuario real en Supabase y verifica login y sesión."""
    import uuid
    from auth.register import registrar_usuario, RegistrationError
    from auth.login import login_usuario
    from auth.session import validar_sesion, cerrar_sesion
    from database.connection import get_connection

    email_test = f"test_{uuid.uuid4().hex[:8]}@integration.test"
    password = "TestPass99!"

    try:
        usuario, token = registrar_usuario("Test Integration", email_test, password)
        assert usuario.id
        assert len(token) > 20

        u2, token2 = login_usuario(email_test, password)
        assert u2.email == email_test

        sesion = validar_sesion(token2)
        assert sesion is not None
        assert sesion.email == email_test

        cerrar_sesion(token2)
        assert validar_sesion(token2) is None
    finally:
        # Limpieza: eliminar el usuario de test
        with get_connection() as conn:
            conn.execute("DELETE FROM usuarios WHERE email = %s", (email_test,))
