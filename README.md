# PZ Mod Compatibility Checker – Build 42 Edition 🧟

A user-friendly tool to check if your Project Zomboid mods will work on Build 42 (including the latest unstable patches).

After the massive Build 42 update, thousands of mods broke because of changed Java methods, removed Lua events,
deprecated hooks, and fragile calls. This tool scans your mod like the game does and tells you what needs fixing — before you waste time testing in-game.

## What It Does

It performs a complete compatibility audit on any mod:

Java analysis (.jar or decompiled folder) — detects missing classes, changed method signatures, removed fields,
visibility issues, and inheritance problems using real bytecode parsing.


Lua analysis (client/server/shared scripts) — catches deprecated events, fragile calls (getPlayer, SandboxVars, getCore, etc.), and old hooks that were removed in B42.


Shows color-coded results (red = critical errors, orange = warnings) with exact file:line locations.

## Key Features

30 beautiful themes (Dark Classic, Neon Cyber, Sunset Orange, Purple Teal Fusion, Crimson Gold, and many more mixed palettes)

Full Workshop scanner with smart caching — scans 1000+ mods in seconds and remembers them
Deep mod support — correctly handles complex folder structures (common/, 42/, nested mods like Knox Event Expanded)


Open Data Folder button — instantly opens where all caches, reports, and logs are saved (native location on every OS)

Color-coded Results tab that stays populated (no more blank screen)
Drag-to-move borderless window + transparency slider
Built-in B42 documentation links (official Lua events, callbacks, JavaDocs)
Clear cache buttons (Game API + Workshop) so you always stay up-to-date with the newest unstable builds

Full CLI support for scripting or batch checking
Auto-saves reports to a clean folder (Documents/PZModChecker on Windows, ~/.config/PZModChecker on Linux,
~/Library/Application Support/PZModChecker on macOS)

Interactive map from https://b42map.com/

### Additional future updates:
Save information, Mod Conflict Check, Quick fix suggestions per error type.

## How It Works

Uses kirjava for accurate Java bytecode parsing (opcodes, constant pool, LineNumberTable, inheritance traversal)


Smart Lua regex with word-boundary protection (no false positives)
Version detection that falls back to Lua keywords when mod.info is missing
Fast caching system (versioned JSON + pickle) — first scan builds the index, later scans are near-instant

Thread-safe GUI with live batch updates so the interface never freezes

### Installation & Usage
Windows users
Download the single .exe and run it — no Python required.
### Linux / macOS users
Bash pip install -r requirements.txt
python gui.py

### License
This project is licensed under the MIT License — free to use, modify, and redistribute.

### CLI:
python main.py <gamepath> <modpath> [options]
options flags:

--lua-only # skips java analysis, only checks against lua

--no-cache # forces fresh game index, ignores any cache data if any.

--ouput FILE or -o FILE # saves report to a text file

--verbose or -V # gives more detailed references

--cache File # uses a custom cache, defaults to game_api_cache.pkl

### Examples:
python main.py "[drive:]\Steam\steamapps\common\ProjectZomboid\projectzomboid.jar" "MyModFolder"


python main.py dummy.jar MyModFolder --lua-only

python main.py projectzomboid.jar MyMod.jar -o my_report.txt

python main.py projectzomboid.jar MyMod --no-cache -v

python main.py --help

### My purpose for the program
I enjoy project zomboid but recently a great mod/modder gave up which left their mod outdated, new unstable build changed certain things so this idea came in order to privatly update the mod myself with ease so I can play it again.

My hope is that mabye this helps bring old mods back,
mabye help new mods as well.

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
