"""Normalización de relaciones entre la forma de la interfaz y la persistida.

La base de datos guarda una única relación por par DIRIGIDO de secciones:
- "Hace referencia a →"      A → B   se guarda como (A, B, 'ref')
- "← Es referenciada por"    B → A   se guarda como (B, A, 'ref')
Si A referencia a B y B referencia a A, existen dos relaciones (dos flechas) independientes.
"""
from __future__ import annotations

import re
import unicodedata

from models.entities import Relation, RelationKind, UiKind

_NON_ALNUM = re.compile(r"[^0-9A-Za-z]")
_CODE_PREFIX = re.compile(r"^\s*(\d+(?:[\s.\-]+\d+)*(?:[A-Za-z](?=\s|$))?)\s*(.*)$")


class SelfRelationError(ValueError):
    def __init__(self, section_id: int) -> None:
        super().__init__("Una sección no puede relacionarse consigo misma.")
        self.section_id = section_id


class DuplicateRelationError(ValueError):
    def __init__(self, existing: Relation, attempted: tuple[int, int, RelationKind]) -> None:
        super().__init__("Esta relación ya está registrada en esa dirección.")
        self.existing = existing
        self.attempted = attempted


def code_key(code: str) -> str:
    """'31 23 00' == '312300' == '31-23-00' == '31.23.00'."""
    return _NON_ALNUM.sub("", code).upper()


def strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def search_key(text: str) -> str:
    return strip_accents(text).casefold()


_TITLE_SEPARATORS = " -–—:|·\t"


def split_code_title(text: str) -> tuple[str, str]:
    """Separa "31 23 00 Excavación" o "03 30 00 - Concreto" en (código, título).

    Acepta separadores opcionales entre número y descripción (guion, dos puntos, barra).
    Si no hay prefijo numérico, todo el texto se toma como código.
    """
    text = text.strip()
    match = _CODE_PREFIX.match(text)
    if not match or not match.group(1).strip():
        return text.strip(_TITLE_SEPARATORS), ""
    code = re.sub(r"\s+", " ", match.group(1).strip())
    title = match.group(2).strip().lstrip(_TITLE_SEPARATORS).strip()
    return code, title


def format_label(code: str, title: str | None) -> str:
    """Etiqueta de una sección para listas y buscadores: '03 30 00 - Concreto'."""
    title = (title or "").strip()
    return f"{code} - {title}" if title else code


def normalize(a_id: int, kind: UiKind, b_id: int) -> tuple[int, int, RelationKind]:
    if a_id == b_id:
        raise SelfRelationError(a_id)
    if kind is UiKind.REFERENCED_BY:
        return b_id, a_id, RelationKind.REF
    return a_id, b_id, RelationKind.REF


def denormalize(rel: Relation) -> tuple[int, UiKind, int]:
    """Forma canónica para mostrar: 'source → target'."""
    return rel.source_id, UiKind.REFERENCES, rel.target_id


def same_pair(rel: Relation, a_id: int, b_id: int) -> bool:
    """Misma pareja de secciones, sin importar la dirección."""
    return {rel.source_id, rel.target_id} == {a_id, b_id}
