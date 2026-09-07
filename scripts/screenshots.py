"""Captura pantallas de la aplicación con el proyecto demo (para verificación visual).

Uso: python scripts/screenshots.py carpeta_salida
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from controllers.export_controller import render_png  # noqa: E402
from controllers.main_controller import MainController  # noqa: E402
from models.project_model import ProjectModel  # noqa: E402
from models.relations_table_model import RelationsTableModel  # noqa: E402
from models.section_completer_model import SectionCompleterModel  # noqa: E402
from scripts.make_demo import build  # noqa: E402
from views.main_window import TAB_3D, TAB_ANALYSIS, TAB_MAP, MainWindow  # noqa: E402


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "screens"
    out.mkdir(parents=True, exist_ok=True)
    app = QApplication(sys.argv)
    app.setStyleSheet((ROOT / "views/styles/theme.qss").read_text(encoding="utf-8"))

    demo_path = out / "demo.specrel"
    if demo_path.exists():
        demo_path.unlink()
    build(demo_path).close()

    project = ProjectModel()
    table_model = RelationsTableModel(project)
    completer_model = SectionCompleterModel()
    window = MainWindow(table_model, completer_model)
    controller = MainController(project, window, table_model, completer_model)
    window.resize(1600, 900)
    window.show()
    project.open_project(demo_path)
    app.processEvents()
    window.view.fit_all()
    app.processEvents()
    window.grab().save(str(out / "01_mapa.png"))

    render_png(window.scene, out / "02_mapa_export.png", scale=1.5)

    window.tabs.setCurrentIndex(TAB_ANALYSIS)
    c = project.section_by_code("31 33 23")
    window.analysis.select_section(c.id)
    controller.analysis.highlight(c.id)
    app.processEvents()
    window.grab().save(str(out / "03_analisis.png"))
    window.tabs.setCurrentIndex(TAB_MAP)
    app.processEvents()
    window.grab().save(str(out / "04_mapa_resaltado.png"))
    controller.canvas.clear_highlight()

    window.tabs.setCurrentIndex(TAB_3D)
    app.processEvents()
    window.grab().save(str(out / "05_3d.png"))
    print(f"Capturas en {out}")
    project.close()


if __name__ == "__main__":
    main()
