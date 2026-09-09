from __future__ import annotations

from models.entities import Relation, RelationKind, Section
from models.graph_engine import GraphEngine


def _sec(i: int) -> Section:
    return Section(i, f"0{i} 00 00", f"0{i}0000", f"S{i}")


def _rel(i: int, s: int, t: int, kind=RelationKind.REF) -> Relation:
    return Relation(i, s, t, kind)


def build() -> GraphEngine:
    g = GraphEngine()
    # 1 -> 2 -> 3, 2 -> 4 y 4 -> 2 (dos flechas), 5 huérfana
    g.rebuild([_sec(i) for i in range(1, 6)],
              [_rel(10, 1, 2), _rel(11, 2, 3), _rel(12, 2, 4), _rel(13, 4, 2)])
    return g


def test_orphans():
    assert build().orphans() == [5]


def test_degrees_sorted_by_total():
    infos = build().degrees()
    assert infos[0].section_id == 2
    two = infos[0]
    assert two.in_degree == 2 and two.out_degree == 2  # 1->2, 4->2 ; 2->3, 2->4


def test_impact_levels():
    r = build().impact(3)
    assert r.affected == {2: 1, 1: 2, 4: 2}
    assert r.depends_on == {}
    r2 = build().impact(1)
    assert r2.depends_on == {2: 1, 3: 2, 4: 2}
    assert r2.affected == {}


def test_components():
    comps = build().components()
    assert len(comps) == 2
    assert comps[0] == {1, 2, 3, 4}


def test_remove_relation_only_removes_own_edges():
    g = build()
    g.remove_relation(_rel(12, 2, 4))
    assert not g.G.has_edge(2, 4) and g.G.has_edge(4, 2)   # la flecha inversa sigue
    assert g.G.has_edge(2, 3)
    assert g.edge_count == 3


def test_hash_stable_and_sensitive():
    a, b = build(), build()
    assert a.graph_hash() == b.graph_hash()
    b.add_relation(_rel(14, 5, 1))
    assert a.graph_hash() != b.graph_hash()
