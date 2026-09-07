"""Trabajo en segundo plano sin congelar la interfaz.

Regla: las funciones que se ejecutan en el hilo de trabajo son puras (reciben datos ya extraídos,
nunca tocan widgets ni el `ProjectModel` abierto ni su conexión SQLite). El resultado vuelve al
hilo principal por señal, donde el controlador actualiza modelo y vistas.

    task = run_in_background(export_report_xlsx, snapshot, path, on_done=self._done, on_error=self._fail)
    ...
    with busy_cursor():          # operaciones de 200 ms a 2 s que sí deben ser sincrónicas
        self.canvas.populate()
"""
from __future__ import annotations

import traceback
from contextlib import contextmanager
from typing import Any, Callable, Iterator

from PyQt6.QtCore import QObject, QRunnable, Qt, QThreadPool, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication, QProgressDialog, QWidget


class TaskSignals(QObject):
    finished = pyqtSignal(object)          # resultado de la función
    failed = pyqtSignal(object, str)       # excepción, traceback formateado


class BackgroundTask(QRunnable):
    """QRunnable que ejecuta `fn(*args, **kwargs)` y devuelve el resultado por señal."""

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self.fn, self.args, self.kwargs = fn, args, kwargs
        self.signals = TaskSignals()
        self.setAutoDelete(True)

    def run(self) -> None:  # hilo de trabajo
        try:
            result = self.fn(*self.args, **self.kwargs)
        except BaseException as exc:  # noqa: BLE001 - se reporta al hilo principal
            self.signals.failed.emit(exc, traceback.format_exc())
            return
        self.signals.finished.emit(result)


class TaskHandle(QObject):
    """Referencia viva a una tarea: mantiene las conexiones y expone `done`/`failed`.

    Se destruye junto con `parent`; si el padre desaparece antes de terminar, el resultado se ignora.
    """

    done = pyqtSignal(object)
    failed = pyqtSignal(object, str)

    def __init__(self, task: BackgroundTask, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._task = task
        self.finished = False
        self.result: Any = None
        self.error: BaseException | None = None
        # Conexión en cola: el slot corre en el hilo del TaskHandle (principal).
        task.signals.finished.connect(self._on_finished, Qt.ConnectionType.QueuedConnection)
        task.signals.failed.connect(self._on_failed, Qt.ConnectionType.QueuedConnection)
        self._signals = task.signals  # evitar que el recolector destruya el QObject antes de tiempo

    def _on_finished(self, result: Any) -> None:
        self.finished, self.result = True, result
        self.done.emit(result)

    def _on_failed(self, exc: BaseException, tb: str) -> None:
        self.finished, self.error = True, exc
        self.failed.emit(exc, tb)


def run_in_background(fn: Callable[..., Any], *args: Any, on_done: Callable[[Any], None] | None = None,
                      on_error: Callable[[BaseException, str], None] | None = None,
                      parent: QObject | None = None, **kwargs: Any) -> TaskHandle:
    """Ejecuta `fn` en el pool de hilos y entrega el resultado en el hilo principal."""
    task = BackgroundTask(fn, *args, **kwargs)
    handle = TaskHandle(task, parent)
    if on_done is not None:
        handle.done.connect(on_done)
    if on_error is not None:
        handle.failed.connect(on_error)
    QThreadPool.globalInstance().start(task)
    return handle


@contextmanager
def busy_cursor() -> Iterator[None]:
    """Cursor de espera mientras dura una operación sincrónica corta."""
    app = QApplication.instance()
    if app is not None:
        app.setOverrideCursor(Qt.CursorShape.WaitCursor)
    try:
        yield
    finally:
        if app is not None:
            app.restoreOverrideCursor()


def progress_dialog(parent: QWidget | None, title: str, text: str, cancelable: bool = False,
                    maximum: int = 0, delay_ms: int = 300) -> QProgressDialog:
    """Diálogo de progreso modal (indeterminado si `maximum` es 0) que aparece tras `delay_ms`."""
    dialog = QProgressDialog(text, "Cancelar" if cancelable else "", 0, maximum, parent)
    dialog.setWindowTitle(title)
    dialog.setWindowModality(Qt.WindowModality.WindowModal)
    dialog.setMinimumDuration(delay_ms)
    dialog.setMinimumWidth(420)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)
    if not cancelable:
        dialog.setCancelButton(None)
    return dialog


def run_with_progress(parent: QWidget | None, title: str, text: str, fn: Callable[..., Any], *args: Any,
                      on_done: Callable[[Any], None] | None = None,
                      on_error: Callable[[BaseException, str], None] | None = None,
                      delay_ms: int = 300, **kwargs: Any) -> TaskHandle:
    """Ejecuta `fn` en segundo plano mostrando un diálogo de progreso indeterminado si tarda.

    El diálogo (creado solo si la tarea supera `delay_ms`) es modal respecto a la ventana: el usuario
    no puede mutar el proyecto mientras tanto, pero la interfaz sigue repintándose y respondiendo al
    sistema, así que no aparece «No responde».
    """
    state: dict[str, Any] = {"dialog": None, "finished": False}

    def show_dialog() -> None:
        if state["finished"]:
            return
        dialog = progress_dialog(parent, title, text, cancelable=False, maximum=0, delay_ms=0)
        state["dialog"] = dialog
        dialog.show()

    timer = QTimer(parent)
    timer.setSingleShot(True)
    timer.setInterval(delay_ms)
    timer.timeout.connect(show_dialog)
    timer.start()

    def finish() -> None:
        state["finished"] = True
        timer.stop()
        dialog = state["dialog"]
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
            state["dialog"] = None

    def done(result: Any) -> None:
        finish()
        if on_done is not None:
            on_done(result)

    def failed(exc: BaseException, tb: str) -> None:
        finish()
        if on_error is not None:
            on_error(exc, tb)

    return run_in_background(fn, *args, on_done=done, on_error=failed, parent=parent, **kwargs)
