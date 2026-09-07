"""Panel acoplable «Secciones MasterFormat»: buscador, árbol por división, doble clic y arrastre."""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QModelIndex, QPoint, QRect, QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDockWidget,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

from config import palette
from models.masterformat_tree_model import (
    ROLE_CATEGORY,
    ROLE_CODE,
    ROLE_CODE_KEY,
    ROLE_HAS_OVERRIDE,
    ROLE_HIDDEN,
    ROLE_IN_PROJECT,
    ROLE_LEVEL,
    ROLE_QUALITY,
    ROLE_TITLE,
    ROLE_TITLE_EDITED,
    ROLE_USER_ADDED,
    CatalogTreeFilterProxy,
    MasterFormatTreeModel,
)

# nombre de categoría -> (relleno, borde)
CategoryColors = dict[str, tuple[str, str]]


def seed_colors() -> CategoryColors:
    return {s.name.casefold(): (s.fill, s.border) for s in palette.DEFAULT_CATEGORIES}


class _CatalogItemDelegate(QStyledItemDelegate):
    _code_font = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
    _title_font = QFont("Segoe UI", 9)

    def __init__(self, colors_provider: Callable[[], CategoryColors], parent=None) -> None:
        super().__init__(parent)
        self._colors = colors_provider

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(option.rect, QColor(palette.PRIMARY_TINT))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(option.rect, QColor("#F2F5F9"))
        r = option.rect.adjusted(4, 0, -4, 0)
        code, title = str(index.data(ROLE_CODE) or ""), str(index.data(ROLE_TITLE) or "")
        level = int(index.data(ROLE_LEVEL) or 3)
        in_project = bool(index.data(ROLE_IN_PROJECT))
        review = index.data(ROLE_QUALITY) == "review"
        category = str(index.data(ROLE_CATEGORY) or "")
        hidden = bool(index.data(ROLE_HIDDEN))
        if hidden:
            painter.setOpacity(0.45)
        x = r.left()
        # Muestra de la clasificación por defecto (color de la categoría).
        fill, border = self._colors().get(category.casefold(), (palette.SURFACE_ALT, palette.BORDER_STRONG))
        chip = QRect(x, r.center().y() - 6, 12, 12)
        painter.setPen(QPen(QColor(border), 1))
        painter.setBrush(QColor(fill))
        painter.drawRoundedRect(chip, 2, 2)
        if index.data(ROLE_HAS_OVERRIDE):
            painter.setPen(QPen(QColor(palette.PRIMARY), 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(chip.adjusted(-2, -2, 2, 2), 3, 3)
        x += 18
        # Punto verde: ya existe en el proyecto.
        if in_project:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(palette.SUCCESS))
            painter.drawEllipse(QRect(x, r.center().y() - 3, 6, 6))
        x += 10
        fm_code = QFontMetrics(self._code_font)
        painter.setFont(self._code_font)
        painter.setPen(QColor(palette.PRIMARY if level <= 2 else palette.TEXT))
        painter.drawText(QPoint(x, r.center().y() + fm_code.ascent() // 2 - 1), code)
        x += fm_code.horizontalAdvance(code) + 8
        painter.setFont(self._title_font)
        fm_title = QFontMetrics(self._title_font)
        color = palette.TEXT_SECONDARY if review else (palette.TEXT if level >= 3 else palette.PRIMARY)
        painter.setPen(QColor(color))
        marks = ("  ⚠" if review else "") + ("  ✎" if index.data(ROLE_TITLE_EDITED) else "") + \
                ("  ＋" if index.data(ROLE_USER_ADDED) else "") + ("  (oculta)" if hidden else "")
        painter.drawText(QPoint(x, r.center().y() + fm_title.ascent() // 2 - 1),
                         fm_title.elidedText(title + marks, Qt.TextElideMode.ElideRight, max(20, r.right() - x)))
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # noqa: N802
        return QSize(260, 26)


class MasterFormatPanel(QDockWidget):
    addRequested = pyqtSignal(str)                 # code_key
    useAsRequested = pyqtSignal(str, str)          # 'a'|'b', code_key
    centerRequested = pyqtSignal(str)              # code_key (sección ya en el proyecto)
    categoryOverrideRequested = pyqtSignal(str, str, bool)  # code_key, categoría, toda la rama
    clearOverrideRequested = pyqtSignal(str)       # code_key
    editTitleRequested = pyqtSignal(str)           # code_key
    addChildRequested = pyqtSignal(str)            # code_key del padre ('' = raíz)
    hideRequested = pyqtSignal(str)                # code_key
    restoreRequested = pyqtSignal(str)             # code_key (quitar edición / mostrar de nuevo)

    def __init__(self, tree_model: MasterFormatTreeModel, parent=None) -> None:
        super().__init__("Secciones MasterFormat", parent)
        self.setObjectName("masterFormatDock")
        self.setAllowedAreas(Qt.DockWidgetArea.LeftDockWidgetArea | Qt.DockWidgetArea.RightDockWidgetArea)
        self.tree_model = tree_model
        self.proxy = CatalogTreeFilterProxy(self)
        self.proxy.setSourceModel(tree_model)
        self._category_colors: CategoryColors = seed_colors()
        self._category_names: list[str] = [s.name for s in palette.DEFAULT_CATEGORIES]

        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(6)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Filtrar por número o título (ej. 03 30 o concrete)")
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)
        row = QHBoxLayout()
        self.only_project = QCheckBox("Solo del proyecto")
        self.show_hidden = QCheckBox("Mostrar ocultas")
        self.show_hidden.setToolTip("Mostrar las secciones que usted ocultó del catálogo, para restaurarlas")
        self.count_label = QLabel("")
        self.count_label.setProperty("role", "hint")
        row.addWidget(self.only_project)
        row.addWidget(self.show_hidden)
        row.addStretch(1)
        row.addWidget(self.count_label)
        layout.addLayout(row)

        self.tree = QTreeView()
        self.tree.setModel(self.proxy)
        self.tree.setHeaderHidden(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setItemDelegate(_CatalogItemDelegate(lambda: self._category_colors, self.tree))
        self.tree.setDragEnabled(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.tree.setMouseTracking(True)
        self.tree.setExpandsOnDoubleClick(False)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.setIndentation(14)
        layout.addWidget(self.tree, 1)
        self.legend = QLabel("")
        self.legend.setProperty("role", "hint")
        self.legend.setWordWrap(True)
        layout.addWidget(self.legend)
        hint = QLabel("Doble clic agrega la sección al proyecto. Arrástrela al mapa para ubicarla. "
                      "Clic derecho para cambiar la clasificación por defecto.")
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.setWidget(body)
        self.setMinimumWidth(300)

        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(150)
        self._search_timer.timeout.connect(self._apply_filter)
        self.search.textChanged.connect(lambda _t: self._search_timer.start())
        self.only_project.toggled.connect(lambda _on: self._apply_filter())
        self.show_hidden.toggled.connect(lambda _on: self._apply_filter())
        self.tree.doubleClicked.connect(self._on_double_clicked)
        self.tree.customContextMenuRequested.connect(self._context_menu)
        self.tree_model.modelReset.connect(self._update_count)
        self._update_count()
        self._update_legend()

    # ------------------------------------------------------------------ categorías (colores/nombres)
    def set_categories(self, categories: list[tuple[str, str, str]]) -> None:
        """[(nombre, relleno, borde)] del proyecto; si está vacío se usan las semilla."""
        colors = seed_colors()
        names = [s.name for s in palette.DEFAULT_CATEGORIES]
        if categories:
            names = [n for n, _f, _b in categories]
            for name, fill, border in categories:
                colors[name.casefold()] = (fill, border)
        self._category_colors, self._category_names = colors, names
        self._update_legend()
        self.tree.viewport().update()

    def _update_legend(self) -> None:
        parts = []
        for name in self._category_names[:6]:
            fill, _border = self._category_colors.get(name.casefold(), (palette.SURFACE_ALT, ""))
            parts.append(f'<span style="background:{fill};">&nbsp;&nbsp;&nbsp;</span> {name}')
        self.legend.setText("Clasificación por defecto: " + " &nbsp; ".join(parts))

    # ------------------------------------------------------------------ filtro
    def _apply_filter(self) -> None:
        self.proxy.set_query(self.search.text())
        self.proxy.set_only_project(self.only_project.isChecked())
        self.proxy.set_show_hidden(self.show_hidden.isChecked())
        if self.proxy.is_filtering:
            self.tree.expandAll()
        else:
            self.tree.collapseAll()
        self._update_count()

    def _update_count(self) -> None:
        total = len(self.tree_model.catalog)
        self.count_label.setText(f"{total:,} secciones".replace(",", "."))

    def selected_keys(self) -> list[str]:
        return [idx.data(ROLE_CODE_KEY) for idx in self.tree.selectionModel().selectedIndexes() if idx.isValid()]

    def reveal(self, code_key: str) -> None:
        src = self.tree_model.index_for_key(code_key)
        idx = self.proxy.mapFromSource(src)
        if idx.isValid():
            self.tree.scrollTo(idx)
            self.tree.setCurrentIndex(idx)

    # ------------------------------------------------------------------ interacción
    def _on_double_clicked(self, index: QModelIndex) -> None:
        key = index.data(ROLE_CODE_KEY)
        if key:
            self.addRequested.emit(key)

    def _context_menu(self, pos) -> None:
        index = self.tree.indexAt(pos)
        if not index.isValid():
            return
        key = index.data(ROLE_CODE_KEY)
        in_project = bool(index.data(ROLE_IN_PROJECT))
        current = str(index.data(ROLE_CATEGORY) or "")
        level = int(index.data(ROLE_LEVEL) or 3)
        menu = QMenu(self)
        menu.addSection(index.data(Qt.ItemDataRole.DisplayRole))
        act_add = menu.addAction("Agregar al proyecto", lambda: self.addRequested.emit(key))
        act_add.setEnabled(not in_project)
        menu.addAction("Usar como Sección A", lambda: self.useAsRequested.emit("a", key))
        menu.addAction("Usar como Sección B", lambda: self.useAsRequested.emit("b", key))
        if in_project:
            menu.addAction("Centrar en el mapa", lambda: self.centerRequested.emit(key))
        menu.addSeparator()
        cat_menu = menu.addMenu(f"Clasificación por defecto (actual: {current or 'sin clasificar'})")
        branch_label = "toda la rama" if level < 4 else "esta sección"
        for name in self._category_names:
            sub = cat_menu.addMenu(name)
            sub.addAction("Solo esta sección",
                          lambda _c=False, n=name: self.categoryOverrideRequested.emit(key, n, False))
            if level < 4:
                sub.addAction(f"Esta sección y {branch_label}",
                              lambda _c=False, n=name: self.categoryOverrideRequested.emit(key, n, True))
        if index.data(ROLE_HAS_OVERRIDE):
            cat_menu.addSeparator()
            cat_menu.addAction("Quitar corrección (volver al catálogo)",
                               lambda: self.clearOverrideRequested.emit(key))
        menu.addSeparator()
        edit_menu = menu.addMenu("Editar catálogo")
        edit_menu.addAction("Editar título…", lambda: self.editTitleRequested.emit(key))
        if level < 4:
            edit_menu.addAction("Agregar sección hija…", lambda: self.addChildRequested.emit(key))
        if index.data(ROLE_HIDDEN):
            edit_menu.addAction("Mostrar de nuevo en el catálogo", lambda: self.restoreRequested.emit(key))
        else:
            label = "Eliminar del catálogo" if index.data(ROLE_USER_ADDED) else "Ocultar del catálogo"
            edit_menu.addAction(label, lambda: self.hideRequested.emit(key))
        if index.data(ROLE_TITLE_EDITED) or index.data(ROLE_HIDDEN):
            edit_menu.addSeparator()
            edit_menu.addAction("Restaurar entrada original", lambda: self.restoreRequested.emit(key))
        menu.exec(self.tree.viewport().mapToGlobal(pos))
