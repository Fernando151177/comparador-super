"""Mercadona ES scraper — uses Mercadona's search API.

Endpoints (no authentication required):
    POST https://tienda.mercadona.es/api/postal-codes/{cp}/
         → sets the warehouse/region; must be called before fetching prices.
    GET  https://tienda.mercadona.es/api/search/?query=TERM&lang=es
         → direct product search (fast, no full catalogue download needed).
"""
import unicodedata
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper
from utils.config import DEFAULT_POSTAL_CODE

_BASE_URL = "https://tienda.mercadona.es/api"
_PRODUCT_URL = "https://tienda.mercadona.es/product/{id}"


def _normalize(text: str) -> str:
    """Lower-cases and strips accents: 'Leche Entera' → 'leche entera'."""
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


class MercadonaESScraper(BaseScraper):
    """Search-based scraper for tienda.mercadona.es (one request per product)."""

    NOMBRE = "Mercadona"
    CODIGO = "MERCADONA_ES"
    PAIS = "ES"

    def __init__(self, codigo_postal: str = DEFAULT_POSTAL_CODE) -> None:
        super().__init__()
        self.codigo_postal = codigo_postal
        self._postal_set = False
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://tienda.mercadona.es",
            "Referer": "https://tienda.mercadona.es/",
        })

    # ── Public API ────────────────────────────────────────────────────────────

    def scrape_products(self, queries: list[str]) -> list[ScrapedProduct]:
        """Searches Mercadona's API once per query (no full catalogue download)."""
        self._ensure_postal_code()

        results: list[ScrapedProduct] = []
        for query in queries:
            product = self._search(query)
            if product:
                results.append(self._to_scraped(query, product))
            else:
                print(f"[{self.NOMBRE}] Not found: {query!r}")

        return results

    # ── Postal code ───────────────────────────────────────────────────────────

    def _ensure_postal_code(self) -> None:
        if self._postal_set:
            return
        resp = self.post(
            f"{_BASE_URL}/postal-codes/{self.codigo_postal}/",
            extra_headers={"Content-Type": "application/json"},
        )
        if resp is None:
            print(f"[{self.NOMBRE}] Warning: could not set postal code {self.codigo_postal}.")
        self._postal_set = True

    # ── Search ────────────────────────────────────────────────────────────────

    def _search(self, query: str) -> Optional[dict]:
        """Calls the search endpoint and returns the best matching product."""
        resp = self.get(
            f"{_BASE_URL}/search/",
            params={"query": query, "lang": "es"},
        )
        if resp is None:
            return None

        data = resp.json()
        products = data.get("products", [])
        if not products:
            return None

        # Return the first result (Mercadona's API already ranks by relevance)
        return self._parse_raw_product(products[0])

    def _parse_raw_product(self, raw: dict) -> Optional[dict]:
        """Extracts a normalised product dict from a raw API response item."""
        price_info = raw.get("price_instructions", {})
        try:
            precio = float(price_info.get("unit_price", 0) or 0)
        except (ValueError, TypeError):
            return None

        if precio <= 0:
            return None

        precio_kilo: Optional[float] = None
        try:
            bulk = price_info.get("bulk_price")
            if bulk:
                precio_kilo = float(bulk)
        except (ValueError, TypeError):
            pass

        return {
            "id":            raw.get("id"),
            "nombre":        raw.get("display_name", "").strip(),
            "marca":         None,
            "categoria":     raw.get("category", {}).get("name", "") if isinstance(raw.get("category"), dict) else "",
            "subcategoria":  None,
            "precio":        precio,
            "precio_kilo":   precio_kilo,
            "unidad_medida": price_info.get("unit_size", ""),
            "url_imagen":    self._extract_image(raw),
            "url_producto":  _PRODUCT_URL.format(id=raw.get("id", "")),
        }

    @staticmethod
    def _extract_image(raw: dict) -> Optional[str]:
        try:
            return raw["photos"][0]["zoom"]
        except (KeyError, IndexError, TypeError):
            return None

    # ── Conversion ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_scraped(query: str, product: dict) -> ScrapedProduct:
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


# ── Manual testing ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
    from database.init_db import init_db
    init_db()

    scraper = MercadonaESScraper()
    test_queries = ["leche entera 1L", "pan de molde", "aceite de oliva", "huevos L"]
    results = scraper.scrape_products(test_queries)

    print(f"\n{'─'*60}")
    for r in results:
        pkilo = f"  ({r.precio_kilo:.2f} €/kg)" if r.precio_kilo else ""
        print(f"  {r.nombre_buscado!r:22} → {r.nombre!r:38} {r.precio:.2f} €{pkilo}")
