"""Configuración global — cargada una vez al importar.

Orden de prioridad:
  1. Variables de entorno del sistema (incluido lo que carga .env localmente)
  2. st.secrets de Streamlit Community Cloud (si se ejecuta en ese contexto)

El scheduler y otros scripts standalone solo necesitan DATABASE_URL,
que siempre estará en el entorno cuando se ejecuten en producción.
"""
import os
from pathlib import Path

from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent
load_dotenv(_BASE / ".env")   # silencioso si no existe (p.ej. en Streamlit Cloud)


def _cfg(key: str, default: str = "") -> str:
    """Lee una clave de entorno; recurre a st.secrets si no está en .env."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        return str(st.secrets.get(key, default))
    except Exception:
        return default


# ── Supabase ──────────────────────────────────────────────────────────────────
SUPABASE_URL:      str = _cfg("SUPABASE_URL")
SUPABASE_ANON_KEY: str = _cfg("SUPABASE_ANON_KEY")
DATABASE_URL:      str = _cfg("DATABASE_URL")

# ── Seguridad ─────────────────────────────────────────────────────────────────
SECRET_KEY:           str = _cfg("SECRET_KEY", "dev-secret-change-in-production")
SESSION_EXPIRY_DAYS:  int = int(_cfg("SESSION_EXPIRY_DAYS", "7"))

# ── Configuración regional ────────────────────────────────────────────────────
DEFAULT_COUNTRY:     str = _cfg("DEFAULT_COUNTRY", "ES")
DEFAULT_POSTAL_CODE: str = _cfg("DEFAULT_POSTAL_CODE", "28001")
ADMIN_EMAIL:         str = _cfg("ADMIN_EMAIL")

# ── HTTP / scraping ───────────────────────────────────────────────────────────
REQUEST_TIMEOUT:   int   = 15
MAX_RETRIES:       int   = 3
BASE_RETRY_DELAY:  float = 1.0    # segundos; se dobla en cada reintento
RATE_LIMIT_DELAY:  float = 0.4    # segundos entre peticiones del mismo scraper

# ── Umbrales de alertas y optimizador ────────────────────────────────────────
PRICE_DROP_THRESHOLD:   float = 0.15   # bajada ≥15 % → generar alerta
MIN_SAVINGS_ALERT:      float = 0.50   # mínimo €0.50 de ahorro para alertar
BULK_DISCOUNT_THRESHOLD: float = 0.15  # bajada ≥15 % → sugerir acopio
MAX_BULK_UNITS:          int   = 10    # máximo de unidades sugeridas

# ── Scheduler ────────────────────────────────────────────────────────────────
SCRAPING_HOUR:       str = "07:00"
WEEKLY_SUMMARY_DAY:  str = "wednesday"
