"""Savings panel page."""
import streamlit as st
import plotly.express as px
import pandas as pd

from domain.models import Usuario
from optimizer.savings_calculator import get_savings_summary, get_weekly_trend, get_annual_projection
from optimizer.bulk_detector import detect_bulk_opportunities


def mostrar(usuario: Usuario) -> None:
    st.title("💰 Panel de ahorro")

    # ── Summary metrics ───────────────────────────────────────────────────────
    savings = get_savings_summary(usuario.id)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Hoy",    f"{savings['diario']:.2f} €")
    col2.metric("Semana", f"{savings['semanal']:.2f} €")
    col3.metric("Mes",    f"{savings['mensual']:.2f} €")
    col4.metric("Año",    f"{savings['anual']:.2f} €")

    proyeccion = get_annual_projection(usuario.id)
    if proyeccion:
        st.info(f"📈 Proyección anual basada en el último mes: **{proyeccion:.2f} €**")

    # ── Weekly trend chart ────────────────────────────────────────────────────
    trend = get_weekly_trend(usuario.id)
    if trend:
        st.markdown("---")
        st.subheader("Evolución semanal")
        df = pd.DataFrame(trend)
        fig = px.bar(
            df, x="semana", y=["gastado", "ahorrado"],
            labels={"value": "€", "semana": "Semana", "variable": ""},
            color_discrete_map={"gastado": "#e74c3c", "ahorrado": "#2ecc71"},
            barmode="group",
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Aún no hay historial de compras. Registra tus compras en el optimizador.")

    # ── Bulk opportunities ────────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("📦 Oportunidades de acopio")
    st.caption("No perecederos con descuento ≥15% respecto a su precio habitual.")

    opps = detect_bulk_opportunities(usuario.id)
    if opps:
        for opp in opps:
            st.success(
                f"**{opp['producto_nombre']}** en {opp['supermercado_nombre']} — "
                f"{opp['precio_hoy']:.2f} € (habitual {opp['precio_habitual']:.2f} €) — "
                f"**{opp['descuento_pct']}% dto.** — "
                f"Compra {opp['unidades_sugeridas']} unidades y ahorra {opp['ahorro_potencial']:.2f} €"
            )
    else:
        st.info("No hay oportunidades de acopio destacadas hoy.")

    # ── Historial de sesiones ─────────────────────────────────────────────────
    st.markdown("---")
    st.subheader("🗓️ Últimas compras registradas")
    _render_historial(usuario.id)


def _render_historial(usuario_id: str) -> None:
    from database.connection import get_connection
    import json

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT fecha, supermercados_visitados, total_gastado,
                   total_ahorrado, productos_comprados
            FROM sesiones_compra
            WHERE usuario_id = %s
            ORDER BY fecha DESC
            LIMIT 10
            """,
            (usuario_id,),
        ).fetchall()

    if not rows:
        st.info(
            "Aún no hay compras registradas. Usa el **🗺️ Optimizador** y pulsa "
            "**Registrar esta compra** al terminar."
        )
        return

    for r in rows:
        supers = r["supermercados_visitados"] or []
        if isinstance(supers, str):
            try:
                supers = json.loads(supers)
            except Exception:
                supers = []
        supers_str = ", ".join(supers) if supers else "—"

        productos = r["productos_comprados"] or []
        if isinstance(productos, str):
            try:
                productos = json.loads(productos)
            except Exception:
                productos = []

        with st.expander(
            f"📅 {r['fecha']} — {float(r['total_gastado']):.2f} € gastados · "
            f"{float(r['total_ahorrado']):.2f} € ahorrados"
        ):
            st.caption(f"Supermercados: {supers_str}")
            if productos:
                for p in productos:
                    st.write(
                        f"• {p.get('nombre', '?')} ×{p.get('cantidad', 1)} — "
                        f"**{float(p.get('precio_total', 0)):.2f} €** "
                        f"({p.get('supermercado', '')})"
                    )
