"""Diálogo para crear/editar una sección (código, título, categoría, color, notas)."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from models.entities import Category
from views.components.categories_dialog import _ColorButton


def _derive_border(fill_hex: str) -> str:
    h = fill_hex.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "#{:02X}{:02X}{:02X}".format(int(r * 0.62), int(g * 0.62), int(b * 0.62))


class SectionEditorDialog(QDialog):
    def __init__(self, categories: list[Category], parent=None, *, code: str = "", title: str = "",
                 category_id: int | None = None, notes: str | None = None, is_new: bool = False,
                 fill_color: str | None = None, border_color: str | None = None,
                 suggestion: tuple[str, str] | None = None,
                 statuses: list | None = None, responsibles: list | None = None,
                 status_id: int | None = None, progress: int = 0,
                 responsible_ids: list[int] | None = None, kind: str = "section") -> None:
        super().__init__(parent)
        self.kind = kind
        self.setWindowTitle("Nueva sección personalizada" if is_new
                            else ("Editar cláusula" if kind == "clause" else "Editar sección"))
        self.setMinimumWidth(480)
        self._categories = {c.id: c for c in categories}
        self._statuses = list(statuses or [])
        self._responsibles = list(responsibles or [])
        layout = QVBoxLayout(self)
        if is_new:
            intro = QLabel("Use este cuadro para códigos que no están en el catálogo MasterFormat ni en las "
                           "cláusulas del pliego. Las secciones y cláusulas del catálogo se eligen desde la lista.")
            intro.setProperty("role", "hint")
            intro.setWordWrap(True)
            layout.addWidget(intro)
        self.suggestion_button: QPushButton | None = None
        if suggestion is not None:
            sug_code, sug_title = suggestion
            row = QHBoxLayout()
            label = QLabel(f"¿Quiso decir <b>{sug_code} - {sug_title}</b> del catálogo?")
            label.setWordWrap(True)
            self.suggestion_button = QPushButton("Usar sugerencia")
            self.suggestion_button.setProperty("role", "secondary")
            self.suggestion_button.clicked.connect(lambda: self._apply_suggestion(sug_code, sug_title))
            row.addWidget(label, 1)
            row.addWidget(self.suggestion_button)
            layout.addLayout(row)
        form = QFormLayout()
        form.setSpacing(8)
        self.code_edit = QLineEdit(code)
        self.code_edit.setPlaceholderText("31 23 00")
        self.title_edit = QLineEdit(title)
        self.title_edit.setPlaceholderText("Excavación")
        self.category_combo = QComboBox()
        for cat in categories:
            pix = QPixmap(14, 14)
            pix.fill(QColor(cat.fill_color))
            self.category_combo.addItem(QIcon(pix), cat.name, cat.id)
        self.category_combo.addItem("Sin categoría", None)
        if category_id is not None:
            idx = self.category_combo.findData(category_id)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)

        # Color: por defecto el de la categoría; opcionalmente personalizado.
        color_row = QWidget()
        cl = QHBoxLayout(color_row)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(8)
        self.custom_color_check = QCheckBox("Personalizar")
        self.custom_color_check.setChecked(bool(fill_color))
        self.fill_button = _ColorButton(fill_color or self._category_fill())
        self.border_button = _ColorButton(border_color or _derive_border(fill_color or self._category_fill()))
        self.fill_label = QLabel("Relleno")
        self.border_label = QLabel("Borde")
        for w in (self.fill_label, self.border_label):
            w.setProperty("role", "hint")
        cl.addWidget(self.custom_color_check)
        cl.addWidget(self.fill_label)
        cl.addWidget(self.fill_button)
        cl.addWidget(self.border_label)
        cl.addWidget(self.border_button)
        cl.addStretch(1)

        # Estatus, avance y responsables
        self.status_combo = QComboBox()
        self.status_combo.addItem("Sin estatus", None)
        for st in self._statuses:
            pix = QPixmap(14, 14)
            pix.fill(QColor(st.color))
            self.status_combo.addItem(QIcon(pix), st.name, st.id)
        if status_id is not None and self.status_combo.findData(status_id) >= 0:
            self.status_combo.setCurrentIndex(self.status_combo.findData(status_id))
        elif is_new:
            default = next((s for s in self._statuses if getattr(s, "is_default", False)), None)
            if default is not None:
                self.status_combo.setCurrentIndex(self.status_combo.findData(default.id))
        progress_row = QWidget()
        pl = QHBoxLayout(progress_row)
        pl.setContentsMargins(0, 0, 0, 0)
        self.progress_slider = QSlider(Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 100)
        self.progress_slider.setSingleStep(5)
        self.progress_slider.setPageStep(25)
        self.progress_spin = QSpinBox()
        self.progress_spin.setRange(0, 100)
        self.progress_spin.setSingleStep(5)
        self.progress_spin.setSuffix(" %")
        self.progress_spin.setFixedWidth(80)
        self.progress_slider.setValue(int(progress or 0))
        self.progress_spin.setValue(int(progress or 0))
        self.progress_slider.valueChanged.connect(self.progress_spin.setValue)
        self.progress_spin.valueChanged.connect(self.progress_slider.setValue)
        pl.addWidget(self.progress_slider, 1)
        pl.addWidget(self.progress_spin)
        self.responsibles_list = QListWidget()
        self.responsibles_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        selected = set(responsible_ids or [])
        for r in self._responsibles:
            pix = QPixmap(14, 14)
            pix.fill(QColor(r.color))
            item = QListWidgetItem(QIcon(pix), r.label)
            item.setData(Qt.ItemDataRole.UserRole, r.id)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if r.id in selected else Qt.CheckState.Unchecked)
            self.responsibles_list.addItem(item)
        self.responsibles_list.setMaximumHeight(max(48, min(6, len(self._responsibles)) * 24 + 8))
        if not self._responsibles:
            self.responsibles_list.addItem("(defina responsables en Edición → Responsables…)")
            self.responsibles_list.setEnabled(False)

        self.notes_edit = QPlainTextEdit(notes or "")
        self.notes_edit.setPlaceholderText("Observaciones (opcional)")
        self.notes_edit.setMaximumHeight(80)
        form.addRow("Número:", self.code_edit)
        form.addRow("Descripción:", self.title_edit)
        if kind == "clause":
            # Una cláusula tiene categoría fija y no lleva estatus, avance ni responsables.
            hint = QLabel("Las cláusulas del pliego solo se conectan y muestran su etiqueta; "
                          "no tienen estatus, avance ni responsables.")
            hint.setProperty("role", "hint")
            hint.setWordWrap(True)
            form.addRow("", hint)
            form.addRow("Color:", color_row)
            for w in (self.category_combo, self.status_combo, self.progress_spin, self.responsibles_list):
                w.hide()
        else:
            form.addRow("Categoría:", self.category_combo)
            form.addRow("Color:", color_row)
            form.addRow("Estatus:", self.status_combo)
            form.addRow("Avance:", progress_row)
            form.addRow("Responsables:", self.responsibles_list)
        form.addRow("Observaciones:", self.notes_edit)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Guardar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.custom_color_check.toggled.connect(self._update_color_state)
        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        self.fill_button.clicked.connect(self._sync_border_from_fill)
        self._update_color_state()
        (self.title_edit if code else self.code_edit).setFocus()

    # ------------------------------------------------------------------ color
    def _category_fill(self) -> str:
        cat = self._categories.get(self.category_combo.currentData()) if hasattr(self, "category_combo") else None
        return cat.fill_color if cat else "#EDEDED"

    def _update_color_state(self) -> None:
        custom = self.custom_color_check.isChecked()
        for w in (self.fill_button, self.border_button, self.fill_label, self.border_label):
            w.setEnabled(custom)
        if not custom:
            self._show_category_colors()

    def _show_category_colors(self) -> None:
        cat = self._categories.get(self.category_combo.currentData())
        if cat is not None:
            self.fill_button.color, self.border_button.color = cat.fill_color, cat.border_color
            self.fill_button._refresh()
            self.border_button._refresh()

    def _on_category_changed(self, _index: int) -> None:
        if not self.custom_color_check.isChecked():
            self._show_category_colors()

    def _sync_border_from_fill(self) -> None:
        # Tras elegir un relleno, proponer un borde acorde (el usuario puede cambiarlo después).
        self.border_button.color = _derive_border(self.fill_button.color)
        self.border_button._refresh()

    def _apply_suggestion(self, code: str, title: str) -> None:
        self.code_edit.setText(code)
        if not self.title_edit.text().strip():
            self.title_edit.setText(title)
        self.title_edit.setFocus()

    # ------------------------------------------------------------------ resultado
    def _accept(self) -> None:
        if not self.code_edit.text().strip():
            self.code_edit.setFocus()
            return
        self.accept()

    def values(self) -> tuple[str, str, int | None, str | None]:
        notes = self.notes_edit.toPlainText().strip() or None
        return (
            " ".join(self.code_edit.text().split()),
            self.title_edit.text().strip(),
            self.category_combo.currentData(),
            notes,
        )

    def colors(self) -> tuple[str | None, str | None]:
        """(relleno, borde) personalizados, o (None, None) para usar el color de la categoría."""
        if not self.custom_color_check.isChecked():
            return None, None
        return self.fill_button.color.upper(), self.border_button.color.upper()

    def extras(self) -> tuple[int | None, int, list[int]]:
        """(status_id, avance %, ids de responsables marcados). Una cláusula devuelve (None, 0, [])."""
        if self.kind == "clause":
            return None, 0, []
        ids: list[int] = []
        if self.responsibles_list.isEnabled():
            for i in range(self.responsibles_list.count()):
                item = self.responsibles_list.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    ids.append(int(item.data(Qt.ItemDataRole.UserRole)))
        return self.status_combo.currentData(), int(self.progress_spin.value()), ids
