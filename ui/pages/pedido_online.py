"""Online order page — Sprint 3."""
import streamlit as st

from domain.models import Usuario
from ordering.supermarket_links import get_by_pais, get_info, build_search_url
from ordering.cart_builder import build_cart_links, format_cart_text
from database.connection import get_connection


def mostrar(usuario: Usuario) -> None:
    st.title("🛍️ Pedido online")
    st.caption("Accede directamente a la tienda online de cada supermercado. No almacenamos datos de pago ni credenciales.")

    supers = [s for s in get_by_pais(usuario.pais_activo) if s.get("online_url")]

    if not supers:
        st.info("No hay supermercados con tienda online para tu zona.")
        return

    # Pick supermarket
    nombres = [s["nombre"] for s in supers]
    codigos = [s["codigo"] for s in supers]
    idx = st.selectbox("Selecciona supermercado", range(len(nombres)),
                       format_func=lambda i: nombres[i])
    codigo = codigos[idx]
    info = get_info(codigo)

    # Delivery info
    col1, col2, col3 = st.columns(3)
    col1.metric("Pedido mínimo",
                f"{info['min_order_eur']:.2f} €" if info["min_order_eur"] else "Sin mínimo")
    col2.metric("Envío",
                f"{info['delivery_eur']:.2f} €" if info["delivery_eur"] else "Consultar")
    col3.metric("Click & Collect",
                "✅ Sí" if info["click_collect"] else "❌ No")

    if info.get("notes"):
        st.caption(info["notes"])

    st.markdown("---")

    # Generate links for the user's shopping list
    items = _load_items(usuario.id)
    if not items:
        st.info("Tu lista está vacía. Añade productos en **📋 Mi lista**.")
        return

    links = build_cart_links(codigo, items)
    st.subheader(f"Tu lista para {info['nombre']}")

    for link in links:
        col1, col2 = st.columns([5, 2])
        with col1:
            st.write(f"×{link['cantidad']} **{link['producto']}**")
        with col2:
            if link["url"]:
                st.link_button("Buscar →", link["url"])

    st.markdown("---")
    cart_text = format_cart_text(codigo, items)
    st.download_button(
        "⬇️ Descargar lista como texto",
        data=cart_text,
        file_name=f"lista_{info['nombre'].lower().replace(' ', '_')}.txt",
        mime="text/plain",
    )

    if info.get("online_url"):
        st.link_button(f"🛒 Ir a la tienda de {info['nombre']}", info["online_url"],
                       use_container_width=True, type="primary")


def _load_items(usuario_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT query_texto AS producto_nombre, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE ORDER BY query_texto",
            (usuario_id,),
        ).fetchall()
    return [dict(r) for r in rows]
