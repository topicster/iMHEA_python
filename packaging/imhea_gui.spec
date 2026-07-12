# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the iMHEA Data Processor desktop app.

Build from the repository root:
    pyinstaller packaging/imhea_gui.spec --noconfirm

Produces dist/iMHEA-Data-Processor/ (one-dir bundle: fast startup, easy to
inspect). On macOS an .app bundle is also generated.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH).parent

a = Analysis(
    [str(ROOT / "gui" / "run_gui.py")],
    pathex=[str(ROOT / "src"), str(ROOT / "gui")],
    binaries=[],
    datas=[],
    hiddenimports=[
        "imhea", "imhea.cli", "imhea_gui.app",
        "matplotlib.backends.backend_qtagg",
        "scipy._cyutility",
        "scipy.special._special_ufuncs",
    ],
    excludes=[
        "tkinter", "IPython", "jupyter", "pytest",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets",
        "PySide6.QtQml", "PySide6.QtQuick", "PySide6.Qt3DCore",
        "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtPdf",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="iMHEA-Data-Processor",
    console=False,
    icon=str(ROOT / "packaging" / "imhea.ico")
    if (ROOT / "packaging" / "imhea.ico").exists() else None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="iMHEA-Data-Processor",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="iMHEA Data Processor.app",
        bundle_identifier="org.imhea.dataprocessor",
        info_plist={"NSHighResolutionCapable": True},
    )
