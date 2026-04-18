"""Savings panel page — diseño premium Smart Shopping Iberia."""
import streamlit as st
import plotly.express as px
import pandas as pd

from domain.models import Usuario
from optimizer.savings_calculator import get_savings_summary, get_weekly_trend, get_annual_projection
from optimizer.bulk_detector import detect_bulk_opportunities
from ui.styles import page_header, section_header, empty_state, savings_hero, metric_cards


def mostrar(usuario: Usuario) -> None:
    page_header(
        "Panel de ahorro",
        subtitle="Seguimiento de tus ahorros reales semana a semana.",
        emoji="💰",
    )

    savings = get_savings_summary(usuario.id)

    # ── Hero — ahorro anual en grande ──────────────────────────────────────────
    savings_hero(savings["anual"], "Ahorro acumulado del año")

    # ── Tarjetas de períodos ───────────────────────────────────────────────────
    metric_cards([
        {"icon": "📅", "value": f"{savings['diario']:.2f} €",  "label": "Hoy"},
        {"icon": "📆", "value": f"{savings['semanal']:.2f} €", "label": "Esta semana"},
        {"icon": "🗓️", "value": f"{savings['mensual']:.2f} €", "label": "Este mes"},
        {"icon": "🏆", "value": f"{savings['anual']:.2f} €",   "label": "Este año",
         "color": "#52B788"},
    ])

    proyeccion = get_annual_projection(usuario.id)
    if proyeccion:
        st.markdown(
            f'<div style="background:#EEF7F3;border-radius:10px;padding:14px 18px;'
            f'margin:18px 0;border-left:4px solid #52B788">'
            f'  <span style="font-weight:700;color:#1B4332">📈 Proyección anual</span> '
            f'  basada en el último mes: '
            f'  <b style="font-size:1.1rem;color:#1B4332">{proyeccion:.2f} €</b>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # ── Logros / achievements ─────────────────────────────────────────────────
    _render_logros(usuario.id, savings)

    # ── Gráfica de evolución semanal ──────────────────────────────────────────
    section_header("📈 Evolución semanal")
    trend = get_weekly_trend(usuario.id)
    if trend:
        df  = pd.DataFrame(trend)
        fig = px.bar(
            df,
            x="semana",
            y=["gastado", "ahorrado"],
            labels={"value": "€", "semana": "Semana", "variable": ""},
            color_discrete_map={"gastado": "#DEE2E6", "ahorrado": "#52B788"},
            barmode="group",
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_family="Inter, sans-serif",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            xaxis=dict(showgrid=False),
            yaxis=dict(gridcolor="#F0F0F0"),
            margin=dict(t=40, b=0, l=0, r=0),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        empty_state(
            "📊",
            "Sin datos de evolución aún",
            "Registra tus compras en el <b>🗺️ Optimizador</b> para ver la gráfica.",
        )

    # ── Oportunidades de acopio ───────────────────────────────────────────────
    section_header("📦 Oportunidades de acopio", "No perecederos con descuento ≥15%")

    opps = detect_bulk_opportunities(usuario.id)
    if opps:
        cards_html = []
        for opp in opps:
            cards_html.append(
                f'<div style="background:white;border-radius:12px;padding:16px 20px;'
                f'box-shadow:0 2px 12px rgba(0,0,0,.07);border:1px solid #E9ECEF;'
                f'margin-bottom:10px;display:flex;align-items:center;gap:16px">'
                f'  <div style="min-width:58px;text-align:center;background:#FFF3CD;'
                f'      border-radius:9px;padding:8px 4px">'
                f'    <div style="font-size:1.1rem;font-weight:800;color:#856404">'
                f'        -{opp["descuento_pct"]}%</div>'
                f'    <div style="font-size:.62rem;color:#856404;font-weight:600;'
                f'         text-transform:uppercase">oferta</div>'
                f'  </div>'
                f'  <div style="flex:1">'
                f'    <div style="font-weight:700;font-size:.92rem">{opp["producto_nombre"]}</div>'
                f'    <div style="font-size:.78rem;color:#6C757D">📍 {opp["supermercado_nombre"]}'
                f'        · Compra {opp["unidades_sugeridas"]} uds.</div>'
                f'  </div>'
                f'  <div style="text-align:right">'
                f'    <div style="font-weight:800;color:#52B788;font-size:1.05rem">'
                f'        {opp["precio_hoy"]:.2f} €</div>'
                f'    <div style="font-size:.75rem;color:#ADB5BD;text-decoration:line-through">'
                f'        {opp["precio_habitual"]:.2f} €</div>'
                f'    <div style="font-size:.78rem;font-weight:700;color:#1B4332;margin-top:3px">'
                f'        Ahorra {opp["ahorro_potencial"]:.2f} €</div>'
                f'  </div>'
                f'</div>'
            )
        st.markdown("".join(cards_html), unsafe_allow_html=True)
    else:
        empty_state("📦", "Sin oportunidades de acopio hoy", "Vuelve cuando los precios bajen ≥15%.")

    # ── Historial de sesiones ─────────────────────────────────────────────────
    section_header("🗓️ Últimas compras registradas")
    _render_historial(usuario.id)


def _render_logros(usuario_id: str, savings: dict) -> None:
    """Tarjetas de logros basadas en el historial real."""
    from database.connection import get_connection

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT fecha, total_ahorrado FROM sesiones_compra "
            "WHERE usuario_id = %s ORDER BY fecha DESC",
            (usuario_id,),
        ).fetchall()

    if not rows:
        return

    mejor_semana   = max((float(r["total_ahorrado"]) for r in rows), default=0)
    racha          = len(rows)
    total_ahorrado = sum(float(r["total_ahorrado"]) for r in rows)

    logros = [
        {
            "icon": "🏆",
            "title": "Mejor sesión",
            "value": f"{mejor_semana:.2f} €",
            "sub": "máximo ahorro en una compra",
        },
        {
            "icon": "🎯",
            "title": "Compras optimizadas",
            "value": str(racha),
            "sub": "sesiones registradas en total",
        },
        {
            "icon": "💎",
            "title": "Ahorro total",
            "value": f"{total_ahorrado:.2f} €",
            "sub": "ahorrado con Smart Shopping",
        },
    ]

    section_header("🏅 Tus logros")
    cols = st.columns(len(logros))
    for col, lg in zip(cols, logros):
        with col:
            st.markdown(
                f'<div style="background:white;border-radius:12px;padding:18px 16px;'
                f'box-shadow:0 2px 12px rgba(0,0,0,.07);border:1px solid #E9ECEF;text-align:center">'
                f'  <div style="font-size:1.8rem;margin-bottom:8px">{lg["icon"]}</div>'
                f'  <div style="font-size:1.3rem;font-weight:800;color:#1B4332">{lg["value"]}</div>'
                f'  <div style="font-size:.8rem;font-weight:700;color:#2D6A4F;margin-top:4px">'
                f'      {lg["title"]}</div>'
                f'  <div style="font-size:.73rem;color:#6C757D;margin-top:3px">{lg["sub"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def _render_historial(usuario_id: str) -> None:
    from database.connection import get_connection
    import json

    with get_connection() as conn:
        rows = conn.execute(
            "SELECT fecha, supermercados_visitados, total_gastado, "
            "       total_ahorrado, productos_comprados "
            "FROM sesiones_compra "
            "WHERE usuario_id = %s "
            "ORDER BY fecha DESC LIMIT 10",
            (usuario_id,),
        ).fetchall()

    if not rows:
        empty_state(
            "🗓️",
            "Sin compras registradas",
            "Usa el <b>🗺️ Optimizador</b> y pulsa <b>Registrar esta compra</b> al terminar.",
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

        gastado  = float(r["total_gastado"])
        ahorrado = float(r["total_ahorrado"])

        with st.expander(
            f"📅 {r['fecha']} — {gastado:.2f} € gastados · {ahorrado:.2f} € ahorrados"
        ):
            st.caption(f"Supermercados: {supers_str}")
            if productos:
                for p in productos:
                    st.write(
                        f"• {p.get('nombre','?')} ×{p.get('cantidad',1)} — "
                        f"**{float(p.get('precio_total',0)):.2f} €** "
                        f"({p.get('supermercado','')})"
                    )
