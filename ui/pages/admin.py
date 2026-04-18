"""Panel de administración — solo accesible para ADMIN_EMAIL.

Muestra:
  - Métricas globales (usuarios, productos, precios hoy, scrapers)
  - Actividad de scrapers (cobertura por supermercado hoy y esta semana)
  - Tabla de usuarios registrados
  - Evolución de precios guardados (últimos 30 días)
  - Top productos más buscados
  - Acciones rápidas (ejecutar scraping, enviar resumen semanal)
"""
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from domain.models import Usuario
from utils.config import ADMIN_EMAIL
from ui.styles import page_header, section_header


def mostrar(usuario: Usuario) -> None:
    if not ADMIN_EMAIL or usuario.email.lower() != ADMIN_EMAIL.lower():
        st.error("Acceso restringido.")
        return

    page_header(
        "Panel de administración",
        subtitle=f"Smart Shopping Iberia · {date.today().strftime('%d/%m/%Y')}",
        emoji="🔧",
    )

    _metricas_globales()
    st.markdown("---")

    col_left, col_right = st.columns([3, 2])
    with col_left:
        _actividad_scrapers()
    with col_right:
        _acciones_rapidas()

    st.markdown("---")
    _evolucion_precios()
    st.markdown("---")

    col_a, col_b = st.columns([3, 2])
    with col_a:
        _tabla_usuarios()
    with col_b:
        _top_queries()


# ── Métricas globales ─────────────────────────────────────────────────────────

def _metricas_globales() -> None:
    from database.connection import get_connection

    hoy = str(date.today())
    ayer = str(date.today() - timedelta(days=1))

    with get_connection() as conn:
        n_usuarios = conn.execute(
            "SELECT COUNT(*) AS n FROM usuarios WHERE activo = TRUE"
        ).fetchone()["n"]

        n_productos = conn.execute(
            "SELECT COUNT(*) AS n FROM productos"
        ).fetchone()["n"]

        precios_hoy = conn.execute(
            "SELECT COUNT(*) AS n FROM precios_historicos WHERE fecha_scraping = %s",
            (hoy,),
        ).fetchone()["n"]

        precios_ayer = conn.execute(
            "SELECT COUNT(*) AS n FROM precios_historicos WHERE fecha_scraping = %s",
            (ayer,),
        ).fetchone()["n"]

        n_alertas_activas = conn.execute(
            "SELECT COUNT(*) AS n FROM alertas WHERE activa = TRUE"
        ).fetchone()["n"]

        n_listas = conn.execute(
            "SELECT COUNT(*) AS n FROM lista_usuario WHERE comprado = FALSE"
        ).fetchone()["n"]

    delta_precios = precios_hoy - precios_ayer if precios_ayer else None

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Usuarios activos",    n_usuarios)
    c2.metric("Productos en catálogo", f"{n_productos:,}")
    c3.metric("Precios guardados hoy", f"{precios_hoy:,}",
              delta=f"{delta_precios:+}" if delta_precios is not None else None)
    c4.metric("Items en listas / alertas activas", f"{n_listas} / {n_alertas_activas}")


# ── Actividad de scrapers ─────────────────────────────────────────────────────

def _actividad_scrapers() -> None:
    from database.connection import get_connection

    hoy  = str(date.today())
    hace7 = str(date.today() - timedelta(days=7))

    section_header("📡 Cobertura de scrapers")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                s.nombre                                            AS supermercado,
                s.pais,
                COUNT(CASE WHEN ph.fecha_scraping = %s THEN 1 END) AS hoy,
                COUNT(CASE WHEN ph.fecha_scraping >= %s THEN 1 END) AS semana,
                MAX(ph.fecha_scraping)                              AS ultimo_scraping
            FROM supermercados s
            LEFT JOIN precios_historicos ph ON ph.supermercado_id = s.id
            GROUP BY s.id, s.nombre, s.pais
            ORDER BY s.pais, hoy DESC
            """,
            (hoy, hace7),
        ).fetchall()

    if not rows:
        st.info("Sin datos de scraping todavía.")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    df["estado"] = df["hoy"].apply(lambda n: "✅ OK" if n > 0 else "⚠️ Sin datos hoy")
    df["ultimo_scraping"] = df["ultimo_scraping"].fillna("—")

    st.dataframe(
        df[["supermercado", "pais", "hoy", "semana", "ultimo_scraping", "estado"]].rename(columns={
            "supermercado":    "Supermercado",
            "pais":            "País",
            "hoy":             "Precios hoy",
            "semana":          "Precios 7 días",
            "ultimo_scraping": "Último scraping",
            "estado":          "Estado",
        }),
        use_container_width=True,
        hide_index=True,
    )


# ── Acciones rápidas ──────────────────────────────────────────────────────────

def _acciones_rapidas() -> None:
    section_header("⚡ Acciones rápidas")

    if st.button("🔄 Ejecutar scrapers ahora", use_container_width=True, type="primary"):
        with st.spinner("Ejecutando scrapers… (puede tardar varios minutos)"):
            try:
                from utils.scheduler import run_all_scrapers
                run_all_scrapers()
                st.success("Scraping completado. Recarga la página para ver los datos.")
            except Exception as exc:
                st.error(f"Error: {exc}")

    st.markdown("")

    if st.button("📊 Enviar resumen semanal ahora", use_container_width=True):
        with st.spinner("Enviando emails…"):
            try:
                from utils.scheduler import run_weekly_summary
                run_weekly_summary()
                st.success("Resumen semanal enviado.")
            except Exception as exc:
                st.error(f"Error: {exc}")

    st.markdown("")

    # Log del scheduler
    from pathlib import Path
    log_path = Path(__file__).resolve().parent.parent.parent / "logs" / "scheduler.log"
    if log_path.exists():
        with st.expander("📄 Últimas líneas del log"):
            lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
            st.code("\n".join(lines[-30:]), language="text")
    else:
        st.caption("Sin log disponible (ejecuta el scheduler al menos una vez).")


# ── Evolución de precios ──────────────────────────────────────────────────────

def _evolucion_precios() -> None:
    import plotly.express as px
    from database.connection import get_connection

    hace30 = str(date.today() - timedelta(days=30))

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT ph.fecha_scraping AS fecha,
                   s.pais,
                   COUNT(*) AS n_precios
            FROM precios_historicos ph
            JOIN supermercados s ON s.id = ph.supermercado_id
            WHERE ph.fecha_scraping >= %s
            GROUP BY ph.fecha_scraping, s.pais
            ORDER BY ph.fecha_scraping
            """,
            (hace30,),
        ).fetchall()

    if not rows:
        st.info("Sin historial de precios en los últimos 30 días.")
        return

    section_header("📈 Precios guardados — últimos 30 días")

    df = pd.DataFrame([dict(r) for r in rows])
    df["fecha"] = pd.to_datetime(df["fecha"])

    fig = px.bar(
        df, x="fecha", y="n_precios", color="pais",
        color_discrete_map={"ES": "#1f77b4", "PT": "#2ca02c"},
        labels={"fecha": "", "n_precios": "Precios guardados", "pais": "País"},
        barmode="stack",
    )
    fig.update_layout(
        height=280,
        margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Tabla de usuarios ─────────────────────────────────────────────────────────

def _tabla_usuarios() -> None:
    from database.connection import get_connection
    from database.repositories.usuarios_repo import UsuariosRepo

    section_header("👥 Usuarios registrados")

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                u.id,
                u.nombre,
                u.email,
                u.pais_activo                        AS pais,
                u.activo,
                u.email_verificado                   AS verificado,
                (cu.valor = 'true')                  AS emails,
                COUNT(l.id)                          AS items_lista,
                COUNT(CASE WHEN a.activa THEN 1 END) AS alertas,
                u.created_at
            FROM usuarios u
            LEFT JOIN configuracion_usuario cu
                ON cu.usuario_id = u.id AND cu.clave = 'notificaciones_email'
            LEFT JOIN lista_usuario l ON l.usuario_id = u.id AND l.comprado = FALSE
            LEFT JOIN alertas       a ON a.usuario_id = u.id
            GROUP BY u.id, u.nombre, u.email, u.pais_activo,
                     u.activo, u.email_verificado, cu.valor, u.created_at
            ORDER BY u.created_at DESC
            """
        ).fetchall()

    if not rows:
        st.info("Sin usuarios registrados.")
        return

    repo = UsuariosRepo()

    # Cabecera
    TH = "font-size:.72rem;font-weight:700;color:#6C757D;text-transform:uppercase;padding-bottom:6px;border-bottom:2px solid #DEE2E6"
    hcols = st.columns([2, 2.5, 0.6, 0.7, 0.7, 0.7, 0.7, 1.2])
    for label, col in zip(["Nombre", "Email", "País", "Activo", "Email OK", "Notif.", "Lista", "Registro"], hcols):
        col.markdown(f'<div style="{TH}">{label}</div>', unsafe_allow_html=True)

    TD = "padding-top:6px;font-size:.85rem"

    for r in rows:
        uid       = str(r["id"])
        activo    = bool(r["activo"])
        verificado = bool(r["verificado"])
        emails    = bool(r["emails"])
        reg_date  = ""
        if r["created_at"]:
            try:
                from datetime import datetime
                reg_date = datetime.fromisoformat(str(r["created_at"])).strftime("%d/%m/%Y")
            except Exception:
                reg_date = str(r["created_at"])[:10]

        rcols = st.columns([2, 2.5, 0.6, 0.7, 0.7, 0.7, 0.7, 1.2])
        rcols[0].markdown(f'<div style="{TD};font-weight:600">{r["nombre"] or "—"}</div>', unsafe_allow_html=True)
        rcols[1].markdown(f'<div style="{TD};color:#6C757D">{r["email"]}</div>', unsafe_allow_html=True)
        rcols[2].markdown(f'<div style="{TD};text-align:center">{r["pais"] or "—"}</div>', unsafe_allow_html=True)

        # Botón activar/desactivar
        with rcols[3]:
            btn_label = "✅" if activo else "🔴"
            btn_help  = "Desactivar usuario" if activo else "Activar usuario"
            if st.button(btn_label, key=f"toggle_{uid}", help=btn_help):
                repo.set_activo(uid, not activo)
                st.rerun()

        rcols[4].markdown(f'<div style="{TD};text-align:center">{"✅" if verificado else "⚠️"}</div>', unsafe_allow_html=True)
        rcols[5].markdown(f'<div style="{TD};text-align:center">{"✅" if emails else "—"}</div>', unsafe_allow_html=True)
        rcols[6].markdown(f'<div style="{TD};text-align:center">{r["items_lista"]}</div>', unsafe_allow_html=True)
        rcols[7].markdown(f'<div style="{TD};color:#ADB5BD">{reg_date}</div>', unsafe_allow_html=True)

        st.markdown('<hr style="margin:2px 0;border:none;border-top:1px solid #F0F0F0">', unsafe_allow_html=True)


# ── Top queries ───────────────────────────────────────────────────────────────

def _top_queries() -> None:
    from database.connection import get_connection

    section_header("🔍 Productos más buscados")

    hoy = str(date.today())

    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT
                l.query_texto                               AS producto,
                COUNT(DISTINCT l.usuario_id)               AS usuarios,
                MIN(ph.precio)                             AS precio_min_hoy,
                COUNT(DISTINCT ph.supermercado_id)         AS superms_con_precio
            FROM lista_usuario l
            LEFT JOIN productos p
                ON LOWER(p.nombre) LIKE '%' || LOWER(l.query_texto) || '%'
            LEFT JOIN precios_historicos ph
                ON ph.producto_id = p.id AND ph.fecha_scraping = %s
            GROUP BY l.query_texto
            ORDER BY usuarios DESC, l.query_texto
            LIMIT 20
            """,
            (hoy,),
        ).fetchall()

    if not rows:
        st.info("Sin datos de búsqueda.")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    df["precio_min_hoy"] = df["precio_min_hoy"].apply(
        lambda v: f"{float(v):.2f} €" if v is not None else "—"
    )
    df["superms_con_precio"] = df["superms_con_precio"].apply(
        lambda v: f"{v}" if v else "—"
    )

    st.dataframe(
        df.rename(columns={
            "producto":           "Producto",
            "usuarios":           "Usuarios",
            "precio_min_hoy":     "Precio mín. hoy",
            "superms_con_precio": "Superms.",
        }),
        use_container_width=True,
        hide_index=True,
    )
