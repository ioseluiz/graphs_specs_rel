"""Modelo de autocompletado de secciones: secciones del proyecto ∪ catálogo maestro MasterFormat.

Rendimiento: el modelo fuente ya está ordenado (secciones del proyecto primero, luego catálogo por
clave), así el proxy solo filtra y nunca ordena en Python (ordenar 8.800 filas costaba ~300 ms
por tecla). Para consultas numéricas se aplica una regla de dos pasadas: si alguna clave empieza
por los dígitos escritos se muestran solo esas; si ninguna, las que los contienen.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QSortFilterProxyModel, Qt

from config import palette
from models.relation_normalizer import code_key, search_key

ROLE_SECTION_ID = Qt.ItemDataRole.UserRole + 1
ROLE_CODE = Qt.ItemDataRole.UserRole + 2
ROLE_TITLE = Qt.ItemDataRole.UserRole + 3
ROLE_KIND = Qt.ItemDataRole.UserRole + 4       # 'section' | 'catalog'
ROLE_FILL = Qt.ItemDataRole.UserRole + 5
ROLE_BORDER = Qt.ItemDataRole.UserRole + 6
ROLE_SEARCH = Qt.ItemDataRole.UserRole + 7
ROLE_CODE_KEY = Qt.ItemDataRole.UserRole + 8


@dataclass
class CompleterEntry:
    kind: str
    section_id: int | None
    code: str
    code_key: str
    title: str
    fill: str
    border: str
    search: str = field(default="")

    def __post_init__(self) -> None:
        if not self.search:
            self.search = f"{self.code_key.lower()} {search_key(self.code)} {search_key(self.title)}"

    @property
    def label(self) -> str:
        return f"{self.code} - {self.title}" if self.title.strip() else self.code


class SectionCompleterModel(QAbstractListModel):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._entries: list[CompleterEntry] = []
        self._by_key: dict[str, int] = {}
        self.rebuilds = 0  # diagnóstico / pruebas

    def set_entries(self, entries: list[CompleterEntry]) -> None:
        self.beginResetModel()
        self._entries = sorted(entries, key=lambda e: (e.kind != "section", e.code_key))
        self._by_key = {e.code_key: i for i, e in enumerate(self._entries)}
        self.endResetModel()

    def rebuild(self, project_model) -> None:
        self.rebuilds += 1
        entries: list[CompleterEntry] = []
        present: set[str] = set()
        for s in project_model.sections():
            fill, border = project_model.section_colors(s)
            entries.append(CompleterEntry("section", s.id, s.code, s.code_key, s.title, fill, border))
            present.add(s.code_key)
        for e in project_model.catalog():  # catálogo adicional del proyecto
            if e.code_key in present:
                continue
            present.add(e.code_key)
            entries.append(CompleterEntry(
                "catalog", None, e.code, e.code_key, e.title, palette.SURFACE_ALT, palette.BORDER))
        # Colores por clasificación: categorías del proyecto por nombre, o semilla si no existen aún.
        colors: dict[str, tuple[str, str]] = {
            s.name.casefold(): (s.fill, s.border) for s in palette.DEFAULT_CATEGORIES}
        for c in project_model.categories():
            colors[c.name.casefold()] = (c.fill_color, c.border_color)
        master = project_model.master
        neutral = (palette.SURFACE_ALT, palette.BORDER)
        for r in master.all():  # catálogo maestro MasterFormat
            if r.code_key in present:
                continue
            category = master.effective_category(r)
            fill, border = colors.get((category or "").casefold(), neutral)
            entries.append(CompleterEntry("catalog", None, r.code, r.code_key, r.title, fill, border,
                                          search=r.search))
        self.set_entries(entries)

    def entries(self) -> list[CompleterEntry]:
        return self._entries

    def entry(self, row: int) -> CompleterEntry | None:
        return self._entries[row] if 0 <= row < len(self._entries) else None

    def row_for_code(self, code: str) -> int:
        return self._by_key.get(code_key(code), -1)

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:  # noqa: N802
        return 0 if parent.isValid() else len(self._entries)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        e = self._entries[index.row()]
        if role in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole):
            return e.label
        if role == ROLE_SECTION_ID:
            return e.section_id
        if role == ROLE_CODE:
            return e.code
        if role == ROLE_TITLE:
            return e.title
        if role == ROLE_KIND:
            return e.kind
        if role == ROLE_FILL:
            return e.fill
        if role == ROLE_BORDER:
            return e.border
        if role == ROLE_SEARCH:
            return e.search
        if role == ROLE_CODE_KEY:
            return e.code_key
        return None


def build_query(text: str) -> tuple[list[str], str]:
    """Devuelve (tokens, dígitos). Si el texto es solo numérico se compara compactado contra la clave."""
    normalized = search_key(text)
    digits = "".join(ch for ch in normalized if ch.isdigit())
    only_digits = bool(digits) and all(ch.isdigit() or ch in " .-" for ch in normalized.strip())
    return ([] if only_digits else normalized.split()), (digits if only_digits else "")


def matches_query(search: str, key: str, tokens: list[str], digits: str) -> bool:
    if digits:
        k = key.lower()
        return k.startswith(digits) or digits in k
    return all(tok in search for tok in tokens)


class SectionFilterProxy(QSortFilterProxyModel):
    """Filtra por tokens (sin acentos) sobre código y título: '31 exc' -> '31 23 00 Excavación'.

    Un token compuesto solo por dígitos y espacios se compara compactado contra la clave
    ('0330 00' encuentra '03 30 00'). El orden es el del modelo fuente (proyecto primero).
    """

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tokens: list[str] = []
        self._digits: str = ""
        self._prefix_only = False
        self.setDynamicSortFilter(False)

    @property
    def query(self) -> tuple[list[str], str]:
        return list(self._tokens), self._digits

    def setSourceModel(self, model) -> None:  # noqa: N802
        super().setSourceModel(model)
        # Tras reconstruir el modelo fuente la regla de prefijo puede cambiar (nuevas secciones).
        model.modelReset.connect(self._on_source_reset)

    def _on_source_reset(self) -> None:
        if self._digits:
            prefix_only = self._any_prefix_match(self._digits)
            if prefix_only != self._prefix_only:
                self._prefix_only = prefix_only
                self.invalidateFilter()

    def set_query(self, text: str) -> None:
        tokens, new_digits = build_query(text)
        if tokens == self._tokens and new_digits == self._digits:
            return
        self._tokens, self._digits = tokens, new_digits
        self._prefix_only = bool(new_digits) and self._any_prefix_match(new_digits)
        self.invalidateFilter()

    def _any_prefix_match(self, digits: str) -> bool:
        src = self.sourceModel()
        entries = getattr(src, "entries", None)
        if callable(entries):
            return any(e.code_key.lower().startswith(digits) for e in entries())
        for row in range(src.rowCount()):
            if (src.data(src.index(row, 0), ROLE_CODE_KEY) or "").lower().startswith(digits):
                return True
        return False

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:  # noqa: N802
        if not self._tokens and not self._digits:
            return True
        src = self.sourceModel()
        entry = src.entry(source_row) if hasattr(src, "entry") else None
        if entry is not None:
            key, haystack = entry.code_key.lower(), entry.search
        else:
            idx = src.index(source_row, 0, source_parent)
            key = (src.data(idx, ROLE_CODE_KEY) or "").lower()
            haystack = src.data(idx, ROLE_SEARCH) or ""
        if self._digits:
            if self._prefix_only:
                return key.startswith(self._digits)
            return self._digits in key
        return all(tok in haystack for tok in self._tokens)
