"""Repositorio para la tabla 'precios_historicos'."""
from datetime import date
from typing import Optional

from database.connection import get_connection
from domain.models import PrecioHistorico, ScrapedProduct


class PreciosRepo:
    """Todo el acceso a base de datos para la tabla precios_historicos."""

    # ── Escritura ─────────────────────────────────────────────────────────────

    def upsert_today(
        self,
        producto_id: int,
        supermercado_id: int,
        sp: ScrapedProduct,
    ) -> None:
        """Inserta el precio de hoy o lo actualiza si ya existe la fila."""
        hoy = str(date.today())
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO precios_historicos
                    (producto_id, supermercado_id, precio, moneda,
                     precio_por_unidad_normalizado, unidad_normalizacion,
                     fecha_scraping, disponible)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (producto_id, supermercado_id, fecha_scraping)
                DO UPDATE SET
                    precio                        = EXCLUDED.precio,
                    precio_por_unidad_normalizado = EXCLUDED.precio_por_unidad_normalizado,
                    disponible                    = EXCLUDED.disponible
                """,
                (
                    producto_id,
                    supermercado_id,
                    sp.precio,
                    sp.moneda,
                    sp.precio_kilo,
                    sp.unidad_normalizacion,
                    hoy,
                    sp.disponible,          # bool directamente (PostgreSQL lo acepta)
                ),
            )

    # ── Lectura ───────────────────────────────────────────────────────────────

    def get_today(
        self,
        producto_id: Optional[int] = None,
        supermercado_id: Optional[int] = None,
    ) -> list[dict]:
        """Devuelve los precios de hoy, con filtros opcionales.

        Cada dict incluye nombre del producto y del supermercado junto al precio.
        """
        hoy = str(date.today())
        params: list = [hoy]
        filters = ["ph.fecha_scraping = %s"]

        if producto_id is not None:
            filters.append("ph.producto_id = %s")
            params.append(producto_id)
        if supermercado_id is not None:
            filters.append("ph.supermercado_id = %s")
            params.append(supermercado_id)

        where = " AND ".join(filters)
        with get_connection() as conn:
            cur = conn.execute(
                f"""
                SELECT
                    ph.id, ph.producto_id, ph.supermercado_id,
                    ph.precio, ph.moneda,
                    ph.precio_por_unidad_normalizado, ph.unidad_normalizacion,
                    ph.fecha_scraping, ph.disponible,
                    p.nombre  AS producto_nombre,
                    p.ean,
                    p.categoria,
                    p.url_imagen,
                    s.nombre  AS supermercado_nombre,
                    s.codigo  AS supermercado_codigo,
                    s.pais
                FROM precios_historicos ph
                JOIN productos     p ON p.id = ph.producto_id
                JOIN supermercados s ON s.id = ph.supermercado_id
                WHERE {where}
                ORDER BY p.nombre, ph.precio
                """,
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_history(
        self,
        producto_id: int,
        supermercado_id: Optional[int] = None,
        days: int = 30,
    ) -> list[dict]:
        """Devuelve hasta `days` días de historial de precios para un producto."""
        params: list = [producto_id]
        extra = ""
        if supermercado_id is not None:
            extra = "AND ph.supermercado_id = %s"
            params.append(supermercado_id)
        params.append(days * (1 if supermercado_id else 15))  # máx 15 supermercados

        with get_connection() as conn:
            cur = conn.execute(
                f"""
                SELECT ph.fecha_scraping, ph.precio,
                       s.nombre AS supermercado_nombre, s.codigo
                FROM precios_historicos ph
                JOIN supermercados s ON s.id = ph.supermercado_id
                WHERE ph.producto_id = %s {extra}
                ORDER BY ph.fecha_scraping DESC
                LIMIT %s
                """,
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def get_median_price(
        self, producto_id: int, supermercado_id: int, days: int = 30
    ) -> Optional[float]:
        """Devuelve el precio mediano de un producto en un supermercado en los últimos N días."""
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT precio FROM precios_historicos
                WHERE producto_id = %s AND supermercado_id = %s
                ORDER BY fecha_scraping DESC
                LIMIT %s
                """,
                (producto_id, supermercado_id, days),
            )
            rows = cur.fetchall()

        if not rows:
            return None
        prices = sorted(float(r["precio"]) for r in rows)
        mid = len(prices) // 2
        return prices[mid]

    def get_prices_for_products(
        self, producto_ids: list[int], pais: Optional[str] = None
    ) -> list[dict]:
        """Devuelve los precios de hoy para una lista de productos.

        Usado por el optimizador para cargar precios en lote.
        """
        if not producto_ids:
            return []

        hoy = str(date.today())
        params: list = [producto_ids, hoy]  # ANY(%s) recibe la lista directamente
        pais_filter = ""
        if pais and pais != "AMBOS":
            pais_filter = "AND s.pais = %s"
            params.append(pais)

        with get_connection() as conn:
            cur = conn.execute(
                f"""
                SELECT
                    ph.producto_id, ph.supermercado_id,
                    ph.precio, ph.precio_por_unidad_normalizado,
                    ph.unidad_normalizacion,
                    p.nombre  AS producto_nombre,
                    p.url_imagen,
                    s.nombre  AS supermercado_nombre,
                    s.codigo  AS supermercado_codigo,
                    s.pais,
                    s.url_online
                FROM precios_historicos ph
                JOIN productos     p ON p.id = ph.producto_id
                JOIN supermercados s ON s.id = ph.supermercado_id
                WHERE ph.producto_id = ANY(%s)
                  AND ph.fecha_scraping = %s
                  {pais_filter}
                  AND ph.disponible = TRUE
                ORDER BY ph.producto_id, ph.precio
                """,
                params,
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
