"""Genera assets/data/clausulas.sqlite a partir del Excel de cláusulas del cliente.

Uso: python scripts/build_clauses_catalog.py [info/clausulas.xlsx] [salida.sqlite]
El Excel tiene las columnas Numeración | Título | Tipo (Cláusula / Subcláusula).
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import CLAUSE_CATALOG_PATH  # noqa: E402
from models.clause_catalog import (  # noqa: E402
    build_clause_records,
    clauses_root_label,
    load_clause_rows,
    write_clauses_sqlite,
)


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "info" / "clausulas.xlsx"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else CLAUSE_CATALOG_PATH
    rows = load_clause_rows(source)
    records, stats = build_clause_records(rows)
    count = write_clauses_sqlite(records, target, {"source": source.name, "edition": "cliente"})
    levels = Counter(r.level for r in records)
    orphans = sum(1 for r in records if r.level == 2 and not any(p.code_key == r.parent_key for p in records))
    print(f"{count} cláusulas escritas en {target}  ({clauses_root_label(records)})")
    print(f"  filas fuente: {stats['rows']} · cláusulas: {levels.get(1, 0)} · subcláusulas: {levels.get(2, 0)} · "
          f"títulos limpiados (número de página): {stats['cleaned_titles']} · duplicados: {stats['duplicates']} · "
          f"omitidas: {stats['skipped']} · subcláusulas sin cláusula padre: {orphans}")


if __name__ == "__main__":
    main()
