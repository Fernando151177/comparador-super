"""Cash Family ES scraper — Playwright stealth.

Family Cash es una cadena de hipermercados valenciana (grupo Miquel Alimentació)
con 43 tiendas en España y Andorra.

Su sitio web (familycash.es) no expone un catálogo online con precios,
por lo que este scraper intenta las páginas de secciones de alimentación
y devuelve [] si no hay productos online disponibles.

Si en el futuro habilitan tienda online, basta con actualizar
_SEARCH_URL_TEMPLATE y los selectores CSS.
"""
from scrapers.playwright_base import PlaywrightBaseScraper


class CashFamilyScraper(PlaywrightBaseScraper):
    NOMBRE = "Cash Family"
    CODIGO = "CASH_FAMILY_ES"
    PAIS = "ES"

    # Intentar la sección de alimentación como punto de entrada
    _SEARCH_URL_TEMPLATE = "https://www.familycash.es/alimentacion/?q={query}"
    _WAIT_SELECTOR = ".product-card, .product-item, .producto, [class*='product']"
    _PRODUCT_SELECTORS = [
        ".product-card",
        ".product-item",
        ".producto",
        "[class*='product-card']",
        "[class*='product-item']",
    ]
    _NAME_SELECTORS = [
        ".product-title",
        ".nombre",
        ".name",
        "h3",
        "h2",
    ]
    _PRICE_SELECTORS = [
        ".price",
        ".precio",
        "[class*='price']",
        "[class*='precio']",
    ]
    _MIN_SCORE = 0.25
