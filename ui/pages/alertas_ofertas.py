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
    """Devuelve bajadas de precio ≥15% para los productos de la lista del usuario."""
    from datetime import date
    from utils.config import PRICE_DROP_THRESHOLD

    hoy = str(date.today())
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT lu.cantidad,
                   p.nombre AS producto_nombre,
                   s.nombre AS supermercado_nombre,
                   ph.precio AS precio_hoy,
                   ph.supermercado_id,
                   lu.producto_id
            FROM lista_usuario lu
            JOIN precios_historicos ph ON ph.producto_id = lu.producto_id
                                     AND ph.fecha_scraping = %s
            JOIN productos p ON p.id = lu.producto_id
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE lu.usuario_id = %s
              AND lu.comprado = FALSE
              AND lu.producto_id IS NOT NULL
            ORDER BY p.nombre
            """,
            (hoy, usuario_id),
        ).fetchall()

    drops = []
    for row in rows:
        # Mediana histórica (últimos 30 días antes de hoy)
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
            continue

        precios = sorted(float(r["precio"]) for r in hist)
        mediana = precios[len(precios) // 2]
        precio_hoy = float(row["precio_hoy"])

        if mediana == 0:
            continue

        if (mediana - precio_hoy) / mediana >= PRICE_DROP_THRESHOLD:
            drops.append({
                "producto_nombre":   row["producto_nombre"],
                "supermercado_nombre": row["supermercado_nombre"],
                "precio_hoy":        precio_hoy,
                "precio_habitual":   round(mediana, 2),
                "cantidad":          row["cantidad"],
            })

    return sorted(drops, key=lambda x: x["precio_habitual"] - x["precio_hoy"], reverse=True)


def _get_user_productos(usuario_id: str) -> list[dict]:
    """Productos vinculados a la lista del usuario (con producto_id asignado)."""
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT lu.producto_id AS id, p.nombre
            FROM lista_usuario lu
            JOIN productos p ON p.id = lu.producto_id
            WHERE lu.usuario_id = %s
              AND lu.producto_id IS NOT NULL
              AND lu.comprado = FALSE
            ORDER BY p.nombre
            """,
            (usuario_id,),
        ).fetchall()
    return [dict(r) for r in rows]
