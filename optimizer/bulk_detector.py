"""Detector de oportunidades de acopio para no perecederos.

Sugiere acumular stock cuando el precio actual de un no perecedero está
≥15% por debajo de su mediana de los últimos 30 días.

Un producto se considera no perecedero si su categoría o nombre contiene
alguna de las palabras clave definidas en _NON_PERISHABLE_KEYWORDS.
Usa fuzzy matching contra query_texto porque producto_id suele ser NULL.
"""
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from typing import Optional

from database.connection import get_connection
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


def _norm(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _is_non_perishable(categoria: Optional[str], nombre: str) -> bool:
    palabras = set(_norm((categoria or "") + " " + nombre).split())
    return bool(palabras & _NON_PERISHABLE_KEYWORDS)


def _best_match(query: str, prices: list[dict]) -> Optional[dict]:
    qn = _norm(query)
    qw = set(qn.split())
    best_score, best = 0.0, None
    for p in prices:
        nn = _norm(p["producto_nombre"])
        sim = SequenceMatcher(None, qn, nn).ratio()
        ov = len(qw & set(nn.split()))
        total = sim + (ov / max(len(qw), 1)) * 0.30
        if total > best_score:
            best_score, best = total, p
    return best if best_score >= 0.40 else None


def detect_bulk_opportunities(usuario_id: str) -> list[dict]:
    """Detecta no perecederos con descuento significativo en la lista del usuario.

    Usa fuzzy matching entre query_texto y productos con precio hoy.

    Returns:
        Lista de dicts con:
            producto_nombre, supermercado_nombre, precio_hoy,
            precio_habitual, descuento_pct, unidades_sugeridas,
            ahorro_potencial.
    """
    hoy = str(date.today())

    # Items de la lista del usuario
    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchall()

    if not items:
        return []

    # Precios de hoy con info de producto
    with get_connection() as conn:
        prices = conn.execute(
            """
            SELECT ph.producto_id, ph.supermercado_id,
                   ph.precio AS precio,
                   p.nombre  AS producto_nombre,
                   p.categoria AS categoria,
                   s.nombre  AS supermercado_nombre
            FROM precios_historicos ph
            JOIN productos     p ON p.id = ph.producto_id
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE ph.fecha_scraping = %s
            """,
            (hoy,),
        ).fetchall()

    if not prices:
        return []

    opportunities: list[dict] = []

    for item in items:
        query = item["query_texto"]

        # Solo no perecederos
        if not _is_non_perishable(None, query):
            continue

        match = _best_match(query, [dict(p) for p in prices])
        if match is None:
            continue

        # Comprobar también la categoría del producto encontrado
        if not _is_non_perishable(match.get("categoria"), match["producto_nombre"]):
            continue

        # Mediana histórica (últimos 30 días, excluyendo hoy)
        with get_connection() as conn:
            hist = conn.execute(
                """
                SELECT precio FROM precios_historicos
                WHERE producto_id = %s AND supermercado_id = %s
                  AND fecha_scraping < %s
                ORDER BY fecha_scraping DESC LIMIT 30
                """,
                (match["producto_id"], match["supermercado_id"], hoy),
            ).fetchall()

        if len(hist) < 3:
            continue

        precios_hist = sorted(float(r["precio"]) for r in hist)
        mediana = precios_hist[len(precios_hist) // 2]
        precio_hoy = float(match["precio"])

        if mediana == 0:
            continue

        descuento = (mediana - precio_hoy) / mediana
        if descuento < BULK_DISCOUNT_THRESHOLD:
            continue

        unidades = min(max(int(descuento / 0.10), 2), MAX_BULK_UNITS)
        ahorro = round((mediana - precio_hoy) * unidades, 2)

        opportunities.append({
            "producto_nombre":     match["producto_nombre"],
            "supermercado_nombre": match["supermercado_nombre"],
            "precio_hoy":          precio_hoy,
            "precio_habitual":     round(mediana, 2),
            "descuento_pct":       round(descuento * 100, 1),
            "unidades_sugeridas":  unidades,
            "ahorro_potencial":    ahorro,
        })

    return sorted(opportunities, key=lambda x: x["descuento_pct"], reverse=True)
