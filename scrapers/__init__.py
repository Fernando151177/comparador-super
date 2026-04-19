# Scraper registry — todos los scrapers disponibles.
from scrapers.es import (
    MercadonaESScraper,
    LidlESScraper,
    CarrefourESScraper,
    AlcampoScraper,
    DiaScraper,
    HipercorScraper,
    AhorramasScraper,
    CashFamilyScraper,
    FACUAMercadonaScraper,
    FACUACarrefourScraper,
    FACUAAlcampoScraper,
    FACUAHipercorScraper,
    FACUADiaScraper,
    FACUAEroskiScraper,
)
from scrapers.pt import (
    ContinenteScraper,
    PingoDoctScraper,
    LidlPTScraper,
    MercadonaPTScraper,
    IntermarchePTScraper,
    AldiPTScraper,
    ModeloScraper,
)

# Lista activa para el scheduler y comparaciones
# Estrategia: FACUA como fuente primaria (datos reales verificados, sin bloqueo)
# + Mercadona API y Lidl API para catálogo completo
# Scrapers bloqueados por Cloudflare (CarrefourES, Alcampo, Día, Hipercor) desactivados
ALL_SCRAPERS_ES = [
    LidlESScraper,           # API pública — catálogo completo, fiable
    MercadonaESScraper,      # API interna — catálogo completo, fiable
    FACUAMercadonaScraper,   # FACUA — precios verificados Mercadona (4 categorías)
    FACUACarrefourScraper,   # FACUA — precios verificados Carrefour (4 categorías)
    FACUAAlcampoScraper,     # FACUA — precios verificados Alcampo (4 categorías)
    FACUAHipercorScraper,    # FACUA — precios verificados Hipercor (4 categorías)
    FACUADiaScraper,         # FACUA — precios verificados Día (4 categorías)
    FACUAEroskiScraper,      # FACUA — precios verificados Eroski (4 categorías)
    # CarrefourESScraper    → bloqueado por Cloudflare
    # AlcampoScraper        → bloqueado por Cloudflare
    # DiaScraper            → bloqueado por Cloudflare
    # HipercorScraper       → bloqueado por Cloudflare
    # AhorramasScraper      → requiere Playwright (no disponible en Cloud)
    # CashFamilyScraper     → sin tienda online activa
]

ALL_SCRAPERS_PT = [
    ContinenteScraper,
    PingoDoctScraper,
    LidlPTScraper,
    MercadonaPTScraper,
    IntermarchePTScraper,
    AldiPTScraper,
    ModeloScraper,
]

ALL_SCRAPERS = ALL_SCRAPERS_ES + ALL_SCRAPERS_PT

__all__ = [
    "ALL_SCRAPERS", "ALL_SCRAPERS_ES", "ALL_SCRAPERS_PT",
    "MercadonaESScraper", "LidlESScraper", "CarrefourESScraper",
    "AlcampoScraper", "DiaScraper", "HipercorScraper",
    "AhorramasScraper", "CashFamilyScraper",
    "FACUAMercadonaScraper", "FACUACarrefourScraper", "FACUAAlcampoScraper",
    "FACUAHipercorScraper", "FACUADiaScraper", "FACUAEroskiScraper",
    "ContinenteScraper", "PingoDoctScraper", "LidlPTScraper",
    "MercadonaPTScraper", "IntermarchePTScraper", "AldiPTScraper",
    "ModeloScraper",
]
