"""Punto de entrada de SpecRel."""
from __future__ import annotations

import ctypes
import os
import sys
import traceback

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

from PyQt6.QtCore import QCoreApplication, Qt  # noqa: E402
from PyQt6.QtGui import QIcon, QPixmap  # noqa: E402
from PyQt6.QtWidgets import QApplication, QMessageBox, QSplashScreen  # noqa: E402

from config.settings import (  # noqa: E402
    APP_NAME,
    APP_ORG,
    APP_USER_MODEL_ID,
    APP_VERSION_LABEL,
    ASSETS_DIR,
    STYLES_DIR,
    debug_mode,
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


def _install_excepthook() -> None:
    """Una excepción no capturada en un slot de PyQt6 aborta el proceso: mejor avisar y seguir.

    Un archivo bloqueado por OneDrive (ProjectLockedError) se explica sin volcar la traza.
    """
    from models.database import ProjectLockedError

    def hook(exc_type, exc, tb) -> None:
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        sys.__stderr__ and sys.__stderr__.write(text)  # type: ignore[union-attr]
        if QApplication.instance() is None:
            return
        if issubclass(exc_type, ProjectLockedError):
            QMessageBox.warning(
                None, f"{APP_NAME} — archivo bloqueado",
                f"{exc}\n\nEl último cambio no se guardó. Repita la acción cuando la sincronización termine "
                "(o marque el archivo como «Mantener siempre en este dispositivo» en OneDrive).")
            return
        QMessageBox.critical(
            None, f"{APP_NAME} — error inesperado",
            "Ocurrió un error inesperado; la aplicación sigue abierta y el proyecto está guardado hasta el "
            f"último cambio correcto.\n\nDetalle técnico:\n{text[-3000:]}")

    sys.excepthook = hook


def _splash() -> QSplashScreen | None:
    icon_path = ASSETS_DIR / "icon.ico"
    pixmap = QPixmap(str(icon_path)) if icon_path.exists() else QPixmap()
    if pixmap.isNull():
        pixmap = QPixmap(360, 200)
        pixmap.fill(Qt.GlobalColor.white)
    else:
        pixmap = pixmap.scaled(160, 160, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
    splash = QSplashScreen(pixmap)
    splash.showMessage(f"{APP_NAME} {APP_VERSION_LABEL}\nCargando catálogo MasterFormat…",
                       Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
    splash.show()
    QApplication.processEvents()
    return splash


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
    assert model.clauses.available, "catálogo de cláusulas no encontrado"
    clause = model.clauses.get("4.28.61")
    assert clause is not None and clause.title == "PAGO FINAL", clause
    c, _created = model.create_section_from_catalog("4.28.61")
    assert c.is_clause and c.status_id is None and model.category(c.category_id).name == "Cláusula"
    print(f"catálogo de cláusulas: {len(model.clauses)} entradas ({model.clauses.path})")
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
    _install_excepthook()
    splash = _splash()  # el arranque tarda 2-3 s (catálogo, árbol, OpenGL): que se vea que abrió

    try:
        from controllers.main_controller import MainController
        from models.master_catalog import MasterCatalog
        from models.masterformat_tree_model import MasterFormatTreeModel
        from models.project_model import ProjectModel
        from models.relations_table_model import RelationsTableModel
        from models.section_completer_model import SectionCompleterModel
        from views.main_window import MainWindow

        from models.clause_catalog import ClauseCatalog

        master = MasterCatalog()
        clauses = ClauseCatalog()
        project = ProjectModel(master=master, clauses=clauses)
        table_model = RelationsTableModel(project)
        completer_model = SectionCompleterModel()
        if splash is not None:
            splash.showMessage(f"{APP_NAME} {APP_VERSION_LABEL}\nPreparando la ventana…",
                               Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter)
            QApplication.processEvents()
        tree_model = MasterFormatTreeModel(master, clauses=clauses)
        window = MainWindow(table_model, completer_model, tree_model)
        controller = MainController(project, window, table_model, completer_model)  # noqa: F841
        initial = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
        controller.start(initial)
        if splash is not None:
            splash.finish(window)
    except Exception:  # noqa: BLE001 - la app se construye sin consola: mostrar el error
        if splash is not None:
            splash.close()
        QMessageBox.critical(None, f"{APP_NAME} — error al iniciar", traceback.format_exc())
        return 1

    # Precalentar scipy/networkx en un hilo: la primera disposición 3D deja de costar ~1 s.
    from models.layout_engine import warm_up
    from utils.workers import run_in_background

    run_in_background(warm_up, parent=app)

    watchdog = None
    if debug_mode():
        from utils.perf import FreezeWatchdog

        watchdog = FreezeWatchdog(threshold_ms=400).start_with_qt_timer()
    try:
        return app.exec()
    finally:
        if watchdog is not None:
            watchdog.stop()


if __name__ == "__main__":
    sys.exit(main())
