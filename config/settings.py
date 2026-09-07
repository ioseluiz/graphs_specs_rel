"""Configuración global de la aplicación.

Resuelve rutas (modo desarrollo y modo congelado con PyInstaller), carga el
archivo .env y expone las banderas de configuración leídas del entorno.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

APP_NAME = "SpecRel"
APP_DISPLAY_NAME = "SpecRel — Referencias cruzadas de especificaciones"
APP_VERSION = "0.2.1"
APP_STAGE = "beta"   # "" cuando salga de pruebas
APP_VERSION_LABEL = f"{APP_VERSION} ({APP_STAGE})" if APP_STAGE else APP_VERSION
APP_ORG = "ACP"
APP_USER_MODEL_ID = "acp.specrel.1_0"
GITHUB_USER = "ioseluiz"
DEVELOPER_NAME = "José Luis Muñoz"
ORGANIZATION_NAME = "Autoridad del Canal de Panamá · INICA"
RELEASE_YEAR = "2026"
PROJECT_EXTENSION = ".specrel"
PROJECT_FILE_FILTER = f"Proyecto SpecRel (*{PROJECT_EXTENSION});;Todos los archivos (*)"

# Claves QSettings
SETTINGS_RECENT_FILES = "files/recent"
SETTINGS_LAST_DIR = "files/last_dir"
SETTINGS_WINDOW_GEOMETRY = "window/geometry"
SETTINGS_WINDOW_STATE = "window/state"
SETTINGS_SPLITTER_STATE = "window/splitter"


def _resource_base() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parent.parent


BASE_DIR = _resource_base()
ASSETS_DIR = BASE_DIR / "assets"
ICONS_DIR = ASSETS_DIR / "icons"
DATA_DIR = ASSETS_DIR / "data"
STYLES_DIR = BASE_DIR / "views" / "styles"
MASTER_CATALOG_PATH = DATA_DIR / "masterformat_2020.sqlite"   # catálogo MasterFormat empaquetado
USER_CATALOG_FILENAME = "masterformat_user.sqlite"            # copia del usuario (reemplaza al empaquetado)


def appdata_dir() -> Path:
    if sys.platform == "win32":
        root = Path(os.environ.get("APPDATA", Path.home()))
    else:
        root = Path.home() / ".config"
    return root / APP_NAME


def ensure_appdata_dir() -> Path:
    path = appdata_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def user_catalog_path() -> Path:
    return appdata_dir() / USER_CATALOG_FILENAME


def category_overrides_path() -> Path:
    """Correcciones del usuario a la clasificación por defecto del catálogo."""
    return appdata_dir() / "category_overrides.json"


def catalog_edits_path() -> Path:
    """Ediciones del usuario al catálogo (títulos, secciones agregadas, ocultas)."""
    return appdata_dir() / "catalog_edits.json"


def load_environment() -> None:
    """Carga el .env: junto al ejecutable en modo congelado, o en BASE_DIR."""
    candidates = [BASE_DIR / ".env"]
    if getattr(sys, "frozen", False):
        candidates.insert(0, Path(sys.executable).resolve().parent / ".env")
    for env_path in candidates:
        if env_path.exists():
            load_dotenv(env_path)
            return


def _flag(name: str, default: str = "false") -> bool:
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def debug_mode() -> bool:
    return _flag("DEBUG_MODE")


def opengl_software() -> bool:
    return _flag("OPENGL_SOFTWARE")


def recent_files_max() -> int:
    try:
        return max(1, int(os.environ.get("RECENT_FILES_MAX", "10")))
    except ValueError:
        return 10


def default_catalog_path() -> Path | None:
    raw = os.environ.get("DEFAULT_CATALOG_PATH", "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.exists() else None
