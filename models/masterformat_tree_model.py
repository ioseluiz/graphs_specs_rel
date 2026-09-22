"""Árbol División › nivel 2 › 3 › 4 del catálogo MasterFormat (+ raíz «Cláusulas»), con filtro recursivo."""
from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QAbstractItemModel, QMimeData, QModelIndex, QSortFilterProxyModel, Qt

from config import palette
from models.clause_catalog import ClauseCatalog, ClauseRecord
from models.master_catalog import CatalogRecord, MasterCatalog
from models.relation_normalizer import search_key, sort_key
from models.section_completer_model import build_query, matches_query

ROLE_RECORD = Qt.ItemDataRole.UserRole + 1
ROLE_CODE = Qt.ItemDataRole.UserRole + 2
ROLE_TITLE = Qt.ItemDataRole.UserRole + 3
ROLE_CODE_KEY = Qt.ItemDataRole.UserRole + 4
ROLE_LEVEL = Qt.ItemDataRole.UserRole + 5
ROLE_IN_PROJECT = Qt.ItemDataRole.UserRole + 6
ROLE_QUALITY = Qt.ItemDataRole.UserRole + 7
ROLE_SEARCH = Qt.ItemDataRole.UserRole + 8
ROLE_CATEGORY = Qt.ItemDataRole.UserRole + 9       # nombre de la clasificación efectiva
ROLE_HAS_OVERRIDE = Qt.ItemDataRole.UserRole + 10  # el usuario corrigió la clasificación
ROLE_HIDDEN = Qt.ItemDataRole.UserRole + 11        # oculta por el usuario
ROLE_USER_ADDED = Qt.ItemDataRole.UserRole + 12    # agregada por el usuario
ROLE_TITLE_EDITED = Qt.ItemDataRole.UserRole + 13  # título editado por el usuario
ROLE_SOURCE = Qt.ItemDataRole.UserRole + 14        # 'mf' (MasterFormat) | 'clause' | 'group'

MIME_SECTION = "application/x-specrel-section"


@dataclass
class _Node:
    record: CatalogRecord | ClauseRecord | None
    parent: "_Node | None" = None
    children: list["_Node"] = field(default_factory=list)
    row: int = 0
    source: str = "mf"


class MasterFormatTreeModel(QAbstractItemModel):
    def __init__(self, catalog: MasterCatalog, parent=None, *, clauses: ClauseCatalog | None = None) -> None:
        super().__init__(parent)
        self.catalog = catalog
        self.clauses: ClauseCatalog = clauses if clauses is not None else ClauseCatalog()
        self._root = _Node(None)
        self._by_key: dict[str, _Node] = {}
        self._project_keys: set[str] = set()
        self.reload()

    # ------------------------------------------------------------------ construcción
    def reload(self) -> None:
        self.beginResetModel()
        self._root = _Node(None)
        self._by_key = {}
        records = self.catalog.all(include_hidden=True)  # las ocultas se filtran en el proxy
        nodes = {r.code_key: _Node(r) for r in records}
        # Enlazar por parent_key; si el padre no existe, buscar el ancestro más cercano o colgar de la raíz.
        for rec in sorted(records, key=lambda r: (r.level, r.code_key)):
            node = nodes[rec.code_key]
            parent = None
            pk = rec.parent_key
            while pk and parent is None:
                parent = nodes.get(pk)
                if parent is None:
                    parent_rec_key = pk
                    pk = _ancestor_key(parent_rec_key)
            target = parent if parent is not None else self._root
            node.parent = target
            node.row = len(target.children)
            target.children.append(node)
            self._by_key[rec.code_key] = node
        for parent in [self._root, *nodes.values()]:
            parent.children.sort(key=lambda n: n.record.code_key if n.record else "")
            for i, child in enumerate(parent.children):
                child.row = i
        self._append_clauses()
        self.endResetModel()

    def _append_clauses(self) -> None:
        """Raíz «Cláusulas 4.28» al final del árbol: cláusulas y, debajo, sus subcláusulas."""
        if not self.clauses.available:
            return
        group_rec = ClauseRecord(code_key="", code=self.clauses.root_label, title="", level=0, parent_key=None)
        group = _Node(group_rec, parent=self._root, row=len(self._root.children), source="group")
        self._root.children.append(group)
        for clause in self.clauses.roots():
            node = _Node(clause, parent=group, row=len(group.children), source="clause")
            group.children.append(node)
            self._by_key[clause.code_key] = node
            for sub in self.clauses.children(clause.code_key):
                child = _Node(sub, parent=node, row=len(node.children), source="clause")
                node.children.append(child)
                self._by_key[sub.code_key] = child

    @property
    def clause_group_index(self) -> QModelIndex:
        for node in self._root.children:
            if node.source == "group":
                return self.index_for_node(node)
        return QModelIndex()

    def set_project_keys(self, keys: set[str]) -> None:
        changed = self._project_keys ^ keys
        self._project_keys = set(keys)
        for key in changed:
            node = self._by_key.get(key)
            if node is not None:
                idx = self.index_for_node(node)
                self.dataChanged.emit(idx, idx, [ROLE_IN_PROJECT])

    def refresh_all(self) -> None:
        """Repinta todo el árbol (p. ej. tras corregir clasificaciones) sin reconstruirlo."""
        if self._root.children:
            top = self.index(0, 0)
            last = self.index(len(self._root.children) - 1, 0)
            self.dataChanged.emit(top, last, [ROLE_CATEGORY, ROLE_HAS_OVERRIDE])
            for node in self._by_key.values():
                if node.children:
                    idx = self.index_for_node(node)
                    self.dataChanged.emit(self.index(0, 0, idx), self.index(len(node.children) - 1, 0, idx),
                                          [ROLE_CATEGORY, ROLE_HAS_OVERRIDE])

    def index_for_key(self, key: str) -> QModelIndex:
        node = self._by_key.get(key)
        return self.index_for_node(node) if node is not None else QModelIndex()

    def index_for_node(self, node: _Node) -> QModelIndex:
        if node is self._root or node.parent is None:
            return QModelIndex()
        return self.createIndex(node.row, 0, node)

    # ------------------------------------------------------------------ Qt API
    def _node(self, index: QModelIndex) -> _Node:
        return index.internalPointer() if index.isValid() else self._root

    def index(self, row: int, column: int, parent: QModelIndex = QModelIndex()) -> QModelIndex:
        node = self._node(parent)
        if 0 <= row < len(node.children) and column == 0:
            return self.createIndex(row, column, node.children[row])
        return QModelIndex()

    def parent(self, index: QModelIndex = QModelIndex()) -> QModelIndex:  # type: ignore[override]
        if not index.isValid():
            return QModelIndex()
        node: _Node = index.internalPointer()
        if node.parent is None or node.parent is self._root:
            return QModelIndex()
        return self.createIndex(node.parent.row, 0, node.parent)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return len(self._node(parent).children)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if index.internalPointer().source == "group":
            return base  # el grupo «Cláusulas» no se arrastra ni se agrega
        return base | Qt.ItemFlag.ItemIsDragEnabled

    def _clause_data(self, node: _Node, role: int):
        rec: ClauseRecord = node.record
        if node.source == "group":
            if role == Qt.ItemDataRole.DisplayRole:
                return rec.code
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"{rec.code}: {len(self.clauses)} cláusulas y subcláusulas del pliego"
            if role == ROLE_CODE:
                return rec.code
            if role in (ROLE_TITLE, ROLE_CODE_KEY):
                return ""
            if role == ROLE_LEVEL:
                return 1
            if role == ROLE_SEARCH:
                return search_key(rec.code) + " clausula clausulas"
            if role == ROLE_CATEGORY:
                return palette.CLAUSE_CATEGORY_NAME
            if role == ROLE_SOURCE:
                return "group"
            if role in (ROLE_IN_PROJECT, ROLE_HAS_OVERRIDE, ROLE_HIDDEN, ROLE_USER_ADDED, ROLE_TITLE_EDITED):
                return False
            return None
        if role == Qt.ItemDataRole.DisplayRole:
            return rec.label
        if role == Qt.ItemDataRole.ToolTipRole:
            extra = " · ya está en el proyecto" if rec.code_key in self._project_keys else ""
            return f"{rec.code} - {rec.title}\n{rec.kind_label}{extra}\nNodo rosado sin estatus ni avance"
        if role == ROLE_CATEGORY:
            return palette.CLAUSE_CATEGORY_NAME
        if role == ROLE_SOURCE:
            return "clause"
        if role in (ROLE_HAS_OVERRIDE, ROLE_HIDDEN, ROLE_USER_ADDED, ROLE_TITLE_EDITED):
            return False
        if role == ROLE_RECORD:
            return rec
        if role == ROLE_CODE:
            return rec.code
        if role == ROLE_TITLE:
            return rec.title
        if role == ROLE_CODE_KEY:
            return rec.code_key
        if role == ROLE_LEVEL:
            return 2 + rec.level   # 3 = cláusula, 4 = subcláusula: el delegate las pinta como hojas
        if role == ROLE_IN_PROJECT:
            return rec.code_key in self._project_keys
        if role == ROLE_QUALITY:
            return rec.quality
        if role == ROLE_SEARCH:
            return rec.search
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        node: _Node = index.internalPointer()
        if node.source != "mf":
            return self._clause_data(node, role)
        rec: CatalogRecord = node.record
        if role == ROLE_SOURCE:
            return "mf"
        if role == Qt.ItemDataRole.DisplayRole:
            return rec.label
        if role == Qt.ItemDataRole.ToolTipRole:
            extra = " · ya está en el proyecto" if rec.code_key in self._project_keys else ""
            warn = " · título por verificar" if rec.quality == "review" else ""
            category = self.catalog.effective_category(rec) or "sin clasificar"
            fixed = " (corregida por el usuario)" if self.catalog.has_override(rec.code_key) else ""
            flags = []
            if self.catalog.is_user_added(rec.code_key):
                flags.append("agregada por el usuario")
            if self.catalog.is_title_edited(rec.code_key):
                flags.append("título editado")
            if self.catalog.is_hidden(rec.code_key):
                flags.append("oculta")
            tail = f"\n{', '.join(flags)}" if flags else ""
            return f"{rec.code} - {rec.title}\nNivel {rec.level}{extra}{warn}\nClasificación: {category}{fixed}{tail}"
        if role == ROLE_CATEGORY:
            return self.catalog.effective_category(rec)
        if role == ROLE_HAS_OVERRIDE:
            return self.catalog.has_override(rec.code_key)
        if role == ROLE_HIDDEN:
            return self.catalog.is_hidden(rec.code_key)
        if role == ROLE_USER_ADDED:
            return self.catalog.is_user_added(rec.code_key)
        if role == ROLE_TITLE_EDITED:
            return self.catalog.is_title_edited(rec.code_key)
        if role == ROLE_RECORD:
            return rec
        if role == ROLE_CODE:
            return rec.code
        if role == ROLE_TITLE:
            return rec.title
        if role == ROLE_CODE_KEY:
            return rec.code_key
        if role == ROLE_LEVEL:
            return rec.level
        if role == ROLE_IN_PROJECT:
            return rec.code_key in self._project_keys
        if role == ROLE_QUALITY:
            return rec.quality
        if role == ROLE_SEARCH:
            return rec.search
        return None

    # ------------------------------------------------------------------ arrastre
    def mimeTypes(self) -> list[str]:  # noqa: N802
        return [MIME_SECTION, "text/plain"]

    def mimeData(self, indexes) -> QMimeData:  # noqa: N802
        data = QMimeData()
        valid = [idx for idx in indexes if idx.isValid() and idx.data(ROLE_CODE_KEY)]
        keys = [idx.data(ROLE_CODE_KEY) for idx in valid]
        labels = [idx.data(Qt.ItemDataRole.DisplayRole) for idx in valid]
        data.setData(MIME_SECTION, ";".join(keys).encode("utf-8"))
        data.setText("\n".join(labels))
        return data

    def supportedDragActions(self) -> Qt.DropAction:  # noqa: N802
        return Qt.DropAction.CopyAction


def _ancestor_key(key: str) -> str | None:
    """Clave del padre inferido a partir de una clave ('310000' -> None, '312300' -> '310000', ...)."""
    if len(key) > 6:
        return key[:6]
    if key.endswith("0000"):
        return None
    if key.endswith("00"):
        return key[:2] + "0000"
    return key[:4] + "00"


class CatalogTreeFilterProxy(QSortFilterProxyModel):
    """Filtro recursivo por tokens/dígitos y, opcionalmente, solo secciones del proyecto."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tokens: list[str] = []
        self._digits = ""
        self._only_project = False
        self._show_hidden = False
        self.setRecursiveFilteringEnabled(True)
        self.setDynamicSortFilter(False)

    @property
    def is_filtering(self) -> bool:
        return bool(self._tokens or self._digits or self._only_project)

    def set_show_hidden(self, on: bool) -> None:
        if on != self._show_hidden:
            self._show_hidden = on
            self.invalidateFilter()

    def set_query(self, text: str) -> None:
        tokens, digits = build_query(text)
        if (tokens, digits) != (self._tokens, self._digits):
            self._tokens, self._digits = tokens, digits
            self.invalidateFilter()

    def set_only_project(self, on: bool) -> None:
        if on != self._only_project:
            self._only_project = on
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        idx = self.sourceModel().index(source_row, 0, source_parent)
        if not self._show_hidden and idx.data(ROLE_HIDDEN):
            return False
        if self._only_project and not idx.data(ROLE_IN_PROJECT):
            return False
        if not self._tokens and not self._digits:
            return True
        return matches_query(idx.data(ROLE_SEARCH) or "", idx.data(ROLE_CODE_KEY) or "",
                             self._tokens, self._digits)
