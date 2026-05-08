#!/usr/bin/env python3
"""Overwrite known-sensitive UCB fields (passwords, keys) with 0xFF.

Usage: tools/sanitize_fixture.py <chip> <in.hex> <out.hex>
"""
from __future__ import annotations

import sys
from pathlib import Path

import ucb_tool
from ucb_tool.core.chip_profile import get_profile
from ucb_tool.core.ucb_bundle import UcbBundle

SENSITIVE_PREFIXES = ("PASSWORD", "HSMKEY", "DEVKEY")


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__, file=sys.stderr)
        return 2
    chip, src, dst = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    schemas_root = Path(ucb_tool.__file__).parent / "schemas"
    chip_dir = schemas_root / get_profile(chip).schema_dir
    bundle = UcbBundle.load(
        src, chip,
        common_dirs=[schemas_root / "common"],
        chip_schema_dir=chip_dir if chip_dir.is_dir() else None,
    )
    for inst in bundle.instances.values():
        for f in inst.fields:
            if any(f.path.startswith(pref) for pref in SENSITIVE_PREFIXES):
                inst.set(f.path, 0xFFFFFFFF if f.size <= 4 else 0xFFFFFFFFFFFFFFFF)
    bundle.save(dst, recompute=True)
    print(f"wrote sanitized {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
