"""Sanity checks on the bundled UM-extracted schemas.

The placeholder ``common/BMHD_0.json`` + ``common/SWAP.json`` were removed
when real UM-driven per-chip schemas replaced them. These tests now
exercise the regenerated chip-specific schemas.
"""

from pathlib import Path

import ucb_tool
from ucb_tool.core.schema_loader import load_schemas

REPO_SCHEMAS = Path(ucb_tool.__file__).parent / "schemas"


def test_common_dir_has_no_placeholders():
    # Placeholder BMHD_0.json / SWAP.json have been removed.
    common = REPO_SCHEMAS / "common"
    assert common.is_dir()
    assert list(common.glob("*.json")) == []


def test_tc4dx_bmhd0_loads():
    reg = load_schemas([REPO_SCHEMAS / "common"],
                       chip_schema_dir=REPO_SCHEMAS / "tc4dx")
    assert "BMHD0" in reg
    bmhd0 = reg["BMHD0"]
    assert bmhd0.size == 0x800  # TC4Dx stride
    orig, copy = bmhd0.address_for_family("TC4Dx")
    # UCB0_09 on TC4Dx: base 0xAE400000 + 9 * 0x800 = 0xAE404800
    assert orig == 0xAE400000 + 9 * 0x800
    assert copy is None


def test_tc48x_bmhd0_loads():
    reg = load_schemas([REPO_SCHEMAS / "common"],
                       chip_schema_dir=REPO_SCHEMAS / "tc48x")
    assert "BMHD0" in reg
    bmhd0 = reg["BMHD0"]
    assert bmhd0.size == 0x100  # TC48x stride
    orig, _ = bmhd0.address_for_family("TC48x")
    # UCB0_09 on TC48x: base 0xAE400000 + 9 * 0x100 = 0xAE400900
    assert orig == 0xAE400000 + 9 * 0x100


def test_tc4zx_bmhd0_loads():
    reg = load_schemas([REPO_SCHEMAS / "common"],
                       chip_schema_dir=REPO_SCHEMAS / "tc4zx")
    assert "BMHD0" in reg
    assert reg["BMHD0"].size == 0x100


def test_every_chip_has_several_schemas():
    for sub in ("tc4dx", "tc48x", "tc4zx"):
        reg = load_schemas([REPO_SCHEMAS / "common"],
                           chip_schema_dir=REPO_SCHEMAS / sub)
        # Each chip should produce at least 10 UCB schemas.
        assert len(reg) >= 10, f"{sub}: only {len(reg)} schemas"


def test_bmhd0_has_bootmode_and_stad():
    reg = load_schemas([REPO_SCHEMAS / "common"],
                       chip_schema_dir=REPO_SCHEMAS / "tc4dx")
    bmhd0 = reg["BMHD0"]
    props = bmhd0.schema["properties"]
    assert "STAD" in props
    # Boot-mode info lives either in a plain "BMI" field or a BMI_BMHDID
    # bitfield parent.
    assert "BMI" in props or "BMI_BMHDID" in props
