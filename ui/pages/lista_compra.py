"""Shopping list page — vista tipo SoySuper.

Layout: lista de la compra (izquierda) + comparativa de precios (derecha).
Incluye menu Opciones, precio por kg/L, estadisticas por supermercado.
"""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

import streamlit as st

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from domain.models import Usuario


# ── Utilidades de matching ────────────────────────────────────────────────────

def _norm(text: str) -> str:
    return (
        unicodedata.normalize("NFD", text)
        .encode("ascii", "ignore")
        .decode()
        .lower()
        .strip()
    )


def _best_match(query: str, prices: list[dict]) -> Optional[dict]:
    """Encuentra el precio que mejor coincide con la query (fuzzy match)."""
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
    return best if best_score >= 0.35 else None


# ── Pagina principal ──────────────────────────────────────────────────────────

def mostrar(usuario: Usuario) -> None:
    # Si hay un producto seleccionado, mostrar su ficha
    if st.session_state.get("detalle_producto"):
        from ui.pages.producto_detalle import mostrar as mostrar_detalle
        mostrar_detalle(usuario)
        return

    # Cabecera
    c1, c2 = st.columns([5, 1])
    with c1:
        st.title("🛒 Mi cesta de la compra")
    with c2:
        st.metric("Codigo postal", usuario.codigo_postal or "—")

    _add_item_form(usuario)
    _opciones_menu(usuario)
    _run_scrapers_button(usuario)

    items = _load_items(usuario.id)
    if not items:
        st.info("Tu lista esta vacia. Añade productos arriba.")
        return

    prices = PreciosRepo().get_today(pais=usuario.pais_activo)

    hide_list = st.session_state.get("hide_list", False)

    if hide_list:
        _render_comparison(items, prices)
    else:
        col_list, col_cmp = st.columns([1, 2], gap="medium")
        with col_list:
            _render_list(usuario, items)
        with col_cmp:
            _render_comparison(items, prices)


# ── Lista de la compra (columna izquierda) ────────────────────────────────────

def _render_list(usuario: Usuario, items: list[dict]) -> None:
    st.subheader(f"Lista ({len(items)} productos)")

    view_by_cat = st.session_state.get("view_by_cat", False)

    if view_by_cat:
        _render_list_by_category(usuario, items)
    else:
        for item in items:
            ca, cb, cc = st.columns([5, 1, 1])
            with ca:
                st.write(f"**{item['query_texto']}** ×{item['cantidad']}")
            with cb:
                if st.button("✅", key=f"done_{item['id']}", help="Comprado"):
                    _mark_done(item["id"])
                    st.rerun()
            with cc:
                if st.button("🗑️", key=f"del_{item['id']}", help="Eliminar"):
                    _delete_item(item["id"])
                    st.rerun()

    if st.button("🗑️ Limpiar comprados", use_container_width=True):
        _clear_done(usuario.id)
        st.rerun()


def _render_list_by_category(usuario: Usuario, items: list[dict]) -> None:
    """Agrupa los items por categoria detectada en el nombre."""
    cats: dict[str, list[dict]] = {}
    for item in items:
        cat = _detect_category(item["query_texto"])
        cats.setdefault(cat, []).append(item)

    for cat_name, cat_items in sorted(cats.items()):
        st.markdown(f"**{cat_name}**")
        for item in cat_items:
            ca, cb = st.columns([6, 1])
            with ca:
                st.write(f"• {item['query_texto']} ×{item['cantidad']}")
            with cb:
                if st.button("🗑️", key=f"del_cat_{item['id']}"):
                    _delete_item(item["id"])
                    st.rerun()


def _detect_category(query: str) -> str:
    """Detecta la categoria del producto por palabras clave."""
    q = _norm(query)
    cats = {
        "🥦 Frescos": ["limon","platano","manzana","pera","naranja","fresa","uva",
                       "melon","sandia","pimiento","tomate","lechuga","cebolla",
                       "zanahoria","patata","pepino","brocoli","espinaca"],
        "🥛 Lacteos": ["leche","yogur","queso","mantequilla","nata","huevo"],
        "🥩 Carne":   ["pollo","ternera","cerdo","pavo","jamon","chorizo","carne"],
        "🐟 Pescado": ["salmon","merluza","atun","sardina","bacalao","gamba"],
        "🍞 Panaderia":["pan","galleta","cereal","tostada"],
        "🧴 Limpieza":["detergente","suavizante","bayeta","papel","jabon"],
        "🥤 Bebidas": ["agua","zumo","refresco","cerveza","vino","cafe","te"],
        "🛢 Aceite":  ["aceite","sal","vinagre"],
    }
    for cat_name, keywords in cats.items():
        if any(kw in q for kw in keywords):
            return cat_name
    return "📦 Otros"


# ── Comparativa de precios (columna derecha) ──────────────────────────────────

def _render_comparison(items: list[dict], prices: list[dict]) -> None:
    if not prices:
        st.info(
            "No hay precios para hoy. Pulsa **🔄 Consultar supermercados ahora** para actualizar."
        )
        return

    # Supermercados disponibles hoy
    supers = sorted({p["supermercado_nombre"] for p in prices})

    # Matching: query → {super: mejor precio encontrado}
    comparison: dict[str, dict] = {}
    for item in items:
        q = item["query_texto"]
        comparison[q] = {}
        for s in supers:
            pool = [p for p in prices if p["supermercado_nombre"] == s]
            match = _best_match(q, pool)
            if match:
                comparison[q][s] = match

    # Tabla de comparativa
    st.subheader("Comparativa de precios")

    # Cabecera
    header_cols = st.columns([3] + [2] * len(supers))
    with header_cols[0]:
        st.markdown("**Producto**")
    for i, s in enumerate(supers):
        with header_cols[i + 1]:
            st.markdown(f"**{s}**")

    st.divider()

    # Filas por producto
    totals: dict[str, float] = {s: 0.0 for s in supers}
    found: dict[str, int] = {s: 0 for s in supers}

    for item in items:
        q = item["query_texto"]
        qty = item["cantidad"]
        row_data = comparison.get(q, {})

        # Precio mas barato entre los supermercados
        min_price = min(
            (row_data[s]["precio"] for s in supers if s in row_data),
            default=None,
        )

        row_cols = st.columns([3] + [2] * len(supers) + [1])
        with row_cols[0]:
            st.write(f"**{q}** ×{qty}")

        for i, s in enumerate(supers):
            with row_cols[i + 1]:
                if s in row_data:
                    p = row_data[s]
                    precio_unit = p["precio"]
                    precio_kg = p.get("precio_por_unidad_normalizado")
                    unidad = p.get("unidad_normalizacion") or "kg"

                    total_item = precio_unit * qty
                    totals[s] += total_item
                    found[s] += 1

                    is_min = (min_price is not None and abs(precio_unit - min_price) < 0.001)
                    price_str = f"**:green[{precio_unit:.2f} €]**" if is_min else f"{precio_unit:.2f} €"
                    st.markdown(price_str)

                    if precio_kg:
                        st.caption(f"{precio_kg:.2f} €/{unidad}")
                    # Nombre real encontrado
                    nombre_real = p.get("producto_nombre", "")
                    if _norm(nombre_real) != _norm(q):
                        st.caption(f"↳ {nombre_real}")
                else:
                    st.markdown("—")

        # Boton ver ficha (ultima columna)
        with row_cols[-1]:
            first_match = next((row_data[s] for s in supers if s in row_data), None)
            if st.button("🔍", key=f"det_{item['id']}", help="Ver ficha del producto"):
                st.session_state["detalle_producto"] = {
                    "query": q,
                    "nombre": first_match["producto_nombre"] if first_match else q,
                    "imagen": first_match.get("url_imagen") if first_match else None,
                    "marca": first_match.get("marca") if first_match else None,
                    "categoria": first_match.get("categoria") if first_match else None,
                    "unidad_medida": first_match.get("unidad_medida") if first_match else None,
                    "precio_base": float(first_match["precio"]) if first_match else None,
                    "precio_kilo": float(first_match["precio_por_unidad_normalizado"]) if first_match and first_match.get("precio_por_unidad_normalizado") else None,
                    "unidad_norm": first_match.get("unidad_normalizacion") if first_match else None,
                    "super_base": first_match["supermercado_nombre"] if first_match else "",
                }
                st.rerun()

    st.divider()

    # Fila de totales
    total_cols = st.columns([3] + [2] * len(supers) + [1])
    with total_cols[0]:
        st.markdown("**TOTAL**")
    total_cols[-1].write("")  # columna boton vacia en fila total
    for i, s in enumerate(supers):
        with total_cols[i + 1]:
            if totals[s] > 0:
                min_total = min(v for v in totals.values() if v > 0)
                is_min = abs(totals[s] - min_total) < 0.001
                total_str = f"**:green[{totals[s]:.2f} €]**" if is_min else f"**{totals[s]:.2f} €**"
                st.markdown(total_str)

    # Estadisticas por supermercado
    st.divider()
    st.markdown("**Resumen por supermercado**")
    stat_cols = st.columns(len(supers))
    for i, s in enumerate(supers):
        with stat_cols[i]:
            n = found[s]
            total_items = len(items)
            pct = int(n / total_items * 100) if total_items else 0
            st.metric(s, f"{n}/{total_items}", f"{pct}% encontrado")

    if len(supers) <= 2:
        st.caption(
            "ℹ️ Solo aparecen Mercadona y Lidl porque Carrefour, Alcampo, Día e Hipercor "
            "bloquean peticiones automáticas desde servidores en la nube (Cloudflare)."
        )


# ── Menu Opciones ─────────────────────────────────────────────────────────────

def _opciones_menu(usuario: Usuario) -> None:
    with st.expander("⚙️ Opciones"):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            hide_list = st.session_state.get("hide_list", False)
            label = "👁 Mostrar lista" if hide_list else "🙈 Ocultar lista"
            if st.button(label, use_container_width=True):
                st.session_state["hide_list"] = not hide_list
                st.rerun()

        with c2:
            by_cat = st.session_state.get("view_by_cat", False)
            cat_label = "📋 Vista normal" if by_cat else "🗂 Ver por categoria"
            if st.button(cat_label, use_container_width=True):
                st.session_state["view_by_cat"] = not by_cat
                st.rerun()

        with c3:
            if st.button("🖨 Imprimir lista", use_container_width=True):
                st.session_state["show_print"] = True
                st.rerun()

        with c4:
            if st.button("🗑️ Vaciar carrito", use_container_width=True, type="secondary"):
                st.session_state["confirm_clear"] = True
                st.rerun()

        if st.session_state.get("confirm_clear"):
            st.warning("¿Seguro que quieres eliminar TODOS los productos de la lista?")
            cc1, cc2 = st.columns(2)
            with cc1:
                if st.button("✅ Si, vaciar", type="primary"):
                    _clear_all(usuario.id)
                    st.session_state["confirm_clear"] = False
                    st.rerun()
            with cc2:
                if st.button("❌ Cancelar"):
                    st.session_state["confirm_clear"] = False
                    st.rerun()

        if st.session_state.get("show_print"):
            _render_print_view(usuario)


def _render_print_view(usuario: Usuario) -> None:
    items = _load_items(usuario.id)
    if not items:
        st.info("Lista vacia.")
        return

    st.markdown("---")
    st.markdown("### 🖨 Lista para imprimir")
    st.caption(f"Codigo postal: {usuario.codigo_postal} · {len(items)} productos")

    cats: dict[str, list[dict]] = {}
    for item in items:
        cat = _detect_category(item["query_texto"])
        cats.setdefault(cat, []).append(item)

    lines = []
    for cat, cat_items in sorted(cats.items()):
        lines.append(f"**{cat}**")
        for it in cat_items:
            lines.append(f"- {it['query_texto']} ×{it['cantidad']}")

    st.markdown("\n".join(lines))

    if st.button("✕ Cerrar vista imprimir"):
        st.session_state["show_print"] = False
        st.rerun()


# ── Formulario añadir item ────────────────────────────────────────────────────

def _add_item_form(usuario: Usuario) -> None:
    with st.form("add_item", clear_on_submit=True):
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            query = st.text_input("Añadir producto", placeholder="Leche entera 1L")
        with col2:
            cantidad = st.number_input("Cant.", min_value=1, max_value=99, value=1)
        with col3:
            st.write("")
            submitted = st.form_submit_button("➕ Añadir", use_container_width=True)
        if submitted:
            if query.strip():
                _insert_item(usuario.id, query.strip(), int(cantidad))
                st.rerun()
            else:
                st.warning("Escribe el nombre del producto.")


# ── Boton actualizar precios ──────────────────────────────────────────────────

def _run_scrapers_button(usuario: Usuario) -> None:
    st.markdown("---")
    col_btn, col_info = st.columns([2, 3])
    with col_btn:
        if st.button("🔄 Consultar supermercados ahora", type="primary", use_container_width=True):
            _run_scrapers(usuario)
            st.rerun()
    with col_info:
        st.caption(
            "Actualiza precios de Mercadona y Lidl en tiempo real. "
            "Carrefour, Alcampo, Día e Hipercor bloquean peticiones automáticas desde servidores en la nube."
        )
    st.markdown("---")


def _run_scrapers(usuario: Usuario) -> None:
    import concurrent.futures
    from scrapers import ALL_SCRAPERS_ES, ALL_SCRAPERS_PT
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo

    items = _load_items(usuario.id)
    if not items:
        st.warning("Tu lista esta vacia.")
        return

    queries = [
        item["query_texto"] for item in items
        if not item["query_texto"].strip().isdigit()
    ]
    if not queries:
        st.warning("Todos los productos son codigos de barras.")
        return

    if usuario.pais_activo == "ES":
        scraper_classes = ALL_SCRAPERS_ES
    elif usuario.pais_activo == "PT":
        scraper_classes = ALL_SCRAPERS_PT
    else:
        scraper_classes = ALL_SCRAPERS_ES + ALL_SCRAPERS_PT

    productos_repo = ProductosRepo()
    precios_repo = PreciosRepo()
    total = 0
    errores = []
    bar = st.progress(0, text="Iniciando...")

    _SCRAPER_TIMEOUT = 90

    for i, cls in enumerate(scraper_classes):
        scraper = cls()
        bar.progress((i + 1) / len(scraper_classes), text=f"Consultando {scraper.NOMBRE}...")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future = ex.submit(scraper.scrape_products, queries)
                results = future.result(timeout=_SCRAPER_TIMEOUT)
            guardados = 0
            for sp in results:
                pid = productos_repo.upsert_from_scraped(sp, scraper.supermarket_id)
                if pid:
                    precios_repo.upsert_today(pid, scraper.supermarket_id, sp)
                    total += 1
                    guardados += 1
            st.caption(f"✔ {scraper.NOMBRE}: {len(results)} encontrados, {guardados} guardados")
        except concurrent.futures.TimeoutError:
            errores.append(f"{scraper.NOMBRE} (timeout)")
        except Exception as exc:
            errores.append(f"{scraper.NOMBRE}: {exc}")

    bar.empty()
    if errores:
        for e in errores:
            st.warning(f"⚠ {e}")
    if total > 0:
        st.success(f"✅ {total} precios guardados en base de datos.")
    else:
        st.error("❌ No se guardo ningun precio.")


# ── DB helpers ────────────────────────────────────────────────────────────────

def _load_items(usuario_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT id, query_texto, cantidad, prioridad
               FROM lista_usuario
               WHERE usuario_id = %s AND comprado = FALSE
               ORDER BY prioridad DESC, query_texto""",
            (usuario_id,),
        ).fetchall()
    return [dict(r) for r in rows]


def _insert_item(usuario_id: str, query: str, cantidad: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO lista_usuario (usuario_id, query_texto, cantidad) VALUES (%s, %s, %s)",
            (usuario_id, query, cantidad),
        )


def _mark_done(item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("UPDATE lista_usuario SET comprado = TRUE WHERE id = %s", (item_id,))


def _delete_item(item_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM lista_usuario WHERE id = %s", (item_id,))


def _clear_done(usuario_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM lista_usuario WHERE usuario_id = %s AND comprado = TRUE",
            (usuario_id,),
        )


def _clear_all(usuario_id: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM lista_usuario WHERE usuario_id = %s", (usuario_id,))
