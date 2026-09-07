"""Cuadro «Acerca de»: icono, versión, descripción y desarrollador con enlace a GitHub."""
from __future__ import annotations

import platform
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog, QDialogButtonBox, QFrame, QHBoxLayout, QLabel, QVBoxLayout

from config import palette
from config.settings import (
    APP_DISPLAY_NAME,
    APP_NAME,
    APP_VERSION_LABEL,
    ASSETS_DIR,
    DEVELOPER_NAME,
    GITHUB_USER,
    ORGANIZATION_NAME,
    RELEASE_YEAR,
)
from views.components.github_link import GithubLinkWidget


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Acerca de {APP_NAME}")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(16)
        icon_label = QLabel()
        icon_path = ASSETS_DIR / "icon.ico"
        if icon_path.exists():
            icon_label.setPixmap(QPixmap(str(icon_path)).scaled(
                72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        header.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignTop)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        name = QLabel(APP_NAME)
        name.setStyleSheet(f"font-size: 20pt; font-weight: 700; color: {palette.PRIMARY};")
        subtitle = QLabel(APP_DISPLAY_NAME.split("—", 1)[-1].strip())
        subtitle.setProperty("role", "subtitle")
        self.version_label = QLabel(f"Versión {APP_VERSION_LABEL}")
        self.version_label.setStyleSheet("font-size: 12pt; font-weight: 600;")
        titles.addWidget(name)
        titles.addWidget(subtitle)
        titles.addWidget(self.version_label)
        header.addLayout(titles, 1)
        layout.addLayout(header)

        description = QLabel(
            "Editor de relaciones entre secciones de especificaciones (MasterFormat) con mapa 2D editable, "
            "vista 3D, análisis de dependencias, estatus, avance y responsables por sección. "
            "Cada proyecto se guarda en un único archivo <code>.specrel</code>."
        )
        description.setWordWrap(True)
        description.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(description)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet(f"color: {palette.BORDER};")
        layout.addWidget(line)

        dev_title = QLabel("Desarrollado por")
        dev_title.setProperty("role", "hint")
        layout.addWidget(dev_title)
        dev_row = QHBoxLayout()
        dev_row.setSpacing(10)
        dev_name = QLabel(DEVELOPER_NAME)
        dev_name.setStyleSheet("font-size: 11pt; font-weight: 600;")
        self.github_link = GithubLinkWidget(GITHUB_USER)
        dev_row.addWidget(dev_name)
        dev_row.addWidget(self.github_link)
        dev_row.addStretch(1)
        layout.addLayout(dev_row)
        org = QLabel(f"{ORGANIZATION_NAME} · {RELEASE_YEAR}")
        org.setProperty("role", "hint")
        layout.addWidget(org)

        tech = QLabel(
            f"Python {platform.python_version()} · PyQt6 · SQLite · networkx · pyqtgraph"
            f"{' · ejecutable empaquetado' if getattr(sys, 'frozen', False) else ''}"
        )
        tech.setProperty("role", "hint")
        layout.addWidget(tech)
        hint = QLabel("Presione F1 en la aplicación para abrir el manual de uso.")
        hint.setProperty("role", "hint")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Cerrar")
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
