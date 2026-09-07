"""Vista 3D del grafo con pyqtgraph.opengl (carga perezosa y fallback sin OpenGL)."""
from __future__ import annotations

import os
from typing import Any

import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from config import palette

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

MAX_AUTO_LABELS = 15
MAX_ALL_LABELS = 200   # «Mostrar todas las etiquetas»: cada GLTextItem cuesta; por encima se etiquetan las de mayor grado


def choose_label_indices(degrees: list[int], show_all: bool, highlight_idx: set[int] | None,
                         max_auto: int = MAX_AUTO_LABELS, max_all: int = MAX_ALL_LABELS) -> set[int]:
    """Índices de nodos a etiquetar (función pura, probada aparte).

    - Sin «todas»: las `max_auto` de mayor grado; con resaltado, solo las resaltadas (todas ellas).
    - Con «todas»: todas si caben en `max_all`; si no, las `max_all` de mayor grado (más las resaltadas).
    """
    n = len(degrees)
    order = sorted(range(n), key=lambda i: -degrees[i])
    if show_all:
        chosen = set(range(n)) if n <= max_all else set(order[:max_all])
        if highlight_idx is not None:
            chosen |= set(highlight_idx)
        return chosen
    chosen = set(order[:max_auto])
    if highlight_idx is not None:
        chosen = {i for i in chosen if i in highlight_idx} | set(highlight_idx)
    return chosen


def _rgba(hex_color: str, alpha: float) -> tuple[float, float, float, float]:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return r, g, b, alpha


class Graph3DWidget(QWidget):
    recalcRequested = pyqtSignal()
    nodeLabelsToggled = pyqtSignal(bool)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._gl: Any = None
        self._view: Any = None
        self._scatter: Any = None
        self._lines: Any = None
        self._grid: Any = None
        self._text_items: list[Any] = []
        self._gl_failed = False
        self._data: dict[str, Any] | None = None
        self._highlight: set[int] | None = None
        self._status = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        bar = QHBoxLayout()
        bar.setContentsMargins(8, 6, 8, 0)
        self.recalc_button = QPushButton("Recalcular disposición")
        self.recalc_button.setProperty("role", "secondary")
        self.reset_button = QPushButton("Restablecer vista")
        self.reset_button.setProperty("role", "secondary")
        self.labels_check = QCheckBox("Mostrar todas las etiquetas")
        self.info_label = QLabel("")
        self.info_label.setProperty("role", "hint")
        bar.addWidget(self.recalc_button)
        bar.addWidget(self.reset_button)
        bar.addWidget(self.labels_check)
        bar.addStretch(1)
        bar.addWidget(self.info_label)
        layout.addLayout(bar)

        self.stack = QStackedWidget()
        self.fallback = QLabel(
            "La vista 3D no está disponible en este equipo (OpenGL no se pudo inicializar).\n"
            "Pruebe definir OPENGL_SOFTWARE=true en el archivo .env o actualice los controladores gráficos."
        )
        self.fallback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.fallback.setWordWrap(True)
        self.fallback.setProperty("role", "subtitle")
        self.stack.addWidget(self.fallback)
        layout.addWidget(self.stack, 1)

        self.recalc_button.clicked.connect(self.recalcRequested)
        self.reset_button.clicked.connect(self.reset_camera)
        self.labels_check.toggled.connect(self._on_labels_toggled)
        # Crear el widget OpenGL de inmediato: si se crea con la ventana ya visible, Qt en Windows
        # recrea la ventana nativa y se percibe un parpadeo al abrir la pestaña 3D por primera vez.
        self.ensure_gl()

    # ------------------------------------------------------------------ OpenGL
    @property
    def available(self) -> bool:
        return self._view is not None

    def ensure_gl(self) -> bool:
        if self._view is not None:
            return True
        if self._gl_failed:
            return False
        try:
            import pyqtgraph.opengl as gl  # import perezoso: puede fallar sin OpenGL

            view = gl.GLViewWidget()
            view.setBackgroundColor(palette.SURFACE)
            view.opts["distance"] = 40
            view.opts["elevation"] = 25
            view.opts["azimuth"] = 45
            grid = gl.GLGridItem()
            grid.setSize(30, 30)
            grid.setSpacing(2, 2)
            grid.translate(0, 0, -12)
            grid.setColor((200, 208, 218, 90))
            view.addItem(grid)
            self._gl, self._view, self._grid = gl, view, grid
            self.stack.addWidget(view)
            self.stack.setCurrentWidget(view)
            return True
        except Exception as exc:  # noqa: BLE001 - cualquier fallo de OpenGL degrada a fallback
            self._gl_failed = True
            self.fallback.setText(self.fallback.text() + f"\n\nDetalle: {exc}")
            self.stack.setCurrentWidget(self.fallback)
            return False

    def reset_camera(self) -> None:
        """Encuadra la cámara sobre el centroide del grafo a una distancia acorde a su extensión."""
        if self._view is None:
            return
        center = (0.0, 0.0, 0.0)
        distance = 40.0
        if self._data is not None and len(self._data["ids"]):
            pos = self._data["pos"]
            lo, hi = pos.min(axis=0), pos.max(axis=0)
            center = tuple(float(v) for v in (lo + hi) / 2)
            extent = float(np.max(hi - lo)) or 1.0
            distance = max(12.0, extent * 2.2)
        try:
            from pyqtgraph import Vector

            self._view.opts["center"] = Vector(*center)
        except Exception:  # noqa: BLE001
            pass
        if self._grid is not None:
            self._grid.resetTransform()
            self._grid.translate(center[0], center[1], center[2] - distance * 0.35)
        self._view.setCameraPosition(distance=distance, elevation=25, azimuth=45)
        self._view.update()

    # ------------------------------------------------------------------ datos
    def set_graph(
        self,
        node_ids: list[int],
        positions: np.ndarray,          # (N, 3)
        fills: list[str],
        edges: np.ndarray,              # (E, 2) índices en node_ids
        mutual: np.ndarray,             # (E,) bool
        labels: list[str],
        degrees: list[int],
    ) -> None:
        first_time = self._data is None or len(self._data["ids"]) == 0
        self._data = {
            "ids": node_ids, "pos": positions, "fills": fills, "edges": edges,
            "mutual": mutual, "labels": labels, "degrees": degrees,
        }
        self._status = ""
        self._update_info()
        self._render()
        if first_time:
            self.reset_camera()

    def set_status(self, text: str) -> None:
        """Mensaje transitorio en la barra de la vista (p. ej. «Calculando disposición 3D…»)."""
        self._status = text
        self._update_info()

    def _update_info(self) -> None:
        parts: list[str] = []
        if self._data is not None:
            n, e = len(self._data["ids"]), len(self._data["edges"])
            parts.append(f"{n} secciones · {e} relaciones")
            if self.labels_check.isChecked() and n > MAX_ALL_LABELS:
                parts.append(f"etiquetas: las {MAX_ALL_LABELS} de mayor grado")
        if getattr(self, "_status", ""):
            parts.append(self._status)
        self.info_label.setText(" · ".join(parts))

    def set_highlight(self, node_ids: set[int] | None) -> None:
        self._highlight = set(node_ids) if node_ids else None
        self._render()

    def clear_graph(self) -> None:
        self._data = None
        self._render()

    # ------------------------------------------------------------------ render
    def _render(self) -> None:
        if not self.ensure_gl():
            return
        gl, view = self._gl, self._view
        for item in (self._scatter, self._lines, *self._text_items):
            if item is not None:
                try:
                    view.removeItem(item)
                except ValueError:
                    pass
        self._scatter = self._lines = None
        self._text_items = []
        data = self._data
        if not data or len(data["ids"]) == 0:
            view.update()
            return

        ids: list[int] = data["ids"]
        pos: np.ndarray = data["pos"].astype(np.float32)
        index_of = {sid: i for i, sid in enumerate(ids)}
        hl = self._highlight

        colors = np.zeros((len(ids), 4), dtype=np.float32)
        sizes = np.full(len(ids), 20.0, dtype=np.float32)
        for i, (sid, fill) in enumerate(zip(ids, data["fills"])):
            alpha = 1.0 if (hl is None or sid in hl) else 0.18
            colors[i] = _rgba(fill, alpha)
            if hl is not None and sid in hl:
                sizes[i] = 26.0
        self._scatter = gl.GLScatterPlotItem(pos=pos, color=colors, size=sizes, pxMode=True)
        self._scatter.setGLOptions("translucent")
        view.addItem(self._scatter)

        edges: np.ndarray = data["edges"]
        if len(edges):
            seg = np.zeros((len(edges) * 2, 3), dtype=np.float32)
            seg_col = np.zeros((len(edges) * 2, 4), dtype=np.float32)
            base = _rgba(palette.EDGE_COLOR, 1.0)
            for k, (a, b) in enumerate(edges):
                seg[2 * k] = pos[a]
                seg[2 * k + 1] = pos[b]
                visible = hl is None or (ids[a] in hl and ids[b] in hl)
                strong = 0.95 if visible else 0.06
                weak = (0.95 if data["mutual"][k] else 0.30) if visible else 0.06
                seg_col[2 * k] = (*base[:3], weak)       # origen tenue → destino fuerte (dirección)
                seg_col[2 * k + 1] = (*base[:3], strong)
            self._lines = gl.GLLinePlotItem(pos=seg, color=seg_col, width=2.0, mode="lines", antialias=True)
            self._lines.setGLOptions("translucent")
            view.addItem(self._lines)

        label_idx = self._label_indices()
        text_cls = getattr(gl, "GLTextItem", None)
        if text_cls is not None:
            from PyQt6.QtGui import QFont

            font = QFont("Segoe UI", 8)
            for i in label_idx:
                item = text_cls(pos=pos[i] + np.array([0.0, 0.0, 0.35], dtype=np.float32),
                                text=data["labels"][i], color=palette.TEXT, font=font)
                view.addItem(item)
                self._text_items.append(item)
        view.update()

    def _on_labels_toggled(self, on: bool) -> None:
        self.nodeLabelsToggled.emit(on)
        self._update_info()
        self._render()

    # ------------------------------------------------------------------ exportación
    def _label_indices(self) -> set[int]:
        data = self._data
        if not data:
            return set()
        ids = data["ids"]
        highlight_idx = None
        if self._highlight is not None:
            index_of = {sid: i for i, sid in enumerate(ids)}
            highlight_idx = {index_of[s] for s in self._highlight if s in index_of}
        return choose_label_indices(list(data["degrees"]), self.labels_check.isChecked(), highlight_idx)

    def render_image(self, scale: float = 2.0):
        """Imagen (QImage) de la vista 3D con la cámara actual, a `scale` veces la resolución."""
        from PyQt6.QtGui import QImage

        if not self.ensure_gl():
            raise RuntimeError("La vista 3D no está disponible en este equipo.")
        from PyQt6.QtCore import QPointF
        from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter

        view = self._view
        w = max(1, int(view.width() * scale))
        h = max(1, int(view.height() * scale))
        # Los tamaños en píxeles (pxMode) no crecen con la resolución: escalarlos durante el render.
        scatter_sizes = None
        if self._scatter is not None and scale != 1.0:
            scatter_sizes = np.array(self._scatter.size, dtype=np.float32)
            self._scatter.setData(size=scatter_sizes * scale)
        if self._lines is not None and scale != 1.0:
            self._lines.setData(width=2.0 * scale)
        try:
            from PyQt6.QtWidgets import QApplication

            if QApplication.platformName() == "offscreen":
                # Sin OpenGL real el render a framebuffer externo aborta el proceso: usar la captura simple.
                raise RuntimeError("plataforma offscreen")
            arr = view.renderToArray((w, h))  # (h, w, 4) BGRA, ya con el origen arriba-izquierda
            bgra = np.ascontiguousarray(arr)
            image = QImage(bgra.data, w, h, w * 4, QImage.Format.Format_ARGB32).copy()
            if image.isNull():
                raise ValueError("render vacío")
        except Exception:  # noqa: BLE001 - algunos drivers no soportan renderToArray
            image = view.grabFramebuffer()
            scale = image.width() / max(1, view.width())
        finally:
            if scatter_sizes is not None:
                self._scatter.setData(size=scatter_sizes)
            if self._lines is not None:
                self._lines.setData(width=2.0)
        # Las etiquetas (GLTextItem) no se dibujan en el render fuera de pantalla: superponerlas.
        scene = self.projected_scene()
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        font = QFont("Segoe UI")
        font.setPointSizeF(8 * scale)
        painter.setFont(font)
        fm = QFontMetrics(font)
        painter.setPen(QColor(palette.TEXT))
        for n in scene["nodes"]:
            if n["label"] and n["visible"]:
                x, y = n["x"] * scale + 12 * scale, n["y"] * scale - 8 * scale
                painter.drawText(QPointF(x, y + fm.ascent() / 2), n["label"])
        painter.end()
        return image

    def projected_scene(self) -> dict[str, Any]:
        """Proyección 2D de la escena con la cámara actual, para exportar a SVG.

        Devuelve: size (w, h), nodes [(x, y, depth, fill, label|None, section_id)], edges [(i, j, mutual, visible)].
        """
        from PyQt6.QtGui import QVector4D

        if not self.ensure_gl():
            raise RuntimeError("La vista 3D no está disponible en este equipo.")
        data = self._data or {"ids": [], "pos": np.zeros((0, 3)), "fills": [], "edges": np.zeros((0, 2), int),
                              "mutual": np.zeros(0, bool), "labels": [], "degrees": []}
        view = self._view
        w, h = max(1, view.width()), max(1, view.height())
        try:  # pyqtgraph >= 0.14 exige región y viewport explícitos
            vp = view.getViewport()
            proj = view.projectionMatrix(vp, vp)
        except TypeError:
            proj = view.projectionMatrix()
        matrix = proj * view.viewMatrix()
        label_idx = self._label_indices()
        hl = self._highlight
        nodes = []
        for i, sid in enumerate(data["ids"]):
            x, y, z = (float(v) for v in data["pos"][i])
            clip = matrix.map(QVector4D(x, y, z, 1.0))
            if abs(clip.w()) < 1e-9:
                continue
            ndc_x, ndc_y, depth = clip.x() / clip.w(), clip.y() / clip.w(), clip.z() / clip.w()
            px, py = (ndc_x + 1) / 2 * w, (1 - ndc_y) / 2 * h
            visible = hl is None or sid in hl
            nodes.append({
                "x": px, "y": py, "depth": depth, "fill": data["fills"][i],
                "label": data["labels"][i] if i in label_idx else None,
                "section_id": sid, "visible": visible,
            })
        edges = []
        for k, (a, b) in enumerate(data["edges"]):
            ids = data["ids"]
            visible = hl is None or (ids[a] in hl and ids[b] in hl)
            edges.append({"a": int(a), "b": int(b), "mutual": bool(data["mutual"][k]), "visible": visible})
        return {"size": (w, h), "nodes": nodes, "edges": edges}
