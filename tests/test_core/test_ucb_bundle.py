from pathlib import Path

import pytest

from ucb_tool.core.errors import ValidationError
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


def test_bitfield_child_get_set(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x3000 + i: 0x00 for i in range(32)} | {0x3020 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)
    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    rich = bundle["RICH"]
    rich.set("FLAGS.PINDIS", 1)
    rich.set("FLAGS.HWCFG", 0b101)  # 5
    assert rich.get("FLAGS.PINDIS") == 1
    assert rich.get("FLAGS.HWCFG") == 0b101
    # Siblings must not collide: PINDIS at bit 0, HWCFG at bits 1..3 -> packed = 0b01011 = 11
    assert rich.get_copy("FLAGS.PINDIS") == 1
    assert rich.get_copy("FLAGS.HWCFG") == 0b101


def test_array_element_get_set(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x3000 + i: 0x00 for i in range(32)} | {0x3020 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)
    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    rich = bundle["RICH"]
    rich.set("KEY[0]", 0xDEADBEEF)
    rich.set("KEY[3]", 0x12345678)
    assert rich.get("KEY[0]") == 0xDEADBEEF
    assert rich.get("KEY[3]") == 0x12345678
    # ORIG/COPY mirrored
    assert rich.get_copy("KEY[0]") == 0xDEADBEEF


def test_unknown_path_raises(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x3000 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)
    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    with pytest.raises(KeyError):
        bundle["RICH"].get("DOES_NOT_EXIST")


def test_readonly_blocks_set_without_advanced(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x3000 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)
    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    with pytest.raises(ValidationError):
        bundle["RICH"].set("CRC_RO", 0xCAFEBABE)
    # With advanced mode the same write succeeds
    bundle["RICH"].advanced = True
    bundle["RICH"].set("CRC_RO", 0xCAFEBABE)
    assert bundle["RICH"].get("CRC_RO") == 0xCAFEBABE


def test_set_copy_requires_advanced(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0x3000 + i: 0x00 for i in range(32)} | {0x3020 + i: 0x00 for i in range(32)}
    write_hex(hex_path, data)
    bundle = UcbBundle.load(hex_path, chip_id="tc4d9",
                            common_dirs=[FIX / "common"],
                            chip_schema_dir=FIX / "tc4dx")
    with pytest.raises(ValidationError):
        bundle["RICH"].set_copy("KEY[0]", 0xDEADBEEF)


def test_save_recomputes_crc32(tmp_path):
    from tests.conftest import LEGACY_COMMON_DIR
    from ucb_tool.core.field_codec import crc32_aurix
    from ucb_tool.core.hex_io import read_hex, slice_range, write_hex

    hex_path = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(hex_path, data)

    bundle = UcbBundle.load(hex_path, "tc4d9",
                            common_dirs=[LEGACY_COMMON_DIR],
                            chip_schema_dir=None)
    bundle["BMHD_0"].set("STAD", 0x80000000)

    out = tmp_path / "out.hex"
    bundle.save(out, recompute=True)

    reloaded = read_hex(out)
    # BMHD_0 CRC at offset 248, 4 bytes, little-endian
    payload = slice_range(reloaded, 0xAF400000, 248)
    expected_crc = crc32_aurix(bytes(payload))
    actual_crc = int.from_bytes(slice_range(reloaded, 0xAF400000 + 248, 4), "little")
    assert actual_crc == expected_crc


def test_empty_ucb_has_present_false(tmp_path):
    """Load a hex covering only some UCBs — the rest must be marked not-present."""
    import ucb_tool
    from ucb_tool.core.hex_io import write_hex
    hex_path = tmp_path / "partial.hex"
    # Only BMHD0's 2 KB slot is populated; every other UCB is outside the hex.
    data = {0xAE404800 + i: 0x00 for i in range(2048)}
    for i, b in enumerate(b"\x00\x48\x40\xAE\x0F\x00\x59\xB3"):  # SAL+BMI magic
        data[0xAE404800 + i] = b
    write_hex(hex_path, data)

    SCHEMAS = Path(ucb_tool.__file__).parent / "schemas"
    bundle = UcbBundle.load(hex_path, "tc4d9",
                            common_dirs=[SCHEMAS / "common"],
                            chip_schema_dir=SCHEMAS / "tc4dx")

    # BMHD0 is in the hex → present
    assert bundle["BMHD0"].present is True
    # CHIPINFO_UCB0_00 was NOT in the hex → empty
    assert bundle["CHIPINFO_UCB0_00"].present is False
    # At least half the UCBs should be marked not-present
    not_present = sum(1 for i in bundle.instances.values() if not i.present)
    assert not_present >= len(bundle.instances) // 2


def test_save_skips_not_present_ucbs(tmp_path):
    """Absent UCBs must not leak 0xFF bytes into the saved hex."""
    import ucb_tool
    from ucb_tool.core.hex_io import read_hex, write_hex
    hex_path = tmp_path / "partial.hex"
    data = {0xAE404800 + i: 0x00 for i in range(2048)}  # only BMHD0
    write_hex(hex_path, data)

    SCHEMAS = Path(ucb_tool.__file__).parent / "schemas"
    bundle = UcbBundle.load(hex_path, "tc4d9",
                            common_dirs=[SCHEMAS / "common"],
                            chip_schema_dir=SCHEMAS / "tc4dx")

    out = tmp_path / "out.hex"
    bundle.save(out)
    reloaded = read_hex(out)
    # BMHD0 region should still be present
    assert 0xAE404800 in reloaded
    # CHIPINFO region (not present on input) must NOT be in the output
    assert 0xAE400000 not in reloaded


def test_export_ucb_single(tmp_path):
    """export_ucb() writes ONLY that UCB's bytes to its own hex file."""
    import ucb_tool
    from ucb_tool.core.hex_io import read_hex, write_hex
    hex_path = tmp_path / "partial.hex"
    data = {0xAE404800 + i: 0x00 for i in range(2048)}  # BMHD0
    data[0x80000000] = 0xAA  # unrelated flash byte we should NOT include
    write_hex(hex_path, data)

    SCHEMAS = Path(ucb_tool.__file__).parent / "schemas"
    bundle = UcbBundle.load(hex_path, "tc4d9",
                            common_dirs=[SCHEMAS / "common"],
                            chip_schema_dir=SCHEMAS / "tc4dx")

    out = tmp_path / "bmhd0.hex"
    bundle.export_ucb("BMHD0", out, recompute=False)
    reloaded = read_hex(out)
    # Exactly BMHD0's bytes (2048 B) should be present
    assert 0xAE404800 in reloaded
    # Nothing else
    assert 0x80000000 not in reloaded
    assert 0xAE400000 not in reloaded
