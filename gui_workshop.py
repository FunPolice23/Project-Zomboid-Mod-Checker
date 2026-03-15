from pathlib import Path
from datetime import datetime
from PyQt6.QtCore import QTimer, Qt, QObject, pyqtSignal
from PyQt6.QtWidgets import QMessageBox, QTreeWidgetItem
from gui_helpers import DOCS_DIR
import json
import threading
import traceback

# ── Thread-safe main-thread dispatcher ───────────────────────────────────────
class _WS_Dispatcher(QObject):
    _call = pyqtSignal(object)
    def __init__(self):
        super().__init__()
        self._call.connect(lambda fn: fn())

_ws_dispatcher = _WS_Dispatcher()

def _ui(fn):
    """Schedule fn() on the main Qt thread. Safe to call from any thread."""
    _ws_dispatcher._call.emit(fn)

CACHE_FILE = DOCS_DIR / "workshop_cache.json"
CACHE_VERSION = 2

class WorkshopScanner:
    """All workshop scanning logic — imported by gui.py"""

    @staticmethod
    def scan_workshop(gui, content_path: Path, force_refresh=False):
        if not force_refresh and WorkshopScanner.load_cache(gui):
            return

        gui.scanning = True
        gui.detected_mods.clear()
        gui.pending_batch.clear()
        gui.seen_mod_roots.clear()
        gui.workshop_tree.clear()

        def worker():
            try:
                for mod_id_dir in content_path.iterdir():
                    if not gui.scanning: break
                    if not mod_id_dir.name.isdigit(): continue
                    _ui(lambda n=mod_id_dir.name: gui.console_text.append(f"→ Found mod ID folder: {n}\n"))
                    WorkshopScanner._recurse_mod_folder(gui, mod_id_dir)
                if gui.scanning:
                    _ui(gui._finish_scan_ui)
                    WorkshopScanner.save_cache(gui)
            except Exception as e:
                error_msg = f"=== THREAD CRASH IN SCANNER ===\n{traceback.format_exc()}"
                with open(str(DOCS_DIR / "crash.log"), "w", encoding="utf-8") as f:
                    f.write(error_msg)
                _ui(lambda err=e: QMessageBox.critical(gui, "Scanner Crash", f"Scan crashed!\nDetails saved to crash.log\n\n{str(err)[:300]}"))

        threading.Thread(target=worker, daemon=True).start()

    @staticmethod
    def save_cache(gui):
        """Save after successful scan (versioned)"""
        try:
            data = {
                "version": CACHE_VERSION,
                "mods": gui.detected_mods,
                "scan_date": datetime.now().isoformat()
            }
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            gui.console_text.append("💾 Cache saved\n")
        except Exception as e:
            print(f"Cache save failed: {e}")

    @staticmethod
    def load_cache(gui):
        """Load cached mods on startup (fast!)"""
        if not CACHE_FILE.exists():
            return False

        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)

            if data.get("version") != CACHE_VERSION:
                gui.console_text.append("⚠️  Cache version changed — forcing full rescan\n")
                return False

            gui.detected_mods = [tuple(item) for item in data.get("mods", [])]
            # FIXED: queue the cached mods so they appear in the tree
            gui.pending_batch = list(gui.detected_mods)

            gui.console_text.append(f"✅ Loaded {len(gui.detected_mods)} mods from cache\n")
            QTimer.singleShot(0, gui._live_add_batch)
            QTimer.singleShot(50, gui._final_sort_and_resize)  # ensures sorting + resize
            return True
        except Exception as e:
            gui.console_text.append(f"⚠️  Cache corrupted — starting fresh scan ({e})\n")
            return False

    @staticmethod
    def _recurse_mod_folder(gui, folder: Path, depth: int = 0):
        if not gui.scanning or depth > 10: 
            return

        # ── Check for mod.info FIRST ──
        if (folder / "mod.info").exists():
            abs_path = str(folder.resolve())
            if abs_path in gui.seen_mod_roots: 
                return
            gui.seen_mod_roots.add(abs_path)

            # Climb up past common/, 42/, AND mods/ to get the TRUE mod root
            true_root = folder
            while true_root.name.lower() in {"common", "42", "mods"} and true_root.parent != true_root:
                true_root = true_root.parent

            WorkshopScanner._process_single_mod(gui, true_root)
            return

        # ── Recurse into common/42/mods folders ──
        folder_lower = folder.name.lower()
        if folder_lower in {"common", "42", "mods"}:
            for sub in folder.iterdir():
                if sub.is_dir():
                    WorkshopScanner._recurse_mod_folder(gui, sub, depth + 1)
            return

        # Normal recursion
        for sub in folder.iterdir():
            if sub.is_dir():
                WorkshopScanner._recurse_mod_folder(gui, sub, depth + 1)

    @staticmethod
    def _process_single_mod(gui, mod_folder: Path):
        from gui_helpers import estimate_compat_from_modinfo  # lazy import
        display_name, compat = estimate_compat_from_modinfo(mod_folder)
        size = sum(f.stat().st_size for f in mod_folder.rglob("*") if f.is_file())
        mtime = max((f.stat().st_mtime for f in mod_folder.rglob("*") if f.is_file()), default=0)

        gui.detected_mods.append((display_name, str(mod_folder), size, mtime, compat))
        gui.pending_batch.append((display_name, str(mod_folder), size, mtime, compat))

        batch_size = [9999, 50, 10, 1][gui.batch_combo.currentIndex()]
        if len(gui.pending_batch) >= batch_size:
            QTimer.singleShot(0, gui._live_add_batch)

    @staticmethod
    def live_add_batch(gui):
        if not gui.pending_batch: return
        for name, path, size_bytes, mtime, compat in gui.pending_batch:
            size_str = f"{size_bytes / 1024 / 1024:.1f} MB" if size_bytes else "—"
            date_str = datetime.fromtimestamp(mtime).strftime("%Y-%m-%d") if mtime else "—"
            item = QTreeWidgetItem([name, size_str, date_str, compat, path])
            item.setData(1, Qt.ItemDataRole.UserRole, size_bytes)
            gui.workshop_tree.addTopLevelItem(item)
        gui.console_text.append(f"→ Found {len(gui.detected_mods)} mods so far...\n")
        gui.workshop_tree.viewport().update()
        gui.pending_batch.clear()

    @staticmethod
    def finish_scan_ui(gui):
        gui.scanning = False
        QTimer.singleShot(0, lambda: WorkshopScanner.live_add_batch(gui))
        QTimer.singleShot(50, gui._final_sort_and_resize)

        # Final summary
        total_size_mb = sum(item.data(1, Qt.ItemDataRole.UserRole) or 0 for item in gui.workshop_tree.findItems("*", Qt.MatchFlag.MatchWildcard) if item) / 1024 / 1024
        gui.console_text.append(f"✅ Scan complete — {len(gui.detected_mods)} mods • ~{total_size_mb:.1f} MB total\n")
