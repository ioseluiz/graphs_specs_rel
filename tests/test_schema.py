from __future__ import annotations

import sqlite3

import pytest

from models.database import ProjectDatabase, ProjectFileError
from models.entities import RelationKind
from models.repositories import CategoryRepo, PositionRepo, RelationRepo, SectionRepo
from models.schema import SCHEMA_VERSION


def _two_sections(db):
    repo = SectionRepo(db)
    a = repo.insert("31 23 00", "Excavación")
    b = repo.insert("33 40 00", "Drenaje pluvial")
    return a, b


def test_schema_version_and_seed(db):
    assert db.schema_version() == SCHEMA_VERSION
    assert db.conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    cats = CategoryRepo(db).all()
    assert [c.name for c in cats] == ["Técnica / constructiva", "Contractual", "Auxiliar / apoyo", "Otra", "Cláusula"]
    assert CategoryRepo(db).default().name == "Otra"
    by_name = {c.name: c for c in cats}
    assert (by_name["Cláusula"].fill_color, by_name["Otra"].fill_color) == ("#F8CBF0", "#EDEDED")


def test_unique_code_key(db):
    repo = SectionRepo(db)
    repo.insert("31 23 00", "Excavación")
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert("312300", "Duplicada con otro formato")


def test_self_relation_rejected(db):
    a, _ = _two_sections(db)
    with pytest.raises(sqlite3.IntegrityError):
        RelationRepo(db).insert(a.id, a.id, RelationKind.REF)


def test_directed_pair_unique_but_inverse_allowed(db):
    """A→B y B→A son dos relaciones distintas; solo la misma dirección es duplicado."""
    a, b = _two_sections(db)
    rels = RelationRepo(db)
    first = rels.insert(a.id, b.id, RelationKind.REF)
    second = rels.insert(b.id, a.id, RelationKind.REF)
    assert first.id != second.id
    assert rels.find_directed(a.id, b.id).id == first.id
    assert rels.find_directed(b.id, a.id).id == second.id
    assert rels.reverse_of(first).id == second.id
    with pytest.raises(sqlite3.IntegrityError):
        rels.insert(a.id, b.id, RelationKind.REF)


def test_migration_v3_to_v4_splits_mutual_into_two_arrows(tmp_path):
    """Una «referencia mutua» del esquema anterior pasa a ser dos relaciones 'ref' independientes."""
    from models.schema import SCHEMA_SQL

    v3_sql = SCHEMA_SQL.replace(
        "kind        TEXT NOT NULL DEFAULT 'ref' CHECK (kind = 'ref'),",
        "kind        TEXT NOT NULL CHECK (kind IN ('ref', 'mutual')),",
    ).replace(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_relations_directed ON relations (source_id, target_id);",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_relations_pair "
        "ON relations (MIN(source_id, target_id), MAX(source_id, target_id));",
    )
    assert "ux_relations_pair" in v3_sql and "'mutual'" in v3_sql
    path = tmp_path / "v3.specrel"
    conn = sqlite3.connect(path)
    conn.executescript(v3_sql)
    conn.execute("PRAGMA user_version = 3")
    conn.execute("INSERT INTO project (id, code, name, created_at, updated_at, app_version) "
                 "VALUES (1, 'X', 'Y', 'now', 'now', '0.2.1')")
    conn.execute("INSERT INTO sections (id, code, code_key, title, created_at, updated_at) "
                 "VALUES (1, '01 35 29', '013529', 'Seguridad', 'now', 'now')")
    conn.execute("INSERT INTO sections (id, code, code_key, title, created_at, updated_at) "
                 "VALUES (2, '03 30 00', '033000', 'Concreto', 'now', 'now')")
    conn.execute("INSERT INTO relations (source_id, target_id, kind, waypoints, source_port, target_port, notes, "
                 "created_at) VALUES (1, 2, 'mutual', '[[10, 20]]', 'right', 'left', 'nota', 'now')")
    conn.execute("INSERT INTO relations (source_id, target_id, kind, created_at) VALUES (2, 1, 'ref', 'now')"
                 if False else "SELECT 1")
    conn.commit()
    conn.close()

    db = ProjectDatabase.open(path)
    assert db.schema_version() == SCHEMA_VERSION == 5
    rels = sorted(RelationRepo(db).all(), key=lambda r: r.id)
    assert [(r.source_id, r.target_id, r.kind) for r in rels] == [(1, 2, RelationKind.REF), (2, 1, RelationKind.REF)]
    original, inverse = rels
    assert original.waypoints == [(10.0, 20.0)] and original.source_port == "right"
    assert inverse.waypoints is None and inverse.source_port is None and inverse.target_port is None
    assert inverse.notes == "nota"
    with pytest.raises(sqlite3.IntegrityError):  # el índice dirigido quedó creado
        RelationRepo(db).insert(1, 2, RelationKind.REF)
    db.close()


def test_cascade_on_section_delete(db):
    a, b = _two_sections(db)
    rels = RelationRepo(db)
    rels.insert(a.id, b.id, RelationKind.REF)
    PositionRepo(db).upsert(a.id, 10, 20, True)
    SectionRepo(db).delete(a.id)
    assert rels.count() == 0
    assert PositionRepo(db).get(a.id) is None


def test_geometry_roundtrip(db):
    a, b = _two_sections(db)
    rels = RelationRepo(db)
    rel = rels.insert(a.id, b.id, RelationKind.REF)
    rels.update_geometry(rel.id, [(10.0, 20.5), (30.0, 40.0)], "top", "left")
    again = rels.get(rel.id)
    assert again.waypoints == [(10.0, 20.5), (30.0, 40.0)]
    assert again.source_port == "top" and again.target_port == "left"
    rels.update_geometry(rel.id, None, None, None)
    assert rels.get(rel.id).waypoints is None


def test_invalid_color_rejected(db):
    with pytest.raises(sqlite3.IntegrityError):
        CategoryRepo(db).insert("Mala", "rojo", "#FFFFFF")


def test_open_invalid_file(tmp_path):
    bad = tmp_path / "bad.specrel"
    bad.write_bytes(b"esto no es sqlite")
    with pytest.raises(ProjectFileError):
        ProjectDatabase.open(bad)


def test_migration_from_v1_adds_section_colors(tmp_path):
    from models.schema import SCHEMA_SQL

    path = tmp_path / "old.specrel"
    v1_sql = "\n".join(
        line for line in SCHEMA_SQL.splitlines()
        if not any(tag in line for tag in ("fill_color   TEXT CHECK", "border_color TEXT CHECK",
                                            "status_id    INTEGER", "progress     INTEGER",
                                            "kind         TEXT NOT NULL"))
    )
    conn = sqlite3.connect(path)
    conn.executescript(v1_sql)
    conn.execute("PRAGMA user_version = 1")
    conn.execute("INSERT INTO project (id, code, name, created_at, updated_at, app_version) "
                 "VALUES (1, 'X', 'Y', 'now', 'now', '0.0')")
    conn.execute("INSERT INTO sections (code, code_key, title, created_at, updated_at) "
                 "VALUES ('31 23 00', '312300', 'Excavación', 'now', 'now')")
    conn.commit()
    conn.close()
    db = ProjectDatabase.open(path)
    assert db.schema_version() == SCHEMA_VERSION
    cols = {r[1] for r in db.conn.execute("PRAGMA table_info(sections)")}
    assert {"fill_color", "border_color", "status_id", "progress"} <= cols
    # v3 crea las listas y las siembra en proyectos existentes
    assert db.conn.execute("SELECT COUNT(*) FROM statuses").fetchone()[0] == 5
    assert db.conn.execute("SELECT COUNT(*) FROM responsibles").fetchone()[0] == 5
    sec = SectionRepo(db).all()[0]
    assert sec.fill_color is None
    sec.fill_color, sec.border_color = "#123456", "#0A0A0A"
    SectionRepo(db).update(sec)
    assert SectionRepo(db).get(sec.id).fill_color == "#123456"
    db.close()


def test_create_open_and_backup(tmp_path):
    path = tmp_path / "demo.specrel"
    db = ProjectDatabase.create(path, "CC-01", "Demo")
    SectionRepo(db).insert("01 11 00", "Resumen")
    db.close()
    db2 = ProjectDatabase.open(path)
    assert SectionRepo(db2).count() == 1
    db2.close()
    assert (tmp_path / "demo.specrel.bak1").exists()


def test_migration_v4_to_v5_recalculates_keys_and_marks_clauses(tmp_path):
    """Las numeraciones de cláusula conservan los puntos y las secciones 4.28.x pasan a ser cláusulas."""
    from models.schema import SCHEMA_SQL

    v4_sql = "\n".join(line for line in SCHEMA_SQL.splitlines() if "kind         TEXT NOT NULL" not in line)
    path = tmp_path / "v4.specrel"
    conn = sqlite3.connect(path)
    conn.executescript(v4_sql)
    conn.execute("PRAGMA user_version = 4")
    conn.execute("INSERT INTO project (id, code, name, created_at, updated_at, app_version) "
                 "VALUES (1, 'X', 'Y', 'now', 'now', '0.3.0')")
    conn.execute("INSERT INTO categories (id, name, fill_color, border_color, sort_order, is_default) "
                 "VALUES (1, 'Otra', '#F8CBF0', '#C55A9E', 0, 1)")
    conn.execute("INSERT INTO statuses (id, name, color, sort_order, is_default) VALUES (1, 'En elaboración', '#FFE699', 0, 1)")
    conn.execute("INSERT INTO responsibles (id, code, name, color, sort_order) VALUES (1, 'INIO', 'Costos', '#5B9BD5', 0)")
    conn.execute("INSERT INTO sections (id, code, code_key, title, category_id, status_id, progress, created_at, "
                 "updated_at) VALUES (1, '4.28.3.1', '42831', 'Retención', 1, 1, 50, 'now', 'now')")
    conn.execute("INSERT INTO sections (id, code, code_key, title, category_id, status_id, progress, created_at, "
                 "updated_at) VALUES (2, '31 23 00', '312300', 'Excavación', 1, 1, 30, 'now', 'now')")
    conn.execute("INSERT INTO section_responsibles (section_id, responsible_id, sort_order) VALUES (1, 1, 0)")
    conn.execute("INSERT INTO catalog (code_key, code, title, category_name) VALUES ('42833', '4.28.33', 'Sitio', NULL)")
    conn.commit()
    conn.close()

    db = ProjectDatabase.open(path)
    assert db.schema_version() == 5
    secs = {s.code: s for s in SectionRepo(db).all()}
    clause, plain = secs["4.28.3.1"], secs["31 23 00"]
    assert clause.code_key == "4.28.3.1" and clause.kind == "clause"
    assert clause.status_id is None and clause.progress == 0
    assert db.conn.execute("SELECT COUNT(*) FROM section_responsibles WHERE section_id = 1").fetchone()[0] == 0
    cats = {c.name: c for c in CategoryRepo(db).all()}
    assert clause.category_id == cats["Cláusula"].id and cats["Cláusula"].fill_color == "#F8CBF0"
    assert (cats["Otra"].fill_color, cats["Otra"].border_color) == ("#EDEDED", "#8C8C8C")
    assert plain.kind == "section" and plain.status_id == 1 and plain.progress == 30 and plain.code_key == "312300"
    assert db.conn.execute("SELECT code_key FROM catalog").fetchone()[0] == "4.28.33"
    db.close()
