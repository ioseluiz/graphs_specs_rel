"""Controlador del mapa: escena <-> ProjectModel, menús contextuales y selección cruzada."""
from __future__ import annotations

from PyQt6.QtCore import QObject, QPoint, QPointF, QSettings
from PyQt6.QtGui import QAction, QColor, QIcon, QPixmap
from PyQt6.QtWidgets import QColorDialog, QDialog, QMenu, QMessageBox

from config import palette
from models.entities import SIDES, Relation, Section, UiKind
from models.layout_engine import initial_layout_2d
from models.line_styles import DASH_KEYS, DASH_LABELS, DEFAULT_WIDTH, WIDTH_PRESETS
from models.project_model import ProjectModel
from utils.debounce import Debouncer
from utils.workers import busy_cursor
from views.components.canvas.line_style_qt import color_icon, dash_icon, width_icon
from views.components.line_style_dialog import LineStyleDialog
from views.components.section_editor_dialog import SectionEditorDialog
from views.main_window import TAB_ANALYSIS, TAB_MAP, MainWindow

SIDE_LABELS = {"top": "Arriba", "right": "Derecha", "bottom": "Abajo", "left": "Izquierda"}


class CanvasController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, relations_controller,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.relations = relations_controller
        self.scene = window.scene
        self.view = window.view
        self._syncing_selection = False
        self._highlight_active = False

        # Modelo -> escena
        project.projectLoaded.connect(self.populate)
        project.projectClosed.connect(self.scene.clear_all)
        project.sectionAdded.connect(self._on_section_added)
        project.sectionUpdated.connect(self._on_section_updated)
        project.sectionRemoved.connect(self.scene.remove_node)
        project.relationAdded.connect(self._on_relation_added)
        project.relationUpdated.connect(self._on_relation_updated)
        project.relationGeometryChanged.connect(self._on_relation_geometry)
        project.relationRemoved.connect(self.scene.remove_edge)
        project.positionChanged.connect(self.scene.set_node_pos)
        self._refresh_all_later = Debouncer(self._refresh_all_nodes, 50, self)
        project.categoriesChanged.connect(self._refresh_all_later)
        project.statusesChanged.connect(self._refresh_all_later)
        project.responsiblesChanged.connect(self._refresh_all_later)

        # Escena -> modelo
        self.scene.nodesMoved.connect(self._on_nodes_moved)
        self.scene.connectRequested.connect(self._on_connect_requested)
        self.scene.edgeGeometryChanged.connect(self._on_edge_geometry_changed)
        self.scene.nodeDoubleClicked.connect(self.edit_section)
        self.scene.nodeContextMenu.connect(self._node_menu)
        self.scene.edgeContextMenu.connect(self._edge_menu)
        self.scene.canvasContextMenu.connect(self._canvas_menu)
        self.scene.selectionChanged.connect(self._on_scene_selection)
        self.view.invertRequested.connect(self.relations.invert)
        window.table_view.selectionChangedIds.connect(self._on_table_selection)
        self._edge_hint_shown = False

        # Acciones de la ventana
        window.act_connect.toggled.connect(self.view.set_connect_mode)
        self.view.connectModeChanged.connect(window.act_connect.setChecked)
        window.act_fit.triggered.connect(self.view.fit_all)
        window.act_zoom_in.triggered.connect(self.view.zoom_in)
        window.act_zoom_out.triggered.connect(self.view.zoom_out)
        window.act_zoom_reset.triggered.connect(self.view.reset_zoom)
        window.act_snap.toggled.connect(self._set_snap)
        window.act_grid.toggled.connect(self._set_grid)
        settings = QSettings()
        show_extras = settings.value("canvas/show_extras", True, type=bool)
        window.act_show_extras.setChecked(show_extras)
        self.scene.show_extras = show_extras
        window.act_show_extras.toggled.connect(self._set_show_extras)
        line_jumps = settings.value("canvas/line_jumps", True, type=bool)
        window.act_line_jumps.setChecked(line_jumps)
        self.scene.line_jumps_enabled = line_jumps
        window.act_line_jumps.toggled.connect(self._set_line_jumps)
        window.act_arrange_new.triggered.connect(self.arrange_unpinned)
        window.act_add_section.triggered.connect(lambda: self.new_section(None))
        window.act_delete.triggered.connect(self.delete_selection)
        self.view.zoomChanged.connect(window.set_zoom_label)

    # ------------------------------------------------------------------ carga
    def populate(self) -> None:
        with busy_cursor():
            self.scene.clear_all()
            for section in self.project.sections():
                self._add_node(section)
            for rel in self.project.relations():
                self.scene.add_edge(rel.id, rel.source_id, rel.target_id, rel.kind, rel.waypoints,
                                    rel.source_port, rel.target_port)
                self._sync_edge_extras(rel)
            self.scene.grow_scene_rect()
            self.scene.refresh_jumps()
            self.view.fit_all()

    def _node_style(self, section: Section) -> tuple[str, str]:
        return self.project.section_colors(section)

    def _node_extras(self, section: Section) -> tuple[str, str | None, int, list[tuple[str, str]]]:
        st = self.project.status(section.status_id)
        resp = [(r.code, r.color) for r in self.project.section_responsibles(section.id)]
        return (st.name if st else "", st.color if st else None, section.progress, resp)

    def _add_node(self, section: Section) -> None:
        pos = self.project.position(section.id)
        x, y = (pos.x, pos.y) if pos else (0.0, 0.0)
        fill, border = self._node_style(section)
        self.scene.add_node(section.id, section.code, section.title, fill, border, x, y, section.kind)
        self.scene.set_node_extras(section.id, *self._node_extras(section))

    def _set_show_extras(self, on: bool) -> None:
        self.scene.set_show_extras(on)
        QSettings().setValue("canvas/show_extras", on)

    def _set_line_jumps(self, on: bool) -> None:
        self.scene.set_line_jumps(on)
        QSettings().setValue("canvas/line_jumps", on)

    # ------------------------------------------------------------------ modelo -> escena
    def _on_section_added(self, section_id: int) -> None:
        section = self.project.section(section_id)
        if section is not None:
            self._add_node(section)
            self.view.ensureVisible(self.scene.nodes[section_id], 60, 60)

    def _on_section_updated(self, section_id: int) -> None:
        section = self.project.section(section_id)
        if section is not None:
            fill, border = self._node_style(section)
            self.scene.update_node(section_id, section.code, section.title, fill, border, section.kind)
            self.scene.set_node_extras(section_id, *self._node_extras(section))

    def _refresh_all_nodes(self) -> None:
        for sid in list(self.scene.nodes):
            self._on_section_updated(sid)

    def _sync_edge_extras(self, rel: Relation) -> None:
        """Estilo propio y observaciones (tooltip) de la flecha, que no viajan por add_edge/update_edge."""
        self.scene.set_edge_style(rel.id, rel.line_color, rel.line_dash, rel.line_width)
        edge = self.scene.edges.get(rel.id)
        if edge is not None:
            edge.set_notes(rel.notes)

    def _on_relation_added(self, relation_id: int) -> None:
        rel = self.project.relation(relation_id)
        if rel is not None:
            self.scene.add_edge(rel.id, rel.source_id, rel.target_id, rel.kind, rel.waypoints,
                                rel.source_port, rel.target_port)
            self._sync_edge_extras(rel)

    def _on_relation_updated(self, relation_id: int) -> None:
        rel = self.project.relation(relation_id)
        if rel is not None:
            self.scene.update_edge(rel.id, rel.source_id, rel.target_id, rel.kind, rel.waypoints,
                                   rel.source_port, rel.target_port)
            self._sync_edge_extras(rel)

    def _on_relation_geometry(self, relation_id: int) -> None:
        rel = self.project.relation(relation_id)
        edge = self.scene.edges.get(relation_id)
        if rel is None or edge is None:
            return
        current = [(p.x(), p.y()) for p in edge.waypoints] if edge.waypoints else None
        if current == rel.waypoints and edge.source_port == rel.source_port and edge.target_port == rel.target_port:
            return  # la escena ya refleja el cambio (origen: la propia escena)
        edge.set_geometry(rel.waypoints, rel.source_port, rel.target_port)

    # ------------------------------------------------------------------ escena -> modelo
    def _on_nodes_moved(self, moves: dict[int, tuple[float, float]]) -> None:
        self.project.move_nodes(moves, pinned=True)

    def _on_connect_requested(self, source_id: int, target_id: int) -> None:
        menu = QMenu(self.window)
        sa, sb = self.project.section(source_id), self.project.section(target_id)
        if sa is None or sb is None:
            return
        menu.addSection(f"{sa.code} … {sb.code}")
        for kind in UiKind:
            act = menu.addAction(f"{sa.code} {kind.value} {sb.code}")
            act.setData(kind)
            existing = self.project.relations_repo.find_directed(
                *((source_id, target_id) if kind is UiKind.REFERENCES else (target_id, source_id)))
            if existing is not None:
                act.setText(act.text() + "   (ya existe)")
                act.setEnabled(False)
        chosen = menu.exec(self.view.mapToGlobal(self.view.mapFromScene(
            self.scene.nodes[target_id].scene_rect().center())))
        if chosen is not None:
            self.relations.add_relation(source_id, chosen.data(), target_id)

    def _on_edge_geometry_changed(self, relation_id: int, waypoints, source_port, target_port) -> None:
        if self.project.relation(relation_id) is not None:
            self.project.set_relation_geometry(relation_id, waypoints, source_port, target_port)

    # ------------------------------------------------------------------ selección cruzada
    def _on_scene_selection(self) -> None:
        if self._syncing_selection:
            return
        node_ids = set(self.scene.selected_node_ids())
        edge_ids = set(self.scene.selected_edge_ids())
        if edge_ids and not node_ids:
            self._announce_edge_selection(edge_ids)
        for sid in node_ids:
            edge_ids.update(r.id for r in self.project.relations_for(sid))
        self._syncing_selection = True
        try:
            self.window.table_view.select_relations(sorted(edge_ids), scroll=bool(edge_ids))
        finally:
            self._syncing_selection = False

    def _announce_edge_selection(self, edge_ids: set[int]) -> None:
        """Barra de estado: qué flecha está seleccionada (códigos) y, la primera vez, cómo operarla."""
        parts = []
        for rid in sorted(edge_ids)[:3]:
            rel = self.project.relation(rid)
            if rel is not None:
                parts.append(self.relations.describe(rel))
        if len(edge_ids) > 3:
            parts.append(f"… y {len(edge_ids) - 3} más")
        text = "Flecha seleccionada: " + "  ·  ".join(parts) if len(edge_ids) == 1 else \
            f"{len(edge_ids)} flechas seleccionadas: " + "  ·  ".join(parts)
        if not self._edge_hint_shown:
            self._edge_hint_shown = True
            text += "   —   Tecla R invierte la dirección; clic derecho: flecha inversa, ruta o eliminar."
        self.window.show_status(text, 9000)

    def select_relation(self, relation_id: int) -> None:
        edge = self.scene.edges.get(relation_id)
        if edge is None:
            return
        self.scene.clearSelection()
        edge.setSelected(True)
        self.view.ensureVisible(edge)

    def _on_table_selection(self, relation_ids: list[int]) -> None:
        if self._syncing_selection:
            return
        self._syncing_selection = True
        try:
            self.scene.clearSelection()
            first = None
            for rid in relation_ids:
                edge = self.scene.edges.get(rid)
                if edge is not None:
                    edge.setSelected(True)
                    first = first or edge
            if first is not None and self.window.tabs.currentIndex() == TAB_MAP:
                self.view.ensureVisible(first, 40, 40)
        finally:
            self._syncing_selection = False

    # ------------------------------------------------------------------ acciones
    def _set_snap(self, on: bool) -> None:
        self.scene.snap_enabled = on

    def _set_grid(self, on: bool) -> None:
        self.scene.grid_visible = on
        self.view.resetCachedContent()  # el fondo (rejilla) está cacheado en la vista
        self.scene.update()

    def new_section(self, scene_pos: QPointF | None) -> None:
        dialog = SectionEditorDialog(self.project.categories(), self.window, is_new=True,
                                     statuses=self.project.statuses(), responsibles=self.project.responsibles())
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        code, title, category_id, notes = dialog.values()
        fill, border = dialog.colors()
        status_id, progress, responsible_ids = dialog.extras()
        if self.project.section_by_code(code) is not None:
            QMessageBox.information(self.window, "Sección", f"La sección {code} ya existe.")
            return
        pos = (scene_pos.x(), scene_pos.y()) if scene_pos is not None else None
        section = self.project.add_section(code, title, category_id, pos)
        self.project.update_section(section.id, code, title, category_id, notes, fill, border, status_id, progress)
        if responsible_ids:
            self.project.set_section_responsibles(section.id, responsible_ids)
        self.window.show_status(f"Sección {section.code} creada.")

    def edit_section(self, section_id: int) -> None:
        section = self.project.section(section_id)
        if section is None:
            return
        dialog = SectionEditorDialog(self.project.categories(), self.window, code=section.code,
                                     title=section.title, category_id=section.category_id, notes=section.notes,
                                     fill_color=section.fill_color, border_color=section.border_color,
                                     statuses=self.project.statuses(), responsibles=self.project.responsibles(),
                                     status_id=section.status_id, progress=section.progress,
                                     responsible_ids=self.project.section_responsible_ids(section_id),
                                     kind=section.kind)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        code, title, category_id, notes = dialog.values()
        fill, border = dialog.colors()
        status_id, progress, responsible_ids = dialog.extras()
        try:
            self.project.update_section(section_id, code, title, category_id, notes, fill, border,
                                        status_id, progress)
            if not section.is_clause:
                self.project.set_section_responsibles(section_id, responsible_ids)
        except ValueError as exc:
            QMessageBox.warning(self.window, "Sección", str(exc))

    def pick_section_color(self, section_id: int) -> None:
        section = self.project.section(section_id)
        if section is None:
            return
        current, _ = self.project.section_colors(section)
        chosen = QColorDialog.getColor(QColor(current), self.window,
                                       f"Color de la sección {section.code}")
        if chosen.isValid():
            self.project.set_section_colors(section_id, chosen.name().upper())

    def apply_color_to_selection(self) -> None:
        ids = self.scene.selected_node_ids()
        if not ids:
            return
        first = self.project.section(ids[0])
        current = self.project.section_colors(first)[0] if first else palette.SURFACE_ALT
        chosen = QColorDialog.getColor(QColor(current), self.window,
                                       f"Color para {len(ids)} sección(es) seleccionada(s)")
        if chosen.isValid():
            for sid in ids:
                self.project.set_section_colors(sid, chosen.name().upper())

    def delete_section(self, section_id: int) -> None:
        section = self.project.section(section_id)
        if section is None:
            return
        count = len(self.project.relations_for(section_id))
        detail = f"\nSe eliminarán también sus {count} relación(es)." if count else ""
        answer = QMessageBox.question(self.window, "Eliminar sección",
                                      f"¿Eliminar la sección {section.code} {section.title}?{detail}")
        if answer == QMessageBox.StandardButton.Yes:
            self.project.remove_section(section_id)

    def delete_selection(self) -> None:
        if self.window.tabs.currentIndex() != TAB_MAP:
            ids = self.window.table_view.selected_relation_ids()
            if ids:
                self.relations.delete_relations(ids)
            return
        node_ids = self.scene.selected_node_ids()
        edge_ids = self.scene.selected_edge_ids()
        if node_ids:
            total_rel = len({r.id for sid in node_ids for r in self.project.relations_for(sid)})
            answer = QMessageBox.question(
                self.window, "Eliminar secciones",
                f"¿Eliminar {len(node_ids)} sección(es) seleccionada(s)?\n"
                f"Se eliminarán también {total_rel} relación(es).")
            if answer != QMessageBox.StandardButton.Yes:
                return
            for sid in node_ids:
                if self.project.section(sid) is not None:
                    self.project.remove_section(sid)
            return
        if edge_ids:
            self.relations.delete_relations(edge_ids)

    def arrange_unpinned(self) -> None:
        ids = self.project.unpinned_ids()
        if not ids:
            self.window.show_status("Todas las secciones ya fueron acomodadas manualmente.")
            return
        sub = self.project.graph.G.subgraph(ids)
        layout = initial_layout_2d(sub)
        pinned = {sid: (p.x, p.y) for sid, p in self.project.positions().items() if p.pinned}
        if pinned:
            # Desplazar el bloque nuevo debajo del contenido ya acomodado.
            max_y = max(y for _, y in pinned.values())
            min_new_y = min(y for _, y in layout.values()) if layout else 0
            shift = max_y + 160 - min_new_y
            layout = {sid: (x, y + shift) for sid, (x, y) in layout.items()}
        self.project.move_nodes(layout, pinned=False)
        self.view.fit_all()

    def center_on(self, section_id: int) -> None:
        self.window.tabs.setCurrentIndex(TAB_MAP)
        self.view.center_on_node(section_id)
        node = self.scene.nodes.get(section_id)
        if node is not None:
            self.scene.clearSelection()
            node.setSelected(True)

    # ------------------------------------------------------------------ resaltado (análisis)
    def highlight(self, node_ids: set[int], focus_id: int | None) -> None:
        edge_ids = self.project.graph.relation_ids_touching(node_ids)
        self.scene.apply_highlight(node_ids, edge_ids, focus_id)
        self._highlight_active = True

    def clear_highlight(self) -> None:
        if self._highlight_active:
            self.scene.clear_highlight()
            self._highlight_active = False

    # ------------------------------------------------------------------ menús contextuales
    def _node_menu(self, section_id: int, global_pos: QPoint) -> None:
        menu = self._build_node_menu(section_id)
        if menu is not None:
            menu.exec(global_pos)

    def _build_node_menu(self, section_id: int) -> QMenu | None:
        """Menú contextual del nodo. Las cláusulas no tienen categoría, estatus, responsables ni avance."""
        section = self.project.section(section_id)
        if section is None:
            return None
        menu = QMenu(self.window)
        if section.is_clause:
            menu.addSection(f"{section.code} · Cláusula")
            menu.addAction("Editar cláusula…", lambda: self.edit_section(section_id))
        else:
            menu.addSection(f"{section.code} {section.title}".strip())
            menu.addAction("Editar sección…", lambda: self.edit_section(section_id))
            cat_menu = menu.addMenu("Categoría")
            for cat in self.project.categories():
                pix = QPixmap(14, 14)
                pix.fill(QColor(cat.fill_color))
                act = QAction(QIcon(pix), cat.name, menu)
                act.setCheckable(True)
                act.setChecked(cat.id == section.category_id)
                act.triggered.connect(
                    lambda _c=False, cid=cat.id: self.project.set_section_category(section_id, cid))
                cat_menu.addAction(act)
        color_menu = menu.addMenu("Color de la sección" if not section.is_clause else "Color de la cláusula")
        selected = self.scene.selected_node_ids()
        if len(selected) > 1 and section_id in selected:
            color_menu.addAction(f"Personalizar color de {len(selected)} seleccionadas…",
                                 self.apply_color_to_selection)
        else:
            color_menu.addAction("Personalizar color…", lambda: self.pick_section_color(section_id))
        act_reset_color = color_menu.addAction("Usar el color de la categoría",
                                               lambda: self.project.set_section_colors(section_id, None))
        act_reset_color.setEnabled(section.has_custom_color)
        if not section.is_clause:
            self._add_extras_menus(menu, section)
        menu.addSeparator()
        menu.addAction("Crear relación desde aquí (arrastre con Alt)",
                       lambda: self.window.act_connect.setChecked(True))
        menu.addAction("Analizar impacto", lambda: self._analyze(section_id))
        menu.addSeparator()
        act_del = menu.addAction("Eliminar cláusula…" if section.is_clause else "Eliminar sección…",
                                 lambda: self.delete_section(section_id))
        act_del.setIcon(self.window.act_delete.icon())
        return menu

    def _add_extras_menus(self, menu: QMenu, section: Section) -> None:
        """Submenús Estatus / Responsables / Avance (solo secciones)."""
        section_id = section.id
        status_menu = menu.addMenu("Estatus")
        for st in self.project.statuses():
            pix = QPixmap(14, 14)
            pix.fill(QColor(st.color))
            act = QAction(QIcon(pix), st.name, menu)
            act.setCheckable(True)
            act.setChecked(st.id == section.status_id)
            act.triggered.connect(lambda _c=False, sid=st.id: self.project.set_section_status(section_id, sid))
            status_menu.addAction(act)
        resp_menu = menu.addMenu("Responsables")
        current_resp = set(self.project.section_responsible_ids(section_id))
        for r in self.project.responsibles():
            pix = QPixmap(14, 14)
            pix.fill(QColor(r.color))
            act = QAction(QIcon(pix), r.label, menu)
            act.setCheckable(True)
            act.setChecked(r.id in current_resp)
            act.triggered.connect(lambda checked, rid=r.id: self._toggle_responsible(section_id, rid, checked))
            resp_menu.addAction(act)
        if not self.project.responsibles():
            resp_menu.addAction("(defina responsables en Edición → Responsables…)").setEnabled(False)
        prog_menu = menu.addMenu(f"Avance ({section.progress} %)")
        for pct in (0, 25, 50, 75, 100):
            act = prog_menu.addAction(f"{pct} %")
            act.setCheckable(True)
            act.setChecked(section.progress == pct)
            act.triggered.connect(lambda _c=False, p=pct: self.project.set_section_progress(section_id, p))
        prog_menu.addSeparator()
        prog_menu.addAction("Otro…", lambda: self._ask_progress(section_id))

    def _toggle_responsible(self, section_id: int, responsible_id: int, checked: bool) -> None:
        ids = self.project.section_responsible_ids(section_id)
        if checked and responsible_id not in ids:
            ids.append(responsible_id)
        elif not checked and responsible_id in ids:
            ids.remove(responsible_id)
        self.project.set_section_responsibles(section_id, ids)

    def _ask_progress(self, section_id: int) -> None:
        from PyQt6.QtWidgets import QInputDialog

        section = self.project.section(section_id)
        if section is None:
            return
        value, ok = QInputDialog.getInt(self.window, "Avance", f"Avance de {section.code} (%):",
                                        section.progress, 0, 100, 5)
        if ok:
            self.project.set_section_progress(section_id, value)

    def _analyze(self, section_id: int) -> None:
        self.window.tabs.setCurrentIndex(TAB_ANALYSIS)
        self.window.analysis.select_section(section_id)

    def _edge_menu(self, relation_id: int, global_pos: QPoint) -> None:
        menu = self._build_edge_menu(relation_id, global_pos)
        if menu is not None:
            menu.exec(global_pos)

    def _build_edge_menu(self, relation_id: int, global_pos: QPoint) -> QMenu | None:
        rel = self.project.relation(relation_id)
        edge = self.scene.edges.get(relation_id)
        if rel is None or edge is None:
            return None
        sa, sb = self.project.section(rel.source_id), self.project.section(rel.target_id)
        code_a, code_b = (sa.code if sa else "?"), (sb.code if sb else "?")
        menu = QMenu(self.window)
        menu.addSection(f"{code_a} → {code_b}  ({code_a} hace referencia a {code_b})")
        current = menu.addAction(f"✓ {code_a} → {code_b}  (actual)")
        current.setEnabled(False)
        reverse = self.project.reverse_relation(relation_id)
        act_invert = menu.addAction(f"⇄ Invertir dirección: {code_b} → {code_a}   (tecla R)",
                                    lambda: self.relations.invert(relation_id))
        if reverse is not None:
            act_invert.setEnabled(False)
            act_invert.setText(f"⇄ Invertir dirección   (ya existe la flecha {code_b} → {code_a})")
            menu.addAction(f"Seleccionar la flecha inversa {code_b} → {code_a}",
                           lambda: self.select_relation(reverse.id))
        else:
            menu.addAction(f"＋ Agregar flecha inversa {code_b} → {code_a}  (dos flechas)",
                           lambda: self.relations.add_reverse(relation_id))
        menu.addSeparator()
        menu.addAction("Agregar punto de quiebre aquí",
                       lambda: edge.insert_waypoint_at(self.view.mapToScene(self.view.mapFromGlobal(global_pos))))
        act_reset = menu.addAction("Restablecer ruta automática", edge.reset_geometry)
        act_reset.setEnabled(bool(edge.waypoints) or edge.source_port is not None or edge.target_port is not None)
        out_menu = menu.addMenu("Puerto de salida")
        in_menu = menu.addMenu("Puerto de entrada")
        for side in SIDES:
            a = out_menu.addAction(SIDE_LABELS[side])
            a.setCheckable(True)
            a.setChecked(edge.source_port == side)
            a.triggered.connect(lambda _c=False, s=side: edge.set_forced_port(s, edge.target_port))
            b = in_menu.addAction(SIDE_LABELS[side])
            b.setCheckable(True)
            b.setChecked(edge.target_port == side)
            b.triggered.connect(lambda _c=False, s=side: edge.set_forced_port(edge.source_port, s))
        for sub, is_out in ((out_menu, True), (in_menu, False)):
            sub.addSeparator()
            auto = sub.addAction("Automático")
            auto.setCheckable(True)
            auto.setChecked((edge.source_port if is_out else edge.target_port) is None)
            if is_out:
                auto.triggered.connect(lambda: edge.set_forced_port(None, edge.target_port))
            else:
                auto.triggered.connect(lambda: edge.set_forced_port(edge.source_port, None))
        menu.addSeparator()
        self._add_style_menu(menu, relation_id)
        menu.addSeparator()
        menu.addAction("Eliminar relación…", lambda: self.relations.delete_relation(relation_id))
        return menu

    # ------------------------------------------------------------------ estilo de las flechas
    def _style_targets(self, relation_id: int) -> list[int]:
        """La flecha del clic o, si está entre varias seleccionadas, todas las seleccionadas."""
        selected = self.scene.selected_edge_ids()
        return list(selected) if len(selected) > 1 and relation_id in selected else [relation_id]

    def _add_style_menu(self, menu: QMenu, relation_id: int) -> None:
        ids = self._style_targets(relation_id)
        rels = [r for r in (self.project.relation(i) for i in ids) if r is not None]
        if not rels:
            return
        title = "Estilo de la flecha" if len(ids) == 1 else f"Estilo de las {len(ids)} flechas seleccionadas"
        style_menu = menu.addMenu(title)

        def all_same(values: list) -> bool:
            return len(set(values)) == 1

        current_colors = [(r.line_color or palette.EDGE_COLOR).upper() for r in rels]
        color_menu = style_menu.addMenu("Color")
        for name, hex_color in palette.EDGE_PALETTE:
            act = QAction(color_icon(hex_color), name, menu)
            act.setCheckable(True)
            act.setChecked(all_same(current_colors) and current_colors[0] == hex_color.upper())
            act.triggered.connect(lambda _c=False, h=hex_color: self.project.set_relations_style(ids, color=h))
            color_menu.addAction(act)
        color_menu.addSeparator()
        color_menu.addAction("Personalizar…", lambda: self.pick_edge_color(ids))
        act_default = color_menu.addAction("Color predeterminado",
                                           lambda: self.project.set_relations_style(ids, color=None))
        act_default.setEnabled(any(r.line_color for r in rels))

        dashes = [r.line_dash for r in rels]
        dash_menu = style_menu.addMenu("Trazo")
        for key in DASH_KEYS:
            act = QAction(dash_icon(key), DASH_LABELS[key], menu)
            act.setCheckable(True)
            act.setChecked(all_same(dashes) and dashes[0] == key)
            act.triggered.connect(lambda _c=False, k=key: self.project.set_relations_style(ids, dash=k))
            dash_menu.addAction(act)

        widths = [r.line_width if r.line_width is not None else DEFAULT_WIDTH for r in rels]
        width_menu = style_menu.addMenu("Grosor")
        for name, preset in WIDTH_PRESETS:
            act = QAction(width_icon(preset), f"{name} ({preset:g} px)", menu)
            act.setCheckable(True)
            act.setChecked(all_same(widths) and abs(widths[0] - preset) < 1e-6)
            value = None if abs(preset - DEFAULT_WIDTH) < 1e-6 else preset
            act.triggered.connect(lambda _c=False, w=value: self.project.set_relations_style(ids, width=w))
            width_menu.addAction(act)

        style_menu.addSeparator()
        style_menu.addAction("Estilo de línea…", lambda: self.edit_edge_style(ids))
        act_reset = style_menu.addAction(
            "Restablecer estilo", lambda: self.project.set_relations_style(ids, color=None, dash="solid", width=None))
        act_reset.setEnabled(any(r.has_custom_style for r in rels))

    def pick_edge_color(self, ids: list[int]) -> None:
        rel = self.project.relation(ids[0]) if ids else None
        if rel is None:
            return
        title = "Color de la flecha" if len(ids) == 1 else f"Color para {len(ids)} flechas"
        chosen = QColorDialog.getColor(QColor(rel.line_color or palette.EDGE_COLOR), self.window, title)
        if chosen.isValid():
            self.project.set_relations_style(ids, color=chosen.name().upper())

    def edit_edge_style(self, ids: list[int]) -> None:
        rel = self.project.relation(ids[0]) if ids else None
        if rel is None:
            return
        dialog = LineStyleDialog(rel.line_color, rel.line_dash, rel.line_width, self.window, count=len(ids))
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        color, dash, width = dialog.values()
        self.project.set_relations_style(ids, color=color, dash=dash, width=width)

    def _canvas_menu(self, scene_pos: QPointF, global_pos: QPoint) -> None:
        menu = QMenu(self.window)
        menu.addAction("Nueva sección aquí…", lambda: self.new_section(scene_pos))
        menu.addSeparator()
        menu.addAction(self.window.act_fit)
        menu.addAction(self.window.act_zoom_reset)
        menu.addAction(self.window.act_arrange_new)
        menu.addSeparator()
        menu.addAction(self.window.act_export_png)
        menu.addAction(self.window.act_export_svg)
        menu.addAction(self.window.act_copy_image)
        if self._highlight_active:
            menu.addSeparator()
            menu.addAction("Quitar resaltado", self.clear_highlight)
        menu.exec(global_pos)
