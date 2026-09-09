"""Repositorios: único lugar con SQL. Devuelven entidades, no filas."""
from __future__ import annotations

import json
import sqlite3
from typing import Iterable

from models.database import ProjectDatabase, now_iso
from models.entities import (
    CatalogEntry,
    Category,
    NodePosition,
    ProjectMeta,
    Relation,
    RelationKind,
    Responsible,
    Section,
    Side,
    Status,
)
from models.relation_normalizer import code_key


def _row_section(row: sqlite3.Row) -> Section:
    keys = row.keys()
    return Section(
        id=row["id"], code=row["code"], code_key=row["code_key"], title=row["title"],
        category_id=row["category_id"], notes=row["notes"],
        created_at=row["created_at"], updated_at=row["updated_at"],
        fill_color=row["fill_color"] if "fill_color" in keys else None,
        border_color=row["border_color"] if "border_color" in keys else None,
        status_id=row["status_id"] if "status_id" in keys else None,
        progress=int(row["progress"] or 0) if "progress" in keys else 0,
    )


def _row_status(row: sqlite3.Row) -> Status:
    return Status(id=row["id"], name=row["name"], color=row["color"], sort_order=row["sort_order"],
                  is_default=bool(row["is_default"]))


def _row_responsible(row: sqlite3.Row) -> Responsible:
    return Responsible(id=row["id"], code=row["code"], name=row["name"], color=row["color"],
                       sort_order=row["sort_order"])


def _row_relation(row: sqlite3.Row) -> Relation:
    raw = row["waypoints"]
    waypoints = None
    if raw:
        try:
            waypoints = [(float(x), float(y)) for x, y in json.loads(raw)]
        except (ValueError, TypeError):
            waypoints = None
    return Relation(
        id=row["id"], source_id=row["source_id"], target_id=row["target_id"],
        kind=RelationKind(row["kind"]), waypoints=waypoints,
        source_port=row["source_port"], target_port=row["target_port"],
        notes=row["notes"], created_at=row["created_at"],
    )


def _row_category(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"], name=row["name"], fill_color=row["fill_color"],
        border_color=row["border_color"], sort_order=row["sort_order"],
        is_default=bool(row["is_default"]),
    )


class _Repo:
    def __init__(self, db: ProjectDatabase) -> None:
        self.db = db
        self.conn = db.conn


class ProjectRepo(_Repo):
    def get(self) -> ProjectMeta:
        row = self.conn.execute("SELECT * FROM project WHERE id = 1").fetchone()
        if row is None:
            return ProjectMeta()
        return ProjectMeta(
            code=row["code"], name=row["name"], created_at=row["created_at"],
            updated_at=row["updated_at"], app_version=row["app_version"],
        )

    def update(self, code: str, name: str) -> None:
        self.conn.execute(
            "UPDATE project SET code = ?, name = ?, updated_at = ? WHERE id = 1",
            (code.strip(), name.strip(), now_iso()),
        )


class CategoryRepo(_Repo):
    def all(self) -> list[Category]:
        rows = self.conn.execute(
            "SELECT * FROM categories ORDER BY sort_order, name").fetchall()
        return [_row_category(r) for r in rows]

    def get(self, category_id: int) -> Category | None:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id = ?", (category_id,)).fetchone()
        return _row_category(row) if row else None

    def default(self) -> Category | None:
        row = self.conn.execute(
            "SELECT * FROM categories WHERE is_default = 1 ORDER BY sort_order LIMIT 1").fetchone()
        if row is None:
            row = self.conn.execute(
                "SELECT * FROM categories ORDER BY sort_order LIMIT 1").fetchone()
        return _row_category(row) if row else None

    def insert(self, name: str, fill: str, border: str) -> Category:
        order = self.conn.execute(
            "SELECT COALESCE(MAX(sort_order), -1) + 1 FROM categories").fetchone()[0]
        cur = self.conn.execute(
            "INSERT INTO categories (name, fill_color, border_color, sort_order) VALUES (?, ?, ?, ?)",
            (name.strip(), fill, border, order),
        )
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, category: Category) -> None:
        self.conn.execute(
            "UPDATE categories SET name = ?, fill_color = ?, border_color = ?, sort_order = ? WHERE id = ?",
            (category.name.strip(), category.fill_color, category.border_color,
             category.sort_order, category.id),
        )

    def set_default(self, category_id: int) -> None:
        self.conn.execute("UPDATE categories SET is_default = 0")
        self.conn.execute("UPDATE categories SET is_default = 1 WHERE id = ?", (category_id,))

    def delete(self, category_id: int) -> None:
        self.conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))

    def usage_count(self, category_id: int) -> int:
        return self.conn.execute(
            "SELECT COUNT(*) FROM sections WHERE category_id = ?", (category_id,)).fetchone()[0]


class SectionRepo(_Repo):
    def all(self) -> list[Section]:
        rows = self.conn.execute("SELECT * FROM sections ORDER BY code_key").fetchall()
        return [_row_section(r) for r in rows]

    def get(self, section_id: int) -> Section | None:
        row = self.conn.execute("SELECT * FROM sections WHERE id = ?", (section_id,)).fetchone()
        return _row_section(row) if row else None

    def get_by_code(self, code: str) -> Section | None:
        row = self.conn.execute(
            "SELECT * FROM sections WHERE code_key = ?", (code_key(code),)).fetchone()
        return _row_section(row) if row else None

    def insert(self, code: str, title: str = "", category_id: int | None = None,
               notes: str | None = None, fill_color: str | None = None,
               border_color: str | None = None, status_id: int | None = None,
               progress: int = 0) -> Section:
        ts = now_iso()
        code = " ".join(code.split())
        cur = self.conn.execute(
            "INSERT INTO sections (code, code_key, title, category_id, notes, created_at, updated_at, "
            "fill_color, border_color, status_id, progress) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (code, code_key(code), title.strip(), category_id, notes, ts, ts, fill_color, border_color,
             status_id, int(progress)),
        )
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, section: Section) -> None:
        code = " ".join(section.code.split())
        self.conn.execute(
            "UPDATE sections SET code = ?, code_key = ?, title = ?, category_id = ?, notes = ?, "
            "updated_at = ?, fill_color = ?, border_color = ?, status_id = ?, progress = ? WHERE id = ?",
            (code, code_key(code), section.title.strip(), section.category_id,
             section.notes, now_iso(), section.fill_color, section.border_color,
             section.status_id, int(section.progress), section.id),
        )

    def delete(self, section_id: int) -> None:
        self.conn.execute("DELETE FROM sections WHERE id = ?", (section_id,))

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM sections").fetchone()[0]


class StatusRepo(_Repo):
    def all(self) -> list[Status]:
        return [_row_status(r) for r in self.conn.execute(
            "SELECT * FROM statuses ORDER BY sort_order, name").fetchall()]

    def get(self, status_id: int) -> Status | None:
        row = self.conn.execute("SELECT * FROM statuses WHERE id = ?", (status_id,)).fetchone()
        return _row_status(row) if row else None

    def default(self) -> Status | None:
        row = self.conn.execute(
            "SELECT * FROM statuses WHERE is_default = 1 ORDER BY sort_order LIMIT 1").fetchone()
        if row is None:
            row = self.conn.execute("SELECT * FROM statuses ORDER BY sort_order LIMIT 1").fetchone()
        return _row_status(row) if row else None

    def insert(self, name: str, color: str) -> Status:
        order = self.conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM statuses").fetchone()[0]
        cur = self.conn.execute("INSERT INTO statuses (name, color, sort_order) VALUES (?, ?, ?)",
                                (name.strip(), color, order))
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, status: Status) -> None:
        self.conn.execute("UPDATE statuses SET name = ?, color = ?, sort_order = ? WHERE id = ?",
                          (status.name.strip(), status.color, status.sort_order, status.id))

    def set_default(self, status_id: int) -> None:
        self.conn.execute("UPDATE statuses SET is_default = 0")
        self.conn.execute("UPDATE statuses SET is_default = 1 WHERE id = ?", (status_id,))

    def delete(self, status_id: int) -> None:
        self.conn.execute("DELETE FROM statuses WHERE id = ?", (status_id,))

    def usage_count(self, status_id: int) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM sections WHERE status_id = ?", (status_id,)).fetchone()[0]


class ResponsibleRepo(_Repo):
    def all(self) -> list[Responsible]:
        return [_row_responsible(r) for r in self.conn.execute(
            "SELECT * FROM responsibles ORDER BY sort_order, code").fetchall()]

    def get(self, responsible_id: int) -> Responsible | None:
        row = self.conn.execute("SELECT * FROM responsibles WHERE id = ?", (responsible_id,)).fetchone()
        return _row_responsible(row) if row else None

    def insert(self, code: str, name: str, color: str) -> Responsible:
        order = self.conn.execute("SELECT COALESCE(MAX(sort_order), -1) + 1 FROM responsibles").fetchone()[0]
        cur = self.conn.execute("INSERT INTO responsibles (code, name, color, sort_order) VALUES (?, ?, ?, ?)",
                                (code.strip(), name.strip(), color, order))
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update(self, resp: Responsible) -> None:
        self.conn.execute("UPDATE responsibles SET code = ?, name = ?, color = ?, sort_order = ? WHERE id = ?",
                          (resp.code.strip(), resp.name.strip(), resp.color, resp.sort_order, resp.id))

    def delete(self, responsible_id: int) -> None:
        self.conn.execute("DELETE FROM responsibles WHERE id = ?", (responsible_id,))

    def usage_count(self, responsible_id: int) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM section_responsibles WHERE responsible_id = ?",
                                 (responsible_id,)).fetchone()[0]

    def all_assignments(self) -> dict[int, list[int]]:
        """section_id -> [responsible_id] en orden."""
        out: dict[int, list[int]] = {}
        for row in self.conn.execute(
                "SELECT section_id, responsible_id FROM section_responsibles ORDER BY section_id, sort_order"):
            out.setdefault(row["section_id"], []).append(row["responsible_id"])
        return out

    def for_section(self, section_id: int) -> list[int]:
        return [r["responsible_id"] for r in self.conn.execute(
            "SELECT responsible_id FROM section_responsibles WHERE section_id = ? ORDER BY sort_order",
            (section_id,))]

    def set_for_section(self, section_id: int, responsible_ids: list[int]) -> None:
        self.conn.execute("DELETE FROM section_responsibles WHERE section_id = ?", (section_id,))
        self.conn.executemany(
            "INSERT OR IGNORE INTO section_responsibles (section_id, responsible_id, sort_order) VALUES (?, ?, ?)",
            [(section_id, rid, i) for i, rid in enumerate(responsible_ids)],
        )


class RelationRepo(_Repo):
    def all(self) -> list[Relation]:
        rows = self.conn.execute("SELECT * FROM relations ORDER BY id").fetchall()
        return [_row_relation(r) for r in rows]

    def get(self, relation_id: int) -> Relation | None:
        row = self.conn.execute("SELECT * FROM relations WHERE id = ?", (relation_id,)).fetchone()
        return _row_relation(row) if row else None

    def for_section(self, section_id: int) -> list[Relation]:
        rows = self.conn.execute(
            "SELECT * FROM relations WHERE source_id = ? OR target_id = ? ORDER BY id",
            (section_id, section_id),
        ).fetchall()
        return [_row_relation(r) for r in rows]

    def find_directed(self, source_id: int, target_id: int) -> Relation | None:
        """La relación exacta source → target, si existe (la inversa es otra relación)."""
        row = self.conn.execute(
            "SELECT * FROM relations WHERE source_id = ? AND target_id = ?", (source_id, target_id)
        ).fetchone()
        return _row_relation(row) if row else None

    def reverse_of(self, rel: Relation) -> Relation | None:
        return self.find_directed(rel.target_id, rel.source_id)

    def insert(self, source_id: int, target_id: int, kind: RelationKind,
               notes: str | None = None) -> Relation:
        """Lanza sqlite3.IntegrityError si viola las restricciones (duplicado, auto-relación)."""
        cur = self.conn.execute(
            "INSERT INTO relations (source_id, target_id, kind, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (source_id, target_id, kind.value, notes, now_iso()),
        )
        return self.get(cur.lastrowid)  # type: ignore[return-value]

    def update_endpoints(self, relation_id: int, source_id: int, target_id: int,
                         kind: RelationKind, keep_geometry: bool) -> None:
        if keep_geometry:
            self.conn.execute(
                "UPDATE relations SET source_id = ?, target_id = ?, kind = ? WHERE id = ?",
                (source_id, target_id, kind.value, relation_id),
            )
        else:
            self.conn.execute(
                "UPDATE relations SET source_id = ?, target_id = ?, kind = ?, waypoints = NULL, "
                "source_port = NULL, target_port = NULL WHERE id = ?",
                (source_id, target_id, kind.value, relation_id),
            )

    def update_geometry(self, relation_id: int, waypoints: list[tuple[float, float]] | None,
                        source_port: Side | None, target_port: Side | None) -> None:
        raw = json.dumps([[round(x, 2), round(y, 2)] for x, y in waypoints]) if waypoints else None
        self.conn.execute(
            "UPDATE relations SET waypoints = ?, source_port = ?, target_port = ? WHERE id = ?",
            (raw, source_port, target_port, relation_id),
        )

    def update_notes(self, relation_id: int, notes: str | None) -> None:
        self.conn.execute("UPDATE relations SET notes = ? WHERE id = ?", (notes, relation_id))

    def delete(self, relation_id: int) -> None:
        self.conn.execute("DELETE FROM relations WHERE id = ?", (relation_id,))

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM relations").fetchone()[0]


class PositionRepo(_Repo):
    def all(self) -> dict[int, NodePosition]:
        rows = self.conn.execute("SELECT * FROM node_positions").fetchall()
        return {
            r["section_id"]: NodePosition(r["section_id"], r["x"], r["y"], bool(r["pinned"]))
            for r in rows
        }

    def get(self, section_id: int) -> NodePosition | None:
        row = self.conn.execute(
            "SELECT * FROM node_positions WHERE section_id = ?", (section_id,)).fetchone()
        return NodePosition(row["section_id"], row["x"], row["y"], bool(row["pinned"])) if row else None

    def upsert(self, section_id: int, x: float, y: float, pinned: bool) -> None:
        self.conn.execute(
            "INSERT INTO node_positions (section_id, x, y, pinned) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(section_id) DO UPDATE SET x = excluded.x, y = excluded.y, pinned = excluded.pinned",
            (section_id, round(x, 2), round(y, 2), int(pinned)),
        )

    def delete(self, section_id: int) -> None:
        self.conn.execute("DELETE FROM node_positions WHERE section_id = ?", (section_id,))


class Layout3DRepo(_Repo):
    def all(self) -> dict[int, tuple[float, float, float]]:
        rows = self.conn.execute("SELECT * FROM layout3d").fetchall()
        return {r["section_id"]: (r["x"], r["y"], r["z"]) for r in rows}

    def replace_all(self, positions: dict[int, tuple[float, float, float]]) -> None:
        self.conn.execute("DELETE FROM layout3d")
        self.conn.executemany(
            "INSERT INTO layout3d (section_id, x, y, z) VALUES (?, ?, ?, ?)",
            [(sid, float(x), float(y), float(z)) for sid, (x, y, z) in positions.items()],
        )

    def upsert(self, section_id: int, x: float, y: float, z: float) -> None:
        self.conn.execute(
            "INSERT INTO layout3d (section_id, x, y, z) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(section_id) DO UPDATE SET x = excluded.x, y = excluded.y, z = excluded.z",
            (section_id, float(x), float(y), float(z)),
        )


class SettingsRepo(_Repo):
    def get(self, key: str, default: str | None = None) -> str | None:
        row = self.conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )

    def delete(self, key: str) -> None:
        self.conn.execute("DELETE FROM settings WHERE key = ?", (key,))


class CatalogRepo(_Repo):
    def all(self) -> list[CatalogEntry]:
        rows = self.conn.execute("SELECT * FROM catalog ORDER BY code_key").fetchall()
        return [CatalogEntry(r["code_key"], r["code"], r["title"], r["category_name"]) for r in rows]

    def get(self, key: str) -> CatalogEntry | None:
        row = self.conn.execute("SELECT * FROM catalog WHERE code_key = ?", (key,)).fetchone()
        return CatalogEntry(row["code_key"], row["code"], row["title"], row["category_name"]) if row else None

    def count(self) -> int:
        return self.conn.execute("SELECT COUNT(*) FROM catalog").fetchone()[0]

    def merge(self, entries: Iterable[CatalogEntry]) -> int:
        """Inserta o actualiza; devuelve la cantidad procesada."""
        rows = [(e.code_key, e.code, e.title, e.category_name) for e in entries if e.code_key]
        self.conn.executemany(
            "INSERT INTO catalog (code_key, code, title, category_name) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(code_key) DO UPDATE SET code = excluded.code, title = excluded.title, "
            "category_name = COALESCE(excluded.category_name, catalog.category_name)",
            rows,
        )
        return len(rows)

    def clear(self) -> None:
        self.conn.execute("DELETE FROM catalog")
