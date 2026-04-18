"""Siembra datos de demostración: 20 productos con precios en 5 supermercados ES.

Uso:
    python scripts/seed_demo_data.py

Idempotente: usa ON CONFLICT DO NOTHING para EANs existentes y
ON CONFLICT (producto_id, supermercado_id, fecha_scraping) DO NOTHING
para no duplicar precios del mismo día.
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from database.connection import get_connection

# ── Datos ─────────────────────────────────────────────────────────────────────

_PRODUCTOS = [
    # (ean, nombre, marca, categoria, subcategoria, unidad_medida)
    ("8410031990004", "Leche entera 1L Hacendado", "Hacendado", "Lácteos", "Leche", "1L"),
    ("8480000105912", "Leche semidesnatada 1L", "Hacendado", "Lácteos", "Leche", "1L"),
    ("8410031991056", "Yogur natural 4 uds", "Hacendado", "Lácteos", "Yogur", "4x125g"),
    ("8480000107374", "Mantequilla 250g", "Hacendado", "Lácteos", "Mantequilla", "250g"),
    ("8412400001234", "Huevos camperos L 12 uds", "Granja El Valle", "Huevos", "Huevos", "12 uds"),
    ("8410031992001", "Pan de molde blanco 500g", "Bimbo", "Panadería", "Pan", "500g"),
    ("8480000200078", "Aceite de oliva virgen 1L", "Hacendado", "Aceites", "Oliva", "1L"),
    ("8410031993004", "Aceite de girasol 1L", "Koipesol", "Aceites", "Girasol", "1L"),
    ("8412300045231", "Pasta espagueti 500g", "Gallo", "Pasta", "Espagueti", "500g"),
    ("8480000102354", "Arroz redondo 1kg", "Hacendado", "Cereales", "Arroz", "1kg"),
    ("8410031994007", "Tomate triturado 400g", "Solís", "Conservas", "Tomate", "400g"),
    ("8480000104892", "Atún en aceite pack 3", "Hacendado", "Conservas", "Atún", "3x80g"),
    ("8412400005678", "Pechuga de pollo 1kg", "Coren", "Carne", "Pollo", "1kg"),
    ("8480000110001", "Carne picada 500g", "Hacendado", "Carne", "Vacuno", "500g"),
    ("8410031995010", "Jamón serrano 100g", "Argal", "Charcutería", "Jamón", "100g"),
    ("8480000201005", "Manzana golden 1kg", "Hacendado", "Fruta", "Manzana", "1kg"),
    ("8410031996013", "Plátanos de Canarias 1kg", "Plátano de Canarias", "Fruta", "Plátano", "1kg"),
    ("8480000203009", "Detergente líquido 30 lavados", "Hacendado", "Limpieza", "Detergente", "30 lav"),
    ("8410031997016", "Papel higiénico 12 rollos", "Renova", "Higiene", "Papel", "12 uds"),
    ("8480000300000", "Cerveza lager pack 6", "Hacendado", "Bebidas", "Cerveza", "6x33cl"),
]

# Supermercados ES por código
_SUPERS_ES = ["MERCADONA_ES", "LIDL_ES", "CARREFOUR_ES", "DIA_ES", "ALCAMPO_ES"]

# Precios por supermercado (misma lista, variación ±30%)
import random
random.seed(42)

_BASE_PRICES = [
    1.05, 0.98, 1.20, 1.89, 2.45,
    1.35, 3.99, 1.49, 0.89, 0.95,
    0.79, 3.25, 5.99, 3.10, 1.75,
    2.20, 1.85, 6.49, 3.99, 5.99,
]

_PRECIO_KG = {
    "1L": None, "4x125g": None, "12 uds": None, "250g": 7.56, "500g": None,
    "1kg": None, "400g": None, "3x80g": None, "100g": 17.50, "30 lav": None,
    "12 uds": None, "6x33cl": None,
}


def seed() -> None:
    hoy = str(date.today())

    with get_connection() as conn:
        # ── Obtener IDs de supermercados ──────────────────────────────────────
        super_ids: dict[str, int] = {}
        for codigo in _SUPERS_ES:
            row = conn.execute(
                "SELECT id FROM supermercados WHERE codigo = %s", (codigo,)
            ).fetchone()
            if row:
                super_ids[codigo] = row["id"]
            else:
                print(f"[seed] Supermercado no encontrado: {codigo} (ejecuta init_db primero)")

        if not super_ids:
            print("[seed] No se encontró ningún supermercado. Ejecuta init_db primero.")
            return

        inserted_products = 0
        inserted_prices = 0

        for i, (ean, nombre, marca, cat, subcat, unidad) in enumerate(_PRODUCTOS):
            # ── Insertar producto (si no existe) ──────────────────────────────
            first_super_id = next(iter(super_ids.values()))
            row = conn.execute(
                "INSERT INTO productos (ean, nombre, marca, categoria, subcategoria, "
                "    unidad_medida, supermercado_id, activo) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,TRUE) "
                "ON CONFLICT (ean) DO NOTHING RETURNING id",
                (ean, nombre, marca, cat, subcat, unidad, first_super_id),
            ).fetchone()

            if row:
                prod_id = row["id"]
                inserted_products += 1
            else:
                r2 = conn.execute(
                    "SELECT id FROM productos WHERE ean = %s", (ean,)
                ).fetchone()
                if r2 is None:
                    continue
                prod_id = r2["id"]

            # ── Insertar precios por supermercado ─────────────────────────────
            base = _BASE_PRICES[i]
            for codigo, super_id in super_ids.items():
                variacion = random.uniform(0.75, 1.30)
                precio = round(base * variacion, 2)
                precio_kilo = round(precio / (base * 0.5), 2) if base < 5 else None

                r = conn.execute(
                    """
                    INSERT INTO precios_historicos
                        (producto_id, supermercado_id, precio, moneda,
                         precio_por_unidad_normalizado, unidad_normalizacion,
                         fecha_scraping, disponible, peso_variable)
                    VALUES (%s,%s,%s,'EUR',%s,%s,%s,TRUE,FALSE)
                    ON CONFLICT (producto_id, supermercado_id, fecha_scraping) DO NOTHING
                    RETURNING id
                    """,
                    (prod_id, super_id, precio, precio_kilo, "kg" if precio_kilo else None, hoy),
                ).fetchone()
                if r:
                    inserted_prices += 1

    print(f"[seed] Productos insertados: {inserted_products}")
    print(f"[seed] Precios insertados:   {inserted_prices} (fecha: {hoy})")
    print("[seed] ¡Listo! Recarga la app para ver los datos de demo.")


if __name__ == "__main__":
    seed()
