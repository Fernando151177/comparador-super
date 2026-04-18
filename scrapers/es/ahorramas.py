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
    _WAIT_SELECTOR = ".product-tile"
    _PRODUCT_SELECTORS = [
        ".product-tile",
        ".product-container",
    ]
    _NAME_SELECTORS = [
        ".pdp-link .link",
        "a.link.product-name-gtm",
        ".pdp-link a",
        ".tile-body a",
    ]
    _PRICE_SELECTORS = [
        ".sales .value",
        ".price .sales",
        ".value",
        ".price",
    ]
    _COOKIE_SELECTOR = "#onetrust-accept-btn-handler"
    _MIN_SCORE = 0.25
