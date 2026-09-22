"""Saltos de línea: detección pura de cruces horizontal-sobre-vertical."""
from __future__ import annotations

from views.components.canvas.line_jumps import JUMP_RADIUS, Jump, find_jumps


def test_simple_cross_jumps_on_horizontal_only():
    polys = {1: [(0.0, 0.0), (100.0, 0.0)], 2: [(50.0, -50.0), (50.0, 50.0)]}
    assert find_jumps(polys) == {1: [Jump(0, 50.0, 0.0, JUMP_RADIUS)]}
    # Da igual el sentido de recorrido de cada tramo.
    polys = {1: [(100.0, 0.0), (0.0, 0.0)], 2: [(50.0, 50.0), (50.0, -50.0)]}
    assert find_jumps(polys) == {1: [Jump(0, 50.0, 0.0, JUMP_RADIUS)]}


def test_crossings_near_segment_ends_or_t_junctions_are_ignored():
    # A 4 px del extremo del tramo horizontal: chocaría con el codo/puerto.
    assert find_jumps({1: [(0.0, 0.0), (100.0, 0.0)], 2: [(4.0, -50.0), (4.0, 50.0)]}) == {}
    assert find_jumps({1: [(0.0, 0.0), (100.0, 0.0)], 2: [(96.0, -50.0), (96.0, 50.0)]}) == {}
    # Unión en T: la vertical termina exactamente sobre la horizontal.
    assert find_jumps({1: [(0.0, 0.0), (100.0, 0.0)], 2: [(50.0, -50.0), (50.0, 0.0)]}) == {}
    # Tramo horizontal demasiado corto para albergar un arco.
    assert find_jumps({1: [(45.0, 0.0), (55.0, 0.0)], 2: [(50.0, -50.0), (50.0, 50.0)]}) == {}


def test_close_crossings_merge_into_a_wider_arc():
    polys = {1: [(0.0, 0.0), (100.0, 0.0)], 2: [(50.0, -50.0), (50.0, 50.0)], 3: [(58.0, -50.0), (58.0, 50.0)]}
    assert find_jumps(polys) == {1: [Jump(0, 54.0, 0.0, 4.0 + JUMP_RADIUS)]}
    # Suficientemente separados: dos arcos, ordenados por x aunque las verticales vengan desordenadas.
    polys = {1: [(0.0, 0.0), (200.0, 0.0)], 2: [(150.0, -5.0), (150.0, 5.0)], 3: [(50.0, -5.0), (50.0, 5.0)],
             4: [(100.0, -5.0), (100.0, 5.0)]}
    assert [j.x for j in find_jumps(polys)[1]] == [50.0, 100.0, 150.0]


def test_parallel_collinear_and_diagonal_segments_do_not_jump():
    # Dos flechas opuestas que comparten el trazado: nada que saltar.
    assert find_jumps({1: [(0.0, 0.0), (100.0, 0.0)], 2: [(100.0, 0.0), (0.0, 0.0)]}) == {}
    assert find_jumps({1: [(0.0, 0.0), (0.0, 100.0)], 2: [(0.0, 100.0), (0.0, 0.0)]}) == {}
    # Un tramo diagonal (fallback del router) se ignora.
    assert find_jumps({1: [(0.0, 0.0), (100.0, 80.0)], 2: [(50.0, -50.0), (50.0, 150.0)]}) == {}


def test_self_crossing_polyline_jumps_on_its_own_horizontal():
    # Espiral: el último tramo horizontal cruza el primer tramo vertical de la misma flecha.
    spiral = [(0.0, 0.0), (0.0, 100.0), (100.0, 100.0), (100.0, 50.0), (-50.0, 50.0)]
    jumps = find_jumps({7: spiral})
    assert jumps == {7: [Jump(3, 0.0, 50.0, JUMP_RADIUS)]}
    # Los codos (tramos adyacentes) nunca cuentan como cruce.
    assert find_jumps({8: [(0.0, 0.0), (100.0, 0.0), (100.0, 100.0)]}) == {}


def test_multiple_horizontal_segments_of_one_polyline_are_indexed():
    zigzag = [(0.0, 0.0), (100.0, 0.0), (100.0, 40.0), (0.0, 40.0)]
    polys = {1: zigzag, 2: [(50.0, -100.0), (50.0, 100.0)]}
    assert find_jumps(polys) == {1: [Jump(0, 50.0, 0.0, JUMP_RADIUS), Jump(2, 50.0, 40.0, JUMP_RADIUS)]}
