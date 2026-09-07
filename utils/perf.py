"""Instrumentación de rendimiento (activa con DEBUG_MODE=true en el .env).

- `timed("nombre")`: decorador que registra la duración de una función cuando supera el umbral.
- `FreezeWatchdog`: hilo que vigila un latido del hilo principal; si deja de latir más de
  `threshold_ms`, escribe en el log la pila del hilo principal en ese instante (dónde está
  congelada la interfaz) y, al recuperarse, cuánto duró el bloqueo.

El log queda en %APPDATA%\\SpecRel\\perf.log para que el usuario pueda enviarlo.
"""
from __future__ import annotations

import functools
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Callable

from config.settings import appdata_dir

SLOW_MS = 150.0


def perf_log_path() -> Path:
    return appdata_dir() / "perf.log"


def _write(line: str) -> None:
    try:
        perf_log_path().parent.mkdir(parents=True, exist_ok=True)
        with perf_log_path().open("a", encoding="utf-8") as fh:
            fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S} {line}\n")
    except OSError:
        pass


def timed(name: str, threshold_ms: float = SLOW_MS, enabled: Callable[[], bool] | None = None):
    """Registra `name` y la duración cuando supera `threshold_ms` (si `enabled()` lo permite)."""

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            if enabled is not None and not enabled():
                return fn(*args, **kwargs)
            t0 = time.perf_counter()
            try:
                return fn(*args, **kwargs)
            finally:
                ms = (time.perf_counter() - t0) * 1000
                if ms >= threshold_ms:
                    _write(f"LENTO {name}: {ms:.0f} ms")
        return wrapper

    return decorator


class FreezeWatchdog:
    """Detecta bloqueos del hilo principal y registra dónde ocurren.

    El hilo principal debe llamar a `beat()` periódicamente (un QTimer de `interval_ms`).
    Si pasan más de `threshold_ms` sin latido, el vigilante captura la pila del hilo principal.
    """

    def __init__(self, threshold_ms: int = 400, interval_ms: int = 100,
                 sink: Callable[[str], None] = _write) -> None:
        self.threshold = threshold_ms / 1000.0
        self.interval_ms = interval_ms
        self._sink = sink
        self._last_beat = time.monotonic()
        self._main_thread_id = threading.main_thread().ident
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._timer = None
        self.freezes = 0

    # ------------------------------------------------------------------ ciclo de vida
    def start(self) -> "FreezeWatchdog":
        if self._thread is not None:
            return self
        self._last_beat = time.monotonic()
        self._thread = threading.Thread(target=self._run, name="specrel-freeze-watchdog", daemon=True)
        self._thread.start()
        return self

    def start_with_qt_timer(self) -> "FreezeWatchdog":
        """Además del hilo vigilante, instala el latido con un QTimer del hilo principal."""
        from PyQt6.QtCore import QTimer

        self._timer = QTimer()
        self._timer.setInterval(self.interval_ms)
        self._timer.timeout.connect(self.beat)
        self._timer.start()
        return self.start()

    def stop(self) -> None:
        self._stop.set()
        if self._timer is not None:
            self._timer.stop()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def beat(self) -> None:
        self._last_beat = time.monotonic()

    # ------------------------------------------------------------------ vigilancia
    def _main_stack(self) -> str:
        frame = sys._current_frames().get(self._main_thread_id)  # noqa: SLF001
        if frame is None:
            return "  (pila no disponible)"
        lines = traceback.format_stack(frame)
        return "".join(lines[-12:]).rstrip()

    def _run(self) -> None:
        reported = False
        started = 0.0
        while not self._stop.wait(self.threshold / 4):
            gap = time.monotonic() - self._last_beat
            if gap >= self.threshold and not reported:
                reported, started = True, self._last_beat
                self.freezes += 1
                self._sink(f"CONGELADA la interfaz ≥ {gap * 1000:.0f} ms. Pila del hilo principal:\n{self._main_stack()}")
            elif gap < self.threshold and reported:
                reported = False
                self._sink(f"RECUPERADA tras {(self._last_beat - started) * 1000:.0f} ms")
