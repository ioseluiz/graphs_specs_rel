"""ProjectModel: fuente única de verdad del proyecto abierto.

Cada mutación es una transacción SQLite + actualización del grafo + señal Qt
con ids. Las vistas nunca mutan el modelo en respuesta a una señal del modelo.
"""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from config import palette
from models.database import ProjectDatabase
from models.entities import (
    CatalogEntry,
    Category,
    NodePosition,
    ProjectMeta,
    Relation,
    RelationKind,
    Responsible,
    Section,
    SectionRemoval,
    Side,
    Status,
    UiKind,
)
from models.graph_engine import GraphEngine
from models.layout_engine import place_new_node
from models.clause_catalog import ClauseCatalog
from models.line_styles import DASH_KEYS, WIDTH_MAX, WIDTH_MIN, valid_hex
from models.master_catalog import CatalogRecord, MasterCatalog, normalize_code
from models.relation_normalizer import (
    DuplicateRelationError,
    SelfRelationError,
    code_key,
    normalize,
    sort_key,
    split_code_title,
)
from models.repositories import (
    CatalogRepo,
    CategoryRepo,
    Layout3DRepo,
    PositionRepo,
    ProjectRepo,
    RelationRepo,
    ResponsibleRepo,
    SectionRepo,
    SettingsRepo,
    StatusRepo,
)


KEEP = object()  # centinela: conservar el valor actual


def derive_border_color(fill_hex: str) -> str:
    """Borde más oscuro y saturado derivado del relleno (misma tonalidad)."""
    h = fill_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    factor = 0.62
    return "#{:02X}{:02X}{:02X}".format(int(r * factor), int(g * factor), int(b * factor))


class ProjectModel(QObject):
    projectLoaded = pyqtSignal()
    projectClosed = pyqtSignal()
    projectMetaChanged = pyqtSignal()
    categoriesChanged = pyqtSignal()
    statusesChanged = pyqtSignal()
    responsiblesChanged = pyqtSignal()
    catalogChanged = pyqtSignal()

    sectionAdded = pyqtSignal(int)
    sectionUpdated = pyqtSignal(int)
    sectionRemoved = pyqtSignal(int)

    relationAdded = pyqtSignal(int)
    relationUpdated = pyqtSignal(int)        # extremos o tipo cambiaron
    relationGeometryChanged = pyqtSignal(int)  # waypoints / puertos
    relationRemoved = pyqtSignal(int)

    positionChanged = pyqtSignal(int, float, float)
    graphChanged = pyqtSignal()  # coalescida: análisis y 3D se refrescan aquí

    def __init__(self, parent: QObject | None = None, master: MasterCatalog | None = None,
                 clauses: ClauseCatalog | None = None) -> None:
        super().__init__(parent)
        self.db: ProjectDatabase | None = None
        self.path: Path | None = None
        self.master: MasterCatalog = master if master is not None else MasterCatalog()
        self.clauses: ClauseCatalog = clauses if clauses is not None else ClauseCatalog()
        self.graph = GraphEngine()
        self._sections: dict[int, Section] = {}
        self._relations: dict[int, Relation] = {}
        self._positions: dict[int, NodePosition] = {}
        self._categories: dict[int, Category] = {}
        self._statuses: dict[int, Status] = {}
        self._responsibles: dict[int, Responsible] = {}
        self._section_responsibles: dict[int, list[int]] = {}
        self._catalog: dict[str, CatalogEntry] = {}
        self._graph_timer = QTimer(self)
        self._graph_timer.setSingleShot(True)
        self._graph_timer.setInterval(0)
        self._graph_timer.timeout.connect(self.graphChanged)

    # ------------------------------------------------------------------ ciclo de vida
    @property
    def is_open(self) -> bool:
        return self.db is not None

    def new_project(self, path: Path | str | None, code: str = "", name: str = "") -> None:
        self.close()
        if path is None:
            db = ProjectDatabase(None)
            db.initialize_schema()
            if code or name:
                ProjectRepo(db).update(code, name)
        else:
            db = ProjectDatabase.create(path, code, name)
        self._attach(db, Path(path) if path is not None else None)

    def open_project(self, path: Path | str) -> None:
        self.close()
        db = ProjectDatabase.open(path)
        self._attach(db, Path(path))

    def _attach(self, db: ProjectDatabase, path: Path | None) -> None:
        self.db = db
        self.path = path
        self.sections_repo = SectionRepo(db)
        self.relations_repo = RelationRepo(db)
        self.categories_repo = CategoryRepo(db)
        self.statuses_repo = StatusRepo(db)
        self.responsibles_repo = ResponsibleRepo(db)
        self.positions_repo = PositionRepo(db)
        self.layout3d_repo = Layout3DRepo(db)
        self.settings_repo = SettingsRepo(db)
        self.catalog_repo = CatalogRepo(db)
        self.project_repo = ProjectRepo(db)
        self.reload_cache()
        self.projectLoaded.emit()

    def reload_cache(self) -> None:
        assert self.db is not None
        self._sections = {s.id: s for s in self.sections_repo.all()}
        self._relations = {r.id: r for r in self.relations_repo.all()}
        self._positions = self.positions_repo.all()
        self._categories = {c.id: c for c in self.categories_repo.all()}
        self._statuses = {s.id: s for s in self.statuses_repo.all()}
        self._responsibles = {r.id: r for r in self.responsibles_repo.all()}
        self._section_responsibles = self.responsibles_repo.all_assignments()
        self._catalog = {e.code_key: e for e in self.catalog_repo.all()}
        self.graph.rebuild(self._sections.values(), self._relations.values())
        self._ensure_positions()

    def _ensure_positions(self) -> None:
        """Asigna posición a secciones que no la tienen (nunca mueve las existentes)."""
        missing = [sid for sid in self._sections if sid not in self._positions]
        if not missing:
            return
        assert self.db is not None
        with self.db.transaction():
            for sid in missing:
                x, y = place_new_node(
                    {k: (p.x, p.y) for k, p in self._positions.items()},
                    self.graph.neighbors(sid),
                )
                self.positions_repo.upsert(sid, x, y, False)
                self._positions[sid] = NodePosition(sid, x, y, False)

    def close(self) -> None:
        if self.db is None:
            return
        self.db.close()
        self.db = None
        self.path = None
        self._sections.clear()
        self._relations.clear()
        self._positions.clear()
        self._categories.clear()
        self._statuses.clear()
        self._responsibles.clear()
        self._section_responsibles.clear()
        self._catalog.clear()
        self.graph.rebuild([], [])
        self.projectClosed.emit()

    def save_copy(self, destination: Path | str) -> None:
        """Duplica el proyecto en otro archivo. El archivo abierto ya está guardado (autoguardado)."""
        assert self.db is not None
        dest = Path(destination)
        if self.path is not None:
            try:
                same = dest.resolve() == self.path.resolve()
            except OSError:
                same = dest == self.path
            if same:
                raise ValueError(
                    "Ese es el archivo del proyecto abierto y ya contiene todos los cambios "
                    "(se guardan automáticamente). Elija otro nombre para crear una copia.")
            if dest.name.startswith(self.path.name + ".bak"):
                raise ValueError("No se puede sobrescribir una copia de respaldo del proyecto abierto.")
        self.db.save_copy(dest)

    def checkpoint(self) -> Path | None:
        """«Guardar» explícito: confirma que no hay transacciones pendientes y actualiza la fecha."""
        assert self.db is not None
        with self.db.transaction():
            self.db.touch()
        return self.path

    @contextmanager
    def bulk(self) -> Iterator[None]:
        """Agrupa muchas mutaciones (importación, reclasificación) en UNA transacción SQLite.

        Las señales por elemento se emiten igual que siempre; los oyentes pesados ya coalescen.
        Sin esto, 300 filas importadas eran 300 transacciones (fsync cada una, más lento en OneDrive).
        """
        assert self.db is not None
        with self.db.transaction():
            yield

    def snapshot(self) -> "ProjectSnapshot":
        """Copia de solo lectura del estado, para exportadores que corren en otro hilo.

        El hilo de trabajo no debe tocar `ProjectModel` (SQLite exige el hilo que abrió la conexión).
        """
        return ProjectSnapshot(
            path=self.path,
            _meta=self.meta(),
            _sections=dict(self._sections),
            _relations=dict(self._relations),
            _categories=dict(self._categories),
            _statuses=dict(self._statuses),
            _responsibles=dict(self._responsibles),
            _section_responsibles={k: list(v) for k, v in self._section_responsibles.items()},
            _positions=dict(self._positions),
            graph=self.graph.copy(),
        )

    # ------------------------------------------------------------------ lectura
    def meta(self) -> ProjectMeta:
        return self.project_repo.get() if self.db else ProjectMeta()

    def sections(self) -> list[Section]:
        return sorted(self._sections.values(), key=lambda s: sort_key(s.code_key))

    def section(self, section_id: int) -> Section | None:
        return self._sections.get(section_id)

    def section_by_code(self, code: str) -> Section | None:
        key = code_key(code)
        for s in self._sections.values():
            if s.code_key == key:
                return s
        return None

    def relations(self) -> list[Relation]:
        return list(self._relations.values())

    def relation(self, relation_id: int) -> Relation | None:
        return self._relations.get(relation_id)

    def relations_for(self, section_id: int) -> list[Relation]:
        return [r for r in self._relations.values() if r.touches(section_id)]

    def position(self, section_id: int) -> NodePosition | None:
        return self._positions.get(section_id)

    def positions(self) -> dict[int, NodePosition]:
        return dict(self._positions)

    def categories(self) -> list[Category]:
        return sorted(self._categories.values(), key=lambda c: (c.sort_order, c.name))

    def category(self, category_id: int | None) -> Category | None:
        if category_id is None:
            return None
        return self._categories.get(category_id)

    def default_category(self) -> Category | None:
        for c in self.categories():
            if c.is_default:
                return c
        cats = self.categories()
        return cats[0] if cats else None

    # ------------------------------------------------------------------ estatus y responsables (lectura)
    def statuses(self) -> list[Status]:
        return sorted(self._statuses.values(), key=lambda s: (s.sort_order, s.name))

    def status(self, status_id: int | None) -> Status | None:
        return self._statuses.get(status_id) if status_id is not None else None

    def default_status(self) -> Status | None:
        for s in self.statuses():
            if s.is_default:
                return s
        sts = self.statuses()
        return sts[0] if sts else None

    def responsibles(self) -> list[Responsible]:
        return sorted(self._responsibles.values(), key=lambda r: (r.sort_order, r.code))

    def responsible(self, responsible_id: int) -> Responsible | None:
        return self._responsibles.get(responsible_id)

    def responsible_by_code(self, code: str) -> Responsible | None:
        wanted = code.strip().casefold()
        return next((r for r in self._responsibles.values() if r.code.casefold() == wanted), None)

    def section_responsible_ids(self, section_id: int) -> list[int]:
        return [rid for rid in self._section_responsibles.get(section_id, []) if rid in self._responsibles]

    def section_responsibles(self, section_id: int) -> list[Responsible]:
        return [self._responsibles[rid] for rid in self.section_responsible_ids(section_id)]

    def catalog(self) -> list[CatalogEntry]:
        return list(self._catalog.values())

    def catalog_entry(self, code: str) -> CatalogEntry | None:
        """Cláusulas del pliego primero; luego catálogo del proyecto (extras/traducciones) y MasterFormat."""
        key = code_key(normalize_code(code))
        local = self._catalog.get(key)
        clause = self.clauses.get(key)
        if clause is not None:
            title = local.title if local is not None and local.title.strip() else clause.title
            return CatalogEntry(clause.code_key, clause.code, title, palette.CLAUSE_CATEGORY_NAME, kind="clause")
        record = self.master.get(key)
        if local is not None:
            category = local.category_name or (self.master.effective_category(record) if record else None)
            return CatalogEntry(local.code_key, local.code, local.title, category)
        if record is not None:
            return CatalogEntry(record.code_key, record.code, record.title, self.master.effective_category(record))
        return None

    def category_by_name(self, name: str | None, create: bool = True) -> Category | None:
        """Categoría del proyecto por nombre; si no existe y `create`, la crea con los colores semilla."""
        if not name or not name.strip():
            return None
        wanted = name.strip().casefold()
        for c in self._categories.values():
            if c.name.casefold() == wanted:
                return c
        if not create or self.db is None:
            return None
        seed = next((s for s in palette.DEFAULT_CATEGORIES if s.name.casefold() == wanted), None)
        fill, border = (seed.fill, seed.border) if seed else ("#EDEDED", "#8C8C8C")
        return self.add_category(name.strip(), fill, border)

    def catalog_category_id(self, code: str) -> int | None:
        """Id de la categoría del proyecto correspondiente a la clasificación por defecto del catálogo."""
        entry = self.catalog_entry(code)
        if entry is None or not entry.category_name:
            return None
        cat = self.category_by_name(entry.category_name, create=True)
        return cat.id if cat else None

    def master_record(self, code: str) -> CatalogRecord | None:
        return self.master.get(code)

    def is_clause_code(self, code: str) -> bool:
        return self.clauses.get(code) is not None

    def clause_category(self) -> Category | None:
        """Categoría fija de las cláusulas (se crea con los colores semilla si el proyecto no la tiene)."""
        return self.category_by_name(palette.CLAUSE_CATEGORY_NAME, create=True)

    def create_section_from_catalog(self, code_or_key: str, near: Iterable[int] = (),
                                    category_id: int | None = None) -> tuple[Section, bool]:
        """Crea (o devuelve) la sección correspondiente a una entrada del catálogo, con código canónico."""
        entry = self.catalog_entry(code_or_key)
        if entry is None:
            raise ValueError(f"El código {code_or_key!r} no está en el catálogo.")
        existing = self.section_by_code(entry.code)
        if existing is not None:
            return existing, False
        near_ids = [n for n in near if n in self._positions]
        pos = place_new_node({k: (p.x, p.y) for k, p in self._positions.items()}, near_ids)
        if category_id is None and entry.category_name:
            cat = self.category_by_name(entry.category_name, create=True)
            category_id = cat.id if cat else None
        return self.add_section(entry.code, entry.title, category_id, pos, kind=entry.kind), True

    def reclassify_from_catalog(self, apply: bool = False) -> list[tuple[Section, Category]]:
        """Secciones del proyecto cuya categoría difiere de la clasificación del catálogo.

        Con `apply=True` actualiza `category_id` (conserva colores personalizados por sección).
        Devuelve los pares (sección, categoría destino) afectados.
        """
        changes: list[tuple[Section, Category]] = []
        for section in self.sections():
            if section.is_clause:
                continue  # la categoría de una cláusula es fija
            entry = self.catalog_entry(section.code)
            if entry is None or not entry.category_name or entry.kind == "clause":
                continue
            cat = self.category_by_name(entry.category_name, create=apply)
            if cat is None or cat.id == section.category_id:
                continue
            changes.append((section, cat))
        if apply and changes:
            with self.bulk():
                for section, cat in changes:
                    self.update_section(section.id, section.code, section.title, cat.id, section.notes)
        return changes

    def setting(self, key: str, default: str | None = None) -> str | None:
        return self.settings_repo.get(key, default) if self.db else default

    def set_setting(self, key: str, value: str) -> None:
        if self.db:
            with self.db.transaction():
                self.settings_repo.set(key, value)

    # ------------------------------------------------------------------ proyecto
    def update_meta(self, code: str, name: str) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.project_repo.update(code, name)
        self.projectMetaChanged.emit()

    # ------------------------------------------------------------------ categorías
    def add_category(self, name: str, fill: str, border: str) -> Category:
        assert self.db is not None
        with self.db.transaction():
            cat = self.categories_repo.insert(name, fill, border)
        self._categories[cat.id] = cat
        self.categoriesChanged.emit()
        return cat

    def update_category(self, category: Category) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.categories_repo.update(category)
            if category.is_default:
                self.categories_repo.set_default(category.id)
        self._categories = {c.id: c for c in self.categories_repo.all()}
        self.categoriesChanged.emit()
        for s in self._sections.values():
            if s.category_id == category.id:
                self.sectionUpdated.emit(s.id)

    def remove_category(self, category_id: int) -> None:
        assert self.db is not None
        affected = [s.id for s in self._sections.values() if s.category_id == category_id]
        with self.db.transaction():
            self.categories_repo.delete(category_id)
        self._categories.pop(category_id, None)
        for sid in affected:
            self._sections[sid] = self.sections_repo.get(sid)  # type: ignore[assignment]
            self.graph.update_section(self._sections[sid])
        self.categoriesChanged.emit()
        for sid in affected:
            self.sectionUpdated.emit(sid)

    # ------------------------------------------------------------------ estatus y responsables (mutación)
    def add_status(self, name: str, color: str) -> Status:
        assert self.db is not None
        with self.db.transaction():
            st = self.statuses_repo.insert(name, color)
        self._statuses[st.id] = st
        self.statusesChanged.emit()
        return st

    def update_status(self, status: Status) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.statuses_repo.update(status)
            if status.is_default:
                self.statuses_repo.set_default(status.id)
        self._statuses = {s.id: s for s in self.statuses_repo.all()}
        self.statusesChanged.emit()
        for s in self._sections.values():
            if s.status_id == status.id:
                self.sectionUpdated.emit(s.id)

    def remove_status(self, status_id: int) -> None:
        assert self.db is not None
        affected = [s.id for s in self._sections.values() if s.status_id == status_id]
        with self.db.transaction():
            self.statuses_repo.delete(status_id)
        self._statuses.pop(status_id, None)
        for sid in affected:
            self._sections[sid] = self.sections_repo.get(sid)  # type: ignore[assignment]
        self.statusesChanged.emit()
        for sid in affected:
            self.sectionUpdated.emit(sid)

    def add_responsible(self, code: str, name: str, color: str) -> Responsible:
        assert self.db is not None
        with self.db.transaction():
            resp = self.responsibles_repo.insert(code, name, color)
        self._responsibles[resp.id] = resp
        self.responsiblesChanged.emit()
        return resp

    def update_responsible(self, resp: Responsible) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.responsibles_repo.update(resp)
        self._responsibles = {r.id: r for r in self.responsibles_repo.all()}
        self.responsiblesChanged.emit()
        for sid, rids in self._section_responsibles.items():
            if resp.id in rids and sid in self._sections:
                self.sectionUpdated.emit(sid)

    def remove_responsible(self, responsible_id: int) -> None:
        assert self.db is not None
        affected = [sid for sid, rids in self._section_responsibles.items() if responsible_id in rids]
        with self.db.transaction():
            self.responsibles_repo.delete(responsible_id)  # cascada en section_responsibles
        self._responsibles.pop(responsible_id, None)
        for sid in affected:
            self._section_responsibles[sid] = [r for r in self._section_responsibles[sid] if r != responsible_id]
        self.responsiblesChanged.emit()
        for sid in affected:
            if sid in self._sections:
                self.sectionUpdated.emit(sid)

    def set_section_responsibles(self, section_id: int, responsible_ids: list[int]) -> None:
        assert self.db is not None
        if self._sections[section_id].is_clause:
            return  # las cláusulas no tienen responsables
        ids = [rid for rid in dict.fromkeys(responsible_ids) if rid in self._responsibles]
        if ids == self.section_responsible_ids(section_id):
            return
        with self.db.transaction():
            self.responsibles_repo.set_for_section(section_id, ids)
            self.db.touch()
        self._section_responsibles[section_id] = ids
        self.sectionUpdated.emit(section_id)

    def set_section_status(self, section_id: int, status_id: int | None) -> None:
        s = self._sections[section_id]
        if s.is_clause:
            return  # las cláusulas no tienen estatus
        if s.status_id != status_id:
            self.update_section(section_id, s.code, s.title, s.category_id, s.notes, status_id=status_id)

    def set_section_progress(self, section_id: int, progress: int) -> None:
        s = self._sections[section_id]
        if s.is_clause:
            return  # las cláusulas no tienen avance
        progress = max(0, min(100, int(progress)))
        if s.progress != progress:
            self.update_section(section_id, s.code, s.title, s.category_id, s.notes, progress=progress)

    def set_section_observations(self, section_id: int, text: str | None) -> None:
        s = self._sections[section_id]
        notes = (text or "").strip() or None
        if s.notes != notes:
            self.update_section(section_id, s.code, s.title, s.category_id, notes)

    # ------------------------------------------------------------------ secciones
    def add_section(self, code: str, title: str = "", category_id: int | None = None,
                    position: tuple[float, float] | None = None, kind: str = "section") -> Section:
        """Idempotente por code_key: si existe, la devuelve sin modificar.

        `kind="clause"`: cláusula del pliego, con categoría fija «Cláusula», sin estatus ni avance.
        """
        assert self.db is not None
        existing = self.section_by_code(code)
        if existing is not None:
            return existing
        if kind == "clause":
            cat = self.clause_category()
            category_id = cat.id if cat else None
            status_id = None
        else:
            if category_id is None:
                default = self.default_category()
                category_id = default.id if default else None
            default_status = self.default_status()
            status_id = default_status.id if default_status else None
        with self.db.transaction():
            section = self.sections_repo.insert(code, title, category_id, status_id=status_id, kind=kind)
            if position is None:
                position = place_new_node({k: (p.x, p.y) for k, p in self._positions.items()})
            self.positions_repo.upsert(section.id, position[0], position[1], False)
            self.db.touch()
        self._sections[section.id] = section
        self._positions[section.id] = NodePosition(section.id, position[0], position[1], False)
        self.graph.add_section(section)
        self.sectionAdded.emit(section.id)
        self._schedule_graph_changed()
        return section

    def get_or_create_section(self, text: str, near: Iterable[int] = ()) -> tuple[Section, bool]:
        """Resuelve texto libre ('31 23 00 Excavación') a una sección; la crea si no existe.

        Devuelve (sección, creada). Si el código está en el catálogo se usa su título.
        """
        code, title = split_code_title(text)
        if not code:
            raise ValueError("Debe indicar el número de la sección.")
        code = normalize_code(code)  # '0330 00' -> '03 30 00'
        existing = self.section_by_code(code)
        if existing is not None:
            if title and not existing.title.strip():
                # La sección existía sin descripción: completar con la que escribió el usuario.
                self.update_section(existing.id, existing.code, title, existing.category_id, existing.notes)
                existing = self._sections[existing.id]
            return existing, False
        entry = self.catalog_entry(code)
        if entry is not None:
            code = entry.code
            if not title:
                title = entry.title
        near_ids = [n for n in near if n in self._positions]
        pos = place_new_node({k: (p.x, p.y) for k, p in self._positions.items()}, near_ids)
        category_id = None
        if entry is not None and entry.category_name:
            cat = self.category_by_name(entry.category_name, create=True)
            category_id = cat.id if cat else None
        return self.add_section(code, title, category_id, pos, kind=entry.kind if entry else "section"), True

    def update_section(self, section_id: int, code: str, title: str,
                       category_id: int | None, notes: str | None = None,
                       fill_color: str | None | object = KEEP,
                       border_color: str | None | object = KEEP,
                       status_id: int | None | object = KEEP,
                       progress: int | object = KEEP) -> None:
        """Actualiza la sección. Colores, estatus y avance se conservan salvo que se indiquen."""
        assert self.db is not None
        section = self._sections[section_id]
        other = self.section_by_code(code)
        if other is not None and other.id != section_id:
            raise ValueError(f"Ya existe otra sección con el código {other.code}.")
        fill = section.fill_color if fill_color is KEEP else fill_color
        border = section.border_color if border_color is KEEP else border_color
        if fill and not border:
            border = derive_border_color(fill)
        new_status = section.status_id if status_id is KEEP else status_id
        new_progress = section.progress if progress is KEEP else max(0, min(100, int(progress)))  # type: ignore[arg-type]
        if section.is_clause:
            # Una cláusula no tiene estatus ni avance y su categoría es fija.
            new_status, new_progress, category_id = None, 0, section.category_id
        updated = Section(section.id, code, code_key(code), title, category_id, notes,
                          section.created_at, section.updated_at, fill, border if fill else None,
                          new_status, new_progress, section.kind)
        with self.db.transaction():
            self.sections_repo.update(updated)
            self.db.touch()
        self._sections[section_id] = self.sections_repo.get(section_id)  # type: ignore[assignment]
        self.graph.update_section(self._sections[section_id])
        self.sectionUpdated.emit(section_id)

    def set_section_category(self, section_id: int, category_id: int | None) -> None:
        s = self._sections[section_id]
        self.update_section(section_id, s.code, s.title, category_id, s.notes)

    def set_section_colors(self, section_id: int, fill_color: str | None,
                           border_color: str | None = None) -> None:
        """Color personalizado de la sección; `fill_color=None` vuelve al color de la categoría."""
        s = self._sections[section_id]
        self.update_section(section_id, s.code, s.title, s.category_id, s.notes, fill_color, border_color)

    def section_colors(self, section: Section) -> tuple[str, str]:
        """Colores efectivos (relleno, borde): personalizado > categoría > neutro."""
        if section.fill_color:
            return section.fill_color, section.border_color or derive_border_color(section.fill_color)
        cat = self.category(section.category_id)
        if cat is not None:
            return cat.fill_color, cat.border_color
        return palette.SURFACE_ALT, palette.BORDER_STRONG

    def remove_section(self, section_id: int) -> SectionRemoval:
        assert self.db is not None
        section = self._sections[section_id]
        relations = self.relations_for(section_id)
        removal = SectionRemoval(section, relations, self._positions.get(section_id))
        with self.db.transaction():
            self.sections_repo.delete(section_id)  # cascada: relaciones, posición, layout3d
            self.db.touch()
        for r in relations:
            self._relations.pop(r.id, None)
            self.graph.remove_relation(r)
        self._sections.pop(section_id, None)
        self._positions.pop(section_id, None)
        self._section_responsibles.pop(section_id, None)
        self.graph.remove_section(section_id)
        for r in relations:
            self.relationRemoved.emit(r.id)
        self.sectionRemoved.emit(section_id)
        self._schedule_graph_changed()
        return removal

    # ------------------------------------------------------------------ relaciones
    def add_relation(self, a_id: int, kind: UiKind, b_id: int, notes: str | None = None) -> Relation:
        """Lanza SelfRelationError o DuplicateRelationError(existing) si ya existe esa misma dirección.

        La relación inversa (B → A) es independiente: se puede agregar sin conflicto.
        """
        assert self.db is not None
        source_id, target_id, rk = normalize(a_id, kind, b_id)
        existing = self.relations_repo.find_directed(source_id, target_id)
        if existing is not None:
            raise DuplicateRelationError(existing, (source_id, target_id, rk))
        try:
            with self.db.transaction():
                rel = self.relations_repo.insert(source_id, target_id, rk, (notes or "").strip() or None)
                self.db.touch()
        except sqlite3.IntegrityError as exc:
            existing = self.relations_repo.find_directed(source_id, target_id)
            if existing is not None:
                raise DuplicateRelationError(existing, (source_id, target_id, rk)) from exc
            raise
        self._relations[rel.id] = rel
        self.graph.add_relation(rel)
        self.relationAdded.emit(rel.id)
        self._schedule_graph_changed()
        return rel

    def update_relation(self, relation_id: int, a_id: int, kind: UiKind, b_id: int) -> Relation:
        """Cambia extremos y/o tipo. Conserva la geometría si el par no cambió."""
        assert self.db is not None
        old = self._relations[relation_id]
        source_id, target_id, rk = normalize(a_id, kind, b_id)
        if (source_id, target_id, rk) == (old.source_id, old.target_id, old.kind):
            return old
        clash = self.relations_repo.find_directed(source_id, target_id)
        if clash is not None and clash.id != relation_id:
            raise DuplicateRelationError(clash, (source_id, target_id, rk))
        # Si se invierte la dirección, la geometría se invalida porque los puertos cambian de nodo.
        keep_geometry = (source_id, target_id) == (old.source_id, old.target_id)
        with self.db.transaction():
            self.relations_repo.update_endpoints(relation_id, source_id, target_id, rk, keep_geometry)
            self.db.touch()
        new = self.relations_repo.get(relation_id)
        assert new is not None
        self._relations[relation_id] = new
        self.graph.replace_relation(old, new)
        self.relationUpdated.emit(relation_id)
        self._schedule_graph_changed()
        return new

    def invert_relation(self, relation_id: int) -> Relation:
        """Cambia A → B por B → A. Lanza DuplicateRelationError si B → A ya existe como otra flecha."""
        rel = self._relations[relation_id]
        return self.update_relation(relation_id, rel.target_id, UiKind.REFERENCES, rel.source_id)

    def reverse_relation(self, relation_id: int) -> Relation | None:
        """La flecha en sentido contrario (B → A) si existe."""
        rel = self._relations.get(relation_id)
        if rel is None:
            return None
        return next((r for r in self._relations.values()
                     if r.source_id == rel.target_id and r.target_id == rel.source_id), None)

    def set_relation_notes(self, relation_id: int, notes: str | None) -> Relation:
        assert self.db is not None
        text = (notes or "").strip() or None
        rel = self._relations[relation_id]
        if rel.notes == text:
            return rel
        with self.db.transaction():
            self.relations_repo.update_notes(relation_id, text)
            self.db.touch()
        new = self.relations_repo.get(relation_id)
        assert new is not None
        self._relations[relation_id] = new
        self.relationUpdated.emit(relation_id)
        return new

    def set_relation_style(self, relation_id: int, *, color: object = KEEP, dash: object = KEEP,
                           width: object = KEEP) -> Relation:
        """Estilo propio de la flecha. KEEP conserva el valor; None (color/grosor) y 'solid' = predeterminado.

        Lanza ValueError (mensaje en español) si el color no es #RRGGBB, el trazo no existe o el grosor
        está fuera de rango. Emite relationUpdated (la escena, la tabla y la vista 3D se repintan).
        """
        assert self.db is not None
        rel = self._relations[relation_id]
        if color is KEEP:
            new_color = rel.line_color
        elif color:
            new_color = valid_hex(str(color))
            if new_color is None:
                raise ValueError(f"Color no válido: {color!r}. Use el formato #RRGGBB.")
        else:
            new_color = None
        new_dash = rel.line_dash if dash is KEEP else (str(dash) if dash else "solid")
        if new_dash not in DASH_KEYS:
            raise ValueError(f"Trazo desconocido: {dash!r}.")
        if width is KEEP:
            new_width = rel.line_width
        elif width is None:
            new_width = None
        else:
            new_width = round(float(width), 2)  # type: ignore[arg-type]
            if not WIDTH_MIN <= new_width <= WIDTH_MAX:
                raise ValueError(f"El grosor debe estar entre {WIDTH_MIN:g} y {WIDTH_MAX:g} px.")
        if (new_color, new_dash, new_width) == rel.style:
            return rel
        with self.db.transaction():
            self.relations_repo.update_style(relation_id, new_color, new_dash, new_width)
            self.db.touch()
        new = self.relations_repo.get(relation_id)
        assert new is not None
        self._relations[relation_id] = new
        self.relationUpdated.emit(relation_id)
        return new

    def set_relations_style(self, relation_ids: Iterable[int], *, color: object = KEEP, dash: object = KEEP,
                            width: object = KEEP) -> None:
        """Mismo estilo para varias flechas, en una sola transacción."""
        ids = [rid for rid in relation_ids if rid in self._relations]
        if not ids:
            return
        with self.bulk():
            for rid in ids:
                self.set_relation_style(rid, color=color, dash=dash, width=width)

    def reset_relation_style(self, relation_id: int) -> Relation:
        return self.set_relation_style(relation_id, color=None, dash="solid", width=None)

    def set_relation_geometry(self, relation_id: int, waypoints: list[tuple[float, float]] | None,
                              source_port: Side | None, target_port: Side | None) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.relations_repo.update_geometry(relation_id, waypoints, source_port, target_port)
        rel = self.relations_repo.get(relation_id)
        assert rel is not None
        self._relations[relation_id] = rel
        self.relationGeometryChanged.emit(relation_id)

    def remove_relation(self, relation_id: int) -> Relation:
        assert self.db is not None
        rel = self._relations[relation_id]
        with self.db.transaction():
            self.relations_repo.delete(relation_id)
            self.db.touch()
        self._relations.pop(relation_id, None)
        self.graph.remove_relation(rel)
        self.relationRemoved.emit(relation_id)
        self._schedule_graph_changed()
        return rel

    # ------------------------------------------------------------------ posiciones
    def move_node(self, section_id: int, x: float, y: float, pinned: bool = True) -> None:
        self.move_nodes({section_id: (x, y)}, pinned)

    def move_nodes(self, moves: dict[int, tuple[float, float]], pinned: bool = True) -> None:
        assert self.db is not None
        changed: list[tuple[int, float, float]] = []
        with self.db.transaction():
            for sid, (x, y) in moves.items():
                if sid not in self._sections:
                    continue
                cur = self._positions.get(sid)
                if cur is not None and abs(cur.x - x) < 0.01 and abs(cur.y - y) < 0.01 and cur.pinned == pinned:
                    continue
                self.positions_repo.upsert(sid, x, y, pinned)
                self._positions[sid] = NodePosition(sid, x, y, pinned)
                changed.append((sid, x, y))
        for sid, x, y in changed:
            self.positionChanged.emit(sid, x, y)

    def unpinned_ids(self) -> list[int]:
        return [sid for sid, p in self._positions.items() if not p.pinned]

    # ------------------------------------------------------------------ 3D
    def layout3d(self) -> dict[int, tuple[float, float, float]]:
        return self.layout3d_repo.all() if self.db else {}

    def store_layout3d(self, positions: dict[int, tuple[float, float, float]], seed: int) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.layout3d_repo.replace_all(positions)
            self.settings_repo.set("layout3d_seed", str(seed))
            self.settings_repo.set("layout3d_graph_hash", self.graph.graph_hash())

    # ------------------------------------------------------------------ catálogo
    def merge_catalog(self, entries: Iterable[CatalogEntry]) -> int:
        assert self.db is not None
        entries = list(entries)
        with self.db.transaction():
            count = self.catalog_repo.merge(entries)
        self._catalog = {e.code_key: e for e in self.catalog_repo.all()}
        self.catalogChanged.emit()
        return count

    def clear_catalog(self) -> None:
        assert self.db is not None
        with self.db.transaction():
            self.catalog_repo.clear()
        self._catalog.clear()
        self.catalogChanged.emit()

    # ------------------------------------------------------------------ interno
    def _schedule_graph_changed(self) -> None:
        self._graph_timer.start()


@dataclass
class ProjectSnapshot:
    """Vista inmutable del proyecto con la misma API de lectura que usan los exportadores."""

    path: Path | None
    _meta: ProjectMeta
    _sections: dict[int, Section]
    _relations: dict[int, Relation]
    _categories: dict[int, Category]
    _statuses: dict[int, Status]
    _responsibles: dict[int, Responsible]
    _section_responsibles: dict[int, list[int]]
    _positions: dict[int, NodePosition] = field(default_factory=dict)
    graph: GraphEngine = field(default_factory=GraphEngine)

    is_open = True

    def meta(self) -> ProjectMeta:
        return self._meta

    def sections(self) -> list[Section]:
        return sorted(self._sections.values(), key=lambda s: sort_key(s.code_key))

    def section(self, section_id: int) -> Section | None:
        return self._sections.get(section_id)

    def relations(self) -> list[Relation]:
        return list(self._relations.values())

    def relations_for(self, section_id: int) -> list[Relation]:
        return [r for r in self._relations.values() if r.touches(section_id)]

    def categories(self) -> list[Category]:
        return sorted(self._categories.values(), key=lambda c: (c.sort_order, c.name))

    def category(self, category_id: int | None) -> Category | None:
        return self._categories.get(category_id) if category_id is not None else None

    def statuses(self) -> list[Status]:
        return sorted(self._statuses.values(), key=lambda s: (s.sort_order, s.name))

    def status(self, status_id: int | None) -> Status | None:
        return self._statuses.get(status_id) if status_id is not None else None

    def responsibles(self) -> list[Responsible]:
        return sorted(self._responsibles.values(), key=lambda r: (r.sort_order, r.code))

    def section_responsible_ids(self, section_id: int) -> list[int]:
        return [rid for rid in self._section_responsibles.get(section_id, []) if rid in self._responsibles]

    def section_responsibles(self, section_id: int) -> list[Responsible]:
        return [self._responsibles[rid] for rid in self.section_responsible_ids(section_id)]

    def position(self, section_id: int) -> NodePosition | None:
        return self._positions.get(section_id)

    def section_colors(self, section: Section) -> tuple[str, str]:
        if section.fill_color:
            return section.fill_color, section.border_color or derive_border_color(section.fill_color)
        cat = self.category(section.category_id)
        if cat is not None:
            return cat.fill_color, cat.border_color
        return palette.SURFACE_ALT, palette.BORDER_STRONG
