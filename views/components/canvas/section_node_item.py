"""Nodo de sección: octágono con número y descripción, responsables encima y avance debajo."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PyQt6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from config import palette
from models.entities import Side
from views.components.canvas.orthogonal_router import port_point

if TYPE_CHECKING:
    from views.components.canvas.relation_edge_item import RelationEdgeItem

MIN_W, MAX_W, HEIGHT, CHAMFER = 150.0, 230.0, 58.0, 12.0
PAD_X = 12.0
RESP_D, RESP_GAP, RESP_MAX = 24.0, 4.0, 4        # círculos de responsables
EXTRA_TOP = RESP_D + 8.0                          # espacio sobre el octágono
BAR_H, EXTRA_BOTTOM = 8.0, 26.0                   # barra de avance + texto de estatus


class SectionNodeItem(QGraphicsItem):
    TYPE = QGraphicsItem.UserType + 1

    def __init__(self, section_id: int, code: str, title: str, fill: str, border: str) -> None:
        super().__init__()
        self.section_id = section_id
        self.code = code
        self.title = title
        self.fill = QColor(fill)
        self.border = QColor(border)
        self._edges: set[RelationEdgeItem] = set()
        self._width = MIN_W
        self._hover = False
        self._dimmed = False
        self._highlight = False
        self._title_lines: list[str] = []
        self._pos_at_press: QPointF | None = None
        self._code_font = QFont("Segoe UI", 9, QFont.Weight.Bold)
        self._title_font = QFont("Segoe UI", 8)
        self._small_font = QFont("Segoe UI", 7)
        self._resp_font = QFont("Segoe UI", 7, QFont.Weight.Bold)
        # Adornos: estatus, avance y responsables
        self._status_name = ""
        self._status_color: str | None = None
        self._progress = 0
        self._responsibles: list[tuple[str, str]] = []   # (código, color)
        self._show_extras = True
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable
        )
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.setZValue(1)
        self._layout_text()

    def type(self) -> int:  # noqa: A003
        return self.TYPE

    # ------------------------------------------------------------------ datos
    def set_data(self, code: str, title: str, fill: str, border: str) -> None:
        self.prepareGeometryChange()
        self.code, self.title = code, title
        self.fill, self.border = QColor(fill), QColor(border)
        self._layout_text()
        self.update()
        for e in self._edges:
            e.update_path()

    def set_extras(self, status_name: str, status_color: str | None, progress: int,
                   responsibles: list[tuple[str, str]], show: bool | None = None) -> None:
        self.prepareGeometryChange()
        self._status_name = status_name or ""
        self._status_color = status_color
        self._progress = max(0, min(100, int(progress)))
        self._responsibles = list(responsibles)
        if show is not None:
            self._show_extras = show
        self._update_tooltip()
        self.update()

    def set_show_extras(self, show: bool) -> None:
        if self._show_extras != show:
            self.prepareGeometryChange()
            self._show_extras = show
            self.update()

    @property
    def show_extras(self) -> bool:
        return self._show_extras

    def _update_tooltip(self) -> None:
        lines = [f"{self.code}\n{self.title}".strip()]
        if self._status_name:
            lines.append(f"Estatus: {self._status_name}")
        lines.append(f"Avance: {self._progress} %")
        if self._responsibles:
            lines.append("Responsables: " + ", ".join(code for code, _c in self._responsibles))
        self.setToolTip("\n".join(lines))

    def _layout_text(self) -> None:
        fm_code = QFontMetrics(self._code_font)
        fm_title = QFontMetrics(self._title_font)
        code_w = fm_code.horizontalAdvance(self.code)
        title_w = fm_title.horizontalAdvance(self.title)
        natural = max(code_w, min(title_w, 260.0)) + 2 * PAD_X + CHAMFER
        self._width = max(MIN_W, min(MAX_W, natural))
        avail = int(self._width - 2 * PAD_X)
        self._title_lines = self._wrap(self.title, fm_title, avail, max_lines=2)
        self._update_tooltip()

    @staticmethod
    def _wrap(text: str, fm: QFontMetrics, width: int, max_lines: int) -> list[str]:
        words = text.split()
        lines: list[str] = []
        current = ""
        for word in words:
            trial = f"{current} {word}".strip()
            if fm.horizontalAdvance(trial) <= width or not current:
                current = trial
            else:
                lines.append(current)
                current = word
            if len(lines) == max_lines:
                break
        if len(lines) < max_lines and current:
            lines.append(current)
        if len(lines) == max_lines and len(words) > sum(len(l.split()) for l in lines):
            lines[-1] = fm.elidedText(lines[-1] + " …", Qt.TextElideMode.ElideRight, width)
        return lines or ([""] if not text else [fm.elidedText(text, Qt.TextElideMode.ElideRight, width)])

    # ------------------------------------------------------------------ geometría
    def rect(self) -> QRectF:
        """Solo el octágono: los puertos y el ruteo no dependen de los adornos."""
        return QRectF(-self._width / 2, -HEIGHT / 2, self._width, HEIGHT)

    def scene_rect(self) -> QRectF:
        return self.rect().translated(self.pos())

    def boundingRect(self) -> QRectF:
        r = self.rect().adjusted(-4, -4, 4, 4)
        if self._show_extras:
            r = r.adjusted(0, -EXTRA_TOP, 0, EXTRA_BOTTOM)
        return r

    def shape(self) -> QPainterPath:
        return self._octagon(self.rect())

    @staticmethod
    def _octagon(r: QRectF) -> QPainterPath:
        c = CHAMFER
        path = QPainterPath()
        path.moveTo(r.left() + c, r.top())
        path.lineTo(r.right() - c, r.top())
        path.lineTo(r.right(), r.top() + c)
        path.lineTo(r.right(), r.bottom() - c)
        path.lineTo(r.right() - c, r.bottom())
        path.lineTo(r.left() + c, r.bottom())
        path.lineTo(r.left(), r.bottom() - c)
        path.lineTo(r.left(), r.top() + c)
        path.closeSubpath()
        return path

    def port_point(self, side: Side) -> QPointF:
        return port_point(self.scene_rect(), side)

    # ------------------------------------------------------------------ aristas
    def add_edge(self, edge: RelationEdgeItem) -> None:
        self._edges.add(edge)

    def remove_edge(self, edge: RelationEdgeItem) -> None:
        self._edges.discard(edge)

    @property
    def edges(self) -> set[RelationEdgeItem]:
        return set(self._edges)

    # ------------------------------------------------------------------ estados
    def set_dimmed(self, dimmed: bool) -> None:
        if self._dimmed != dimmed:
            self._dimmed = dimmed
            self.setOpacity(palette.DIMMED_OPACITY if dimmed else 1.0)

    def set_highlight(self, on: bool) -> None:
        if self._highlight != on:
            self._highlight = on
            self.update()

    # ------------------------------------------------------------------ eventos
    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            scene = self.scene()
            if scene is not None and getattr(scene, "snap_enabled", False):
                g = 10.0
                value = QPointF(round(value.x() / g) * g, round(value.y() / g) * g)
            return value
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self._edges:
                edge.update_path()
        elif change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.update()
        return super().itemChange(change, value)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self._hover = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self._hover = False
        self.update()
        super().hoverLeaveEvent(event)

    # ------------------------------------------------------------------ pintura
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        r = self.rect()
        path = self._octagon(r)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        if self._hover and not self.isSelected():
            shadow = QPainterPath(path)
            shadow.translate(0, 2)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(0, 0, 0, 28))
            painter.drawPath(shadow)
        pen = QPen(self.border, 1.5)
        if self._highlight:
            pen = QPen(QColor(palette.HIGHLIGHT_BORDER), 2.8)
        elif self.isSelected():
            pen = QPen(QColor(palette.NODE_SELECTED_BORDER), 2.5)
        painter.setPen(pen)
        painter.setBrush(QBrush(self.fill))
        painter.drawPath(path)

        painter.setPen(QColor(palette.NODE_TEXT))
        painter.setFont(self._code_font)
        fm_code = QFontMetrics(self._code_font)
        fm_title = QFontMetrics(self._title_font)
        total_h = fm_code.height() + len(self._title_lines) * fm_title.height()
        y = r.top() + (r.height() - total_h) / 2 + fm_code.ascent()
        painter.drawText(QPointF(r.center().x() - fm_code.horizontalAdvance(self.code) / 2, y), self.code)
        painter.setFont(self._title_font)
        painter.setPen(QColor(palette.NODE_SUBTEXT))
        y += fm_code.descent() + fm_title.ascent()
        for line in self._title_lines:
            painter.drawText(QPointF(r.center().x() - fm_title.horizontalAdvance(line) / 2, y), line)
            y += fm_title.height()

        if self._show_extras:
            self._paint_responsibles(painter, r)
            self._paint_progress(painter, r)

    def _paint_responsibles(self, painter: QPainter, r: QRectF) -> None:
        items = list(self._responsibles)
        if not items:
            return
        overflow = 0
        if len(items) > RESP_MAX:
            overflow = len(items) - (RESP_MAX - 1)
            items = items[: RESP_MAX - 1] + [(f"+{overflow}", palette.RESPONSIBLE_EXTRA)]
        fm = QFontMetrics(self._resp_font)
        # Píldoras: círculo para códigos cortos, se ensanchan para leer códigos largos (INI-PY).
        widths = [max(RESP_D, fm.horizontalAdvance(code) + 10) for code, _c in items]
        total_w = sum(widths) + (len(items) - 1) * RESP_GAP
        max_w = r.width() + 40
        if total_w > max_w:  # demasiado ancho: recortar textos proporcionalmente
            scale = max_w / total_w
            widths = [max(RESP_D, w * scale) for w in widths]
            total_w = sum(widths) + (len(items) - 1) * RESP_GAP
        x = r.center().x() - total_w / 2
        cy = r.top() - 6 - RESP_D / 2
        for (code, color), w in zip(items, widths):
            pill = QRectF(x, cy - RESP_D / 2, w, RESP_D)
            painter.setPen(QPen(QColor(color).darker(125), 1))
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(pill, RESP_D / 2, RESP_D / 2)
            painter.setPen(QColor(palette.contrast_text(color)))
            painter.setFont(self._resp_font)
            text = fm.elidedText(code, Qt.TextElideMode.ElideRight, int(w - 4))
            painter.drawText(pill, int(Qt.AlignmentFlag.AlignCenter), text)
            x += w + RESP_GAP

    def _paint_progress(self, painter: QPainter, r: QRectF) -> None:
        fm = QFontMetrics(self._small_font)
        label = f"{self._progress} %"
        label_w = fm.horizontalAdvance("100 %")
        bar = QRectF(r.left() + 6, r.bottom() + 6, r.width() - 12 - label_w - 6, BAR_H)
        painter.setPen(QPen(QColor(palette.BORDER), 0.8))
        painter.setBrush(QColor(palette.PROGRESS_TRACK))
        painter.drawRoundedRect(bar, 3, 3)
        if self._progress > 0:
            fill_color = QColor(self._status_color) if self._status_color else QColor(palette.PRIMARY)
            if self._status_color and QColor(self._status_color).lightness() > 200:
                fill_color = fill_color.darker(135)  # estatus muy claros: barra visible
            filled = QRectF(bar.left(), bar.top(), bar.width() * self._progress / 100.0, bar.height())
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(fill_color)
            painter.drawRoundedRect(filled, 3, 3)
        painter.setFont(self._small_font)
        painter.setPen(QColor(palette.TEXT_SECONDARY))
        painter.drawText(QRectF(bar.right() + 6, bar.top() - 3, label_w + 4, BAR_H + 6),
                         int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft), label)
        if self._status_name:
            painter.setFont(self._small_font)
            painter.setPen(QColor(palette.TEXT_SECONDARY))
            text = fm.elidedText(self._status_name, Qt.TextElideMode.ElideRight, int(r.width() - 12))
            painter.drawText(QPointF(r.left() + 6, bar.bottom() + 2 + fm.ascent()), text)
