import pytest

from ucb_tool.core.field_codec import (
    ConfirmationState,
    confirmation_magic,
    crc32_aurix,
    decode_int,
    detect_confirmation,
    encode_int,
    pack_bitfield,
    unpack_bitfield,
)


@pytest.mark.parametrize("value, size, endian, expected", [
    (0x5A,        1, "little", b"\x5a"),
    (0x1234,      2, "little", b"\x34\x12"),
    (0x1234,      2, "big",    b"\x12\x34"),
    (0x80000000,  4, "little", b"\x00\x00\x00\x80"),
    (0xDEADBEEF,  4, "little", b"\xef\xbe\xad\xde"),
    (0xDEADBEEF,  4, "big",    b"\xde\xad\xbe\xef"),
])
def test_encode_int(value, size, endian, expected):
    assert encode_int(value, size, endian) == expected


def test_encode_int_overflow_raises():
    with pytest.raises(ValueError):
        encode_int(0x1_0000, 2, "little")
    with pytest.raises(ValueError):
        encode_int(-1, 1, "little")


def test_decode_int_roundtrip():
    for v in (0, 1, 0xFF, 0x1234, 0xDEADBEEF):
        size = 4 if v > 0xFFFF else 2 if v > 0xFF else 1
        enc = encode_int(v, size, "little")
        assert decode_int(enc, "little") == v


def test_pack_single_bit_boolean():
    # PINDIS at bit [0,0]
    assert pack_bitfield({"PINDIS": True}, {"PINDIS": (0, 0)}) == 0b1
    assert pack_bitfield({"PINDIS": False}, {"PINDIS": (0, 0)}) == 0b0


def test_pack_multi_field():
    # PINDIS=bit 0, HWCFG=bits 1..3
    layout = {"PINDIS": (0, 0), "HWCFG": (1, 3)}
    assert pack_bitfield({"PINDIS": True, "HWCFG": 0b101}, layout) == 0b01011
    assert pack_bitfield({"PINDIS": False, "HWCFG": 0b111}, layout) == 0b1110


def test_unpack_inverse():
    # unpack returns raw ints; caller handles type coercion.
    layout = {"PINDIS": (0, 0), "HWCFG": (1, 3)}
    packed = pack_bitfield({"PINDIS": True, "HWCFG": 0b101}, layout)
    assert unpack_bitfield(packed, layout) == {"PINDIS": 1, "HWCFG": 0b101}


def test_value_exceeds_range_raises():
    layout = {"HWCFG": (1, 3)}
    with pytest.raises(ValueError):
        pack_bitfield({"HWCFG": 0b1000}, layout)  # 8 doesn't fit in 3 bits


def test_crc32_ieee_vector_123456789():
    # Standard CRC-32/IEEE 802.3 test vector
    assert crc32_aurix(b"123456789") == 0xCBF43926


def test_crc32_empty():
    # init 0xFFFFFFFF XOR final 0xFFFFFFFF = 0
    assert crc32_aurix(b"") == 0x00000000


def test_crc32_single_zero():
    # CRC-32/IEEE of b"\x00" = 0xD202EF8D
    assert crc32_aurix(b"\x00") == 0xD202EF8D


def test_magic_lengths_are_8_bytes():
    for state in ConfirmationState:
        assert len(confirmation_magic(state)) == 8


def test_unlocked_magic_matches_real_ucb_dump():
    # Verified against a real TC4Dx UNLOCKED UCB dump: bytes 0x7F0..0x7F7
    # in every UCB slot contain 34 12 21 43 00 00 00 00 (LE 0x43211234).
    assert confirmation_magic(ConfirmationState.UNLOCKED) == \
        b"\x34\x12\x21\x43\x00\x00\x00\x00"


def test_confirmed_magic_is_0x57B5327F():
    # Per user: the CONFIRMED state magic is 0x57B5327F
    # (bytes 7F 32 B5 57 00 00 00 00, little-endian).
    assert confirmation_magic(ConfirmationState.CONFIRMED) == \
        b"\x7f\x32\xb5\x57\x00\x00\x00\x00"


def test_detect_unlocked_from_real_bytes():
    assert detect_confirmation(b"\x34\x12\x21\x43\x00\x00\x00\x00") == \
        ConfirmationState.UNLOCKED


def test_detect_confirmed_from_real_bytes():
    assert detect_confirmation(b"\x7f\x32\xb5\x57\x00\x00\x00\x00") == \
        ConfirmationState.CONFIRMED


def test_detect_anything_else_is_errored():
    # Virgin flash
    assert detect_confirmation(b"\xff" * 8) == ConfirmationState.ERRORED
    # All zeros
    assert detect_confirmation(b"\x00" * 8) == ConfirmationState.ERRORED
    # Near-miss (last byte differs from UNLOCKED)
    assert detect_confirmation(b"\x34\x12\x21\x43\x00\x00\x00\x01") == \
        ConfirmationState.ERRORED
    # Byte-swapped UNLOCKED
    assert detect_confirmation(b"\x43\x21\x34\x12\x00\x00\x00\x00") == \
        ConfirmationState.ERRORED


def test_detect_roundtrip():
    for state in ConfirmationState:
        blob = confirmation_magic(state)
        assert detect_confirmation(blob) == state
