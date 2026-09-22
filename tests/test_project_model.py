from __future__ import annotations

import pytest

from models.entities import CatalogEntry, RelationKind, UiKind
from models.relation_normalizer import DuplicateRelationError, SelfRelationError


def test_add_section_emits_once_and_is_idempotent(model, spy):
    added = spy(model.sectionAdded)
    s1 = model.add_section("31 23 00", "Excavación")
    s2 = model.add_section("312300", "otra")
    assert s1.id == s2.id
    assert len(added) == 1
    assert model.position(s1.id) is not None


def test_get_or_create_uses_catalog(model):
    model.merge_catalog([CatalogEntry("311100", "31 11 00", "Limpieza y desbroce", "Contractual")])
    sec, created = model.get_or_create_section("31 11 00")
    assert created and sec.title == "Limpieza y desbroce"
    assert model.category(sec.category_id).name == "Contractual"
    sec2, created2 = model.get_or_create_section("31 11 00 lo que sea")
    assert not created2 and sec2.id == sec.id


def test_add_relation_normalizes_and_signals(model, spy):
    a = model.add_section("31 33 23", "Estabilización de roca")
    b = model.add_section("01 31 19", "Conferencia inicial")
    added = spy(model.relationAdded)
    rel = model.add_relation(b.id, UiKind.REFERENCED_BY, a.id)  # b es referenciada por a  => a -> b
    assert (rel.source_id, rel.target_id, rel.kind) == (a.id, b.id, RelationKind.REF)
    assert len(added) == 1
    assert model.graph.G.has_edge(a.id, b.id)


def test_inverse_relation_is_independent_and_same_direction_is_duplicate(model):
    a = model.add_section("A")
    b = model.add_section("B")
    rel = model.add_relation(a.id, UiKind.REFERENCES, b.id)
    back = model.add_relation(b.id, UiKind.REFERENCES, a.id)   # B → A: segunda flecha, sin conflicto
    assert back.id != rel.id and len(model.relations()) == 2
    assert model.reverse_relation(rel.id).id == back.id and model.reverse_relation(back.id).id == rel.id
    assert model.graph.G.has_edge(a.id, b.id) and model.graph.G.has_edge(b.id, a.id)
    assert model.graph.edge_count == 2
    with pytest.raises(DuplicateRelationError) as exc:
        model.add_relation(a.id, UiKind.REFERENCES, b.id)
    assert exc.value.existing.id == rel.id
    with pytest.raises(DuplicateRelationError) as exc2:
        model.add_relation(a.id, UiKind.REFERENCED_BY, b.id)   # = B → A, ya existe
    assert exc2.value.existing.id == back.id
    with pytest.raises(SelfRelationError):
        model.add_relation(a.id, UiKind.REFERENCES, a.id)


def test_invert_relation_resets_geometry_and_is_blocked_by_existing_inverse(model, spy):
    a = model.add_section("A")
    b = model.add_section("B")
    rel = model.add_relation(a.id, UiKind.REFERENCES, b.id)
    model.set_relation_geometry(rel.id, [(1.0, 2.0)], "right", "left")
    updated = spy(model.relationUpdated)
    new = model.invert_relation(rel.id)
    assert (new.source_id, new.target_id, new.kind) == (b.id, a.id, RelationKind.REF)
    assert new.waypoints is None and new.source_port is None   # los puertos cambian de nodo
    assert len(updated) == 1
    assert model.graph.G.has_edge(b.id, a.id) and not model.graph.G.has_edge(a.id, b.id)
    model.add_relation(a.id, UiKind.REFERENCES, b.id)          # ahora existen ambas
    with pytest.raises(DuplicateRelationError):
        model.invert_relation(new.id)                          # B → A no puede volverse A → B: ya existe


def test_relation_notes_persist(model):
    a = model.add_section("A")
    b = model.add_section("B")
    rel = model.add_relation(a.id, UiKind.REFERENCES, b.id, notes="  Ver artículo 3.2  ")
    assert rel.notes == "Ver artículo 3.2"
    model.set_relation_notes(rel.id, "")
    assert model.relation(rel.id).notes is None


def test_update_relation_changes_target(model):
    a = model.add_section("A")
    b = model.add_section("B")
    c = model.add_section("C")
    rel = model.add_relation(a.id, UiKind.REFERENCES, b.id)
    model.set_relation_geometry(rel.id, [(1.0, 2.0)], "top", "left")
    new = model.update_relation(rel.id, a.id, UiKind.REFERENCES, c.id)
    assert new.target_id == c.id
    assert new.waypoints is None  # el par cambió: geometría descartada
    assert not model.graph.G.has_edge(a.id, b.id) and model.graph.G.has_edge(a.id, c.id)


def test_remove_section_removes_relations(model, spy):
    a = model.add_section("A")
    b = model.add_section("B")
    model.add_relation(a.id, UiKind.REFERENCES, b.id)
    removed_rel = spy(model.relationRemoved)
    removed_sec = spy(model.sectionRemoved)
    removal = model.remove_section(a.id)
    assert len(removal.relations) == 1
    assert len(removed_rel) == 1 and len(removed_sec) == 1
    assert model.relations() == []
    assert model.graph.node_count == 1


def test_move_nodes_batch(model, spy):
    a = model.add_section("A")
    b = model.add_section("B")
    moved = spy(model.positionChanged)
    model.move_nodes({a.id: (100.0, 50.0), b.id: (300.0, 50.0)})
    assert len(moved) == 2
    assert model.position(a.id).pinned is True
    model.move_nodes({a.id: (100.0, 50.0)})  # sin cambio real
    assert len(moved) == 2


def test_persist_and_reopen(tmp_path, qcore_app):
    from models.project_model import ProjectModel

    path = tmp_path / "p.specrel"
    m = ProjectModel()
    m.new_project(path, "CC-1", "Demo")
    a = m.add_section("A", "Alpha")
    b = m.add_section("B", "Beta")
    m.add_relation(a.id, UiKind.REFERENCES, b.id)
    m.add_relation(b.id, UiKind.REFERENCES, a.id)
    m.move_node(a.id, 42, 24)
    m.close()

    m2 = ProjectModel()
    m2.open_project(path)
    assert m2.meta().header == "CC-1 | Demo"
    assert [s.code for s in m2.sections()] == ["A", "B"]
    assert len(m2.relations()) == 2 and all(r.kind is RelationKind.REF for r in m2.relations())
    assert (m2.position(m2.section_by_code("A").id).x, m2.position(m2.section_by_code("A").id).y) == (42, 24)
    m2.close()


def test_section_custom_color_overrides_category(model, spy):
    a = model.add_section("A", "Alpha")
    cat = model.category(a.category_id)
    assert model.section_colors(a) == (cat.fill_color, cat.border_color)
    updated = spy(model.sectionUpdated)
    model.set_section_colors(a.id, "#FF8800")
    a = model.section(a.id)
    assert a.fill_color == "#FF8800" and a.border_color and a.border_color != "#FF8800"
    assert model.section_colors(a)[0] == "#FF8800"
    assert len(updated) == 1
    # Editar otros campos conserva el color; quitarlo vuelve al de la categoría.
    model.update_section(a.id, "A", "Alpha 2", a.category_id)
    assert model.section(a.id).fill_color == "#FF8800"
    model.set_section_colors(a.id, None)
    assert model.section(a.id).fill_color is None
    assert model.section_colors(model.section(a.id)) == (cat.fill_color, cat.border_color)


def test_create_from_catalog_assigns_default_category(model):
    if not model.master.available:
        pytest.skip("catálogo empaquetado no generado")
    sec, created = model.create_section_from_catalog("015719")
    assert created and model.category(sec.category_id).name == "Auxiliar / apoyo"
    sec2, _ = model.create_section_from_catalog("31 23 00")
    assert model.category(sec2.category_id).name == "Técnica / constructiva"
    sec3, _ = model.create_section_from_catalog("01 31 19")
    assert model.category(sec3.category_id).name == "Contractual"


def test_category_by_name_creates_with_seed_colors(model):
    model.remove_category(model.category_by_name("Contractual", create=False).id)
    assert model.category_by_name("Contractual", create=False) is None
    cat = model.category_by_name("contractual", create=True)
    assert cat is not None and cat.fill_color == "#FFF2CC"
    other = model.category_by_name("Ambiental", create=True)
    assert other.fill_color == "#EDEDED"


def test_reclassify_from_catalog(model):
    if not model.master.available:
        pytest.skip("catálogo empaquetado no generado")
    otra = model.default_category()
    a = model.add_section("01 57 19", "Protección ambiental", otra.id)   # debería ser Auxiliar
    b = model.add_section("31 23 00", "Excavación", otra.id)             # debería ser Técnica
    c = model.add_section("4.28.33", "Sitio de obra", otra.id)           # fuera del catálogo: no cambia
    model.set_section_colors(b.id, "#FF8800")
    preview = model.reclassify_from_catalog(apply=False)
    assert {s.id for s, _ in preview} == {a.id, b.id}
    applied = model.reclassify_from_catalog(apply=True)
    assert len(applied) == 2
    assert model.category(model.section(a.id).category_id).name == "Auxiliar / apoyo"
    assert model.category(model.section(b.id).category_id).name == "Técnica / constructiva"
    assert model.section(b.id).fill_color == "#FF8800"  # color personalizado conservado
    assert model.section(c.id).category_id == otra.id
    assert model.reclassify_from_catalog(apply=False) == []


def test_save_copy_refuses_same_file_and_backups(tmp_path, qcore_app, master):
    from models.project_model import ProjectModel

    path = tmp_path / "p.specrel"
    m = ProjectModel(master=master)
    m.new_project(path, "CC", "Demo")
    m.add_section("A")
    with pytest.raises(ValueError):
        m.save_copy(path)                          # mismo archivo abierto
    with pytest.raises(ValueError):
        m.save_copy(tmp_path / "p.specrel.bak1")   # respaldo del abierto
    copy = tmp_path / "copia.specrel"
    m.save_copy(copy)
    assert copy.exists() and copy.stat().st_size > 0
    assert m.checkpoint() == path
    m.close()
    m2 = ProjectModel(master=master)
    m2.open_project(copy)
    assert m2.section_by_code("A") is not None
    m2.close()


def test_update_category_signals_sections(model, spy):
    a = model.add_section("A")
    cat = model.default_category()
    updated = spy(model.sectionUpdated)
    cat.fill_color = "#123456"
    model.update_category(cat)
    assert len(updated) == 1 and updated.calls[0][0] == a.id
    assert model.category(cat.id).fill_color == "#123456"


def test_clause_from_catalog_has_no_status_and_fixed_category(model, spy):
    if not model.clauses.available:
        pytest.skip("catálogo de cláusulas no disponible")
    c, created = model.create_section_from_catalog("4.28.61")
    assert created and c.is_clause and c.kind == "clause"
    assert c.title == "PAGO FINAL" and c.status_id is None and c.progress == 0
    cat = model.category(c.category_id)
    assert cat.name == "Cláusula" and cat.fill_color == "#F8CBF0"
    updated = spy(model.sectionUpdated)
    model.set_section_status(c.id, model.default_status().id)
    model.set_section_progress(c.id, 60)
    model.set_section_responsibles(c.id, [model.responsibles()[0].id])
    assert len(updated) == 0
    s = model.section(c.id)
    assert s.status_id is None and s.progress == 0 and model.section_responsibles(c.id) == []
    # Editar el título conserva el tipo y la categoría fija aunque se pida otra.
    other = model.categories()[0]
    model.update_section(c.id, c.code, "Pago final (rev.)", other.id, "nota", status_id=1, progress=90)
    s = model.section(c.id)
    assert s.is_clause and s.category_id == c.category_id and s.status_id is None and s.progress == 0
    assert s.title == "Pago final (rev.)"


def test_free_text_and_colliding_clause_codes(model):
    if not model.clauses.available:
        pytest.skip("catálogo de cláusulas no disponible")
    a, created = model.get_or_create_section("4.28.3.1 Retención de impuestos")
    b, _ = model.get_or_create_section("4.28.31")
    assert created and a.is_clause and b.is_clause and a.id != b.id
    assert a.code_key == "4.28.3.1" and b.code_key == "4.28.31"
    assert model.section_by_code("4.28.3.1").id == a.id and model.section_by_code("4.28.31").id == b.id
    assert model.is_clause_code("4.28.3.1") and not model.is_clause_code("03 30 00")
    assert model.reclassify_from_catalog() == []


def test_sections_are_naturally_ordered(model):
    for code in ("4.28.10", "31 23 00", "4.28.2", "03 30 00"):
        model.add_section(code, kind="clause" if "." in code else "section")
    assert [s.code for s in model.sections()] == ["03 30 00", "31 23 00", "4.28.2", "4.28.10"]


def test_relation_style_persists_keep_and_reset(model, spy, tmp_path):
    a = model.add_section("A", "Alpha")
    b = model.add_section("B", "Beta")
    rel = model.add_relation(a.id, UiKind.REFERENCES, b.id)
    updated = spy(model.relationUpdated)
    styled = model.set_relation_style(rel.id, color="#c00000")
    assert styled.style == ("#C00000", "solid", None) and styled.has_custom_style
    assert len(updated) == 1
    model.set_relation_style(rel.id, color="#C00000")           # sin cambio: sin señal
    assert len(updated) == 1
    model.set_relation_style(rel.id, dash="dash", width=2.5)     # color se conserva (KEEP)
    assert model.relation(rel.id).style == ("#C00000", "dash", 2.5)
    inverted = model.invert_relation(rel.id)                     # invertir conserva el estilo
    assert inverted.style == ("#C00000", "dash", 2.5)
    with pytest.raises(ValueError):
        model.set_relation_style(rel.id, dash="wavy")
    with pytest.raises(ValueError):
        model.set_relation_style(rel.id, width=20)
    with pytest.raises(ValueError):
        model.set_relation_style(rel.id, color="rojo")
    model.reset_relation_style(rel.id)
    assert model.relation(rel.id).style == (None, "solid", None)
    other = model.add_relation(a.id, UiKind.REFERENCES, model.add_section("C").id)
    model.set_relations_style([rel.id, other.id, 9999], dash="dot")
    assert model.relation(rel.id).line_dash == "dot" and model.relation(other.id).line_dash == "dot"


def test_relation_style_survives_reopen(tmp_path, qcore_app):
    from models.project_model import ProjectModel

    path = tmp_path / "estilo.specrel"
    m = ProjectModel()
    m.new_project(path, "CC-1", "Demo")
    a, b = m.add_section("A"), m.add_section("B")
    rel = m.add_relation(a.id, UiKind.REFERENCES, b.id)
    m.set_relation_style(rel.id, color="#548235", dash="dashdot", width=4.0)
    m.close()
    m2 = ProjectModel()
    m2.open_project(path)
    assert m2.relations()[0].style == ("#548235", "dashdot", 4.0)
    m2.close()
