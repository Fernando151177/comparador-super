"""Cash Family ES scraper — HTML con BeautifulSoup.

Cash Family es una cadena de supermercados del grupo Miquel Alimentació.
No expone una API JSON pública conocida.

Estrategia:
1. Buscar en https://www.cashfamily.es/busqueda?q={term}
2. Parsear HTML con BeautifulSoup para extraer nombre y precio.

Si el sitio requiere JavaScript para renderizar los productos,
devuelve [] sin excepción.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_SEARCH_URL = "https://www.cashfamily.es/busqueda"
_PRODUCT_BASE = "https://www.cashfamily.es"

# Alternativa si el dominio principal no funciona
_SEARCH_URL_ALT = "https://www.cash-family.es/search"


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


class CashFamilyScraper(BaseScraper):
    """Scraper para cashfamily.es."""

    NOMBRE = "Cash Family"
    CODIGO = "CASH_FAMILY_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.25

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "text/html,application/json,*/*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": "https://www.cashfamily.es/",
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
        for url in (_SEARCH_URL, _SEARCH_URL_ALT):
            resp = self.get(url, params={"q": query})
            if resp is None:
                continue

            # Intentar JSON primero
            try:
                data = resp.json()
                products = self._parse_json(data)
                if products:
                    return products
            except Exception:
                pass

            # HTML fallback
            products = self._parse_html(resp.text, url)
            if products:
                return products

        print(f"[{self.NOMBRE}] No se pudo obtener datos para: {query!r}")
        return []

    def _parse_json(self, data) -> list[dict]:
        if not isinstance(data, dict):
            return []
        items = data.get("products") or data.get("items") or data.get("results") or []
        products = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            nombre = (raw.get("name") or raw.get("title") or "").strip()
            if not nombre:
                continue
            precio = None
            for k in ("price", "salePrice", "pvp"):
                v = raw.get(k)
                if isinstance(v, (int, float)) and float(v) > 0:
                    precio = float(v)
                    break
            if not precio:
                continue
            products.append({
                "nombre": nombre,
                "precio": precio,
                "ean": raw.get("ean") or None,
                "url_imagen": raw.get("image") or None,
                "url_producto": raw.get("url") or None,
            })
        return products

    def _parse_html(self, html: str, base_url: str) -> list[dict]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"[{self.NOMBRE}] beautifulsoup4 no está instalado. Ejecuta: pip install beautifulsoup4")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products = []

        for card in soup.select(".product-item, .product-miniature, .product, [data-product-id]"):
            nombre_tag = card.select_one(".product-title, .product-name, h2, h3, .name")
            precio_tag = card.select_one(".price, .product-price, .precio")

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
            imagen = img_tag.get("src") or img_tag.get("data-src") if img_tag else None

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
            print(f"[{self.NOMBRE}] No se encontraron productos en el HTML.")
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
