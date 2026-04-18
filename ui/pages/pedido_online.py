"""Pedido online — diseño premium."""
import streamlit as st

from domain.models import Usuario
from ordering.supermarket_links import get_by_pais, get_info, build_search_url
from ordering.cart_builder import build_cart_links, format_cart_text
from database.connection import get_connection
from ui.styles import page_header, section_header, empty_state


def mostrar(usuario: Usuario) -> None:
    page_header(
        "Pedido online",
        subtitle="Accede a la tienda online de cada supermercado. No guardamos datos de pago.",
        emoji="🛍️",
    )

    supers = [s for s in get_by_pais(usuario.pais_activo) if s.get("online_url")]

    if not supers:
        empty_state("🛒", "Sin tiendas online disponibles",
                    "No hay supermercados con tienda online para tu zona activa.")
        return

    # ── Selector de supermercado ──────────────────────────────────────────────
    nombres = [s["nombre"] for s in supers]
    codigos = [s["codigo"] for s in supers]
    idx = st.selectbox("Selecciona supermercado", range(len(nombres)),
                       format_func=lambda i: nombres[i])
    codigo = codigos[idx]
    info = get_info(codigo)

    # ── Métricas de entrega ───────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Pedido mínimo",
                f"{info['min_order_eur']:.2f} €" if info["min_order_eur"] else "Sin mínimo")
    col2.metric("Envío a domicilio",
                f"{info['delivery_eur']:.2f} €" if info["delivery_eur"] else "Consultar")
    col3.metric("Click & Collect", "✅ Sí" if info["click_collect"] else "❌ No")

    if info.get("notes"):
        st.caption(info["notes"])

    # ── Lista del usuario para este super ─────────────────────────────────────
    section_header(f"🛒 Tu lista para {info['nombre']}")

    items = _load_items(usuario.id)
    if not items:
        empty_state("📋", "Tu lista está vacía",
                    "Añade productos en <b>📋 Mi lista</b> para buscarlos aquí.")
        if info.get("online_url"):
            st.link_button(f"Ir a {info['nombre']} →", info["online_url"],
                           use_container_width=True, type="primary")
        return

    links = build_cart_links(codigo, items)

    cards_html = []
    for link in links:
        link_btn = (
            f'<a href="{link["url"]}" target="_blank" rel="noopener noreferrer" '
            f'style="display:inline-block;background:#1B4332;color:white;text-decoration:none;'
            f'padding:5px 12px;border-radius:6px;font-size:.78rem;font-weight:600">Buscar →</a>'
            if link["url"] else
            '<span style="color:#ADB5BD;font-size:.78rem">sin enlace</span>'
        )
        cards_html.append(
            f'<div style="background:white;border-radius:10px;padding:12px 16px;'
            f'margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;'
            f'box-shadow:0 1px 6px rgba(0,0,0,.06);border:1px solid #F0F0F0">'
            f'  <span style="font-size:.9rem;font-weight:500">'
            f'      ×{link["cantidad"]} <b>{link["producto"]}</b></span>'
            f'  {link_btn}'
            f'</div>'
        )
    st.markdown("".join(cards_html), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_dl, col_go = st.columns(2)
    cart_text = format_cart_text(codigo, items)
    with col_dl:
        st.download_button(
            "⬇️ Descargar lista (.txt)",
            data=cart_text,
            file_name=f"lista_{info['nombre'].lower().replace(' ', '_')}.txt",
            mime="text/plain",
            use_container_width=True,
        )
    with col_go:
        if info.get("online_url"):
            st.link_button(f"🛒 Ir a {info['nombre']}", info["online_url"],
                           use_container_width=True, type="primary")


def _load_items(usuario_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT query_texto AS producto_nombre, cantidad FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE ORDER BY query_texto",
            (usuario_id,),
        ).fetchall()
    return [dict(r) for r in rows]
