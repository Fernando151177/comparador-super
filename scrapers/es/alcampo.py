"""Alcampo ES scraper — Salesforce Commerce Cloud.

Alcampo usa Salesforce Commerce Cloud (SFCC).  El endpoint de búsqueda
devuelve JSON cuando se añade el parámetro format=page-designer o
se envían cabeceras Accept: application/json.

Endpoint principal:
    GET https://www.alcampo.es/api/2.0/page-designer
        ?aspectRatio=1:1&viewType=desktop
    (catálogo completo, paginado)

Endpoint de búsqueda (más práctico):
    GET https://www.alcampo.es/on/demandware.store/Sites-Alcampo-Site/es_ES/Search-Show
        ?q={term}&format=ajax&start=0&sz=10

Nota: Si la respuesta sigue siendo HTML, significa que Alcampo requiere
cookies de sesión o JavaScript.  En ese caso la búsqueda devuelve []
sin lanzar excepción.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.alcampo.es/on/demandware.store/Sites-Alcampo-Site/es_ES/Search-Show"
_PRODUCT_BASE = "https://www.alcampo.es"


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


class AlcampoScraper(BaseScraper):
    """Scraper para alcampo.es (Salesforce Commerce Cloud)."""

    NOMBRE = "Alcampo"
    CODIGO = "ALCAMPO_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Origin": "https://www.alcampo.es",
            "Referer": "https://www.alcampo.es/",
            "X-Requested-With": "XMLHttpRequest",
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
            params={"q": query, "format": "ajax", "start": 0, "sz": 10},
        )
        if resp is None:
            return []

        # SFCC devuelve JSON cuando se pide format=ajax
        try:
            data = resp.json()
            return self._parse_sfcc(data)
        except Exception:
            pass

        # Si responde HTML, intentar extraer datos con regex como fallback
        return self._parse_html(resp.text, query)

    def _parse_sfcc(self, data: dict) -> list[dict]:
        products = []
        # Formato SFCC estándar
        hits = (
            data.get("hits")
            or data.get("products")
            or data.get("productSearchResult", {}).get("hits", [])
        )
        for raw in hits:
            p = self._parse_hit(raw)
            if p:
                products.append(p)
        return products

    def _parse_hit(self, raw: dict) -> Optional[dict]:
        nombre = (raw.get("productName") or raw.get("name") or "").strip()
        if not nombre:
            return None

        precio = None
        price_info = raw.get("price") or raw.get("pricing") or {}
        if isinstance(price_info, dict):
            for k in ("sales", "list", "current", "value"):
                v = price_info.get(k)
                if isinstance(v, dict):
                    precio = v.get("value") or v.get("decimalPrice")
                elif isinstance(v, (int, float)):
                    precio = float(v)
                if precio:
                    break
        elif isinstance(price_info, (int, float)):
            precio = float(price_info)

        if not precio or float(precio) <= 0:
            return None

        ean = raw.get("ean") or raw.get("barcode") or None
        imagen = None
        imgs = raw.get("images") or {}
        if isinstance(imgs, dict):
            small = imgs.get("small") or imgs.get("medium") or []
            if small and isinstance(small, list):
                imagen = small[0].get("url")
        elif isinstance(imgs, list) and imgs:
            imagen = imgs[0].get("url") or imgs[0].get("link")

        url_raw = raw.get("url") or raw.get("productUrl") or ""
        url_producto = (
            (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None
        )

        return {
            "nombre": nombre,
            "precio": float(precio),
            "ean": ean,
            "url_imagen": imagen,
            "url_producto": url_producto,
        }

    def _parse_html(self, html: str, query: str) -> list[dict]:
        """Extracción básica de precio/nombre desde HTML como último recurso."""
        products = []
        # Buscar bloques JSON embebidos en el HTML (común en SFCC)
        matches = re.findall(r'data-product="(\{[^"]+\})"', html)
        for m in matches:
            try:
                import json
                raw = json.loads(m.replace("&quot;", '"'))
                p = self._parse_hit(raw)
                if p:
                    products.append(p)
            except Exception:
                continue
        if not products:
            print(f"[{self.NOMBRE}] HTML response — cannot parse. Site may require JavaScript/cookies.")
        return products

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
            url_imagen=p.get("url_imagen"),
            url_producto=p.get("url_producto"),
            disponible=True,
            nombre_buscado=query,
        )
