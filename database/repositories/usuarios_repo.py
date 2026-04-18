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

    def update_notificaciones_email(self, usuario_id: str, activo: bool) -> None:
        self._set_config(usuario_id, "notificaciones_email", "true" if activo else "false")

    def get_usuarios_con_notificaciones(self) -> list[dict]:
        """Devuelve usuarios activos, verificados y con notificaciones email activadas."""
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT u.id, u.nombre, u.email
                FROM usuarios u
                JOIN configuracion_usuario cu
                  ON cu.usuario_id = u.id
                 AND cu.clave = 'notificaciones_email'
                 AND cu.valor = 'true'
                WHERE u.activo = TRUE
                  AND u.email_verificado = TRUE
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def set_activo(self, usuario_id: str, activo: bool) -> None:
        """Activa o desactiva un usuario (admin)."""
        with get_connection() as conn:
            conn.execute(
                "UPDATE usuarios SET activo = %s WHERE id = %s",
                (activo, usuario_id),
            )

    def update_favoritos(self, usuario_id: str, codigos: list[str]) -> None:
        """Guarda la lista de supermercados favoritos del usuario."""
        import json
        self._set_config(usuario_id, "supermercados_favoritos", json.dumps(codigos))

    def update_coste_desplazamiento(self, usuario_id: str, coste: float) -> None:
        """Guarda el coste en € por visita extra a un supermercado."""
        self._set_config(usuario_id, "coste_desplazamiento", str(coste))

    def _set_config(self, usuario_id: str, clave: str, valor: str) -> None:
        with get_connection() as conn:
            conn.execute(
                """
                INSERT INTO configuracion_usuario (usuario_id, clave, valor)
                VALUES (%s, %s, %s)
                ON CONFLICT (usuario_id, clave) DO UPDATE
                    SET valor = EXCLUDED.valor, updated_at = now()
                """,
                (usuario_id, clave, valor),
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

    def set_verification_token(self, usuario_id: str, token: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE usuarios SET email_verificado = FALSE, token_verificacion = %s "
                "WHERE id = %s",
                (token, usuario_id),
            )

    def verify_email_token(self, token: str) -> Optional[str]:
        """Valida el token; si es correcto marca email_verificado=TRUE y devuelve el usuario_id."""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM usuarios WHERE token_verificacion = %s AND email_verificado = FALSE",
                (token,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE usuarios SET email_verificado = TRUE, token_verificacion = NULL "
                "WHERE id = %s",
                (row["id"],),
            )
        return str(row["id"])

    def deactivate(self, usuario_id: str) -> None:
        with get_connection() as conn:
            conn.execute(
                "UPDATE usuarios SET activo = FALSE WHERE id = %s",
                (usuario_id,),
            )

    # ── Lectura ───────────────────────────────────────────────────────────────

    def get_by_id(self, usuario_id: str) -> Optional[Usuario]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE id = %s", (usuario_id,)
            ).fetchone()
            if row is None:
                return None
            config = self._load_config(conn, usuario_id)
        return self._to_model(row, config)

    def get_by_email(self, email: str) -> Optional[Usuario]:
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE LOWER(email) = LOWER(%s)",
                (email.strip(),),
            ).fetchone()
            if row is None:
                return None
            config = self._load_config(conn, row["id"])
        return self._to_model(row, config)

    @staticmethod
    def _load_config(conn, usuario_id) -> dict:
        rows = conn.execute(
            "SELECT clave, valor FROM configuracion_usuario WHERE usuario_id = %s",
            (str(usuario_id),),
        ).fetchall()
        return {r["clave"]: r["valor"] for r in rows}

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
    def _to_model(row: dict, config: dict | None = None) -> Usuario:
        import json
        cfg = config or {}
        try:
            favoritos = json.loads(cfg.get("supermercados_favoritos", "[]"))
        except Exception:
            favoritos = []
        try:
            coste = float(cfg.get("coste_desplazamiento", "0"))
        except Exception:
            coste = 0.0
        notif = cfg.get("notificaciones_email", "false") == "true"
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
            supermercados_favoritos=favoritos,
            coste_desplazamiento=coste,
            notificaciones_email=notif,
            email_verificado=bool(row.get("email_verificado", True)),
        )
