import pytest
from ucb_tool.core.chip_profile import (
    ChipFamily, get_profile, ucb_address, list_chips,
)


def test_list_chips_nonempty():
    chips = list_chips()
    assert {"tc4d9", "tc4d7", "tc489", "tc4z9"} <= set(chips)


def test_tc4d9_userorig_at_correct_slot():
    # TC4Dx RTC USERCFG ORIG = slot 17, stride 0x800, base 0xAE400000
    addr = ucb_address("tc4d9", "USERCFG_ORIG_RTC")
    assert addr == 0xAE400000 + 17 * 0x800


def test_tc489_userorig_at_correct_slot():
    # TC48x RTC USERCFG ORIG = slot 2, stride 0x100
    addr = ucb_address("tc489", "USERCFG_ORIG_RTC")
    assert addr == 0xAE400000 + 2 * 0x100


def test_tc4d9_swap_orig_cs():
    # TC4Dx CS SWAP ORIG = slot 12, stride 0x800, CS base 0xAEC00000
    addr = ucb_address("tc4d9", "SWAP_ORIG_CS")
    assert addr == 0xAEC00000 + 12 * 0x800


def test_unknown_chip_raises():
    with pytest.raises(KeyError):
        ucb_address("stm32", "BMHD_0")


def test_family_of():
    p = get_profile("tc4d9")
    assert p.family == ChipFamily.TC4DX
    p = get_profile("tc489")
    assert p.family == ChipFamily.TC48X
