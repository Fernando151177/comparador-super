"""Día ES scraper — backend SAP Hybris.

Endpoint de búsqueda:
    GET https://www.dia.es/api/v2/products/search
        ?query={term}&pageSize=10&fields=FULL&lang=es

Respuesta: productEntries[].product.{name, price.value, ean, images[]}
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.dia.es/api/v2/products/search"
_PRODUCT_BASE = "https://www.dia.es"


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


class DiaScraper(BaseScraper):
    """Scraper para dia.es (SAP Hybris)."""

    NOMBRE = "Día"
    CODIGO = "DIA_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json",
            "Accept-Language": "es-ES,es;q=0.9",
            "Origin": "https://www.dia.es",
            "Referer": "https://www.dia.es/",
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
            params={"query": query, "pageSize": 10, "fields": "FULL", "lang": "es"},
        )
        if resp is None:
            return []
        try:
            data = resp.json()
        except Exception:
            print(f"[{self.NOMBRE}] Respuesta no es JSON. El sitio puede requerir cookies/JS.")
            return []

        products = []
        # Formato SAP Hybris: productEntries o products
        entries = (
            data.get("productEntries")
            or data.get("products")
            or data.get("results")
            or []
        )
        for entry in entries:
            # productEntries envuelven el producto en "product"
            raw = entry.get("product") or entry
            p = self._parse_product(raw)
            if p:
                products.append(p)
        return products

    def _parse_product(self, raw: dict) -> Optional[dict]:
        nombre = (raw.get("name") or raw.get("summary") or "").strip()
        if not nombre:
            return None

        # Precio
        precio = None
        price = raw.get("price") or {}
        if isinstance(price, dict):
            precio = price.get("value") or price.get("decimalValue")
        elif isinstance(price, (int, float)):
            precio = float(price)

        if not precio or float(precio) <= 0:
            return None

        ean = raw.get("ean") or raw.get("code") or None
        # Solo usamos como EAN si parece un código numérico de 8-14 dígitos
        if ean and not str(ean).isdigit():
            ean = None

        # Imagen
        imagen = None
        images = raw.get("images") or []
        if images:
            # Hybris devuelve lista de imágenes con "format": "product", "thumbnail", etc.
            for img in images:
                if isinstance(img, dict) and img.get("format") in ("product", "zoom"):
                    url_img = img.get("url", "")
                    imagen = (_PRODUCT_BASE + url_img) if url_img.startswith("/") else url_img
                    break
            if not imagen and images:
                url_img = images[0].get("url", "")
                imagen = (_PRODUCT_BASE + url_img) if url_img.startswith("/") else url_img

        url_raw = raw.get("url") or ""
        url_producto = (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None

        # Precio por kg/L (Hybris a veces lo incluye como pricePerUnit)
        precio_kilo = None
        ppu = raw.get("pricePerUnit") or {}
        if isinstance(ppu, dict) and ppu.get("value"):
            try:
                precio_kilo = float(ppu["value"])
            except (ValueError, TypeError):
                pass

        return {
            "nombre": nombre,
            "precio": float(precio),
            "ean": ean,
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

    scraper = DiaScraper()
    queries = ["leche entera 1L", "pan de molde", "aceite de oliva"]
    results = scraper.run(queries)
    print(f"\n{'─'*60}")
    for r in results:
        print(f"  {r.nombre_buscado!r:25} → {r.nombre!r:40} {r.precio:.2f} €")
