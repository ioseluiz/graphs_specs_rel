from __future__ import annotations

from models.entities import RelationKind, UiKind
from models.project_io import (
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
    assert parse_kind("Referencia mutua ↔") is UiKind.MUTUAL
    assert parse_kind("MUTUA") is UiKind.MUTUAL
    assert parse_kind("<->") is UiKind.MUTUAL
    assert parse_kind("") is UiKind.REFERENCES


def test_template_roundtrip_xlsx(tmp_path, model):
    path = tmp_path / "plantilla.xlsx"
    write_template_xlsx(path)
    tables = read_tables([path])
    assert len(tables.sections) == 4 and len(tables.relations) == 3
    summary = apply_tables(model, tables)
    assert summary.sections_created == 4
    assert summary.relations_created == 3
    assert not summary.errors
    concreto = model.section_by_code("03 30 00")
    assert concreto.title == "Concreto"
    assert model.category(concreto.category_id).name == "Técnica / constructiva"
    seg = model.section_by_code("01 35 29")
    assert seg.fill_color == "#DDEBF7"
    # "01 31 19 ← Es referenciada por 31 23 00" se guarda como 31 23 00 -> 01 31 19
    rel = next(r for r in model.relations() if r.touches(model.section_by_code("01 31 19").id))
    assert model.section(rel.source_id).code == "31 23 00"
    mutual = next(r for r in model.relations() if r.kind is RelationKind.MUTUAL)
    assert {model.section(mutual.source_id).code, model.section(mutual.target_id).code} == {"01 35 29", "03 30 00"}


def test_reimport_is_idempotent_and_updates_titles(tmp_path, model):
    path = tmp_path / "plantilla.xlsx"
    write_template_xlsx(path)
    apply_tables(model, read_tables([path]))
    summary = apply_tables(model, read_tables([path]))
    assert summary.sections_created == 0 and summary.relations_created == 0
    assert summary.relations_duplicated == 3


def test_csv_pair_import_creates_missing_sections_and_categories(tmp_path, model):
    sec, rel = write_template_csv(tmp_path)
    rel.write_text("Sección A;Relación;Sección B\n33 40 00 - Drenaje pluvial;->;31 23 00\n", encoding="utf-8-sig")
    sec.write_text("Número;Descripción;Categoría;Color\n31 23 00;Excavación;Movimiento de tierra;\n", encoding="utf-8-sig")
    summary = apply_tables(model, read_tables([sec, rel]))
    assert summary.categories_created == 1
    assert model.section_by_code("33 40 00").title == "Drenaje pluvial"
    assert summary.relations_created == 1


def test_export_tables_then_import_equivalent(tmp_path, model):
    a = model.add_section("A", "Alpha")
    b = model.add_section("B", "Beta")
    model.add_relation(a.id, UiKind.MUTUAL, b.id)
    model.set_section_colors(a.id, "#FF8800")
    out = tmp_path / "proyecto.xlsx"
    export_tables_xlsx(model, out)
    tables = read_tables([out])
    assert [s["code"] for s in tables.sections] == ["A", "B"]
    assert tables.relations[0]["kind"] == UiKind.MUTUAL.value
    assert tables.sections[0]["color"] == "#FF8800"


def test_import_without_category_uses_catalog_classification(tmp_path, model):
    if not model.master.available:
        import pytest

        pytest.skip("catálogo empaquetado no generado")
    sec, _rel = write_template_csv(tmp_path)
    sec.write_text("Número;Descripción;Categoría;Color\n01 57 19;Protección ambiental;;\n4.28.33;Sitio de obra;;\n",
                   encoding="utf-8-sig")
    apply_tables(model, read_tables([sec]))
    assert model.category(model.section_by_code("01 57 19").category_id).name == "Auxiliar / apoyo"
    assert model.section_by_code("4.28.33").category_id == model.default_category().id


def test_existing_section_without_title_gets_title_from_entry(model):
    model.add_section("03 30 00")
    sec, created = model.get_or_create_section("03 30 00 - Concreto")
    assert not created and sec.title == "Concreto"
