"""Estilo propio de una flecha (color, trazo y grosor): constantes, etiquetas y parsers sin Qt.

`None` (color, grosor) y `'solid'` (trazo) significan «predeterminado»: la flecha se pinta con la paleta global.
"""
from __future__ import annotations

import re

from models.relation_normalizer import search_key

DASH_SOLID, DASH_DASH, DASH_DOT, DASH_DASHDOT = "solid", "dash", "dot", "dashdot"
DASH_KEYS: tuple[str, ...] = (DASH_SOLID, DASH_DASH, DASH_DOT, DASH_DASHDOT)
DASH_LABELS: dict[str, str] = {
    DASH_SOLID: "Continua",
    DASH_DASH: "Discontinua",
    DASH_DOT: "Punteada",
    DASH_DASHDOT: "Punto y raya",
}
DEFAULT_WIDTH = 1.6
WIDTH_MIN, WIDTH_MAX = 0.5, 8.0
WIDTH_PRESETS: tuple[tuple[str, float], ...] = (("Fina", 1.0), ("Normal", 1.6), ("Gruesa", 2.5), ("Muy gruesa", 4.0))
KEEP = object()   # centinela «no cambiar» para ProjectModel.set_relation_style

_DASH_SYNONYMS: dict[str, tuple[str, ...]] = {
    DASH_SOLID: ("continua", "solida", "solid", "normal", "-", "—", "linea"),
    DASH_DASH: ("discontinua", "rayas", "a rayas", "guiones", "dashed", "dash", "--", "- -"),
    DASH_DOT: ("punteada", "puntos", "dotted", "dot", "..", "...", "…"),
    DASH_DASHDOT: ("punto y raya", "punto-raya", "punto raya", "raya-punto", "raya punto", "dashdot", "dash-dot",
                   "dash dot", "-.", ".-", "-.-"),
}
_HEX = re.compile(r"^#?[0-9A-Fa-f]{6}$")


def valid_hex(value: str | None) -> str | None:
    """'#c00000' / 'C00000' -> '#C00000'; None si no es un color hexadecimal de 6 dígitos."""
    v = (value or "").strip()
    if not v or not _HEX.match(v):
        return None
    return "#" + v.lstrip("#").upper()


def parse_dash(text: str | None) -> str:
    """Texto de la celda «Trazo» -> clave. Vacío = 'solid'. ValueError si no se reconoce."""
    raw = (text or "").strip()
    if not raw:
        return DASH_SOLID
    if raw in DASH_KEYS:
        return raw
    key = re.sub(r"\s+", " ", search_key(raw)).strip()
    compact = key.replace(" ", "")
    for dash, names in _DASH_SYNONYMS.items():
        if key in names or compact in names or key == dash:
            return dash
    raise ValueError(f"Trazo desconocido: {raw!r}. Use Continua, Discontinua, Punteada o Punto y raya.")


def parse_width(text: str | float | int | None) -> float | None:
    """Texto de la celda «Grosor» -> grosor en px. Vacío = None (predeterminado). ValueError si no es válido."""
    if text is None:
        return None
    if isinstance(text, (int, float)):
        value = float(text)
    else:
        raw = text.strip()
        if not raw:
            return None
        key = search_key(raw)
        for name, preset in WIDTH_PRESETS:
            if key == search_key(name):
                return preset
        try:
            value = float(raw.replace(",", ".").replace("px", "").strip())
        except ValueError as exc:
            raise ValueError(f"Grosor desconocido: {raw!r}. Use Fina, Normal, Gruesa, Muy gruesa o un número.") from exc
    if not WIDTH_MIN <= value <= WIDTH_MAX:
        raise ValueError(f"El grosor debe estar entre {WIDTH_MIN:g} y {WIDTH_MAX:g} px (recibido {value:g}).")
    return round(value, 2)


def dash_label(key: str | None) -> str:
    """Etiqueta para exportar: vacía si es el trazo predeterminado."""
    if not key or key == DASH_SOLID:
        return ""
    return DASH_LABELS.get(key, key)


def width_label(width: float | None) -> str:
    """Etiqueta para exportar: vacía si es el grosor predeterminado; nombre del preset si coincide."""
    if width is None:
        return ""
    for name, preset in WIDTH_PRESETS:
        if abs(preset - width) < 1e-6:
            return name
    return f"{width:g}"


def width_name(width: float | None) -> str:
    """Nombre legible del grosor efectivo (siempre devuelve algo)."""
    return width_label(width if width is not None else DEFAULT_WIDTH) or f"{width:g}"
