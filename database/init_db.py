"""Inicialización de datos iniciales en Supabase.

El schema (tablas, índices) se crea UNA sola vez ejecutando
database/supabase_schema.sql en el SQL Editor de Supabase.

Esta función solo siembra los 15 supermercados si todavía no existen,
y se llama automáticamente al arrancar la app en app.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_connection

# ── Datos iniciales: 15 supermercados ─────────────────────────────────────────

_SUPERMERCADOS: list[tuple] = [
    # (nombre, codigo, pais, base_url, url_online)
    # España ──────────────────────────────────────────────────────────────────
    ("Mercadona",   "MERCADONA_ES",   "ES", "https://tienda.mercadona.es",              "https://tienda.mercadona.es"),
    ("Lidl",        "LIDL_ES",        "ES", "https://www.lidl.es",                      "https://www.lidl.es/p/compras-online"),
    ("Alcampo",     "ALCAMPO_ES",     "ES", "https://www.alcampo.es",                   "https://www.alcampo.es/compra-online"),
    ("Ahorramas",   "AHORRAMAS_ES",   "ES", "https://www.ahorramas.com",                None),
    ("Hipercor",    "HIPERCOR_ES",    "ES", "https://www.hipercor.es",                  "https://www.hipercor.es/supermercado"),
    ("Carrefour",   "CARREFOUR_ES",   "ES", "https://www.carrefour.es",                 "https://www.carrefour.es/supermercado"),
    ("Día",         "DIA_ES",         "ES", "https://www.dia.es",                       "https://www.dia.es/tienda-online"),
    ("Cash Family", "CASH_FAMILY_ES", "ES", "https://www.cashfamily.es",                None),
    ("Eroski",      "EROSKI_ES",      "ES", "https://www.eroski.es",                    "https://www.eroski.es/compra-online"),
    # Portugal ────────────────────────────────────────────────────────────────
    ("Continente",  "CONTINENTE_PT",  "PT", "https://www.continente.pt",                "https://www.continente.pt"),
    ("Pingo Doce",  "PINGO_DOCE_PT",  "PT", "https://www.pingodoce.pt",                 "https://www.pingodoce.pt/compras-online"),
    ("Modelo",      "MODELO_PT",      "PT", "https://www.continente.pt/lojas/modelo",   None),
    ("Lidl PT",     "LIDL_PT",        "PT", "https://www.lidl.pt",                      "https://www.lidl.pt/p/compras-online"),
    ("Mercadona PT","MERCADONA_PT",   "PT", "https://www.mercadona.pt",                 "https://www.mercadona.pt"),
    ("Intermarché", "INTERMARCHE_PT", "PT", "https://www.intermarche.pt",               None),
    ("Aldi PT",     "ALDI_PT",        "PT", "https://www.aldi.pt",                      None),
]


def init_db() -> None:
    """Siembra los 15 supermercados y aplica migraciones idempotentes al arrancar."""
    with get_connection() as conn:
        # Supermercados
        conn.executemany(
            """
            INSERT INTO supermercados (nombre, codigo, pais, base_url, url_online)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (codigo) DO NOTHING
            """,
            _SUPERMERCADOS,
        )
        # Migración: columnas de verificación de email (idempotente en Postgres)
        try:
            conn.execute(
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                "email_verificado BOOLEAN NOT NULL DEFAULT TRUE"
            )
            conn.execute(
                "ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS "
                "token_verificacion TEXT DEFAULT NULL"
            )
        except Exception:
            pass  # columnas ya existen
    print("[DB] Supermercados sincronizados y migraciones aplicadas.")


if __name__ == "__main__":
    init_db()
