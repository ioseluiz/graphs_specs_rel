"""Diálogo del reporte de secciones en Excel: ruta de salida y opciones."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)


class ReportDialog(QDialog):
    def __init__(self, suggested: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Reporte de secciones (Excel)")
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        intro = QLabel("Genera un libro de Excel con las hojas <b>Resumen</b> (indicadores, por estatus, por "
                       "responsable, por categoría), <b>Secciones</b> (estatus, avance, responsables, "
                       "observaciones), <b>Por responsable</b> (una fila por sección y responsable) y "
                       "<b>Relaciones</b>.")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        row = QHBoxLayout()
        self.path_edit = QLineEdit(str(suggested))
        browse = QPushButton("Examinar…")
        browse.setProperty("role", "secondary")
        browse.clicked.connect(self._browse)
        row.addWidget(QLabel("Guardar en:"))
        row.addWidget(self.path_edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)
        self.include_map = QCheckBox("Incluir una hoja «Mapa» con la imagen actual del mapa 2D")
        self.include_map.setChecked(True)
        self.open_after = QCheckBox("Abrir el archivo al terminar")
        self.open_after.setChecked(True)
        layout.addWidget(self.include_map)
        layout.addWidget(self.open_after)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Generar reporte")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        path, _ = QFileDialog.getSaveFileName(self, "Guardar reporte", self.path_edit.text(),
                                              "Libro de Excel (*.xlsx)")
        if path:
            self.path_edit.setText(path)

    def _accept(self) -> None:
        if not self.path_edit.text().strip():
            self.path_edit.setFocus()
            return
        self.accept()

    def result(self) -> tuple[Path, bool, bool]:
        p = Path(self.path_edit.text().strip())
        if p.suffix.lower() != ".xlsx":
            p = p.with_suffix(".xlsx")
        return p, self.include_map.isChecked(), self.open_after.isChecked()
