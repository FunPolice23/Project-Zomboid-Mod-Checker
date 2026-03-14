import zipfile
from pathlib import Path
import kirjava
from tqdm import tqdm
import re

from constants import (
    normalize_class_name,
    resolve_class,
    resolve_method_name,
    resolve_method_descriptor,
    resolve_field_name,
    resolve_field_descriptor,
    get_line_number,
)
from luaparser import LuaReferences

IGNORED_PACKAGES = {
    "java.", "javax.", "jdk.", "sun.", "com.sun.",
    "org.w3c.", "org.xml.", "kotlin.", "fmod.", "imgui."
}

class ModReferences:
    def __init__(self):
        self.references = []
        self.lua_references = LuaReferences()
        self.parse_failures = []

    def parse_mod(self, path: str):
        p = Path(path)
        class_entries = []

        if p.suffix.lower() == '.jar' and p.is_file():
            print(f"→ Reading mod JAR: {p.name}")
            with zipfile.ZipFile(p) as zf:
                class_entries = [(name, zf.read(name)) for name in zf.namelist() if name.endswith('.class')]
        elif p.is_dir():
            print(f"→ Scanning mod directory: {p}")
            class_entries = [(str(f), f.read_bytes()) for f in p.rglob("*.class")]
        else:
            raise ValueError(f"Path must be .jar or directory: {path}")

        print(f"Found {len(class_entries):,} .class files")

        # ── Java bytecode parsing (already perfect — unchanged) ──
        for name_or_path, data in tqdm(class_entries, desc="Parsing mod classes"):
            try:
                cf = kirjava.load(data)
                source_class = normalize_class_name(cf.name)

                for method in cf.methods:
                    if not hasattr(method, 'code') or not hasattr(method.code, 'instructions'):
                        continue

                    for insn in method.code.instructions:
                        opcode = getattr(insn, 'opcode', None)
                        offset = getattr(insn, 'offset', getattr(insn, 'pc', 0))
                        line = get_line_number(method, offset) or 0

                        if opcode in (182, 183, 184, 185, 186):  # method calls
                            try:
                                idx = getattr(insn, 'index', None) or getattr(insn, 'method_index', None)
                                if idx is None: continue
                                tgt_class = resolve_class(cf, idx)
                                member_name = resolve_method_name(cf, idx)
                                descriptor = resolve_method_descriptor(cf, idx)

                                if tgt_class == "<unknown>" or any(tgt_class.startswith(p) for p in IGNORED_PACKAGES):
                                    continue

                                self.references.append({
                                    "type": "method_call", "source_class": source_class,
                                    "source_method": method.name, "line": line,
                                    "target_class": tgt_class, "target_member": member_name,
                                    "descriptor": descriptor
                                })
                            except: continue

                        elif opcode in (180, 181, 178, 179):  # field accesses
                            try:
                                idx = getattr(insn, 'index', None) or getattr(insn, 'field_index', None)
                                if idx is None: continue
                                tgt_class = resolve_class(cf, idx)
                                member_name = resolve_field_name(cf, idx)
                                descriptor = resolve_field_descriptor(cf, idx)

                                if tgt_class == "<unknown>" or any(tgt_class.startswith(p) for p in IGNORED_PACKAGES):
                                    continue

                                self.references.append({
                                    "type": "field_access", "source_class": source_class,
                                    "source_method": method.name, "line": line,
                                    "target_class": tgt_class, "target_member": member_name,
                                    "descriptor": descriptor
                                })
                            except: continue

            except Exception as e:
                self.parse_failures.append((name_or_path, str(e)))
                continue

        if self.parse_failures:
            print(f"⚠️  {len(self.parse_failures)} mod classes failed to parse")

        # ── Lua scanning — ONE call per folder (much faster) ──
        lua_folders = set()
        for lua_file in p.rglob("*.lua"):
            if lua_file.is_file():
                folder = str(lua_file.parent)
                if folder not in lua_folders:
                    lua_folders.add(folder)
                    print(f"→ Found Lua folder: {lua_file.relative_to(p).parent}")
                    self.lua_references.parse_mod_lua(folder)

        if not lua_folders:
            print("⚠️  No .lua files found anywhere in the mod")
        else:
            print(f"   Lua warnings found: {len(self.lua_references.references)}")
