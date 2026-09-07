"""Importación de catálogo de secciones: archivo, mapeo de columnas y vista previa."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from models.catalog_importer import CatalogImportError, ColumnMapping, TablePreview, preview_for

NONE_LABEL = "(ninguna)"


class ImportCatalogDialog(QDialog):
    def __init__(self, parent=None, initial: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importar catálogo de secciones")
        self.setMinimumSize(680, 460)
        self._preview: TablePreview | None = None
        layout = QVBoxLayout(self)
        hint = QLabel("El catálogo alimenta el autocompletado. Acepta CSV, XLSX o la base "
                      "SQLite MasterFormat (tabla master_format). Las secciones se crean solo cuando se usan.")
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        file_row = QHBoxLayout()
        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        browse = QPushButton("Examinar…")
        browse.setProperty("role", "secondary")
        browse.clicked.connect(self._browse)
        file_row.addWidget(self.path_edit, 1)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        form = QFormLayout()
        self.code_combo = QComboBox()
        self.title_combo = QComboBox()
        self.category_combo = QComboBox()
        self.level_spin = QSpinBox()
        self.level_spin.setRange(1, 4)
        self.level_spin.setValue(3)
        self.level_spin.setToolTip("Solo para master_format.db: nivel máximo de sección a importar")
        form.addRow("Columna de número:", self.code_combo)
        form.addRow("Columna de descripción:", self.title_combo)
        form.addRow("Columna de categoría:", self.category_combo)
        form.addRow("Nivel máximo (SQLite):", self.level_spin)
        layout.addLayout(form)

        self.preview_table = QTableWidget(0, 0)
        self.preview_table.verticalHeader().setVisible(False)
        layout.addWidget(self.preview_table, 1)

        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.ok_button = box.button(QDialogButtonBox.StandardButton.Ok)
        self.ok_button.setText("Importar")
        self.ok_button.setEnabled(False)
        box.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        if initial is not None:
            self._load(initial)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Seleccionar catálogo", "",
            "Catálogos (*.csv *.xlsx *.xlsm *.db *.sqlite *.sqlite3);;Todos los archivos (*)")
        if path:
            self._load(Path(path))

    def _load(self, path: Path) -> None:
        self.path_edit.setText(str(path))
        self._preview = None
        self.preview_table.clear()
        self.preview_table.setRowCount(0)
        self.preview_table.setColumnCount(0)
        is_sqlite = path.suffix.lower() in (".db", ".sqlite", ".sqlite3")
        for combo in (self.code_combo, self.title_combo, self.category_combo):
            combo.clear()
            combo.setEnabled(not is_sqlite)
        self.level_spin.setEnabled(is_sqlite)
        if is_sqlite:
            self.ok_button.setEnabled(True)
            return
        try:
            preview = preview_for(path)
        except CatalogImportError as exc:
            QMessageBox.warning(self, "Importar catálogo", str(exc))
            self.ok_button.setEnabled(False)
            return
        self._preview = preview
        for combo in (self.code_combo, self.title_combo):
            combo.addItems(preview.headers)
        self.category_combo.addItem(NONE_LABEL)
        self.category_combo.addItems(preview.headers)
        if preview.suggested:
            self.code_combo.setCurrentText(preview.suggested.code)
            self.title_combo.setCurrentText(preview.suggested.title)
            if preview.suggested.category:
                self.category_combo.setCurrentText(preview.suggested.category)
        self.preview_table.setColumnCount(len(preview.headers))
        self.preview_table.setHorizontalHeaderLabels(preview.headers)
        self.preview_table.setRowCount(len(preview.rows))
        for r, row in enumerate(preview.rows):
            for c, value in enumerate(row[: len(preview.headers)]):
                self.preview_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.preview_table.resizeColumnsToContents()
        self.ok_button.setEnabled(True)

    def result(self) -> tuple[Path, ColumnMapping | None, int]:
        path = Path(self.path_edit.text())
        mapping = None
        if self._preview is not None:
            category = self.category_combo.currentText()
            mapping = ColumnMapping(
                self.code_combo.currentText(), self.title_combo.currentText(),
                None if category == NONE_LABEL else category)
        return path, mapping, self.level_spin.value()
