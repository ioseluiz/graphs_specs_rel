"""Encabezado 'Proyecto: CC-XX-XX | Nombre del proyecto' con edición inline."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QPushButton, QWidget


class ProjectHeader(QWidget):
    metaEdited = pyqtSignal(str, str)  # code, name

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        self.prefix = QLabel("Proyecto:")
        self.prefix.setProperty("role", "subtitle")
        self.title = QLabel("—")
        self.title.setProperty("role", "title")
        self.title.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("CC-XX-XX")
        self.code_edit.setMaximumWidth(140)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Nombre del proyecto")
        self.edit_button = QPushButton("Editar")
        self.edit_button.setProperty("role", "secondary")
        self.save_button = QPushButton("Guardar")
        self.cancel_button = QPushButton("Cancelar")
        self.cancel_button.setProperty("role", "secondary")
        for w in (self.prefix, self.title, self.code_edit, self.name_edit):
            layout.addWidget(w)
        layout.addStretch(1)
        for w in (self.edit_button, self.save_button, self.cancel_button):
            layout.addWidget(w)
        self._code, self._name = "", ""
        self.edit_button.clicked.connect(lambda: self.set_editing(True))
        self.cancel_button.clicked.connect(lambda: self.set_editing(False))
        self.save_button.clicked.connect(self._save)
        self.name_edit.returnPressed.connect(self._save)
        self.code_edit.returnPressed.connect(self._save)
        self.title.mouseDoubleClickEvent = lambda _e: self.set_editing(True)  # type: ignore[method-assign]
        self.set_editing(False)

    def set_meta(self, code: str, name: str) -> None:
        self._code, self._name = code, name
        parts = [p for p in (code.strip(), name.strip()) if p]
        self.title.setText(" | ".join(parts) if parts else "Proyecto sin nombre (doble clic para editar)")

    def set_editing(self, editing: bool) -> None:
        self.title.setVisible(not editing)
        self.edit_button.setVisible(not editing)
        for w in (self.code_edit, self.name_edit, self.save_button, self.cancel_button):
            w.setVisible(editing)
        if editing:
            self.code_edit.setText(self._code)
            self.name_edit.setText(self._name)
            self.code_edit.setFocus()
            self.code_edit.selectAll()

    def _save(self) -> None:
        self.metaEdited.emit(self.code_edit.text().strip(), self.name_edit.text().strip())
        self.set_editing(False)
