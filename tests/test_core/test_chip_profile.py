import pytest

from ucb_tool.core.chip_profile import (
    UCB0_BASE,
    UCB1_BASE,
    ChipFamily,
    ChipProfile,
    get_profile,
    list_chips,
    ucb_address,
)


def test_list_chips_nonempty():
    chips = list_chips()
    assert {"tc4d9", "tc4d7", "tc489", "tc4z9"} <= set(chips)


def test_family_of():
    p = get_profile("tc4d9")
    assert p.family == ChipFamily.TC4DX
    p = get_profile("tc489")
    assert p.family == ChipFamily.TC48X
    p = get_profile("tc4z9")
    assert p.family == ChipFamily.TC4ZX


def test_profile_stride_and_schema_dir():
    p = get_profile("tc4d9")
    assert p.stride == 0x800
    assert p.schema_dir == "tc4dx"

    p = get_profile("tc489")
    assert p.stride == 0x100
    assert p.schema_dir == "tc48x"


def test_region_bases():
    assert UCB0_BASE == 0xAE400000
    assert UCB1_BASE == 0xAEC00000


def test_unknown_chip_raises():
    with pytest.raises(KeyError):
        get_profile("stm32")


def test_ucb_address_is_deprecated():
    # The old position-based lookup is gone — addresses now live in each
    # schema's x-ucb-meta.addresses. ucb_address() must still raise
    # KeyError on both unknown chips and any UCB-name lookup.
    with pytest.raises(KeyError):
        ucb_address("stm32", "BMHD0")
    with pytest.raises(KeyError):
        ucb_address("tc4d9", "BMHD0")


def test_chip_profile_dataclass_fields():
    # slots kept for backward compat; default empty.
    p = ChipProfile(chip_id="tc4d9", family=ChipFamily.TC4DX,
                    stride=0x800, schema_dir="tc4dx")
    assert p.slots == {}
