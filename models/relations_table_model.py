"""Modelo de tabla de relaciones registradas (vista sobre ProjectModel)."""
from __future__ import annotations

from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSignal

from config import palette
from models.entities import UiKind
from models.project_model import ProjectModel
from models.relation_normalizer import denormalize

COL_NUM, COL_A, COL_KIND, COL_B, COL_ACTIONS = range(5)
HEADERS = ["N.º", "Sección A", "Relación", "Sección B", ""]

ROLE_RELATION_ID = Qt.ItemDataRole.UserRole + 1
ROLE_SECTION_ID = Qt.ItemDataRole.UserRole + 2
ROLE_CODE = Qt.ItemDataRole.UserRole + 3
ROLE_TITLE = Qt.ItemDataRole.UserRole + 4
ROLE_FILL = Qt.ItemDataRole.UserRole + 5
ROLE_BORDER = Qt.ItemDataRole.UserRole + 6
ROLE_UI_KIND = Qt.ItemDataRole.UserRole + 7
ROLE_CODE_A = Qt.ItemDataRole.UserRole + 8
ROLE_CODE_B = Qt.ItemDataRole.UserRole + 9

INVERT_OPTION = "Invertir dirección (B → A)"   # opción del combo de la celda Relación
FLASH_COLOR = "#FFF2CC"


class RelationsTableModel(QAbstractTableModel):
    # (relation_id, column, value) — el controlador aplica el cambio sobre ProjectModel
    editRequested = pyqtSignal(int, int, object)

    def __init__(self, project: ProjectModel, parent=None) -> None:
        super().__init__(parent)
        self.project = project
        self._ids: list[int] = []
        self._flashed: int | None = None
        project.projectLoaded.connect(self.reload)
        project.projectClosed.connect(self.reload)
        project.relationAdded.connect(self._on_added)
        project.relationUpdated.connect(self._on_updated)
        project.relationRemoved.connect(self._on_removed)
        project.sectionUpdated.connect(self._on_section_updated)
        project.categoriesChanged.connect(self._refresh_all)
        self.reload()

    # ------------------------------------------------------------------ orden
    def _sort_key(self, rid: int):
        rel = self.project.relation(rid)
        if rel is None:
            return ("", "", rid)
        a, _, b = denormalize(rel)
        sa, sb = self.project.section(a), self.project.section(b)
        return (sa.code_key if sa else "", sb.code_key if sb else "", rid)

    def reload(self) -> None:
        self.beginResetModel()
        self._ids = sorted((r.id for r in self.project.relations()), key=self._sort_key)
        self.endResetModel()

    def _refresh_all(self) -> None:
        if self._ids:
            self.dataChanged.emit(self.index(0, 0), self.index(len(self._ids) - 1, COL_ACTIONS))

    def _on_added(self, rid: int) -> None:
        key = self._sort_key(rid)
        row = 0
        while row < len(self._ids) and self._sort_key(self._ids[row]) < key:
            row += 1
        self.beginInsertRows(QModelIndex(), row, row)
        self._ids.insert(row, rid)
        self.endInsertRows()

    def _on_updated(self, rid: int) -> None:
        if rid not in self._ids:
            self._on_added(rid)
            return
        old_row = self._ids.index(rid)
        self._ids.pop(old_row)
        key = self._sort_key(rid)
        new_row = 0
        while new_row < len(self._ids) and self._sort_key(self._ids[new_row]) < key:
            new_row += 1
        self._ids.insert(old_row, rid)
        if new_row != old_row and new_row != old_row + 1:
            dest = new_row if new_row < old_row else new_row + 1
            self.beginMoveRows(QModelIndex(), old_row, old_row, QModelIndex(), dest)
            self._ids.pop(old_row)
            self._ids.insert(new_row if new_row < old_row else new_row, rid)
            self.endMoveRows()
        row = self._ids.index(rid)
        self.dataChanged.emit(self.index(row, 0), self.index(row, COL_ACTIONS))

    def _on_removed(self, rid: int) -> None:
        if rid not in self._ids:
            return
        row = self._ids.index(rid)
        self.beginRemoveRows(QModelIndex(), row, row)
        self._ids.pop(row)
        self.endRemoveRows()

    def _on_section_updated(self, section_id: int) -> None:
        for row, rid in enumerate(self._ids):
            rel = self.project.relation(rid)
            if rel is not None and rel.touches(section_id):
                self.dataChanged.emit(self.index(row, COL_A), self.index(row, COL_B))

    # ------------------------------------------------------------------ resaltado temporal
    def flash(self, relation_id: int, duration_ms: int = 1500) -> None:
        """Resalta la fila un instante para confirmar visualmente un cambio."""
        from PyQt6.QtCore import QTimer

        self._flashed = relation_id
        self._emit_row(relation_id)
        QTimer.singleShot(duration_ms, lambda: self._unflash(relation_id))

    def _unflash(self, relation_id: int) -> None:
        if self._flashed == relation_id:
            self._flashed = None
            self._emit_row(relation_id)

    def _emit_row(self, relation_id: int) -> None:
        row = self.row_of(relation_id)
        if row >= 0:
            self.dataChanged.emit(self.index(row, 0), self.index(row, COL_ACTIONS))

    # ------------------------------------------------------------------ acceso
    def relation_id_at(self, row: int) -> int | None:
        return self._ids[row] if 0 <= row < len(self._ids) else None

    def row_of(self, relation_id: int) -> int:
        try:
            return self._ids.index(relation_id)
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
        if index.column() in (COL_A, COL_KIND, COL_B):
            return base | Qt.ItemFlag.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        rid = self._ids[index.row()]
        rel = self.project.relation(rid)
        if rel is None:
            return None
        a_id, ui_kind, b_id = denormalize(rel)
        col = index.column()
        if role == ROLE_RELATION_ID:
            return rid
        if role in (ROLE_CODE_A, ROLE_CODE_B):
            sec = self.project.section(a_id if role == ROLE_CODE_A else b_id)
            return sec.code if sec else ""
        if role == Qt.ItemDataRole.BackgroundRole and self._flashed == rid:
            from PyQt6.QtGui import QColor
            return QColor(FLASH_COLOR)
        if col == COL_NUM:
            if role == Qt.ItemDataRole.DisplayRole:
                return str(index.row() + 1)
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignCenter)
            if role == Qt.ItemDataRole.ForegroundRole:
                from PyQt6.QtGui import QColor
                return QColor(palette.TEXT_SECONDARY)
            return None
        if col in (COL_A, COL_B):
            sid = a_id if col == COL_A else b_id
            sec = self.project.section(sid)
            if sec is None:
                return None
            fill, border = self.project.section_colors(sec)
            if role == Qt.ItemDataRole.DisplayRole:
                return f"{sec.code}\n{sec.title}" if sec.title else sec.code
            if role == Qt.ItemDataRole.EditRole:
                return sid
            if role == ROLE_SECTION_ID:
                return sid
            if role == ROLE_CODE:
                return sec.code
            if role == ROLE_TITLE:
                return sec.title
            if role == ROLE_FILL:
                return fill
            if role == ROLE_BORDER:
                return border
            if role == Qt.ItemDataRole.ToolTipRole:
                return f"{sec.code} {sec.title}".strip()
            return None
        if col == COL_KIND:
            if role == Qt.ItemDataRole.DisplayRole:
                return ui_kind.value
            if role in (Qt.ItemDataRole.EditRole, ROLE_UI_KIND):
                return ui_kind.value
            if role == Qt.ItemDataRole.TextAlignmentRole:
                return int(Qt.AlignmentFlag.AlignCenter)
            return None
        return None

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:  # noqa: N802
        if not index.isValid() or role != Qt.ItemDataRole.EditRole:
            return False
        rid = self._ids[index.row()]
        if index.column() == COL_KIND:
            if str(value) == INVERT_OPTION or str(value) == "invert":
                value = "invert"
            else:
                try:
                    value = UiKind.from_text(str(value))
                except ValueError:
                    return False
        self.editRequested.emit(rid, index.column(), value)
        return True
