"""Poblar la BD con todos los productos reales de FACUA.

Rasca las 4 categorías × 6 supermercados y guarda los precios.
Uso: python scripts/seed_facua.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.init_db import init_db
from database.repositories.productos_repo import ProductosRepo
from database.repositories.precios_repo import PreciosRepo
from scrapers.es.facua import (
    FACUAMercadonaScraper,
    FACUACarrefourScraper,
    FACUAAlcampoScraper,
    FACUAHipercorScraper,
    FACUADiaScraper,
    FACUAEroskiScraper,
)

# Todas las queries para cubrir las 4 categorías
QUERIES = [
    "leche entera",
    "leche semidesnatada",
    "leche desnatada",
    "aceite de oliva",
    "aceite de girasol",
    "huevos",
]

SCRAPERS = [
    FACUAMercadonaScraper,
    FACUACarrefourScraper,
    FACUAAlcampoScraper,
    FACUAHipercorScraper,
    FACUADiaScraper,
    FACUAEroskiScraper,
]


def main() -> None:
    print("=== Seed FACUA — datos reales ===")
    init_db()

    productos_repo = ProductosRepo()
    precios_repo   = PreciosRepo()
    total = 0

    for cls in SCRAPERS:
        scraper = cls()
        print(f"\n[{scraper.NOMBRE}] Consultando FACUA...")
        try:
            results = scraper.scrape_products(QUERIES)
        except Exception as exc:
            print(f"  ERROR: {exc}")
            continue

        guardados = 0
        for sp in results:
            try:
                pid = productos_repo.upsert_from_scraped(sp, scraper.supermarket_id)
                if pid:
                    precios_repo.upsert_today(pid, scraper.supermarket_id, sp)
                    guardados += 1
                    print(f"  OK {sp.nombre} - {sp.precio:.2f}EUR")
            except Exception as exc:
                print(f"  ERR {sp.nombre}: {exc}")

        print(f"  → {guardados}/{len(results)} guardados")
        total += guardados

    print(f"\n=== Total guardados: {total} precios reales ===")


if __name__ == "__main__":
    main()
