# Spain scrapers
from scrapers.es.mercadona import MercadonaESScraper
from scrapers.es.lidl_es import LidlESScraper
from scrapers.es.carrefour_es import CarrefourESScraper
from scrapers.es.alcampo import AlcampoScraper
from scrapers.es.dia import DiaScraper
from scrapers.es.hipercor import HipercorScraper
from scrapers.es.ahorramas import AhorramasScraper
from scrapers.es.cash_family import CashFamilyScraper
from scrapers.es.facua import (
    FACUABaseScraper,
    FACUAMercadonaScraper,
    FACUACarrefourScraper,
    FACUAAlcampoScraper,
    FACUAHipercorScraper,
    FACUADiaScraper,
    FACUAEroskiScraper,
)

__all__ = [
    "MercadonaESScraper",
    "LidlESScraper",
    "CarrefourESScraper",
    "AlcampoScraper",
    "DiaScraper",
    "HipercorScraper",
    "AhorramasScraper",
    "CashFamilyScraper",
    "FACUABaseScraper",
    "FACUAMercadonaScraper",
    "FACUACarrefourScraper",
    "FACUAAlcampoScraper",
    "FACUAHipercorScraper",
    "FACUADiaScraper",
    "FACUAEroskiScraper",
]
