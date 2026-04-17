"""Página de alertas de bajada de precio."""
import streamlit as st

from database.repositories.alertas_repo import AlertasRepo
from database.connection import get_connection
from domain.models import Usuario


def mostrar(usuario: Usuario) -> None:
    st.title("🔔 Alertas de ofertas")
    st.caption("Te avisamos cuando el precio de un producto de tu lista baja ≥15% respecto a su precio habitual.")

    repo = AlertasRepo()

    # ── Bajadas de precio detectadas hoy ─────────────────────────────────────
    drops = _get_price_drops_today(usuario.id)
    if drops:
        st.subheader(f"📉 {len(drops)} bajada(s) de precio hoy")
        for d in drops:
            pct = round((d["precio_habitual"] - d["precio_hoy"]) / d["precio_habitual"] * 100, 1)
            ahorro = round((d["precio_habitual"] - d["precio_hoy"]) * d["cantidad"], 2)
            col1, col2 = st.columns([5, 2])
            with col1:
                st.success(
                    f"**{d['producto_nombre']}** en {d['supermercado_nombre']}  \n"
                    f"Hoy: **{d['precio_hoy']:.2f} €** · Habitual: {d['precio_habitual']:.2f} € · "
                    f"**-{pct}%**"
                )
            with col2:
                st.metric("Ahorras", f"{ahorro:.2f} €")
        st.markdown("---")
    else:
        st.info("No hay bajadas de precio significativas hoy en tu lista.")
        st.markdown("---")

    # ── Alertas activas ───────────────────────────────────────────────────────
    alertas = repo.get_active_for_user(usuario.id)
    if alertas:
        st.subheader(f"⚡ {len(alertas)} alerta(s) activa(s)")
        for a in alertas:
            col1, col2 = st.columns([7, 1])
            with col1:
                nombre = a.get("producto_nombre") or a.get("ean") or "Producto desconocido"
                icono = {"BAJADA_PRECIO": "📉", "OFERTA_ENVIO": "🚚", "CROSS_BORDER": "🌍"}.get(
                    a["tipo_alerta"], "🔔"
                )
                umbral = f" (umbral: {a['umbral_precio']:.2f} €)" if a.get("umbral_precio") else ""
                st.write(f"{icono} **{nombre}**{umbral}")
                if a.get("ultima_activacion"):
                    st.caption(f"Última activación: {a['ultima_activacion']}")
            with col2:
                if st.button("✖", key=f"del_{a['id']}", help="Desactivar alerta"):
                    repo.deactivate(a["id"])
                    st.rerun()
    else:
        st.info("No tienes alertas activas. Las alertas se generan automáticamente cuando detectamos bajadas de precio.")

    st.markdown("---")

    # ── Crear alerta manual ───────────────────────────────────────────────────
    with st.expander("➕ Crear alerta manual"):
        productos = _get_user_productos(usuario.id)
        if not productos:
            st.info("Añade productos a tu lista para poder crear alertas.")
        else:
            with st.form("nueva_alerta"):
                opciones = {f"{p['nombre']} (id {p['id']})": p["id"] for p in productos}
                seleccion = st.selectbox("Producto", list(opciones.keys()))
                umbral = st.number_input(
                    "Avísame si el precio baja de (€)", min_value=0.0, value=0.0, step=0.10,
                    help="Deja en 0 para alertar con cualquier bajada ≥15%."
                )
                if st.form_submit_button("🔔 Crear alerta", type="primary"):
                    repo.create(
                        usuario_id=usuario.id,
                        tipo_alerta="BAJADA_PRECIO",
                        producto_id=opciones[seleccion],
                        umbral_precio=umbral if umbral > 0 else None,
                    )
                    st.success("Alerta creada.")
                    st.rerun()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_price_drops_today(usuario_id: str) -> list[dict]:
    """Devuelve bajadas de precio para los productos de la lista del usuario.

    Usa fuzzy matching entre query_texto y nombres de productos con precio hoy,
    ya que lista_usuario.producto_id suele ser NULL.
    """
    import unicodedata
    from difflib import SequenceMatcher
    from datetime import date
    from utils.config import PRICE_DROP_THRESHOLD

    def norm(t: str) -> str:
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    hoy = str(date.today())

    # Items de la lista del usuario
    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchall()

    if not items:
        return []

    # Precios de hoy con histórico
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

    drops = []
    for item in items:
        query = item["query_texto"]
        qn = norm(query)
        qw = set(qn.split())

        # Mejor coincidencia entre todos los precios de hoy
        best, best_score = None, 0.0
        for p in prices:
            nn = norm(p["producto_nombre"])
            sim = SequenceMatcher(None, qn, nn).ratio()
            ov = len(qw & set(nn.split()))
            total = sim + (ov / max(len(qw), 1)) * 0.30
            if total > best_score:
                best_score, best = total, p

        if best is None or best_score < 0.40:
            continue

        # Mediana histórica de ese producto (últimos 30 días excluyendo hoy)
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
            continue

        precios_hist = sorted(float(r["precio"]) for r in hist)
        mediana = precios_hist[len(precios_hist) // 2]
        precio_hoy = float(best["precio_hoy"])

        if mediana == 0:
            continue

        if (mediana - precio_hoy) / mediana >= PRICE_DROP_THRESHOLD:
            drops.append({
                "producto_nombre":     best["producto_nombre"],
                "supermercado_nombre": best["supermercado_nombre"],
                "precio_hoy":          precio_hoy,
                "precio_habitual":     round(mediana, 2),
                "cantidad":            item["cantidad"],
            })

    return sorted(drops, key=lambda x: x["precio_habitual"] - x["precio_hoy"], reverse=True)


def _get_user_productos(usuario_id: str) -> list[dict]:
    """Devuelve los productos de hoy que mejor coinciden con la lista del usuario."""
    import unicodedata
    from difflib import SequenceMatcher
    from datetime import date

    def norm(t: str) -> str:
        return unicodedata.normalize("NFD", t).encode("ascii", "ignore").decode().lower().strip()

    hoy = str(date.today())
    with get_connection() as conn:
        items = conn.execute(
            "SELECT query_texto FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchall()
        prices = conn.execute(
            """
            SELECT DISTINCT p.id, p.nombre
            FROM precios_historicos ph
            JOIN productos p ON p.id = ph.producto_id
            WHERE ph.fecha_scraping = %s
            """,
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

    # deduplicate
    seen = set()
    unique = []
    for r in result:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append(r)

    return unique
