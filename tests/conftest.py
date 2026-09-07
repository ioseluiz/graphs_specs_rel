from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from models.database import ProjectDatabase  # noqa: E402
from models.project_model import ProjectModel  # noqa: E402


@pytest.fixture(scope="session")
def qcore_app():
    app = QCoreApplication.instance() or QCoreApplication([])
    yield app


@pytest.fixture
def db():
    database = ProjectDatabase(None)
    database.initialize_schema()
    yield database
    database.close()


@pytest.fixture(scope="session")
def master():
    from models.master_catalog import MasterCatalog

    return MasterCatalog()


@pytest.fixture
def model(qcore_app, master):
    m = ProjectModel(master=master)
    m.new_project(None, "CC-25-01", "Proyecto de prueba")
    yield m
    m.close()


class SignalSpy:
    """Registra las emisiones de una señal PyQt (sin depender de QSignalSpy)."""

    def __init__(self, signal) -> None:
        self.calls: list[tuple] = []
        signal.connect(self._record)

    def _record(self, *args) -> None:
        self.calls.append(args)

    def __len__(self) -> int:
        return len(self.calls)


@pytest.fixture
def spy():
    return SignalSpy
