"""Home / dashboard — diseño premium Smart Shopping Iberia."""
import unicodedata
from datetime import date, datetime, timedelta
from difflib import SequenceMatcher

import streamlit as st

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from domain.models import Usuario
from ordering.supermarket_links import get_info
from utils.config import PRICE_DROP_THRESHOLD
from ui.styles import (
    page_header, section_header, metric_cards, empty_state, badge_html
)


def mostrar(usuario: Usuario) -> None:
    # ── Saludo dinámico ───────────────────────────────────────────────────────
    hora = datetime.now().hour
    saludo = "Buenos días" if hora < 13 else ("Buenas tardes" if hora < 20 else "Buenas noches")
    pais_lbl = {"ES": "🇪🇸 España", "PT": "🇵🇹 Portugal", "AMBOS": "🌍 ES + PT"}.get(
        usuario.pais_activo, usuario.pais_activo
    )
    page_header(
        f"{saludo}, {usuario.nombre} 👋",
        subtitle=f"Tu panel de compra inteligente · {pais_lbl}",
    )

    precios_hoy = PreciosRepo().get_today(pais=usuario.pais_activo)
    n_lista    = _count_lista(usuario.id)
    n_alertas  = _count_alertas(usuario.id)
    n_supers   = len({p["supermercado_nombre"] for p in precios_hoy})
    ahorro_sem = _ahorro_semana(usuario.id)
    prox_compra = _proximo_dia(usuario.dia_compra)

    # ── 4 tarjetas métricas ───────────────────────────────────────────────────
    metric_cards([
        {
            "icon": "💰",
            "value": f"{ahorro_sem:.2f} €" if ahorro_sem > 0 else "—",
            "label": "Ahorro esta semana",
            "delta": "¡buen trabajo!" if ahorro_sem > 0 else "",
            "color": "#1B4332",
        },
        {
            "icon": "🛒",
            "value": str(n_lista),
            "label": "Productos en lista",
            "color": "#2D6A4F",
        },
        {
            "icon": "🔔",
            "value": str(n_alertas),
            "label": "Alertas activas",
            "color": "#40916C" if n_alertas == 0 else "#E63946",
        },
        {
            "icon": "📅",
            "value": prox_compra,
            "label": "Próxima compra",
            "color": "#52B788",
        },
    ])

    st.markdown("<br>", unsafe_allow_html=True)

    if not precios_hoy:
        empty_state(
            "🔄",
            "Sin precios para hoy",
            "Ve a <b>📋 Mi lista</b> y pulsa <b>Consultar supermercados ahora</b> "
            "para obtener los precios actualizados.",
        )
        return

    # ── Layout: columna principal + lateral ───────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        _render_lista_resumen(usuario, precios_hoy)
        _render_price_drops(usuario.id, precios_hoy)

    with col_right:
        _render_ahorro_stats(usuario.id)
        _render_super_del_dia(usuario, precios_hoy)


# ── Resumen de la lista ───────────────────────────────────────────────────────

def _render_lista_resumen(usuario: Usuario, precios_hoy: list[dict]) -> None:
    section_header("📋 Tu lista de hoy", "Los primeros 8 productos con su precio mínimo")

    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE "
            "ORDER BY query_texto LIMIT 8",
            (usuario.id,),
        ).fetchall()

    if not items:
        empty_state(
            "🛒",
            "Tu lista está vacía",
            "¡Empieza añadiendo productos en <b>📋 Mi lista</b>!",
        )
        if st.button("➕ Añadir productos", type="primary", use_container_width=True):
            st.session_state["page"] = "lista"
            st.rerun()
        return

    def norm(t):
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    total_min = 0.0
    rows_html = []
    for item in items:
        q  = item["query_texto"]
        qn = norm(q)
        qw = set(qn.split())
        best_price, best_super = None, None
        for p in precios_hoy:
            nn  = norm(p["producto_nombre"])
            sim = SequenceMatcher(None, qn, nn).ratio()
            ov  = len(qw & set(nn.split()))
            sc  = sim + (ov / max(len(qw), 1)) * 0.30
            if sc >= 0.35 and (best_price is None or p["precio"] < best_price):
                best_price = float(p["precio"])
                best_super = p["supermercado_nombre"]

        qty = item["cantidad"]
        if best_price is not None:
            total_min += best_price * qty
            price_html = (
                f'<span style="font-weight:700;color:#1B4332">{best_price:.2f} €</span>'
                f'<span style="font-size:.75rem;color:#6C757D;margin-left:6px">{best_super}</span>'
            )
        else:
            price_html = '<span style="color:#ADB5BD">sin precio</span>'

        qty_str = f"×{qty} " if qty > 1 else ""
        rows_html.append(
            f'<div style="display:flex;justify-content:space-between;align-items:center;'
            f'padding:10px 14px;border-radius:9px;margin-bottom:5px;background:white;'
            f'box-shadow:0 1px 6px rgba(0,0,0,.06);border:1px solid #F0F0F0">'
            f'<span style="font-weight:500;font-size:.9rem">{qty_str}<b>{q}</b></span>'
            f'<span>{price_html}</span>'
            f'</div>'
        )

    st.markdown("".join(rows_html), unsafe_allow_html=True)

    n_total = _count_lista(usuario.id)
    if n_total > 8:
        st.caption(f"… y {n_total - 8} producto(s) más en tu lista")

    if total_min > 0:
        st.markdown(
            f'<div style="text-align:right;margin-top:10px;padding:10px 14px;'
            f'background:#D8F3DC;border-radius:9px">'
            f'Mínimo estimado: <b style="font-size:1.15rem;color:#1B4332">{total_min:.2f} €</b>'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Bajadas de precio ─────────────────────────────────────────────────────────

def _render_price_drops(usuario_id: str, precios_hoy: list[dict]) -> None:
    section_header("📉 Mejores ofertas hoy", "Productos de tu lista con bajada ≥15%")
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
            nn    = norm(p["producto_nombre"])
            sim   = SequenceMatcher(None, qn, nn).ratio()
            ov    = len(qw & set(nn.split()))
            total = sim + (ov / max(len(qw), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p
        if best is None or best_score < 0.40:
            continue

        with get_connection() as conn:
            hist = conn.execute(
                "SELECT precio FROM precios_historicos "
                "WHERE producto_id = %s AND supermercado_id = %s "
                "  AND fecha_scraping < %s "
                "ORDER BY fecha_scraping DESC LIMIT 30",
                (best["producto_id"], best["supermercado_id"], hoy),
            ).fetchall()

        if len(hist) < 3:
            continue
        precios_h     = sorted(float(r["precio"]) for r in hist)
        mediana       = precios_h[len(precios_h) // 2]
        precio_hoy_v  = float(best["precio"])
        if mediana > 0 and (mediana - precio_hoy_v) / mediana >= PRICE_DROP_THRESHOLD:
            pct = round((mediana - precio_hoy_v) / mediana * 100, 1)
            drops.append({
                "nombre":  item["query_texto"],
                "super":   best["supermercado_nombre"],
                "precio":  precio_hoy_v,
                "habitual": round(mediana, 2),
                "pct":     pct,
            })

    if not drops:
        st.markdown(
            '<div style="padding:14px 18px;background:#F8F9FA;border-radius:10px;'
            'color:#6C757D;font-size:.88rem">Sin bajadas significativas hoy en tu lista.</div>',
            unsafe_allow_html=True,
        )
        return

    cards_html = []
    for d in drops[:4]:
        cards_html.append(
            f'<div style="background:white;border-radius:12px;padding:14px 18px;'
            f'box-shadow:0 2px 10px rgba(0,0,0,.07);border:1px solid #E9ECEF;'
            f'margin-bottom:10px;display:flex;align-items:center;gap:16px">'
            f'  <div style="min-width:58px;text-align:center;background:#FFF0F0;'
            f'      border-radius:9px;padding:7px 4px">'
            f'    <div style="font-size:1.2rem;font-weight:800;color:#E63946">-{d["pct"]}%</div>'
            f'  </div>'
            f'  <div style="flex:1">'
            f'    <div style="font-weight:700;font-size:.9rem">{d["nombre"]}</div>'
            f'    <div style="font-size:.77rem;color:#6C757D;margin-top:2px">📍 {d["super"]}</div>'
            f'  </div>'
            f'  <div style="text-align:right">'
            f'    <div style="font-weight:800;color:#52B788;font-size:1.05rem">{d["precio"]:.2f} €</div>'
            f'    <div style="font-size:.75rem;color:#ADB5BD;text-decoration:line-through">'
            f'        {d["habitual"]:.2f} €</div>'
            f'  </div>'
            f'</div>'
        )
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    if len(drops) > 4:
        st.caption(f"… y {len(drops) - 4} bajada(s) más en **🔔 Alertas**")


# ── Stats de ahorro ───────────────────────────────────────────────────────────

def _render_ahorro_stats(usuario_id: str) -> None:
    section_header("💰 Tu ahorro acumulado")

    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_ahorrado),0) AS total, "
            "       COALESCE(SUM(total_gastado),0)  AS gastado, "
            "       COUNT(*) AS sesiones "
            "FROM sesiones_compra WHERE usuario_id = %s",
            (usuario_id,),
        ).fetchone()

    if not row or row["sesiones"] == 0:
        empty_state(
            "📊",
            "Sin historial aún",
            "Usa el <b>🗺️ Optimizador</b> y pulsa <b>Registrar esta compra</b> "
            "para empezar a acumular estadísticas.",
        )
        return

    total_ahorrado = float(row["total"])
    total_gastado  = float(row["gastado"])
    sesiones       = row["sesiones"]
    pct = round(total_ahorrado / (total_gastado + total_ahorrado) * 100, 1) if total_gastado > 0 else 0

    # Hero numérico inline (más pequeño que el de panel_ahorro)
    st.markdown(
        f'<div style="background:linear-gradient(135deg,#1B4332,#2D6A4F);border-radius:12px;'
        f'padding:20px 24px;color:white;text-align:center;margin-bottom:14px">'
        f'  <div style="font-size:2.4rem;font-weight:800;letter-spacing:-.03em">'
        f'      {total_ahorrado:.2f} €</div>'
        f'  <div style="font-size:.82rem;opacity:.8;margin-top:4px">ahorro acumulado total</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns(2)
    c1.metric("Compras registradas", sesiones)
    c2.metric("% de ahorro medio", f"{pct}%")

    st.progress(min(pct / 30, 1.0), text=f"Ahorro del {pct}% sobre precio máximo")

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
    section_header("🏪 Ranking de hoy", "¿Dónde gastarías menos con tu lista actual?")

    def norm(t):
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario.id,),
        ).fetchall()

    if not items:
        st.caption("Añade productos a tu lista para ver el ranking.")
        return

    supers   = sorted({p["supermercado_nombre"] for p in precios_hoy})
    totales:  dict[str, float] = {}
    cobertura: dict[str, int]  = {}

    for s in supers:
        pool        = [p for p in precios_hoy if p["supermercado_nombre"] == s]
        total       = 0.0
        encontrados = 0
        for item in items:
            qn = norm(item["query_texto"])
            qw = set(qn.split())
            best_p, best_sc = None, 0.0
            for p in pool:
                nn = norm(p["producto_nombre"])
                sc = SequenceMatcher(None, qn, nn).ratio() + (
                    len(qw & set(nn.split())) / max(len(qw), 1)
                ) * 0.30
                if sc > best_sc:
                    best_sc, best_p = sc, p
            if best_p and best_sc >= 0.35:
                total       += float(best_p["precio"]) * item["cantidad"]
                encontrados += 1
        if encontrados > 0:
            totales[s]   = round(total, 2)
            cobertura[s] = encontrados

    if not totales:
        st.caption("Sin datos suficientes para comparar.")
        return

    n_items       = len(items)
    sorted_supers = sorted(totales.items(), key=lambda x: x[1])
    precio_min    = sorted_supers[0][1]

    # Emojis de ranking
    medallas = ["🥇", "🥈", "🥉"]

    cards_html = []
    for i, (s, total) in enumerate(sorted_supers[:5]):
        cob     = cobertura[s]
        pct_cob = int(cob / n_items * 100)
        es_fav  = any(
            p.get("supermercado_codigo", "") in usuario.supermercados_favoritos
            for p in precios_hoy if p["supermercado_nombre"] == s
        )
        fav_mark = " ⭐" if es_fav else ""
        medal    = medallas[i] if i < 3 else f"#{i+1}"
        diff     = round(total - precio_min, 2)
        diff_str = (
            '<span style="color:#52B788;font-weight:700">✓ más barato</span>'
            if i == 0 else
            f'<span style="color:#6C757D;font-size:.82rem">+{diff:.2f} €</span>'
        )
        bg = "#EEF7F3" if i == 0 else "white"
        border = "2px solid #52B788" if i == 0 else "1px solid #E9ECEF"

        cards_html.append(
            f'<div style="background:{bg};border:{border};border-radius:11px;'
            f'padding:12px 16px;margin-bottom:8px;display:flex;align-items:center;gap:12px">'
            f'  <div style="font-size:1.3rem;width:30px;text-align:center">{medal}</div>'
            f'  <div style="flex:1">'
            f'    <div style="font-weight:700;font-size:.9rem">{s}{fav_mark}</div>'
            f'    <div style="font-size:.74rem;color:#6C757D">{cob}/{n_items} productos ({pct_cob}%)</div>'
            f'  </div>'
            f'  <div style="text-align:right">'
            f'    <div style="font-weight:800;color:#1B4332;font-size:1rem">{total:.2f} €</div>'
            f'    {diff_str}'
            f'  </div>'
            f'</div>'
        )
    st.markdown("".join(cards_html), unsafe_allow_html=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def _ahorro_semana(usuario_id: str) -> float:
    hace_7 = str(date.today() - timedelta(days=7))
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(total_ahorrado),0) AS total "
            "FROM sesiones_compra "
            "WHERE usuario_id = %s AND fecha >= %s",
            (usuario_id, hace_7),
        ).fetchone()
    return float(row["total"]) if row else 0.0


def _proximo_dia(dia_compra: str | None) -> str:
    """Devuelve el día de la semana de la próxima compra."""
    dias_es = {
        "MONDAY":    "Lunes",
        "TUESDAY":   "Martes",
        "WEDNESDAY": "Miércoles",
        "THURSDAY":  "Jueves",
        "FRIDAY":    "Viernes",
        "SATURDAY":  "Sábado",
        "SUNDAY":    "Domingo",
    }
    return dias_es.get((dia_compra or "SATURDAY").upper(), "Sábado")
