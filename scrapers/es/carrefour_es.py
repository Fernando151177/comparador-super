"""Carrefour ES scraper — API de búsqueda interna.

Carrefour España expone un endpoint de búsqueda JSON:
    GET https://www.carrefour.es/search-api/query?jsonQuery={...}

El endpoint requiere cabeceras específicas para no recibir 403.
Si el endpoint sigue bloqueado, el método scrape_products devuelve []
sin lanzar excepción, para no interrumpir el resto de scrapers.

Cabeceras necesarias:
    Content-Type: application/json
    x-dtreferer: https://www.carrefour.es/
    User-Agent: (navegador moderno)
"""
import json
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.carrefour.es/search-api/query"
_PRODUCT_BASE = "https://www.carrefour.es"


def _normalize(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio()


class CarrefourESScraper(BaseScraper):
    """Scraper para carrefour.es."""

    NOMBRE = "Carrefour"
    CODIGO = "CARREFOUR_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json",
            "Accept-Language": "es-ES,es;q=0.9",
            "Content-Type": "application/json",
            "Origin": "https://www.carrefour.es",
            "Referer": "https://www.carrefour.es/",
            "x-dtreferer": "https://www.carrefour.es/",
        })

    # ── Public API ────────────────────────────────────────────────────────────

    def scrape_products(self, queries: list[str]) -> list[ScrapedProduct]:
        results: list[ScrapedProduct] = []
        for query in queries:
            candidates = self._search(query)
            best = self._best_match(query, candidates)
            if best:
                results.append(self._to_scraped(query, best))
            else:
                print(f"[{self.NOMBRE}] Not found: {query!r}")
        return results

    # ── API call ──────────────────────────────────────────────────────────────

    def _search(self, query: str) -> list[dict]:
        """Busca en carrefour.es y devuelve lista de productos parseados."""
        # Intentar endpoint de búsqueda tipo catálogo
        resp = self.get(
            "https://www.carrefour.es/tienda/alimentacion/c/alimentacion",
            params={"q": query, "pageSize": 10, "lang": "es"},
            extra_headers={"Accept": "application/json"},
        )

        if resp is None or resp.status_code != 200:
            # Fallback: intentar endpoint alternativo
            resp = self.get(
                "https://www.carrefour.es/api/catalog/search",
                params={"query": query, "pageSize": 10},
            )

        if resp is None:
            print(f"[{self.NOMBRE}] Blocked or unavailable for query: {query!r}")
            return []

        try:
            data = resp.json()
        except Exception:
            print(f"[{self.NOMBRE}] Response is not JSON (possibly HTML). Check if site requires cookies/JS.")
            return []

        return self._parse_response(data)

    def _parse_response(self, data: dict) -> list[dict]:
        """Parsea la respuesta de la API de Carrefour en distintos formatos."""
        products = []

        # Formato 1: {"products": [...]}
        items = data.get("products") or data.get("results") or data.get("hits") or []

        for raw in items:
            parsed = self._parse_product(raw)
            if parsed:
                products.append(parsed)
        return products

    def _parse_product(self, raw: dict) -> Optional[dict]:
        nombre = (
            raw.get("name") or raw.get("title") or raw.get("displayName") or ""
        ).strip()
        if not nombre:
            return None

        # Precio — Carrefour tiene varios formatos
        precio = None
        for key in ("price", "priceData", "currentPrice", "salePrice"):
            val = raw.get(key)
            if isinstance(val, (int, float)):
                precio = float(val)
                break
            if isinstance(val, dict):
                for sub in ("value", "price", "current"):
                    if isinstance(val.get(sub), (int, float)):
                        precio = float(val[sub])
                        break
            if precio is not None:
                break

        if not precio or precio <= 0:
            return None

        ean = raw.get("ean") or raw.get("barcode") or raw.get("gtin") or None
        unidad = raw.get("unitSize") or raw.get("packagingInfo") or None
        imagen = raw.get("thumbnail") or raw.get("image") or raw.get("imageUrl") or None
        url_raw = raw.get("url") or raw.get("productUrl") or ""
        url_producto = (
            (_PRODUCT_BASE + url_raw)
            if url_raw.startswith("/")
            else url_raw or None
        )
        categoria = raw.get("category") or raw.get("categories") or None
        if isinstance(categoria, list):
            categoria = categoria[0] if categoria else None

        return {
            "nombre": nombre,
            "precio": precio,
            "ean": ean,
            "unidad_medida": unidad,
            "url_imagen": imagen,
            "url_producto": url_producto,
            "categoria": str(categoria) if categoria else None,
        }

    # ── Matching ──────────────────────────────────────────────────────────────

    def _best_match(self, query: str, candidates: list[dict]) -> Optional[dict]:
        if not candidates:
            return None
        query_lower = _normalize(query)
        query_words = set(query_lower.split())
        best_score, best = 0.0, None
        for p in candidates:
            score = _similarity(query, p.get("nombre", ""))
            overlap = len(query_words & set(_normalize(p.get("nombre", "")).split()))
            total = score + (overlap / max(len(query_words), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p
        return best if best_score >= self._MIN_SCORE else None

    # ── Conversion ────────────────────────────────────────────────────────────

    @staticmethod
    def _to_scraped(query: str, p: dict) -> ScrapedProduct:
        return ScrapedProduct(
            nombre=p["nombre"],
            precio=p["precio"],
            moneda="EUR",
            ean=p.get("ean"),
            categoria=p.get("categoria"),
            unidad_medida=p.get("unidad_medida"),
            url_imagen=p.get("url_imagen"),
            url_producto=p.get("url_producto"),
            disponible=True,
            nombre_buscado=query,
        )


# ── Manual testing ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

    scraper = CarrefourESScraper()
    queries = ["leche entera 1L", "pan de molde", "aceite de oliva"]
    results = scraper.run(queries)

    print(f"\n{'─'*60}")
    for r in results:
        print(f"  {r.nombre_buscado!r:25} → {r.nombre!r:40} {r.precio:.2f} €")
