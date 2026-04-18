"""Continente PT scraper — Playwright (el sitio requiere JS para renderizar).

URL de búsqueda: https://www.continente.pt/pesquisa/?q={query}
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from scrapers.playwright_base import PlaywrightBaseScraper


class ContinenteScraper(PlaywrightBaseScraper):
    """Scraper para continente.pt (Sonae)."""

    NOMBRE = "Continente"
    CODIGO = "CONTINENTE_PT"
    PAIS = "PT"

    _SEARCH_URL_TEMPLATE = "https://www.continente.pt/pesquisa/?q={query}"
    _WAIT_SELECTOR = ".ct-product-tile"
    _PRODUCT_SELECTORS = [
        ".ct-product-tile",
        ".product-tile",
    ]
    _NAME_SELECTORS = [
        ".ct-pdp-details a",
        ".ct-tile-description a",
        "a.link",
    ]
    _PRICE_SELECTORS = [
        ".pwc-tile--price-primary",
        ".ct-price-formatted",
        ".price .pwc-tile--price-primary",
        ".sales .value",
    ]
    _COOKIE_SELECTOR = "#onetrust-accept-btn-handler"
    _MIN_SCORE = 0.25

    # Modelo PT fallback reutiliza _to_scraped — mantenemos compatibilidad
    @staticmethod
    def _to_scraped(query: str, p: dict):
        from domain.models import ScrapedProduct
        return ScrapedProduct(
            nombre=p["nombre"],
            precio=p["precio"],
            moneda="EUR",
            ean=p.get("ean"),
            url_imagen=p.get("url_imagen"),
            url_producto=p.get("url_producto"),
            disponible=True,
            nombre_buscado=query,
        )
