"""Controlador de ayuda: manual integrado (F1 contextual) y pistas de primera vez en la barra de estado."""
from __future__ import annotations

from PyQt6.QtCore import QObject

from models.help_content import HelpContent
from views.components.help_dialog import HelpDialog
from views.main_window import TAB_3D, TAB_ANALYSIS, TAB_MAP, TAB_SECTIONS, MainWindow

TAB_TOPICS = {TAB_MAP: "mapa", TAB_3D: "vista3d", TAB_SECTIONS: "estatus", TAB_ANALYSIS: "analisis"}

HINTS = {
    "connect": "Modo Conectar: arrastre desde una sección hasta otra y elija el tipo de relación en el menú. "
               "Esc cancela. (F1 para más ayuda)",
    "snap": "Ajustar a rejilla activado: al soltar un nodo se alinea a la cuadrícula de 10 px, así los nodos "
            "quedan en fila y las flechas salen rectas. Los nodos ya colocados no se mueven. (F1 para más ayuda)",
    "extras": "Avance y responsables ocultos: el mapa se exporta limpio. Vuelva a activarlos con F6.",
}


class HelpController(QObject):
    def __init__(self, window: MainWindow, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.window = window
        self.content = HelpContent()
        self._dialog: HelpDialog | None = None
        self._hinted: set[str] = set()
        window.act_manual.triggered.connect(self.show_contextual)
        window.act_shortcuts.triggered.connect(lambda: self.show_topic("atajos"))
        window.welcome_help.clicked.connect(lambda: self.show_topic("inicio"))
        window.act_connect.toggled.connect(lambda on: on and self.hint("connect"))
        window.act_snap.toggled.connect(lambda on: on and self.hint("snap"))
        window.act_show_extras.toggled.connect(lambda on: (not on) and self.hint("extras"))

    # ------------------------------------------------------------------ manual
    def dialog(self) -> HelpDialog:
        if self._dialog is None:
            self._dialog = HelpDialog(self.content, self.window)
        return self._dialog

    def show_topic(self, topic_id: str) -> None:
        dialog = self.dialog()
        dialog.show_topic(topic_id)
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def contextual_topic(self) -> str:
        if self.window.stack.currentIndex() == 0:
            return "inicio"
        return TAB_TOPICS.get(self.window.tabs.currentIndex(), "inicio")

    def show_contextual(self) -> None:
        self.show_topic(self.contextual_topic())

    # ------------------------------------------------------------------ pistas
    def hint(self, key: str) -> bool:
        """Muestra la pista una sola vez por sesión. Devuelve True si se mostró."""
        if key in self._hinted or key not in HINTS:
            return False
        self._hinted.add(key)
        self.window.show_status(HINTS[key], 10000)
        return True
