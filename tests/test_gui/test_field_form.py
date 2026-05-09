import pytest

from tests.conftest import LEGACY_COMMON_DIR
from ucb_tool.core.hex_io import write_hex
from ucb_tool.core.ucb_bundle import UcbBundle
from ucb_tool.gui.views.field_form import FieldForm


@pytest.fixture
def bmhd_inst(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(hex_path, data)
    bundle = UcbBundle.load(hex_path, "tc4d9",
                            common_dirs=[LEGACY_COMMON_DIR],
                            chip_schema_dir=None)
    return bundle["BMHD_0"]


def test_form_has_row_per_leaf_field(qtbot, qapp, bmhd_inst):
    form = FieldForm()
    form.set_instance(bmhd_inst)
    qtbot.addWidget(form)
    assert form.row_count() >= 3


def test_editing_value_writes_back(qtbot, qapp, bmhd_inst):
    form = FieldForm()
    form.set_instance(bmhd_inst)
    qtbot.addWidget(form)
    form.set_value("STAD", 0x80000000)
    assert bmhd_inst.get("STAD") == 0x80000000


def test_enum_dropdown_sets_underlying_int(qtbot, qapp, bmhd_inst):
    form = FieldForm()
    form.set_instance(bmhd_inst)
    qtbot.addWidget(form)
    form.set_value("BMI.HWCFG", 3)
    assert bmhd_inst.get("BMI.HWCFG") == 3
