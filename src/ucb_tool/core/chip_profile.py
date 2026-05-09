"""Chip-specific UCB layout.

Each AURIX chip family differs in the size of an individual UCB slot
(its ``stride``) and in which schema subdirectory supplies per-family
definitions:

* ``tc4dx`` — TC4D9 / TC4D7, stride 0x800 (2 KB)
* ``tc48x`` — TC489, stride 0x100 (256 B)
* ``tc4zx`` — TC4Z9, stride 0x100 (256 B)

UCB0 region is rooted at 0xAE400000; UCB1 region at 0xAEC00000. Per-slot
absolute addresses are encoded directly in each generated schema's
``x-ucb-meta.addresses`` field, so this module no longer needs the old
``slots`` dict. A ``slots`` attribute is still exposed as an empty dict for
backward compatibility with older callers that pre-date schema-driven
addresses.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class ChipFamily(str, Enum):
    TC4DX = "TC4Dx"
    TC48X = "TC48x"
    TC4ZX = "TC4Zx"


# Region base addresses. Kept for callers (e.g. UcbBundle) that still
# reference them directly.
UCB0_BASE = 0xAE400000
UCB1_BASE = 0xAEC00000


@dataclass(frozen=True)
class ChipProfile:
    chip_id: str          # lower-case: tc4d9, tc4d7, tc489, tc4z9, ...
    family: ChipFamily
    stride: int           # bytes per UCB slot
    schema_dir: str       # name under schemas/ (tc4dx / tc48x / tc4zx)
    # `slots` is deprecated — addresses now live in each schema's
    # x-ucb-meta.addresses entry. Kept as an empty dict so legacy code
    # doesn't KeyError when probing it.
    slots: dict[str, tuple[int, int]] = field(default_factory=dict)

    def address(self, ucb_name: str) -> int:
        """Deprecated: read addresses directly from the schema instead."""
        raise KeyError(
            f"ChipProfile.address() is deprecated; look up {ucb_name!r} "
            "in the schema's x-ucb-meta.addresses entry instead."
        )


_REGISTRY: dict[str, ChipProfile] = {
    "tc4d9": ChipProfile("tc4d9", ChipFamily.TC4DX, 0x800, "tc4dx"),
    "tc4d7": ChipProfile("tc4d7", ChipFamily.TC4DX, 0x800, "tc4dx"),
    "tc489": ChipProfile("tc489", ChipFamily.TC48X, 0x100, "tc48x"),
    "tc4z9": ChipProfile("tc4z9", ChipFamily.TC4ZX, 0x100, "tc4zx"),
}


def list_chips() -> list[str]:
    return sorted(_REGISTRY.keys())


def get_profile(chip_id: str) -> ChipProfile:
    try:
        return _REGISTRY[chip_id.lower()]
    except KeyError as exc:
        raise KeyError(
            f"unknown chip {chip_id!r}; known: {list_chips()}"
        ) from exc


def ucb_address(chip_id: str, ucb_name: str) -> int:
    """Deprecated shim: raises KeyError for all names now.

    Addresses are supplied by each schema's ``x-ucb-meta.addresses`` entry.
    This function is kept so older callers fail loudly rather than
    silently returning a wrong address.
    """
    # Validate that chip_id is known so callers still get a sensible error
    # on unknown chips.
    get_profile(chip_id)
    raise KeyError(
        f"ucb_address() no longer resolves {ucb_name!r}; read "
        "x-ucb-meta.addresses from the schema for this chip."
    )
