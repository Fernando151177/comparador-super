"""Saturday optimizer page — modos habitual y oportunidad."""
import json
from datetime import date

import streamlit as st

from database.connection import get_connection
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

    if favoritos and modo_key == "habitual":
        nombres_fav = [get_info(c)["nombre"] for c in favoritos if get_info(c)]
        st.caption(f"Supermercados habituales: {', '.join(nombres_fav)}")

    st.markdown("---")

    col_calc, col_clear = st.columns([3, 1])
    with col_calc:
        calcular = st.button(
            "⚡ Calcular plan óptimo", type="primary", use_container_width=True
        )
    with col_clear:
        if st.button("🔄 Limpiar", use_container_width=True):
            st.session_state.pop("opt_result", None)
            st.session_state.pop("opt_meta", None)
            st.rerun()

    if calcular:
        with st.spinner("Calculando…"):
            result = optimize_for_user(
                usuario.id,
                pais=pais,
                modo=modo_key,
                favoritos=favoritos,
                coste_desplazamiento=coste_km,
            )
        st.session_state["opt_result"] = result
        st.session_state["opt_meta"] = {
            "favoritos": favoritos,
            "coste_km": coste_km,
            "usuario_id": usuario.id,
        }
        st.session_state.pop("opt_registrado", None)
        st.rerun()

    if "opt_result" in st.session_state:
        _render_result(
            st.session_state["opt_result"],
            st.session_state["opt_meta"]["favoritos"],
            st.session_state["opt_meta"]["coste_km"],
            st.session_state["opt_meta"]["usuario_id"],
        )
    else:
        st.info("Pulsa el botón para calcular el plan de compra optimizado con los precios de hoy.")


# ── Render resultado ──────────────────────────────────────────────────────────

def _render_result(result, favoritos: list[str], coste_km: float, usuario_id: str) -> None:
    if not result.plan and not result.productos_sin_precio:
        st.warning("Tu lista está vacía. Añade productos en **📋 Mi lista**.")
        return

    n_supers = len(result.por_supermercado)
    n_extras = len(set(result.por_supermercado.keys()) - set(favoritos))
    coste_extra = round(n_extras * coste_km, 2)

    ahorro_neto = get_displacement_adjusted_savings(
        total_ahorrado=result.ahorro_total,
        supermercados_visitados=n_supers,
        favoritos_visitados=n_supers - n_extras,
        coste_desplazamiento=coste_km,
    )

    # ── Métricas ──────────────────────────────────────────────────────────────
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
    )

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
                c1, c2 = st.columns([5, 2])
                with c1:
                    st.write(
                        f"**{item.query_texto}** ×{item.cantidad}{link}  \n"
                        f"_{item.producto_nombre}_{pkilo}"
                    )
                with c2:
                    st.write(f"**{item.precio_total:.2f} €**")
                    if item.ahorro_vs_caro > 0:
                        st.caption(f"Ahorras {item.ahorro_vs_caro:.2f} €")

    if result.productos_sin_precio:
        st.warning(
            f"Sin precio hoy: {', '.join(result.productos_sin_precio)}. "
            "Actualiza los precios en **📋 Mi lista**."
        )

    # ── Registrar compra ──────────────────────────────────────────────────────
    st.markdown("---")
    _render_registro(result, ahorro_neto, usuario_id)


def _render_registro(result, ahorro_neto: float, usuario_id: str) -> None:
    """Sección para registrar la compra en el historial."""

    if st.session_state.get("opt_registrado"):
        st.success("✅ Compra registrada. El panel de ahorro ya refleja este gasto.")
        return

    st.subheader("💾 Registrar esta compra")
    st.caption(
        "Guarda esta sesión en tu historial para que el panel de ahorro "
        "acumule tus estadísticas reales."
    )

    with st.form("registrar_compra"):
        marcar_comprados = st.checkbox(
            "Marcar todos los productos como comprados en mi lista",
            value=True,
            help="Los productos se moverán a la sección 'Comprados' de tu lista.",
        )
        confirmar = st.form_submit_button("✅ Registrar compra", type="primary")

    if confirmar:
        _guardar_sesion(result, ahorro_neto, usuario_id, marcar_comprados)
        st.session_state["opt_registrado"] = True
        st.rerun()


def _guardar_sesion(result, ahorro_neto: float, usuario_id: str, marcar_comprados: bool) -> None:
    """Inserta una fila en sesiones_compra y opcionalmente marca items comprados."""
    supers_visitados = list(result.por_supermercado.keys())
    productos = [
        {
            "nombre": item.query_texto,
            "producto": item.producto_nombre,
            "cantidad": item.cantidad,
            "precio_total": item.precio_total,
            "supermercado": item.supermercado_codigo,
        }
        for item in result.plan
    ]

    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO sesiones_compra
                (usuario_id, fecha, supermercados_visitados,
                 total_gastado, total_ahorrado, productos_comprados)
            VALUES (%s, %s, %s::jsonb, %s, %s, %s::jsonb)
            """,
            (
                usuario_id,
                str(date.today()),
                json.dumps(supers_visitados),
                result.total_optimo,
                ahorro_neto,
                json.dumps(productos),
            ),
        )

        if marcar_comprados:
            queries = [item.query_texto for item in result.plan]
            for q in queries:
                conn.execute(
                    "UPDATE lista_usuario SET comprado = TRUE "
                    "WHERE usuario_id = %s AND query_texto = %s AND comprado = FALSE",
                    (usuario_id, q),
                )
