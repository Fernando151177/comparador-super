"""Fábrica de conexiones a Supabase PostgreSQL via psycopg2.

Exporta get_connection() que devuelve un objeto con la misma interfaz
que sqlite3.Connection, para que los repositorios cambien lo mínimo posible:

    with get_connection() as conn:
        cur = conn.execute("SELECT * FROM tabla WHERE id = %s", (id,))
        row = cur.fetchone()        # → dict  (como sqlite3.Row)
        rows = cur.fetchall()       # → list[dict]

Diferencias respecto a SQLite que debes recordar:
  - Los placeholders son %s en lugar de ?
  - Las funciones de fecha son now() y current_date (no datetime('now'))
  - Los BOOLEAN devuelven True/False de Python (no 0/1)
"""
import re

import psycopg2
import psycopg2.extras

from utils.config import DATABASE_URL

# Columnas booleanas conocidas — solo en ellas convertimos = 0/1 → FALSE/TRUE
_BOOL_COLS = {"comprado", "activo", "activa", "disponible", "peso_variable"}

# Patrón: nombre_columna = 0  o  nombre_columna = 1
_BOOL_RE = re.compile(
    r'\b(' + '|'.join(_BOOL_COLS) + r')\s*(=|!=)\s*([01])\b'
)


def _sqlite_to_pg(sql: str) -> str:
    """Convierte sintaxis SQLite → PostgreSQL de forma automática."""
    # 1. Placeholders
    sql = sql.replace("?", "%s")
    # 2. Booleanos: comprado = 0 → comprado = FALSE
    def _repl(m: re.Match) -> str:
        col, op, val = m.group(1), m.group(2), m.group(3)
        return f"{col} {op} {'TRUE' if val == '1' else 'FALSE'}"
    sql = _BOOL_RE.sub(_repl, sql)
    return sql


class _PgConn:
    """Adaptador delgado sobre psycopg2.Connection.

    Permite usar conn.execute(), conn.executemany() y conn.commit()
    igual que con sqlite3, sin tocar todos los repositorios.
    """

    def __init__(self, raw_conn: psycopg2.extensions.connection) -> None:
        self._conn = raw_conn
        # RealDictCursor: las filas se acceden como diccionarios → row["campo"]
        self._cur = raw_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ── Operaciones SQL ───────────────────────────────────────────────────────

    def execute(self, sql: str, params=None):
        """Ejecuta una sentencia SQL y devuelve el cursor (para fetchone/fetchall).

        Convierte automáticamente la sintaxis SQLite a PostgreSQL:
          - Placeholders:  ?       → %s
          - Booleanos:     = 0/1   → = FALSE/TRUE
          - Booleanos:     != 0/1  → != FALSE/TRUE
        """
        self._cur.execute(_sqlite_to_pg(sql), params or ())
        return self._cur

    def executemany(self, sql: str, params_list) -> None:
        """Ejecuta la misma sentencia SQL con múltiples conjuntos de parámetros."""
        psycopg2.extras.execute_batch(self._cur, sql.replace("?", "%s"), params_list)

    def commit(self) -> None:
        """Confirma la transacción actual."""
        self._conn.commit()

    def rollback(self) -> None:
        """Cancela la transacción actual."""
        self._conn.rollback()

    # ── Context manager (for … as conn:) ─────────────────────────────────────

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type:
            # Si hubo error → deshacer cambios
            self._conn.rollback()
        else:
            # Si todo fue bien → guardar cambios
            self._conn.commit()
        self._cur.close()
        self._conn.close()


def get_connection() -> _PgConn:
    """Abre y devuelve una conexión a Supabase PostgreSQL.

    Uso habitual:
        with get_connection() as conn:
            cur = conn.execute("SELECT ...", params)
            rows = cur.fetchall()
    """
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL no está configurada. "
            "Copia .env.example a .env y rellena tus credenciales de Supabase."
        )
    raw = psycopg2.connect(DATABASE_URL)
    return _PgConn(raw)
