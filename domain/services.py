"""Domain services — business logic that coordinates repositories.

Services are stateless functions / thin classes that operate on domain
models.  They do NOT import Streamlit or any UI code.
"""
from datetime import date
from typing import Optional

from domain.models import ScrapedProduct, PrecioHistorico


# ── Price normalization ───────────────────────────────────────────────────────

def normalize_price_per_kg(precio: float, unidad_texto: str) -> tuple[Optional[float], Optional[str]]:
    """Parses a unit string and returns (price_per_kg_or_L, unit_label).

    Handles common Spanish / Portuguese formats:
        '1 l', '500 ml', '150 g', '1 kg', '4x195 g', '2x1 kg', '75 cl'

    Returns (None, None) if the string cannot be parsed.
    """
    import re

    if not unidad_texto or not precio:
        return None, None

    texto = unidad_texto.lower().strip()

    # Pattern: NxM unit  e.g. '4x195 g', '2x1 kg'
    m = re.match(r'(\d+)\s*[x×]\s*([\d.,]+)\s*(kg|g|l|ml|cl)', texto)
    if m:
        unidades = float(m.group(1))
        cantidad = float(m.group(2).replace(',', '.'))
        unit = m.group(3)
    else:
        # Pattern: N unit  e.g. '500 ml', '1.5 kg'
        m = re.match(r'([\d.,]+)\s*(kg|g|l|ml|cl)', texto)
        if not m:
            return None, None
        unidades = 1.0
        cantidad = float(m.group(1).replace(',', '.'))
        unit = m.group(2)

    total = unidades * cantidad
    if unit in ('g', 'ml'):
        total_kg = total / 1000.0
        label = 'kg' if unit == 'g' else 'L'
    elif unit == 'cl':
        total_kg = total / 100.0
        label = 'L'
    elif unit == 'l':
        total_kg = total
        label = 'L'
    else:  # kg
        total_kg = total
        label = 'kg'

    if total_kg <= 0:
        return None, None

    return round(precio / total_kg, 4), label


# ── Cross-border comparison ───────────────────────────────────────────────────

def compare_cross_border(
    prices_es: list[dict],
    prices_pt: list[dict],
    product_name: str,
) -> dict:
    """Compares today's prices for the same product in ES and PT.

    Args:
        prices_es: List of {'supermercado': str, 'precio': float} for Spain.
        prices_pt: List of {'supermercado': str, 'precio': float} for Portugal.
        product_name: Human-readable product name for the report.

    Returns:
        Dict with keys: product, cheapest_es, cheapest_pt, saving_eur, cheaper_in.
    """
    best_es = min(prices_es, key=lambda p: p['precio']) if prices_es else None
    best_pt = min(prices_pt, key=lambda p: p['precio']) if prices_pt else None

    if not best_es or not best_pt:
        return {
            "product": product_name,
            "cheapest_es": best_es,
            "cheapest_pt": best_pt,
            "saving_eur": None,
            "cheaper_in": None,
        }

    saving = abs(best_es['precio'] - best_pt['precio'])
    cheaper_in = "ES" if best_es['precio'] <= best_pt['precio'] else "PT"

    return {
        "product": product_name,
        "cheapest_es": best_es,
        "cheapest_pt": best_pt,
        "saving_eur": round(saving, 2),
        "cheaper_in": cheaper_in,
    }


# ── Savings calculator ────────────────────────────────────────────────────────

def calculate_real_savings(
    precio_pagado: float,
    precio_max_hoy: float,
    cantidad: int = 1,
) -> float:
    """Returns how much the user saved vs. the most expensive option today."""
    return round((precio_max_hoy - precio_pagado) * cantidad, 2)
