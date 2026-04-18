"""Página de alertas de bajada de precio — diseño premium Smart Shopping Iberia."""
import streamlit as st

from database.repositories.alertas_repo import AlertasRepo
from database.connection import get_connection
from domain.models import Usuario
from ui.styles import page_header, section_header, empty_state, alert_card_html


def mostrar(usuario: Usuario) -> None:
    page_header(
        "Alertas de ofertas",
        subtitle="Te avisamos cuando el precio baja ≥15% respecto al precio habitual.",
        emoji="🔔",
    )

    repo      = AlertasRepo()
    favoritos = usuario.supermercados_favoritos

    # ── Bajadas de precio detectadas hoy ─────────────────────────────────────
    drops = _get_price_drops_today(usuario.id)

    if drops:
        drops_fav   = [d for d in drops if d.get("supermercado_codigo") in favoritos]
        drops_otros = [d for d in drops if d.get("supermercado_codigo") not in favoritos]
        drops_sorted = drops_fav + drops_otros

        section_header(
            f"📉 {len(drops_sorted)} bajada(s) de precio hoy",
            "Favoritos primero · ordenados por mayor ahorro",
        )

        for d in drops_sorted:
            pct   = round((d["precio_habitual"] - d["precio_hoy"]) / d["precio_habitual"] * 100, 1)
            ahorro = round((d["precio_habitual"] - d["precio_hoy"]) * d["cantidad"], 2)

            col_card, col_btn = st.columns([5, 1])
            with col_card:
                st.markdown(
                    alert_card_html(
                        d["producto_nombre"],
                        d["supermercado_nombre"],
                        pct,
                        d["precio_hoy"],
                        d["precio_habitual"],
                    ),
                    unsafe_allow_html=True,
                )
            with col_btn:
                st.markdown("<br>", unsafe_allow_html=True)
                st.metric("Ahorro", f"{ahorro:.2f} €")

        st.markdown("---")
    else:
        empty_state(
            "✅",
            "Sin bajadas significativas hoy",
            "Cuando detectemos una oferta en tu lista, aparecerá aquí.",
        )
        st.markdown("---")

    # ── Alertas activas ───────────────────────────────────────────────────────
    alertas = repo.get_active_for_user(usuario.id)
    if alertas:
        section_header(f"⚡ {len(alertas)} alerta(s) activa(s)")
        for a in alertas:
            nombre = a.get("producto_nombre") or a.get("ean") or "Producto desconocido"
            icono  = {
                "BAJADA_PRECIO": "📉",
                "OFERTA_ENVIO":  "🚚",
                "CROSS_BORDER":  "🌍",
            }.get(a["tipo_alerta"], "🔔")
            umbral = f" (umbral: {a['umbral_precio']:.2f} €)" if a.get("umbral_precio") else ""

            col1, col2 = st.columns([7, 1])
            with col1:
                st.markdown(
                    f'<div style="background:white;border-radius:10px;padding:12px 16px;'
                    f'box-shadow:0 1px 8px rgba(0,0,0,.06);border:1px solid #E9ECEF;'
                    f'margin-bottom:8px">'
                    f'  <div style="font-weight:700;font-size:.92rem">{icono} {nombre}{umbral}</div>'
                    f'  {"<div style=\"font-size:.76rem;color:#6C757D;margin-top:3px\">Última activación: " + str(a["ultima_activacion"]) + "</div>" if a.get("ultima_activacion") else ""}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("✖", key=f"del_{a['id']}", help="Desactivar alerta"):
                    repo.deactivate(a["id"])
                    st.rerun()
    else:
        st.info(
            "No tienes alertas activas. Se generan automáticamente cuando detectamos bajadas de precio."
        )

    st.markdown("---")

    # ── Crear alerta manual ───────────────────────────────────────────────────
    with st.expander("➕ Crear alerta manual"):
        productos = _get_user_productos(usuario.id)
        if not productos:
            st.info("Añade productos a tu lista para poder crear alertas.")
        else:
            with st.form("nueva_alerta"):
                opciones  = {f"{p['nombre']} (id {p['id']})": p["id"] for p in productos}
                seleccion = st.selectbox("Producto", list(opciones.keys()))
                umbral    = st.number_input(
                    "Avísame si el precio baja de (€)",
                    min_value=0.0, value=0.0, step=0.10,
                    help="Deja en 0 para alertar con cualquier bajada ≥15%.",
                )
                if st.form_submit_button("🔔 Crear alerta", type="primary"):
                    repo.create(
                        usuario_id=usuario.id,
                        tipo_alerta="BAJADA_PRECIO",
                        producto_id=opciones[seleccion],
                        umbral_precio=umbral if umbral > 0 else None,
                    )
                    st.success("✅ Alerta creada correctamente.")
                    st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_price_drops_today(usuario_id: str) -> list[dict]:
    import unicodedata
    from difflib import SequenceMatcher
    from datetime import date
    from utils.config import PRICE_DROP_THRESHOLD

    def norm(t: str) -> str:
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    hoy = str(date.today())

    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchall()

    if not items:
        return []

    with get_connection() as conn:
        prices = conn.execute(
            """
            SELECT ph.producto_id, ph.supermercado_id,
                   ph.precio AS precio_hoy,
                   p.nombre  AS producto_nombre,
                   s.nombre  AS supermercado_nombre,
                   s.codigo  AS supermercado_codigo
            FROM precios_historicos ph
            JOIN productos     p ON p.id = ph.producto_id
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE ph.fecha_scraping = %s
            """,
            (hoy,),
        ).fetchall()

    drops = []
    for item in items:
        qn = norm(item["query_texto"])
        qw = set(qn.split())

        best, best_score = None, 0.0
        for p in prices:
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

        if len(hist) < 2:
            continue

        precios_hist = sorted(float(r["precio"]) for r in hist)
        mediana      = precios_hist[len(precios_hist) // 2]
        precio_hoy   = float(best["precio_hoy"])

        if mediana == 0:
            continue

        if (mediana - precio_hoy) / mediana >= PRICE_DROP_THRESHOLD:
            drops.append({
                "producto_nombre":     best["producto_nombre"],
                "supermercado_nombre": best["supermercado_nombre"],
                "supermercado_codigo": best.get("supermercado_codigo", ""),
                "precio_hoy":          precio_hoy,
                "precio_habitual":     round(mediana, 2),
                "cantidad":            item["cantidad"],
            })

    return sorted(drops, key=lambda x: x["precio_habitual"] - x["precio_hoy"], reverse=True)


def _get_user_productos(usuario_id: str) -> list[dict]:
    import unicodedata
    from difflib import SequenceMatcher
    from datetime import date

    def norm(t: str) -> str:
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    hoy = str(date.today())
    with get_connection() as conn:
        items  = conn.execute(
            "SELECT query_texto FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchall()
        prices = conn.execute(
            "SELECT DISTINCT p.id, p.nombre "
            "FROM precios_historicos ph "
            "JOIN productos p ON p.id = ph.producto_id "
            "WHERE ph.fecha_scraping = %s",
            (hoy,),
        ).fetchall()

    result = []
    for item in items:
        qn = norm(item["query_texto"])
        best, best_score = None, 0.0
        for p in prices:
            score = SequenceMatcher(None, qn, norm(p["nombre"])).ratio()
            if score > best_score:
                best_score, best = score, p
        if best and best_score >= 0.40:
            result.append({"id": best["id"], "nombre": best["nombre"]})

    seen, unique = set(), []
    for r in result:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)
    return unique
