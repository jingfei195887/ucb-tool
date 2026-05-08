import pytest
from pathlib import Path
from ucb_tool.core.hex_io import read_hex, write_hex, slice_range, merge_range
from ucb_tool.core.errors import HexParseError


def test_roundtrip_tiny(tmp_path: Path):
    src = tmp_path / "in.hex"
    # Intel HEX: one data record at 0x0100 = "DE AD BE EF"
    src.write_text(
        ":020000040000FA\n"
        ":04010000DEADBEEFC3\n"
        ":00000001FF\n"
    )
    data = read_hex(src)
    assert data[0x0100] == 0xDE
    assert data[0x0101] == 0xAD
    assert data[0x0102] == 0xBE
    assert data[0x0103] == 0xEF

    out = tmp_path / "out.hex"
    write_hex(out, data)
    data2 = read_hex(out)
    assert data == data2


def test_high_address_uses_ela(tmp_path: Path):
    out = tmp_path / "out.hex"
    write_hex(out, {0xAF400000: 0x5A, 0xAF400001: 0xA5})
    data = read_hex(out)
    assert data[0xAF400000] == 0x5A
    assert data[0xAF400001] == 0xA5


def test_malformed_raises(tmp_path: Path):
    src = tmp_path / "bad.hex"
    src.write_text("not a hex file\n")
    with pytest.raises(HexParseError):
        read_hex(src)


def test_read_range_slice(tmp_path: Path):
    src = tmp_path / "in.hex"
    src.write_text(
        ":020000040000FA\n"
        ":10000000000102030405060708090A0B0C0D0E0F78\n"
        ":00000001FF\n"
    )
    data = read_hex(src)
    chunk = slice_range(data, 0x0004, 4)
    assert chunk == bytes([0x04, 0x05, 0x06, 0x07])


def test_slice_range_fills_missing_with_ff():
    data = {0x100: 0xAA, 0x101: 0xBB}  # no 0x102, 0x103
    assert slice_range(data, 0x100, 4) == bytes([0xAA, 0xBB, 0xFF, 0xFF])


def test_merge_range_writes_blob():
    data: dict[int, int] = {}
    merge_range(data, 0x100, b"\x11\x22\x33")
    assert data == {0x100: 0x11, 0x101: 0x22, 0x102: 0x33}
