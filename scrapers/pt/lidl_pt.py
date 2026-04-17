"""Lidl PT scraper — misma API que Lidl ES, parámetros PT.

Endpoint:
    GET https://www.lidl.pt/q/api/search
        ?assortment=PT&locale=pt_PT&version=v2.0.0&q={term}&pageSize=20

Reutiliza toda la lógica de LidlESScraper.
"""
from scrapers.es.lidl_es import LidlESScraper

_BASE_URL = "https://www.lidl.pt/q/api/search"
_PRODUCT_BASE = "https://www.lidl.pt"


class LidlPTScraper(LidlESScraper):
    """Scraper para lidl.pt — subclase de LidlESScraper con parámetros PT."""

    NOMBRE = "Lidl PT"
    CODIGO = "LIDL_PT"
    PAIS = "PT"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept-Language": "pt-PT,pt;q=0.9",
            "Origin": "https://www.lidl.pt",
            "Referer": "https://www.lidl.pt/",
        })

    def _search(self, query: str) -> list[dict]:
        resp = self.get(
            _BASE_URL,
            params={
                "assortment": "PT",
                "locale": "pt_PT",
                "version": "v2.0.0",
                "q": query,
                "pageSize": 20,
            },
        )
        if resp is None:
            return []
        try:
            data = resp.json()
        except Exception:
            return []

        products = []
        for item in data.get("items", []):
            parsed = self._parse_item(item)
            if parsed:
                # Corregir URL del producto para dominio PT
                if parsed.get("url_producto", "").startswith("https://www.lidl.es"):
                    parsed["url_producto"] = parsed["url_producto"].replace(
                        "https://www.lidl.es", _PRODUCT_BASE
                    )
                products.append(parsed)
        return products

    def _to_scraped(self, query, p):
        sp = super()._to_scraped(query, p)
        sp.moneda = "EUR"   # Portugal también usa EUR
        return sp
