# -*- mode: python ; coding: utf-8 -*-
# PZModCompatibilityChecker.spec
# Generated for PyInstaller -- update paths if needed.

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        # Non-Python assets only. All .py modules are found automatically
        # by PyInstaller's import tracer — do NOT list them here.
        # Add any data files your mod needs here, e.g.:
        # ('icon.ico', '.'),
    ],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'PyQt6.QtNetwork',
        'kirjava',
        'tqdm',
        'sqlite3',
        'zipfile',
        'pickle',
        'zstandard',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='PZModCompatibilityChecker',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.ico'],
)
