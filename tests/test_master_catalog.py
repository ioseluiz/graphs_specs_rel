from __future__ import annotations

import pytest

from models.master_catalog import (
    REVIEW_TITLE,
    MasterCatalog,
    build_records,
    clean_title,
    derive_parent_key,
    infer_level,
    normalize_code,
    write_catalog_sqlite,
)


def test_normalize_code_fixes_spacing():
    assert normalize_code("0330 00") == "03 30 00"
    assert normalize_code("033000") == "03 30 00"
    assert normalize_code("03-30-00") == "03 30 00"
    assert normalize_code("02 03 01.19") == "02 03 01.19"
    assert normalize_code("4.28.33") == "4.28.33"  # fuera de MasterFormat: se respeta


def test_infer_level_and_parent():
    assert infer_level("00 00 00") == 1 and derive_parent_key("00 00 00", 1) is None
    assert infer_level("00 10 00") == 2 and derive_parent_key("00 10 00", 2) == "000000"
    assert infer_level("00 01 01") == 3 and derive_parent_key("00 01 01", 3) == "000100"
    assert infer_level("02 03 01.19") == 4 and derive_parent_key("02 03 01.19", 4) == "020301"


def test_clean_title_rules():
    assert clean_title("Excavation and Fill") == ("Excavation and Fill", "ok")
    assert clean_title("Mothballing Period Structures\n") == ("Mothballing Period Structures", "ok")
    assert clean_title("Seals Page 05 05 53 metal fastenings") == ("Seals Page", "ok")
    assert clean_title("Electrical Power Generation Voltage Test Equipment 537 Keyword Index convenient")[1] == "ok"
    # Texto de índice (empieza en minúscula): se marca para verificar en lugar de inventar un título.
    assert clean_title("transit mixing, concrete 02 81 00 hazardous materials") == (REVIEW_TITLE, "review")
    assert clean_title("") == (REVIEW_TITLE, "review")
    assert clean_title("x" * 120) == (REVIEW_TITLE, "review")


def test_build_records_dedupes_and_prefers_quality():
    rows = [
        {"code": "12 36 61.13", "title_en": "Cultured Marble Countertops", "level": 4},
        {"code": "12 36 61.16", "title_en": "Solid Surfacing Countertops", "level": 4},
        {"code": "03 30 00", "title_en": "", "level": 2},
        {"code": "03 30 00", "title_en": "Cast-in-Place Concrete", "level": 2},
        {"code": "", "title_en": "basura"},
    ]
    records = build_records(rows)
    keys = [r.code_key for r in records]
    assert keys == ["033000", "12366113", "12366116"]
    concreto = records[0]
    assert concreto.title_en == "Cast-in-Place Concrete" and concreto.quality == "ok"
    assert concreto.division == "03" and concreto.parent_key == "030000"


def test_write_and_query_catalog(tmp_path):
    records = build_records([
        {"code": "31 00 00", "title_en": "Earthwork", "level": 1},
        {"code": "31 20 00", "title_en": "Earth Moving", "level": 2},
        {"code": "31 23 00", "title_en": "Excavation and Fill", "title_es": "Excavación y relleno", "level": 2},
        {"code": "31 23 16", "title_en": "Excavation", "level": 3},
    ])
    path = tmp_path / "cat.sqlite"
    assert write_catalog_sqlite(records, path, {"edition": "test"}) == 4
    cat = MasterCatalog(path)
    assert len(cat) == 4 and cat.meta["edition"] == "test"
    assert [d.code for d in cat.divisions()] == ["31 00 00"]
    assert [c.code for c in cat.children("310000")] == ["31 20 00", "31 23 00"]
    assert cat.get("0330 00") is None
    assert cat.get("3123 00").title == "Excavación y relleno"
    assert cat.suggest_for_code("312300").code == "31 23 00"
    found = cat.search("31 exc")
    assert {r.code for r in found} == {"31 23 00", "31 23 16"}
    assert cat.search("relleno")[0].code == "31 23 00"


def test_title_overrides_fix_review_titles(tmp_path):
    from models.master_catalog import apply_title_overrides, load_title_overrides

    path = tmp_path / "ov.csv"
    path.write_text("code;title_en\n0330 00;Cast-in-Place Concrete\n", encoding="utf-8")
    overrides = load_title_overrides(path)
    assert overrides == {"033000": "Cast-in-Place Concrete"}
    records = build_records([{"code": "03 30 00", "title_en": "transit mixing, concrete 02 81 00", "level": 2}])
    assert records[0].quality == "review"
    fixed = apply_title_overrides(records, overrides)
    assert fixed[0].title_en == "Cast-in-Place Concrete" and fixed[0].quality == "ok"


def _rules():
    from models.master_catalog import DEFAULT_RULES_PATH, load_category_rules

    rules = load_category_rules(DEFAULT_RULES_PATH)
    assert rules, "scripts/category_rules.csv debe existir"
    return rules


@pytest.mark.parametrize("code,expected", [
    ("00 73 00", "Contractual"),
    ("01 13 00", "Contractual"),
    ("01 31 19", "Contractual"),
    ("01 35 29", "Auxiliar / apoyo"),
    ("01 50 00", "Auxiliar / apoyo"),
    ("01 57 20", "Auxiliar / apoyo"),
    ("01 81 00", "Técnica / constructiva"),
    ("02 32 19", "Auxiliar / apoyo"),
    ("02 41 00", "Técnica / constructiva"),
    ("03 30 00", "Técnica / constructiva"),
    ("26 08 00", "Auxiliar / apoyo"),
    ("31 23 00", "Técnica / constructiva"),
])
def test_category_rules(code, expected):
    from models.master_catalog import match_category
    from models.relation_normalizer import code_key

    assert match_category(code_key(code), _rules()) == expected


def test_longest_prefix_and_wildcard():
    from models.master_catalog import match_category

    rules = [("", "T"), ("01", "C"), ("0135", "A"), ("??06", "S")]
    assert match_category("013529", rules) == "A"
    assert match_category("013119", rules) == "C"
    assert match_category("330600", rules) == "S"
    assert match_category("312300", rules) == "T"


def test_user_overrides_precedence(tmp_path):
    from models.master_catalog import classify

    records = classify(build_records([
        {"code": "01 40 00", "title_en": "Quality Requirements", "level": 2},
        {"code": "01 45 00", "title_en": "Quality Control", "level": 2},
        {"code": "01 45 16", "title_en": "Contractor Quality Control", "level": 3},
    ]), _rules())
    path = tmp_path / "cat.sqlite"
    write_catalog_sqlite(records, path)
    overrides = tmp_path / "overrides.json"
    cat = MasterCatalog(path, overrides_path=overrides)
    assert cat.effective_category("01 45 16") == "Auxiliar / apoyo"
    cat.set_category_override("014500", "Contractual", whole_branch=True)  # rama 0145
    assert cat.effective_category("01 45 16") == "Contractual"
    assert cat.effective_category("01 40 00") == "Auxiliar / apoyo"
    cat.set_category_override("014516", "Técnica / constructiva", whole_branch=False)
    assert cat.effective_category("01 45 16") == "Técnica / constructiva"  # código > prefijo
    assert cat.has_override("014516") and cat.override_count == 2
    # Persistencia entre instancias
    again = MasterCatalog(path, overrides_path=overrides)
    assert again.effective_category("01 45 16") == "Técnica / constructiva"
    again.clear_category_override("014516")
    assert again.effective_category("01 45 16") == "Contractual"
    again.clear_category_overrides()
    assert again.effective_category("01 45 16") == "Auxiliar / apoyo" and again.override_count == 0


def test_catalog_without_category_column_is_classified_on_load(tmp_path):
    import sqlite3

    path = tmp_path / "old.sqlite"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE catalog (code_key TEXT PRIMARY KEY, code TEXT, title_en TEXT, title_es TEXT,
                              level INTEGER, parent_key TEXT, division TEXT, quality TEXT);
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO catalog VALUES ('013529','01 35 29','Health, Safety, and Emergency Response Procedures',
                                    NULL, 3, '013500', '01', 'ok');
    """)
    conn.commit()
    conn.close()
    cat = MasterCatalog(path, overrides_path=tmp_path / "o.json")
    assert cat.get("01 35 29").category == "Auxiliar / apoyo"


def _small_catalog(tmp_path) -> MasterCatalog:
    from models.master_catalog import classify

    records = classify(build_records([
        {"code": "03 00 00", "title_en": "Concrete", "level": 1},
        {"code": "03 30 00", "title_en": "Cast-in-Place Concrete", "level": 2},
        {"code": "03 30 53", "title_en": "Miscellaneous Cast-in-Place Concrete", "level": 3},
    ]), _rules())
    path = tmp_path / "c.sqlite"
    write_catalog_sqlite(records, path)
    return MasterCatalog(path, overrides_path=tmp_path / "o.json", edits_path=tmp_path / "e.json")


def test_user_edits_title_add_hide_restore(tmp_path):
    from models.master_catalog import MasterCatalogError

    cat = _small_catalog(tmp_path)
    # Editar título (con español)
    cat.set_title("033000", "Cast-in-Place Concrete", "Concreto vaciado en sitio")
    assert cat.get("03 30 00").title == "Concreto vaciado en sitio" and cat.is_title_edited("033000")
    # Agregar sección hija: padre derivado del código, clasificación por reglas
    rec = cat.add_section("03 30 16", "Concreto para fundaciones")
    assert rec.parent_key == "033000" and rec.level == 3 and rec.category == "Técnica / constructiva"
    assert [c.code for c in cat.children("033000")] == ["03 30 16", "03 30 53"]
    with pytest.raises(MasterCatalogError):
        cat.add_section("03 30 16", "duplicada")
    # Ocultar una del catálogo y una agregada (esta se elimina)
    cat.hide("033053")
    assert cat.get("03 30 53") is None and cat.get("03 30 53", include_hidden=True) is not None
    assert cat.is_hidden("033053") and len(cat.all()) == 3 and len(cat.all(include_hidden=True)) == 4
    cat.hide("033016")
    assert cat.get("03 30 16", include_hidden=True) is None
    assert cat.edit_count == 2  # título editado + oculta
    # Persistencia y restauración
    again = MasterCatalog(tmp_path / "c.sqlite", overrides_path=tmp_path / "o.json", edits_path=tmp_path / "e.json")
    assert again.is_hidden("033053") and again.get("03 30 00").title_es == "Concreto vaciado en sitio"
    again.unhide("033053")
    assert again.get("03 30 53") is not None
    again.restore_entry("033000")
    assert again.get("03 30 00").title_es is None and not again.is_title_edited("033000")
    again.clear_edits()
    assert again.edit_count == 0


def test_set_title_same_as_original_removes_edit(tmp_path):
    cat = _small_catalog(tmp_path)
    cat.set_title("033000", "Otro", None)
    assert cat.is_title_edited("033000")
    cat.set_title("033000", "Cast-in-Place Concrete", None)
    assert not cat.is_title_edited("033000")


def test_export_xlsx_roundtrip(tmp_path):
    from models.master_catalog import load_source_rows

    cat = _small_catalog(tmp_path)
    cat.set_title("033000", "Cast-in-Place Concrete", "Concreto")
    out = tmp_path / "cat.xlsx"
    assert cat.export_xlsx(out) == 3
    rows = load_source_rows(out)
    by_code = {r["code"]: r for r in rows}
    assert by_code["03 30 00"]["title_es"] == "Concreto"
    assert by_code["03 30 00"]["category"] == "Técnica / constructiva"
    # El Excel exportado se puede volver a cargar como catálogo
    records = build_records(rows)
    assert len(records) == 3 and records[1].title_es == "Concreto"


def test_bundled_catalog_is_present_and_clean():
    cat = MasterCatalog()
    if not cat.available:
        pytest.skip("catálogo empaquetado no generado (ejecute scripts/build_master_catalog.py)")
    assert len(cat) > 8000
    assert cat.get("31 23 00").title_en == "Excavation and Fill"
    assert cat.get("33 40 00").title_en == "Stormwater Utilities"
    assert cat.get("03 30 00").title_en == "Cast-in-Place Concrete"  # corregido por title_overrides.csv
    from collections import Counter

    counts = Counter(r.category for r in cat.all())
    assert set(counts) == {"Técnica / constructiva", "Contractual", "Auxiliar / apoyo"}
    assert counts.most_common(1)[0][0] == "Técnica / constructiva"
    assert cat.get("01 31 19").category == "Contractual"
    assert cat.get("01 57 19").category == "Auxiliar / apoyo"  # Temporary Environmental Controls
    review = [r for r in cat.all() if r.quality == "review"]
    assert len(review) < 200
    # Cada sección de nivel 2..4 tiene padre existente (jerarquía derivada del código).
    orphans = [r for r in cat.all() if r.level > 1 and r.parent_key not in {x.code_key for x in cat.all()}]
    assert len(orphans) < len(cat) * 0.05
