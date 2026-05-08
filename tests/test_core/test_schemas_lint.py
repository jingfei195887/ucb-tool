import json
from pathlib import Path

import pytest

import ucb_tool

REPO_SCHEMAS = Path(ucb_tool.__file__).parent / "schemas"


def _all_schemas():
    paths = sorted(REPO_SCHEMAS.rglob("*.json"))
    out = []
    for p in paths:
        out.append((p, json.loads(p.read_text(encoding="utf-8"))))
    return out


@pytest.mark.parametrize("schema_path,schema", _all_schemas(),
                         ids=lambda x: str(x))
def test_has_ucb_meta(schema_path, schema):
    assert "x-ucb-meta" in schema, f"{schema_path} missing x-ucb-meta"
    meta = schema["x-ucb-meta"]
    for k in ("name", "size", "addresses"):
        assert k in meta, f"{schema_path} x-ucb-meta missing {k}"


def test_fields_fit_in_ucb():
    for path, schema in _all_schemas():
        size = int(schema["x-ucb-meta"]["size"])
        props = schema.get("properties") or {}
        for name, sub in props.items():
            if "x-offset" in sub and "x-size" in sub:
                off = int(sub["x-offset"]); sz = int(sub["x-size"])
                assert off + sz <= size, (
                    f"{path}: {name} off={off} size={sz} > UCB size {size}"
                )


def test_no_computed_with_bits():
    for path, schema in _all_schemas():
        props = schema.get("properties") or {}
        for name, sub in props.items():
            if sub.get("x-computed") and "x-bits" in sub:
                pytest.fail(f"{path}.{name}: cannot have x-computed + x-bits")


def test_bitfield_children_fit_in_parent():
    for path, schema in _all_schemas():
        for name, sub in (schema.get("properties") or {}).items():
            if not sub.get("x-bitfield"):
                continue
            total_bits = int(sub["x-size"]) * 8
            for child, cs in (sub.get("properties") or {}).items():
                bits = cs.get("x-bits")
                assert bits is not None, f"{path}.{name}.{child} missing x-bits"
                lo, hi = int(bits[0]), int(bits[1])
                assert 0 <= lo <= hi < total_bits, (
                    f"{path}.{name}.{child} bits {bits} out of range [0..{total_bits - 1}]"
                )
