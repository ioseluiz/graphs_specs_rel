"""Debouncer: agrupa ráfagas de llamadas (p. ej. 300 `sectionAdded` en una importación) en una sola.

Uso:
    self._refresh = Debouncer(self.refresh, 50, parent=self)
    signal.connect(self._refresh)          # cada emisión reprograma el temporizador
    self._refresh.flush()                  # ejecutar ya (pruebas, cierre de proyecto)
"""
from __future__ import annotations

from typing import Callable

from PyQt6.QtCore import QObject, QTimer


class Debouncer(QObject):
    def __init__(self, callback: Callable[[], None], interval_ms: int = 50, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._callback = callback
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(max(0, int(interval_ms)))
        self._timer.timeout.connect(self._fire)
        self.calls = 0          # llamadas recibidas (diagnóstico / pruebas)
        self.fired = 0          # ejecuciones reales del callback

    def __call__(self, *_args, **_kwargs) -> None:
        """Compatible con cualquier firma de señal: los argumentos se ignoran."""
        self.schedule()

    def schedule(self) -> None:
        self.calls += 1
        self._timer.start()

    @property
    def pending(self) -> bool:
        return self._timer.isActive()

    def cancel(self) -> None:
        self._timer.stop()

    def flush(self) -> None:
        """Ejecuta el callback ahora si hay una llamada pendiente."""
        if self._timer.isActive():
            self._timer.stop()
            self._fire()

    def _fire(self) -> None:
        self.fired += 1
        self._callback()
