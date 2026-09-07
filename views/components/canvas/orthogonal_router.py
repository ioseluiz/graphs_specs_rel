"""Ruteo ortogonal de conexiones entre nodos (funciones puras, solo QtCore).

Convención del cliente: la conexión sale preferiblemente por la parte superior o
derecha del nodo origen y llega por la parte inferior o izquierda del destino.
Si el espacio no lo permite, se ajusta automáticamente el punto de conexión.
"""
from __future__ import annotations

from typing import Iterable, Sequence

from PyQt6.QtCore import QPointF, QRectF

from models.entities import SIDES, Side

OUT: dict[Side, tuple[int, int]] = {
    "top": (0, -1), "right": (1, 0), "bottom": (0, 1), "left": (-1, 0),
}
GAP = 24.0          # tramo recto mínimo al salir/entrar de un nodo
BEND_COST = 80.0    # penalización por codo, en píxeles equivalentes (favorece formas L)
SOURCE_SIDES: tuple[Side, ...] = ("top", "right")
TARGET_SIDES: tuple[Side, ...] = ("bottom", "left")


def port_point(rect: QRectF, side: Side) -> QPointF:
    c = rect.center()
    if side == "top":
        return QPointF(c.x(), rect.top())
    if side == "bottom":
        return QPointF(c.x(), rect.bottom())
    if side == "left":
        return QPointF(rect.left(), c.y())
    return QPointF(rect.right(), c.y())


def _stub(point: QPointF, side: Side, gap: float = GAP) -> QPointF:
    dx, dy = OUT[side]
    return QPointF(point.x() + dx * gap, point.y() + dy * gap)


def _length(points: Sequence[QPointF]) -> float:
    total = 0.0
    for a, b in zip(points, points[1:]):
        total += abs(b.x() - a.x()) + abs(b.y() - a.y())
    return total


def dedupe(points: Iterable[QPointF]) -> list[QPointF]:
    """Elimina puntos repetidos y vértices colineales."""
    out: list[QPointF] = []
    for p in points:
        if out and abs(out[-1].x() - p.x()) < 1e-6 and abs(out[-1].y() - p.y()) < 1e-6:
            continue
        out.append(QPointF(p))
    i = 1
    while i < len(out) - 1:
        a, b, c = out[i - 1], out[i], out[i + 1]
        same_x = abs(a.x() - b.x()) < 1e-6 and abs(b.x() - c.x()) < 1e-6
        same_y = abs(a.y() - b.y()) < 1e-6 and abs(b.y() - c.y()) < 1e-6
        if same_x or same_y:
            del out[i]
        else:
            i += 1
    return out


def bends(points: Sequence[QPointF]) -> int:
    return max(0, len(dedupe(points)) - 2)


def is_orthogonal(points: Sequence[QPointF]) -> bool:
    return all(
        abs(a.x() - b.x()) < 1e-6 or abs(a.y() - b.y()) < 1e-6
        for a, b in zip(points, points[1:])
    )


def _segment_crosses(a: QPointF, b: QPointF, rect: QRectF) -> bool:
    """True si un segmento H/V atraviesa el interior (estricto) del rectángulo."""
    r = rect.adjusted(1.0, 1.0, -1.0, -1.0)
    if r.isEmpty():
        return False
    if abs(a.y() - b.y()) < 1e-6:  # horizontal
        y = a.y()
        if not (r.top() < y < r.bottom()):
            return False
        x0, x1 = sorted((a.x(), b.x()))
        return x0 < r.right() and x1 > r.left()
    if abs(a.x() - b.x()) < 1e-6:  # vertical
        x = a.x()
        if not (r.left() < x < r.right()):
            return False
        y0, y1 = sorted((a.y(), b.y()))
        return y0 < r.bottom() and y1 > r.top()
    return True  # diagonal: se considera inválido


def _valid(points: Sequence[QPointF], src: QRectF, tgt: QRectF, ports: tuple[Side, Side]) -> bool:
    if len(points) < 2 or not is_orthogonal(points):
        return False
    segs = list(zip(points, points[1:]))
    # El primer tramo debe salir hacia afuera del puerto de origen y el último entrar hacia el destino;
    # de lo contrario una "recta" podría atravesar ambos nodos y esconder las puntas de flecha.
    s_out, t_out = OUT[ports[0]], OUT[ports[1]]
    a, b = segs[0]
    if (b.x() - a.x()) * s_out[0] + (b.y() - a.y()) * s_out[1] <= 0:
        return False
    a, b = segs[-1]
    if (b.x() - a.x()) * t_out[0] + (b.y() - a.y()) * t_out[1] >= 0:
        return False
    # Los tramos posteriores al stub de salida no cruzan el origen; los anteriores al de entrada, el destino.
    for i, (a, b) in enumerate(segs):
        if i > 0 and _segment_crosses(a, b, src):
            return False
        if i < len(segs) - 1 and _segment_crosses(a, b, tgt):
            return False
    return True


def _candidates(p1: QPointF, q1: QPointF, src: QRectF, tgt: QRectF) -> list[list[QPointF]]:
    mid_x = (p1.x() + q1.x()) / 2
    mid_y = (p1.y() + q1.y()) / 2
    left = min(src.left(), tgt.left()) - GAP
    right = max(src.right(), tgt.right()) + GAP
    top = min(src.top(), tgt.top()) - GAP
    bottom = max(src.bottom(), tgt.bottom()) + GAP
    cands: list[list[QPointF]] = [
        [p1, q1],
        [p1, QPointF(p1.x(), q1.y()), q1],                      # L vertical-horizontal
        [p1, QPointF(q1.x(), p1.y()), q1],                      # L horizontal-vertical
        [p1, QPointF(p1.x(), mid_y), QPointF(q1.x(), mid_y), q1],   # Z: V-H-V
        [p1, QPointF(mid_x, p1.y()), QPointF(mid_x, q1.y()), q1],   # Z: H-V-H
    ]
    for x in (left, right):  # rodeos H-V-H por los costados
        cands.append([p1, QPointF(x, p1.y()), QPointF(x, q1.y()), q1])
    for y in (top, bottom):  # rodeos V-H-V por arriba/abajo
        cands.append([p1, QPointF(p1.x(), y), QPointF(q1.x(), y), q1])
    # Rodeos en U con 4 codos: salir, ir al costado, cruzar, volver.
    for x in (left, right):
        for y in (top, bottom):
            cands.append([p1, QPointF(p1.x(), y), QPointF(x, y), QPointF(x, q1.y()), q1])
            cands.append([p1, QPointF(x, p1.y()), QPointF(x, y), QPointF(q1.x(), y), q1])
    return cands


def route(src: QRectF, tgt: QRectF, ports: tuple[Side, Side]) -> list[QPointF]:
    """Devuelve la polilínea ortogonal completa (incluye puntos de puerto)."""
    s_side, t_side = ports
    P = port_point(src, s_side)
    Q = port_point(tgt, t_side)
    p1 = _stub(P, s_side)
    q1 = _stub(Q, t_side)
    best: list[QPointF] | None = None
    best_cost = float("inf")
    fallback: list[QPointF] | None = None
    fallback_cost = float("inf")
    for cand in _candidates(p1, q1, src, tgt):
        pts = dedupe([P, *cand, Q])
        if not is_orthogonal(pts):
            continue
        cost = _length(pts) + BEND_COST * bends(pts)
        if _valid(pts, src, tgt, ports):
            if cost < best_cost:
                best, best_cost = pts, cost
        elif cost < fallback_cost:
            fallback, fallback_cost = pts, cost
    return best if best is not None else (fallback or dedupe([P, p1, q1, Q]))


def is_valid_route(points: Sequence[QPointF], src: QRectF, tgt: QRectF, ports: tuple[Side, Side]) -> bool:
    return _valid(points, src, tgt, ports)


def route_cost(points: Sequence[QPointF]) -> float:
    return _length(points) + BEND_COST * bends(points)


def choose_ports(
    src: QRectF,
    tgt: QRectF,
    source_sides: Sequence[Side] = SOURCE_SIDES,
    target_sides: Sequence[Side] = TARGET_SIDES,
) -> tuple[Side, Side]:
    """Evalúa las combinaciones permitidas y elige la ruta de menor costo.

    Si ninguna combinación preferida produce una ruta válida, se amplía a los
    cuatro lados (el sistema ajusta automáticamente el punto de conexión).
    """
    best: tuple[Side, Side] | None = None
    best_cost = float("inf")
    delta = tgt.center() - src.center()
    # Desempate: salir por el lado que apunta al eje dominante hacia el destino.
    dominant: Side = ("right" if delta.x() >= 0 else "left") if abs(delta.x()) >= abs(delta.y())         else ("bottom" if delta.y() >= 0 else "top")
    for s_side in source_sides:
        for t_side in target_sides:
            pts = route(src, tgt, (s_side, t_side))
            if not _valid(pts, src, tgt, (s_side, t_side)):
                continue
            cost = route_cost(pts) + (0.0 if s_side == dominant else 1.0)
            if cost < best_cost:
                best, best_cost = (s_side, t_side), cost
    if best is not None:
        return best
    if tuple(source_sides) != SIDES or tuple(target_sides) != SIDES:
        return choose_ports(src, tgt, SIDES, SIDES)
    return source_sides[0], target_sides[0]


def choose_ports_near(
    src: QRectF,
    tgt: QRectF,
    first_wp: QPointF,
    last_wp: QPointF,
    source_sides: Sequence[Side] = SOURCE_SIDES,
    target_sides: Sequence[Side] = TARGET_SIDES,
) -> tuple[Side, Side]:
    """Con waypoints manuales: cada puerto es el lado permitido más cercano al waypoint extremo."""
    def nearest(rect: QRectF, sides: Sequence[Side], to: QPointF) -> Side:
        best, best_d = sides[0], float("inf")
        for side in sides:
            stub = _stub(port_point(rect, side), side)
            d = abs(stub.x() - to.x()) + abs(stub.y() - to.y())
            if d < best_d:
                best, best_d = side, d
        return best

    return nearest(src, source_sides, first_wp), nearest(tgt, target_sides, last_wp)


def repair_waypoints(
    src: QRectF, s_side: Side, waypoints: Sequence[QPointF], tgt: QRectF, t_side: Side
) -> list[QPointF]:
    """Une puerto -> waypoints (absolutos) -> puerto insertando codos ortogonales."""
    P = port_point(src, s_side)
    Q = port_point(tgt, t_side)
    p1 = _stub(P, s_side)
    q1 = _stub(Q, t_side)
    pts: list[QPointF] = [P, p1]
    prev_vertical = OUT[s_side][0] == 0  # el stub de salida es vertical si el lado es top/bottom
    for w in [*waypoints, q1]:
        last = pts[-1]
        if abs(last.x() - w.x()) > 1e-6 and abs(last.y() - w.y()) > 1e-6:
            # Alternar orientación respecto al tramo anterior para un trazo natural.
            elbow = QPointF(last.x(), w.y()) if prev_vertical else QPointF(w.x(), last.y())
            pts.append(elbow)
            prev_vertical = not prev_vertical
        else:
            prev_vertical = abs(last.x() - w.x()) < 1e-6
        pts.append(QPointF(w))
    # Tramo final: asegurar que se entra al destino en línea recta por su puerto.
    last = pts[-1]
    if abs(last.x() - q1.x()) > 1e-6 or abs(last.y() - q1.y()) > 1e-6:
        pts.append(q1)
    pts.append(Q)
    return dedupe(pts)


def nearest_segment_index(points: Sequence[QPointF], pos: QPointF) -> int:
    """Índice del segmento (i, i+1) más cercano a `pos`."""
    best_i, best_d = 0, float("inf")
    for i, (a, b) in enumerate(zip(points, points[1:])):
        d = _point_segment_distance(pos, a, b)
        if d < best_d:
            best_i, best_d = i, d
    return best_i


def _point_segment_distance(p: QPointF, a: QPointF, b: QPointF) -> float:
    ax, ay, bx, by = a.x(), a.y(), b.x(), b.y()
    dx, dy = bx - ax, by - ay
    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        return ((p.x() - ax) ** 2 + (p.y() - ay) ** 2) ** 0.5
    t = ((p.x() - ax) * dx + (p.y() - ay) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = ax + t * dx, ay + t * dy
    return ((p.x() - cx) ** 2 + (p.y() - cy) ** 2) ** 0.5
