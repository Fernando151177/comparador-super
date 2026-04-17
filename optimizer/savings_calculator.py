"""Savings calculator — calcula el ahorro histórico del usuario.

Usa la tabla sesiones_compra para agregar totales por período.
"""
from datetime import date, timedelta
from typing import Optional

from database.connection import get_connection


def get_savings_summary(usuario_id: str) -> dict:
    """Devuelve los totales de ahorro en distintas ventanas temporales.

    Returns:
        Dict con claves: diario, semanal, mensual, anual (floats, EUR).
    """
    hoy = date.today()
    return {
        "diario":  _total_saved(usuario_id, hoy, hoy),
        "semanal": _total_saved(usuario_id, hoy - timedelta(days=7), hoy),
        "mensual": _total_saved(usuario_id, hoy - timedelta(days=30), hoy),
        "anual":   _total_saved(usuario_id, hoy - timedelta(days=365), hoy),
    }


def get_weekly_trend(usuario_id: str, weeks: int = 12) -> list[dict]:
    """Devuelve gasto y ahorro semanal de las últimas N semanas.

    Returns:
        Lista de dicts: [{'semana': 'YYYY-IW', 'gastado': float, 'ahorrado': float}]
    """
    desde = str(date.today() - timedelta(days=weeks * 7))
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT TO_CHAR(fecha::date, 'IYYY-IW') AS semana,
                   SUM(total_gastado)               AS gastado,
                   SUM(total_ahorrado)              AS ahorrado
            FROM sesiones_compra
            WHERE usuario_id = %s
              AND fecha >= %s
            GROUP BY semana
            ORDER BY semana
            """,
            (usuario_id, desde),
        ).fetchall()
    return [dict(r) for r in rows]


def get_annual_projection(usuario_id: str) -> Optional[float]:
    """Proyecta el ahorro anual basándose en los últimos 30 días."""
    mensual = _total_saved(
        usuario_id,
        date.today() - timedelta(days=30),
        date.today(),
    )
    return round(mensual * 12, 2) if mensual else None


# ── Internal ──────────────────────────────────────────────────────────────────

def _total_saved(usuario_id: str, desde: date, hasta: date) -> float:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT COALESCE(SUM(total_ahorrado), 0) AS total
            FROM sesiones_compra
            WHERE usuario_id = %s AND fecha BETWEEN %s AND %s
            """,
            (usuario_id, str(desde), str(hasta)),
        ).fetchone()
    return round(float(row["total"]), 2) if row else 0.0
