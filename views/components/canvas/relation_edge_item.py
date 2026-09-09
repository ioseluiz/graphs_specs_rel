"""Conexión entre dos nodos: polilínea ortogonal con flechas y waypoints editables."""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPainterPath, QPainterPathStroker, QPen, QPolygonF
from PyQt6.QtWidgets import QGraphicsItem, QGraphicsPathItem, QStyleOptionGraphicsItem, QWidget

from config import palette
from models.entities import RelationKind, Side  # noqa: F401  (kind se conserva por compatibilidad)
from views.components.canvas.orthogonal_router import (
    choose_ports,
    choose_ports_near,
    nearest_segment_index,
    repair_waypoints,
    route,
)
from views.components.canvas.waypoint_handle_item import WaypointHandleItem

if TYPE_CHECKING:
    from views.components.canvas.section_node_item import SectionNodeItem

ARROW_LEN, ARROW_HALF = 11.0, 4.5
ENDPOINT_R = 4.0   # marcador del origen cuando la flecha está seleccionada


class RelationEdgeItem(QGraphicsPathItem):
    TYPE = QGraphicsItem.UserType + 2

    def __init__(
        self,
        relation_id: int,
        source: SectionNodeItem,
        target: SectionNodeItem,
        kind: RelationKind,
        waypoints: list[tuple[float, float]] | None = None,
        source_port: Side | None = None,
        target_port: Side | None = None,
    ) -> None:
        super().__init__()
        self.relation_id = relation_id
        self.source = source
        self.target = target
        self.kind = kind
        self.waypoints: list[QPointF] | None = [QPointF(x, y) for x, y in waypoints] if waypoints else None
        self.source_port = source_port
        self.target_port = target_port
        self.effective_ports: tuple[Side, Side] = ("top", "bottom")
        self.points: list[QPointF] = []
        self._arrows: list[QPolygonF] = []
        self._hover = False
        self._dimmed = False
        self._highlight = False
        self.notes = ""
        self._handles: list[WaypointHandleItem] = []
        self._shape = QPainterPath()
        self._bounds = QRectF()
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)
        self.setZValue(0)
        source.add_edge(self)
        target.add_edge(self)
        self.update_path()

    def type(self) -> int:  # noqa: A003
        return self.TYPE

    # ------------------------------------------------------------------ datos
    def set_kind(self, kind: RelationKind) -> None:
        self.kind = kind
        self.update_path()

    def set_geometry(self, waypoints: list[tuple[float, float]] | None,
                     source_port: Side | None, target_port: Side | None) -> None:
        self.waypoints = [QPointF(x, y) for x, y in waypoints] if waypoints else None
        self.source_port, self.target_port = source_port, target_port
        self.update_path()
        if self._handles:
            self.show_handles(True)

    def rebind(self, source: SectionNodeItem, target: SectionNodeItem) -> None:
        self.source.remove_edge(self)
        self.target.remove_edge(self)
        self.source, self.target = source, target
        source.add_edge(self)
        target.add_edge(self)
        self.update_path()

    def detach(self) -> None:
        self.show_handles(False)
        self.source.remove_edge(self)
        self.target.remove_edge(self)

    # ------------------------------------------------------------------ ruteo
    def update_path(self) -> None:
        src, tgt = self.source.scene_rect(), self.target.scene_rect()
        if self.source_port and self.target_port:
            ports: tuple[Side, Side] = (self.source_port, self.target_port)
        else:
            if self.waypoints:
                auto = choose_ports_near(src, tgt, self.waypoints[0], self.waypoints[-1])
            else:
                auto = choose_ports(src, tgt)
            ports = (self.source_port or auto[0], self.target_port or auto[1])
        self.effective_ports = ports
        if self.waypoints:
            pts = repair_waypoints(src, ports[0], self.waypoints, tgt, ports[1])
        else:
            pts = route(src, tgt, ports)
        self.points = pts
        self._update_tooltip()
        self.prepareGeometryChange()
        path = QPainterPath()
        if pts:
            path.moveTo(pts[0])
            for p in pts[1:]:
                path.lineTo(p)
        # shape()/boundingRect() se consultan en cada repintado, selección y hover: se calculan una vez aquí.
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        self._shape = stroker.createStroke(path)
        self._bounds = self._shape.controlPointRect().adjusted(-ARROW_LEN, -ARROW_LEN, ARROW_LEN, ARROW_LEN)
        self.setPath(path)
        self._arrows = []
        if len(pts) >= 2:
            self._arrows.append(self._arrow_head(pts[-2], pts[-1]))
        for h in self._handles:
            if self.waypoints and h.index < len(self.waypoints) and not h._dragging:
                h.setPos(self.waypoints[h.index])

    def set_notes(self, notes: str | None) -> None:
        self.notes = (notes or "").strip()
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        text = f"{self.source.code} → {self.target.code}"
        if getattr(self, "notes", ""):
            text += f"\n{self.notes}"
        text += "\nClic: seleccionar (resalta las secciones vinculadas) · Tecla R: invertir · Clic derecho: más opciones"
        self.setToolTip(text)

    @staticmethod
    def _arrow_head(from_pt: QPointF, tip: QPointF) -> QPolygonF:
        ang = math.atan2(tip.y() - from_pt.y(), tip.x() - from_pt.x())
        left = QPointF(tip.x() - ARROW_LEN * math.cos(ang) + ARROW_HALF * math.sin(ang),
                       tip.y() - ARROW_LEN * math.sin(ang) - ARROW_HALF * math.cos(ang))
        right = QPointF(tip.x() - ARROW_LEN * math.cos(ang) - ARROW_HALF * math.sin(ang),
                        tip.y() - ARROW_LEN * math.sin(ang) + ARROW_HALF * math.cos(ang))
        return QPolygonF([tip, left, right])

    def shape(self) -> QPainterPath:
        return self._shape

    def boundingRect(self) -> QRectF:  # type: ignore[override]
        return self._bounds

    # ------------------------------------------------------------------ waypoints
    def show_handles(self, on: bool) -> None:
        scene = self.scene()
        for h in self._handles:
            if h.scene() is not None:
                h.scene().removeItem(h)
        self._handles = []
        if on and scene is not None and self.waypoints:
            for i, wp in enumerate(self.waypoints):
                handle = WaypointHandleItem(self, i, wp)
                scene.addItem(handle)
                self._handles.append(handle)

    def preview_waypoint(self, index: int, pos: QPointF) -> None:
        if self.waypoints and index < len(self.waypoints):
            self.waypoints[index] = QPointF(pos)
            self.update_path()

    def commit_waypoint(self, index: int, pos: QPointF) -> None:
        self.preview_waypoint(index, pos)
        self._emit_geometry()

    def insert_waypoint_at(self, scene_pos: QPointF) -> None:
        """Doble clic sobre un segmento: inserta un waypoint en esa posición."""
        if not self.points:
            return
        seg = nearest_segment_index(self.points, scene_pos)
        if self.waypoints is None:
            # Convertir la ruta automática en waypoints explícitos (vértices interiores).
            interior = self.points[2:-2]  # excluye puertos y stubs
            self.waypoints = [QPointF(p) for p in interior]
            self.update_path()
            seg = nearest_segment_index(self.points, scene_pos)
        # Mapear el segmento de la polilínea al índice de inserción en waypoints.
        insert_at = 0
        for i, wp in enumerate(self.waypoints):
            idx = next((k for k, p in enumerate(self.points) if p == wp), None)
            if idx is not None and idx <= seg:
                insert_at = i + 1
        self.waypoints.insert(insert_at, QPointF(scene_pos))
        self.update_path()
        self.show_handles(True)
        self._emit_geometry()

    def remove_waypoint(self, index: int) -> None:
        if self.waypoints and index < len(self.waypoints):
            del self.waypoints[index]
            if not self.waypoints:
                self.waypoints = None
            self.update_path()
            self.show_handles(bool(self.waypoints) and self.isSelected())
            self._emit_geometry()

    def reset_geometry(self) -> None:
        self.waypoints = None
        self.source_port = None
        self.target_port = None
        self.show_handles(False)
        self.update_path()
        self._emit_geometry()

    def set_forced_port(self, source_port: Side | None, target_port: Side | None) -> None:
        self.source_port, self.target_port = source_port, target_port
        self.update_path()
        self._emit_geometry()

    def _emit_geometry(self) -> None:
        scene = self.scene()
        if scene is not None and hasattr(scene, "edgeGeometryChanged"):
            wps = [(p.x(), p.y()) for p in self.waypoints] if self.waypoints else None
            scene.edgeGeometryChanged.emit(self.relation_id, wps, self.source_port, self.target_port)

    # ------------------------------------------------------------------ estados
    def set_dimmed(self, dimmed: bool) -> None:
        if self._dimmed != dimmed:
            self._dimmed = dimmed
            self.setOpacity(palette.DIMMED_OPACITY if dimmed else 1.0)

    def set_highlight(self, on: bool) -> None:
        if self._highlight != on:
            self._highlight = on
            self.update()

    def itemChange(self, change, value):  # type: ignore[override]
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedHasChanged:
            self.show_handles(bool(value) and bool(self.waypoints))
            self.setZValue(2 if value else 0)
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

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        event.accept()
        self.insert_waypoint_at(event.scenePos())

    # ------------------------------------------------------------------ pintura
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget | None = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = QColor(palette.EDGE_COLOR)
        width = 1.6
        selected = self.isSelected()
        if self._highlight:
            color, width = QColor(palette.HIGHLIGHT_BORDER), 2.6
        elif selected:
            color, width = QColor(palette.EDGE_SELECTED), 3.0
        elif self._hover:
            color, width = QColor(palette.EDGE_HOVER), 2.2
        if selected:
            # Halo translúcido bajo la flecha: la selección se distingue de las demás líneas a simple vista.
            halo = QPen(QColor(palette.EDGE_SELECTED_HALO), width + 7)
            halo.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            halo.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(halo)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())
            for arrow in self._arrows:
                painter.drawPolygon(arrow)
        pen = QPen(color, width)
        pen.setJoinStyle(Qt.PenJoinStyle.MiterJoin)
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())
        painter.setPen(QPen(color, 1))
        painter.setBrush(color)
        for arrow in self._arrows:
            painter.drawPolygon(arrow)
        if selected and self.points:
            # Marcador del punto de salida (círculo claro): la punta de flecha ya marca la entrada.
            painter.setPen(QPen(color, 1.6))
            painter.setBrush(QColor(palette.SURFACE))
            painter.drawEllipse(self.points[0], ENDPOINT_R, ENDPOINT_R)
