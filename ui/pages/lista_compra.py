"""Shopping list page — diseño premium Smart Shopping Iberia."""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

import streamlit as st

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from domain.models import Usuario
from utils.i18n import t
from ui.styles import page_header, section_header, empty_state, badge_html


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
    qn = _norm(query)
    qw = set(qn.split())
    best_score, best = 0.0, None
    for p in prices:
        nn    = _norm(p["producto_nombre"])
        sim   = SequenceMatcher(None, qn, nn).ratio()
        ov    = len(qw & set(nn.split()))
        total = sim + (ov / max(len(qw), 1)) * 0.30
        if total > best_score:
            best_score, best = total, p
    return best if best_score >= 0.35 else None


# ── Página principal ──────────────────────────────────────────────────────────

def mostrar(usuario: Usuario) -> None:
    if st.session_state.get("detalle_producto"):
        from ui.pages.producto_detalle import mostrar as mostrar_detalle
        mostrar_detalle(usuario)
        return

    page_header("Mi lista de la compra", "Compara precios en tiempo real en todos los supermercados", "🛒")

    _add_item_form(usuario)
    _opciones_menu(usuario)
    _run_scrapers_button(usuario)

    items = _load_items(usuario.id)
    if not items:
        empty_state(
            "🛒",
            "Tu lista está vacía",
            "¡Empieza añadiendo productos con el formulario de arriba!",
        )
        return

    prices = PreciosRepo().get_today(pais=usuario.pais_activo)

    # ── Barra de cobertura de precios ─────────────────────────────────────────
    if prices:
        with_price = sum(1 for it in items if _best_match(it["query_texto"], prices))
        total_items = len(items)
        pct = with_price / total_items if total_items else 0
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;'
            f'margin-bottom:6px">'
            f'  <span style="font-size:.85rem;font-weight:600;color:#1B4332">'
            f'      📊 Cobertura de precios</span>'
            f'  <span style="font-size:.85rem;color:#6C757D">'
            f'      <b style="color:#52B788">{with_price}</b> de <b>{total_items}</b> productos</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.progress(pct)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Acceso rápido al optimizador ─────────────────────────────────────────
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1B4332,#2D6A4F);border-radius:12px;'
        'padding:16px 22px;color:white;display:flex;align-items:center;'
        'justify-content:space-between;margin-bottom:8px">'
        '  <div>'
        '    <div style="font-weight:700;font-size:.95rem">🗺️ Optimizador del sábado</div>'
        '    <div style="font-size:.8rem;opacity:.8;margin-top:3px">'
        '        Calculamos la ruta más barata con los precios de hoy</div>'
        '  </div>'
        '  <div style="font-size:.8rem;opacity:.7;white-space:nowrap;margin-left:16px">'
        '      ← menú lateral</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    st.markdown("<br>", unsafe_allow_html=True)

    hide_list = st.session_state.get("hide_list", False)

    if hide_list:
        _render_comparison(items, prices, usuario)
    else:
        col_list, col_cmp = st.columns([1, 2], gap="medium")
        with col_list:
            _render_list(usuario, items)
        with col_cmp:
            _render_comparison(items, prices, usuario)


# ── Lista de la compra (columna izquierda) ────────────────────────────────────

def _render_list(usuario: Usuario, items: list[dict]) -> None:
    section_header(f"📋 Lista ({len(items)} productos)")

    view_by_cat = st.session_state.get("view_by_cat", False)

    if view_by_cat:
        _render_list_by_category(usuario, items)
    else:
        for item in items:
            _render_item_card(item)

    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("✅ Limpiar comprados", use_container_width=True):
        _clear_done(usuario.id)
        st.rerun()


def _render_item_card(item: dict) -> None:
    """Renderiza un item de la lista como mini-card con botones."""
    ca, cb, cc = st.columns([5, 1, 1])
    with ca:
        st.markdown(
            f'<div style="padding:8px 12px;background:white;border-radius:9px;'
            f'box-shadow:0 1px 6px rgba(0,0,0,.06);border:1px solid #F0F0F0;'
            f'font-size:.9rem">'
            f'  <b>{item["query_texto"]}</b>'
            f'  <span style="color:#ADB5BD;margin-left:6px">×{item["cantidad"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    with cb:
        if st.button("✅", key=f"done_{item['id']}", help="Marcar como comprado"):
            _mark_done(item["id"])
            st.rerun()
    with cc:
        if st.button("🗑️", key=f"del_{item['id']}", help="Eliminar"):
            _delete_item(item["id"])
            st.rerun()


def _render_list_by_category(usuario: Usuario, items: list[dict]) -> None:
    cats: dict[str, list[dict]] = {}
    for item in items:
        cat = _detect_category(item["query_texto"])
        cats.setdefault(cat, []).append(item)

    for cat_name, cat_items in sorted(cats.items()):
        st.markdown(
            f'<div style="font-weight:700;font-size:.82rem;color:#6C757D;'
            f'text-transform:uppercase;letter-spacing:.06em;margin:14px 0 6px">'
            f'{cat_name}</div>',
            unsafe_allow_html=True,
        )
        for item in cat_items:
            ca, cb = st.columns([6, 1])
            with ca:
                st.markdown(
                    f'<div style="padding:7px 12px;background:white;border-radius:8px;'
                    f'box-shadow:0 1px 5px rgba(0,0,0,.05);font-size:.88rem">'
                    f'• {item["query_texto"]} <span style="color:#ADB5BD">×{item["cantidad"]}</span></div>',
                    unsafe_allow_html=True,
                )
            with cb:
                if st.button("🗑️", key=f"del_cat_{item['id']}"):
                    _delete_item(item["id"])
                    st.rerun()


def _detect_category(query: str) -> str:
    q = _norm(query)
    cats = {
        "🥦 Frescos":   ["limon","platano","manzana","pera","naranja","fresa","uva",
                         "melon","sandia","pimiento","tomate","lechuga","cebolla",
                         "zanahoria","patata","pepino","brocoli","espinaca"],
        "🥛 Lácteos":   ["leche","yogur","queso","mantequilla","nata","huevo"],
        "🥩 Carne":     ["pollo","ternera","cerdo","pavo","jamon","chorizo","carne"],
        "🐟 Pescado":   ["salmon","merluza","atun","sardina","bacalao","gamba"],
        "🍞 Panadería": ["pan","galleta","cereal","tostada"],
        "🧴 Limpieza":  ["detergente","suavizante","bayeta","papel","jabon"],
        "🥤 Bebidas":   ["agua","zumo","refresco","cerveza","vino","cafe","te"],
        "🛢 Aceite":    ["aceite","sal","vinagre"],
    }
    for cat_name, keywords in cats.items():
        if any(kw in q for kw in keywords):
            return cat_name
    return "📦 Otros"


# ── Comparativa de precios ────────────────────────────────────────────────────

def _render_comparison(items: list[dict], prices: list[dict], usuario=None) -> None:
    if not prices:
        empty_state("💸", "Sin precios para hoy", t("no_prices_today"))
        return

    favoritos = usuario.supermercados_favoritos if usuario else []

    # Supermercados activos: favoritos primero, luego el resto por cobertura
    super_codigos: dict[str, str] = {}
    super_coverage: dict[str, int] = {}
    for p in prices:
        s = p["supermercado_nombre"]
        super_codigos[s] = p.get("supermercado_codigo", "")
        super_coverage[s] = super_coverage.get(s, 0) + 1

    supers_fav   = sorted([n for n, c in super_codigos.items() if c in favoritos])
    supers_otros = sorted(
        [n for n, c in super_codigos.items() if c not in favoritos],
        key=lambda n: -super_coverage.get(n, 0),
    )
    # Limitar a 8 columnas para que la tabla quepa en pantalla
    supers = (supers_fav + supers_otros)[:8]

    # ── Construir matriz de comparación ──────────────────────────────────────
    comparison: dict[str, dict] = {}
    for item in items:
        q = item["query_texto"]
        comparison[q] = {}
        for s in supers:
            pool  = [p for p in prices if p["supermercado_nombre"] == s]
            match = _best_match(q, pool)
            if match:
                comparison[q][s] = match

    section_header("💸 Comparativa de precios")

    # ── Tabla HTML ────────────────────────────────────────────────────────────
    th_style = (
        "padding:10px 12px;font-size:.75rem;font-weight:700;color:#6C757D;"
        "text-transform:uppercase;letter-spacing:.05em;border-bottom:2px solid #DEE2E6;"
        "white-space:nowrap;background:#FAFAFA"
    )
    td_base = (
        "padding:10px 12px;vertical-align:top;border-bottom:1px solid #F0F0F0;"
        "font-size:.88rem"
    )

    # Cabecera
    header_cells = f'<th style="{th_style};text-align:left">Producto</th>'
    for s in supers:
        fav_mark = " ⭐" if super_codigos.get(s, "") in favoritos else ""
        # Abreviar nombres largos de supermercados
        label = s[:12] + ("…" if len(s) > 12 else "")
        header_cells += (
            f'<th style="{th_style};text-align:center" title="{s}">'
            f'{label}{fav_mark}</th>'
        )

    totals: dict[str, float] = {s: 0.0 for s in supers}
    found:  dict[str, int]   = {s: 0   for s in supers}
    detail_map: dict[str, dict] = {}  # para los botones 🔍 de abajo

    # Filas de productos
    data_rows = ""
    for idx, item in enumerate(items):
        q   = item["query_texto"]
        qty = int(item["cantidad"])
        row = comparison.get(q, {})

        min_price = min(
            (float(row[s]["precio"]) for s in supers if s in row),
            default=None,
        )

        # Primera celda: nombre + cantidad
        bg_row = "#FAFAFA" if idx % 2 == 0 else "white"
        td_row = td_base + f";background:{bg_row}"
        data_rows += (
            f'<tr>'
            f'<td style="{td_row};font-weight:600;min-width:140px">'
            f'{q}'
            f'<span style="color:#ADB5BD;font-size:.8rem;margin-left:6px">×{qty}</span>'
            f'</td>'
        )

        first_match = None
        for s in supers:
            if s in row:
                p            = row[s]
                precio_unit  = float(p["precio"])
                precio_kg_v  = p.get("precio_por_unidad_normalizado")
                unidad       = p.get("unidad_normalizacion") or "kg"
                totals[s]   += precio_unit * qty
                found[s]    += 1
                is_min       = min_price is not None and abs(precio_unit - min_price) < 0.001

                if first_match is None:
                    first_match = p
                    detail_map[q] = {
                        "id":           item["id"],
                        "query":        q,
                        "nombre":       p.get("producto_nombre", q),
                        "imagen":       p.get("url_imagen"),
                        "marca":        p.get("marca"),
                        "categoria":    p.get("categoria"),
                        "unidad_medida": p.get("unidad_medida"),
                        "precio_base":  precio_unit,
                        "precio_kilo":  float(precio_kg_v) if precio_kg_v else None,
                        "unidad_norm":  unidad,
                        "super_base":   s,
                    }

                if is_min:
                    price_cell = (
                        f'<span style="font-weight:800;color:#1B4332;font-size:.92rem">'
                        f'{precio_unit:.2f}&nbsp;€</span>'
                        f'&nbsp;<span style="display:inline-block;padding:2px 6px;'
                        f'border-radius:20px;background:#D8F3DC;color:#1B4332;'
                        f'font-size:.65rem;font-weight:700;vertical-align:middle">MIN</span>'
                    )
                else:
                    price_cell = (
                        f'<span style="color:#495057;font-size:.9rem">'
                        f'{precio_unit:.2f}&nbsp;€</span>'
                    )

                subtext = ""
                if precio_kg_v:
                    subtext = (
                        f'<br><span style="color:#ADB5BD;font-size:.74rem">'
                        f'{float(precio_kg_v):.2f}&nbsp;€/{unidad}</span>'
                    )

                data_rows += (
                    f'<td style="{td_row};text-align:center">'
                    f'{price_cell}{subtext}'
                    f'</td>'
                )
            else:
                data_rows += (
                    f'<td style="{td_row};text-align:center;color:#DEE2E6;'
                    f'font-size:.9rem">—</td>'
                )

        data_rows += "</tr>"

    # Fila de totales
    min_total = min((v for v in totals.values() if v > 0), default=None)
    total_td  = td_base + ";font-weight:800;font-size:.9rem;border-top:2px solid #DEE2E6;background:#FAFAFA"
    total_row = (
        f'<tr><td style="{total_td}">TOTAL ESTIMADO</td>'
    )
    for s in supers:
        if totals[s] > 0:
            is_min = min_total is not None and abs(totals[s] - min_total) < 0.001
            if is_min:
                total_row += (
                    f'<td style="{total_td};text-align:center">'
                    f'<span style="color:#1B4332;background:#D8F3DC;border-radius:7px;'
                    f'padding:4px 8px;display:inline-block">'
                    f'{totals[s]:.2f}&nbsp;€</span></td>'
                )
            else:
                total_row += (
                    f'<td style="{total_td};text-align:center;color:#495057">'
                    f'{totals[s]:.2f}&nbsp;€</td>'
                )
        else:
            total_row += f'<td style="{total_td};text-align:center;color:#DEE2E6">—</td>'
    total_row += "</tr>"

    table_html = (
        '<div style="overflow-x:auto;margin-top:4px">'
        '<table style="width:100%;border-collapse:collapse;font-family:Inter,sans-serif">'
        f'<thead><tr>{header_cells}</tr></thead>'
        f'<tbody>{data_rows}</tbody>'
        f'<tfoot>{total_row}</tfoot>'
        '</table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)

    # ── Botones de detalle (uno por producto con precio) ──────────────────────
    productos_con_precio = [q for q in detail_map]
    if productos_con_precio:
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("Ver ficha completa de un producto:")
        det_cols = st.columns(min(len(productos_con_precio), 4))
        for i, q in enumerate(productos_con_precio):
            with det_cols[i % len(det_cols)]:
                label = q[:22] + ("…" if len(q) > 22 else "")
                if st.button(f"🔍 {label}", key=f"det_{detail_map[q]['id']}", use_container_width=True):
                    d = detail_map[q]
                    st.session_state["detalle_producto"] = {
                        k: v for k, v in d.items() if k != "id"
                    }
                    st.rerun()

    # ── Cobertura por supermercado ────────────────────────────────────────────
    n_items = len(items)
    if any(found[s] > 0 for s in supers):
        st.markdown("<br>", unsafe_allow_html=True)
        section_header("📊 Cobertura por supermercado")
        n_cols = min(len(supers), 4)
        stat_cols = st.columns(n_cols)
        for i, s in enumerate(supers[:n_cols]):
            pct_cob = int(found[s] / n_items * 100) if n_items else 0
            fav_str = " ⭐" if super_codigos.get(s, "") in favoritos else ""
            stat_cols[i].metric(f"{s[:14]}{fav_str}", f"{found[s]}/{n_items}", f"{pct_cob}%")

    if len(supers) == 0:
        st.caption("ℹ️ Pulsa «Consultar supermercados ahora» para obtener precios.")


# ── Menú de opciones ──────────────────────────────────────────────────────────

def _opciones_menu(usuario: Usuario) -> None:
    with st.expander("⚙️ Opciones de lista"):
        c1, c2, c3, c4 = st.columns(4)

        with c1:
            hide_list = st.session_state.get("hide_list", False)
            label = "👁 Mostrar lista" if hide_list else "🙈 Ocultar lista"
            if st.button(label, use_container_width=True):
                st.session_state["hide_list"] = not hide_list
                st.rerun()

        with c2:
            by_cat    = st.session_state.get("view_by_cat", False)
            cat_label = "📋 Vista normal" if by_cat else "🗂 Por categoría"
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
                if st.button("✅ Sí, vaciar", type="primary"):
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
        st.info("Lista vacía.")
        return

    st.markdown("---")
    st.markdown("### 🖨 Lista para imprimir")
    st.caption(f"Código postal: {usuario.codigo_postal} · {len(items)} productos")

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
    from utils.voice_input import render_voice_button, read_voice_text

    voice_text = read_voice_text()

    with st.form("add_item", clear_on_submit=True):
        col1, col2, col3 = st.columns([4, 1, 1])
        with col1:
            query = st.text_input(
                "Añadir producto",
                placeholder="Ej: Leche entera 1L, Pechuga de pollo…",
                value=voice_text,
                label_visibility="collapsed",
            )
        with col2:
            cantidad = st.number_input("Cant.", min_value=1, max_value=99, value=1, label_visibility="collapsed")
        with col3:
            st.write("")
            submitted = st.form_submit_button("➕ Añadir", use_container_width=True, type="primary")
        if submitted:
            if query.strip():
                _insert_item(usuario.id, query.strip(), int(cantidad))
                st.rerun()
            else:
                st.warning("Escribe el nombre del producto.")

    lang = "pt-PT" if usuario.pais_activo == "PT" else "es-ES"
    col_caption, col_btn = st.columns([6, 1])
    with col_caption:
        st.caption("¿Prefieres la voz? Pulsa 🎤 (Chrome/Edge)")
    with col_btn:
        render_voice_button(lang=lang)


# ── Botón actualizar precios ──────────────────────────────────────────────────

def _run_scrapers_button(usuario: Usuario) -> None:
    col_btn, col_info = st.columns([2, 3])
    with col_btn:
        if st.button("🔄 Consultar supermercados ahora", type="primary", use_container_width=True):
            _run_scrapers(usuario)
            st.rerun()
    with col_info:
        st.caption(
            "Actualiza Mercadona, Lidl y FACUA (Carrefour, Alcampo, Hipercor, Día) "
            "en tiempo real. Ahorramas vía Playwright stealth."
        )


def _run_scrapers(usuario: Usuario) -> None:
    import concurrent.futures
    from scrapers import ALL_SCRAPERS_ES, ALL_SCRAPERS_PT
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo

    items = _load_items(usuario.id)
    if not items:
        st.warning("Tu lista está vacía.")
        return

    queries = [it["query_texto"] for it in items if not it["query_texto"].strip().isdigit()]
    if not queries:
        st.warning("Todos los productos son códigos de barras.")
        return

    if usuario.pais_activo == "ES":
        scraper_classes = ALL_SCRAPERS_ES
    elif usuario.pais_activo == "PT":
        scraper_classes = ALL_SCRAPERS_PT
    else:
        scraper_classes = ALL_SCRAPERS_ES + ALL_SCRAPERS_PT

    productos_repo = ProductosRepo()
    precios_repo   = PreciosRepo()
    total          = 0
    errores        = []
    bar            = st.progress(0, text="Iniciando…")

    from scrapers.playwright_base import PlaywrightBaseScraper

    for i, cls in enumerate(scraper_classes):
        scraper          = cls()
        _SCRAPER_TIMEOUT = 180 if isinstance(scraper, PlaywrightBaseScraper) else 90
        bar.progress((i + 1) / len(scraper_classes), text=f"Consultando {scraper.NOMBRE}…")
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                future  = ex.submit(scraper.scrape_products, queries)
                results = future.result(timeout=_SCRAPER_TIMEOUT)
            guardados = 0
            for sp in results:
                pid = productos_repo.upsert_from_scraped(sp, scraper.supermarket_id)
                if pid:
                    precios_repo.upsert_today(pid, scraper.supermarket_id, sp)
                    total    += 1
                    guardados += 1
            st.caption(f"✔ {scraper.NOMBRE}: {len(results)} encontrados, {guardados} guardados")
        except concurrent.futures.TimeoutError:
            errores.append(f"{scraper.NOMBRE} (timeout)")
        except Exception as exc:
            errores.append(f"{scraper.NOMBRE}: {exc}")

    bar.empty()
    for e in errores:
        st.warning(f"⚠ {e}")
    if total > 0:
        st.success(f"✅ {total} precios guardados en base de datos.")
    else:
        st.error("❌ No se guardó ningún precio.")


# ── DB helpers ────────────────────────────────────────────────────────────────

def _load_items(usuario_id: str) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT id, query_texto, cantidad, prioridad "
            "FROM lista_usuario "
            "WHERE usuario_id = %s AND comprado = FALSE "
            "ORDER BY prioridad DESC, query_texto",
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
