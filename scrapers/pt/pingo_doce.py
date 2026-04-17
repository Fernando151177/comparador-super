"""Pingo Doce PT scraper — API Jerónimo Martins.

Pingo Doce (Jerónimo Martins) expone una API de búsqueda:
    GET https://www.pingodoce.pt/api/products/search?query={term}&pageSize=10

Respuesta esperada: items[].{name, brand, price, ean, imageUrl}

Si el endpoint devuelve 403/404/HTML se intenta el endpoint
del catálogo online de la tienda.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.pingodoce.pt/api/products/search"
_SEARCH_URL_ALT = "https://www.pingodoce.pt/produtos/"
_PRODUCT_BASE = "https://www.pingodoce.pt"


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


class PingoDoctScraper(BaseScraper):
    """Scraper para pingodoce.pt."""

    NOMBRE = "Pingo Doce"
    CODIGO = "PINGO_DOCE_PT"
    PAIS = "PT"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-PT,pt;q=0.9",
            "Origin": "https://www.pingodoce.pt",
            "Referer": "https://www.pingodoce.pt/",
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
        # Endpoint principal
        resp = self.get(_SEARCH_URL, params={"query": query, "pageSize": 10})
        if resp is not None:
            try:
                data = resp.json()
                products = self._parse_response(data)
                if products:
                    return products
            except Exception:
                pass

        # Endpoint alternativo con parámetro diferente
        resp = self.get(_SEARCH_URL, params={"q": query, "size": 10})
        if resp is not None:
            try:
                data = resp.json()
                products = self._parse_response(data)
                if products:
                    return products
            except Exception:
                pass

        print(f"[{self.NOMBRE}] Sin resultados para: {query!r}")
        return []

    def _parse_response(self, data) -> list[dict]:
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = (
                data.get("items")
                or data.get("products")
                or data.get("results")
                or data.get("data")
                or []
            )
        else:
            return []

        products = []
        for raw in items:
            p = self._parse_product(raw)
            if p:
                products.append(p)
        return products

    def _parse_product(self, raw: dict) -> Optional[dict]:
        if not isinstance(raw, dict):
            return None

        nombre = (raw.get("name") or raw.get("title") or raw.get("description") or "").strip()
        if not nombre:
            return None

        precio = None
        for key in ("price", "salePrice", "sellPrice", "currentPrice", "pvp"):
            val = raw.get(key)
            if isinstance(val, (int, float)) and float(val) > 0:
                precio = float(val)
                break
            if isinstance(val, dict):
                for sub in ("value", "amount", "current", "pvp"):
                    if isinstance(val.get(sub), (int, float)):
                        precio = float(val[sub])
                        break
            if precio:
                break

        if not precio:
            return None

        ean = raw.get("ean") or raw.get("barcode") or raw.get("gtin") or None
        marca = raw.get("brand") or raw.get("brandName") or None

        imagen = (
            raw.get("imageUrl")
            or raw.get("image")
            or raw.get("thumbnail")
            or None
        )

        url_raw = raw.get("url") or raw.get("productUrl") or ""
        url_produto = (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None

        precio_kilo = None
        ppu = raw.get("pricePerKg") or raw.get("unitPrice") or raw.get("pricePerUnit")
        if isinstance(ppu, (int, float)) and float(ppu) > 0:
            precio_kilo = float(ppu)

        return {
            "nombre": nombre,
            "precio": precio,
            "ean": ean,
            "marca": marca,
            "precio_kilo": precio_kilo,
            "url_imagen": imagen,
            "url_producto": url_produto,
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

    scraper = PingoDoctScraper()
    queries = ["leite meio gordo", "pão de forma", "azeite"]
    results = scraper.run(queries)
    print(f"\n{'─'*60}")
    for r in results:
        print(f"  {r.nombre_buscado!r:25} → {r.nombre!r:40} {r.precio:.2f} €")
