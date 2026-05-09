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


# UCB confirmation magic values (8 bytes each, little-endian 64-bit words).
#
# Only two canonical values exist — there is no "mode" switch; `aurix_ucb.c`'s
# `#if UCB_CONFIRMATION_MODE` at lines 173/178 was selecting *which state the
# C code tests for*, not distinguishing two values of the same state:
#
#   UNLOCKED  = 0x0000_0000_4321_1234  (bytes 34 12 21 43 00 00 00 00)
#   CONFIRMED = 0x0000_0000_57B5_327F  (bytes 7F 32 B5 57 00 00 00 00)
#   anything else → ERRORED
#
# UNLOCKED byte pattern verified against a real TC4Dx UCB dump.
_UNLOCKED_MAGIC:  bytes = b"\x34\x12\x21\x43\x00\x00\x00\x00"
_CONFIRMED_MAGIC: bytes = b"\x7f\x32\xb5\x57\x00\x00\x00\x00"
_ERRORED_SENTINEL: bytes = b"\xff\xff\xff\xff\xff\xff\xff\xff"  # erased-flash; only used for encoding

_MAGIC: dict[ConfirmationState, bytes] = {
    ConfirmationState.UNLOCKED:  _UNLOCKED_MAGIC,
    ConfirmationState.CONFIRMED: _CONFIRMED_MAGIC,
    ConfirmationState.ERRORED:   _ERRORED_SENTINEL,
}


def confirmation_magic(state: ConfirmationState) -> bytes:
    """Return the 8-byte confirmation magic for a given UCB state."""
    return _MAGIC[state]


def detect_confirmation(blob: bytes) -> ConfirmationState:
    """Decode an 8-byte CONFIRMATION region to a UCB state.

    Rule: match against UNLOCKED first, then CONFIRMED; anything else is ERRORED.
    """
    if blob == _UNLOCKED_MAGIC:
        return ConfirmationState.UNLOCKED
    if blob == _CONFIRMED_MAGIC:
        return ConfirmationState.CONFIRMED
    return ConfirmationState.ERRORED
