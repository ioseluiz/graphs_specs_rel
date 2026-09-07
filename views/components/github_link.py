"""Enlace al perfil de GitHub del autor, con el logo oficial (Octocat mark), para la barra de estado."""
from __future__ import annotations

from PyQt6.QtCore import QByteArray, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QMouseEvent, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QWidget

from config import palette

# Mark oficial de GitHub (uso permitido según GitHub Logos and Usage).
_GITHUB_SVG = b"""<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'>
<path fill='{color}' fill-rule='evenodd' d='M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z'/>
</svg>"""


def render_github_pixmap(size: int = 18, color: str = palette.TEXT) -> QPixmap:
    svg = _GITHUB_SVG.replace(b"{color}", color.encode("ascii"))
    renderer = QSvgRenderer(QByteArray(svg))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    return pixmap


class GithubLinkWidget(QWidget):
    """Logo de GitHub + usuario. Un clic abre el perfil en el navegador."""

    def __init__(self, username: str, parent=None) -> None:
        super().__init__(parent)
        self.username = username
        self.url = QUrl(f"https://github.com/{username}")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"Abrir {self.url.toString()}")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(6)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(render_github_pixmap(16, palette.TEXT))
        self.text_label = QLabel(username)
        self.text_label.setStyleSheet(f"color: {palette.TEXT_SECONDARY};")
        layout.addWidget(self.icon_label)
        layout.addWidget(self.text_label)

    def enterEvent(self, event) -> None:  # noqa: N802
        self.icon_label.setPixmap(render_github_pixmap(16, palette.PRIMARY))
        self.text_label.setStyleSheet(f"color: {palette.PRIMARY}; text-decoration: underline;")
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802
        self.icon_label.setPixmap(render_github_pixmap(16, palette.TEXT))
        self.text_label.setStyleSheet(f"color: {palette.TEXT_SECONDARY};")
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            QDesktopServices.openUrl(self.url)
        super().mouseReleaseEvent(event)
