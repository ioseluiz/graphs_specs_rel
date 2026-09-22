"""Traducción del estilo de flecha (models.line_styles) a Qt: pens, iconos de menú y vista previa."""
from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap, QPolygonF

from config import palette
from models.line_styles import DASH_DASH, DASH_DASHDOT, DASH_DOT, DASH_SOLID, DEFAULT_WIDTH

# Patrones en unidades del ancho del pen (Qt los escala con el grosor). FlatCap: los puntos no se funden.
DASH_PATTERNS: dict[str, list[float] | None] = {
    DASH_SOLID: None,
    DASH_DASH: [4.0, 3.0],
    DASH_DOT: [1.0, 2.0],
    DASH_DASHDOT: [4.0, 2.0, 1.0, 2.0],
}


def make_pen(color: QColor | str, width: float, dash: str = DASH_SOLID) -> QPen:
    pen = QPen(QColor(color), width)
    pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
    pen.setCapStyle(Qt.PenCapStyle.FlatCap)
    pattern = DASH_PATTERNS.get(dash)
    if pattern:
        pen.setDashPattern(pattern)
    return pen


def _arrow_head(from_pt: QPointF, tip: QPointF, length: float = 9.0, half: float = 3.8) -> QPolygonF:
    ang = math.atan2(tip.y() - from_pt.y(), tip.x() - from_pt.x())
    left = QPointF(tip.x() - length * math.cos(ang) + half * math.sin(ang),
                   tip.y() - length * math.sin(ang) - half * math.cos(ang))
    right = QPointF(tip.x() - length * math.cos(ang) - half * math.sin(ang),
                    tip.y() - length * math.sin(ang) + half * math.cos(ang))
    return QPolygonF([tip, left, right])


def draw_sample(painter: QPainter, rect: QRectF, color: str | None, dash: str, width: float | None,
                arrow: bool = True) -> None:
    """Dibuja una muestra horizontal de la flecha con su estilo dentro de `rect` (centrada verticalmente)."""
    c = QColor(color or palette.EDGE_COLOR)
    w = width if width is not None else DEFAULT_WIDTH
    y = rect.center().y()
    start, end = QPointF(rect.left() + 2, y), QPointF(rect.right() - 2, y)
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    line_end = QPointF(end.x() - (7 if arrow else 0), y)
    path = QPainterPath(start)
    path.lineTo(line_end)
    painter.setPen(make_pen(c, w, dash))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    if arrow:
        painter.setPen(QPen(c, 1))
        painter.setBrush(c)
        painter.drawPolygon(_arrow_head(start, end))
    painter.restore()


def _pixmap(width: int, height: int, background: str | None = None) -> QPixmap:
    pix = QPixmap(width, height)
    pix.fill(QColor(background) if background else Qt.GlobalColor.transparent)
    return pix


def color_icon(hex_color: str, size: int = 14) -> QIcon:
    pix = _pixmap(size, size)
    painter = QPainter(pix)
    painter.setPen(QPen(QColor(hex_color).darker(125), 1))
    painter.setBrush(QColor(hex_color))
    painter.drawRoundedRect(QRectF(0.5, 0.5, size - 1, size - 1), 3, 3)
    painter.end()
    return QIcon(pix)


def dash_icon(dash: str, width: float = DEFAULT_WIDTH, color: str = palette.EDGE_COLOR,
              size: QSize = QSize(40, 14)) -> QIcon:
    pix = _pixmap(size.width(), size.height())
    painter = QPainter(pix)
    draw_sample(painter, QRectF(0, 0, size.width(), size.height()), color, dash, width, arrow=False)
    painter.end()
    return QIcon(pix)


def width_icon(width: float, color: str = palette.EDGE_COLOR, size: QSize = QSize(40, 14)) -> QIcon:
    return dash_icon(DASH_SOLID, width, color, size)


def preview_pixmap(color: str | None, dash: str, width: float | None, w: int = 260, h: int = 44) -> QPixmap:
    pix = _pixmap(w, h, palette.SURFACE)
    painter = QPainter(pix)
    painter.setPen(QPen(QColor(palette.BORDER), 1))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), 4, 4)
    draw_sample(painter, QRectF(12, 0, w - 24, h), color, dash, width, arrow=True)
    painter.end()
    return pix
