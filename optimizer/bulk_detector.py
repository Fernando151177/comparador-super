"""Detector de oportunidades de acopio para no perecederos.

Sugiere acumular stock cuando el precio actual de un no perecedero está
≥15% por debajo de su mediana de los últimos 30 días.

Un producto se considera no perecedero si su categoría contiene alguna
de las palabras clave definidas en _NON_PERISHABLE_KEYWORDS.  No se
requiere la tabla productos_no_perecederos (que puede estar vacía).
"""
from datetime import date
from typing import Optional

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from utils.config import BULK_DISCOUNT_THRESHOLD, MAX_BULK_UNITS

# Palabras clave en la categoría que indican que el producto no es perecedero
_NON_PERISHABLE_KEYWORDS = {
    # Alimentación seca / conservas
    "conserva", "conservas", "enlatado", "enlatados",
    "lata", "latas", "bote", "botes", "tarro", "tarros",
    "arroz", "pasta", "pastas", "legumbre", "legumbres",
    "garbanzo", "garbanzos", "lenteja", "lentejas",
    "alubia", "alubias", "harina", "harinas",
    "azucar", "aceite", "aceites", "vinagre",
    "sal", "especias", "especia",
    "cafe", "infusion", "infusiones",
    "galleta", "galletas", "cereal", "cereales", "chocolate",
    "caldo", "caldos", "sopa", "sopas",
    # Higiene y limpieza
    "limpieza", "detergente", "detergentes",
    "jabon", "jabones", "papel",
    "suavizante", "lavavajillas", "fregasuelos",
    # Bebidas no perecederas
    "agua", "refresco", "refrescos",
    "zumo", "zumos", "nectar",
    "cerveza", "cervezas", "vino", "vinos",
}


def _is_non_perishable(categoria: Optional[str], nombre: str) -> bool:
    """Devuelve True si el producto parece no perecedero por su categoría o nombre."""
    import unicodedata

    def norm(t: str) -> str:
        return (
            unicodedata.normalize("NFD", t)
            .encode("ascii", "ignore")
            .decode()
            .lower()
        )

    palabras = set(norm((categoria or "") + " " + nombre).split())
    return bool(palabras & _NON_PERISHABLE_KEYWORDS)


def detect_bulk_opportunities(usuario_id: str) -> list[dict]:
    """Detecta no perecederos con descuento significativo en la lista del usuario.

    Returns:
        Lista de dicts con:
            producto_nombre, supermercado_nombre, precio_hoy,
            precio_habitual, descuento_pct, unidades_sugeridas,
            ahorro_potencial.
    """
    hoy = str(date.today())
    precios_repo = PreciosRepo()

    # Productos de la lista del usuario con precio hoy
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT lu.producto_id, lu.cantidad,
                   p.nombre    AS producto_nombre,
                   p.categoria AS categoria
            FROM lista_usuario lu
            JOIN productos p ON p.id = lu.producto_id
            WHERE lu.usuario_id = %s
              AND lu.comprado = FALSE
              AND lu.producto_id IS NOT NULL
            """,
            (usuario_id,),
        ).fetchall()

    opportunities: list[dict] = []

    for row in rows:
        # Filtrar solo no perecederos
        if not _is_non_perishable(row.get("categoria"), row["producto_nombre"]):
            continue

        pid = row["producto_id"]
        today_prices = precios_repo.get_prices_for_products([pid])

        for price_row in today_prices:
            mediana = precios_repo.get_median_price(pid, price_row["supermercado_id"])
            if mediana is None or mediana == 0:
                continue

            precio_hoy = float(price_row["precio"])
            descuento = (mediana - precio_hoy) / mediana

            if descuento < BULK_DISCOUNT_THRESHOLD:
                continue

            unidades = min(max(int(descuento / 0.10), 2), MAX_BULK_UNITS)
            ahorro = round((mediana - precio_hoy) * unidades, 2)

            opportunities.append({
                "producto_nombre":    row["producto_nombre"],
                "supermercado_nombre": price_row["supermercado_nombre"],
                "precio_hoy":         precio_hoy,
                "precio_habitual":    round(mediana, 2),
                "descuento_pct":      round(descuento * 100, 1),
                "unidades_sugeridas": unidades,
                "ahorro_potencial":   ahorro,
            })

    return sorted(opportunities, key=lambda x: x["descuento_pct"], reverse=True)
