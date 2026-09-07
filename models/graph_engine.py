"""Grafo dirigido en memoria (networkx) espejo del proyecto, con análisis."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Iterable

import networkx as nx

from models.entities import Relation, RelationKind, Section


@dataclass
class DegreeInfo:
    section_id: int
    out_degree: int   # a cuántas secciones hace referencia
    in_degree: int    # por cuántas es referenciada

    @property
    def total(self) -> int:
        return self.out_degree + self.in_degree


@dataclass
class ImpactResult:
    section_id: int
    affected: dict[int, int] = field(default_factory=dict)    # quienes la referencian (transitivo): id -> nivel
    depends_on: dict[int, int] = field(default_factory=dict)  # a quienes referencia (transitivo): id -> nivel

    @property
    def all_ids(self) -> set[int]:
        return {self.section_id, *self.affected, *self.depends_on}


class GraphEngine:
    """Nodo = section_id. 'ref' -> arista source->target; 'mutual' -> ambas direcciones."""

    def __init__(self) -> None:
        self.G = nx.DiGraph()

    # ------------------------------------------------------------------ mantenimiento
    def rebuild(self, sections: Iterable[Section], relations: Iterable[Relation]) -> None:
        self.G.clear()
        for s in sections:
            self.add_section(s)
        for r in relations:
            self.add_relation(r)

    def add_section(self, section: Section) -> None:
        self.G.add_node(section.id, code=section.code, title=section.title,
                        category_id=section.category_id)

    def update_section(self, section: Section) -> None:
        if section.id in self.G:
            self.G.nodes[section.id].update(code=section.code, title=section.title,
                                            category_id=section.category_id)

    def remove_section(self, section_id: int) -> None:
        if section_id in self.G:
            self.G.remove_node(section_id)

    def add_relation(self, rel: Relation) -> None:
        self.G.add_edge(rel.source_id, rel.target_id, rid=rel.id, kind=rel.kind.value)
        if rel.kind is RelationKind.MUTUAL:
            self.G.add_edge(rel.target_id, rel.source_id, rid=rel.id, kind=rel.kind.value)

    def remove_relation(self, rel: Relation) -> None:
        for u, v in ((rel.source_id, rel.target_id), (rel.target_id, rel.source_id)):
            if self.G.has_edge(u, v) and self.G.edges[u, v].get("rid") == rel.id:
                self.G.remove_edge(u, v)

    def replace_relation(self, old: Relation, new: Relation) -> None:
        self.remove_relation(old)
        self.add_relation(new)

    # ------------------------------------------------------------------ análisis
    def orphans(self) -> list[int]:
        return sorted(n for n, d in self.G.degree() if d == 0)

    def degrees(self) -> list[DegreeInfo]:
        infos = [
            DegreeInfo(n, self.G.out_degree(n), self.G.in_degree(n)) for n in self.G.nodes
        ]
        infos.sort(key=lambda i: (-i.total, -i.in_degree, i.section_id))
        return infos

    def impact(self, section_id: int) -> ImpactResult:
        result = ImpactResult(section_id)
        if section_id not in self.G:
            return result
        # Afectadas: quienes llegan a S (predecesores transitivos) -> distancias en el grafo inverso.
        reverse = self.G.reverse(copy=False)
        for node, level in nx.single_source_shortest_path_length(reverse, section_id).items():
            if node != section_id:
                result.affected[node] = level
        for node, level in nx.single_source_shortest_path_length(self.G, section_id).items():
            if node != section_id:
                result.depends_on[node] = level
        return result

    def components(self) -> list[set[int]]:
        comps = [set(c) for c in nx.weakly_connected_components(self.G)]
        comps.sort(key=lambda c: (-len(c), min(c)))
        return comps

    def neighbors(self, section_id: int) -> set[int]:
        if section_id not in self.G:
            return set()
        return set(self.G.successors(section_id)) | set(self.G.predecessors(section_id))

    def relation_ids_touching(self, section_ids: set[int]) -> set[int]:
        return {
            data["rid"] for u, v, data in self.G.edges(data=True)
            if u in section_ids and v in section_ids
        }

    def graph_hash(self) -> str:
        h = hashlib.sha1()
        for n in sorted(self.G.nodes):
            h.update(f"n{n};".encode())
        for u, v in sorted(self.G.edges):
            h.update(f"e{u}>{v};".encode())
        return h.hexdigest()

    @property
    def node_count(self) -> int:
        return self.G.number_of_nodes()

    @property
    def edge_count(self) -> int:
        return len({d["rid"] for _, _, d in self.G.edges(data=True)})
