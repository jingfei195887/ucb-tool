from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ucb_tool.core.errors import SchemaError


def _parse_hex_or_int(v: object) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, str):
        return int(v, 0)
    raise SchemaError(f"expected int or hex string, got {v!r}")


@dataclass
class UcbSchema:
    name: str
    schema: dict[str, Any]
    meta: dict[str, Any]

    @property
    def size(self) -> int:
        return int(self.meta["size"])

    @property
    def has_orig_copy(self) -> bool:
        return bool(self.meta.get("has_orig_copy", False))

    def address_for_family(self, family: str) -> tuple[int, int | None]:
        """Return (orig_addr, copy_addr_or_None)."""
        addrs = self.meta.get("addresses") or {}
        if family not in addrs:
            raise KeyError(f"UCB {self.name} has no address for family {family}")
        entry = addrs[family]
        orig = _parse_hex_or_int(entry["orig"])
        copy = _parse_hex_or_int(entry["copy"]) if "copy" in entry else None
        return orig, copy


class SchemaRegistry(dict[str, UcbSchema]):
    """Name → UcbSchema."""


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge: overlay dict into base dict; scalar/list values replace."""
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _validate_ucb_meta(schema: dict[str, Any], path: Path) -> dict[str, Any]:
    meta = schema.get("x-ucb-meta")
    if not isinstance(meta, dict):
        raise SchemaError(f"{path}: missing or invalid x-ucb-meta")
    for key in ("name", "size", "addresses"):
        if key not in meta:
            raise SchemaError(f"{path}: x-ucb-meta missing '{key}'")
    return meta


def load_schemas(common_dirs: Iterable[Path], chip_schema_dir: Path | None) -> SchemaRegistry:
    """Load common/*.json then overlay chip-specific *.json by $id.

    Args:
        common_dirs: one or more directories treated as 'common' tier.
        chip_schema_dir: optional overlay dir (e.g., schemas/tc4dx).
    """
    by_id: dict[str, dict[str, Any]] = {}
    source_of_id: dict[str, Path] = {}

    for d in common_dirs:
        for p in sorted(Path(d).glob("*.json")):
            raw = json.loads(p.read_text(encoding="utf-8"))
            sid = raw.get("$id")
            if not sid:
                raise SchemaError(f"{p}: missing $id")
            by_id[sid] = raw
            source_of_id[sid] = p

    if chip_schema_dir is not None:
        for p in sorted(Path(chip_schema_dir).glob("*.json")):
            raw = json.loads(p.read_text(encoding="utf-8"))
            sid = raw.get("$id")
            if not sid:
                raise SchemaError(f"{p}: missing $id")
            base = by_id.get(sid, {})
            by_id[sid] = _deep_merge(base, raw)
            source_of_id[sid] = p

    reg = SchemaRegistry()
    for sid, schema in by_id.items():
        meta = _validate_ucb_meta(schema, source_of_id[sid])
        reg[meta["name"]] = UcbSchema(name=meta["name"], schema=schema, meta=meta)
    return reg
