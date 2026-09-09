"""Vista del mapa: zoom, pan, selección rectangular, modo conectar y menús contextuales."""
from __future__ import annotations

from PyQt6.QtCore import QPoint, QPointF, Qt, pyqtSignal
from PyQt6.QtGui import QContextMenuEvent, QKeyEvent, QMouseEvent, QPainter, QWheelEvent
from PyQt6.QtWidgets import QGraphicsView

from views.components.canvas.graph_scene import GraphScene
from views.components.canvas.relation_edge_item import RelationEdgeItem
from views.components.canvas.section_node_item import SectionNodeItem
from views.components.canvas.temp_edge_item import TempEdgeItem

MIN_SCALE, MAX_SCALE = 0.1, 4.0


MIME_SECTION = "application/x-specrel-section"


class GraphView(QGraphicsView):
    connectModeChanged = pyqtSignal(bool)
    zoomChanged = pyqtSignal(float)
    sectionsDropped = pyqtSignal(object, object)  # list[code_key], QPointF (escena)
    filesDropped = pyqtSignal(list)                # rutas locales soltadas sobre el mapa (las trata la ventana)
    invertRequested = pyqtSignal(int)              # relation_id (tecla R sobre una flecha seleccionada)

    def __init__(self, scene: GraphScene, parent=None) -> None:
        super().__init__(scene, parent)
        self.graph_scene = scene
        self.setRenderHints(
            QPainter.RenderHint.Antialiasing
            | QPainter.RenderHint.TextAntialiasing
            | QPainter.RenderHint.SmoothPixmapTransform
        )
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        # La rejilla del fondo se dibuja línea a línea: cachearla evita redibujarla en cada paneo.
        self.setCacheMode(QGraphicsView.CacheModeFlag.CacheBackground)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self._connect_mode = False
        self._panning = False
        self._pan_start = QPoint()
        self._space_held = False
        self._temp_edge: TempEdgeItem | None = None
        self._connect_source: SectionNodeItem | None = None
        self.setAcceptDrops(True)

    # ------------------------------------------------------------------ arrastre desde el catálogo
    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME_SECTION) or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME_SECTION) or event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasFormat(MIME_SECTION):
            raw = bytes(event.mimeData().data(MIME_SECTION)).decode("utf-8")
            keys = [k for k in raw.split(";") if k]
            self.sectionsDropped.emit(keys, self.mapToScene(event.position().toPoint()))
            event.acceptProposedAction()
            return
        if event.mimeData().hasUrls():
            # Un hijo que acepta drops no los propaga a la ventana: se reenvían explícitamente.
            paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
            if paths:
                event.acceptProposedAction()
                self.filesDropped.emit(paths)
                return
        super().dropEvent(event)

    # ------------------------------------------------------------------ modo conectar
    @property
    def connect_mode(self) -> bool:
        return self._connect_mode

    def set_connect_mode(self, on: bool) -> None:
        if self._connect_mode == on:
            return
        self._connect_mode = on
        self._cancel_connect()
        self.setDragMode(QGraphicsView.DragMode.NoDrag if on else QGraphicsView.DragMode.RubberBandDrag)
        self.viewport().setCursor(Qt.CursorShape.CrossCursor if on else Qt.CursorShape.ArrowCursor)
        self.connectModeChanged.emit(on)

    def _start_connect(self, node: SectionNodeItem, scene_pos: QPointF) -> None:
        self._connect_source = node
        self._temp_edge = TempEdgeItem(node.scene_rect().center())
        self._temp_edge.set_end(scene_pos)
        self.graph_scene.addItem(self._temp_edge)

    def _cancel_connect(self) -> None:
        if self._temp_edge is not None and self._temp_edge.scene() is not None:
            self.graph_scene.removeItem(self._temp_edge)
        self._temp_edge = None
        self._connect_source = None

    # ------------------------------------------------------------------ zoom / encuadre
    def current_scale(self) -> float:
        return self.transform().m11()

    def zoom_by(self, factor: float) -> None:
        new_scale = self.current_scale() * factor
        if new_scale < MIN_SCALE:
            factor = MIN_SCALE / self.current_scale()
        elif new_scale > MAX_SCALE:
            factor = MAX_SCALE / self.current_scale()
        self.scale(factor, factor)
        self.zoomChanged.emit(self.current_scale())

    def zoom_in(self) -> None:
        self.zoom_by(1.2)

    def zoom_out(self) -> None:
        self.zoom_by(1 / 1.2)

    def reset_zoom(self) -> None:
        self.resetTransform()
        self.zoomChanged.emit(1.0)

    def fit_all(self) -> None:
        rect = self.graph_scene.content_rect()
        if rect.isNull():
            self.reset_zoom()
            self.centerOn(0, 0)
            return
        self.fitInView(rect.adjusted(-40, -40, 40, 40), Qt.AspectRatioMode.KeepAspectRatio)
        if self.current_scale() > 1.5:
            self.resetTransform()
            self.scale(1.5, 1.5)
            self.centerOn(rect.center())
        self.zoomChanged.emit(self.current_scale())

    def center_on_node(self, section_id: int) -> None:
        node = self.graph_scene.nodes.get(section_id)
        if node is not None:
            self.centerOn(node)

    # ------------------------------------------------------------------ eventos
    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta == 0:
            return
        self.zoom_by(1.15 ** (delta / 120))
        event.accept()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_held
        ):
            self._panning = True
            self._pan_start = event.pos()
            self.viewport().setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton:
            scene_pos = self.mapToScene(event.pos())
            node = self.graph_scene.node_at(scene_pos)
            alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
            if node is not None and (self._connect_mode or alt):
                self._start_connect(node, scene_pos)
                event.accept()
                return
            if self._connect_mode:
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._temp_edge is not None:
            self._temp_edge.set_end(self.mapToScene(event.pos()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._panning and event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.LeftButton):
            self._panning = False
            self.viewport().setCursor(
                Qt.CursorShape.CrossCursor if self._connect_mode else Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        if self._temp_edge is not None and event.button() == Qt.MouseButton.LeftButton:
            source = self._connect_source
            target = self.graph_scene.node_at(self.mapToScene(event.pos()))
            self._cancel_connect()
            if source is not None and target is not None and target is not source:
                self.graph_scene.connectRequested.emit(source.section_id, target.section_id)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = True
            self.viewport().setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            if self._temp_edge is not None:
                self._cancel_connect()
            elif self._connect_mode:
                self.set_connect_mode(False)
            else:
                self.graph_scene.clearSelection()
            event.accept()
            return
        if event.key() == Qt.Key.Key_R and not event.modifiers():
            edges = self.graph_scene.selected_edge_ids()
            if edges:
                for rid in edges:
                    self.invertRequested.emit(rid)
                event.accept()
                return
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            step = 10.0 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1.0
            dx = {Qt.Key.Key_Left: -step, Qt.Key.Key_Right: step}.get(event.key(), 0.0)
            dy = {Qt.Key.Key_Up: -step, Qt.Key.Key_Down: step}.get(event.key(), 0.0)
            moved: dict[int, tuple[float, float]] = {}
            for item in self.graph_scene.selectedItems():
                if isinstance(item, SectionNodeItem):
                    item.setPos(item.pos().x() + dx, item.pos().y() + dy)
                    moved[item.section_id] = (item.pos().x(), item.pos().y())
            if moved:
                self.graph_scene.nodesMoved.emit(moved)
                event.accept()
                return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Space and not event.isAutoRepeat():
            self._space_held = False
            if not self._panning:
                self.viewport().setCursor(
                    Qt.CursorShape.CrossCursor if self._connect_mode else Qt.CursorShape.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        scene_pos = self.mapToScene(event.pos())
        for item in self.graph_scene.items(scene_pos):
            if isinstance(item, SectionNodeItem):
                if not item.isSelected():
                    self.graph_scene.clearSelection()
                    item.setSelected(True)
                self.graph_scene.nodeContextMenu.emit(item.section_id, event.globalPos())
                return
            if isinstance(item, RelationEdgeItem):
                if not item.isSelected():
                    self.graph_scene.clearSelection()
                    item.setSelected(True)
                self.graph_scene.edgeContextMenu.emit(item.relation_id, event.globalPos())
                return
        self.graph_scene.canvasContextMenu.emit(scene_pos, event.globalPos())
