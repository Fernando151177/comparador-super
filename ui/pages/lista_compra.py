"""Shopping list page — tabla única con lista + comparativa de precios."""
import unicodedata
from difflib import SequenceMatcher
from typing import Optional

import streamlit as st

from database.connection import get_connection
from database.repositories.precios_repo import PreciosRepo
from domain.models import Usuario
from utils.i18n import t
from ui.styles import page_header, section_header, empty_state


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

    # Barra de cobertura
    if prices:
        with_price = sum(1 for it in items if _best_match(it["query_texto"], prices))
        pct = with_price / len(items) if items else 0
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px">'
            f'<span style="font-size:.85rem;font-weight:600;color:#1B4332">📊 Cobertura de precios</span>'
            f'<span style="font-size:.85rem;color:#6C757D">'
            f'<b style="color:#52B788">{with_price}</b> de <b>{len(items)}</b> productos</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.progress(pct)
        st.markdown("<br>", unsafe_allow_html=True)

    # Banner optimizador
    st.markdown(
        '<div style="background:linear-gradient(135deg,#1B4332,#2D6A4F);border-radius:12px;'
        'padding:14px 20px;color:white;display:flex;align-items:center;'
        'justify-content:space-between;margin-bottom:16px">'
        '<div>'
        '<div style="font-weight:700;font-size:.92rem">🗺️ Optimizador del sábado</div>'
        '<div style="font-size:.78rem;opacity:.8;margin-top:2px">Calculamos la ruta más barata con los precios de hoy</div>'
        '</div>'
        '<div style="font-size:.78rem;opacity:.6;white-space:nowrap;margin-left:16px">← menú lateral</div>'
        '</div>',
        unsafe_allow_html=True,
    )

    _render_unified_table(items, prices, usuario)


# ── Tabla única: lista + precios ──────────────────────────────────────────────

def _render_unified_table(items: list[dict], prices: list[dict], usuario: Optional[Usuario] = None) -> None:
    favoritos = usuario.supermercados_favoritos if usuario else []

    # Supermercados disponibles
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
    supers = (supers_fav + supers_otros)[:6]

    # Deduplicar items por query_texto
    seen: set[str] = set()
    unique_items: list[dict] = []
    for item in items:
        q = item["query_texto"]
        if q not in seen:
            seen.add(q)
            unique_items.append(item)

    # Matriz de comparación
    comparison: dict[str, dict] = {}
    for item in unique_items:
        q = item["query_texto"]
        comparison[q] = {}
        for s in supers:
            pool  = [p for p in prices if p["supermercado_nombre"] == s]
            match = _best_match(q, pool)
            if match:
                comparison[q][s] = match

    # Ratios de columnas: [✓] [producto] [cant] [super...] [🗑]
    n = len(supers)
    ratios = [0.38, 2.6, 0.85] + [1.3] * n + [0.38]

    section_header("🛒 Lista y comparativa de precios")

    # ── Cabecera de tabla ─────────────────────────────────────────────────────
    TH = "font-size:.7rem;font-weight:700;color:#6C757D;text-transform:uppercase;letter-spacing:.05em;padding-bottom:8px;border-bottom:2px solid #DEE2E6"
    hcols = st.columns(ratios)
    hcols[0].markdown(f'<div style="{TH};text-align:center">✓</div>', unsafe_allow_html=True)
    hcols[1].markdown(f'<div style="{TH}">Producto</div>', unsafe_allow_html=True)
    hcols[2].markdown(f'<div style="{TH};text-align:center">Cant.</div>', unsafe_allow_html=True)
    for i, s in enumerate(supers):
        fav = " ⭐" if super_codigos.get(s, "") in favoritos else ""
        label = (s[:9] + "…") if len(s) > 9 else s
        hcols[3 + i].markdown(f'<div style="{TH};text-align:center" title="{s}">{label}{fav}</div>', unsafe_allow_html=True)
    hcols[-1].markdown(f'<div style="{TH}"></div>', unsafe_allow_html=True)

    # ── Filas de productos ────────────────────────────────────────────────────
    totals:     dict[str, float] = {s: 0.0 for s in supers}
    found:      dict[str, int]   = {s: 0   for s in supers}
    detail_map: dict[str, dict]  = {}

    TD_NAME  = "padding-top:8px;font-weight:600;font-size:.88rem;line-height:1.3"
    TD_PRICE = "padding-top:6px;text-align:center"
    TD_DASH  = "padding-top:10px;text-align:center;color:#CED4DA;font-size:.88rem"

    for item in unique_items:
        q   = item["query_texto"]
        qty = int(item["cantidad"])
        row = comparison.get(q, {})

        min_price = min(
            (float(row[s]["precio"]) for s in supers if s in row),
            default=None,
        )

        rcols = st.columns(ratios)

        # ✅ Marcar comprado
        with rcols[0]:
            st.write("")
            if st.button("✅", key=f"done_{item['id']}", help="Marcar como comprado"):
                _mark_done(item["id"])
                st.rerun()

        # Nombre del producto
        with rcols[1]:
            label_q = (q[:34] + "…") if len(q) > 34 else q
            st.markdown(f'<div style="{TD_NAME}">{label_q}</div>', unsafe_allow_html=True)

        # Cantidad −/+
        with rcols[2]:
            qa, qb, qc = st.columns([1, 1.1, 1])
            with qa:
                if st.button("−", key=f"minus_{item['id']}") and qty > 1:
                    _update_qty(item["id"], qty - 1)
                    st.rerun()
            with qb:
                st.markdown(
                    f'<div style="text-align:center;padding-top:8px;font-size:.85rem;font-weight:600">×{qty}</div>',
                    unsafe_allow_html=True,
                )
            with qc:
                if st.button("+", key=f"plus_{item['id']}"):
                    _update_qty(item["id"], qty + 1)
                    st.rerun()

        # Precios por supermercado
        for i, s in enumerate(supers):
            with rcols[3 + i]:
                if s not in row:
                    st.markdown(f'<div style="{TD_DASH}">—</div>', unsafe_allow_html=True)
                    continue

                p           = row[s]
                precio      = float(p["precio"])
                precio_kg_v = p.get("precio_por_unidad_normalizado")
                unidad      = p.get("unidad_normalizacion") or "kg"
                totals[s]  += precio * qty
                found[s]   += 1
                is_min      = min_price is not None and abs(precio - min_price) < 0.001

                if q not in detail_map:
                    detail_map[q] = {
                        "id":            item["id"],
                        "query":         q,
                        "nombre":        p.get("producto_nombre", q),
                        "imagen":        p.get("url_imagen"),
                        "marca":         p.get("marca"),
                        "categoria":     p.get("categoria"),
                        "unidad_medida": p.get("unidad_medida"),
                        "precio_base":   precio,
                        "precio_kilo":   float(precio_kg_v) if precio_kg_v else None,
                        "unidad_norm":   unidad,
                        "super_base":    s,
                    }

                if is_min:
                    price_html = (
                        f'<span style="font-weight:800;color:#1B4332">{precio:.2f}&nbsp;€</span>'
                        f'&nbsp;<span style="display:inline-block;padding:1px 5px;border-radius:20px;'
                        f'background:#D8F3DC;color:#1B4332;font-size:.6rem;font-weight:700">MIN</span>'
                    )
                else:
                    price_html = f'<span style="color:#495057">{precio:.2f}&nbsp;€</span>'

                subtext = ""
                if precio_kg_v:
                    subtext = f'<br><span style="color:#ADB5BD;font-size:.7rem">{float(precio_kg_v):.2f}&nbsp;€/{unidad}</span>'

                st.markdown(f'<div style="{TD_PRICE}">{price_html}{subtext}</div>', unsafe_allow_html=True)

        # 🗑 Eliminar
        with rcols[-1]:
            st.write("")
            if st.button("🗑️", key=f"del_{item['id']}", help="Eliminar de la lista"):
                _delete_item(item["id"])
                st.rerun()

        # Separador entre filas
        st.markdown('<hr style="margin:2px 0;border:none;border-top:1px solid #F0F0F0">', unsafe_allow_html=True)

    # ── Fila de totales ───────────────────────────────────────────────────────
    if supers and any(totals[s] > 0 for s in supers):
        min_total = min((v for v in totals.values() if v > 0), default=None)
        tcols = st.columns(ratios)
        tcols[1].markdown(
            '<div style="padding-top:8px;font-weight:800;font-size:.85rem;color:#1B4332">TOTAL ESTIMADO</div>',
            unsafe_allow_html=True,
        )
        for i, s in enumerate(supers):
            with tcols[3 + i]:
                if totals[s] > 0:
                    is_min = min_total is not None and abs(totals[s] - min_total) < 0.001
                    if is_min:
                        val = (
                            f'<span style="background:#D8F3DC;color:#1B4332;border-radius:6px;'
                            f'padding:3px 8px;display:inline-block;font-weight:800">'
                            f'{totals[s]:.2f}&nbsp;€</span>'
                        )
                    else:
                        val = f'<span style="color:#495057;font-weight:700">{totals[s]:.2f}&nbsp;€</span>'
                    st.markdown(f'<div style="padding-top:6px;text-align:center">{val}</div>', unsafe_allow_html=True)
                else:
                    st.markdown(f'<div style="{TD_DASH}">—</div>', unsafe_allow_html=True)

    # ── Limpiar comprados ─────────────────────────────────────────────────────
    st.write("")
    if st.button("✅ Limpiar comprados", use_container_width=False):
        _clear_done(usuario.id)
        st.rerun()

    # ── Botones de detalle ────────────────────────────────────────────────────
    if detail_map:
        st.write("")
        st.caption("Ver ficha completa de un producto:")
        det_cols = st.columns(min(len(detail_map), 4))
        for i, q in enumerate(detail_map):
            with det_cols[i % len(det_cols)]:
                btn_label = (q[:22] + "…") if len(q) > 22 else q
                if st.button(f"🔍 {btn_label}", key=f"det_{detail_map[q]['id']}", use_container_width=True):
                    d = detail_map[q]
                    st.session_state["detalle_producto"] = {k: v for k, v in d.items() if k != "id"}
                    st.rerun()

    # ── Sin precios cargados aún ──────────────────────────────────────────────
    if not supers:
        st.info("ℹ️ Pulsa «Consultar supermercados ahora» para ver precios comparados.")

    # ── Cobertura por supermercado ────────────────────────────────────────────
    n_items = len(unique_items)
    if supers and any(found[s] > 0 for s in supers):
        st.write("")
        section_header("📊 Cobertura por supermercado")
        n_cols = min(len(supers), 4)
        stat_cols = st.columns(n_cols)
        for i, s in enumerate(supers[:n_cols]):
            pct_cob = int(found[s] / n_items * 100) if n_items else 0
            fav_str = " ⭐" if super_codigos.get(s, "") in favoritos else ""
            stat_cols[i].metric(f"{s[:14]}{fav_str}", f"{found[s]}/{n_items}", f"{pct_cob}%")


# ── Categoría de producto ─────────────────────────────────────────────────────

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


# ── Menú de opciones ──────────────────────────────────────────────────────────

def _opciones_menu(usuario: Usuario) -> None:
    with st.expander("⚙️ Opciones de lista"):
        c1, c2, c3 = st.columns(3)

        with c1:
            if st.button("🖨 Imprimir lista", use_container_width=True):
                st.session_state["show_print"] = True
                st.rerun()

        with c2:
            if st.button("🗑️ Vaciar carrito", use_container_width=True, type="secondary"):
                st.session_state["confirm_clear"] = True
                st.rerun()

        with c3:
            st.write("")  # espacio

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


def _update_qty(item_id: int, cantidad: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE lista_usuario SET cantidad = %s WHERE id = %s",
            (max(1, cantidad), item_id),
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
