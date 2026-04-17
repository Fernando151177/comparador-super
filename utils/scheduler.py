"""Scheduler diario de scraping y detección de alertas.

Uso:
    python -m utils.scheduler           # ejecuta scrapers ahora mismo
    python -m utils.scheduler --daemon  # espera SCRAPING_HOUR y repite cada 24 h
"""
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.config import SCRAPING_HOUR


# ── Carga de queries desde la base de datos ───────────────────────────────────

def _load_all_queries() -> list[str]:
    """Devuelve la lista única de query_texto de todos los usuarios activos."""
    from database.connection import get_connection
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT query_texto
            FROM lista_usuario
            WHERE comprado = FALSE
            ORDER BY query_texto
            """
        ).fetchall()
    queries = [r["query_texto"] for r in rows]
    print(f"[Scheduler] {len(queries)} búsquedas cargadas de la base de datos.")
    return queries


# ── Detección de alertas por bajada de precio ─────────────────────────────────

def _detect_and_save_alerts() -> int:
    """Detecta bajadas de precio y crea alertas para los usuarios afectados.

    Compara el precio de hoy con la mediana de los últimos 30 días.
    Solo genera alerta si la bajada supera PRICE_DROP_THRESHOLD y el ahorro
    absoluto supera MIN_SAVINGS_ALERT.

    Devuelve el número de alertas nuevas generadas.
    """
    from datetime import date
    from database.connection import get_connection
    from database.repositories.alertas_repo import AlertasRepo
    from utils.config import PRICE_DROP_THRESHOLD, MIN_SAVINGS_ALERT

    hoy = str(date.today())
    repo = AlertasRepo()
    nuevas = 0

    with get_connection() as conn:
        # Productos de la lista de cada usuario con precio hoy
        rows = conn.execute(
            """
            SELECT DISTINCT lu.usuario_id, lu.producto_id, lu.cantidad,
                            ph.precio AS precio_hoy,
                            ph.supermercado_id,
                            p.nombre  AS producto_nombre
            FROM lista_usuario lu
            JOIN precios_historicos ph ON ph.producto_id = lu.producto_id
                                     AND ph.fecha_scraping = %s
            JOIN productos p ON p.id = lu.producto_id
            WHERE lu.comprado = FALSE
              AND lu.producto_id IS NOT NULL
            """,
            (hoy,),
        ).fetchall()

    for row in rows:
        # Mediana de los últimos 30 días (excluyendo hoy)
        with get_connection() as conn:
            hist = conn.execute(
                """
                SELECT precio FROM precios_historicos
                WHERE producto_id = %s
                  AND supermercado_id = %s
                  AND fecha_scraping < %s
                ORDER BY fecha_scraping DESC
                LIMIT 30
                """,
                (row["producto_id"], row["supermercado_id"], hoy),
            ).fetchall()

        if len(hist) < 3:
            continue  # sin suficiente historial

        precios = sorted(float(r["precio"]) for r in hist)
        mediana = precios[len(precios) // 2]
        precio_hoy = float(row["precio_hoy"])

        if mediana == 0:
            continue

        descuento = (mediana - precio_hoy) / mediana

        if descuento < PRICE_DROP_THRESHOLD:
            continue

        ahorro_abs = (mediana - precio_hoy) * int(row["cantidad"])
        if ahorro_abs < MIN_SAVINGS_ALERT:
            continue

        # Comprobar que no existe ya una alerta activa para este par usuario/producto
        with get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM alertas
                WHERE usuario_id = %s AND producto_id = %s
                  AND tipo_alerta = 'BAJADA_PRECIO' AND activa = TRUE
                """,
                (str(row["usuario_id"]), row["producto_id"]),
            ).fetchone()

        if existing:
            repo.mark_activated(existing["id"])
        else:
            repo.create(
                usuario_id=str(row["usuario_id"]),
                tipo_alerta="BAJADA_PRECIO",
                producto_id=row["producto_id"],
                umbral_precio=precio_hoy,
            )
            nuevas += 1

    return nuevas


# ── Orquestación principal ────────────────────────────────────────────────────

def run_all_scrapers() -> None:
    """Ejecuta todos los scrapers activos, guarda precios y genera alertas."""
    from database.init_db import init_db
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo
    from scrapers import ALL_SCRAPERS

    init_db()

    queries = _load_all_queries()

    productos_repo = ProductosRepo()
    precios_repo = PreciosRepo()

    start = datetime.now()
    print(f"\n{'='*55}")
    print(f"  Scraping iniciado: {start:%Y-%m-%d %H:%M:%S}")
    print(f"  Queries: {len(queries)}")
    print(f"{'='*55}\n")

    total_precios = 0
    for cls in ALL_SCRAPERS:
        scraper = cls()
        try:
            # Mercadona descarga catálogo completo; el resto usa queries
            if queries:
                results = scraper.run(queries)
            else:
                results = scraper.run()

            for sp in results:
                pid = productos_repo.upsert_from_scraped(sp, scraper.supermarket_id)
                if pid:
                    precios_repo.upsert_today(pid, scraper.supermarket_id, sp)
                    total_precios += 1
        except Exception as exc:
            print(f"[{scraper.NOMBRE}] Error inesperado: {exc}")

    # ── Detección de alertas ──────────────────────────────────────────────────
    print("\n[Scheduler] Detectando bajadas de precio…")
    try:
        n_alertas = _detect_and_save_alerts()
        print(f"[Scheduler] {n_alertas} alertas nuevas generadas.")
    except Exception as exc:
        print(f"[Scheduler] Error en detección de alertas: {exc}")

    elapsed = (datetime.now() - start).seconds
    print(f"\n{'='*55}")
    print(f"  Precios guardados : {total_precios}")
    print(f"  Duración          : {elapsed}s")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    import schedule

    if "--daemon" in sys.argv:
        print(f"Modo daemon — scraping programado a las {SCRAPING_HOUR} cada día.")
        schedule.every().day.at(SCRAPING_HOUR).do(run_all_scrapers)
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        run_all_scrapers()
