"""Controlador de la vista 3D: calcula/carga la disposición y alimenta el widget GL.

El cálculo completo de la disposición (`layout3d`, spring layout con scipy) corre en un hilo de
trabajo: la primera vez cuesta ~1 s solo por importar scipy, y con cientos de secciones cientos de
milisegundos más. Mientras se calcula, la pestaña muestra «Calculando disposición 3D…» y conserva
la disposición anterior. Los ajustes incrementales (nodos nuevos cerca de sus vecinos) siguen siendo
sincrónicos porque son inmediatos.
"""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import QObject

from config import palette
from models.entities import RelationKind
from models.layout_engine import layout3d, place_new_node_3d
from models.project_model import ProjectModel
from utils.debounce import Debouncer
from utils.workers import run_in_background
from views.main_window import TAB_3D, MainWindow

DEFAULT_SEED = 42


class View3DController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.widget = window.view3d
        self._dirty = True
        self._computing: tuple[str, int] | None = None  # (hash del grafo, semilla) en cálculo
        self.async_layout = True  # las pruebas pueden desactivarlo para obtener resultados sincrónicos
        # Coalescido: una ráfaga de cambios con la pestaña 3D visible refresca una sola vez.
        self.refresh_later = Debouncer(self.refresh, 60, self)
        project.projectLoaded.connect(self._mark_dirty)
        project.projectClosed.connect(self._on_closed)
        project.graphChanged.connect(self._mark_dirty)
        project.sectionUpdated.connect(lambda _sid: self._mark_dirty())
        project.categoriesChanged.connect(self._mark_dirty)
        window.tabs.currentChanged.connect(self._on_tab_changed)
        self.widget.recalcRequested.connect(self.recalculate)

    def _mark_dirty(self) -> None:
        self._dirty = True
        if self.window.tabs.currentIndex() == TAB_3D:
            self.refresh_later.schedule()

    def _on_closed(self) -> None:
        self._dirty = True
        self._computing = None
        self.refresh_later.cancel()
        self.widget.clear_graph()

    def _on_tab_changed(self, index: int) -> None:
        if index == TAB_3D and self._dirty:
            self.refresh()

    # ------------------------------------------------------------------ disposición
    def _current_seed(self) -> int:
        try:
            return int(self.project.setting("layout3d_seed", str(DEFAULT_SEED)) or DEFAULT_SEED)
        except ValueError:
            return DEFAULT_SEED

    def _needs_full_layout(self) -> bool:
        return not self.project.layout3d()

    def _positions(self, force: bool = False) -> dict[int, tuple[float, float, float]]:
        """Disposición actual (sincrónica). Con caché la ajusta incrementalmente; sin caché la calcula."""
        g = self.project.graph
        cached = self.project.layout3d()
        stored_hash = self.project.setting("layout3d_graph_hash")
        seed = self._current_seed()
        if not force and cached and stored_hash == g.graph_hash():
            return cached
        if not force and cached:
            # Grafo cambiado: conservar lo cacheado y ubicar nodos nuevos cerca de sus vecinos.
            positions = {sid: p for sid, p in cached.items() if sid in g.G}
            new_ids = [sid for sid in g.G.nodes if sid not in positions]
            for k, sid in enumerate(new_ids):
                positions[sid] = place_new_node_3d(positions, g.neighbors(sid), k)
            if new_ids or len(positions) != len(cached):
                self.project.store_layout3d(positions, seed)
            return positions
        positions = layout3d(g.G, seed)
        self.project.store_layout3d(positions, seed)
        return positions

    def _compute_async(self, seed: int) -> None:
        """Lanza `layout3d` en un hilo con una copia del grafo; el resultado se aplica al volver."""
        g = self.project.graph
        key = (g.graph_hash(), seed)
        if self._computing == key:
            return  # ya hay un cálculo idéntico en curso
        self._computing = key
        self.widget.set_status("Calculando disposición 3D…")
        run_in_background(layout3d, g.G.copy(), seed, on_done=lambda pos: self._on_layout_ready(key, pos),
                          on_error=lambda exc, _tb: self._on_layout_failed(key, exc), parent=self)

    def _on_layout_ready(self, key: tuple[str, int], positions: dict) -> None:
        if self._computing != key:
            return  # llegó tarde: hubo otro cálculo o se cerró el proyecto
        self._computing = None
        if not self.project.is_open:
            return
        if self.project.graph.graph_hash() != key[0]:
            # El grafo cambió mientras se calculaba: guardar y dejar que el ajuste incremental complete.
            self.project.store_layout3d(positions, key[1])
            self._dirty = True
            self.refresh()
            return
        self.project.store_layout3d(positions, key[1])
        self._dirty = True
        self.refresh()

    def _on_layout_failed(self, key: tuple[str, int], exc: BaseException) -> None:
        if self._computing == key:
            self._computing = None
        self.widget.set_status(f"No se pudo calcular la disposición 3D: {exc}")

    def recalculate(self) -> None:
        if not self.project.is_open:
            return
        seed = self._current_seed() + 1
        if self.async_layout:
            self._compute_async(seed)
            return
        positions = layout3d(self.project.graph.G, seed)
        self.project.store_layout3d(positions, seed)
        self._dirty = True
        self.refresh()

    # ------------------------------------------------------------------ render
    def refresh(self) -> None:
        self.refresh_later.cancel()
        if not self.project.is_open:
            self.widget.clear_graph()
            return
        if not self.widget.ensure_gl():
            self._dirty = False
            return
        if self.async_layout and self._needs_full_layout() and self.project.graph.node_count > 0:
            self._compute_async(self._current_seed())
            self._dirty = False
            return
        positions = self._positions()
        self._render(positions)
        self._dirty = False

    def _render(self, positions: dict[int, tuple[float, float, float]]) -> None:
        sections = self.project.sections()
        ids = [s.id for s in sections if s.id in positions]
        index = {sid: i for i, sid in enumerate(ids)}
        pos = np.array([positions[sid] for sid in ids], dtype=np.float32) if ids else np.zeros((0, 3), np.float32)
        fills: list[str] = []
        labels: list[str] = []
        for sid in ids:
            s = self.project.section(sid)
            fills.append(self.project.section_colors(s)[1] if s else palette.BORDER_STRONG)
            labels.append(s.code if s else str(sid))
        edges: list[tuple[int, int]] = []
        mutual: list[bool] = []
        for rel in self.project.relations():
            if rel.source_id in index and rel.target_id in index:
                edges.append((index[rel.source_id], index[rel.target_id]))
                mutual.append(rel.kind is RelationKind.MUTUAL)
        degrees = [self.project.graph.G.degree(sid) if sid in self.project.graph.G else 0 for sid in ids]
        self.widget.set_graph(
            ids, pos, fills,
            np.array(edges, dtype=np.int32).reshape(-1, 2), np.array(mutual, dtype=bool),
            labels, degrees,
        )
