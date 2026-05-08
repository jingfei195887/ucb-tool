import json
from pathlib import Path

import pytest

from ucb_tool.core.errors import SchemaError
from ucb_tool.core.schema_loader import load_schemas

FIX = Path(__file__).parent / "fixtures_schemas"


def test_load_common_only():
    reg = load_schemas([FIX / "common"], chip_schema_dir=None)
    assert "DEMO" in reg
    assert reg["DEMO"].meta["size"] == 32


def test_chip_overrides_common():
    reg = load_schemas([FIX / "common"], chip_schema_dir=FIX / "tc4dx")
    # tc4dx DEMO adds a new field CHIP_EXTRA and overrides BASE_FIELD.title
    schema = reg["DEMO"].schema
    assert "CHIP_EXTRA" in schema["properties"]
    assert schema["properties"]["BASE_FIELD"]["title"] == "overridden"


def test_missing_ucb_meta_raises(tmp_path: Path):
    bad = tmp_path / "BAD.json"
    bad.write_text(json.dumps({"$id": "ucb://common/BAD", "type": "object"}))
    with pytest.raises(SchemaError):
        load_schemas([tmp_path], chip_schema_dir=None)


def test_address_lookup_per_family():
    reg = load_schemas([FIX / "common"], chip_schema_dir=None)
    demo = reg["DEMO"]
    assert demo.address_for_family("TC4Dx") == (0x1000, 0x1020)
    with pytest.raises(KeyError):
        demo.address_for_family("UNKNOWN")
