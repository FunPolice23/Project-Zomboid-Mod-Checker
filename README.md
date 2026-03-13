# 🧟 PZ Mod Compatibility Checker – Build 42 Edition

**Quickly check if your mods will work on the latest Project Zomboid Build 42.**

Tired of broken mods after the big B42 update? This tool scans your mod (`.jar`, decompiled folder, or pure Lua) against the real game code and tells you exactly what needs fixing.

### ✨ Features
- Full Java bytecode analysis (missing methods, fields, changed signatures)
- Smart Lua scanning (deprecated events, fragile calls like `getPlayer`, `SandboxVars`, old hooks)
- Color-coded Results tab (red = errors, orange = warnings)
- 30 beautiful themes (dark, light, neon, sunset, etc.)
- Workshop scanner with fast caching (loads 1000+ mods instantly)
- "Open Data Folder" button – everything saved neatly in `Documents/PZModChecker` (or native folder on Linux/macOS)
- GUI + simple CLI support
- Cross-platform (Windows .exe + full source for Linux/macOS)

### Why use it?
- Catches issues **before** you upload to Nexus or Steam Workshop
- Works on old B41 mods too (shows exactly what broke in B42)
- Super lightweight and fast

**License:** [MIT](LICENSE) – free to use, modify, and share.

Just run the `.exe` (Windows) or `python gui.py` (Linux/macOS) and you're ready to mod again! 🧟
