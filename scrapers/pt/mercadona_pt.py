"""Mercadona PT scraper — misma API que ES, dominio .pt.

Mercadona Portugal usa la misma arquitectura REST que España:
    POST https://www.mercadona.pt/api/postal-codes/{cp}/
    GET  https://www.mercadona.pt/api/categories/?lang=pt

No reutiliza _cached_catalogue del módulo ES (que hardcodea URLs .es).
Descarga las categorías relevantes directamente.
"""
from scrapers.es.mercadona import MercadonaESScraper, _relevant_categories

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
        self.session.headers.update({
            "Origin": "https://www.mercadona.pt",
            "Referer": "https://www.mercadona.pt/",
            "Accept-Language": "pt-PT,pt;q=0.9",
        })

    # ── Override scrape_products to use PT URLs directly (no ES cached fn) ────

    def scrape_products(self, queries: list[str]) -> list["ScrapedProduct"]:
        from domain.models import ScrapedProduct

        self._set_postal_code()
        all_cats = self._fetch_categories()
        if not all_cats:
            return []

        relevant = _relevant_categories(queries, all_cats)
        subcats = []
        for cat in relevant:
            for sub in cat.get("categories", []):
                subcats.append({
                    "id": sub["id"],
                    "name": sub.get("name", cat.get("name", "")),
                })
        if not subcats:
            return []

        catalogue: list[dict] = []
        for sub in subcats:
            catalogue.extend(self._fetch_category_products(sub["id"], sub["name"]))

        if not catalogue:
            print(f"[{self.NOMBRE}] Catálogo vacío.")
            return []

        results: list[ScrapedProduct] = []
        for query in queries:
            match = self._best_match(query, catalogue)
            if match:
                results.append(self._to_scraped(query, match))
            else:
                print(f"[{self.NOMBRE}] No encontrado: {query!r}")
        return results

    def _set_postal_code(self) -> None:
        if self._postal_set:
            return
        try:
            self.session.post(
                f"{_BASE_URL_PT}/postal-codes/{self.codigo_postal}/",
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
        except Exception:
            pass
        self._postal_set = True

    def _fetch_categories(self) -> list[dict]:
        resp = self.get(f"{_BASE_URL_PT}/categories/", params={"lang": "pt"})
        if resp is None:
            return []
        return resp.json().get("results", [])

    def _fetch_category_products(self, category_id: int, category_name: str = "") -> list[dict]:
        resp = self.get(
            f"{_BASE_URL_PT}/categories/{category_id}/", params={"lang": "pt"}
        )
        if resp is None:
            return []
        data = resp.json()
        products = []
        for sub in data.get("categories", []):
            for raw in sub.get("products", []):
                parsed = self._parse_raw_product(raw, category_name)
                if parsed:
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
