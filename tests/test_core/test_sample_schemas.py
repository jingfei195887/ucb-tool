from pathlib import Path

import ucb_tool
from ucb_tool.core.schema_loader import load_schemas

REPO_SCHEMAS = Path(ucb_tool.__file__).parent / "schemas"


def test_common_BMHD_0_loads():
    reg = load_schemas([REPO_SCHEMAS / "common"], chip_schema_dir=None)
    assert "BMHD_0" in reg
    assert reg["BMHD_0"].size == 256


def test_common_BMHD_0_addresses_all_families():
    reg = load_schemas([REPO_SCHEMAS / "common"], chip_schema_dir=None)
    schema = reg["BMHD_0"]
    for fam in ("TC4Dx", "TC48x", "TC4Zx"):
        orig, copy = schema.address_for_family(fam)
        assert orig == 0xAF400000
        assert copy is None  # has_orig_copy: false


def test_swap_addresses_resolved(tmp_path):
    from ucb_tool.core.hex_io import write_hex
    from ucb_tool.core.ucb_bundle import UcbBundle

    hex_path = tmp_path / "u.hex"
    write_hex(hex_path, {0: 0xFF})
    bundle = UcbBundle.load(hex_path, "tc4d9",
                            common_dirs=[REPO_SCHEMAS / "common"],
                            chip_schema_dir=None)
    assert "SWAP" in bundle.instances
    inst = bundle.instances["SWAP"]
    # TC4Dx RTC SWAP ORIG = 0xAE400000 + 19 * 0x800 = 0xAE409800
    assert inst.orig_addr == 0xAE400000 + 19 * 0x800
    assert inst.copy_addr == 0xAE400000 + 20 * 0x800
