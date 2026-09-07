"""Estatus, avance, responsables y observaciones por sección."""
from __future__ import annotations

import sqlite3

import pytest

from models.entities import UiKind
from models.project_io import apply_tables, export_tables_xlsx, read_tables, write_template_csv, write_template_xlsx
from models.repositories import ResponsibleRepo, SectionRepo, StatusRepo


def test_seeds_present(model):
    assert [s.name for s in model.statuses()] == ["No iniciada", "En elaboración", "En revisión", "Aprobada", "Emitida"]
    assert [r.code for r in model.responsibles()] == ["INIO", "INIG", "INIE", "INI-PY", "INIC"]
    assert model.responsible_by_code("INIO").name == "Ingeniería de Costos y Especificaciones"
    assert model.default_status().name == "No iniciada"


def test_new_section_gets_default_status_and_zero_progress(model):
    s = model.add_section("A", "Alpha")
    assert model.status(s.status_id).name == "No iniciada" and s.progress == 0
    assert model.section_responsibles(s.id) == []


def test_progress_bounds_enforced_by_db(db):
    repo = SectionRepo(db)
    with pytest.raises(sqlite3.IntegrityError):
        repo.insert("A", "Alpha", progress=120)


def test_set_status_progress_responsibles_emit_updates(model, spy):
    s = model.add_section("A", "Alpha")
    updated = spy(model.sectionUpdated)
    st = next(x for x in model.statuses() if x.name == "En elaboración")
    model.set_section_status(s.id, st.id)
    model.set_section_progress(s.id, 70)
    inio, inig = model.responsible_by_code("INIO"), model.responsible_by_code("inig")
    model.set_section_responsibles(s.id, [inig.id, inio.id])
    model.set_section_observations(s.id, "Pendiente")
    s = model.section(s.id)
    assert s.status_id == st.id and s.progress == 70 and s.notes == "Pendiente"
    assert [r.code for r in model.section_responsibles(s.id)] == ["INIG", "INIO"]  # conserva el orden
    assert len(updated) == 4
    model.set_section_progress(s.id, 70)  # sin cambio -> sin señal
    model.set_section_responsibles(s.id, [inig.id, inio.id])
    assert len(updated) == 4
    model.set_section_progress(s.id, 250)
    assert model.section(s.id).progress == 100


def test_remove_responsible_cascades_to_sections(model, spy):
    s = model.add_section("A")
    inio = model.responsible_by_code("INIO")
    model.set_section_responsibles(s.id, [inio.id])
    updated = spy(model.sectionUpdated)
    changed = spy(model.responsiblesChanged)
    model.remove_responsible(inio.id)
    assert model.section_responsibles(s.id) == [] and len(updated) == 1 and len(changed) == 1
    assert ResponsibleRepo(model.db).for_section(s.id) == []


def test_remove_status_clears_sections(model):
    s = model.add_section("A")
    sid = s.status_id
    model.remove_status(sid)
    assert model.section(s.id).status_id is None
    assert StatusRepo(model.db).get(sid) is None


def test_add_update_responsible_and_status(model):
    r = model.add_responsible("INIA", "Ambiental", "#00B050")
    r.name = "Ambiente"
    model.update_responsible(r)
    assert model.responsible_by_code("INIA").name == "Ambiente"
    st = model.add_status("Cancelada", "#C00000")
    st.is_default = True
    model.update_status(st)
    assert model.default_status().name == "Cancelada"


def test_persist_and_reopen_extras(tmp_path, qcore_app, master):
    from models.project_model import ProjectModel

    path = tmp_path / "p.specrel"
    m = ProjectModel(master=master)
    m.new_project(path, "CC", "Demo")
    s = m.add_section("A", "Alpha")
    m.set_section_progress(s.id, 55)
    m.set_section_responsibles(s.id, [m.responsible_by_code("INIC").id])
    m.close()
    m2 = ProjectModel(master=master)
    m2.open_project(path)
    s2 = m2.section_by_code("A")
    assert s2.progress == 55 and [r.code for r in m2.section_responsibles(s2.id)] == ["INIC"]
    m2.close()


def test_template_roundtrip_with_extras(tmp_path, model):
    path = tmp_path / "plantilla.xlsx"
    write_template_xlsx(path)
    summary = apply_tables(model, read_tables([path]))
    assert not summary.errors
    concreto = model.section_by_code("03 30 00")
    assert concreto.progress == 70 and model.status(concreto.status_id).name == "En elaboración"
    assert [r.code for r in model.section_responsibles(concreto.id)] == ["INIO", "INIC"]
    assert concreto.notes == "Pendiente revisión de mezcla"
    # Exportar y reimportar en otro proyecto conserva todo
    out = tmp_path / "tablas.xlsx"
    export_tables_xlsx(model, out)
    tables = read_tables([out])
    row = next(r for r in tables.sections if r["code"] == "03 30 00")
    assert row["status"] == "En elaboración" and row["progress"] == "70" and row["responsibles"] == "INIO, INIC"


def test_import_creates_unknown_status_and_responsible(tmp_path, model):
    sec, _rel = write_template_csv(tmp_path)
    sec.write_text("Número;Descripción;Categoría;Color;Estatus;Avance;Responsables;Observaciones\n"
                   "A;Alpha;;;Suspendida;0.5;INIA/INIO;nota\n", encoding="utf-8-sig")
    summary = apply_tables(model, read_tables([sec]))
    assert summary.statuses_created == 1 and summary.responsibles_created == 1
    a = model.section_by_code("A")
    assert model.status(a.status_id).name == "Suspendida" and a.progress == 50
    assert [r.code for r in model.section_responsibles(a.id)] == ["INIA", "INIO"]


def test_sections_table_model_reflects_and_requests_edits(model, qcore_app):
    from models.sections_table_model import COL_PROGRESS, COL_RESP, COL_STATUS, SectionsTableModel

    tm = SectionsTableModel(model)
    a = model.add_section("A", "Alpha")
    assert tm.rowCount() == 1
    assert tm.index(0, COL_STATUS).data() == "No iniciada"
    requests = []
    tm.editRequested.connect(lambda sid, col, val: requests.append((sid, col, val)))
    from PyQt6.QtCore import Qt

    tm.setData(tm.index(0, COL_PROGRESS), 40, Qt.ItemDataRole.EditRole)
    tm.setData(tm.index(0, COL_RESP), [model.responsible_by_code("INIO").id], Qt.ItemDataRole.EditRole)
    assert requests[0] == (a.id, COL_PROGRESS, 40) and requests[1][1] == COL_RESP
    model.set_section_progress(a.id, 40)
    assert tm.index(0, COL_PROGRESS).data() == "40 %"
    model.remove_section(a.id)
    assert tm.rowCount() == 0


def test_node_extras_geometry(qcore_app):
    from PyQt6.QtWidgets import QApplication

    if QApplication.instance() is None:
        pytest.skip("requiere QApplication")
    from views.components.canvas.section_node_item import EXTRA_BOTTOM, EXTRA_TOP, SectionNodeItem

    node = SectionNodeItem(1, "31 33 23", "Estabilización Roca", "#E2EFDA", "#70AD47")
    base = node.rect()
    node.set_extras("En elaboración", "#FFE699", 70, [("INIO", "#5B9BD5"), ("INIG", "#70AD47")], show=True)
    br = node.boundingRect()
    assert br.top() <= base.top() - EXTRA_TOP and br.bottom() >= base.bottom() + EXTRA_BOTTOM
    assert node.shape().boundingRect() == base  # los puertos y la selección siguen en el octágono
    node.set_show_extras(False)
    assert node.boundingRect().height() < br.height()
    assert "INIO" in node.toolTip() and "70 %" in node.toolTip()
