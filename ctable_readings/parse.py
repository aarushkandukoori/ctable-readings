"""Turn a model's raw text answer into a reading (a tuple of slot values)."""
import re

from .dataset import FAMILIES

INVALID = "invalid"


def norm_time(v):
    """'10 PM', '22:00', '9:30pm', 22 -> 'HH:MM'. Returns None if it cannot tell."""
    if isinstance(v, (int, float)):
        h = int(v)
        return f"{h:02d}:00" if 0 <= h < 24 else None
    s = str(v).strip().lower().replace(".", "")
    m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", s)
    if not m:
        return None
    h, mi, ap = int(m.group(1)), int(m.group(2) or 0), m.group(3)
    if ap == "pm" and h < 12:
        h += 12
    if ap == "am" and h == 12:
        h = 0
    if not (0 <= h < 24 and 0 <= mi < 60):
        return None
    return f"{h:02d}:{mi:02d}"


def norm_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    m = re.search(r"-?\d+", str(v))
    return int(m.group(0)) if m else None


def norm_value(slot_spec, v):
    kind = slot_spec["kind"]
    if kind == "enum":
        s = str(v).strip().lower().replace(" ", "_").replace("-", "_")
        return s if s in slot_spec["values"] else INVALID
    if kind == "int":
        x = norm_int(v)
        return INVALID if x is None else x
    if kind == "time":
        x = norm_time(v)
        return INVALID if x is None else x
    raise ValueError(kind)


def _find_key(text, name):
    """Value of the first '"name": value' anywhere in the text (works inside nested
    objects, lists and when the model adds // comments). Lists count as no answer."""
    m = re.search(r'"%s"\s*:\s*("([^"]*)"|-?\d+(?:\.\d+)?|\[|true|false|null)' % re.escape(name), text)
    if not m:
        return None, False
    tok = m.group(1)
    if tok == "[" or tok in ("true", "false", "null"):
        return INVALID, True
    if tok.startswith('"'):
        return m.group(2), True
    return float(tok) if "." in tok else int(tok), True


def parse_reading(family, text):
    """Return a tuple of normalized slot values, or None if none of the keys appear."""
    slots = FAMILIES[family]["slots"]
    vals = []
    found_any = False
    for name, spec in slots.items():
        v, found = _find_key(text, name)
        found_any |= found
        vals.append(INVALID if (not found or v == INVALID) else norm_value(spec, v))
    return tuple(vals) if found_any else None
