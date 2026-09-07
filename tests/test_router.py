from __future__ import annotations

import pytest
from PyQt6.QtCore import QPointF, QRectF

from views.components.canvas.orthogonal_router import (
    SOURCE_SIDES,
    TARGET_SIDES,
    _segment_crosses,
    choose_ports,
    is_orthogonal,
    port_point,
    repair_waypoints,
    route,
)

W, H = 160.0, 60.0
SRC = QRectF(0, 0, W, H)

OFFSETS = {
    "arriba": (0, -300), "abajo": (0, 300), "derecha": (400, 0), "izquierda": (-400, 0),
    "arriba-derecha": (400, -300), "arriba-izquierda": (-400, -300),
    "abajo-derecha": (400, 300), "abajo-izquierda": (-400, 300),
}


def _tgt(dx: float, dy: float) -> QRectF:
    return QRectF(dx, dy, W, H)


def _crosses_any(points, rect) -> bool:
    segs = list(zip(points, points[1:]))
    return any(_segment_crosses(a, b, rect) for a, b in segs[1:-1])


@pytest.mark.parametrize("name,offset", OFFSETS.items())
def test_route_respects_convention_and_is_orthogonal(name, offset):
    tgt = _tgt(*offset)
    ports = choose_ports(SRC, tgt)
    pts = route(SRC, tgt, ports)
    assert is_orthogonal(pts), name
    assert ports[0] in SOURCE_SIDES and ports[1] in TARGET_SIDES, name
    assert pts[0] == port_point(SRC, ports[0]) and pts[-1] == port_point(tgt, ports[1])
    # Los tramos intermedios no atraviesan el interior de origen ni destino.
    assert not _crosses_any(pts, SRC), name
    assert not _crosses_any(pts, tgt), name


@pytest.mark.parametrize("offset", [(-400, 0), (0, 300), (-400, 300), (-40, 300)])
def test_route_never_runs_through_nodes(offset):
    """Destino a la izquierda o debajo: la ruta debe rodear, nunca cruzar los nodos en línea recta."""
    from views.components.canvas.orthogonal_router import OUT, is_valid_route

    tgt = _tgt(*offset)
    ports = choose_ports(SRC, tgt)
    pts = route(SRC, tgt, ports)
    assert is_valid_route(pts, SRC, tgt, ports)
    # Primer tramo hacia afuera del origen y último hacia adentro del destino.
    sx, sy = OUT[ports[0]]
    assert (pts[1].x() - pts[0].x()) * sx + (pts[1].y() - pts[0].y()) * sy > 0
    tx, ty = OUT[ports[1]]
    assert (pts[-1].x() - pts[-2].x()) * tx + (pts[-1].y() - pts[-2].y()) * ty < 0
    for a, b in zip(pts, pts[1:]):
        assert not _segment_crosses(a, b, SRC.adjusted(2, 2, -2, -2)) or a == pts[0]
        assert not _segment_crosses(a, b, tgt.adjusted(2, 2, -2, -2)) or b == pts[-1]


def test_choose_ports_deterministic():
    tgt = _tgt(400, -300)
    assert choose_ports(SRC, tgt) == choose_ports(SRC, tgt)


def test_target_above_uses_top_to_bottom():
    tgt = _tgt(0, -300)
    ports = choose_ports(SRC, tgt)
    assert ports == ("top", "bottom")
    pts = route(SRC, tgt, ports)
    assert len(pts) == 2  # línea recta


def test_target_right_uses_right_to_left():
    tgt = _tgt(400, 0)
    assert choose_ports(SRC, tgt) == ("right", "left")


def test_target_up_right_is_L():
    tgt = _tgt(400, -300)
    ports = choose_ports(SRC, tgt)
    pts = route(SRC, tgt, ports)
    assert ports == ("right", "bottom")
    assert len(pts) == 3  # P, codo, Q: el stub de salida es colineal y se absorbe (una sola esquina)


def test_overlapping_rects_still_returns_path():
    tgt = QRectF(20, 10, W, H)
    ports = choose_ports(SRC, tgt)
    pts = route(SRC, tgt, ports)
    assert len(pts) >= 2 and is_orthogonal(pts)


def test_repair_waypoints_keeps_orthogonality():
    tgt = _tgt(500, 300)
    wps = [QPointF(80, -120), QPointF(300, -120), QPointF(300, 330)]
    pts = repair_waypoints(SRC, "top", wps, tgt, "left")
    assert is_orthogonal(pts)
    assert pts[0] == port_point(SRC, "top") and pts[-1] == port_point(tgt, "left")
    # Los waypoints del usuario se conservan en la polilínea.
    assert all(any(p == w for p in pts) for w in wps)
    # Al mover el destino, se mantiene ortogonal sin tocar los waypoints.
    tgt2 = _tgt(700, 420)
    pts2 = repair_waypoints(SRC, "top", wps, tgt2, "left")
    assert is_orthogonal(pts2) and pts2[-1] == port_point(tgt2, "left")
    # El último waypoint queda colineal con el nuevo tramo y se absorbe; los demás persisten.
    assert all(any(p == w for p in pts2) for w in wps[:2])
