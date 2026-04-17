"""Repositorio para la tabla 'alertas'."""
from datetime import date
from typing import Optional

from database.connection import get_connection
from domain.models import Alerta


class AlertasRepo:
    """Todo el acceso a base de datos para la tabla alertas."""

    # ── Escritura ─────────────────────────────────────────────────────────────

    def create(
        self,
        usuario_id: str,                # UUID
        tipo_alerta: str = "BAJADA_PRECIO",
        *,
        producto_id: Optional[int] = None,
        ean: Optional[str] = None,
        umbral_precio: Optional[float] = None,
    ) -> int:
        """Crea una nueva alerta y devuelve su id."""
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO alertas
                    (usuario_id, producto_id, ean, tipo_alerta, umbral_precio)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (usuario_id, producto_id, ean, tipo_alerta, umbral_precio),
            )
            return cur.fetchone()["id"]

    def mark_activated(self, alerta_id: int) -> None:
        """Actualiza la marca de tiempo de última activación."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE alertas SET ultima_activacion = now() WHERE id = %s",
                (alerta_id,),
            )

    def deactivate(self, alerta_id: int) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE alertas SET activa = FALSE WHERE id = %s",
                (alerta_id,),
            )

    def delete(self, alerta_id: int, usuario_id: str) -> None:
        """Elimina una alerta, comprobando que pertenece al usuario indicado."""
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM alertas WHERE id = %s AND usuario_id = %s",
                (alerta_id, usuario_id),
            )

    # ── Lectura ───────────────────────────────────────────────────────────────

    def get_active_for_user(self, usuario_id: str) -> list[dict]:
        """Devuelve las alertas activas con contexto de producto."""
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT a.*,
                       p.nombre  AS producto_nombre,
                       p.ean     AS producto_ean
                FROM alertas a
                LEFT JOIN productos p ON p.id = a.producto_id
                WHERE a.usuario_id = %s AND a.activa = TRUE
                ORDER BY a.created_at DESC
                """,
                (usuario_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    def detect_price_drops(self, usuario_id: str) -> list[dict]:
        """Detecta bajadas de precio para las alertas activas de un usuario.

        Compara el precio de hoy con la mediana de los últimos 30 días.
        Devuelve las filas donde la bajada supera el umbral configurado.
        """
        hoy = str(date.today())
        with get_connection() as conn:
            cur = conn.execute(
                """
                SELECT
                    a.id        AS alerta_id,
                    a.producto_id,
                    a.umbral_precio,
                    p.nombre    AS producto_nombre,
                    ph.precio   AS precio_hoy,
                    ph.supermercado_id,
                    s.nombre    AS supermercado_nombre
                FROM alertas a
                JOIN lista_usuario lu ON lu.producto_id = a.producto_id
                                      AND lu.usuario_id = a.usuario_id
                JOIN precios_historicos ph ON ph.producto_id = a.producto_id
                                          AND ph.fecha_scraping = %s
                JOIN productos     p ON p.id = a.producto_id
                JOIN supermercados s ON s.id = ph.supermercado_id
                WHERE a.usuario_id = %s
                  AND a.activa = TRUE
                  AND a.tipo_alerta = 'BAJADA_PRECIO'
                """,
                (hoy, usuario_id),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_model(row: dict) -> Alerta:
        return Alerta(
            id=row["id"],
            usuario_id=str(row["usuario_id"]),
            producto_id=row["producto_id"],
            ean=row["ean"],
            tipo_alerta=row["tipo_alerta"],
            umbral_precio=float(row["umbral_precio"]) if row["umbral_precio"] else None,
            activa=bool(row["activa"]),
            ultima_activacion=str(row["ultima_activacion"]) if row["ultima_activacion"] else None,
        )
