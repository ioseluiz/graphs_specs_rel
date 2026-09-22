"""Modelo de la pestaña «Secciones»: todas las secciones del proyecto con sus atributos editables."""
from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, QSortFilterProxyModel, Qt, pyqtSignal

from config import palette
from models.project_model import ProjectModel
from models.relation_normalizer import search_key, sort_key

COL_CODE, COL_TITLE, COL_CATEGORY, COL_STATUS, COL_PROGRESS, COL_RESP, COL_OBS = range(7)
HEADERS = ["Número", "Descripción", "Categoría", "Estatus", "Avance", "Responsables", "Observaciones"]

ROLE_SECTION_ID = Qt.ItemDataRole.UserRole + 1
ROLE_COLOR = Qt.ItemDataRole.UserRole + 2        # color asociado a la celda (categoría/estatus)
ROLE_BORDER = Qt.ItemDataRole.UserRole + 3
ROLE_RESPONSIBLES = Qt.ItemDataRole.UserRole + 4  # list[(id, code, color)]
ROLE_SORT = Qt.ItemDataRole.UserRole + 5
ROLE_SEARCH = Qt.ItemDataRole.UserRole + 6


class SectionsTableModel(QAbstractTableModel):
    editRequested = pyqtSignal(int, int, object)  # section_id, column, value

    def __init__(self, project: ProjectModel, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self._ids: list[int] = []
        project.projectLoaded.connect(self.reload)
        project.projectClosed.connect(self.reload)
        project.sectionAdded.connect(self._on_added)
        project.sectionUpdated.connect(self._on_updated)
        project.sectionRemoved.connect(self._on_removed)
        for sig in (project.categoriesChanged, project.statusesChanged, project.responsiblesChanged):
            sig.connect(self._refresh_all)
        self.reload()

    # ------------------------------------------------------------------ mantenimiento
    def reload(self) -> None:
        self.beginResetModel()
        self._ids = [s.id for s in self.project.sections()]
        self.endResetModel()

    def _refresh_all(self) -> None:
        if self._ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._ids) - 1, COL_OBS))

    def _on_added(self, sid: int) -> None:
        keys = [sort_key(self.project.section(i).code_key) for i in self._ids]
        key = sort_key(self.project.section(sid).code_key)
        row = sum(1 for k in keys if k < key)
        self.beginInsertRows(QModelIndex(), row, row)
        self._ids.insert(row, sid)
        self.endInsertRows()

    def _on_updated(self, sid: int) -> None:
        if sid not in self._ids:
            self._on_added(sid)
            return
        row = self._ids.index(sid)
        self.dataChanged.emit(self.index(row, 0), self.index(row, COL_OBS))

    def _on_removed(self, sid: int) -> None:
        if sid in self._ids:
            row = self._ids.index(sid)
            self.beginRemoveRows(QModelIndex(), row, row)
            self._ids.pop(row)
            self.endRemoveRows()

    def row_of(self, section_id: int) -> int:
        try:
            return self._ids.index(section_id)
        except ValueError:
            return -1

    # ------------------------------------------------------------------ Qt API
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._ids)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(HEADERS)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return HEADERS[section]
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        base = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        editable = (COL_TITLE, COL_CATEGORY, COL_STATUS, COL_PROGRESS, COL_RESP, COL_OBS)
        if index.isValid() and 0 <= index.row() < len(self._ids):
            sec = self.project.section(self._ids[index.row()])
            if sec is not None and sec.is_clause:
                editable = (COL_TITLE, COL_OBS)   # cláusula: categoría fija, sin estatus/avance/responsables
        if index.column() in editable:
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        sid = self._ids[index.row()]
        sec = self.project.section(sid)
        if sec is None:
            return None
        col = index.column()
        if role == ROLE_SECTION_ID:
            return sid
        if role == ROLE_SEARCH:
            resp = " ".join(r.code for r in self.project.section_responsibles(sid))
            st = self.project.status(sec.status_id)
            kind = "clausula" if sec.is_clause else ""
            return search_key(f"{sec.code_key} {sec.code} {sec.title} {resp} {st.name if st else ''} "
                              f"{sec.notes or ''} {kind}")
        if col == COL_CODE:
            if role == Qt.ItemDataRole.DisplayRole:
                return sec.code
            if role == ROLE_SORT:
                return sort_key(sec.code_key)
            if role in (ROLE_COLOR, ROLE_BORDER):
                fill, border = self.project.section_colors(sec)
                return fill if role == ROLE_COLOR else border
        elif col == COL_TITLE:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, ROLE_SORT):
                return sec.title
        elif col == COL_CATEGORY:
            cat = self.project.category(sec.category_id)
            if role == Qt.ItemDataRole.DisplayRole or role == ROLE_SORT:
                return cat.name if cat else ""
            if role == Qt.ItemDataRole.EditRole:
                return sec.category_id
            if role == ROLE_COLOR:
                return cat.fill_color if cat else palette.SURFACE_ALT
            if role == ROLE_BORDER:
                return cat.border_color if cat else palette.BORDER_STRONG
        elif col == COL_STATUS:
            st = self.project.status(sec.status_id)
            if role == Qt.ItemDataRole.DisplayRole or role == ROLE_SORT:
                return st.name if st else ""
            if role == Qt.ItemDataRole.EditRole:
                return sec.status_id
            if role == ROLE_COLOR:
                return st.color if st else palette.SURFACE_ALT
            if role == ROLE_BORDER:
                return palette.BORDER_STRONG
        elif col == COL_PROGRESS:
            if sec.is_clause:
                return "" if role == Qt.ItemDataRole.DisplayRole else (-1 if role == ROLE_SORT else None)
            if role == Qt.ItemDataRole.DisplayRole:
                return f"{sec.progress} %"
            if role in (Qt.ItemDataRole.EditRole, ROLE_SORT):
                return sec.progress
            if role == ROLE_COLOR:
                st = self.project.status(sec.status_id)
                return st.color if st else palette.PRIMARY
        elif col == COL_RESP:
            resp = self.project.section_responsibles(sid)
            if role == Qt.ItemDataRole.DisplayRole or role == ROLE_SORT:
                return ", ".join(r.code for r in resp)
            if role == Qt.ItemDataRole.EditRole:
                return [r.id for r in resp]
            if role == ROLE_RESPONSIBLES:
                return [(r.id, r.code, r.color) for r in resp]
            if role == Qt.ItemDataRole.ToolTipRole:
                return "\n".join(r.label for r in resp)
        elif col == COL_OBS:
            if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, ROLE_SORT, Qt.ItemDataRole.ToolTipRole):
                return sec.notes or ""
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        self.editRequested.emit(self._ids[index.row()], index.column(), value)
        return True


class SectionsFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tokens: list[str] = []
        self.setSortRole(ROLE_SORT)
        self.setDynamicSortFilter(True)

    def set_query(self, text: str) -> None:
        tokens = search_key(text).split()
        if tokens != self._tokens:
            self._tokens = tokens
            self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self._tokens:
            return True
        idx = self.sourceModel().index(source_row, 0, source_parent)
        hay = idx.data(ROLE_SEARCH) or ""
        return all(t in hay for t in self._tokens)
