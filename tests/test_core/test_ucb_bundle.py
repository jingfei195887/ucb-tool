from pathlib import Path

from ucb_tool.core.hex_io import read_hex, slice_range, write_hex
from ucb_tool.core.ucb_bundle import FieldPath, UcbBundle

FIX = Path(__file__).parent / "fixtures_schemas"


def test_load_bundle_from_hex_and_schemas(tmp_path):
    hex_path = tmp_path / "u.hex"
    # DEMO.orig=0x1000, copy=0x1020, size=32
    data: dict[int, int] = {}
    for i in range(32):
        data[0x1000 + i] = 0xAA
        data[0x1020 + i] = 0xAA
    # BASE_FIELD @ offset 0 (4 bytes, little-endian) = 0xDEADBEEF
    for i, b in enumerate(b"\xef\xbe\xad\xde"):
        data[0x1000 + i] = b
        data[0x1020 + i] = b
    write_hex(hex_path, data)

    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    assert "DEMO" in bundle.instances
    demo = bundle["DEMO"]
    assert demo.get("BASE_FIELD") == 0xDEADBEEF


def test_set_mirrors_orig_to_copy(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x1000 + i: 0x00 for i in range(32)} | {0x1020 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)

    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    demo = bundle["DEMO"]
    demo.set("BASE_FIELD", 0x12345678)
    assert demo.get("BASE_FIELD") == 0x12345678
    assert demo.get_copy("BASE_FIELD") == 0x12345678


def test_advanced_mode_allows_copy_divergence(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x1000 + i: 0x00 for i in range(32)} | {0x1020 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)

    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    demo = bundle["DEMO"]
    demo.advanced = True
    demo.set("BASE_FIELD", 0x11111111)
    demo.set_copy("BASE_FIELD", 0x22222222)
    assert demo.get("BASE_FIELD") == 0x11111111
    assert demo.get_copy("BASE_FIELD") == 0x22222222


def test_save_round_trips(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x1000 + i: 0x00 for i in range(32)} | {0x1020 + i: 0x00 for i in range(32)}
    data[0x4000] = 0x5A
    data[0x4001] = 0xA5
    write_hex(hex_path, data)

    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    bundle["DEMO"].set("BASE_FIELD", 0xCAFEBABE)
    out = tmp_path / "out.hex"
    bundle.save(out)

    reloaded = read_hex(out)
    assert slice_range(reloaded, 0x1000, 4) == b"\xbe\xba\xfe\xca"
    assert slice_range(reloaded, 0x1020, 4) == b"\xbe\xba\xfe\xca"
    # Non-UCB bytes preserved
    assert reloaded[0x4000] == 0x5A
    assert reloaded[0x4001] == 0xA5


def test_fieldpath_array_syntax():
    p = FieldPath.parse("PASSWORD[3]")
    assert p.parts == ["PASSWORD"]
    assert p.index == 3
    p2 = FieldPath.parse("BMI.HWCFG")
    assert p2.parts == ["BMI", "HWCFG"]
    assert p2.index is None
