"""Genera assets/data/masterformat_2020.sqlite a partir del Excel MasterFormat del cliente.

Uso: python scripts/build_master_catalog.py [info/master_format_data.xlsx] [salida.sqlite]
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from config.settings import MASTER_CATALOG_PATH  # noqa: E402
from models.master_catalog import (  # noqa: E402
    apply_title_overrides,
    build_records,
    classify,
    load_category_rules,
    load_source_rows,
    load_title_overrides,
    write_catalog_sqlite,
)

OVERRIDES = Path(__file__).resolve().parent / "title_overrides.csv"
RULES = Path(__file__).resolve().parent / "category_rules.csv"


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "info" / "master_format_data.xlsx"
    target = Path(sys.argv[2]) if len(sys.argv) > 2 else MASTER_CATALOG_PATH
    rows = load_source_rows(source)
    records = build_records(rows)
    overrides = load_title_overrides(OVERRIDES)
    records = apply_title_overrides(records, overrides)
    rules = load_category_rules(RULES)
    records = classify(records, rules, overwrite=True)
    count = write_catalog_sqlite(records, target, {"edition": "2020", "source": source.name,
                                                   "overrides": str(len(overrides)), "rules": str(len(rules))})
    levels = Counter(r.level for r in records)
    review = sum(1 for r in records if r.quality == "review")
    categories = Counter(r.category or "(sin clasificar)" for r in records)
    print(f"{count} secciones escritas en {target}")
    print(f"  filas fuente: {len(rows)} · niveles: {dict(sorted(levels.items()))} · "
          f"correcciones manuales: {len(overrides)} · por verificar: {review}")
    print(f"  clasificación ({len(rules)} reglas): " + ", ".join(f"{k}: {v}" for k, v in categories.most_common()))


if __name__ == "__main__":
    main()
