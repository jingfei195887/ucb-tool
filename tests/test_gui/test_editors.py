from PySide6.QtWidgets import QLineEdit

from ucb_tool.gui.widgets.editors import (
    BoolCheck,
    EnumCombo,
    HexIntEdit,
    PasswordEdit,
)


def test_hex_int_edit_set_get(qtbot, qapp):
    w = HexIntEdit(max_bits=32)
    qtbot.addWidget(w)
    w.set_value(0xDEADBEEF)
    assert "DEADBEEF" in w.edit.text().upper()


def test_hex_int_edit_emits_on_valid(qtbot, qapp):
    w = HexIntEdit(max_bits=32)
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.edit.setText("0x10")
    w._emit()
    assert captured == [0x10]


def test_hex_int_edit_rejects_out_of_range(qtbot, qapp):
    w = HexIntEdit(max_bits=8)
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.edit.setText("0x100")  # 256 > max 255
    w._emit()
    assert captured == []  # rejected


def test_hex_int_edit_ignores_empty(qtbot, qapp):
    w = HexIntEdit(max_bits=32)
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.edit.setText("")
    w._emit()
    assert captured == []


def test_hex_int_edit_ignores_invalid(qtbot, qapp):
    w = HexIntEdit(max_bits=32)
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.edit.setText("zzz")
    w._emit()
    assert captured == []


def test_password_edit_toggle_echo(qtbot, qapp):
    w = PasswordEdit()
    qtbot.addWidget(w)
    assert w.edit.echoMode() == QLineEdit.EchoMode.Password
    w.btn.setChecked(True)
    assert w.edit.echoMode() == QLineEdit.EchoMode.Normal
    w.btn.setChecked(False)
    assert w.edit.echoMode() == QLineEdit.EchoMode.Password


def test_password_edit_emits_on_valid(qtbot, qapp):
    w = PasswordEdit()
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.set_value(0xCAFE)
    w._emit()
    assert captured == [0xCAFE]


def test_password_edit_set_value_hex_format(qtbot, qapp):
    w = PasswordEdit()
    qtbot.addWidget(w)
    w.set_value(0xABCD)
    assert w.edit.text().upper() == "ABCD"


def test_enum_combo_set_value(qtbot, qapp):
    w = EnumCombo({0: "zero", 1: "one", 3: "three"})
    qtbot.addWidget(w)
    w.set_value(3)
    assert w.currentIndex() == 2


def test_enum_combo_emits_on_change(qtbot, qapp):
    w = EnumCombo({0: "zero", 1: "one", 3: "three"})
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.setCurrentIndex(1)
    assert captured == [1]


def test_enum_combo_unknown_value_is_noop(qtbot, qapp):
    w = EnumCombo({0: "zero", 1: "one"})
    qtbot.addWidget(w)
    w.setCurrentIndex(0)
    w.set_value(999)  # not in mapping — no crash, index unchanged
    assert w.currentIndex() == 0


def test_bool_check_set_value(qtbot, qapp):
    w = BoolCheck()
    qtbot.addWidget(w)
    w.set_value(1)
    assert w.isChecked() is True
    w.set_value(0)
    assert w.isChecked() is False


def test_bool_check_emits_on_toggle(qtbot, qapp):
    w = BoolCheck()
    qtbot.addWidget(w)
    captured = []
    w.valueChanged.connect(captured.append)
    w.setChecked(True)
    assert captured == [1]
    w.setChecked(False)
    assert captured == [1, 0]
