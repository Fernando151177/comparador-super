"""Internacionalización mínima ES/PT.

Uso:
    from utils.i18n import t
    st.title(t("my_shopping_list"))

La función t() lee el país activo de st.session_state["usuario"].pais_activo
y devuelve la cadena en el idioma apropiado (PT cuando pais_activo == "PT",
ES en todos los demás casos).
"""
from __future__ import annotations

_STRINGS: dict[str, dict[str, str]] = {
    # ── app.py / sidebar ─────────────────────────────────────────────────────
    "nav_home":         {"ES": "🏠 Inicio",            "PT": "🏠 Início"},
    "nav_list":         {"ES": "📋 Mi lista",           "PT": "📋 A minha lista"},
    "nav_optimizer":    {"ES": "🗺️ Optimizador sábado", "PT": "🗺️ Optimizador sábado"},
    "nav_savings":      {"ES": "💰 Panel de ahorro",    "PT": "💰 Painel de poupança"},
    "nav_alerts":       {"ES": "🔔 Alertas",            "PT": "🔔 Alertas"},
    "nav_order":        {"ES": "🛍️ Pedido online",      "PT": "🛍️ Encomenda online"},
    "nav_scanner":      {"ES": "📷 Escáner",            "PT": "📷 Scanner"},
    "nav_profile":      {"ES": "👤 Mi perfil",          "PT": "👤 O meu perfil"},
    "nav_admin":        {"ES": "🔧 Admin",              "PT": "🔧 Admin"},
    "sidebar_hello":    {"ES": "Hola, **{name}**",      "PT": "Olá, **{name}**"},
    "logout":           {"ES": "🚪 Cerrar sesión",      "PT": "🚪 Terminar sessão"},
    "country_active":   {"ES": "País activo",           "PT": "País ativo"},
    # ── lista_compra.py ───────────────────────────────────────────────────────
    "my_cart":              {"ES": "🛒 Mi cesta de la compra",   "PT": "🛒 O meu carrinho"},
    "postal_code":          {"ES": "Codigo postal",              "PT": "Código postal"},
    "add_product":          {"ES": "Añadir producto",            "PT": "Adicionar produto"},
    "add_placeholder":      {"ES": "Leche entera 1L",            "PT": "Leite gordo 1L"},
    "qty":                  {"ES": "Cant.",                      "PT": "Qtd."},
    "btn_add":              {"ES": "➕ Añadir",                  "PT": "➕ Adicionar"},
    "warn_write_product":   {"ES": "Escribe el nombre del producto.", "PT": "Escreve o nome do produto."},
    "voice_hint":           {"ES": "¿Prefieres usar la voz? Pulsa 🎤 y di el nombre del producto. (Chrome / Edge)",
                             "PT": "Preferes usar a voz? Clica em 🎤 e diz o nome do produto. (Chrome / Edge)"},
    "list_empty":           {"ES": "Tu lista esta vacia. Añade productos arriba.",
                             "PT": "A tua lista está vazia. Adiciona produtos acima."},
    "price_comparison":     {"ES": "Comparativa de precios",     "PT": "Comparação de preços"},
    "product_col":          {"ES": "**Producto**",               "PT": "**Produto**"},
    "total_row":            {"ES": "**TOTAL**",                  "PT": "**TOTAL**"},
    "summary_per_super":    {"ES": "**Resumen por supermercado**","PT": "**Resumo por supermercado**"},
    "found_pct":            {"ES": "{pct}% encontrado",          "PT": "{pct}% encontrado"},
    "no_prices_today":      {"ES": "No hay precios para hoy. Pulsa **🔄 Consultar supermercados ahora** para actualizar.",
                             "PT": "Sem preços para hoje. Clica em **🔄 Consultar supermercados agora** para atualizar."},
    "btn_refresh":          {"ES": "🔄 Consultar supermercados ahora", "PT": "🔄 Consultar supermercados agora"},
    "scraper_caption":      {"ES": "Consulta Mercadona, Lidl y FACUA (Carrefour, Alcampo, Hipercor, Día, Eroski) en tiempo real. Ahorramas vía Playwright stealth.",
                             "PT": "Consulta Continente, Pingo Doce, Lidl e outros em tempo real."},
    "list_empty_warn":      {"ES": "Tu lista esta vacia.",        "PT": "A tua lista está vazia."},
    "all_barcodes":         {"ES": "Todos los productos son codigos de barras.",
                             "PT": "Todos os produtos são códigos de barras."},
    "btn_clear_bought":     {"ES": "🗑️ Limpiar comprados",       "PT": "🗑️ Limpar comprados"},
    "list_subtitle":        {"ES": "Lista ({n} productos)",      "PT": "Lista ({n} produtos)"},
    "hint_consult":         {"ES": "ℹ️ Pulsa «Consultar supermercados ahora» para obtener precios.",
                             "PT": "ℹ️ Clica em «Consultar supermercados agora» para obter preços."},
    # ── perfil.py ─────────────────────────────────────────────────────────────
    "my_profile":           {"ES": "👤 Mi perfil",               "PT": "👤 O meu perfil"},
    "name":                 {"ES": "Nombre",                     "PT": "Nome"},
    "email":                {"ES": "Email",                      "PT": "Email"},
    "email_no_change":      {"ES": "El email no se puede cambiar.", "PT": "O email não pode ser alterado."},
    "active_country":       {"ES": "País activo",                "PT": "País ativo"},
    "auto_detected":        {"ES": "Detectado automáticamente",  "PT": "Detetado automaticamente"},
    "shopping_day":         {"ES": "Día de compra habitual",     "PT": "Dia habitual de compras"},
    "btn_save":             {"ES": "💾 Guardar cambios",         "PT": "💾 Guardar alterações"},
    "prefs_saved":          {"ES": "Preferencias guardadas.",    "PT": "Preferências guardadas."},
    "postal_hint":          {"ES": "¿No sabes tu código postal?","PT": "Não sabes o teu código postal?"},
    "geo_btn":              {"ES": "📍 Detectar automáticamente","PT": "📍 Detetar automaticamente"},
    "purchase_habits":      {"ES": "🏪 Hábitos de compra",       "PT": "🏪 Hábitos de compra"},
    "habits_caption":       {"ES": "Indica en qué supermercados sueles comprar y cuánto te cuesta desplazarte a uno adicional.",
                             "PT": "Indica em que supermercados costumas comprar e quanto te custa deslocar a um adicional."},
    "my_supers":            {"ES": "Mis supermercados habituales","PT": "Os meus supermercados habituais"},
    "displacement_cost":    {"ES": "Coste de desplazamiento a un supermercado extra (€)",
                             "PT": "Custo de deslocação a um supermercado extra (€)"},
    "displacement_help":    {"ES": "Gasolina + tiempo. Se descuenta del ahorro al valorar si merece visitar un supermercado extra.",
                             "PT": "Gasolina + tempo. É descontado da poupança ao avaliar se vale a pena visitar um supermercado extra."},
    "btn_save_habits":      {"ES": "💾 Guardar hábitos",         "PT": "💾 Guardar hábitos"},
    "habits_saved":         {"ES": "Hábitos de compra guardados.","PT": "Hábitos de compra guardados."},
    "email_notifs":         {"ES": "📧 Notificaciones por email","PT": "📧 Notificações por email"},
    "notifs_caption":       {"ES": "Cuando el scraper diario detecte una bajada de precio ≥15% en tu lista, te avisamos por email.",
                             "PT": "Quando o scraper diário detetar uma descida de preço ≥15% na tua lista, avisamos-te por email."},
    "notifs_toggle":        {"ES": "Recibir alertas por email",  "PT": "Receber alertas por email"},
    "btn_save_notifs":      {"ES": "💾 Guardar",                 "PT": "💾 Guardar"},
    "notifs_saved":         {"ES": "Preferencia de notificaciones guardada.",
                             "PT": "Preferência de notificações guardada."},
    "security":             {"ES": "Seguridad",                  "PT": "Segurança"},
    "last_access":          {"ES": "Último acceso: {ts}",        "PT": "Último acesso: {ts}"},
    "first_time":           {"ES": "primera vez",                "PT": "primeira vez"},
    # ── optimizador ───────────────────────────────────────────────────────────
    "optimizer_title":      {"ES": "🗺️ Optimizador de compra",  "PT": "🗺️ Optimizador de compra"},
    # ── home / general ────────────────────────────────────────────────────────
    "app_subtitle":         {"ES": "Compara precios en 15 supermercados de España y Portugal",
                             "PT": "Compara preços em 15 supermercados de Espanha e Portugal"},
    "login_tab":            {"ES": "Iniciar sesión",             "PT": "Iniciar sessão"},
    "register_tab":         {"ES": "Crear cuenta",               "PT": "Criar conta"},
}

_DAYS_ES = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves",
            4: "Viernes", 5: "Sábado", 6: "Domingo"}
_DAYS_PT = {0: "Segunda", 1: "Terça", 2: "Quarta", 3: "Quinta",
            4: "Sexta", 5: "Sábado", 6: "Domingo"}


def _lang() -> str:
    """Returns 'PT' only when the active user has pais_activo == 'PT'."""
    try:
        import streamlit as st
        u = st.session_state.get("usuario")
        if u and getattr(u, "pais_activo", "ES") == "PT":
            return "PT"
    except Exception:
        pass
    return "ES"


def t(key: str, **kwargs) -> str:
    """Translates key to the current language.

    Supports format kwargs: t("sidebar_hello", name="María") → "Hola, **María**"
    Falls back to the key itself if not found.
    """
    lang = _lang()
    entry = _STRINGS.get(key, {})
    text = entry.get(lang) or entry.get("ES") or key
    if kwargs:
        text = text.format(**kwargs)
    return text


def shopping_days() -> list[str]:
    """Returns the weekday names in the current language."""
    return list((_DAYS_PT if _lang() == "PT" else _DAYS_ES).values())


def shopping_days_inv() -> dict[str, int]:
    """Returns {day_name: int} in the current language."""
    d = _DAYS_PT if _lang() == "PT" else _DAYS_ES
    return {v: k for k, v in d.items()}
