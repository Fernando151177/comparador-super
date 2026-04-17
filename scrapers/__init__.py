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

# Lista completa para el scheduler
ALL_SCRAPERS_ES = [
    LidlESScraper,       # API pública — funciona desde Streamlit Cloud
    MercadonaESScraper,  # Catálogo completo — lento pero funciona
    # CarrefourESScraper  — bloquea IPs de servidor
    # AlcampoScraper      — bloquea IPs de servidor
    # DiaScraper          — bloquea IPs de servidor
    # HipercorScraper     — bloquea IPs de servidor
    # AhorramasScraper    — bloquea IPs de servidor
    # CashFamilyScraper   — bloquea IPs de servidor
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
    "ContinenteScraper", "PingoDoctScraper", "LidlPTScraper",
    "MercadonaPTScraper", "IntermarchePTScraper", "AldiPTScraper",
    "ModeloScraper",
]
