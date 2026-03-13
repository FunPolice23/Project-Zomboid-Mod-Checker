from typing import Dict, Any, List, Optional

class CompatibilityChecker:
    def __init__(self, game_api, mod_refs):
        self.game_api = game_api
        self.mod_refs = mod_refs
        self.issues: List[Dict[str, Any]] = []

    def check(self):
        for ref in self.mod_refs.references:
            source = f"{ref.get('source_class', 'Unknown')}.{ref.get('source_method', 'Unknown')}:{ref.get('line', '?')}"

            tgt_class = ref.get("target_class")
            if not tgt_class or tgt_class not in self.game_api.classes:
                self.issues.append({
                    "severity": "ERROR",
                    "source": source,
                    "message": f"Missing class: {tgt_class}"
                })
                continue

            ref_type = ref.get("type")
            member_name = ref.get("target_member")
            descriptor = ref.get("descriptor")

            # ── METHOD CALL ──
            if ref_type == "method_call" and member_name:
                found = self._find_method(tgt_class, member_name, descriptor)
                if not found:
                    similar = self._find_similar_methods(tgt_class, member_name)
                    if similar:
                        descs = ", ".join(f"{m['name']}{m['descriptor']}" for m in similar)
                        msg = f"Method signature changed or removed: {member_name}\n  expected: {descriptor or '(any)'}\n  found: {descs}"
                        self.issues.append({"severity": "ERROR", "message": msg, "source": source})
                    else:
                        self.issues.append({
                            "severity": "ERROR",
                            "message": f"Missing method: {member_name}{descriptor or ''}",
                            "source": source
                        })
                elif not self._is_accessible(ref.get("source_class", ""), tgt_class, found):
                    self.issues.append({
                        "severity": "WARNING",
                        "message": f"Method may no longer be accessible (visibility changed): {member_name}{descriptor or ''}",
                        "source": source
                    })

            # ── FIELD ACCESS ──
            elif ref_type == "field_access" and member_name:
                found = self._find_field(tgt_class, member_name, descriptor)
                if not found:
                    similar = self._find_similar_fields(tgt_class, member_name)
                    if similar:
                        descs = ", ".join(f"{f['name']}{f['descriptor']}" for f in similar)
                        msg = f"Field type or signature changed: {member_name}\n  expected: {descriptor or '(any)'}\n  found: {descs}"
                        self.issues.append({"severity": "ERROR", "message": msg, "source": source})
                    else:
                        self.issues.append({
                            "severity": "ERROR",
                            "message": f"Missing field: {member_name}{descriptor or ''}",
                            "source": source
                        })
                elif not self._is_accessible(ref.get("source_class", ""), tgt_class, found):
                    self.issues.append({
                        "severity": "WARNING",
                        "message": f"Field may no longer be accessible: {member_name}",
                        "source": source
                    })

            # class_reference already handled above

        # ── Lua issues (unchanged, just added as warnings) ──
        for ref in self.mod_refs.lua_references.references:
            self.issues.append({
                "severity": "WARNING",
                "message": ref["message"],
                "source": f"{ref['source_file']}:{ref['line']}"
            })

        return self.issues

    # ── Helper methods (updated for new rich structure) ──
    def _find_method(self, cls: str, name: str, desc: str | None, visited=None) -> Optional[Dict]:
        if visited is None:
            visited = set()
        if cls in visited or cls not in self.game_api.classes:
            return None
        visited.add(cls)

        info = self.game_api.classes[cls]
        for m in info["methods"]:
            if m["name"] == name and (not desc or m["descriptor"] == desc):
                return m

        # inheritance
        if info["super_name"]:
            found = self._find_method(info["super_name"], name, desc, visited)
            if found: return found
        for iface in info["interfaces"]:
            found = self._find_method(iface, name, desc, visited)
            if found: return found

        return None

    def _find_field(self, cls: str, name: str, desc: str | None, visited=None) -> Optional[Dict]:
        if visited is None:
            visited = set()
        if cls in visited or cls not in self.game_api.classes:
            return None
        visited.add(cls)

        info = self.game_api.classes[cls]
        for f in info["fields"]:
            if f["name"] == name and (not desc or f["descriptor"] == desc):
                return f

        # inheritance (super + interfaces)
        if info["super_name"]:
            found = self._find_field(info["super_name"], name, desc, visited)
            if found: return found
        for iface in info["interfaces"]:
            found = self._find_field(iface, name, desc, visited)
            if found: return found

        return None

    def _find_similar_methods(self, cls: str, name: str) -> List[Dict]:
        result = []
        queue = [cls]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current in visited: continue
            visited.add(current)
            if current not in self.game_api.classes: continue

            info = self.game_api.classes[current]
            result.extend(m for m in info["methods"] if m["name"] == name)

            if info["super_name"]:
                queue.append(info["super_name"])
            queue.extend(info["interfaces"])

        return result

    def _find_similar_fields(self, cls: str, name: str) -> List[Dict]:
        result = []
        queue = [cls]
        visited = set()

        while queue:
            current = queue.pop(0)
            if current in visited: continue
            visited.add(current)
            if current not in self.game_api.classes: continue

            info = self.game_api.classes[current]
            result.extend(f for f in info["fields"] if f["name"] == name)

            if info["super_name"]:
                queue.append(info["super_name"])
            queue.extend(info["interfaces"])

        return result

    def _is_accessible(self, src_cls: str, tgt_cls: str, member: Dict) -> bool:
        flags = member.get("access_flags", 0)
        if flags & 0x0001: return True          # public
        if src_cls == tgt_cls: return True

        src_pkg = src_cls.rsplit(".", 1)[0] if "." in src_cls else ""
        tgt_pkg = tgt_cls.rsplit(".", 1)[0] if "." in tgt_cls else ""

        if src_pkg == tgt_pkg and not (flags & 0x0002):  # package-private
            return True

        return False  # protected/private = not accessible from mod


if __name__ == "__main__":
    print("CompatibilityChecker loaded")