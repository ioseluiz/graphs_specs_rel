"""Ventana principal: toolbar, encabezado, tabla (izquierda) y pestañas Mapa 2D / 3D / Análisis."""
from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QStatusBar,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from config.settings import APP_DISPLAY_NAME, APP_NAME, GITHUB_USER, ICONS_DIR
from models.masterformat_tree_model import MasterFormatTreeModel
from models.project_bootstrap import is_droppable
from models.relations_table_model import RelationsTableModel
from models.section_completer_model import SectionCompleterModel
from views.components.analysis_panel import AnalysisPanel
from views.components.masterformat_panel import MasterFormatPanel
from views.components.canvas.graph_scene import GraphScene
from views.components.canvas.graph_view import GraphView
from views.components.github_link import GithubLinkWidget
from views.components.graph3d_widget import Graph3DWidget
from views.components.project_header import ProjectHeader
from views.components.relation_entry_widget import RelationEntryWidget
from views.components.relations_table_view import RelationsTableView
from views.components.sections_table_view import SectionsTableView

TAB_MAP, TAB_3D, TAB_SECTIONS, TAB_ANALYSIS = range(4)


def icon(name: str) -> QIcon:
    path = ICONS_DIR / f"{name}.svg"
    return QIcon(str(path)) if path.exists() else QIcon()


class MainWindow(QMainWindow):
    recentFileActivated = pyqtSignal(str)
    aboutToClose = pyqtSignal()
    filesDropped = pyqtSignal(list)   # rutas locales (.specrel, .xlsx, .csv) soltadas sobre la ventana

    def __init__(self, table_model: RelationsTableModel, completer_model: SectionCompleterModel,
                 tree_model: MasterFormatTreeModel | None = None) -> None:
        super().__init__()
        self.setWindowTitle(APP_DISPLAY_NAME)
        self.resize(1600, 900)
        self.setMinimumSize(1024, 640)
        self.setAcceptDrops(True)
        self._build_actions()
        self._build_central(table_model, completer_model)
        self._build_catalog_dock(tree_model)
        self._build_menus()
        self._build_toolbar()
        self.setStatusBar(QStatusBar())
        self.saved_label = QLabel("")
        self.saved_label.setProperty("role", "hint")
        self.saved_label.setToolTip("Los cambios se guardan automáticamente en el archivo del proyecto")
        self.statusBar().addPermanentWidget(self.saved_label)
        self.github_link = GithubLinkWidget(GITHUB_USER)
        self.statusBar().addPermanentWidget(self.github_link)
        self.zoom_label = QLabel("100 %")
        self.zoom_label.setMinimumWidth(48)
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.statusBar().addPermanentWidget(self.zoom_label)
        self.set_project_open(False)

    # ------------------------------------------------------------------ acciones
    def _build_actions(self) -> None:
        def make(text: str, icon_name: str, shortcut: str | None = None, checkable: bool = False,
                 tip: str | None = None) -> QAction:
            act = QAction(icon(icon_name), text, self)
            if shortcut:
                act.setShortcut(QKeySequence(shortcut))
            act.setCheckable(checkable)
            if tip:
                act.setToolTip(tip)
                act.setStatusTip(tip)
            return act

        self.act_new = make("Nuevo proyecto…", "new", "Ctrl+N", tip="Crear un archivo de proyecto nuevo")
        self.act_open = make("Abrir proyecto…", "open", "Ctrl+O")
        self.act_save = make("Guardar", "save", "Ctrl+S",
                             tip="Los cambios se guardan automáticamente en el archivo del proyecto; "
                                 "Guardar solo confirma que todo está escrito")
        self.act_save_copy = make("Guardar copia como…", "save", "Ctrl+Shift+S",
                                  tip="Crea un duplicado del proyecto en otro archivo")
        self.act_close = make("Cerrar proyecto", "close", "Ctrl+W")
        self.act_exit = make("Salir", "exit", "Ctrl+Q")

        self.act_connect = make("Conectar", "connect", "C", checkable=True,
                                tip="Crear relaciones en el mapa: active el modo, arrastre desde una sección "
                                    "hasta otra y elija el tipo. Esc cancela. También: Alt + arrastre.")
        self.act_add_section = make("Nueva sección…", "section", "Ctrl+Shift+N")
        self.act_delete = make("Eliminar selección", "delete", "Delete")
        self.act_fit = make("Ajustar a la vista", "fit", "Ctrl+0")
        self.act_zoom_in = make("Acercar", "zoom-in", "Ctrl++")
        self.act_zoom_out = make("Alejar", "zoom-out", "Ctrl+-")
        self.act_zoom_reset = make("Zoom 100 %", "zoom-reset", "Ctrl+1")
        self.act_snap = make("Ajustar a rejilla", "snap", checkable=True,
                             tip="Al soltar un nodo, lo alinea a la cuadrícula de 10 px para que los nodos queden "
                                 "en fila y las flechas salgan rectas. No mueve los nodos ya colocados.")
        self.act_grid = make("Mostrar rejilla", "grid", checkable=True,
                             tip="Muestra u oculta las líneas de la cuadrícula del fondo (no afecta el ajuste)")
        self.act_grid.setChecked(True)
        self.act_show_extras = make("Mostrar avance y responsables", "analysis", "F6", checkable=True,
                                    tip="Círculos de responsables y barra de avance en cada sección del mapa")
        self.act_show_extras.setChecked(True)
        self.act_responsibles = make("Responsables…", "categories",
                                     tip="Unidades responsables (INIO, INIG, …): agregar, editar, borrar, reordenar")
        self.act_statuses = make("Estatus…", "categories", tip="Estados de elaboración de las secciones")
        self.act_arrange_new = make("Organizar secciones no acomodadas", "arrange",
                                    tip="Distribuye solo las secciones que el usuario no ha movido manualmente")

        self.act_categories = make("Categorías…", "categories")
        self.act_import_tables = make("Importar tablas o crear mapa desde Excel/CSV…", "import", "Ctrl+I",
                                      tip="Carga secciones y relaciones desde la plantilla de Excel o CSV. "
                                          "Sin proyecto abierto crea el mapa directamente (el archivo .specrel "
                                          "se guarda junto al Excel). También puede arrastrar el archivo aquí.")
        self.act_export_tables = make("Exportar tablas a Excel…", "export-svg",
                                      tip="Guarda secciones y relaciones en el formato de la plantilla")
        self.act_save_template = make("Guardar plantilla de Excel…", "new",
                                      tip="Plantilla vacía con ejemplos para armar un proyecto en Excel")
        self.act_import_catalog = make("Catálogo adicional del proyecto…", "import",
                                       tip="Secciones extra o traducciones solo para este proyecto")
        self.act_clear_catalog = make("Vaciar catálogo adicional del proyecto", "clear")
        self.act_replace_catalog = make("Reemplazar catálogo MasterFormat…", "import",
                                        tip="Cargar otro listado MasterFormat (Excel/CSV) para todos los proyectos")
        self.act_reset_catalog = make("Restaurar catálogo incluido", "clear")
        self.act_apply_catalog_categories = make(
            "Aplicar clasificación del catálogo a las secciones del proyecto…", "categories",
            tip="Reasigna la categoría de las secciones del proyecto según la clasificación del catálogo")
        self.act_clear_category_overrides = make("Quitar todas las correcciones de clasificación", "clear")
        self.act_export_catalog = make("Exportar catálogo a Excel…", "export-svg",
                                       tip="Excel editable con el formato que acepta «Reemplazar catálogo…»")
        self.act_add_catalog_entry = make("Agregar sección al catálogo…", "section")
        self.act_clear_catalog_edits = make("Quitar todas las ediciones del catálogo", "clear")
        self.act_export_png = make("Mapa 2D como PNG…", "export", "Ctrl+E")
        self.act_export_svg = make("Mapa 2D como SVG…", "export-svg")
        self.act_copy_image = make("Copiar mapa 2D al portapapeles", "copy", "Ctrl+Shift+C")
        self.act_export_3d_png = make("Vista 3D como PNG…", "export", "Ctrl+Shift+E")
        self.act_export_3d_svg = make("Vista 3D como SVG…", "export-svg",
                                      tip="Proyección vectorial de la vista 3D con la cámara actual")
        self.act_copy_3d_image = make("Copiar vista 3D al portapapeles", "copy")
        self.act_export_current = make("Exportar…", "export",
                                       tip="Exporta la vista activa (mapa 2D o vista 3D) como PNG")
        self.act_export_report = make("Reporte de secciones (Excel)…", "export-svg", "Ctrl+R",
                                      tip="Libro de Excel con resumen, secciones (estatus, avance, responsables, "
                                          "observaciones), desglose por responsable y relaciones")
        self.act_manual = make("Manual de uso", "about", "F1", tip="Manual de uso (abre el tema de la pestaña activa)")
        self.act_shortcuts = make("Atajos de teclado", "about")
        self.act_about = make("Acerca de…", "about")

    def _build_menus(self) -> None:
        bar = self.menuBar()
        m_file = bar.addMenu("&Archivo")
        m_file.addActions([self.act_new, self.act_open])
        self.menu_recent = QMenu("Recientes", self)
        m_file.addMenu(self.menu_recent)
        m_file.addSeparator()
        m_file.addActions([self.act_save, self.act_save_copy, self.act_close])
        m_file.addSeparator()
        m_tables = m_file.addMenu("Tablas (Excel / CSV)")
        m_tables.addActions([self.act_import_tables, self.act_export_tables, self.act_save_template])
        self.menu_export = QMenu("Exportar", self)
        self.menu_export.setIcon(icon("export"))
        self.menu_export.addSection("Mapa 2D")
        self.menu_export.addActions([self.act_export_png, self.act_export_svg, self.act_copy_image])
        self.menu_export.addSection("Vista 3D")
        self.menu_export.addActions([self.act_export_3d_png, self.act_export_3d_svg, self.act_copy_3d_image])
        self.menu_export.addSection("Reportes")
        self.menu_export.addAction(self.act_export_report)
        m_file.addMenu(self.menu_export)
        m_file.addSeparator()
        m_file.addAction(self.act_exit)

        m_edit = bar.addMenu("&Edición")
        m_edit.addActions([self.act_add_section, self.act_connect, self.act_delete])
        m_edit.addSeparator()
        m_edit.addActions([self.act_categories, self.act_responsibles, self.act_statuses])
        m_catalog = m_edit.addMenu("Catálogo MasterFormat")
        m_catalog.addActions([self.act_apply_catalog_categories, self.act_clear_category_overrides])
        m_catalog.addSeparator()
        m_catalog.addActions([self.act_add_catalog_entry, self.act_clear_catalog_edits])
        m_catalog.addSeparator()
        m_catalog.addActions([self.act_export_catalog, self.act_replace_catalog, self.act_reset_catalog])
        m_catalog.addSeparator()
        m_catalog.addActions([self.act_import_catalog, self.act_clear_catalog])

        m_view = bar.addMenu("&Ver")
        m_view.addAction(self.act_toggle_catalog)
        m_view.addSeparator()
        m_view.addActions([self.act_fit, self.act_zoom_in, self.act_zoom_out, self.act_zoom_reset])
        m_view.addSeparator()
        m_view.addActions([self.act_snap, self.act_grid, self.act_show_extras, self.act_arrange_new])

        m_help = bar.addMenu("A&yuda")
        m_help.addActions([self.act_manual, self.act_shortcuts])
        m_help.addSeparator()
        m_help.addAction(self.act_about)

    def _build_toolbar(self) -> None:
        tb = QToolBar("Principal")
        tb.setObjectName("mainToolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.addActions([self.act_new, self.act_open, self.act_save])
        tb.addSeparator()
        tb.addActions([self.act_add_section, self.act_connect, self.act_delete])
        tb.addSeparator()
        tb.addActions([self.act_fit, self.act_snap])
        tb.addSeparator()
        tb.addActions([self.act_toggle_catalog, self.act_categories, self.act_responsibles, self.act_import_tables])
        self.export_button = QToolButton()
        self.export_button.setDefaultAction(self.act_export_current)
        self.export_button.setMenu(self.menu_export)
        self.export_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.export_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        tb.addWidget(self.export_button)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        tb.addAction(self.act_manual)
        self.addToolBar(tb)
        self.toolbar = tb

    # ------------------------------------------------------------------ central
    def _build_central(self, table_model: RelationsTableModel, completer_model: SectionCompleterModel) -> None:
        self.stack = QStackedWidget()
        self.stack.setObjectName("centralWidget")
        self.setCentralWidget(self.stack)

        # Página de inicio
        welcome = QWidget()
        welcome.setObjectName("welcomePage")
        welcome.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.welcome_page = welcome
        wl = QVBoxLayout(welcome)
        wl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(APP_NAME)
        title.setProperty("role", "title")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle = QLabel("Mapa de referencias cruzadas entre secciones de especificaciones.\n"
                          "Cada proyecto se guarda en un único archivo .specrel, sin base de datos central.")
        subtitle.setProperty("role", "subtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buttons = QHBoxLayout()
        self.welcome_import = QPushButton("Crear mapa desde Excel/CSV…")
        self.welcome_import.setToolTip("Elija un archivo de la plantilla: el mapa se crea directamente y el "
                                       "proyecto se guarda junto al Excel")
        self.welcome_new = QPushButton("Nuevo proyecto vacío…")
        self.welcome_new.setProperty("role", "secondary")
        self.welcome_open = QPushButton("Abrir proyecto…")
        self.welcome_open.setProperty("role", "secondary")
        self.welcome_template = QPushButton("Descargar plantilla de Excel…")
        self.welcome_template.setProperty("role", "secondary")
        self.welcome_template.setToolTip("Plantilla para preparar secciones y relaciones en Excel y luego "
                                         "importarlas en un proyecto nuevo")
        self.welcome_help = QPushButton("Ver manual de uso")
        self.welcome_help.setProperty("role", "secondary")
        buttons.addStretch(1)
        buttons.addWidget(self.welcome_import)
        buttons.addWidget(self.welcome_new)
        buttons.addWidget(self.welcome_open)
        buttons.addWidget(self.welcome_template)
        buttons.addWidget(self.welcome_help)
        buttons.addStretch(1)
        self.drop_hint = QLabel("También puede arrastrar aquí un archivo .xlsx / .csv de la plantilla "
                                "o un proyecto .specrel")
        self.drop_hint.setProperty("role", "hint")
        self.drop_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        recent_label = QLabel("Proyectos recientes")
        recent_label.setProperty("role", "subtitle")
        recent_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.recent_list = QListWidget()
        self.recent_list.setMaximumWidth(620)
        self.recent_list.setMaximumHeight(200)
        wl.addWidget(title)
        wl.addWidget(subtitle)
        wl.addSpacing(16)
        wl.addLayout(buttons)
        wl.addSpacing(8)
        wl.addWidget(self.drop_hint)
        wl.addSpacing(24)
        wl.addWidget(recent_label)
        wl.addWidget(self.recent_list, 0, Qt.AlignmentFlag.AlignHCenter)
        self.stack.addWidget(welcome)
        self.welcome_import.clicked.connect(self.act_import_tables.trigger)
        self.welcome_new.clicked.connect(self.act_new.trigger)
        self.welcome_open.clicked.connect(self.act_open.trigger)
        self.welcome_template.clicked.connect(self.act_save_template.trigger)
        self.recent_list.itemActivated.connect(
            lambda item: self.recentFileActivated.emit(item.data(Qt.ItemDataRole.UserRole)))

        # Espacio de trabajo
        workspace = QWidget()
        workspace.setObjectName("workspacePage")
        workspace.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.workspace_page = workspace
        layout = QVBoxLayout(workspace)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)
        self.header = ProjectHeader()
        layout.addWidget(self.header)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)
        self.entry = RelationEntryWidget(completer_model)
        self.table_view = RelationsTableView(table_model, completer_model)
        left_layout.addWidget(self.entry)
        left_layout.addWidget(self.table_view, 1)
        self.splitter.addWidget(left)

        self.tabs = QTabWidget()
        self.scene = GraphScene(self)
        self.view = GraphView(self.scene)
        self.tabs.addTab(self.view, icon("map"), "Mapa de referencias")
        self.view3d = Graph3DWidget()
        self.tabs.addTab(self.view3d, icon("3d"), "Vista 3D")
        self.sections_view = SectionsTableView()
        self.tabs.addTab(self.sections_view, icon("section"), "Secciones")
        self.analysis = AnalysisPanel()
        self.tabs.addTab(self.analysis, icon("analysis"), "Análisis")
        self.splitter.addWidget(self.tabs)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setSizes([560, 900])
        layout.addWidget(self.splitter, 1)
        self.stack.addWidget(workspace)

    # ------------------------------------------------------------------ panel del catálogo
    def _build_catalog_dock(self, tree_model: MasterFormatTreeModel | None) -> None:
        if tree_model is None:
            from models.master_catalog import MasterCatalog

            tree_model = MasterFormatTreeModel(MasterCatalog(), self)
        self.catalog_tree_model = tree_model
        self.catalog_panel = MasterFormatPanel(tree_model, self)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.catalog_panel)
        self.resizeDocks([self.catalog_panel], [340], Qt.Orientation.Horizontal)
        self.act_toggle_catalog = self.catalog_panel.toggleViewAction()
        self.act_toggle_catalog.setText("Panel MasterFormat")
        self.act_toggle_catalog.setIcon(icon("categories"))
        self.act_toggle_catalog.setShortcut(QKeySequence("F4"))
        self.act_toggle_catalog.setToolTip("Mostrar u ocultar el panel de secciones MasterFormat (F4)")
        self._catalog_wanted = True  # preferencia del usuario (el dock se oculta solo sin proyecto)
        self._project_open = False
        self.act_toggle_catalog.toggled.connect(self._on_catalog_toggled)

    def _on_catalog_toggled(self, checked: bool) -> None:
        if self._project_open:
            self._catalog_wanted = checked

    # ------------------------------------------------------------------ estado
    def set_project_open(self, is_open: bool) -> None:
        self.stack.setCurrentIndex(1 if is_open else 0)
        self._project_open = is_open
        self.catalog_panel.setVisible(is_open and self._catalog_wanted)
        self.act_toggle_catalog.setEnabled(is_open)
        self.saved_label.setVisible(is_open)
        for act in (self.act_save, self.act_save_copy, self.act_close, self.act_connect, self.act_add_section,
                    self.act_delete,
                    self.act_fit, self.act_zoom_in, self.act_zoom_out, self.act_zoom_reset, self.act_snap,
                    self.act_grid, self.act_arrange_new, self.act_categories, self.act_import_catalog,
                    self.act_clear_catalog, self.act_export_tables,
                    self.act_replace_catalog, self.act_reset_catalog, self.act_apply_catalog_categories,
                    self.act_export_catalog, self.act_add_catalog_entry,
                    self.act_show_extras, self.act_responsibles, self.act_statuses,
                    self.act_export_png, self.act_export_svg, self.act_copy_image,
                    self.act_export_3d_png, self.act_export_3d_svg, self.act_copy_3d_image,
                    self.act_export_current, self.act_export_report):
            act.setEnabled(is_open)

    def set_recent_files(self, paths: list[str]) -> None:
        self.menu_recent.clear()
        self.recent_list.clear()
        for path in paths:
            act = self.menu_recent.addAction(path)
            act.triggered.connect(lambda _c=False, p=path: self.recentFileActivated.emit(p))
            from PyQt6.QtWidgets import QListWidgetItem

            item = QListWidgetItem(path)
            item.setData(Qt.ItemDataRole.UserRole, path)
            self.recent_list.addItem(item)
        self.menu_recent.setEnabled(bool(paths))
        if not paths:
            self.menu_recent.addAction("(sin proyectos recientes)").setEnabled(False)

    def show_status(self, message: str, timeout_ms: int = 5000) -> None:
        self.statusBar().showMessage(message, timeout_ms)

    def set_saved_indicator(self, text: str) -> None:
        self.saved_label.setText(text)

    def set_zoom_label(self, scale: float) -> None:
        self.zoom_label.setText(f"{scale * 100:.0f} %")

    # ------------------------------------------------------------------ arrastrar archivos
    @staticmethod
    def dropped_paths(event) -> list[str]:
        mime = event.mimeData()
        if not mime.hasUrls():
            return []
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and is_droppable(u.toLocalFile())]

    def set_drop_active(self, on: bool) -> None:
        """Resalta la página visible mientras se arrastra un archivo aceptable sobre la ventana."""
        for page in (self.welcome_page, self.workspace_page):
            if bool(page.property("dropActive")) != on:
                page.setProperty("dropActive", on)
                page.style().unpolish(page)
                page.style().polish(page)
                page.update()

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self.dropped_paths(event):
            event.acceptProposedAction()
            self.set_drop_active(True)
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:  # noqa: N802
        if self.dropped_paths(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.set_drop_active(False)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.set_drop_active(False)
        paths = self.dropped_paths(event)
        if not paths:
            event.ignore()
            return
        event.acceptProposedAction()
        self.filesDropped.emit(paths)

    def closeEvent(self, event) -> None:  # noqa: N802
        self.aboutToClose.emit()
        super().closeEvent(event)
