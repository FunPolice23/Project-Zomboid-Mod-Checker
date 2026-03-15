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

REM Warn if running Python 3.14+ (not fully tested with all deps)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Detected Python %PYVER%
echo NOTE: Python 3.14+ is experimental with PyInstaller and kirjava.
echo       If the build fails, try Python 3.11 or 3.12.
echo.

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
