"""Ventana del manual de uso: índice de temas, buscador y visor Markdown."""
from __future__ import annotations

from PyQt6.QtCore import QSettings, QUrl, Qt
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from config.settings import APP_NAME, APP_VERSION_LABEL
from models.help_content import HelpContent

SETTINGS_GEOMETRY = "help/geometry"


class HelpDialog(QDialog):
    def __init__(self, content: HelpContent, parent=None) -> None:
        super().__init__(parent)
        self.content = content
        self.setWindowTitle(f"Manual de uso — {APP_NAME}")
        self.setWindowFlag(Qt.WindowType.WindowMinMaxButtonsHint, True)
        self.setModal(False)
        self.resize(1040, 720)
        self._current: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter, 1)

        left = QWidget()
        ll = QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Buscar en el manual… (ej. conectar, mutua, avance)")
        self.search.setClearButtonEnabled(True)
        self.topics_list = QListWidget()
        self.topics_list.setMinimumWidth(240)
        ll.addWidget(self.search)
        ll.addWidget(self.topics_list, 1)
        splitter.addWidget(left)

        right = QWidget()
        rl = QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setSearchPaths([str(content.folder)])
        self.browser.document().setDefaultStyleSheet(
            "h1 { color: #1F4E79; font-size: 18pt; } h2 { color: #1F4E79; font-size: 13pt; margin-top: 14px; } "
            "p, li { font-size: 10.5pt; line-height: 130%; } code { background: #EEF2F7; padding: 1px 3px; } "
            "table { border-collapse: collapse; } th { background: #1F4E79; color: white; padding: 4px 8px; } "
            "td { border: 1px solid #D9DEE5; padding: 4px 8px; }"
        )
        self.browser.anchorClicked.connect(self._on_anchor)
        rl.addWidget(self.browser, 1)
        nav = QHBoxLayout()
        self.prev_button = QPushButton("◀ Anterior")
        self.prev_button.setProperty("role", "secondary")
        self.next_button = QPushButton("Siguiente ▶")
        self.next_button.setProperty("role", "secondary")
        self.folder_button = QPushButton("Abrir carpeta del manual")
        self.folder_button.setProperty("role", "secondary")
        self.version_label = QLabel(f"{APP_NAME} {APP_VERSION_LABEL}")
        self.version_label.setProperty("role", "hint")
        nav.addWidget(self.prev_button)
        nav.addWidget(self.next_button)
        nav.addStretch(1)
        nav.addWidget(self.version_label)
        nav.addWidget(self.folder_button)
        rl.addLayout(nav)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 780])

        self._populate(content.topics)
        self.search.textChanged.connect(self._on_search)
        self.topics_list.currentItemChanged.connect(self._on_item_changed)
        self.prev_button.clicked.connect(lambda: self._step(-1))
        self.next_button.clicked.connect(lambda: self._step(1))
        self.folder_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(content.folder))))
        geometry = QSettings().value(SETTINGS_GEOMETRY)
        if geometry is not None:
            self.restoreGeometry(geometry)
        if content.error:
            self.browser.setMarkdown(f"# Manual no disponible\n\n{content.error}")
        elif content.topics:
            self.show_topic(content.topics[0].id)

    # ------------------------------------------------------------------ navegación
    def _populate(self, topics) -> None:
        self.topics_list.blockSignals(True)
        self.topics_list.clear()
        for i, t in enumerate(topics):
            item = QListWidgetItem(f"{self.content.index_of(t.id) + 1}. {t.title}")
            item.setData(Qt.ItemDataRole.UserRole, t.id)
            self.topics_list.addItem(item)
        self.topics_list.blockSignals(False)

    def show_topic(self, topic_id: str) -> None:
        topic = self.content.topic(topic_id)
        if topic is None:
            return
        self._current = topic_id
        self.browser.setMarkdown(topic.markdown)
        self.browser.verticalScrollBar().setValue(0)
        for i in range(self.topics_list.count()):
            if self.topics_list.item(i).data(Qt.ItemDataRole.UserRole) == topic_id:
                self.topics_list.blockSignals(True)
                self.topics_list.setCurrentRow(i)
                self.topics_list.blockSignals(False)
                break
        idx = self.content.index_of(topic_id)
        self.prev_button.setEnabled(idx > 0)
        self.next_button.setEnabled(idx < len(self.content.topics) - 1)
        self.setWindowTitle(f"{topic.title} — Manual de {APP_NAME}")

    @property
    def current_topic(self) -> str | None:
        return self._current

    def _step(self, delta: int) -> None:
        if self._current is None:
            return
        idx = self.content.index_of(self._current) + delta
        if 0 <= idx < len(self.content.topics):
            self.show_topic(self.content.topics[idx].id)

    def _on_item_changed(self, current: QListWidgetItem | None, _previous) -> None:
        if current is not None:
            self.show_topic(current.data(Qt.ItemDataRole.UserRole))

    def _on_search(self, text: str) -> None:
        matches = self.content.search(text)
        self._populate(matches)
        if matches and (self._current is None or all(t.id != self._current for t in matches)):
            self.show_topic(matches[0].id)
        elif not matches:
            self.browser.setMarkdown(f"# Sin resultados\n\nNingún tema contiene «{text}».")

    def _on_anchor(self, url: QUrl) -> None:
        # Enlaces internos «tema:id» navegan dentro del manual; el resto los abre el sistema.
        if url.scheme() == "tema":
            self.show_topic(url.path().lstrip("/") or url.host())

    def closeEvent(self, event) -> None:  # noqa: N802
        QSettings().setValue(SETTINGS_GEOMETRY, self.saveGeometry())
        super().closeEvent(event)
