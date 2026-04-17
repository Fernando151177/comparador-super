"""Configuración compartida de pytest.

Marcas disponibles:
    @pytest.mark.integration  — requiere DATABASE_URL real (Supabase).
                                 Se omiten por defecto; ejecutar con:
                                 pytest -m integration
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: tests que necesitan conexión real a Supabase (omitidos por defecto)",
    )


def pytest_collection_modifyitems(config, items):
    """Salta los tests de integración salvo que se pidan explícitamente."""
    if config.getoption("-m", default="") == "integration":
        return
    skip_integration = pytest.mark.skip(reason="Test de integración — ejecuta con: pytest -m integration")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
