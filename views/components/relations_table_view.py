"""Tabla de relaciones registradas."""
from __future__ import annotations

from PyQt6.QtCore import QItemSelection, QItemSelectionModel, Qt, pyqtSignal
from PyQt6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QTableView, QVBoxLayout, QWidget

from models.relations_table_model import (
    COL_A,
    COL_ACTIONS,
    COL_B,
    COL_KIND,
    COL_NUM,
    ROLE_RELATION_ID,
    RelationsTableModel,
)
from models.section_completer_model import SectionCompleterModel
from views.components.delegates import (
    ROW_HEIGHT,
    ActionsDelegate,
    RelationKindDelegate,
    SectionPickerDelegate,
    TwoLineSectionDelegate,
)


class RelationsTableView(QWidget):
    editRequested = pyqtSignal(int)
    invertRequested = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)
    selectionChangedIds = pyqtSignal(object)  # list[int]

    def __init__(self, table_model: RelationsTableModel, completer_model: SectionCompleterModel,
                 parent=None) -> None:
        super().__init__(parent)
        self._syncing = False
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        header = QLabel("RELACIONES REGISTRADAS")
        header.setProperty("role", "section-header")
        layout.addWidget(header)

        self.table = QTableView()
        self.table.setModel(table_model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT)
        self.table.setWordWrap(False)
        self.table.setMouseTracking(True)

        self._section_delegate = TwoLineSectionDelegate(self.table)
        self._picker_delegate = SectionPickerDelegate(completer_model, self.table)
        self._kind_delegate = RelationKindDelegate(self.table)
        self._actions_delegate = ActionsDelegate(self.table)
        self.table.setItemDelegateForColumn(COL_A, self._picker_delegate)
        self.table.setItemDelegateForColumn(COL_B, self._picker_delegate)
        self.table.setItemDelegateForColumn(COL_KIND, self._kind_delegate)
        self.table.setItemDelegateForColumn(COL_ACTIONS, self._actions_delegate)
        # El delegado de pintura de dos líneas se aplica dentro del delegado de edición:
        self._picker_delegate.paint = self._section_delegate.paint  # type: ignore[method-assign]
        self._picker_delegate.sizeHint = self._section_delegate.sizeHint  # type: ignore[method-assign]

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_NUM, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(COL_NUM, 44)
        hh.setSectionResizeMode(COL_A, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_KIND, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_B, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_ACTIONS, QHeaderView.ResizeMode.Fixed)
        hh.resizeSection(COL_ACTIONS, 90)
        self.table.setMouseTracking(True)
        self.table.clicked.connect(self._on_clicked)
        hh.setHighlightSections(False)
        layout.addWidget(self.table, 1)

        self.empty_label = QLabel("Aún no hay relaciones registradas. Use la entrada superior o el modo "
                                  "«Conectar» del mapa.")
        self.empty_label.setProperty("role", "hint")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setWordWrap(True)
        layout.addWidget(self.empty_label)

        self._actions_delegate.editRequested.connect(self.editRequested)
        self._actions_delegate.invertRequested.connect(self.invertRequested)
        self._actions_delegate.deleteRequested.connect(self.deleteRequested)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        table_model.rowsInserted.connect(self._update_empty)
        table_model.rowsRemoved.connect(self._update_empty)
        table_model.modelReset.connect(self._update_empty)
        self._update_empty()

    def _on_clicked(self, index) -> None:
        """Un solo clic en la celda «Relación» abre el combo (no hace falta doble clic)."""
        if index.column() == COL_KIND:
            self.table.edit(index)

    def flash_relation(self, relation_id: int) -> None:
        model: RelationsTableModel = self.table.model()  # type: ignore[assignment]
        self.select_relations([relation_id])
        model.flash(relation_id)

    def _update_empty(self, *_args) -> None:
        empty = self.table.model().rowCount() == 0
        self.empty_label.setVisible(empty)

    def _on_selection_changed(self, _sel: QItemSelection, _desel: QItemSelection) -> None:
        if self._syncing:
            return
        self.selectionChangedIds.emit(self.selected_relation_ids())

    def selected_relation_ids(self) -> list[int]:
        ids: list[int] = []
        for idx in self.table.selectionModel().selectedRows():
            rid = idx.data(ROLE_RELATION_ID)
            if rid is not None:
                ids.append(int(rid))
        return ids

    def select_relations(self, relation_ids: list[int], scroll: bool = True) -> None:
        model: RelationsTableModel = self.table.model()  # type: ignore[assignment]
        self._syncing = True
        try:
            sel_model = self.table.selectionModel()
            sel_model.clearSelection()
            first = None
            for rid in relation_ids:
                row = model.row_of(rid)
                if row < 0:
                    continue
                idx = model.index(row, 0)
                sel_model.select(idx, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
                first = idx if first is None else first
            if scroll and first is not None:
                self.table.scrollTo(first)
        finally:
            self._syncing = False

    def edit_relation(self, relation_id: int) -> None:
        model: RelationsTableModel = self.table.model()  # type: ignore[assignment]
        row = model.row_of(relation_id)
        if row >= 0:
            idx = model.index(row, COL_A)
            self.table.setCurrentIndex(idx)
            self.table.edit(idx)
