"""Tests para el optimizador, calculador de ahorro y detector de acopio.

Unit tests: funciones puras, sin base de datos ni red.
Integration tests (marca @pytest.mark.integration): requieren DB activa.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── savings_calculator — funciones puras ──────────────────────────────────────

class TestDisplacementAdjustedSavings:
    def test_sin_extras_devuelve_ahorro_bruto(self):
        from optimizer.savings_calculator import get_displacement_adjusted_savings
        result = get_displacement_adjusted_savings(10.0, 2, 2, 3.0)
        assert result == 10.0

    def test_un_supermercado_extra(self):
        from optimizer.savings_calculator import get_displacement_adjusted_savings
        result = get_displacement_adjusted_savings(10.0, 3, 2, 3.0)
        assert result == 7.0

    def test_coste_mayor_que_ahorro_devuelve_cero(self):
        from optimizer.savings_calculator import get_displacement_adjusted_savings
        result = get_displacement_adjusted_savings(2.0, 4, 1, 3.0)
        assert result == 0.0

    def test_sin_coste_desplazamiento(self):
        from optimizer.savings_calculator import get_displacement_adjusted_savings
        result = get_displacement_adjusted_savings(15.0, 5, 1, 0.0)
        assert result == 15.0

    def test_redondeo_dos_decimales(self):
        from optimizer.savings_calculator import get_displacement_adjusted_savings
        result = get_displacement_adjusted_savings(10.0, 2, 1, 1.005)
        assert result == round(10.0 - 1.005, 2)

    def test_favoritos_mayor_que_visitados_no_falla(self):
        # Si se visitan menos de los favoritos habituales, extras = 0
        from optimizer.savings_calculator import get_displacement_adjusted_savings
        result = get_displacement_adjusted_savings(5.0, 1, 3, 2.0)
        assert result == 5.0


# ── bulk_detector — funciones puras ───────────────────────────────────────────

class TestNorm:
    def test_minusculas_y_sin_tildes(self):
        from optimizer.bulk_detector import _norm
        assert _norm("Aceite") == "aceite"
        assert _norm("Leché Éntera") == "leche entera"

    def test_espacios_recortados(self):
        from optimizer.bulk_detector import _norm
        assert _norm("  arroz  ") == "arroz"

    def test_cadena_vacia(self):
        from optimizer.bulk_detector import _norm
        assert _norm("") == ""


class TestIsNonPerishable:
    def test_aceite_es_no_perecedero(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable(None, "aceite de oliva virgen") is True

    def test_arroz_es_no_perecedero(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable(None, "arroz redondo") is True

    def test_leche_no_es_no_perecedero(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable(None, "leche entera 1L") is False

    def test_categoria_detecta_conserva(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable("conservas", "tomate frito") is True

    def test_detergente_es_no_perecedero(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable(None, "detergente ropa blanca") is True

    def test_fruta_fresca_es_perecedero(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable(None, "manzanas golden") is False

    def test_agua_es_no_perecedero(self):
        from optimizer.bulk_detector import _is_non_perishable
        assert _is_non_perishable(None, "agua mineral 1.5L") is True


class TestBestMatch:
    def _make_price(self, nombre, precio=1.0):
        return {"producto_nombre": nombre, "precio": precio,
                "producto_id": 1, "supermercado_id": 1,
                "supermercado_nombre": "Test", "categoria": None}

    def test_encuentra_mejor_coincidencia(self):
        from optimizer.bulk_detector import _best_match
        prices = [
            self._make_price("Aceite de oliva virgen extra 1L"),
            self._make_price("Galletas Maria 400g"),
        ]
        result = _best_match("aceite de oliva", prices)
        assert result is not None
        assert "aceite" in result["producto_nombre"].lower()

    def test_sin_coincidencia_devuelve_none(self):
        from optimizer.bulk_detector import _best_match
        prices = [self._make_price("Champú anti-caspa")]
        result = _best_match("pasta carbonara", prices)
        assert result is None

    def test_lista_vacia_devuelve_none(self):
        from optimizer.bulk_detector import _best_match
        assert _best_match("arroz", []) is None

    def test_coincidencia_exacta_tiene_mejor_score(self):
        from optimizer.bulk_detector import _best_match
        prices = [
            self._make_price("Arroz SOS 1kg"),
            self._make_price("Arroz basmati largo"),
            self._make_price("Leche entera 1L"),
        ]
        result = _best_match("arroz", prices)
        assert result is not None
        assert "arroz" in result["producto_nombre"].lower()


# ── saturday_optimizer — funciones puras ─────────────────────────────────────

class TestCostPerSingleSupermarket:
    def _build_by_product(self):
        return {
            1: [
                {"supermercado_codigo": "MERCADONA_ES", "supermercado_nombre": "Mercadona",
                 "precio": 1.0},
                {"supermercado_codigo": "CARREFOUR_ES", "supermercado_nombre": "Carrefour",
                 "precio": 1.20},
            ],
            2: [
                {"supermercado_codigo": "MERCADONA_ES", "supermercado_nombre": "Mercadona",
                 "precio": 2.0},
                {"supermercado_codigo": "CARREFOUR_ES", "supermercado_nombre": "Carrefour",
                 "precio": 1.80},
            ],
        }

    def test_calcula_totales_correctos(self):
        from optimizer.saturday_optimizer import _cost_per_single_supermarket
        by_product = self._build_by_product()
        product_ids = {1: ("leche", 1), 2: ("aceite", 1)}
        result = _cost_per_single_supermarket(by_product, product_ids, "ES")
        assert result["MERCADONA_ES"] == pytest.approx(3.0)
        assert result["CARREFOUR_ES"] == pytest.approx(3.0)

    def test_supermercado_sin_cobertura_total_excluido(self):
        from optimizer.saturday_optimizer import _cost_per_single_supermarket
        by_product = {
            1: [{"supermercado_codigo": "MERCADONA_ES",
                 "supermercado_nombre": "Mercadona", "precio": 1.0}],
            2: [{"supermercado_codigo": "LIDL_ES",
                 "supermercado_nombre": "Lidl", "precio": 2.0}],
        }
        product_ids = {1: ("leche", 1), 2: ("aceite", 1)}
        result = _cost_per_single_supermarket(by_product, product_ids, "ES")
        # Ningún supermercado cubre los dos → dict vacío
        assert result == {}

    def test_cantidad_multiplicada(self):
        from optimizer.saturday_optimizer import _cost_per_single_supermarket
        by_product = {
            1: [{"supermercado_codigo": "MERCADONA_ES",
                 "supermercado_nombre": "Mercadona", "precio": 2.0}],
        }
        product_ids = {1: ("leche", 3)}
        result = _cost_per_single_supermarket(by_product, product_ids, "ES")
        assert result["MERCADONA_ES"] == pytest.approx(6.0)

    def test_byproduct_vacio(self):
        from optimizer.saturday_optimizer import _cost_per_single_supermarket
        result = _cost_per_single_supermarket({}, {}, "ES")
        assert result == {}


class TestEmptyResult:
    def test_devuelve_resultado_vacio(self):
        from optimizer.saturday_optimizer import _empty_result
        from domain.models import OptimizerResult
        result = _empty_result()
        assert isinstance(result, OptimizerResult)
        assert result.plan == []
        assert result.total_optimo == 0.0
        assert result.ahorro_total == 0.0
        assert result.productos_sin_precio == []


class TestFuzzyFindProduct:
    """Test del matching difuso usando una conexión mockeada."""

    def _make_conn(self, rows):
        conn = MagicMock()
        cursor = MagicMock()
        cursor.fetchall.return_value = rows
        conn.execute.return_value = cursor
        return conn

    def test_encuentra_coincidencia_buena(self):
        from optimizer.saturday_optimizer import _fuzzy_find_product

        row = MagicMock()
        row.__getitem__ = lambda self, k: {"id": 42, "nombre": "Leche entera 1L"}[k]
        conn = self._make_conn([row])

        result = _fuzzy_find_product(conn, "leche entera", "ES", "2026-01-01")
        assert result == 42

    def test_rechaza_coincidencia_pobre(self):
        from optimizer.saturday_optimizer import _fuzzy_find_product

        row = MagicMock()
        row.__getitem__ = lambda self, k: {"id": 99, "nombre": "Champú hidratante"}[k]
        conn = self._make_conn([row])

        result = _fuzzy_find_product(conn, "leche entera", "ES", "2026-01-01")
        assert result is None

    def test_lista_vacia_devuelve_none(self):
        from optimizer.saturday_optimizer import _fuzzy_find_product
        conn = self._make_conn([])
        result = _fuzzy_find_product(conn, "leche", "ES", "2026-01-01")
        assert result is None


class TestOptimizeForUserMocked:
    """Tests del flujo completo con DB completamente mockeada."""

    def _mock_lista(self, items):
        """Devuelve ItemLista ficticios."""
        from domain.models import ItemLista
        return [
            ItemLista(id=i, usuario_id="u1", producto_id=None, ean=None,
                      query_texto=q, cantidad=c, prioridad=0, comprado=False)
            for i, (q, c) in enumerate(items, 1)
        ]

    def test_lista_vacia_devuelve_resultado_vacio(self):
        from optimizer.saturday_optimizer import optimize_for_user
        with patch("optimizer.saturday_optimizer._load_lista", return_value=[]), \
             patch("optimizer.saturday_optimizer._get_user_pais", return_value="ES"):
            result = optimize_for_user("u1")
        assert result.plan == []
        assert result.ahorro_total == 0.0

    def test_sin_precios_hoy_items_van_a_sin_precio(self):
        from optimizer.saturday_optimizer import optimize_for_user
        lista = self._mock_lista([("leche entera", 1), ("aceite oliva", 2)])
        with patch("optimizer.saturday_optimizer._load_lista", return_value=lista), \
             patch("optimizer.saturday_optimizer._get_user_pais", return_value="ES"), \
             patch("optimizer.saturday_optimizer._resolve_products",
                   return_value=({}, ["leche entera", "aceite oliva"])):
            result = optimize_for_user("u1")
        assert result.plan == []
        assert set(result.productos_sin_precio) == {"leche entera", "aceite oliva"}

    def test_plan_optimo_asigna_mas_barato(self):
        from optimizer.saturday_optimizer import optimize_for_user
        from domain.models import ItemLista
        lista = self._mock_lista([("leche entera", 2)])

        prices = [
            {"producto_id": 1, "supermercado_codigo": "MERCADONA_ES",
             "supermercado_nombre": "Mercadona", "producto_nombre": "Leche Entera 1L",
             "precio": 0.89, "precio_por_unidad_normalizado": None},
            {"producto_id": 1, "supermercado_codigo": "CARREFOUR_ES",
             "supermercado_nombre": "Carrefour", "producto_nombre": "Leche Entera 1L",
             "precio": 1.05, "precio_por_unidad_normalizado": None},
        ]
        mock_repo = MagicMock()
        mock_repo.get_prices_for_products.return_value = prices

        with patch("optimizer.saturday_optimizer._load_lista", return_value=lista), \
             patch("optimizer.saturday_optimizer._get_user_pais", return_value="ES"), \
             patch("optimizer.saturday_optimizer._resolve_products",
                   return_value=({1: ("leche entera", 2)}, [])), \
             patch("optimizer.saturday_optimizer.PreciosRepo", return_value=mock_repo):
            result = optimize_for_user("u1")

        assert len(result.plan) == 1
        item = result.plan[0]
        assert item.supermercado_codigo == "MERCADONA_ES"
        assert item.precio_unitario == pytest.approx(0.89)
        assert item.precio_total == pytest.approx(1.78)

    def test_modo_habitual_filtra_favoritos(self):
        from optimizer.saturday_optimizer import optimize_for_user
        lista = self._mock_lista([("aceite oliva", 1)])

        all_prices = [
            {"producto_id": 1, "supermercado_codigo": "MERCADONA_ES",
             "supermercado_nombre": "Mercadona", "producto_nombre": "Aceite Oliva 1L",
             "precio": 2.50, "precio_por_unidad_normalizado": None},
            {"producto_id": 1, "supermercado_codigo": "LIDL_ES",
             "supermercado_nombre": "Lidl", "producto_nombre": "Aceite Oliva 1L",
             "precio": 2.10, "precio_por_unidad_normalizado": None},
        ]
        mock_repo = MagicMock()
        mock_repo.get_prices_for_products.return_value = all_prices

        with patch("optimizer.saturday_optimizer._load_lista", return_value=lista), \
             patch("optimizer.saturday_optimizer._get_user_pais", return_value="ES"), \
             patch("optimizer.saturday_optimizer._resolve_products",
                   return_value=({1: ("aceite oliva", 1)}, [])), \
             patch("optimizer.saturday_optimizer.PreciosRepo", return_value=mock_repo):
            result = optimize_for_user(
                "u1", modo="habitual", favoritos=["MERCADONA_ES"]
            )

        # Lidl filtrado → solo Mercadona disponible
        assert len(result.plan) == 1
        assert result.plan[0].supermercado_codigo == "MERCADONA_ES"

    def test_coste_desplazamiento_suma_al_total(self):
        from optimizer.saturday_optimizer import optimize_for_user
        lista = self._mock_lista([("leche", 1), ("aceite", 1)])

        prices = [
            {"producto_id": 1, "supermercado_codigo": "MERCADONA_ES",
             "supermercado_nombre": "Mercadona", "producto_nombre": "Leche",
             "precio": 1.0, "precio_por_unidad_normalizado": None},
            {"producto_id": 2, "supermercado_codigo": "LIDL_ES",
             "supermercado_nombre": "Lidl", "producto_nombre": "Aceite",
             "precio": 2.0, "precio_por_unidad_normalizado": None},
        ]
        mock_repo = MagicMock()
        mock_repo.get_prices_for_products.return_value = prices

        with patch("optimizer.saturday_optimizer._load_lista", return_value=lista), \
             patch("optimizer.saturday_optimizer._get_user_pais", return_value="ES"), \
             patch("optimizer.saturday_optimizer._resolve_products",
                   return_value=({1: ("leche", 1), 2: ("aceite", 1)}, [])), \
             patch("optimizer.saturday_optimizer.PreciosRepo", return_value=mock_repo):
            result = optimize_for_user(
                "u1",
                modo="oportunidad",
                favoritos=["MERCADONA_ES"],
                coste_desplazamiento=2.0,
            )

        # Lidl es extra → +2€
        assert result.total_optimo == pytest.approx(1.0 + 2.0 + 2.0)
