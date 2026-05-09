from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from ucb_tool.core.chip_profile import get_profile
from ucb_tool.core.errors import SchemaError, ValidationError
from ucb_tool.core.field_codec import (
    BitRange,
    ConfirmationState,
    Endian,
    confirmation_magic,
    crc32_aurix,
    decode_int,
    encode_int,
)
from ucb_tool.core.hex_io import merge_range, read_hex, slice_range, write_hex
from ucb_tool.core.schema_loader import (
    SchemaRegistry,
    UcbSchema,
    load_schemas,
    resolve_profile_addresses,
)

_ARRAY_RE = re.compile(r"^([^\[]+)\[(\d+)\]$")


@dataclass(frozen=True)
class FieldPath:
    parts: list[str]
    index: int | None = None  # for PASSWORD[3] style

    @classmethod
    def parse(cls, s: str) -> FieldPath:
        m = _ARRAY_RE.match(s)
        if m:
            return cls(parts=[m.group(1)], index=int(m.group(2)))
        return cls(parts=s.split("."), index=None)


@dataclass
class FieldDescriptor:
    name: str
    path: str  # dot path including parent scopes
    offset: int  # relative to UCB start
    size: int
    endian: str
    schema: dict[str, Any]
    bit_range: BitRange | None = None  # None for non-bitfield; set for sub-fields
    parent_offset: int | None = None
    parent_size: int | None = None

    @property
    def danger(self) -> str:
        return str(self.schema.get("x-danger", "safe"))

    @property
    def computed(self) -> str | None:
        v = self.schema.get("x-computed")
        return str(v) if v is not None else None

    @property
    def read_only(self) -> bool:
        return bool(self.schema.get("readOnly", False))


def _walk_fields(schema: dict[str, Any], prefix: str = "") -> list[FieldDescriptor]:
    """Yield leaf FieldDescriptors by walking `properties` recursively.

    Handles simple fields, bitfield parent+children (with x-bits),
    and fixed-length arrays.
    """
    out: list[FieldDescriptor] = []
    props: dict[str, Any] = schema.get("properties") or {}
    for name, sub in props.items():
        dot = f"{prefix}{name}" if not prefix else f"{prefix}.{name}"
        if sub.get("x-bitfield"):
            parent_off = int(sub["x-offset"])
            parent_sz = int(sub["x-size"])
            parent_endian = sub.get("x-endian", "little")
            for child_name, child in (sub.get("properties") or {}).items():
                bits = child.get("x-bits")
                if bits is None:
                    raise SchemaError(
                        f"bitfield child {dot}.{child_name} missing x-bits"
                    )
                out.append(FieldDescriptor(
                    name=child_name,
                    path=f"{dot}.{child_name}",
                    offset=parent_off,
                    size=parent_sz,
                    endian=parent_endian,
                    schema=child,
                    bit_range=(int(bits[0]), int(bits[1])),
                    parent_offset=parent_off,
                    parent_size=parent_sz,
                ))
            # also expose parent as a read-only descriptor (for display)
            out.append(FieldDescriptor(
                name=name,
                path=dot,
                offset=parent_off,
                size=parent_sz,
                endian=parent_endian,
                schema={**sub, "readOnly": True},
            ))
        elif sub.get("type") == "array":
            off = int(sub["x-offset"])
            total = int(sub["x-size"])
            items = sub["items"]
            n = int(sub.get("maxItems", sub.get("minItems", 1)))
            item_size = total // n
            for i in range(n):
                out.append(FieldDescriptor(
                    name=f"{name}[{i}]",
                    path=f"{dot}[{i}]",
                    offset=off + i * item_size,
                    size=item_size,
                    endian=sub.get("x-endian", "little"),
                    schema=items,
                ))
        else:
            out.append(FieldDescriptor(
                name=name,
                path=dot,
                offset=int(sub["x-offset"]),
                size=int(sub["x-size"]),
                endian=sub.get("x-endian", "little"),
                schema=sub,
            ))
    return out


@dataclass
class UcbInstance:
    schema: UcbSchema
    family: str
    orig_addr: int
    copy_addr: int | None
    buf_orig: bytearray
    buf_copy: bytearray | None
    advanced: bool = False
    fields: list[FieldDescriptor] = field(default_factory=list)

    def field_by_path(self, path: str) -> FieldDescriptor:
        for f in self.fields:
            if f.path == path:
                return f
        raise KeyError(f"field {path!r} not in UCB {self.schema.name}")

    def _read(self, buf: bytearray, f: FieldDescriptor) -> int:
        endian = cast(Endian, f.endian)
        raw = bytes(buf[f.offset:f.offset + f.size])
        packed = decode_int(raw, endian)
        if f.bit_range is not None:
            lo, hi = f.bit_range
            width = hi - lo + 1
            return (packed >> lo) & ((1 << width) - 1)
        return packed

    def _write(self, buf: bytearray, f: FieldDescriptor, value: int) -> None:
        endian = cast(Endian, f.endian)
        if f.bit_range is not None:
            lo, hi = f.bit_range
            width = hi - lo + 1
            mask = ((1 << width) - 1) << lo
            cur = decode_int(bytes(buf[f.offset:f.offset + f.size]), endian)
            cur = (cur & ~mask) | ((int(value) & ((1 << width) - 1)) << lo)
            buf[f.offset:f.offset + f.size] = encode_int(cur, f.size, endian)
        else:
            buf[f.offset:f.offset + f.size] = encode_int(
                int(value), f.size, endian
            )

    def get(self, path: str) -> int:
        return self._read(self.buf_orig, self.field_by_path(path))

    def get_copy(self, path: str) -> int:
        if self.buf_copy is None:
            raise ValueError("UCB has no COPY")
        return self._read(self.buf_copy, self.field_by_path(path))

    def set(self, path: str, value: int) -> None:
        f = self.field_by_path(path)
        if f.read_only and not self.advanced:
            raise ValidationError(path, "readOnly field; unlock Advanced mode")
        self._write(self.buf_orig, f, value)
        if self.buf_copy is not None and not self.advanced:
            self._write(self.buf_copy, f, value)

    def set_copy(self, path: str, value: int) -> None:
        if not self.advanced:
            raise ValidationError(
                path, "COPY independent edit requires Advanced mode"
            )
        if self.buf_copy is None:
            raise ValueError("UCB has no COPY")
        self._write(self.buf_copy, self.field_by_path(path), value)


def _recompute_fields(inst: UcbInstance) -> None:
    for f in inst.fields:
        algo = f.computed
        if not algo:
            continue
        if algo == "crc32-aurix":
            payload = bytes(inst.buf_orig[:f.offset])
            crc = crc32_aurix(payload)
            inst.buf_orig[f.offset:f.offset + f.size] = crc.to_bytes(f.size, "little")
            if inst.buf_copy is not None:
                payload_c = bytes(inst.buf_copy[:f.offset])
                crc_c = crc32_aurix(payload_c)
                inst.buf_copy[f.offset:f.offset + f.size] = crc_c.to_bytes(
                    f.size, "little"
                )
        elif algo == "confirmation":
            # Default to UNLOCKED when auto-recomputing — this is the safe
            # choice for freshly written UCBs that are not yet password-locked.
            # Users who explicitly want CONFIRMED must write it before save.
            magic = confirmation_magic(ConfirmationState.UNLOCKED)
            # f.size should be 8; if the schema says otherwise, truncate/extend
            magic = magic[:f.size].ljust(f.size, b"\x00")
            inst.buf_orig[f.offset:f.offset + f.size] = magic
            if inst.buf_copy is not None:
                inst.buf_copy[f.offset:f.offset + f.size] = magic
        elif algo == "zero_pad":
            inst.buf_orig[f.offset:f.offset + f.size] = b"\x00" * f.size
            if inst.buf_copy is not None:
                inst.buf_copy[f.offset:f.offset + f.size] = b"\x00" * f.size
        # Unknown algo: silently skip. Validator will flag unknowns separately.


@dataclass
class UcbBundle:
    chip_id: str
    family: str
    instances: dict[str, UcbInstance] = field(default_factory=dict)
    raw_bytes: dict[int, int] = field(default_factory=dict)

    def __getitem__(self, name: str) -> UcbInstance:
        return self.instances[name]

    @classmethod
    def load(cls, hex_path: str | Path, chip_id: str,
             common_dirs: Iterable[Path],
             chip_schema_dir: Path | None) -> UcbBundle:
        profile = get_profile(chip_id)
        schemas: SchemaRegistry = load_schemas(common_dirs, chip_schema_dir)
        resolve_profile_addresses(schemas, chip_id)
        raw = read_hex(hex_path)

        instances: dict[str, UcbInstance] = {}
        family_key = profile.family.value
        for name, schema in schemas.items():
            try:
                orig, copy = schema.address_for_family(family_key)
            except KeyError:
                continue  # this UCB not supported on this family
            size = schema.size
            buf_orig = bytearray(slice_range(raw, orig, size))
            buf_copy = (
                bytearray(slice_range(raw, copy, size))
                if copy is not None else None
            )
            inst = UcbInstance(
                schema=schema, family=family_key,
                orig_addr=orig, copy_addr=copy,
                buf_orig=buf_orig, buf_copy=buf_copy,
                fields=_walk_fields(schema.schema),
            )
            instances[name] = inst
        return cls(chip_id=chip_id, family=family_key,
                   instances=instances, raw_bytes=raw)

    def save(self, out_path: str | Path, recompute: bool = True) -> None:
        if recompute:
            for inst in self.instances.values():
                _recompute_fields(inst)
        data = dict(self.raw_bytes)
        for inst in self.instances.values():
            merge_range(data, inst.orig_addr, bytes(inst.buf_orig))
            if inst.buf_copy is not None and inst.copy_addr is not None:
                merge_range(data, inst.copy_addr, bytes(inst.buf_copy))
        write_hex(out_path, data)
