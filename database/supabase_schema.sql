-- ════════════════════════════════════════════════════════════════════════════
-- Smart Shopping Iberia — Schema para Supabase (PostgreSQL)
--
-- INSTRUCCIONES (primera vez):
--   1. Ve a https://app.supabase.com → tu proyecto → SQL Editor
--   2. Pega este fichero completo y haz clic en "Run"
--   3. Solo necesitas ejecutarlo UNA vez
--
-- Si ya tienes el schema antiguo, ejecuta solo la sección
-- "MIGRACIONES" al final del fichero.
-- ════════════════════════════════════════════════════════════════════════════


-- ── Usuarios ──────────────────────────────────────────────────────────────────
-- Auth propia con bcrypt (sin Supabase Auth)
CREATE TABLE IF NOT EXISTS usuarios (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre          TEXT        NOT NULL,
    email           TEXT        NOT NULL UNIQUE,
    password_hash   TEXT        NOT NULL DEFAULT '',
    pais_activo     TEXT        NOT NULL DEFAULT 'ES',   -- ES | PT | AMBOS
    codigo_postal   TEXT        NOT NULL DEFAULT '28001',
    dia_compra      INTEGER     NOT NULL DEFAULT 5,       -- 0=Lun … 6=Dom
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    ultimo_acceso   TIMESTAMPTZ,
    activo          BOOLEAN     NOT NULL DEFAULT TRUE
);


-- ── Sesiones (tokens propios, sin Supabase Auth) ──────────────────────────────
CREATE TABLE IF NOT EXISTS sesiones (
    id          SERIAL      PRIMARY KEY,
    usuario_id  UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token       TEXT        NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sesiones_token      ON sesiones(token);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario_id ON sesiones(usuario_id);


-- ── Supermercados ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS supermercados (
    id          SERIAL      PRIMARY KEY,
    nombre      TEXT        NOT NULL,
    codigo      TEXT        NOT NULL UNIQUE,  -- MERCADONA_ES, LIDL_PT, …
    pais        TEXT        NOT NULL,          -- ES | PT
    base_url    TEXT        NOT NULL,
    url_online  TEXT,
    activo      BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- ── Productos ─────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS productos (
    id              SERIAL      PRIMARY KEY,
    ean             TEXT,
    nombre          TEXT        NOT NULL,
    marca           TEXT,
    categoria       TEXT,
    subcategoria    TEXT,
    unidad_medida   TEXT,
    url_imagen      TEXT,
    supermercado_id INTEGER     NOT NULL REFERENCES supermercados(id),
    activo          BOOLEAN     NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_productos_ean    ON productos(ean) WHERE ean IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_productos_super  ON productos(supermercado_id);
CREATE INDEX IF NOT EXISTS idx_productos_nombre ON productos(nombre);


-- ── Historial de precios ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS precios_historicos (
    id                              SERIAL        PRIMARY KEY,
    producto_id                     INTEGER       NOT NULL REFERENCES productos(id),
    supermercado_id                 INTEGER       NOT NULL REFERENCES supermercados(id),
    precio                          NUMERIC(10,4) NOT NULL,
    moneda                          TEXT          NOT NULL DEFAULT 'EUR',
    precio_por_unidad_normalizado   NUMERIC(10,4),
    unidad_normalizacion            TEXT,     -- kg | L | ud
    fecha_scraping                  DATE          NOT NULL,
    disponible                      BOOLEAN       NOT NULL DEFAULT TRUE,
    peso_variable                   BOOLEAN       NOT NULL DEFAULT FALSE,
    created_at                      TIMESTAMPTZ   NOT NULL DEFAULT now(),
    UNIQUE (producto_id, supermercado_id, fecha_scraping)
);
CREATE INDEX IF NOT EXISTS idx_precios_fecha ON precios_historicos(fecha_scraping);
CREATE INDEX IF NOT EXISTS idx_precios_prod  ON precios_historicos(producto_id);
CREATE INDEX IF NOT EXISTS idx_precios_super ON precios_historicos(supermercado_id);


-- ── Lista de compra por usuario ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS lista_usuario (
    id          SERIAL      PRIMARY KEY,
    usuario_id  UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    producto_id INTEGER     REFERENCES productos(id),
    ean         TEXT,
    query_texto TEXT        NOT NULL,
    cantidad    INTEGER     NOT NULL DEFAULT 1,
    prioridad   INTEGER     NOT NULL DEFAULT 0,
    comprado    BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_lista_usuario ON lista_usuario(usuario_id);


-- ── Alertas de precio ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alertas (
    id                  SERIAL        PRIMARY KEY,
    usuario_id          UUID          NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    producto_id         INTEGER       REFERENCES productos(id),
    ean                 TEXT,
    tipo_alerta         TEXT          NOT NULL DEFAULT 'BAJADA_PRECIO',
    umbral_precio       NUMERIC(10,4),
    activa              BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ   NOT NULL DEFAULT now(),
    ultima_activacion   TIMESTAMPTZ
);


-- ── Productos no perecederos ──────────────────────────────────────────────────
-- Tabla auxiliar opcional; el detector infiere no perecederos por categoría.
CREATE TABLE IF NOT EXISTS productos_no_perecederos (
    id                          SERIAL  PRIMARY KEY,
    producto_id                 INTEGER NOT NULL UNIQUE REFERENCES productos(id),
    vida_util_dias              INTEGER,
    stock_recomendado_unidades  INTEGER NOT NULL DEFAULT 3
);


-- ── Sesiones de compra (historial de ahorro) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS sesiones_compra (
    id                      SERIAL        PRIMARY KEY,
    usuario_id              UUID          NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    fecha                   DATE          NOT NULL DEFAULT current_date,
    supermercados_visitados JSONB,
    total_gastado           NUMERIC(10,4) NOT NULL DEFAULT 0,
    total_ahorrado          NUMERIC(10,4) NOT NULL DEFAULT 0,
    productos_comprados     JSONB
);


-- ── Pedidos online ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS pedidos_online (
    id              SERIAL        PRIMARY KEY,
    usuario_id      UUID          NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    supermercado_id INTEGER       NOT NULL REFERENCES supermercados(id),
    fecha           TIMESTAMPTZ   NOT NULL DEFAULT now(),
    estado          TEXT          NOT NULL DEFAULT 'PENDIENTE',
    url_pedido      TEXT,
    total_estimado  NUMERIC(10,4),
    coste_envio     NUMERIC(10,4)
);


-- ── Configuración por usuario ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS configuracion_usuario (
    id          SERIAL      PRIMARY KEY,
    usuario_id  UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    clave       TEXT        NOT NULL,
    valor       TEXT        NOT NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (usuario_id, clave)
);


-- ════════════════════════════════════════════════════════════════════════════
-- DATOS INICIALES: 15 supermercados
-- ════════════════════════════════════════════════════════════════════════════
INSERT INTO supermercados (nombre, codigo, pais, base_url, url_online) VALUES
    ('Mercadona',   'MERCADONA_ES',   'ES', 'https://tienda.mercadona.es',            'https://tienda.mercadona.es'),
    ('Lidl',        'LIDL_ES',        'ES', 'https://www.lidl.es',                    'https://www.lidl.es/p/compras-online'),
    ('Alcampo',     'ALCAMPO_ES',     'ES', 'https://www.alcampo.es',                 'https://www.alcampo.es/compra-online'),
    ('Ahorramas',   'AHORRAMAS_ES',   'ES', 'https://www.ahorramas.com',              NULL),
    ('Hipercor',    'HIPERCOR_ES',    'ES', 'https://www.hipercor.es',                'https://www.hipercor.es/supermercado'),
    ('Carrefour',   'CARREFOUR_ES',   'ES', 'https://www.carrefour.es',               'https://www.carrefour.es/supermercado'),
    ('Día',         'DIA_ES',         'ES', 'https://www.dia.es',                     'https://www.dia.es/tienda-online'),
    ('Family Cash', 'CASH_FAMILY_ES', 'ES', 'https://www.familycash.es',              NULL),
    ('Continente',  'CONTINENTE_PT',  'PT', 'https://www.continente.pt',              'https://www.continente.pt'),
    ('Pingo Doce',  'PINGO_DOCE_PT',  'PT', 'https://www.pingodoce.pt',               'https://www.pingodoce.pt/compras-online'),
    ('Modelo',      'MODELO_PT',      'PT', 'https://www.continente.pt/lojas/modelo', NULL),
    ('Lidl PT',     'LIDL_PT',        'PT', 'https://www.lidl.pt',                    'https://www.lidl.pt/p/compras-online'),
    ('Mercadona PT','MERCADONA_PT',   'PT', 'https://www.mercadona.pt',               'https://www.mercadona.pt'),
    ('Intermarché', 'INTERMARCHE_PT', 'PT', 'https://www.intermarche.pt',             NULL),
    ('Aldi PT',     'ALDI_PT',        'PT', 'https://www.aldi.pt',                    NULL)
ON CONFLICT (codigo) DO NOTHING;


-- ════════════════════════════════════════════════════════════════════════════
-- MIGRACIONES (ejecutar solo si ya tenías el schema antiguo)
-- ════════════════════════════════════════════════════════════════════════════

-- Añadir password_hash a usuarios (si no existe):
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS password_hash TEXT NOT NULL DEFAULT '';

-- Eliminar la FK a auth.users (si existe):
ALTER TABLE usuarios DROP CONSTRAINT IF EXISTS usuarios_id_fkey;

-- Crear tabla sesiones (si no existe):
CREATE TABLE IF NOT EXISTS sesiones (
    id          SERIAL      PRIMARY KEY,
    usuario_id  UUID        NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    token       TEXT        NOT NULL UNIQUE,
    expires_at  TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_sesiones_token      ON sesiones(token);
CREATE INDEX IF NOT EXISTS idx_sesiones_usuario_id ON sesiones(usuario_id);
