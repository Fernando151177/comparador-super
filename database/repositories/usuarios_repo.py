"""Repositorio para la tabla 'usuarios'."""
from typing import Optional

from database.connection import get_connection
from domain.models import Usuario


class UsuariosRepo:
    """Todo el acceso a base de datos para la tabla usuarios."""

    # ── Escritura ─────────────────────────────────────────────────────────────

    def create(
        self,
        id: str,
        nombre: str,
        email: str,
        password_hash: str,
        pais_activo: str = "ES",
        codigo_postal: str = "28001",
        dia_compra: int = 5,
    ) -> Usuario:
        """Inserta un nuevo usuario y devuelve la fila creada."""
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO usuarios
                    (id, nombre, email, password_hash, pais_activo, codigo_postal, dia_compra)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (id, nombre, email.lower().strip(), password_hash,
                 pais_activo, codigo_postal, dia_compra),
            )
        return self.get_by_id(id)  # type: ignore[return-value]

    def update_ultimo_acceso(self, usuario_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE usuarios SET ultimo_acceso = now() WHERE id = %s",
                (usuario_id,),
            )

    def update_preferences(
        self,
        usuario_id: str,
        *,
        nombre: Optional[str] = None,
        pais_activo: Optional[str] = None,
        codigo_postal: Optional[str] = None,
        dia_compra: Optional[int] = None,
    ) -> None:
        fields: list[str] = []
        params: list = []

        if nombre is not None:
            fields.append("nombre = %s")
            params.append(nombre)
        if pais_activo is not None:
            fields.append("pais_activo = %s")
            params.append(pais_activo)
        if codigo_postal is not None:
            fields.append("codigo_postal = %s")
            params.append(codigo_postal)
        if dia_compra is not None:
            fields.append("dia_compra = %s")
            params.append(dia_compra)

        if not fields:
            return

        params.append(usuario_id)
        with get_connection() as conn:
            conn.execute(
                f"UPDATE usuarios SET {', '.join(fields)} WHERE id = %s",
                params,
            )

    def deactivate(self, usuario_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE usuarios SET activo = FALSE WHERE id = %s",
                (usuario_id,),
            )

    # ── Lectura ───────────────────────────────────────────────────────────────

    def get_by_id(self, usuario_id: str) -> Optional[Usuario]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM usuarios WHERE id = %s", (usuario_id,)
            )
            row = cur.fetchone()
        return self._to_model(row) if row else None

    def get_by_email(self, email: str) -> Optional[Usuario]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM usuarios WHERE LOWER(email) = LOWER(%s)",
                (email.strip(),),
            )
            row = cur.fetchone()
        return self._to_model(row) if row else None

    def list_active(self) -> list[Usuario]:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM usuarios WHERE activo = TRUE ORDER BY nombre"
            )
            rows = cur.fetchall()
        return [self._to_model(r) for r in rows]

    def email_exists(self, email: str) -> bool:
        with get_connection() as conn:
            cur = conn.execute(
                "SELECT 1 FROM usuarios WHERE LOWER(email) = LOWER(%s)",
                (email.strip(),),
            )
            row = cur.fetchone()
        return row is not None

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _to_model(row: dict) -> Usuario:
        return Usuario(
            id=str(row["id"]),
            nombre=row["nombre"],
            email=row["email"],
            password_hash=row["password_hash"],
            pais_activo=row["pais_activo"],
            codigo_postal=row["codigo_postal"],
            dia_compra=row["dia_compra"],
            created_at=str(row["created_at"]),
            ultimo_acceso=str(row["ultimo_acceso"]) if row["ultimo_acceso"] else None,
            activo=bool(row["activo"]),
        )
