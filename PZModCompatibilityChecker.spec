# -*- mode: python ; coding: utf-8 -*-
# PZModCompatibilityChecker.spec
# Generated for PyInstaller -- update paths if needed.

a = Analysis(
    ['gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        # All split gui modules must be bundled explicitly
        ('gui_debug.py',    '.'),
        ('gui_save.py',     '.'),
        ('gui_conflict.py', '.'),
        ('gui_quickfix.py', '.'),
        ('gui_tabs.py',     '.'),
        ('gui_workshop.py', '.'),
        ('gui_helpers.py',  '.'),
        ('gui_themes.py',   '.'),
        # Core analysis modules
        ('indexer.py',      '.'),
        ('modparser.py',    '.'),
        ('comparison.py',   '.'),
        ('luaparser.py',    '.'),
        ('constants.py',    '.'),
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
