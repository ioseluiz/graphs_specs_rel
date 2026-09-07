"""Pestaña «Secciones»: tabla de todas las secciones del proyecto con edición en línea."""
from __future__ import annotations

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from models.sections_table_model import (
    COL_CATEGORY,
    COL_CODE,
    COL_OBS,
    COL_PROGRESS,
    COL_RESP,
    COL_STATUS,
    COL_TITLE,
    ROLE_SECTION_ID,
    SectionsFilterProxy,
    SectionsTableModel,
)
from views.components.delegates import (
    ROW_HEIGHT,
    ColoredChoiceDelegate,
    ProgressDelegate,
    ResponsiblesDelegate,
)


class SectionsTableView(QWidget):
    sectionActivated = pyqtSignal(int)       # doble clic en número: centrar en el mapa
    responsiblesRequested = pyqtSignal()
    statusesRequested = pyqtSignal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.model: SectionsTableModel | None = None
        self.proxy = SectionsFilterProxy(self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        row = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por número, descripción, responsable, estatus u observación…")
        self.search.setClearButtonEnabled(True)
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "hint")
        self.responsibles_button = QPushButton("Responsables…")
        self.responsibles_button.setProperty("role", "secondary")
        self.statuses_button = QPushButton("Estatus…")
        self.statuses_button.setProperty("role", "secondary")
        row.addWidget(self.search, 1)
        row.addWidget(self.count_label)
        row.addWidget(self.responsibles_button)
        row.addWidget(self.statuses_button)
        layout.addLayout(row)

        self.table = QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked
                                   | QAbstractItemView.EditTrigger.EditKeyPressed
                                   | QAbstractItemView.EditTrigger.SelectedClicked)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(ROW_HEIGHT - 6)
        self.table.setWordWrap(False)
        layout.addWidget(self.table, 1)
        hint = QLabel("Doble clic en una celda para editar. Doble clic en el número centra la sección en el mapa. "
                      "Los cambios se guardan automáticamente.")
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.search.textChanged.connect(self.proxy.set_query)
        self.search.textChanged.connect(lambda _t: self._update_count())
        self.table.doubleClicked.connect(self._on_double_clicked)
        self.responsibles_button.clicked.connect(self.responsiblesRequested)
        self.statuses_button.clicked.connect(self.statusesRequested)

    def set_model(self, model: SectionsTableModel, status_provider, responsible_provider, category_provider) -> None:
        self.model = model
        self.proxy.setSourceModel(model)
        self.table.setItemDelegateForColumn(COL_CATEGORY, ColoredChoiceDelegate(category_provider, self.table))
        self.table.setItemDelegateForColumn(COL_STATUS, ColoredChoiceDelegate(status_provider, self.table))
        self.table.setItemDelegateForColumn(COL_PROGRESS, ProgressDelegate(self.table))
        self.table.setItemDelegateForColumn(COL_RESP, ResponsiblesDelegate(responsible_provider, self.table))
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(COL_CODE, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(COL_TITLE, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(COL_CATEGORY, QHeaderView.ResizeMode.Interactive)
        hh.resizeSection(COL_CATEGORY, 170)
        hh.setSectionResizeMode(COL_STATUS, QHeaderView.ResizeMode.Interactive)
        hh.resizeSection(COL_STATUS, 140)
        hh.setSectionResizeMode(COL_PROGRESS, QHeaderView.ResizeMode.Interactive)
        hh.resizeSection(COL_PROGRESS, 130)
        hh.setSectionResizeMode(COL_RESP, QHeaderView.ResizeMode.Interactive)
        hh.resizeSection(COL_RESP, 150)
        hh.setSectionResizeMode(COL_OBS, QHeaderView.ResizeMode.Stretch)
        hh.setHighlightSections(False)
        self.table.sortByColumn(COL_CODE, Qt.SortOrder.AscendingOrder)
        model.rowsInserted.connect(lambda *_a: self._update_count())
        model.rowsRemoved.connect(lambda *_a: self._update_count())
        model.modelReset.connect(self._update_count)
        self._update_count()

    def _update_count(self) -> None:
        shown = self.proxy.rowCount()
        total = self.model.rowCount() if self.model else 0
        self.count_label.setText(f"{shown} de {total}" if shown != total else f"{total} secciones")

    def _on_double_clicked(self, index: QModelIndex) -> None:
        if index.column() == COL_CODE:
            sid = index.data(ROLE_SECTION_ID)
            if sid is not None:
                self.sectionActivated.emit(int(sid))

    def select_section(self, section_id: int) -> None:
        if self.model is None:
            return
        row = self.model.row_of(section_id)
        if row < 0:
            return
        idx = self.proxy.mapFromSource(self.model.index(row, 0))
        if idx.isValid():
            self.table.selectRow(idx.row())
            self.table.scrollTo(idx)
