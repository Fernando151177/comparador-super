"""Modelo PT scraper — misma plataforma que Continente (Sonae).

Modelo y Continente pertenecen al grupo Sonae. modelo.pt no tiene tienda
online activa, así que usamos directamente la búsqueda de continente.pt.
"""
from scrapers.pt.continente import ContinenteScraper


class ModeloScraper(ContinenteScraper):
    NOMBRE = "Modelo"
    CODIGO = "MODELO_PT"
    PAIS = "PT"
