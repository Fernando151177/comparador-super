"""Tests de la capa de base de datos.

Unit tests: comprueban modelos y lógica sin tocar Supabase.
Integration tests (marca): comprueban repositorios contra Supabase real.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── Modelos de dominio (sin DB) ───────────────────────────────────────────────

def test_scraped_product_defaults():
    from domain.models import ScrapedProduct
    sp = ScrapedProduct(nombre="Leche", precio=0.89)
    assert sp.moneda == "EUR"
    assert sp.disponible is True
    assert sp.ean is None
    assert sp.precio_kilo is None


def test_scraped_product_completo():
    from domain.models import ScrapedProduct
    sp = ScrapedProduct(
        nombre="Aceite de oliva",
        precio=5.49,
        ean="8410188112015",
        precio_kilo=5.49,
        unidad_normalizacion="L",
    )
    assert sp.ean == "8410188112015"
    assert sp.precio_kilo == 5.49
    assert sp.unidad_normalizacion == "L"


def test_usuario_model():
    from domain.models import Usuario
    u = Usuario(
        id="uuid-test", nombre="Ana", email="ana@test.com",
        password_hash="hash", pais_activo="PT", codigo_postal="1000-001",
        dia_compra=6, created_at="2024-01-01", ultimo_acceso=None, activo=True,
    )
    assert u.pais_activo == "PT"
    assert u.activo is True


# ── Lógica de repositorios (DB mockeada) ──────────────────────────────────────

def _mock_conn(fetchone_val=None, fetchall_val=None):
    """Crea un context manager de conexión mockeado."""
    cur = MagicMock()
    cur.fetchone.return_value = fetchone_val
    cur.fetchall.return_value = fetchall_val or []

    conn = MagicMock()
    conn.execute.return_value = cur
    conn.__enter__ = MagicMock(return_value=conn)
    conn.__exit__ = MagicMock(return_value=False)
    return conn


def test_usuarios_repo_email_exists_true():
    from database.repositories.usuarios_repo import UsuariosRepo

    mock_conn = _mock_conn(fetchone_val={"id": "uuid-1"})
    with patch("database.repositories.usuarios_repo.get_connection", return_value=mock_conn):
        repo = UsuariosRepo()
        assert repo.email_exists("test@test.com") is True


def test_usuarios_repo_email_exists_false():
    from database.repositories.usuarios_repo import UsuariosRepo

    mock_conn = _mock_conn(fetchone_val=None)
    with patch("database.repositories.usuarios_repo.get_connection", return_value=mock_conn):
        repo = UsuariosRepo()
        assert repo.email_exists("no_existe@test.com") is False


def test_productos_repo_search_by_name():
    from database.repositories.productos_repo import ProductosRepo
    from domain.models import Producto

    fila = {
        "id": 1, "ean": None, "nombre": "Arroz largo",
        "marca": None, "categoria": "Arroz", "subcategoria": None,
        "unidad_medida": "500g", "url_imagen": None,
        "supermercado_id": 1, "activo": True,
        "created_at": "2024-01-01", "updated_at": "2024-01-01",
    }
    mock_conn = _mock_conn(fetchall_val=[fila])
    with patch("database.repositories.productos_repo.get_connection", return_value=mock_conn):
        repo = ProductosRepo()
        results = repo.search_by_name("arroz")
        assert len(results) == 1
        assert results[0].nombre == "Arroz largo"


def test_precios_repo_get_today_vacio():
    from database.repositories.precios_repo import PreciosRepo

    mock_conn = _mock_conn(fetchall_val=[])
    with patch("database.repositories.precios_repo.get_connection", return_value=mock_conn):
        repo = PreciosRepo()
        rows = repo.get_today(producto_id=999)
        assert rows == []


def test_precios_repo_get_median_sin_datos():
    from database.repositories.precios_repo import PreciosRepo

    mock_conn = _mock_conn(fetchall_val=[])
    with patch("database.repositories.precios_repo.get_connection", return_value=mock_conn):
        repo = PreciosRepo()
        assert repo.get_median_price(1, 1) is None


def test_precios_repo_get_median_impar():
    from database.repositories.precios_repo import PreciosRepo

    filas = [{"precio": p} for p in [1.20, 1.10, 1.30, 1.00, 1.40]]
    mock_conn = _mock_conn(fetchall_val=filas)
    with patch("database.repositories.precios_repo.get_connection", return_value=mock_conn):
        repo = PreciosRepo()
        mediana = repo.get_median_price(1, 1)
        # sorted: [1.00, 1.10, 1.20, 1.30, 1.40] → índice 2 → 1.20
        assert mediana == pytest.approx(1.20)


def test_alertas_repo_deactivate_llama_sql():
    from database.repositories.alertas_repo import AlertasRepo

    mock_conn = _mock_conn()
    with patch("database.repositories.alertas_repo.get_connection", return_value=mock_conn):
        repo = AlertasRepo()
        repo.deactivate(42)
        # Verificar que se ejecutó un UPDATE con el id correcto
        sql_call = mock_conn.execute.call_args[0][0]
        assert "UPDATE alertas" in sql_call
        assert mock_conn.execute.call_args[0][1] == (42,)


# ── Domain services (sin DB) ──────────────────────────────────────────────────

def test_normalize_price_per_kg_ml():
    from domain.services import normalize_price_per_kg
    price, label = normalize_price_per_kg(1.20, "500 ml")
    assert price == pytest.approx(2.40)
    assert label == "L"


def test_normalize_price_per_kg_kg():
    from domain.services import normalize_price_per_kg
    price, label = normalize_price_per_kg(2.50, "1 kg")
    assert price == pytest.approx(2.50)
    assert label == "kg"


def test_normalize_price_per_kg_multipack():
    from domain.services import normalize_price_per_kg
    price, label = normalize_price_per_kg(3.60, "4x195 g")
    assert price == pytest.approx(4.615, abs=0.01)
    assert label == "kg"


def test_normalize_price_per_kg_unidad():
    from domain.services import normalize_price_per_kg
    price, label = normalize_price_per_kg(1.0, "cada unidad")
    assert price is None


# ── Bulk detector (sin DB) ────────────────────────────────────────────────────

def test_bulk_detector_no_perecedero():
    from optimizer.bulk_detector import _is_non_perishable
    assert _is_non_perishable("Conservas", "Atún al natural") is True
    assert _is_non_perishable("Aceites", "Aceite de oliva") is True
    assert _is_non_perishable(None, "Arroz largo") is True
    assert _is_non_perishable(None, "Detergente lavadora") is True


def test_bulk_detector_perecedero():
    from optimizer.bulk_detector import _is_non_perishable
    assert _is_non_perishable("Lácteos", "Leche entera 1L") is False
    assert _is_non_perishable("Carnicería", "Pollo fresco") is False
    assert _is_non_perishable("Panadería", "Pan de molde") is False


# ── Integration tests (requieren Supabase) ────────────────────────────────────

@pytest.mark.integration
def test_integration_supermercados_sembrados():
    """Verifica que los 15 supermercados están en Supabase."""
    from database.connection import get_connection
    with get_connection() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM supermercados").fetchone()
    assert row["n"] == 15


@pytest.mark.integration
def test_integration_upsert_producto_y_precio():
    """Inserta producto + precio en Supabase y los recupera."""
    from database.connection import get_connection
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo
    from domain.models import ScrapedProduct

    with get_connection() as conn:
        super_id = conn.execute(
            "SELECT id FROM supermercados WHERE codigo = 'LIDL_ES'"
        ).fetchone()["id"]

    sp = ScrapedProduct(nombre="Yogur Natural Test", precio=0.45)
    prod_repo = ProductosRepo()
    price_repo = PreciosRepo()

    try:
        pid = prod_repo.upsert_from_scraped(sp, super_id)
        assert pid is not None

        price_repo.upsert_today(pid, super_id, sp)
        today = price_repo.get_today(producto_id=pid)
        assert len(today) == 1
        assert today[0]["precio"] == pytest.approx(0.45)

        # Idempotente: precio actualizado
        sp2 = ScrapedProduct(nombre="Yogur Natural Test", precio=0.39)
        price_repo.upsert_today(pid, super_id, sp2)
        today2 = price_repo.get_today(producto_id=pid)
        assert len(today2) == 1
        assert today2[0]["precio"] == pytest.approx(0.39)
    finally:
        with get_connection() as conn:
            conn.execute("DELETE FROM precios_historicos WHERE producto_id = %s", (pid,))
            conn.execute("DELETE FROM productos WHERE id = %s", (pid,))
