# -*- mode: python ; coding: utf-8 -*-
"""Spec de PyInstaller para SpecRel (onedir, sin consola).

Uso: pyinstaller specrel.spec
"""
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = (
    collect_submodules("pyqtgraph")
    + collect_submodules("OpenGL")
    + ["OpenGL.platform.win32", "PyQt6.QtSvg", "PyQt6.QtOpenGL", "PyQt6.QtOpenGLWidgets", "openpyxl"]
)

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("assets", "assets"),               # incluye assets/data/masterformat_2020.sqlite y clausulas.sqlite
        ("views/styles", "views/styles"),
    ],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PyQt5", "PySide2", "PySide6", "tkinter", "matplotlib", "scipy", "pandas", "IPython",
        "PyQt6.QtWebEngineCore", "PyQt6.QtWebEngineWidgets", "PyQt6.QtQml", "PyQt6.QtQuick",
        "PyQt6.QtMultimedia", "PyQt6.QtBluetooth", "PyQt6.QtNfc", "PyQt6.QtPositioning",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SpecRel",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon="assets/icon.ico",
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="SpecRel",
)
