"""Genera las imágenes del manual (assets/help/img) a partir del proyecto de demostración.

Uso: python scripts/help_screenshots.py   (requiere plataforma gráfica real, no offscreen)
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

from PyQt6.QtCore import QCoreApplication, QPointF, QRectF, Qt  # noqa: E402

QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from PyQt6.QtGui import QImage, QPainter  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from controllers.main_controller import MainController  # noqa: E402
from models.master_catalog import MasterCatalog  # noqa: E402
from models.masterformat_tree_model import MasterFormatTreeModel  # noqa: E402
from models.project_model import ProjectModel  # noqa: E402
from models.relations_table_model import RelationsTableModel  # noqa: E402
from models.section_completer_model import SectionCompleterModel  # noqa: E402
from scripts.make_demo import build  # noqa: E402
from views.components.canvas.temp_edge_item import TempEdgeItem  # noqa: E402
from views.main_window import TAB_ANALYSIS, TAB_MAP, TAB_SECTIONS, MainWindow  # noqa: E402

OUT = ROOT / "assets" / "help" / "img"
MAX_W = 700  # el visor del manual no escala imágenes: limitar el ancho para que quepan sin desplazar


def save_fit(image: QImage, path: Path) -> None:
    if image.width() > MAX_W:
        image = image.scaledToWidth(MAX_W, Qt.TransformationMode.SmoothTransformation)
    image.save(str(path))


def render_scene(scene, path: Path, scale: float = 1.0) -> None:
    grid = scene.grid_visible
    scene.grid_visible = False
    rect = scene.content_rect().adjusted(-30, -30, 30, 30)
    scale = min(scale, MAX_W / rect.width())
    img = QImage(int(rect.width() * scale), int(rect.height() * scale), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    scene.render(p, QRectF(img.rect()), rect)
    p.end()
    scene.grid_visible = grid
    save_fit(img, path)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyleSheet((ROOT / "views/styles/theme.qss").read_text(encoding="utf-8"))
    demo = Path(tempfile.gettempdir()) / "specrel_help_demo.specrel"
    if demo.exists():
        demo.unlink()
    build(demo).close()

    master = MasterCatalog()
    project = ProjectModel(master=master)
    tm, cm = RelationsTableModel(project), SectionCompleterModel()
    w = MainWindow(tm, cm, MasterFormatTreeModel(master))
    c = MainController(project, w, tm, cm)
    w.resize(1500, 900)
    w.show()
    project.open_project(demo)
    app.processEvents()

    by = {s.code: s for s in project.sections()}
    sts = {s.name: s.id for s in project.statuses()}
    rs = {r.code: r.id for r in project.responsibles()}
    s = by["31 33 23"]
    project.set_section_status(s.id, sts["En elaboración"])
    project.set_section_progress(s.id, 70)
    project.set_section_responsibles(s.id, [rs["INIO"], rs["INIG"], rs["INIC"]])
    s = by["33 40 00"]
    project.set_section_status(s.id, sts["Aprobada"])
    project.set_section_progress(s.id, 100)
    project.set_section_responsibles(s.id, [rs["INIC"]])
    s = by["01 35 29"]
    project.set_section_status(s.id, sts["En revisión"])
    project.set_section_progress(s.id, 40)
    project.set_section_responsibles(s.id, [rs["INIO"], rs["INIE"]])
    app.processEvents()

    # mapa.png: mapa completo con adornos
    render_scene(w.scene, OUT / "mapa.png", 0.9)

    # conectar.png: línea temporal entre dos nodos, recortada
    a, b = w.scene.nodes[by["31 33 23"].id], w.scene.nodes[by["01 13 00"].id]
    temp = TempEdgeItem(a.scene_rect().center())
    temp.set_end(b.scene_rect().center() + QPointF(-30, 20))
    w.scene.addItem(temp)
    grid = w.scene.grid_visible
    w.scene.grid_visible = False
    rect = a.sceneBoundingRect().united(b.sceneBoundingRect()).adjusted(-40, -40, 40, 40)
    img = QImage(int(rect.width()), int(rect.height()), QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.white)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    w.scene.render(p, QRectF(img.rect()), rect)
    p.end()
    save_fit(img, OUT / "conectar.png")
    w.scene.removeItem(temp)
    w.scene.grid_visible = grid

    # panel.png: panel MasterFormat filtrado
    w.catalog_panel.search.setText("excav")
    QTest.qWait(400)
    app.processEvents()
    save_fit(w.catalog_panel.grab().toImage(), OUT / "panel.png")
    w.catalog_panel.search.clear()

    # entrada.png: entrada de relaciones con una sugerencia elegida (columna izquierda ampliada)
    w.splitter.setSizes([700, 500])
    app.processEvents()
    w.entry.picker_a.set_section(by["31 33 23"].id, by["31 33 23"].label)
    w.entry.picker_b.setText("0330")
    app.processEvents()
    save_fit(w.entry.grab().toImage(), OUT / "entrada.png")
    w.entry.clear_inputs()
    w.splitter.setSizes([560, 900])

    # acciones.png: filas de la tabla de relaciones con los iconos ✎ ⇄ 🗑 (panel oculto para dar ancho)
    w.catalog_panel.hide()
    w.splitter.setSizes([760, 500])
    app.processEvents()
    table = w.table_view.table
    table.selectRow(0)
    app.processEvents()
    full = w.table_view.grab().toImage()
    header_h = w.table_view.table.geometry().top()
    crop = full.copy(0, header_h, full.width(), min(full.height() - header_h, 44 + 4 * 44))
    save_fit(crop, OUT / "acciones.png")
    table.clearSelection()
    w.splitter.setSizes([560, 900])
    w.catalog_panel.show()

    # secciones.png / analisis.png: pestañas
    w.tabs.setCurrentIndex(TAB_SECTIONS)
    app.processEvents()
    save_fit(w.sections_view.grab().toImage(), OUT / "secciones.png")
    w.tabs.setCurrentIndex(TAB_ANALYSIS)
    w.analysis.select_section(by["31 33 23"].id)
    app.processEvents()
    save_fit(w.analysis.grab().toImage(), OUT / "analisis.png")
    w.tabs.setCurrentIndex(TAB_MAP)
    project.close()
    print(f"Imágenes del manual en {OUT}: {sorted(p.name for p in OUT.glob('*.png'))}")


if __name__ == "__main__":
    main()
