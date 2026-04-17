"""Supermarket online-order URLs and cart-building metadata.

No payment or credential data is ever stored here.
Links open the supermarket's own website; the user completes the purchase
on their platform.

Each entry in SUPERMARKET_INFO contains:
    online_url      Base URL for online shopping.
    search_url      URL template for searching a product (use {query}).
    min_order_eur   Minimum order for home delivery (None if unknown).
    delivery_eur    Typical delivery cost (None if unknown / free).
    click_collect   Whether click-and-collect is available.
    notes           Short note shown in the UI.
"""
from typing import Optional

SUPERMARKET_INFO: dict[str, dict] = {
    # ── España ────────────────────────────────────────────────────────────────
    "MERCADONA_ES": {
        "nombre": "Mercadona",
        "pais": "ES",
        "online_url": "https://tienda.mercadona.es",
        "search_url": "https://tienda.mercadona.es/search-results?query={query}",
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Entrega a domicilio disponible en muchas ciudades.",
    },
    "LIDL_ES": {
        "nombre": "Lidl",
        "pais": "ES",
        "online_url": "https://www.lidl.es/p/compras-online",
        "search_url": "https://www.lidl.es/q/search?q={query}",
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Tienda online con productos no-alimentarios principalmente.",
    },
    "ALCAMPO_ES": {
        "nombre": "Alcampo",
        "pais": "ES",
        "online_url": "https://www.alcampo.es/compra-online",
        "search_url": "https://www.alcampo.es/compra-online/#/search?q={query}",
        "min_order_eur": 50.0,
        "delivery_eur": 5.90,
        "click_collect": True,
        "notes": "Click & Collect disponible en hipermercados.",
    },
    "AHORRAMAS_ES": {
        "nombre": "Ahorramas",
        "pais": "ES",
        "online_url": None,
        "search_url": None,
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Sin tienda online — compra presencial.",
    },
    "HIPERCOR_ES": {
        "nombre": "Hipercor",
        "pais": "ES",
        "online_url": "https://www.hipercor.es/supermercado",
        "search_url": "https://www.hipercor.es/supermercado/search/?s={query}",
        "min_order_eur": 30.0,
        "delivery_eur": 4.95,
        "click_collect": True,
        "notes": "Integrado con El Corte Inglés.",
    },
    "CARREFOUR_ES": {
        "nombre": "Carrefour",
        "pais": "ES",
        "online_url": "https://www.carrefour.es/supermercado",
        "search_url": "https://www.carrefour.es/supermercado/buscar?query={query}",
        "min_order_eur": None,
        "delivery_eur": 4.90,
        "click_collect": True,
        "notes": "Drive disponible en hipermercados seleccionados.",
    },
    "DIA_ES": {
        "nombre": "Día",
        "pais": "ES",
        "online_url": "https://www.dia.es/tienda-online",
        "search_url": "https://www.dia.es/tienda-online/buscar?q={query}",
        "min_order_eur": 15.0,
        "delivery_eur": 2.90,
        "click_collect": False,
        "notes": "Entrega express disponible en zonas urbanas.",
    },
    "CASH_FAMILY_ES": {
        "nombre": "Cash Family",
        "pais": "ES",
        "online_url": None,
        "search_url": None,
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Sin tienda online — compra presencial.",
    },
    # ── Portugal ──────────────────────────────────────────────────────────────
    "CONTINENTE_PT": {
        "nombre": "Continente",
        "pais": "PT",
        "online_url": "https://www.continente.pt",
        "search_url": "https://www.continente.pt/pesquisa/?q={query}",
        "min_order_eur": 35.0,
        "delivery_eur": 4.99,
        "click_collect": True,
        "notes": "Una de las tiendas online más completas de Portugal.",
    },
    "PINGO_DOCE_PT": {
        "nombre": "Pingo Doce",
        "pais": "PT",
        "online_url": "https://www.pingodoce.pt/compras-online",
        "search_url": "https://www.pingodoce.pt/pesquisa/?q={query}",
        "min_order_eur": 40.0,
        "delivery_eur": 5.49,
        "click_collect": True,
        "notes": "Disponible en Lisboa, Porto y otras ciudades.",
    },
    "MODELO_PT": {
        "nombre": "Modelo",
        "pais": "PT",
        "online_url": None,
        "search_url": None,
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Tienda física — usa Continente online para pedidos.",
    },
    "LIDL_PT": {
        "nombre": "Lidl PT",
        "pais": "PT",
        "online_url": "https://www.lidl.pt/p/compras-online",
        "search_url": "https://www.lidl.pt/q/search?q={query}",
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Principalmente artículos no-alimentarios online.",
    },
    "MERCADONA_PT": {
        "nombre": "Mercadona PT",
        "pais": "PT",
        "online_url": "https://www.mercadona.pt",
        "search_url": "https://www.mercadona.pt/search-results?query={query}",
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Disponible en zonas del norte y centro de Portugal.",
    },
    "INTERMARCHE_PT": {
        "nombre": "Intermarché PT",
        "pais": "PT",
        "online_url": None,
        "search_url": None,
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Sin tienda online activa — compra presencial.",
    },
    "ALDI_PT": {
        "nombre": "Aldi PT",
        "pais": "PT",
        "online_url": None,
        "search_url": None,
        "min_order_eur": None,
        "delivery_eur": None,
        "click_collect": False,
        "notes": "Sin tienda online — compra presencial.",
    },
}


def get_info(codigo: str) -> Optional[dict]:
    """Returns metadata for a supermarket by its código, or None."""
    return SUPERMARKET_INFO.get(codigo)


def build_search_url(codigo: str, query: str) -> Optional[str]:
    """Returns a direct search URL for the given product query, or None."""
    info = get_info(codigo)
    if not info or not info.get("search_url"):
        return info.get("online_url") if info else None
    return info["search_url"].format(query=query.replace(" ", "+"))


def get_by_pais(pais: str) -> list[dict]:
    """Returns all supermarket entries for a given country ('ES' or 'PT')."""
    return [
        {"codigo": k, **v}
        for k, v in SUPERMARKET_INFO.items()
        if pais == "AMBOS" or v["pais"] == pais
    ]
