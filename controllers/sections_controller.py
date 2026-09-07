"""Controlador de la pestaña «Secciones» y de las listas de Responsables y Estatus."""
from __future__ import annotations

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox

from models.project_model import ProjectModel
from models.sections_table_model import (
    COL_CATEGORY,
    COL_OBS,
    COL_PROGRESS,
    COL_RESP,
    COL_STATUS,
    COL_TITLE,
    SectionsTableModel,
)
from views.components.list_dialogs import ResponsiblesDialog, StatusesDialog
from views.main_window import MainWindow


class SectionsController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, canvas_controller,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.canvas = canvas_controller
        self.model = SectionsTableModel(project, self)
        view = window.sections_view
        view.set_model(
            self.model,
            status_provider=lambda: [(s.id, s.name, s.color) for s in project.statuses()],
            responsible_provider=lambda: [(r.id, r.code, r.color) for r in project.responsibles()],
            category_provider=lambda: [(c.id, c.name, c.fill_color) for c in project.categories()],
        )
        self.model.editRequested.connect(self.on_edit)
        view.sectionActivated.connect(self.canvas.center_on)
        view.responsiblesRequested.connect(self.edit_responsibles)
        view.statusesRequested.connect(self.edit_statuses)
        window.act_responsibles.triggered.connect(self.edit_responsibles)
        window.act_statuses.triggered.connect(self.edit_statuses)

    # ------------------------------------------------------------------ edición en línea
    def on_edit(self, section_id: int, column: int, value) -> None:
        section = self.project.section(section_id)
        if section is None:
            return
        try:
            if column == COL_TITLE:
                self.project.update_section(section_id, section.code, str(value or "").strip(),
                                            section.category_id, section.notes)
            elif column == COL_CATEGORY:
                self.project.set_section_category(section_id, value)
            elif column == COL_STATUS:
                self.project.set_section_status(section_id, value)
            elif column == COL_PROGRESS:
                self.project.set_section_progress(section_id, int(value))
            elif column == COL_RESP:
                self.project.set_section_responsibles(section_id, [int(v) for v in (value or [])])
            elif column == COL_OBS:
                self.project.set_section_observations(section_id, str(value or ""))
        except (ValueError, TypeError) as exc:
            QMessageBox.warning(self.window, "Secciones", str(exc))

    # ------------------------------------------------------------------ listas
    def edit_responsibles(self) -> None:
        if not self.project.is_open:
            return
        items = self.project.responsibles()
        usage = {r.id: self.project.responsibles_repo.usage_count(r.id) for r in items}
        dialog = ResponsiblesDialog(items, usage, self.window)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        edits, deleted = dialog.result_edits()
        for rid in deleted:
            self.project.remove_responsible(rid)
        by_id = {r.id: r for r in self.project.responsibles()}
        for order, e in enumerate(edits):
            if e.id is None:
                resp = self.project.add_responsible(e.code, e.name, e.color)
                resp.sort_order = order
                self.project.update_responsible(resp)
            elif e.id in by_id:
                resp = by_id[e.id]
                if (resp.code, resp.name, resp.color, resp.sort_order) != (e.code, e.name, e.color, order):
                    resp.code, resp.name, resp.color, resp.sort_order = e.code, e.name, e.color, order
                    self.project.update_responsible(resp)
        self.window.show_status("Responsables actualizados.")

    def edit_statuses(self) -> None:
        if not self.project.is_open:
            return
        items = self.project.statuses()
        usage = {s.id: self.project.statuses_repo.usage_count(s.id) for s in items}
        dialog = StatusesDialog(items, usage, self.window)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        edits, deleted = dialog.result_edits()
        for sid in deleted:
            self.project.remove_status(sid)
        by_id = {s.id: s for s in self.project.statuses()}
        for order, e in enumerate(edits):
            if e.id is None:
                st = self.project.add_status(e.name, e.color)
                st.sort_order, st.is_default = order, e.is_default
                self.project.update_status(st)
            elif e.id in by_id:
                st = by_id[e.id]
                if (st.name, st.color, st.sort_order, st.is_default) != (e.name, e.color, order, e.is_default):
                    st.name, st.color, st.sort_order, st.is_default = e.name, e.color, order, e.is_default
                    self.project.update_status(st)
        self.window.show_status("Estatus actualizados.")
