"""Mercadona PT scraper — misma API que ES, dominio .pt.

Mercadona Portugal usa la misma arquitectura REST que España:
    POST https://www.mercadona.pt/api/postal-codes/{cp}/
    GET  https://www.mercadona.pt/api/categories/?lang=pt

Reutiliza MercadonaESScraper con la URL base de Portugal.
"""
from scrapers.es.mercadona import MercadonaESScraper

_BASE_URL_PT = "https://www.mercadona.pt/api"
_PRODUCT_URL_PT = "https://www.mercadona.pt/product/{id}"

# Código postal de Lisboa por defecto
_DEFAULT_CP_PT = "1000-001"


class MercadonaPTScraper(MercadonaESScraper):
    """Scraper para mercadona.pt — subclase de MercadonaESScraper."""

    NOMBRE = "Mercadona PT"
    CODIGO = "MERCADONA_PT"
    PAIS = "PT"

    def __init__(self, codigo_postal: str = _DEFAULT_CP_PT) -> None:
        super().__init__(codigo_postal=codigo_postal)
        # Actualizar cabeceras para dominio PT
        self.session.headers.update({
            "Origin": "https://www.mercadona.pt",
            "Referer": "https://www.mercadona.pt/",
            "Accept-Language": "pt-PT,pt;q=0.9",
        })

    def _set_postal_code(self) -> None:
        resp = self.post(
            f"{_BASE_URL_PT}/postal-codes/{self.codigo_postal}/",
            extra_headers={"Content-Type": "application/json"},
        )
        if resp is None:
            print(f"[{self.NOMBRE}] Warning: could not set postal code {self.codigo_postal}.")

    def _fetch_categories(self) -> list[dict]:
        resp = self.get(f"{_BASE_URL_PT}/categories/", params={"lang": "pt"})
        if resp is None:
            return []
        return resp.json().get("results", [])

    def _fetch_category_products(self, category_id: int) -> list[dict]:
        resp = self.get(
            f"{_BASE_URL_PT}/categories/{category_id}/", params={"lang": "pt"}
        )
        if resp is None:
            return []
        data = resp.json()
        products = []
        for sub in data.get("categories", []):
            for raw in sub.get("products", []):
                parsed = self._parse_raw_product(raw, data.get("name", ""))
                if parsed:
                    # Corregir URL al dominio PT
                    parsed["url_producto"] = _PRODUCT_URL_PT.format(id=raw.get("id", ""))
                    products.append(parsed)
        return products

    @staticmethod
    def _to_scraped(query: str, product: dict):
        from domain.models import ScrapedProduct
        return ScrapedProduct(
            nombre=product["nombre"],
            precio=product["precio"],
            moneda="EUR",
            ean=None,
            marca=product.get("marca"),
            categoria=product.get("categoria"),
            subcategoria=product.get("subcategoria"),
            precio_kilo=product.get("precio_kilo"),
            unidad_normalizacion="kg" if product.get("precio_kilo") else None,
            unidad_medida=product.get("unidad_medida"),
            url_imagen=product.get("url_imagen"),
            url_producto=product.get("url_producto"),
            disponible=True,
            nombre_buscado=query,
        )
