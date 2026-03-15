@echo off
title PZ Mod Compatibility Checker - PyInstaller Build
echo =====================================================
echo  PZ Mod Compatibility Checker - Release Build
echo  Output: dist\PZModCompatibilityChecker.exe
echo =====================================================
echo.

REM ── Pre-flight checks ──────────────────────────────────
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found in PATH.
    echo Install Python 3.11 or 3.12 from https://python.org
    pause & exit /b 1
)

pyinstaller --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: PyInstaller not found.
    echo Run: pip install pyinstaller
    pause & exit /b 1
)

echo Pre-flight OK. Starting build...
echo.

REM ── PyInstaller build ──────────────────────────────────
pyinstaller ^
  --onefile ^
  --windowed ^
  --name PZModCompatibilityChecker ^
  --icon=icon.ico ^
  --hidden-import PyQt6.QtCore ^
  --hidden-import PyQt6.QtGui ^
  --hidden-import PyQt6.QtWidgets ^
  --hidden-import PyQt6.QtWebEngineWidgets ^
  --hidden-import PyQt6.QtWebEngineCore ^
  --hidden-import PyQt6.QtNetwork ^
  --hidden-import kirjava ^
  --hidden-import tqdm ^
  --hidden-import sqlite3 ^
  --add-data "gui_debug.py;." ^
  --add-data "gui_save.py;." ^
  --add-data "gui_conflict.py;." ^
  --add-data "gui_quickfix.py;." ^
  --add-data "gui_tabs.py;." ^
  --add-data "gui_workshop.py;." ^
  --add-data "gui_helpers.py;." ^
  --add-data "gui_themes.py;." ^
  --add-data "indexer.py;." ^
  --add-data "modparser.py;." ^
  --add-data "comparison.py;." ^
  --add-data "luaparser.py;." ^
  --add-data "constants.py;." ^
  gui.py

echo.
if errorlevel 1 (
    echo BUILD FAILED — check output above for errors.
    pause & exit /b 1
)

echo =====================================================
echo  BUILD COMPLETE
echo  Output: dist\PZModCompatibilityChecker.exe
echo.
echo  IMPORTANT: Set DEBUG = False in gui_debug.py
echo  before making a public release build.
echo =====================================================
echo.
pause