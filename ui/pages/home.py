"""Home / dashboard page."""
import streamlit as st
import pandas as pd

from database.repositories.precios_repo import PreciosRepo
from database.connection import get_connection
from domain.models import Usuario


def mostrar(usuario: Usuario) -> None:
    st.title("🛒 Smart Shopping Iberia")
    st.caption(f"Hola, **{usuario.nombre}** · {_pais_label(usuario.pais_activo)}")

    # ── Quick metrics ─────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    n_lista = _count_lista(usuario.id)
    precios_hoy = PreciosRepo().get_today(pais=usuario.pais_activo)
    n_alertas = _count_alertas(usuario.id)

    col1.metric("En tu lista", n_lista, help="Productos en tu lista de la compra")
    col2.metric("Precios de hoy", len(precios_hoy), help="Precios scrapeados hoy")
    col3.metric("Alertas activas", n_alertas, help="Bajadas de precio pendientes")
    col4.metric("Supermercados", _count_active_supers(), help="Supermercados con precios hoy")

    st.markdown("---")

    # ── Price table ───────────────────────────────────────────────────────────
    if precios_hoy:
        st.subheader("Precios de hoy")
        st.caption("El precio más barato de cada producto aparece resaltado en verde.")
        _render_price_table(precios_hoy)
    else:
        st.info(
            "No hay precios para hoy. Ve a **📋 Mi lista** y pulsa "
            "**Actualizar precios** para consultar los supermercados."
        )


def _render_price_table(prices: list[dict]) -> None:
    df = pd.DataFrame(prices)
    if df.empty:
        return

    pivot = df.pivot_table(
        index="producto_nombre",
        columns="supermercado_nombre",
        values="precio",
        aggfunc="min",
    ).round(2)

    pivot["Mín (€)"] = pivot.min(axis=1)
    pivot["Más barato"] = pivot.drop(columns="Mín (€)").idxmin(axis=1)
    supers = [c for c in pivot.columns if c not in ("Mín (€)", "Más barato")]

    def _highlight(row):
        styles = []
        vals = [row[s] for s in supers if pd.notna(row.get(s))]
        minval = min(vals) if vals else None
        for col in pivot.columns:
            if col in supers and pd.notna(row.get(col)) and row[col] == minval:
                styles.append("background-color:#d4edda;color:#155724;font-weight:bold")
            else:
                styles.append("")
        return styles

    styled = pivot.style.apply(_highlight, axis=1).format(
        {s: "{:.2f} €" for s in supers} | {"Mín (€)": "{:.2f} €"},
        na_rep="—",
    )
    st.dataframe(styled, use_container_width=True)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pais_label(pais: str) -> str:
    return {"ES": "🇪🇸 España", "PT": "🇵🇹 Portugal", "AMBOS": "🌍 ES + PT"}.get(pais, pais)


def _count_lista(usuario_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM lista_usuario WHERE usuario_id = %s AND comprado = FALSE",
            (usuario_id,),
        ).fetchone()
    return row["n"] if row else 0


def _count_alertas(usuario_id: str) -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM alertas WHERE usuario_id = %s AND activa = TRUE",
            (usuario_id,),
        ).fetchone()
    return row["n"] if row else 0


def _count_active_supers() -> int:
    from datetime import date
    hoy = str(date.today())
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT supermercado_id) AS n FROM precios_historicos WHERE fecha_scraping = %s",
            (hoy,),
        ).fetchone()
    return row["n"] if row else 0
