"""Diálogo para editar el título de una entrada del catálogo o agregar una sección nueva al catálogo."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QVBoxLayout,
)

from models.master_catalog import normalize_code


class CatalogEntryDialog(QDialog):
    def __init__(self, parent=None, *, code: str = "", title_en: str = "", title_es: str = "",
                 category: str | None = None, categories: list[str] | None = None,
                 is_new: bool = False, parent_label: str | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Agregar sección al catálogo" if is_new else "Editar entrada del catálogo")
        self.setMinimumWidth(480)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Esta edición se guarda en su perfil de usuario y aplica a todos los proyectos. "
            "No modifica el catálogo incluido en la aplicación y puede revertirse."
            + (f"\nSe agregará bajo: {parent_label}" if is_new and parent_label else "")
        )
        intro.setProperty("role", "hint")
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        form.setSpacing(8)
        self.code_edit = QLineEdit(code)
        self.code_edit.setPlaceholderText("03 30 16")
        self.code_edit.setReadOnly(not is_new)
        self.title_en_edit = QLineEdit(title_en)
        self.title_en_edit.setPlaceholderText("Título (inglés o el idioma del catálogo)")
        self.title_es_edit = QLineEdit(title_es or "")
        self.title_es_edit.setPlaceholderText("Título en español (opcional; se muestra si existe)")
        form.addRow("Número:", self.code_edit)
        form.addRow("Descripción:", self.title_en_edit)
        form.addRow("Descripción ES:", self.title_es_edit)
        self.category_combo: QComboBox | None = None
        if is_new:
            self.category_combo = QComboBox()
            for name in (categories or []):
                self.category_combo.addItem(name)
            if category and self.category_combo.findText(category) >= 0:
                self.category_combo.setCurrentText(category)
            form.addRow("Clasificación:", self.category_combo)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        (self.code_edit if is_new and not code else self.title_en_edit).setFocus()

    def _accept(self) -> None:
        if not self.code_edit.text().strip():
            self.code_edit.setFocus()
            return
        if not self.title_en_edit.text().strip():
            self.title_en_edit.setFocus()
            return
        self.accept()

    def values(self) -> tuple[str, str, str | None, str | None]:
        """(código normalizado, título, título ES o None, clasificación o None)."""
        category = self.category_combo.currentText() if self.category_combo is not None else None
        return (
            normalize_code(self.code_edit.text()),
            self.title_en_edit.text().strip(),
            self.title_es_edit.text().strip() or None,
            category or None,
        )
