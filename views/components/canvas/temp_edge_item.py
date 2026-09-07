"""Línea temporal mostrada mientras el usuario arrastra para crear una relación."""
from __future__ import annotations

from PyQt6.QtCore import QLineF, QPointF, Qt
from PyQt6.QtGui import QColor, QPen
from PyQt6.QtWidgets import QGraphicsLineItem

from config import palette


class TempEdgeItem(QGraphicsLineItem):
    def __init__(self, start: QPointF) -> None:
        super().__init__(QLineF(start, start))
        pen = QPen(QColor(palette.EDGE_SELECTED), 2, Qt.PenStyle.DashLine)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        self.setPen(pen)
        self.setZValue(10)
        self.setAcceptedMouseButtons(Qt.MouseButton.NoButton)

    def set_end(self, end: QPointF) -> None:
        line = self.line()
        self.setLine(QLineF(line.p1(), end))
