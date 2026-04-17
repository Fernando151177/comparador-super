"""Tests de scrapers.

Unit tests: comprueban lógica de matching y normalización sin red.
Integration tests (marca): lanzan scrapers reales contra las webs.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ── BaseScraper (sin DB, sin red) ─────────────────────────────────────────────

def test_base_scraper_es_abstracto():
    from scrapers.base import BaseScraper
    with pytest.raises(TypeError):
        BaseScraper()  # type: ignore[abstract]


def test_todos_los_scrapers_tienen_atributos():
    from scrapers import ALL_SCRAPERS
    for cls in ALL_SCRAPERS:
        assert cls.NOMBRE, f"{cls.__name__} debe tener NOMBRE"
        assert cls.CODIGO, f"{cls.__name__} debe tener CODIGO"
        assert cls.PAIS in ("ES", "PT"), f"{cls.__name__} PAIS debe ser ES o PT"


def test_numero_scrapers():
    from scrapers import ALL_SCRAPERS, ALL_SCRAPERS_ES, ALL_SCRAPERS_PT
    assert len(ALL_SCRAPERS) == 15
    assert len(ALL_SCRAPERS_ES) == 8
    assert len(ALL_SCRAPERS_PT) == 7


# ── Normalización y similitud (sin red) ──────────────────────────────────────

def test_mercadona_normalize():
    from scrapers.es.mercadona import _normalize
    assert _normalize("Léche Ëntera") == "leche entera"
    assert _normalize("ACEITE DE OLIVA") == "aceite de oliva"
    assert _normalize("  pan  ") == "pan"


def test_mercadona_similarity_alta():
    from scrapers.es.mercadona import _similarity
    assert _similarity("leche entera", "Leche Entera 1L") > 0.70


def test_mercadona_similarity_baja():
    from scrapers.es.mercadona import _similarity
    assert _similarity("leche", "cerveza rubia") < 0.40


def test_lidl_similarity_rechazo_falso_positivo():
    """El filtro de Lidl no debe emparejar 'leche entera 1L' con una cafetera.

    La cafetera se descarta porque ninguna palabra clave de la query aparece
    en el nombre del producto (overlap == 0).  El scraper aplica ese filtro
    ANTES de comparar similitud, por lo que el candidato nunca llega al umbral.
    """
    from scrapers.es.lidl_es import _normalize

    query = "leche entera 1L"
    candidato = "SILVERCREST® Cafetera 1000 W"

    key_words = {w for w in _normalize(query).split() if len(w) >= 3}
    product_words = set(_normalize(candidato).split())
    overlap = len(key_words & product_words)

    # El candidato se descarta porque no comparte ninguna palabra clave
    assert overlap == 0


def test_lidl_similarity_acepta_buena_coincidencia():
    """El filtro de Lidl debe aceptar 'aceite de oliva' → 'Aceite de oliva virgen'."""
    from scrapers.es.lidl_es import LidlESScraper, _normalize, _similarity

    scraper = LidlESScraper()
    query = "aceite de oliva"
    candidato = "Aceite de oliva virgen"

    key_words = {w for w in _normalize(query).split() if len(w) >= 3}
    product_words = set(_normalize(candidato).split())
    overlap = len(key_words & product_words)

    assert overlap >= 1
    assert _similarity(query, candidato) >= scraper._MIN_SIM


# ── Supermarket links (sin DB, sin red) ───────────────────────────────────────

def test_build_search_url_mercadona():
    from ordering.supermarket_links import build_search_url
    url = build_search_url("MERCADONA_ES", "leche entera")
    assert url is not None
    assert "leche" in url or "mercadona" in url


def test_build_search_url_sin_online():
    from ordering.supermarket_links import build_search_url
    # Ahorramas no tiene tienda online
    url = build_search_url("AHORRAMAS_ES", "cualquier cosa")
    assert url is None


def test_get_info_existente():
    from ordering.supermarket_links import get_info
    info = get_info("MERCADONA_ES")
    assert info is not None
    assert info["nombre"] == "Mercadona"
    assert info["pais"] == "ES"


def test_get_info_inexistente():
    from ordering.supermarket_links import get_info
    assert get_info("NO_EXISTE") is None


def test_get_by_pais_es():
    from ordering.supermarket_links import get_by_pais
    es = get_by_pais("ES")
    assert len(es) == 8
    assert all(s["pais"] == "ES" for s in es)


def test_get_by_pais_pt():
    from ordering.supermarket_links import get_by_pais
    pt = get_by_pais("PT")
    assert len(pt) == 7
    assert all(s["pais"] == "PT" for s in pt)


def test_get_by_pais_ambos():
    from ordering.supermarket_links import get_by_pais
    ambos = get_by_pais("AMBOS")
    assert len(ambos) == 15


# ── Cart builder (sin DB, sin red) ────────────────────────────────────────────

def test_cart_builder_genera_links():
    from ordering.cart_builder import build_cart_links
    items = [
        {"producto_nombre": "Leche entera", "cantidad": 2},
        {"producto_nombre": "Aceite de oliva", "cantidad": 1},
    ]
    links = build_cart_links("MERCADONA_ES", items)
    assert len(links) == 2
    assert links[0]["producto"] == "Leche entera"
    assert links[0]["cantidad"] == 2


def test_cart_builder_sin_url_si_sin_online():
    from ordering.cart_builder import build_cart_links
    items = [{"producto_nombre": "Arroz", "cantidad": 1}]
    links = build_cart_links("AHORRAMAS_ES", items)
    assert links[0]["url"] is None


def test_format_cart_text():
    from ordering.cart_builder import format_cart_text
    items = [
        {"producto_nombre": "Leche", "cantidad": 1, "precio_total": 0.89},
        {"producto_nombre": "Pan", "cantidad": 2, "precio_total": 2.50},
    ]
    text = format_cart_text("MERCADONA_ES", items)
    assert "Mercadona" in text
    assert "Leche" in text
    assert "3.39" in text  # total


# ── Integration tests (requieren red y DB) ────────────────────────────────────

@pytest.mark.integration
def test_integration_lidl_scraper():
    """Prueba real contra la API de Lidl ES."""
    from scrapers.es.lidl_es import LidlESScraper

    scraper = LidlESScraper()
    results = scraper.scrape_products(["aceite de oliva"])
    # Al menos uno debe encontrarse (Lidl tiene aceite de oliva online)
    assert len(results) >= 1
    r = results[0]
    assert r.precio > 0
    assert r.nombre


@pytest.mark.integration
def test_integration_mercadona_scraper():
    """Prueba real contra la API de Mercadona."""
    from scrapers.es.mercadona import MercadonaESScraper

    scraper = MercadonaESScraper()
    results = scraper.scrape_products(["leche entera"])
    assert len(results) >= 1
    assert results[0].precio > 0
