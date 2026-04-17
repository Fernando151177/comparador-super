"""Mercadona ES scraper — uses Mercadona's undocumented REST API.

Endpoints (no authentication required):
    POST https://tienda.mercadona.es/api/postal-codes/{cp}/
         → sets the warehouse/region; must be called before fetching prices.
    GET  https://tienda.mercadona.es/api/categories/?lang=es
         → list of top-level categories.
    GET  https://tienda.mercadona.es/api/categories/{id}/?lang=es
         → products in a category (nested subcategories).

Strategy:
    Download the full product catalogue once per scraper instance (~30 s).
    Cache it in memory.  Match search queries using combined string similarity
    + keyword bonus scoring.

Rate limiting:
    0.3 s between category requests (polite, well below DDoS thresholds).
"""
import time
import unicodedata
from difflib import SequenceMatcher
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


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


class MercadonaESScraper(BaseScraper):
    """Full-catalogue scraper for tienda.mercadona.es."""

    NOMBRE = "Mercadona"
    CODIGO = "MERCADONA_ES"
    PAIS = "ES"

    # Similarity threshold below which a match is discarded
    _MIN_SCORE: float = 0.30

    def __init__(self, codigo_postal: str = DEFAULT_POSTAL_CODE) -> None:
        super().__init__()
        self.codigo_postal = codigo_postal
        self._catalogue: list[dict] = []   # in-memory cache
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Origin": "https://tienda.mercadona.es",
            "Referer": "https://tienda.mercadona.es/",
        })

    # ── Public API ────────────────────────────────────────────────────────────

    def scrape_products(self, queries: list[str]) -> list[ScrapedProduct]:
        """Fetches prices for the given queries from the Mercadona catalogue."""
        self._ensure_catalogue()

        results: list[ScrapedProduct] = []
        for query in queries:
            match = self._best_match(query)
            if match:
                results.append(self._to_scraped(query, match))
            else:
                print(f"[{self.NOMBRE}] Not found: {query!r}")

        return results

    # ── Catalogue management ──────────────────────────────────────────────────

    def _ensure_catalogue(self) -> None:
        """Downloads the full catalogue if not already cached."""
        if self._catalogue:
            return

        self._set_postal_code()
        categories = self._fetch_categories()
        if not categories:
            print(f"[{self.NOMBRE}] Failed to fetch categories.")
            return

        print(f"[{self.NOMBRE}] Downloading catalogue ({len(categories)} categories)…")
        all_products: list[dict] = []
        for i, cat in enumerate(categories):
            print(f"[{self.NOMBRE}]   {i + 1}/{len(categories)} {cat.get('name', '')}")
            all_products.extend(self._fetch_category_products(cat["id"]))
            time.sleep(0.3)

        self._catalogue = all_products
        print(f"[{self.NOMBRE}] Catalogue ready — {len(all_products)} products.")

    def _set_postal_code(self) -> None:
        """Sends the postal code to Mercadona so the API returns local prices."""
        resp = self.post(
            f"{_BASE_URL}/postal-codes/{self.codigo_postal}/",
            extra_headers={"Content-Type": "application/json"},
        )
        if resp is None:
            print(f"[{self.NOMBRE}] Warning: could not set postal code {self.codigo_postal}.")

    def _fetch_categories(self) -> list[dict]:
        resp = self.get(f"{_BASE_URL}/categories/", params={"lang": "es"})
        if resp is None:
            return []
        data = resp.json()
        return data.get("results", [])

    def _fetch_category_products(self, category_id: int) -> list[dict]:
        resp = self.get(
            f"{_BASE_URL}/categories/{category_id}/", params={"lang": "es"}
        )
        if resp is None:
            return []

        data = resp.json()
        products: list[dict] = []
        for sub in data.get("categories", []):
            for raw in sub.get("products", []):
                parsed = self._parse_raw_product(raw, data.get("name", ""))
                if parsed:
                    products.append(parsed)
        return products

    def _parse_raw_product(self, raw: dict, category_name: str) -> Optional[dict]:
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

        # Mercadona's API does not expose the EAN in this endpoint.
        return {
            "id":           raw.get("id"),
            "nombre":       raw.get("display_name", "").strip(),
            "marca":        None,   # not available in this endpoint
            "categoria":    category_name,
            "subcategoria": None,
            "precio":       precio,
            "precio_kilo":  precio_kilo,
            "unidad_medida": price_info.get("unit_size", ""),
            "url_imagen":   self._extract_image(raw),
            "url_producto": _PRODUCT_URL.format(id=raw.get("id", "")),
        }

    @staticmethod
    def _extract_image(raw: dict) -> Optional[str]:
        try:
            return raw["photos"][0]["zoom"]
        except (KeyError, IndexError, TypeError):
            return None

    # ── Matching ──────────────────────────────────────────────────────────────

    def _best_match(self, query: str) -> Optional[dict]:
        """Returns the catalogue product with the highest relevance score."""
        query_lower = _normalize(query)
        query_words = set(query_lower.split())

        best_score = 0.0
        best_product: Optional[dict] = None

        for product in self._catalogue:
            nombre = product.get("nombre", "")
            if not nombre:
                continue

            # Base string similarity
            score = _similarity(query, nombre)

            # Bonus: proportion of query words present in product name
            product_words = set(_normalize(nombre).split())
            overlap = len(query_words & product_words)
            bonus = (overlap / max(len(query_words), 1)) * 0.30

            total = score + bonus
            if total > best_score:
                best_score = total
                best_product = product

        if best_score < self._MIN_SCORE:
            return None
        return best_product

    # ── Conversion ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_scraped(query: str, product: dict) -> ScrapedProduct:
        return ScrapedProduct(
            nombre=product["nombre"],
            precio=product["precio"],
            moneda="EUR",
            ean=None,                    # not available via this API
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
