"""Modelo PT scraper — misma plataforma que Continente (Sonae).

Modelo y Continente pertenecen al grupo Sonae y comparten
la misma plataforma de e-commerce.  Este scraper reutiliza
ContinenteScraper apuntando al dominio modelo.pt.

Si modelo.pt no tiene tienda online activa, la búsqueda
se redirige al catálogo de continente.pt.
"""
from scrapers.pt.continente import ContinenteScraper

_SEARCH_URLS_MODELO = [
    "https://www.modelo.pt/api/2.0/catalog/",
    "https://www.modelo.pt/on/demandware.store/Sites-Modelo-Site/pt_PT/Search-Show",
]
_PRODUCT_BASE_MODELO = "https://www.modelo.pt"


class ModeloScraper(ContinenteScraper):
    """Scraper para modelo.pt — subclase de ContinenteScraper."""

    NOMBRE = "Modelo"
    CODIGO = "MODELO_PT"
    PAIS = "PT"

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update({
            "Origin": "https://www.modelo.pt",
            "Referer": "https://www.modelo.pt/",
        })

    def _search(self, query: str) -> list[dict]:
        import unicodedata
        from scrapers.base import BaseScraper

        params_list = [
            {"text": query, "pageSize": 10, "currentPage": 0, "prefill": "false"},
            {"q": query, "format": "ajax", "start": 0, "sz": 10},
        ]
        for url, params in zip(_SEARCH_URLS_MODELO, params_list):
            resp = self.get(url, params=params)
            if resp is None:
                continue
            try:
                data = resp.json()
                products = self._parse_response(data)
                if products:
                    # Corregir URLs al dominio de Modelo
                    for p in products:
                        url_p = p.get("url_producto", "") or ""
                        if "continente.pt" in url_p:
                            p["url_producto"] = url_p.replace(
                                "https://www.continente.pt", _PRODUCT_BASE_MODELO
                            )
                    return products
            except Exception:
                continue

        # Fallback: usar Continente como fuente de datos
        print(f"[{self.NOMBRE}] modelo.pt sin API activa — usando datos de Continente.")
        return super()._search(query)
