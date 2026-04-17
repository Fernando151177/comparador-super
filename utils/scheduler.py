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

    Usa fuzzy matching entre query_texto y productos con precio hoy,
    ya que lista_usuario.producto_id suele ser NULL.

    Compara el precio de hoy con la mediana de los últimos 30 días.
    Solo genera alerta si la bajada supera PRICE_DROP_THRESHOLD y el ahorro
    absoluto supera MIN_SAVINGS_ALERT.

    Devuelve el número de alertas nuevas generadas.
    """
    import unicodedata
    from datetime import date
    from difflib import SequenceMatcher
    from database.connection import get_connection
    from database.repositories.alertas_repo import AlertasRepo
    from utils.config import PRICE_DROP_THRESHOLD, MIN_SAVINGS_ALERT

    def norm(t: str) -> str:
        return (
            unicodedata.normalize("NFD", t)
            .encode("ascii", "ignore")
            .decode()
            .lower()
            .strip()
        )

    hoy = str(date.today())
    repo = AlertasRepo()
    nuevas = 0

    # Todos los items activos de todos los usuarios
    with get_connection() as conn:
        items = conn.execute(
            "SELECT usuario_id, query_texto, cantidad FROM lista_usuario "
            "WHERE comprado = FALSE"
        ).fetchall()

    if not items:
        return 0

    # Precios de hoy con metadata de producto
    with get_connection() as conn:
        prices = conn.execute(
            """
            SELECT ph.producto_id, ph.supermercado_id,
                   ph.precio AS precio_hoy,
                   p.nombre  AS producto_nombre
            FROM precios_historicos ph
            JOIN productos p ON p.id = ph.producto_id
            WHERE ph.fecha_scraping = %s
            """,
            (hoy,),
        ).fetchall()

    if not prices:
        return 0

    prices_list = [dict(p) for p in prices]

    # Cache de medianas para evitar consultas repetidas
    mediana_cache: dict[tuple, float | None] = {}

    for item in items:
        usuario_id = str(item["usuario_id"])
        query = item["query_texto"]
        cantidad = int(item["cantidad"])
        qn = norm(query)
        qw = set(qn.split())

        # Mejor coincidencia fuzzy
        best, best_score = None, 0.0
        for p in prices_list:
            nn = norm(p["producto_nombre"])
            sim = SequenceMatcher(None, qn, nn).ratio()
            ov = len(qw & set(nn.split()))
            total = sim + (ov / max(len(qw), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p

        if best is None or best_score < 0.40:
            continue

        key = (best["producto_id"], best["supermercado_id"])

        # Mediana histórica (con cache)
        if key not in mediana_cache:
            with get_connection() as conn:
                hist = conn.execute(
                    """
                    SELECT precio FROM precios_historicos
                    WHERE producto_id = %s AND supermercado_id = %s
                      AND fecha_scraping < %s
                    ORDER BY fecha_scraping DESC LIMIT 30
                    """,
                    (best["producto_id"], best["supermercado_id"], hoy),
                ).fetchall()
            if len(hist) < 3:
                mediana_cache[key] = None
            else:
                ps = sorted(float(r["precio"]) for r in hist)
                mediana_cache[key] = ps[len(ps) // 2]

        mediana = mediana_cache[key]
        if mediana is None or mediana == 0:
            continue

        precio_hoy = float(best["precio_hoy"])
        descuento = (mediana - precio_hoy) / mediana

        if descuento < PRICE_DROP_THRESHOLD:
            continue

        ahorro_abs = (mediana - precio_hoy) * cantidad
        if ahorro_abs < MIN_SAVINGS_ALERT:
            continue

        # Comprobar alerta existente (por usuario + query_texto)
        with get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM alertas
                WHERE usuario_id = %s AND tipo_alerta = 'BAJADA_PRECIO'
                  AND activa = TRUE
                  AND (producto_id = %s OR ean IS NULL)
                LIMIT 1
                """,
                (usuario_id, best["producto_id"]),
            ).fetchone()

        if existing:
            repo.mark_activated(existing["id"])
        else:
            repo.create(
                usuario_id=usuario_id,
                tipo_alerta="BAJADA_PRECIO",
                producto_id=best["producto_id"],
                umbral_precio=precio_hoy,
            )
            nuevas += 1

    return nuevas


# ── Notificaciones email ──────────────────────────────────────────────────────

def _send_price_drop_emails() -> int:
    """Envía emails de bajada de precio a usuarios con notificaciones activas.

    Por cada usuario con notificaciones activadas, busca bajadas de precio
    en su lista y envía un email si hay al menos una.
    Devuelve el número de emails enviados.
    """
    import unicodedata
    from datetime import date
    from difflib import SequenceMatcher
    from database.connection import get_connection
    from database.repositories.usuarios_repo import UsuariosRepo
    from utils.config import PRICE_DROP_THRESHOLD
    from utils.email_sender import build_price_drop_email, send_email

    hoy = str(date.today())
    repo = UsuariosRepo()
    usuarios = repo.get_usuarios_con_notificaciones()

    if not usuarios:
        return 0

    # Precios de hoy (cargamos una vez, filtramos por usuario)
    with get_connection() as conn:
        prices = conn.execute(
            """
            SELECT ph.producto_id, ph.supermercado_id,
                   ph.precio AS precio_hoy,
                   p.nombre  AS producto_nombre,
                   s.nombre  AS supermercado_nombre
            FROM precios_historicos ph
            JOIN productos     p ON p.id = ph.producto_id
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE ph.fecha_scraping = %s
            """,
            (hoy,),
        ).fetchall()

    prices_list = [dict(p) for p in prices]
    if not prices_list:
        return 0

    def norm(t: str) -> str:
        return (
            unicodedata.normalize("NFD", t)
            .encode("ascii", "ignore")
            .decode()
            .lower()
            .strip()
        )

    mediana_cache: dict[tuple, float | None] = {}
    enviados = 0

    for u in usuarios:
        usuario_id = str(u["id"])

        with get_connection() as conn:
            items = conn.execute(
                "SELECT query_texto, cantidad FROM lista_usuario "
                "WHERE usuario_id = %s AND comprado = FALSE",
                (usuario_id,),
            ).fetchall()

        if not items:
            continue

        drops = []
        for item in items:
            qn = norm(item["query_texto"])
            qw = set(qn.split())
            best, best_score = None, 0.0
            for p in prices_list:
                nn = norm(p["producto_nombre"])
                sim = SequenceMatcher(None, qn, nn).ratio()
                ov = len(qw & set(nn.split()))
                total = sim + (ov / max(len(qw), 1)) * 0.30
                if total > best_score:
                    best_score, best = total, p
            if best is None or best_score < 0.40:
                continue

            key = (best["producto_id"], best["supermercado_id"])
            if key not in mediana_cache:
                with get_connection() as conn:
                    hist = conn.execute(
                        """SELECT precio FROM precios_historicos
                           WHERE producto_id = %s AND supermercado_id = %s
                             AND fecha_scraping < %s
                           ORDER BY fecha_scraping DESC LIMIT 30""",
                        (best["producto_id"], best["supermercado_id"], hoy),
                    ).fetchall()
                if len(hist) < 3:
                    mediana_cache[key] = None
                else:
                    ps = sorted(float(r["precio"]) for r in hist)
                    mediana_cache[key] = ps[len(ps) // 2]

            mediana = mediana_cache[key]
            if mediana is None or mediana == 0:
                continue

            precio_hoy_val = float(best["precio_hoy"])
            descuento = (mediana - precio_hoy_val) / mediana
            if descuento >= PRICE_DROP_THRESHOLD:
                pct = round(descuento * 100, 1)
                ahorro_abs = round((mediana - precio_hoy_val) * int(item["cantidad"]), 2)
                drops.append({
                    "producto_nombre":     item["query_texto"],
                    "supermercado_nombre": best["supermercado_nombre"],
                    "precio_hoy":          precio_hoy_val,
                    "precio_habitual":     round(mediana, 2),
                    "pct_bajada":          pct,
                    "ahorro_abs":          ahorro_abs,
                })

        if not drops:
            continue

        html = build_price_drop_email(u["nombre"], drops)
        ok = send_email(
            to=u["email"],
            subject=f"📉 {len(drops)} bajada(s) de precio en tu lista — Smart Shopping",
            html=html,
        )
        if ok:
            enviados += 1

    return enviados


# ── Orquestación principal ────────────────────────────────────────────────────

def run_all_scrapers() -> None:
    """Ejecuta todos los scrapers activos, guarda precios y genera alertas."""
    from database.init_db import init_db
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo
    from scrapers import ALL_SCRAPERS_ES as ALL_SCRAPERS

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

    # ── Notificaciones por email ──────────────────────────────────────────────
    print("\n[Scheduler] Enviando notificaciones por email…")
    try:
        n_emails = _send_price_drop_emails()
        print(f"[Scheduler] {n_emails} email(s) enviados.")
    except Exception as exc:
        print(f"[Scheduler] Error en notificaciones: {exc}")

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
