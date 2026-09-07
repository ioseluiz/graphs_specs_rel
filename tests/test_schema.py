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
    assert len(cats) == 4
    assert CategoryRepo(db).default().name == "Otra"


def test_unique_code_key(db):
    repo = SectionRepo(db)
    repo.insert("31 23 00", "Excavación")
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert("312300", "Duplicada con otro formato")


def test_self_relation_rejected(db):
    a, _ = _two_sections(db)
    with pytest.raises(sqlite3.IntegrityError):
        RelationRepo(db).insert(a.id, a.id, RelationKind.REF)


def test_pair_unique_regardless_of_direction(db):
    a, b = _two_sections(db)
    rels = RelationRepo(db)
    rels.insert(a.id, b.id, RelationKind.REF)
    with pytest.raises(sqlite3.IntegrityError):
        rels.insert(b.id, a.id, RelationKind.REF)
    with pytest.raises(sqlite3.IntegrityError):
        rels.insert(min(a.id, b.id), max(a.id, b.id), RelationKind.MUTUAL)


def test_mutual_must_be_canonical(db):
    a, b = _two_sections(db)
    with pytest.raises(sqlite3.IntegrityError):
        RelationRepo(db).insert(max(a.id, b.id), min(a.id, b.id), RelationKind.MUTUAL)
    rel = RelationRepo(db).insert(min(a.id, b.id), max(a.id, b.id), RelationKind.MUTUAL)
    assert rel.kind is RelationKind.MUTUAL


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
                                            "status_id    INTEGER", "progress     INTEGER"))
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
