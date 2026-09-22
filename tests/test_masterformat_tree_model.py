from __future__ import annotations

from PyQt6.QtCore import QModelIndex, Qt

from models.master_catalog import MasterCatalog, build_records, write_catalog_sqlite
from models.masterformat_tree_model import (
    MIME_SECTION,
    ROLE_CODE,
    ROLE_CODE_KEY,
    ROLE_IN_PROJECT,
    CatalogTreeFilterProxy,
    MasterFormatTreeModel,
)


def _catalog(tmp_path) -> MasterCatalog:
    records = build_records([
        {"code": "03 00 00", "title_en": "Concrete", "level": 1},
        {"code": "03 30 00", "title_en": "Cast-in-Place Concrete", "level": 2},
        {"code": "03 30 53", "title_en": "Miscellaneous Cast-in-Place Concrete", "level": 3},
        {"code": "31 00 00", "title_en": "Earthwork", "level": 1},
        {"code": "31 23 00", "title_en": "Excavation and Fill", "level": 2},
        {"code": "31 23 16.13", "title_en": "Trenching", "level": 4},  # padre 31 23 16 ausente -> 31 23 00
    ])
    path = tmp_path / "c.sqlite"
    write_catalog_sqlite(records, path)
    return MasterCatalog(path)


def _no_clauses(tmp_path):
    """Catálogo de cláusulas vacío: las pruebas del árbol MasterFormat no dependen del empaquetado."""
    from models.clause_catalog import ClauseCatalog

    return ClauseCatalog(tmp_path / "sin_clausulas.sqlite")


def _clauses(tmp_path):
    from models.clause_catalog import ClauseCatalog, build_clause_records, write_clauses_sqlite

    records, _ = build_clause_records([
        {"code": "4.28.10", "title": "DECLARACIONES", "type": "Cláusula"},
        {"code": "4.28.2", "title": "TRIBUTOS", "type": "Cláusula"},
        {"code": "4.28.3", "title": "RETENCIÓN", "type": "Cláusula"},
        {"code": "4.28.3.1", "title": "Retención: contratistas", "type": "Subcláusula"},
        {"code": "4.28.31", "title": "OTROS CONTRATOS", "type": "Cláusula"},
    ])
    path = tmp_path / "clausulas.sqlite"
    write_clauses_sqlite(records, path)
    return ClauseCatalog(path)


def _codes(model, parent=QModelIndex()) -> list[str]:
    return [model.index(r, 0, parent).data(ROLE_CODE) for r in range(model.rowCount(parent))]


def test_tree_structure_and_missing_parent_fallback(tmp_path, qcore_app):
    model = MasterFormatTreeModel(_catalog(tmp_path), clauses=_no_clauses(tmp_path))
    assert _codes(model) == ["03 00 00", "31 00 00"]
    div03 = model.index(0, 0)
    assert _codes(model, div03) == ["03 30 00"]
    assert _codes(model, model.index(0, 0, div03)) == ["03 30 53"]
    div31 = model.index(1, 0)
    excav = model.index(0, 0, div31)
    assert excav.data(ROLE_CODE) == "31 23 00"
    assert _codes(model, excav) == ["31 23 16.13"]  # colgó del ancestro más cercano existente
    assert model.parent(model.index(0, 0, excav)) == excav


def test_project_keys_role_and_signal(tmp_path, qcore_app):
    model = MasterFormatTreeModel(_catalog(tmp_path), clauses=_no_clauses(tmp_path))
    idx = model.index_for_key("033000")
    assert idx.isValid() and idx.data(ROLE_IN_PROJECT) is False
    changed = []
    model.dataChanged.connect(lambda a, b, roles: changed.append(a.data(ROLE_CODE_KEY)))
    model.set_project_keys({"033000"})
    assert idx.data(ROLE_IN_PROJECT) is True and changed == ["033000"]


def test_recursive_filter_by_text_and_digits(tmp_path, qcore_app):
    model = MasterFormatTreeModel(_catalog(tmp_path), clauses=_no_clauses(tmp_path))
    proxy = CatalogTreeFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_query("trench")
    assert proxy.rowCount() == 1  # división 31 permanece porque un descendiente coincide
    div = proxy.index(0, 0)
    assert div.data(ROLE_CODE) == "31 00 00"
    assert proxy.rowCount(proxy.index(0, 0, div)) == 1
    proxy.set_query("0330 00")
    assert proxy.rowCount() == 1 and proxy.index(0, 0).data(ROLE_CODE) == "03 00 00"
    proxy.set_query("")
    proxy.set_only_project(True)
    assert proxy.rowCount() == 0
    model.set_project_keys({"312300"})
    proxy.invalidateFilter()
    assert proxy.rowCount() == 1 and proxy.index(0, 0).data(ROLE_CODE) == "31 00 00"


def test_category_role_reflects_overrides(tmp_path, qcore_app):
    from models.master_catalog import classify, load_category_rules
    from models.masterformat_tree_model import ROLE_CATEGORY, ROLE_HAS_OVERRIDE

    records = classify(build_records([
        {"code": "01 00 00", "title_en": "General Requirements", "level": 1},
        {"code": "01 40 00", "title_en": "Quality Requirements", "level": 2},
        {"code": "01 45 00", "title_en": "Quality Control", "level": 2},
    ]), load_category_rules())
    path = tmp_path / "c.sqlite"
    write_catalog_sqlite(records, path)
    cat = MasterCatalog(path, overrides_path=tmp_path / "o.json")
    model = MasterFormatTreeModel(cat, clauses=_no_clauses(tmp_path))
    idx = model.index_for_key("014500")
    assert idx.data(ROLE_CATEGORY) == "Auxiliar / apoyo" and idx.data(ROLE_HAS_OVERRIDE) is False
    cat.set_category_override("014500", "Contractual", whole_branch=True)
    model.refresh_all()
    assert idx.data(ROLE_CATEGORY) == "Contractual" and idx.data(ROLE_HAS_OVERRIDE) is True


def test_hidden_entries_filtered_unless_requested(tmp_path, qcore_app):
    from models.masterformat_tree_model import ROLE_HIDDEN

    cat = MasterCatalog(tmp_path / "none.sqlite", overrides_path=tmp_path / "o.json", edits_path=tmp_path / "e.json")
    # catálogo vacío en disco: construir uno pequeño
    records = build_records([
        {"code": "31 00 00", "title_en": "Earthwork", "level": 1},
        {"code": "31 23 00", "title_en": "Excavation and Fill", "level": 2},
    ])
    write_catalog_sqlite(records, tmp_path / "c.sqlite")
    cat.load(tmp_path / "c.sqlite")
    cat.hide("312300")
    model = MasterFormatTreeModel(cat, clauses=_no_clauses(tmp_path))
    proxy = CatalogTreeFilterProxy()
    proxy.setSourceModel(model)
    div = proxy.index(0, 0)
    assert proxy.rowCount(div) == 0
    proxy.set_show_hidden(True)
    assert proxy.rowCount(div) == 1 and proxy.index(0, 0, div).data(ROLE_HIDDEN) is True


def test_mime_data_carries_keys(tmp_path, qcore_app):
    model = MasterFormatTreeModel(_catalog(tmp_path), clauses=_no_clauses(tmp_path))
    idx = model.index_for_key("312300")
    mime = model.mimeData([idx])
    assert mime.hasFormat(MIME_SECTION)
    assert bytes(mime.data(MIME_SECTION)).decode() == "312300"
    assert "31 23 00" in mime.text()
    assert model.flags(idx) & Qt.ItemFlag.ItemIsDragEnabled


def test_clause_group_is_appended_with_natural_order_and_dotted_keys(tmp_path, qcore_app):
    from PyQt6.QtCore import Qt

    from models.masterformat_tree_model import ROLE_CATEGORY, ROLE_LEVEL, ROLE_SOURCE

    model = MasterFormatTreeModel(_catalog(tmp_path), clauses=_clauses(tmp_path))
    assert _codes(model) == ["03 00 00", "31 00 00", "Cláusulas 4.28"]
    group = model.clause_group_index
    assert group.isValid() and group.data(ROLE_SOURCE) == "group"
    assert not (model.flags(group) & Qt.ItemFlag.ItemIsDragEnabled)
    assert _codes(model, group) == ["4.28.2", "4.28.3", "4.28.10", "4.28.31"]     # orden natural
    clause = model.index_for_key("4.28.3")
    assert _codes(model, clause) == ["4.28.3.1"] and clause.data(ROLE_LEVEL) == 3
    sub = model.index_for_key("4.28.3.1")
    assert sub.data(ROLE_LEVEL) == 4 and sub.data(ROLE_CATEGORY) == "Cláusula" and sub.data(ROLE_SOURCE) == "clause"
    assert model.index_for_key("4.28.31").isValid() and model.index_for_key("42831").isValid() is False
    mime = model.mimeData([group, sub, clause])
    assert bytes(mime.data(MIME_SECTION)).decode() == "4.28.3.1;4.28.3"   # el grupo no se arrastra
    proxy = CatalogTreeFilterProxy()
    proxy.setSourceModel(model)
    proxy.set_query("4.28.3")
    shown = [proxy.index(r, 0).data() for r in range(proxy.rowCount())]
    assert shown == ["Cláusulas 4.28"]
    pg = proxy.index(0, 0)
    assert {proxy.index(r, 0, pg).data(ROLE_CODE) for r in range(proxy.rowCount(pg))} == {"4.28.3", "4.28.31"}
