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
    #: True if the loaded hex file actually covers any byte of this UCB's
    #: address range.  When False, the UCB is displayed as "empty / not
    #: present" in the UI and excluded from the saved hex output, so the
    #: partial-hex input shape is preserved on round-trip.
    present: bool = True
    #: True if this UCB is part of the chip's *mandatory* set — one that
    #: the boot ROM expects to find populated for the chip to boot cleanly.
    #: Derived at load time by comparing against the bundled reference
    #: template (src/ucb_tool/templates/{family}.hex).  Missing mandatory
    #: UCBs are flagged in the UI and can be auto-filled from the template
    #: on save via `fill_missing_mandatory()` or the `--fill-missing` flag.
    is_mandatory: bool = False

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


def _template_path_for_chip(chip_id: str) -> Path | None:
    """Locate the bundled reference template hex for a given chip.

    Templates live under ``src/ucb_tool/templates/{schema_dir}.hex`` where
    ``schema_dir`` is the chip-family directory (``tc4dx`` / ``tc48x`` /
    ``tc4zx``).  Returns None if no template exists for this chip.
    """
    from ucb_tool.core.chip_profile import get_profile
    try:
        profile = get_profile(chip_id)
    except KeyError:
        return None
    # Locate the package's templates dir regardless of install mode.
    import ucb_tool
    tpl = Path(ucb_tool.__file__).parent / "templates" / f"{profile.schema_dir}.hex"
    return tpl if tpl.is_file() else None


def _load_template_raw(chip_id: str) -> dict[int, int] | None:
    """Read the chip's reference template hex into a sparse address map."""
    tpl = _template_path_for_chip(chip_id)
    if tpl is None:
        return None
    return read_hex(tpl)


def _load_mandatory_set(chip_id: str,
                        schemas: SchemaRegistry,
                        profile: Any,
                        template_path: str | Path | None = None) -> set[str]:
    """Derive the chip's mandatory UCB set from a template.

    A UCB is "mandatory" for a given chip if the chip's reference template
    covers at least one byte of the UCB's ORIG (or COPY) address range.
    Pass ``template_path`` to override the bundled default.
    """
    if template_path is not None:
        tpl_raw: dict[int, int] | None = read_hex(template_path)
    else:
        tpl_raw = _load_template_raw(chip_id)
    if tpl_raw is None:
        return set()
    family_key = profile.family.value
    mandatory: set[str] = set()
    for name, schema in schemas.items():
        try:
            orig, copy = schema.address_for_family(family_key)
        except KeyError:
            continue
        size = schema.size
        if any((orig + i) in tpl_raw for i in range(size)) or copy is not None and any((copy + i) in tpl_raw for i in range(size)):
            mandatory.add(name)
    return mandatory


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
             chip_schema_dir: Path | None,
             template_path: str | Path | None = None) -> UcbBundle:
        """Load a hex + schemas into a bundle.

        Args:
            hex_path: user's ucb.hex to analyse / edit.
            chip_id: target chip (tc4d9 / tc4d7 / tc489 / tc4z9).
            common_dirs: schema directories applied to every chip.
            chip_schema_dir: chip-specific schema directory.
            template_path: optional override for the 'mandatory UCB set'
                template.  When None, the bundled
                ``src/ucb_tool/templates/{family}.hex`` is used.  Pass a
                project-specific template here to customise which UCBs
                count as mandatory without editing the installed package.
        """
        profile = get_profile(chip_id)
        schemas: SchemaRegistry = load_schemas(common_dirs, chip_schema_dir)
        resolve_profile_addresses(schemas, chip_id)
        raw = read_hex(hex_path)

        # Compute the mandatory UCB set for this chip: a UCB is "mandatory"
        # if it is populated in the reference template hex.  Override with
        # `template_path` to swap in a project-specific template.
        mandatory: set[str] = _load_mandatory_set(
            chip_id, schemas, profile, template_path=template_path,
        )

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
            # Presence = at least one byte of the UCB's address range is
            # actually defined in the input hex.  Missing UCBs are shown as
            # empty in the UI instead of decoding their 0xFF fill-bytes into
            # fabricated 0xFFFFFFFF field values.
            present = any((orig + i) in raw for i in range(size))
            if not present and copy is not None:
                present = any((copy + i) in raw for i in range(size))
            inst = UcbInstance(
                schema=schema, family=family_key,
                orig_addr=orig, copy_addr=copy,
                buf_orig=buf_orig, buf_copy=buf_copy,
                fields=_walk_fields(schema.schema),
                present=present,
                is_mandatory=(name in mandatory),
            )
            instances[name] = inst
        return cls(chip_id=chip_id, family=family_key,
                   instances=instances, raw_bytes=raw)

    def missing_mandatory(self) -> list[str]:
        """Names of mandatory UCBs that are not present in the loaded hex."""
        return [n for n, i in self.instances.items()
                if i.is_mandatory and not i.present]

    def fill_missing_mandatory(self, chip_id: str | None = None,
                               template_path: str | Path | None = None,
                               ) -> list[str]:
        """Copy bytes from a template into every mandatory UCB whose
        `present` is False, marking it present.

        Args:
            chip_id: override chip id (default: self.chip_id).
            template_path: optional explicit template hex path.  When
                None, falls back to the bundled
                ``src/ucb_tool/templates/{family}.hex``.  Pass a
                project-specific template here to pull in UCB byte
                patterns that differ from the default reference.

        Returns the list of UCB names that were filled.  Does not modify
        UCBs that were already present (user edits are never overwritten).
        """
        cid = chip_id or self.chip_id
        template_raw: dict[int, int] | None = (
            read_hex(template_path) if template_path is not None
            else _load_template_raw(cid)
        )
        if template_raw is None:
            return []  # no template bundled for this chip
        filled: list[str] = []
        for name, inst in self.instances.items():
            if inst.present or not inst.is_mandatory:
                continue
            size = inst.schema.size
            inst.buf_orig = bytearray(slice_range(template_raw, inst.orig_addr, size))
            if inst.copy_addr is not None:
                inst.buf_copy = bytearray(
                    slice_range(template_raw, inst.copy_addr, size)
                )
            inst.present = True
            filled.append(name)
        return filled

    def save(self, out_path: str | Path, recompute: bool = True) -> None:
        """Emit hex with edited UCBs merged back.

        UCBs whose `present` is False (absent from the input hex) are NOT
        written — this preserves the partial-hex shape of the input.  A user
        who wants to synthesize a brand-new UCB must explicitly flip
        `inst.present = True` (e.g., via an upcoming 'Initialize' UI action)
        before saving.
        """
        if recompute:
            for inst in self.instances.values():
                if inst.present:
                    _recompute_fields(inst)
        data = dict(self.raw_bytes)
        for inst in self.instances.values():
            if not inst.present:
                continue
            merge_range(data, inst.orig_addr, bytes(inst.buf_orig))
            if inst.buf_copy is not None and inst.copy_addr is not None:
                merge_range(data, inst.copy_addr, bytes(inst.buf_copy))
        write_hex(out_path, data)

    def export_ucb(self, name: str, out_path: str | Path,
                   recompute: bool = True,
                   include_copy: bool = True) -> None:
        """Write a SINGLE UCB's bytes to an Intel HEX file.

        Unlike :meth:`save`, this does NOT include any other UCBs or
        surrounding flash bytes — only the ORIG (and, by default, COPY)
        region(s) of the named UCB are emitted.  Useful for sharing a
        single UCB with another engineer or a flashing tool without
        leaking the rest of the chip image.

        Args:
            name: UCB name (matching a key in ``self.instances``).
            out_path: destination .hex path.
            recompute: if True (default) auto-fill x-computed fields
                (CRC, confirmation) before emitting.
            include_copy: if True (default) and the UCB has a COPY, its
                bytes are emitted alongside ORIG so the result stands
                alone when re-loaded.
        """
        inst = self.instances[name]
        if recompute and inst.present:
            _recompute_fields(inst)
        data: dict[int, int] = {}
        merge_range(data, inst.orig_addr, bytes(inst.buf_orig))
        if include_copy and inst.buf_copy is not None and inst.copy_addr is not None:
            merge_range(data, inst.copy_addr, bytes(inst.buf_copy))
        write_hex(out_path, data)
