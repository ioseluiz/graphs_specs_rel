"""Manija arrastrable para editar la geometría de una conexión."""
from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QBrush, QColor, QPen
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsRectItem

from config import palette

if TYPE_CHECKING:
    from views.components.canvas.relation_edge_item import RelationEdgeItem

SIZE = 9.0


class WaypointHandleItem(QGraphicsRectItem):
    TYPE = QGraphicsItem.UserType + 3

    def __init__(self, edge: RelationEdgeItem, index: int, pos: QPointF) -> None:
        super().__init__(QRectF(-SIZE / 2, -SIZE / 2, SIZE, SIZE))
        self.edge = edge
        self.index = index
        self.setPos(pos)
        self.setZValue(5)
        self.setBrush(QBrush(QColor("#FFFFFF")))
        self.setPen(QPen(QColor(palette.EDGE_SELECTED), 1.5))
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges
            | QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations
        )
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.setAcceptHoverEvents(True)
        self._dragging = False

    def type(self) -> int:  # noqa: A003
        return self.TYPE

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and self._dragging:
            self.edge.preview_waypoint(self.index, self.pos())
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        self._dragging = True
        event.accept()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        super().mouseReleaseEvent(event)
        self._dragging = False
        self.edge.commit_waypoint(self.index, self.pos())

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        event.accept()
        self.edge.remove_waypoint(self.index)

    def hoverEnterEvent(self, event) -> None:  # noqa: N802
        self.setBrush(QBrush(QColor(palette.PRIMARY_TINT)))
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event) -> None:  # noqa: N802
        self.setBrush(QBrush(QColor("#FFFFFF")))
        super().hoverLeaveEvent(event)
