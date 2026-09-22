"""Estilo de flecha: parsers y etiquetas puras (sin Qt)."""
from __future__ import annotations

import pytest

from models.line_styles import (
    DASH_DASH,
    DASH_DASHDOT,
    DASH_DOT,
    DASH_SOLID,
    dash_label,
    parse_dash,
    parse_width,
    valid_hex,
    width_label,
)


@pytest.mark.parametrize("text,expected", [
    ("", DASH_SOLID), ("Continua", DASH_SOLID), ("solid", DASH_SOLID), ("-", DASH_SOLID),
    ("Discontinua", DASH_DASH), ("dashed", DASH_DASH), ("--", DASH_DASH), ("a rayas", DASH_DASH), ("dash", DASH_DASH),
    ("Punteada", DASH_DOT), ("dotted", DASH_DOT), ("..", DASH_DOT), ("PUNTOS", DASH_DOT),
    ("Punto y raya", DASH_DASHDOT), ("punto-raya", DASH_DASHDOT), ("dashdot", DASH_DASHDOT), ("-.", DASH_DASHDOT),
    ("Dash-Dot", DASH_DASHDOT),
])
def test_parse_dash_synonyms(text, expected):
    assert parse_dash(text) == expected


def test_parse_dash_rejects_unknown():
    with pytest.raises(ValueError):
        parse_dash("ondulada")


@pytest.mark.parametrize("text,expected", [
    ("", None), (None, None), ("Fina", 1.0), ("normal", 1.6), ("GRUESA", 2.5), ("Muy gruesa", 4.0),
    ("2", 2.0), ("2,5", 2.5), ("3.25", 3.25), ("0.5", 0.5), ("8", 8.0), (2, 2.0), (1.6, 1.6), ("3 px", 3.0),
])
def test_parse_width_presets_and_numbers(text, expected):
    assert parse_width(text) == expected


@pytest.mark.parametrize("text", ["0.4", "9", "grueso extremo", "-1"])
def test_parse_width_rejects_out_of_range_or_unknown(text):
    with pytest.raises(ValueError):
        parse_width(text)


def test_labels_are_empty_for_defaults():
    assert dash_label(DASH_SOLID) == "" and dash_label(None) == ""
    assert dash_label(DASH_DASH) == "Discontinua" and dash_label(DASH_DASHDOT) == "Punto y raya"
    assert width_label(None) == ""
    assert width_label(2.5) == "Gruesa" and width_label(1.6) == "Normal" and width_label(4.0) == "Muy gruesa"
    assert width_label(2.0) == "2" and width_label(3.25) == "3.25"


def test_valid_hex():
    assert valid_hex("#c00000") == "#C00000" and valid_hex("4472c4") == "#4472C4"
    assert valid_hex("rojo") is None and valid_hex("#FFF") is None and valid_hex("") is None
