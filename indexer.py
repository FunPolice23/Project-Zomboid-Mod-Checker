import os
import pickle
from pathlib import Path
from tqdm import tqdm
import zipfile
import kirjava

from constants import normalize_class_name

RELEVANT_PREFIXES = (
    "zombie.", "se.krka.kahlua", "zomboid.", "com.pz.",
    "zombie.core.", "zombie.characters.", "zombie.inventory.",
    "zombie.iso.", "zombie.ui.", "zombie.network.", "zombie.scripting.",
    "zombie.globalObjects.", "zombie.audio.", "zombie.debug."
)

class GameAPI:
    def __init__(self):
        self.classes = {}
        self.parse_failures = []

    def build_index(self, path: str, cache_file: str | None = None):
        if cache_file and os.path.exists(cache_file):
            print(f"Loading cached game API from {cache_file}")
            try:
                self.load(cache_file)
                print(f"✅ Loaded {len(self.classes):,} classes from cache")
                return
            except Exception as e:
                print(f"⚠️ Corrupt cache — deleting and rebuilding ({e})")
                Path(cache_file).unlink(missing_ok=True)

        p = Path(path)
        print(f"→ Reading game source: {p.name}")

        class_entries = []
        if p.suffix.lower() == '.jar' and p.is_file():
            with zipfile.ZipFile(p) as zf:
                class_entries = [(name, zf.read(name)) for name in zf.namelist() if name.endswith('.class')]
        elif p.is_dir():
            class_entries = [(str(f), f.read_bytes()) for f in p.rglob("*.class")]
        else:
            raise ValueError(f"Path must be projectzomboid.jar or decompiled folder: {path}")

        print(f"Found {len(class_entries):,} .class files — starting indexing...")

        indexed_count = 0
        for name_or_path, data in tqdm(class_entries, desc="Indexing game classes"):
            # Correct full package name for JAR and folder
            if '/' in str(name_or_path) or '\\' in str(name_or_path):
                internal = str(name_or_path).replace('\\', '/').replace('.class', '')
                full_class_name = internal.replace('/', '.')
            else:
                full_class_name = str(name_or_path).replace('.class', '')

            if not any(full_class_name.lower().startswith(prefix.lower()) for prefix in RELEVANT_PREFIXES):
                continue

            try:
                cf = kirjava.load(data)
                source_class = normalize_class_name(cf.name)

                self.classes[source_class] = {
                    "super_name": normalize_class_name(getattr(cf, 'super_name', None)),
                    "interfaces": [normalize_class_name(i) for i in getattr(cf, 'interfaces', [])],
                    "methods": [
                        {"name": m.name, "descriptor": getattr(m, 'descriptor', ''), "access_flags": getattr(m, 'access_flags', 0)}
                        for m in getattr(cf, 'methods', [])
                    ],
                    "fields": [
                        {"name": f.name, "descriptor": getattr(f, 'descriptor', ''), "access_flags": getattr(f, 'access_flags', 0)}
                        for f in getattr(cf, 'fields', [])
                    ]
                }
                indexed_count += 1
                if indexed_count % 500 == 0:
                    print(f"   → Indexed {indexed_count} relevant classes so far...")

            except Exception as e:
                self.parse_failures.append((name_or_path, str(e)))
                continue

        if self.parse_failures:
            print(f"⚠️  {len(self.parse_failures)} game classes failed to parse (normal)")

        print(f"✅ Successfully indexed {len(self.classes):,} relevant game classes")

        if cache_file:
            print(f"💾 Saving cache → {cache_file}")
            self.save(cache_file)

    def save(self, path: str):
        with open(path, "wb") as f:
            pickle.dump({"classes": self.classes}, f)

    def load(self, path: str):
        with open(path, "rb") as f:
            data = pickle.load(f)
            self.classes = data["classes"]