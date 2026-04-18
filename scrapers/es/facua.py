"""FACUA scraper — super.facua.org

Federación de Usuarios-Consumidores Independientes publica diariamente
los precios de productos básicos verificados.  Datos públicos y legales,
sin riesgo de bloqueo por IP.

Categorías rastreadas: aceite de girasol, aceite de oliva, huevos, leche
Supermercados: Mercadona, Carrefour, Alcampo, Hipercor, Día, Eroski

Estrategia:
1. Mapear el query a la categoría FACUA más cercana por palabra clave.
2. GET HTML de https://super.facua.org/{slug}/{categoría}/ (servidor, sin JS).
3. BeautifulSoup: localizar "Precio hoy" → subir al contenedor → extraer nombre.
4. Fuzzy matching para devolver el mejor candidato.
"""
import re
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_BASE_URL = "https://super.facua.org"

# Palabras clave → slug de categoría FACUA (ordenadas de más a menos específicas)
_KEYWORD_TO_CAT: list[tuple[str, str]] = [
    ("aceite girasol", "aceite-de-girasol"),
    ("aceite de girasol", "aceite-de-girasol"),
    ("aceite oliva", "aceite-de-oliva"),
    ("aceite de oliva", "aceite-de-oliva"),
    ("girasol", "aceite-de-girasol"),
    ("aove", "aceite-de-oliva"),
    ("oliva", "aceite-de-oliva"),
    ("huevo", "huevos"),
    ("leche", "leche"),
    ("lactosa", "leche"),
    ("desnatada", "leche"),
    ("semidesnatada", "leche"),
    ("entera", "leche"),
]


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


class FACUABaseScraper(BaseScraper):
    """Base para scrapers FACUA.  Subclases deben definir _FACUA_SLUG."""

    _FACUA_SLUG: str = ""
    _MIN_SCORE: float = 0.30

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "text/html,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate",  # sin brotli — requests no lo decodifica
            "Accept-Language": "es-ES,es;q=0.9",
            "Referer": _BASE_URL + "/",
        })

    # ── Public API ────────────────────────────────────────────────────────────

    def scrape_products(self, queries: list[str]) -> list[ScrapedProduct]:
        results: list[ScrapedProduct] = []
        for query in queries:
            category = self._detect_category(query)
            if not category:
                print(f"[{self.NOMBRE}] Sin categoría FACUA para: {query!r}")
                continue
            candidates = self._fetch_category(category)
            best = self._best_match(query, candidates)
            if best:
                results.append(self._to_scraped(query, best))
            else:
                print(f"[{self.NOMBRE}] Not found: {query!r}")
        return results

    # ── Category detection ────────────────────────────────────────────────────

    def _detect_category(self, query: str) -> Optional[str]:
        q = _norm(query)
        for keyword, cat in _KEYWORD_TO_CAT:
            if keyword in q:
                return cat
        return None

    # ── Fetch & parse ─────────────────────────────────────────────────────────

    def _fetch_category(self, category: str) -> list[dict]:
        url = f"{_BASE_URL}/{self._FACUA_SLUG}/{category}/"
        resp = self.get(url)
        if resp is None:
            return []
        return self._parse_html(resp.text)

    def _parse_html(self, html: str) -> list[dict]:
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            print(f"[{self.NOMBRE}] beautifulsoup4 no instalado")
            return []

        soup = BeautifulSoup(html, "html.parser")
        products: list[dict] = []

        # Estructura FACUA: div.card > card-body > p.fw-bolder (nombre) + p (precio)
        #                            card-footer > a (link histórico)
        for card in soup.find_all("div", class_="card"):
            name_el = card.find("p", class_="fw-bolder")
            if not name_el:
                continue
            nombre = name_el.get_text(strip=True)
            if not nombre or len(nombre) < 4:
                continue

            # Precio: hermano <p> que contiene "Precio hoy:"
            precio_el = card.find("p", string=re.compile(r"Precio\s+hoy", re.I))
            if not precio_el:
                continue
            m = re.search(r"([\d]+[,\.][\d]{1,2})\s*€", precio_el.get_text())
            if not m:
                continue
            try:
                precio = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if precio <= 0:
                continue

            # Link al histórico (también es la URL del producto)
            a_tag = card.find("a", href=True)
            href = a_tag.get("href", "") if a_tag else ""
            url_prod = href if href.startswith("http") else (
                f"{_BASE_URL}{href}" if href else None
            )

            # Imagen
            img = card.find("img", class_="card-img-top")
            img_url = None
            if img:
                src = img.get("src") or img.get("data-src") or ""
                img_url = src if src.startswith("http") else (
                    f"{_BASE_URL}{src}" if src else None
                )

            products.append(
                {
                    "nombre": nombre,
                    "precio": precio,
                    "url_producto": url_prod,
                    "url_imagen": img_url,
                }
            )

        if products:
            return products

        # Fallback: localizar "Precio hoy" en cualquier <p> y subir al card contenedor
        for precio_el in soup.find_all("p", string=re.compile(r"Precio\s+hoy", re.I)):
            m = re.search(r"([\d]+[,\.][\d]{1,2})\s*€", precio_el.get_text())
            if not m:
                continue
            try:
                precio = float(m.group(1).replace(",", "."))
            except ValueError:
                continue
            if precio <= 0:
                continue
            container = precio_el.find_parent()
            for _ in range(6):
                if container is None:
                    break
                name_el = container.find(
                    ["p", "h2", "h3", "h4"],
                    class_=re.compile(r"fw-bold|product|name|title", re.I),
                )
                if name_el:
                    nombre = name_el.get_text(strip=True)
                    if nombre and len(nombre) > 4:
                        a_tag = container.find("a", href=True)
                        href = a_tag.get("href", "") if a_tag else ""
                        url_prod = href if href.startswith("http") else (
                            f"{_BASE_URL}{href}" if href else None
                        )
                        products.append(
                            {"nombre": nombre, "precio": precio, "url_producto": url_prod}
                        )
                        break
                container = container.parent

        return products

    # ── Matching ──────────────────────────────────────────────────────────────

    def _best_match(self, query: str, candidates: list[dict]) -> Optional[dict]:
        if not candidates:
            return None
        qn = _norm(query)
        qw = set(qn.split())
        best_score, best = 0.0, None
        for p in candidates:
            nn = _norm(p.get("nombre", ""))
            sim = _similarity(query, p.get("nombre", ""))
            overlap = len(qw & set(nn.split()))
            total = sim + (overlap / max(len(qw), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p
        return best if best_score >= self._MIN_SCORE else None

    @staticmethod
    def _to_scraped(query: str, p: dict) -> ScrapedProduct:
        return ScrapedProduct(
            nombre=p["nombre"],
            precio=p["precio"],
            moneda="EUR",
            url_imagen=p.get("url_imagen"),
            url_producto=p.get("url_producto"),
            disponible=True,
            nombre_buscado=query,
        )


# ── Subclases por supermercado ────────────────────────────────────────────────

class FACUAMercadonaScraper(FACUABaseScraper):
    NOMBRE = "Mercadona (FACUA)"
    CODIGO = "MERCADONA_ES"
    PAIS = "ES"
    _FACUA_SLUG = "mercadona"


class FACUACarrefourScraper(FACUABaseScraper):
    NOMBRE = "Carrefour (FACUA)"
    CODIGO = "CARREFOUR_ES"
    PAIS = "ES"
    _FACUA_SLUG = "carrefour"


class FACUAAlcampoScraper(FACUABaseScraper):
    NOMBRE = "Alcampo (FACUA)"
    CODIGO = "ALCAMPO_ES"
    PAIS = "ES"
    _FACUA_SLUG = "alcampo"


class FACUAHipercorScraper(FACUABaseScraper):
    NOMBRE = "Hipercor (FACUA)"
    CODIGO = "HIPERCOR_ES"
    PAIS = "ES"
    _FACUA_SLUG = "hipercor"


class FACUADiaScraper(FACUABaseScraper):
    NOMBRE = "Día (FACUA)"
    CODIGO = "DIA_ES"
    PAIS = "ES"
    _FACUA_SLUG = "dia"


class FACUAEroskiScraper(FACUABaseScraper):
    NOMBRE = "Eroski (FACUA)"
    CODIGO = "EROSKI_ES"
    PAIS = "ES"
    _FACUA_SLUG = "eroski"
