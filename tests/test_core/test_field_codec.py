import pytest

from ucb_tool.core.field_codec import (
    crc32_aurix,
    decode_int,
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
