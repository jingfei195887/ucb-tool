from __future__ import annotations

import zlib
from enum import Enum
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


class ConfirmationState(str, Enum):
    UNLOCKED = "UNLOCKED"
    CONFIRMED = "CONFIRMED"
    ERRORED = "ERRORED"


# Source: vendor/infineon/chips/aurix/aurix_ucb.c
# CONFIRMED is extracted directly from lines 173/178; UNLOCKED and ERRORED
# require extraction at implementation time (see plan M2.4 notes).
_MAGIC: dict[tuple[int, ConfirmationState], bytes] = {
    (0, ConfirmationState.CONFIRMED): b"\x34\x12\x21\x43\x00\x00\x00\x00",
    (1, ConfirmationState.CONFIRMED): b"\x7f\x32\xb5\x57\x00\x00\x00\x00",
    # UNLOCKED = all-0xFF (erased flash) per Infineon convention; confirm via C code.
    (0, ConfirmationState.UNLOCKED): b"\xff\xff\xff\xff\xff\xff\xff\xff",
    (1, ConfirmationState.UNLOCKED): b"\xff\xff\xff\xff\xff\xff\xff\xff",
    # ERRORED sentinel: per aurix_ucb.c logic, any non-matching blob is ERRORED.
    # For encoding, represent with all 0x00.
    (0, ConfirmationState.ERRORED): b"\x00\x00\x00\x00\x00\x00\x00\x00",
    (1, ConfirmationState.ERRORED): b"\x00\x00\x00\x00\x00\x00\x00\x00",
}


def confirmation_magic(state: ConfirmationState, mode: int = 0) -> bytes:
    return _MAGIC[(mode, state)]


def detect_confirmation(blob: bytes, mode: int = 0) -> ConfirmationState:
    """Given an 8-byte confirmation region, return which state it represents.

    Anything that is not UNLOCKED nor CONFIRMED is treated as ERRORED.
    """
    if blob == _MAGIC[(mode, ConfirmationState.CONFIRMED)]:
        return ConfirmationState.CONFIRMED
    if blob == _MAGIC[(mode, ConfirmationState.UNLOCKED)]:
        return ConfirmationState.UNLOCKED
    return ConfirmationState.ERRORED
