import pytest

from ucb_tool.core.field_codec import decode_int, encode_int


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
