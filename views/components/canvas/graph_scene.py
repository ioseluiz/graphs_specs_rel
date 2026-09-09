"""Escena del mapa: registro id -> item y señales de interacción hacia el controlador."""
from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QGraphicsScene, QGraphicsSceneMouseEvent

from config import palette
from models.entities import RelationKind, Side
from views.components.canvas.relation_edge_item import RelationEdgeItem
from views.components.canvas.section_node_item import SectionNodeItem

GRID = 20


class GraphScene(QGraphicsScene):
    nodesMoved = pyqtSignal(object)            # dict[int, tuple[float, float]]
    connectRequested = pyqtSignal(int, int)    # source_section_id, target_section_id
    edgeGeometryChanged = pyqtSignal(int, object, object, object)  # rid, waypoints|None, sport, tport
    nodeDoubleClicked = pyqtSignal(int)
    nodeContextMenu = pyqtSignal(int, object)    # section_id, QPoint (global)
    edgeContextMenu = pyqtSignal(int, object)    # relation_id, QPoint (global)
    canvasContextMenu = pyqtSignal(object, object)  # QPointF scene, QPoint global

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.nodes: dict[int, SectionNodeItem] = {}
        self.edges: dict[int, RelationEdgeItem] = {}
        self.snap_enabled = False
        self.grid_visible = True
        self.show_extras = True   # responsables y avance en los nodos
        self._press_positions: dict[int, QPointF] = {}
        self.setBackgroundBrush(QColor(palette.CANVAS_BACKGROUND))
        self.setItemIndexMethod(QGraphicsScene.ItemIndexMethod.BspTreeIndex)
        self.setSceneRect(QRectF(-2000, -2000, 4000, 4000))
        self.selectionChanged.connect(self._sync_linked)

    def _sync_linked(self) -> None:
        """Marca como «vinculadas» las secciones en los extremos de las flechas seleccionadas."""
        linked: set[int] = set()
        for item in self.selectedItems():
            if isinstance(item, RelationEdgeItem):
                linked.add(item.source.section_id)
                linked.add(item.target.section_id)
        for sid, node in self.nodes.items():
            node.set_linked(sid in linked)

    # ------------------------------------------------------------------ nodos
    def add_node(self, section_id: int, code: str, title: str, fill: str, border: str,
                 x: float, y: float) -> SectionNodeItem:
        node = SectionNodeItem(section_id, code, title, fill, border)
        node.set_show_extras(self.show_extras)
        node.setPos(x, y)
        self.addItem(node)
        self.nodes[section_id] = node
        self.grow_scene_rect_to(node.sceneBoundingRect())  # O(1): no recorre toda la escena por nodo
        return node

    def update_node(self, section_id: int, code: str, title: str, fill: str, border: str) -> None:
        node = self.nodes.get(section_id)
        if node is not None:
            node.set_data(code, title, fill, border)

    def set_node_extras(self, section_id: int, status_name: str, status_color: str | None, progress: int,
                        responsibles: list[tuple[str, str]]) -> None:
        node = self.nodes.get(section_id)
        if node is not None:
            node.set_extras(status_name, status_color, progress, responsibles, self.show_extras)

    def set_show_extras(self, show: bool) -> None:
        self.show_extras = show
        for node in self.nodes.values():
            node.set_show_extras(show)
        self.update()

    def set_node_pos(self, section_id: int, x: float, y: float) -> None:
        node = self.nodes.get(section_id)
        if node is None:
            return
        if abs(node.pos().x() - x) > 0.01 or abs(node.pos().y() - y) > 0.01:
            node.setPos(x, y)
            self.grow_scene_rect_to(node.sceneBoundingRect())

    def remove_node(self, section_id: int) -> None:
        node = self.nodes.pop(section_id, None)
        if node is None:
            return
        for edge in node.edges:
            self.remove_edge(edge.relation_id)
        self.removeItem(node)

    # ------------------------------------------------------------------ aristas
    def add_edge(self, relation_id: int, source_id: int, target_id: int, kind: RelationKind,
                 waypoints: list[tuple[float, float]] | None, source_port: Side | None,
                 target_port: Side | None) -> RelationEdgeItem | None:
        src, tgt = self.nodes.get(source_id), self.nodes.get(target_id)
        if src is None or tgt is None:
            return None
        edge = RelationEdgeItem(relation_id, src, tgt, kind, waypoints, source_port, target_port)
        self.addItem(edge)
        self.edges[relation_id] = edge
        return edge

    def update_edge(self, relation_id: int, source_id: int, target_id: int, kind: RelationKind,
                    waypoints: list[tuple[float, float]] | None, source_port: Side | None,
                    target_port: Side | None) -> None:
        edge = self.edges.get(relation_id)
        if edge is None:
            self.add_edge(relation_id, source_id, target_id, kind, waypoints, source_port, target_port)
            return
        src, tgt = self.nodes.get(source_id), self.nodes.get(target_id)
        if src is None or tgt is None:
            self.remove_edge(relation_id)
            return
        if edge.source is not src or edge.target is not tgt:
            edge.rebind(src, tgt)
        edge.kind = kind
        edge.set_geometry(waypoints, source_port, target_port)

    def remove_edge(self, relation_id: int) -> None:
        edge = self.edges.pop(relation_id, None)
        if edge is None:
            return
        edge.detach()
        self.removeItem(edge)

    def clear_all(self) -> None:
        for rid in list(self.edges):
            self.remove_edge(rid)
        for sid in list(self.nodes):
            self.remove_node(sid)
        self.clear()
        self.nodes.clear()
        self.edges.clear()

    # ------------------------------------------------------------------ resaltado
    def apply_highlight(self, node_ids: set[int], edge_ids: set[int], focus_id: int | None = None) -> None:
        for sid, node in self.nodes.items():
            node.set_dimmed(sid not in node_ids)
            node.set_highlight(sid == focus_id)
        for rid, edge in self.edges.items():
            edge.set_dimmed(rid not in edge_ids)
            edge.set_highlight(False)

    def clear_highlight(self) -> None:
        for node in self.nodes.values():
            node.set_dimmed(False)
            node.set_highlight(False)
        for edge in self.edges.values():
            edge.set_dimmed(False)
            edge.set_highlight(False)

    def hide_handles(self) -> None:
        for edge in self.edges.values():
            edge.show_handles(False)

    # ------------------------------------------------------------------ utilidades
    def content_rect(self) -> QRectF:
        rect = QRectF()
        for node in self.nodes.values():
            rect = rect.united(node.sceneBoundingRect())
        for edge in self.edges.values():
            rect = rect.united(edge.sceneBoundingRect())
        return rect

    def grow_scene_rect(self) -> None:
        content = self.content_rect()
        if content.isNull():
            return
        self.grow_scene_rect_to(content)

    def grow_scene_rect_to(self, rect: QRectF) -> None:
        """Amplía el rectángulo de la escena para contener `rect` con margen (nunca lo reduce)."""
        if rect.isNull():
            return
        margin = 800
        wanted = rect.adjusted(-margin, -margin, margin, margin)
        if not self.sceneRect().contains(wanted):
            self.setSceneRect(self.sceneRect().united(wanted))

    def node_at(self, pos: QPointF) -> SectionNodeItem | None:
        for item in self.items(pos):
            if isinstance(item, SectionNodeItem):
                return item
        return None

    def selected_node_ids(self) -> list[int]:
        return [i.section_id for i in self.selectedItems() if isinstance(i, SectionNodeItem)]

    def selected_edge_ids(self) -> list[int]:
        return [i.relation_id for i in self.selectedItems() if isinstance(i, RelationEdgeItem)]

    # ------------------------------------------------------------------ eventos
    def mousePressEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_positions = {
                i.section_id: QPointF(i.pos())
                for i in self.selectedItems() if isinstance(i, SectionNodeItem)
            }

    def mouseReleaseEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        super().mouseReleaseEvent(event)
        if event.button() != Qt.MouseButton.LeftButton or not self._press_positions:
            return
        moved: dict[int, tuple[float, float]] = {}
        for sid, before in self._press_positions.items():
            node = self.nodes.get(sid)
            if node is None:
                continue
            if abs(node.pos().x() - before.x()) > 0.01 or abs(node.pos().y() - before.y()) > 0.01:
                moved[sid] = (node.pos().x(), node.pos().y())
        self._press_positions = {}
        if moved:
            self.grow_scene_rect()
            self.nodesMoved.emit(moved)

    def mouseDoubleClickEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        node = self.node_at(event.scenePos())
        if node is not None:
            self.nodeDoubleClicked.emit(node.section_id)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        if not self.grid_visible:
            return
        painter.setPen(QPen(QColor(palette.CANVAS_GRID), 0))
        left = int(rect.left()) - (int(rect.left()) % GRID)
        top = int(rect.top()) - (int(rect.top()) % GRID)
        x = left
        while x < rect.right():
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += GRID
        y = top
        while y < rect.bottom():
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += GRID
