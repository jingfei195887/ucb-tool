"""Chip-specific UCB layout.

Source of truth: vendor/infineon/chips/aurix/aurix_ucb.h (see spec for citation).
TC4Dx: stride 0x800 (2 KB), slots per table below.
TC48x / TC4Zx: stride 0x100 (256 B), different slot assignments.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ChipFamily(str, Enum):
    TC4DX = "TC4Dx"
    TC48X = "TC48x"
    TC4ZX = "TC4Zx"


RTC_BASE = 0xAE400000
CS_BASE = 0xAEC00000


@dataclass(frozen=True)
class ChipProfile:
    chip_id: str  # lower-case: tc4d9, tc4d7, tc489, tc4z9, ...
    family: ChipFamily
    stride: int  # bytes per UCB slot
    slots: dict[str, tuple[int, int]]  # ucb_name -> (region_base, slot_no)
    schema_dir: str  # name under schemas/ (tc4dx / tc48x / tc4zx)

    def address(self, ucb_name: str) -> int:
        region_base, slot = self.slots[ucb_name]
        return region_base + slot * self.stride


# --- Slot tables (derived from aurix_ucb.h) ------------------------------

_TC4DX_SLOTS: dict[str, tuple[int, int]] = {
    "USERCFG_ORIG_RTC": (RTC_BASE, 17),
    "USERCFG_COPY_RTC": (RTC_BASE, 18),
    "SWAP_ORIG_RTC":    (RTC_BASE, 19),
    "SWAP_COPY_RTC":    (RTC_BASE, 20),
    "SWAP_ORIG_CS":     (CS_BASE, 12),
    "SWAP_COPY_CS":     (CS_BASE, 13),
    "USERCFG_ORIG_CS":  (CS_BASE, 15),
    "USERCFG_COPY_CS":  (CS_BASE, 16),
}

_TC48X_TC4ZX_SLOTS: dict[str, tuple[int, int]] = {
    "USERCFG_ORIG_RTC": (RTC_BASE, 2),
    "USERCFG_COPY_RTC": (RTC_BASE, 3),
    "SWAP_ORIG_RTC":    (RTC_BASE, 6),
    "SWAP_COPY_RTC":    (RTC_BASE, 7),
    "USERCFG_ORIG_CS":  (CS_BASE, 7),
    "USERCFG_COPY_CS":  (CS_BASE, 8),
    "SWAP_ORIG_CS":     (CS_BASE, 12),
    "SWAP_COPY_CS":     (CS_BASE, 13),
}

# BMHD_0..3 are at fixed addresses below the UCB slot region in all families.
_BMHD_ADDRS: dict[str, tuple[int, int]] = {
    "BMHD_0": (0xAF400000, 0),  # slot_no=0 + stride=0 -> use base directly
    "BMHD_1": (0xAF400200, 0),
    "BMHD_2": (0xAF400400, 0),
    "BMHD_3": (0xAF400600, 0),
}


def _build(chip_id: str, family: ChipFamily, stride: int,
           slots: dict[str, tuple[int, int]], schema_dir: str) -> ChipProfile:
    merged: dict[str, tuple[int, int]] = dict(slots)
    # BMHDs are fixed-address, treat as slot 0 at the address itself
    for name, (addr, _) in _BMHD_ADDRS.items():
        merged[name] = (addr, 0)
    return ChipProfile(chip_id=chip_id, family=family, stride=stride,
                       slots=merged, schema_dir=schema_dir)


_REGISTRY: dict[str, ChipProfile] = {
    "tc4d9": _build("tc4d9", ChipFamily.TC4DX, 0x800, _TC4DX_SLOTS, "tc4dx"),
    "tc4d7": _build("tc4d7", ChipFamily.TC4DX, 0x800, _TC4DX_SLOTS, "tc4dx"),
    "tc489": _build("tc489", ChipFamily.TC48X, 0x100, _TC48X_TC4ZX_SLOTS, "tc48x"),
    "tc4z9": _build("tc4z9", ChipFamily.TC4ZX, 0x100, _TC48X_TC4ZX_SLOTS, "tc4zx"),
}


def list_chips() -> list[str]:
    return sorted(_REGISTRY.keys())


def get_profile(chip_id: str) -> ChipProfile:
    try:
        return _REGISTRY[chip_id.lower()]
    except KeyError as exc:
        raise KeyError(f"unknown chip {chip_id!r}; known: {list_chips()}") from exc


def ucb_address(chip_id: str, ucb_name: str) -> int:
    return get_profile(chip_id).address(ucb_name)
