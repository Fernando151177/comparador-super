"""Shopping list management page."""
import streamlit as st

from database.connection import get_connection
from domain.models import Usuario


def mostrar(usuario: Usuario) -> None:
    st.title("📋 Mi lista de la compra")

    _add_item_form(usuario)
    st.markdown("---")
    _render_list(usuario)
    _run_scrapers_button(usuario)


def _add_item_form(usuario: Usuario) -> None:
    with st.form("add_item", clear_on_submit=True):
        col1, col2 = st.columns([4, 1])
        with col1:
            query = st.text_input("Añadir producto", placeholder="Leche entera 1L")
        with col2:
            cantidad = st.number_input("Cant.", min_value=1, max_value=99, value=1)
        if st.form_submit_button("➕ Añadir", use_container_width=True):
            if query.strip():
                _insert_item(usuario.id, query.strip(), int(cantidad))
                st.rerun()
            else:
                st.warning("Escribe el nombre del producto.")


def _render_list(usuario: Usuario) -> None:
    items = _load_items(usuario.id)
    if not items:
        st.info("Tu lista está vacía. Añade productos arriba.")
        return

    st.subheader(f"{len(items)} producto(s) en tu lista")
    for item in items:
        col1, col2, col3 = st.columns([5, 1, 1])
        with col1:
            st.write(f"**{item['query_texto']}** ×{item['cantidad']}")
        with col2:
            if st.button("✅", key=f"done_{item['id']}", help="Marcar como comprado"):
                _mark_done(item["id"])
                st.rerun()
        with col3:
            if st.button("🗑️", key=f"del_{item['id']}", help="Eliminar"):
                _delete_item(item["id"])
                st.rerun()

    if st.button("🗑️ Limpiar comprados"):
        _clear_done(usuario.id)
        st.rerun()


def _run_scrapers_button(usuario: Usuario) -> None:
    st.markdown("---")
    st.subheader("Actualizar precios")
    if st.button("🔄 Consultar supermercados ahora", type="primary"):
        _run_scrapers(usuario)
        st.rerun()


def _run_scrapers(usuario: Usuario) -> None:
    """Ejecuta los scrapers para los productos de la lista del usuario."""
    import concurrent.futures
    from scrapers import ALL_SCRAPERS_ES, ALL_SCRAPERS_PT
    from database.repositories.productos_repo import ProductosRepo
    from database.repositories.precios_repo import PreciosRepo

    items = _load_items(usuario.id)
    if not items:
        st.warning("Tu lista está vacía.")
        return

    # Excluir EANs puros (números largos) de la búsqueda por nombre
    queries = [
        item["query_texto"] for item in items
        if not item["query_texto"].strip().isdigit()
    ]
    if not queries:
        st.warning("Todos los productos son códigos de barras — añade nombres de producto.")
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
    bar = st.progress(0, text="Iniciando…")

    _SCRAPER_TIMEOUT = 45  # segundos máximo por supermercado (Mercadona necesita más)

    for i, cls in enumerate(scraper_classes):
        scraper = cls()
        bar.progress((i + 1) / len(scraper_classes), text=f"Consultando {scraper.NOMBRE}…")
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
            st.warning(f"⚠️ {e}")
    if total > 0:
        st.success(f"✅ {total} precios guardados en base de datos.")
    else:
        st.error("❌ No se guardó ningún precio. Revisa los avisos de arriba.")


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
