"""Ahorramas ES scraper — HTML con BeautifulSoup.

Ahorramas no expone una API JSON pública.  El scraper intenta dos
estrategias en orden:

1. Endpoint JSON interno (si Ahorramas lo activa):
   GET https://www.ahorramas.com/search/?q={term}&format=json

2. Parseo HTML básico con BeautifulSoup buscando los selectores
   de producto habituales en su tienda online.

Si ninguna estrategia funciona, devuelve [] sin excepción.

Nota: Ahorramas opera principalmente en Madrid y centro de España.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.ahorramas.com/search/"
_PRODUCT_BASE = "https://www.ahorramas.com"


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


class AhorramasScraper(BaseScraper):
    """Scraper para ahorramas.com."""

    NOMBRE = "Ahorramas"
    CODIGO = "AHORRAMAS_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": "https://www.ahorramas.com/",
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

    # ── Search strategies ─────────────────────────────────────────────────────

    def _search(self, query: str) -> list[dict]:
        # Estrategia 1: JSON
        resp = self.get(_SEARCH_URL, params={"q": query, "format": "json"})
        if resp is not None:
            try:
                data = resp.json()
                products = self._parse_json(data)
                if products:
                    return products
            except Exception:
                pass

        # Estrategia 2: HTML
        resp = self.get(_SEARCH_URL, params={"q": query})
        if resp is None:
            return []
        return self._parse_html(resp.text)

    def _parse_json(self, data) -> list[dict]:
        if not isinstance(data, dict):
            return []
        items = data.get("products") or data.get("items") or data.get("results") or []
        products = []
        for raw in items:
            p = self._parse_item(raw)
            if p:
                products.append(p)
        return products

    def _parse_item(self, raw: dict) -> Optional[dict]:
        nombre = (raw.get("name") or raw.get("title") or "").strip()
        if not nombre:
            return None
        precio = None
        for key in ("price", "salePrice", "current_price"):
            val = raw.get(key)
            if isinstance(val, (int, float)) and float(val) > 0:
                precio = float(val)
                break
            if isinstance(val, dict):
                v = val.get("value") or val.get("amount")
                if isinstance(v, (int, float)) and float(v) > 0:
                    precio = float(v)
                    break
        if not precio:
            return None
        return {
            "nombre": nombre,
            "precio": precio,
            "ean": raw.get("ean") or None,
            "url_imagen": raw.get("image") or raw.get("thumbnail") or None,
            "url_producto": raw.get("url") or None,
        }

    def _parse_html(self, html: str) -> list[dict]:
        """Parseo HTML con BeautifulSoup si está disponible."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"[{self.NOMBRE}] beautifulsoup4 no está instalado. Ejecuta: pip install beautifulsoup4")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []

        # Selectores comunes en tiendas Prestashop/Magento
        for card in soup.select(".product-miniature, .product-item, [data-id-product]"):
            nombre_tag = card.select_one(".product-title, .product-name, h2, h3")
            precio_tag = card.select_one(".price, .product-price, [data-price]")

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

            img_tag = card.select_one("img")
            imagen = img_tag["src"] if img_tag and img_tag.get("src") else None

            a_tag = card.select_one("a[href]")
            url_raw = a_tag["href"] if a_tag else ""
            url_producto = (_PRODUCT_BASE + url_raw) if url_raw.startswith("/") else url_raw or None

            products.append({
                "nombre": nombre,
                "precio": precio,
                "url_imagen": imagen,
                "url_producto": url_producto,
            })

        if not products:
            print(f"[{self.NOMBRE}] No se encontraron productos en el HTML. El sitio puede requerir JavaScript.")
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
