"""Entidades del dominio: dataclasses y enumeraciones compartidas."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

Side = Literal["top", "right", "bottom", "left"]
SIDES: tuple[Side, ...] = ("top", "right", "bottom", "left")


class RelationKind(str, Enum):
    """Tipo persistido en la base de datos."""

    REF = "ref"  # source hace referencia a target (único tipo desde el esquema v4)


class UiKind(str, Enum):
    """Tipo tal como lo elige el usuario en la interfaz."""

    REFERENCES = "Hace referencia a →"
    REFERENCED_BY = "← Es referenciada por"

    @property
    def short(self) -> str:
        return {"REFERENCES": "→", "REFERENCED_BY": "←"}[self.name]

    @classmethod
    def from_text(cls, text: str) -> "UiKind":
        for kind in cls:
            if kind.value == text:
                return kind
        raise ValueError(f"Tipo de relación desconocido: {text!r}")


@dataclass
class ProjectMeta:
    code: str = ""
    name: str = ""
    created_at: str = ""
    updated_at: str = ""
    app_version: str = ""

    @property
    def header(self) -> str:
        parts = [p for p in (self.code.strip(), self.name.strip()) if p]
        return " | ".join(parts) if parts else "Proyecto sin nombre"


@dataclass
class Category:
    id: int
    name: str
    fill_color: str
    border_color: str
    sort_order: int = 0
    is_default: bool = False


@dataclass
class Section:
    id: int
    code: str
    code_key: str
    title: str = ""
    category_id: int | None = None
    notes: str | None = None
    created_at: str = ""
    updated_at: str = ""
    fill_color: str | None = None    # color personalizado; None = usar el de la categoría
    border_color: str | None = None
    status_id: int | None = None
    progress: int = 0                # 0..100
    kind: str = "section"            # 'section' (MasterFormat) | 'clause' (cláusula del pliego: sin estatus/avance)

    @property
    def label(self) -> str:
        """'03 30 00 - Concreto' (o solo el código si no hay descripción)."""
        title = (self.title or "").strip()
        return f"{self.code} - {title}" if title else self.code

    @property
    def is_clause(self) -> bool:
        return self.kind == "clause"

    @property
    def has_custom_color(self) -> bool:
        return bool(self.fill_color)

    @property
    def observations(self) -> str:
        return self.notes or ""


@dataclass
class Status:
    id: int
    name: str
    color: str
    sort_order: int = 0
    is_default: bool = False


@dataclass
class Responsible:
    id: int
    code: str
    name: str
    color: str
    sort_order: int = 0

    @property
    def label(self) -> str:
        return f"{self.code} - {self.name}" if self.name else self.code


@dataclass
class Relation:
    id: int
    source_id: int
    target_id: int
    kind: RelationKind
    waypoints: list[tuple[float, float]] | None = None
    source_port: Side | None = None
    target_port: Side | None = None
    notes: str | None = None
    created_at: str = ""
    line_color: str | None = None     # None = palette.EDGE_COLOR
    line_dash: str = "solid"          # ver models.line_styles.DASH_KEYS
    line_width: float | None = None   # None = models.line_styles.DEFAULT_WIDTH

    @property
    def has_custom_style(self) -> bool:
        return self.line_color is not None or self.line_dash != "solid" or self.line_width is not None

    @property
    def style(self) -> tuple[str | None, str, float | None]:
        return (self.line_color, self.line_dash, self.line_width)

    def touches(self, section_id: int) -> bool:
        return section_id in (self.source_id, self.target_id)

    def other(self, section_id: int) -> int:
        return self.target_id if section_id == self.source_id else self.source_id


@dataclass
class NodePosition:
    section_id: int
    x: float
    y: float
    pinned: bool = False


@dataclass
class CatalogEntry:
    code_key: str
    code: str
    title: str
    category_name: str | None = None
    kind: str = "section"            # 'section' | 'clause'


@dataclass
class SectionRemoval:
    """Información devuelta al eliminar una sección (base para undo futuro)."""

    section: Section
    relations: list[Relation] = field(default_factory=list)
    position: NodePosition | None = None
