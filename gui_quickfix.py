"""
gui_quickfix.py — Quick Fix Tab

Expanded QUICK_FIX_DB with before/after code snippets for every issue type.
Improved detail panel with Copy Fix and Open Docs buttons.
Direct links to https://demiurgequantified.github.io/ProjectZomboidLuaDocs/

Usage in gui_tabs.py:
    from gui_quickfix import QuickFixTab
    # _ui is wired automatically via the shared dispatcher
"""
import re
import webbrowser
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFileDialog, QTreeWidget, QTreeWidgetItem,
    QTextEdit, QComboBox, QHeaderView, QSplitter, QMessageBox
)

# Dispatcher is imported lazily to avoid circular import
def _ui(fn):
    from gui_tabs import _ui as _real_ui
    _real_ui(fn)


# ══════════════════════════════════════════════════════════════════════════════
# QUICK FIX DATABASE
# match: substring checked against the error/warning message (case-insensitive)
# code:  optional before/after snippet shown in the detail pane
# docs:  URL opened by the "Open Docs" button
# ══════════════════════════════════════════════════════════════════════════════

QUICK_FIX_DB: list[dict] = [

    # ── Lua – Fragile Calls ───────────────────────────────────────────────────
    {
        "match":    "getPlayer",
        "category": "Lua – Fragile Call",
        "problem":  "getPlayer() assumes singleplayer and returns nil in multiplayer. Also unsafe to call at module load time.",
        "fix":      "Use getSpecificPlayer(0) for singleplayer-only code. For events, receive the player object through the event arguments instead of calling getPlayer().",
        "code":     (
            "-- BEFORE (breaks in MP, may be nil at load time)\n"
            "local player = getPlayer()\n"
            "player:getInventory():addItem(\"Base.Axe\")\n\n"
            "-- AFTER (safe for SP and MP)\n"
            "Events.OnCreatePlayer.Add(function(playerIndex, player)\n"
            "    player:getInventory():addItem(\"Base.Axe\")\n"
            "end)\n"
            "-- or for singleplayer-only:\n"
            "local player = getSpecificPlayer(0)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/namespaceumbrella.html",
    },
    {
        "match":    "SandboxVars",
        "category": "Lua – Fragile Call",
        "problem":  "SandboxVars may not be initialised at module load time in B42. Direct access outside an event can return nil.",
        "fix":      "Always access SandboxVars inside an event callback such as OnGameStart or OnNewGame, never at the top level of a Lua file.",
        "code":     (
            "-- BEFORE (SandboxVars may be nil here)\n"
            "local zombieCount = SandboxVars.ZombieCount\n\n"
            "-- AFTER\n"
            "Events.OnGameStart.Add(function()\n"
            "    local zombieCount = SandboxVars.ZombieCount\n"
            "    print(\"Zombie count setting: \" .. tostring(zombieCount))\n"
            "end)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
    },
    {
        "match":    "getCore",
        "category": "Lua – Fragile Call",
        "problem":  "getCore().getOption() and similar calls were removed or renamed in B42. Many settings moved to SandboxVars or GameSettings.",
        "fix":      "Check the B42 JavaDocs for the current Core API. Sandbox options use SandboxVars.OptionName directly.",
        "code":     (
            "-- BEFORE\n"
            "local val = getCore():getOption(\"someOption\")\n\n"
            "-- AFTER (sandbox options)\n"
            "local val = SandboxVars.SomeOption\n\n"
            "-- AFTER (game settings — check JavaDocs for exact method)\n"
            "local settings = GameSettings.getInstance()\n"
            "local val = settings:getSomeOption()"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
    {
        "match":    "ISBuildingMenu",
        "category": "Lua – Fragile Call",
        "problem":  "ISBuildingMenu was restructured into BuildingMenu in B42. The old registration API no longer exists.",
        "fix":      "Replace ISBuildingMenu with BuildingMenu. Register recipes via BuildingMenu.addRecipe() and categories via BuildingMenu.addBuildCategory().",
        "code":     (
            "-- BEFORE (B41)\n"
            "function ISBuildingMenu.onFillWorldObjectContextMenu(player, menu, worldobjects)\n"
            "    local option = menu:addOption(\"Build Thing\", ...)\nend\n\n"
            "-- AFTER (B42)\n"
            "BuildingMenu.addRecipe(\n"
            "    \"MyCategory\",\n"
            "    {\n"
            "        name = \"Build Thing\",\n"
            "        buildFunction = function(player, tile) ... end\n"
            "    }\n"
            ")"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html",
    },
    {
        "match":    "ISTimedActionQueue",
        "category": "Lua – Fragile Call",
        "problem":  "ISTimedActionQueue.add() now requires the player object as the first argument. Global player references are not safe.",
        "fix":      "Pass the player explicitly. Receive the player from the event or function context rather than calling getPlayer().",
        "code":     (
            "-- BEFORE (B41)\n"
            "ISTimedActionQueue.add(ISGrabItemAction:new(item))\n\n"
            "-- AFTER (B42 — player passed explicitly)\n"
            "-- Receive player from event:\n"
            "Events.OnPlayerUpdate.Add(function(player)\n"
            "    if someCondition then\n"
            "        ISTimedActionQueue.add(player, ISGrabItemAction:new(player, item))\n"
            "    end\n"
            "end)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html",
    },
    {
        "match":    "keyBinding",
        "category": "Lua – Key Binding",
        "problem":  "Key binding registration changed significantly in B42. The old Keyboard table and registerKey approach were removed.",
        "fix":      "Use the new InputSystem API. Register key bindings inside OnGameBoot, not at module load time.",
        "code":     (
            "-- BEFORE (B41)\n"
            "Keyboard.registerKey(\"MyMod_Action\", KEY_Z)\n"
            "Events.OnKeyPressed.Add(function(key)\n"
            "    if key == KEY_Z then doMyAction() end\n"
            "end)\n\n"
            "-- AFTER (B42)\n"
            "Events.OnGameBoot.Add(function()\n"
            "    InputSystem.addKeyBinding(\"MyMod\", \"MyAction\", Keyboard.KEY_Z)\n"
            "end)\n"
            "Events.OnKeyPressed.Add(function(key)\n"
            "    if InputSystem.isKeyBound(\"MyMod\", \"MyAction\", key) then\n"
            "        doMyAction()\n"
            "    end\n"
            "end)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Callbacks.html",
    },
    {
        "match":    "ISContextMenu",
        "category": "Lua – Context Menu",
        "problem":  "ISContextMenu and ISInventoryContextMenu were refactored in B42. Direct instantiation no longer works.",
        "fix":      "Register via OnFillWorldObjectContextMenu or OnFillInventoryObjectContextMenu events. Use the context object passed by the event.",
        "code":     (
            "-- BEFORE (B41)\n"
            "function ISContextMenu.onRightMouseButton(objects, x, y)\n"
            "    local menu = ISContextMenu.get(0, x+10, y+10)\n"
            "    menu:addOption(\"My Option\", objects, myFunction)\n"
            "end\n\n"
            "-- AFTER (B42)\n"
            "Events.OnFillWorldObjectContextMenu.Add(\n"
            "function(playerIndex, context, worldobjects)\n"
            "    context:addOption(\"My Option\", worldobjects, myFunction)\n"
            "end)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
    },
    {
        "match":    "luautils",
        "category": "Lua – Fragile Call",
        "problem":  "Some luautils functions were changed or removed in B42.",
        "fix":      "Check the B42 Lua docs for the current luautils API. Some helpers moved into global scope or new utility modules.",
        "code":     "-- Check current API:\n-- https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html",
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html",
    },
    {
        "match":    "AdjacentFreeTileFinder",
        "category": "Lua – Fragile Call",
        "problem":  "AdjacentFreeTileFinder API changed in B42 alongside the tile system revision.",
        "fix":      "Verify method signatures in the B42 JavaDocs.",
        "code":     "// Check: https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },

    # ── Lua – Deprecated / Removed Events ────────────────────────────────────
    {
        "match":    "OnInitializeBuildingMenuRecipes",
        "category": "Lua – Removed Event",
        "problem":  "OnInitializeBuildingMenuRecipes was removed in B42.",
        "fix":      "Use the new BuildingMenu.addRecipe() API or hook into OnFillWorldObjectContextMenu for context-menu-based building.",
        "code":     (
            "-- BEFORE (B41)\n"
            "Events.OnInitializeBuildingMenuRecipes.Add(function(menu)\n"
            "    ISBuildingMenu.addBuildCategory(\"MyMod\", ...)\n"
            "end)\n\n"
            "-- AFTER (B42)\n"
            "BuildingMenu.addRecipe(\"MyCategory\", {\n"
            "    name = \"My Build\",\n"
            "    buildFunction = function(player, tile) end\n"
            "})"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
    },
    {
        "match":    "OnFillInventoryObjectContextMenu",
        "category": "Lua – Changed Event",
        "problem":  "Signature changed in B42: playerIndex (int) is now the first argument instead of an IsoPlayer object.",
        "fix":      "Update the function signature. Use getSpecificPlayer(playerIndex) to get the player object when needed.",
        "code":     (
            "-- BEFORE (B41)\n"
            "Events.OnFillInventoryObjectContextMenu.Add(\n"
            "function(player, context, items)  -- player = IsoPlayer\n"
            "    context:addOption(\"Action\", items, myFn)\n"
            "end)\n\n"
            "-- AFTER (B42)\n"
            "Events.OnFillInventoryObjectContextMenu.Add(\n"
            "function(playerIndex, context, items)  -- playerIndex = int\n"
            "    local player = getSpecificPlayer(playerIndex)\n"
            "    context:addOption(\"Action\", items, myFn)\n"
            "end)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
    },
    {
        "match":    "OnFillWorldObjectContextMenu",
        "category": "Lua – Changed Event",
        "problem":  "Signature changed in B42: playerIndex (int) is now the first argument.",
        "fix":      "Update the function signature. Use getSpecificPlayer(playerIndex) to get the player object.",
        "code":     (
            "-- BEFORE (B41)\n"
            "Events.OnFillWorldObjectContextMenu.Add(\n"
            "function(player, context, worldobjects)\n"
            "end)\n\n"
            "-- AFTER (B42)\n"
            "Events.OnFillWorldObjectContextMenu.Add(\n"
            "function(playerIndex, context, worldobjects)\n"
            "    local player = getSpecificPlayer(playerIndex)\n"
            "end)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
    },
    {
        "match":    "removed or changed in Build 42",
        "category": "Lua – Unknown Event",
        "problem":  "This Lua event does not exist in the B42 event list. It may have been renamed, merged, or removed.",
        "fix":      "Search the B42 events page. Common pattern: events that previously received an IsoPlayer now receive a playerIndex int instead.",
        "code":     (
            "-- Search the full B42 event list:\n"
            "-- https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html\n\n"
            "-- Common renames:\n"
            "--   Old: Events.SomeName.Add(function(player, ...) end)\n"
            "--   New: Events.SomeName.Add(function(playerIndex, ...) end)\n"
            "--        local player = getSpecificPlayer(playerIndex)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
    },
    {
        "match":    "fragile call",
        "category": "Lua – Fragile Call",
        "problem":  "A Lua call flagged as potentially fragile in B42.",
        "fix":      "Check the B42 Lua docs for the current function signature and whether it still exists.",
        "code":     "-- https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html",
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/annotated.html",
    },

    # ── Java – Class / Method / Field ─────────────────────────────────────────
    {
        "match":    "Missing class",
        "category": "Java – Missing Class",
        "problem":  "The mod references a game class that no longer exists in B42. It may have been renamed, moved to a different package, or merged.",
        "fix":      "Search the B42 JavaDocs by class name. Check nearby packages — classes were often reorganised between B41 and B42.",
        "code":     (
            "// Search B42 JavaDocs:\n"
            "// https://demiurgequantified.github.io/ProjectZomboidJavaDocs/\n\n"
            "// Common package moves in B42:\n"
            "//   zombie.ui.*       → zombie.core.ui.*\n"
            "//   zombie.iso.*      → may be zombie.world.*\n\n"
            "// Lua instanceof update:\n"
            "-- BEFORE: instanceof(obj, \"zombie.old.ClassName\")\n"
            "-- AFTER:  instanceof(obj, \"zombie.new.ClassName\")"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
    {
        "match":    "Missing method",
        "category": "Java – Missing Method",
        "problem":  "The method was removed or renamed in B42. The class exists but this specific method does not.",
        "fix":      "Open the class in B42 JavaDocs and look for a method with similar purpose. Check for renamed, split, or overloaded variants.",
        "code":     (
            "// Common B42 method patterns:\n"
            "//   getXxx() removed   → look for xxx() or isXxx()\n"
            "//   setXxx(val)        → look for configureXxx() or withXxx()\n"
            "//   Methods may have gained playerIndex as first arg\n\n"
            "-- Lua bridge example:\n"
            "-- BEFORE: player:getXyzManager():oldMethod(arg)\n"
            "-- AFTER:  player:getXyzManager():newMethod(playerIndex, arg)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
    {
        "match":    "Method signature changed",
        "category": "Java – Signature Changed",
        "problem":  "The method exists in B42 but its parameters changed. The error shows what was expected vs what was found.",
        "fix":      "Update the call to match the new signature. The most common B42 change: a playerIndex (int) argument was added as the first parameter.",
        "code":     (
            "// BEFORE (B41 signature)\n"
            "someObject.doThing(itemStack)\n\n"
            "// AFTER (B42 — playerIndex added)\n"
            "someObject.doThing(playerIndex, itemStack)\n\n"
            "-- Lua callbacks follow the same pattern:\n"
            "-- B41: function callback(player, context)\n"
            "-- B42: function callback(playerIndex, context)\n"
            "--      local player = getSpecificPlayer(playerIndex)"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
    {
        "match":    "Missing field",
        "category": "Java – Missing Field",
        "problem":  "A class field (variable) was removed or renamed in B42.",
        "fix":      "Check the class in B42 JavaDocs. Fields are often converted to getter/setter methods, moved to a parent class, or replaced with a config object.",
        "code":     (
            "// BEFORE: direct field access\n"
            "float val = someObject.myField;\n\n"
            "// AFTER: field became a method\n"
            "float val = someObject.getMyField();\n\n"
            "-- Lua equivalent:\n"
            "-- BEFORE: local val = someObject.myField\n"
            "-- AFTER:  local val = someObject:getMyField()"
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
    {
        "match":    "Field type or signature changed",
        "category": "Java – Field Changed",
        "problem":  "A field exists in B42 but its type changed.",
        "fix":      "Update the access to match the new type shown in B42 JavaDocs.",
        "code":     "// Common type changes in B42:\n// int → float\n// String → TextDrawObject\n// boolean → Boolean (boxed)\n// Check the class in JavaDocs for the exact new type",
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
    {
        "match":    "visibility changed",
        "category": "Java – Visibility Warning",
        "problem":  "A method or field changed from public to protected/private in B42. Mods should not rely on private API.",
        "fix":      "Find an officially public API method that provides the same functionality. Using reflection is fragile and will break on future updates.",
        "code":     (
            "// DO NOT use reflection — it breaks on every update.\n\n"
            "// Instead, look for a public getter/setter in JavaDocs:\n"
            "//   someObject.getField()   ← look for this\n"
            "//   someObject.doAction()   ← or a method that wraps the same logic\n\n"
            "// If no public API exists, consider using the Lua scripting\n"
            "// layer instead of calling Java methods directly."
        ),
        "docs":     "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
    },
]


def _find_fixes(message: str) -> list[dict]:
    """Return all fix entries whose match string appears in the error message."""
    msg_lower = message.lower()
    return [f for f in QUICK_FIX_DB if f["match"].lower() in msg_lower]


# ══════════════════════════════════════════════════════════════════════════════
# QUICK FIX TAB
# ══════════════════════════════════════════════════════════════════════════════

class QuickFixTab:
    """
    Displays fix suggestions for every issue found by the compatibility scan.
    Call QuickFixTab.refresh(issues) after each scan to update the view.
    """
    _refresh_fn = None

    @staticmethod
    def build(parent_widget: QWidget):
        layout = QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(8)

        # ── Header ────────────────────────────────────────────────────────
        header = QLabel("💡 Quick Fix Suggestions")
        header.setFont(QFont("Helvetica", 15, QFont.Weight.Bold))
        layout.addWidget(header)

        hint = QLabel(
            "Run a compatibility check (Main tab) or load a saved report. "
            "Click any issue to see a detailed fix with code examples."
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # ── Top action bar ────────────────────────────────────────────────
        top_row = QHBoxLayout()
        load_btn = QPushButton("📂 Load Report")
        load_btn.setToolTip("Load a previously saved compatibility report (.txt)")
        docs_btn = QPushButton("📖 B42 Lua Docs")
        docs_btn.setToolTip("Open the B42 Lua events reference in your browser")
        java_btn = QPushButton("☕ B42 Java Docs")
        java_btn.setToolTip("Open the B42 Java API reference in your browser")
        top_row.addWidget(load_btn)
        top_row.addStretch()
        top_row.addWidget(docs_btn)
        top_row.addWidget(java_btn)
        layout.addLayout(top_row)

        # ── Filter bar ────────────────────────────────────────────────────
        filter_row = QHBoxLayout()
        filter_box = QLineEdit()
        filter_box.setPlaceholderText("🔍 Filter by keyword, class name, or file path…")
        cat_combo = QComboBox()
        cat_combo.addItem("All Categories")
        for cat in sorted({f["category"] for f in QUICK_FIX_DB}):
            cat_combo.addItem(cat)
        filter_row.addWidget(filter_box, stretch=2)
        filter_row.addWidget(cat_combo, stretch=1)
        layout.addLayout(filter_row)

        # ── Splitter: issue list (left) | fix detail (right) ──────────────
        splitter = QSplitter(Qt.Orientation.Horizontal)

        issue_tree = QTreeWidget()
        issue_tree.setHeaderLabels(["Sev", "Category", "Source / Message"])
        issue_tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        issue_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        issue_tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        issue_tree.setRootIsDecorated(False)
        splitter.addWidget(issue_tree)

        # Right panel: detail text + action buttons
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(4, 0, 0, 0)
        right_layout.setSpacing(4)

        detail_box = QTextEdit()
        detail_box.setReadOnly(True)
        detail_box.setFont(QFont("Consolas", 10))
        detail_box.setPlaceholderText("← Select an issue to see fix suggestions and code examples")
        right_layout.addWidget(detail_box, stretch=1)

        action_row = QHBoxLayout()
        copy_fix_btn = QPushButton("📋 Copy Fix")
        copy_fix_btn.setToolTip("Copy the fix suggestion and code example to clipboard")
        open_doc_btn = QPushButton("🌐 Open Docs")
        open_doc_btn.setToolTip("Open the relevant B42 documentation page in your browser")
        copy_fix_btn.setEnabled(False)
        open_doc_btn.setEnabled(False)
        action_row.addWidget(copy_fix_btn)
        action_row.addWidget(open_doc_btn)
        action_row.addStretch()
        right_layout.addLayout(action_row)

        splitter.addWidget(right_widget)
        splitter.setSizes([480, 520])
        layout.addWidget(splitter, stretch=1)

        status = QLabel("No scan results loaded.")
        layout.addWidget(status)
        parent_widget.setLayout(layout)

        # ── State ─────────────────────────────────────────────────────────
        _all_issues: list[dict] = []
        _cur_docs:   list[str]  = [""]
        _cur_fix:    list[str]  = [""]

        # ── Helpers ───────────────────────────────────────────────────────
        def _populate_tree(issues: list[dict]):
            issue_tree.clear()
            shown = errors = warnings = 0
            kw = filter_box.text().lower()
            cat_filter = cat_combo.currentText()

            for issue in issues:
                msg = issue.get("message", "")
                src = issue.get("source",  "—")
                sev = issue.get("severity", "WARNING")
                fixes = _find_fixes(msg)

                if kw and kw not in msg.lower() and kw not in src.lower():
                    continue
                category = fixes[0]["category"] if fixes else "Unknown / Other"
                if cat_filter != "All Categories" and category != cat_filter:
                    continue

                short_src = src if len(src) < 65 else "…" + src[-62:]
                item = QTreeWidgetItem([sev, category, short_src])
                item.setData(0, Qt.ItemDataRole.UserRole, (msg, src, fixes))
                item.setToolTip(2, src)

                if sev == "ERROR":
                    item.setForeground(0, QColor(255, 90, 90))
                else:
                    item.setForeground(0, QColor(255, 175, 50))

                issue_tree.addTopLevelItem(item)
                shown += 1
                if sev == "ERROR": errors += 1
                else: warnings += 1

            status.setText(
                f"Showing {shown} of {len(issues)} issue(s) — "
                f"{errors} error(s), {warnings} warning(s)"
            )

        def _on_select(item: QTreeWidgetItem, _col: int):
            msg, src, fixes = item.data(0, Qt.ItemDataRole.UserRole)
            lines = [
                "━━━ ISSUE ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                msg,
                f"\nSource: {src}",
            ]
            docs_url = fix_text = ""

            if fixes:
                for fix in fixes:
                    lines += [
                        "\n━━━ FIX SUGGESTION ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                        f"Category : {fix['category']}",
                        f"Problem  : {fix['problem']}",
                        f"\nFix      : {fix['fix']}",
                    ]
                    if fix.get("code"):
                        lines += [
                            "\n── Code Example ──────────────────────────────────────",
                            fix["code"],
                            "──────────────────────────────────────────────────────",
                        ]
                    if fix.get("docs"):
                        lines.append(f"\nDocs: {fix['docs']}")
                        docs_url = fix["docs"]
                        fix_text = fix["fix"]
                        if fix.get("code"):
                            fix_text += "\n\n" + fix["code"]
            else:
                lines += [
                    "\n━━━ NO SPECIFIC FIX FOUND ━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                    "No pre-written fix for this exact issue type.",
                    "\nSuggested steps:",
                    "  1. Search the B42 JavaDocs for the class or method name",
                    "  2. Check the B42 Lua Events list for event signature changes",
                    "  3. Look for the playerIndex (int) pattern — many B41 functions",
                    "     that received IsoPlayer now receive a playerIndex int in B42",
                    "\nDocs:",
                    "  https://demiurgequantified.github.io/ProjectZomboidJavaDocs/",
                    "  https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html",
                ]
                docs_url = "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/"
                fix_text = "\n".join(lines)

            detail_box.setPlainText("\n".join(lines))
            _cur_docs[0] = docs_url
            _cur_fix[0]  = fix_text
            copy_fix_btn.setEnabled(True)
            open_doc_btn.setEnabled(bool(docs_url))

        def _refresh(issues: list[dict]):
            nonlocal _all_issues
            _all_issues = issues
            _populate_tree(issues)

        def _parse_report_file(path: str) -> list[dict]:
            issues = []
            try:
                text = open(path, encoding="utf-8", errors="ignore").read()
                for m in re.finditer(
                    r'\[(ERROR|WARNING)\]\s+(.+?)\n\s+at\s+(.+?)(?=\n|$)',
                    text, re.S
                ):
                    issues.append({
                        "severity": m.group(1),
                        "message":  m.group(2).strip(),
                        "source":   m.group(3).strip(),
                    })
            except Exception as e:
                QMessageBox.warning(parent_widget, "Load Report",
                                    f"Could not parse report:\n{e}")
            return issues

        def _load_report():
            from gui_helpers import DOCS_DIR
            path, _ = QFileDialog.getOpenFileName(
                parent_widget, "Load Compatibility Report", str(DOCS_DIR),
                "Text files (*.txt);;All files (*.*)"
            )
            if path:
                issues = _parse_report_file(path)
                if issues:
                    _refresh(issues)
                    status.setText(f"Loaded {len(issues)} issue(s) from report.")
                else:
                    status.setText("No issues found — check file format.")

        def _copy_fix():
            from PyQt6.QtWidgets import QApplication
            QApplication.clipboard().setText(_cur_fix[0])

        def _open_docs():
            if _cur_docs[0]:
                webbrowser.open(_cur_docs[0])

        # ── Wire controls ─────────────────────────────────────────────────
        load_btn.clicked.connect(_load_report)
        docs_btn.clicked.connect(lambda: webbrowser.open(
            "https://demiurgequantified.github.io/ProjectZomboidLuaDocs/md_Events.html"
        ))
        java_btn.clicked.connect(lambda: webbrowser.open(
            "https://demiurgequantified.github.io/ProjectZomboidJavaDocs/"
        ))
        copy_fix_btn.clicked.connect(_copy_fix)
        open_doc_btn.clicked.connect(_open_docs)
        issue_tree.itemClicked.connect(_on_select)
        filter_box.textChanged.connect(lambda _: _populate_tree(_all_issues))
        cat_combo.currentIndexChanged.connect(lambda _: _populate_tree(_all_issues))

        QuickFixTab._refresh_fn = _refresh

    @staticmethod
    def refresh(issues: list[dict]):
        """Call from gui.py after each scan completes to populate the tab."""
        if QuickFixTab._refresh_fn:
            _ui(lambda i=issues: QuickFixTab._refresh_fn(i))