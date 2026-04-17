"""Escáner de código de barras — usa la cámara del móvil o del PC."""
import io

import streamlit as st
from PIL import Image
from pyzbar import pyzbar

from database.connection import get_connection
from domain.models import Usuario


def mostrar(usuario: Usuario) -> None:
    st.title("📷 Escáner de código de barras")
    st.caption("Apunta la cámara al código de barras del producto para añadirlo a tu lista.")

    # ── Dos métodos: cámara o introducir EAN a mano ───────────────────────────
    tab_camara, tab_manual = st.tabs(["📸 Cámara", "⌨️ Introducir EAN"])

    with tab_camara:
        _tab_camara(usuario)

    with tab_manual:
        _tab_manual(usuario)


# ── Pestaña cámara ────────────────────────────────────────────────────────────

def _tab_camara(usuario: Usuario) -> None:
    st.markdown(
        "**Instrucciones:**\n"
        "1. Haz clic en *Tomar foto*\n"
        "2. Apunta al código de barras del producto\n"
        "3. La app lo detectará automáticamente"
    )

    foto = st.camera_input("Tomar foto del código de barras")

    if foto is not None:
        imagen = Image.open(io.BytesIO(foto.getvalue()))
        codigos = pyzbar.decode(imagen)

        if not codigos:
            st.warning("No se detectó ningún código de barras. Inténtalo más cerca y con buena luz.")
            return

        # Tomamos el primer código detectado
        ean = codigos[0].data.decode("utf-8")
        st.success(f"Código detectado: **{ean}**")

        # Buscar el producto en la base de datos
        producto = _buscar_por_ean(ean)

        if producto:
            st.info(f"Producto encontrado: **{producto['nombre']}** ({producto['supermercado']})")
            nombre_producto = producto["nombre"]
        else:
            st.info("Producto no encontrado en la base de datos. Puedes añadirlo por su EAN.")
            nombre_producto = ean  # usamos el EAN como texto de búsqueda

        # Formulario para añadir a la lista
        with st.form("add_scanned"):
            col1, col2 = st.columns([3, 1])
            with col1:
                nombre = st.text_input("Nombre en tu lista", value=nombre_producto)
            with col2:
                cantidad = st.number_input("Cant.", min_value=1, max_value=99, value=1)
            if st.form_submit_button("➕ Añadir a mi lista", use_container_width=True, type="primary"):
                _add_to_list(usuario.id, nombre.strip(), int(cantidad), ean)
                st.success(f"✅ **{nombre}** añadido a tu lista.")
                st.rerun()


# ── Pestaña manual ────────────────────────────────────────────────────────────

def _tab_manual(usuario: Usuario) -> None:
    st.markdown("Introduce el código EAN del producto (los números del código de barras).")

    with st.form("add_manual_ean", clear_on_submit=True):
        ean = st.text_input("Código EAN", placeholder="8410188112015", max_chars=14)
        cantidad = st.number_input("Cantidad", min_value=1, max_value=99, value=1)
        buscar = st.form_submit_button("🔍 Buscar y añadir", use_container_width=True, type="primary")

    if buscar and ean.strip():
        producto = _buscar_por_ean(ean.strip())
        if producto:
            _add_to_list(usuario.id, producto["nombre"], int(cantidad), ean.strip())
            st.success(f"✅ **{producto['nombre']}** añadido a tu lista.")
        else:
            # No está en la BD, añadir con el EAN como nombre
            _add_to_list(usuario.id, ean.strip(), int(cantidad), ean.strip())
            st.success(f"✅ EAN **{ean}** añadido a tu lista. El nombre se actualizará cuando se haga scraping.")


# ── Helpers de base de datos ──────────────────────────────────────────────────

def _buscar_por_ean(ean: str) -> dict | None:
    """Busca un producto por EAN y devuelve nombre + supermercado, o None."""
    with get_connection() as conn:
        cur = conn.execute(
            """
            SELECT p.nombre, s.nombre AS supermercado
            FROM productos p
            JOIN supermercados s ON s.id = p.supermercado_id
            WHERE p.ean = %s AND p.activo = TRUE
            LIMIT 1
            """,
            (ean,),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def _add_to_list(usuario_id: str, query_texto: str, cantidad: int, ean: str) -> None:
    """Añade un producto a la lista del usuario."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO lista_usuario (usuario_id, query_texto, cantidad, ean)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (usuario_id, query_texto, cantidad, ean),
        )
