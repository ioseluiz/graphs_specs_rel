"""Diálogos de listas configurables del proyecto: Responsables y Estatus (CRUD con reorden)."""
from __future__ import annotations

from dataclasses import dataclass

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
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

from models.entities import Responsible, Status
from views.components.categories_dialog import _ColorButton


@dataclass
class ResponsibleEdit:
    id: int | None
    code: str
    name: str
    color: str


@dataclass
class StatusEdit:
    id: int | None
    name: str
    color: str
    is_default: bool


def _centered(widget: QWidget) -> QWidget:
    wrapper = QWidget()
    lay = QHBoxLayout(wrapper)
    lay.setContentsMargins(4, 2, 4, 2)
    lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lay.addWidget(widget)
    wrapper.inner = widget  # type: ignore[attr-defined]
    return wrapper


class _ListDialog(QDialog):
    """Base: tabla editable + agregar/eliminar/subir/bajar + validación de nombres únicos."""

    def __init__(self, title: str, hint: str, headers: list[str], usage: dict[int, int], parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(640, 400)
        self._usage = usage
        self._deleted: list[int] = []
        layout = QVBoxLayout(self)
        lbl = QLabel(hint)
        lbl.setProperty("role", "hint")
        lbl.setWordWrap(True)
        layout.addWidget(lbl)
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.table, 1)
        row = QHBoxLayout()
        self.add_button = QPushButton("+ Agregar")
        self.add_button.setProperty("role", "secondary")
        self.remove_button = QPushButton("Eliminar")
        self.remove_button.setProperty("role", "danger")
        self.up_button = QPushButton("▲ Subir")
        self.up_button.setProperty("role", "secondary")
        self.down_button = QPushButton("▼ Bajar")
        self.down_button.setProperty("role", "secondary")
        for b in (self.add_button, self.remove_button, self.up_button, self.down_button):
            row.addWidget(b)
        row.addStretch(1)
        layout.addLayout(row)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.remove_button.clicked.connect(self._remove_selected)
        self.up_button.clicked.connect(lambda: self._move(-1))
        self.down_button.clicked.connect(lambda: self._move(1))

    # ------------------------------------------------------------------ utilidades
    def _current_row(self) -> int:
        rows = {i.row() for i in self.table.selectedIndexes()}
        return min(rows) if rows else -1

    def _id_at(self, row: int) -> int | None:
        item = self.table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _remove_selected(self) -> None:
        row = self._current_row()
        if row < 0:
            return
        item_id = self._id_at(row)
        count = self._usage.get(item_id, 0) if item_id is not None else 0
        if count:
            answer = QMessageBox.question(
                self, "Eliminar", f"{count} sección(es) usan este elemento. Se les quitará. ¿Continuar?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        if item_id is not None:
            self._deleted.append(item_id)
        self.table.removeRow(row)

    def _move(self, delta: int) -> None:
        row = self._current_row()
        target = row + delta
        if row < 0 or target < 0 or target >= self.table.rowCount():
            return
        self._swap_rows(row, target)
        self.table.selectRow(target)

    def _swap_rows(self, a: int, b: int) -> None:  # implementado por las subclases (widgets por celda)
        raise NotImplementedError

    def _names(self, col: int) -> list[str]:
        return [self.table.item(r, col).text().strip() for r in range(self.table.rowCount())]

    def _validate_unique(self, col: int, what: str) -> bool:
        names = self._names(col)
        if any(not n for n in names):
            QMessageBox.warning(self, self.windowTitle(), f"Todos los elementos deben tener {what}.")
            return False
        if len({n.casefold() for n in names}) != len(names):
            QMessageBox.warning(self, self.windowTitle(), f"Hay {what}s repetidos.")
            return False
        return True

    def _accept(self) -> None:
        raise NotImplementedError


class ResponsiblesDialog(_ListDialog):
    COL_CODE, COL_NAME, COL_COLOR, COL_USAGE = range(4)

    def __init__(self, responsibles: list[Responsible], usage: dict[int, int], parent=None) -> None:
        super().__init__(
            "Responsables",
            "Unidades responsables de las secciones (no personas). El código se muestra dentro del círculo "
            "sobre cada sección; use códigos cortos (hasta 6 caracteres) para que se lean bien.",
            ["Código", "Nombre", "Color", "Secciones"], usage, parent)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_CODE, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(self.COL_COLOR, QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(self.COL_USAGE, QHeaderView.ResizeMode.ResizeToContents)
        for r in responsibles:
            self._add_row(r.id, r.code, r.name, r.color)
        self.add_button.clicked.connect(lambda: self._add_row(None, "NUEVO", "", "#8C949E"))

    def _add_row(self, rid: int | None, code: str, name: str, color: str, row: int | None = None) -> None:
        row = self.table.rowCount() if row is None else row
        self.table.insertRow(row)
        code_item = QTableWidgetItem(code)
        code_item.setData(Qt.ItemDataRole.UserRole, rid)
        self.table.setItem(row, self.COL_CODE, code_item)
        self.table.setItem(row, self.COL_NAME, QTableWidgetItem(name))
        self.table.setCellWidget(row, self.COL_COLOR, _centered(_ColorButton(color)))
        usage = QTableWidgetItem(str(self._usage.get(rid, 0)) if rid is not None else "0")
        usage.setFlags(usage.flags() & ~Qt.ItemFlag.ItemIsEditable)
        usage.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_USAGE, usage)
        self.table.setRowHeight(row, 36)

    def _row_values(self, row: int) -> tuple[int | None, str, str, str]:
        return (self._id_at(row), self.table.item(row, self.COL_CODE).text(),
                self.table.item(row, self.COL_NAME).text(),
                self.table.cellWidget(row, self.COL_COLOR).inner.color)  # type: ignore[attr-defined]

    def _swap_rows(self, a: int, b: int) -> None:
        va, vb = self._row_values(a), self._row_values(b)
        for row, (rid, code, name, color) in ((a, vb), (b, va)):
            self.table.removeRow(row)
            self._add_row(rid, code, name, color, row)

    def _accept(self) -> None:
        if self._validate_unique(self.COL_CODE, "código"):
            self.accept()

    def result_edits(self) -> tuple[list[ResponsibleEdit], list[int]]:
        edits = [ResponsibleEdit(*self._row_values(r)) for r in range(self.table.rowCount())]
        for e in edits:
            e.code, e.name, e.color = e.code.strip().upper(), e.name.strip(), e.color.upper()
        return edits, list(self._deleted)


class StatusesDialog(_ListDialog):
    COL_NAME, COL_COLOR, COL_DEFAULT, COL_USAGE = range(4)

    def __init__(self, statuses: list[Status], usage: dict[int, int], parent=None) -> None:
        super().__init__(
            "Estatus de secciones",
            "Estados de elaboración de una sección. El color del estatus colorea la barra de avance del nodo. "
            "El estatus por defecto se asigna a las secciones nuevas.",
            ["Nombre", "Color", "Por defecto", "Secciones"], usage, parent)
        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(self.COL_NAME, QHeaderView.ResizeMode.Stretch)
        for c in (self.COL_COLOR, self.COL_DEFAULT, self.COL_USAGE):
            hh.setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents)
        for s in statuses:
            self._add_row(s.id, s.name, s.color, s.is_default)
        self.add_button.clicked.connect(lambda: self._add_row(None, "Nuevo estatus", "#D9DEE5", False))

    def _add_row(self, sid: int | None, name: str, color: str, is_default: bool, row: int | None = None) -> None:
        row = self.table.rowCount() if row is None else row
        self.table.insertRow(row)
        name_item = QTableWidgetItem(name)
        name_item.setData(Qt.ItemDataRole.UserRole, sid)
        self.table.setItem(row, self.COL_NAME, name_item)
        self.table.setCellWidget(row, self.COL_COLOR, _centered(_ColorButton(color)))
        radio = QRadioButton()
        radio.setAutoExclusive(True)
        radio.setChecked(is_default)
        self.table.setCellWidget(row, self.COL_DEFAULT, _centered(radio))
        usage = QTableWidgetItem(str(self._usage.get(sid, 0)) if sid is not None else "0")
        usage.setFlags(usage.flags() & ~Qt.ItemFlag.ItemIsEditable)
        usage.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.table.setItem(row, self.COL_USAGE, usage)
        self.table.setRowHeight(row, 36)

    def _row_values(self, row: int) -> tuple[int | None, str, str, bool]:
        return (self._id_at(row), self.table.item(row, self.COL_NAME).text(),
                self.table.cellWidget(row, self.COL_COLOR).inner.color,  # type: ignore[attr-defined]
                self.table.cellWidget(row, self.COL_DEFAULT).inner.isChecked())  # type: ignore[attr-defined]

    def _swap_rows(self, a: int, b: int) -> None:
        va, vb = self._row_values(a), self._row_values(b)
        for row, (sid, name, color, default) in ((a, vb), (b, va)):
            self.table.removeRow(row)
            self._add_row(sid, name, color, default, row)

    def _accept(self) -> None:
        if self._validate_unique(self.COL_NAME, "nombre"):
            self.accept()

    def result_edits(self) -> tuple[list[StatusEdit], list[int]]:
        edits = [StatusEdit(*self._row_values(r)) for r in range(self.table.rowCount())]
        for e in edits:
            e.name, e.color = e.name.strip(), e.color.upper()
        if edits and not any(e.is_default for e in edits):
            edits[0].is_default = True
        return edits, list(self._deleted)
