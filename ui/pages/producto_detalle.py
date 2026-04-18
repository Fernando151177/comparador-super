"""Ficha de producto — comparativa de precios con barras, imagen, historico.

Se invoca desde lista_compra.py via st.session_state['detalle_producto'].
No es una pagina independiente en el router: se renderiza dentro de lista.
"""
import unicodedata
from datetime import date, timedelta
from difflib import SequenceMatcher
from typing import Optional

import streamlit as st

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from domain.models import Usuario


# ── Utilidades ────────────────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _best_match(query: str, prices: list[dict]) -> Optional[dict]:
    qn = _norm(query)
    qw = set(qn.split())
    best_score, best = 0.0, None
    for p in prices:
        nn = _norm(p["producto_nombre"])
        sim = SequenceMatcher(None, qn, nn).ratio()
        ov = len(qw & set(nn.split()))
        total = sim + (ov / max(len(qw), 1)) * 0.30
        if total > best_score:
            best_score, best = total, p
    return best if best_score >= 0.30 else None


def _bar_html(precio: float, precio_min: float, precio_max: float,
              super_nombre: str, is_min: bool, is_max: bool) -> str:
    """Genera HTML para una fila de barra de precio horizontal."""
    rng = precio_max - precio_min if precio_max > precio_min else 1
    pct = int(((precio - precio_min) / rng) * 70) + 10  # 10-80%
    if is_min:
        color = "#52B788"
        badge = '<span style="color:#1B4332;font-weight:700"> ✓ MÁS BARATO</span>'
    elif is_max:
        color = "#E63946"
        badge = '<span style="color:#E63946"> ✗ MÁS CARO</span>'
    else:
        color = "#74C69D"
        badge = ""

    return f"""
<div style="display:flex;align-items:center;margin:4px 0;gap:8px">
  <span style="width:110px;font-size:0.85rem;text-align:right;white-space:nowrap">
    {super_nombre}
  </span>
  <div style="flex:1;background:#eee;border-radius:4px;height:18px;position:relative">
    <div style="width:{pct}%;background:{color};border-radius:4px;height:100%"></div>
  </div>
  <span style="width:60px;font-weight:bold;font-size:0.9rem">{precio:.2f} €</span>
  {badge}
</div>
"""


# ── Entrada principal ─────────────────────────────────────────────────────────

def mostrar(usuario: Usuario) -> None:
    """Renderiza la ficha de producto.

    Lee 'detalle_producto' de st.session_state:
        {'query': str, 'nombre': str, 'imagen': str | None,
         'marca': str | None, 'categoria': str | None,
         'unidad_medida': str | None, 'precio_base': float | None,
         'precio_kilo': float | None, 'unidad_norm': str | None,
         'super_base': str}
    """
    detalle = st.session_state.get("detalle_producto", {})
    query = detalle.get("query", "")
    if not query:
        st.error("No hay producto seleccionado.")
        return

    if st.button("← Volver a la lista", type="secondary"):
        del st.session_state["detalle_producto"]
        st.rerun()

    st.divider()

    # ── Cargar todos los precios de hoy para este query ───────────────────────
    all_prices_hoy = PreciosRepo().get_today(pais=usuario.pais_activo)
    supers = sorted({p["supermercado_nombre"] for p in all_prices_hoy})

    # Mejor coincidencia por supermercado
    matches: dict[str, dict] = {}
    for s in supers:
        pool = [p for p in all_prices_hoy if p["supermercado_nombre"] == s]
        m = _best_match(query, pool)
        if m:
            matches[s] = m

    # Usar el match del supermercado base (o el primero disponible) para metadata
    base_super = detalle.get("super_base", "")
    meta = matches.get(base_super) or (next(iter(matches.values())) if matches else None)

    # ── CABECERA ──────────────────────────────────────────────────────────────
    img_url = detalle.get("imagen") or (meta["url_imagen"] if meta else None)
    nombre_real = meta["producto_nombre"] if meta else query
    marca = detalle.get("marca") or (meta.get("marca") if meta else None)
    categoria = detalle.get("categoria") or (meta.get("categoria") if meta else None)
    unidad_medida = detalle.get("unidad_medida") or (meta.get("unidad_medida") if meta else None)

    col_img, col_info = st.columns([1, 2], gap="large")

    with col_img:
        if img_url:
            try:
                st.image(img_url, width=220)
            except Exception:
                st.markdown(
                    "<div style='width:220px;height:220px;background:#f0f0f0;"
                    "border-radius:8px;display:flex;align-items:center;"
                    "justify-content:center;font-size:3rem'>🛒</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<div style='width:220px;height:220px;background:#f0f0f0;"
                "border-radius:8px;display:flex;align-items:center;"
                "justify-content:center;font-size:3rem'>🛒</div>",
                unsafe_allow_html=True,
            )

    with col_info:
        st.markdown(f"## {nombre_real}")
        if marca:
            st.caption(f"Marca: **{marca}**")
        tags = []
        if categoria:
            tags.append(f"📂 {categoria}")
        if unidad_medida:
            tags.append(f"📦 {unidad_medida}")
        if tags:
            st.caption("  ·  ".join(tags))

        st.markdown("---")

        # ── PRECIO PRINCIPAL ──────────────────────────────────────────────────
        precio_base = detalle.get("precio_base")
        precio_kilo = detalle.get("precio_kilo")
        unidad_norm = detalle.get("unidad_norm") or "kg"

        if precio_base is None and meta:
            precio_base = float(meta["precio"])
            precio_kilo = meta.get("precio_por_unidad_normalizado")
            if precio_kilo:
                precio_kilo = float(precio_kilo)
            unidad_norm = meta.get("unidad_normalizacion") or "kg"
            base_super_nombre = meta.get("supermercado_nombre", "")
        else:
            base_super_nombre = base_super

        if precio_base is not None:
            pc1, pc2 = st.columns([1, 2])
            with pc1:
                st.markdown(f"### {precio_base:.2f} €")
                if precio_kilo:
                    st.caption(f"{precio_kilo:.2f} €/{unidad_norm}")
                if base_super_nombre:
                    st.caption(f"en {base_super_nombre}")
            with pc2:
                # Controles de cantidad
                qty_key = f"qty_{_norm(query)}"
                if qty_key not in st.session_state:
                    st.session_state[qty_key] = 1
                qty = st.number_input(
                    "Cantidad", min_value=1, max_value=99,
                    value=st.session_state[qty_key],
                    key=f"ni_{qty_key}",
                )
                st.session_state[qty_key] = qty

                if st.button("➕ Añadir a la lista", type="primary", use_container_width=True):
                    _add_to_list(usuario.id, query, qty)
                    st.success(f"✅ {query} ×{qty} añadido a tu lista.")

    st.divider()

    # ── COMPARATIVA DE PRECIOS ────────────────────────────────────────────────
    st.subheader("📊 Comparativa de precios")

    if not matches:
        st.info("No hay precios disponibles hoy. Pulsa 'Actualizar precios' en la lista.")
    else:
        # Ordenar de menor a mayor precio
        sorted_matches = sorted(matches.items(), key=lambda x: x[1]["precio"])
        precios = [float(m["precio"]) for _, m in sorted_matches]
        precio_min = precios[0]
        precio_max = precios[-1]

        bars_html = "".join(
            _bar_html(
                float(m["precio"]),
                precio_min, precio_max,
                s_name,
                is_min=(abs(float(m["precio"]) - precio_min) < 0.001),
                is_max=(abs(float(m["precio"]) - precio_max) < 0.001),
            )
            for s_name, m in sorted_matches
        )
        st.markdown(
            f'<div style="padding:12px;background:#fafafa;border-radius:8px;'
            f'border:1px solid #e0e0e0">{bars_html}</div>',
            unsafe_allow_html=True,
        )

        # Ahorro maximo
        if len(precios) > 1:
            ahorro = precio_max - precio_min
            st.caption(
                f"💡 Ahorro comprando en {sorted_matches[0][0]} "
                f"en lugar de {sorted_matches[-1][0]}: **{ahorro:.2f} €** por unidad"
            )

        # Tabla detallada
        st.markdown("**Detalle por supermercado**")
        for s_name, m in sorted_matches:
            c1, c2, c3, c4 = st.columns([2, 1, 2, 2])
            with c1:
                st.write(s_name)
            with c2:
                st.write(f"**{float(m['precio']):.2f} €**")
            with c3:
                pkilo = m.get("precio_por_unidad_normalizado")
                unorm = m.get("unidad_normalizacion") or "kg"
                st.caption(f"{float(pkilo):.2f} €/{unorm}" if pkilo else "—")
            with c4:
                nombre_enc = m.get("producto_nombre", "")
                if _norm(nombre_enc) != _norm(query):
                    st.caption(f"↳ {nombre_enc}")

    st.divider()

    # ── HISTORICO DE PRECIOS ──────────────────────────────────────────────────
    st.subheader("📈 Historico de precios (30 dias)")
    _render_price_history(query, matches, usuario.pais_activo)

    st.divider()

    # ── INFORMACION ADICIONAL ─────────────────────────────────────────────────
    st.subheader("ℹ️ Informacion adicional")
    info_cols = st.columns(2)
    with info_cols[0]:
        st.markdown("**Caracteristicas**")
        if unidad_medida:
            st.write(f"• Formato: {unidad_medida}")
        if categoria:
            st.write(f"• Categoria: {categoria}")
        if meta and meta.get("ean"):
            st.write(f"• EAN: {meta['ean']}")

    with info_cols[1]:
        st.markdown("**Disponibilidad**")
        for s_name, m in matches.items():
            disponible = m.get("disponible", True)
            icon = "✅" if disponible else "❌"
            st.write(f"{icon} {s_name}")


# ── Historico ─────────────────────────────────────────────────────────────────

def _render_price_history(query: str, matches: dict, pais: str) -> None:
    """Muestra un line chart con el historial de precios de los ultimos 30 dias."""
    if not matches:
        st.info("Sin datos historicos disponibles.")
        return

    # Recopilar producto_ids de los matches de hoy
    producto_ids = []
    for m in matches.values():
        pid = m.get("producto_id")
        if pid and pid not in producto_ids:
            producto_ids.append(pid)

    if not producto_ids:
        st.info("Sin datos historicos disponibles.")
        return

    # Cargar historico de los ultimos 30 dias
    desde = str(date.today() - timedelta(days=30))
    hist = _load_history(producto_ids, desde)

    if not hist:
        st.info("Solo hay datos de hoy. El historico se construira con el tiempo.")
        return

    # Pivot para el chart: fecha → {supermercado: precio}
    try:
        import pandas as pd
        df = pd.DataFrame(hist)
        df["fecha"] = pd.to_datetime(df["fecha"])
        df["precio"] = df["precio"].astype(float)
        pivot = df.pivot_table(
            index="fecha",
            columns="supermercado_nombre",
            values="precio",
            aggfunc="min",
        )
        st.line_chart(pivot, use_container_width=True)
    except Exception:
        st.info("No hay suficientes datos para mostrar el historico.")


def _load_history(producto_ids: list[int], desde: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT ph.fecha_scraping AS fecha,
                   ph.precio,
                   s.nombre AS supermercado_nombre
            FROM precios_historicos ph
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE ph.producto_id = ANY(%s)
              AND ph.fecha_scraping >= %s
            ORDER BY ph.fecha_scraping
            """,
            (producto_ids, desde),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Añadir a lista ────────────────────────────────────────────────────────────

def _add_to_list(usuario_id: str, query: str, cantidad: int) -> None:
    with get_connection() as conn:
        # Evitar duplicados
        existing = conn.execute(
            """SELECT id FROM lista_usuario
               WHERE usuario_id = %s AND query_texto = %s AND comprado = FALSE""",
            (usuario_id, query),
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE lista_usuario SET cantidad = cantidad + %s WHERE id = %s",
                (cantidad, existing["id"]),
            )
        else:
            conn.execute(
                "INSERT INTO lista_usuario (usuario_id, query_texto, cantidad) VALUES (%s, %s, %s)",
                (usuario_id, query, cantidad),
            )
