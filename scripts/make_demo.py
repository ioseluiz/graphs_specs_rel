"""Genera un proyecto de demostración con las secciones del ejemplo del cliente.

Uso: python scripts/make_demo.py [ruta/salida.specrel]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PyQt6.QtCore import QCoreApplication  # noqa: E402

from models.entities import UiKind  # noqa: E402
from models.project_model import ProjectModel  # noqa: E402

# (código, título, categoría, x, y) — disposición aproximada de la captura del cliente
SECTIONS = [
    ("01 35 13", "Requisito de Proyecto", "Contractual", 0, 300),
    ("09 97 13", "Recubr. Control", "Técnica / constructiva", 220, 340),
    ("31 11 00", "Limpieza y desbroce", "Técnica / constructiva", 360, 190),
    ("01 35 29", "Req. de Seguridad", "Auxiliar / apoyo", 560, 160),
    ("01 57 20", "Protección ambiental", "Auxiliar / apoyo", 700, 100),
    ("01 31 19", "Conferencia inicial", "Contractual", 820, 220),
    ("4.28.33", "Sitio de obra", "Otra", 1000, 40),
    ("4.28.59", "Pago Contratista", "Otra", 1060, 260),
    ("01 13 00", "Requisito de Contrato", "Contractual", 860, 420),
    ("4.28.48", "Cant. estimada", "Otra", 1080, 460),
    ("31 23 00", "Excavación", "Técnica / constructiva", 1260, 240),
    ("03 30 53", "Concreto Vac. sitio", "Técnica / constructiva", 1300, 100),
    ("32 11 24", "Capabase agregado", "Técnica / constructiva", 1560, 160),
    ("31 05 19", "Geosintéticos", "Técnica / constructiva", 1620, 350),
    ("31 33 23", "Estabilización Roca", "Técnica / constructiva", 560, 660),
    ("01 50 00", "Inst. y Control temporal", "Auxiliar / apoyo", 1000, 650),
    ("33 40 00", "Drenaje Pluvial", "Técnica / constructiva", 1420, 700),
]

RELATIONS = [
    ("31 33 23", UiKind.REFERENCES, "01 35 13"),
    ("31 33 23", UiKind.REFERENCES, "09 97 13"),
    ("31 33 23", UiKind.REFERENCES, "31 11 00"),
    ("31 33 23", UiKind.REFERENCES, "01 35 29"),
    ("31 33 23", UiKind.REFERENCES, "01 57 20"),
    ("31 33 23", UiKind.REFERENCES, "01 31 19"),
    ("31 33 23", UiKind.REFERENCES, "4.28.33"),
    ("31 33 23", UiKind.REFERENCES, "4.28.59"),
    ("31 33 23", UiKind.REFERENCES, "01 13 00"),
    ("01 13 00", UiKind.REFERENCES, "4.28.48"),
    ("01 13 00", UiKind.REFERENCES, "01 35 29"),
    ("33 40 00", UiKind.REFERENCES, "31 23 00"),
    ("33 40 00", UiKind.REFERENCES, "03 30 53"),
    ("33 40 00", UiKind.REFERENCES, "32 11 24"),
    ("33 40 00", UiKind.REFERENCES, "31 05 19"),
    ("33 40 00", UiKind.REFERENCES, "01 50 00"),
    ("01 50 00", UiKind.REFERENCED_BY, "33 40 00"),  # duplicado inverso: se ignora en el script
    ("01 35 29", UiKind.REFERENCES, "01 57 20"),
    ("01 57 20", UiKind.REFERENCES, "01 35 29"),  # sentido contrario: dos flechas entre el mismo par
]


def build(path: Path | None) -> ProjectModel:
    model = ProjectModel()
    model.new_project(path, "CC-25-01", "Proyecto de demostración")
    cats = {c.name: c.id for c in model.categories()}
    for code, title, cat, x, y in SECTIONS:
        model.add_section(code, title, cats.get(cat), (float(x), float(y)))
    model.move_nodes({s.id: (model.position(s.id).x, model.position(s.id).y) for s in model.sections()},
                     pinned=True)
    for a, kind, b in RELATIONS:
        sa, sb = model.section_by_code(a), model.section_by_code(b)
        try:
            model.add_relation(sa.id, kind, sb.id)
        except Exception:  # noqa: BLE001 - duplicados intencionales del ejemplo
            pass
    return model


def main() -> None:
    QCoreApplication.instance() or QCoreApplication(sys.argv)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "demo.specrel"
    if out.exists():
        out.unlink()
    model = build(out)
    print(f"Proyecto demo: {out} ({len(model.sections())} secciones, {len(model.relations())} relaciones)")
    model.close()


if __name__ == "__main__":
    main()
