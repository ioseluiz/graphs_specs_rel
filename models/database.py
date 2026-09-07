"""Gestión del archivo de proyecto SQLite (.specrel)."""
from __future__ import annotations

import shutil
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from config.palette import DEFAULT_CATEGORIES, DEFAULT_RESPONSIBLES, DEFAULT_STATUSES
from config.settings import APP_VERSION
from models.schema import MIGRATIONS, SCHEMA_SQL, SCHEMA_VERSION

BACKUP_COPIES = 3
BUSY_TIMEOUT_MS = 1500     # antes 5000: con OneDrive bloqueando, la interfaz esperaba 5 s por escritura
LOCK_RETRY_DELAY = 0.3     # segundos entre el primer intento de BEGIN y el reintento


class ProjectFileError(Exception):
    """El archivo no es un proyecto válido o no se puede abrir."""


class ProjectLockedError(ProjectFileError):
    """El archivo está bloqueado (p. ej. sincronización de OneDrive en curso)."""


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


class ProjectDatabase:
    """Conexión a un archivo de proyecto. `path=None` crea una base en memoria (tests)."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path: Path | None = Path(path) if path is not None else None
        self.conn: sqlite3.Connection = self._connect()
        self._configure()

    # ------------------------------------------------------------------ apertura
    def _connect(self) -> sqlite3.Connection:
        target = ":memory:" if self.path is None else str(self.path)
        try:
            conn = sqlite3.connect(target, timeout=BUSY_TIMEOUT_MS / 1000.0, isolation_level=None)
        except sqlite3.OperationalError as exc:
            raise ProjectFileError(f"No se pudo abrir el archivo: {exc}") from exc
        conn.row_factory = sqlite3.Row
        return conn

    def _configure(self) -> None:
        try:
            self.conn.execute("PRAGMA foreign_keys = ON")
            self.conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            if self.path is not None:
                # DELETE en lugar de WAL: OneDrive no sincroniza bien -wal/-shm.
                self.conn.execute("PRAGMA journal_mode = DELETE")
                # NORMAL: seguro ante cierres de la aplicación (solo un corte de energía podría perder
                # la última transacción) y evita un fsync extra por cada cambio.
                self.conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.DatabaseError as exc:
            self._raise_for(exc)

    @classmethod
    def create(cls, path: Path | str, code: str = "", name: str = "") -> "ProjectDatabase":
        path = Path(path)
        if path.exists():
            path.unlink()
        db = cls(path)
        db.initialize_schema()
        db.conn.execute(
            "UPDATE project SET code = ?, name = ?, updated_at = ? WHERE id = 1",
            (code, name, now_iso()),
        )
        return db

    @classmethod
    def open(cls, path: Path | str) -> "ProjectDatabase":
        path = Path(path)
        if not path.exists():
            raise ProjectFileError(f"El archivo no existe: {path}")
        cls._rotate_backups(path)
        db = cls(path)
        db.verify()
        db.migrate()
        return db

    @staticmethod
    def _rotate_backups(path: Path) -> None:
        try:
            for i in range(BACKUP_COPIES - 1, 0, -1):
                src = path.with_name(f"{path.name}.bak{i}")
                if src.exists():
                    shutil.copy2(src, path.with_name(f"{path.name}.bak{i + 1}"))
            shutil.copy2(path, path.with_name(f"{path.name}.bak1"))
        except OSError:
            pass  # el backup es una conveniencia; no debe impedir abrir el proyecto

    def verify(self) -> None:
        try:
            row = self.conn.execute("PRAGMA integrity_check").fetchone()
            if row is None or row[0] != "ok":
                raise ProjectFileError("El archivo está dañado (integrity_check falló).")
            tables = {r[0] for r in self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'")}
        except sqlite3.DatabaseError as exc:
            self._raise_for(exc)
        if "project" not in tables or "sections" not in tables:
            raise ProjectFileError("El archivo no es un proyecto SpecRel válido.")

    def _raise_for(self, exc: sqlite3.DatabaseError) -> None:
        message = str(exc).lower()
        if "locked" in message or "busy" in message:
            raise ProjectLockedError(
                "El archivo está bloqueado por otro proceso (posiblemente OneDrive). "
                "Espere a que termine la sincronización e intente de nuevo."
            ) from exc
        if "not a database" in message or "malformed" in message:
            raise ProjectFileError("El archivo no es una base de datos SQLite válida.") from exc
        raise ProjectFileError(str(exc)) from exc

    # ------------------------------------------------------------------ esquema
    def initialize_schema(self) -> None:
        # executescript hace COMMIT implícito: se ejecuta fuera de la transacción.
        self.conn.executescript(SCHEMA_SQL)
        self.conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        with self.transaction():
            ts = now_iso()
            self.conn.execute(
                "INSERT OR IGNORE INTO project (id, code, name, created_at, updated_at, app_version) "
                "VALUES (1, '', '', ?, ?, ?)",
                (ts, ts, APP_VERSION),
            )
            self._seed_defaults()

    def _seed_defaults(self) -> None:
        """Inserta las listas semilla (categorías, estatus, responsables) cuando están vacías."""
        if self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0] == 0:
            for order, seed in enumerate(DEFAULT_CATEGORIES):
                self.conn.execute(
                    "INSERT INTO categories (name, fill_color, border_color, sort_order, is_default) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (seed.name, seed.fill, seed.border, order, int(seed.is_default)),
                )
        if self.conn.execute("SELECT COUNT(*) FROM statuses").fetchone()[0] == 0:
            for order, st in enumerate(DEFAULT_STATUSES):
                self.conn.execute(
                    "INSERT INTO statuses (name, color, sort_order, is_default) VALUES (?, ?, ?, ?)",
                    (st.name, st.color, order, int(st.is_default)),
                )
        if self.conn.execute("SELECT COUNT(*) FROM responsibles").fetchone()[0] == 0:
            for order, rs in enumerate(DEFAULT_RESPONSIBLES):
                self.conn.execute(
                    "INSERT INTO responsibles (code, name, color, sort_order) VALUES (?, ?, ?, ?)",
                    (rs.code, rs.name, rs.color, order),
                )

    def schema_version(self) -> int:
        return int(self.conn.execute("PRAGMA user_version").fetchone()[0])

    def migrate(self) -> None:
        current = self.schema_version()
        if current > SCHEMA_VERSION:
            raise ProjectFileError(
                f"El proyecto fue creado con una versión más nueva de la aplicación "
                f"(esquema {current} > {SCHEMA_VERSION})."
            )
        if current == 0:
            self.initialize_schema()
            return
        for version in range(current + 1, SCHEMA_VERSION + 1):
            with self.transaction():
                for statement in MIGRATIONS.get(version, []):
                    try:
                        self.conn.execute(statement)
                    except sqlite3.OperationalError as exc:
                        if "duplicate column name" in str(exc).lower():
                            continue  # archivo parcialmente migrado: la columna ya existe
                        raise
                self.conn.execute(f"PRAGMA user_version = {version}")
        with self.transaction():
            self._seed_defaults()  # listas nuevas en proyectos existentes (idempotente)

    # ------------------------------------------------------------------ utilidades
    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Transacción explícita (soporta anidamiento trivial vía savepoints)."""
        if self.conn.in_transaction:
            self.conn.execute("SAVEPOINT sp")
            try:
                yield self.conn
                self.conn.execute("RELEASE sp")
            except Exception:
                self.conn.execute("ROLLBACK TO sp")
                self.conn.execute("RELEASE sp")
                raise
            return
        self._begin()
        try:
            yield self.conn
        except Exception:
            self._rollback()
            raise
        if self.conn.in_transaction:
            try:
                self.conn.execute("COMMIT")
            except sqlite3.OperationalError as exc:
                self._rollback()
                self._raise_for(exc)  # p. ej. "database is locked" -> ProjectLockedError

    def _begin(self) -> None:
        """BEGIN IMMEDIATE con un reintento breve si el archivo está bloqueado (OneDrive)."""
        for attempt in range(2):
            try:
                self.conn.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as exc:
                message = str(exc).lower()
                if attempt == 0 and ("locked" in message or "busy" in message):
                    time.sleep(LOCK_RETRY_DELAY)
                    continue
                self._raise_for(exc)

    def _rollback(self) -> None:
        try:
            if self.conn.in_transaction:
                self.conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass

    def touch(self) -> None:
        self.conn.execute(
            "UPDATE project SET updated_at = ?, app_version = ? WHERE id = 1",
            (now_iso(), APP_VERSION),
        )

    def save_copy(self, destination: Path | str) -> None:
        destination = Path(destination)
        if self.path is not None and destination.exists():
            try:
                if destination.resolve() == self.path.resolve():
                    raise ProjectFileError("El destino es el mismo archivo del proyecto abierto.")
            except OSError:
                pass
        try:
            target = sqlite3.connect(str(destination), timeout=2.0)
        except sqlite3.Error as exc:
            raise ProjectFileError(f"No se pudo crear la copia: {exc}") from exc
        try:
            self.conn.backup(target)
        except sqlite3.Error as exc:
            self._raise_for(exc)
        finally:
            target.close()

    def close(self) -> None:
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    def __enter__(self) -> "ProjectDatabase":
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
