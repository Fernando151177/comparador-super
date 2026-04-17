"""Saturday optimizer page."""
import streamlit as st

from domain.models import Usuario
from optimizer.saturday_optimizer import optimize_for_user
from ordering.supermarket_links import get_info, build_search_url


def mostrar(usuario: Usuario) -> None:
    st.title("🗺️ Optimizador del sábado")
    st.caption("Calculamos dónde comprar cada producto para gastar lo mínimo.")

    pais_options = {"🇪🇸 España": "ES", "🇵🇹 Portugal": "PT", "🌍 Ambos": "AMBOS"}
    pais_label = st.radio(
        "Supermercados a considerar",
        list(pais_options.keys()),
        horizontal=True,
        index={"ES": 0, "PT": 1, "AMBOS": 2}.get(usuario.pais_activo, 0),
    )
    pais = pais_options[pais_label]

    if st.button("⚡ Calcular plan óptimo", type="primary"):
        with st.spinner("Calculando…"):
            result = optimize_for_user(usuario.id, pais)
        _render_result(result)
    else:
        st.info("Pulsa el botón para calcular el plan de compra optimizado con los precios de hoy.")


def _render_result(result) -> None:
    if not result.plan and not result.productos_sin_precio:
        st.warning("Tu lista está vacía. Añade productos en **📋 Mi lista**.")
        return

    # ── Summary metrics ───────────────────────────────────────────────────────
    col1, col2, col3 = st.columns(3)
    col1.metric("Total óptimo", f"{result.total_optimo:.2f} €")
    col2.metric("Ahorro vs. un solo super", f"{result.ahorro_total:.2f} €",
                delta_color="inverse" if result.ahorro_total > 0 else "off")
    col3.metric("Supermercados a visitar", len(result.por_supermercado))

    if result.total_si_uno:
        st.markdown("---")
        st.markdown("**¿Cuánto gastarías comprando TODO en un único supermercado?**")
        cols = st.columns(len(result.total_si_uno))
        for col, (codigo, total) in zip(cols, sorted(result.total_si_uno.items(), key=lambda x: x[1])):
            info = get_info(codigo)
            nombre = info["nombre"] if info else codigo
            col.metric(nombre, f"{total:.2f} €")

    st.markdown("---")

    # ── Plan grouped by supermarket ───────────────────────────────────────────
    for codigo, items in result.por_supermercado.items():
        info = get_info(codigo)
        nombre = info["nombre"] if info else codigo
        subtotal = sum(i.precio_total for i in items)

        with st.expander(f"🏪 **{nombre}** — {len(items)} productos — {subtotal:.2f} €", expanded=True):
            for item in items:
                url = build_search_url(codigo, item.producto_nombre)
                link = f" [(ver)]({url})" if url else ""
                pkilo = f" · {item.precio_kilo:.2f} €/kg" if item.precio_kilo else ""
                col1, col2 = st.columns([5, 2])
                with col1:
                    st.write(
                        f"**{item.query_texto}** ×{item.cantidad}{link}  \n"
                        f"_{item.producto_nombre}_{pkilo}"
                    )
                with col2:
                    st.write(f"**{item.precio_total:.2f} €**")
                    if item.ahorro_vs_caro > 0:
                        st.caption(f"Ahorras {item.ahorro_vs_caro:.2f} €")

    # ── Items with no price ───────────────────────────────────────────────────
    if result.productos_sin_precio:
        st.warning(
            f"Sin precio hoy: {', '.join(result.productos_sin_precio)}. "
            "Actualiza los precios en **📋 Mi lista**."
        )
