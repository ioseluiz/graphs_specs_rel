"""Diálogo «Estilo de línea…»: color, trazo y grosor de una o varias flechas, con vista previa."""
from __future__ import annotations

from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from config import palette
from models.line_styles import DASH_KEYS, DASH_LABELS, DEFAULT_WIDTH, WIDTH_PRESETS
from views.components.canvas.line_style_qt import dash_icon, preview_pixmap, width_icon
from views.components.categories_dialog import _ColorButton


class LineStyleDialog(QDialog):
    def __init__(self, color: str | None, dash: str, width: float | None, parent=None, count: int = 1) -> None:
        super().__init__(parent)
        self.setWindowTitle("Estilo de línea" if count <= 1 else f"Estilo de línea ({count} flechas)")
        self.setMinimumWidth(360)
        layout = QVBoxLayout(self)
        hint = QLabel("El estilo se guarda con la relación. Vacío o «predeterminado» usa el azul y el grosor "
                      "normal de la aplicación. La punta de la flecha siempre es sólida.")
        hint.setProperty("role", "hint")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        form = QFormLayout()
        color_row = QHBoxLayout()
        self.custom_color_check = QCheckBox("Color personalizado")
        self.custom_color_check.setChecked(bool(color))
        self.color_button = _ColorButton(color or palette.EDGE_COLOR)
        self.color_button.setEnabled(bool(color))
        color_row.addWidget(self.custom_color_check)
        color_row.addWidget(self.color_button)
        color_row.addStretch(1)
        form.addRow("Color:", color_row)

        self.dash_combo = QComboBox()
        for key in DASH_KEYS:
            self.dash_combo.addItem(dash_icon(key), DASH_LABELS[key], key)
        self.dash_combo.setCurrentIndex(max(0, self.dash_combo.findData(dash)))
        form.addRow("Trazo:", self.dash_combo)

        self.width_combo = QComboBox()
        for name, preset in WIDTH_PRESETS:
            self.width_combo.addItem(width_icon(preset), f"{name} ({preset:g} px)", preset)
        effective = width if width is not None else DEFAULT_WIDTH
        idx = next((i for i in range(self.width_combo.count())
                    if abs(float(self.width_combo.itemData(i)) - effective) < 1e-6), -1)
        if idx < 0:
            self.width_combo.addItem(width_icon(effective), f"Personalizado ({effective:g} px)", effective)
            idx = self.width_combo.count() - 1
        self.width_combo.setCurrentIndex(idx)
        form.addRow("Grosor:", self.width_combo)

        self.preview = QLabel()
        form.addRow("Vista previa:", self.preview)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Aplicar")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.custom_color_check.toggled.connect(self._on_custom_toggled)
        # `_ColorButton._pick` se conectó antes en su constructor: cuando llega este slot, `.color` ya cambió.
        self.color_button.clicked.connect(self._refresh_preview)
        self.dash_combo.currentIndexChanged.connect(self._refresh_preview)
        self.width_combo.currentIndexChanged.connect(self._refresh_preview)
        self._refresh_preview()

    def _on_custom_toggled(self, on: bool) -> None:
        self.color_button.setEnabled(on)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        color, dash, width = self.values()
        self.preview.setPixmap(preview_pixmap(color, dash, width))

    def values(self) -> tuple[str | None, str, float | None]:
        """(color hex o None, clave de trazo, grosor o None si es el predeterminado)."""
        color = self.color_button.color.upper() if self.custom_color_check.isChecked() else None
        dash = str(self.dash_combo.currentData())
        width = float(self.width_combo.currentData())
        return color, dash, (None if abs(width - DEFAULT_WIDTH) < 1e-6 else width)
