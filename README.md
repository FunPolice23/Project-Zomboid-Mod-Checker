# 🧟 PZ Mod Compatibility Checker – Build 42 Edition

**Quickly check if your mods will work on the latest Project Zomboid Build 42.**

Tired of broken mods after the big B42 update? This tool scans your mod (`.jar`, decompiled folder, or pure Lua) against the game code and tells you what needs fixing.

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

Just run the `.exe` (Windows) or `python gui.py` (Linux/macOS) and you're ready to mod again.

Main Tab
<img width="1920" height="1032" alt="main" src="https://github.com/user-attachments/assets/ee4f6dbd-55a6-489f-a120-297e683edfaa" />
Console Tab
<img width="1920" height="1032" alt="console" src="https://github.com/user-attachments/assets/1811db95-d83e-4672-97a5-355174f608fc" />
Results Tab
<img width="1920" height="1032" alt="results" src="https://github.com/user-attachments/assets/680500b3-1708-41de-90fe-d9d15f8a112d" />
Docs Tab
<img width="1920" height="1032" alt="docs" src="https://github.com/user-attachments/assets/ced93e6b-0698-41a1-b485-352338b58042" />
Settings Tab
<img width="1920" height="1032" alt="settings" src="https://github.com/user-attachments/assets/9ac04067-d16b-4088-a4fd-2c1295237942" />
