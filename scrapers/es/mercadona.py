"""Mercadona ES scraper — descarga solo las categorías relevantes para las queries.

Endpoints:
    POST https://tienda.mercadona.es/api/postal-codes/{cp}/
    GET  https://tienda.mercadona.es/api/categories/?lang=es
    GET  https://tienda.mercadona.es/api/categories/{id}/?lang=es
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

import requests

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper
from utils.config import DEFAULT_POSTAL_CODE

_BASE_URL = "https://tienda.mercadona.es/api"
_PRODUCT_URL = "https://tienda.mercadona.es/product/{id}"

# Palabras clave por categoría para seleccionar solo las relevantes
_CATEGORY_KEYWORDS = {
    "fruta":    ["limon", "platano", "manzana", "pera", "naranja", "fresa", "uva",
                 "melon", "sandia", "kiwi", "mango", "cereza", "ciruela", "nectarina"],
    "verdura":  ["pimiento", "tomate", "lechuga", "cebolla", "ajo", "zanahoria",
                 "patata", "pepino", "calabacin", "brocoli", "espinaca", "acelga"],
    "lacteo":   ["leche", "yogur", "queso", "mantequilla", "nata", "huevo"],
    "carne":    ["pollo", "ternera", "cerdo", "pavo", "cordero", "jamon", "chorizo"],
    "pescado":  ["salmon", "merluza", "atun", "sardina", "bacalao", "gamba", "mejillon"],
    "pan":      ["pan", "barra", "tostada", "galleta", "cereal"],
    "bebida":   ["agua", "zumo", "refresco", "cerveza", "vino", "cafe", "te"],
    "limpieza": ["detergente", "suavizante", "friegaplatos", "bayeta", "papel"],
}


def _norm(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _relevant_categories(queries: list[str], all_cats: list[dict]) -> list[dict]:
    """Devuelve solo las categorías de Mercadona que coinciden con las queries."""
    query_words = set()
    for q in queries:
        query_words.update(_norm(q).split())

    # Detectar qué grupos de categorías necesitamos
    needed_groups: set[str] = set()
    for group, keywords in _CATEGORY_KEYWORDS.items():
        if query_words & set(keywords):
            needed_groups.add(group)

    if not needed_groups:
        # Si no detectamos categoría específica, devolver todas
        return all_cats

    # Filtrar categorías de Mercadona por nombre
    group_terms = {kw for g in needed_groups for kw in _CATEGORY_KEYWORDS[g]}
    relevant = []
    for cat in all_cats:
        cat_name = _norm(cat.get("name", ""))
        if any(kw in cat_name for kw in group_terms):
            relevant.append(cat)

    # Si el filtro es demasiado estricto y no coincide nada, devolver todas
    return relevant if relevant else all_cats




try:
    import streamlit as st

    @st.cache_data(ttl=3600, show_spinner=False)
    def _cached_catalogue(codigo_postal: str, category_ids_key: str) -> list[dict]:
        """Descarga solo las categorías indicadas (cacheado 1h)."""
        scraper = _make_bare_scraper(codigo_postal)
        ids = [int(x) for x in category_ids_key.split(",") if x]
        products: list[dict] = []
        for cat_id in ids:
            products.extend(scraper._fetch_category_products(cat_id, ""))
        return products

except ImportError:
    def _cached_catalogue(codigo_postal: str, category_ids_key: str) -> list[dict]:
        scraper = _make_bare_scraper(codigo_postal)
        ids = [int(x) for x in category_ids_key.split(",") if x]
        products: list[dict] = []
        for cat_id in ids:
            products.extend(scraper._fetch_category_products(cat_id, ""))
        return products


def _make_bare_scraper(codigo_postal: str) -> "MercadonaESScraper":
    """Crea un scraper sin llamar a __init__ de BaseScraper (para uso en caché)."""
    import requests as _requests
    scraper = MercadonaESScraper.__new__(MercadonaESScraper)
    scraper.session = _requests.Session()
    scraper.session.headers.update({
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://tienda.mercadona.es",
        "Referer": "https://tienda.mercadona.es/",
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        ),
    })
    scraper._postal_set = False
    scraper._supermarket_id = None
    scraper.codigo_postal = codigo_postal
    return scraper


class MercadonaESScraper(BaseScraper):
    """Scraper de Mercadona — descarga catálogo cacheado y busca por similitud."""

    NOMBRE = "Mercadona"
    CODIGO = "MERCADONA_ES"
    PAIS = "ES"
    _MIN_SCORE: float = 0.35

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
        # 1. Obtener lista de categorías (1 sola petición)
        self._set_postal_code()
        all_cats = self._fetch_categories()
        if not all_cats:
            return []

        # 2. Filtrar solo las categorías relevantes para las queries
        relevant = _relevant_categories(queries, all_cats)
        ids_key = ",".join(str(c["id"]) for c in relevant)

        # 3. Descargar solo esas categorías (cacheado 1h)
        catalogue = _cached_catalogue(self.codigo_postal, ids_key)
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

    # ── Descarga ──────────────────────────────────────────────────────────────

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

    def _fetch_category_products(self, category_id: int, category_name: str) -> list[dict]:
        resp = self.get(f"{_BASE_URL}/categories/{category_id}/", params={"lang": "es"})
        if resp is None:
            return []
        data = resp.json()
        products: list[dict] = []
        for sub in data.get("categories", []):
            for raw in sub.get("products", []):
                parsed = self._parse_raw_product(raw, category_name)
                if parsed:
                    products.append(parsed)
        return products

    def _parse_raw_product(self, raw: dict, category_name: str = "") -> Optional[dict]:
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
            "categoria":     category_name,
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

    # ── Matching ─────────────────────────────────────────────────────────────

    def _best_match(self, query: str, catalogue: list[dict]) -> Optional[dict]:
        query_words = set(_norm(query).split())
        best_score, best = 0.0, None
        for product in catalogue:
            nombre = product.get("nombre", "")
            if not nombre:
                continue
            score = _similarity(query, nombre)
            overlap = len(query_words & set(_norm(nombre).split()))
            total = score + (overlap / max(len(query_words), 1)) * 0.30
            if total > best_score:
                best_score, best = total, product
        return best if best_score >= self._MIN_SCORE else None

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

    scraper = MercadonaESScraper()
    test_queries = ["limon", "pimiento rojo", "platano", "leche entera"]
    results = scraper.scrape_products(test_queries)

    print(f"\n{'─'*60}")
    for r in results:
        pkilo = f"  ({r.precio_kilo:.2f} €/kg)" if r.precio_kilo else ""
        print(f"  {r.nombre_buscado!r:22} → {r.nombre!r:38} {r.precio:.2f} €{pkilo}")
