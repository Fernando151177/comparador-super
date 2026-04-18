"""Scheduler diario de scraping y detección de alertas.

Uso:
    python -m utils.scheduler              # ejecuta scrapers ahora mismo
    python -m utils.scheduler --daemon     # bucle daemon: scraping diario + resumen semanal
    python -m utils.scheduler --summary    # envía solo el resumen semanal ahora
"""
import concurrent.futures
import logging
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.config import SCRAPING_HOUR, WEEKLY_SUMMARY_DAY

# ── Logging ───────────────────────────────────────────────────────────────────

_LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "scheduler.log"
_LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(_LOG_FILE, encoding="utf-8"),
    ],
)
log = logging.getLogger("scheduler")

# Timeout por tipo de scraper (segundos)
_TIMEOUT_PLAYWRIGHT = 240
_TIMEOUT_DEFAULT    = 90


# ── Carga de queries ──────────────────────────────────────────────────────────

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
    log.info(f"{len(queries)} búsquedas cargadas de la base de datos.")
    return queries


# ── Scraping con timeout ──────────────────────────────────────────────────────

def _run_one_scraper(
    cls,
    queries: list[str],
    productos_repo,
    precios_repo,
) -> int:
    """Ejecuta un scraper con timeout, guarda resultados y devuelve precios guardados."""
    from scrapers.playwright_base import PlaywrightBaseScraper

    scraper = cls()
    timeout = _TIMEOUT_PLAYWRIGHT if isinstance(scraper, PlaywrightBaseScraper) else _TIMEOUT_DEFAULT

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(scraper.run, queries if queries else None)
            results = future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        log.warning(f"[{scraper.NOMBRE}] Timeout tras {timeout}s — saltando.")
        return 0
    except Exception as exc:
        log.error(f"[{scraper.NOMBRE}] Error inesperado: {exc}")
        return 0

    guardados = 0
    for sp in results:
        try:
            pid = productos_repo.upsert_from_scraped(sp, scraper.supermarket_id)
            if pid:
                precios_repo.upsert_today(pid, scraper.supermarket_id, sp)
                guardados += 1
        except Exception as exc:
            log.warning(f"[{scraper.NOMBRE}] Error guardando producto: {exc}")

    log.info(f"[{scraper.NOMBRE}] {len(results)} encontrados — {guardados} guardados.")
    return guardados


# ── Detección de alertas ──────────────────────────────────────────────────────

def _detect_and_save_alerts() -> int:
    """Detecta bajadas de precio y crea alertas para los usuarios afectados.

    Compara el precio de hoy con la mediana de los últimos 30 días.
    Solo genera alerta si la bajada supera PRICE_DROP_THRESHOLD y el ahorro
    absoluto supera MIN_SAVINGS_ALERT.
    """
    import unicodedata
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

    with get_connection() as conn:
        items = conn.execute(
            "SELECT usuario_id, query_texto, cantidad FROM lista_usuario "
            "WHERE comprado = FALSE"
        ).fetchall()

    if not items:
        return 0

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
    mediana_cache: dict[tuple, float | None] = {}

    for item in items:
        usuario_id = str(item["usuario_id"])
        query = item["query_texto"]
        cantidad = int(item["cantidad"])
        qn = norm(query)
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
                    """
                    SELECT precio FROM precios_historicos
                    WHERE producto_id = %s AND supermercado_id = %s
                      AND fecha_scraping < %s
                    ORDER BY fecha_scraping DESC LIMIT 30
                    """,
                    (best["producto_id"], best["supermercado_id"], hoy),
                ).fetchall()
            if len(hist) < 2:
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

        with get_connection() as conn:
            existing = conn.execute(
                """
                SELECT id FROM alertas
                WHERE usuario_id = %s AND tipo_alerta = 'BAJADA_PRECIO'
                  AND activa = TRUE AND producto_id = %s
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


# ── Email: bajadas de precio diarias ─────────────────────────────────────────

def _send_price_drop_emails() -> int:
    """Envía emails de bajada de precio a usuarios con notificaciones activas."""
    import unicodedata
    from difflib import SequenceMatcher
    from database.connection import get_connection
    from database.repositories.usuarios_repo import UsuariosRepo
    from utils.config import PRICE_DROP_THRESHOLD
    from utils.email_sender import build_price_drop_email, send_email

    hoy = str(date.today())
    usuarios = UsuariosRepo().get_usuarios_con_notificaciones()
    if not usuarios:
        return 0

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
                if len(hist) < 2:
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
                drops.append({
                    "producto_nombre":     item["query_texto"],
                    "supermercado_nombre": best["supermercado_nombre"],
                    "precio_hoy":          precio_hoy_val,
                    "precio_habitual":     round(mediana, 2),
                    "pct_bajada":          round(descuento * 100, 1),
                    "ahorro_abs":          round((mediana - precio_hoy_val) * int(item["cantidad"]), 2),
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


# ── Email: resumen semanal ────────────────────────────────────────────────────

def _send_weekly_summary() -> int:
    """Envía el resumen semanal a usuarios con notificaciones activas.

    Incluye los mejores precios de la semana para cada producto de la lista,
    el ahorro total acumulado y los top descuentos de los últimos 7 días.
    """
    from database.connection import get_connection
    from database.repositories.usuarios_repo import UsuariosRepo
    from utils.config import PRICE_DROP_THRESHOLD
    from utils.email_sender import build_weekly_summary_email, send_email

    hoy = date.today()
    hace_7 = str(hoy - timedelta(days=7))
    hoy_str = str(hoy)

    usuarios = UsuariosRepo().get_usuarios_con_notificaciones()
    if not usuarios:
        return 0

    # Mejores precios de la semana con mediana histórica
    with get_connection() as conn:
        precios_semana = conn.execute(
            """
            SELECT
                p.nombre        AS producto_nombre,
                s.nombre        AS supermercado_nombre,
                MIN(ph.precio)  AS precio_min_semana,
                ph.fecha_scraping
            FROM precios_historicos ph
            JOIN productos     p ON p.id = ph.producto_id
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE ph.fecha_scraping BETWEEN %s AND %s
            GROUP BY p.nombre, s.nombre, ph.fecha_scraping
            ORDER BY p.nombre
            """,
            (hace_7, hoy_str),
        ).fetchall()

    if not precios_semana:
        log.info("[Scheduler] Sin precios esta semana para el resumen.")
        return 0

    # Índice de precios por producto (nombre normalizado → min precio + supermercado)
    import unicodedata
    from difflib import SequenceMatcher

    def norm(t: str) -> str:
        return (
            unicodedata.normalize("NFD", t)
            .encode("ascii", "ignore")
            .decode()
            .lower()
            .strip()
        )

    # Agrupa el precio mínimo semanal por producto
    best_weekly: dict[str, dict] = {}
    for row in precios_semana:
        key = norm(row["producto_nombre"])
        precio = float(row["precio_min_semana"])
        if key not in best_weekly or precio < best_weekly[key]["precio"]:
            best_weekly[key] = {
                "producto_nombre":     row["producto_nombre"],
                "supermercado_nombre": row["supermercado_nombre"],
                "precio":              precio,
            }

    # Medianas históricas (30 días previos a la semana)
    hace_37 = str(hoy - timedelta(days=37))
    with get_connection() as conn:
        hist_rows = conn.execute(
            """
            SELECT p.nombre AS producto_nombre,
                   ph.precio
            FROM precios_historicos ph
            JOIN productos p ON p.id = ph.producto_id
            WHERE ph.fecha_scraping BETWEEN %s AND %s
            """,
            (hace_37, hace_7),
        ).fetchall()

    medianas: dict[str, float] = {}
    from collections import defaultdict
    hist_map: dict[str, list[float]] = defaultdict(list)
    for r in hist_rows:
        hist_map[norm(r["producto_nombre"])].append(float(r["precio"]))
    for k, vals in hist_map.items():
        if len(vals) >= 3:
            sv = sorted(vals)
            medianas[k] = sv[len(sv) // 2]

    # Construir top deals: productos con bajada ≥ umbral respecto a mediana
    top_deals = []
    for key, info in best_weekly.items():
        if key not in medianas:
            continue
        mediana = medianas[key]
        if mediana == 0:
            continue
        descuento = (mediana - info["precio"]) / mediana
        if descuento >= PRICE_DROP_THRESHOLD:
            top_deals.append({
                **info,
                "precio_habitual": round(mediana, 2),
                "pct_bajada":      round(descuento * 100, 1),
            })
    top_deals.sort(key=lambda d: d["pct_bajada"], reverse=True)

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

        # Filtrar top_deals relevantes para este usuario
        qnorms = [norm(i["query_texto"]) for i in items]
        user_deals = []
        for deal in top_deals:
            dkey = norm(deal["producto_nombre"])
            for qn in qnorms:
                qw = set(qn.split())
                sim = SequenceMatcher(None, qn, dkey).ratio()
                ov = len(qw & set(dkey.split()))
                if sim + (ov / max(len(qw), 1)) * 0.30 >= 0.40:
                    user_deals.append(deal)
                    break

        # Stats de la semana para este usuario
        with get_connection() as conn:
            sesiones = conn.execute(
                """SELECT total_ahorrado FROM sesiones_compra
                   WHERE usuario_id = %s
                     AND fecha >= %s""",
                (usuario_id, hace_7),
            ).fetchall()

        ahorro_semana = sum(float(s["total_ahorrado"] or 0) for s in sesiones)
        n_compras = len(sesiones)

        html = build_weekly_summary_email(
            nombre_usuario=u["nombre"],
            top_deals=user_deals[:5],
            ahorro_semana=ahorro_semana,
            n_compras=n_compras,
            semana_inicio=hace_7,
            semana_fin=hoy_str,
        )
        ok = send_email(
            to=u["email"],
            subject=f"📊 Tu resumen semanal de Smart Shopping — {hoy.strftime('%d/%m/%Y')}",
            html=html,
        )
        if ok:
            enviados += 1

    return enviados


# ── Tareas orquestadas (una por franja horaria) ───────────────────────────────

def run_scrapers_task() -> None:
    """06:00 — Ejecuta todos los scrapers y guarda precios."""
    from database.init_db import init_db
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo
    from scrapers import ALL_SCRAPERS

    init_db()
    queries = _load_all_queries()
    productos_repo = ProductosRepo()
    precios_repo   = PreciosRepo()

    start = datetime.now()
    log.info("=" * 55)
    log.info(f"[06:00] Scraping iniciado: {start:%Y-%m-%d %H:%M:%S}")
    log.info(f"Scrapers: {len(ALL_SCRAPERS)}  |  Queries: {len(queries)}")
    log.info("=" * 55)

    total = 0
    for cls in ALL_SCRAPERS:
        total += _run_one_scraper(cls, queries, productos_repo, precios_repo)

    elapsed = (datetime.now() - start).seconds
    log.info(f"[06:00] Precios guardados: {total}  |  Duración: {elapsed}s")


def run_detect_alerts_task() -> None:
    """06:30 — Detecta bajadas de precio >15% y crea alertas en BD."""
    log.info("[06:30] Detectando bajadas de precio…")
    try:
        n = _detect_and_save_alerts()
        log.info(f"[06:30] {n} alerta(s) nueva(s) generadas.")
    except Exception as exc:
        log.error(f"[06:30] Error en detección de alertas: {exc}")


def run_send_alerts_task() -> None:
    """07:00 — Envía emails de alerta de bajada de precio a usuarios."""
    log.info("[07:00] Enviando emails de alertas de precio…")
    try:
        n = _send_price_drop_emails()
        log.info(f"[07:00] {n} email(s) de alerta enviados.")
    except Exception as exc:
        log.error(f"[07:00] Error enviando emails de alerta: {exc}")


def run_weekly_summary() -> None:
    """Miércoles 08:00 — Envía el resumen semanal a todos los usuarios."""
    log.info("[08:00 mié] Enviando resumen semanal…")
    try:
        n = _send_weekly_summary()
        log.info(f"[08:00 mié] Resumen semanal enviado a {n} usuario(s).")
    except Exception as exc:
        log.error(f"[08:00 mié] Error en resumen semanal: {exc}")


# Alias para compatibilidad con código existente (botón manual en admin)
def run_all_scrapers() -> None:
    run_scrapers_task()
    run_detect_alerts_task()
    run_send_alerts_task()


# ── Daemon para arranque automático desde app.py ──────────────────────────────

import threading as _threading

_daemon_thread: _threading.Thread | None = None


def start_daemon() -> None:
    """Arranca el scheduler en un hilo daemon. Llámalo una sola vez al inicio de app.py.

    Horario:
        06:00  →  scrapers
        06:30  →  detectar bajadas
        07:00  →  enviar emails de alerta
        mié 08:00 → resumen semanal
    """
    global _daemon_thread
    if _daemon_thread is not None and _daemon_thread.is_alive():
        return  # ya está corriendo

    import schedule as _schedule

    _schedule.clear()
    _schedule.every().day.at("06:00").do(run_scrapers_task)
    _schedule.every().day.at("06:30").do(run_detect_alerts_task)
    _schedule.every().day.at("07:00").do(run_send_alerts_task)
    _schedule.every().wednesday.at("08:00").do(run_weekly_summary)

    def _loop() -> None:
        log.info("Scheduler daemon iniciado. Proximas ejecuciones programadas:")
        log.info("  06:00 scrapers | 06:30 alertas | 07:00 emails | mie 08:00 resumen")
        while True:
            _schedule.run_pending()
            time.sleep(30)

    _daemon_thread = _threading.Thread(target=_loop, name="scheduler-daemon", daemon=True)
    _daemon_thread.start()
    log.info("Scheduler daemon arrancado en hilo background.")


# ── Entry point CLI ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    import schedule

    if "--summary" in sys.argv:
        run_weekly_summary()

    elif "--daemon" in sys.argv:
        log.info("Modo daemon CLI — horario fijo (06:00 / 06:30 / 07:00 / mié 08:00).")
        schedule.every().day.at("06:00").do(run_scrapers_task)
        schedule.every().day.at("06:30").do(run_detect_alerts_task)
        schedule.every().day.at("07:00").do(run_send_alerts_task)
        schedule.every().wednesday.at("08:00").do(run_weekly_summary)
        run_scrapers_task()
        while True:
            schedule.run_pending()
            time.sleep(30)

    else:
        run_all_scrapers()
