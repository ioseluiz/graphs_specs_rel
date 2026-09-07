from __future__ import annotations

import networkx as nx

from models.layout_engine import NODE_H, NODE_W, layout3d, place_new_node


def _overlaps(a, b) -> bool:
    return abs(a[0] - b[0]) < NODE_W and abs(a[1] - b[1]) < NODE_H


def test_place_new_node_never_overlaps():
    existing: dict[int, tuple[float, float]] = {}
    for i in range(40):
        pos = place_new_node(existing, neighbor_ids=[i - 1] if i else [])
        assert all(not _overlaps(pos, p) for p in existing.values())
        existing[i] = pos


def test_place_near_neighbors():
    existing = {1: (0.0, 0.0), 2: (1000.0, 1000.0)}
    pos = place_new_node(existing, neighbor_ids=[1])
    assert abs(pos[0]) < 400 and abs(pos[1]) < 400


def test_layout3d_deterministic():
    G = nx.DiGraph([(1, 2), (2, 3), (3, 1), (3, 4)])
    a = layout3d(G, seed=7)
    b = layout3d(G, seed=7)
    c = layout3d(G, seed=8)
    assert a == b
    assert a != c
    assert set(a) == {1, 2, 3, 4}
