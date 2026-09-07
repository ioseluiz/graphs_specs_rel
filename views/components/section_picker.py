"""Buscador de secciones con autocompletado por número o descripción (selección estricta).

`value()` devuelve:
- `int`                 id de una sección existente del proyecto
- `("catalog", key)`    entrada del catálogo MasterFormat aún no creada en el proyecto
- `None`                nada elegido (texto libre no válido)
"""
from __future__ import annotations

from PyQt6.QtCore import QModelIndex, Qt, pyqtSignal
from PyQt6.QtWidgets import QCompleter, QLineEdit, QListView

from models.master_catalog import normalize_code
from models.relation_normalizer import code_key, format_label
from models.section_completer_model import (
    ROLE_CODE,
    ROLE_CODE_KEY,
    ROLE_KIND,
    ROLE_SECTION_ID,
    ROLE_TITLE,
    SectionCompleterModel,
    SectionFilterProxy,
)
from views.components.delegates import TwoLineSectionDelegate

PickerValue = int | tuple[str, str] | None


class SectionPicker(QLineEdit):
    entryActivated = pyqtSignal()   # el usuario eligió una sugerencia
    submitted = pyqtSignal()        # Enter con una elección válida
    noMatch = pyqtSignal(str)       # Enter sin coincidencia en la lista (texto libre)

    def __init__(self, source: SectionCompleterModel, parent=None) -> None:
        super().__init__(parent)
        self._source = source
        self._chosen_id: int | None = None
        self._chosen_key: str | None = None
        self._proxy = SectionFilterProxy(self)
        self._proxy.setSourceModel(source)
        self.setPlaceholderText("Busque por número o descripción (ej. 03 30 o concreto)")
        self.setClearButtonEnabled(True)

        self._completer = QCompleter(self._proxy, self)
        self._completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._completer.setMaxVisibleItems(12)
        popup = QListView()
        popup.setItemDelegate(TwoLineSectionDelegate(popup, compact=True))
        popup.setUniformItemSizes(True)
        popup.setMinimumWidth(560)
        self._completer.setPopup(popup)
        self.setCompleter(self._completer)
        self._completer.activated[QModelIndex].connect(self._on_activated)
        self.textEdited.connect(self._on_text_edited)
        popup.installEventFilter(self)  # Enter con el popup abierto: elegir coincidencia exacta / única
        self._update_state()

    # ------------------------------------------------------------------ API
    def value(self) -> PickerValue:
        if self._chosen_id is not None:
            return self._chosen_id
        if self._chosen_key is not None:
            return ("catalog", self._chosen_key)
        return None

    def has_choice(self) -> bool:
        return self._chosen_id is not None or self._chosen_key is not None

    def set_section(self, section_id: int | None, label: str) -> None:
        self._chosen_id, self._chosen_key = section_id, None
        self.setText(label)
        self._update_state()

    def set_catalog_entry(self, key: str, label: str) -> None:
        self._chosen_id, self._chosen_key = None, key
        self.setText(label)
        self._update_state()

    def clear_value(self) -> None:
        self._chosen_id = self._chosen_key = None
        self.clear()
        self._proxy.set_query("")
        self._update_state()

    def popup_visible(self) -> bool:
        return self._completer.popup().isVisible()

    def match_count(self) -> int:
        return self._proxy.rowCount()

    # ------------------------------------------------------------------ interno
    def _update_state(self) -> None:
        invalid = bool(self.text().strip()) and not self.has_choice()
        if self.property("invalid") != invalid:
            self.setProperty("invalid", invalid)
            self.style().unpolish(self)
            self.style().polish(self)
        self.setToolTip("Elija una sección de la lista (o use «Sección personalizada…»)" if invalid else "")

    def _choose_row(self, proxy_row: int) -> None:
        self._on_activated(self._proxy.index(proxy_row, 0))

    def _try_exact_match(self) -> bool:
        """Si el texto es un código que existe (aun con espacios mal puestos), o hay una sola coincidencia."""
        text = self.text().strip()
        if not text:
            return False
        key = code_key(normalize_code(text))
        for row in range(self._proxy.rowCount()):
            idx = self._proxy.index(row, 0)
            if (idx.data(ROLE_CODE_KEY) or "") == key:
                self._on_activated(idx)
                return True
        if self._proxy.rowCount() == 1:
            self._choose_row(0)
            return True
        return False

    def _on_text_edited(self, text: str) -> None:
        self._chosen_id = self._chosen_key = None
        self._proxy.set_query(text)
        self._update_state()
        if text.strip():
            self._completer.complete()
        else:
            self._completer.popup().hide()

    def _on_activated(self, index: QModelIndex) -> None:
        kind = index.data(ROLE_KIND)
        code = index.data(ROLE_CODE) or ""
        title = index.data(ROLE_TITLE) or ""
        if kind == "section":
            self._chosen_id, self._chosen_key = index.data(ROLE_SECTION_ID), None
        else:
            self._chosen_id, self._chosen_key = None, index.data(ROLE_CODE_KEY)
        self.setText(format_label(code, title))
        self._completer.popup().hide()
        self._update_state()
        self.entryActivated.emit()

    def _handle_return(self) -> None:
        popup = self._completer.popup()
        current = popup.currentIndex() if popup.isVisible() else QModelIndex()
        if current.isValid():
            self._on_activated(current)
            self.submitted.emit()
            return
        if self.has_choice() or self._try_exact_match():
            self._completer.popup().hide()
            self.submitted.emit()
        elif self._proxy.rowCount() > 0 and self.text().strip():
            self._completer.complete()  # mostrar las coincidencias para que elija
            self._completer.popup().setCurrentIndex(self._proxy.index(0, 0))
        else:
            self._completer.popup().hide()
            self.noMatch.emit(self.text().strip())

    def eventFilter(self, obj, event):  # noqa: N802
        from PyQt6.QtCore import QEvent

        if obj is self._completer.popup() and event.type() == QEvent.Type.KeyPress and \
                event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_return()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._handle_return()
            event.accept()
            return
        super().keyPressEvent(event)
