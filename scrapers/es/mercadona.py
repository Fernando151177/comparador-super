"""Mercadona ES scraper — full catalogue download with Streamlit cache.

Endpoints (no authentication required):
    POST https://tienda.mercadona.es/api/postal-codes/{cp}/
    GET  https://tienda.mercadona.es/api/categories/?lang=es
    GET  https://tienda.mercadona.es/api/categories/{id}/?lang=es
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
        """Fetches prices for the given queries from the Mercadona catalogue."""
        catalogue = self._get_catalogue()
        if not catalogue:
            print(f"[{self.NOMBRE}] Empty catalogue — skipping.")
            return []

        results: list[ScrapedProduct] = []
        for query in queries:
            match = self._best_match(query, catalogue)
            if match:
                results.append(self._to_scraped(query, match))
            else:
                print(f"[{self.NOMBRE}] Not found: {query!r}")

        return results

    # ── Catalogue ─────────────────────────────────────────────────────────────

    def _get_catalogue(self) -> list[dict]:
        """Returns the full catalogue, using Streamlit cache when available."""
        try:
            import streamlit as st
            return _cached_mercadona_catalogue(self.codigo_postal, self)
        except Exception:
            return self._download_catalogue()

    def _download_catalogue(self) -> list[dict]:
        """Downloads the full product catalogue from Mercadona."""
        self._set_postal_code()
        categories = self._fetch_categories()
        if not categories:
            return []

        all_products: list[dict] = []
        for cat in categories:
            all_products.extend(self._fetch_category_products(cat["id"]))

        return all_products

    def _set_postal_code(self) -> None:
        if self._postal_set:
            return
        self.post(
            f"{_BASE_URL}/postal-codes/{self.codigo_postal}/",
            extra_headers={"Content-Type": "application/json"},
        )
        self._postal_set = True

    def _fetch_categories(self) -> list[dict]:
        resp = self.get(f"{_BASE_URL}/categories/", params={"lang": "es"})
        if resp is None:
            return []
        return resp.json().get("results", [])

    def _fetch_category_products(self, category_id: int) -> list[dict]:
        resp = self.get(f"{_BASE_URL}/categories/{category_id}/", params={"lang": "es"})
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

    # ── Matching ─────────────────────────────────────────────────────────────

    def _best_match(self, query: str, catalogue: list[dict]) -> Optional[dict]:
        from difflib import SequenceMatcher
        import unicodedata as ud

        def norm(t: str) -> str:
            return ud.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

        query_words = set(norm(query).split())
        best_score, best = 0.0, None
        for product in catalogue:
            nombre = product.get("nombre", "")
            if not nombre:
                continue
            score = SequenceMatcher(None, norm(query), norm(nombre)).ratio()
            overlap = len(query_words & set(norm(nombre).split()))
            total = score + (overlap / max(len(query_words), 1)) * 0.30
            if total > best_score:
                best_score, best = total, product
        return best if best_score >= 0.35 else None

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


# ── Streamlit cache (evita descargar el catálogo en cada búsqueda) ────────────

try:
    import streamlit as st

    @st.cache_data(ttl=3600, show_spinner="Descargando catálogo Mercadona…")
    def _cached_mercadona_catalogue(codigo_postal: str, scraper) -> list[dict]:
        return scraper._download_catalogue()

except ImportError:
    def _cached_mercadona_catalogue(codigo_postal: str, scraper) -> list[dict]:
        return scraper._download_catalogue()


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
