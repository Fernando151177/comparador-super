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
ALL_SCRAPERS_ES = [
    LidlESScraper,           # API pública — funciona desde Streamlit Cloud
    MercadonaESScraper,      # API interna — catálogo completo
    FACUACarrefourScraper,   # FACUA — datos verificados, sin bloqueo
    FACUAAlcampoScraper,     # FACUA — datos verificados, sin bloqueo
    FACUAHipercorScraper,    # FACUA — datos verificados, sin bloqueo
    FACUADiaScraper,         # FACUA — datos verificados, sin bloqueo
    FACUAEroskiScraper,      # FACUA — datos verificados, sin bloqueo
    AhorramasScraper,        # Playwright stealth
    CashFamilyScraper,       # Playwright stealth (sin tienda online activa)
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
