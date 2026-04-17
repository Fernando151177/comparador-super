"""Home / dashboard page."""
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher

import streamlit as st

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from domain.models import Usuario
from ordering.supermarket_links import get_info
from utils.config import PRICE_DROP_THRESHOLD


def mostrar(usuario: Usuario) -> None:
    st.title("🛒 Smart Shopping Iberia")
    st.caption(f"Hola, **{usuario.nombre}** · {_pais_label(usuario.pais_activo)}")

    precios_hoy = PreciosRepo().get_today(pais=usuario.pais_activo)
    n_lista = _count_lista(usuario.id)
    n_alertas = _count_alertas(usuario.id)
    n_supers = len({p["supermercado_nombre"] for p in precios_hoy})

    # ── Métricas rápidas ──────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("En tu lista", n_lista, help="Productos pendientes de comprar")
    col2.metric("Precios actualizados", len(precios_hoy), help="Precios de hoy en BD")
    col3.metric("Alertas activas", n_alertas, help="Bajadas de precio pendientes")
    col4.metric("Supermercados", n_supers, help="Supermercados con precios hoy")

    st.markdown("---")

    if not precios_hoy:
        st.info(
            "No hay precios para hoy. Ve a **📋 Mi lista** y pulsa "
            "**🔄 Consultar supermercados ahora** para actualizar."
        )
        return

    # ── Layout principal: columna izquierda + derecha ─────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        _render_lista_resumen(usuario, precios_hoy)
        st.markdown("---")
        _render_price_drops(usuario.id, precios_hoy)

    with col_right:
        _render_ahorro_stats(usuario.id)
        st.markdown("---")
        _render_super_del_dia(usuario, precios_hoy)


# ── Resumen de la lista ───────────────────────────────────────────────────────

def _render_lista_resumen(usuario: Usuario, precios_hoy: list[dict]) -> None:
    st.subheader("📋 Tu lista de hoy")

    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE "
            "ORDER BY query_texto LIMIT 8",
            (usuario.id,),
        ).fetchall()

    if not items:
        st.info("Tu lista está vacía.")
        if st.button("➕ Añadir productos", use_container_width=True):
            st.session_state["page"] = "lista"
            st.rerun()
        return

    # Para cada item buscar el precio mínimo de hoy
    def norm(t):
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    total_min = 0.0
    rows_html = []
    for item in items:
        q = item["query_texto"]
        qn = norm(q)
        qw = set(qn.split())
        best_price, best_super = None, None
        for p in precios_hoy:
            nn = norm(p["producto_nombre"])
            sim = SequenceMatcher(None, qn, nn).ratio()
            ov = len(qw & set(nn.split()))
            score = sim + (ov / max(len(qw), 1)) * 0.30
            if score >= 0.35 and (best_price is None or p["precio"] < best_price):
                best_price = float(p["precio"])
                best_super = p["supermercado_nombre"]

        qty = item["cantidad"]
        if best_price is not None:
            total_min += best_price * qty
            price_str = f"{best_price:.2f} €"
            super_str = f"<span style='color:#888;font-size:0.8rem'>{best_super}</span>"
        else:
            price_str = "—"
            super_str = ""

        rows_html.append(
            f"<div style='display:flex;justify-content:space-between;"
            f"padding:4px 0;border-bottom:1px solid #f0f0f0'>"
            f"<span>{'×'+str(qty)+' ' if qty>1 else ''}<b>{q}</b></span>"
            f"<span>{super_str} <b>{price_str}</b></span>"
            f"</div>"
        )

    st.markdown("".join(rows_html), unsafe_allow_html=True)

    n_total = _count_lista(usuario.id)
    if n_total > 8:
        st.caption(f"… y {n_total - 8} más")

    if total_min > 0:
        st.markdown(
            f"<div style='text-align:right;margin-top:8px'>"
            f"Mínimo estimado: <b style='font-size:1.1rem'>{total_min:.2f} €</b>"
            f"</div>",
            unsafe_allow_html=True,
        )


# ── Bajadas de precio ─────────────────────────────────────────────────────────

def _render_price_drops(usuario_id: str, precios_hoy: list[dict]) -> None:
    st.subheader("📉 Bajadas de precio detectadas")
    hoy = str(date.today())

    def norm(t):
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchall()

    drops = []
    for item in items:
        qn = norm(item["query_texto"])
        qw = set(qn.split())
        best, best_score = None, 0.0
        for p in precios_hoy:
            nn = norm(p["producto_nombre"])
            sim = SequenceMatcher(None, qn, nn).ratio()
            ov = len(qw & set(nn.split()))
            total = sim + (ov / max(len(qw), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p
        if best is None or best_score < 0.40:
            continue

        with get_connection() as conn:
            hist = conn.execute(
                """SELECT precio FROM precios_historicos
                   WHERE producto_id = %s AND supermercado_id = %s
                     AND fecha_scraping < %s
                   ORDER BY fecha_scraping DESC LIMIT 30""",
                (best["producto_id"], best["supermercado_id"], hoy),
            ).fetchall()

        if len(hist) < 3:
            continue
        precios_h = sorted(float(r["precio"]) for r in hist)
        mediana = precios_h[len(precios_h) // 2]
        precio_hoy_val = float(best["precio"])
        if mediana > 0 and (mediana - precio_hoy_val) / mediana >= PRICE_DROP_THRESHOLD:
            pct = round((mediana - precio_hoy_val) / mediana * 100, 1)
            drops.append({
                "nombre": item["query_texto"],
                "super": best["supermercado_nombre"],
                "precio": precio_hoy_val,
                "habitual": round(mediana, 2),
                "pct": pct,
            })

    if not drops:
        st.caption("Sin bajadas significativas hoy en tu lista.")
        return

    for d in drops[:4]:
        st.success(
            f"**{d['nombre']}** en {d['super']} — "
            f"**{d['precio']:.2f} €** ~~{d['habitual']:.2f} €~~ **-{d['pct']}%**"
        )
    if len(drops) > 4:
        st.caption(f"… y {len(drops) - 4} bajada(s) más en **🔔 Alertas**")


# ── Stats de ahorro ───────────────────────────────────────────────────────────

def _render_ahorro_stats(usuario_id: str) -> None:
    st.subheader("💰 Tu ahorro acumulado")

    with get_connection() as conn:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_ahorrado),0) AS total,
                      COALESCE(SUM(total_gastado),0)  AS gastado,
                      COUNT(*) AS sesiones
               FROM sesiones_compra WHERE usuario_id = %s""",
            (usuario_id,),
        ).fetchone()

    if not row or row["sesiones"] == 0:
        st.info(
            "Aún sin historial. Usa el **🗺️ Optimizador** y pulsa "
            "**Registrar esta compra** para empezar a acumular estadísticas."
        )
        return

    total_ahorrado = float(row["total"])
    total_gastado = float(row["gastado"])
    sesiones = row["sesiones"]
    pct = round(total_ahorrado / (total_gastado + total_ahorrado) * 100, 1) if total_gastado > 0 else 0

    c1, c2 = st.columns(2)
    c1.metric("Total ahorrado", f"{total_ahorrado:.2f} €")
    c2.metric("Compras registradas", sesiones)
    st.progress(min(pct / 30, 1.0), text=f"Ahorro medio del {pct}% sobre precio máximo")

    # Última compra
    with get_connection() as conn:
        last = conn.execute(
            "SELECT fecha, total_gastado, total_ahorrado FROM sesiones_compra "
            "WHERE usuario_id = %s ORDER BY fecha DESC LIMIT 1",
            (usuario_id,),
        ).fetchone()
    if last:
        st.caption(
            f"Última compra: {last['fecha']} · "
            f"{float(last['total_gastado']):.2f} € gastados · "
            f"{float(last['total_ahorrado']):.2f} € ahorrados"
        )


# ── Supermercado más barato del día ───────────────────────────────────────────

def _render_super_del_dia(usuario: Usuario, precios_hoy: list[dict]) -> None:
    st.subheader("🏪 Supermercado más barato hoy")
    st.caption("Para tu lista actual, ¿dónde gastarías menos comprando todo en un solo sitio?")

    def norm(t):
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario.id,),
        ).fetchall()

    if not items:
        st.caption("Añade productos a tu lista para ver esta comparativa.")
        return

    # Total por supermercado (solo si tiene precio para todos los items)
    supers = sorted({p["supermercado_nombre"] for p in precios_hoy})
    totales: dict[str, float] = {}
    cobertura: dict[str, int] = {}

    for s in supers:
        pool = [p for p in precios_hoy if p["supermercado_nombre"] == s]
        total = 0.0
        encontrados = 0
        for item in items:
            qn = norm(item["query_texto"])
            qw = set(qn.split())
            best_p, best_sc = None, 0.0
            for p in pool:
                nn = norm(p["producto_nombre"])
                sim = SequenceMatcher(None, qn, nn).ratio()
                ov = len(qw & set(nn.split()))
                sc = sim + (ov / max(len(qw), 1)) * 0.30
                if sc > best_sc:
                    best_sc, best_p = sc, p
            if best_p and best_sc >= 0.35:
                total += float(best_p["precio"]) * item["cantidad"]
                encontrados += 1
        if encontrados > 0:
            totales[s] = round(total, 2)
            cobertura[s] = encontrados

    if not totales:
        st.caption("Sin datos suficientes para comparar.")
        return

    n_items = len(items)
    sorted_supers = sorted(totales.items(), key=lambda x: x[1])
    precio_min = sorted_supers[0][1]

    for i, (s, total) in enumerate(sorted_supers):
        cob = cobertura[s]
        pct_cob = int(cob / n_items * 100)
        es_fav = "⭐ " if any(
            p.get("supermercado_codigo", "") in usuario.supermercados_favoritos
            for p in precios_hoy if p["supermercado_nombre"] == s
        ) else ""

        if i == 0:
            diff_str = "✓ MÁS BARATO"
            color = "green"
        else:
            diff = round(total - precio_min, 2)
            diff_str = f"+{diff:.2f} €"
            color = "normal"

        col_a, col_b, col_c = st.columns([3, 2, 2])
        with col_a:
            st.write(f"{es_fav}**{s}**")
            st.caption(f"{cob}/{n_items} productos ({pct_cob}%)")
        with col_b:
            st.write(f"**{total:.2f} €**")
        with col_c:
            if color == "green":
                st.markdown(f":green[**{diff_str}**]")
            else:
                st.caption(diff_str)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pais_label(pais: str) -> str:
    return {"ES": "🇪🇸 España", "PT": "🇵🇹 Portugal", "AMBOS": "🌍 ES + PT"}.get(pais, pais)


def _count_lista(usuario_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchone()
    return row["n"] if row else 0


def _count_alertas(usuario_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM alertas WHERE usuario_id = %s AND activa = TRUE",
            (usuario_id,),
        ).fetchone()
    return row["n"] if row else 0
