"""Módulo de envío de email por SMTP.

Configura las variables en .env o en los secrets de Streamlit Cloud:
    SMTP_HOST      (default: smtp.gmail.com)
    SMTP_PORT      (default: 587)
    SMTP_USER      cuenta remitente, p.ej. tu@gmail.com
    SMTP_PASSWORD  contraseña o App Password de Google
    SMTP_FROM      nombre + dirección que aparece en el De:

Para Gmail: activa "Verificación en 2 pasos" y genera un
"App Password" en myaccount.google.com/apppasswords.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from utils.config import SMTP_FROM, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


def send_email(to: str, subject: str, html: str) -> bool:
    """Envía un email HTML.

    Returns True si se envió correctamente, False si hubo error.
    No lanza excepciones para no interrumpir el scheduler.
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        print("[Email] SMTP_USER / SMTP_PASSWORD no configurados. Email no enviado.")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(SMTP_USER, to, msg.as_string())
        print(f"[Email] Enviado a {to}: {subject}")
        return True
    except Exception as exc:
        print(f"[Email] Error enviando a {to}: {exc}")
        return False


# ── Plantillas ────────────────────────────────────────────────────────────────

def build_price_drop_email(nombre_usuario: str, drops: list[dict]) -> str:
    """Genera el HTML del email de bajada de precios.

    Args:
        nombre_usuario: Nombre del usuario para el saludo.
        drops: Lista de dicts con claves:
               producto_nombre, supermercado_nombre, precio_hoy,
               precio_habitual, pct_bajada, ahorro_abs.
    """
    filas = ""
    for d in drops:
        filas += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0">
            <b>{d['producto_nombre']}</b><br>
            <span style="color:#666;font-size:0.85em">{d['supermercado_nombre']}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                     text-decoration:line-through;color:#999">
            {d['precio_habitual']:.2f} €
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                     color:#28a745;font-weight:bold">
            {d['precio_hoy']:.2f} €
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                     color:#28a745;font-weight:bold">
            -{d['pct_bajada']:.1f}%
          </td>
        </tr>
        """

    total_ahorro = sum(d.get("ahorro_abs", 0) for d in drops)

    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f8f9fa;margin:0;padding:20px">
  <div style="max-width:600px;margin:0 auto;background:white;
              border-radius:8px;overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,.08)">

    <!-- Cabecera -->
    <div style="background:#1f77b4;padding:24px 32px">
      <h1 style="color:white;margin:0;font-size:1.4rem">
        📉 Bajadas de precio en tu lista
      </h1>
      <p style="color:#cce4f7;margin:6px 0 0">
        Hola <b>{nombre_usuario}</b>, hemos detectado
        <b>{len(drops)} bajada{'s' if len(drops) != 1 else ''}</b>
        en productos de tu lista de la compra.
      </p>
    </div>

    <!-- Tabla de bajadas -->
    <div style="padding:24px 32px">
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#f0f4f8">
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Producto</th>
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Precio habitual</th>
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Precio hoy</th>
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Bajada</th>
          </tr>
        </thead>
        <tbody>
          {filas}
        </tbody>
      </table>

      {"" if total_ahorro == 0 else f'''
      <div style="margin-top:16px;padding:12px 16px;background:#d4edda;
                  border-radius:6px;color:#155724">
        💡 Si compras todos estos productos hoy ahorras
        <b>{total_ahorro:.2f} €</b> respecto a sus precios habituales.
      </div>
      '''}
    </div>

    <!-- Footer -->
    <div style="padding:16px 32px;background:#f8f9fa;
                border-top:1px solid #e9ecef;font-size:0.8em;color:#999">
      Smart Shopping Iberia · Puedes desactivar estas notificaciones
      en <b>Mi perfil → Hábitos de compra</b>.
    </div>
  </div>
</body>
</html>
"""


def build_weekly_summary_email(
    nombre_usuario: str,
    top_deals: list[dict],
    ahorro_semana: float,
    n_compras: int,
    semana_inicio: str,
    semana_fin: str,
) -> str:
    """Genera el HTML del resumen semanal.

    Args:
        nombre_usuario: Nombre del usuario.
        top_deals: Hasta 5 dicts con producto_nombre, supermercado_nombre,
                   precio, precio_habitual, pct_bajada.
        ahorro_semana: Total ahorrado en sesiones de compra esta semana.
        n_compras:     Número de sesiones de compra registradas esta semana.
        semana_inicio: Fecha inicio (YYYY-MM-DD).
        semana_fin:    Fecha fin (YYYY-MM-DD).
    """
    # ── Top deals ─────────────────────────────────────────────────────────────
    if top_deals:
        filas_deals = ""
        for d in top_deals:
            filas_deals += f"""
        <tr>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0">
            <b>{d['producto_nombre']}</b><br>
            <span style="color:#666;font-size:0.85em">{d['supermercado_nombre']}</span>
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                     text-decoration:line-through;color:#999">
            {d['precio_habitual']:.2f} €
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                     color:#28a745;font-weight:bold">
            {d['precio']:.2f} €
          </td>
          <td style="padding:8px 12px;border-bottom:1px solid #f0f0f0;
                     color:#28a745;font-weight:bold">
            -{d['pct_bajada']:.1f}%
          </td>
        </tr>"""
        deals_section = f"""
      <h2 style="font-size:1rem;color:#333;margin:0 0 12px">
        🏷️ Mejores ofertas esta semana en tu lista
      </h2>
      <table style="width:100%;border-collapse:collapse">
        <thead>
          <tr style="background:#f0f4f8">
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Producto</th>
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Habitual</th>
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Esta semana</th>
            <th style="padding:8px 12px;text-align:left;font-size:0.85em;color:#555">Bajada</th>
          </tr>
        </thead>
        <tbody>{filas_deals}</tbody>
      </table>"""
    else:
        deals_section = """
      <p style="color:#666;font-style:italic">
        Sin bajadas significativas esta semana en tu lista de la compra.
      </p>"""

    # ── Stats de ahorro ───────────────────────────────────────────────────────
    if ahorro_semana > 0:
        ahorro_bloque = f"""
      <div style="margin-top:16px;padding:12px 16px;background:#d4edda;
                  border-radius:6px;color:#155724">
        💰 Esta semana has ahorrado <b>{ahorro_semana:.2f} €</b>
        en {n_compras} compra{'s' if n_compras != 1 else ''} registrada{'s' if n_compras != 1 else ''}.
      </div>"""
    elif n_compras > 0:
        ahorro_bloque = f"""
      <div style="margin-top:16px;padding:12px 16px;background:#e2f0fb;
                  border-radius:6px;color:#004085">
        🛒 Has realizado {n_compras} compra{'s' if n_compras != 1 else ''} esta semana.
      </div>"""
    else:
        ahorro_bloque = ""

    # Formateo de fechas
    try:
        from datetime import datetime
        fi = datetime.strptime(semana_inicio, "%Y-%m-%d").strftime("%d/%m")
        ff = datetime.strptime(semana_fin,    "%Y-%m-%d").strftime("%d/%m/%Y")
        rango = f"{fi} – {ff}"
    except Exception:
        rango = f"{semana_inicio} – {semana_fin}"

    return f"""
<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"></head>
<body style="font-family:Arial,sans-serif;background:#f8f9fa;margin:0;padding:20px">
  <div style="max-width:600px;margin:0 auto;background:white;
              border-radius:8px;overflow:hidden;
              box-shadow:0 2px 8px rgba(0,0,0,.08)">

    <!-- Cabecera -->
    <div style="background:#1f77b4;padding:24px 32px">
      <h1 style="color:white;margin:0;font-size:1.4rem">
        📊 Tu resumen semanal
      </h1>
      <p style="color:#cce4f7;margin:6px 0 0">
        Hola <b>{nombre_usuario}</b> — semana del {rango}
      </p>
    </div>

    <!-- Contenido -->
    <div style="padding:24px 32px">
      {deals_section}
      {ahorro_bloque}
    </div>

    <!-- Footer -->
    <div style="padding:16px 32px;background:#f8f9fa;
                border-top:1px solid #e9ecef;font-size:0.8em;color:#999">
      Smart Shopping Iberia · Puedes desactivar estas notificaciones
      en <b>Mi perfil → Hábitos de compra</b>.
    </div>
  </div>
</body>
</html>
"""
