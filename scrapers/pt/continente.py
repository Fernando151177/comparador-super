"""Continente PT scraper — API Sonae.

Continente (Sonae) expone una API de búsqueda basada en OCC (Oracle Commerce Cloud):
    GET https://www.continente.pt/api/2.0/catalog/
        ?prefill=false&text={term}&pageSize=10&currentPage=0

También se puede intentar:
    GET https://www.continente.pt/on/demandware.store/Sites-Continente-Site/pt_PT/Search-Show
        ?q={term}&format=ajax

Respuesta: results[].{name, brand, sellPrice, ean, images[]}

Si los endpoints devuelven 410/403/HTML, el scraper devuelve []
sin lanzar excepción.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URLS = [
    "https://www.continente.pt/api/2.0/catalog/",
    "https://www.continente.pt/on/demandware.store/Sites-Continente-Site/pt_PT/Search-Show",
]
_PRODUCT_BASE = "https://www.continente.pt"


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


class ContinenteScraper(BaseScraper):
    """Scraper para continente.pt (Sonae)."""

    NOMBRE = "Continente"
    CODIGO = "CONTINENTE_PT"
    PAIS = "PT"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "pt-PT,pt;q=0.9",
            "Origin": "https://www.continente.pt",
            "Referer": "https://www.continente.pt/",
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
        # Intentar los distintos endpoints conocidos
        params_list = [
            {"text": query, "pageSize": 10, "currentPage": 0, "prefill": "false"},
            {"q": query, "format": "ajax", "start": 0, "sz": 10},
        ]
        for url, params in zip(_SEARCH_URLS, params_list):
            resp = self.get(url, params=params)
            if resp is None:
                continue
            try:
                data = resp.json()
                products = self._parse_response(data)
                if products:
                    return products
            except Exception:
                continue

        print(f"[{self.NOMBRE}] Todos los endpoints fallaron para: {query!r}")
        return []

    def _parse_response(self, data: dict) -> list[dict]:
        items = (
            data.get("results")
            or data.get("products")
            or data.get("hits")
            or data.get("productEntries")
            or []
        )
        products = []
        for raw in items:
            # OCC a veces envuelve en "product"
            if isinstance(raw, dict) and "product" in raw:
                raw = raw["product"]
            p = self._parse_product(raw)
            if p:
                products.append(p)
        return products

    def _parse_product(self, raw: dict) -> Optional[dict]:
        nombre = (raw.get("name") or raw.get("title") or "").strip()
        if not nombre:
            return None

        # Precio — Continente usa sellPrice o price
        precio = None
        for key in ("sellPrice", "price", "salePrice", "currentPrice"):
            val = raw.get(key)
            if isinstance(val, (int, float)) and float(val) > 0:
                precio = float(val)
                break
            if isinstance(val, dict):
                for sub in ("value", "amount", "current"):
                    if isinstance(val.get(sub), (int, float)):
                        precio = float(val[sub])
                        break
            if precio:
                break

        if not precio:
            return None

        ean = raw.get("ean") or raw.get("barcode") or None
        marca = raw.get("brand") or None

        # Imagen
        imagen = None
        imgs = raw.get("images") or raw.get("imageGroups") or []
        if isinstance(imgs, list) and imgs:
            first = imgs[0]
            if isinstance(first, str):
                imagen = first
            elif isinstance(first, dict):
                imagen = (
                    first.get("url")
                    or first.get("link")
                    or (first.get("images") or [{}])[0].get("link")
                )
        elif isinstance(imgs, str):
            imagen = imgs

        url_raw = raw.get("url") or raw.get("productUrl") or ""
        url_producto = (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None

        precio_kilo = None
        ppu = raw.get("pricePerUnit") or raw.get("unitPrice") or {}
        if isinstance(ppu, dict):
            v = ppu.get("value") or ppu.get("amount")
            if isinstance(v, (int, float)):
                precio_kilo = float(v)
        elif isinstance(ppu, (int, float)) and float(ppu) > 0:
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

    scraper = ContinenteScraper()
    queries = ["leite meio gordo", "pão de forma", "azeite"]
    results = scraper.run(queries)
    print(f"\n{'─'*60}")
    for r in results:
        print(f"  {r.nombre_buscado!r:25} → {r.nombre!r:40} {r.precio:.2f} €")
