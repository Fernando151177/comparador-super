"""Cart builder — Sprint 3 module.

Generates deep-links or shareable shopping lists per supermarket.
No payment or credential data is stored or transmitted.
"""
from typing import Optional

from ordering.supermarket_links import build_search_url, get_info


def build_cart_links(
    supermercado_codigo: str,
    items: list[dict],
) -> list[dict]:
    """Generates a per-item search link for a supermarket.

    Args:
        supermercado_codigo: e.g. 'MERCADONA_ES'
        items: list of {'producto_nombre': str, 'cantidad': int}

    Returns:
        List of {'producto': str, 'cantidad': int, 'url': str | None}
    """
    links = []
    for item in items:
        url = build_search_url(supermercado_codigo, item["producto_nombre"])
        links.append({
            "producto": item["producto_nombre"],
            "cantidad": item["cantidad"],
            "url": url,
        })
    return links


def format_cart_text(
    supermercado_codigo: str,
    items: list[dict],
) -> str:
    """Returns a plain-text shopping list for copy-pasting or sharing.

    Args:
        supermercado_codigo: e.g. 'MERCADONA_ES'
        items: list of {'producto_nombre': str, 'cantidad': int, 'precio_total': float}
    """
    info = get_info(supermercado_codigo)
    nombre = info["nombre"] if info else supermercado_codigo
    lines = [f"🛒 Lista para {nombre}:", ""]
    total = 0.0
    for item in items:
        precio = item.get("precio_total", 0.0)
        total += precio
        lines.append(
            f"  • {item['cantidad']}× {item['producto_nombre']}"
            + (f"  — {precio:.2f} €" if precio else "")
        )
    lines.append("")
    lines.append(f"  Total estimado: {total:.2f} €")
    return "\n".join(lines)
