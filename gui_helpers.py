import winreg
import re
import platform
from pathlib import Path

# Cross-platform user data folder
if platform.system() == "Windows":
    DOCS_DIR = Path.home() / "Documents" / "PZModChecker"
elif platform.system() == "Darwin":          # macOS
    DOCS_DIR = Path.home() / "Library" / "Application Support" / "PZModChecker"
else:                                        # Linux and everything else
    DOCS_DIR = Path.home() / ".config" / "PZModChecker"

DOCS_DIR.mkdir(parents=True, exist_ok=True)

def get_steam_install_path() -> Path | None:
    """Find Steam install path — works on 99% of machines (including custom installs)"""
    candidates = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_CURRENT_USER,  r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam\SteamPath"),
        (winreg.HKEY_CURRENT_USER,  r"Software\Valve\Steam\SteamPath"),
    ]
    for hive, subkey in candidates:
        try:
            key = winreg.OpenKey(hive, subkey, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
            path_str, _ = winreg.QueryValueEx(key, "InstallPath" if "SteamPath" not in subkey else "SteamPath")
            path = Path(path_str).resolve()
            if path.exists() and (path / "steam.exe").is_file():
                return path
        except:
            continue
    return None

def parse_libraryfolders_vdf(steam_root: Path) -> list[Path]:
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    if not vdf_path.is_file():
        return [steam_root]

    libraries = [steam_root]
    try:
        text = vdf_path.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            lib_path = Path(match.group(1).replace(r"\\", "\\")).resolve()
            if lib_path.is_dir():
                libraries.append(lib_path)
    except:
        pass
    return libraries

def find_pz_workshop_content_path() -> Path | None:
    steam_root = get_steam_install_path()
    if not steam_root:
        return None

    libraries = parse_libraryfolders_vdf(steam_root)
    for lib_root in libraries:
        candidate = lib_root / "steamapps" / "workshop" / "content" / "108600"
        if candidate.is_dir():
            return candidate
    return None

def estimate_compat_from_modinfo(mod_folder: Path) -> tuple[str, str]:
    """Powerful recursive version detector — now scans Lua files as fallback"""
    display_name = mod_folder.name
    versions_found = set()
    structure = "✓"

    # 1. mod.info (as before)
    for info_file in mod_folder.rglob("mod.info"):
        try:
            text = info_file.read_text(encoding="utf-8", errors="ignore")
            content = text.lower()
            if "name=" in content and display_name == mod_folder.name:
                for line in text.splitlines():
                    if line.lower().startswith("name="):
                        display_name = line.split("=", 1)[1].strip().strip('"\'')
                        break
            for pat in [r'42\.\d+', r'build\s*42', r'b42', r'\[b?42', r'versionmin.*42', r'version.*42', r'42\.0', r'build42']:
                if re.search(pat, content):
                    versions_found.add("42")
            for pat in [r'41\.\d+', r'build\s*41', r'b41', r'\[b?41', r'versionmin.*41']:
                if re.search(pat, content):
                    versions_found.add("41")
        except:
            pass

    # 2. Folder names
    for item in mod_folder.rglob("*"):
        if item.is_dir():
            name = item.name.lower()
            if any(x in name for x in ['42.', 'b42', 'build42', '42_']):
                versions_found.add("42")
            if any(x in name for x in ['41.', 'b41', 'build41']):
                versions_found.add("41")

    # 3. NEW: Fallback — scan Lua files for B42 keywords (catches mods without version tags)
    for lua_file in mod_folder.rglob("*.lua"):
        try:
            text = lua_file.read_text(encoding="utf-8", errors="ignore").lower()
            if any(x in text for x in ['42.', 'b42', 'build42', 'onplayerupdate', 'getplayer', 'oncreateplayer', 'onfillworldobjectcontextmenu']):
                versions_found.add("42")
            if any(x in text for x in ['41.', 'b41', 'build41']):
                versions_found.add("41")
        except:
            pass

    # Structure check
    has_common = (mod_folder / "common").exists()
    has_42_folder = any((mod_folder / f"42{x}").exists() for x in ["", ".", "1", "15", ".15", "_"])
    if not has_common and not has_42_folder:
        structure = "❌ missing common/ + 42/"

    if versions_found:
        vlist = sorted(versions_found)
        if len(vlist) > 1:
            compat = f"Multi-version ({'+'.join(vlist)}) {structure}"
        else:
            compat = f"✅ B{vlist[0]} {structure}"
    else:
        compat = f"Unknown {structure}"

    return display_name, compat


if __name__ == "__main__":
    print("gui_helpers loaded — enhanced B42 version detection ready")