"""Controlador del panel de análisis: alimenta el panel desde GraphEngine y dispara resaltados."""
from __future__ import annotations

from PyQt6.QtCore import QObject

from models.project_model import ProjectModel
from utils.debounce import Debouncer
from views.main_window import MainWindow


class AnalysisController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, canvas_controller,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.canvas = canvas_controller
        self.panel = window.analysis
        # Coalescido: una importación de 300 secciones dispara cientos de señales; se refresca una vez.
        self.refresh_later = Debouncer(self.refresh, 50, self)
        project.projectLoaded.connect(self._on_project_state)
        project.projectClosed.connect(self._on_project_state)
        project.graphChanged.connect(self.refresh_later)
        project.sectionUpdated.connect(self.refresh_later)
        project.responsiblesChanged.connect(self.refresh_later)
        self.panel.centerOnSection.connect(self.canvas.center_on)
        self.panel.highlightRequested.connect(self.highlight)
        self.panel.clearHighlightRequested.connect(self.canvas.clear_highlight)
        self.panel.impactSectionChanged.connect(self._on_impact_section)

    def _label(self, section_id: int) -> str:
        s = self.project.section(section_id)
        return s.label if s else f"#{section_id}"

    def _on_project_state(self) -> None:
        self.refresh_later.cancel()
        self.refresh()

    def refresh(self) -> None:
        self.refresh_later.cancel()
        if not self.project.is_open:
            self.panel.set_metrics(0, 0, 0, 0)
            self.panel.set_responsible_progress([])
            self.panel.set_orphans([])
            self.panel.set_hubs([])
            self.panel.set_sections([])
            self.panel.set_impact([], [])
            self.panel.set_components([])
            return
        g = self.project.graph
        orphans = g.orphans()
        comps = g.components()
        sections = self.project.sections()
        avg = (sum(s.progress for s in sections) / len(sections)) if sections else None
        self.panel.set_metrics(g.node_count, g.edge_count, len(orphans), len(comps), avg)
        rows = []
        for resp in self.project.responsibles():
            mine = [s for s in sections if resp.id in self.project.section_responsible_ids(s.id)]
            if mine:
                rows.append((resp.code, resp.color, len(mine), sum(s.progress for s in mine) / len(mine),
                             sum(1 for s in mine if s.progress >= 100)))
        self.panel.set_responsible_progress(rows)
        self.panel.set_orphans([(sid, self._label(sid)) for sid in orphans])
        self.panel.set_hubs([
            (d.section_id, self._label(d.section_id), d.out_degree, d.in_degree, d.total)
            for d in g.degrees() if d.total > 0
        ][:50])
        self.panel.set_sections([(s.id, s.label) for s in self.project.sections()])
        self.panel.set_components([[self._label(sid) for sid in sorted(c, key=self._label)] for c in comps if len(c) > 1])
        self._on_impact_section(self.panel.impact_combo.currentData())

    def _on_impact_section(self, section_id) -> None:
        if section_id is None or not self.project.is_open:
            self.panel.set_impact([], [])
            return
        result = self.project.graph.impact(int(section_id))
        affected = sorted(((sid, self._label(sid), lvl) for sid, lvl in result.affected.items()),
                          key=lambda t: (t[2], t[1]))
        depends = sorted(((sid, self._label(sid), lvl) for sid, lvl in result.depends_on.items()),
                         key=lambda t: (t[2], t[1]))
        self.panel.set_impact(affected, depends)

    def highlight(self, section_id: int) -> None:
        result = self.project.graph.impact(section_id)
        self.canvas.highlight(result.all_ids, section_id)
        self.window.show_status(
            f"Resaltado: {len(result.affected)} afectadas, {len(result.depends_on)} dependencias. "
            "Use «Quitar resaltado» para restaurar.", 8000)
        view3d = getattr(self.window, "view3d", None)
        if view3d is not None:
            view3d.set_highlight(result.all_ids)
