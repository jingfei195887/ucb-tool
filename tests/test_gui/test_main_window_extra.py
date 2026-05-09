import pytest

from tests.conftest import LEGACY_COMMON_DIR
from ucb_tool.core.hex_io import write_hex
from ucb_tool.gui.main_window import MainWindow


@pytest.fixture
def hex_file(tmp_path):
    hex_path = tmp_path / "u.hex"
    data = {0xAF400000 + i: 0xFF for i in range(256)}
    write_hex(hex_path, data)
    return hex_path


@pytest.fixture
def loaded_win(qtbot, qapp, hex_file):
    win = MainWindow()
    win._extra_common_dirs = [LEGACY_COMMON_DIR]
    qtbot.addWidget(win)
    win._source_path = hex_file
    win._current_chip = "tc4d9"
    win._bundle = win._load(str(hex_file), "tc4d9")
    win._populate_tree()
    win.action_save.setEnabled(True)
    return win


def test_populate_tree_fills_items(loaded_win):
    assert loaded_win.tree.topLevelItemCount() >= 1


def test_on_select_updates_form(qtbot, loaded_win):
    # Select the first tree item -> _on_select fires, form updated
    item = loaded_win.tree.topLevelItem(0)
    loaded_win.tree.setCurrentItem(item)
    # Form has rows after selection
    assert loaded_win.form.row_count() >= 1


def test_on_select_ignores_when_no_bundle(qtbot, qapp):
    win = MainWindow()
    qtbot.addWidget(win)
    # Directly invoke _on_select with None bundle — must be a no-op
    win._on_select(None, None)


def test_on_advanced_toggle_propagates(loaded_win):
    loaded_win.advanced_check.setChecked(True)
    for inst in loaded_win._bundle.instances.values():
        assert inst.advanced is True
    loaded_win.advanced_check.setChecked(False)
    for inst in loaded_win._bundle.instances.values():
        assert inst.advanced is False


def test_on_advanced_toggle_no_bundle(qtbot, qapp):
    win = MainWindow()
    qtbot.addWidget(win)
    # Should not raise when bundle is None
    win.advanced_check.setChecked(True)
    win.advanced_check.setChecked(False)


def test_on_open_cancelled(qtbot, qapp, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **kw: ("", "")),
    )
    win.on_open()
    assert win._bundle is None


def test_on_open_chip_dialog_cancelled(qtbot, qapp, hex_file, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **kw: (str(hex_file), "")),
    )
    # Chip picker rejected
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.ChipPickerDialog.exec",
        lambda self: int(self.DialogCode.Rejected),
    )
    win.on_open()
    assert win._bundle is None


def test_on_open_success(qtbot, qapp, hex_file, monkeypatch):
    win = MainWindow()
    win._extra_common_dirs = [LEGACY_COMMON_DIR]
    qtbot.addWidget(win)
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **kw: (str(hex_file), "")),
    )

    class FakeDlg:
        class DialogCode:
            Accepted = 1
            Rejected = 0

        def __init__(self, *a, **kw):
            self.chip_id = "tc4d9"

        def exec(self):
            return self.DialogCode.Accepted

    monkeypatch.setattr("ucb_tool.gui.main_window.ChipPickerDialog", FakeDlg)
    win.on_open()
    assert win._bundle is not None
    assert win._current_chip == "tc4d9"
    assert win.action_save.isEnabled() is True


def test_on_open_load_failure_shows_error(qtbot, qapp, hex_file, monkeypatch):
    win = MainWindow()
    qtbot.addWidget(win)
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **kw: (str(hex_file), "")),
    )

    class FakeDlg:
        class DialogCode:
            Accepted = 1
            Rejected = 0

        def __init__(self, *a, **kw):
            self.chip_id = "tc4d9"

        def exec(self):
            return self.DialogCode.Accepted

    monkeypatch.setattr("ucb_tool.gui.main_window.ChipPickerDialog", FakeDlg)

    # Force _load to raise
    def boom(self, path, chip):
        raise RuntimeError("boom")

    monkeypatch.setattr(MainWindow, "_load", boom)

    # Silence QMessageBox.critical
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QMessageBox.critical",
        staticmethod(lambda *a, **kw: 0),
    )
    win.on_open()
    assert win._bundle is None


def test_on_save_guard_when_empty(qtbot, qapp):
    win = MainWindow()
    qtbot.addWidget(win)
    # No bundle loaded -> early return, no crash
    win.on_save()


def test_on_save_cancelled_filesave(loaded_win, monkeypatch):
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **kw: ("", "")),
    )
    # No danger changes with an unmodified bundle — save path flows to dialog, user cancels
    loaded_win.on_save()


def test_on_save_writes_file(loaded_win, tmp_path, monkeypatch):
    out = tmp_path / "saved.hex"
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getSaveFileName",
        staticmethod(lambda *a, **kw: (str(out), "")),
    )
    loaded_win.on_save()
    assert out.exists()


def test_on_apply_xlsx_guard_when_empty(qtbot, qapp):
    win = MainWindow()
    qtbot.addWidget(win)
    win.on_apply_xlsx()  # early return, no crash


def test_on_apply_xlsx_cancelled_filedialog(loaded_win, monkeypatch):
    monkeypatch.setattr(
        "ucb_tool.gui.main_window.QFileDialog.getOpenFileName",
        staticmethod(lambda *a, **kw: ("", "")),
    )
    loaded_win.on_apply_xlsx()  # early return after cancel
