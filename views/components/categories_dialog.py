"""Diálogo de categorías: nombre, color de relleno, color de borde y categoría por defecto."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from models.entities import Category


@dataclass
class CategoryEdit:
    id: int | None
    name: str
    fill: str
    border: str
    is_default: bool


class _ColorButton(QPushButton):
    def __init__(self, color: str, parent=None) -> None:
        super().__init__(parent)
        self.color = color
        self.setFixedSize(60, 26)
        self.clicked.connect(self._pick)
        self._refresh()

    def _refresh(self) -> None:
        self.setStyleSheet(
            f"QPushButton {{ background-color: {self.color}; border: 1px solid #B8C1CC; border-radius: 4px; }}")
        self.setToolTip(self.color)

    def _pick(self) -> None:
        chosen = QColorDialog.getColor(QColor(self.color), self, "Elegir color")
        if chosen.isValid():
            self.color = chosen.name().upper()
            self._refresh()


class CategoriesDialog(QDialog):
    COL_NAME, COL_FILL, COL_BORDER, COL_DEFAULT, COL_USAGE = range(5)

    def __init__(self, categories: list[Category], usage: dict[int, int], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Categorías de secciones")
        self.setMinimumSize(620, 380)
        self._usage = usage
        self._deleted: list[int] = []
        layout = QVBoxLayout(self)
        hint = QLabel("Los colores identifican visualmente el tipo de contenido de cada sección en el mapa. "
                      "La categoría por defecto se asigna a las secciones creadas automáticamente.")
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Nombre", "Relleno", "Borde", "Por defecto", "Secciones"])
        self.table.horizontalHeader().setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        for col in (self.COL_FILL, self.COL_BORDER, self.COL_DEFAULT, self.COL_USAGE):
            self.table.horizontalHeader().setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.table, 1)

        buttons_row = QHBoxLayout()
        self.add_button = QPushButton("+ Agregar categoría")
        self.add_button.setProperty("role", "secondary")
        self.remove_button = QPushButton("Eliminar seleccionada")
        self.remove_button.setProperty("role", "danger")
        buttons_row.addWidget(self.add_button)
        buttons_row.addWidget(self.remove_button)
        buttons_row.addStretch(1)
        layout.addLayout(buttons_row)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

        for cat in categories:
            self._add_row(cat.id, cat.name, cat.fill_color, cat.border_color, cat.is_default)
        self.add_button.clicked.connect(lambda: self._add_row(None, "Nueva categoría", "#EDEDED", "#8C8C8C", False))
        self.remove_button.clicked.connect(self._remove_selected)

    def _add_row(self, cat_id: int | None, name: str, fill: str, border: str, is_default: bool) -> None:
        row = self.table.rowCount()
        self.table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, cat_id)
        self.table.setItem(row, self.COL_NAME, name_item)
        self.table.setCellWidget(row, self.COL_FILL, self._centered(_ColorButton(fill)))
        self.table.setCellWidget(row, self.COL_BORDER, self._centered(_ColorButton(border)))
        radio = QRadioButton()
        radio.setChecked(is_default)
        radio.setAutoExclusive(True)
        self.table.setCellWidget(row, self.COL_DEFAULT, self._centered(radio))
        usage = QTableWidgetItem(str(self._usage.get(cat_id, 0)) if cat_id is not None else "0")
        usage.setFlags(usage.flags() & ~Qt.ItemFlag.ItemIsEditable)
        usage.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_USAGE, usage)
        self.table.setRowHeight(row, 36)

    @staticmethod
    def _centered(widget: QWidget) -> QWidget:
        wrapper = QWidget()
        lay = QHBoxLayout(wrapper)
        lay.setContentsMargins(4, 2, 4, 2)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(widget)
        wrapper.inner = widget  # type: ignore[attr-defined]
        return wrapper

    def _remove_selected(self) -> None:
        rows = sorted({i.row() for i in self.table.selectedIndexes()}, reverse=True)
        for row in rows:
            cat_id = self.table.item(row, self.COL_NAME).data(Qt.ItemDataRole.UserRole)
            count = self._usage.get(cat_id, 0) if cat_id is not None else 0
            if count:
                answer = QMessageBox.question(
                    self, "Eliminar categoría",
                    f"{count} sección(es) usan esta categoría y quedarán sin categoría. ¿Continuar?")
                if answer != QMessageBox.StandardButton.Yes:
                    continue
            if cat_id is not None:
                self._deleted.append(cat_id)
            self.table.removeRow(row)

    def _accept(self) -> None:
        names = [self.table.item(r, self.COL_NAME).text().strip() for r in range(self.table.rowCount())]
        if any(not n for n in names):
            QMessageBox.warning(self, "Categorías", "Todas las categorías deben tener nombre.")
            return
        if len({n.casefold() for n in names}) != len(names):
            QMessageBox.warning(self, "Categorías", "Hay nombres de categoría repetidos.")
            return
        self.accept()

    def result_edits(self) -> tuple[list[CategoryEdit], list[int]]:
        edits: list[CategoryEdit] = []
        any_default = False
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, self.COL_NAME)
            fill = self.table.cellWidget(row, self.COL_FILL).inner.color  # type: ignore[attr-defined]
            border = self.table.cellWidget(row, self.COL_BORDER).inner.color  # type: ignore[attr-defined]
            is_default = self.table.cellWidget(row, self.COL_DEFAULT).inner.isChecked()  # type: ignore[attr-defined]
            any_default = any_default or is_default
            edits.append(CategoryEdit(name_item.data(Qt.ItemDataRole.UserRole), name_item.text().strip(),
                                      fill, border, is_default))
        if edits and not any_default:
            edits[0].is_default = True
        return edits, list(self._deleted)
