"""Crear un mapa directamente desde Excel/CSV y arrastrar archivos sobre la ventana (offscreen, pytest-qt)."""
from __future__ import annotations

from pathlib import Path

import pytest
from PyQt6.QtCore import QMimeData, QPointF, Qt, QUrl
from PyQt6.QtGui import QDropEvent

from controllers.main_controller import MainController
from models.masterformat_tree_model import MasterFormatTreeModel
from models.project_io import read_tables, write_template_xlsx
from models.project_model import ProjectModel
from models.relations_table_model import RelationsTableModel
from models.section_completer_model import SectionCompleterModel
from views.main_window import MainWindow


@pytest.fixture
def app(qtbot, monkeypatch, master):
    from PyQt6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes))
    monkeypatch.setattr(QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(QMessageBox, "warning", staticmethod(lambda *a, **k: None))
    project = ProjectModel(master=master)
    table_model = RelationsTableModel(project)
    completer_model = SectionCompleterModel()
    window = MainWindow(table_model, completer_model, MasterFormatTreeModel(master))
    controller = MainController(project, window, table_model, completer_model)
    qtbot.addWidget(window)
    # Sin diálogos modales: las tablas se leen en el mismo hilo y el resumen/las preguntas se registran.
    shown: list[tuple[str, object]] = []
    controller.answers: list[int | None] = []
    monkeypatch.setattr(controller, "_read_tables_then", lambda files, on_done: on_done(read_tables(files)))
    monkeypatch.setattr(controller, "_show_import_summary",
                        lambda title, summary, header="": shown.append((title, summary)))
    monkeypatch.setattr(controller, "_ask_choice",
                        lambda *a, **k: controller.answers.pop(0) if controller.answers else None)
    controller.shown = shown
    window.show()
    yield project, window, controller, table_model
    project.close()


def _template(tmp_path: Path, name: str = "CC-26-30 relaciones.xlsx") -> Path:
    xlsx = tmp_path / name
    write_template_xlsx(xlsx)
    return xlsx


def _drop_event(paths: list[Path]) -> QDropEvent:
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(p)) for p in paths])
    event = QDropEvent(QPointF(10, 10), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton,
                       Qt.KeyboardModifier.NoModifier)
    event._mime = mime   # el evento no es dueno del QMimeData: evitar que Python lo libere antes de usarlo
    return event


def test_import_action_enabled_without_project_and_welcome_button_exists(app):
    _project, window, _c, _t = app
    assert window.stack.currentIndex() == 0
    assert window.act_import_tables.isEnabled()
    assert window.welcome_import.isVisible()


def test_create_project_from_template_next_to_excel_and_arranged(app, tmp_path):
    project, window, controller, table_model = app
    xlsx = _template(tmp_path)
    controller.create_project_from_tables([xlsx])
    dest = tmp_path / "CC-26-30 relaciones.specrel"
    assert dest.exists() and project.is_open and project.path == dest
    assert project.meta().code == "CC-26-01"           # hoja «Proyecto» de la plantilla
    assert window.stack.currentIndex() == 1
    assert len(project.sections()) == 4 and table_model.rowCount() == 4
    positions = {(round(p.x), round(p.y)) for p in project.positions().values()}
    assert len(positions) == 4                          # acomodo automático: posiciones distintas
    assert not any(p.pinned for p in project.positions().values())
    title, summary = controller.shown[-1]
    assert title == "Mapa creado" and summary.relations_created == 4
    assert str(dest) in window.statusBar().currentMessage()


def test_file_name_gives_project_code_when_sheet_is_missing(app, tmp_path):
    project, _w, controller, _t = app
    csv = tmp_path / "puente rev3.csv"
    csv.write_text("Sección A;Relación;Sección B\n01 13 00;->;31 33 23\n31 33 23;->;01 13 00\n", encoding="utf-8-sig")
    controller.create_project_from_tables([csv])
    assert project.is_open and project.path == tmp_path / "puente rev3.specrel"
    assert project.meta().code == "puente rev3"
    assert len(project.relations()) == 2                 # las dos direcciones son dos flechas


def test_existing_project_file_asks_and_can_open_it(app, tmp_path):
    project, _w, controller, table_model = app
    xlsx = _template(tmp_path)
    controller.create_project_from_tables([xlsx])
    first_path = project.path
    controller.answers = [0]                            # «Abrir el existente y agregar las tablas»
    controller.create_project_from_tables([xlsx])
    assert project.path == first_path and table_model.rowCount() == 4
    _title, summary = controller.shown[-1]
    assert summary.relations_created == 0 and summary.relations_duplicated == 4
    controller.answers = [None]                         # cancelar: no pasa nada
    controller.create_project_from_tables([xlsx])
    assert project.path == first_path


def test_drop_tables_with_project_open_asks_add_or_new(app, tmp_path):
    project, window, controller, table_model = app
    project.new_project(None, "CC-25-01", "Demo")
    xlsx = _template(tmp_path)
    controller.answers = [0]                            # agregar al proyecto abierto
    controller.open_dropped_files([str(xlsx)])
    assert project.path is None and table_model.rowCount() == 4
    controller.answers = [1]                            # crear un mapa nuevo
    controller.open_dropped_files([str(xlsx)])
    assert project.path == tmp_path / "CC-26-30 relaciones.specrel"


def test_drop_specrel_opens_it_and_unknown_files_are_reported(app, tmp_path):
    project, window, controller, _t = app
    other = ProjectModel()
    other.new_project(tmp_path / "otro.specrel", "OTRO", "Otro proyecto")
    other.add_section("03 30 00", "Concreto")
    other.close()
    controller.open_dropped_files([str(tmp_path / "otro.specrel")])
    assert project.is_open and project.meta().code == "OTRO" and len(project.sections()) == 1
    controller.open_dropped_files([str(tmp_path / "foto.png")])
    assert "Formato no soportado" in window.statusBar().currentMessage()


def test_window_and_canvas_drop_events_emit_paths(app, tmp_path, qtbot):
    _project, window, _c, _t = app
    xlsx = _template(tmp_path)
    got: list[list[str]] = []
    window.filesDropped.connect(got.append)
    window.dropEvent(_drop_event([xlsx, tmp_path / "ignorado.txt"]))
    assert got == [[str(xlsx).replace("\\", "/")]] or got == [[str(xlsx)]]
    assert window.dropped_paths(_drop_event([tmp_path / "x.pdf"])) == []
    got_view: list[list[str]] = []
    window.view.filesDropped.connect(got_view.append)
    window.view.dropEvent(_drop_event([xlsx]))
    assert len(got_view) == 1 and got_view[0][0].endswith("CC-26-30 relaciones.xlsx")
