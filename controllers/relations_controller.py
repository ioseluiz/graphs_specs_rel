"""Controlador de la entrada y la tabla de relaciones."""
from __future__ import annotations

from PyQt6.QtCore import QObject
from PyQt6.QtWidgets import QMessageBox

from models.entities import RelationKind, Section, UiKind
from models.master_catalog import normalize_code
from models.project_model import ProjectModel
from models.relation_normalizer import DuplicateRelationError, SelfRelationError, denormalize, split_code_title
from models.relations_table_model import COL_A, COL_B, COL_KIND, RelationsTableModel
from views.components.section_editor_dialog import SectionEditorDialog
from views.main_window import MainWindow


class RelationsController(QObject):
    def __init__(self, project: ProjectModel, window: MainWindow, table_model: RelationsTableModel,
                 parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project = project
        self.window = window
        self.table_model = table_model
        window.entry.addRequested.connect(self.on_add_requested)
        window.entry.customSectionRequested.connect(self.on_custom_section_requested)
        table_model.editRequested.connect(self.on_table_edit)
        window.table_view.editRequested.connect(window.table_view.edit_relation)
        window.table_view.invertRequested.connect(self.invert)
        window.table_view.deleteRequested.connect(self.delete_relation)

    # ------------------------------------------------------------------ utilidades
    def describe(self, rel) -> str:
        sa, sb = self.project.section(rel.source_id), self.project.section(rel.target_id)
        arrow = "↔" if rel.kind is RelationKind.MUTUAL else "→"
        return f"{sa.code if sa else '?'} {arrow} {sb.code if sb else '?'}"

    def _announce_change(self, before: str, relation_id: int) -> None:
        rel = self.project.relation(relation_id)
        if rel is None:
            return
        after = self.describe(rel)
        if after != before:
            self.window.show_status(f"Relación actualizada: {after}  (antes {before})", 8000)
        self.window.table_view.flash_relation(relation_id)

    # ------------------------------------------------------------------ resolución de secciones
    def resolve_section(self, value, near: list[int] | None = None) -> int | None:
        """Convierte el valor de un picker (id, ('catalog', key) o texto) en el id de una sección."""
        if value is None:
            return None
        if isinstance(value, int):
            return value if self.project.section(value) else None
        if isinstance(value, tuple) and len(value) == 2 and value[0] == "catalog":
            try:
                section, created = self.project.create_section_from_catalog(value[1], near or [])
            except ValueError as exc:
                QMessageBox.warning(self.window, "Sección", str(exc))
                return None
            if created:
                self.window.show_status(
                    f"Sección {section.label} agregada desde el catálogo MasterFormat.", 7000)
            return section.id
        text = str(value).strip()
        if not text:
            return None
        try:
            section, created = self.project.get_or_create_section(text, near or [])
        except ValueError as exc:
            QMessageBox.warning(self.window, "Sección", str(exc))
            return None
        if created:
            self.window.show_status(f"Sección {section.code} creada.", 7000)
        return section.id

    # ------------------------------------------------------------------ sección personalizada
    def on_custom_section_requested(self, which: str, typed: str) -> None:
        section = self.create_custom_section(typed)
        if section is not None:
            self.window.entry.set_picker_section(which, section.id, section.label)
            self.window.entry.set_hint(f"Sección {section.label} lista para relacionar.")

    def create_custom_section(self, typed: str = "") -> Section | None:
        """Diálogo para códigos fuera de MasterFormat; propone la entrada del catálogo si el código coincide."""
        code, title = split_code_title(typed) if typed else ("", "")
        record = self.project.master_record(normalize_code(code)) if code else None
        suggestion = None
        if record is not None:
            suggestion = (record.code, record.title)
        dialog = SectionEditorDialog(self.project.categories(), self.window, code=code, title=title,
                                     is_new=True, suggestion=suggestion,
                                     statuses=self.project.statuses(), responsibles=self.project.responsibles())
        if dialog.exec() != dialog.DialogCode.Accepted:
            return None
        code, title, category_id, notes = dialog.values()
        fill, border = dialog.colors()
        status_id, progress, responsible_ids = dialog.extras()
        canonical = normalize_code(code)
        existing = self.project.section_by_code(canonical)
        if existing is not None:
            self.window.show_status(f"La sección {existing.label} ya existía en el proyecto.")
            return existing
        section = self.project.add_section(canonical, title, category_id)
        self.project.update_section(section.id, canonical, title, category_id, notes, fill, border,
                                    status_id, progress)
        if responsible_ids:
            self.project.set_section_responsibles(section.id, responsible_ids)
        return self.project.section(section.id)

    # ------------------------------------------------------------------ alta
    def on_add_requested(self, a_value, kind: UiKind, b_value) -> None:
        a_id = self.resolve_section(a_value)
        if a_id is None:
            self.window.entry.set_hint("Elija la Sección A de la lista.", warning=True)
            return
        b_id = self.resolve_section(b_value, near=[a_id])
        if b_id is None:
            self.window.entry.set_hint("Elija la Sección B de la lista.", warning=True)
            return
        if self.add_relation(a_id, kind, b_id):
            self.window.entry.clear_inputs()

    def add_relation(self, a_id: int, kind: UiKind, b_id: int) -> bool:
        try:
            rel = self.project.add_relation(a_id, kind, b_id)
        except SelfRelationError:
            QMessageBox.warning(self.window, "Relación", "Una sección no puede relacionarse consigo misma.")
            return False
        except DuplicateRelationError as exc:
            return self._handle_duplicate(exc, a_id, kind, b_id)
        self.window.table_view.select_relations([rel.id])
        return True

    def _handle_duplicate(self, exc: DuplicateRelationError, a_id: int, kind: UiKind, b_id: int) -> bool:
        existing = exc.existing
        sa = self.project.section(existing.source_id)
        sb = self.project.section(existing.target_id)
        label_a = sa.code if sa else "?"
        label_b = sb.code if sb else "?"
        attempted_kind = exc.attempted[2]
        if existing.kind is RelationKind.MUTUAL:
            QMessageBox.information(
                self.window, "Relación duplicada",
                f"Ya existe una referencia mutua entre {label_a} y {label_b}.")
            self.window.table_view.select_relations([existing.id])
            return False
        same_direction = (exc.attempted[0], exc.attempted[1]) == (existing.source_id, existing.target_id)
        if attempted_kind is RelationKind.REF and same_direction:
            QMessageBox.information(
                self.window, "Relación duplicada",
                f"La relación {label_a} → {label_b} ya está registrada.")
            self.window.table_view.select_relations([existing.id])
            return False
        answer = QMessageBox.question(
            self.window, "Relación existente",
            f"Ya existe la relación {label_a} → {label_b}.\n\n"
            "¿Desea convertirla en una referencia mutua ↔?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            rel = self.project.make_mutual(existing.id)
            self.window.table_view.select_relations([rel.id])
            self.window.show_status(f"Relación {label_a} ↔ {label_b} convertida en mutua.")
            return True
        return False

    # ------------------------------------------------------------------ edición desde la tabla
    def on_table_edit(self, relation_id: int, column: int, value) -> None:
        rel = self.project.relation(relation_id)
        if rel is None:
            return
        a_id, ui_kind, b_id = denormalize(rel)
        if column == COL_A:
            new_a = self.resolve_section(value, near=[b_id])
            if new_a is None:
                return
            a_id = new_a
        elif column == COL_B:
            new_b = self.resolve_section(value, near=[a_id])
            if new_b is None:
                return
            b_id = new_b
        elif column == COL_KIND:
            if value == "invert":
                self.invert(relation_id)
                return
            ui_kind = value
        before = self.describe(rel)
        if self.update_relation(relation_id, a_id, ui_kind, b_id):
            self._announce_change(before, relation_id)

    def update_relation(self, relation_id: int, a_id: int, ui_kind: UiKind, b_id: int) -> bool:
        try:
            self.project.update_relation(relation_id, a_id, ui_kind, b_id)
            return True
        except SelfRelationError:
            QMessageBox.warning(self.window, "Relación", "Una sección no puede relacionarse consigo misma.")
        except DuplicateRelationError as exc:
            sa = self.project.section(exc.existing.source_id)
            sb = self.project.section(exc.existing.target_id)
            QMessageBox.information(
                self.window, "Relación duplicada",
                f"Ya existe otra relación entre {sa.code if sa else '?'} y {sb.code if sb else '?'}.")
        return False

    def set_kind(self, relation_id: int, ui_kind: UiKind) -> None:
        rel = self.project.relation(relation_id)
        if rel is None:
            return
        a_id, _, b_id = denormalize(rel)
        before = self.describe(rel)
        if self.update_relation(relation_id, a_id, ui_kind, b_id):
            self._announce_change(before, relation_id)

    def set_direction(self, relation_id: int, source_id: int, target_id: int) -> None:
        """Convierte en dirigida con el sentido indicado (útil desde una mutua)."""
        rel = self.project.relation(relation_id)
        if rel is None:
            return
        before = self.describe(rel)
        if self.update_relation(relation_id, source_id, UiKind.REFERENCES, target_id):
            self._announce_change(before, relation_id)

    def invert(self, relation_id: int) -> None:
        rel = self.project.relation(relation_id)
        if rel is None:
            return
        if rel.kind is RelationKind.MUTUAL:
            self.window.show_status("Una referencia mutua no tiene dirección que invertir; cambie el tipo "
                                    "desde el menú de la flecha o la celda Relación.", 6000)
            return
        before = self.describe(rel)
        if self.update_relation(relation_id, rel.target_id, UiKind.REFERENCES, rel.source_id):
            self._announce_change(before, relation_id)

    # ------------------------------------------------------------------ baja
    def delete_relation(self, relation_id: int, confirm: bool = True) -> bool:
        rel = self.project.relation(relation_id)
        if rel is None:
            return False
        if confirm:
            sa, sb = self.project.section(rel.source_id), self.project.section(rel.target_id)
            arrow = "↔" if rel.kind is RelationKind.MUTUAL else "→"
            answer = QMessageBox.question(
                self.window, "Eliminar relación",
                f"¿Eliminar la relación {sa.code if sa else '?'} {arrow} {sb.code if sb else '?'}?")
            if answer != QMessageBox.StandardButton.Yes:
                return False
        self.project.remove_relation(relation_id)
        return True

    def delete_relations(self, relation_ids: list[int]) -> None:
        ids = [rid for rid in relation_ids if self.project.relation(rid)]
        if not ids:
            return
        if len(ids) == 1:
            self.delete_relation(ids[0])
            return
        answer = QMessageBox.question(self.window, "Eliminar relaciones",
                                      f"¿Eliminar {len(ids)} relaciones seleccionadas?")
        if answer == QMessageBox.StandardButton.Yes:
            for rid in ids:
                self.project.remove_relation(rid)
