"""Guardas de rendimiento y de trabajo en segundo plano (fase 8: sin congelamientos).

Los umbrales de tiempo son holgados para no fallar en CI; lo que protegen es el orden de magnitud
(p. ej. que filtrar el autocompletado no vuelva a costar 300 ms por tecla).
"""
from __future__ import annotations

import sqlite3
import threading
import time
from pathlib import Path

import pytest

from models.database import ProjectDatabase, ProjectLockedError
from models.section_completer_model import ROLE_CODE_KEY, ROLE_KIND, SectionCompleterModel, SectionFilterProxy
from utils.debounce import Debouncer
from utils.perf import FreezeWatchdog
from utils.workers import run_in_background, run_with_progress
from views.components.graph3d_widget import MAX_ALL_LABELS, MAX_AUTO_LABELS, choose_label_indices


# ============================================================================ autocompletado
@pytest.fixture
def completer(model):
    if not model.master.available:
        pytest.skip("catálogo MasterFormat no disponible")
    model.add_section("03 30 00", "Concreto")
    model.add_section("31 23 00", "Excavación")
    source = SectionCompleterModel()
    source.rebuild(model)
    proxy = SectionFilterProxy()
    proxy.setSourceModel(source)
    return source, proxy


def _rows(proxy, role):
    return [proxy.index(r, 0).data(role) for r in range(proxy.rowCount())]


def test_text_query_is_fast_and_keeps_project_first(completer):
    source, proxy = completer
    proxy.set_query("xyzq")  # calentar (primer invalidateFilter)
    t0 = time.perf_counter()
    proxy.set_query("conc")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert elapsed_ms < 150, f"filtrar por texto tardó {elapsed_ms:.0f} ms (antes ~330 ms por el orden en Python)"
    kinds = _rows(proxy, ROLE_KIND)
    assert kinds and kinds[0] == "section"                       # la sección del proyecto va primero
    first_catalog = kinds.index("catalog") if "catalog" in kinds else len(kinds)
    assert all(k == "section" for k in kinds[:first_catalog])     # y todas las del proyecto antes del catálogo
    keys = _rows(proxy, ROLE_CODE_KEY)[first_catalog:]
    from models.relation_normalizer import sort_key

    assert keys == sorted(keys, key=sort_key)                     # el catálogo conserva el orden natural por clave
    for row in range(proxy.rowCount()):
        assert "conc" in source.entry(proxy.mapToSource(proxy.index(row, 0)).row()).search


def test_digit_query_shows_only_prefix_matches_when_they_exist(completer):
    source, proxy = completer
    proxy.set_query("0330 00")
    keys = _rows(proxy, ROLE_CODE_KEY)
    assert keys and all(k.startswith("033000") for k in keys)
    assert keys[0] == "033000"  # la sección del proyecto (03 30 00) encabeza
    proxy.set_query("03 30")
    keys = _rows(proxy, ROLE_CODE_KEY)
    assert keys and all(k.startswith("0330") for k in keys)
    # Sin coincidencias por prefijo se muestran las que contienen los dígitos.
    all_keys = [e.code_key for e in source.entries()]
    digits = "3000"
    if not any(k.startswith(digits) for k in all_keys):
        proxy.set_query(digits)
        keys = _rows(proxy, ROLE_CODE_KEY)
        assert keys and all(digits in k for k in keys) and "033000" in keys


def test_rebuild_after_query_recomputes_prefix_rule(completer, model):
    source, proxy = completer
    proxy.set_query("777777")
    assert proxy.rowCount() == 0
    model.add_section("77 77 77", "Sección rara")
    source.rebuild(model)  # modelReset -> la regla de prefijo se recalcula
    assert _rows(proxy, ROLE_CODE_KEY) == ["777777"]


def test_catalog_record_search_is_cached(master):
    if not master.available:
        pytest.skip("catálogo MasterFormat no disponible")
    rec = master.all()[0]
    assert rec.search is rec.search  # cached_property: misma cadena, no se recalcula por acceso


# ============================================================================ coalescencia
def test_debouncer_coalesces_bursts(qtbot):
    calls: list[int] = []
    deb = Debouncer(lambda: calls.append(1), 30)
    for _ in range(50):
        deb("ignored", 123)  # firma libre: acepta argumentos de cualquier señal
    assert deb.calls == 50 and deb.pending and not calls
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=2000)
    qtbot.wait(80)
    assert len(calls) == 1 and deb.fired == 1
    deb.schedule()
    deb.flush()
    assert len(calls) == 2 and not deb.pending
    deb.schedule()
    deb.cancel()
    qtbot.wait(80)
    assert len(calls) == 2


def test_bulk_groups_mutations_in_one_transaction(model):
    statements: list[str] = []
    model.db.conn.set_trace_callback(statements.append)
    with model.bulk():
        for i in range(20):
            model.add_section(f"{i:02d} 11 00", f"Sección {i}")
    model.db.conn.set_trace_callback(None)
    begins = [s for s in statements if s.upper().startswith("BEGIN")]
    assert len(begins) == 1, f"se esperaban 1 BEGIN, hubo {len(begins)}"
    assert len(model.sections()) == 20


# ============================================================================ hilos
def test_run_in_background_delivers_result_and_errors(qtbot):
    handle = run_in_background(lambda x: x * 2, 21)
    with qtbot.waitSignal(handle.done, timeout=5000) as blocker:
        pass
    assert blocker.args == [42] and handle.result == 42

    def boom() -> None:
        raise ValueError("falló")

    handle = run_in_background(boom)
    with qtbot.waitSignal(handle.failed, timeout=5000) as blocker:
        pass
    assert isinstance(blocker.args[0], ValueError) and "falló" in blocker.args[1]


def test_run_with_progress_reports_in_main_thread(qtbot):
    from PyQt6.QtWidgets import QWidget

    parent = QWidget()
    qtbot.addWidget(parent)
    seen: dict[str, object] = {}
    main_thread = threading.get_ident()

    def work() -> str:
        seen["worker_thread"] = threading.get_ident()
        return "listo"

    def done(result: str) -> None:
        seen["result"] = result
        seen["done_thread"] = threading.get_ident()

    handle = run_with_progress(parent, "Prueba", "Trabajando…", work, on_done=done, delay_ms=50)
    qtbot.waitUntil(lambda: "result" in seen, timeout=5000)
    assert seen["result"] == "listo" and handle.finished
    assert seen["worker_thread"] != main_thread and seen["done_thread"] == main_thread


def test_snapshot_export_report_from_worker_thread(model, tmp_path):
    from models.entities import UiKind
    from models.report_export import export_report_xlsx

    a = model.add_section("03 30 00", "Concreto")
    b = model.add_section("31 23 00", "Excavación")
    model.add_relation(a.id, UiKind.REFERENCES, b.id)
    snapshot = model.snapshot()
    assert [s.code for s in snapshot.sections()] == [s.code for s in model.sections()]
    assert snapshot.meta().code == model.meta().code and snapshot.graph.edge_count == 1
    out = tmp_path / "reporte.xlsx"
    errors: list[BaseException] = []

    def work() -> None:
        try:
            export_report_xlsx(snapshot, out)  # otro hilo: el modelo real (SQLite) no se toca
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    t = threading.Thread(target=work)
    t.start()
    t.join(timeout=30)
    assert not errors and out.exists() and out.stat().st_size > 0


# ============================================================================ SQLite / OneDrive
def test_database_pragmas_do_not_block_for_seconds(tmp_path):
    db = ProjectDatabase.create(tmp_path / "p.specrel", "X", "Y")
    try:
        assert db.conn.execute("PRAGMA busy_timeout").fetchone()[0] == 1500
        assert db.conn.execute("PRAGMA synchronous").fetchone()[0] == 1  # NORMAL
        assert db.conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
    finally:
        db.close()


def test_locked_file_raises_lock_error_quickly(tmp_path, monkeypatch):
    import models.database as dbmod

    monkeypatch.setattr(dbmod, "BUSY_TIMEOUT_MS", 200)
    monkeypatch.setattr(dbmod, "LOCK_RETRY_DELAY", 0.05)
    path = tmp_path / "locked.specrel"
    db = ProjectDatabase.create(path, "X", "Y")
    other = sqlite3.connect(str(path), isolation_level=None)
    other.execute("BEGIN EXCLUSIVE")  # simula OneDrive/otro proceso reteniendo el archivo
    try:
        t0 = time.perf_counter()
        with pytest.raises(ProjectLockedError):
            with db.transaction():
                db.touch()
        elapsed = time.perf_counter() - t0
        assert elapsed < 2.0, f"esperó {elapsed:.1f} s con el archivo bloqueado"
        other.execute("ROLLBACK")
        with db.transaction():  # liberado: vuelve a funcionar
            db.touch()
    finally:
        other.close()
        db.close()


# ============================================================================ 3D y vigilancia
def test_choose_label_indices_caps_show_all():
    degrees = list(range(500))
    chosen = choose_label_indices(degrees, show_all=True, highlight_idx=None)
    assert len(chosen) == MAX_ALL_LABELS and max(chosen) == 499 and 0 not in chosen  # las de mayor grado
    assert len(choose_label_indices(list(range(100)), True, None)) == 100
    auto = choose_label_indices(degrees, False, None)
    assert len(auto) == MAX_AUTO_LABELS and 499 in auto
    with_hl = choose_label_indices(degrees, False, {3, 4})
    assert with_hl == {3, 4}
    assert {7} <= choose_label_indices(degrees, True, {7})


def test_freeze_watchdog_logs_main_thread_stack():
    lines: list[str] = []
    dog = FreezeWatchdog(threshold_ms=100, sink=lines.append).start()
    try:
        dog.beat()
        time.sleep(0.35)          # el hilo principal "se congela"
        dog.beat()
        time.sleep(0.06)          # un ciclo de sondeo (threshold/4) para registrar la recuperación
    finally:
        dog.stop()
    assert dog.freezes == 1
    assert any("CONGELADA" in line and "test_perf_guards" in line for line in lines)
    assert any("RECUPERADA" in line for line in lines)


def test_edge_geometry_cached_and_scene_growth(qtbot):
    from models.entities import RelationKind
    from views.components.canvas.graph_scene import GraphScene

    scene = GraphScene()
    scene.add_node(1, "A", "Uno", "#FFFFFF", "#000000", 0, 0)
    scene.add_node(2, "B", "Dos", "#FFFFFF", "#000000", 400, 300)
    edge = scene.add_edge(10, 1, 2, RelationKind.REF, None, None, None)
    assert edge is not None
    before = edge.boundingRect()
    assert edge.shape() is edge.shape()  # cacheado: no se reconstruye en cada consulta
    rect_before = scene.sceneRect()
    scene.set_node_pos(2, 3000, 2500)
    assert edge.boundingRect() != before        # el movimiento recalculó la geometría cacheada
    assert scene.sceneRect().contains(scene.nodes[2].sceneBoundingRect())
    assert scene.sceneRect().width() > rect_before.width()


def test_find_jumps_is_fast_on_a_dense_grid():
    """30 flechas horizontales × 30 verticales = 900 cruces: el cálculo debe ser instantáneo (se repite al arrastrar)."""
    import time

    from views.components.canvas.line_jumps import find_jumps

    polys = {}
    for i in range(30):
        polys[i] = [(0.0, i * 40.0), (2000.0, i * 40.0)]
        polys[100 + i] = [(50.0 + i * 60.0, -100.0), (50.0 + i * 60.0, 2000.0)]
    t0 = time.perf_counter()
    result = find_jumps(polys)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert sum(len(v) for v in result.values()) == 900
    assert elapsed_ms < 50, f"find_jumps tardó {elapsed_ms:.0f} ms"
