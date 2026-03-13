"""Helper functions for resolving constant pool entries and line numbers.
Improved robustness for kirjava parsing and Build 41/42 compatibility."""

from typing import Optional


def normalize_class_name(name: str | None) -> str | None:
    """Convert internal JVM class name (with /) to dotted Java name."""
    if name is None:
        return None
    return name.replace('/', '.').replace('\\', '.')


def resolve_class(cf, idx: int) -> str:
    """Safely resolve a class reference from constant pool."""
    try:
        if idx is None:
            return "<unknown>"
        c = cf.constant_pool[idx]

        # Handle different kirjava structures
        if hasattr(c, 'name'):
            name_val = c.name
            if hasattr(name_val, 'value'):
                name_val = name_val.value
            return normalize_class_name(name_val)
        elif hasattr(c, 'value'):
            return normalize_class_name(c.value)
        elif hasattr(c, 'class_name'):
            return normalize_class_name(c.class_name)
    except (IndexError, AttributeError, TypeError):
        pass
    return "<unknown>"


def resolve_method_name(cf, idx: int) -> str:
    """Resolve method name from NameAndType or similar."""
    try:
        if idx is None:
            return "<unknown>"
        nt = cf.constant_pool[idx]
        if hasattr(nt, 'name'):
            name_val = nt.name
            if hasattr(name_val, 'value'):
                name_val = name_val.value
            return name_val
        elif hasattr(nt, 'value'):
            return nt.value
    except (IndexError, AttributeError, TypeError):
        pass
    return "<unknown>"


def resolve_method_descriptor(cf, idx: int) -> str:
    """Resolve method descriptor (signature)."""
    try:
        if idx is None:
            return ""
        nt = cf.constant_pool[idx]
        if hasattr(nt, 'descriptor'):
            desc_val = nt.descriptor
            if hasattr(desc_val, 'value'):
                desc_val = desc_val.value
            return desc_val
        elif hasattr(nt, 'value'):
            return nt.value
    except (IndexError, AttributeError, TypeError):
        pass
    return ""


def resolve_field_name(cf, idx: int) -> str:
    """Resolve field name from constant pool."""
    try:
        if idx is None:
            return "<unknown>"
        nt = cf.constant_pool[idx]
        if hasattr(nt, 'name'):
            name_val = nt.name
            if hasattr(name_val, 'value'):
                name_val = name_val.value
            return name_val
    except (IndexError, AttributeError, TypeError):
        pass
    return "<unknown>"


def resolve_field_descriptor(cf, idx: int) -> str:
    """Resolve field descriptor (type)."""
    try:
        if idx is None:
            return ""
        nt = cf.constant_pool[idx]
        if hasattr(nt, 'descriptor'):
            desc_val = nt.descriptor
            if hasattr(desc_val, 'value'):
                desc_val = desc_val.value
            return desc_val
    except (IndexError, AttributeError, TypeError):
        pass
    return ""


def resolve_invokedynamic_name(cf, idx: int) -> str:
    """Future-proof helper for invokedynamic (opcode 186)."""
    try:
        if idx is None:
            return "<unknown>"
        boot = cf.constant_pool[idx]
        if hasattr(boot, 'name'):
            name_val = boot.name
            if hasattr(name_val, 'value'):
                name_val = name_val.value
            return name_val
    except (IndexError, AttributeError, TypeError):
        pass
    return "<unknown>"


def get_line_number(method, offset: int = 0) -> int:
    """Robust line number lookup from LineNumberTable attribute.
    Handles multiple possible attribute layouts in kirjava."""
    try:
        for attr in getattr(method, 'attributes', []) or []:
            attr_name = getattr(attr, 'name', None)
            if attr_name != "LineNumberTable":
                continue

            # Standard layout
            line_numbers = getattr(attr, 'line_numbers', None) or getattr(attr, 'line_number_table', None)
            if isinstance(line_numbers, (list, tuple)):
                for entry in line_numbers:
                    start = getattr(entry, 'start_pc', None)
                    line = getattr(entry, 'line_number', None)
                    if start is not None and line is not None:
                        if start <= offset:
                            return line
                        if start > offset:
                            break

            # Alternative layouts
            table = getattr(attr, 'table', None)
            if isinstance(table, (list, tuple)):
                for entry in table:
                    start = getattr(entry, 'start_pc', None)
                    line = getattr(entry, 'line_number', None)
                    if start is not None and line is not None:
                        if start <= offset:
                            return line
                        if start > offset:
                            break
        return 0
    except Exception:
        return 0


if __name__ == "__main__":
    print("Constants helper loaded successfully")