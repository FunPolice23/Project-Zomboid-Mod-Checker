import argparse
import sys
from pathlib import Path

from indexer import GameAPI
from modparser import ModReferences
from comparison import CompatibilityChecker

def main():
    parser = argparse.ArgumentParser(
        description="Project Zomboid Mod Compatibility Checker – Build 42 Edition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py "C:\\...\\projectzomboid.jar" "H:\\MyMod"
  python main.py game_folder mod_folder --lua-only
  python main.py game.jar mymod.jar --output report.txt --verbose
        """
    )

    parser.add_argument("game_path", help="projectzomboid.jar OR decompiled folder")
    parser.add_argument("mod_path", help="Mod .jar or folder")
    parser.add_argument("--cache", default="game_api_cache.pkl", help="Cache file")
    parser.add_argument("--no-cache", action="store_true", help="Force re-index")
    parser.add_argument("--output", "-o", help="Output report file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed references")
    parser.add_argument("--lua-only", action="store_true", help="Skip Java, only run Lua checks")

    args = parser.parse_args()

    # ── Mod parsing ──
    print("→ Scanning mod...")
    mod_refs = ModReferences()
    mod_refs.parse_mod(args.mod_path)

    if args.lua_only:
        print(f"   Lua warnings found: {len(mod_refs.lua_references.references)}")
        issues = []
        for ref in mod_refs.lua_references.references:
            issues.append({
                "severity": "WARNING",
                "message": ref["message"],
                "source": f"{ref['source_file']}:{ref['line']}"
            })
    else:
        # ── Game indexing (new kirjava version) ──
        print("→ Building game API index...")
        game_api = GameAPI()
        game_api.build_index(args.game_path, None if args.no_cache else args.cache)

        print("→ Running compatibility analysis...")
        checker = CompatibilityChecker(game_api, mod_refs)
        issues = checker.check()

    # ── Output ──
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]

    if args.output:
        out_path = Path(args.output)
        with open(out_path, "w", encoding="utf-8") as f:
            _write_report(issues, f)
        print(f"✅ Full report written to: {out_path}")
    else:
        _write_report(issues, sys.stdout)

    # ── Summary ──
    print("\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total issues : {len(issues)}")
    print(f"   Errors    : {len(errors)}")
    print(f"   Warnings  : {len(warnings)}")
    print(f"Game classes : {len(game_api.classes) if not args.lua_only else 'N/A'}")
    print("="*70)

    if errors:
        print(f"⚠️  {len(errors)} CRITICAL ERRORS — mod likely broken on B42!")
    elif warnings:
        print("⚠️  Only warnings — mod should mostly work but may need tweaks.")
    else:
        print("✅ No compatibility issues detected!")

    if args.verbose and mod_refs.references:
        print("\nSample references (first 5):")
        for ref in mod_refs.references[:5]:
            print(f"   {ref.get('type')} → {ref.get('target_class')}.{ref.get('target_member') or ''}")

def _write_report(issues, out):
    errors = [i for i in issues if i.get("severity") == "ERROR"]
    warnings = [i for i in issues if i.get("severity") == "WARNING"]

    out.write("=" * 80 + "\n")
    out.write("PROJECT ZOMBOID MOD COMPATIBILITY REPORT (B42)\n")
    out.write("=" * 80 + "\n\n")
    out.write(f"Total issues : {len(issues)}\n")
    out.write(f"Errors       : {len(errors)}\n")
    out.write(f"Warnings     : {len(warnings)}\n\n")

    if errors:
        out.write("ERRORS:\n" + "─" * 70 + "\n")
        for e in errors:
            out.write(f"[{e.get('severity')}] {e.get('message')}\n")
            out.write(f"    at {e.get('source', '—')}\n\n")

    if warnings:
        out.write("WARNINGS:\n" + "─" * 70 + "\n")
        for w in warnings:
            out.write(f"[{w.get('severity')}] {w.get('message')}\n")
            out.write(f"    at {w.get('source', '—')}\n\n")

    out.write("=" * 80 + "\n")


if __name__ == "__main__":
    main()