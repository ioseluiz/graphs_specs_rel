"""Catálogo de cláusulas del pliego: construcción desde Excel, claves con puntos, jerarquía y reemplazo."""
from __future__ import annotations

from pathlib import Path

import pytest

from config.settings import CLAUSE_CATALOG_PATH
from models.clause_catalog import (
    ClauseCatalog,
    ClauseCatalogError,
    build_clause_records,
    clean_clause_title,
    clauses_root_label,
    load_clause_rows,
    write_clauses_sqlite,
)

ROWS = [
    ("Numeración", "Título", "Tipo"),
    ("4.28.3", "RETENCIÓN DE IMPUESTOS", "Cláusula"),
    ("4.28.3.1", "Retención De Impuestos: Los contratistas…", "Subcláusula"),
    ("4.28.31", "OTROS CONTRATOS", "Cláusula"),
    ("4.28.61", "50PAGO FINAL", "Cláusula"),
    ("4.28.61.1", "50Pago Final: El pago final constituye", "Subcláusula"),
    ("4.28.61", "50PAGO FINAL (repetida)", "Cláusula"),
    (None, None, None),
    ("4.28.10", "DECLARACIONES", "Cláusula"),
    ("4.28.2", "TRIBUTOS", "Cláusula"),
]


def _xlsx(tmp_path: Path, rows=ROWS) -> Path:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(list(r))
    path = tmp_path / "clausulas.xlsx"
    wb.save(path)
    return path


def test_clean_title_removes_page_number_prefix():
    assert clean_clause_title("50PAGO FINAL") == ("PAGO FINAL", True)
    assert clean_clause_title("37Protección De Recursos") == ("Protección De Recursos", True)
    assert clean_clause_title("  SALARIO   MÍNIMO ") == ("SALARIO MÍNIMO", False)
    assert clean_clause_title("2 REQUISITOS") == ("2 REQUISITOS", False)   # número seguido de espacio: se respeta


def test_build_records_keeps_dotted_keys_and_hierarchy(tmp_path):
    rows = load_clause_rows(_xlsx(tmp_path))
    records, stats = build_clause_records(rows)
    by_code = {r.code: r for r in records}
    assert by_code["4.28.3.1"].code_key == "4.28.3.1" and by_code["4.28.31"].code_key == "4.28.31"
    assert by_code["4.28.3.1"].parent_key == "4.28.3" and by_code["4.28.3.1"].level == 2
    assert by_code["4.28.61"].title == "PAGO FINAL (repetida)"   # gana la última fila
    assert by_code["4.28.61.1"].title.startswith("Pago Final:")
    assert stats["duplicates"] == 1 and stats["cleaned_titles"] == 3 and stats["skipped"] == 0
    assert [r.code for r in records if r.level == 1] == ["4.28.2", "4.28.3", "4.28.10", "4.28.31", "4.28.61"]
    assert clauses_root_label(records) == "Cláusulas 4.28"


def test_catalog_roundtrip_and_queries(tmp_path):
    records, _ = build_clause_records(load_clause_rows(_xlsx(tmp_path)))
    target = tmp_path / "c.sqlite"
    assert write_clauses_sqlite(records, target) == 7
    cat = ClauseCatalog(target)
    assert cat.available and len(cat) == 7 and cat.root_label == "Cláusulas 4.28"
    assert [r.code for r in cat.roots()] == ["4.28.2", "4.28.3", "4.28.10", "4.28.31", "4.28.61"]
    assert [r.code for r in cat.children("4.28.3")] == ["4.28.3.1"]
    assert cat.get("4.28.3.1").title.startswith("Retención") and cat.get(" 4.28.61 ").title.endswith("(repetida)")
    assert cat.get("4.28.99") is None
    assert [r.code for r in cat.search("pago")] == ["4.28.61", "4.28.61.1"]
    assert cat.get("4.28.61").kind_label == "Cláusula" and cat.get("4.28.61.1").kind_label == "Subcláusula"


def test_build_user_catalog_file_and_reset(tmp_path, monkeypatch):
    import models.clause_catalog as mod

    user_copy = tmp_path / "user" / "clausulas_user.sqlite"
    monkeypatch.setattr(mod, "user_clause_catalog_path", lambda: user_copy)
    target, count = ClauseCatalog.build_user_catalog_file(_xlsx(tmp_path))
    assert target == user_copy and count == 7 and user_copy.exists()
    cat = ClauseCatalog()
    assert cat.is_user_copy and len(cat) == 7
    cat.reset_to_bundled()
    assert not user_copy.exists() and not cat.is_user_copy
    with pytest.raises(ClauseCatalogError):
        ClauseCatalog.build_user_catalog_file(_xlsx(tmp_path, rows=ROWS[:3]), tmp_path / "few.sqlite")


def test_load_rows_requires_numbering_column(tmp_path):
    from openpyxl import Workbook

    wb = Workbook()
    wb.active.append(["Descripción", "Otra cosa"])
    wb.active.append(["a", "b"])
    path = tmp_path / "sin.xlsx"
    wb.save(path)
    with pytest.raises(ClauseCatalogError):
        load_clause_rows(path)


def test_bundled_catalog_from_client_excel():
    if not CLAUSE_CATALOG_PATH.exists():
        pytest.skip("catálogo de cláusulas empaquetado no generado")
    cat = ClauseCatalog()
    assert len(cat) == 458 and len(cat.roots()) == 99
    assert cat.get("4.28.61").title == "PAGO FINAL"
    assert cat.get("4.28.3.1") is not None and cat.get("4.28.31") is not None
    assert cat.get("4.28.3.1").code_key != cat.get("4.28.31").code_key
    assert not any(r.title[:1].isdigit() and r.title[1:2].isalpha() for r in cat.all())
