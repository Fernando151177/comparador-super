"""Saturday shopping optimizer.

Core algorithm
──────────────
1. Load the user's shopping list (items in lista_usuario).
2. For each item, resolve it to a DB product_id (via EAN or fuzzy text match
   across today's prices).
3. Fetch today's prices for all resolved product_ids.
4. Assign each product to the cheapest supermarket available today.
5. Group assignments by supermarket and compute savings.

The optimizer is intentionally decoupled from Streamlit: it returns a
plain ``OptimizerResult`` dataclass that the UI layer can render however
it likes.
"""
from datetime import date
from typing import Optional

from database.repositories.precios_repo import PreciosRepo
from database.connection import get_connection
from domain.models import ItemLista, OptimizerItem, OptimizerResult


def optimize_for_user(usuario_id: str, pais: Optional[str] = None) -> OptimizerResult:
    """Builds the optimal shopping plan for a user.

    Args:
        usuario_id: The authenticated user's id.
        pais:       'ES' | 'PT' | 'AMBOS' — filters supermarkets.
                    Defaults to the user's pais_activo setting.

    Returns:
        An OptimizerResult with the full plan and savings breakdown.
    """
    pais = pais or _get_user_pais(usuario_id)
    lista = _load_lista(usuario_id)

    if not lista:
        return _empty_result()

    # Resolve lista items to product_ids using today's prices
    product_ids, unmatched = _resolve_products(lista, pais)

    if not product_ids:
        return OptimizerResult(
            plan=[],
            por_supermercado={},
            total_optimo=0.0,
            total_si_uno={},
            ahorro_total=0.0,
            productos_sin_precio=[item.query_texto for item in lista],
            fecha=str(date.today()),
        )

    precios_repo = PreciosRepo()
    prices = precios_repo.get_prices_for_products(list(product_ids.keys()), pais)

    # Group prices by product_id
    by_product: dict[int, list[dict]] = {}
    for p in prices:
        by_product.setdefault(p["producto_id"], []).append(p)

    plan: list[OptimizerItem] = []
    sin_precio: list[str] = list(unmatched)

    for producto_id, opciones in by_product.items():
        query_texto, cantidad = product_ids[producto_id]
        if not opciones:
            sin_precio.append(query_texto)
            continue

        # Cheapest option today
        cheapest = min(opciones, key=lambda o: o["precio"])
        precio_max = max(o["precio"] for o in opciones)

        plan.append(
            OptimizerItem(
                query_texto=query_texto,
                cantidad=cantidad,
                producto_nombre=cheapest["producto_nombre"],
                supermercado_nombre=cheapest["supermercado_nombre"],
                supermercado_codigo=cheapest["supermercado_codigo"],
                precio_unitario=round(cheapest["precio"], 2),
                precio_total=round(cheapest["precio"] * cantidad, 2),
                precio_kilo=cheapest.get("precio_por_unidad_normalizado"),
                url_producto=None,  # extended in Sprint 2
                ahorro_vs_caro=round((precio_max - cheapest["precio"]) * cantidad, 2),
            )
        )

    # Group plan by supermarket
    por_supermercado: dict[str, list[OptimizerItem]] = {}
    total_optimo = 0.0
    for item in plan:
        por_supermercado.setdefault(item.supermercado_codigo, []).append(item)
        total_optimo += item.precio_total

    # What would it cost to buy everything at a single supermarket?
    total_si_uno = _cost_per_single_supermarket(by_product, product_ids, pais)

    # Savings vs. cheapest single-supermarket option
    cheapest_single = min(total_si_uno.values()) if total_si_uno else total_optimo
    ahorro_total = round(cheapest_single - total_optimo, 2)

    return OptimizerResult(
        plan=plan,
        por_supermercado=por_supermercado,
        total_optimo=round(total_optimo, 2),
        total_si_uno=total_si_uno,
        ahorro_total=max(ahorro_total, 0.0),
        productos_sin_precio=sin_precio,
        fecha=str(date.today()),
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_lista(usuario_id: str) -> list[ItemLista]:
    """Loads the user's active (not yet bought) shopping list items."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT id, usuario_id, producto_id, ean, query_texto,
                   cantidad, prioridad, comprado
            FROM lista_usuario
            WHERE usuario_id = ? AND comprado = 0
            ORDER BY prioridad DESC, query_texto
            """,
            (usuario_id,),
        ).fetchall()
    return [
        ItemLista(
            id=r["id"],
            usuario_id=r["usuario_id"],
            producto_id=r["producto_id"],
            ean=r["ean"],
            query_texto=r["query_texto"],
            cantidad=r["cantidad"],
            prioridad=r["prioridad"],
            comprado=bool(r["comprado"]),
        )
        for r in rows
    ]


def _resolve_products(
    lista: list[ItemLista], pais: str
) -> tuple[dict[int, tuple[str, int]], list[str]]:
    """Maps lista items to product_ids.

    Returns:
        matched:   {product_id: (query_texto, cantidad)}
        unmatched: list of query_texto strings with no price today
    """
    matched: dict[int, tuple[str, int]] = {}
    unmatched: list[str] = []
    today = str(date.today())

    with get_connection() as conn:
        for item in lista:
            pid: Optional[int] = item.producto_id

            # If already linked, verify it has a price today
            if pid is not None:
                has_price = conn.execute(
                    "SELECT 1 FROM precios_historicos WHERE producto_id = ? AND fecha_scraping = ?",
                    (pid, today),
                ).fetchone()
                if has_price:
                    matched[pid] = (item.query_texto, item.cantidad)
                    continue

            # Fuzzy match against products with prices today
            pid = _fuzzy_find_product(conn, item.query_texto, pais, today)
            if pid:
                matched[pid] = (item.query_texto, item.cantidad)
            else:
                unmatched.append(item.query_texto)

    return matched, unmatched


def _fuzzy_find_product(conn, query: str, pais: str, today: str) -> Optional[int]:
    """Finds the best-matching product_id with a price today."""
    from difflib import SequenceMatcher
    import unicodedata

    def norm(t: str) -> str:
        return (
            unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower()
        )

    pais_filter = "" if pais == "AMBOS" else "AND s.pais = ?"
    params: list = [today]
    if pais != "AMBOS":
        params.append(pais)

    rows = conn.execute(
        f"""
        SELECT DISTINCT p.id, p.nombre
        FROM productos p
        JOIN precios_historicos ph ON ph.producto_id = p.id
        JOIN supermercados s ON s.id = ph.supermercado_id
        WHERE ph.fecha_scraping = ? {pais_filter}
        """,
        params,
    ).fetchall()

    best_id: Optional[int] = None
    best_score = 0.0
    q_norm = norm(query)

    for row in rows:
        score = SequenceMatcher(None, q_norm, norm(row["nombre"])).ratio()
        if score > best_score:
            best_score = score
            best_id = row["id"]

    return best_id if best_score >= 0.45 else None


def _cost_per_single_supermarket(
    by_product: dict[int, list[dict]],
    product_ids: dict[int, tuple[str, int]],
    pais: str,
) -> dict[str, float]:
    """Computes the total basket cost if buying everything at each supermarket."""
    # Collect all supermarket codes that appear in today's prices
    all_supermarkets: dict[str, str] = {}
    for opciones in by_product.values():
        for o in opciones:
            all_supermarkets[o["supermercado_codigo"]] = o["supermercado_nombre"]

    totals: dict[str, float] = {}
    for codigo, nombre in all_supermarkets.items():
        total = 0.0
        all_covered = True
        for producto_id, (_, cantidad) in product_ids.items():
            opciones = by_product.get(producto_id, [])
            precio = next(
                (o["precio"] for o in opciones if o["supermercado_codigo"] == codigo),
                None,
            )
            if precio is None:
                all_covered = False
                break
            total += precio * cantidad
        if all_covered:
            totals[codigo] = round(total, 2)

    return totals


def _get_user_pais(usuario_id: str) -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT pais_activo FROM usuarios WHERE id = %s", (usuario_id,)
        ).fetchone()
    return row["pais_activo"] if row else "ES"


def _empty_result() -> OptimizerResult:
    return OptimizerResult(
        plan=[],
        por_supermercado={},
        total_optimo=0.0,
        total_si_uno={},
        ahorro_total=0.0,
        productos_sin_precio=[],
        fecha=str(date.today()),
    )
