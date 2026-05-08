from __future__ import annotations

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
