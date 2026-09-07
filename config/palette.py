"""Paleta de colores de la aplicación y categorías semilla de secciones."""
from __future__ import annotations

from dataclasses import dataclass

# Interfaz
PRIMARY = "#1F4E79"
PRIMARY_HOVER = "#2A6399"
PRIMARY_PRESSED = "#173B5C"
PRIMARY_TINT = "#E3ECF5"
BACKGROUND = "#F5F7FA"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F9FAFC"
BORDER = "#D9DEE5"
BORDER_STRONG = "#B8C1CC"
TEXT = "#1E1E1E"
TEXT_SECONDARY = "#5F6B7A"
TEXT_DISABLED = "#A0A6AE"
DANGER = "#C0392B"
SUCCESS = "#2E7D32"

# Lienzo
CANVAS_BACKGROUND = "#FFFFFF"
CANVAS_GRID = "#EEF1F5"
EDGE_COLOR = "#4472C4"
EDGE_SELECTED = "#1F4E79"
EDGE_HOVER = "#2F5597"
NODE_SELECTED_BORDER = "#1F4E79"
NODE_TEXT = "#1E1E1E"
NODE_SUBTEXT = "#3F4A57"
HIGHLIGHT_BORDER = "#C00000"
DIMMED_OPACITY = 0.22


@dataclass(frozen=True)
class CategorySeed:
    name: str
    fill: str
    border: str
    is_default: bool = False


# Clasificación inicial propuesta por el cliente. "Otra" es la categoría por
# defecto para secciones creadas automáticamente desde la entrada de relaciones.
DEFAULT_CATEGORIES: tuple[CategorySeed, ...] = (
    CategorySeed("Técnica / constructiva", "#E2EFDA", "#70AD47"),
    CategorySeed("Contractual", "#FFF2CC", "#BF9000"),
    CategorySeed("Auxiliar / apoyo", "#DDEBF7", "#5B9BD5"),
    CategorySeed("Otra", "#F8CBF0", "#C55A9E", is_default=True),
)


@dataclass(frozen=True)
class StatusSeed:
    name: str
    color: str
    is_default: bool = False


@dataclass(frozen=True)
class ResponsibleSeed:
    code: str
    name: str
    color: str


# Estatus de elaboración de una sección (lista configurable por proyecto).
DEFAULT_STATUSES: tuple[StatusSeed, ...] = (
    StatusSeed("No iniciada", "#D9DEE5", is_default=True),
    StatusSeed("En elaboración", "#FFE699"),
    StatusSeed("En revisión", "#BDD7EE"),
    StatusSeed("Aprobada", "#C6E0B4"),
    StatusSeed("Emitida", "#8FAADC"),
)

# Unidades responsables (no personas). Configurables por proyecto.
DEFAULT_RESPONSIBLES: tuple[ResponsibleSeed, ...] = (
    ResponsibleSeed("INIO", "Ingeniería de Costos y Especificaciones", "#5B9BD5"),
    ResponsibleSeed("INIG", "Ingeniería Geotécnica", "#70AD47"),
    ResponsibleSeed("INIE", "Ingeniería Eléctrica", "#7030A0"),
    ResponsibleSeed("INI-PY", "Proyectos", "#BF9000"),
    ResponsibleSeed("INIC", "Ingeniería Civil", "#ED7D31"),
)

# Adornos del nodo (responsables y avance)
PROGRESS_TRACK = "#E9EEF4"
RESPONSIBLE_EXTRA = "#8C949E"


def contrast_text(hex_color: str) -> str:
    """Blanco o texto oscuro según la luminancia del relleno."""
    h = hex_color.lstrip("#")
    try:
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return TEXT
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#FFFFFF" if lum < 0.6 else TEXT
