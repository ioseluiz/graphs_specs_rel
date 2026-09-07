from __future__ import annotations

import sqlite3

from models.catalog_importer import (
    ColumnMapping,
    import_for,
    import_masterformat_db,
    preview_csv,
    suggest_mapping,
)


def test_suggest_mapping_spanish_headers():
    m = suggest_mapping(["Número", "Descripción", "Categoría"])
    assert m.code == "Número" and m.title == "Descripción" and m.category == "Categoría"


def test_csv_preview_and_import(tmp_path):
    csv_path = tmp_path / "cat.csv"
    csv_path.write_text(
        "codigo;titulo;tipo\n31 23 00;Excavación;Técnica\n312300;Duplicada;Técnica\n01 31 19;Conferencia inicial;\n",
        encoding="utf-8",
    )
    preview = preview_csv(csv_path)
    assert preview.headers == ["codigo", "titulo", "tipo"]
    entries = import_for(csv_path, preview.suggested)
    assert len(entries) == 2  # deduplicado por code_key
    by_key = {e.code_key: e for e in entries}
    assert by_key["312300"].title == "Duplicada"
    assert by_key["013119"].category_name is None


def test_xlsx_import(tmp_path):
    from openpyxl import Workbook

    path = tmp_path / "cat.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.append(["Sección", "Título"])
    ws.append(["33 40 00", "Drenaje pluvial"])
    ws.append([None, None])
    ws.append(["31 05 19", "Geosintéticos"])
    wb.save(path)
    entries = import_for(path, ColumnMapping("Sección", "Título"))
    assert {e.code for e in entries} == {"33 40 00", "31 05 19"}


def test_masterformat_db(tmp_path):
    path = tmp_path / "mf.db"
    conn = sqlite3.connect(path)
    conn.execute("CREATE TABLE master_format (codigo_display TEXT, nombre TEXT, nivel INTEGER)")
    conn.executemany(
        "INSERT INTO master_format VALUES (?, ?, ?)",
        [("31 00 00", "Earthwork", 1), ("31 23 00", "Excavation and Fill", 2), ("31 23 16.13", "Trenching", 4)],
    )
    conn.commit()
    conn.close()
    entries = import_masterformat_db(path, max_level=3)
    assert {e.code for e in entries} == {"31 00 00", "31 23 00"}
