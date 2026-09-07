"""Genera assets/icon.ico si no existe.

Diseño: tres nodos octogonales conectados (una red de referencias) sobre un
círculo azul institucional. Se ejecuta en CI para que PyInstaller e Inno Setup
siempre tengan un icono sin versionar el binario.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
ASSETS = ROOT / "assets"
TARGET = ASSETS / "icon.ico"

PRIMARY = (31, 78, 121, 255)       # #1F4E79
NODE = (255, 255, 255, 255)
EDGE = (221, 235, 247, 255)        # #DDEBF7
TRANSPARENT = (0, 0, 0, 0)
SIZES = (16, 24, 32, 48, 64, 128, 256)


def _octagon(cx: float, cy: float, w: float, h: float, c: float) -> list[tuple[float, float]]:
    x0, y0, x1, y1 = cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2
    return [
        (x0 + c, y0), (x1 - c, y0), (x1, y0 + c), (x1, y1 - c),
        (x1 - c, y1), (x0 + c, y1), (x0, y1 - c), (x0, y0 + c),
    ]


def _make_image(size: int) -> Image.Image:
    scale = 4
    canvas = size * scale
    img = Image.new("RGBA", (canvas, canvas), TRANSPARENT)
    draw = ImageDraw.Draw(img)
    inset = max(canvas // 20, 2)
    draw.ellipse((inset, inset, canvas - inset, canvas - inset), fill=PRIMARY)

    nodes = [
        (canvas * 0.32, canvas * 0.34),
        (canvas * 0.68, canvas * 0.34),
        (canvas * 0.50, canvas * 0.68),
    ]
    width = max(canvas // 28, 2)
    for a, b in ((0, 2), (1, 2), (0, 1)):
        draw.line((*nodes[a], *nodes[b]), fill=EDGE, width=width)
    w, h = canvas * 0.30, canvas * 0.18
    for cx, cy in nodes:
        draw.polygon(_octagon(cx, cy, w, h, h * 0.35), fill=NODE)
    return img.resize((size, size), Image.Resampling.LANCZOS)


def main() -> None:
    ASSETS.mkdir(parents=True, exist_ok=True)
    if TARGET.exists():
        print(f"{TARGET} ya existe, se conserva.")
        return
    images = [_make_image(s) for s in SIZES]
    images[-1].save(TARGET, format="ICO", sizes=[(s, s) for s in SIZES])
    print(f"Icono generado en {TARGET}")


if __name__ == "__main__":
    main()
