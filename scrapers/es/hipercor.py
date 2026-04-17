"""Hipercor ES scraper — API propia de El Corte Inglés.

Hipercor (grupo El Corte Inglés) expone una API JSON de supermercado:
    GET https://www.hipercor.es/supermarket/api/catalog/supermercado/
        ?q={term}&scope=supermarket&offset=0&items_per_page=10

Respuesta: items[].{title, name, price, brand, ean, thumbnails[]}
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.hipercor.es/supermarket/api/catalog/supermercado/"
_PRODUCT_BASE = "https://www.hipercor.es"


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


class HipercorScraper(BaseScraper):
    """Scraper para hipercor.es (El Corte Inglés)."""

    NOMBRE = "Hipercor"
    CODIGO = "HIPERCOR_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Origin": "https://www.hipercor.es",
            "Referer": "https://www.hipercor.es/supermarket/",
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
        resp = self.get(
            _SEARCH_URL,
            params={
                "q": query,
                "scope": "supermarket",
                "offset": 0,
                "items_per_page": 10,
            },
        )
        if resp is None:
            return []
        try:
            data = resp.json()
        except Exception:
            print(f"[{self.NOMBRE}] Respuesta no es JSON.")
            return []

        items = (
            data.get("items")
            or data.get("products")
            or data.get("results")
            or []
        )
        products = []
        for raw in items:
            p = self._parse_product(raw)
            if p:
                products.append(p)
        return products

    def _parse_product(self, raw: dict) -> Optional[dict]:
        nombre = (
            raw.get("title") or raw.get("name") or raw.get("display_name") or ""
        ).strip()
        if not nombre:
            return None

        # Precio — ECI usa varios campos
        precio = None
        for key in ("price", "selling_price", "min_price", "list_price"):
            val = raw.get(key)
            if isinstance(val, (int, float)) and float(val) > 0:
                precio = float(val)
                break
            if isinstance(val, dict):
                for sub in ("current", "amount", "value"):
                    if isinstance(val.get(sub), (int, float)):
                        precio = float(val[sub])
                        break
            if precio:
                break

        if not precio:
            return None

        ean = raw.get("ean") or raw.get("barcode") or None
        marca = raw.get("brand") or raw.get("brand_name") or None

        # Imagen
        imagen = None
        for key in ("thumbnail", "image_url", "picture"):
            img = raw.get(key)
            if isinstance(img, str) and img:
                imagen = img
                break
            if isinstance(img, list) and img:
                imagen = img[0] if isinstance(img[0], str) else img[0].get("url")
                break

        url_raw = raw.get("url") or raw.get("canonical_url") or ""
        url_producto = (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None

        precio_kilo = None
        ppu = raw.get("price_per_unit") or raw.get("unit_price")
        if isinstance(ppu, (int, float)) and float(ppu) > 0:
            precio_kilo = float(ppu)

        return {
            "nombre": nombre,
            "precio": precio,
            "ean": ean,
            "marca": marca,
            "precio_kilo": precio_kilo,
            "url_imagen": imagen,
            "url_producto": url_producto,
        }

    # ── Matching ──────────────────────────────────────────────────────────────

    def _best_match(self, query: str, candidates: list[dict]) -> Optional[dict]:
        if not candidates:
            return None
        qw = set(_normalize(query).split())
        best_score, best = 0.0, None
        for p in candidates:
            score = _similarity(query, p.get("nombre", ""))
            overlap = len(qw & set(_normalize(p.get("nombre", "")).split()))
            total = score + (overlap / max(len(qw), 1)) * 0.30
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
            marca=p.get("marca"),
            precio_kilo=p.get("precio_kilo"),
            unidad_normalizacion="kg" if p.get("precio_kilo") else None,
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

    scraper = HipercorScraper()
    queries = ["leche entera 1L", "pan de molde", "aceite de oliva"]
    results = scraper.run(queries)
    print(f"\n{'─'*60}")
    for r in results:
        print(f"  {r.nombre_buscado!r:25} → {r.nombre!r:40} {r.precio:.2f} €")
