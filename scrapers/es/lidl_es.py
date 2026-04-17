"""Lidl ES scraper — usa la API de búsqueda de lidl.es.

Endpoint confirmado:
    GET https://www.lidl.es/q/api/search
        ?assortment=ES&locale=es_ES&version=v2.0.0&q={term}&pageSize=20

Respuesta relevante por item:
    item.gridbox.data.fullTitle      → nombre del producto
    item.gridbox.data.price.price    → precio en EUR
    item.gridbox.data.price.packaging.text  → unidad de medida
    item.gridbox.data.ians[0]        → EAN (cuando existe)
    item.gridbox.data.image          → URL imagen
    item.gridbox.data.canonicalUrl   → ruta relativa del producto
    item.gridbox.data.keyfacts[].value donde keyfact contiene "Food"/"Alimentaci"
        → usado para filtrar productos de alimentación

Estrategia:
    Una petición de búsqueda por query.  Devuelve el mejor resultado por
    similitud de nombre, igual que MercadonaESScraper.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

from domain.models import ScrapedProduct
from scrapers.base import BaseScraper

_BASE_URL = "https://www.lidl.es/q/api/search"
_PRODUCT_BASE = "https://www.lidl.es"


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


class LidlESScraper(BaseScraper):
    """Scraper para lidl.es mediante su API de búsqueda."""

    NOMBRE = "Lidl"
    CODIGO = "LIDL_ES"
    PAIS = "ES"

    _MIN_SCORE: float = 0.45   # total (sim + bonus)
    _MIN_SIM: float = 0.50     # similitud base sin bonus

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "es-ES,es;q=0.9",
            "Origin": "https://www.lidl.es",
            "Referer": "https://www.lidl.es/",
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
        """Llama a la API de Lidl y devuelve una lista de productos parseados."""
        resp = self.get(
            _BASE_URL,
            params={
                "assortment": "ES",
                "locale": "es_ES",
                "version": "v2.0.0",
                "q": query,
                "pageSize": 20,
            },
        )
        if resp is None:
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        products = []
        for item in data.get("items", []):
            parsed = self._parse_item(item)
            if parsed:
                products.append(parsed)
        return products

    def _parse_item(self, item: dict) -> Optional[dict]:
        """Extrae un dict normalizado de un item de la respuesta de Lidl."""
        try:
            d = item["gridbox"]["data"]
        except (KeyError, TypeError):
            return None

        nombre = d.get("fullTitle", "").strip()
        if not nombre:
            return None

        # Precio
        try:
            precio = float(d["price"]["price"])
        except (KeyError, TypeError, ValueError):
            return None

        if precio <= 0:
            return None

        # EAN (primer elemento de 'ians' si existe)
        eans = d.get("ians") or []
        ean = str(eans[0]) if eans else None

        # Unidad de medida
        try:
            unidad = d["price"]["packaging"]["text"]
        except (KeyError, TypeError):
            unidad = None

        # Precio por kg/L
        precio_kilo: Optional[float] = None
        try:
            base_price = d["price"]["basePrice"]["value"]
            if base_price:
                precio_kilo = float(base_price)
        except (KeyError, TypeError, ValueError):
            pass

        # URL imagen
        imagen = d.get("image") or None

        # URL producto
        canonical = d.get("canonicalUrl") or ""
        url_producto = (_PRODUCT_BASE + canonical) if canonical.startswith("/") else canonical or None

        # Categoría (para posible filtrado futuro)
        categoria = None
        try:
            for kf in d.get("keyfacts", []):
                if isinstance(kf, dict) and kf.get("value"):
                    categoria = kf["value"]
                    break
        except Exception:
            pass

        return {
            "nombre": nombre,
            "precio": precio,
            "ean": ean,
            "unidad_medida": unidad,
            "precio_kilo": precio_kilo,
            "url_imagen": imagen,
            "url_producto": url_producto,
            "categoria": categoria,
        }

    # ── Matching ──────────────────────────────────────────────────────────────

    @staticmethod
    def _word_overlap(query_words: set[str], product_words: set[str]) -> int:
        """Cuenta cuántas palabras clave de la query aparecen en el producto.

        Usa coincidencia de prefijo para cubrir plurales del español:
        'pimiento' coincide con 'pimientos', 'verde' con 'verdes', etc.
        Solo se consideran palabras de 4+ caracteres para evitar ruido.
        """
        count = 0
        for qw in query_words:
            if len(qw) < 4:
                continue
            for pw in product_words:
                # prefijo: 'pimiento' en 'pimientos', o 'verdes' empieza por 'verde'
                if pw.startswith(qw) or qw.startswith(pw):
                    count += 1
                    break
        return count

    def _best_match(self, query: str, candidates: list[dict]) -> Optional[dict]:
        if not candidates:
            return None

        query_words = set(_normalize(query).split())
        # Palabras clave: >= 4 chars, excluye artículos/preposiciones
        key_words = {w for w in query_words if len(w) >= 4}

        # Palabra principal de la query: la primera con >= 4 chars (normalmente el sustantivo)
        main_words = [w for w in _normalize(query).split() if len(w) >= 4]
        main_word = main_words[0] if main_words else None

        best_score = 0.0
        best: Optional[dict] = None

        for p in candidates:
            nombre = p.get("nombre", "")
            product_words = set(_normalize(nombre).split())

            # Requiere que al menos 1 palabra clave de la query aparezca (con plurales)
            overlap = self._word_overlap(key_words, product_words)
            if overlap == 0:
                continue

            # Si la query tiene varias palabras clave, la palabra principal debe estar presente
            if main_word and len(key_words) >= 2:
                main_present = any(
                    pw.startswith(main_word) or main_word.startswith(pw)
                    for pw in product_words if len(pw) >= 4
                )
                if not main_present:
                    continue

            score = _similarity(query, nombre)
            # Rechazar si la similitud base es demasiado baja (evita falsos positivos)
            if score < self._MIN_SIM:
                continue
            bonus = (overlap / max(len(key_words), 1)) * 0.30
            total = score + bonus
            if total > best_score:
                best_score = total
                best = p

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
            precio_kilo=p.get("precio_kilo"),
            unidad_normalizacion="kg" if p.get("precio_kilo") else None,
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

    scraper = LidlESScraper()
    queries = ["leche entera 1L", "pan de molde", "aceite de oliva", "huevos L"]
    results = scraper.run(queries)

    print(f"\n{'─'*60}")
    for r in results:
        pkilo = f"  ({r.precio_kilo:.2f} €/kg)" if r.precio_kilo else ""
        print(f"  {r.nombre_buscado!r:25} → {r.nombre!r:40} {r.precio:.2f} €{pkilo}")
