#!/usr/bin/env python3
"""Merge every themes/*.yaml (except the generated file) into themes/woow_ha_themes.yaml.

HACS theme repos can only ship ONE yaml file, so this generated file is what HACS installs
(see hacs.json "filename"). The individual files stay as the editable sources.
Run:  python3 scripts/build_combined_theme.py   (CI runs it on every push to main)
"""
from __future__ import annotations
import re, sys, pathlib, yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
THEMES = ROOT / "themes"
OUT = THEMES / "woow_ha_themes.yaml"
HEADER = (
    "# GENERATED FILE — do not edit. Built by scripts/build_combined_theme.py from the\n"
    "# individual themes/*.yaml sources. This is the single file HACS installs.\n"
)

def main() -> int:
    srcs = sorted(p for p in THEMES.glob("*.yaml") if p.name != OUT.name)
    seen: dict[str, str] = {}
    chunks = [HEADER]
    for p in srcs:
        text = p.read_text(encoding="utf-8")
        # drop YAML document markers/directives so the files can be concatenated into one doc
        text = "\n".join(l for l in text.splitlines() if not re.match(r"^(---|\.\.\.)\s*$|^%YAML", l))
        data = yaml.safe_load(text) or {}
        if not isinstance(data, dict):
            print(f"ERROR {p.name}: top level is not a mapping", file=sys.stderr); return 1
        for k in data:
            if k in seen:
                print(f"ERROR duplicate theme key '{k}' in {p.name} and {seen[k]}", file=sys.stderr); return 1
            seen[k] = p.name
        chunks.append(f"\n# ---- source: {p.name} ----\n{text.rstrip()}\n")
    combined = "".join(chunks)
    merged = yaml.safe_load(combined)
    assert isinstance(merged, dict) and set(merged) == set(seen), "merged key set mismatch"
    if OUT.exists() and OUT.read_text(encoding="utf-8") == combined:
        print(f"{OUT.name} up to date ({len(seen)} themes from {len(srcs)} files)"); return 0
    OUT.write_text(combined, encoding="utf-8")
    print(f"wrote {OUT.name}: {len(seen)} themes from {len(srcs)} files"); return 0

if __name__ == "__main__":
    sys.exit(main())
