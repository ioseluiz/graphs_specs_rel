"""Controlador principal: ciclo de vida del archivo de proyecto y wiring de sub-controladores."""
from __future__ import annotations

from pathlib import Path

from PyQt6.QtCore import QObject, QSettings
from PyQt6.QtWidgets import QApplication, QFileDialog, QInputDialog, QMessageBox

from config.settings import (
    APP_DISPLAY_NAME,
    APP_NAME,
    APP_VERSION,
    PROJECT_EXTENSION,
    PROJECT_FILE_FILTER,
    SETTINGS_LAST_DIR,
    SETTINGS_RECENT_FILES,
    SETTINGS_SPLITTER_STATE,
    SETTINGS_WINDOW_GEOMETRY,
    SETTINGS_WINDOW_STATE,
    default_catalog_path,
    recent_files_max,
)
from controllers.analysis_controller import AnalysisController
from controllers.canvas_controller import CanvasController
from controllers.catalog_controller import CatalogController
from controllers.export_controller import ExportController
from controllers.help_controller import HelpController
from controllers.relations_controller import RelationsController
from controllers.sections_controller import SectionsController
from controllers.view3d_controller import View3DController
from models.catalog_importer import CatalogImportError, import_for
from models.database import ProjectFileError, ProjectLockedError
from models.project_bootstrap import classify_paths, project_meta_from, project_path_for
from models.project_io import (
    ProjectIOError,
    apply_tables,
    export_tables_xlsx,
    read_tables,
    write_template_csv,
    write_template_xlsx,
)
from models.project_model import ProjectModel
from models.relations_table_model import RelationsTableModel
from models.section_completer_model import SectionCompleterModel
from utils.debounce import Debouncer
from utils.workers import busy_cursor, progress_dialog, run_with_progress
from views.components.categories_dialog import CategoriesDialog
from views.components.import_catalog_dialog import ImportCatalogDialog
from views.main_window import MainWindow


class MainController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, table_model: RelationsTableModel,
                 completer_model: SectionCompleterModel, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.table_model = table_model
        self.completer_model = completer_model
        self.settings = QSettings()
        # Reconstruir el autocompletado (~30 ms con el catálogo completo) una vez por ráfaga de cambios,
        # no una vez por cada sección importada.
        self.rebuild_completer_later = Debouncer(self._rebuild_completer, 50, self)
        self._onedrive_hint_shown = False

        self.relations = RelationsController(project, window, table_model, self)
        self.canvas = CanvasController(project, window, self.relations, self)
        self.analysis = AnalysisController(project, window, self.canvas, self)
        self.view3d = View3DController(project, window, self)
        self.export = ExportController(window, self)
        self.export.project = project
        self.catalog = CatalogController(project, window, window.catalog_tree_model,
                                         self.rebuild_completer_later, self)
        self.sections = SectionsController(project, window, self.canvas, self)
        self.help = HelpController(window, self)
        window.filesDropped.connect(self.open_dropped_files)
        window.view.filesDropped.connect(self.open_dropped_files)

        window.act_new.triggered.connect(self.new_project)
        window.act_open.triggered.connect(self.open_project_dialog)
        window.act_save.triggered.connect(self.save)
        window.act_save_copy.triggered.connect(self.save_copy)
        for sig in (project.sectionAdded, project.sectionUpdated, project.sectionRemoved, project.relationAdded,
                    project.relationUpdated, project.relationRemoved, project.relationGeometryChanged,
                    project.categoriesChanged, project.statusesChanged, project.responsiblesChanged,
                    project.projectMetaChanged):
            sig.connect(lambda *_a: self._mark_saved())
        project.positionChanged.connect(lambda *_a: self._mark_saved())
        window.act_close.triggered.connect(self.close_project)
        window.act_exit.triggered.connect(window.close)
        window.act_categories.triggered.connect(self.edit_categories)
        window.act_import_catalog.triggered.connect(self.import_catalog)
        window.act_clear_catalog.triggered.connect(self.clear_catalog)
        window.act_import_tables.triggered.connect(self.import_tables)
        window.act_export_tables.triggered.connect(self.export_tables)
        window.act_save_template.triggered.connect(self.save_template)
        window.act_about.triggered.connect(self.about)
        window.recentFileActivated.connect(self.open_project)
        window.header.metaEdited.connect(self.project.update_meta)
        window.aboutToClose.connect(self._save_window_state)

        project.projectLoaded.connect(self._on_project_loaded)
        project.projectClosed.connect(self._on_project_closed)
        project.projectMetaChanged.connect(self._refresh_header)
        for sig in (project.sectionAdded, project.sectionUpdated, project.sectionRemoved,
                    project.categoriesChanged, project.catalogChanged):
            sig.connect(self.rebuild_completer_later)

        self._restore_window_state()
        self._refresh_recent()

    # ------------------------------------------------------------------ arranque
    def start(self, path: str | None = None) -> None:
        self.window.show()
        if path:
            # «Abrir con…» desde Windows: un .specrel se abre; un .xlsx/.csv de la plantilla crea el mapa.
            self.open_dropped_files([path])

    # ------------------------------------------------------------------ recientes
    def _recent(self) -> list[str]:
        value = self.settings.value(SETTINGS_RECENT_FILES, [], type=list)
        return [str(p) for p in value if p]

    def _push_recent(self, path: Path) -> None:
        recent = [p for p in self._recent() if Path(p) != path]
        recent.insert(0, str(path))
        self.settings.setValue(SETTINGS_RECENT_FILES, recent[: recent_files_max()])
        self._refresh_recent()

    def _refresh_recent(self) -> None:
        existing = [p for p in self._recent() if Path(p).exists()]
        self.window.set_recent_files(existing)

    # ------------------------------------------------------------------ archivo
    def new_project(self) -> None:
        start = self.settings.value(SETTINGS_LAST_DIR, "", type=str)
        path, _ = QFileDialog.getSaveFileName(
            self.window, "Nuevo proyecto", str(Path(start) / f"proyecto{PROJECT_EXTENSION}"), PROJECT_FILE_FILTER)
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != PROJECT_EXTENSION:
            p = p.with_suffix(PROJECT_EXTENSION)
        code, ok = QInputDialog.getText(self.window, "Nuevo proyecto", "Código del proyecto (p. ej. CC-25-01):")
        if not ok:
            return
        name, ok = QInputDialog.getText(self.window, "Nuevo proyecto", "Nombre del proyecto:")
        if not ok:
            return
        try:
            self.project.new_project(p, code.strip(), name.strip())
        except ProjectFileError as exc:
            QMessageBox.critical(self.window, "Nuevo proyecto", str(exc))
            return
        self._after_project_created(p)

    def _after_project_created(self, p: Path) -> None:
        self.settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        self._push_recent(p)
        catalog = default_catalog_path()
        if catalog is not None:
            self._import_catalog_file(catalog, None, 3, silent=True)

    def open_project_dialog(self) -> None:
        start = self.settings.value(SETTINGS_LAST_DIR, "", type=str)
        path, _ = QFileDialog.getOpenFileName(self.window, "Abrir proyecto", start, PROJECT_FILE_FILTER)
        if path:
            self.open_project(path)

    def _rebuild_completer(self) -> None:
        self.completer_model.rebuild(self.project)

    def open_project(self, path: str) -> None:
        p = Path(path)
        try:
            with busy_cursor():
                self.project.open_project(p)
        except ProjectLockedError as exc:
            retry = QMessageBox.question(
                self.window, "Archivo bloqueado", f"{exc}\n\n¿Reintentar?",
                QMessageBox.StandardButton.Retry | QMessageBox.StandardButton.Cancel)
            if retry == QMessageBox.StandardButton.Retry:
                self.open_project(path)
            return
        except ProjectFileError as exc:
            QMessageBox.critical(self.window, "Abrir proyecto", str(exc))
            recent = [r for r in self._recent() if Path(r) != p]
            self.settings.setValue(SETTINGS_RECENT_FILES, recent)
            self._refresh_recent()
            return
        self.settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        self._push_recent(p)
        self._maybe_warn_onedrive(p)

    def _maybe_warn_onedrive(self, p: Path) -> None:
        """Aviso único por sesión: OneDrive puede bloquear el archivo y detener la app unos segundos."""
        if self._onedrive_hint_shown or "onedrive" not in str(p).lower():
            return
        self._onedrive_hint_shown = True
        self.window.show_status(
            "Este proyecto está en una carpeta de OneDrive: si la sincronización bloquea el archivo, un cambio "
            "puede tardar en guardarse. Recomendado: clic derecho al archivo → «Mantener siempre en este "
            "dispositivo», o trabajar en una carpeta local.", 15000)

    def _mark_saved(self) -> None:
        if self.project.is_open:
            from datetime import datetime

            self.window.set_saved_indicator(f"Guardado automáticamente {datetime.now():%H:%M:%S}")

    def save(self) -> None:
        """«Guardar» explícito: todo ya está en el archivo; se confirma y se informa dónde."""
        if not self.project.is_open:
            return
        try:
            path = self.project.checkpoint()
        except ProjectFileError as exc:
            QMessageBox.critical(self.window, "Guardar", str(exc))
            return
        self._mark_saved()
        self.window.show_status(f"Proyecto guardado en {path}. Los cambios se guardan automáticamente.", 8000)

    def save_copy(self) -> None:
        if not self.project.is_open:
            return
        start = self.settings.value(SETTINGS_LAST_DIR, "", type=str)
        base_dir = self.project.path.parent if self.project.path else Path(start)
        suggested = (self.project.path.stem + "_copia" if self.project.path else "proyecto") + PROJECT_EXTENSION
        path, _ = QFileDialog.getSaveFileName(
            self.window, "Guardar copia como (el proyecto abierto ya está guardado)",
            str(base_dir / suggested), PROJECT_FILE_FILTER)
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != PROJECT_EXTENSION:
            p = p.with_suffix(PROJECT_EXTENSION)
        try:
            self.project.save_copy(p)
        except ValueError as exc:
            QMessageBox.information(self.window, "Guardar copia", str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self.window, "Guardar copia", str(exc))
            return
        self.settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        self.window.show_status(f"Copia guardada en {p}. El proyecto abierto sigue siendo {self.project.path}.", 8000)

    def close_project(self) -> None:
        self.project.close()

    def _on_project_loaded(self) -> None:
        self.rebuild_completer_later.cancel()
        self.completer_model.rebuild(self.project)
        self._refresh_header()
        self.window.set_project_open(True)
        self.window.setWindowTitle(f"{self.project.meta().header} — {APP_NAME}")
        self.window.entry.picker_a.setFocus()
        self._mark_saved()
        n_sec, n_rel = len(self.project.sections()), len(self.project.relations())
        self.window.show_status(f"Proyecto abierto: {n_sec} secciones, {n_rel} relaciones. "
                                "Los cambios se guardan automáticamente.")

    def _on_project_closed(self) -> None:
        self.rebuild_completer_later.cancel()
        self.completer_model.set_entries([])
        self.window.set_project_open(False)
        self.window.setWindowTitle(APP_DISPLAY_NAME)
        self._refresh_recent()

    def _refresh_header(self) -> None:
        meta = self.project.meta()
        self.window.header.set_meta(meta.code, meta.name)
        if self.project.is_open:
            self.window.setWindowTitle(f"{meta.header} — {APP_NAME}")

    # ------------------------------------------------------------------ categorías y catálogo
    def edit_categories(self) -> None:
        cats = self.project.categories()
        usage = {c.id: self.project.categories_repo.usage_count(c.id) for c in cats}
        dialog = CategoriesDialog(cats, usage, self.window)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        edits, deleted = dialog.result_edits()
        for cid in deleted:
            self.project.remove_category(cid)
        by_id = {c.id: c for c in self.project.categories()}
        for order, edit in enumerate(edits):
            if edit.id is None:
                cat = self.project.add_category(edit.name, edit.fill, edit.border)
                cat.sort_order = order
                cat.is_default = edit.is_default
                self.project.update_category(cat)
            elif edit.id in by_id:
                cat = by_id[edit.id]
                cat.name, cat.fill_color, cat.border_color = edit.name, edit.fill, edit.border
                cat.sort_order, cat.is_default = order, edit.is_default
                self.project.update_category(cat)
        self.window.show_status("Categorías actualizadas.")

    def import_catalog(self) -> None:
        dialog = ImportCatalogDialog(self.window)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        path, mapping, level = dialog.result()
        self._import_catalog_file(path, mapping, level)

    def _import_catalog_file(self, path: Path, mapping, level: int, silent: bool = False) -> None:
        try:
            entries = import_for(path, mapping, level)
        except CatalogImportError as exc:
            if not silent:
                QMessageBox.warning(self.window, "Importar catálogo", str(exc))
            return
        count = self.project.merge_catalog(entries)
        self.window.show_status(f"Catálogo importado: {count} secciones disponibles para autocompletar.")

    def clear_catalog(self) -> None:
        if not self.project.is_open:
            return
        answer = QMessageBox.question(self.window, "Vaciar catálogo",
                                      "¿Quitar todas las entradas del catálogo de autocompletado? "
                                      "Las secciones del proyecto no se modifican.")
        if answer == QMessageBox.StandardButton.Yes:
            self.project.clear_catalog()

    # ------------------------------------------------------------------ tablas Excel / CSV
    def save_template(self) -> None:
        start = self.settings.value(SETTINGS_LAST_DIR, "", type=str)
        path, selected = QFileDialog.getSaveFileName(
            self.window, "Guardar plantilla", str(Path(start) / "plantilla_specrel.xlsx"),
            "Libro de Excel (*.xlsx);;Carpeta con CSV (*.csv)")
        if not path:
            return
        p = Path(path)
        try:
            if selected.startswith("Carpeta") or p.suffix.lower() == ".csv":
                sec, rel = write_template_csv(p.parent / p.stem)
                self.window.show_status(f"Plantilla CSV guardada: {sec.name} y {rel.name} en {sec.parent}", 8000)
                QMessageBox.information(self.window, "Plantilla",
                                        f"Se crearon dos archivos CSV en:\n{sec.parent}\n\n"
                                        "Complete las tablas y luego use Archivo → Tablas → Importar.")
            else:
                if p.suffix.lower() != ".xlsx":
                    p = p.with_suffix(".xlsx")
                write_template_xlsx(p)
                self.window.show_status(f"Plantilla guardada: {p}", 8000)
                QMessageBox.information(self.window, "Plantilla",
                                        f"Plantilla guardada en:\n{p}\n\nTiene hojas «Secciones», «Relaciones» "
                                        "e «Instrucciones». Complete las tablas y luego use "
                                        "Archivo → Tablas → Importar tablas.")
            self.settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        except ProjectIOError as exc:
            QMessageBox.critical(self.window, "Plantilla", str(exc))

    def import_tables(self) -> None:
        """Con proyecto abierto: agrega las tablas. Sin proyecto: crea el mapa (y el .specrel) desde el archivo."""
        start = self.settings.value(SETTINGS_LAST_DIR, "", type=str)
        title = ("Importar tablas de secciones y relaciones" if self.project.is_open
                 else "Crear mapa desde Excel o CSV (plantilla)")
        paths, _ = QFileDialog.getOpenFileNames(
            self.window, title, start, "Excel o CSV (*.xlsx *.xlsm *.csv);;Todos los archivos (*)")
        if not paths:
            return
        files = [Path(p) for p in paths]
        if self.project.is_open:
            self._read_tables_then(files, lambda tables: self._confirm_and_apply_tables(tables, files))
        else:
            self.create_project_from_tables(files)

    def _read_tables_then(self, files: list[Path], on_done) -> None:
        # Leer el Excel (openpyxl puede tardar segundos en libros grandes) sin bloquear la ventana.
        run_with_progress(self.window, "Leer tablas", "Leyendo el archivo…", read_tables, files,
                          on_done=on_done, on_error=self._on_import_read_failed)

    # ------------------------------------------------------------------ archivos arrastrados / «Abrir con»
    def open_dropped_files(self, paths: list) -> None:
        """Rutas soltadas sobre la ventana o pasadas por línea de comandos."""
        projects, tables, others = classify_paths([str(p) for p in paths])
        if projects:
            self.open_project(str(projects[0]))
            if len(projects) > 1 or tables:
                self.window.show_status("Se abrió el primer proyecto; los demás archivos se ignoraron.", 8000)
            return
        if tables:
            if not self.project.is_open:
                self.create_project_from_tables(tables)
                return
            names = ", ".join(p.name for p in tables)
            choice = self._ask_choice(
                "Archivo de tablas",
                f"¿Qué desea hacer con {names}?",
                ["Agregar al proyecto abierto", "Crear un mapa nuevo con este archivo"],
                informative="«Agregar» crea o actualiza secciones y relaciones en el proyecto actual sin borrar "
                            "nada. «Crear un mapa nuevo» guarda otro proyecto (.specrel) junto al archivo.")
            if choice == 0:
                self._read_tables_then(tables, lambda t: self._confirm_and_apply_tables(t, tables))
            elif choice == 1:
                self.create_project_from_tables(tables)
            return
        if others:
            self.window.show_status(
                f"Formato no soportado: {others[0].name}. Arrastre un proyecto {PROJECT_EXTENSION} o un archivo "
                ".xlsx/.csv de la plantilla.", 8000)

    def _ask_choice(self, title: str, text: str, options: list[str], informative: str = "",
                    destructive: int | None = None) -> int | None:
        """Pregunta con botones propios; devuelve el índice elegido o None si se cancela."""
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(text)
        if informative:
            box.setInformativeText(informative)
        buttons = []
        for i, label in enumerate(options):
            role = QMessageBox.ButtonRole.DestructiveRole if i == destructive else QMessageBox.ButtonRole.AcceptRole
            buttons.append(box.addButton(label, role))
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(buttons[0])
        box.exec()
        clicked = box.clickedButton()
        return next((i for i, b in enumerate(buttons) if b is clicked), None)

    def create_project_from_tables(self, files: list[Path]) -> None:
        """Lee las tablas y crea un proyecto nuevo con ellas (el .specrel se guarda junto al primer archivo)."""
        self._read_tables_then(files, lambda tables: self._create_project_with_tables(tables, files))

    def _create_project_with_tables(self, tables, files: list[Path]) -> None:
        dest = project_path_for(files[0])
        if dest.exists():
            choice = self._ask_choice(
                "Crear mapa desde Excel",
                f"Ya existe un proyecto con ese nombre:\n{dest}",
                ["Abrir el existente y agregar las tablas", "Reemplazar", "Elegir otra ubicación…"],
                informative="«Reemplazar» borra el proyecto existente y crea uno nuevo solo con estas tablas.",
                destructive=1)
            if choice == 0:
                self.open_project(str(dest))
                if self.project.is_open:
                    self._confirm_and_apply_tables(tables, files)
                return
            if choice == 2:
                path, _ = QFileDialog.getSaveFileName(
                    self.window, "Guardar el proyecto nuevo como", str(dest), PROJECT_FILE_FILTER)
                if not path:
                    return
                dest = Path(path)
                if dest.suffix.lower() != PROJECT_EXTENSION:
                    dest = dest.with_suffix(PROJECT_EXTENSION)
            elif choice != 1:
                return
        code, name = project_meta_from(tables, files[0])
        try:
            with busy_cursor():
                self.project.new_project(dest, code, name)
        except ProjectFileError as exc:
            QMessageBox.critical(self.window, "Crear mapa desde Excel", str(exc))
            return
        self._after_project_created(dest)
        summary = self.apply_tables_with_progress(tables)
        if summary is None:
            return
        # Proyecto recién creado: nada está fijado, así que se acomoda todo el mapa (nunca en proyectos existentes).
        self.canvas.arrange_unpinned()
        self.canvas.view.fit_all()
        self._show_import_summary("Mapa creado", summary,
                                  f"Proyecto guardado en:\n{dest}\n\nLas secciones se acomodaron "
                                  "automáticamente; puede moverlas y no volverán a moverse.")
        self.window.show_status(f"Mapa creado en {dest}: {len(self.project.sections())} secciones, "
                                f"{len(self.project.relations())} relaciones. Los cambios se guardan "
                                "automáticamente.", 12000)

    def _show_import_summary(self, title: str, summary, header: str = "") -> None:
        """Resumen de la importación con botón «Copiar detalle» (todas las filas omitidas o con problemas)."""
        box = QMessageBox(self.window)
        box.setWindowTitle(title)
        box.setIcon(QMessageBox.Icon.Information)
        box.setText(header or title)
        box.setInformativeText(summary.text())
        copy_btn = None
        if summary.skipped or summary.errors:
            copy_btn = box.addButton("Copiar detalle", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Ok)
        box.exec()
        if copy_btn is not None and box.clickedButton() is copy_btn:
            QApplication.clipboard().setText(summary.full_text())
            self.window.show_status("Detalle de la importación copiado al portapapeles.", 6000)

    def _on_import_read_failed(self, exc: BaseException, _tb: str) -> None:
        if isinstance(exc, ProjectIOError):
            QMessageBox.warning(self.window, "Importar tablas", str(exc))
        else:
            QMessageBox.critical(self.window, "Importar tablas", f"No se pudo leer el archivo:\n{exc}")

    def _confirm_and_apply_tables(self, tables, files: list[Path]) -> None:
        if not self.project.is_open:
            return
        n_sec, n_rel = len(tables.sections), len(tables.relations)
        answer = QMessageBox.question(
            self.window, "Importar tablas",
            f"Se encontraron {n_sec} fila(s) de secciones y {n_rel} fila(s) de relaciones.\n\n"
            "Las secciones existentes se actualizan y las nuevas se crean; nada se elimina. ¿Continuar?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        summary = self.apply_tables_with_progress(tables)
        if summary is None:
            return
        self.settings.setValue(SETTINGS_LAST_DIR, str(files[0].parent))
        self.canvas.view.fit_all()
        self._show_import_summary("Importación completada", summary)
        self.window.show_status(
            f"Importadas {summary.sections_created} secciones y {summary.relations_created} relaciones.", 8000)

    def apply_tables_with_progress(self, tables):
        """Aplica las tablas al modelo (hilo principal: muta el proyecto) mostrando el avance.

        La escritura va en una sola transacción y los oyentes pesados están coalescidos, así que la
        parte lenta que queda es crear los nodos del mapa; el diálogo se repinta cada pocas filas.
        """
        total = len(tables.sections) + len(tables.relations)
        dialog = progress_dialog(self.window, "Importar tablas", "Creando secciones y relaciones…",
                                 maximum=max(1, total), delay_ms=400)

        def on_progress(done: int, count: int) -> None:
            dialog.setValue(done)
            dialog.setLabelText(f"Creando secciones y relaciones… {done} de {count}")
            QApplication.processEvents()

        try:
            with busy_cursor():
                return apply_tables(self.project, tables, progress=on_progress)
        except ProjectFileError as exc:
            QMessageBox.critical(self.window, "Importar tablas", str(exc))
            return None
        finally:
            dialog.close()
            dialog.deleteLater()

    def export_tables(self) -> None:
        if not self.project.is_open:
            return
        start = self.settings.value(SETTINGS_LAST_DIR, "", type=str)
        suggested = (self.project.path.stem if self.project.path else "proyecto") + "_tablas.xlsx"
        path, _ = QFileDialog.getSaveFileName(self.window, "Exportar tablas a Excel",
                                              str(Path(start) / suggested), "Libro de Excel (*.xlsx)")
        if not path:
            return
        p = Path(path)
        if p.suffix.lower() != ".xlsx":
            p = p.with_suffix(".xlsx")
        self.settings.setValue(SETTINGS_LAST_DIR, str(p.parent))
        snapshot = self.project.snapshot()  # copia de solo lectura: el hilo no toca el modelo ni SQLite

        def failed(exc: BaseException, _tb: str) -> None:
            QMessageBox.critical(self.window, "Exportar tablas", str(exc))

        run_with_progress(self.window, "Exportar tablas", "Generando el libro de Excel…",
                          export_tables_xlsx, snapshot, p,
                          on_done=lambda _r: self.window.show_status(f"Tablas exportadas: {p}", 8000),
                          on_error=failed)

    # ------------------------------------------------------------------ varios
    def about(self) -> None:
        from views.components.about_dialog import AboutDialog

        AboutDialog(self.window).exec()

    def _restore_window_state(self) -> None:
        geometry = self.settings.value(SETTINGS_WINDOW_GEOMETRY)
        if geometry is not None:
            self.window.restoreGeometry(geometry)
        state = self.settings.value(SETTINGS_WINDOW_STATE)
        if state is not None:
            self.window.restoreState(state)
        splitter = self.settings.value(SETTINGS_SPLITTER_STATE)
        if splitter is not None:
            self.window.splitter.restoreState(splitter)

    def _save_window_state(self) -> None:
        self.settings.setValue(SETTINGS_WINDOW_GEOMETRY, self.window.saveGeometry())
        self.settings.setValue(SETTINGS_WINDOW_STATE, self.window.saveState())
        self.settings.setValue(SETTINGS_SPLITTER_STATE, self.window.splitter.saveState())
        self.project.close()
