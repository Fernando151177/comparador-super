"""Ahorramas ES scraper — Playwright stealth.

ahorramas.com renderiza resultados de búsqueda en HTML servidor pero bloquea
peticiones HTTP simples por User-Agent/IP.  Playwright con stealth bypasea
la detección de bots y permite extraer los productos correctamente.

URL de búsqueda: https://www.ahorramas.com/search?q={query}
Nota: Ahorramas opera principalmente en Madrid y centro de España.
"""
from scrapers.playwright_base import PlaywrightBaseScraper


class AhorramasScraper(PlaywrightBaseScraper):
    NOMBRE = "Ahorramas"
    CODIGO = "AHORRAMAS_ES"
    PAIS = "ES"

    _SEARCH_URL_TEMPLATE = "https://www.ahorramas.com/search?q={query}"
    _WAIT_SELECTOR = ".product-card, .product-item, [data-id-product]"
    _PRODUCT_SELECTORS = [
        ".product-card",
        ".product-item",
        "[data-id-product]",
        ".product-miniature",
        "article.product",
    ]
    _NAME_SELECTORS = [
        ".product-title a",
        ".product-name a",
        "h3 a",
        "h2 a",
        "a.product-title",
        ".name",
    ]
    _PRICE_SELECTORS = [
        ".price",
        ".current-price span",
        ".product-price",
        "[data-price]",
        "span.price",
    ]
    _COOKIE_SELECTOR = "#onetrust-accept-btn-handler"
    _MIN_SCORE = 0.25
