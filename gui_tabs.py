import re
import os
import threading
import platform
import traceback as _traceback
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer, QUrl, QObject, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QIcon
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QGroupBox, QMessageBox, QComboBox, QHeaderView,
    QSplitter, QProgressBar, QTabWidget, QCheckBox
)
from gui_quickfix import QuickFixTab, QUICK_FIX_DB

# Set to True to enable the Debug tab in the main window.
# The debug tab captures all stdout/stderr and internal log calls live.
DEBUG = False

# Bulk cache
_stop_bulk = False
_bulk_cache = {}  # mod_path → files_dict cache

# ── Thread-safe main-thread dispatcher ───────────────────────────────────────
# QTimer.singleShot from a non-Qt thread causes QBasicTimer warnings and
# dropped callbacks. This dispatcher uses a Qt signal so the callback always
# runs on the main thread via the event loop, regardless of caller thread.
class _Dispatcher(QObject):
    _call = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self._call.connect(lambda fn: fn())

_dispatcher = _Dispatcher()

def _ui(fn):
    """Schedule fn() on the main Qt thread. Safe to call from any thread."""
    _dispatcher._call.emit(fn)

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    _HAS_WEBENGINE = True
except ImportError:
    _HAS_WEBENGINE = False

# ── PZ save location helpers ─────────────────────────────────────────────────

def _find_pz_saves_dir() -> Path | None:
    """
    Find the PZ Saves folder. PZ always writes to USERPROFILE/Zomboid/Saves
    on Windows. Does not follow the Steam library or exe location.
    Checks all drive letters and non-standard root locations as fallbacks.
    """
    import platform
    candidates: list[Path] = []
    if platform.system() == "Windows":
        userprofile = os.environ.get("USERPROFILE", "")
        if userprofile:
            candidates.append(Path(userprofile) / "Zomboid" / "Saves")
        candidates.append(Path.home() / "Zomboid" / "Saves")
        for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
            drive = Path(f"{letter}:/")
            if drive.exists():
                candidates.append(drive / "Users" / Path.home().name / "Zomboid" / "Saves")
                candidates.append(drive / "Zomboid" / "Saves")
    elif platform.system() == "Darwin":
        candidates.append(Path.home() / "Zomboid" / "Saves")
        candidates.append(Path.home() / "Library" / "Application Support" / "Zomboid" / "Saves")
    else:
        candidates.append(Path.home() / "Zomboid" / "Saves")
        candidates.append(Path.home() / ".local" / "share" / "Zomboid" / "Saves")
    for c in candidates:
        try:
            if c.is_dir() and any(c.iterdir()):
                return c
        except (PermissionError, OSError):
            continue
    return None


# PZ save structure:
#   Saves/
#     {GameMode}/        e.g. Apocalypse, Survivor, Sandbox, Builder, Multiplayer
#       {SaveName}/      timestamp or custom name
#         *.bin, *.lua, players.db, mods.txt, ...
#
# We detect leaf save folders by presence of at least one known save file.

_SAVE_MARKER_FILES = {"WorldDictionary.bin", "players.db", "vehicles.db", "mods.txt"}

def _is_save_folder(path: Path) -> bool:
    return any((path / m).exists() for m in _SAVE_MARKER_FILES)


def _read_mod_info_ids(folder: Path) -> list[tuple[str, str, str]]:
    """
    Read all mod.info files under folder and return list of
    (mod_id, display_name, folder_path_str) tuples.
    Handles semicolon-separated IDs on one line.
    """
    results = []
    try:
        for info_file in folder.rglob("mod.info"):
            try:
                text = info_file.read_text(encoding="utf-8", errors="ignore")
                ids_found = []
                disp = folder.name
                for line in text.splitlines():
                    stripped = line.strip()
                    if stripped.lower().startswith("id="):
                        val = stripped.split("=", 1)[1].strip()
                        ids_found.extend(v.strip() for v in val.replace(",", ";").split(";") if v.strip())
                    elif stripped.lower().startswith("name="):
                        disp = stripped.split("=", 1)[1].strip().strip("\"'")
                # Use the mod folder that contains this mod.info as the path
                mod_root = info_file.parent
                for mod_id in ids_found:
                    results.append((mod_id, disp, str(mod_root)))
            except Exception:
                pass
    except Exception:
        pass
    return results


def _build_mod_id_index(detected_mods: list) -> dict[str, tuple]:
    """
    Build a dict mapping lowercase mod ID -> (display_name, folder_path_str).

    Sources scanned in priority order:
      1. Workshop cache JSON paths  (from workshop_cache.json — most reliable,
         already scanned and stored, works even before detected_mods is populated)
      2. detected_mods list         (live list passed from gui.py)
      3. ~/Zomboid/mods             (manually installed mods)

    Returns: { "mod_id_lower": (display_name, path_str), ... }
    """
    from gui_helpers import DOCS_DIR
    import json as _json

    index: dict[str, tuple] = {}

    def _add(folder: Path):
        if not folder.is_dir():
            return
        for mod_id, disp, path_str in _read_mod_info_ids(folder):
            index[mod_id.lower()] = (disp, path_str)

    # ── 1. Workshop cache JSON (paths already known, independent of timing) ──
    cache_file = DOCS_DIR / "workshop_cache.json"
    if cache_file.exists():
        try:
            data = _json.loads(cache_file.read_text(encoding="utf-8", errors="ignore"))
            for entry in data.get("mods", []):
                # entry: [name, path, size, mtime, compat]
                folder = Path(entry[1]) if len(entry) > 1 else None
                if folder and folder.is_dir():
                    _add(folder)
        except Exception:
            pass

    # ── 2. detected_mods list (may be populated if scan ran before index build) ──
    for entry in detected_mods:
        folder = Path(entry[1]) if len(entry) > 1 else None
        if folder and folder.is_dir():
            _add(folder)

    # ── 3. ~/Zomboid/mods (manually installed mods) ──────────────────────────
    local_mods = Path.home() / "Zomboid" / "mods"
    if local_mods.is_dir():
        for sub in local_mods.iterdir():
            if sub.is_dir():
                _add(sub)

    return index


def _fast_dir_size(path: Path, max_depth: int = 2) -> int:
    """Estimate folder size by walking only top levels — avoids hanging on huge saves."""
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            depth = root[len(str(path)):].count(os.sep)
            if depth >= max_depth:
                dirs[:] = []
                continue
            for fname in files:
                try:
                    total += os.path.getsize(os.path.join(root, fname))
                except OSError:
                    pass
    except Exception:
        pass
    return total


def _scan_all_saves(saves_root: Path, log=None, add_callback=None):
    """
    Incremental scan — calls add_callback for each save found.
    Returns full list at end for compatibility.
    """
    results = []
    if not saves_root.is_dir():
        return results
    if log:
        log(f"Scanning: {saves_root}")

    for mode_dir in sorted(saves_root.iterdir()):
        if not mode_dir.is_dir():
            continue
        if log:
            log(f"Checking game mode: {mode_dir.name}")

        for save_dir in sorted(mode_dir.iterdir()):
            if not save_dir.is_dir() or not _is_save_folder(save_dir):
                continue
            try:
                mtime = save_dir.stat().st_mtime
                size = _fast_dir_size(save_dir, max_depth=2)
            except Exception:
                mtime, size = 0, 0

            entry = {
                "name": save_dir.name,
                "game_mode": mode_dir.name,
                "path": save_dir,
                "mtime": mtime,
                "size_mb": size / 1024 / 1024,
            }
            results.append(entry)

            # Live add to UI if callback provided
            if add_callback:
                _ui(lambda e=entry: add_callback(e))

            if log:
                log(f" Found: {mode_dir.name}/{save_dir.name} ({entry['size_mb']:.1f} MB)")

    results.sort(key=lambda x: x["mtime"], reverse=True)
    if log:
        log(f"Done — {len(results)} save(s) found.")
    return results

# ══════════════════════════════════════════════════════════════════════════════
# 0.  DEBUG TAB  (shown only when DEBUG = True)
# ══════════════════════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════════════
# 0.  DEBUG TAB  (shown only when DEBUG = True)
# ══════════════════════════════════════════════════════════════════════════════

class DebugTab:
    """
    Rich live debug console. Captures:
      - All stdout / stderr (print, tracebacks, tqdm, etc.)
      - Explicit DebugTab.dbg() calls from anywhere in the codebase
      - Workshop scan events, save index rebuilds, conflict checks
      - Thread activity, QTimer events, cache read/write
      - Full exception tracebacks via sys.excepthook

    Set DEBUG = False at the top of this file before shipping.
    """
    _log_lines: list = []
    _listeners: list = []

    # ── Category tags for colour-coding ──────────────────────────────────
    _COLOURS = {
        "[SCAN]":    "#4fc3f7",   # light blue
        "[SAVE]":    "#81c784",   # green
        "[CONFLICT]":"#ffb74d",   # orange
        "[CACHE]":   "#ce93d8",   # purple
        "[CRASH]":   "#ef5350",   # red
        "[THREAD]":  "#80cbc4",   # teal
        "[UI]":      "#fff176",   # yellow
        "[out]":     "#b0bec5",   # grey  (stdout/stderr)
        "[err]":     "#ef9a9a",   # pink-red (stderr)
    }

    @staticmethod
    def dbg(msg: str, tag: str = ""):
        """
        Emit a debug message. tag is optional e.g. '[SCAN]', '[CRASH]'.
        Called from anywhere — thread-safe.
        """
        ts = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        prefix = f"{tag}  " if tag else ""
        line = f"[{ts}]  {prefix}{msg}"
        DebugTab._log_lines.append(line)
        if len(DebugTab._log_lines) > 8000:
            DebugTab._log_lines = DebugTab._log_lines[-6000:]
        for fn in list(DebugTab._listeners):
            try:
                _ui(lambda l=line, f=fn: f(l))
            except Exception:
                pass

    @staticmethod
    def build(parent_widget: QWidget):
        layout = QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        # ── Toolbar ───────────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        title = QLabel("🐛 Debug Console")
        title.setFont(QFont("Helvetica", 11, QFont.Weight.Bold))
        autoscroll_cb = QCheckBox("Auto-scroll")
        autoscroll_cb.setChecked(True)
        pause_cb = QCheckBox("Pause")
        clear_btn = QPushButton("🗑 Clear")
        copy_btn  = QPushButton("📋 Copy")
        save_btn  = QPushButton("💾 Save")
        for b in (clear_btn, copy_btn, save_btn):
            b.setFixedHeight(28)
        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(autoscroll_cb)
        toolbar.addWidget(pause_cb)
        toolbar.addWidget(clear_btn)
        toolbar.addWidget(copy_btn)
        toolbar.addWidget(save_btn)
        layout.addLayout(toolbar)

        # ── Filter + category row ─────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_box = QLineEdit()
        filter_box.setPlaceholderText("🔍 Filter… (keyword or tag like [CRASH])")
        filter_box.setFixedHeight(26)
        cat_combo = QComboBox()
        cat_combo.setFixedHeight(26)
        cat_combo.addItem("All categories")
        for tag in DebugTab._COLOURS:
            cat_combo.addItem(tag.strip("[]"))
        filter_row.addWidget(filter_box, stretch=3)
        filter_row.addWidget(QLabel("Category:"))
        filter_row.addWidget(cat_combo, stretch=1)
        layout.addLayout(filter_row)

        # ── Log output ────────────────────────────────────────────────────
        log_out = QTextEdit()
        log_out.setReadOnly(True)
        log_out.setFont(QFont("Consolas", 9))
        log_out.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        layout.addWidget(log_out, stretch=1)

        # ── Stats bar ─────────────────────────────────────────────────────
        stat_row = QHBoxLayout()
        stat_lbl = QLabel("Lines: 0")
        stat_lbl.setStyleSheet("color: gray; font-size: 10px;")
        thread_lbl = QLabel("")
        thread_lbl.setStyleSheet("color: #80cbc4; font-size: 10px;")
        stat_row.addWidget(stat_lbl)
        stat_row.addStretch()
        stat_row.addWidget(thread_lbl)
        layout.addLayout(stat_row)
        parent_widget.setLayout(layout)

        _kw: list = [""]
        _cat: list = [""]   # active category filter

        def _scroll():
            if autoscroll_cb.isChecked() and not pause_cb.isChecked():
                sb = log_out.verticalScrollBar()
                sb.setValue(sb.maximum())

        def _matches(line: str) -> bool:
            kw  = _kw[0].lower()
            cat = _cat[0]
            if kw and kw not in line.lower():
                return False
            if cat and f"[{cat}]" not in line:
                return False
            return True

        def _stat():
            shown = sum(1 for l in DebugTab._log_lines if _matches(l))
            stat_lbl.setText(
                f"Lines: {len(DebugTab._log_lines)}  |  "
                f"Shown: {shown}  |  "
                f"Filter: {repr(_kw[0]) if _kw[0] else 'off'}"
            )

        def _refresh_all():
            log_out.clear()
            for line in DebugTab._log_lines:
                if _matches(line):
                    _append_coloured(line)
            _scroll()
            _stat()

        def _append_coloured(line: str):
            colour = "#cccccc"
            for tag, col in DebugTab._COLOURS.items():
                if tag in line:
                    colour = col
                    break
            log_out.append(f'<span style="color:{colour}">{line}</span>')

        def _on_new_line(line: str):
            if pause_cb.isChecked():
                return
            if _matches(line):
                _append_coloured(line)
                _scroll()
            _stat()

        DebugTab._listeners.append(_on_new_line)
        _refresh_all()

        # ── Controls ──────────────────────────────────────────────────────
        def _on_filter(text: str):
            _kw[0] = text.strip()
            _refresh_all()

        def _on_cat(idx: int):
            _cat[0] = "" if idx == 0 else cat_combo.currentText()
            _refresh_all()

        filter_box.textChanged.connect(_on_filter)
        cat_combo.currentIndexChanged.connect(_on_cat)

        clear_btn.clicked.connect(lambda: (
            DebugTab._log_lines.clear(), log_out.clear(),
            stat_lbl.setText("Lines: 0  |  Cleared")
        ))

        def _copy():
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(
                "\n".join(l for l in DebugTab._log_lines if _matches(l))
            )
        copy_btn.clicked.connect(_copy)

        def _save():
            from gui_helpers import DOCS_DIR
            p, _ = QFileDialog.getSaveFileName(
                parent_widget, "Save Debug Log",
                str(DOCS_DIR / f"debug_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"),
                "Text files (*.txt)"
            )
            if p:
                try:
                    with open(p, "w", encoding="utf-8") as f:
                        f.write("\n".join(DebugTab._log_lines))
                except Exception as ex:
                    QMessageBox.warning(parent_widget, "Save Failed", str(ex))
        save_btn.clicked.connect(_save)

        # ── Live thread monitor ───────────────────────────────────────────
        import threading as _thr
        def _update_threads():
            n = len(_thr.enumerate())
            thread_lbl.setText(f"Threads: {n}")
        _thread_timer = QTimer()
        _thread_timer.timeout.connect(_update_threads)
        _thread_timer.start(2000)

        # ── Intercept stdout / stderr ─────────────────────────────────────
        import sys as _sys

        class _Tee:
            def __init__(self, orig, tag):
                self._orig = orig
                self._tag  = tag
                self._buf  = ""
            def write(self, text):
                try: self._orig.write(text)
                except Exception: pass
                self._buf += text
                while "\n" in self._buf:
                    line, self._buf = self._buf.split("\n", 1)
                    if line.strip():
                        DebugTab.dbg(line, self._tag)
            def flush(self):
                try: self._orig.flush()
                except Exception: pass
            def fileno(self): return self._orig.fileno()

        if not isinstance(_sys.stdout, _Tee):
            _sys.stdout = _Tee(_sys.__stdout__, "[out]")
        if not isinstance(_sys.stderr, _Tee):
            _sys.stderr = _Tee(_sys.__stderr__, "[err]")

        # ── Global uncaught exception hook ────────────────────────────────
        _orig_hook = _sys.excepthook
        def _exc_hook(etype, evalue, etb):
            import traceback as _tb
            msg = "".join(_tb.format_exception(etype, evalue, etb))
            DebugTab.dbg(f"UNCAUGHT EXCEPTION:\n{msg}", "[CRASH]")
            _orig_hook(etype, evalue, etb)
        _sys.excepthook = _exc_hook

        DebugTab.dbg("=== Debug tab ready ===", "[UI]")
        DebugTab.dbg(f"Python {_sys.version}", "[UI]")
        DebugTab.dbg(f"stdout/stderr captured | excepthook installed", "[UI]")




# ══════════════════════════════════════════════════════════════════════════════
# 1.  MAP TAB
# ══════════════════════════════════════════════════════════════════════════════

class MapTab:
    """Embedded interactive map - requires PyQt6-WebEngine."""

    @staticmethod
    def build(parent_widget: QWidget):
        layout = QVBoxLayout()
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        if not _HAS_WEBENGINE:
            msg = QLabel(
                "⚠️  PyQt6-WebEngine is not installed.\n\n"
                "Run:  pip install PyQt6-WebEngine\n\n"
                "Then restart the application to use the map."
            )
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setFont(QFont("Consolas", 13))
            layout.addWidget(msg)
            parent_widget.setLayout(layout)
            return

        # Button row
        btn_row = QHBoxLayout()
        b42_btn = QPushButton("🗺️ B42 Map (b42map.com)")
        reload_btn = QPushButton("🔄 Reload")

        view = QWebEngineView()
        view.setUrl(QUrl("https://b42map.com/"))

        b42_btn.clicked.connect(lambda: view.setUrl(QUrl("https://b42map.com/")))
        reload_btn.clicked.connect(view.reload)

        for btn in (b42_btn, reload_btn):
            btn_row.addWidget(btn)

        layout.addLayout(btn_row)
        layout.addWidget(view, stretch=1)
        parent_widget.setLayout(layout)


# ══════════════════════════════════════════════════════════════════════════════
# 2.  SAVE INFO TAB
# ══════════════════════════════════════════════════════════════════════════════

# ── Save data extraction ──────────────────────────────────────────────────────
# Patterns tried against text blobs from .lua/.txt files in the save folder.
# WorldDictionaryReadable.lua is the richest source — it contains most stats.
_SAVE_TEXT_PATTERNS = {
    # Player identity
    "Player Name":        re.compile(r'playerName\s*[=:]\s*"?([^"\n,}]+)"?', re.I),
    # World / session
    "World Name":         re.compile(r'WorldName\s*[=:]\s*"?([^"\n,}]+)"?', re.I),
    "Game Mode":          re.compile(r'GameMode\s*[=:]\s*"?([^"\n,}]+)"?', re.I),
    "Build Version":      re.compile(r'buildVersion\s*[=:]\s*([0-9.]+)', re.I),
    # Survival stats
    "Hours Survived":     re.compile(r'hoursSurvived\s*[=:]\s*([0-9.]+)', re.I),
    "Zombies Killed":     re.compile(r'numZombiesKilled\s*[=:]\s*([0-9]+)', re.I),
    "Survivors Killed":   re.compile(r'numSurvivorsKilled\s*[=:]\s*([0-9]+)', re.I),
    # Player state
    "Player XP":          re.compile(r'xp\s*[=:]\s*([0-9]+)', re.I),
    "Profession":         re.compile(r'profession\s*[=:]\s*"?([^"\n,}]+)"?', re.I),
    "Is Alive":           re.compile(r'isDead\s*[=:]\s*(true|false)', re.I),
    # World state
    "In-Game Day":        re.compile(r'WorldGameTime\s*[=:]\s*([0-9.]+)', re.I),
    "Sandbox Preset":     re.compile(r'SandboxVars\.Preset\s*[=:]\s*"?([^"\n,}]+)"?', re.I),
    "Zombie Count":       re.compile(r'ZombieCount\s*[=:]\s*([0-9]+)', re.I),
    "Start Location":     re.compile(r'StartLocation\s*[=:]\s*"?([^"\n,}]+)"?', re.I),
    # Map version (from map_ver.bin — read as text, usually has a version string)
    "Map Version":        re.compile(r'(\d+\.\d+[\.\d]*)', re.M),
}

_MOD_LIST_PATTERN = re.compile(r'mods\s*[=:]\s*\[([^\]]+)\]', re.I | re.S)

# Sandbox preset IDs to human names (from PZ source)
_SANDBOX_PRESETS = {
    "0": "Custom", "1": "Apocalypse", "2": "Survivor", "3": "Builder",
    "4": "Beginner", "5": "First Week", "6": "Short Month", "7": "6 Months Later",
}


def _read_players_db(db_path: Path) -> dict:
    """
    Read player stats from players.db (SQLite3).
    Returns a dict of field -> value strings.
    Falls back gracefully if sqlite3 or the table structure is unexpected.
    """
    result = {}
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        # PZ stores player data in a 'networkPlayers' or 'Player' table depending on version
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        for table in tables:
            try:
                rows = cur.execute(f"SELECT * FROM [{table}] LIMIT 5").fetchall()
                cols = [d[0] for d in cur.description]
                if rows:
                    row = rows[0]
                    for col, val in zip(cols, row):
                        if val is not None and str(val).strip():
                            result[f"DB: {col}"] = str(val)[:120]
            except Exception:
                pass
        conn.close()
    except Exception:
        pass
    return result


def _read_radio_save(radio_path: Path) -> dict:
    """Parse radio/data/RADIO_SAVE.txt for station info."""
    result = {}
    try:
        text = radio_path.read_text(encoding="utf-8", errors="ignore")
        freq = re.search(r'currentFreq\s*[=:]\s*([0-9.]+)', text, re.I)
        if freq:
            result["Radio Freq (MHz)"] = freq.group(1)
        station = re.search(r'stationName\s*[=:]\s*"?([^"\n]+)"?', text, re.I)
        if station:
            result["Radio Station"] = station.group(1).strip()
    except Exception:
        pass
    return result


def _read_map_ver(map_ver_path: Path) -> str:
    """Read map_ver.bin — it often contains a plain version string."""
    try:
        raw = map_ver_path.read_bytes()
        # Try to decode as UTF-8 text first
        text = raw.decode("utf-8", errors="ignore").strip()
        m = re.search(r'(\d+\.\d+[\.\d]*)', text)
        if m:
            return m.group(1)
        # Fallback: read first 4 bytes as a little-endian int (B42 format)
        if len(raw) >= 4:
            import struct
            val = struct.unpack_from('<I', raw)[0]
            if 1 <= val <= 9999:
                return str(val)
    except Exception:
        pass
    return "—"


def _parse_save_folder(save_path: Path) -> dict:
    """
    Fast targeted extraction — only the files we need. No freeze.
    Now cleans the weird save mods.txt format.
    """
    info = {
        "Active Mods": [], "Files Found": 0, "Total Size": 0,
        "Thumbnail": None, "_db_fields": {}, "Map Version": "—"
    }

    # Size & count (fast)
    info["Total Size"] = _fast_dir_size(save_path, max_depth=3)
    info["Files Found"] = sum(1 for _ in save_path.rglob("*"))

    # Thumbnail
    thumb_path = save_path / "thumb.png"
    if thumb_path.exists():
        info["Thumbnail"] = thumb_path

    # ── Text blob (only the two important files) ─────────────────────
    text_blob = ""
    for fname in ["mods.txt", "WorldDictionaryReadable.lua"]:
        f = save_path / fname
        if f.exists():
            try:
                if "worlddictionaryreadable" in fname.lower():
                    chunk = f.read_bytes()[:256 * 1024].decode("utf-8", errors="ignore")
                else:
                    chunk = f.read_text(encoding="utf-8", errors="ignore")
                text_blob += chunk + "\n"
            except Exception:
                pass

    # ── Mods list — CLEAN the weird format ──────────────────────────
    mods_txt = save_path / "mods.txt"
    if mods_txt.exists():
        try:
            raw = [line.strip() for line in mods_txt.read_text(encoding="utf-8", errors="ignore").splitlines() if line.strip()]
            clean_mods = []
            for line in raw:
                if line.startswith("mod ="):
                    mod_id = line.split("=", 1)[1].strip().strip("\\, ")  # remove \, and comma
                    if mod_id:
                        clean_mods.append(mod_id)
            info["Active Mods"] = clean_mods
        except Exception:
            pass

    if not info["Active Mods"]:
        m = _MOD_LIST_PATTERN.search(text_blob)
        if m:
            info["Active Mods"] = [x.strip().strip('"\'') for x in m.group(1).split(",") if x.strip()]

    # ── Text patterns, map_ver, players.db, radio (unchanged) ───────
    for field, pat in _SAVE_TEXT_PATTERNS.items():
        if field == "Map Version":
            continue
        m = pat.search(text_blob)
        if m:
            val = m.group(1).strip()
            if field == "Is Alive":
                val = "No" if val.lower() == "true" else "Yes"
            elif field == "In-Game Day":
                try:
                    hours = float(val)
                    val = f"Day {int(hours // 24) + 1} (hour {int(hours % 24):02d}:00)"
                except ValueError:
                    pass
            elif field == "Sandbox Preset":
                val = _SANDBOX_PRESETS.get(val, val)
            elif field == "Hours Survived":
                try:
                    h = float(val)
                    val = f"{h:.1f} hrs ({int(h // 24)} days)"
                except ValueError:
                    pass
            info[field] = val

    map_ver_path = save_path / "map_ver.bin"
    if map_ver_path.exists():
        v = _read_map_ver(map_ver_path)
        if v != "—":
            info["Map Version"] = v

    players_db = save_path / "players.db"
    if players_db.exists():
        info["_db_fields"] = _read_players_db(players_db)

    radio_txt = save_path / "radio" / "data" / "RADIO_SAVE.txt"
    if radio_txt.exists():
        info.update(_read_radio_save(radio_txt))

    # File counts
    bin_count = sum(1 for f in save_path.rglob("*.bin") if f.is_file())
    lua_count = sum(1 for f in save_path.rglob("*.lua") if f.is_file())
    info["Binary Files (.bin)"] = str(bin_count)
    info["Lua Files (.lua)"] = str(lua_count)

    size_mb = info["Total Size"] / 1024 / 1024
    info["Total Size"] = f"{size_mb:.1f} MB"
    return info

class SaveInfoTab:
    """
    Read-only save inspector.
    Shows all saves grouped by game mode on the left.
    Selecting one loads: thumbnail screenshot, full stats tree, and mod list.
    """

    # Set during build() — called when workshop scan finishes to refresh the index
    _rebuild_index_fn = None

    @staticmethod
    def refresh_index(detected_mods: list):
        """
        Call from gui.py after the workshop scan completes.
        Refreshes the mod-ID index so save mod lookups reflect the new scan.
        """
        if SaveInfoTab._rebuild_index_fn:
            _ui(lambda m=detected_mods: SaveInfoTab._rebuild_index_fn(m))

    @staticmethod
    def build(parent_widget: QWidget, detected_mods: list | None = None):
        """
        detected_mods: list of (name, path, size, mtime, compat) from workshop scanner.
        Used to cross-reference save mods against installed/cached mods.
        """
        from PyQt6.QtGui import QPixmap
        _detected_mods: list = list(detected_mods) if detected_mods else []
        # Mod-ID index: rebuilt on first use AND whenever the workshop scan completes
        _mod_id_index: dict = {}

        def _ensure_index():
            """
            Build/rebuild the mod ID index.
            Always reads from workshop_cache.json so it works even if
            detected_mods was empty at build time (startup timing issue).
            Also picks up detected_mods if the scan has since completed.
            """
            if DEBUG:
                DebugTab.dbg(f"Building mod-ID index ({len(_detected_mods)} live mods)", "[CACHE]")
            _mod_id_index.clear()
            _mod_id_index.update(_build_mod_id_index(_detected_mods))
            if DEBUG:
                DebugTab.dbg(f"Index built: {len(_mod_id_index)} mod IDs mapped", "[CACHE]")

        def _rebuild_index_from_live(mods: list):
            """Called when the workshop scan finishes — refresh the index."""
            if DEBUG:
                DebugTab.dbg(f"Index rebuild from live scan: {len(mods)} mods", "[CACHE]")
            _detected_mods.clear()
            _detected_mods.extend(mods)
            _mod_id_index.clear()
            _mod_id_index.update(_build_mod_id_index(_detected_mods))
            if DEBUG:
                DebugTab.dbg(f"Index refreshed: {len(_mod_id_index)} mod IDs mapped", "[CACHE]")
            # Repopulate currently displayed mod tree if any
            if _current_mod_ids:
                _populate_mod_tree(_current_mod_ids)

        SaveInfoTab._rebuild_index_fn = _rebuild_index_from_live

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # ── Top bar ────────────────────────────────────────────────────────
        top_row = QHBoxLayout()
        saves_root_entry = QLineEdit()
        saves_root_entry.setReadOnly(True)
        saves_root_entry.setPlaceholderText("Saves root folder…")
        #auto_btn   = QPushButton("🔍 Auto-Detect Saves")
        browse_btn = QPushButton("📁 Browse Saves Root")
        top_row.addWidget(saves_root_entry, stretch=1)
        #top_row.addWidget(auto_btn)
        top_row.addWidget(browse_btn)
        layout.addLayout(top_row)

        # ── Main splitter: save list (left) | detail panel (right) ────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: tree of all saves grouped by game mode
        save_tree = QTreeWidget()
        save_tree.setHeaderLabels(["Save", "Date", "Size"])
        save_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        save_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        save_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        save_tree.setMinimumWidth(280)
        splitter.addWidget(save_tree)

        # Right: vertical splitter — thumbnail + info tree on top, mod list below
        right_splitter = QSplitter(Qt.Orientation.Vertical)

        # Top-right: horizontal — thumbnail (left) + info tree (right)
        top_right = QSplitter(Qt.Orientation.Horizontal)

        # Thumbnail panel
        thumb_container = QWidget()
        thumb_layout = QVBoxLayout(thumb_container)
        thumb_layout.setContentsMargins(4, 4, 4, 4)
        thumb_label = QLabel("No screenshot")
        thumb_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        thumb_label.setMinimumSize(200, 130)
        thumb_label.setMaximumSize(320, 200)
        thumb_label.setStyleSheet("border: 1px solid #444; border-radius: 4px;")
        thumb_layout.addWidget(thumb_label)
        thumb_layout.addStretch()
        top_right.addWidget(thumb_container)

        # Info tree
        info_tree = QTreeWidget()
        info_tree.setHeaderLabels(["Field", "Value"])
        info_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        info_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        top_right.addWidget(info_tree)
        top_right.setSizes([240, 460])

        right_splitter.addWidget(top_right)

        # Bottom-right: mod tree + controls
        mod_box = QGroupBox("📋 Active Mods in Save")
        mod_layout = QVBoxLayout()
        mod_layout.setContentsMargins(6, 6, 6, 6)
        mod_layout.setSpacing(4)

        # Search + count row
        mod_top_row = QHBoxLayout()
        mod_search = QLineEdit()
        mod_search.setPlaceholderText("🔍 Filter mods by ID…")
        mod_count_lbl = QLabel("")
        mod_count_lbl.setStyleSheet("color: gray; font-size: 11px;")
        mod_top_row.addWidget(mod_search, stretch=1)
        mod_top_row.addWidget(mod_count_lbl)
        mod_layout.addLayout(mod_top_row)

        # Tree: # | Mod ID | Status
        mod_tree = QTreeWidget()
        mod_tree.setHeaderLabels(["#", "Mod ID", "Status"])
        mod_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        mod_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        mod_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        mod_tree.setRootIsDecorated(False)
        mod_tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        mod_tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        mod_layout.addWidget(mod_tree, stretch=1)

        # Button row
        mod_btn_row = QHBoxLayout()
        conflict_btn = QPushButton("⚔️ Check Mods for Conflicts")
        conflict_btn.setToolTip(
            "Sends all mods found on disk to the Conflict Checker tab "
            "so you can compare any two of them."
        )
        conflict_btn.setEnabled(False)
        copy_mod_btn = QPushButton("📋 Copy Mod List")
        copy_mod_btn.setToolTip("Copy all mod IDs to clipboard.")
        mod_btn_row.addWidget(conflict_btn, stretch=2)
        mod_btn_row.addWidget(copy_mod_btn, stretch=1)
        mod_layout.addLayout(mod_btn_row)

        mod_box.setLayout(mod_layout)
        right_splitter.addWidget(mod_box)
        right_splitter.setSizes([340, 280])

        # Shared state
        _current_mod_ids: list[str] = []

        splitter.addWidget(right_splitter)
        splitter.setSizes([300, 700])
        layout.addWidget(splitter, stretch=1)

        status = QLabel("Click Auto-Detect or browse to your Zomboid/Saves folder.")
        layout.addWidget(status)
        parent_widget.setLayout(layout)

        # ── Helpers ────────────────────────────────────────────────────────
        def _populate_tree(saves: list[dict]):
            save_tree.clear()
            by_mode: dict[str, list[dict]] = {}
            for s in saves:
                by_mode.setdefault(s["game_mode"], []).append(s)

            for mode in sorted(by_mode):
                mode_item = QTreeWidgetItem([f"📂 {mode}", "", ""])
                mode_item.setFont(0, QFont("Helvetica", 11, QFont.Weight.Bold))
                mode_item.setData(0, Qt.ItemDataRole.UserRole, None)
                for s in by_mode[mode]:
                    date_str = datetime.fromtimestamp(s["mtime"]).strftime("%Y-%m-%d %H:%M") if s["mtime"] else "—"
                    size_str = f"{s['size_mb']:.0f} MB"
                    child = QTreeWidgetItem([s["name"], date_str, size_str])
                    child.setData(0, Qt.ItemDataRole.UserRole, s)
                    mode_item.addChild(child)
                save_tree.addTopLevelItem(mode_item)
                mode_item.setExpanded(True)

            count = len(saves)
            status.setText(f"✅ Found {count} save(s) across {len(by_mode)} game mode(s). Select one to inspect.")

        def _on_save_selected(item: QTreeWidgetItem, _col: int):
            save_data = item.data(0, Qt.ItemDataRole.UserRole)
            if not save_data:
                return

            save_path: Path = save_data["path"]
            status.setText(f"⏳ Loading {save_path.name}…")

            info_tree.clear()
            mod_tree.clear()
            mod_count_lbl.setText("")
            conflict_btn.setEnabled(False)
            thumb_label.setText("Loading…")
            thumb_label.setPixmap(QPixmap())  # clear

            def worker():
                try:
                    parsed = _parse_save_folder(save_path)
                    # EXPLICIT CAPTURE — this fixes the NameError
                    _ui(lambda sd=save_data, p=parsed: _show_detail(sd, p))
                except Exception as e:
                    _ui(lambda err=str(e): status.setText(f"❌ Error: {err}"))

            threading.Thread(target=worker, daemon=True).start()

        def _show_detail(save_data: dict, parsed: dict):
            # ── Defensive capture ─────────────────────────────
            if not isinstance(save_data, dict) or 'name' not in save_data:
                game_mode = save_data.get('game_mode', 'Unknown') if isinstance(save_data, dict) else 'Unknown'
                save_name = save_data.get('name', 'Unnamed') if isinstance(save_data, dict) else 'Unnamed'
            else:
                game_mode = save_data['game_mode']
                save_name = save_data['name']

            info_tree.clear()

            # ── Thumbnail ─────────────────────────────────────────────────────
            thumb_label.setStyleSheet("""
                color: #7f8c8d; 
                font-style: italic; 
                background-color: #2c2c2c; 
                border: 1px solid #444; 
                border-radius: 4px;
            """)

            thumb_path: Path | None = parsed.pop("Thumbnail", None)
            if thumb_path and thumb_path.exists():
                px = QPixmap(str(thumb_path))
                if not px.isNull():
                    px = px.scaled(
                        thumb_label.maximumWidth(),
                        thumb_label.maximumHeight(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation
                    )
                    thumb_label.setPixmap(px)
                    thumb_label.setText("")
                else:
                    thumb_label.setText("⚠️ Corrupt / unreadable image")
                    thumb_label.setStyleSheet(thumb_label.styleSheet() + "color: #e74c3c; font-weight: bold;")
            else:
                thumb_label.setText("🖼️ No screenshot available")

            # ── Open Save Folder button ───────────────────────────────────────
            open_save_btn = QPushButton("📂 Open Save Folder")
            open_save_btn.setFixedWidth(180)
            thumb_layout.addWidget(open_save_btn)

            def _open_current_save():
                if isinstance(save_data, dict) and "path" in save_data and save_data["path"].exists():
                    p = save_data["path"]
                    if platform.system() == "Windows":
                        os.startfile(p)
                    elif platform.system() == "Darwin":
                        subprocess.call(["open", str(p)])
                    else:
                        subprocess.call(["xdg-open", str(p)])
                else:
                    status.setText("No save currently selected")

            open_save_btn.clicked.connect(_open_current_save)

            # ── Section helper ────────────────────────────────────────────────
            def _section(title: str) -> QTreeWidgetItem:
                item = QTreeWidgetItem([title, ""])
                item.setFont(0, QFont("Helvetica", 10, QFont.Weight.Bold))
                item.setForeground(0, QColor(100, 200, 255))
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Checked)
                item.setData(0, Qt.ItemDataRole.UserRole, "section")
                info_tree.addTopLevelItem(item)
                return item

            def _row(field: str, value: str, parent: QTreeWidgetItem | None = None):
                item = QTreeWidgetItem([field, str(value)])
                if parent:
                    parent.addChild(item)
                else:
                    info_tree.addTopLevelItem(item)
                return item

            # ── Save metadata section ─────────────────────────────────────────
            sec = _section("📁 Save Info")
            _row("Game Mode", game_mode, sec)
            _row("Save Name", save_name, sec)
            _row("Last Saved", datetime.fromtimestamp(save_data.get("mtime", 0)).strftime("%Y-%m-%d %H:%M:%S") if save_data.get("mtime") else "—", sec)
            _row("Total Size", parsed.pop("Total Size", "—"), sec)
            _row("Files", str(parsed.pop("Files Found", "—")), sec)
            _row("Binary (.bin)", parsed.pop("Binary Files (.bin)", "—"), sec)
            _row("Lua (.lua)", parsed.pop("Lua Files (.lua)", "—"), sec)
            if "Map Version" in parsed:
                _row("Map Version", parsed.pop("Map Version"), sec)
            sec.setExpanded(True)

            # ── Player section ─────────────────────────────────────────────
            player_fields = ["Player Name", "Profession", "Is Alive", "Player XP"]
            if any(parsed.get(f, "—") != "—" for f in player_fields):
                sec2 = _section("🧍 Player")
                for f in player_fields:
                    v = parsed.pop(f, "—")
                    if v != "—":
                        _row(f, v, sec2)
                sec2.setExpanded(True)

            # ── World / survival section ───────────────────────────────────
            world_fields = ["World Name", "Game Mode", "Hours Survived", "In-Game Day",
                            "Zombies Killed", "Survivors Killed", "Zombie Count",
                            "Start Location", "Sandbox Preset", "Build Version"]
            if any(parsed.get(f, "—") != "—" for f in world_fields):
                sec3 = _section("🌍 World & Survival")
                for f in world_fields:
                    v = parsed.pop(f, "—")
                    if v != "—":
                        _row(f, v, sec3)
                sec3.setExpanded(True)

            # ── Radio section ──────────────────────────────────────────────
            radio_fields = ["Radio Freq (MHz)", "Radio Station"]
            if any(parsed.get(f) for f in radio_fields):
                sec4 = _section("📻 Radio")
                for f in radio_fields:
                    v = parsed.pop(f, None)
                    if v:
                        _row(f, v, sec4)
                sec4.setExpanded(True)

            # ── Database fields (players.db) ───────────────────────────────
            db_fields: dict = parsed.pop("_db_fields", {})
            if db_fields:
                sec5 = _section("🗄️ Database (players.db)")
                for k, v in list(db_fields.items())[:30]:  # cap at 30 rows
                    _row(k.replace("DB: ", ""), v, sec5)
                sec5.setExpanded(False)  # collapsed by default — can be verbose

            # ── Any remaining parsed fields ────────────────────────────────
            remaining = {k: v for k, v in parsed.items()
                         if k not in {"Active Mods"} and v not in ("—", "", None)}
            if remaining:
                sec6 = _section("📄 Other")
                for k, v in remaining.items():
                    _row(k, str(v), sec6)

            info_tree.expandToDepth(0)

            # ── Mod tree ──────────────────────────────────────────────────────
            nonlocal _current_mod_ids
            mods = parsed.get("Active Mods", [])
            _current_mod_ids = list(mods)
            _populate_mod_tree(mods)

            # ── Final status (now 100% safe) ──────────────────────────────────
            if mods:
                status.setText(
                    f"✅ {game_mode} / {save_name} — "
                    f"{len(mods)} mod(s) active"
                )
                conflict_btn.setEnabled(True)
            else:
                status.setText(
                    f"✅ {game_mode} / {save_name} — no mod list found"
                )
                conflict_btn.setEnabled(False)

        # ── Mod tree helpers ───────────────────────────────────────────────────
        def _populate_mod_tree(mods: list[str], kw: str = ""):
            """Fill mod_tree with index, mod ID, and install status."""
            mod_tree.clear()
            _ensure_index()
            kw_lower = kw.lower()
            shown = 0
            found_count = 0
            missing_count = 0

            for i, mod_id in enumerate(mods, 1):
                if kw_lower and kw_lower not in mod_id.lower():
                    continue

                entry = _mod_id_index.get(mod_id.lower())
                if entry:
                    disp_name, path_str = entry
                    display_text = disp_name if disp_name and disp_name != mod_id else mod_id
                    status_str = "✅ Workshop" if "workshop" in path_str.lower() else "📁 Local"
                    color = QColor(100, 220, 100)
                    tooltip = f"ID: {mod_id}\n{display_text}\n{path_str}"
                    found_count += 1
                else:
                    display_text = mod_id
                    status_str = "❌ Not found on disk"
                    tooltip = f"ID: {mod_id}\nNot installed or not scanned yet"
                    color = QColor(220, 80, 80)

                item = QTreeWidgetItem([str(i), display_text, status_str])
                item.setForeground(2, color)
                item.setToolTip(0, tooltip)
                item.setToolTip(1, tooltip)
                item.setData(0, Qt.ItemDataRole.UserRole, path_str if entry else "")
                mod_tree.addTopLevelItem(item)
                shown += 1

            total = len(mods)
            lbl_parts = [f"{shown}/{total}"]
            if kw_lower == "":
                lbl_parts = [f"{found_count} found, {missing_count} missing"]
            mod_count_lbl.setText("  ".join(lbl_parts))

        def _on_mod_search(text: str):
            _populate_mod_tree(_current_mod_ids, kw=text)

        mod_search.textChanged.connect(_on_mod_search)

        def _send_to_conflict():
            """Send save mods to Conflict tab and switch reliably."""
            _ensure_index()
            found_mods = []
            for mod_id in _current_mod_ids:
                entry = _mod_id_index.get(mod_id.lower())
                if entry:
                    found_mods.append(entry)

            total = len(_current_mod_ids)
            if len(found_mods) < 2:
                QMessageBox.information(
                    parent_widget,
                    "Conflict Check",
                    f"Found {len(found_mods)} of {total} save mods on disk.\n\n"
                    f"Need at least 2 installed mods to check conflicts.\n"
                    f"Make sure Workshop tab was scanned first."
                )
                return

            # Switch tab FIRST
            tab_widget = parent_widget
            while tab_widget and not isinstance(tab_widget, QTabWidget):
                tab_widget = tab_widget.parent()

            if isinstance(tab_widget, QTabWidget):
                for i in range(tab_widget.count()):
                    tab_text = tab_widget.tabText(i).lower()
                    if "conflict" in tab_text or "conflicts" in tab_text:
                        tab_widget.setCurrentIndex(i)
                        break
                else:
                    status.setText("⚠️ Could not find Conflict tab — switch manually.")
            else:
                status.setText("⚠️ Could not locate tab widget — switch manually.")

            # Populate AFTER switch
            def _do_load():
                if DEBUG: DebugTab.dbg(f"[CONFLICT] Sending {len(found_mods)}/{total} save mods to Conflict tab")
            ConflictCheckerTab.set_save_mods(found_mods)

            QTimer.singleShot(100, _do_load)  # 100 ms

        conflict_btn.clicked.connect(_send_to_conflict)

        def _load_saves_root(root_path: str):
            p = Path(root_path)
            if not p.is_dir():
                QMessageBox.warning(parent_widget, "Invalid Path", "Not a valid folder.")
                return
            saves_root_entry.setText(str(p))
            status.setText("⏳ Scanning saves…")

            def _log(msg: str):
                _ui(lambda m=msg: status.setText(f"⏳ {m}"))

            # Dict keyed by raw mode name so lookups never fail due to emoji prefix
            _mode_items: dict[str, QTreeWidgetItem] = {}

            def add_one_save(entry):
                mode_name = entry["game_mode"]
                mode_item = _mode_items.get(mode_name)
                if mode_item is None:
                    mode_item = QTreeWidgetItem([f"📂 {mode_name}", "", ""])
                    mode_item.setFont(0, QFont("Helvetica", 11, QFont.Weight.Bold))
                    mode_item.setData(0, Qt.ItemDataRole.UserRole, None)
                    save_tree.addTopLevelItem(mode_item)
                    mode_item.setExpanded(True)
                    _mode_items[mode_name] = mode_item

                date_str = datetime.fromtimestamp(entry["mtime"]).strftime("%Y-%m-%d %H:%M") if entry["mtime"] else "—"
                size_str = f"{entry['size_mb']:.0f} MB"
                child = QTreeWidgetItem([entry["name"], date_str, size_str])
                child.setData(0, Qt.ItemDataRole.UserRole, entry)
                mode_item.addChild(child)
                total_so_far = sum(m.childCount() for m in _mode_items.values())
                status.setText(f"⏳ Found {total_so_far} save(s)…")

            def worker():
                saves = _scan_all_saves(p, log=_log, add_callback=add_one_save)
                total = len(saves)
                modes = len(_mode_items)
                _ui(lambda t=total, m=modes: status.setText(
                    f"✅ Found {t} save(s) across {m} game mode(s). Select one to inspect."
                ))

            threading.Thread(target=worker, daemon=True).start()

        def _auto_detect():
            saves_dir = _find_pz_saves_dir()
            if saves_dir:
                _load_saves_root(str(saves_dir))
            else:
                status.setText("⚠️ Could not find ~/Zomboid/Saves — use Browse instead.")

        def _browse():
            path = QFileDialog.getExistingDirectory(parent_widget, "Select Zomboid/Saves folder")
            if path:
                _load_saves_root(path)

        def _on_mod_double_clicked(item: QTreeWidgetItem, column: int):
            path_str = item.data(0, Qt.ItemDataRole.UserRole)
            if path_str and Path(path_str).exists():
                p = Path(path_str)
                if platform.system() == "Windows":
                    os.startfile(p)
                elif platform.system() == "Darwin":
                    subprocess.call(["open", str(p)])
                else:
                    subprocess.call(["xdg-open", str(p)])
            else:
                status.setText("Mod path not available or not found")

        mod_tree.itemDoubleClicked.connect(_on_mod_double_clicked)
        
        def _on_item_changed(item: QTreeWidgetItem, column: int):
            if item.data(0, Qt.ItemDataRole.UserRole) == "section":
                state = item.checkState(column)
                for i in range(item.childCount()):
                    child = item.child(i)
                    child.setHidden(state == Qt.CheckState.Unchecked)

        info_tree.itemChanged.connect(_on_item_changed)

        def _copy_mod_list():
            from PyQt6.QtWidgets import QApplication
            if not _current_mod_ids:
                status.setText("⚠️ No mod IDs loaded yet.")
                return
            QApplication.clipboard().setText("\n".join(_current_mod_ids))
            status.setText(f"✅ Copied {len(_current_mod_ids)} mod IDs to clipboard.")

        copy_mod_btn.clicked.connect(_copy_mod_list)

        # Auto-scan on startup if saves folder is known
        saves_dir = _find_pz_saves_dir()
        if saves_dir:
            saves_root_entry.setText(str(saves_dir))
            status.setText("⏳ Auto-scanning saves on startup…")
            _load_saves_root(str(saves_dir))  # triggers the scan immediately
        else:
            status.setText("⚠️ Could not auto-detect ~/Zomboid/Saves — use Browse.")

        #auto_btn.clicked.connect(_auto_detect)
        browse_btn.clicked.connect(_browse)
        save_tree.itemClicked.connect(_on_save_selected)


# ══════════════════════════════════════════════════════════════════════════════
# 3.  CONFLICT CHECKER TAB
# ══════════════════════════════════════════════════════════════════════════════

def _collect_mod_files(mod_path: Path, log=None) -> dict[str, list[Path]]:
    """
    Returns a dict mapping relative file paths to absolute Paths.
    Depth-limited and extension-filtered to avoid hanging on large mods.
    """
    RELEVANT_EXTS = {".lua", ".class", ".jar", ".txt", ".json", ".xml",
                     ".ini", ".cfg", ".png", ".ogg", ".wav"}
    SKIP_DIRS = {"chunkdata", "map", "metagrid", "zpop", "apop", "isoregiondata"}
    MAX_DEPTH = 8
    result: dict[str, list[Path]] = {}
    scanned = 0
    for root, dirs, files in os.walk(mod_path):
        depth = root[len(str(mod_path)):].count(os.sep)
        if depth >= MAX_DEPTH:
            dirs[:] = []
            continue
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        for fname in files:
            if Path(fname).suffix.lower() not in RELEVANT_EXTS:
                continue
            full = Path(root) / fname
            try:
                rel = str(full.relative_to(mod_path))
            except ValueError:
                rel = fname
            result.setdefault(rel, []).append(full)
            scanned += 1
    if log:
        log(f"Indexed {scanned} files in {mod_path.name}")
    return result


def _check_lua_function_overlap(path_a: Path, path_b: Path) -> list[str]:
    """Return Lua function names defined in both files."""
    pat = re.compile(r'(?:^|\s)function\s+([\w.:]+)\s*\(', re.M)

    def funcs(p: Path):
        try:
            return set(pat.findall(p.read_text(encoding="utf-8", errors="ignore")))
        except Exception:
            return set()

    shared = funcs(path_a) & funcs(path_b)
    return sorted(shared)


class ConflictCheckerTab:
    """Compare two mods for file and Lua function conflicts."""

    _refresh_mods_fn = None
    _set_save_mods_fn = None

    @staticmethod
    def set_save_mods(mods: list):
        """
        Called from SaveInfoTab — pre-loads a save's found mods into the
        conflict checker workshop list and resets the pickers.
        mods: list of (display_name, path_str) tuples.
        """
        if ConflictCheckerTab._set_save_mods_fn:
            _ui(lambda m=mods: ConflictCheckerTab._set_save_mods_fn(m))

    @staticmethod
    def build(parent_widget: QWidget, detected_mods: list | None = None):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        # ── Workshop list with search + sort ──────────────────────────────
        ws_group = QGroupBox("🔍 Workshop Mods — double-click to load into A or B")
        ws_layout = QVBoxLayout()

        ws_search_row = QHBoxLayout()
        ws_search = QLineEdit()
        ws_search.setPlaceholderText("Filter mods by name…")
        ws_sort = QComboBox()
        ws_sort.addItems(["Name (A-Z)", "Size (largest first)", "Last Modified", "Compatibility"])
        ws_search_row.addWidget(ws_search, stretch=1)
        ws_search_row.addWidget(QLabel("Sort:"))
        ws_search_row.addWidget(ws_sort)
        ws_layout.addLayout(ws_search_row)

        ws_tree = QTreeWidget()
        ws_tree.setHeaderLabels(["Mod Name", "Size", "Last Modified", "Compat", "Path"])
        ws_tree.setColumnWidth(0, 320)
        ws_tree.setMaximumHeight(200)
        ws_tree.setSortingEnabled(True)
        ws_layout.addWidget(ws_tree)

        ws_hint = QLabel("Double-click: 1st click sets Mod A, 2nd sets Mod B, then alternates.")
        ws_hint.setStyleSheet("color: gray; font-size: 11px;")
        ws_layout.addWidget(ws_hint)
        ws_group.setLayout(ws_layout)
        layout.addWidget(ws_group)

        # ── Manual path pickers ───────────────────────────────────────────
        def _make_picker(label_text: str):
            group = QGroupBox(label_text)
            row = QHBoxLayout()
            entry = QLineEdit()
            entry.setPlaceholderText("Path to mod folder — or double-click from list above")
            browse = QPushButton("📁 Browse")
            clear_btn = QPushButton("✖")
            clear_btn.setFixedWidth(32)
            row.addWidget(entry, stretch=1)
            row.addWidget(browse)
            row.addWidget(clear_btn)
            group.setLayout(row)

            def _do_browse(lbl=label_text, e=entry):
                p = QFileDialog.getExistingDirectory(parent_widget, f"Select {lbl}")
                if p:
                    e.setText(p)

            browse.clicked.connect(_do_browse)
            clear_btn.clicked.connect(entry.clear)
            return group, entry

        group_a, entry_a = _make_picker("⚔️  Mod A")
        group_b, entry_b = _make_picker("⚔️  Mod B")
        layout.addWidget(group_a)
        layout.addWidget(group_b)

        # ── Run button + scan log ─────────────────────────────────────────
        run_row = QHBoxLayout()
        run_btn = QPushButton("🔍 Check A vs B")
        run_btn.setFixedHeight(44)
        progress = QProgressBar()
        progress.setVisible(False)

        # ── Run buttons row 1: A-vs-B + Workshop loader ───────────────────
        run_row1 = QHBoxLayout()
        run_btn = QPushButton("🔍 Check A vs B")
        run_btn.setFixedHeight(36)
        workshop_btn = QPushButton("📦 Load Workshop Mods")
        workshop_btn.setFixedHeight(36)
        workshop_btn.setToolTip("Load the full workshop mod cache into the list above for manual A vs B comparison.")
        progress = QProgressBar()
        progress.setVisible(False)
        run_row1.addWidget(run_btn, stretch=1)
        run_row1.addWidget(workshop_btn, stretch=1)
        run_row1.addWidget(progress, stretch=1)
        layout.addLayout(run_row1)

        # ── Run buttons row 2: Bulk scan + stop ───────────────────────────
        run_row2 = QHBoxLayout()
        bulk_btn = QPushButton("🔥 Bulk One-vs-All Scan")
        bulk_btn.setFixedHeight(36)
        bulk_btn.setToolTip("Scans every mod in the list against every other.\nResults + full report saved automatically.")
        stop_btn = QPushButton("⏹ Stop")
        stop_btn.setFixedHeight(36)
        stop_btn.setEnabled(False)
        copy_btn = QPushButton("📋 Copy Mod IDs")
        copy_btn.setFixedHeight(36)
        run_row2.addWidget(bulk_btn, stretch=2)
        run_row2.addWidget(stop_btn, stretch=1)
        run_row2.addWidget(copy_btn, stretch=1)
        layout.addLayout(run_row2)

        log_box = QTextEdit()
        log_box.setReadOnly(True)
        log_box.setFont(QFont("Consolas", 10))
        log_box.setMaximumHeight(80)
        log_box.setPlaceholderText("Scan log will appear here…")
        layout.addWidget(log_box)

        # ── Results tree ──────────────────────────────────────────────────
        results = QTreeWidget()
        results.setHeaderLabels(["Type", "File / Symbol", "Detail"])
        results.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        results.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(results, stretch=1)

        status = QLabel("Select two mods and click Check.")
        layout.addWidget(status)
        parent_widget.setLayout(layout)

        # ── Workshop tree ─────────────────────────────────────────────────
        _all_mods: list = list(detected_mods) if detected_mods else []
        _dbl_slot = [0]  # 0=A, 1=B, alternates

        def _populate_ws_tree(mods: list):
            if DEBUG: DebugTab.dbg(f"[CONFLICT] _populate_ws_tree called with {len(mods)} mods (filter={repr(ws_search.text())})")
            ws_tree.clear()
            kw = ws_search.text().lower()
            for entry in mods:
                name, mod_path, size_bytes, mtime, compat = entry
                if kw and kw not in name.lower():
                    continue
                size_str = f"{size_bytes/1024/1024:.1f} MB" if size_bytes else "—"
                date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") if mtime else "—"
                item = QTreeWidgetItem([name, size_str, date_str, compat, str(mod_path)])
                ws_tree.addTopLevelItem(item)
            ws_tree.resizeColumnToContents(0)
            ws_tree.viewport().update()  # force redraw

        def _apply_ws_sort():
            idx = ws_sort.currentIndex()
            order = Qt.SortOrder.DescendingOrder if idx in (1, 2) else Qt.SortOrder.AscendingOrder
            ws_tree.sortItems(idx, order)

        def _on_ws_dbl_click(item: QTreeWidgetItem, _col: int):
            path = item.text(4)
            if not path:
                return
            if _dbl_slot[0] == 0:
                entry_a.setText(path)
                status.setText(f"Loaded into Mod A: {item.text(0)}")
                _dbl_slot[0] = 1
            else:
                entry_b.setText(path)
                status.setText(f"Loaded into Mod B: {item.text(0)}")
                _dbl_slot[0] = 0

        def _copy_mods():
            from PyQt6.QtWidgets import QApplication
            lines = []
            for i in range(ws_tree.topLevelItemCount()):
                item = ws_tree.topLevelItem(i)
                lines.append(item.text(0))  # mod name
            if not lines:
                status.setText("⚠️ No mods in list to copy.")
                return
            QApplication.clipboard().setText("\n".join(lines))
            status.setText(f"Copied {len(lines)} mod name(s) to clipboard.")

        copy_btn.clicked.connect(_copy_mods)

        def _load_workshop_mods():
            """Reload the full workshop cache into the mod list."""
            from gui_helpers import DOCS_DIR
            import json as _json
            cache_path = DOCS_DIR / "workshop_cache.json"
            if not cache_path.exists():
                QMessageBox.information(parent_widget, "No Cache",
                    "No workshop cache found.\nScan the workshop on the Main tab first.")
                return
            try:
                data = _json.loads(cache_path.read_bytes().decode("utf-8", errors="ignore"))
                mods_raw = data.get("mods", [])
                as_5t = [tuple(m) for m in mods_raw if len(m) >= 5]
                nonlocal _all_mods
                _all_mods = as_5t
                ws_search.clear()
                _populate_ws_tree(as_5t)
                if DEBUG: DebugTab.dbg(f"[CONFLICT] Workshop mods loaded: {len(as_5t)} entries")
                status.setText(f"Loaded {len(as_5t)} workshop mods — double-click to set A or B.")
            except Exception as ex:
                QMessageBox.warning(parent_widget, "Load Failed", str(ex))

        workshop_btn.clicked.connect(_load_workshop_mods)

        def _stop_scan():
            global _stop_bulk
            _stop_bulk = True
            stop_btn.setEnabled(False)

        stop_btn.clicked.connect(_stop_scan)

        ws_search.textChanged.connect(lambda _: _populate_ws_tree(_all_mods))
        ws_sort.currentIndexChanged.connect(lambda _: _apply_ws_sort())
        ws_tree.itemDoubleClicked.connect(_on_ws_dbl_click)
        if _all_mods:
            _populate_ws_tree(_all_mods)

        # ── Log helper ────────────────────────────────────────────────────
        def _log(msg: str):
            _ui(lambda m=msg: log_box.append(m))

        # ── Conflict check logic ──────────────────────────────────────────
        def _run_check():
            pa_str = entry_a.text().strip()
            pb_str = entry_b.text().strip()
            if not pa_str:
                QMessageBox.warning(parent_widget, "Mod A", "Mod A path is empty.")
                return
            if not pb_str:
                QMessageBox.warning(parent_widget, "Mod B", "Mod B path is empty.")
                return
            path_a, path_b = Path(pa_str), Path(pb_str)
            if not path_a.is_dir() and not path_a.is_file():
                QMessageBox.warning(parent_widget, "Mod A", "Mod A path does not exist.")
                return
            if not path_b.is_dir() and not path_b.is_file():
                QMessageBox.warning(parent_widget, "Mod B", "Mod B path does not exist.")
                return
            if path_a.resolve() == path_b.resolve():
                QMessageBox.warning(parent_widget, "Same Mod", "Both paths point to the same mod.")
                return

            run_btn.setEnabled(False)
            progress.setVisible(True)
            progress.setRange(0, 0)
            results.clear()
            log_box.clear()
            status.setText("⏳ Scanning…")

            def worker():
                try:
                    _log(f"Mod A: {path_a.name}")
                    files_a = _collect_mod_files(path_a, _log)
                    _log(f"Mod A → {len(files_a)} relevant files")

                    _log(f"Mod B: {path_b.name}")
                    files_b = _collect_mod_files(path_b, _log)
                    _log(f"Mod B → {len(files_b)} relevant files")

                    _ui(lambda: progress.setRange(0, len(files_a) + len(files_b)))
                    _ui(lambda: progress.setValue(0))

                    shared = set(files_a) & set(files_b)
                    file_conflicts = []
                    lua_conflicts = []

                    total = len(shared)
                    for i, rel in enumerate(sorted(shared), 1):
                        if Path(rel).name.lower() in SKIP:
                            continue
                        file_conflicts.append(rel)
                        if rel.lower().endswith(".lua"):
                            for fn in _check_lua_function_overlap(files_a[rel][0], files_b[rel][0]):
                                lua_conflicts.append((rel, fn))
                        _ui(lambda v=i: progress.setValue(v))

                    _ui(lambda fc=file_conflicts, lc=lua_conflicts: _populate(fc, lc))
                finally:
                    _ui(lambda: (run_btn.setEnabled(True), progress.setVisible(False)))

            threading.Thread(target=worker, daemon=True).start()

        def _populate(file_conflicts: list, lua_conflicts: list):
            results.clear()
            if not file_conflicts and not lua_conflicts:
                item = QTreeWidgetItem(["🎉 Looks clean!", "—", "No overlapping files or shared Lua function definitions found.\nThese two mods should coexist without hard conflicts."])
                item.setBackground(0, QColor(40, 140, 40))
                item.setForeground(0, QColor(220, 255, 220))
                results.addTopLevelItem(item)
                status.setText("✅ No file or Lua function conflicts detected.")
                return
            for rel in file_conflicts:
                item = QTreeWidgetItem(["📄 File Overlap", rel, "Both mods ship this file"])
                item.setBackground(0, QColor(120, 60, 0))
                results.addTopLevelItem(item)
            for rel, fn in lua_conflicts:
                item = QTreeWidgetItem(["⚠️ Lua Function", fn, f"Both define this in {Path(rel).name}"])
                item.setBackground(0, QColor(139, 0, 0))
                results.addTopLevelItem(item)
            results.resizeColumnToContents(0)
            status.setText(
                f"Found {len(file_conflicts)} file overlap(s) and "
                f"{len(lua_conflicts)} Lua function conflict(s)."
            )

        def _refresh_mods(mods: list):
            nonlocal _all_mods
            _all_mods = list(mods)
            _populate_ws_tree(_all_mods)

        def _set_save_mods_impl(save_mods: list):
            """
            Pre-load save mods into the conflict checker workshop list.
            Called via _ui() so we are already on the main thread.
            Clears the search filter FIRST so nothing gets hidden.
            """
            nonlocal _all_mods
            as_5t = [(name, path, 0, 0, "From Save") for name, path in save_mods]
            _all_mods = as_5t

            # Clear filters before populating — a non-empty search hides everything
            ws_search.clear()
            entry_a.clear()
            entry_b.clear()
            _dbl_slot[0] = 0

            if DEBUG: DebugTab.dbg(f"[CONFLICT] _set_save_mods_impl: populating {len(as_5t)} mods into ws_tree")
            # Populate synchronously — safe because _ui() already put us on main thread
            _populate_ws_tree(as_5t)
            ws_tree.resizeColumnToContents(0)
            ws_tree.resizeColumnToContents(1)
            ws_tree.resizeColumnToContents(2)

            status.setText(
                f"Loaded {len(save_mods)} mods from save — "
                f"double-click to set Mod A and Mod B."
            )
        
        def _bulk_one_vs_all():
            global _stop_bulk
            _stop_bulk = False

            if not _all_mods or len(_all_mods) < 2:
                QMessageBox.warning(parent_widget, "Bulk Scan",
                    "Need at least 2 mods in the list.\nLoad mods via Save Info tab or Workshop Mods button first.")
                return

            # Build path list from _all_mods (5-tuple: name, path, size, mtime, compat)
            mod_list = []
            for entry in _all_mods:
                name = entry[0]
                path = Path(entry[1])
                if path.exists():
                    mod_list.append((name, path))

            if len(mod_list) < 2:
                status.setText("⚠️ Not enough valid mod paths to scan.")
                return

            total_pairs = len(mod_list) * (len(mod_list) - 1) // 2
            run_btn.setEnabled(False)
            bulk_btn.setEnabled(False)
            stop_btn.setEnabled(True)
            progress.setVisible(True)
            progress.setRange(0, total_pairs)
            progress.setValue(0)
            results.clear()
            log_box.clear()
            _log(f"Starting bulk scan: {len(mod_list)} mods, {total_pairs} pairs…")
            if DEBUG: DebugTab.dbg(f"[CONFLICT] Bulk scan started: {len(mod_list)} mods, {total_pairs} pairs", "[CONFLICT]")

            def worker():
                global _stop_bulk
                all_conflicts = []
                step = 0

                for i, (name_a, path_a) in enumerate(mod_list):
                    if _stop_bulk:
                        _log("⏹ Stopped by user.")
                        break
                    _log(f"→ Indexing {name_a} ({i+1}/{len(mod_list)})")
                    if path_a not in _bulk_cache:
                        _bulk_cache[path_a] = _collect_mod_files(path_a)
                    files_a = _bulk_cache[path_a]

                    for j in range(i + 1, len(mod_list)):
                        if _stop_bulk:
                            break
                        name_b, path_b = mod_list[j]
                        if path_b not in _bulk_cache:
                            _bulk_cache[path_b] = _collect_mod_files(path_b)
                        files_b = _bulk_cache[path_b]

                        shared = set(files_a) & set(files_b)
                        file_conflicts, lua_conflicts = [], []
                        for rel in shared:
                            if Path(rel).name.lower() in {"mod.info", "preview.png", "thumb.png"}:
                                continue
                            file_conflicts.append(rel)
                            if rel.lower().endswith(".lua"):
                                for fn in _check_lua_function_overlap(files_a[rel][0], files_b[rel][0]):
                                    lua_conflicts.append((rel, fn))

                        if file_conflicts or lua_conflicts:
                            all_conflicts.append((name_a, name_b, file_conflicts, lua_conflicts))
                            _log(f"  ⚠️ Conflict: {name_a} ↔ {name_b} "
                                 f"({len(file_conflicts)} files, {len(lua_conflicts)} Lua)")

                        step += 1
                        _ui(lambda v=step: progress.setValue(v))

                # Save report
                from gui_helpers import DOCS_DIR as _DD
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                report_path = _DD / f"bulk_conflicts_{timestamp}.txt"
                try:
                    with open(report_path, "w", encoding="utf-8") as f:
                        f.write("=== BULK MOD CONFLICT REPORT ===\n")
                        f.write(f"Date: {datetime.now()}\n")
                        f.write(f"Mods: {len(mod_list)}  Pairs: {step}  "
                                f"Stopped early: {'Yes' if _stop_bulk else 'No'}\n\n")
                        for a, b, files, lua in all_conflicts:
                            f.write(f"\nCONFLICT: {a} ↔ {b}\n")
                            for rel in files:
                                f.write(f"  📄 {rel}\n")
                            for rel, fn in lua:
                                f.write(f"  ⚠️ {fn} in {rel}\n")
                    _log(f"Report saved: {report_path.name}")
                except Exception as ex:
                    _log(f"Report save failed: {ex}")

                _ui(lambda c=all_conflicts: _populate_bulk_results(c))
                _ui(lambda: status.setText(
                    f"Done — {len(all_conflicts)} conflicting pair(s) out of {step} checked."
                ))
                _ui(lambda: (
                    run_btn.setEnabled(True),
                    bulk_btn.setEnabled(True),
                    stop_btn.setEnabled(False),
                    progress.setVisible(False)
                ))

            threading.Thread(target=worker, daemon=True).start()

        def _populate_bulk_results(conflicts):
            results.clear()
            if not conflicts:
                item = QTreeWidgetItem(["🎉 Clean!", "—", "No conflicts found between any save mods!"])
                item.setBackground(0, QColor(40, 140, 40))
                results.addTopLevelItem(item)
                return

            for a, b, files, lua in conflicts:
                pair_item = QTreeWidgetItem([f"{a} ↔ {b}", "", f"{len(files)} files + {len(lua)} Lua functions"])
                pair_item.setBackground(0, QColor(120, 60, 0))
                results.addTopLevelItem(pair_item)
                for rel in files:
                    results.addTopLevelItem(QTreeWidgetItem(["📄 File", rel, "Both mods contain this file"]))
                for rel, fn in lua:
                    results.addTopLevelItem(QTreeWidgetItem(["⚠️ Lua", fn, f"Defined in both ({rel})"]))

        ConflictCheckerTab._refresh_mods_fn = _refresh_mods
        ConflictCheckerTab._set_save_mods_fn = _set_save_mods_impl
        bulk_btn.clicked.connect(_bulk_one_vs_all)
        run_btn.clicked.connect(_run_check)

    @staticmethod
    def refresh_mods(mods: list):
        """Call from gui.py after workshop scan completes to populate the mod list."""
        if ConflictCheckerTab._refresh_mods_fn:
            _ui(lambda m=mods: ConflictCheckerTab._refresh_mods_fn(m))
        """Call from gui.py after workshop scan completes to populate the mod list."""
        if ConflictCheckerTab._refresh_mods_fn:
            _ui(lambda m=mods: ConflictCheckerTab._refresh_mods_fn(m))

