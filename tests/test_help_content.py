from __future__ import annotations

import json

from models.help_content import HELP_DIR, HelpContent

EXPECTED = ["inicio", "secciones", "clausulas", "relaciones", "mapa", "estatus", "categorias", "analisis",
            "vista3d", "exportar", "atajos", "faq"]


def test_bundled_manual_loads_all_topics():
    content = HelpContent()
    assert content.available and content.error is None
    assert [t.id for t in content.topics] == EXPECTED
    assert all(t.markdown.lstrip().startswith("# ") for t in content.topics)


def test_manual_images_exist():
    content = HelpContent()
    assert content.missing_images() == [], "imágenes referenciadas que no existen (ejecute scripts/help_screenshots.py)"


def test_search_finds_connect_in_map_topic():
    content = HelpContent()
    ids = [t.id for t in content.search("conectar")]
    assert "mapa" in ids and "faq" in ids
    assert [t.id for t in content.search("referencia mutua")][0] in ("relaciones", "faq", "mapa")
    assert content.search("") == content.topics
    assert content.search("palabra_inexistente_xyz") == []


def test_missing_folder_is_tolerated(tmp_path):
    content = HelpContent(tmp_path / "nada")
    assert not content.available and content.error


def test_missing_topic_file_shows_placeholder(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps({"topics": [{"id": "x", "title": "X", "file": "x.md"}]}),
                                         encoding="utf-8")
    content = HelpContent(tmp_path)
    assert content.available and "aún no tiene contenido" in content.topic("x").markdown


def test_help_dir_is_inside_assets():
    assert HELP_DIR.name == "help" and HELP_DIR.parent.name == "assets"
