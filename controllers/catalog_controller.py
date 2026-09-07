"""Controlador del catálogo MasterFormat: panel lateral, arrastre al mapa, clasificación y reemplazo."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from PyQt6.QtCore import QObject, QPointF, QSettings
from PyQt6.QtWidgets import QFileDialog, QMessageBox

from config.settings import SETTINGS_LAST_DIR
from models.master_catalog import MasterCatalogError
from models.masterformat_tree_model import MasterFormatTreeModel
from models.project_model import ProjectModel
from views.main_window import TAB_MAP, MainWindow


class CatalogController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, tree_model: MasterFormatTreeModel,
                 on_catalog_replaced: Callable[[], None], parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.tree_model = tree_model
        self.panel = window.catalog_panel
        self._on_catalog_replaced = on_catalog_replaced

        self.panel.addRequested.connect(self.add_from_catalog)
        self.panel.useAsRequested.connect(self.use_as)
        self.panel.centerRequested.connect(self.center_on)
        self.panel.categoryOverrideRequested.connect(self.set_category_override)
        self.panel.clearOverrideRequested.connect(self.clear_category_override)
        self.panel.editTitleRequested.connect(self.edit_title)
        self.panel.addChildRequested.connect(self.add_entry)
        self.panel.hideRequested.connect(self.hide_entry)
        self.panel.restoreRequested.connect(self.restore_entry)
        window.view.sectionsDropped.connect(self.on_dropped)
        window.act_replace_catalog.triggered.connect(self.replace_catalog)
        window.act_reset_catalog.triggered.connect(self.reset_catalog)
        window.act_apply_catalog_categories.triggered.connect(self.apply_catalog_categories)
        window.act_clear_category_overrides.triggered.connect(self.clear_all_overrides)
        window.act_export_catalog.triggered.connect(self.export_catalog)
        window.act_add_catalog_entry.triggered.connect(lambda: self.add_entry(""))
        window.act_clear_catalog_edits.triggered.connect(self.clear_all_edits)

        for sig in (project.projectLoaded, project.projectClosed):
            sig.connect(self._refresh_project_keys)
            sig.connect(self._refresh_categories)
        for sig in (project.sectionAdded, project.sectionUpdated, project.sectionRemoved):
            sig.connect(lambda _sid: self._refresh_project_keys())
        project.categoriesChanged.connect(self._refresh_categories)
        self._refresh_project_keys()
        self._refresh_categories()
        self._update_catalog_status()

    # ------------------------------------------------------------------ estado
    def _refresh_project_keys(self) -> None:
        self.tree_model.set_project_keys({s.code_key for s in self.project.sections()})

    def _refresh_categories(self) -> None:
        cats = self.project.categories() if self.project.is_open else []
        self.panel.set_categories([(c.name, c.fill_color, c.border_color) for c in cats])

    def _update_catalog_status(self) -> None:
        master = self.project.master
        self.window.act_reset_catalog.setEnabled(master.is_user_copy)
        self.window.act_clear_category_overrides.setEnabled(master.override_count > 0)
        self.window.act_clear_catalog_edits.setEnabled(master.edit_count > 0)
        title = "Secciones MasterFormat"
        if master.is_user_copy:
            title += " (copia del usuario)"
        if master.edit_count:
            title += f" · {master.edit_count} edición(es)"
        self.panel.setWindowTitle(title)

    # ------------------------------------------------------------------ edición del catálogo
    def edit_title(self, code_key: str) -> None:
        from views.components.catalog_entry_dialog import CatalogEntryDialog

        rec = self.project.master.get(code_key, include_hidden=True)
        if rec is None:
            return
        dialog = CatalogEntryDialog(self.window, code=rec.code, title_en=rec.title_en,
                                    title_es=rec.title_es or "", is_new=False)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        _code, title_en, title_es, _cat = dialog.values()
        try:
            self.project.master.set_title(code_key, title_en, title_es)
        except MasterCatalogError as exc:
            QMessageBox.warning(self.window, "Catálogo", str(exc))
            return
        self._after_catalog_change()
        self.window.show_status(f"Título de {rec.code} actualizado en el catálogo.", 6000)

    def add_entry(self, parent_key: str) -> None:
        from views.components.catalog_entry_dialog import CatalogEntryDialog

        master = self.project.master
        parent = master.get(parent_key, include_hidden=True) if parent_key else None
        prefill = ""
        if parent is not None:
            # Sugerir el siguiente hueco de la rama: "03 30 " para nivel 2, "03 30 53." para nivel 3.
            prefill = {1: parent.code[:3], 2: parent.code[:6], 3: parent.code + "."}.get(parent.level, "")
        categories = [c.name for c in self.project.categories()] if self.project.is_open else \
            [s.name for s in __import__("config.palette", fromlist=["DEFAULT_CATEGORIES"]).DEFAULT_CATEGORIES]
        default_cat = master.effective_category(parent) if parent is not None else None
        dialog = CatalogEntryDialog(self.window, code=prefill, is_new=True, categories=categories,
                                    category=default_cat, parent_label=parent.label if parent else None)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        code, title_en, title_es, category = dialog.values()
        try:
            rec = master.add_section(code, title_en, title_es, category)
        except MasterCatalogError as exc:
            QMessageBox.warning(self.window, "Catálogo", str(exc))
            return
        self._after_catalog_change()
        self.panel.reveal(rec.code_key)
        self.window.show_status(f"Sección {rec.label} agregada al catálogo ({category}).", 7000)

    def hide_entry(self, code_key: str) -> None:
        master = self.project.master
        rec = master.get(code_key, include_hidden=True)
        if rec is None:
            return
        children = master.children(code_key)
        detail = f"\nSus {len(children)} secciones hijas seguirán visibles." if children else ""
        verb = "Eliminar" if master.is_user_added(code_key) else "Ocultar"
        answer = QMessageBox.question(
            self.window, f"{verb} del catálogo",
            f"¿{verb} «{rec.label}» del catálogo MasterFormat?{detail}\n"
            "Las secciones ya creadas en los proyectos no se modifican.")
        if answer != QMessageBox.StandardButton.Yes:
            return
        master.hide(code_key)
        self._after_catalog_change()

    def restore_entry(self, code_key: str) -> None:
        self.project.master.restore_entry(code_key)
        self._after_catalog_change()
        self.panel.reveal(code_key)

    def clear_all_edits(self) -> None:
        answer = QMessageBox.question(self.window, "Ediciones del catálogo",
                                      "¿Quitar todas las ediciones (títulos, secciones agregadas y ocultas) "
                                      "y volver al catálogo original?")
        if answer == QMessageBox.StandardButton.Yes:
            self.project.master.clear_edits()
            self._after_catalog_change()

    def export_catalog(self) -> None:
        settings = QSettings()
        start = settings.value(SETTINGS_LAST_DIR, "", type=str)
        path, _ = QFileDialog.getSaveFileName(self.window, "Exportar catálogo a Excel",
                                              str(Path(start) / "catalogo_masterformat.xlsx"),
                                              "Libro de Excel (*.xlsx)")
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".xlsx":
            p = p.with_suffix(".xlsx")
        try:
            count = self.project.master.export_xlsx(p, include_hidden=True)
        except MasterCatalogError as exc:
            QMessageBox.critical(self.window, "Exportar catálogo", str(exc))
            return
        settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        QMessageBox.information(self.window, "Exportar catálogo",
                                f"{count} secciones exportadas a:\n{p}\n\nPuede editar el archivo en Excel y "
                                "cargarlo con «Reemplazar catálogo MasterFormat…».")

    # ------------------------------------------------------------------ acciones del panel
    def add_from_catalog(self, code_key: str, position: tuple[float, float] | None = None) -> int | None:
        if not self.project.is_open:
            self.window.show_status("Abra o cree un proyecto antes de agregar secciones.", 6000)
            return None
        try:
            section, created = self.project.create_section_from_catalog(code_key)
        except ValueError as exc:
            QMessageBox.warning(self.window, "Catálogo", str(exc))
            return None
        if position is not None:
            self.project.move_node(section.id, position[0], position[1], pinned=True)
        entry = self.window.entry
        focused = self.window.focusWidget()
        if focused is entry.picker_a or focused is entry.picker_b:
            which = "a" if focused is entry.picker_a else "b"
            entry.set_picker_section(which, section.id, section.label)
        cat = self.project.category(section.category_id)
        suffix = f" · {cat.name}" if cat else ""
        self.window.show_status(
            f"Sección {section.label} {'agregada' if created else 'ya estaba en el proyecto'}{suffix}.", 6000)
        return section.id

    def use_as(self, which: str, code_key: str) -> None:
        section_id = self.add_from_catalog(code_key)
        if section_id is not None:
            section = self.project.section(section_id)
            self.window.entry.set_picker_section(which, section_id, section.label if section else "")

    def center_on(self, code_key: str) -> None:
        record = self.project.master.get(code_key)
        section = self.project.section_by_code(record.code) if record else None
        if section is not None:
            self.window.tabs.setCurrentIndex(TAB_MAP)
            self.window.view.center_on_node(section.id)
            node = self.window.scene.nodes.get(section.id)
            if node is not None:
                self.window.scene.clearSelection()
                node.setSelected(True)

    def on_dropped(self, keys: list[str], scene_pos: QPointF) -> None:
        if not self.project.is_open:
            return
        x, y = scene_pos.x(), scene_pos.y()
        for i, key in enumerate(keys):
            self.add_from_catalog(key, (x, y + i * 80))

    # ------------------------------------------------------------------ clasificación
    def set_category_override(self, code_key: str, category: str, whole_branch: bool) -> None:
        self.project.master.set_category_override(code_key, category, whole_branch)
        self._after_classification_change()
        record = self.project.master.get(code_key)
        scope = "y su rama" if whole_branch else "(solo esta sección)"
        self.window.show_status(
            f"Clasificación de {record.code if record else code_key} {scope} → {category}. "
            "Las secciones ya creadas no cambian; use «Aplicar clasificación del catálogo…» si lo desea.", 9000)

    def clear_category_override(self, code_key: str) -> None:
        self.project.master.clear_category_override(code_key)
        self._after_classification_change()

    def clear_all_overrides(self) -> None:
        answer = QMessageBox.question(self.window, "Correcciones de clasificación",
                                      "¿Quitar todas las correcciones y volver a la clasificación del catálogo?")
        if answer == QMessageBox.StandardButton.Yes:
            self.project.master.clear_category_overrides()
            self._after_classification_change()

    def apply_catalog_categories(self) -> None:
        if not self.project.is_open:
            return
        changes = self.project.reclassify_from_catalog(apply=False)
        if not changes:
            QMessageBox.information(self.window, "Clasificación",
                                    "Todas las secciones del catálogo ya tienen la clasificación por defecto.")
            return
        preview = "\n".join(f"  • {s.label}: → {c.name}" for s, c in changes[:12])
        more = f"\n  … y {len(changes) - 12} más" if len(changes) > 12 else ""
        answer = QMessageBox.question(
            self.window, "Aplicar clasificación del catálogo",
            f"{len(changes)} sección(es) cambiarían de categoría:\n\n{preview}{more}\n\n"
            "Los colores personalizados por sección se conservan. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        applied = self.project.reclassify_from_catalog(apply=True)
        self.window.show_status(f"{len(applied)} sección(es) reclasificadas según el catálogo.", 8000)

    def _after_classification_change(self) -> None:
        self.tree_model.refresh_all()
        self._update_catalog_status()
        self._on_catalog_replaced()  # el autocompletado muestra los colores de la clasificación

    # ------------------------------------------------------------------ reemplazo del catálogo
    def replace_catalog(self) -> None:
        settings = QSettings()
        start = settings.value(SETTINGS_LAST_DIR, "", type=str)
        path, _ = QFileDialog.getOpenFileName(
            self.window, "Reemplazar catálogo MasterFormat", start,
            "Excel, CSV o SQLite (*.xlsx *.xlsm *.csv *.sqlite *.db);;Todos los archivos (*)")
        if not path:
            return
        try:
            count = self.project.master.replace_from_file(Path(path))
        except MasterCatalogError as exc:
            QMessageBox.critical(self.window, "Catálogo MasterFormat", str(exc))
            return
        settings.setValue(SETTINGS_LAST_DIR, str(Path(path).parent))
        self._after_catalog_change()
        QMessageBox.information(self.window, "Catálogo MasterFormat",
                                f"Catálogo reemplazado: {count} secciones.\nSe guardó una copia en su perfil "
                                "de usuario y se usará en todos los proyectos.")

    def reset_catalog(self) -> None:
        answer = QMessageBox.question(self.window, "Restaurar catálogo",
                                      "¿Volver al catálogo MasterFormat incluido en la aplicación?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.project.master.reset_to_bundled()
        self._after_catalog_change()
        self.window.show_status("Catálogo MasterFormat restaurado.", 6000)

    def _after_catalog_change(self) -> None:
        self.tree_model.reload()
        self._refresh_project_keys()
        self._update_catalog_status()
        self._on_catalog_replaced()
