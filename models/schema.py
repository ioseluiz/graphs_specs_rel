"""DDL del archivo de proyecto (.specrel) y versionado de esquema."""
from __future__ import annotations

SCHEMA_VERSION = 4

HEX_COLOR_CHECK = "GLOB '#[0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f][0-9A-Fa-f]'"

SCHEMA_SQL = f"""
CREATE TABLE IF NOT EXISTS project (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    code        TEXT NOT NULL DEFAULT '',
    name        TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    app_version TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    fill_color   TEXT NOT NULL CHECK (fill_color {HEX_COLOR_CHECK}),
    border_color TEXT NOT NULL CHECK (border_color {HEX_COLOR_CHECK}),
    sort_order   INTEGER NOT NULL DEFAULT 0,
    is_default   INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1))
);

CREATE TABLE IF NOT EXISTS sections (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    code_key    TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL DEFAULT '',
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    fill_color   TEXT CHECK (fill_color IS NULL OR fill_color {HEX_COLOR_CHECK}),
    border_color TEXT CHECK (border_color IS NULL OR border_color {HEX_COLOR_CHECK}),
    status_id    INTEGER REFERENCES statuses(id) ON DELETE SET NULL,
    progress     INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100),
    CHECK (length(trim(code)) > 0)
);

CREATE TABLE IF NOT EXISTS statuses (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    color      TEXT NOT NULL CHECK (color {HEX_COLOR_CHECK}),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1))
);

CREATE TABLE IF NOT EXISTS responsibles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    code       TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name       TEXT NOT NULL DEFAULT '',
    color      TEXT NOT NULL CHECK (color {HEX_COLOR_CHECK}),
    sort_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS section_responsibles (
    section_id     INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    responsible_id INTEGER NOT NULL REFERENCES responsibles(id) ON DELETE CASCADE,
    sort_order     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (section_id, responsible_id)
);

CREATE TABLE IF NOT EXISTS relations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id   INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    target_id   INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
    kind        TEXT NOT NULL DEFAULT 'ref' CHECK (kind = 'ref'),
    waypoints   TEXT,
    source_port TEXT CHECK (source_port IS NULL OR source_port IN ('top','right','bottom','left')),
    target_port TEXT CHECK (target_port IS NULL OR target_port IN ('top','right','bottom','left')),
    notes       TEXT,
    created_at  TEXT NOT NULL,
    CHECK (source_id <> target_id)
);
-- Una relación por par DIRIGIDO: A→B y B→A son dos flechas distintas.
CREATE UNIQUE INDEX IF NOT EXISTS ux_relations_directed ON relations (source_id, target_id);
CREATE INDEX IF NOT EXISTS ix_relations_source ON relations(source_id);
CREATE INDEX IF NOT EXISTS ix_relations_target ON relations(target_id);

CREATE TABLE IF NOT EXISTS node_positions (
    section_id INTEGER PRIMARY KEY REFERENCES sections(id) ON DELETE CASCADE,
    x          REAL NOT NULL,
    y          REAL NOT NULL,
    pinned     INTEGER NOT NULL DEFAULT 0 CHECK (pinned IN (0, 1))
);

CREATE TABLE IF NOT EXISTS layout3d (
    section_id INTEGER PRIMARY KEY REFERENCES sections(id) ON DELETE CASCADE,
    x REAL NOT NULL,
    y REAL NOT NULL,
    z REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS catalog (
    code_key      TEXT PRIMARY KEY,
    code          TEXT NOT NULL,
    title         TEXT NOT NULL,
    category_name TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

# Migraciones lineales: {versión_destino: [sentencias SQL]}
MIGRATIONS: dict[int, list[str]] = {
    # v2: color personalizado opcional por sección (prevalece sobre el de la categoría)
    2: [
        "ALTER TABLE sections ADD COLUMN fill_color TEXT",
        "ALTER TABLE sections ADD COLUMN border_color TEXT",
    ],
    # v3: estatus, avance y responsables por sección
    3: [
        f"""CREATE TABLE IF NOT EXISTS statuses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE COLLATE NOCASE,
            color TEXT NOT NULL CHECK (color {HEX_COLOR_CHECK}), sort_order INTEGER NOT NULL DEFAULT 0,
            is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)))""",
        f"""CREATE TABLE IF NOT EXISTS responsibles (
            id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE COLLATE NOCASE,
            name TEXT NOT NULL DEFAULT '', color TEXT NOT NULL CHECK (color {HEX_COLOR_CHECK}),
            sort_order INTEGER NOT NULL DEFAULT 0)""",
        """CREATE TABLE IF NOT EXISTS section_responsibles (
            section_id INTEGER NOT NULL REFERENCES sections(id) ON DELETE CASCADE,
            responsible_id INTEGER NOT NULL REFERENCES responsibles(id) ON DELETE CASCADE,
            sort_order INTEGER NOT NULL DEFAULT 0, PRIMARY KEY (section_id, responsible_id))""",
        "ALTER TABLE sections ADD COLUMN status_id INTEGER REFERENCES statuses(id) ON DELETE SET NULL",
        "ALTER TABLE sections ADD COLUMN progress INTEGER NOT NULL DEFAULT 0 CHECK (progress BETWEEN 0 AND 100)",
    ],
    # v4: se elimina la "referencia mutua"; cada dirección es una relación independiente.
    # Las mutuas existentes se dividen en dos 'ref' (la inversa nace sin geometría: waypoints y
    # puertos solo valen para la dirección original). Los CHECK antiguos de la tabla quedan en las
    # bases migradas, pero ya no estorban porque no habrá filas 'mutual'.
    4: [
        "DROP INDEX IF EXISTS ux_relations_pair",
        """INSERT INTO relations (source_id, target_id, kind, notes, created_at)
            SELECT target_id, source_id, 'ref', notes, created_at FROM relations WHERE kind = 'mutual'""",
        "UPDATE relations SET kind = 'ref' WHERE kind = 'mutual'",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_relations_directed ON relations (source_id, target_id)",
    ],
}
