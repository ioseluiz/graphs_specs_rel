"""Colocación de nodos: posición inicial 2D y disposición 3D determinista."""
from __future__ import annotations

import math
from typing import Iterable, Mapping

import networkx as nx

NODE_W = 160.0
NODE_H = 60.0
GAP_X = 60.0
GAP_Y = 90.0   # deja espacio para responsables (arriba) y avance (abajo) del nodo
STEP_X = NODE_W + GAP_X
STEP_Y = NODE_H + GAP_Y


def _occupied(positions: Iterable[tuple[float, float]], x: float, y: float) -> bool:
    for px, py in positions:
        if abs(px - x) < NODE_W + GAP_X * 0.5 and abs(py - y) < NODE_H + GAP_Y * 0.5:
            return True
    return False


def place_new_node(
    existing: Mapping[int, tuple[float, float]],
    neighbor_ids: Iterable[int] = (),
) -> tuple[float, float]:
    """Coloca un nodo nuevo cerca de sus vecinos ya ubicados o en la siguiente celda libre.

    Nunca mueve nodos existentes (restricción del cliente).
    """
    taken = list(existing.values())
    neighbor_pos = [existing[n] for n in neighbor_ids if n in existing]

    if neighbor_pos:
        cx = sum(p[0] for p in neighbor_pos) / len(neighbor_pos)
        cy = sum(p[1] for p in neighbor_pos) / len(neighbor_pos)
        # Anillos concéntricos alrededor del centroide de los vecinos.
        for ring in range(1, 8):
            radius = ring * STEP_Y
            samples = 8 * ring
            for k in range(samples):
                ang = 2 * math.pi * k / samples - math.pi / 2  # arriba primero
                x = cx + radius * 1.6 * math.cos(ang)
                y = cy + radius * math.sin(ang)
                if not _occupied(taken, x, y):
                    return _snap(x), _snap(y)

    if not taken:
        return 0.0, 0.0
    # Rejilla: siguiente celda libre recorriendo filas de izquierda a derecha.
    min_x = min(p[0] for p in taken)
    max_x = max(p[0] for p in taken)
    min_y = min(p[1] for p in taken)
    cols = max(1, int((max_x - min_x) / STEP_X) + 1)
    cols = max(cols, 4)
    row = 0
    while row < 500:
        for col in range(cols):
            x = min_x + col * STEP_X
            y = min_y + row * STEP_Y
            if not _occupied(taken, x, y):
                return _snap(x), _snap(y)
        row += 1
    return _snap(max_x + STEP_X), _snap(min_y)


def _snap(v: float, grid: float = 10.0) -> float:
    return round(v / grid) * grid


def initial_layout_2d(G: nx.Graph, seed: int = 42) -> dict[int, tuple[float, float]]:
    """Disposición inicial (solo para nodos sin posición): spring layout escalado a píxeles."""
    if G.number_of_nodes() == 0:
        return {}
    if G.number_of_nodes() == 1:
        return {next(iter(G.nodes)): (0.0, 0.0)}
    n = G.number_of_nodes()
    scale = max(400.0, math.sqrt(n) * STEP_X * 0.9)
    pos = nx.spring_layout(G.to_undirected(as_view=True), seed=seed, k=2.0 / math.sqrt(n),
                           iterations=200, scale=scale)
    return {node: (_snap(float(p[0]) * 1.4), _snap(float(p[1]))) for node, p in pos.items()}


def layout3d(G: nx.Graph, seed: int = 42) -> dict[int, tuple[float, float, float]]:
    """Spring layout 3D determinista (misma semilla -> mismas posiciones).

    Cada componente conexa se distribuye por separado (así no colapsa por la repulsión entre
    grupos) y los grupos se colocan sobre una espiral, del más grande al más pequeño.
    """
    if G.number_of_nodes() == 0:
        return {}
    H = G.to_undirected(as_view=True)
    comps = sorted(nx.connected_components(H), key=lambda c: (-len(c), min(c)))
    result: dict[int, tuple[float, float, float]] = {}
    radii = [max(1.2, 1.7 * math.sqrt(len(c))) for c in comps]
    for i, comp in enumerate(comps):
        n = len(comp)
        radius = radii[i]
        if n == 1:
            local = {next(iter(comp)): (0.0, 0.0, 0.0)}
        else:
            sub = H.subgraph(comp)
            pos = nx.spring_layout(sub, dim=3, seed=seed + i, iterations=150, scale=radius)
            local = {node: (float(p[0]), float(p[1]), float(p[2])) for node, p in pos.items()}
        if i == 0:
            cx, cy, cz = 0.0, 0.0, 0.0
        else:
            ang = i * 2.399963  # ángulo dorado
            dist = radii[0] + radius + 2.5 + 0.9 * i
            cx, cy, cz = dist * math.cos(ang), dist * math.sin(ang), 0.5 * radius * math.sin(i * 1.3)
        for node, (x, y, z) in local.items():
            result[node] = (x + cx, y + cy, z + cz)
    return result


def place_new_node_3d(
    existing: Mapping[int, tuple[float, float, float]],
    neighbor_ids: Iterable[int],
    seed_index: int,
) -> tuple[float, float, float]:
    neighbor_pos = [existing[n] for n in neighbor_ids if n in existing]
    if neighbor_pos:
        cx = sum(p[0] for p in neighbor_pos) / len(neighbor_pos)
        cy = sum(p[1] for p in neighbor_pos) / len(neighbor_pos)
        cz = sum(p[2] for p in neighbor_pos) / len(neighbor_pos)
        ang = seed_index * 2.399  # ángulo dorado para dispersar
        return cx + 1.5 * math.cos(ang), cy + 1.5 * math.sin(ang), cz + 0.8 * math.sin(ang * 0.5)
    ang = seed_index * 2.399
    return 11.0 * math.cos(ang), 11.0 * math.sin(ang), 0.0
