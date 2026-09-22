from __future__ import annotations

from models.entities import RelationKind, UiKind
from models.project_io import (
    KIND_BOTH,
    apply_tables,
    export_tables_xlsx,
    parse_kind,
    read_tables,
    write_template_csv,
    write_template_xlsx,
)
from models.relation_normalizer import split_code_title


def test_split_code_title_with_dash_separators():
    assert split_code_title("03 30 00 - Concreto") == ("03 30 00", "Concreto")
    assert split_code_title("03 30 00 – Concreto") == ("03 30 00", "Concreto")
    assert split_code_title("03 30 00: Concreto") == ("03 30 00", "Concreto")
    assert split_code_title("4.28.33 | Sitio de obra") == ("4.28.33", "Sitio de obra")


def test_parse_kind_variants():
    assert parse_kind("Hace referencia a →") is UiKind.REFERENCES
    assert parse_kind("->") is UiKind.REFERENCES
    assert parse_kind("← Es referenciada por") is UiKind.REFERENCED_BY
    assert parse_kind("<-") is UiKind.REFERENCED_BY
    # Texto de la plantilla 0.2.x: hoy equivale a dos filas (A → B y B → A)
    assert parse_kind("Referencia mutua ↔") == KIND_BOTH
    assert parse_kind("MUTUA") == KIND_BOTH
    assert parse_kind("<->") == KIND_BOTH
    assert parse_kind("") is UiKind.REFERENCES


def _codes(model, rel) -> tuple[str, str]:
    return model.section(rel.source_id).code, model.section(rel.target_id).code


def test_template_roundtrip_xlsx(tmp_path, model):
    path = tmp_path / "plantilla.xlsx"
    write_template_xlsx(path)
    tables = read_tables([path])
    assert len(tables.sections) == 5 and len(tables.relations) == 5
    assert tables.project == {"code": "CC-26-01", "name": "Proyecto de ejemplo"}
    summary = apply_tables(model, tables)
    assert summary.sections_created == 5
    assert summary.relations_created == 5
    assert not summary.errors and not summary.skipped
    clause = model.section_by_code("4.28.61")
    assert clause.is_clause and clause.status_id is None and model.category(clause.category_id).name == "Cláusula"
    concreto = model.section_by_code("03 30 00")
    assert concreto.title == "Concreto"
    assert model.category(concreto.category_id).name == "Técnica / constructiva"
    seg = model.section_by_code("01 35 29")
    assert seg.fill_color == "#DDEBF7"
    pairs = {_codes(model, r) for r in model.relations()}
    # "01 31 19 ← Es referenciada por 31 23 00" se guarda como 31 23 00 -> 01 31 19
    assert ("31 23 00", "01 31 19") in pairs
    # El ejemplo trae las dos direcciones entre 01 35 29 y 03 30 00: dos flechas distintas
    assert ("01 35 29", "03 30 00") in pairs and ("03 30 00", "01 35 29") in pairs
    assert all(r.kind is RelationKind.REF for r in model.relations())
    noted = next(r for r in model.relations() if _codes(model, r) == ("31 23 00", "01 31 19"))
    assert noted.notes == "Ver artículo 3.2"


def test_reimport_is_idempotent_and_lists_skipped_rows(tmp_path, model):
    path = tmp_path / "plantilla.xlsx"
    write_template_xlsx(path)
    apply_tables(model, read_tables([path]))
    summary = apply_tables(model, read_tables([path]))
    assert summary.sections_created == 0 and summary.relations_created == 0
    assert summary.relations_duplicated == 5
    assert len(summary.skipped) == 5
    assert all("ya existía en el proyecto" in line for line in summary.skipped)
    assert "Filas omitidas (5)" in summary.text()


def test_opposite_directions_are_two_relations_and_exact_repeats_are_reported(tmp_path, model):
    """Caso real del cliente: 01 13 00 → 31 33 23 y 31 33 23 → 01 13 00 (repetida 4 veces)."""
    sec, rel = write_template_csv(tmp_path)
    rel.write_text(
        "Sección A;Relación;Sección B;Observaciones\n"
        "01 13 00;Hace referencia a →;31 33 23;\n"
        "31 33 23;Hace referencia a →;01 13 00;\n"
        "31 33 23;Hace referencia a →;01 13 00;Esta línea no la cargaba\n"
        "31 33 23;Hace referencia a →;01 13 00;\n"
        "31 33 23;Hace referencia a →;01 11 00;\n",
        encoding="utf-8-sig")
    summary = apply_tables(model, read_tables([rel]))
    assert summary.relations_created == 3
    assert summary.relations_duplicated == 2
    pairs = {_codes(model, r) for r in model.relations()}
    assert ("01 13 00", "31 33 23") in pairs and ("31 33 23", "01 13 00") in pairs
    assert summary.skipped == [
        "Relaciones fila 4: 31 33 23 → 01 13 00 omitida (repite la fila 3).",
        "Relaciones fila 5: 31 33 23 → 01 13 00 omitida (repite la fila 3).",
    ]
    # La observación de una fila repetida se conserva si la flecha no tenía nota
    back = next(r for r in model.relations() if _codes(model, r) == ("31 33 23", "01 13 00"))
    assert back.notes == "Esta línea no la cargaba"


def test_legacy_mutual_text_creates_two_arrows(tmp_path, model):
    sec, rel = write_template_csv(tmp_path)
    rel.write_text("Sección A;Relación;Sección B\nA;Referencia mutua ↔;B\n", encoding="utf-8-sig")
    summary = apply_tables(model, read_tables([rel]))
    assert summary.relations_created == 2
    assert {_codes(model, r) for r in model.relations()} == {("A", "B"), ("B", "A")}


def test_csv_pair_import_creates_missing_sections_and_categories(tmp_path, model):
    sec, rel = write_template_csv(tmp_path)
    rel.write_text("Sección A;Relación;Sección B\n33 40 00 - Drenaje pluvial;->;31 23 00\n", encoding="utf-8-sig")
    sec.write_text("Número;Descripción;Categoría;Color\n31 23 00;Excavación;Movimiento de tierra;\n", encoding="utf-8-sig")
    tables = read_tables([sec, rel, tmp_path / "proyecto.csv"])
    assert tables.project == {"code": "CC-26-01", "name": "Proyecto de ejemplo"}
    summary = apply_tables(model, tables)
    assert summary.categories_created == 1
    assert model.section_by_code("33 40 00").title == "Drenaje pluvial"
    assert summary.relations_created == 1


def test_export_tables_then_import_equivalent(tmp_path, model):
    a = model.add_section("A", "Alpha")
    b = model.add_section("B", "Beta")
    model.add_relation(a.id, UiKind.REFERENCES, b.id, notes="nota")
    model.add_relation(b.id, UiKind.REFERENCES, a.id)
    model.set_section_colors(a.id, "#FF8800")
    out = tmp_path / "proyecto.xlsx"
    export_tables_xlsx(model, out)
    tables = read_tables([out])
    assert [s["code"] for s in tables.sections] == ["A", "B"]
    assert [(r["a"], r["kind"], r["b"], r["notes"]) for r in tables.relations] == [
        ("A - Alpha", UiKind.REFERENCES.value, "B - Beta", "nota"),
        ("B - Beta", UiKind.REFERENCES.value, "A - Alpha", ""),
    ]
    assert tables.sections[0]["color"] == "#FF8800"
    assert tables.project["code"] == model.meta().code


def test_import_without_category_uses_catalog_classification(tmp_path, model):
    if not model.master.available:
        import pytest

        pytest.skip("catálogo empaquetado no generado")
    sec, _rel = write_template_csv(tmp_path)
    sec.write_text("Número;Descripción;Categoría;Color\n01 57 19;Protección ambiental;;\n4.28.33;Sitio de obra;;\n",
                   encoding="utf-8-sig")
    apply_tables(model, read_tables([sec]))
    assert model.category(model.section_by_code("01 57 19").category_id).name == "Auxiliar / apoyo"
    clause = model.section_by_code("4.28.33")   # numeración de cláusula: nodo cláusula, no «Otra»
    assert clause.is_clause and model.category(clause.category_id).name == "Cláusula"


def test_existing_section_without_title_gets_title_from_entry(model):
    model.add_section("03 30 00")
    sec, created = model.get_or_create_section("03 30 00 - Concreto")
    assert not created and sec.title == "Concreto"


def test_clause_row_ignores_status_progress_and_responsibles(tmp_path, model):
    if not model.clauses.available:
        import pytest

        pytest.skip("catálogo de cláusulas no disponible")
    sec, _rel = write_template_csv(tmp_path)
    sec.write_text("Número;Descripción;Categoría;Color;Estatus;Avance;Responsables;Observaciones\n"
                   "4.28.61;;;;Suspendida;50;INIA;Nota de la cláusula\n"
                   "4.28.99.1;Texto libre de cláusula;Cláusula;;;;;\n",
                   encoding="utf-8-sig")
    summary = apply_tables(model, read_tables([sec]))
    assert summary.sections_created == 2 and summary.statuses_created == 0 and summary.responsibles_created == 0
    assert any("es una cláusula; se ignoran Estatus, Avance, Responsables" in e for e in summary.errors)
    c = model.section_by_code("4.28.61")
    assert c.is_clause and c.title == "PAGO FINAL" and c.notes == "Nota de la cláusula" and c.status_id is None
    free = model.section_by_code("4.28.99.1")
    assert free.is_clause and free.title == "Texto libre de cláusula"   # Categoría «Cláusula» sin catálogo
    out = tmp_path / "tablas.xlsx"
    export_tables_xlsx(model, out)
    rows = {r["code"]: r for r in read_tables([out]).sections}
    assert rows["4.28.61"]["category"] == "Cláusula" and rows["4.28.61"]["progress"] == ""
