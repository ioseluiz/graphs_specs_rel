"""Contenido del manual integrado: índice JSON + temas en Markdown dentro de assets/help."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from config.settings import ASSETS_DIR
from models.relation_normalizer import search_key

HELP_DIR = ASSETS_DIR / "help"
_IMG_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


@dataclass
class HelpTopic:
    id: str
    title: str
    file: str
    markdown: str

    @property
    def search_text(self) -> str:
        return search_key(f"{self.title} {self.markdown}")

    def images(self) -> list[str]:
        return _IMG_RE.findall(self.markdown)


class HelpContent:
    def __init__(self, folder: Path | None = None) -> None:
        self.folder = folder if folder is not None else HELP_DIR
        self.topics: list[HelpTopic] = []
        self.error: str | None = None
        self.load()

    def load(self) -> None:
        self.topics, self.error = [], None
        index = self.folder / "index.json"
        if not index.exists():
            self.error = f"No se encontró el manual en {self.folder}."
            return
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            self.error = f"El índice del manual no se pudo leer: {exc}"
            return
        for entry in data.get("topics", []):
            path = self.folder / entry.get("file", "")
            try:
                markdown = path.read_text(encoding="utf-8")
            except OSError:
                markdown = f"# {entry.get('title', '')}\n\n*Este tema aún no tiene contenido ({entry.get('file')}).*"
            self.topics.append(HelpTopic(entry["id"], entry.get("title", entry["id"]), entry.get("file", ""), markdown))

    @property
    def available(self) -> bool:
        return bool(self.topics)

    def topic(self, topic_id: str) -> HelpTopic | None:
        return next((t for t in self.topics if t.id == topic_id), None)

    def index_of(self, topic_id: str) -> int:
        return next((i for i, t in enumerate(self.topics) if t.id == topic_id), -1)

    def search(self, text: str) -> list[HelpTopic]:
        """Temas cuyo título o contenido contienen todas las palabras (sin acentos ni mayúsculas)."""
        tokens = search_key(text).split()
        if not tokens:
            return list(self.topics)
        out = []
        for t in self.topics:
            hay = t.search_text
            if all(tok in hay for tok in tokens):
                out.append(t)
        return out

    def missing_images(self) -> list[tuple[str, str]]:
        missing = []
        for t in self.topics:
            for rel in t.images():
                if not (self.folder / rel).exists():
                    missing.append((t.id, rel))
        return missing
