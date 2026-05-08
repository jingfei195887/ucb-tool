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
