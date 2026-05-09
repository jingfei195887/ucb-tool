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


# UCB confirmation magic values.
#
# Decoding rule (from user + Infineon):
#   blob == UNLOCKED magic  → UNLOCKED
#   blob == CONFIRMED magic → CONFIRMED
#   anything else           → ERRORED
#
# UNLOCKED (verified against a real TC4Dx UCB dump):
#   mode 0 (non-secure / default):  0x0000_0000_4321_1234
#   mode 1 (secure alternate):      0x0000_0000_57B5_327F
#   In aurix_ucb.c:173/178 this same byte pattern is named `confirmation_code[]`;
#   the C code's memcmp() at line 906 actually tests *for* UNLOCKED (despite the
#   variable name).
#
# CONFIRMED: UNKNOWN.  Needs extraction from Infineon UM §6.3.13 "UCB
# confirmation code and UCB state evaluation" or aurix_ucb.c:334
# ucb_confirmation_status().  Until then we use a placeholder byte pattern
# that is UNLIKELY to appear in real flash (all 0xA5).  Consequences:
#   - A real UCB in CONFIRMED state WILL be misdetected as ERRORED.
#   - Writing state=CONFIRMED will produce a non-canonical byte pattern.
# This is acceptable for v0.1 because all real TC4Dx UCBs we have samples
# of are UNLOCKED; tighten before anyone attempts to read a CONFIRMED UCB.
_CONFIRMED_PLACEHOLDER = b"\xa5\xa5\xa5\xa5\xa5\xa5\xa5\xa5"  # TBD: extract real magic

_MAGIC: dict[tuple[int, ConfirmationState], bytes] = {
    (0, ConfirmationState.UNLOCKED):  b"\x34\x12\x21\x43\x00\x00\x00\x00",
    (1, ConfirmationState.UNLOCKED):  b"\x7f\x32\xb5\x57\x00\x00\x00\x00",
    (0, ConfirmationState.CONFIRMED): _CONFIRMED_PLACEHOLDER,
    (1, ConfirmationState.CONFIRMED): _CONFIRMED_PLACEHOLDER,
    # ERRORED sentinel used only for *encoding* (write back) — any value that
    # is neither UNLOCKED nor CONFIRMED works.  All-0xFF is the erased-flash
    # convention.  Decoding never reads this entry; it catches the "else" case.
    (0, ConfirmationState.ERRORED):   b"\xff\xff\xff\xff\xff\xff\xff\xff",
    (1, ConfirmationState.ERRORED):   b"\xff\xff\xff\xff\xff\xff\xff\xff",
}


def confirmation_magic(state: ConfirmationState, mode: int = 0) -> bytes:
    return _MAGIC[(mode, state)]


def detect_confirmation(blob: bytes, mode: int = 0) -> ConfirmationState:
    """Decode an 8-byte CONFIRMATION region to a UCB state.

    Rule: match against UNLOCKED, then CONFIRMED; anything else is ERRORED.
    """
    if blob == _MAGIC[(mode, ConfirmationState.UNLOCKED)]:
        return ConfirmationState.UNLOCKED
    if blob == _MAGIC[(mode, ConfirmationState.CONFIRMED)]:
        return ConfirmationState.CONFIRMED
    return ConfirmationState.ERRORED
