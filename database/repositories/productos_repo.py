"""Repositorio para la tabla 'productos'."""
from difflib import SequenceMatcher
from typing import Optional

from database.connection import get_connection
from domain.models import Producto, ScrapedProduct


class ProductosRepo:
    """Todo el acceso a base de datos para la tabla productos."""

    # ── Escritura ─────────────────────────────────────────────────────────────

    def create(
        self,
        nombre: str,
        supermercado_id: int,
        *,
        ean: Optional[str] = None,
        marca: Optional[str] = None,
        categoria: Optional[str] = None,
        subcategoria: Optional[str] = None,
        unidad_medida: Optional[str] = None,
        url_imagen: Optional[str] = None,
    ) -> int:
        """Inserta un nuevo producto y devuelve su id."""
        with get_connection() as conn:
            cur = conn.execute(
                """
                INSERT INTO productos
                    (ean, nombre, marca, categoria, subcategoria,
                     unidad_medida, url_imagen, supermercado_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (ean, nombre, marca, categoria, subcategoria,
                 unidad_medida, url_imagen, supermercado_id),
            )
            return cur.fetchone()["id"]

    def upsert_from_scraped(
        self, sp: ScrapedProduct, supermercado_id: int
    ) -> Optional[int]:
        """Busca un producto existente o inserta uno nuevo.

        Estrategia (en orden de prioridad):
        1. Coincidencia por EAN dentro del mismo supermercado.
        2. Coincidencia por nombre (similitud ≥80 %) dentro del mismo supermercado.
        3. Sin coincidencia → inserta fila nueva.

        Devuelve el id del producto.
        """
        # 1. Búsqueda por EAN
        if sp.ean:
            existing_id = self.get_id_by_ean(sp.ean, supermercado_id)
            if existing_id:
                self._update_metadata(existing_id, sp)
                return existing_id

        # 2. Búsqueda por nombre aproximado
        existing_id = self._fuzzy_match_id(sp.nombre, supermercado_id)
        if existing_id:
            self._update_metadata(existing_id, sp)
            return existing_id

        # 3. Insertar nuevo
        return self.create(
            nombre=sp.nombre,
            supermercado_id=supermercado_id,
            ean=sp.ean,
            marca=sp.marca,
            categoria=sp.categoria,
            subcategoria=sp.subcategoria,
            unidad_medida=sp.unidad_medida,
            url_imagen=sp.url_imagen,
        )

    # ── Lectura ───────────────────────────────────────────────────────────────

    def get_by_id(self, producto_id: int) -> Optional[Producto]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM productos WHERE id = %s", (producto_id,)
            )
            row = cur.fetchone()
        return self._to_model(row) if row else None

    def get_id_by_ean(self, ean: str, supermercado_id: int) -> Optional[int]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT id FROM productos WHERE ean = %s AND supermercado_id = %s",
                (ean, supermercado_id),
            )
            row = cur.fetchone()
        return row["id"] if row else None

    def search_by_name(
        self, query: str, supermercado_id: Optional[int] = None, limit: int = 20
    ) -> list[Producto]:
        """Búsqueda por nombre, insensible a mayúsculas (ILIKE).

        Busca en todos los supermercados o solo en uno.
        """
        with get_connection() as conn:
            if supermercado_id:
                cur = conn.execute(
                    """SELECT * FROM productos
                       WHERE nombre ILIKE %s AND supermercado_id = %s AND activo = TRUE
                       ORDER BY nombre LIMIT %s""",
                    (f"%{query}%", supermercado_id, limit),
                )
            else:
                cur = conn.execute(
                    """SELECT * FROM productos
                       WHERE nombre ILIKE %s AND activo = TRUE
                       ORDER BY nombre LIMIT %s""",
                    (f"%{query}%", limit),
                )
            rows = cur.fetchall()
        return [self._to_model(r) for r in rows]

    def list_by_supermarket(self, supermercado_id: int) -> list[Producto]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM productos WHERE supermercado_id = %s AND activo = TRUE",
                (supermercado_id,),
            )
            rows = cur.fetchall()
        return [self._to_model(r) for r in rows]

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _fuzzy_match_id(
        self, nombre: str, supermercado_id: int, threshold: float = 0.80
    ) -> Optional[int]:
        """Devuelve el id del producto con nombre más similar, o None."""
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT id, nombre FROM productos WHERE supermercado_id = %s AND activo = TRUE",
                (supermercado_id,),
            )
            rows = cur.fetchall()

        best_id: Optional[int] = None
        best_score = 0.0
        nombre_lower = nombre.lower()
        for row in rows:
            score = SequenceMatcher(None, nombre_lower, row["nombre"].lower()).ratio()
            if score > best_score:
                best_score = score
                best_id = row["id"]

        return best_id if best_score >= threshold else None

    def _update_metadata(self, producto_id: int, sp: ScrapedProduct) -> None:
        """Actualiza campos de metadata mutables en un producto existente."""
        with get_connection() as conn:
            conn.execute(
                """
                UPDATE productos
                SET nombre = %s, marca = %s, categoria = %s, subcategoria = %s,
                    unidad_medida = %s, url_imagen = %s, updated_at = now()
                WHERE id = %s
                """,
                (sp.nombre, sp.marca, sp.categoria, sp.subcategoria,
                 sp.unidad_medida, sp.url_imagen, producto_id),
            )

    @staticmethod
    def _to_model(row: dict) -> Producto:
        return Producto(
            id=row["id"],
            ean=row["ean"],
            nombre=row["nombre"],
            marca=row["marca"],
            categoria=row["categoria"],
            subcategoria=row["subcategoria"],
            unidad_medida=row["unidad_medida"],
            url_imagen=row["url_imagen"],
            supermercado_id=row["supermercado_id"],
            activo=bool(row["activo"]),
            created_at=str(row["created_at"]),
            updated_at=str(row["updated_at"]),
        )
