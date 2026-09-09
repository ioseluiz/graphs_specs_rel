from __future__ import annotations

from pathlib import Path

from models.project_bootstrap import classify_paths, is_droppable, project_meta_from, project_path_for
from models.project_io import Tables


def test_project_path_is_next_to_source_with_same_stem():
    src = Path("C:/datos/CC-26-30 relaciones rev2.xlsx")
    assert project_path_for(src) == Path("C:/datos/CC-26-30 relaciones rev2.specrel")
    assert project_path_for(Path("carpeta/relaciones.csv")) == Path("carpeta/relaciones.specrel")


def test_project_meta_prefers_sheet_and_falls_back_to_file_name():
    src = Path("C:/datos/CC-26-30 relaciones rev2.xlsx")
    assert project_meta_from(Tables(project={"code": "CC-26-30", "name": "Esclusas"}), src) == ("CC-26-30", "Esclusas")
    assert project_meta_from(Tables(project={"name": "Solo nombre"}), src) == ("", "Solo nombre")
    assert project_meta_from(Tables(), src) == ("CC-26-30 relaciones rev2", "")


def test_classify_paths_and_droppable():
    projects, tables, others = classify_paths(["a.specrel", "b.XLSX", "c.csv", "d.txt", Path("e.xlsm")])
    assert [p.name for p in projects] == ["a.specrel"]
    assert [p.name for p in tables] == ["b.XLSX", "c.csv", "e.xlsm"]
    assert [p.name for p in others] == ["d.txt"]
    assert is_droppable("x.specrel") and is_droppable("x.csv") and not is_droppable("x.pdf")
