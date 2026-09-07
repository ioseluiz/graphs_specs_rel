"""Panel de análisis: huérfanas, hubs, impacto e islas (solo widgets, sin lógica de grafo)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class AnalysisPanel(QWidget):
    centerOnSection = pyqtSignal(int)
    highlightRequested = pyqtSignal(int)
    clearHighlightRequested = pyqtSignal()
    impactSectionChanged = pyqtSignal(object)  # section_id | None

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(8, 8, 8, 8)

        # Métricas
        metrics = QHBoxLayout()
        self.metric_sections = self._metric("Secciones")
        self.metric_relations = self._metric("Relaciones")
        self.metric_orphans = self._metric("Huérfanas")
        self.metric_components = self._metric("Grupos aislados")
        self.metric_progress = self._metric("Avance promedio")
        for m in (self.metric_sections, self.metric_relations, self.metric_orphans, self.metric_components,
                  self.metric_progress):
            metrics.addWidget(m[0])
        outer.addLayout(metrics)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter, 1)

        # Columna izquierda: huérfanas + hubs
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        orphans_box = QGroupBox("Secciones huérfanas (sin relaciones)")
        ob = QVBoxLayout(orphans_box)
        self.orphans_list = QListWidget()
        self.orphans_list.setToolTip("Doble clic para centrar en el mapa")
        ob.addWidget(self.orphans_list)
        left_layout.addWidget(orphans_box, 1)

        hubs_box = QGroupBox("Secciones con mayor interacción")
        hb = QVBoxLayout(hubs_box)
        self.hubs_table = QTableWidget(0, 4)
        self.hubs_table.setHorizontalHeaderLabels(["Sección", "Ref. a →", "← Ref. por", "Total"])
        self.hubs_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            self.hubs_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.hubs_table.horizontalHeader().resizeSection(c, 78)
        self.hubs_table.horizontalHeader().setToolTip(
            "Ref. a →: a cuántas secciones hace referencia · ← Ref. por: por cuántas es referenciada")
        self.hubs_table.verticalHeader().setVisible(False)
        self.hubs_table.setSortingEnabled(True)
        self.hubs_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.hubs_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        hb.addWidget(self.hubs_table)
        left_layout.addWidget(hubs_box, 2)
        splitter.addWidget(left)

        # Columna derecha: impacto + islas
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        impact_box = QGroupBox("Análisis de impacto")
        ib = QVBoxLayout(impact_box)
        row = QHBoxLayout()
        row.addWidget(QLabel("Sección:"))
        self.impact_combo = QComboBox()
        self.impact_combo.setMinimumWidth(160)
        self.impact_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        row.addWidget(self.impact_combo, 1)
        self.highlight_button = QPushButton("Resaltar en mapa")
        self.clear_button = QPushButton("Quitar resaltado")
        self.clear_button.setProperty("role", "secondary")
        row.addWidget(self.highlight_button)
        row.addWidget(self.clear_button)
        ib.addLayout(row)
        grid = QGridLayout()
        self.affected_label = QLabel("Se ven afectadas si esta sección cambia (la referencian):")
        self.affected_label.setProperty("role", "hint")
        self.affected_label.setWordWrap(True)
        self.depends_label = QLabel("Esta sección depende de (hace referencia a):")
        self.depends_label.setProperty("role", "hint")
        self.depends_label.setWordWrap(True)
        self.affected_list = QListWidget()
        self.depends_list = QListWidget()
        grid.addWidget(self.affected_label, 0, 0)
        grid.addWidget(self.depends_label, 0, 1)
        grid.addWidget(self.affected_list, 1, 0)
        grid.addWidget(self.depends_list, 1, 1)
        ib.addLayout(grid)
        right_layout.addWidget(impact_box, 2)

        comps_box = QGroupBox("Grupos aislados (componentes)")
        cb = QVBoxLayout(comps_box)
        self.components_list = QListWidget()
        self.components_list.setWordWrap(True)
        self.components_list.setTextElideMode(Qt.TextElideMode.ElideNone)
        cb.addWidget(self.components_list)
        right_layout.addWidget(comps_box, 1)

        resp_box = QGroupBox("Avance por responsable")
        rb = QVBoxLayout(resp_box)
        self.responsibles_table = QTableWidget(0, 4)
        self.responsibles_table.setHorizontalHeaderLabels(["Responsable", "Secciones", "Avance %", "Al 100 %"])
        self.responsibles_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for c in (1, 2, 3):
            self.responsibles_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.Fixed)
            self.responsibles_table.horizontalHeader().resizeSection(c, 84)
        self.responsibles_table.verticalHeader().setVisible(False)
        self.responsibles_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.responsibles_table.setSortingEnabled(True)
        rb.addWidget(self.responsibles_table)
        right_layout.addWidget(resp_box, 1)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([480, 480])

        # Señales
        self.orphans_list.itemDoubleClicked.connect(self._emit_center)
        self.affected_list.itemDoubleClicked.connect(self._emit_center)
        self.depends_list.itemDoubleClicked.connect(self._emit_center)
        self.hubs_table.itemDoubleClicked.connect(self._hub_double_clicked)
        self.highlight_button.clicked.connect(self._emit_highlight)
        self.clear_button.clicked.connect(self.clearHighlightRequested)
        self.impact_combo.currentIndexChanged.connect(
            lambda _i: self.impactSectionChanged.emit(self.impact_combo.currentData()))

    @staticmethod
    def _metric(title: str) -> tuple[QWidget, QLabel]:
        card = QWidget()
        card.setProperty("role", "card")
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 8, 12, 8)
        value = QLabel("0")
        value.setProperty("role", "metric")
        value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label = QLabel(title)
        label.setProperty("role", "hint")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(value)
        lay.addWidget(label)
        return card, value

    # ------------------------------------------------------------------ carga de datos
    def set_metrics(self, sections: int, relations: int, orphans: int, components: int,
                    avg_progress: float | None = None) -> None:
        self.metric_sections[1].setText(str(sections))
        self.metric_relations[1].setText(str(relations))
        self.metric_orphans[1].setText(str(orphans))
        self.metric_components[1].setText(str(components))
        self.metric_progress[1].setText("—" if avg_progress is None else f"{avg_progress:.0f} %")

    def set_responsible_progress(self, rows: list[tuple[str, str, int, float, int]]) -> None:
        """rows: (código, color, secciones, promedio %, completadas)."""
        from PyQt6.QtGui import QColor, QIcon, QPixmap

        self.responsibles_table.setSortingEnabled(False)
        self.responsibles_table.setRowCount(len(rows))
        for r, (code, color, count, avg, done) in enumerate(rows):
            pix = QPixmap(14, 14)
            pix.fill(QColor(color))
            self.responsibles_table.setItem(r, 0, QTableWidgetItem(QIcon(pix), code))
            for c, value in enumerate((count, round(avg), done), start=1):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.responsibles_table.setItem(r, c, item)
        self.responsibles_table.setSortingEnabled(True)

    def set_orphans(self, items: list[tuple[int, str]]) -> None:
        self.orphans_list.clear()
        for sid, label in items:
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, sid)
            self.orphans_list.addItem(item)

    def set_hubs(self, rows: list[tuple[int, str, int, int, int]]) -> None:
        self.hubs_table.setSortingEnabled(False)
        self.hubs_table.setRowCount(len(rows))
        for r, (sid, label, out_d, in_d, total) in enumerate(rows):
            name = QTableWidgetItem(label)
            name.setData(Qt.ItemDataRole.UserRole, sid)
            self.hubs_table.setItem(r, 0, name)
            for c, v in enumerate((out_d, in_d, total), start=1):
                item = QTableWidgetItem()
                item.setData(Qt.ItemDataRole.DisplayRole, v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.hubs_table.setItem(r, c, item)
        self.hubs_table.setSortingEnabled(True)
        self.hubs_table.sortItems(3, Qt.SortOrder.DescendingOrder)

    def set_sections(self, items: list[tuple[int, str]]) -> None:
        current = self.impact_combo.currentData()
        self.impact_combo.blockSignals(True)
        self.impact_combo.clear()
        self.impact_combo.addItem("— seleccione —", None)
        for sid, label in items:
            self.impact_combo.addItem(label, sid)
        idx = self.impact_combo.findData(current) if current is not None else 0
        self.impact_combo.setCurrentIndex(max(0, idx))
        self.impact_combo.blockSignals(False)

    def select_section(self, section_id: int) -> None:
        idx = self.impact_combo.findData(section_id)
        if idx >= 0:
            self.impact_combo.setCurrentIndex(idx)

    def set_impact(self, affected: list[tuple[int, str, int]], depends: list[tuple[int, str, int]]) -> None:
        for widget, rows in ((self.affected_list, affected), (self.depends_list, depends)):
            widget.clear()
            for sid, label, level in rows:
                item = QListWidgetItem(f"Nivel {level} · {label}")
                item.setData(Qt.ItemDataRole.UserRole, sid)
                widget.addItem(item)
        self.affected_label.setText(
            f"Se ven afectadas si esta sección cambia ({len(affected)}):")
        self.depends_label.setText(f"Esta sección depende de ({len(depends)}):")

    def set_components(self, groups: list[list[str]]) -> None:
        self.components_list.clear()
        for i, labels in enumerate(groups, start=1):
            preview = ", ".join(labels[:6]) + (" …" if len(labels) > 6 else "")
            item = QListWidgetItem(f"Grupo {i} · {len(labels)} sección(es): {preview}")
            item.setToolTip("\n".join(labels))
            self.components_list.addItem(item)

    # ------------------------------------------------------------------ slots
    def _emit_center(self, item: QListWidgetItem) -> None:
        sid = item.data(Qt.ItemDataRole.UserRole)
        if sid is not None:
            self.centerOnSection.emit(int(sid))

    def _hub_double_clicked(self, item: QTableWidgetItem) -> None:
        name = self.hubs_table.item(item.row(), 0)
        sid = name.data(Qt.ItemDataRole.UserRole) if name else None
        if sid is not None:
            self.select_section(int(sid))
            self.centerOnSection.emit(int(sid))

    def _emit_highlight(self) -> None:
        sid = self.impact_combo.currentData()
        if sid is not None:
            self.highlightRequested.emit(int(sid))
