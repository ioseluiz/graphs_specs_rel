"""Saltos de línea en cruces de flechas (como Visio o draw.io): el tramo HORIZONTAL dibuja un arco sobre el vertical.

Módulo puro (sin Qt): recibe las polilíneas lógicas de todas las flechas y devuelve, por flecha, los puntos donde
sus tramos horizontales deben "saltar". Los tramos horizontales nunca se comparan entre sí (paralelos/colineales,
como A→B y B→A que comparten trazado, no producen saltos) y un cruce demasiado cerca de un codo, puerto o punta se
descarta para no deformar la flecha.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from typing import Mapping, NamedTuple, Sequence

JUMP_RADIUS = 6.0        # radio del arco, en píxeles de escena
EPS_ORTHO = 1e-6         # misma tolerancia que el router para considerar un tramo horizontal o vertical
EPS_END_V = 0.5          # un tramo vertical que termina sobre la horizontal (unión en T) no es un cruce

Point = tuple[float, float]


class Jump(NamedTuple):
    segment: int   # índice i del tramo horizontal (points[i] -> points[i+1]) de la flecha que salta
    x: float       # centro del arco
    y: float       # ordenada del tramo
    r: float       # radio (JUMP_RADIUS, o mayor si se fusionaron cruces vecinos)


class _HSeg(NamedTuple):
    rid: int
    index: int
    y: float
    xmin: float
    xmax: float


class _VSeg(NamedTuple):
    rid: int
    index: int
    x: float
    ymin: float
    ymax: float


def _classify(polylines: Mapping[int, Sequence[Point]], radius: float) -> tuple[list[_HSeg], list[_VSeg]]:
    horizontals: list[_HSeg] = []
    verticals: list[_VSeg] = []
    min_len = 2 * (radius + 1)
    for rid, pts in polylines.items():
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            if abs(y1 - y0) < EPS_ORTHO:
                if abs(x1 - x0) >= min_len:
                    horizontals.append(_HSeg(rid, i, y0, min(x0, x1), max(x0, x1)))
            elif abs(x1 - x0) < EPS_ORTHO:
                if abs(y1 - y0) > EPS_ORTHO:
                    verticals.append(_VSeg(rid, i, x0, min(y0, y1), max(y0, y1)))
            # tramos diagonales (solo el fallback del router los produce): sin saltos
    return horizontals, verticals


def _merge(xs: list[float], radius: float, seg: _HSeg) -> list[Jump]:
    """Cruces muy juntos (< 2r) se unen en un solo arco más ancho; el que no cabe en el tramo se descarta."""
    jumps: list[Jump] = []
    cluster: list[float] = []

    def flush() -> None:
        if not cluster:
            return
        xa, xb = cluster[0], cluster[-1]
        center, r = (xa + xb) / 2, (xb - xa) / 2 + radius
        if center - r >= seg.xmin + 1 and center + r <= seg.xmax - 1:
            jumps.append(Jump(seg.index, center, seg.y, r))
        cluster.clear()

    for x in xs:
        if cluster and x - cluster[-1] >= 2 * radius:
            flush()
        cluster.append(x)
    flush()
    return jumps


def find_jumps(polylines: Mapping[int, Sequence[Point]], radius: float = JUMP_RADIUS) -> dict[int, list[Jump]]:
    """Devuelve {rid: [Jump, ...]} solo para las flechas con al menos un salto; saltos ordenados por x."""
    horizontals, verticals = _classify(polylines, radius)
    if not horizontals or not verticals:
        return {}
    verticals.sort(key=lambda v: v.x)
    xs_sorted = [v.x for v in verticals]
    result: dict[int, list[Jump]] = {}
    for h in horizontals:
        lo = bisect_right(xs_sorted, h.xmin + radius + 1)
        hi = bisect_left(xs_sorted, h.xmax - radius - 1)
        crossings: list[float] = []
        for v in verticals[lo:hi]:
            if v.rid == h.rid and abs(v.index - h.index) == 1:
                continue  # tramo adyacente de la misma flecha: es un codo, no un cruce
            if v.ymin + EPS_END_V < h.y < v.ymax - EPS_END_V:
                crossings.append(v.x)
        if not crossings:
            continue
        crossings.sort()
        jumps = _merge(crossings, radius, h)
        if jumps:
            result.setdefault(h.rid, []).extend(jumps)
    for rid in result:
        result[rid].sort(key=lambda j: (j.segment, j.x))
    return result
