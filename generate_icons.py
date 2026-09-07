"""Genera los iconos SVG monocromos de la barra de herramientas en assets/icons/."""
from __future__ import annotations

from pathlib import Path

ICONS_DIR = Path(__file__).parent / "assets" / "icons"
STROKE = "#1F4E79"

# Cada icono: lista de elementos SVG (viewBox 0 0 24 24, trazo 1.8, sin relleno).
ICONS: dict[str, str] = {
    "new": '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/><path d="M12 12v6M9 15h6"/>',
    "open": '<path d="M3 7h6l2 2h10v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><path d="M3 7V5a2 2 0 0 1 2-2h4l2 2"/>',
    "save": '<path d="M5 3h11l3 3v15H5z"/><path d="M8 3v6h8V3"/><rect x="8" y="14" width="8" height="5"/>',
    "close": '<circle cx="12" cy="12" r="9"/><path d="M9 9l6 6M15 9l-6 6"/>',
    "exit": '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="M16 17l5-5-5-5M21 12H9"/>',
    "connect": '<rect x="2" y="14" width="8" height="6" rx="1"/><rect x="14" y="4" width="8" height="6" rx="1"/><path d="M10 17h3v-8h1"/><path d="M12.5 8l1.5-1.5M12.5 10l1.5 1.5" transform="translate(-0.5,0)"/>',
    "section": '<path d="M7 4h10l3 3v0l-3 3H7L4 7z" transform="translate(0,4)"/><path d="M9 11h6"/>',
    "delete": '<path d="M4 7h16"/><path d="M10 11v6M14 11v6"/><path d="M6 7l1 13h10l1-13"/><path d="M9 7V4h6v3"/>',
    "fit": '<path d="M4 9V4h5M15 4h5v5M20 15v5h-5M9 20H4v-5"/><rect x="9" y="9" width="6" height="6"/>',
    "zoom-in": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/><path d="M11 8v6M8 11h6"/>',
    "zoom-out": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/><path d="M8 11h6"/>',
    "zoom-reset": '<circle cx="11" cy="11" r="7"/><path d="M21 21l-4.5-4.5"/><path d="M9 8h2v6M9 14h4"/>',
    "snap": '<path d="M4 8h16M4 16h16M8 4v16M16 4v16"/><circle cx="8" cy="8" r="1.5" fill="' + STROKE + '"/>',
    "grid": '<rect x="3" y="3" width="18" height="18"/><path d="M9 3v18M15 3v18M3 9h18M3 15h18"/>',
    "arrange": '<rect x="3" y="3" width="7" height="5"/><rect x="14" y="3" width="7" height="5"/><rect x="8.5" y="14" width="7" height="5"/><path d="M6.5 8v3h11V8M12 11v3"/>',
    "categories": '<circle cx="8" cy="8" r="3.5"/><circle cx="16" cy="16" r="3.5"/><circle cx="16" cy="8" r="3.5"/><circle cx="8" cy="16" r="3.5"/>',
    "import": '<path d="M12 3v12"/><path d="M8 11l4 4 4-4"/><path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "clear": '<path d="M4 6h16"/><path d="M8 6V4h8v2"/><path d="M6 10l1.5 10h9L18 10"/>',
    "export": '<rect x="3" y="5" width="18" height="14" rx="1"/><path d="M3 16l5-5 4 4 3-3 6 6"/><circle cx="16" cy="9" r="1.5"/>',
    "export-svg": '<path d="M4 20h16"/><path d="M6 16l4-8 3 5 2-3 3 6"/>',
    "copy": '<rect x="9" y="9" width="11" height="11" rx="1"/><path d="M5 15H4a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v1"/>',
    "about": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6"/><circle cx="12" cy="8" r="0.8" fill="' + STROKE + '"/>',
    "map": '<path d="M3 6l6-2 6 2 6-2v14l-6 2-6-2-6 2z"/><path d="M9 4v14M15 6v14"/>',
    "3d": '<path d="M12 3l8 4.5v9L12 21l-8-4.5v-9z"/><path d="M12 12l8-4.5M12 12v9M12 12L4 7.5"/>',
    "analysis": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
}

TEMPLATE = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="{stroke}" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">{body}</svg>\n'
)


def main() -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    for name, body in ICONS.items():
        (ICONS_DIR / f"{name}.svg").write_text(TEMPLATE.format(stroke=STROKE, body=body), encoding="utf-8")
    print(f"{len(ICONS)} iconos generados en {ICONS_DIR}")


if __name__ == "__main__":
    main()
