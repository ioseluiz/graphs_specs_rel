"""Exportación de diagramas: mapa 2D y vista 3D a PNG, SVG y portapapeles."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QPointF, QRectF, QSettings, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen
from PyQt6.QtSvg import QSvgGenerator
from PyQt6.QtWidgets import QApplication, QFileDialog, QMessageBox

from config import palette
from config.settings import APP_NAME, SETTINGS_LAST_DIR
from views.components.canvas.graph_scene import GraphScene
from views.components.graph3d_widget import Graph3DWidget
from views.main_window import TAB_3D, MainWindow

MARGIN = 30.0


# ============================================================================ Mapa 2D
def render_png(scene: GraphScene, path: Path, scale: float = 3.0) -> None:
    image = _scene_image(scene, scale)
    if not image.save(str(path)):
        raise OSError(f"No se pudo guardar la imagen en {path}")


def render_svg(scene: GraphScene, path: Path) -> None:
    rect = _prepare(scene)
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setResolution(96)  # 1 unidad = 1 px de pantalla (por defecto usa 72 dpi)
    generator.setSize(rect.size().toSize())
    generator.setViewBox(rect)
    generator.setTitle("Mapa de referencias cruzadas")
    generator.setDescription(f"Generado por {APP_NAME}")
    painter = QPainter(generator)
    scene.render(painter, QRectF(rect), rect)
    painter.end()


def render_to_clipboard(scene: GraphScene, scale: float = 2.0) -> None:
    QApplication.clipboard().setImage(_scene_image(scene, scale))


def _scene_image(scene: GraphScene, scale: float) -> QImage:
    rect = _prepare(scene)
    size = (rect.size() * scale).toSize()
    image = QImage(size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.white)
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    scene.render(painter, QRectF(image.rect()), rect)
    painter.end()
    return image


def _prepare(scene: GraphScene) -> QRectF:
    scene.clearSelection()
    scene.hide_handles()
    rect = scene.content_rect()
    if rect.isNull():
        rect = QRectF(0, 0, 400, 300)
    return rect.adjusted(-MARGIN, -MARGIN, MARGIN, MARGIN)


# ============================================================================ Vista 3D
def render_3d_png(widget: Graph3DWidget, path: Path, scale: float = 2.0) -> None:
    image = widget.render_image(scale)
    if image.isNull() or not image.save(str(path)):
        raise OSError(f"No se pudo guardar la imagen 3D en {path}")


def render_3d_to_clipboard(widget: Graph3DWidget, scale: float = 2.0) -> None:
    QApplication.clipboard().setImage(widget.render_image(scale))


def render_3d_svg(widget: Graph3DWidget, path: Path) -> None:
    """SVG vectorial de la vista 3D: proyección de nodos y aristas con la cámara actual."""
    scene = widget.projected_scene()
    w, h = scene["size"]
    generator = QSvgGenerator()
    generator.setFileName(str(path))
    generator.setResolution(96)
    generator.setSize(QSize(w, h))
    generator.setViewBox(QRectF(0, 0, w, h))
    generator.setTitle("Vista 3D de referencias cruzadas")
    generator.setDescription(f"Generado por {APP_NAME}")
    painter = QPainter(generator)
    try:
        paint_projected_scene(painter, scene)
    finally:
        painter.end()


def paint_projected_scene(painter: QPainter, scene: dict) -> None:
    w, h = scene["size"]
    nodes: list[dict] = scene["nodes"]
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.fillRect(QRectF(0, 0, w, h), QColor(palette.SURFACE))
    if not nodes:
        return
    depths = [n["depth"] for n in nodes]
    d_min, d_max = min(depths), max(depths)
    span = (d_max - d_min) or 1.0

    def radius(n: dict) -> float:
        near = 1.0 - (n["depth"] - d_min) / span  # 1 = más cerca de la cámara
        return 5.0 + 6.0 * near

    edge_color = QColor(palette.EDGE_COLOR)
    # Aristas primero (de atrás hacia adelante), con el tramo final más intenso para indicar dirección.
    edges = sorted(scene["edges"], key=lambda e: -(nodes[e["a"]]["depth"] + nodes[e["b"]]["depth"]))
    for e in edges:
        a, b = nodes[e["a"]], nodes[e["b"]]
        pa, pb = QPointF(a["x"], a["y"]), QPointF(b["x"], b["y"])
        mid = pa + (pb - pa) * 0.6
        strong = 0.95 if e["visible"] else 0.08
        weak = (0.95 if e["mutual"] else 0.35) if e["visible"] else 0.08
        c1, c2 = QColor(edge_color), QColor(edge_color)
        c1.setAlphaF(weak)
        c2.setAlphaF(strong)
        painter.setPen(QPen(c1, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(pa, mid)
        painter.setPen(QPen(c2, 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(mid, pb)
    # Nodos de atrás hacia adelante.
    for n in sorted(nodes, key=lambda n: -n["depth"]):
        r = radius(n)
        fill = QColor(n["fill"])
        border = QColor(fill).darker(140)
        if not n["visible"]:
            fill.setAlphaF(0.18)
            border.setAlphaF(0.18)
        painter.setPen(QPen(border, 1.0))
        painter.setBrush(fill)
        painter.drawEllipse(QPointF(n["x"], n["y"]), r, r)
    # Etiquetas al final.
    font = QFont("Segoe UI", 8)
    painter.setFont(font)
    fm = QFontMetrics(font)
    for n in nodes:
        if not n["label"] or not n["visible"]:
            continue
        color = QColor(palette.TEXT)
        painter.setPen(color)
        painter.drawText(QPointF(n["x"] + radius(n) + 3, n["y"] - fm.descent() + fm.ascent() / 2), n["label"])


# ============================================================================ Controlador
class ExportController(QObject):
    def __init__(self, window: MainWindow, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.window = window
        window.act_export_png.triggered.connect(self.export_png)
        window.act_export_svg.triggered.connect(self.export_svg)
        window.act_copy_image.triggered.connect(self.copy_image)
        window.act_export_3d_png.triggered.connect(self.export_3d_png)
        window.act_export_3d_svg.triggered.connect(self.export_3d_svg)
        window.act_copy_3d_image.triggered.connect(self.copy_3d_image)
        window.act_export_current.triggered.connect(self.export_current)
        window.act_export_report.triggered.connect(self.export_report)
        self.project = None  # lo inyecta MainController (el reporte necesita el modelo)

    # ------------------------------------------------------------------ reporte Excel
    def export_report(self) -> None:
        import tempfile
        from datetime import datetime

        from PyQt6.QtCore import QUrl
        from PyQt6.QtGui import QDesktopServices

        from models.report_export import ReportExportError, export_report_xlsx
        from views.components.report_dialog import ReportDialog

        project = self.project
        if project is None or not project.is_open:
            return
        meta = project.meta()
        base = project.path.parent if project.path else Path(QSettings().value(SETTINGS_LAST_DIR, "", type=str))
        code = (meta.code or "proyecto").replace("/", "-").replace("\\", "-").strip() or "proyecto"
        suggested = base / f"{code}_reporte_secciones_{datetime.now():%Y%m%d}.xlsx"
        dialog = ReportDialog(suggested, self.window)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        path, include_map, open_after = dialog.result()
        map_png: Path | None = None
        if include_map:
            map_png = Path(tempfile.gettempdir()) / f"specrel_mapa_{datetime.now():%Y%m%d%H%M%S}.png"
            grid = self.window.scene.grid_visible
            try:
                self.window.scene.grid_visible = False
                render_png(self.window.scene, map_png, scale=1.5)
            except OSError:
                map_png = None
            finally:
                self.window.scene.grid_visible = grid
                self.window.scene.update()
        try:
            stats = export_report_xlsx(project, path, map_png)
        except ReportExportError as exc:
            QMessageBox.critical(self.window, "Reporte de secciones", str(exc))
            return
        finally:
            if map_png is not None:
                try:
                    map_png.unlink()
                except OSError:
                    pass
        QSettings().setValue(SETTINGS_LAST_DIR, str(path.parent))
        self.window.show_status(
            f"Reporte generado: {stats.sections} secciones, {stats.relations} relaciones, avance promedio "
            f"{stats.avg_progress:.0f} % → {path}", 10000)
        if open_after:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path)))

    # ------------------------------------------------------------------ utilidades
    def _ask_path(self, title: str, filter_: str, suffix: str, default_name: str) -> Path | None:
        settings = QSettings()
        start = settings.value(SETTINGS_LAST_DIR, "", type=str)
        path, _ = QFileDialog.getSaveFileName(self.window, title, str(Path(start) / default_name), filter_)
        if not path:
            return None
        p = Path(path)
        if p.suffix.lower() != suffix:
            p = p.with_suffix(suffix)
        settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        return p

    def _run_2d(self, fn: Callable, path: Path, what: str) -> None:
        scene = self.window.scene
        grid = scene.grid_visible
        try:
            scene.grid_visible = False
            fn(scene, path)
            self.window.show_status(f"{what} exportado: {path}")
        except OSError as exc:
            QMessageBox.critical(self.window, "Exportar", str(exc))
        finally:
            scene.grid_visible = grid
            scene.update()

    def _run_3d(self, fn: Callable, path: Path | None, what: str) -> None:
        widget = self.window.view3d
        if not widget.available:
            QMessageBox.warning(self.window, "Exportar vista 3D",
                                "La vista 3D no está disponible en este equipo (OpenGL).")
            return
        if self.window.tabs.currentIndex() != TAB_3D:
            # La cámara y el tamaño dependen del widget visible: mostrar la pestaña antes de capturar.
            self.window.tabs.setCurrentIndex(TAB_3D)
            QApplication.processEvents()
        try:
            fn(widget, path) if path is not None else fn(widget)
            self.window.show_status(f"{what} listo{': ' + str(path) if path else '.'}")
        except (OSError, RuntimeError) as exc:
            QMessageBox.critical(self.window, "Exportar vista 3D", str(exc))

    # ------------------------------------------------------------------ 2D
    def export_png(self) -> None:
        path = self._ask_path("Exportar mapa 2D como PNG", "Imagen PNG (*.png)", ".png", "mapa_2d.png")
        if path:
            self._run_2d(render_png, path, "Mapa 2D (PNG)")

    def export_svg(self) -> None:
        path = self._ask_path("Exportar mapa 2D como SVG", "Gráfico vectorial (*.svg)", ".svg", "mapa_2d.svg")
        if path:
            self._run_2d(render_svg, path, "Mapa 2D (SVG)")

    def copy_image(self) -> None:
        scene = self.window.scene
        grid = scene.grid_visible
        try:
            scene.grid_visible = False
            render_to_clipboard(scene)
            self.window.show_status("Mapa 2D copiado al portapapeles.")
        finally:
            scene.grid_visible = grid
            scene.update()

    # ------------------------------------------------------------------ 3D
    def export_3d_png(self) -> None:
        path = self._ask_path("Exportar vista 3D como PNG", "Imagen PNG (*.png)", ".png", "vista_3d.png")
        if path:
            self._run_3d(render_3d_png, path, "Vista 3D (PNG)")

    def export_3d_svg(self) -> None:
        path = self._ask_path("Exportar vista 3D como SVG", "Gráfico vectorial (*.svg)", ".svg", "vista_3d.svg")
        if path:
            self._run_3d(render_3d_svg, path, "Vista 3D (SVG)")

    def copy_3d_image(self) -> None:
        self._run_3d(render_3d_to_clipboard, None, "Vista 3D copiada al portapapeles")

    # ------------------------------------------------------------------ vista actual
    def export_current(self) -> None:
        """Botón de la barra: exporta la pestaña visible (3D si está activa; si no, el mapa 2D)."""
        if self.window.tabs.currentIndex() == TAB_3D:
            self.export_3d_png()
        else:
            self.export_png()
