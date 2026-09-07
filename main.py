"""Punto de entrada de SpecRel."""
from __future__ import annotations

import ctypes
import os
import sys
import traceback

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

from PyQt6.QtCore import QCoreApplication, Qt  # noqa: E402
from PyQt6.QtGui import QIcon  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from config.settings import (  # noqa: E402
    APP_NAME,
    APP_ORG,
    APP_USER_MODEL_ID,
    ASSETS_DIR,
    STYLES_DIR,
    ensure_appdata_dir,
    load_environment,
    opengl_software,
)

if sys.platform == "win32":
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_USER_MODEL_ID)
    except Exception:  # noqa: BLE001
        pass


def _load_stylesheet() -> str:
    qss = STYLES_DIR / "theme.qss"
    return qss.read_text(encoding="utf-8") if qss.exists() else ""


def _selftest() -> int:
    """Comprobación rápida para CI: modelo en memoria + importación de OpenGL."""
    from models.entities import UiKind
    from models.project_model import ProjectModel

    for stream in (sys.stdout, sys.stderr):  # consolas sin UTF-8 (CI, cmd): no fallar por acentos
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError):
            pass

    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)
    app = QApplication(sys.argv)  # noqa: F841
    model = ProjectModel()
    model.new_project(None, "CC-00", "Selftest")
    a = model.add_section("31 23 00", "Excavación")
    b = model.add_section("33 40 00", "Drenaje pluvial")
    model.add_relation(a.id, UiKind.REFERENCES, b.id)
    assert model.graph.edge_count == 1
    assert model.master.available, "catálogo MasterFormat no encontrado"
    assert model.master.get("03 30 00") is not None
    print(f"catálogo MasterFormat: {len(model.master)} secciones ({model.master.path})")
    try:
        import pyqtgraph.opengl  # noqa: F401
        print("pyqtgraph.opengl importado correctamente")
    except Exception as exc:  # noqa: BLE001
        print(f"Aviso: pyqtgraph.opengl no disponible: {exc}")
    model.close()
    print("selftest OK")
    return 0


def main() -> int:
    load_environment()
    ensure_appdata_dir()
    if "--selftest" in sys.argv:
        return _selftest()
    if opengl_software():
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_UseSoftwareOpenGL)
    # Contextos compartidos: evita recrear la ventana nativa cuando aparece el widget OpenGL.
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORG)
    icon_path = ASSETS_DIR / "icon.ico"
    if icon_path.exists():
        app.setWindowIcon(QIcon(str(icon_path)))
    stylesheet = _load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    try:
        from controllers.main_controller import MainController
        from models.master_catalog import MasterCatalog
        from models.masterformat_tree_model import MasterFormatTreeModel
        from models.project_model import ProjectModel
        from models.relations_table_model import RelationsTableModel
        from models.section_completer_model import SectionCompleterModel
        from views.main_window import MainWindow

        master = MasterCatalog()
        project = ProjectModel(master=master)
        table_model = RelationsTableModel(project)
        completer_model = SectionCompleterModel()
        tree_model = MasterFormatTreeModel(master)
        window = MainWindow(table_model, completer_model, tree_model)
        controller = MainController(project, window, table_model, completer_model)  # noqa: F841
        initial = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
        controller.start(initial)
    except Exception:  # noqa: BLE001 - la app se construye sin consola: mostrar el error
        QMessageBox.critical(None, f"{APP_NAME} — error al iniciar", traceback.format_exc())
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
