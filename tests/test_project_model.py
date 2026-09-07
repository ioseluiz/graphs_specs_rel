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


def test_duplicate_relation_reports_existing(model):
    a = model.add_section("A")
    b = model.add_section("B")
    rel = model.add_relation(a.id, UiKind.REFERENCES, b.id)
    with pytest.raises(DuplicateRelationError) as exc:
        model.add_relation(b.id, UiKind.REFERENCES, a.id)
    assert exc.value.existing.id == rel.id
    with pytest.raises(SelfRelationError):
        model.add_relation(a.id, UiKind.REFERENCES, a.id)


def test_make_mutual_reorders(model, spy):
    a = model.add_section("A")
    b = model.add_section("B")
    rel = model.add_relation(b.id, UiKind.REFERENCES, a.id)  # b -> a (source > target)
    updated = spy(model.relationUpdated)
    new = model.make_mutual(rel.id)
    assert new.kind is RelationKind.MUTUAL
    assert new.source_id < new.target_id
    assert len(updated) == 1
    assert model.graph.G.has_edge(a.id, b.id) and model.graph.G.has_edge(b.id, a.id)


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
    m.add_relation(a.id, UiKind.MUTUAL, b.id)
    m.move_node(a.id, 42, 24)
    m.close()

    m2 = ProjectModel()
    m2.open_project(path)
    assert m2.meta().header == "CC-1 | Demo"
    assert [s.code for s in m2.sections()] == ["A", "B"]
    assert m2.relations()[0].kind is RelationKind.MUTUAL
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
