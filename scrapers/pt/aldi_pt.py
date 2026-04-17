"""Aldi PT scraper — API de búsqueda de aldi.pt.

Aldi Portugal usa una arquitectura similar a Aldi ES.
Endpoint a intentar:
    GET https://www.aldi.pt/api/search?q={term}&pageSize=10
    GET https://www.aldi.pt/search/?q={term}  (HTML fallback)

Si ningún endpoint funciona, devuelve [] sin excepción.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URLS = [
    "https://www.aldi.pt/api/search",
    "https://www.aldi.pt/api/products/search",
]
_HTML_URL = "https://www.aldi.pt/pesquisa.html"
_PRODUCT_BASE = "https://www.aldi.pt"


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


class AldiPTScraper(BaseScraper):
    """Scraper para aldi.pt."""

    NOMBRE = "Aldi PT"
    CODIGO = "ALDI_PT"
    PAIS = "PT"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json, text/html, */*",
            "Accept-Language": "pt-PT,pt;q=0.9",
            "Origin": "https://www.aldi.pt",
            "Referer": "https://www.aldi.pt/",
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

    # ── Search ────────────────────────────────────────────────────────────────

    def _search(self, query: str) -> list[dict]:
        for url in _SEARCH_URLS:
            for params in ({"q": query, "pageSize": 10}, {"query": query, "size": 10}):
                resp = self.get(url, params=params)
                if resp is None:
                    continue
                try:
                    data = resp.json()
                    products = self._parse_json(data)
                    if products:
                        return products
                except Exception:
                    pass

        # HTML fallback
        resp = self.get(_HTML_URL, params={"q": query})
        if resp is None:
            return []
        return self._parse_html(resp.text)

    def _parse_json(self, data) -> list[dict]:
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("products") or data.get("items") or data.get("results") or []
        else:
            return []
        products = []
        for raw in items:
            p = self._parse_item(raw)
            if p:
                products.append(p)
        return products

    def _parse_item(self, raw: dict) -> Optional[dict]:
        if not isinstance(raw, dict):
            return None
        nombre = (raw.get("name") or raw.get("title") or "").strip()
        if not nombre:
            return None
        precio = None
        for k in ("price", "salePrice", "pvp"):
            v = raw.get(k)
            if isinstance(v, (int, float)) and float(v) > 0:
                precio = float(v)
                break
            if isinstance(v, dict):
                for sub in ("value", "amount"):
                    if isinstance(v.get(sub), (int, float)):
                        precio = float(v[sub])
                        break
            if precio:
                break
        if not precio:
            return None
        return {
            "nombre": nombre,
            "precio": precio,
            "ean": raw.get("ean") or None,
            "url_imagen": raw.get("image") or raw.get("imageUrl") or None,
            "url_producto": raw.get("url") or None,
        }

    def _parse_html(self, html: str) -> list[dict]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"[{self.NOMBRE}] beautifulsoup4 no instalado.")
            return []
        soup = BeautifulSoup(html, "html.parser")
        products = []
        for card in soup.select(".product-tile, .product-item, [data-product-id]"):
            nombre_tag = card.select_one(".product-tile__header, .product-name, h3")
            precio_tag = card.select_one(".product-tile__price, .price")
            if not nombre_tag or not precio_tag:
                continue
            nombre = nombre_tag.get_text(strip=True)
            precio_txt = precio_tag.get_text(strip=True).replace("€", "").replace(",", ".").strip()
            try:
                precio = float("".join(c for c in precio_txt if c.isdigit() or c == "."))
            except ValueError:
                continue
            if precio <= 0:
                continue
            a_tag = card.select_one("a[href]")
            url_raw = a_tag["href"] if a_tag else ""
            products.append({
                "nombre": nombre,
                "precio": precio,
                "url_producto": (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None,
            })
        if not products:
            print(f"[{self.NOMBRE}] Sin productos en HTML.")
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
