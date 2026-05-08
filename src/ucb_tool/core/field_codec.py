from __future__ import annotations

import zlib
from typing import Literal

Endian = Literal["little", "big"]


def encode_int(value: int, size: int, endian: Endian) -> bytes:
    """Encode an unsigned integer into exactly `size` bytes."""
    if value < 0:
        raise ValueError(f"negative value {value} not supported")
    if value >= 1 << (size * 8):
        raise ValueError(f"value {value:#x} does not fit in {size} bytes")
    return value.to_bytes(size, endian)


def decode_int(blob: bytes, endian: Endian) -> int:
    return int.from_bytes(blob, endian)


BitRange = tuple[int, int]  # (lo, hi) inclusive


def pack_bitfield(values: dict[str, int | bool], layout: dict[str, BitRange]) -> int:
    """Pack named bit-fields into a single integer.

    layout: {name: (lo_bit, hi_bit)} - both inclusive.
    values: {name: int or bool}
    """
    out = 0
    for name, (lo, hi) in layout.items():
        width = hi - lo + 1
        v = int(values.get(name, 0))
        if v < 0 or v >= 1 << width:
            raise ValueError(
                f"bitfield {name}={v} does not fit in {width} bits [{lo}..{hi}]"
            )
        mask = (1 << width) - 1
        out |= (v & mask) << lo
    return out


def unpack_bitfield(packed: int, layout: dict[str, BitRange]) -> dict[str, int]:
    out: dict[str, int] = {}
    for name, (lo, hi) in layout.items():
        width = hi - lo + 1
        mask = (1 << width) - 1
        out[name] = (packed >> lo) & mask
    return out


def crc32_aurix(data: bytes) -> int:
    """CRC-32/IEEE 802.3.

    Matches vendor/infineon/chips/aurix/aurix_ucb.c:648 crc32_software().
    Python's zlib.crc32 implements the same polynomial with the same
    init/final XOR convention.
    """
    return zlib.crc32(data) & 0xFFFFFFFF
