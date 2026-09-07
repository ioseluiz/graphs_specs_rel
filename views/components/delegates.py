"""Delegados de la tabla de relaciones y del popup de autocompletado."""
from __future__ import annotations

from PyQt6.QtCore import QEvent, QModelIndex, QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QWidget,
)

from config import palette
from models.entities import UiKind
from models.section_completer_model import (
    ROLE_BORDER as C_BORDER,
    ROLE_CODE as C_CODE,
    ROLE_FILL as C_FILL,
    ROLE_KIND as C_KIND,
    ROLE_TITLE as C_TITLE,
)
from models.relations_table_model import ROLE_BORDER, ROLE_CODE, ROLE_FILL, ROLE_RELATION_ID, ROLE_TITLE

ROW_HEIGHT = 44
SWATCH = 12


class TwoLineSectionDelegate(QStyledItemDelegate):
    """Código en negrita + título debajo, con muestra de color de la categoría."""

    def __init__(self, parent=None, compact: bool = False) -> None:
        super().__init__(parent)
        self.compact = compact
        self._code_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        self._title_font = QFont("Segoe UI", 8)

    def _roles(self, index: QModelIndex) -> tuple[str, str, str, str, bool]:
        # Sirve tanto para el modelo de tabla como para el de autocompletado.
        code = index.data(ROLE_CODE) or index.data(C_CODE) or ""
        title = index.data(ROLE_TITLE) or index.data(C_TITLE) or ""
        fill = index.data(ROLE_FILL) or index.data(C_FILL) or palette.SURFACE_ALT
        border = index.data(ROLE_BORDER) or index.data(C_BORDER) or palette.BORDER_STRONG
        from_catalog = index.data(C_KIND) == "catalog"
        return str(code), str(title), str(fill), str(border), from_catalog

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        code, title, fill, border, from_catalog = self._roles(index)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor("#F2F5F9"))
        r = option.rect.adjusted(8, 4, -6, -4)
        sw = QRect(r.left(), r.top() + (r.height() - SWATCH) // 2, SWATCH, SWATCH)
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(fill))
        painter.drawRoundedRect(sw, 2, 2)
        text_left = sw.right() + 8
        fm_code = QFontMetrics(self._code_font)
        fm_title = QFontMetrics(self._title_font)
        width = r.right() - text_left
        painter.setFont(self._code_font)
        painter.setPen(QColor(palette.TEXT_SECONDARY if from_catalog else palette.TEXT))
        y = r.top() + fm_code.ascent() + (0 if title else (r.height() - fm_code.height()) // 2)
        painter.drawText(text_left, y, fm_code.elidedText(code, Qt.TextElideMode.ElideRight, width))
        if title:
            painter.setFont(self._title_font)
            painter.setPen(QColor(palette.TEXT_SECONDARY))
            y2 = y + fm_code.descent() + fm_title.ascent() + 1
            label = title + ("  (catálogo)" if from_catalog else "")
            painter.drawText(text_left, y2, fm_title.elidedText(label, Qt.TextElideMode.ElideRight, width))
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(220, 38 if self.compact else ROW_HEIGHT)


class RelationKindDelegate(QStyledItemDelegate):
    """Celda «Relación»: muestra 'A → B' / 'A ↔ B' y edita con un combo desplegado de inmediato.

    Opciones: «Hace referencia a →», «Referencia mutua ↔» e «Invertir dirección (B → A)». La opción
    «← Es referenciada por» no se ofrece aquí: la fila siempre muestra origen → destino, así que en una
    relación existente invertir es la acción clara.
    """

    _FONT = QFont("Segoe UI", 9)
    _SMALL = QFont("Segoe UI", 7)

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:  # noqa: N802
        from models.relations_table_model import INVERT_OPTION, ROLE_IS_MUTUAL

        combo = QComboBox(parent)
        combo.addItem(UiKind.REFERENCES.value)
        combo.addItem(UiKind.MUTUAL.value)
        if not index.data(ROLE_IS_MUTUAL):
            combo.addItem(INVERT_OPTION)
        combo.setToolTip("La fila muestra siempre origen → destino. «Invertir» intercambia A y B.")
        return combo

    def setEditorData(self, editor: QComboBox, index: QModelIndex) -> None:  # noqa: N802
        current = index.data(Qt.ItemDataRole.EditRole)
        pos = editor.findText(str(current))
        editor.setCurrentIndex(max(0, pos))
        editor.showPopup()

    def setModelData(self, editor: QComboBox, model, index: QModelIndex) -> None:  # noqa: N802
        if editor.currentText() != str(index.data(Qt.ItemDataRole.EditRole)):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        from models.relations_table_model import ROLE_CODE_A, ROLE_CODE_B, ROLE_IS_MUTUAL

        painter.save()
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        elif bg is not None:
            painter.fillRect(option.rect, bg)
        painter.setPen(QColor(palette.PRIMARY))
        painter.setFont(self._FONT)
        r = option.rect
        fm = QFontMetrics(self._FONT)
        fm_small = QFontMetrics(self._SMALL)
        label = str(index.data() or "")
        arrow = "↔" if index.data(ROLE_IS_MUTUAL) else "→"
        detail = f"{index.data(ROLE_CODE_A) or ''} {arrow} {index.data(ROLE_CODE_B) or ''}".strip()
        total_h = fm.height() + fm_small.height()
        top = r.top() + (r.height() - total_h) // 2
        painter.drawText(QRect(r.left(), top, r.width(), fm.height()),
                         int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter), label)
        painter.setFont(self._SMALL)
        painter.setPen(QColor(palette.TEXT_SECONDARY))
        painter.drawText(QRect(r.left(), top + fm.height(), r.width(), fm_small.height()),
                         int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter),
                         fm_small.elidedText(detail, Qt.TextElideMode.ElideMiddle, r.width() - 6))
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        fm = QFontMetrics(self._FONT)
        widest = max(fm.horizontalAdvance(k.value) for k in UiKind)
        return QSize(widest + 28, ROW_HEIGHT)


class SectionPickerDelegate(QStyledItemDelegate):
    """Editor inline con el buscador de secciones."""

    def __init__(self, completer_model, parent=None) -> None:
        super().__init__(parent)
        self._completer_model = completer_model

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:  # noqa: N802
        from views.components.section_picker import SectionPicker

        editor = SectionPicker(self._completer_model, parent)
        editor.submitted.connect(lambda: self.commitData.emit(editor))
        editor.submitted.connect(lambda: self.closeEditor.emit(editor))
        return editor

    def setEditorData(self, editor, index: QModelIndex) -> None:  # noqa: N802
        from models.relation_normalizer import format_label

        code = index.data(ROLE_CODE) or ""
        title = index.data(ROLE_TITLE) or ""
        editor.set_section(index.data(Qt.ItemDataRole.EditRole), format_label(code, title))
        editor.selectAll()

    def setModelData(self, editor, model, index: QModelIndex) -> None:  # noqa: N802
        value = editor.value()
        if value is None and editor.text().strip():
            editor._try_exact_match()
            value = editor.value()
        if value is None:
            return  # sin elección válida: no se modifica la relación
        model.setData(index, value, Qt.ItemDataRole.EditRole)


# ============================================================================ pestaña Secciones
class ColoredChoiceDelegate(QStyledItemDelegate):
    """Celda con muestra de color + nombre; editor combo. `provider()` -> [(id, nombre, color)]."""

    def __init__(self, provider, parent=None, allow_none: bool = True, none_label: str = "(ninguna)") -> None:
        super().__init__(parent)
        self._provider = provider
        self._allow_none = allow_none
        self._none_label = none_label

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        from models.sections_table_model import ROLE_BORDER as S_BORDER, ROLE_COLOR as S_COLOR

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        text = str(index.data() or "")
        r = option.rect.adjusted(8, 0, -6, 0)
        if text:
            sw = QRect(r.left(), r.center().y() - SWATCH // 2, SWATCH, SWATCH)
            painter.setPen(QPen(QColor(str(index.data(S_BORDER) or palette.BORDER_STRONG)), 1))
            painter.setBrush(QColor(str(index.data(S_COLOR) or palette.SURFACE_ALT)))
            painter.drawRoundedRect(sw, 2, 2)
            left = sw.right() + 8
        else:
            left = r.left()
            text = "—"
        painter.setPen(QColor(palette.TEXT if text != "—" else palette.TEXT_DISABLED))
        painter.setFont(QFont("Segoe UI", 9))
        fm = QFontMetrics(painter.font())
        painter.drawText(left, r.center().y() + fm.ascent() // 2 - 1,
                         fm.elidedText(text, Qt.TextElideMode.ElideRight, r.right() - left))
        painter.restore()

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:  # noqa: N802
        from PyQt6.QtGui import QIcon, QPixmap

        combo = QComboBox(parent)
        if self._allow_none:
            combo.addItem(self._none_label, None)
        for item_id, name, color in self._provider():
            pix = QPixmap(14, 14)
            pix.fill(QColor(color))
            combo.addItem(QIcon(pix), name, item_id)
        return combo

    def setEditorData(self, editor: QComboBox, index: QModelIndex) -> None:  # noqa: N802
        current = index.data(Qt.ItemDataRole.EditRole)
        pos = editor.findData(current)
        editor.setCurrentIndex(max(0, pos))
        editor.showPopup()

    def setModelData(self, editor: QComboBox, model, index: QModelIndex) -> None:  # noqa: N802
        model.setData(index, editor.currentData(), Qt.ItemDataRole.EditRole)


class ProgressDelegate(QStyledItemDelegate):
    """Barra de avance con porcentaje; editor QSpinBox 0–100."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        from models.sections_table_model import ROLE_COLOR as S_COLOR

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        try:
            value = int(index.data(Qt.ItemDataRole.EditRole) or 0)
        except (TypeError, ValueError):
            value = 0
        r = option.rect.adjusted(8, 0, -8, 0)
        label_w = 36
        bar = QRect(r.left(), r.center().y() - 4, max(10, r.width() - label_w - 6), 8)
        painter.setPen(QPen(QColor(palette.BORDER), 1))
        painter.setBrush(QColor(palette.PROGRESS_TRACK))
        painter.drawRoundedRect(bar, 3, 3)
        if value > 0:
            color = QColor(str(index.data(S_COLOR) or palette.PRIMARY))
            if color.lightness() > 200:
                color = color.darker(135)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRect(bar.left(), bar.top(), int(bar.width() * value / 100), bar.height()), 3, 3)
        painter.setPen(QColor(palette.TEXT))
        painter.setFont(QFont("Segoe UI", 9))
        painter.drawText(QRect(bar.right() + 6, r.top(), label_w, r.height()),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), f"{value} %")
        painter.restore()

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:  # noqa: N802
        from PyQt6.QtWidgets import QSpinBox

        spin = QSpinBox(parent)
        spin.setRange(0, 100)
        spin.setSingleStep(5)
        spin.setSuffix(" %")
        return spin

    def setEditorData(self, editor, index: QModelIndex) -> None:  # noqa: N802
        try:
            editor.setValue(int(index.data(Qt.ItemDataRole.EditRole) or 0))
        except (TypeError, ValueError):
            editor.setValue(0)
        editor.selectAll()

    def setModelData(self, editor, model, index: QModelIndex) -> None:  # noqa: N802
        editor.interpretText()
        model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)


class ResponsiblesDelegate(QStyledItemDelegate):
    """Círculos de responsables; editor: lista con casillas. `provider()` -> [(id, code, color)]."""

    D = 22

    def __init__(self, provider, parent=None) -> None:
        super().__init__(parent)
        self._provider = provider

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        from models.sections_table_model import ROLE_RESPONSIBLES

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        items = index.data(ROLE_RESPONSIBLES) or []
        x = option.rect.left() + 8
        cy = option.rect.center().y()
        font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        fm = QFontMetrics(font)
        painter.setFont(font)
        for _rid, code, color in items:
            w = max(self.D, fm.horizontalAdvance(code) + 10)
            if x + w > option.rect.right() - 4:
                painter.setPen(QColor(palette.TEXT_SECONDARY))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(QRect(x, option.rect.top(), 20, option.rect.height()),
                                 int(Qt.AlignmentFlag.AlignVCenter), "…")
                break
            pill = QRect(x, cy - self.D // 2, w, self.D)
            painter.setPen(QPen(QColor(color).darker(125), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(pill, self.D // 2, self.D // 2)
            painter.setPen(QColor(palette.contrast_text(color)))
            painter.setFont(font)
            painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), code)
            x += w + 4
        if not items:
            painter.setPen(QColor(palette.TEXT_DISABLED))
            painter.setFont(QFont("Segoe UI", 9))
            painter.drawText(option.rect.adjusted(8, 0, 0, 0), int(Qt.AlignmentFlag.AlignVCenter), "—")
        painter.restore()

    def createEditor(self, parent: QWidget, option: QStyleOptionViewItem, index: QModelIndex) -> QWidget:  # noqa: N802
        from PyQt6.QtGui import QIcon, QPixmap
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem

        lst = QListWidget(parent)
        lst.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        for rid, code, color in self._provider():
            pix = QPixmap(14, 14)
            pix.fill(QColor(color))
            item = QListWidgetItem(QIcon(pix), code)
            item.setData(Qt.ItemDataRole.UserRole, rid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            lst.addItem(item)
        lst.setMinimumHeight(min(6, max(1, lst.count())) * 24 + 8)
        return lst

    def updateEditorGeometry(self, editor, option, index) -> None:  # noqa: N802
        rect = QRect(option.rect)
        rect.setHeight(max(option.rect.height(), editor.minimumHeight()))
        rect.setWidth(max(option.rect.width(), 160))
        editor.setGeometry(rect)

    def setEditorData(self, editor, index: QModelIndex) -> None:  # noqa: N802
        selected = set(index.data(Qt.ItemDataRole.EditRole) or [])
        for i in range(editor.count()):
            item = editor.item(i)
            item.setCheckState(Qt.CheckState.Checked if item.data(Qt.ItemDataRole.UserRole) in selected
                               else Qt.CheckState.Unchecked)

    def setModelData(self, editor, model, index: QModelIndex) -> None:  # noqa: N802
        ids = [editor.item(i).data(Qt.ItemDataRole.UserRole) for i in range(editor.count())
               if editor.item(i).checkState() == Qt.CheckState.Checked]
        model.setData(index, ids, Qt.ItemDataRole.EditRole)


class ActionsDelegate(QStyledItemDelegate):
    """Iconos de fila: ✎ editar secciones · ⇄ invertir dirección · 🗑 eliminar (con tooltips)."""

    editRequested = pyqtSignal(int)
    invertRequested = pyqtSignal(int)
    deleteRequested = pyqtSignal(int)

    ICON_W = 26
    TIPS = ("Editar Sección A / Sección B", "Invertir dirección (B → A)", "Eliminar relación")

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        from models.relations_table_model import ROLE_IS_MUTUAL

        painter.save()
        bg = index.data(Qt.ItemDataRole.BackgroundRole)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        elif bg is not None:
            painter.fillRect(option.rect, bg)
        edit_rect, inv_rect, del_rect = self._rects(option.rect)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setFont(QFont("Segoe UI Symbol", 11))
        painter.setPen(QColor(palette.PRIMARY))
        painter.drawText(edit_rect, int(Qt.AlignmentFlag.AlignCenter), "✎")
        mutual = bool(index.data(ROLE_IS_MUTUAL))
        painter.setPen(QColor(palette.TEXT_DISABLED if mutual else palette.PRIMARY))
        painter.setFont(QFont("Segoe UI Symbol", 12, QFont.Weight.Bold))
        painter.drawText(inv_rect, int(Qt.AlignmentFlag.AlignCenter), "⇄")
        painter.setFont(QFont("Segoe UI Symbol", 11))
        painter.setPen(QColor(palette.DANGER))
        painter.drawText(del_rect, int(Qt.AlignmentFlag.AlignCenter), "🗑")
        painter.restore()

    def _rects(self, rect: QRect) -> tuple[QRect, QRect, QRect]:
        total = self.ICON_W * 3
        left = rect.left() + (rect.width() - total) // 2
        return (QRect(left, rect.top(), self.ICON_W, rect.height()),
                QRect(left + self.ICON_W, rect.top(), self.ICON_W, rect.height()),
                QRect(left + 2 * self.ICON_W, rect.top(), self.ICON_W, rect.height()))

    def editorEvent(self, event: QEvent, model, option: QStyleOptionViewItem, index: QModelIndex) -> bool:  # noqa: N802
        from models.relations_table_model import ROLE_IS_MUTUAL

        if event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
            rid = index.data(ROLE_RELATION_ID)
            edit_rect, inv_rect, del_rect = self._rects(option.rect)
            pos = event.position().toPoint()
            if edit_rect.contains(pos):
                self.editRequested.emit(int(rid))
                return True
            if inv_rect.contains(pos):
                if not index.data(ROLE_IS_MUTUAL):
                    self.invertRequested.emit(int(rid))
                return True
            if del_rect.contains(pos):
                self.deleteRequested.emit(int(rid))
                return True
        return False

    def helpEvent(self, event, view, option: QStyleOptionViewItem, index: QModelIndex) -> bool:  # noqa: N802
        from PyQt6.QtWidgets import QToolTip

        from models.relations_table_model import ROLE_IS_MUTUAL

        if event.type() == QEvent.Type.ToolTip:
            pos = event.pos()
            tips = list(self.TIPS)
            if index.data(ROLE_IS_MUTUAL):
                tips[1] = "Invertir no aplica a una referencia mutua"
            for rect, tip in zip(self._rects(option.rect), tips):
                if rect.contains(pos):
                    QToolTip.showText(event.globalPos(), tip, view)
                    return True
            QToolTip.hideText()
            return True
        return super().helpEvent(event, view, option, index)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(self.ICON_W * 3 + 8, ROW_HEIGHT)
