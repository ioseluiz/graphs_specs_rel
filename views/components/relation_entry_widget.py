"""Entrada de relaciones: Sección A | Tipo de relación | Sección B | Agregar (+ sección personalizada)."""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from models.entities import UiKind
from models.section_completer_model import SectionCompleterModel
from views.components.section_picker import PickerValue, SectionPicker


class RelationEntryWidget(QWidget):
    addRequested = pyqtSignal(object, object, object)   # a_value, UiKind, b_value (valores del picker)
    customSectionRequested = pyqtSignal(str, str)       # 'a'|'b', texto tipeado

    def __init__(self, completer_model: SectionCompleterModel, parent=None) -> None:
        super().__init__(parent)
        self._last_focused = "a"
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        header = QLabel("ENTRADA DE RELACIONES")
        header.setProperty("role", "section-header")
        layout.addWidget(header)

        grid = QGridLayout()
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(4)
        for col, text in enumerate(("SECCIÓN A", "TIPO DE RELACIÓN / CONEXIÓN", "SECCIÓN B", "")):
            lbl = QLabel(text)
            lbl.setProperty("role", "hint")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            grid.addWidget(lbl, 0, col)

        self.picker_a = SectionPicker(completer_model)
        self.kind_combo = QComboBox()
        for kind in UiKind:
            self.kind_combo.addItem(kind.value)
        self.kind_combo.setToolTip(
            "La relación define el sentido, sin importar el orden en que se seleccionen las secciones.\n"
            "• Hace referencia a →  : A → B\n"
            "• ← Es referenciada por : B → A\n"
            "Si ambas se referencian entre sí, registre las dos direcciones: serán dos flechas."
        )
        self.picker_b = SectionPicker(completer_model)
        self.add_button = QPushButton("+ Agregar")
        self.add_button.setDefault(True)
        self.add_button.setToolTip("Enter crea una nueva línea")

        grid.addWidget(self.picker_a, 1, 0)
        grid.addWidget(self.kind_combo, 1, 1)
        grid.addWidget(self.picker_b, 1, 2)
        grid.addWidget(self.add_button, 1, 3)
        grid.setColumnStretch(0, 5)
        grid.setColumnStretch(1, 4)
        grid.setColumnStretch(2, 5)
        layout.addLayout(grid)

        row = QHBoxLayout()
        self.hint = QLabel(
            "Escriba para filtrar la lista MasterFormat y elija una sección. Para códigos que no están en "
            "el catálogo use «Sección personalizada…»."
        )
        self.hint.setProperty("role", "hint")
        self.hint.setWordWrap(True)
        self.custom_button = QPushButton("Sección personalizada…")
        self.custom_button.setProperty("role", "secondary")
        self.custom_button.setToolTip("Crear una sección con un número que no está en el catálogo MasterFormat "
                                      "(las cláusulas 4.28.x sí están: elíjalas de la lista)")
        row.addWidget(self.hint, 1)
        row.addWidget(self.custom_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(row)

        self.add_button.clicked.connect(self._emit_add)
        self.custom_button.clicked.connect(self._emit_custom)
        self.picker_a.submitted.connect(self._on_a_submitted)
        self.picker_b.submitted.connect(self._emit_add)
        self.picker_a.entryActivated.connect(lambda: self.kind_combo.setFocus())
        self.picker_b.entryActivated.connect(self._emit_add)
        self.picker_a.noMatch.connect(lambda text: self._on_no_match("a", text))
        self.picker_b.noMatch.connect(lambda text: self._on_no_match("b", text))
        self.picker_a.installEventFilter(self)
        self.picker_b.installEventFilter(self)

    # ------------------------------------------------------------------ API
    def current_kind(self) -> UiKind:
        return UiKind.from_text(self.kind_combo.currentText())

    def focused_picker(self) -> str:
        return self._last_focused

    def picker(self, which: str) -> SectionPicker:
        return self.picker_a if which == "a" else self.picker_b

    def set_picker_section(self, which: str, section_id: int, label: str) -> None:
        self.picker(which).set_section(section_id, label)
        (self.kind_combo if which == "a" else self.add_button).setFocus()

    def set_hint(self, text: str, warning: bool = False) -> None:
        self.hint.setText(text)
        self.hint.setStyleSheet("color: #BF9000; font-weight: 600;" if warning else "")

    def clear_inputs(self) -> None:
        self.picker_a.clear_value()
        self.picker_b.clear_value()
        self.set_hint("Escriba para filtrar la lista MasterFormat y elija una sección. Para códigos que no "
                      "están en el catálogo use «Sección personalizada…».")
        self.picker_a.setFocus()

    def set_enabled_all(self, enabled: bool) -> None:
        for w in (self.picker_a, self.kind_combo, self.picker_b, self.add_button, self.custom_button):
            w.setEnabled(enabled)

    # ------------------------------------------------------------------ interno
    def eventFilter(self, obj, event):  # noqa: N802
        from PyQt6.QtCore import QEvent

        if event.type() == QEvent.Type.FocusIn:
            if obj is self.picker_a:
                self._last_focused = "a"
            elif obj is self.picker_b:
                self._last_focused = "b"
        return super().eventFilter(obj, event)

    def _on_a_submitted(self) -> None:
        if self.picker_b.has_choice():
            self._emit_add()
        else:
            self.picker_b.setFocus()

    def _on_no_match(self, which: str, text: str) -> None:
        self._last_focused = which
        self.set_hint(f"«{text}» no está en la lista. Elija una sección del catálogo o cree una "
                      "sección personalizada con el botón de la derecha.", warning=True)

    def _emit_custom(self) -> None:
        which = self._last_focused
        self.customSectionRequested.emit(which, self.picker(which).text().strip())

    def _emit_add(self) -> None:
        a: PickerValue = self.picker_a.value()
        b: PickerValue = self.picker_b.value()
        if a is None or b is None:
            missing = self.picker_a if a is None else self.picker_b
            self._last_focused = "a" if a is None else "b"
            if missing.text().strip() and not missing._try_exact_match():
                self._on_no_match(self._last_focused, missing.text().strip())
            missing.setFocus()
            if missing.value() is None:
                return
            a, b = self.picker_a.value(), self.picker_b.value()
            if a is None or b is None:
                return
        self.addRequested.emit(a, self.current_kind(), b)
