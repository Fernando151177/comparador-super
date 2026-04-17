"""Saturday optimizer page — modos habitual y oportunidad."""
import streamlit as st

from domain.models import Usuario
from optimizer.saturday_optimizer import optimize_for_user
from optimizer.savings_calculator import get_displacement_adjusted_savings
from ordering.supermarket_links import get_info, build_search_url


def mostrar(usuario: Usuario) -> None:
    st.title("🗺️ Optimizador del sábado")
    st.caption("Calculamos dónde comprar cada producto para gastar lo mínimo.")

    favoritos = usuario.supermercados_favoritos
    coste_km = usuario.coste_desplazamiento

    # ── Selector de modo ──────────────────────────────────────────────────────
    col_modo, col_pais = st.columns([3, 2])

    with col_modo:
        if favoritos:
            modo = st.radio(
                "Modo de optimización",
                ["🏠 Habitual", "🔍 Oportunidad"],
                horizontal=True,
                help=(
                    "**Habitual**: solo tus supermercados favoritos.\n\n"
                    "**Oportunidad**: todos los supermercados, "
                    f"descontando {coste_km:.2f} € por cada visita extra."
                ),
            )
            modo_key = "habitual" if "Habitual" in modo else "oportunidad"
        else:
            st.info(
                "💡 Define tus supermercados favoritos en **👤 Mi perfil** "
                "para activar el modo Habitual."
            )
            modo_key = "oportunidad"

    with col_pais:
        pais_options = {"🇪🇸 España": "ES", "🇵🇹 Portugal": "PT", "🌍 Ambos": "AMBOS"}
        pais_label = st.radio(
            "Supermercados a considerar",
            list(pais_options.keys()),
            horizontal=True,
            index={"ES": 0, "PT": 1, "AMBOS": 2}.get(usuario.pais_activo, 0),
        )
        pais = pais_options[pais_label]

    # Mostrar favoritos activos
    if favoritos and modo_key == "habitual":
        nombres_fav = [
            get_info(c)["nombre"] for c in favoritos if get_info(c)
        ]
        st.caption(f"Supermercados habituales: {', '.join(nombres_fav)}")

    st.markdown("---")

    if st.button("⚡ Calcular plan óptimo", type="primary", use_container_width=True):
        with st.spinner("Calculando…"):
            result = optimize_for_user(
                usuario.id,
                pais=pais,
                modo=modo_key,
                favoritos=favoritos,
                coste_desplazamiento=coste_km,
            )
        _render_result(result, favoritos, coste_km)
    else:
        st.info("Pulsa el botón para calcular el plan de compra optimizado con los precios de hoy.")


def _render_result(result, favoritos: list[str], coste_km: float) -> None:
    if not result.plan and not result.productos_sin_precio:
        st.warning("Tu lista está vacía. Añade productos en **📋 Mi lista**.")
        return

    # ── Métricas principales ──────────────────────────────────────────────────
    n_supers = len(result.por_supermercado)
    n_extras = len(set(result.por_supermercado.keys()) - set(favoritos))
    coste_extra = round(n_extras * coste_km, 2)

    ahorro_neto = get_displacement_adjusted_savings(
        total_ahorrado=result.ahorro_total,
        supermercados_visitados=n_supers,
        favoritos_visitados=n_supers - n_extras,
        coste_desplazamiento=coste_km,
    )

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total óptimo", f"{result.total_optimo:.2f} €")
    col2.metric("Supermercados", n_supers)
    col3.metric(
        "Ahorro bruto",
        f"{result.ahorro_total:.2f} €",
        help="Diferencia vs. comprar todo en el supermercado más caro.",
    )
    col4.metric(
        "Ahorro neto",
        f"{ahorro_neto:.2f} €",
        delta=f"-{coste_extra:.2f} € desplazamiento" if coste_extra > 0 else None,
        delta_color="inverse" if coste_extra > 0 else "off",
        help="Ahorro bruto menos coste de desplazamiento a supermercados extra.",
    )

    # Aviso si el ahorro neto no justifica ir a otro supermercado
    if coste_extra > 0 and ahorro_neto <= 0:
        st.warning(
            f"⚠️ El ahorro de precios ({result.ahorro_total:.2f} €) no compensa "
            f"el coste de desplazamiento ({coste_extra:.2f} €). "
            "Considera comprar todo en un único supermercado."
        )

    if result.total_si_uno:
        st.markdown("---")
        st.markdown("**¿Cuánto gastarías comprando TODO en un único supermercado?**")
        cols = st.columns(len(result.total_si_uno))
        for col, (codigo, total) in zip(cols, sorted(result.total_si_uno.items(), key=lambda x: x[1])):
            info = get_info(codigo)
            nombre = info["nombre"] if info else codigo
            es_fav = "⭐ " if codigo in favoritos else ""
            col.metric(f"{es_fav}{nombre}", f"{total:.2f} €")

    st.markdown("---")

    # ── Plan por supermercado ─────────────────────────────────────────────────
    for codigo, items in result.por_supermercado.items():
        info = get_info(codigo)
        nombre = info["nombre"] if info else codigo
        subtotal = sum(i.precio_total for i in items)
        es_fav = "⭐ " if codigo in favoritos else ""
        es_extra = " *(desplazamiento extra)*" if codigo not in favoritos and favoritos else ""

        with st.expander(
            f"🏪 {es_fav}**{nombre}**{es_extra} — {len(items)} productos — {subtotal:.2f} €",
            expanded=True,
        ):
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

    # ── Sin precio ────────────────────────────────────────────────────────────
    if result.productos_sin_precio:
        st.warning(
            f"Sin precio hoy: {', '.join(result.productos_sin_precio)}. "
            "Actualiza los precios en **📋 Mi lista**."
        )
