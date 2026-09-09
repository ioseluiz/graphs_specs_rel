"""Crear un proyecto directamente desde archivos de tablas (Excel/CSV) o abrir lo que el usuario arrastre.

Funciones puras (sin Qt) que deciden dónde va el archivo `.specrel` y con qué código/nombre nace el proyecto.
"""
from __future__ import annotations

from pathlib import Path

from config.settings import PROJECT_EXTENSION
from models.project_io import Tables

TABLE_SUFFIXES = frozenset({".xlsx", ".xlsm", ".csv"})


def project_path_for(source: Path) -> Path:
    """`.../CC-26-30 relaciones rev2.xlsx` -> `.../CC-26-30 relaciones rev2.specrel` (misma carpeta)."""
    return source.with_suffix(PROJECT_EXTENSION)


def project_meta_from(tables: Tables, source: Path) -> tuple[str, str]:
    """(código, nombre) del proyecto nuevo: hoja «Proyecto» si existe; si no, el nombre del archivo."""
    code = (tables.project.get("code") or "").strip()
    name = (tables.project.get("name") or "").strip()
    if not code and not name:
        return source.stem.strip(), ""
    return code, name


def classify_paths(paths: list[str | Path]) -> tuple[list[Path], list[Path], list[Path]]:
    """Separa rutas en (proyectos .specrel, tablas Excel/CSV, otros)."""
    projects: list[Path] = []
    tables: list[Path] = []
    others: list[Path] = []
    for raw in paths:
        p = Path(raw)
        suffix = p.suffix.lower()
        if suffix == PROJECT_EXTENSION:
            projects.append(p)
        elif suffix in TABLE_SUFFIXES:
            tables.append(p)
        else:
            others.append(p)
    return projects, tables, others


def is_droppable(path: str | Path) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix == PROJECT_EXTENSION or suffix in TABLE_SUFFIXES
