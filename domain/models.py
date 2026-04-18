"""Modelos de dominio puros — sin dependencias de base de datos ni framework."""
from dataclasses import dataclass, field
from typing import Optional


# ── Entidades principales ─────────────────────────────────────────────────────

@dataclass
class Usuario:
    id: str                     # UUID generado con uuid.uuid4()
    nombre: str
    email: str
    password_hash: str          # hash bcrypt de la contraseña
    pais_activo: str            # 'ES' | 'PT' | 'AMBOS'
    codigo_postal: str
    dia_compra: int             # 0 = Lunes … 6 = Domingo
    created_at: str             # ISO-8601
    ultimo_acceso: Optional[str]
    activo: bool
    # Hábitos de compra (cargados desde configuracion_usuario)
    supermercados_favoritos: list = field(default_factory=list)  # ['MERCADONA_ES', ...]
    coste_desplazamiento: float = 0.0   # € por visita extra a un supermercado
    notificaciones_email: bool = False  # recibir email en bajadas de precio
    email_verificado: bool = True       # False hasta que el usuario confirme su email


@dataclass
class Supermercado:
    id: int
    nombre: str
    codigo: str                 # 'MERCADONA_ES', 'LIDL_PT', …
    pais: str                   # 'ES' | 'PT'
    base_url: str
    url_online: Optional[str]
    activo: bool


@dataclass
class Producto:
    id: int
    ean: Optional[str]
    nombre: str
    marca: Optional[str]
    categoria: Optional[str]
    subcategoria: Optional[str]
    unidad_medida: Optional[str]
    url_imagen: Optional[str]
    supermercado_id: int
    activo: bool
    created_at: str
    updated_at: str


@dataclass
class PrecioHistorico:
    id: int
    producto_id: int
    supermercado_id: int
    precio: float
    moneda: str                 # 'EUR'
    precio_por_unidad_normalizado: Optional[float]
    unidad_normalizacion: Optional[str]   # 'kg' | 'L' | 'ud'
    fecha_scraping: str         # 'YYYY-MM-DD'
    disponible: bool
    peso_variable: bool


@dataclass
class ItemLista:
    id: int
    usuario_id: str             # UUID
    producto_id: Optional[int]  # None hasta que se vincule a un producto de la BD
    ean: Optional[str]
    query_texto: str
    cantidad: int
    prioridad: int              # 0 = normal, 1 = alta
    comprado: bool


@dataclass
class Alerta:
    id: int
    usuario_id: str             # UUID
    producto_id: Optional[int]
    ean: Optional[str]
    tipo_alerta: str            # 'BAJADA_PRECIO' | 'OFERTA_ENVIO' | 'CROSS_BORDER'
    umbral_precio: Optional[float]
    activa: bool
    ultima_activacion: Optional[str]


@dataclass
class SesionCompra:
    id: int
    usuario_id: str             # UUID
    fecha: str
    supermercados_visitados: Optional[str]   # JSON array de códigos
    total_gastado: float
    total_ahorrado: float
    productos_comprados: Optional[str]        # JSON array


# ── Objeto de transferencia de scrapers ──────────────────────────────────────

@dataclass
class ScrapedProduct:
    """Resultado en bruto de un scraper, antes de guardarse en la base de datos.

    Los scrapers devuelven listas de estos objetos; el scheduler los mapea
    a filas Producto y PrecioHistorico a través de los repositorios.
    """
    nombre: str
    precio: float
    moneda: str = "EUR"
    ean: Optional[str] = None
    marca: Optional[str] = None
    categoria: Optional[str] = None
    subcategoria: Optional[str] = None
    precio_kilo: Optional[float] = None          # precio normalizado por kg o L
    unidad_normalizacion: Optional[str] = None   # 'kg' | 'L' | 'ud'
    unidad_medida: Optional[str] = None          # cadena original, ej. '1L'
    url_imagen: Optional[str] = None
    url_producto: Optional[str] = None
    disponible: bool = True
    nombre_buscado: Optional[str] = None         # búsqueda que encontró este producto


# ── Objetos de transferencia del optimizador ─────────────────────────────────

@dataclass
class OptimizerItem:
    """Asignación de un producto dentro de un plan de compra."""
    query_texto: str
    cantidad: int
    producto_nombre: str
    supermercado_nombre: str
    supermercado_codigo: str
    precio_unitario: float
    precio_total: float
    precio_kilo: Optional[float]
    url_producto: Optional[str]
    ahorro_vs_caro: float        # ahorro frente a la opción más cara del día


@dataclass
class OptimizerResult:
    """Salida completa del optimizador de sábado para un usuario."""
    plan: list[OptimizerItem]
    por_supermercado: dict[str, list[OptimizerItem]]   # codigo → items
    total_optimo: float
    total_si_uno: dict[str, float]    # codigo → total comprando todo allí
    ahorro_total: float               # frente al supermercado más barato único
    productos_sin_precio: list[str]   # productos sin precio hoy
    fecha: str                        # 'YYYY-MM-DD'
