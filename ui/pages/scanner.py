"""Escáner de código de barras — diseño premium."""
import io

import streamlit as st
from PIL import Image
from pyzbar import pyzbar

from database.connection import get_connection
from domain.models import Usuario
from ui.styles import page_header, section_header, empty_state


def mostrar(usuario: Usuario) -> None:
    page_header(
        "Escáner de productos",
        subtitle="Apunta la cámara al código de barras para añadirlo a tu lista.",
        emoji="📷",
    )

    tab_camara, tab_manual = st.tabs(["📸 Cámara", "⌨️ Introducir EAN"])

    with tab_camara:
        _tab_camara(usuario)

    with tab_manual:
        _tab_manual(usuario)


def _tab_camara(usuario: Usuario) -> None:
    st.markdown(
        '<div style="background:#EEF7F3;border-radius:10px;padding:12px 16px;'
        'margin-bottom:16px;font-size:.88rem;color:#1B4332">'
        '📌 <b>Instrucciones:</b> haz clic en <i>Tomar foto</i>, '
        'apunta al código de barras y espera la detección automática.'
        '</div>',
        unsafe_allow_html=True,
    )

    foto = st.camera_input("Tomar foto del código de barras")

    if foto is not None:
        imagen = Image.open(io.BytesIO(foto.getvalue()))
        codigos = pyzbar.decode(imagen)

        if not codigos:
            st.warning("No se detectó ningún código de barras. Inténtalo más cerca y con buena luz.")
            return

        ean = codigos[0].data.decode("utf-8")
        st.success(f"Código detectado: **{ean}**")

        producto = _buscar_por_ean(ean)

        if producto:
            st.info(f"Producto encontrado: **{producto['nombre']}** · {producto['supermercado']}")
            nombre_producto = producto["nombre"]
        else:
            st.info("Producto no encontrado en la base de datos. Se añadirá por su EAN.")
            nombre_producto = ean

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


def _tab_manual(usuario: Usuario) -> None:
    section_header("⌨️ Introducir EAN manualmente",
                   "Los números debajo del código de barras del producto.")

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
            _add_to_list(usuario.id, ean.strip(), int(cantidad), ean.strip())
            st.info(
                f"EAN **{ean}** añadido. El nombre se actualizará con el próximo scraping."
            )


def _buscar_por_ean(ean: str) -> dict | None:
    with get_connection() as conn:
        row = conn.execute(
            """
            SELECT p.nombre, s.nombre AS supermercado
            FROM productos p
            JOIN supermercados s ON s.id = p.supermercado_id
            WHERE p.ean = %s AND p.activo = TRUE
            LIMIT 1
            """,
            (ean,),
        ).fetchone()
    return dict(row) if row else None


def _add_to_list(usuario_id: str, query_texto: str, cantidad: int, ean: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO lista_usuario (usuario_id, query_texto, cantidad, ean)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (usuario_id, query_texto, cantidad, ean),
        )
