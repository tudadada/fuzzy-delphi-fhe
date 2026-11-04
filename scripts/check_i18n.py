"""Fail if en.json and vi.json don't have exactly the same keys and placeholders."""
import json, re, sys
from pathlib import Path

d = Path(__file__).resolve().parent.parent / "web" / "i18n"
en = json.loads((d / "en.json").read_text(encoding="utf-8"))
vi = json.loads((d / "vi.json").read_text(encoding="utf-8"))
ph = lambda s: sorted(re.findall(r"\{(\w+)\}", s))
errors = [f"missing in vi: {k}" for k in en if k not in vi] + \
         [f"missing in en: {k}" for k in vi if k not in en] + \
         [f"placeholder mismatch: {k}" for k in en if k in vi and ph(en[k]) != ph(vi[k])]
print("\n".join(errors) or f"OK: {len(en)} keys match")
sys.exit(1 if errors else 0)
