import sys
import json
import traceback
import threading
import webbrowser
from pathlib import Path
import platform
import subprocess, os

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QComboBox, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QMessageBox, QFileDialog, QGroupBox, QStatusBar,
    QGraphicsOpacityEffect, QCheckBox, QSlider, QRadioButton, QButtonGroup,
    QHeaderView
)
from PyQt6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QUrl
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtGui import QFont, QColor

# ── split modules ──
from gui_helpers import find_pz_workshop_content_path, get_steam_install_path, parse_libraryfolders_vdf, DOCS_DIR
from gui_workshop import WorkshopScanner, CACHE_FILE
from gui_themes import THEME_STYLES
from indexer import GameAPI
from modparser import ModReferences
from comparison import CompatibilityChecker

class ConsoleRedirect:
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.buffer = ""

    def write(self, text):
        self.buffer += text
        if "\n" in self.buffer:
            QTimer.singleShot(0, lambda: self.text_widget.append(self.buffer.strip()))
            self.buffer = ""

    def flush(self):
        pass

class CompatibilityGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("🧟 PZ Mod Compatibility Checker – Build 42 Edition")
        self.setGeometry(80, 80, 1400, 980)
        self.setStyleSheet(THEME_STYLES["Dark Classic"])

        self.issues = []
        self.current_issues = []
        self.detected_mods = []
        self._populating = False
        self.pending_batch = []
        self.scanning = False
        self.running = False
        self.seen_mod_roots = set()
        self.verbose_scan = True

        self.config_path = Path.home() / ".pzmodchecker_config.json"
        self.cache_var = str(DOCS_DIR / "game_api_cache.pkl")
        self.output_var = str(DOCS_DIR / "compatibility_report.txt")

        self._build_ui()
        #self.tabs.currentChanged.connect(self._on_tab_changed)
        self._load_last_paths()
        self._detect_workshop()
        self.statusBar().showMessage("✅ v1.2 - Initiated - Enjoy")
        self._on_mode_changed()

    # Settings Tab    
    def _build_settings_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)

        # Batch size
        batch_group = QGroupBox("📋 Workshop List Batch Size")
        batch_layout = QVBoxLayout()
        self.batch_combo = QComboBox()
        self.batch_combo.addItems(["All at once", "Medium batches (50)", "Small batches (10)", "One by one (smoothest)"])
        self.batch_combo.setCurrentIndex(2)
        batch_layout.addWidget(QLabel("How fast mods appear in the list:"))
        batch_layout.addWidget(self.batch_combo)
        batch_group.setLayout(batch_layout)
        layout.addWidget(batch_group)

        # Performance
        perf_group = QGroupBox("⚡ Performance")
        perf_layout = QVBoxLayout()
        self.cache_clear_btn = QPushButton("🗑️ Clear Game API Cache")
        self.cache_clear_btn.clicked.connect(self._clear_cache)
        perf_layout.addWidget(self.cache_clear_btn)

        self.mod_cache_clear_btn = QPushButton("🗑️ Clear Workshop Mod Cache")
        self.mod_cache_clear_btn.clicked.connect(self._clear_mod_cache)
        perf_layout.addWidget(self.mod_cache_clear_btn)

        # NEW: Open Data Folder button
        self.open_folder_btn = QPushButton("📁 Open Data Folder")
        self.open_folder_btn.clicked.connect(self._open_data_folder)
        perf_layout.addWidget(self.open_folder_btn)

        self.anim_check = QCheckBox("✨ Enable fade/slide animations")
        self.anim_check.setChecked(True)
        perf_layout.addWidget(self.anim_check)
        self.verbose_check = QCheckBox("Verbose Workshop Scan (show every mod)")
        self.verbose_check.setChecked(True)
        self.verbose_check.toggled.connect(lambda c: setattr(self, 'verbose_scan', c))
        perf_layout.addWidget(self.verbose_check)
        perf_group.setLayout(perf_layout)
        layout.addWidget(perf_group)

        # Theme selector (unchanged)
        theme_group = QGroupBox("🎨 Color Scheme")
        theme_layout = QVBoxLayout()
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(list(THEME_STYLES.keys()))
        self.theme_combo.currentTextChanged.connect(self._change_theme)
        theme_layout.addWidget(QLabel("Choose a color scheme:"))
        theme_layout.addWidget(self.theme_combo)
        theme_group.setLayout(theme_layout)
        layout.addWidget(theme_group)

        # Window mode & Transparency (unchanged)
        win_group = QGroupBox("🪟 Window Mode")
        win_layout = QVBoxLayout()
        self.win_combo = QComboBox()
        self.win_combo.addItems(["Windowed", "Borderless", "Fullscreen"])
        self.win_combo.currentTextChanged.connect(self._change_window_mode)
        win_layout.addWidget(QLabel("Choose window style:"))
        win_layout.addWidget(self.win_combo)
        win_group.setLayout(win_layout)
        layout.addWidget(win_group)

        trans_group = QGroupBox("🌫️ Window Transparency")
        trans_layout = QVBoxLayout()
        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setRange(70, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.valueChanged.connect(self._set_opacity)
        trans_layout.addWidget(QLabel("Drag to change transparency:"))
        trans_layout.addWidget(self.opacity_slider)
        trans_group.setLayout(trans_layout)
        layout.addWidget(trans_group)

        layout.addStretch()
        self.tab_settings.setLayout(layout)

    def _filter_workshop(self, text):
        for i in range(self.workshop_tree.topLevelItemCount()):
            item = self.workshop_tree.topLevelItem(i)
            item.setHidden(text.lower() not in item.text(0).lower())

    # Draggable borderless window
    def mousePressEvent(self, event):
        if self.win_combo.currentText() == "Borderless":
            self.old_pos = event.globalPosition().toPoint()
            
    def mouseMoveEvent(self, event):
        if hasattr(self, 'old_pos') and self.win_combo.currentText() == "Borderless":
            delta = event.globalPosition().toPoint() - self.old_pos
            self.move(self.pos() + delta)
            self.old_pos = event.globalPosition().toPoint()

    def _set_opacity(self, val):
        self.setWindowOpacity(val / 100)

    def _clear_cache(self):
        cache_path = Path(self.cache_var)
        if cache_path.exists():
            cache_path.unlink()
            QMessageBox.information(self, "Cache Cleared", "Game API cache deleted!\nNext scan will rebuild from scratch.")
    
    def _clear_mod_cache(self):
        if CACHE_FILE.exists():
            CACHE_FILE.unlink()
            QMessageBox.information(self, "Cache Cleared", "Workshop mod cache deleted!\nNext scan will rebuild from scratch.")
            self.workshop_tree.clear()
            self.detected_mods.clear()
            self.pending_batch.clear()
            self.console_text.append("🗑️ Workshop cache cleared — ready for fresh scan!\n")

    def _open_data_folder(self):
        folder = Path(self.cache_var).parent
        try:
            if platform.system() == "Windows":
                os.startfile(folder)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", str(folder)])
            else:
                subprocess.Popen(["xdg-open", str(folder)])
            self.console_text.append(f"📁 Opened data folder: {folder}\n")
        except Exception as e:
            QMessageBox.warning(self, "Open Folder", f"Could not open folder:\n{str(e)}")

    def _build_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_main = QWidget()
        self.tab_console = QWidget()
        self.tab_results = QWidget()
        self.tab_map = QWidget()
        self.tab_docs = QWidget()
        self.tab_settings = QWidget()

        self.tabs.addTab(self.tab_main, "🏠 Main")
        self.tabs.addTab(self.tab_console, "📜 Console")
        self.tabs.addTab(self.tab_results, "📊 Results")
        self.tabs.addTab(self.tab_map, "🗺️ B42 Map")
        self.tabs.addTab(self.tab_docs, "📖 B42 Docs")
        self.tabs.addTab(self.tab_settings, "⚙️ Settings")

        self._build_main_tab()
        self._build_console_tab()
        self._build_results_tab()
        self._build_map_tab()
        self._build_docs_tab()
        self._build_settings_tab()

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

    def _build_main_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)

        # ── Analysis Mode (compact horizontal radios) ──
        mode_group = QGroupBox("🔬 Analysis Mode")
        mode_layout = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_jar = QRadioButton("📦 JAR Mode")
        self.mode_folder = QRadioButton("📁 Folder Mode")
        self.mode_lua = QRadioButton("⚡ Lua-Only Mode")
        self.mode_jar.setChecked(True)
        for rb in (self.mode_jar, self.mode_folder, self.mode_lua):
            self.mode_group.addButton(rb)
            mode_layout.addWidget(rb)

        self.mode_group.buttonClicked.connect(self._on_mode_changed)
        mode_layout.addWidget(QLabel("   Game Source Path:"))
        self.game_entry = QLineEdit()
        self.game_browse_btn = QPushButton("Browse", clicked=self._browse_game)
        mode_layout.addWidget(self.game_entry)
        mode_layout.addWidget(self.game_browse_btn)
        mode_group.setLayout(mode_layout)
        layout.addWidget(mode_group)

        # ── Mod to Check (compact horizontal radios) ──
        mod_group = QGroupBox("📦 Mod to Check")
        m_layout = QHBoxLayout()
        self.mod_mode_group = QButtonGroup(self)
        self.mod_jar = QRadioButton("📦 JAR")
        self.mod_folder = QRadioButton("📁 Folder")
        self.mod_pure_lua = QRadioButton("⚡ Pure Lua")
        self.mod_jar.setChecked(True)
        for rb in (self.mod_jar, self.mod_folder, self.mod_pure_lua):
            self.mod_mode_group.addButton(rb)
            m_layout.addWidget(rb)

        self.mod_mode_group.buttonClicked.connect(self._on_mod_mode_changed)
        m_layout.addWidget(QLabel("   Mod Path:"))
        self.mod_entry = QLineEdit()
        self.mod_browse_btn = QPushButton("Browse", clicked=self._browse_mod)
        m_layout.addWidget(self.mod_entry)
        m_layout.addWidget(self.mod_browse_btn)
        mod_group.setLayout(m_layout)
        layout.addWidget(mod_group)

        # ── Workshop Mods (tree gets maximum vertical space) ──
        ws_group = QGroupBox("🔍 Workshop Mods (double-click to load)")
        ws_layout = QVBoxLayout()
        self.workshop_entry = QLineEdit()
        self.workshop_entry.setReadOnly(True)
        ws_layout.addWidget(self.workshop_entry)

        search_layout = QHBoxLayout()
        self.ws_search = QLineEdit()
        self.ws_search.setPlaceholderText("🔍 Type mod name to filter...")
        self.ws_search.textChanged.connect(self._filter_workshop)
        search_layout.addWidget(self.ws_search)
        ws_layout.addLayout(search_layout)

        sort_h = QHBoxLayout()
        sort_h.addWidget(QLabel("Sort by:"))
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name (A-Z)", "Size (largest first)", "Last Modified", "Compatibility"])
        self.sort_combo.currentIndexChanged.connect(self._apply_sort)
        sort_h.addWidget(self.sort_combo)
        ws_layout.addLayout(sort_h)

        self.workshop_tree = QTreeWidget()
        self.workshop_tree.setHeaderLabels(["Mod Name", "Size", "Last Modified", "Compat", "Path"])
        self.workshop_tree.setSortingEnabled(True)
        self.workshop_tree.setColumnWidth(0, 380)
        self.workshop_tree.itemDoubleClicked.connect(self._on_mod_clicked)
        ws_layout.addWidget(self.workshop_tree, stretch=1)   # ← tree takes all remaining space

        ws_group.setLayout(ws_layout)
        layout.addWidget(ws_group)

        bottom_row = QHBoxLayout()
        self.run_btn = QPushButton("🚀 Run Compatibility Check")
        self.run_btn.setFixedHeight(55)
        self.run_btn.clicked.connect(self._start_check)

        refresh_btn = QPushButton("🔄 Refresh List")
        refresh_btn.clicked.connect(lambda: WorkshopScanner.scan_workshop(self, Path(self.workshop_entry.text() or "."), force_refresh=True))

        scan_btn = QPushButton("🔍 Scan All Workshop Mods")
        scan_btn.clicked.connect(self._scan_workshop)

        bottom_row.addWidget(self.run_btn, stretch=2)
        bottom_row.addWidget(refresh_btn)
        bottom_row.addWidget(scan_btn)
        layout.addLayout(bottom_row)

        self.tab_main.setLayout(layout)

    def _build_map_tab(self):
        layout = QVBoxLayout()
        btn_row = QHBoxLayout()
        
        self.map_b42_btn = QPushButton("🗺️ B42 Map")
        self.map_b41_btn = QPushButton("🗺️ Classic Map")
        self.map_b42_btn.clicked.connect(lambda: self.map_view.setUrl(QUrl("https://b42map.com/")))
        btn_row.addWidget(self.map_b42_btn)
        layout.addLayout(btn_row)

        self.map_view = QWebEngineView()
        self.map_view.setUrl(QUrl("https://b42map.com/"))
        layout.addWidget(self.map_view, stretch=1)
        #self.tab_map.setLayout(layout)

    def _build_docs_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        title = QLabel("📖 Project Zomboid Build 42 Official Docs")
        title.setFont(QFont("Helvetica", 22, QFont.Weight.Bold))
        layout.addWidget(title)

        docs = [
            ("Events", "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html"),
            ("Callbacks", "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Callbacks.html"),
            ("Hooks", "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Hooks.html"),
            ("JavaDocs", "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/"),
            ("Lua Namespace", "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/namespaceumbrella.html"),
            ("Annotated", "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html"),
            ("Files", "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/files.html"),
        ]
        for name, url in docs:
            btn = QPushButton(f"📄 Open {name}")
            btn.clicked.connect(lambda _, u=url: webbrowser.open(u))
            layout.addWidget(btn)

        layout.addStretch()
        self.tab_docs.setLayout(layout)

    def _build_console_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        self.phase_label = QLabel("Waiting...")
        self.phase_label.setFont(QFont("Helvetica", 15))
        layout.addWidget(self.phase_label)
        self.console_text = QTextEdit()
        self.console_text.setReadOnly(True)
        self.console_text.setFont(QFont("Consolas", 12))
        layout.addWidget(self.console_text)
        self.tab_console.setLayout(layout)

    def _build_results_tab(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Permanent tree (no recreate = no crash)
        self.results_tree = QTreeWidget()
        self.results_tree.setHeaderLabels(["Severity", "Location", "Message"])
        self.results_tree.header().setStretchLastSection(True)
        self.results_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.results_tree.setMinimumHeight(500)
        
        layout.addWidget(self.results_tree, stretch=1)
        
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QPushButton("Copy Report", clicked=self._copy_report))
        btn_layout.addWidget(QPushButton("Save Report", clicked=self._save_report))
        btn_layout.addWidget(QPushButton("🔄 Refresh Results", clicked=self._populate_results))
        layout.addLayout(btn_layout)
        
        self.tab_results.setLayout(layout)

    def _force_results_redraw(self):
        """Bulletproof redraw — forces Qt to show every item instantly"""
        self.results_tree.setVisible(True)
        self.results_tree.show()
        for col in range(3):
            self.results_tree.resizeColumnToContents(col)
        self.results_tree.viewport().update()
        self.results_tree.repaint()
        self.results_tree.updateGeometry()
        QTimer.singleShot(0, self.results_tree.repaint)
        QTimer.singleShot(30, self.results_tree.viewport().update)
        QTimer.singleShot(120, lambda: self.results_tree.setCurrentItem(
            self.results_tree.topLevelItem(0) if self.results_tree.topLevelItemCount() > 0 else None
        ))

    def _animate_button(self):
        anim = QPropertyAnimation(self.run_btn, b"geometry")
        anim.setDuration(180)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        rect = self.run_btn.geometry()
        anim.setStartValue(rect)
        anim.setEndValue(rect.adjusted(-6, -6, 6, 6))
        anim.start()

    def _fade_in_results(self):
        effect = QGraphicsOpacityEffect()
        self.results_tree.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity")
        anim.setDuration(700)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.start()

    def _get_default_jar_path(self):
        steam_root = get_steam_install_path()
        if not steam_root:
            return ""

        libraries = parse_libraryfolders_vdf(steam_root)
        for lib_root in libraries:
            candidate = lib_root / "steamapps" / "common" / "ProjectZomboid" / "projectzomboid.jar"
            if candidate.exists():
                return str(candidate)
        return ""

    def _on_mode_changed(self):
        if self.mode_jar.isChecked():
            self.game_browse_btn.setText("Browse JAR")
            self.game_entry.setText(self._get_default_jar_path())
            self.game_entry.setEnabled(True)
        elif self.mode_folder.isChecked():
            self.game_browse_btn.setText("Browse Folder")
            self.game_entry.clear()
            self.game_entry.setEnabled(True)
        else:
            self.game_browse_btn.setText("—")
            self.game_entry.setText("(Lua-only — no game source needed)")
            self.game_entry.setEnabled(False)

    def _on_mod_mode_changed(self):
        """Dynamically update browse button and placeholder"""
        if self.mod_jar.isChecked():
            self.mod_browse_btn.setText("Browse JAR")
            self.mod_entry.setPlaceholderText("Select mod .jar file")
        elif self.mod_folder.isChecked():
            self.mod_browse_btn.setText("Browse Folder")
            self.mod_entry.setPlaceholderText("Select decompiled mod folder")
        else:
            self.mod_browse_btn.setText("Browse Folder")
            self.mod_entry.setPlaceholderText("(Pure Lua mod - any folder)")

    def _change_theme(self, name):
        """Safe theme switch with fallback"""
        try:
            self.setStyleSheet(THEME_STYLES[name])
        except (KeyError, TypeError):
            self.setStyleSheet(THEME_STYLES["Dark Classic"])  # safe fallback

    def _change_window_mode(self, mode):
        if mode == "Fullscreen":
            self.showFullScreen()
        elif mode == "Borderless":
            self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
            self.show()
        else:
            self.setWindowFlags(Qt.WindowType.Window)
            self.showNormal()

    def _scan_workshop(self):
        ws = Path(self.workshop_entry.text())
        if ws.is_dir():
            WorkshopScanner.scan_workshop(self, ws)

    def _live_add_batch(self):
        WorkshopScanner.live_add_batch(self)

    def _finish_scan_ui(self):
        WorkshopScanner.finish_scan_ui(self)

    def _final_sort_and_resize(self):
        self.workshop_tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        for col in range(5):
            self.workshop_tree.resizeColumnToContents(col)
        self.workshop_tree.viewport().update()
        self.console_text.append(f"✅ Scan complete — {len(self.detected_mods)} mods visible!\n")

    def _apply_sort(self):
        idx = self.sort_combo.currentIndex()
        if idx == 0:
            self.workshop_tree.sortItems(0, Qt.SortOrder.AscendingOrder)
        elif idx == 1:
            self.workshop_tree.sortItems(1, Qt.SortOrder.DescendingOrder)
        elif idx == 2:
            self.workshop_tree.sortItems(2, Qt.SortOrder.DescendingOrder)
        else:
            self.workshop_tree.sortItems(3, Qt.SortOrder.AscendingOrder)

    def _on_mod_clicked(self, item):
        path = item.text(4)
        if path:
            self.mod_entry.setText(path)
            self.tabs.setCurrentWidget(self.tab_main)

    def _on_tab_changed(self, index):
        """Auto-refresh Results tab every time you switch to it"""
        if self.tabs.widget(index) == self.tab_results:
            QTimer.singleShot(50, self._populate_results)

    def _start_check(self):
        if self.running: return
        self.running = True
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Running...")
        self.tabs.setCurrentWidget(self.tab_console)
        self.console_text.clear()

        self.console_redirect = ConsoleRedirect(self.console_text)
        sys.stdout = self.console_redirect
        sys.stderr = self.console_redirect

        threading.Thread(target=self._run_backend, daemon=True).start()

    def _run_backend(self):
        try:
            lua_only = self.mode_lua.isChecked()
            mod_path = self.mod_entry.text().strip()

            if not mod_path:
                print("❌ No mod selected!")  # safe print
                QTimer.singleShot(0, self._reset_run_button)
                return

            print(f"→ Scanning mod: {Path(mod_path).name}")
            mod_refs = ModReferences()
            mod_refs.parse_mod(mod_path)

            print(f"   Java references found: {len(mod_refs.references):,}")
            print(f"   Lua checks found: {len(mod_refs.lua_references.references):,}")

            if lua_only:
                self.issues = []
                seen = set()
                for ref in mod_refs.lua_references.references:
                    key = (ref.get('source_file'), ref.get('line'), ref.get('message'))
                    if key not in seen:
                        seen.add(key)
                        self.issues.append({"severity": "WARNING", "message": ref.get("message"), "source": f"{ref.get('source_file')}:{ref.get('line', '?')}"})
                print("→ Lua-only analysis complete")
            else:
                game_path = self.game_entry.text().strip()
                if game_path in ["(Lua-only — no game source needed)", ""]:
                    game_path = self._get_default_jar_path()
                    QTimer.singleShot(0, lambda p=game_path: self.game_entry.setText(p))

                if not game_path:
                    print("❌ No game path selected!")
                    QTimer.singleShot(0, self._reset_run_button)
                    return

                print("→ Building game API index...")
                game_api = GameAPI()
                game_api.build_index(game_path, self.cache_var)
                print(f"   Game API ready — {len(game_api.classes):,} classes indexed")

                print("→ Running compatibility analysis...")
                checker = CompatibilityChecker(game_api, mod_refs)
                self.issues = checker.check()

            print(f"→ Analysis complete — {len(self.issues)} total issues found")

            self.current_issues = self.issues.copy()

            QTimer.singleShot(0, lambda: self.tabs.setCurrentWidget(self.tab_results))
            QTimer.singleShot(300, self._populate_results)

        except Exception as e:
            error_msg = f"\nCRASH: {str(e)}\n{traceback.format_exc()}"
            print(error_msg)
            with open(str(DOCS_DIR / "crash.log"), "w", encoding="utf-8") as f:
                f.write(error_msg)
            QTimer.singleShot(0, lambda: QMessageBox.critical(self, "Crash", f"Crash occurred!\nDetails saved to {DOCS_DIR / 'crash.log'}"))
        finally:
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__
            QTimer.singleShot(0, self._reset_run_button)

    def _populate_results(self):
        if getattr(self, "_populating", False):
            return
        self._populating = True

        self.console_text.append(f"Populating Results tab with {len(self.current_issues)} issues...")

        self.results_tree.setUpdatesEnabled(False)
        self.results_tree.clear()

        if not self.current_issues:
            item = QTreeWidgetItem(["INFO", "—", "No compatibility issues detected! 🎉"])
            item.setBackground(0, QColor(0, 100, 0))      # green
            self.results_tree.addTopLevelItem(item)
        else:
            for i in self.current_issues:
                severity = i.get("severity", "WARNING")
                item = QTreeWidgetItem([
                    severity,
                    i.get("source", "—"),
                    i.get("message", "")
                ])
                # Color coding
                if severity == "ERROR":
                    color = QColor(139, 0, 0)      # dark red
                elif severity == "WARNING":
                    color = QColor(204, 102, 0)    # dark orange
                else:
                    color = QColor(0, 100, 0)      # green
                item.setBackground(0, color)
                item.setFont(0, QFont("Helvetica", 10, QFont.Weight.Bold))
                self.results_tree.addTopLevelItem(item)

        self.results_tree.setUpdatesEnabled(True)
        self.results_tree.header().setStretchLastSection(True)
        self.results_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)

        for col in range(3):
            self.results_tree.resizeColumnToContents(col)

        self.results_tree.setVisible(True)
        self.results_tree.show()
        self.results_tree.viewport().update()
        self.results_tree.repaint()
        QApplication.processEvents()

        QTimer.singleShot(0, self.results_tree.repaint)
        QTimer.singleShot(30, self.results_tree.viewport().update)
        #QTimer.singleShot(80, self.results_tree.repaint)
        QTimer.singleShot(250, self._select_first_item_safe)

        self.console_text.append(f"✅ Results tab populated with {len(self.current_issues)} items — visible now!\n")
        self._populating = False

    def _select_first_item_safe(self):
        """Safe selection (never crashes)"""
        if hasattr(self, "results_tree") and self.results_tree.topLevelItemCount() > 0:
            self.results_tree.setCurrentItem(self.results_tree.topLevelItem(0))

    def _reset_run_button(self):
        self.running = False
        self.run_btn.setEnabled(True)
        self.run_btn.setText("🚀 Run Compatibility Check")

    def _write_report(self, issues, file):
        errors = [i for i in issues if i.get("severity") == "ERROR"]
        warnings = [i for i in issues if i.get("severity") == "WARNING"]
        file.write("="*80 + "\nPZ MOD COMPATIBILITY REPORT\n" + "="*80 + "\n\n")
        file.write(f"Total: {len(issues)}   Errors: {len(errors)}   Warnings: {len(warnings)}\n\n")
        if errors:
            file.write("ERRORS:\n" + "─"*70 + "\n")
            for e in errors:
                file.write(f"[{e.get('severity')}] {e.get('message')}\n    at {e.get('source','—')}\n\n")
        if warnings:
            file.write("WARNINGS:\n" + "─"*70 + "\n")
            for w in warnings:
                file.write(f"[{w.get('severity')}] {w.get('message')}\n    at {w.get('source','—')}\n\n")
        file.write("="*80 + "\n")

    def _copy_report(self):
        try:
            from io import StringIO
            buf = StringIO()
            self._write_report(self.current_issues, buf)
            text = buf.getvalue()
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copied", "Full report copied to clipboard!")
            self.console_text.append("📋 Report copied to clipboard\n")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def _save_report(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Report", self.output_var, "Text (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                self._write_report(self.current_issues, f)
            QMessageBox.information(self, "Saved", f"Saved to:\n{path}")

    def _browse_game(self):
        if self.mode_jar.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "Select game JAR", "", "JAR files (*.jar)")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select game folder")
        if path:
            self.game_entry.setText(path)

    def _browse_mod(self):
        if self.mod_jar.isChecked():
            path, _ = QFileDialog.getOpenFileName(self, "Select mod JAR", "", "JAR files (*.jar)")
        else:
            path = QFileDialog.getExistingDirectory(self, "Select mod folder")
        if path:
            self.mod_entry.setText(path)

    def _detect_workshop(self):
        ws_path = find_pz_workshop_content_path()
        if ws_path:
            self.workshop_entry.setText(str(ws_path))
            if not WorkshopScanner.load_cache(self):
                QTimer.singleShot(600, lambda: WorkshopScanner.scan_workshop(self, ws_path))
        else:
            self.workshop_entry.setText("Not found — set manually")

    def _load_last_paths(self):
        if not self.config_path.is_file(): return
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = json.load(f)
            self.game_entry.setText(data.get("game_path", ""))
            self.mod_entry.setText(data.get("mod_path", ""))
            self.workshop_entry.setText(data.get("workshop_path", ""))
        except: pass

    def _save_last_paths(self):
        try:
            data = {
                "game_path": self.game_entry.text(),
                "mod_path": self.mod_entry.text(),
                "workshop_path": self.workshop_entry.text(),
            }
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except: pass

    def closeEvent(self, event):
        self._save_last_paths()
        event.accept()

if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        app.setStyle("Fusion")
        window = CompatibilityGUI()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        error_msg = f"=== CRASH ON STARTUP ===\n{traceback.format_exc()}"
        with open("crash.log", "w", encoding="utf-8") as f:
            f.write(error_msg)
        QMessageBox.critical(None, "Crash", f"Startup crash!\nDetails saved to crash.log")
        sys.exit(1)
