# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for LoudspeakerFEA.

Build command:
    pyinstaller LoudspeakerFEA.spec --clean
"""

import sys
from pathlib import Path

# Project root (where src/ lives)
project_root = Path(SPECPATH)

block_cipher = None

a = Analysis(
    [str(project_root / "src" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PyQt6
        "PyQt6",
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "PyQt6.sip",
        # Matplotlib backends and internals
        "matplotlib",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_qt",
        "matplotlib.figure",
        "matplotlib.ticker",
        "matplotlib.tri",
        "matplotlib.pyplot",
        "matplotlib.cm",
        "matplotlib.colors",
        # stdlib used by the app
        "sqlite3",
        "json",
        "math",
        "bisect",
        "re",
        "subprocess",
        "shutil",
        "tempfile",
        # Optional Elmer-related (imported conditionally in try/except)
        "numpy",
        "scipy",
        "meshio",
        # Application modules (ensure they are packed)
        "src",
        "src.models",
        "src.engine",
        "src.database",
        "src.api",
        "src.elmer_integration",
        "src.main_window",
        "src.geometry_builder",
        "src.elmer_solver",
        "src.post_processor",
        "src.materials",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="LoudspeakerFEA",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LoudspeakerFEA",
)
